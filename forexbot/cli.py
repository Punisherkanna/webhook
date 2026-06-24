"""Command-line entry point.

    python -m forexbot backtest --data data/EURUSD_M15.csv --strategy ma_crossover
    python -m forexbot live --config config.yaml
    python -m forexbot live --config config.yaml --live   # disable dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from .backtest.data import load_csv
from .backtest.engine import Backtester, BacktestConfig
from .config import AppConfig
from .core.engine import TradingEngine
from .core.risk import RiskConfig
from .strategies import get_strategy


def _build_broker(cfg: AppConfig):
    name = cfg.broker.lower()
    opts = cfg.broker_options
    if name == "paper":
        from .brokers.paper import PaperBroker
        return PaperBroker(starting_balance=opts.get("starting_balance", 10_000.0))
    if name == "mt5":
        from .brokers.mt5_broker import MT5Broker
        return MT5Broker(**opts)
    if name == "ninjatrader":
        from .brokers.ninjatrader_broker import NinjaTraderBroker
        return NinjaTraderBroker(**opts)
    raise ValueError(f"unknown broker '{cfg.broker}'")


def cmd_backtest(args) -> int:
    if args.config:
        cfg = AppConfig.load(args.config)
        strategy_name = args.strategy or cfg.strategy
        params = cfg.strategy_params
        symbol = cfg.symbol
        risk = cfg.risk
    else:
        strategy_name = args.strategy or "ma_crossover"
        params = {}
        symbol = args.symbol
        risk = RiskConfig(risk_per_trade=args.risk)

    bars = load_csv(args.data)
    if not bars:
        print(f"no bars loaded from {args.data}", file=sys.stderr)
        return 1

    strat_cls = get_strategy(strategy_name)
    strategy = strat_cls(symbol=symbol, params=params)
    bt_cfg = BacktestConfig(
        symbol=symbol,
        starting_equity=args.equity,
        spread_pips=args.spread,
        commission_per_lot=args.commission,
        risk=risk,
    )
    result = Backtester(strategy, bt_cfg).run(bars)
    print(f"\n=== Backtest: {strategy_name} on {symbol} "
          f"({len(bars)} bars) ===")
    print(result.summary())

    if args.plot:
        from .backtest.plot import save_equity_plot
        out = save_equity_plot(result, args.plot)
        print(f"\nEquity curve saved to {out}")
    return 0


def cmd_live(args) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = AppConfig.load(args.config)
    broker = _build_broker(cfg)
    strategy = get_strategy(cfg.strategy)(symbol=cfg.symbol,
                                          params=cfg.strategy_params)
    cfg.engine.dry_run = not args.live
    engine = TradingEngine(broker, strategy, cfg.risk, cfg.engine)
    engine.run_forever()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="forexbot",
                                description="Forex trading robot (MT5 / NinjaTrader)")
    sub = p.add_subparsers(dest="command", required=True)

    bt = sub.add_parser("backtest", help="run a backtest over CSV data")
    bt.add_argument("--data", required=True, help="OHLCV CSV path")
    bt.add_argument("--config", help="optional config.yaml for strategy/risk")
    bt.add_argument("--strategy", help="strategy name (overrides config)")
    bt.add_argument("--symbol", default="EURUSD")
    bt.add_argument("--equity", type=float, default=10_000.0)
    bt.add_argument("--spread", type=float, default=0.8, help="spread in pips")
    bt.add_argument("--commission", type=float, default=7.0, help="per lot per side")
    bt.add_argument("--risk", type=float, default=0.01, help="risk per trade (0-1)")
    bt.add_argument("--plot", metavar="PATH",
                    help="save equity-curve chart to PATH (.svg needs no deps; "
                         ".png needs matplotlib)")
    bt.set_defaults(func=cmd_backtest)

    live = sub.add_parser("live", help="run the live/paper trading engine")
    live.add_argument("--config", required=True, help="config.yaml path")
    live.add_argument("--live", action="store_true",
                      help="actually send orders (default is dry-run)")
    live.set_defaults(func=cmd_live)
    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
