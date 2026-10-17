@echo off
setlocal

rem ============================================================================
rem  DBFinalBout - Observacion LIGERA (diagnostico de bajo impacto)
rem ----------------------------------------------------------------------------
rem  Objetivo: registrar una sesion larga (menus + combate) SIN perturbar el
rem  timing del emulador como hacia el capturador anterior.
rem
rem  Diferencias frente a INICIAR_FINAL_BOUT_CON_CAPTURA.bat:
rem    - PSX_FAIL_FAST_UNKNOWN_DISPATCH=0 : un dispatch no resuelto se REGISTRA
rem      en el ring del runtime, no aborta el proceso.
rem    - El capturador corre en modo --light: solo consulta contadores baratos
rem      (ping, fn_stats, dirty_ram_stats, wtrace_stats). NO pide gpu_state,
rem      overlay ni history, que serializan payloads grandes en el hilo de
rem      diagnostico y pueden alterar el timing del guest.
rem    - No vuelca los rings de 100.000 entradas (wtrace/mmio/fntrace).
rem    - Intervalo de 10 s (menos peticiones).
rem
rem  Para el analisis profundo posterior, cuando el juego YA este en combate y
rem  estable, se puede volcar el ring de fallos con el comando TCP
rem  `unknown_dispatch_log` (no incluido aqui a proposito).
rem
rem  Uso: doble clic. Juega hasta entrar en combate y deja correr la sesion.
rem ============================================================================

set "PROJECT=%~dp0"
set "BUILD=%PROJECT%build-release"
set "GAME=%BUILD%\DBFinalBout_Recompiled.exe"
set "CAPTURE=C:\Users\javie\Desktop\PROYECTOS IA\DB Final Bout\tools\psxrecomp\tools\capture_final_bout_session.py"
set "OUT=%BUILD%\captures"
set "CAPTURE_OUT=%OUT%\final_bout_ligero_%RANDOM%.json"

if not exist "%GAME%" (
    echo ERROR: No se encuentra:
    echo "%GAME%"
    pause
    exit /b 2
)
if not exist "%CAPTURE%" (
    echo ERROR: No se encuentra la herramienta de captura:
    echo "%CAPTURE%"
    pause
    exit /b 3
)

set "PYTHON="
where py.exe >nul 2>&1
if not errorlevel 1 set "PYTHON=py.exe"
if not defined PYTHON (
    where python.exe >nul 2>&1
    if not errorlevel 1 set "PYTHON=python.exe"
)
if not defined PYTHON (
    echo ERROR: No se encuentra Python.
    pause
    exit /b 4
)

if not exist "%OUT%" mkdir "%OUT%"

set "PSX_FAIL_FAST_UNKNOWN_DISPATCH=0"

echo Iniciando DBFinalBout_Recompiled.exe (observacion ligera)...
echo.
echo  PSX_FAIL_FAST_UNKNOWN_DISPATCH=0
echo  Captura --light, intervalo 10 s, sin volcado de rings.
echo.
start "Dragon Ball GT - Final Bout" /D "%BUILD%" "%GAME%"

echo Esperando 10 s a que arranque el servidor de diagnostico (puerto 4370)...
timeout /t 10 /nobreak >nul

echo Juega hasta el combate. La observacion durara 30 minutos.
%PYTHON% "%CAPTURE%" --host 127.0.0.1 --port 4370 ^
    --label observacion_ligera --light --manual --seconds 1800 --interval 10 ^
    --output "%CAPTURE_OUT%"

echo.
echo OBSERVACION TERMINADA.
echo Archivo: "%CAPTURE_OUT%"
echo Revisa tambien: %BUILD%\psx_crash.txt y %BUILD%\psx_last_run_report.json
echo.
pause
exit /b 0
