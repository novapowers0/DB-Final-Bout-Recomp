@echo off
setlocal

rem Launcher de prueba: inicia la build release y captura la sesion manual.
rem No modifica la configuracion del juego ni envia botones.

set "PROJECT=%~dp0"
set "BUILD=%PROJECT%build-release"
set "GAME=%BUILD%\DBFinalBout_Recompiled.exe"
set "CAPTURE=C:\Users\javie\Desktop\PROYECTOS IA\DB Final Bout\tools\psxrecomp\tools\capture_final_bout_session.py"
set "OUT=%BUILD%\captures"
set "CAPTURE_OUT=%OUT%\final_bout_manual_play_%RANDOM%.json"

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
    echo Instala Python 3 o anade py.exe/python.exe al PATH.
    pause
    exit /b 4
)

if not exist "%OUT%" mkdir "%OUT%"

echo Iniciando DBFinalBout_Recompiled.exe...
start "Dragon Ball GT - Final Bout" /D "%BUILD%" "%GAME%"

echo Esperando al servidor de diagnostico en el puerto 4370...
timeout /t 8 /nobreak >nul

echo.
echo La captura estara activa durante 15 minutos.
echo Juega normalmente por menus y combates.
echo No cierres esta ventana hasta que aparezca CAPTURA TERMINADA.
echo.

%PYTHON% "%CAPTURE%" --host 127.0.0.1 --port 4370 ^
    --label manual_play --manual --seconds 900 --interval 5 ^
    --output "%CAPTURE_OUT%"

if errorlevel 1 (
    echo.
    echo La captura termino con un error. El JSON puede contener fatal_error.
    pause
    exit /b 5
)

echo.
echo CAPTURA TERMINADA.
echo Archivo generado:
echo "%CAPTURE_OUT%"
echo.
pause
exit /b 0
