@echo off
setlocal EnableExtensions

rem Prueba A/B: ejecuta la misma build usando OpenGL en vez de Vulkan.
rem Restaura settings.toml al cerrar la captura.

set "PROJECT=%~dp0"
set "BUILD=%PROJECT%build-release"
set "GAME=%BUILD%\DBFinalBout_Recompiled.exe"
set "SETTINGS=%BUILD%\settings.toml"
set "BACKUP=%BUILD%\settings.toml.before_opengl_test"
set "CAPTURE=C:\Users\javie\Desktop\PROYECTOS IA\DB Final Bout\tools\psxrecomp\tools\capture_final_bout_session.py"
set "OUT=%BUILD%\captures"
set "CAPTURE_OUT=%OUT%\final_bout_opengl_%RANDOM%.json"

if not exist "%GAME%" (
    echo ERROR: No se encuentra "%GAME%"
    pause
    exit /b 2
)
if not exist "%SETTINGS%" (
    echo ERROR: No se encuentra "%SETTINGS%"
    pause
    exit /b 3
)
if not exist "%CAPTURE%" (
    echo ERROR: No se encuentra "%CAPTURE%"
    pause
    exit /b 4
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
    exit /b 5
)

copy /y "%SETTINGS%" "%BACKUP%" >nul
set "SETTINGS=%SETTINGS%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = [IO.File]::ReadAllText('%SETTINGS%'); $p = [regex]::Replace($p, '(?m)^renderer\s*=\s*\"[^\"]*\"', 'renderer          = \"opengl\"'); [IO.File]::WriteAllText('%SETTINGS%', $p)"

if errorlevel 1 (
    echo ERROR: No se pudo preparar OpenGL.
    copy /y "%BACKUP%" "%SETTINGS%" >nul
    del /q "%BACKUP%" >nul 2>&1
    pause
    exit /b 6
)

if not exist "%OUT%" mkdir "%OUT%"
echo Iniciando Final Bout con OpenGL...
start "Dragon Ball GT - Final Bout OpenGL" /D "%BUILD%" "%GAME%"
timeout /t 8 /nobreak >nul

echo La captura estara activa durante 15 minutos.
echo Juega hasta llegar al combate y comprueba si vuelve a fallar.
echo.
%PYTHON% "%CAPTURE%" --host 127.0.0.1 --port 4370 ^
    --label opengl_test --manual --seconds 900 --interval 5 ^
    --output "%CAPTURE_OUT%"

copy /y "%BACKUP%" "%SETTINGS%" >nul
del /q "%BACKUP%" >nul 2>&1
echo.
echo OpenGL terminado. El renderer anterior ha sido restaurado.
echo Captura: "%CAPTURE_OUT%"
pause
exit /b 0
