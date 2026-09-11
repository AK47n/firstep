@echo off
rem E2 timeout-state degradation shim (probe-only; no product file is touched).
rem
rem Why: start-app.bat resolves "python" via PATH, and the service process it
rem spawns inherits cmd's environment. Prepending this directory to PATH lets us
rem delay ONLY the service-start command, without editing any product file.
rem
rem Gate: inject the delay only when the command line contains
rem contest_generator.webapp (the service start). The launcher's four fast
rem self-checks (import sys / version / deps / health probe) must stay fast,
rem otherwise the probe corrupts the launcher's own timing.
rem
rem Delay 30s > the 20x1s polling window in start-app.bat -> :timeout branch.
rem NOTE: this file is deliberately ASCII-only. cmd.exe parses .cmd bodies under
rem the console codepage (chcp 936 here), and UTF-8 Chinese comments in a
rem non-BOM .cmd get mangled into "not recognized as an internal command" noise
rem (observed in the v4 first run) -- the same class of hazard the repo's
rem PowerShell-BOM rule exists for.
set "PYEXE_REAL=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYEXE_REAL%" set "PYEXE_REAL=C:\Users\luoji\AppData\Local\Python\pythoncore-3.14-64\python.exe"

echo %* | findstr /C:"contest_generator.webapp" >nul 2>&1
if not errorlevel 1 (
  if defined FIRSTEP_SLOW_SERVICE_DELAY (
    echo [python-shim] delaying service start by %FIRSTEP_SLOW_SERVICE_DELAY%s
    "%SystemRoot%\System32\timeout.exe" /t %FIRSTEP_SLOW_SERVICE_DELAY% /nobreak >nul 2>&1
  )
)
"%PYEXE_REAL%" %*
rem bare "exit /b": forward the real interpreter's exit code verbatim
rem (%errorlevel% would expand too early here)
exit /b
