from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from quant.domain import ExperimentRun, ValidationRun, ValidationType

ADVERSARIAL_ANALYZER_VERSION = "adversarial-analyzer-v1"


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


class FindingCategory(StrEnum):
    GENERALIZATION = "generalization"
    TEMPORAL_STABILITY = "temporal_stability"
    PARAMETER_ROBUSTNESS = "parameter_robustness"
    EXECUTION_ROBUSTNESS = "execution_robustness"
    SEQUENCE_RISK = "sequence_risk"
    CONCENTRATION = "concentration"
    SAMPLE_SIZE = "sample_size"
    BENCHMARK = "benchmark"
    DATA_INTEGRITY = "data_integrity"
    VALIDATION_COVERAGE = "validation_coverage"


@dataclass(frozen=True, slots=True)
class AdversarialAnalysisConfiguration:
    max_oos_sharpe_drop: float
    max_oos_return_drop: float
    max_oos_drawdown_worsening: float
    min_profitable_fold_ratio: float
    max_fold_return_dispersion: float
    max_fold_sharpe_dispersion: float
    max_neighbor_sharpe_delta: float
    min_profitable_parameter_ratio: float
    max_parameter_sharpe_dispersion: float
    max_stress_return_drop: float
    max_stress_drawdown_worsening: float
    max_bootstrap_loss_frequency: float
    max_adverse_bootstrap_drawdown: float
    max_bootstrap_losing_streak: int
    max_historical_return_percentile: float
    min_trade_count_for_interpretation: int
    max_top_trade_profit_share: float
    max_top_three_profit_share: float

    def __post_init__(self) -> None:
        ratio_names = (
            "min_profitable_fold_ratio",
            "min_profitable_parameter_ratio",
            "max_bootstrap_loss_frequency",
            "max_historical_return_percentile",
            "max_top_trade_profit_share",
            "max_top_three_profit_share",
        )
        for name in ratio_names:
            value = getattr(self, name)
            if value < 0 or value > 1:
                raise ValueError(f"{name} must be between 0 and 1")
        non_negative = (
            "max_oos_sharpe_drop",
            "max_oos_return_drop",
            "max_oos_drawdown_worsening",
            "max_fold_return_dispersion",
            "max_fold_sharpe_dispersion",
            "max_neighbor_sharpe_delta",
            "max_parameter_sharpe_dispersion",
            "max_stress_return_drop",
            "max_stress_drawdown_worsening",
            "max_bootstrap_losing_streak",
        )
        if any(getattr(self, name) < 0 for name in non_negative):
            raise ValueError("adversarial thresholds cannot be negative")
        if self.max_adverse_bootstrap_drawdown > 0:
            raise ValueError("max_adverse_bootstrap_drawdown must be non-positive")
        if self.min_trade_count_for_interpretation < 0:
            raise ValueError("minimum trade count cannot be negative")


@dataclass(frozen=True, slots=True)
class AdversarialFinding:
    code: str
    category: FindingCategory
    severity: FindingSeverity
    title: str
    evidence: Mapping[str, object]
    metric_references: tuple[str, ...]
    source_validation_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))


@dataclass(frozen=True, slots=True)
class AdversarialSummary:
    finding_count: int
    info_count: int
    warning_count: int
    high_count: int
    categories_with_findings: tuple[FindingCategory, ...]


@dataclass(frozen=True, slots=True)
class AdversarialValidationReport:
    experiment_run_id: UUID
    generated_from_validation_ids: tuple[UUID, ...]
    coverage: Mapping[ValidationType, bool]
    findings: tuple[AdversarialFinding, ...]
    summary: AdversarialSummary
    analyzer_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "coverage", MappingProxyType(dict(self.coverage)))


SOURCE_TYPES = (
    ValidationType.BACKTEST,
    ValidationType.OUT_OF_SAMPLE,
    ValidationType.WALK_FORWARD,
    ValidationType.PARAMETER_SENSITIVITY,
    ValidationType.STRESS,
    ValidationType.MONTE_CARLO,
)


def analyze_adversarial_evidence(
    experiment_run: ExperimentRun,
    validations: Sequence[ValidationRun],
    configuration: AdversarialAnalysisConfiguration,
    *,
    fingerprint: str = "",
) -> AdversarialValidationReport:
    sources = _source_map(validations)
    coverage = {
        validation_type: validation_type in sources for validation_type in SOURCE_TYPES
    }
    findings: list[AdversarialFinding] = []
    for validation_type in SOURCE_TYPES:
        if validation_type not in sources:
            findings.append(
                _finding(
                    f"{validation_type.name}_NOT_AVAILABLE",
                    FindingCategory.VALIDATION_COVERAGE,
                    FindingSeverity.INFO,
                    f"{validation_type.value} evidence is not available",
                    {"validation_type": validation_type.value, "available": False},
                )
            )
    backtest = sources.get(ValidationType.BACKTEST)
    oos = sources.get(ValidationType.OUT_OF_SAMPLE)
    if backtest is not None:
        _sample_and_concentration_checks(
            findings, experiment_run, backtest, configuration
        )
        _benchmark_checks(findings, backtest)
    if backtest is not None and oos is not None:
        _oos_checks(findings, backtest, oos, configuration)
    walk_forward = sources.get(ValidationType.WALK_FORWARD)
    if walk_forward is not None:
        _walk_forward_checks(findings, walk_forward, configuration)
    sensitivity = sources.get(ValidationType.PARAMETER_SENSITIVITY)
    if sensitivity is not None:
        _parameter_checks(findings, sensitivity, configuration)
    stress = sources.get(ValidationType.STRESS)
    if stress is not None:
        _stress_checks(findings, stress, configuration)
    monte_carlo = sources.get(ValidationType.MONTE_CARLO)
    if monte_carlo is not None:
        _monte_carlo_checks(findings, monte_carlo, configuration)
    ordered = tuple(sorted(findings, key=_finding_sort_key))
    summary = _summary(ordered)
    return AdversarialValidationReport(
        experiment_run.id,
        tuple(sources[kind].id for kind in SOURCE_TYPES if kind in sources),
        coverage,
        ordered,
        summary,
        ADVERSARIAL_ANALYZER_VERSION,
        fingerprint,
    )


def _source_map(
    validations: Sequence[ValidationRun],
) -> dict[ValidationType, ValidationRun]:
    sources: dict[ValidationType, ValidationRun] = {}
    for validation in validations:
        if validation.validation_type not in SOURCE_TYPES:
            continue
        if validation.validation_type in sources:
            raise ValueError(f"multiple {validation.validation_type.value} validations")
        sources[validation.validation_type] = validation
    return sources


def _oos_checks(
    findings: list[AdversarialFinding],
    backtest: ValidationRun,
    oos: ValidationRun,
    config: AdversarialAnalysisConfiguration,
) -> None:
    baseline = backtest.metric_set
    held_out = oos.metric_set
    if baseline is None or held_out is None:
        return
    refs = (backtest.id, oos.id)
    if baseline.total_return is not None and held_out.total_return is not None:
        delta = held_out.total_return - baseline.total_return
        if baseline.total_return > 0 > held_out.total_return:
            findings.append(
                _finding(
                    "OOS_SIGN_REVERSAL",
                    FindingCategory.GENERALIZATION,
                    FindingSeverity.HIGH,
                    "OOS return reverses sign",
                    {
                        "backtest_total_return": baseline.total_return,
                        "oos_total_return": held_out.total_return,
                        "delta": delta,
                    },
                    ("total_return",),
                    refs,
                )
            )
        elif delta <= -config.max_oos_return_drop:
            findings.append(
                _finding(
                    "OOS_RETURN_DROPOFF",
                    FindingCategory.GENERALIZATION,
                    FindingSeverity.WARNING,
                    "OOS return deteriorates",
                    {
                        "backtest_total_return": baseline.total_return,
                        "oos_total_return": held_out.total_return,
                        "delta": delta,
                        "threshold": config.max_oos_return_drop,
                    },
                    ("total_return",),
                    refs,
                )
            )
    if baseline.sharpe is not None and held_out.sharpe is not None:
        delta = held_out.sharpe - baseline.sharpe
        if delta <= -config.max_oos_sharpe_drop:
            findings.append(
                _finding(
                    "OOS_SHARPE_DROPOFF",
                    FindingCategory.GENERALIZATION,
                    FindingSeverity.WARNING,
                    "OOS Sharpe deteriorates",
                    {
                        "backtest_sharpe": baseline.sharpe,
                        "oos_sharpe": held_out.sharpe,
                        "delta": delta,
                        "threshold": config.max_oos_sharpe_drop,
                    },
                    ("sharpe",),
                    refs,
                )
            )
    if baseline.max_drawdown is not None and held_out.max_drawdown is not None:
        worsening = baseline.max_drawdown - held_out.max_drawdown
        if worsening >= config.max_oos_drawdown_worsening:
            findings.append(
                _finding(
                    "OOS_DRAWDOWN_DETERIORATION",
                    FindingCategory.GENERALIZATION,
                    FindingSeverity.WARNING,
                    "OOS maximum drawdown deteriorates",
                    {
                        "backtest_max_drawdown": baseline.max_drawdown,
                        "oos_max_drawdown": held_out.max_drawdown,
                        "worsening": worsening,
                        "threshold": config.max_oos_drawdown_worsening,
                    },
                    ("max_drawdown",),
                    refs,
                )
            )
    if (
        baseline.expectancy is not None
        and held_out.expectancy is not None
        and baseline.expectancy > 0 > held_out.expectancy
    ):
        findings.append(
            _finding(
                "OOS_EXPECTANCY_REVERSAL",
                FindingCategory.GENERALIZATION,
                FindingSeverity.HIGH,
                "OOS expectancy reverses sign",
                {
                    "backtest_expectancy": baseline.expectancy,
                    "oos_expectancy": held_out.expectancy,
                },
                ("expectancy",),
                refs,
            )
        )
    if (
        held_out.trade_count is not None
        and held_out.trade_count < config.min_trade_count_for_interpretation
    ):
        findings.append(
            _finding(
                "OOS_INSUFFICIENT_TRADES",
                FindingCategory.SAMPLE_SIZE,
                FindingSeverity.WARNING,
                "OOS completed-trade sample is small",
                {
                    "trade_count": held_out.trade_count,
                    "minimum": config.min_trade_count_for_interpretation,
                },
                ("trade_count",),
                (oos.id,),
            )
        )


def _walk_forward_checks(
    findings: list[AdversarialFinding],
    validation: ValidationRun,
    config: AdversarialAnalysisConfiguration,
) -> None:
    aggregate = _mapping(validation.configuration.get("aggregate"))
    checks = (
        (
            "profitable_fold_ratio",
            config.min_profitable_fold_ratio,
            "LOW_PROFITABLE_FOLD_RATIO",
            "minimum",
            False,
        ),
        (
            "return_std_across_folds",
            config.max_fold_return_dispersion,
            "HIGH_RETURN_DISPERSION",
            "maximum",
            True,
        ),
        (
            "sharpe_std_across_folds",
            config.max_fold_sharpe_dispersion,
            "HIGH_SHARPE_DISPERSION",
            "maximum",
            True,
        ),
    )
    for field, threshold, code, threshold_name, above in checks:
        value = _number(aggregate.get(field))
        triggered = value is not None and (
            value > threshold if above else value < threshold
        )
        if triggered:
            findings.append(
                _finding(
                    code,
                    FindingCategory.TEMPORAL_STABILITY,
                    FindingSeverity.WARNING,
                    "Walk-forward evidence is temporally unstable",
                    {field: value, threshold_name: threshold},
                    (field,),
                    (validation.id,),
                )
            )


def _parameter_checks(
    findings: list[AdversarialFinding],
    validation: ValidationRun,
    config: AdversarialAnalysisConfiguration,
) -> None:
    summary = _mapping(validation.configuration.get("summary"))
    neighbor_delta = _number(summary.get("sharpe_neighbor_delta"))
    if (
        neighbor_delta is not None
        and neighbor_delta >= config.max_neighbor_sharpe_delta
    ):
        findings.append(
            _finding(
                "ISOLATED_PARAMETER_PEAK",
                FindingCategory.PARAMETER_ROBUSTNESS,
                FindingSeverity.HIGH,
                "Baseline Sharpe is isolated from configured neighbors",
                {
                    "sharpe_neighbor_delta": neighbor_delta,
                    "threshold": config.max_neighbor_sharpe_delta,
                    "neighbor_median_sharpe": summary.get("neighbor_median_sharpe"),
                },
                ("sharpe",),
                (validation.id,),
            )
        )
    profitable = _number(summary.get("profitable_combination_ratio"))
    if profitable is not None and profitable < config.min_profitable_parameter_ratio:
        findings.append(
            _finding(
                "LOW_PROFITABLE_PARAMETER_RATIO",
                FindingCategory.PARAMETER_ROBUSTNESS,
                FindingSeverity.WARNING,
                "Few parameter candidates are profitable",
                {
                    "profitable_combination_ratio": profitable,
                    "minimum": config.min_profitable_parameter_ratio,
                },
                ("total_return",),
                (validation.id,),
            )
        )
    dispersion = _number(summary.get("sharpe_dispersion"))
    if dispersion is not None and dispersion > config.max_parameter_sharpe_dispersion:
        findings.append(
            _finding(
                "HIGH_PARAMETER_METRIC_DISPERSION",
                FindingCategory.PARAMETER_ROBUSTNESS,
                FindingSeverity.WARNING,
                "Parameter Sharpe values are dispersed",
                {
                    "sharpe_dispersion": dispersion,
                    "maximum": config.max_parameter_sharpe_dispersion,
                },
                ("sharpe",),
                (validation.id,),
            )
        )


def _stress_checks(
    findings: list[AdversarialFinding],
    validation: ValidationRun,
    config: AdversarialAnalysisConfiguration,
) -> None:
    scenarios = validation.configuration.get("scenarios")
    if not isinstance(scenarios, list):
        return
    for raw in scenarios:
        scenario_result = _mapping(raw)
        scenario = _mapping(scenario_result.get("scenario"))
        stress_type_value = scenario.get("stress_type")
        stress_type = stress_type_value if isinstance(stress_type_value, str) else None
        comparison = _mapping(scenario_result.get("comparison"))
        metrics = _mapping(scenario_result.get("metrics"))
        baseline = _mapping(
            _mapping(validation.configuration.get("baseline")).get("metrics")
        )
        delta = _number(comparison.get("total_return_delta"))
        codes = {
            "fee_multiplier": "FEE_SENSITIVITY",
            "slippage_multiplier": "SLIPPAGE_SENSITIVITY",
            "adverse_price": "ADVERSE_FILL_SENSITIVITY",
            "execution_delay": "EXECUTION_TIMING_FRAGILITY",
        }
        code = codes.get(stress_type) if stress_type is not None else None
        if (
            code is not None
            and delta is not None
            and delta <= -config.max_stress_return_drop
        ):
            findings.append(
                _finding(
                    code,
                    FindingCategory.EXECUTION_ROBUSTNESS,
                    FindingSeverity.WARNING,
                    "Stress scenario materially reduces return",
                    {
                        "scenario_id": scenario.get("id"),
                        "stress_type": stress_type,
                        "total_return_delta": delta,
                        "threshold": config.max_stress_return_drop,
                    },
                    ("total_return",),
                    (validation.id,),
                )
            )
        stressed_return = _number(metrics.get("total_return"))
        baseline_return = _number(baseline.get("total_return"))
        if (
            baseline_return is not None
            and stressed_return is not None
            and baseline_return > 0 > stressed_return
        ):
            findings.append(
                _finding(
                    "STRESS_RETURN_SIGN_REVERSAL",
                    FindingCategory.EXECUTION_ROBUSTNESS,
                    FindingSeverity.HIGH,
                    "Stress return reverses sign",
                    {
                        "scenario_id": scenario.get("id"),
                        "baseline_total_return": baseline_return,
                        "stressed_total_return": stressed_return,
                    },
                    ("total_return",),
                    (validation.id,),
                )
            )
        worsening = _number(comparison.get("max_drawdown_worsening"))
        if worsening is not None and worsening >= config.max_stress_drawdown_worsening:
            findings.append(
                _finding(
                    "STRESS_DRAWDOWN_EXPANSION",
                    FindingCategory.EXECUTION_ROBUSTNESS,
                    FindingSeverity.WARNING,
                    "Stress expands maximum drawdown",
                    {
                        "scenario_id": scenario.get("id"),
                        "max_drawdown_worsening": worsening,
                        "threshold": config.max_stress_drawdown_worsening,
                    },
                    ("max_drawdown",),
                    (validation.id,),
                )
            )


def _monte_carlo_checks(
    findings: list[AdversarialFinding],
    validation: ValidationRun,
    config: AdversarialAnalysisConfiguration,
) -> None:
    distribution = _mapping(validation.configuration.get("distribution"))
    loss = _number(distribution.get("empirical_loss_frequency"))
    if loss is not None and loss >= config.max_bootstrap_loss_frequency:
        findings.append(
            _finding(
                "HIGH_BOOTSTRAP_LOSS_FREQUENCY",
                FindingCategory.SEQUENCE_RISK,
                FindingSeverity.WARNING,
                "Empirical bootstrap loss frequency is elevated",
                {
                    "empirical_loss_frequency": loss,
                    "threshold": config.max_bootstrap_loss_frequency,
                    "interpretation": "empirical_bootstrap_frequency",
                },
                (),
                (validation.id,),
            )
        )
    drawdowns = _mapping(distribution.get("max_drawdown_percentiles"))
    adverse = min(
        (_number(value) for value in drawdowns.values()),
        default=None,
        key=lambda value: float("inf") if value is None else value,
    )
    if adverse is not None and adverse <= config.max_adverse_bootstrap_drawdown:
        findings.append(
            _finding(
                "LARGE_ADVERSE_DRAWDOWN",
                FindingCategory.SEQUENCE_RISK,
                FindingSeverity.HIGH,
                "Bootstrap distribution contains large adverse drawdown",
                {
                    "adverse_max_drawdown_percentile": adverse,
                    "threshold": config.max_adverse_bootstrap_drawdown,
                },
                ("max_drawdown",),
                (validation.id,),
            )
        )
    streaks = _mapping(distribution.get("max_losing_streak_percentiles"))
    longest = max(
        (_number(value) for value in streaks.values()),
        default=None,
        key=lambda value: float("-inf") if value is None else value,
    )
    if longest is not None and longest >= config.max_bootstrap_losing_streak:
        findings.append(
            _finding(
                "LONG_LOSS_STREAK_RISK",
                FindingCategory.SEQUENCE_RISK,
                FindingSeverity.WARNING,
                "Bootstrap loss streak is long",
                {
                    "adverse_losing_streak_percentile": longest,
                    "threshold": config.max_bootstrap_losing_streak,
                },
                (),
                (validation.id,),
            )
        )
    position = _number(distribution.get("historical_total_return_percentile"))
    if position is not None and position >= config.max_historical_return_percentile:
        findings.append(
            _finding(
                "HISTORICAL_RESULT_HIGH_RELATIVE_TO_BOOTSTRAP",
                FindingCategory.SEQUENCE_RISK,
                FindingSeverity.WARNING,
                "Historical return lies high in the empirical bootstrap distribution",
                {
                    "historical_total_return_percentile": position,
                    "threshold": config.max_historical_return_percentile,
                },
                ("total_return",),
                (validation.id,),
            )
        )


def _sample_and_concentration_checks(
    findings: list[AdversarialFinding],
    run: ExperimentRun,
    backtest: ValidationRun,
    config: AdversarialAnalysisConfiguration,
) -> None:
    metrics = backtest.metric_set
    if (
        metrics is not None
        and metrics.trade_count is not None
        and metrics.trade_count < config.min_trade_count_for_interpretation
    ):
        findings.append(
            _finding(
                "LOW_COMPLETED_TRADE_COUNT",
                FindingCategory.SAMPLE_SIZE,
                FindingSeverity.WARNING,
                "Completed-trade sample is small",
                {
                    "trade_count": metrics.trade_count,
                    "minimum": config.min_trade_count_for_interpretation,
                },
                ("trade_count",),
                (backtest.id,),
            )
        )
    stored = _mapping(run.configuration)
    evidence = _mapping(stored.get("evidence"))
    trades = _mapping(evidence.get("backtest")).get("trades")
    if not isinstance(trades, list):
        return
    profits = sorted(
        (_number(_mapping(item).get("realized_pnl")) for item in trades),
        reverse=True,
        key=lambda value: float("-inf") if value is None else value,
    )
    positive = [value for value in profits if value is not None and value > 0]
    gross_profit = sum(positive)
    if gross_profit <= 0:
        return
    top_share = positive[0] / gross_profit
    top_three_share = sum(positive[:3]) / gross_profit
    if top_share >= config.max_top_trade_profit_share:
        findings.append(
            _finding(
                "TOP_TRADE_CONCENTRATION",
                FindingCategory.CONCENTRATION,
                FindingSeverity.WARNING,
                "Gross winning profit is concentrated in one trade",
                {
                    "top_trade_profit_share": top_share,
                    "threshold": config.max_top_trade_profit_share,
                    "gross_winning_profit": gross_profit,
                },
                ("realized_pnl",),
                (backtest.id,),
            )
        )
    if len(positive) >= 3 and top_three_share >= config.max_top_three_profit_share:
        findings.append(
            _finding(
                "TOP_3_TRADES_CONCENTRATION",
                FindingCategory.CONCENTRATION,
                FindingSeverity.WARNING,
                "Gross winning profit is concentrated in three trades",
                {
                    "top_three_profit_share": top_three_share,
                    "threshold": config.max_top_three_profit_share,
                    "gross_winning_profit": gross_profit,
                },
                ("realized_pnl",),
                (backtest.id,),
            )
        )


def _benchmark_checks(
    findings: list[AdversarialFinding], backtest: ValidationRun
) -> None:
    strategy = backtest.metric_set
    benchmark = _mapping(backtest.configuration.get("benchmark_metrics"))
    if strategy is None:
        return
    benchmark_return = _number(benchmark.get("total_return"))
    benchmark_drawdown = _number(benchmark.get("max_drawdown"))
    benchmark_sharpe = _number(benchmark.get("sharpe"))
    strategy_return = strategy.total_return
    strategy_drawdown = strategy.max_drawdown
    strategy_sharpe = strategy.sharpe
    if (
        strategy_return is not None
        and strategy_drawdown is not None
        and strategy_sharpe is not None
        and benchmark_return is not None
        and benchmark_drawdown is not None
        and benchmark_sharpe is not None
        and benchmark_return >= strategy_return
        and benchmark_drawdown >= strategy_drawdown
        and benchmark_sharpe >= strategy_sharpe
    ):
        findings.append(
            _finding(
                "BENCHMARK_DOMINANCE",
                FindingCategory.BENCHMARK,
                FindingSeverity.WARNING,
                "Benchmark is no worse on return, drawdown, and Sharpe",
                {
                    "strategy_total_return": strategy.total_return,
                    "benchmark_total_return": benchmark_return,
                    "strategy_max_drawdown": strategy.max_drawdown,
                    "benchmark_max_drawdown": benchmark_drawdown,
                    "strategy_sharpe": strategy.sharpe,
                    "benchmark_sharpe": benchmark_sharpe,
                },
                ("total_return", "max_drawdown", "sharpe"),
                (backtest.id,),
            )
        )


def _finding(
    code: str,
    category: FindingCategory,
    severity: FindingSeverity,
    title: str,
    evidence: Mapping[str, object],
    metric_references: tuple[str, ...] = (),
    source_ids: tuple[UUID, ...] = (),
) -> AdversarialFinding:
    return AdversarialFinding(
        code, category, severity, title, evidence, metric_references, source_ids
    )


def _summary(findings: tuple[AdversarialFinding, ...]) -> AdversarialSummary:
    return AdversarialSummary(
        len(findings),
        sum(item.severity is FindingSeverity.INFO for item in findings),
        sum(item.severity is FindingSeverity.WARNING for item in findings),
        sum(item.severity is FindingSeverity.HIGH for item in findings),
        tuple(
            sorted({item.category for item in findings}, key=lambda item: item.value)
        ),
    )


def _finding_sort_key(finding: AdversarialFinding) -> tuple[int, str, str]:
    priority = {
        FindingSeverity.HIGH: 0,
        FindingSeverity.WARNING: 1,
        FindingSeverity.INFO: 2,
    }
    return priority[finding.severity], finding.category.value, finding.code


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
