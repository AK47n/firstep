@echo off
rem Probe-only ASCII trace copy of start-app.bat (same flow, no Chinese comments, extra trace lines).
rem Used by run-E2-timeout-v6.ps1 to record WHICH branch the real launcher would take.
set "TRACE=%TEMP%\e2v6-trace.txt"
echo [%TIME%] START cwd=%CD% > "%TRACE%"
chcp 936 >nul
cd /d "%~dp0..\.."
set PYTHONPATH=src
set FIRSTEP_LAUNCHER=1
set UPD_DIR=%USERPROFILE%\.contest_generator\updates
if exist "%UPD_DIR%\updating.lock" goto :upd_lock
if exist "%UPD_DIR%\pending-update.json" goto :upd_pending
goto :cont
:upd_lock
echo [%TIME%] branch updating >> "%TRACE%"
exit /b 1
:upd_pending
echo [%TIME%] branch update_left >> "%TRACE%"
exit /b 1
:cont
set PYEXE=python
if exist ".venv\Scripts\python.exe" set PYEXE=.venv\Scripts\python.exe
echo [%TIME%] PYEXE=%PYEXE% >> "%TRACE%"
%PYEXE% -c "import sys" >nul 2>&1
echo [%TIME%] selfcheck import rc=%errorlevel% >> "%TRACE%"
if errorlevel 1 goto :no_python
%PYEXE% -c "import sys;sys.exit(0 if sys.version_info>=(3,13) else 1)" >nul 2>&1
echo [%TIME%] selfcheck version rc=%errorlevel% >> "%TRACE%"
if errorlevel 1 goto :old_python
%PYEXE% -c "import fastapi,uvicorn,pypdf,PIL,fitz" >nul 2>&1
echo [%TIME%] selfcheck deps rc=%errorlevel% >> "%TRACE%"
if errorlevel 1 goto :no_deps
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
echo [%TIME%] netstat rc=%errorlevel% >> "%TRACE%"
if errorlevel 1 goto :start_service
%PYEXE% -c "import urllib.request,json;json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3))" >nul 2>&1
echo [%TIME%] health-identity rc=%errorlevel% >> "%TRACE%"
if errorlevel 1 goto :port_busy
goto :open
:start_service
echo [%TIME%] branch start_service >> "%TRACE%"
start "" /b %PYEXE% -m contest_generator.webapp >> "%USERPROFILE%\.contest_generator\webapp.log" 2>&1
echo [%TIME%] service launched >> "%TRACE%"
set /a tries=0
:wait
timeout /t 1 /nobreak >nul
set /a tries+=1
%PYEXE% -c "import urllib.request,json;json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1))" >nul 2>&1
echo [%TIME%] poll tries=%tries% rc=%errorlevel% >> "%TRACE%"
if not errorlevel 1 goto :open
if %tries% geq 20 goto :timeout
goto :wait
:port_busy
echo [%TIME%] branch port_busy >> "%TRACE%"
exit /b 1
:timeout
echo [%TIME%] branch timeout >> "%TRACE%"
exit /b 1
:open
echo [%TIME%] branch open >> "%TRACE%"
exit /b 0
:no_python
echo [%TIME%] branch no_python >> "%TRACE%"
exit /b 1
:old_python
echo [%TIME%] branch old_python >> "%TRACE%"
exit /b 1
:no_deps
echo [%TIME%] branch no_deps >> "%TRACE%"
exit /b 1
