from dataclasses import dataclass
from datetime import datetime
from decimal import Context, Decimal, localcontext

from quant.backtest.configuration import BacktestConfiguration
from quant.backtest.execution import ExecutionSimulator
from quant.backtest.models import EquityPoint, Fill, Order, OrderSide, Position, Trade
from quant.backtest.portfolio import Portfolio
from quant.domain import HistoricalDataset, Signal, SignalAction
from quant.strategies import ExecutableStrategy


@dataclass(frozen=True, slots=True)
class BacktestResult:
    configuration: BacktestConfiguration
    initial_cash: Decimal
    final_cash: Decimal
    final_equity: Decimal
    signals: tuple[Signal, ...]
    orders: tuple[Order, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    equity_curve: tuple[EquityPoint, ...]
    open_position: Position | None
    skipped_signals: tuple[Signal, ...]
    unexecuted_signals: tuple[Signal, ...]


@dataclass(frozen=True, slots=True)
class BacktestEngine:
    """Deterministic single-asset LONG/FLAT event-driven simulator."""

    def run(
        self,
        dataset: HistoricalDataset,
        strategy: ExecutableStrategy,
        configuration: BacktestConfiguration,
    ) -> BacktestResult:
        portfolio = Portfolio(configuration.initial_cash)
        execution = ExecutionSimulator(
            configuration.fee_model, configuration.slippage_model
        )
        signals: list[Signal] = []
        orders: list[Order] = []
        fills: list[Fill] = []
        trades: list[Trade] = []
        equity_curve: list[EquityPoint] = []
        skipped_signals: list[Signal] = []
        pending: Signal | None = None

        for index, bar in enumerate(dataset.bars):
            if pending is not None:
                order = self._create_order(
                    pending,
                    bar.timestamp,
                    bar.open,
                    portfolio,
                    configuration,
                    len(orders) + 1,
                )
                if order is None:
                    skipped_signals.append(pending)
                else:
                    fill = execution.execute(order)
                    orders.append(order)
                    fills.append(fill)
                    if fill.side is OrderSide.BUY:
                        portfolio.apply_buy(fill)
                    else:
                        trades.append(portfolio.apply_sell(fill))
                pending = None

            equity_curve.append(portfolio.mark(bar.timestamp, bar.close))
            prefix = HistoricalDataset.from_bars(
                market=dataset.market,
                instrument=dataset.instrument,
                timeframe=dataset.timeframe,
                adjustment_policy=dataset.adjustment_policy,
                bars=dataset.bars[: index + 1],
                metadata=dataset.metadata,
            )
            current_signal = self._current_signal(strategy, prefix, bar.timestamp)
            if current_signal is not None:
                signals.append(current_signal)
                desired_long = current_signal.action is SignalAction.LONG
                if desired_long != portfolio.is_long:
                    pending = current_signal

        final_point = equity_curve[-1]
        return BacktestResult(
            configuration=configuration,
            initial_cash=configuration.initial_cash,
            final_cash=portfolio.cash,
            final_equity=final_point.equity,
            signals=tuple(signals),
            orders=tuple(orders),
            fills=tuple(fills),
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            open_position=portfolio.position(dataset.bars[-1].close),
            skipped_signals=tuple(skipped_signals),
            unexecuted_signals=(pending,) if pending is not None else (),
        )

    @staticmethod
    def _current_signal(
        strategy: ExecutableStrategy,
        prefix: HistoricalDataset,
        timestamp: datetime,
    ) -> Signal | None:
        generated = tuple(strategy.generate_signals(prefix))
        if any(signal.timestamp > prefix.bars[-1].timestamp for signal in generated):
            raise ValueError("strategy generated a signal from future data")
        current = [signal for signal in generated if signal.timestamp == timestamp]
        if len(current) > 1:
            raise ValueError("strategy generated duplicate signals for one timestamp")
        return current[0] if current else None

    @staticmethod
    def _create_order(
        signal: Signal,
        timestamp: datetime,
        reference_price: Decimal,
        portfolio: Portfolio,
        configuration: BacktestConfiguration,
        sequence: int,
    ) -> Order | None:
        if signal.action is SignalAction.FLAT:
            quantity = portfolio.quantity
            side = OrderSide.SELL
        else:
            side = OrderSide.BUY
            quantity = BacktestEngine._maximum_affordable_quantity(
                portfolio.cash,
                configuration.position_fraction,
                reference_price,
                configuration,
            )
        if quantity == 0:
            return None
        return Order(
            id=f"ORDER-{sequence:06d}",
            timestamp=timestamp,
            side=side,
            quantity=quantity,
            reference_price=reference_price,
        )

    @staticmethod
    def _maximum_affordable_quantity(
        cash: Decimal,
        fraction: Decimal,
        reference_price: Decimal,
        configuration: BacktestConfiguration,
    ) -> int:
        fill_price = configuration.slippage_model.apply(
            side=OrderSide.BUY, reference_price=reference_price
        )
        with localcontext(Context(prec=64)):
            allocation = cash * fraction
            high = int(allocation // fill_price)
            low = 0
            while low < high:
                candidate = (low + high + 1) // 2
                fees = configuration.fee_model.calculate(
                    quantity=candidate, price=fill_price
                )
                if fees < 0:
                    raise ValueError("fee model returned a negative fee")
                cost = Decimal(candidate) * fill_price + fees
                if cost <= allocation:
                    low = candidate
                else:
                    high = candidate - 1
            return low
