# mypy: disable-error-code="no-untyped-def,no-untyped-call,arg-type"

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from quant.application import PaperPromotionError, PaperPromotionService
from quant.domain import (
    AdjustmentPolicy,
    DatasetSnapshot,
    Experiment,
    ExperimentRun,
    ExperimentRunStatus,
    ExperimentStatus,
    GateDecision,
    HistoricalDataset,
    MarketBar,
    PaperPromotionStatus,
    StrategyVersion,
    ValidationGateResult,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)


class Promotions:
    def __init__(self):
        self.items = {}

    def add(self, value):
        self.items[value.id] = value

    save = add

    def get(self, identity):
        return self.items.get(identity)

    def list_all(self):
        return tuple(self.items.values())

    def get_for_lineage(self, run_id, version_id, gate_id):
        return next(
            (
                x
                for x in self.items.values()
                if (x.experiment_run_id, x.strategy_version_id, x.validation_gate_id)
                == (run_id, version_id, gate_id)
            ),
            None,
        )


class Experiments:
    def __init__(self, experiment, run):
        self.experiment, self.run = experiment, run

    def get(self, identity):
        return self.experiment if self.experiment.id == identity else None

    def get_run(self, identity):
        return self.run if self.run.id == identity else None


class Gates:
    def __init__(self, gate=None):
        self.gate = gate

    def get(self, identity):
        return self.gate if self.gate and self.gate.id == identity else None

    def list_for_run(self, run_id):
        return (
            (self.gate,) if self.gate and self.gate.experiment_run_id == run_id else ()
        )


class Strategies:
    def __init__(self, version):
        self.version = version

    def get_version(self, identity):
        return self.version if self.version.id == identity else None


class Datasets:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def get(self, identity):
        return self.snapshot if self.snapshot.id == identity else None


def fixture(decision=GateDecision.PASS):
    version = StrategyVersion(
        uuid4(),
        uuid4(),
        "v1",
        "abc",
        "moving_average_trend",
        {"short_window": 2, "long_window": 3},
        NOW,
    )
    snapshot = DatasetSnapshot(
        uuid4(),
        "fixture",
        "US_EQUITIES",
        "SPY",
        "1D",
        NOW,
        NOW + timedelta(days=1),
        "v1",
        "sha256:test",
        "test/bars.parquet",
        AdjustmentPolicy.RAW,
        NOW,
    )
    experiment = Experiment(
        uuid4(), uuid4(), version.id, snapshot.id, ExperimentStatus.COMPLETED, NOW
    )
    run = ExperimentRun(
        uuid4(),
        experiment.id,
        "abc",
        "backtest-engine-v1",
        "zero",
        "zero",
        {},
        NOW,
        NOW,
        ExperimentRunStatus.COMPLETED,
    )
    gate = ValidationGateResult(
        uuid4(),
        run.id,
        version.id,
        "HISTORICAL_TO_PAPER",
        1,
        decision,
        (),
        {},
        {},
        "validation-gate-v1",
        NOW,
        "gate-fp",
    )
    dataset = HistoricalDataset.from_bars(
        market="US_EQUITIES",
        instrument="SPY",
        timeframe="1D",
        adjustment_policy=AdjustmentPolicy.RAW,
        bars=(
            MarketBar(
                NOW,
                Decimal("1"),
                Decimal("1"),
                Decimal("1"),
                Decimal("1"),
                Decimal("1"),
            ),
            MarketBar(
                NOW + timedelta(days=1),
                Decimal("1"),
                Decimal("1"),
                Decimal("1"),
                Decimal("1"),
                Decimal("1"),
            ),
        ),
    )
    promotions = Promotions()
    service = PaperPromotionService(
        promotions,
        Experiments(experiment, run),
        Gates(gate),
        Strategies(version),
        Datasets(snapshot),
        lambda _: dataset,
    )
    return service, promotions, experiment, run, gate, version, snapshot


def test_gate_fail_and_missing_gate_cannot_promote():
    service, _, _, run, gate, _, _ = fixture(GateDecision.FAIL)
    assert not service.eligibility(run.id, gate.id).eligible
    with pytest.raises(PaperPromotionError):
        service.approve(run.id, gate.id, confirm=True, reason="no")
    service = replace(service, gates=Gates())
    assert not service.eligibility(run.id).eligible


def test_gate_for_another_run_and_confirmation_fail_closed():
    service, _, _, run, gate, _, _ = fixture()
    other = replace(gate, experiment_run_id=uuid4())
    service = replace(service, gates=Gates(other))
    assert not service.eligibility(run.id, other.id).eligible
    with pytest.raises(PaperPromotionError, match="confirmation"):
        service.approve(run.id, other.id, confirm=False, reason="no")


def test_pass_persists_exact_lineage_is_idempotent_and_revocable():
    service, promotions, experiment, run, gate, version, snapshot = fixture()
    assert service.eligibility(run.id, gate.id).eligible
    approved = service.approve(run.id, gate.id, confirm=True, reason="forward only")
    duplicate = service.approve(
        run.id, gate.id, confirm=True, reason="ignored duplicate"
    )
    assert duplicate.id == approved.id
    assert len(promotions.items) == 1
    assert (
        approved.hypothesis_id,
        approved.strategy_version_id,
        approved.experiment_id,
        approved.experiment_run_id,
        approved.validation_gate_id,
        approved.dataset_snapshot_id,
    ) == (
        experiment.hypothesis_id,
        version.id,
        experiment.id,
        run.id,
        gate.id,
        snapshot.id,
    )
    revoked = service.revoke(approved.id, confirm=True, reason="operator stop")
    assert revoked.status is PaperPromotionStatus.REVOKED
    assert gate.decision is GateDecision.PASS
    with pytest.raises(PaperPromotionError, match="new gate"):
        service.approve(run.id, gate.id, confirm=True, reason="cannot overwrite")


def test_invalidated_dataset_evidence_is_not_eligible():
    service, _, _, run, gate, _, _ = fixture()
    service = replace(
        service,
        load_dataset=lambda _: (_ for _ in ()).throw(ValueError("checksum mismatch")),
    )
    result = service.eligibility(run.id, gate.id)
    assert not result.eligible
    assert "checksum mismatch" in result.reason
