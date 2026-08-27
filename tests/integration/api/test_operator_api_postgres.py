from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from apps.api.dependencies import get_operator_queries, get_research_workflow
from apps.api.main import app
from infra.market_data import LocalParquetDatasetStorage
from infra.persistence.repositories import (
    SQLAlchemyDatasetRepository,
    SQLAlchemyExperimentRepository,
    SQLAlchemyGateRepository,
    SQLAlchemyHypothesisRepository,
    SQLAlchemyKnowledgeRepository,
    SQLAlchemyStrategyRepository,
)
from quant.application import (
    LoadDatasetSnapshot,
    OperatorQueries,
    OperatorResearchWorkflow,
    canonical_bars_checksum,
)
from quant.domain import (
    AdjustmentPolicy,
    DatasetSnapshot,
    EvidenceKind,
    EvidenceReference,
    Experiment,
    ExperimentRun,
    ExperimentRunStatus,
    ExperimentStatus,
    GateDecision,
    GateRuleOutcome,
    GateRuleResult,
    Hypothesis,
    HypothesisStatus,
    KnowledgeRecord,
    MarketBar,
    MetricSet,
    ReconsiderationCondition,
    ResearchSignature,
    Strategy,
    StrategyVersion,
    ValidationGateResult,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.knowledge import research_fingerprint

pytestmark = pytest.mark.integration
NOW = datetime(2026, 8, 15, 12, tzinfo=UTC)


def test_operator_can_create_and_run_complete_research_lineage(
    postgres_session: Session, tmp_path: Path
) -> None:
    hypotheses = SQLAlchemyHypothesisRepository(postgres_session)
    strategies = SQLAlchemyStrategyRepository(postgres_session)
    datasets = SQLAlchemyDatasetRepository(postgres_session)
    experiments = SQLAlchemyExperimentRepository(postgres_session)
    gates = SQLAlchemyGateRepository(postgres_session)
    knowledge = SQLAlchemyKnowledgeRepository(postgres_session)
    storage = LocalParquetDatasetStorage(tmp_path)
    bars = tuple(
        MarketBar(
            NOW + timedelta(days=index),
            Decimal(100 + index),
            Decimal(102 + index),
            Decimal(99 + index),
            Decimal(101 + index),
            Decimal(1_000),
        )
        for index in range(8)
    )
    snapshot_id = uuid4()
    snapshot = DatasetSnapshot(
        snapshot_id,
        "fixture",
        "US_EQUITIES",
        "SPY",
        "1Day",
        bars[0].timestamp,
        bars[-1].timestamp + timedelta(microseconds=1),
        "ohlcv-v1",
        canonical_bars_checksum(bars),
        storage.write(snapshot_id, bars),
        AdjustmentPolicy.RAW,
        NOW,
    )
    datasets.add(snapshot)
    workflow = OperatorResearchWorkflow(
        hypotheses,
        knowledge,
        strategies,
        datasets,
        experiments,
        LoadDatasetSnapshot(storage, datasets),
    )
    queries = OperatorQueries(
        hypotheses, strategies, datasets, experiments, gates, knowledge
    )
    app.dependency_overrides[get_research_workflow] = lambda: workflow
    app.dependency_overrides[get_operator_queries] = lambda: queries
    try:
        with TestClient(app) as client:
            hypothesis_request = {
                    "title": "SPY daily trend",
                    "description": "Test a daily moving-average trend rule.",
                    "rationale": "Persistent trends may survive costs.",
                    "strategy_family": "moving_average_trend",
                    "market": "US_EQUITIES",
                    "instrument": "SPY",
                    "timeframe": "1Day",
                    "parameters": {"short_window": 2, "long_window": 3},
                    "expected_benefit": "Transparent trend exposure",
                    "expected_tradeoff": "Whipsaw losses",
                    "success_criteria": "Reproducible positive evidence",
                    "rejection_criteria": "No robust evidence",
            }
            hypothesis_response = client.post(
                "/api/v1/hypotheses", json=hypothesis_request
            )
            assert hypothesis_response.status_code == 201
            duplicate = client.post("/api/v1/hypotheses", json=hypothesis_request)
            assert duplicate.status_code == 409
            hypothesis_id = hypothesis_response.json()["id"]

            version_response = client.post(
                "/api/v1/strategy-versions",
                json={
                    "name": "MA Trend",
                    "description": "Daily moving-average trend",
                    "strategy_family": "moving_average_trend",
                    "version": "v1",
                    "git_commit": "api-test",
                    "algorithm_key": "moving_average_trend",
                    "parameters": {"short_window": 2, "long_window": 3},
                },
            )
            assert version_response.status_code == 201
            version_id = version_response.json()["strategy_version_id"]
            experiment_response = client.post(
                "/api/v1/experiments",
                json={
                    "hypothesis_id": hypothesis_id,
                    "strategy_version_id": version_id,
                    "dataset_snapshot_id": str(snapshot.id),
                },
            )
            assert experiment_response.status_code == 201
            experiment_id = experiment_response.json()["experiment_id"]
            run_response = client.post(
                f"/api/v1/experiments/{experiment_id}/runs",
                json={
                    "initial_cash": "10000",
                    "position_fraction": "1",
                    "fee": {"model": "percentage", "rate": "0.001"},
                    "slippage": {"model": "basis_points", "basis_points": "10"},
                    "periods_per_year": 252,
                    "annual_risk_free_rate": "0",
                },
            )
            assert run_response.status_code == 201
            payload = run_response.json()
            assert payload["status"] == "completed"
            assert payload["result_fingerprint"]
            assert len(payload["validation_ids"]) == 1
            assert client.get(
                f"/api/v1/experiment-runs/{payload['experiment_run_id']}"
            ).status_code == 200
            validations = client.get(
                f"/api/v1/experiment-runs/{payload['experiment_run_id']}/validations"
            ).json()
            assert [item["validation_type"] for item in validations] == ["backtest"]
    finally:
        app.dependency_overrides.clear()


def test_complete_research_evidence_is_observable_over_http(
    postgres_session: Session,
) -> None:
    hypotheses = SQLAlchemyHypothesisRepository(postgres_session)
    strategies = SQLAlchemyStrategyRepository(postgres_session)
    datasets = SQLAlchemyDatasetRepository(postgres_session)
    experiments = SQLAlchemyExperimentRepository(postgres_session)
    gates = SQLAlchemyGateRepository(postgres_session)
    knowledge = SQLAlchemyKnowledgeRepository(postgres_session)
    hypothesis = Hypothesis(
        uuid4(),
        "API fixture",
        "Complete observable evidence",
        "Rationale",
        "trend",
        "US_EQUITIES",
        "1D",
        "Benefit",
        "Tradeoff",
        "Success",
        "Reject",
        HypothesisStatus.REJECTED,
        "New market",
        NOW,
    )
    strategy = Strategy(uuid4(), "MA Trend", "Strategy", "trend", NOW)
    version = StrategyVersion(
        uuid4(),
        strategy.id,
        "v1",
        "abc123",
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
        NOW - timedelta(days=30),
        NOW,
        "v1",
        "sha256-api",
        "private/bars.parquet",
        AdjustmentPolicy.RAW,
        NOW,
    )
    experiment = Experiment(
        uuid4(), hypothesis.id, version.id, snapshot.id, ExperimentStatus.COMPLETED, NOW
    )
    run = ExperimentRun(
        uuid4(),
        experiment.id,
        "abc123",
        "backtest-engine-v1",
        "percentage-fee-v1",
        "bps-slippage-v1",
        {"analytics": {"version": "metrics-v1"}, "result_fingerprint": "run-api"},
        NOW,
        NOW,
        ExperimentRunStatus.COMPLETED,
    )
    hypotheses.add(hypothesis)
    strategies.add(strategy)
    strategies.add_version(version)
    datasets.add(snapshot)
    experiments.add(experiment)
    experiments.add_run(run)
    validations: list[ValidationRun] = []
    for index, validation_type in enumerate(
        (
            ValidationType.BACKTEST,
            ValidationType.OUT_OF_SAMPLE,
            ValidationType.WALK_FORWARD,
            ValidationType.PARAMETER_SENSITIVITY,
            ValidationType.STRESS,
            ValidationType.MONTE_CARLO,
            ValidationType.ADVERSARIAL_REVIEW,
        )
    ):
        configuration: dict[str, object] = {"fingerprint": f"validation-{index}"}
        if validation_type is ValidationType.BACKTEST:
            configuration["benchmark_metrics"] = {"total_return": 0.08}
        if validation_type is ValidationType.ADVERSARIAL_REVIEW:
            configuration["report"] = {
                "summary": {"high_count": 0, "warning_count": 1},
                "findings": [],
            }
        validation = ValidationRun(
            uuid4(),
            run.id,
            validation_type,
            ValidationStatus.PASSED,
            MetricSet(total_return=0.1, sharpe=0.7, max_drawdown=-0.1, trade_count=10)
            if validation_type is not ValidationType.ADVERSARIAL_REVIEW
            else None,
            configuration,
            NOW + timedelta(seconds=index),
            NOW + timedelta(seconds=index),
        )
        experiments.add_validation(validation)
        validations.append(validation)
    gate = ValidationGateResult(
        uuid4(),
        run.id,
        version.id,
        "HISTORICAL_TO_PAPER",
        1,
        GateDecision.PASS,
        (
            GateRuleResult(
                "REQUIRED_BACKTEST",
                GateRuleOutcome.PASS,
                "AVAILABLE",
                "AVAILABLE",
                (validations[0].id,),
                {},
            ),
        ),
        {"backtest": {"validation_id": str(validations[0].id)}},
        {"policy_id": "HISTORICAL_TO_PAPER"},
        "validation-gate-v1",
        NOW,
        "gate-api",
    )
    gates.add(gate)
    signature = ResearchSignature(
        "trend", "US_EQUITIES", "SPY", "1D", {"short_window": 2, "long_window": 3}
    )
    knowledge.add(
        KnowledgeRecord(
            uuid4(),
            hypothesis.id,
            None,
            HypothesisStatus.REJECTED,
            signature,
            snapshot.start_at,
            snapshot.end_at,
            "Rejected fixture",
            "Fixture rejection",
            (ReconsiderationCondition.NEW_MARKET,),
            None,
            (EvidenceReference(EvidenceKind.VALIDATION_RUN, validations[1].id),),
            research_fingerprint(signature),
            NOW,
        )
    )
    queries = OperatorQueries(
        hypotheses, strategies, datasets, experiments, gates, knowledge
    )
    app.dependency_overrides[get_operator_queries] = lambda: queries
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/experiments").json()["page"]["returned"] == 1
            assert client.get(f"/api/v1/experiments/{experiment.id}").status_code == 200
            evidence = client.get(
                f"/api/v1/experiment-runs/{run.id}/validations"
            ).json()
            assert {item["validation_type"] for item in evidence} == {
                item.value for item in ValidationType
            }
            assert (
                client.get(
                    f"/api/v1/experiment-runs/{run.id}/adversarial-report"
                ).status_code
                == 200
            )
            assert (
                client.get(f"/api/v1/gate-evaluations/{gate.id}").json()["decision"]
                == "pass"
            )
            assert (
                client.get("/api/v1/knowledge?status=rejected").json()["page"][
                    "returned"
                ]
                == 1
            )
    finally:
        app.dependency_overrides.clear()
