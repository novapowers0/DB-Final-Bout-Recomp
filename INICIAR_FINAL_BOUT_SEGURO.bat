@echo off
setlocal

rem ============================================================================
rem  DBFinalBout - Arranque SEGURO (no aborta ante un dispatch desconocido)
rem ----------------------------------------------------------------------------
rem  Igual que INICIAR_FINAL_BOUT_NATIVO.bat, pero define
rem  PSX_FAIL_FAST_UNKNOWN_DISPATCH=0 ANTES de lanzar el juego.
rem
rem  Que hace ese interruptor (runtime/src/traps.c):
rem    - Con el valor por defecto (1), el primer dispatch no resuelto aborta el
rem      proceso con "FAIL-FAST unknown dispatch" y escribe psx_crash.txt.
rem    - Con 0, el runtime REGISTRA el fallo en su ring interno (consultable por
rem      TCP con el comando unknown_dispatch_log) y CONTINUA sin ejecutar esa
rem      funcion. Es el modo diagnostico previsto por el propio framework para
rem      sobrevivir a los fallos y enumerarlos.
rem
rem  No es una correccion del bug: es la via documentada para sesiones largas en
rem  las que no queremos perder la partida por un unico dispatch no resuelto.
rem  El fallo sigue quedando registrado para analizarlo despues.
rem
rem  Uso: doble clic.
rem ============================================================================

set "PROJECT=%~dp0"
set "BUILD=%PROJECT%build-release"
set "GAME=%BUILD%\DBFinalBout_Recompiled.exe"

if not exist "%GAME%" (
    echo ERROR: No se encuentra:
    echo "%GAME%"
    pause
    exit /b 2
)

set "PSX_FAIL_FAST_UNKNOWN_DISPATCH=0"

echo Iniciando Dragon Ball GT - Final Bout (modo seguro)...
echo.
echo  PSX_FAIL_FAST_UNKNOWN_DISPATCH=0
echo  Los dispatch desconocidos se registran pero no abortan el proceso.
echo.

start "Dragon Ball GT - Final Bout" /D "%BUILD%" "%GAME%"

echo Juego lanzado. Cierra esta ventana cuando quieras.
exit /b 0
