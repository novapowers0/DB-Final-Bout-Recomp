@echo off
setlocal

rem ============================================================================
rem  DBFinalBout - Arranque NATIVO (sin capturador, sin cliente de diagnostico)
rem ----------------------------------------------------------------------------
rem  Este lanzador reproduce la ejecucion limpia que funcionaba: abre el juego
rem  directamente y NO abre ninguna conexion TCP al puerto 4370.
rem
rem  H1 (que el capturador causara el crash) ya fue refutada: este lanzador
rem  tambien reprodujo el fallo sin cliente TCP. Usalo ahora para validar el fix
rem  RI actualizado, con fail-fast activo.
rem
rem  Prueba pendiente: Little Goku contra Piccolo. Comprueba si la transicion
rem  continua y si aparece un psx_crash.txt nuevo o se cuelga el juego.
rem
rem  Uso: doble clic. No requiere Python ni PowerShell.
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

echo Iniciando Dragon Ball GT - Final Bout (modo nativo, sin diagnostico)...
echo.
echo  - No se conecta al servidor de diagnostico.
echo  - Juega hasta entrar en combate.
echo  - Si vuelve a aparecer un crash, revisa:
echo      %BUILD%\psx_crash.txt
echo.

start "Dragon Ball GT - Final Bout" /D "%BUILD%" "%GAME%"

echo Juego lanzado. Cierra esta ventana cuando quieras.
exit /b 0
