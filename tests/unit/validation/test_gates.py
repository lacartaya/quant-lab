from datetime import UTC, datetime
from uuid import uuid4

import pytest

from quant.domain import (
    ExperimentRun,
    ExperimentRunStatus,
    GateDecision,
    GateRuleCode,
    GateRuleDefinition,
    GateRuleOutcome,
    MetricSet,
    StrategyVersion,
    ValidationGatePolicy,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.validation import GateEvaluationContext, evaluate_validation_gate

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def context(
    policy: ValidationGatePolicy,
    *,
    oos_sharpe: float = 0.7,
    oos_drawdown: float = -0.2,
    monte_loss: float = 0.2,
    fold_ratio: float = 0.7,
    forbidden: bool = False,
    omit: ValidationType | None = None,
) -> GateEvaluationContext:
    run = ExperimentRun(
        uuid4(),
        uuid4(),
        "abc123",
        "backtest-engine-v1",
        "zero-fee-v1",
        "zero-slippage-v1",
        {},
        NOW,
        NOW,
        ExperimentRunStatus.COMPLETED,
    )
    strategy = StrategyVersion(
        uuid4(),
        uuid4(),
        "v1",
        "abc123",
        "moving_average_trend",
        {"short_window": 2, "long_window": 3},
        NOW,
    )
    configurations: dict[ValidationType, tuple[MetricSet | None, dict[str, object]]] = {
        ValidationType.BACKTEST: (MetricSet(total_return=0.2), {}),
        ValidationType.OUT_OF_SAMPLE: (
            MetricSet(
                total_return=0.1,
                sharpe=oos_sharpe,
                max_drawdown=oos_drawdown,
                trade_count=30,
            ),
            {},
        ),
        ValidationType.WALK_FORWARD: (
            None,
            {
                "aggregate": {
                    "profitable_fold_ratio": fold_ratio,
                    "median_sharpe": 0.8,
                    "sharpe_std_across_folds": 0.2,
                    "benchmark_outperformance_ratio": 0.6,
                }
            },
        ),
        ValidationType.PARAMETER_SENSITIVITY: (
            None,
            {
                "summary": {
                    "profitable_combination_ratio": 0.8,
                    "sharpe_dispersion": 0.2,
                    "sharpe_neighbor_delta": 0.1,
                }
            },
        ),
        ValidationType.STRESS: (
            None,
            {
                "aggregate": {
                    "profitable_scenario_ratio": 0.8,
                    "worst_total_return": 0.01,
                    "worst_max_drawdown": -0.2,
                }
            },
        ),
        ValidationType.MONTE_CARLO: (
            None,
            {
                "distribution": {
                    "empirical_loss_frequency": monte_loss,
                    "total_return_percentiles": {"p05": "-0.1"},
                    "max_drawdown_percentiles": {"p05": "-0.2"},
                    "max_losing_streak_percentiles": {"p95": "5"},
                }
            },
        ),
        ValidationType.ADVERSARIAL_REVIEW: (
            None,
            {
                "report": {
                    "summary": {"high_count": 0, "warning_count": 1},
                    "findings": (
                        [{"code": "ISOLATED_PARAMETER_PEAK"}] if forbidden else []
                    ),
                }
            },
        ),
    }
    validations = {
        kind: ValidationRun(
            uuid4(),
            run.id,
            kind,
            ValidationStatus.PASSED,
            metrics,
            configuration,
            NOW,
            NOW,
        )
        for kind, (metrics, configuration) in configurations.items()
        if kind is not omit
    }
    return GateEvaluationContext(run, strategy, validations, policy)


def policy(
    *rules: GateRuleDefinition,
    version: int = 1,
    required: tuple[ValidationType, ...] = (),
    adversarial: bool = False,
) -> ValidationGatePolicy:
    return ValidationGatePolicy(
        "HISTORICAL_TO_PAPER",
        version,
        "Example non-production historical eligibility",
        required,
        adversarial,
        rules,
    )


def outcome_for(actual: float, code: GateRuleCode, threshold: float) -> GateDecision:
    result = evaluate_validation_gate(
        context(
            policy(GateRuleDefinition(code, threshold)),
            oos_sharpe=actual if code is GateRuleCode.MIN_OOS_SHARPE else 0.7,
            oos_drawdown=actual if code is GateRuleCode.MAX_OOS_DRAWDOWN else -0.2,
            monte_loss=(
                actual if code is GateRuleCode.MAX_MONTE_CARLO_LOSS_FREQUENCY else 0.2
            ),
        )
    )
    return result.decision


def test_complete_policy_passes_and_every_rule_executes() -> None:
    selected = policy(
        GateRuleDefinition(GateRuleCode.MIN_OOS_SHARPE, 0.5),
        GateRuleDefinition(GateRuleCode.MAX_OOS_DRAWDOWN, -0.25),
        GateRuleDefinition(GateRuleCode.MIN_WALK_FORWARD_PROFITABLE_FOLD_RATIO, 0.6),
        GateRuleDefinition(GateRuleCode.MIN_PARAMETER_PROFITABLE_RATIO, 0.5),
        GateRuleDefinition(GateRuleCode.MIN_STRESS_PROFITABLE_RATIO, 0.5),
        GateRuleDefinition(GateRuleCode.MAX_MONTE_CARLO_LOSS_FREQUENCY, 0.3),
        GateRuleDefinition(GateRuleCode.MAX_HIGH_ADVERSARIAL_FINDINGS, 0),
        required=(
            ValidationType.BACKTEST,
            ValidationType.OUT_OF_SAMPLE,
            ValidationType.WALK_FORWARD,
            ValidationType.PARAMETER_SENSITIVITY,
            ValidationType.STRESS,
            ValidationType.MONTE_CARLO,
        ),
        adversarial=True,
    )

    result = evaluate_validation_gate(context(selected))

    assert result.decision is GateDecision.PASS
    assert len(result.rule_results) == 14
    assert all(item.result is GateRuleOutcome.PASS for item in result.rule_results)


def test_single_and_multiple_failures_do_not_short_circuit() -> None:
    selected = policy(
        GateRuleDefinition(GateRuleCode.MIN_OOS_SHARPE, 0.5),
        GateRuleDefinition(GateRuleCode.MIN_WALK_FORWARD_PROFITABLE_FOLD_RATIO, 0.6),
        GateRuleDefinition(GateRuleCode.MAX_MONTE_CARLO_LOSS_FREQUENCY, 0.25),
    )
    single = evaluate_validation_gate(context(selected, oos_sharpe=0.4))
    multiple = evaluate_validation_gate(
        context(selected, oos_sharpe=0.4, fold_ratio=0.4, monte_loss=0.3)
    )

    assert single.decision is GateDecision.FAIL
    assert [
        item.rule_code
        for item in single.rule_results
        if item.result is GateRuleOutcome.FAIL
    ] == ["MIN_OOS_SHARPE"]
    assert len(multiple.rule_results) == 3
    assert all(item.result is GateRuleOutcome.FAIL for item in multiple.rule_results)


def test_missing_required_validation_fails_without_crashing_metric_rule() -> None:
    selected = policy(
        GateRuleDefinition(GateRuleCode.MAX_MONTE_CARLO_LOSS_FREQUENCY, 0.25),
        required=(ValidationType.MONTE_CARLO,),
    )

    result = evaluate_validation_gate(
        context(selected, omit=ValidationType.MONTE_CARLO)
    )

    assert result.decision is GateDecision.FAIL
    assert [item.rule_code for item in result.rule_results] == [
        "REQUIRED_MONTE_CARLO",
        "MAX_MONTE_CARLO_LOSS_FREQUENCY",
    ]
    assert all(item.result is GateRuleOutcome.FAIL for item in result.rule_results)
    assert result.rule_results[1].details["reason"] == "REQUIRED_EVIDENCE_MISSING"


@pytest.mark.parametrize(
    ("actual", "expected"),
    [(-0.2, GateDecision.PASS), (-0.25, GateDecision.PASS), (-0.3, GateDecision.FAIL)],
)
def test_negative_drawdown_boundary(actual: float, expected: GateDecision) -> None:
    assert outcome_for(actual, GateRuleCode.MAX_OOS_DRAWDOWN, -0.25) is expected


@pytest.mark.parametrize(
    ("actual", "expected"),
    [(0.49, GateDecision.FAIL), (0.5, GateDecision.PASS), (0.51, GateDecision.PASS)],
)
def test_minimum_boundary(actual: float, expected: GateDecision) -> None:
    assert outcome_for(actual, GateRuleCode.MIN_OOS_SHARPE, 0.5) is expected


@pytest.mark.parametrize(
    ("actual", "expected"),
    [(0.24, GateDecision.PASS), (0.25, GateDecision.PASS), (0.26, GateDecision.FAIL)],
)
def test_monte_carlo_frequency_boundary(actual: float, expected: GateDecision) -> None:
    assert (
        outcome_for(actual, GateRuleCode.MAX_MONTE_CARLO_LOSS_FREQUENCY, 0.25)
        is expected
    )


def test_forbidden_adversarial_finding_is_policy_controlled() -> None:
    selected = policy(
        GateRuleDefinition(
            GateRuleCode.FORBIDDEN_ADVERSARIAL_FINDING,
            "ISOLATED_PARAMETER_PEAK",
        ),
        adversarial=True,
    )

    failed = evaluate_validation_gate(context(selected, forbidden=True))
    passed = evaluate_validation_gate(context(selected, forbidden=False))

    assert failed.decision is GateDecision.FAIL
    assert passed.decision is GateDecision.PASS


def test_policy_versions_can_reach_different_decisions() -> None:
    v1 = policy(GateRuleDefinition(GateRuleCode.MIN_OOS_SHARPE, 0.5), version=1)
    v2 = policy(GateRuleDefinition(GateRuleCode.MIN_OOS_SHARPE, 0.8), version=2)

    assert evaluate_validation_gate(context(v1)).decision is GateDecision.PASS
    assert evaluate_validation_gate(context(v2)).decision is GateDecision.FAIL
