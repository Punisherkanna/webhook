# forexbot

Un **robot de trading de Forex en Python** independiente del bróker, con un
**backtester** basado en eventos y ejecución en vivo sobre **MetaTrader 5** y
**NinjaTrader 8**.

La misma estrategia se ejecuta sin cambios en el backtest, en un bróker de papel
(simulado), en MT5 y en NinjaTrader — las estrategias y el motor solo hablan con
una interfaz `Broker`, así que cambiar de plataforma es un cambio de una línea en
la configuración.

> **Las estrategias son modelos de tendencia/momentum de una sola posición.** No
> hay lógica de grid, cobertura (hedging), HFT ni martingala en ningún punto del
> proyecto — cada entrada abre una posición con un stop de protección fijo basado
> en ATR.

> 🇬🇧 English documentation: see [README.md](README.md).

## Lo más destacado

- **Cero dependencias pesadas en el núcleo.** El motor, el backtester, los
  indicadores y las estrategias usan solo la biblioteca estándar de Python +
  PyYAML. Sin numpy/pandas.
- **Backtester** con modelado de spread + comisión, stops/objetivos basados en
  ATR y un informe completo de estadísticas (tasa de acierto, factor de
  beneficio, drawdown máximo, curva de capital).
- **Dimensionamiento de posición centrado en el riesgo** — cada operación se
  dimensiona para arriesgar una fracción fija del capital según la distancia de
  su stop, ajustada al lote del bróker.
- **Brókers conectables**: `paper` (en memoria), `mt5` (paquete oficial
  MetaTrader5), `ninjatrader` (puente ATI basado en archivos).
- **Con pruebas**: 49 pruebas unitarias que cubren indicadores, riesgo, llenado
  del backtest, estrategias, el motor en vivo y el puente de NinjaTrader.

## Estrategias

Todas son modelos de tendencia/momentum de una sola posición con stops de
protección basados en ATR — sin grid, cobertura, HFT ni martingala.

| Nombre               | Tipo            | Idea                                                            |
|----------------------|-----------------|----------------------------------------------------------------|
| `ma_crossover`       | Tendencia       | La SMA rápida cruza la SMA lenta.                              |
| `rsi_reversion`      | Reversión       | El RSI sale de sobreventa/sobrecompra.                        |
| `donchian_breakout`  | Ruptura         | El precio rompe el máximo/mínimo de las N velas previas.      |
| `macd_trend`         | Tendencia       | Cruce MACD/señal, filtrado por la dirección de una EMA lenta. |
| `bollinger_breakout` | Ruptura         | El cierre supera una banda de Bollinger.                      |

## Estructura del proyecto

```
forexbot/
  core/        modelos, interfaces Broker y Strategy, gestor de riesgo, motor en vivo
  indicators/  SMA, EMA, RSI, ATR, MACD, Bollinger, Donchian (Python puro)
  strategies/  ma_crossover, rsi_reversion, donchian_breakout, macd_trend,
               bollinger_breakout (+ registro)
  backtest/    motor basado en eventos + cargador de datos CSV
  brokers/     paper, mt5_broker, ninjatrader_broker
  config.py    YAML -> configuración tipada
  cli.py       `python -m forexbot ...`
examples/      generador de datos sintéticos
tests/         conjunto de pruebas pytest
data/          CSV de muestra EURUSD M15
```

## Inicio rápido

```bash
pip install -r requirements.txt          # solo PyYAML para el núcleo
pip install pytest                        # para las pruebas

# Generar datos de muestra nuevos (opcional; ya hay una muestra incluida)
python examples/generate_sample_data.py --rows 2000 --out data/EURUSD_M15.csv

# Backtest
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy ma_crossover
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy donchian_breakout
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy macd_trend
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy bollinger_breakout

# Ejecutar pruebas
python -m pytest -q
```

Ejemplo de salida del backtest:

```
=== Backtest: ma_crossover on EURUSD (2000 bars) ===
Symbol:          EURUSD
Trades:          19
Win rate:        63.2%
Net profit:      884.43 (+8.84%)
Profit factor:   2.07
Max drawdown:    2.58%
```

> El conjunto de datos incluido es **sintético** — los resultados demuestran el
> motor, no un sistema rentable. Valida siempre las estrategias con datos
> históricos reales.

### Gráfico de la curva de capital

Añade `--plot RUTA` para guardar un gráfico de la curva de capital (azul), la
marca de máximo histórico (verde discontinuo) y el drawdown (sombreado rojo):

```bash
# .svg usa un renderizador interno sin dependencias (no requiere paquetes extra)
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy macd_trend \
    --plot equity.svg

# .png requiere matplotlib (pip install matplotlib)
python -m forexbot backtest --data data/EURUSD_M15.csv --strategy macd_trend \
    --plot equity.png
```

El formato se elige según la extensión del archivo. El SVG funciona sin
instalar nada; el PNG solo hace falta si quieres una imagen rasterizada.

## Trading en vivo / papel

```bash
cp config.example.yaml config.yaml       # luego edita bróker, símbolo, estrategia
python -m forexbot live --config config.yaml          # simulación (registra órdenes previstas)
python -m forexbot live --config config.yaml --live   # envía órdenes de verdad
```

El motor actúa **solo sobre velas cerradas** y respeta `max_open_positions`, de
modo que el comportamiento en vivo coincide con el del backtester. `dry_run` (el
valor por defecto) registra cada orden prevista sin enviarla.

### MetaTrader 5

En un equipo Windows con el terminal MT5 en ejecución:

```bash
pip install MetaTrader5
```

```yaml
broker: mt5
broker_options:
  login: 12345678
  password: "tu-contraseña"
  server: "TuBroker-Demo"
```

El adaptador asigna las cadenas de temporalidad a las constantes de MT5, obtiene
las cotizaciones con `copy_rates_from_pos` y envía órdenes de mercado con SL/TP
adjuntos.

### NinjaTrader 8

NinjaTrader no tiene un SDK oficial de Python, por lo que este adaptador usa su
**Interfaz de Trading Automatizado (ATI)** mediante *Order Instruction Files* —
comandos de texto plano depositados en `Documents/NinjaTrader 8/incoming/`.

1. En NinjaTrader: **Tools → Options → Automated trading interface** → activa
   *AT Interface*.
2. Configura el bróker:

```yaml
broker: ninjatrader
broker_options:
  account: "Sim101"
  incoming_dir: "C:/Users/tu/Documents/NinjaTrader 8/incoming"
  data_dir: "C:/Users/tu/Documents/NinjaTrader 8/export"   # para las velas
```

**Límites (por diseño):** la ATI está orientada a órdenes. `place_order` /
`close_position` son robustos. Las velas **no** se transmiten por el puente de
archivos — apunta `data_dir` a una exportación CSV de NinjaScript, o alimenta los
datos de mercado desde MT5/CSV y usa NinjaTrader solo para la ejecución.
`get_positions`/`get_account` leen archivos de estado opcionales
(`positions.csv`, `account.csv`) que un NinjaScript complementario puede
escribir; en su ausencia, devuelven datos vacíos/marcadores en lugar de fallar.

## Escribir una estrategia

Hereda de `Strategy` y devuelve un `Signal` desde `on_bar()`; lee el histórico
desde `self.bars` / `self.closes`:

```python
from forexbot.core.strategy import Strategy
from forexbot.core.models import Signal, SignalType
from forexbot.indicators import sma

class MiEstrategia(Strategy):
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

Regístrala en `forexbot/strategies/__init__.py` para usarla desde la
configuración o la CLI.

## Aviso

Para investigación y educación. Operar Forex apalancado conlleva un riesgo
sustancial de pérdida. Prueba a fondo en cuentas demo antes de arriesgar capital
real. Sin garantías.
