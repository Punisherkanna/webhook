# Scripts para Windows

Lanzadores `.bat` para usar forexbot con doble clic, sin escribir comandos.
Pensados para usar el bot con MetaTrader 5 en Windows.

| Script          | Qué hace                                                                 |
|-----------------|--------------------------------------------------------------------------|
| `install.bat`   | Instala Python deps + el conector `MetaTrader5`.                         |
| `run_dry.bat`   | Prueba en seco: muestra las órdenes que haría, **sin enviarlas**.       |
| `run_live.bat`  | Modo en vivo: **envía órdenes reales** (pide confirmación escribiendo `SI`). |
| `backtest.bat`  | Backtest sobre CSV + genera `equity.svg`. Uso: `backtest.bat [estrategia] [csv]`. |

## Cómo usarlos

1. Ejecuta **`install.bat`** una vez (doble clic).
2. Copia `config.example.yaml` a `config.yaml` (en la raíz del repo) y rellena
   tu `login`, `password` y `server` de MT5.
3. Abre el terminal **MetaTrader 5** e inicia sesión, con **AutoTrading** activado.
4. Ejecuta **`run_dry.bat`** para comprobar que conecta y decide bien.
5. Cuando estés conforme, ejecuta **`run_live.bat`** (envía órdenes reales).

> Empieza siempre con una cuenta **demo**. El conector `MetaTrader5` solo
> funciona en Windows con el terminal de escritorio abierto.

Estos scripts detectan Python automáticamente (`py` o `python`) y se sitúan en
la raíz del repo, así que puedes ejecutarlos desde donde sea.
