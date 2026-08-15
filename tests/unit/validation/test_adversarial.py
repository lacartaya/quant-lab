from datetime import UTC, datetime
from uuid import UUID, uuid4

from quant.domain import (
    ExperimentRun,
    ExperimentRunStatus,
    MetricSet,
    ValidationRun,
    ValidationStatus,
    ValidationType,
)
from quant.validation import (
    AdversarialAnalysisConfiguration,
    AdversarialFinding,
    AdversarialValidationReport,
    FindingSeverity,
    analyze_adversarial_evidence,
)

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def config() -> AdversarialAnalysisConfiguration:
    return AdversarialAnalysisConfiguration(
        max_oos_sharpe_drop=0.5,
        max_oos_return_drop=0.1,
        max_oos_drawdown_worsening=0.1,
        min_profitable_fold_ratio=0.5,
        max_fold_return_dispersion=0.2,
        max_fold_sharpe_dispersion=0.5,
        max_neighbor_sharpe_delta=0.75,
        min_profitable_parameter_ratio=0.5,
        max_parameter_sharpe_dispersion=0.5,
        max_stress_return_drop=0.1,
        max_stress_drawdown_worsening=0.1,
        max_bootstrap_loss_frequency=0.25,
        max_adverse_bootstrap_drawdown=-0.3,
        max_bootstrap_losing_streak=8,
        max_historical_return_percentile=0.95,
        min_trade_count_for_interpretation=20,
        max_top_trade_profit_share=0.7,
        max_top_three_profit_share=0.9,
    )


def experiment_run(trade_pnls: tuple[str, ...] = ()) -> ExperimentRun:
    trades = [{"realized_pnl": value} for value in trade_pnls]
    return ExperimentRun(
        uuid4(),
        uuid4(),
        "abc123",
        "backtest-engine-v1",
        "zero-fee-v1",
        "zero-slippage-v1",
        {"evidence": {"backtest": {"trades": trades}}},
        NOW,
        NOW,
        ExperimentRunStatus.COMPLETED,
    )


def validation(
    run_id: UUID,
    validation_type: ValidationType,
    *,
    metrics: MetricSet | None = None,
    configuration: dict[str, object] | None = None,
) -> ValidationRun:
    return ValidationRun(
        uuid4(),
        run_id,
        validation_type,
        ValidationStatus.PASSED,
        metrics,
        {} if configuration is None else configuration,
        NOW,
        NOW,
    )


def finding(report: AdversarialValidationReport, code: str) -> AdversarialFinding:
    return next(item for item in report.findings if item.code == code)


def test_oos_sharpe_drop_is_structured_and_stable_but_small_drop_is_quiet() -> None:
    run = experiment_run()
    backtest = validation(
        run.id,
        ValidationType.BACKTEST,
        metrics=MetricSet(total_return=0.2, sharpe=1.2, trade_count=30),
    )
    weak_oos = validation(
        run.id,
        ValidationType.OUT_OF_SAMPLE,
        metrics=MetricSet(total_return=0.12, sharpe=0.3, trade_count=25),
    )

    report = analyze_adversarial_evidence(run, (backtest, weak_oos), config())
    drop = finding(report, "OOS_SHARPE_DROPOFF")

    assert drop.severity is FindingSeverity.WARNING
    assert drop.evidence == {
        "backtest_sharpe": 1.2,
        "oos_sharpe": 0.3,
        "delta": -0.8999999999999999,
        "threshold": 0.5,
    }
    stable_oos = validation(
        run.id,
        ValidationType.OUT_OF_SAMPLE,
        metrics=MetricSet(total_return=0.19, sharpe=0.92, trade_count=25),
    )
    stable = analyze_adversarial_evidence(run, (backtest, stable_oos), config())
    assert "OOS_SHARPE_DROPOFF" not in {item.code for item in stable.findings}


def test_parameter_stress_and_monte_carlo_golden_findings() -> None:
    run = experiment_run()
    sensitivity = validation(
        run.id,
        ValidationType.PARAMETER_SENSITIVITY,
        configuration={
            "summary": {
                "sharpe_neighbor_delta": 1.4,
                "neighbor_median_sharpe": 0.4,
                "profitable_combination_ratio": 0.8,
                "sharpe_dispersion": 0.2,
            }
        },
    )
    stress = validation(
        run.id,
        ValidationType.STRESS,
        configuration={
            "baseline": {"metrics": {"total_return": 0.15}},
            "scenarios": [
                {
                    "scenario": {
                        "id": "FEES-3X",
                        "stress_type": "fee_multiplier",
                    },
                    "metrics": {"total_return": -0.05},
                    "comparison": {
                        "total_return_delta": -0.2,
                        "max_drawdown_worsening": 0.05,
                    },
                }
            ],
        },
    )
    monte_carlo = validation(
        run.id,
        ValidationType.MONTE_CARLO,
        configuration={
            "distribution": {
                "empirical_loss_frequency": 0.35,
                "max_drawdown_percentiles": {"p05": "-0.4", "p50": "-0.1"},
                "max_losing_streak_percentiles": {"p50": "4", "p95": "9"},
                "historical_total_return_percentile": 0.96,
            }
        },
    )

    report = analyze_adversarial_evidence(
        run, (sensitivity, stress, monte_carlo), config()
    )
    codes = {item.code for item in report.findings}

    assert "ISOLATED_PARAMETER_PEAK" in codes
    assert "FEE_SENSITIVITY" in codes
    assert "STRESS_RETURN_SIGN_REVERSAL" in codes
    assert "HIGH_BOOTSTRAP_LOSS_FREQUENCY" in codes
    assert "LARGE_ADVERSE_DRAWDOWN" in codes
    assert "LONG_LOSS_STREAK_RISK" in codes
    assert "HISTORICAL_RESULT_HIGH_RELATIVE_TO_BOOTSTRAP" in codes
    empirical = finding(report, "HIGH_BOOTSTRAP_LOSS_FREQUENCY")
    assert empirical.evidence["interpretation"] == "empirical_bootstrap_frequency"


def test_trade_concentration_and_low_sample_size_use_gross_winning_profit() -> None:
    run = experiment_run(("100", "10", "10", "10"))
    backtest = validation(
        run.id,
        ValidationType.BACKTEST,
        metrics=MetricSet(total_return=0.1, trade_count=4),
    )

    report = analyze_adversarial_evidence(run, (backtest,), config())

    concentration = finding(report, "TOP_TRADE_CONCENTRATION")
    assert concentration.evidence["gross_winning_profit"] == 130
    assert concentration.evidence["top_trade_profit_share"] == 100 / 130
    assert "LOW_COMPLETED_TRADE_COUNT" in {item.code for item in report.findings}


def test_missing_evidence_is_coverage_not_failure() -> None:
    run = experiment_run()
    backtest = validation(run.id, ValidationType.BACKTEST, metrics=MetricSet())
    oos = validation(run.id, ValidationType.OUT_OF_SAMPLE, metrics=MetricSet())

    report = analyze_adversarial_evidence(run, (backtest, oos), config())

    assert report.coverage[ValidationType.BACKTEST]
    assert report.coverage[ValidationType.OUT_OF_SAMPLE]
    for missing in (
        ValidationType.WALK_FORWARD,
        ValidationType.PARAMETER_SENSITIVITY,
        ValidationType.STRESS,
        ValidationType.MONTE_CARLO,
    ):
        assert not report.coverage[missing]
        item = finding(report, f"{missing.name}_NOT_AVAILABLE")
        assert item.severity is FindingSeverity.INFO


def test_benchmark_dominance_requires_no_worse_drawdown() -> None:
    run = experiment_run()
    dominated = validation(
        run.id,
        ValidationType.BACKTEST,
        metrics=MetricSet(total_return=0.1, max_drawdown=-0.2, sharpe=0.8),
        configuration={
            "benchmark_metrics": {
                "total_return": 0.12,
                "max_drawdown": -0.15,
                "sharpe": 0.9,
            }
        },
    )
    protected = validation(
        run.id,
        ValidationType.BACKTEST,
        metrics=MetricSet(total_return=0.1, max_drawdown=-0.05, sharpe=0.8),
        configuration={
            "benchmark_metrics": {
                "total_return": 0.12,
                "max_drawdown": -0.15,
                "sharpe": 0.9,
            }
        },
    )

    first = analyze_adversarial_evidence(run, (dominated,), config())
    second = analyze_adversarial_evidence(run, (protected,), config())

    assert "BENCHMARK_DOMINANCE" in {item.code for item in first.findings}
    assert "BENCHMARK_DOMINANCE" not in {item.code for item in second.findings}
    assert first == analyze_adversarial_evidence(run, (dominated,), config())
