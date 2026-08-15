import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from types import MappingProxyType

from quant.domain import MetricSet

MONTE_CARLO_VERSION = "monte-carlo-v1"
MAX_SIMULATION_COUNT = 100_000
MIN_OBSERVATION_COUNT = 2


class SamplingMethod(StrEnum):
    TRADE_BOOTSTRAP = "trade_bootstrap"


@dataclass(frozen=True, slots=True)
class MonteCarloConfiguration:
    simulation_count: int
    random_seed: int
    confidence_percentiles: tuple[Decimal, ...]
    sampling_method: SamplingMethod
    drawdown_threshold: Decimal | None = None
    ruin_equity_fraction: Decimal | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.simulation_count, int)
            or isinstance(self.simulation_count, bool)
            or self.simulation_count <= 0
        ):
            raise ValueError("simulation_count must be a positive integer")
        if self.simulation_count > MAX_SIMULATION_COUNT:
            raise ValueError(
                f"simulation_count exceeds maximum {MAX_SIMULATION_COUNT}"
            )
        if not isinstance(self.random_seed, int) or isinstance(self.random_seed, bool):
            raise TypeError("random_seed must be an integer")
        if not self.confidence_percentiles:
            raise ValueError("confidence_percentiles cannot be empty")
        if len(self.confidence_percentiles) != len(set(self.confidence_percentiles)):
            raise ValueError("confidence_percentiles must be unique")
        for percentile in self.confidence_percentiles:
            if (
                not isinstance(percentile, Decimal)
                or not percentile.is_finite()
                or percentile < 0
                or percentile > 1
            ):
                raise ValueError("percentiles must be finite Decimals from 0 to 1")
        if self.drawdown_threshold is not None and (
            not self.drawdown_threshold.is_finite()
            or self.drawdown_threshold >= 0
            or self.drawdown_threshold < -1
        ):
            raise ValueError("drawdown_threshold must be between -1 and 0")
        if self.ruin_equity_fraction is not None and (
            not self.ruin_equity_fraction.is_finite()
            or self.ruin_equity_fraction <= 0
            or self.ruin_equity_fraction >= 1
        ):
            raise ValueError("ruin_equity_fraction must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class MonteCarloPathSummary:
    simulation_index: int
    final_equity: Decimal
    minimum_equity: Decimal
    total_return: Decimal
    max_drawdown: Decimal
    max_consecutive_losses: int


@dataclass(frozen=True, slots=True)
class MonteCarloDistributionSummary:
    final_equity_percentiles: Mapping[str, Decimal]
    total_return_percentiles: Mapping[str, Decimal]
    max_drawdown_percentiles: Mapping[str, Decimal]
    max_losing_streak_percentiles: Mapping[str, Decimal]
    empirical_loss_frequency: float
    empirical_severe_drawdown_frequency: float | None
    empirical_ruin_frequency: float | None
    historical_total_return_percentile: float | None

    def __post_init__(self) -> None:
        for name in (
            "final_equity_percentiles",
            "total_return_percentiles",
            "max_drawdown_percentiles",
            "max_losing_streak_percentiles",
        ):
            object.__setattr__(
                self, name, MappingProxyType(dict(getattr(self, name)))
            )


@dataclass(frozen=True, slots=True)
class MonteCarloAnalysis:
    configuration: MonteCarloConfiguration
    source_observation_count: int
    observation_fingerprint: str
    historical_metrics: MetricSet
    path_summaries: tuple[MonteCarloPathSummary, ...]
    distribution: MonteCarloDistributionSummary


def trade_return_observations(
    trades: Sequence[Mapping[str, object]],
) -> tuple[Decimal, ...]:
    observations: list[Decimal] = []
    for trade in trades:
        entry_price = _decimal_value(trade, "entry_price")
        entry_fees = _decimal_value(trade, "entry_fees")
        realized_pnl = _decimal_value(trade, "realized_pnl")
        quantity = trade.get("quantity")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("trade quantity must be a positive integer")
        with localcontext(Context(prec=64)):
            capital_basis = entry_price * Decimal(quantity) + entry_fees
            if capital_basis <= 0:
                raise ValueError("trade capital basis must be positive")
            trade_return = realized_pnl / capital_basis
        if trade_return <= -1:
            raise ValueError("trade return cannot lose more than its capital basis")
        observations.append(trade_return)
    if len(observations) < MIN_OBSERVATION_COUNT:
        raise ValueError(
            f"trade bootstrap requires at least {MIN_OBSERVATION_COUNT} observations"
        )
    return tuple(observations)


def simulate_trade_bootstrap(
    observations: tuple[Decimal, ...],
    initial_equity: Decimal,
    configuration: MonteCarloConfiguration,
) -> tuple[MonteCarloPathSummary, ...]:
    if len(observations) < MIN_OBSERVATION_COUNT:
        raise ValueError("insufficient bootstrap observations")
    if initial_equity <= 0 or not initial_equity.is_finite():
        raise ValueError("initial_equity must be positive and finite")
    if any(value <= -1 or not value.is_finite() for value in observations):
        raise ValueError("observed returns must be finite and greater than -1")
    rng = random.Random(configuration.random_seed)
    paths: list[MonteCarloPathSummary] = []
    for simulation_index in range(1, configuration.simulation_count + 1):
        sampled = tuple(rng.choice(observations) for _ in observations)
        paths.append(
            summarize_bootstrap_path(simulation_index, initial_equity, sampled)
        )
    return tuple(paths)


def summarize_monte_carlo(
    paths: tuple[MonteCarloPathSummary, ...],
    initial_equity: Decimal,
    configuration: MonteCarloConfiguration,
    historical_total_return: float | None,
) -> MonteCarloDistributionSummary:
    if not paths:
        raise ValueError("path summaries cannot be empty")
    percentiles = configuration.confidence_percentiles
    finals = tuple(path.final_equity for path in paths)
    returns = tuple(path.total_return for path in paths)
    drawdowns = tuple(path.max_drawdown for path in paths)
    streaks = tuple(Decimal(path.max_consecutive_losses) for path in paths)
    count = len(paths)
    severe_frequency = (
        sum(path.max_drawdown <= configuration.drawdown_threshold for path in paths)
        / count
        if configuration.drawdown_threshold is not None
        else None
    )
    ruin_level = (
        initial_equity * configuration.ruin_equity_fraction
        if configuration.ruin_equity_fraction is not None
        else None
    )
    historical_decimal = (
        Decimal(str(historical_total_return))
        if historical_total_return is not None
        else None
    )
    return MonteCarloDistributionSummary(
        final_equity_percentiles=_percentiles(finals, percentiles),
        total_return_percentiles=_percentiles(returns, percentiles),
        max_drawdown_percentiles=_percentiles(drawdowns, percentiles),
        max_losing_streak_percentiles=_percentiles(streaks, percentiles),
        empirical_loss_frequency=(
            sum(value < initial_equity for value in finals) / count
        ),
        empirical_severe_drawdown_frequency=severe_frequency,
        empirical_ruin_frequency=(
            sum(path.minimum_equity <= ruin_level for path in paths) / count
            if ruin_level is not None
            else None
        ),
        historical_total_return_percentile=(
            sum(value <= historical_decimal for value in returns) / count
            if historical_decimal is not None
            else None
        ),
    )


def percentile(values: Sequence[Decimal], probability: Decimal) -> Decimal:
    if not values:
        raise ValueError("percentile values cannot be empty")
    if probability < 0 or probability > 1:
        raise ValueError("percentile probability must be between 0 and 1")
    ordered = sorted(values)
    with localcontext(Context(prec=64)):
        position = Decimal(len(ordered) - 1) * probability
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = position - Decimal(lower)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def maximum_consecutive_losses(returns: Sequence[Decimal]) -> int:
    maximum = 0
    current = 0
    for value in returns:
        if value < 0:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def summarize_bootstrap_path(
    simulation_index: int,
    initial_equity: Decimal,
    sampled_returns: Sequence[Decimal],
) -> MonteCarloPathSummary:
    if initial_equity <= 0 or not initial_equity.is_finite():
        raise ValueError("initial_equity must be positive and finite")
    if any(value < -1 or not value.is_finite() for value in sampled_returns):
        raise ValueError("sampled returns must be finite and at least -1")
    equity = initial_equity
    peak = initial_equity
    minimum = initial_equity
    max_drawdown = Decimal(0)
    with localcontext(Context(prec=64)):
        for value in sampled_returns:
            equity *= Decimal(1) + value
            if equity <= 0:
                equity = Decimal(0)
                minimum = Decimal(0)
                max_drawdown = Decimal(-1)
                break
            peak = max(peak, equity)
            minimum = min(minimum, equity)
            max_drawdown = min(max_drawdown, equity / peak - Decimal(1))
        total_return = equity / initial_equity - Decimal(1)
    return MonteCarloPathSummary(
        simulation_index,
        equity,
        minimum,
        total_return,
        max_drawdown,
        maximum_consecutive_losses(sampled_returns),
    )


def _percentiles(
    values: Sequence[Decimal], probabilities: tuple[Decimal, ...]
) -> dict[str, Decimal]:
    return {
        f"p{int(probability * 100):02d}": percentile(values, probability)
        for probability in probabilities
    }


def _decimal_value(values: Mapping[str, object], name: str) -> Decimal:
    value = values.get(name)
    if not isinstance(value, str):
        raise ValueError(f"trade {name} must be a canonical decimal string")
    try:
        return Decimal(value)
    except ValueError as error:
        raise ValueError(f"trade {name} is invalid") from error
