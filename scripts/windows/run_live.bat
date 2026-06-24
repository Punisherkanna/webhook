@echo off
REM ============================================================
REM  forexbot - Modo EN VIVO (envia ordenes REALES)
REM  Usa la cuenta configurada en config.yaml. Pide confirmacion.
REM ============================================================
chcp 65001 >nul
setlocal

cd /d "%~dp0..\.."
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

if not exist "config.yaml" (
    echo.
    echo [ERROR] No existe config.yaml.
    echo         Copia config.example.yaml a config.yaml y editalo primero.
    goto :fin
)

echo.
echo ************************************************************
echo  ATENCION: Esto enviara ORDENES REALES a la cuenta de MT5
echo  configurada en config.yaml. Usa una cuenta DEMO si tienes
echo  cualquier duda.
echo ************************************************************
echo.
set "OK="
set /p "OK=Escribe SI (en mayusculas) para continuar: "
if not "%OK%"=="SI" (
    echo Cancelado. No se ha enviado ninguna orden.
    goto :fin
)

echo.
echo === forexbot: EN VIVO === Asegurate de que MT5 esta ABIERTO con AutoTrading.
echo Pulsa Ctrl+C para detener.
echo.
%PY% -m forexbot live --config config.yaml --live

:fin
echo.
pause
endlocal
