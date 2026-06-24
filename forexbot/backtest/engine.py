"""Event-driven backtesting engine.

Replays bars one at a time through a strategy, simulates fills with spread and
commission, manages a single position with stop-loss/take-profit, and produces a
:class:`BacktestResult` with an equity curve and trade-by-trade breakdown.

Design notes / honesty about assumptions:
  * Entries fill at the next bar's open (no look-ahead on the signal bar).
  * Stops/targets are checked against each bar's high/low. When a bar straddles
    both, we conservatively assume the STOP hit first (worst case).
  * Spread is applied as a half-spread to each side; commission is per-lot,
    per-side.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..core.models import Bar, Position, Side, Signal, SignalType, Trade
from ..core.risk import RiskConfig, RiskManager, pip_size
from ..core.strategy import Strategy


@dataclass
class BacktestConfig:
    symbol: str = "EURUSD"
    starting_equity: float = 10_000.0
    spread_pips: float = 0.8          # round-turn spread in pips
    commission_per_lot: float = 7.0   # cash per lot, per side
    risk: RiskConfig = field(default_factory=RiskConfig)


@dataclass
class BacktestResult:
    config: BacktestConfig
    trades: List[Trade]
    equity_curve: List[float]
    starting_equity: float
    ending_equity: float

    # --- summary statistics -------------------------------------------------
    @property
    def net_profit(self) -> float:
        return self.ending_equity - self.starting_equity

    @property
    def return_pct(self) -> float:
        if self.starting_equity == 0:
            return 0.0
        return self.net_profit / self.starting_equity * 100.0

    @property
    def num_trades(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> List[Trade]:
        return [t for t in self.trades if t.pnl > 0]

    @property
    def losses(self) -> List[Trade]:
        return [t for t in self.trades if t.pnl <= 0]

    @property
    def win_rate(self) -> float:
        return len(self.wins) / self.num_trades * 100.0 if self.num_trades else 0.0

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.pnl for t in self.wins)
        gross_loss = abs(sum(t.pnl for t in self.losses))
        if gross_loss == 0:
            return float("inf") if gross_win > 0 else 0.0
        return gross_win / gross_loss

    @property
    def max_drawdown_pct(self) -> float:
        """Largest peak-to-trough drop on the equity curve, as a percentage."""
        peak = self.equity_curve[0] if self.equity_curve else self.starting_equity
        max_dd = 0.0
        for eq in self.equity_curve:
            peak = max(peak, eq)
            if peak > 0:
                max_dd = max(max_dd, (peak - eq) / peak)
        return max_dd * 100.0

    def summary(self) -> str:
        return (
            f"Symbol:          {self.config.symbol}\n"
            f"Trades:          {self.num_trades}\n"
            f"Win rate:        {self.win_rate:.1f}%\n"
            f"Net profit:      {self.net_profit:,.2f} "
            f"({self.return_pct:+.2f}%)\n"
            f"Profit factor:   {self.profit_factor:.2f}\n"
            f"Max drawdown:    {self.max_drawdown_pct:.2f}%\n"
            f"Start equity:    {self.starting_equity:,.2f}\n"
            f"End equity:      {self.ending_equity:,.2f}"
        )


class Backtester:
    """Run a single-symbol, single-position backtest."""

    def __init__(self, strategy: Strategy, config: BacktestConfig) -> None:
        self.strategy = strategy
        self.config = config
        self.risk = RiskManager(config.risk)

    def run(self, bars: List[Bar]) -> BacktestResult:
        cfg = self.config
        pip = pip_size(cfg.symbol)
        half_spread = (cfg.spread_pips * pip) / 2.0

        equity = cfg.starting_equity
        equity_curve: List[float] = [equity]
        trades: List[Trade] = []
        position: Optional[Position] = None
        pending: Optional[Signal] = None  # signal awaiting next-bar open fill

        for bar in bars:
            # 1) Manage an open position against this bar's range first.
            if position is not None:
                exit_info = self._check_exit(position, bar, half_spread)
                if exit_info is not None:
                    exit_price, reason = exit_info
                    trade, pnl = self._close(position, bar, exit_price, reason,
                                             pip, half_spread)
                    equity += pnl
                    trades.append(trade)
                    position = None

            # 2) Fill a pending entry at this bar's open.
            if position is None and pending is not None:
                position = self._open(pending, bar, equity, half_spread)
                pending = None

            # 3) Feed the bar to the strategy for a new decision.
            signal = self.strategy.update(bar)
            if position is None and signal.type in (
                SignalType.ENTER_LONG, SignalType.ENTER_SHORT
            ):
                pending = signal
            elif position is not None and signal.type is SignalType.EXIT:
                # Exit at next concept isn't needed; close at this close.
                exit_price = bar.close - half_spread * position.side.sign
                trade, pnl = self._close(position, bar, exit_price,
                                         "strategy exit", pip, half_spread)
                equity += pnl
                trades.append(trade)
                position = None

            equity_curve.append(self._mark_to_market(equity, position, bar))

        return BacktestResult(
            config=cfg,
            trades=trades,
            equity_curve=equity_curve,
            starting_equity=cfg.starting_equity,
            ending_equity=equity,
        )

    # --- internals ----------------------------------------------------------
    def _open(self, signal: Signal, bar: Bar, equity: float,
              half_spread: float) -> Optional[Position]:
        side = Side.BUY if signal.type is SignalType.ENTER_LONG else Side.SELL
        # Buyers pay the ask, sellers receive the bid.
        entry = bar.open + half_spread * side.sign
        stop = signal.stop_loss
        if stop is None:
            return None
        lots = self.risk.size_for_stop(equity, self.config.symbol, entry, stop)
        if lots <= 0:
            return None
        return Position(
            symbol=self.config.symbol,
            side=side,
            volume=lots,
            entry_price=entry,
            open_time=bar.timestamp,
            stop_loss=stop,
            take_profit=signal.take_profit,
        )

    def _check_exit(self, pos: Position, bar: Bar,
                    half_spread: float) -> Optional[tuple]:
        """Return (exit_price, reason) if SL/TP hit this bar, else None."""
        if pos.side is Side.BUY:
            # Conservative: check stop before target if both are inside the bar.
            if pos.stop_loss is not None and bar.low <= pos.stop_loss:
                return pos.stop_loss - half_spread, "stop loss"
            if pos.take_profit is not None and bar.high >= pos.take_profit:
                return pos.take_profit - half_spread, "take profit"
        else:
            if pos.stop_loss is not None and bar.high >= pos.stop_loss:
                return pos.stop_loss + half_spread, "stop loss"
            if pos.take_profit is not None and bar.low <= pos.take_profit:
                return pos.take_profit + half_spread, "take profit"
        return None

    def _close(self, pos: Position, bar: Bar, exit_price: float, reason: str,
               pip: float, half_spread: float) -> tuple:
        cs = self.config.risk.contract_size
        gross = (exit_price - pos.entry_price) * pos.side.sign * pos.volume * cs
        commission = self.config.commission_per_lot * pos.volume * 2  # both sides
        pnl = gross - commission
        pnl_pips = (exit_price - pos.entry_price) * pos.side.sign / pip
        trade = Trade(
            symbol=pos.symbol,
            side=pos.side,
            volume=pos.volume,
            entry_time=pos.open_time,
            entry_price=pos.entry_price,
            exit_time=bar.timestamp,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pips=pnl_pips,
            reason=reason,
        )
        return trade, pnl

    def _mark_to_market(self, equity: float, pos: Optional[Position],
                        bar: Bar) -> float:
        if pos is None:
            return equity
        return equity + pos.unrealized_pnl(bar.close, self.config.risk.contract_size)
