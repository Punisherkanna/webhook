@echo off
REM ============================================================
REM  forexbot - Instalacion de dependencias (Windows)
REM  Doble clic para instalar todo lo necesario para usar MT5.
REM ============================================================
chcp 65001 >nul
setlocal

REM Ir a la raiz del repo (este script esta en scripts\windows\)
cd /d "%~dp0..\.."

REM Detectar el lanzador de Python (py preferido, si no python)
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

echo.
echo === Comprobando Python ===
%PY% --version
if errorlevel 1 (
    echo.
    echo [ERROR] No se encontro Python. Instalalo desde https://python.org
    echo         y marca "Add Python to PATH" durante la instalacion.
    goto :fin
)

echo.
echo === Instalando dependencias del bot ===
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo === Instalando el conector de MetaTrader 5 ===
%PY% -m pip install MetaTrader5
if errorlevel 1 (
    echo.
    echo [AVISO] No se pudo instalar MetaTrader5. Recuerda que SOLO funciona
    echo         en Windows. El backtester funciona igual sin este paquete.
)

echo.
echo === Instalacion completada ===
echo Siguiente paso: copia config.example.yaml a config.yaml y editalo,
echo luego ejecuta run_dry.bat para una prueba en seco.
goto :fin

:error
echo.
echo [ERROR] Fallo la instalacion de dependencias. Revisa los mensajes de arriba.

:fin
echo.
pause
endlocal
