@echo off
setlocal EnableExtensions EnableDelayedExpansion
title DBFinalBout - Session Recording
chcp 65001 >NUL

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "EXE=%ROOT%\build-release\DBFinalBout_Recompiled.exe"
set "GAME=%ROOT%\game.toml"
set "OUT=%ROOT%\build-release"

echo ============================================================
echo  DBFinalBout - session recording
echo ============================================================
echo.
echo  Recorded automatically while you play:
echo    - overlay_captures.json          (overlays loaded into RAM)
echo    - overlay_captures.addendum.jsonl (session history)
echo    - psx_freeze_dump_*.json          (crash signatures)
echo.
echo  WHAT TO DO:
echo    1. The game launcher window will open.
echo    2. Press PLAY in the launcher to enter the game.
echo    3. Go through menus, then play at least ONE fight.
echo    4. Close the game window when done.
echo.
echo  IMPORTANT: leave WIDESCREEN OFF (default) for this capture
echo  session - we want a clean baseline. We test widescreen after
echo  the overlays are recompiled.
echo.

if not exist "%EXE%" (
  echo  ERROR: %EXE% not found. Build the game first.
  pause
  exit /b 1
)

if not exist "%OUT%" mkdir "%OUT%"

echo  Launching the game now...
echo  ^>^>^> Press PLAY in the launcher and play. Close when done. ^<^<^<
echo.

rem Launch in FOREGROUND: this cmd waits until the game exits.
"%EXE%" --game "%GAME%" --debug-port 4370

echo.
echo  ============================================================
echo  Game closed. Session artifacts:
echo  ============================================================
if exist "%OUT%\overlay_captures.json" (
  echo   [OK] overlay_captures.json
) else (
  echo   [--] overlay_captures.json NOT created yet
  echo        (appears after the game loads its first overlay - enter a fight)
)
if exist "%OUT%\overlay_captures.addendum.jsonl" (
  echo   [OK] session history
)
for %%f in ("%OUT%\psx_freeze_dump_*.json") do (
  if exist "%%f" (
    echo   [!!] freeze dumps present - crash signatures recorded
    goto :dumpsdone
  )
)
:dumpsdone

echo.
echo  Next:  python tools\analyze_session.py
echo.
pause
