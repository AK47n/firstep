@echo off
rem firstep 启动器（由 start-app.vbs 隐藏运行，无黑窗口）：
rem 全流程中文反馈——找不到 Python / 版本过低 / 依赖缺失 / 端口被占 /
rem 启动超时都弹窗说明，不再静默失败只退 exit code。
rem 服务完全后台（无窗口，日志落 %USERPROFILE%\.contest_generator\webapp.log），
rem 浏览器直接打开；关掉浏览器最后一个标签页 = 停止服务（应用内标签会话机制）。
rem 重复双击：本应用已在运行则只再开一个浏览器标签。
rem 弹窗实现：powershell 的 WScript.Shell.Popup（任何 Win10/11 自带 powershell.exe；
rem 消息内不用英文单引号/双引号，避免引号转义问题）。
chcp 936 >nul
cd /d "%~dp0"
set PYTHONPATH=src
set FIRSTEP_LAUNCHER=1
rem ---------- 0. 更新中/待更新标记检测（工单 auto-update/06）----------
set UPD_DIR=%USERPROFILE%\.contest_generator\updates
if exist "%UPD_DIR%\updating.lock" goto :updating
if exist "%UPD_DIR%\pending-update.json" goto :update_left

:updating
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('firstep 正在更新中，请稍候片刻再启动（更新完成后会自动打开浏览器）',0,'firstep 更新中',64)"
exit /b 1

:update_left
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('检测到上次更新未完成。请重新打开工具后到设置页点「检查更新」重试；若持续失败请查看日志：%USERPROFILE%\.contest_generator\updates\updater.log',0,'firstep 更新未完成',16)"
exit /b 1


rem ---------- 1. 定位 Python：.venv 优先，缺失回退系统 python ----------
set PYEXE=python
if exist ".venv\Scripts\python.exe" set PYEXE=.venv\Scripts\python.exe

%PYEXE% -c "import sys" >nul 2>&1
if errorlevel 1 goto :no_python

%PYEXE% -c "import sys;sys.exit(0 if sys.version_info>=(3,13) else 1)" >nul 2>&1
if errorlevel 1 goto :old_python

%PYEXE% -c "import fastapi,uvicorn,pypdf,PIL,fitz" >nul 2>&1
if errorlevel 1 goto :no_deps

rem ---------- 2. 端口探测：无服务 / 本应用已在跑 / 其他程序占着 ----------
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 goto :start_service

rem 有东西在听 8000：用 /api/health 判定是不是本应用
%PYEXE% -c "import urllib.request,json;json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3))" >nul 2>&1
if errorlevel 1 goto :port_busy
goto :open

:start_service
rem 后台启动服务，日志追加到用户配置目录
start "" /b %PYEXE% -m contest_generator.webapp >> "%USERPROFILE%\.contest_generator\webapp.log" 2>&1

rem ---------- 3. 轮询 /api/health 最多 20 秒 ----------
set /a tries=0
:wait
timeout /t 1 /nobreak >nul
set /a tries+=1
%PYEXE% -c "import urllib.request,json;json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1))" >nul 2>&1
if not errorlevel 1 goto :open
if %tries% geq 20 goto :timeout
goto :wait

:no_python
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('没有找到 Python。请先安装 Python 3.13 或更新版本（https://www.python.org/downloads/），装完运行 install.bat 再启动',0,'firstep 启动失败',16)"
exit /b 1

:old_python
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('找到的 Python 版本太旧，需要 3.13 或更新版本。请到 https://www.python.org/downloads/ 下载新版安装后重试',0,'firstep 启动失败',16)"
exit /b 1

:no_deps
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('依赖没有装好。请先双击运行 install.bat（会创建虚拟环境并安装依赖），装完再启动',0,'firstep 启动失败',16)"
exit /b 1

:port_busy
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('端口 8000 已被其他程序占用，本工具不会自动换端口。请先关闭占用该端口的程序，再重新双击 start-app.vbs',0,'firstep 启动失败',16)"
exit /b 1

:timeout
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('启动超时（20 秒），服务未能就绪。请运行 install.bat 检查依赖，并查看日志：%USERPROFILE%\.contest_generator\webapp.log',0,'firstep 启动失败',16)"
exit /b 1

:open
start "" "http://127.0.0.1:8000"
exit /b 0
