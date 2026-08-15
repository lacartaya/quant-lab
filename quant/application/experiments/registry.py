from collections.abc import Mapping
from decimal import Decimal

from quant.analytics import METRICS_VERSION, AnalyticsConfiguration, analyze_backtest
from quant.backtest import (
    BACKTEST_ENGINE_VERSION,
    BacktestConfiguration,
    BacktestEngine,
    BasisPointsSlippageModel,
    FeeModel,
    PercentageFeeModel,
    SlippageModel,
    ZeroFeeModel,
    ZeroSlippageModel,
)
from quant.domain import StrategyVersion
from quant.strategies import MovingAverageParameters, MovingAverageTrendStrategy


class UnsupportedVersionError(ValueError):
    """Raised when persisted lineage names an unavailable implementation."""


def build_strategy(version: StrategyVersion) -> MovingAverageTrendStrategy:
    if version.algorithm_key != MovingAverageTrendStrategy.strategy_key:
        raise UnsupportedVersionError(
            f"unsupported strategy algorithm: {version.algorithm_key}"
        )
    short_window = version.parameters.get("short_window")
    long_window = version.parameters.get("long_window")
    if not isinstance(short_window, int) or isinstance(short_window, bool):
        raise ValueError("short_window must be persisted as an integer")
    if not isinstance(long_window, int) or isinstance(long_window, bool):
        raise ValueError("long_window must be persisted as an integer")
    return MovingAverageTrendStrategy(
        MovingAverageParameters(short_window, long_window)
    )


def serialize_execution_configuration(
    backtest: BacktestConfiguration, analytics: AnalyticsConfiguration
) -> dict[str, object]:
    if isinstance(backtest.fee_model, ZeroFeeModel):
        fee_configuration: dict[str, object] = {
            "version": backtest.fee_model.version
        }
    elif isinstance(backtest.fee_model, PercentageFeeModel):
        fee_configuration = {
            "version": backtest.fee_model.version,
            "rate": str(backtest.fee_model.rate),
        }
    else:
        raise UnsupportedVersionError("unsupported fee model")
    if isinstance(backtest.slippage_model, ZeroSlippageModel):
        slippage_configuration: dict[str, object] = {
            "version": backtest.slippage_model.version
        }
    elif isinstance(backtest.slippage_model, BasisPointsSlippageModel):
        slippage_configuration = {
            "version": backtest.slippage_model.version,
            "basis_points": str(backtest.slippage_model.basis_points),
        }
    else:
        raise UnsupportedVersionError("unsupported slippage model")
    return {
        "engine_version": BACKTEST_ENGINE_VERSION,
        "backtest": {
            "initial_cash": str(backtest.initial_cash),
            "position_fraction": str(backtest.position_fraction),
        },
        "fee": fee_configuration,
        "slippage": slippage_configuration,
        "analytics": {
            "version": METRICS_VERSION,
            "periods_per_year": analytics.periods_per_year,
            "annual_risk_free_rate": str(analytics.annual_risk_free_rate),
        },
        "benchmark": "BUY_AND_HOLD",
    }


def reconstruct_configurations(
    stored: Mapping[str, object],
) -> tuple[BacktestConfiguration, AnalyticsConfiguration]:
    engine_version = stored.get("engine_version")
    if engine_version != BACKTEST_ENGINE_VERSION:
        raise UnsupportedVersionError(f"unsupported backtest engine: {engine_version}")
    backtest_values = _mapping(stored.get("backtest"), "backtest")
    fee_values = _mapping(stored.get("fee"), "fee")
    slippage_values = _mapping(stored.get("slippage"), "slippage")
    analytics_values = _mapping(stored.get("analytics"), "analytics")

    fee_version = fee_values.get("version")
    if fee_version == ZeroFeeModel.version:
        fee_model: FeeModel = ZeroFeeModel()
    elif isinstance(fee_version, str) and fee_version.startswith("percentage-v1:"):
        fee_model = PercentageFeeModel(Decimal(_string(fee_values, "rate")))
    else:
        raise UnsupportedVersionError(f"unsupported fee model: {fee_version}")

    slippage_version = slippage_values.get("version")
    if slippage_version == ZeroSlippageModel.version:
        slippage_model: SlippageModel = ZeroSlippageModel()
    elif isinstance(slippage_version, str) and slippage_version.startswith(
        "basis-points-v1:"
    ):
        slippage_model = BasisPointsSlippageModel(
            Decimal(_string(slippage_values, "basis_points"))
        )
    else:
        raise UnsupportedVersionError(
            f"unsupported slippage model: {slippage_version}"
        )

    analytics_version = analytics_values.get("version")
    if analytics_version != METRICS_VERSION:
        raise UnsupportedVersionError(
            f"unsupported analytics version: {analytics_version}"
        )
    periods = analytics_values.get("periods_per_year")
    if not isinstance(periods, int) or isinstance(periods, bool):
        raise ValueError("periods_per_year must be persisted as an integer")
    return (
        BacktestConfiguration(
            initial_cash=Decimal(_string(backtest_values, "initial_cash")),
            position_fraction=Decimal(_string(backtest_values, "position_fraction")),
            fee_model=fee_model,
            slippage_model=slippage_model,
        ),
        AnalyticsConfiguration(
            periods_per_year=periods,
            annual_risk_free_rate=Decimal(
                _string(analytics_values, "annual_risk_free_rate")
            ),
        ),
    )


def resolve_engine(version: str) -> BacktestEngine:
    if version != BACKTEST_ENGINE_VERSION:
        raise UnsupportedVersionError(f"unsupported backtest engine: {version}")
    return BacktestEngine()


def resolve_analytics(version: str) -> object:
    if version != METRICS_VERSION:
        raise UnsupportedVersionError(f"unsupported analytics version: {version}")
    return analyze_backtest


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} configuration is missing")
    return value


def _string(values: Mapping[str, object], field_name: str) -> str:
    value = values.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} configuration is missing")
    return value
