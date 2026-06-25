# forexbot — versión nativa MQL5 (Expert Advisor)

Esta es la versión del bot que **se compila e instala dentro de MetaTrader 5**,
sin Python. Es un Expert Advisor (`forexbot.mq5`) que corre directamente en el
terminal MT5, sobre cualquier símbolo y temporalidad.

Incluye las **mismas 5 estrategias** que la versión Python y la misma filosofía:
una sola posición a la vez, stop y objetivo basados en ATR. **Sin grid, hedging,
HFT ni martingala.**

> ¿Cuál usar? La versión **MQL5** (esta) es la más sencilla: todo ocurre dentro
> de MT5, funciona en cualquier sistema donde corra MT5 y se puede optimizar con
> el *Strategy Tester*. La versión **Python** te sirve si quieres controlar MT5
> desde fuera o reutilizar el backtester en Python.

## Estrategias y parámetros

Seleccionas la estrategia con el parámetro **`InpStrategy`**:

| Valor                      | Estrategia                                         |
|----------------------------|----------------------------------------------------|
| `STRAT_MA_CROSSOVER`       | Cruce de medias (SMA rápida/lenta)                |
| `STRAT_RSI_REVERSION`      | Reversión por RSI (sale de sobreventa/sobrecompra) |
| `STRAT_DONCHIAN_BREAKOUT`  | Ruptura del canal de las N velas previas           |
| `STRAT_MACD_TREND`         | Cruce MACD filtrado por una EMA de tendencia       |
| `STRAT_BOLLINGER_BREAKOUT` | Ruptura de banda de Bollinger                      |

Riesgo y stops (comunes a todas):
- `InpRiskPerTrade` — fracción del *equity* arriesgada por operación (0.01 = 1%).
  El lote se calcula con el *tick value* real del símbolo y la distancia del stop.
- `InpAtrPeriod`, `InpAtrStop`, `InpAtrTarget` — stop = `ATR * InpAtrStop`,
  objetivo = `ATR * InpAtrTarget`.
- `InpMaxPositions` — máximo de posiciones simultáneas de este EA (por defecto 1).
- `InpNewBarOnly` — operar solo al cerrar cada vela (recomendado).

## Cómo compilar e instalar (paso a paso)

1. **Abre la carpeta de datos de MT5**: en MetaTrader 5 → menú
   **Archivo → Abrir carpeta de datos**. Se abrirá el explorador.
2. Entra en la carpeta **`MQL5\Experts`** y copia ahí el archivo
   [`Experts/forexbot.mq5`](Experts/forexbot.mq5) de este repo.
3. **Abre MetaEditor** (en MT5 pulsa **F4**, o el botón "IDE / MetaEditor").
4. En el navegador de MetaEditor, abre `Experts\forexbot.mq5` y pulsa
   **Compilar** (**F7**). Debe terminar con **0 errores**. Se generará
   `forexbot.ex5`.
5. Vuelve a MT5. En el panel **Navegador → Asesores Expertos** verás
   **forexbot** (pulsa actualizar si no aparece).

## Cómo ponerlo a operar

1. Abre el gráfico del símbolo y la temporalidad que quieras (p. ej. EURUSD M15).
2. **Arrastra** `forexbot` desde el Navegador al gráfico.
3. En la pestaña **Comunes**, marca **"Permitir trading algorítmico"**.
4. En la pestaña **Entradas (Inputs)**, elige la estrategia y ajusta el riesgo.
5. Acepta. Asegúrate de que el botón **"Algo Trading"** de la barra superior de
   MT5 esté **activado** (verde). Verás una carita 🙂 arriba a la derecha del
   gráfico cuando el EA esté activo.

## Panel visual en el gráfico

El EA dibuja un panel profesional (tema oscuro con degradado y barra de acento)
directamente sobre el gráfico, que se **refresca cada segundo**. Muestra:

- **Símbolo** y temporalidad en operación.
- **Señal** (bias direccional en vivo): `COMPRA` (verde), `VENTA` (rojo) o `NEUTRAL`.
- **Riesgo %** configurado por operación.
- **Posición** abierta (dirección, lotes y precio de entrada).
- **PnL flotante** de la posición abierta (verde/rojo).
- **Operaciones** cerradas por el EA.
- **P/L total** realizado (verde/rojo).
- **Balance** y **Equity** de la cuenta.

Parámetros del grupo *Panel visual*:

| Parámetro        | Qué hace                                              |
|------------------|-------------------------------------------------------|
| `InpShowPanel`   | Muestra u oculta el panel.                             |
| `InpPanelX/Y`    | Posición en píxeles desde la esquina de anclaje.      |
| `InpPanelCorner` | Esquina del gráfico donde se ancla el panel.          |
| `InpAccent`      | Color de acento (cabecera y barras).                  |

> El fondo es un degradado **dibujado por código**, así que no necesitas copiar
> ninguna imagen: el panel se ve bien nada más compilar. Si quieres una imagen
> propia de fondo, se puede añadir como recurso `OBJ_BITMAP_LABEL` — dímelo y lo
> integro.

## Probar antes con el Strategy Tester (recomendado)

Antes de operar en real, pruébalo con datos históricos:

1. En MT5 abre **Ver → Probador de estrategias** (**Ctrl+R**).
2. Selecciona el Asesor Experto **forexbot**, el símbolo, la temporalidad y el
   rango de fechas.
3. Ejecuta. Puedes usar **Optimización** para barrer parámetros (periodos, ATR…).

> Empieza **siempre** con una cuenta **demo**. Operar Forex apalancado conlleva
> un riesgo sustancial de pérdida. Esto es software educativo, sin garantías.

## Notas técnicas

- Usa solo indicadores nativos de MT5 (`iMA`, `iRSI`, `iATR`, `iMACD`, `iBands`)
  y `iHighest`/`iLowest` para Donchian, más la clase estándar `CTrade`
  (`<Trade/Trade.mqh>`). No requiere librerías externas.
- Las señales se evalúan sobre la **vela cerrada** (shift 1 frente a 2), igual
  que el backtester en Python, para que el comportamiento sea coherente.
- Respeta `SYMBOL_TRADE_STOPS_LEVEL` (distancia mínima de SL/TP del bróker) y los
  límites de volumen del símbolo (`VOLUME_MIN/STEP/MAX`).
- El EA identifica sus propias posiciones por **número mágico** (`InpMagic`), así
  que puede convivir con operaciones manuales u otros EAs.
