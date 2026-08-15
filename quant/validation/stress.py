from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from statistics import median
from types import MappingProxyType

from quant.analytics import BenchmarkResult
from quant.backtest import BacktestResult
from quant.domain import MetricSet
from quant.strategies import MovingAverageParameters


class StressType(StrEnum):
    FEE_MULTIPLIER = "fee_multiplier"
    SLIPPAGE_MULTIPLIER = "slippage_multiplier"
    EXECUTION_DELAY = "execution_delay"
    ADVERSE_PRICE = "adverse_price"
    PARAMETER_PERTURBATION = "parameter_perturbation"


class StressEvaluationScope(StrEnum):
    FULL_HISTORY_RESEARCH = "full_history_research"


@dataclass(frozen=True, slots=True)
class StressScenario:
    id: str
    name: str
    stress_type: StressType
    configuration: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("stress scenario id and name cannot be empty")
        copied = deepcopy(dict(self.configuration))
        _validate_scenario(self.stress_type, copied)
        object.__setattr__(self, "configuration", MappingProxyType(copied))


@dataclass(frozen=True, slots=True)
class StressTestingConfiguration:
    scenarios: tuple[StressScenario, ...]
    evaluation_scope: StressEvaluationScope = (
        StressEvaluationScope.FULL_HISTORY_RESEARCH
    )

    def __post_init__(self) -> None:
        if not self.scenarios:
            raise ValueError("at least one stress scenario is required")
        identifiers = [scenario.id for scenario in self.scenarios]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("stress scenario ids must be unique")


@dataclass(frozen=True, slots=True)
class StressComparison:
    total_return_delta: float | None
    max_drawdown_delta: float | None
    max_drawdown_worsening: float | None
    sharpe_delta: float | None
    trade_count_delta: int | None
    final_equity_delta: Decimal
    retained_total_return_ratio: float | None
    retained_sharpe_ratio: float | None


@dataclass(frozen=True, slots=True)
class StressScenarioResult:
    scenario: StressScenario
    effective_configuration: Mapping[str, object]
    no_effect: bool
    backtest_result: BacktestResult
    metrics: MetricSet
    comparison: StressComparison
    benchmark: BenchmarkResult

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "effective_configuration",
            MappingProxyType(deepcopy(dict(self.effective_configuration))),
        )


@dataclass(frozen=True, slots=True)
class StressAggregate:
    scenario_count: int
    profitable_scenario_count: int
    profitable_scenario_ratio: float
    median_total_return: float
    worst_total_return: float
    median_sharpe: float | None
    worst_sharpe: float | None
    worst_max_drawdown: float | None
    scenario_outperformance_vs_baseline_count: int
    worst_return_scenario_id: str
    worst_drawdown_scenario_id: str | None
    worst_sharpe_scenario_id: str | None


@dataclass(frozen=True, slots=True)
class StressAnalysis:
    configuration: StressTestingConfiguration
    baseline_backtest: BacktestResult
    baseline_metrics: MetricSet
    baseline_benchmark: BenchmarkResult
    scenario_results: tuple[StressScenarioResult, ...]
    aggregate: StressAggregate


def compare_stress_result(
    baseline_result: BacktestResult,
    baseline_metrics: MetricSet,
    stressed_result: BacktestResult,
    stressed_metrics: MetricSet,
) -> StressComparison:
    baseline_return = baseline_metrics.total_return
    stressed_return = stressed_metrics.total_return
    baseline_drawdown = baseline_metrics.max_drawdown
    stressed_drawdown = stressed_metrics.max_drawdown
    baseline_sharpe = baseline_metrics.sharpe
    stressed_sharpe = stressed_metrics.sharpe
    baseline_trades = baseline_metrics.trade_count
    stressed_trades = stressed_metrics.trade_count
    return StressComparison(
        total_return_delta=_delta(stressed_return, baseline_return),
        max_drawdown_delta=_delta(stressed_drawdown, baseline_drawdown),
        max_drawdown_worsening=(
            baseline_drawdown - stressed_drawdown
            if baseline_drawdown is not None and stressed_drawdown is not None
            else None
        ),
        sharpe_delta=_delta(stressed_sharpe, baseline_sharpe),
        trade_count_delta=(
            stressed_trades - baseline_trades
            if stressed_trades is not None and baseline_trades is not None
            else None
        ),
        final_equity_delta=(
            stressed_result.final_equity - baseline_result.final_equity
        ),
        retained_total_return_ratio=_retained_ratio(
            stressed_return, baseline_return
        ),
        retained_sharpe_ratio=_retained_ratio(stressed_sharpe, baseline_sharpe),
    )


def aggregate_stress_results(
    results: tuple[StressScenarioResult, ...], baseline_metrics: MetricSet
) -> StressAggregate:
    if not results:
        raise ValueError("stress scenario results cannot be empty")
    returns = [
        _required(result.metrics.total_return, "total_return") for result in results
    ]
    sharpes = [
        (result.scenario.id, value)
        for result in results
        if (value := result.metrics.sharpe) is not None
    ]
    drawdowns = [
        (result.scenario.id, value)
        for result in results
        if (value := result.metrics.max_drawdown) is not None
    ]
    profitable = sum(value > 0 for value in returns)
    baseline_return = _required(baseline_metrics.total_return, "baseline return")
    worst_return_index = min(range(len(results)), key=lambda index: returns[index])
    return StressAggregate(
        scenario_count=len(results),
        profitable_scenario_count=profitable,
        profitable_scenario_ratio=profitable / len(results),
        median_total_return=median(returns),
        worst_total_return=returns[worst_return_index],
        median_sharpe=median(value for _, value in sharpes) if sharpes else None,
        worst_sharpe=min(value for _, value in sharpes) if sharpes else None,
        worst_max_drawdown=min(value for _, value in drawdowns) if drawdowns else None,
        scenario_outperformance_vs_baseline_count=sum(
            value > baseline_return for value in returns
        ),
        worst_return_scenario_id=results[worst_return_index].scenario.id,
        worst_drawdown_scenario_id=(
            min(drawdowns, key=lambda item: item[1])[0] if drawdowns else None
        ),
        worst_sharpe_scenario_id=(
            min(sharpes, key=lambda item: item[1])[0] if sharpes else None
        ),
    )


def _validate_scenario(
    stress_type: StressType, configuration: Mapping[str, object]
) -> None:
    if stress_type in (StressType.FEE_MULTIPLIER, StressType.SLIPPAGE_MULTIPLIER):
        multiplier = configuration.get("multiplier")
        if not isinstance(multiplier, Decimal) or not multiplier.is_finite():
            raise ValueError("multiplier must be a finite Decimal")
        if multiplier <= 1:
            raise ValueError("stress multiplier must be greater than one")
    elif stress_type is StressType.EXECUTION_DELAY:
        delay = configuration.get("additional_delay_bars")
        if not isinstance(delay, int) or isinstance(delay, bool) or delay < 0:
            raise ValueError("additional_delay_bars must be a non-negative integer")
    elif stress_type is StressType.ADVERSE_PRICE:
        basis_points = configuration.get("additional_basis_points")
        if (
            not isinstance(basis_points, Decimal)
            or not basis_points.is_finite()
            or basis_points < 0
        ):
            raise ValueError("additional_basis_points must be non-negative")
    elif stress_type is StressType.PARAMETER_PERTURBATION:
        parameters = configuration.get("parameters")
        if not isinstance(parameters, Mapping):
            raise ValueError("parameter perturbation requires parameters")
        short = parameters.get("short_window")
        long = parameters.get("long_window")
        if not isinstance(short, int) or isinstance(short, bool):
            raise ValueError("short_window must be an integer")
        if not isinstance(long, int) or isinstance(long, bool):
            raise ValueError("long_window must be an integer")
        MovingAverageParameters(short, long)


def _delta(stressed: float | None, baseline: float | None) -> float | None:
    return (
        stressed - baseline
        if stressed is not None and baseline is not None
        else None
    )


def _retained_ratio(stressed: float | None, baseline: float | None) -> float | None:
    if stressed is None or baseline is None or baseline <= 0:
        return None
    return stressed / baseline


def _required(value: float | None, name: str) -> float:
    if value is None:
        raise ValueError(f"{name} is required")
    return value
