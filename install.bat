@echo off
rem firstep 一键安装：检测 Python → 创建虚拟环境 → 安装依赖 → 首次库目录 → 桌面快捷方式 → 自检
chcp 936 >nul
cd /d "%~dp0"
rem 工具根（快捷方式负载要用）：cmd 的 set 不自动导出给子进程，必须显式设
set "FIRSTEP_ROOT=%~dp0"

echo ============================================
echo  firstep（电赛工程生成器）一键安装
echo ============================================
echo.

rem ---------- 第 1 步：检测 Python ----------
where python >nul 2>&1
if errorlevel 1 goto :need_python

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)"
if errorlevel 1 goto :old_python

echo [1/5] Python 检查通过（需要 3.13 或更新版本）

rem ---------- 第 2 步：虚拟环境 ----------
if not exist ".venv\Scripts\python.exe" (
    echo [2/5] 正在创建虚拟环境 .venv（第一次需要一点时间）...
    python -m venv .venv
    if errorlevel 1 goto :venv_fail
) else (
    echo [2/5] 虚拟环境已存在，跳过创建
)
if not exist ".venv\Scripts\python.exe" goto :venv_fail

rem ---------- 第 3 步：安装依赖 ----------
echo [3/5] 正在安装依赖（需要联网，约几分钟；可重复运行）...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :pip_fail

rem ---------- 第 4 步：首次运行自动指向随包 library（已存在配置则跳过） ----------
".venv\Scripts\python.exe" -c "from contest_generator.config import write_bootstrap_config as _w; _w(r'%~dp0library\modules', r'%~dp0library\masters')"
if errorlevel 1 (
    echo [4/5] 自动配置库目录失败（不影响安装）；可稍后到「设置 → 库目录」手动填入
) else (
    echo [4/5] 库目录已就绪：首次安装自动指向随包 library（已有配置则未改动）
)
rem ---------- 第 5 步：桌面快捷方式（可选，失败不阻断安装）----------
rem 负载用 -EncodedCommand 传（Base64 UTF-16LE）：直接 -Command 在本机实测会被
rem cmd 吃掉内层引号（$s.Arguments 的引号）→ ParseError。负载内幂等：已存在即跳过。
set FIRSTEP_SHORTCUT_PS=JABFAHIAcgBvAHIAQQBjAHQAaQBvAG4AUAByAGUAZgBlAHIAZQBuAGMAZQAgAD0AIAAnAFMAdABvAHAAJwAKACQAcgBvAG8AdAAgAD0AIAAkAGUAbgB2ADoARgBJAFIAUwBUAEUAUABfAFIATwBPAFQALgBUAHIAaQBtAEUAbgBkACgAJwBcACcAKQAKACQAcAAgAD0AIABKAG8AaQBuAC0AUABhAHQAaAAgACgAWwBFAG4AdgBpAHIAbwBuAG0AZQBuAHQAXQA6ADoARwBlAHQARgBvAGwAZABlAHIAUABhAHQAaAAoACcARABlAHMAawB0AG8AcAAnACkAKQAgACcAZgBpAHIAcwB0AGUAcAAuAGwAbgBrACcACgBpAGYAIAAoAFQAZQBzAHQALQBQAGEAdABoACAAJABwACkAIAB7ACAAZQB4AGkAdAAgADAAIAB9AAoAJABzACAAPQAgACgATgBlAHcALQBPAGIAagBlAGMAdAAgAC0AQwBvAG0ATwBiAGoAZQBjAHQAIABXAFMAYwByAGkAcAB0AC4AUwBoAGUAbABsACkALgBDAHIAZQBhAHQAZQBTAGgAbwByAHQAYwB1AHQAKAAkAHAAKQAKACQAcwAuAFQAYQByAGcAZQB0AFAAYQB0AGgAIAA9ACAAIgAkAGUAbgB2ADoAUwB5AHMAdABlAG0AUgBvAG8AdABcAFMAeQBzAHQAZQBtADMAMgBcAHcAcwBjAHIAaQBwAHQALgBlAHgAZQAiAAoAJABzAC4AQQByAGcAdQBtAGUAbgB0AHMAIAA9ACAAJwAiACcAIAArACAAJAByAG8AbwB0ACAAKwAgACcAXABzAHQAYQByAHQALQBhAHAAcAAuAHYAYgBzACIAJwAKACQAcwAuAFcAbwByAGsAaQBuAGcARABpAHIAZQBjAHQAbwByAHkAIAA9ACAAJAByAG8AbwB0AAoAJABzAC4ARABlAHMAYwByAGkAcAB0AGkAbwBuACAAPQAgACcAZgBpAHIAcwB0AGUAcAAnAAoAJABzAC4AUwBhAHYAZQAoACkA
if defined FIRSTEP_SHORTCUT_PS (
    echo [5/5] 正在创建桌面快捷方式...
    "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -EncodedCommand "%FIRSTEP_SHORTCUT_PS%"
    if errorlevel 1 (
        echo [5/5] 桌面快捷方式创建失败（不影响使用）：双击本目录的 start-app.vbs 即可启动
    ) else (
        echo [5/5] 桌面快捷方式已就绪（已存在则不重复创建）
    )
) else (
    echo [5/5] 跳过桌面快捷方式
)
rem ---------- 自检 ----------
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, pypdf, PIL, fitz"
if errorlevel 1 goto :check_fail

echo.
echo ============================================
echo  安装完成！双击桌面的 firstep 快捷方式启动
echo  （也可以双击本目录的 start-app.vbs；浏览器会自动打开 http://127.0.0.1:8000）
echo.
echo  以后每次启动：双击桌面的 firstep 即可，不用再运行本脚本。
echo ============================================
echo.
pause
exit /b 0

:need_python
echo [错误] 没有找到 Python。
echo 请先安装 Python 3.13 或更新版本，下载地址：
echo   https://www.python.org/downloads/
echo 安装时勾选 "Add python.exe to PATH"，装完重新运行本脚本即可。
pause
exit /b 1

:old_python
echo [错误] 找到的 Python 版本太旧（需要 3.13 或更新）。
echo 请到 https://www.python.org/downloads/ 下载新版安装，装完重新运行本脚本即可。
pause
exit /b 1

:venv_fail
echo [错误] 创建虚拟环境失败，请检查 Python 安装是否完整。
pause
exit /b 1

:pip_fail
echo [错误] 安装依赖失败，请检查网络后重新运行本脚本。
echo 提示：本脚本可重复运行，已装好的部分会自动跳过。
pause
exit /b 1

:check_fail
echo [错误] 依赖自检未通过，请重新运行本脚本。
pause
exit /b 1
