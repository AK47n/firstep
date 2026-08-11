@echo off
rem firstep 启动器（由 start-app.vbs 隐藏运行，无黑窗口）：
rem 服务完全后台（无窗口，日志落文件），浏览器直接打开；
rem 关掉浏览器最后一个标签页 = 停止服务（应用内标签会话机制）。
rem 重复双击只会再开一个浏览器标签。
cd /d "%~dp0"
set PYTHONPATH=src
set FIRSTEP_LAUNCHER=1

rem 已在运行？直接开浏览器（幂等）
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 goto :open

rem 启动服务：后台运行，日志追加到用户配置目录
start "" /b python -m contest_generator.webapp >> "%USERPROFILE%\.contest_generator\webapp.log" 2>&1

rem 等服务就绪（最多 20 秒），就绪后开浏览器
set /a tries=0
:wait
timeout /t 1 /nobreak >nul
set /a tries+=1
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 goto :open
if %tries% geq 20 goto :fail
goto :wait

:fail
exit /b 1

:open
start "" "http://127.0.0.1:8000"
exit /b 0
