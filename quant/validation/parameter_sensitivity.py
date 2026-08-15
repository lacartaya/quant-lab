from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from itertools import product
from math import prod
from statistics import median, pstdev
from types import MappingProxyType

from quant.analytics import BenchmarkResult
from quant.backtest import BacktestResult
from quant.domain import MetricSet
from quant.strategies import MovingAverageParameters


class SensitivityEvaluationScope(StrEnum):
    FULL_HISTORY_RESEARCH = "full_history_research"


class ParameterSpaceTooLarge(ValueError):
    """Raised before execution when a requested surface exceeds its guard."""


@dataclass(frozen=True, slots=True)
class ParameterSensitivityConfiguration:
    parameters: Mapping[str, tuple[int, ...]]
    maximum_combinations: int
    evaluation_scope: SensitivityEvaluationScope = (
        SensitivityEvaluationScope.FULL_HISTORY_RESEARCH
    )

    def __post_init__(self) -> None:
        if set(self.parameters) != {"short_window", "long_window"}:
            raise ValueError("moving-average sensitivity requires both window axes")
        if (
            not isinstance(self.maximum_combinations, int)
            or isinstance(self.maximum_combinations, bool)
            or self.maximum_combinations <= 0
        ):
            raise ValueError("maximum_combinations must be a positive integer")
        copied: dict[str, tuple[int, ...]] = {}
        for name, configured in self.parameters.items():
            values = tuple(configured)
            if not values:
                raise ValueError(f"{name} values cannot be empty")
            if len(values) != len(set(values)):
                raise ValueError(f"{name} values must be unique")
            if any(
                not isinstance(value, int) or isinstance(value, bool)
                for value in values
            ):
                raise TypeError(f"{name} values must be integers")
            copied[name] = values
        object.__setattr__(self, "parameters", MappingProxyType(copied))


@dataclass(frozen=True, slots=True)
class ParameterCombination:
    index: int
    values: Mapping[str, int]
    is_baseline: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    @property
    def id(self) -> str:
        return f"COMBINATION-{self.index:03d}"


@dataclass(frozen=True, slots=True)
class ParameterSpace:
    requested_count: int
    invalid_count: int
    baseline_added: bool
    combinations: tuple[ParameterCombination, ...]


@dataclass(frozen=True, slots=True)
class ParameterCandidateResult:
    combination: ParameterCombination
    metrics: MetricSet
    backtest_result: BacktestResult
    relative_distance: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "relative_distance", MappingProxyType(dict(self.relative_distance))
        )


@dataclass(frozen=True, slots=True)
class ParameterSensitivitySummary:
    parameter_combinations_requested: int
    parameter_combinations_executed: int
    invalid_combination_count: int
    median_total_return: float
    median_sharpe: float | None
    median_max_drawdown: float | None
    min_sharpe: float | None
    max_sharpe: float | None
    return_dispersion: float
    sharpe_dispersion: float | None
    profitable_combination_count: int
    profitable_combination_ratio: float
    return_at_least_baseline_ratio: float
    sharpe_at_least_baseline_ratio: float | None
    drawdown_no_worse_than_baseline_ratio: float | None
    neighbor_count: int
    neighbor_median_sharpe: float | None
    neighbor_min_sharpe: float | None
    neighbor_max_sharpe: float | None
    sharpe_neighbor_delta: float | None


@dataclass(frozen=True, slots=True)
class ParameterSensitivityAnalysis:
    configuration: ParameterSensitivityConfiguration
    baseline_parameters: Mapping[str, int]
    baseline_metrics: MetricSet
    candidates: tuple[ParameterCandidateResult, ...]
    benchmark: BenchmarkResult
    summary: ParameterSensitivitySummary

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "baseline_parameters",
            MappingProxyType(dict(self.baseline_parameters)),
        )


def generate_parameter_combinations(
    configuration: ParameterSensitivityConfiguration,
    baseline: Mapping[str, object],
) -> ParameterSpace:
    baseline_values = _baseline_values(baseline)
    names = tuple(sorted(configuration.parameters))
    axes = tuple(configuration.parameters[name] for name in names)
    requested = prod(len(axis) for axis in axes)
    if requested > configuration.maximum_combinations:
        raise ParameterSpaceTooLarge(
            f"requested {requested} combinations exceeds maximum "
            f"{configuration.maximum_combinations}"
        )
    valid_values: list[dict[str, int]] = []
    invalid = 0
    for raw_values in product(*axes):
        values = dict(zip(names, raw_values, strict=True))
        try:
            MovingAverageParameters(**values)
        except (TypeError, ValueError):
            invalid += 1
            continue
        valid_values.append(values)
    baseline_added = baseline_values not in valid_values
    if baseline_added:
        if len(valid_values) + 1 > configuration.maximum_combinations:
            raise ParameterSpaceTooLarge("adding baseline exceeds maximum_combinations")
        valid_values.append(baseline_values)
    return ParameterSpace(
        requested_count=requested,
        invalid_count=invalid,
        baseline_added=baseline_added,
        combinations=tuple(
            ParameterCombination(index, values, values == baseline_values)
            for index, values in enumerate(valid_values, start=1)
        ),
    )


def summarize_parameter_sensitivity(
    space: ParameterSpace,
    results: tuple[ParameterCandidateResult, ...],
    configuration: ParameterSensitivityConfiguration,
) -> ParameterSensitivitySummary:
    if not results:
        raise ValueError("candidate results cannot be empty")
    baseline = next(
        (result for result in results if result.combination.is_baseline), None
    )
    if baseline is None:
        raise ValueError("baseline result is required")
    returns = [
        _required(result.metrics.total_return, "total_return") for result in results
    ]
    sharpes = [
        value
        for result in results
        if (value := result.metrics.sharpe) is not None
    ]
    drawdowns = [
        value
        for result in results
        if (value := result.metrics.max_drawdown) is not None
    ]
    profitable = sum(value > 0 for value in returns)
    baseline_return = _required(baseline.metrics.total_return, "baseline return")
    baseline_sharpe = baseline.metrics.sharpe
    baseline_drawdown = baseline.metrics.max_drawdown
    neighbors = _neighbors(results, baseline, configuration)
    neighbor_sharpes = [
        value for result in neighbors if (value := result.metrics.sharpe) is not None
    ]
    return ParameterSensitivitySummary(
        parameter_combinations_requested=space.requested_count,
        parameter_combinations_executed=len(results),
        invalid_combination_count=space.invalid_count,
        median_total_return=median(returns),
        median_sharpe=median(sharpes) if sharpes else None,
        median_max_drawdown=median(drawdowns) if drawdowns else None,
        min_sharpe=min(sharpes) if sharpes else None,
        max_sharpe=max(sharpes) if sharpes else None,
        return_dispersion=pstdev(returns),
        sharpe_dispersion=pstdev(sharpes) if sharpes else None,
        profitable_combination_count=profitable,
        profitable_combination_ratio=profitable / len(results),
        return_at_least_baseline_ratio=(
            sum(value >= baseline_return for value in returns) / len(returns)
        ),
        sharpe_at_least_baseline_ratio=(
            sum(value >= baseline_sharpe for value in sharpes) / len(sharpes)
            if baseline_sharpe is not None and sharpes
            else None
        ),
        drawdown_no_worse_than_baseline_ratio=(
            sum(value >= baseline_drawdown for value in drawdowns) / len(drawdowns)
            if baseline_drawdown is not None and drawdowns
            else None
        ),
        neighbor_count=len(neighbors),
        neighbor_median_sharpe=(median(neighbor_sharpes) if neighbor_sharpes else None),
        neighbor_min_sharpe=min(neighbor_sharpes) if neighbor_sharpes else None,
        neighbor_max_sharpe=max(neighbor_sharpes) if neighbor_sharpes else None,
        sharpe_neighbor_delta=(
            baseline_sharpe - median(neighbor_sharpes)
            if baseline_sharpe is not None and neighbor_sharpes
            else None
        ),
    )


def relative_parameter_distance(
    values: Mapping[str, int], baseline: Mapping[str, int]
) -> dict[str, float]:
    return {
        name: (values[name] - baseline[name]) / abs(baseline[name])
        for name in sorted(baseline)
    }


def _neighbors(
    results: tuple[ParameterCandidateResult, ...],
    baseline: ParameterCandidateResult,
    configuration: ParameterSensitivityConfiguration,
) -> tuple[ParameterCandidateResult, ...]:
    neighbor_values: set[tuple[tuple[str, int], ...]] = set()
    baseline_values = baseline.combination.values
    for name, configured in configuration.parameters.items():
        if baseline_values[name] not in configured:
            continue
        position = configured.index(baseline_values[name])
        for neighbor_position in (position - 1, position + 1):
            if 0 <= neighbor_position < len(configured):
                candidate = dict(baseline_values)
                candidate[name] = configured[neighbor_position]
                neighbor_values.add(tuple(sorted(candidate.items())))
    return tuple(
        result
        for result in results
        if tuple(sorted(result.combination.values.items())) in neighbor_values
    )


def _baseline_values(baseline: Mapping[str, object]) -> dict[str, int]:
    short = baseline.get("short_window")
    long = baseline.get("long_window")
    if not isinstance(short, int) or isinstance(short, bool):
        raise ValueError("baseline short_window must be an integer")
    if not isinstance(long, int) or isinstance(long, bool):
        raise ValueError("baseline long_window must be an integer")
    MovingAverageParameters(short, long)
    return {"short_window": short, "long_window": long}


def _required(value: float | None, name: str) -> float:
    if value is None:
        raise ValueError(f"{name} is required")
    return value
