@echo off
REM ============================================================
REM  forexbot - Backtest sobre datos historicos (CSV)
REM  Uso:  backtest.bat [estrategia] [ruta_csv]
REM  Por defecto: estrategia macd_trend sobre data\EURUSD_M15.csv
REM  Genera ademas un grafico de la curva de capital (equity.svg).
REM ============================================================
chcp 65001 >nul
setlocal

cd /d "%~dp0..\.."
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

set "STRAT=%~1"
if "%STRAT%"=="" set "STRAT=macd_trend"

set "DATA=%~2"
if "%DATA%"=="" set "DATA=data\EURUSD_M15.csv"

if not exist "%DATA%" (
    echo [ERROR] No se encontro el archivo de datos: %DATA%
    goto :fin
)

echo.
echo === Backtest: %STRAT% sobre %DATA% ===
%PY% -m forexbot backtest --data "%DATA%" --strategy %STRAT% --plot equity.svg

echo.
echo Grafico guardado en equity.svg (abrelo con tu navegador).

:fin
echo.
pause
endlocal
