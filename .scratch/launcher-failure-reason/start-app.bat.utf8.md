@echo off
rem firstep 启动器（由 start-app.vbs 隐藏运行，无黑窗口）：
rem 全流程中文反馈——找不到 Python / 版本过低 / 依赖缺失 / 端口被占 /
rem 启动超时都弹窗说明，不再静默失败只退 exit code。
rem 服务完全后台（无窗口，日志落 %USERPROFILE%\.contest_generator\webapp.log），
rem 浏览器直接打开；关掉浏览器最后一个标签页 = 停止服务（应用内标签会话机制）。
rem 重复双击：本应用已在运行则只再开一个浏览器标签。
rem 弹窗实现：powershell 的 WScript.Shell.Popup（任何 Win10/11 自带 powershell.exe；
rem 消息内不用英文单引号/双引号，避免引号转义问题）。
rem 留痕（工单 launcher-failure-reason/01）：每条退出路径都调 tools\launcher-log.ps1 往
rem %USERPROFILE%\.contest_generator\launcher.log 追加一行 reason=<分支码> 供机器判读；
rem 行内容纯 ASCII、值内不含空格；新增退出分支必须照着写（tests/test_launcher_log.py 静态守卫钉住）。
rem 退出码口径：成功分支 exit /b 0，失败分支 exit /b 1（区分靠 reason，不靠码值）。
rem 端口可覆盖（默认 8000）：只给验收/测试用，正常双击不设这个变量。
rem 取值校验与 webapp.resolve_port 同口径：只认 1..65535 的纯数字，否则回落到 8000
rem （否则会出现「launcher 轮询某个坏端口、服务却绑 8000」的假超时）。
chcp 936 >nul
cd /d "%~dp0"
set PYTHONPATH=src
set FIRSTEP_LAUNCHER=1
if not defined FIRSTEP_LAUNCHER_PORT set FIRSTEP_LAUNCHER_PORT=8000
echo %FIRSTEP_LAUNCHER_PORT%| findstr /r "^[1-9][0-9]*$" >nul 2>&1
if errorlevel 1 set FIRSTEP_LAUNCHER_PORT=8000
if %FIRSTEP_LAUNCHER_PORT% gtr 65535 set FIRSTEP_LAUNCHER_PORT=8000
rem 留痕脚本的绝对路径（%~dp0 末尾自带反斜杠）
set LAUNCHER_LOG_PS1=%~dp0tools\launcher-log.ps1
rem 旧进程判据脚本的绝对路径（同一个 %~dp0 口径）
set LAUNCHER_STALE_PY=%~dp0tools\launcher-stale.py
rem ---------- 0. 更新中/待更新标记检测（工单 auto-update/06）----------
set UPD_DIR=%USERPROFILE%\.contest_generator\updates
if exist "%UPD_DIR%\updating.lock" goto :updating
if exist "%UPD_DIR%\pending-update.json" goto :update_left

goto :launcher_continue

:updating
rem launcher-log
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_LOG_PS1%" -Reason updating
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('firstep 正在更新中，请稍候片刻再启动（更新完成后会自动打开浏览器）',0,'firstep 更新中',64)"
exit /b 1

:update_left
rem launcher-log
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_LOG_PS1%" -Reason update_left
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('检测到上次更新未完成。请重新打开工具后到设置页点「检查更新」重试；若持续失败请查看日志：%USERPROFILE%\.contest_generator\updates\updater.log',0,'firstep 更新未完成',16)"
exit /b 1


:launcher_continue
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
netstat -ano | findstr ":%FIRSTEP_LAUNCHER_PORT%" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 goto :start_service

rem 有东西在听这个端口：用 /api/health 判定是不是本应用
rem 身份判据 = 响应能解析成 JSON 且 app 字段等于 contest-generator（与 webapp 的
rem /api/health 契约同源）；请求失败 / 不是 JSON / 身份不符，一律算「不是本应用」→ port_busy
rem （这一条是既有行为，本单只把它记进日志，没有改过它的走向）。
%PYEXE% -c "import urllib.request,json;json.load(urllib.request.urlopen('http://127.0.0.1:%FIRSTEP_LAUNCHER_PORT%/api/health',timeout=3))" >nul 2>&1
if errorlevel 1 goto :port_busy
set FIRSTEP_HEALTH_APP=unknown
for /f "usebackq delims=" %%a in (`%PYEXE% -c "import urllib.request,json;d=json.load(urllib.request.urlopen('http://127.0.0.1:%FIRSTEP_LAUNCHER_PORT%/api/health',timeout=3));print(d.get('app',''))" 2^>nul`) do set FIRSTEP_HEALTH_APP=%%a
if /i not "%FIRSTEP_HEALTH_APP%"=="contest-generator" goto :port_busy
rem 身份是本应用：再比一次版本。更新换的是盘上的文件，跑着的进程不会跟着变——
rem 旧进程还占着端口时，光看身份会把它当成「已在运行」（真机演练实测：盘上 1.2.1、服务仍 1.1.1）。
rem 版本比较不在这里手写（批处理只会比字符串与整数），问 tools\launcher-stale.py：
rem 它打印 stale / fresh / unknown 三选一，不是 stale（空、unknown、其它）一律走原来的复用路径。
set FIRSTEP_STALE=
set FIRSTEP_STALE_NOTE=
for /f "tokens=1,*" %%a in (`%PYEXE% "%LAUNCHER_STALE_PY%" --port %FIRSTEP_LAUNCHER_PORT% 2^>nul`) do (
    set FIRSTEP_STALE=%%a
    set FIRSTEP_STALE_NOTE=%%b
)
if /i "%FIRSTEP_STALE%"=="stale" goto :stale_service
goto :already_running

:stale_service
rem 端口上那个是本应用的旧进程（文件换了、进程没停）：踢掉它，再走下面原本的起服务流程。
rem 身份已经在这条路的上游确认过，所以这里按本端口杀，不会被别的程序误伤。
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%FIRSTEP_LAUNCHER_PORT%" ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
rem 等一拍再起：刚被杀的进程要放开端口，抢这一拍会让新进程绑不上、误报启动超时
"%SystemRoot%\System32\ping.exe" -n 2 127.0.0.1 >nul 2>&1

:start_service
rem 后台启动服务，日志追加到用户配置目录
start "" /b %PYEXE% -m contest_generator.webapp >> "%USERPROFILE%\.contest_generator\webapp.log" 2>&1

rem ---------- 3. 轮询 /api/health 最多 20 秒 ----------
rem 用 ping 当「睡一秒」：timeout.exe 在 stdin 被重定向（无控制台输入）时会立刻报错退出，
rem 轮询预算就会被瞬间烧光、把「服务没起来」误判成超时（验收侧实测踩到过）。
set /a tries=0
:wait
"%SystemRoot%\System32\ping.exe" -n 2 127.0.0.1 >nul 2>&1
set /a tries+=1
%PYEXE% -c "import urllib.request,json;json.load(urllib.request.urlopen('http://127.0.0.1:%FIRSTEP_LAUNCHER_PORT%/api/health',timeout=1))" >nul 2>&1
if not errorlevel 1 goto :started
if %tries% geq 20 goto :timeout
goto :wait

:no_python
rem launcher-log
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_LOG_PS1%" -Reason no_python
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('没有找到 Python。请先安装 Python 3.13 或更新版本（https://www.python.org/downloads/），装完运行 install.bat 再启动',0,'firstep 启动失败',16)"
exit /b 1

:old_python
rem launcher-log
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_LOG_PS1%" -Reason old_python
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('找到的 Python 版本太旧，需要 3.13 或更新版本。请到 https://www.python.org/downloads/ 下载新版安装后重试',0,'firstep 启动失败',16)"
exit /b 1

:no_deps
rem launcher-log
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_LOG_PS1%" -Reason no_deps
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('依赖没有装好。请先双击运行 install.bat（会创建虚拟环境并安装依赖），装完再启动。详情见：%USERPROFILE%\.contest_generator\launcher.log',0,'firstep 启动失败',16)"
exit /b 1

:port_busy
rem launcher-log
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_LOG_PS1%" -Reason port_busy port=%FIRSTEP_LAUNCHER_PORT%
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('端口 %FIRSTEP_LAUNCHER_PORT% 已被其他程序占用，本工具不会自动换端口。请先关闭占用该端口的程序，再重新双击 start-app.vbs。详情见：%USERPROFILE%\.contest_generator\launcher.log',0,'firstep 启动失败',16)"
exit /b 1

:timeout
rem launcher-log
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_LOG_PS1%" -Reason timeout port=%FIRSTEP_LAUNCHER_PORT%
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "(New-Object -ComObject WScript.Shell).Popup('启动超时（20 秒），服务未能就绪。请运行 install.bat 检查依赖，并查看日志：%USERPROFILE%\.contest_generator\webapp.log（启动原因见 %USERPROFILE%\.contest_generator\launcher.log）',0,'firstep 启动失败',16)"
exit /b 1

:already_running
rem launcher-log
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_LOG_PS1%" -Reason already_running port=%FIRSTEP_LAUNCHER_PORT% %FIRSTEP_STALE_NOTE%
start "" "http://127.0.0.1:%FIRSTEP_LAUNCHER_PORT%"
exit /b 0

:started
rem launcher-log
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%LAUNCHER_LOG_PS1%" -Reason started tries=%tries% port=%FIRSTEP_LAUNCHER_PORT% %FIRSTEP_STALE_NOTE%
start "" "http://127.0.0.1:%FIRSTEP_LAUNCHER_PORT%"
exit /b 0
