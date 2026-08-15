from datetime import UTC, datetime, timedelta
from typing import TypedDict, cast
from unittest.mock import Mock
from uuid import UUID

from fastapi.testclient import TestClient

from apps.api.dependencies import get_operator_queries
from apps.api.main import app
from quant.application import (
    DashboardSummary,
    ExperimentDetail,
    ExperimentSummary,
    HypothesisDetail,
    OperatorQueries,
    OperatorResourceNotFound,
)
from quant.domain import (
    AdjustmentPolicy,
    DatasetSnapshot,
    Experiment,
    ExperimentRun,
    ExperimentRunStatus,
    ExperimentStatus,
    GateDecision,
    GateRuleOutcome,
    GateRuleResult,
    Hypothesis,
    HypothesisStatus,
    MetricSet,
    Strategy,
    StrategyVersion,
    ValidationGateResult,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.domain.knowledge import (
    EvidenceKind,
    EvidenceReference,
    KnowledgeRecord,
    ReconsiderationCondition,
    ResearchSignature,
)
from quant.knowledge import research_fingerprint

NOW = datetime(2026, 8, 15, 10, tzinfo=UTC)
IDS = [UUID(int=index) for index in range(1, 20)]


class FixtureValues(TypedDict):
    hypothesis: Hypothesis
    version: StrategyVersion
    experiment: Experiment
    run: ExperimentRun
    validation: ValidationRun
    gate: ValidationGateResult


def fixture() -> tuple[Mock, FixtureValues]:
    hypothesis = Hypothesis(
        IDS[0],
        "Trend persists",
        "A deterministic hypothesis",
        "Rationale",
        "trend",
        "US_EQUITIES",
        "1D",
        "Benefit",
        "Tradeoff",
        "Success",
        "Reject",
        HypothesisStatus.ACTIVE_RESEARCH,
        None,
        NOW,
    )
    strategy = Strategy(IDS[1], "MA Trend", "Trend strategy", "trend", NOW)
    version = StrategyVersion(
        IDS[2],
        strategy.id,
        "v1",
        "abc123",
        "moving_average_trend",
        {"short_window": 2, "long_window": 3},
        NOW,
    )
    dataset = DatasetSnapshot(
        IDS[3],
        "fixture",
        "US_EQUITIES",
        "SPY",
        "1D",
        NOW - timedelta(days=10),
        NOW,
        "v1",
        "sha256-fixture",
        "/private/secret.parquet",
        AdjustmentPolicy.RAW,
        NOW,
    )
    experiment = Experiment(
        IDS[4], hypothesis.id, version.id, dataset.id, ExperimentStatus.COMPLETED, NOW
    )
    run = ExperimentRun(
        IDS[5],
        experiment.id,
        "abc123",
        "backtest-engine-v1",
        "percentage-fee-v1",
        "bps-slippage-v1",
        {
            "analytics": {"version": "metrics-v1"},
            "result_fingerprint": "run-fingerprint",
        },
        NOW,
        NOW + timedelta(minutes=1),
        ExperimentRunStatus.COMPLETED,
    )
    validation = ValidationRun(
        IDS[6],
        run.id,
        ValidationType.BACKTEST,
        ValidationStatus.PASSED,
        MetricSet(total_return=0.1234, max_drawdown=-0.1, sharpe=None, trade_count=4),
        {
            "benchmark_metrics": {"total_return": 0.2, "sharpe": 0.8},
            "fingerprint": "validation-fingerprint",
        },
        NOW,
        NOW,
    )
    adversarial = ValidationRun(
        IDS[7],
        run.id,
        ValidationType.ADVERSARIAL_REVIEW,
        ValidationStatus.PASSED,
        None,
        {
            "report": {
                "summary": {"high_count": 1, "warning_count": 2},
                "findings": [
                    {
                        "code": "OOS_SHARPE_DROPOFF",
                        "severity": "warning",
                        "title": "OOS Sharpe fell",
                        "evidence": {"delta": -0.7},
                    }
                ],
            },
            "fingerprint": "adversarial-fingerprint",
        },
        NOW,
        NOW,
    )
    gate = ValidationGateResult(
        IDS[8],
        run.id,
        version.id,
        "HISTORICAL_TO_PAPER",
        1,
        GateDecision.FAIL,
        (
            GateRuleResult(
                "MIN_OOS_SHARPE",
                GateRuleOutcome.FAIL,
                ">= 0.5",
                0.3,
                (validation.id,),
                {},
            ),
        ),
        {"backtest": {"validation_id": str(validation.id)}},
        {"policy_id": "HISTORICAL_TO_PAPER"},
        "validation-gate-v1",
        NOW,
        "gate-fingerprint",
    )
    signature = ResearchSignature(
        "trend", "US_EQUITIES", "SPY", "1D", {"short_window": 2, "long_window": 3}
    )
    record = KnowledgeRecord(
        IDS[9],
        hypothesis.id,
        None,
        HypothesisStatus.REJECTED,
        signature,
        NOW - timedelta(days=10),
        NOW,
        "Rejected research",
        "Weak OOS",
        (ReconsiderationCondition.NEW_MARKET,),
        None,
        (EvidenceReference(EvidenceKind.VALIDATION_RUN, validation.id),),
        research_fingerprint(signature),
        NOW,
    )
    queries = Mock(spec=OperatorQueries)
    queries.list_experiments.return_value = (
        ExperimentSummary(
            experiment,
            run,
            (ValidationType.BACKTEST, ValidationType.ADVERSARIAL_REVIEW),
            gate,
        ),
    )
    queries.experiment_detail.return_value = ExperimentDetail(
        experiment, hypothesis, strategy, version, dataset, (run,)
    )
    queries.experiment_run.return_value = run
    queries.validations.return_value = (validation, adversarial)
    queries.validation.return_value = validation
    queries.adversarial_reports.return_value = (adversarial,)
    queries.gate_evaluations.return_value = (gate,)
    queries.gate_evaluation.return_value = gate
    queries.strategy_version.return_value = version
    queries.list_hypotheses.return_value = (hypothesis,)
    queries.hypothesis_detail.return_value = HypothesisDetail(
        hypothesis, (experiment,), (record,), ()
    )
    queries.search_knowledge.return_value = (record,)
    queries.dashboard_summary.return_value = DashboardSummary(
        0,
        1,
        1,
        0,
        1,
        1,
        2,
        {
            status: int(status is HypothesisStatus.REJECTED)
            for status in HypothesisStatus
        },
    )
    knowledge_repository = Mock()
    knowledge_repository.list_all.return_value = [record]
    queries.knowledge = knowledge_repository
    return queries, {
        "hypothesis": hypothesis,
        "version": version,
        "experiment": experiment,
        "run": run,
        "validation": validation,
        "gate": gate,
    }


def client_for(queries: Mock) -> TestClient:
    app.dependency_overrides[get_operator_queries] = lambda: cast(
        OperatorQueries, queries
    )
    return TestClient(app)


def test_health_and_dashboard_smoke() -> None:
    queries, _ = fixture()
    with client_for(queries) as client:
        assert client.get("/health").json() == {"status": "ok"}
        dashboard = client.get("/dashboard/")
        assert dashboard.status_code == 200
        assert "Quant Lab" in dashboard.text
        assert "No gate evaluation" in client.get("/dashboard/app.js").text
    app.dependency_overrides.clear()


def test_missing_experiment_returns_404_without_internal_details() -> None:
    queries, _ = fixture()
    queries.experiment_detail.side_effect = OperatorResourceNotFound(
        "experiment was not found"
    )
    with client_for(queries) as client:
        response = client.get(f"/api/v1/experiments/{UUID(int=999)}")
        assert response.status_code == 404
        assert response.json() == {"detail": "experiment was not found"}
    app.dependency_overrides.clear()


def test_experiment_run_validation_adversarial_and_gate_endpoints() -> None:
    queries, values = fixture()
    with client_for(queries) as client:
        listing = client.get("/api/v1/experiments").json()
        assert listing["items"][0]["experiment_id"] == str(values["experiment"].id)
        detail = client.get(f"/api/v1/experiments/{values['experiment'].id}").json()
        assert detail["dataset_snapshot"]["checksum"] == "sha256-fixture"
        assert "storage_location" not in detail["dataset_snapshot"]
        run = client.get(f"/api/v1/experiment-runs/{values['run'].id}").json()
        assert run["analytics_version"] == "metrics-v1"
        validations = client.get(
            f"/api/v1/experiment-runs/{values['run'].id}/validations"
        ).json()
        assert validations[0]["metrics"]["total_return"] == 0.1234
        assert validations[0]["metrics"]["sharpe"] is None
        assert validations[0]["evidence"]["benchmark_metrics"]["total_return"] == 0.2
        assert (
            client.get(f"/api/v1/validations/{values['validation'].id}").status_code
            == 200
        )
        reports = client.get(
            f"/api/v1/experiment-runs/{values['run'].id}/adversarial-report"
        ).json()
        assert (
            reports[0]["evidence"]["report"]["findings"][0]["code"]
            == "OOS_SHARPE_DROPOFF"
        )
        gates = client.get(
            f"/api/v1/experiment-runs/{values['run'].id}/gate-evaluations"
        ).json()
        assert gates[0]["decision"] == "fail"
        assert "eligibility" in gates[0]["decision_semantics"]
        assert (
            client.get(f"/api/v1/gate-evaluations/{values['gate'].id}").status_code
            == 200
        )
    app.dependency_overrides.clear()


def test_hypothesis_knowledge_strategy_prior_art_and_summary_endpoints() -> None:
    queries, values = fixture()
    with client_for(queries) as client:
        assert client.get("/api/v1/hypotheses").json()["page"]["returned"] == 1
        assert (
            client.get(f"/api/v1/hypotheses/{values['hypothesis'].id}").status_code
            == 200
        )
        assert (
            client.get(f"/api/v1/strategy-versions/{values['version'].id}").json()[
                "algorithm_key"
            ]
            == "moving_average_trend"
        )
        memory = client.get("/api/v1/knowledge?status=rejected").json()
        assert memory["items"][0]["rejection_reason"] == "Weak OOS"
        prior_art_result = client.post(
            "/api/v1/knowledge/prior-art-check",
            json={
                "strategy_family": "trend",
                "market": "US_EQUITIES",
                "instrument": "SPY",
                "timeframe": "1D",
                "parameters": {"short_window": 2, "long_window": 3},
                "numeric_parameter_relative_tolerance": 0.05,
            },
        )
        assert prior_art_result.status_code == 200
        assert prior_art_result.json()["duplicate_detected"] is True
        assert client.get("/api/v1/operator-summary").json()["failed_gates"] == 1
    app.dependency_overrides.clear()
