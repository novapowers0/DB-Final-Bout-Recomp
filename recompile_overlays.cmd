@echo off
setlocal EnableExtensions EnableDelayedExpansion
title DBFinalBout - Recompile overlays
chcp 65001 >NUL

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "CAPTURES=%ROOT%\build-release\overlay_captures.json"
set "GCC=C:\msys64\mingw64\bin\gcc.exe"

rem MinGW on PATH: without it the ninja recompiler build (and the gcc shard
rem compile below) fail silently. Prepend only if present.
if exist "C:\msys64\mingw64\bin" set "PATH=C:\msys64\mingw64\bin;%PATH%"

echo ============================================================
echo  DBFinalBout - recompile captured overlays (native)
echo ============================================================
echo.
echo  Requires: play_session.cmd already run (overlay_captures.json exists)
echo.

if not exist "%CAPTURES%" (
  echo  ERROR: %CAPTURES% not found.
  echo  Run play_session.cmd first and play through menus + one fight.
  pause
  exit /b 1
)

if not exist "%GCC%" (
  echo  ERROR: %GCC% not found.
  echo  The native overlay pipeline is fail-closed to avoid an incompatible cache.
  pause
  exit /b 1
)

if not exist "%ROOT%\build-recompiler\psxrecomp-game.exe" (
  echo  ERROR: current Clang recompiler not found:
  echo    %ROOT%\build-recompiler\psxrecomp-game.exe
  echo  Rebuild it before compiling overlays.
  pause
  exit /b 1
)

echo  Recompiling overlays into build-release\cache ...
echo.

python "%ROOT%\psxrecomp\tools\compile_overlays.py" ^
  --captures        "%CAPTURES%" ^
  --game-toml       "%ROOT%\game.toml" ^
  --recompiler      "%ROOT%\build-recompiler\psxrecomp-game.exe" ^
  --runtime-include "%ROOT%\psxrecomp\runtime\include" ^
  --project-root    "%ROOT%\psxrecomp" ^
  --out-dir         "%ROOT%\build-release\cache" ^
  --gcc             "%GCC%"

if errorlevel 1 (
  echo.
  echo  Overlay compile had errors. See output above.
  echo  If it says the recompiler is stale, rebuild it:
  echo    cmake --build build-recompiler --target psxrecomp-game
  pause
  exit /b 1
)

echo.
echo  DONE. Overlays are now native (DLL cache in build-release\cache).
echo  The runtime picks them up on next launch automatically.
echo  Run the offline consistency check:
echo    python tools\verify_offline.py
echo  Re-run play_session.cmd to verify stability + widescreen.
echo.
pause
