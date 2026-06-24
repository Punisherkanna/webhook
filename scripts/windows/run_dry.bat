@echo off
REM ============================================================
REM  forexbot - Modo PRUEBA EN SECO (dry-run)
REM  Conecta a MT5 y muestra las ordenes que HARIA, sin enviarlas.
REM ============================================================
chcp 65001 >nul
setlocal

cd /d "%~dp0..\.."
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

if not exist "config.yaml" (
    echo.
    echo [ERROR] No existe config.yaml.
    echo         Copia config.example.yaml a config.yaml y editalo con los
    echo         datos de tu cuenta MT5 ^(login, password, server^).
    goto :fin
)

echo.
echo === forexbot: PRUEBA EN SECO (no se envian ordenes reales) ===
echo Asegurate de que el terminal MT5 esta ABIERTO y con AutoTrading activado.
echo Pulsa Ctrl+C para detener.
echo.
%PY% -m forexbot live --config config.yaml

:fin
echo.
pause
endlocal
