# forexbot

A broker-agnostic **Forex trading robot in Python** with an event-driven
**backtester** and live execution on **MetaTrader 5** and **NinjaTrader 8**.

The same strategy object runs unchanged in backtest, on a paper broker, on MT5,
and on NinjaTrader — strategies and the engine only ever talk to a `Broker`
interface, so switching venues is a one-line config change.

> **Strategies are single-position trend/momentum models.** There is no grid,
> hedging, HFT, or martingale logic anywhere in this project — every entry takes
> one position with a fixed, ATR-based protective stop.

## Highlights

- **Zero heavy dependencies for the core.** Engine, backtester, indicators, and
  strategies use only the Python standard library + PyYAML. No numpy/pandas.
- **Backtester** with spread + commission modelling, ATR stops/targets, and a
  full stats report (win rate, profit factor, max drawdown, equity curve).
- **Risk-first position sizing** — every trade is sized to risk a fixed fraction
  of equity given its stop distance, snapped to broker lot steps.
- **Pluggable brokers**: `paper` (in-memory), `mt5` (official MetaTrader5
  package), `ninjatrader` (file-based ATI bridge).
- **Tested**: 34 unit tests covering indicators, risk, backtest fills,
  strategies, the live engine, and the NinjaTrader bridge.

## Strategies

All are single-position trend/momentum models with ATR-based protective stops —
no grid, hedging, HFT, or martingale logic.

| Name                 | Type            | Idea                                                        |
|----------------------|-----------------|-------------------------------------------------------------|
| `ma_crossover`       | Trend           | Fast SMA crosses the slow SMA.                              |
| `rsi_reversion`      | Mean-reversion  | RSI exits oversold/overbought.                              |
| `donchian_breakout`  | Breakout        | Price breaks the prior N-bar high/low (Turtle-style).      |
| `macd_trend`         | Trend           | MACD/signal cross, filtered by a slow-EMA trend direction. |
| `bollinger_breakout` | Breakout        | Close pushes outside a Bollinger Band.                      |

```bash
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy donchian_breakout
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy macd_trend
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy bollinger_breakout
```

> Spanish docs: see [README.es.md](README.es.md).

## Project layout

```
forexbot/
  core/        models, Broker & Strategy interfaces, risk manager, live engine
  indicators/  pure-Python SMA, EMA, RSI, ATR
  strategies/  ma_crossover, rsi_reversion, donchian_breakout, macd_trend,
               bollinger_breakout (+ registry)
  backtest/    event-driven engine + CSV data loader
  brokers/     paper, mt5_broker, ninjatrader_broker
  config.py    YAML -> typed config
  cli.py       `python -m forexbot ...`
examples/      synthetic data generator
tests/         pytest suite
data/          sample EURUSD M15 CSV
```

## Quick start

```bash
pip install -r requirements.txt          # just PyYAML for the core
pip install pytest                        # for the tests

# Generate fresh sample data (optional; a sample is committed)
python examples/generate_sample_data.py --rows 2000 --out data/EURUSD_M15.csv

# Backtest
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy ma_crossover
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy rsi_reversion

# Run tests
python -m pytest -q
```

Example backtest output:

```
=== Backtest: ma_crossover on EURUSD (2000 bars) ===
Symbol:          EURUSD
Trades:          19
Win rate:        63.2%
Net profit:      884.43 (+8.84%)
Profit factor:   2.07
Max drawdown:    2.58%
```

> The committed dataset is **synthetic** — results demonstrate the engine, not a
> profitable system. Always validate strategies on real historical data.

### Equity-curve plot

Add `--plot PATH` to save a chart of the equity curve (blue), high-water mark
(dashed green), and drawdown (red shading):

```bash
# .svg uses a built-in zero-dependency renderer (no extra packages)
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy macd_trend \
    --plot equity.svg

# .png requires matplotlib (pip install matplotlib)
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy macd_trend \
    --plot equity.png
```

The format is chosen from the file extension. SVG works out of the box; PNG is
only needed if you specifically want a raster image.

## Live / paper trading

```bash
cp config.example.yaml config.yaml       # then edit broker, symbol, strategy
python -m forexbot live --config config.yaml          # dry-run (logs intended orders)
python -m forexbot live --config config.yaml --live   # actually send orders
```

The engine acts on **closed bars only** and respects `max_open_positions`, so
live behaviour matches the backtester. `dry_run` (the default) logs every
intended order without sending it.

### MetaTrader 5

On a Windows host with the MT5 terminal running:

```bash
pip install MetaTrader5
```

```yaml
broker: mt5
broker_options:
  login: 12345678
  password: "your-password"
  server: "YourBroker-Demo"
```

The adapter maps timeframe strings to MT5 constants, pulls rates via
`copy_rates_from_pos`, and submits market orders with attached SL/TP.

**Windows one-click launchers:** double-click scripts in
[`scripts/windows/`](scripts/windows/) — `install.bat`, `run_dry.bat`,
`run_live.bat`, `backtest.bat` — to install deps and run the bot without typing
commands.

### NinjaTrader 8

NinjaTrader has no official Python SDK, so this adapter drives its supported
**Automated Trading Interface (ATI)** through *Order Instruction Files* — plain
text commands dropped into `Documents/NinjaTrader 8/incoming/`.

1. In NinjaTrader: **Tools → Options → Automated trading interface** → enable
   *AT Interface*.
2. Configure the broker:

```yaml
broker: ninjatrader
broker_options:
  account: "Sim101"
  incoming_dir: "C:/Users/you/Documents/NinjaTrader 8/incoming"
  data_dir: "C:/Users/you/Documents/NinjaTrader 8/export"   # for bars
```

**Boundaries (by design):** the ATI is order-centric. `place_order` /
`close_position` are robust. Bars do **not** stream over the file bridge — point
`data_dir` at a NinjaScript CSV export, or feed market data from MT5/CSV and use
NinjaTrader purely for execution. `get_positions`/`get_account` read optional
state files (`positions.csv`, `account.csv`) that a companion NinjaScript can
write back; absent those, they return empty/placeholder data rather than failing.

## Writing a strategy

Subclass `Strategy` and return a `Signal` from `on_bar()`; read history from
`self.bars` / `self.closes`:

```python
from forexbot.core.strategy import Strategy
from forexbot.core.models import Signal, SignalType
from forexbot.indicators import sma

class MyStrategy(Strategy):
    def on_bar(self):
        closes = self.closes
        if len(closes) < 50:
            return Signal.none()
        if sma(closes, 20)[-1] > sma(closes, 50)[-1]:
            price = closes[-1]
            return Signal(SignalType.ENTER_LONG,
                          stop_loss=price * 0.997,
                          take_profit=price * 1.006)
        return Signal.none()
```

Register it in `forexbot/strategies/__init__.py` to use it from config/CLI.

## Disclaimer

For research and education. Trading leveraged FX carries substantial risk of
loss. Test thoroughly on demo accounts before risking real capital. No warranty.
