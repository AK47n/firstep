@echo off
rem firstep 备用停止：杀掉占用 8000 端口的进程（正常情况关浏览器即可停，
rem 浏览器崩溃/断电后服务可能变孤儿，用它兜底）
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /f /pid %%p
