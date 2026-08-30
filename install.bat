@echo off
rem firstep 一键安装：检测 Python → 创建虚拟环境 → 安装依赖 → 自检 → 首次库目录
chcp 936 >nul
cd /d "%~dp0"

echo ============================================
echo  firstep（电赛工程生成器）一键安装
echo ============================================
echo.

rem ---------- 第 1 步：检测 Python ----------
where python >nul 2>&1
if errorlevel 1 goto :need_python

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)"
if errorlevel 1 goto :old_python

echo [1/4] Python 检查通过（需要 3.13 或更新版本）

rem ---------- 第 2 步：虚拟环境 ----------
if not exist ".venv\Scripts\python.exe" (
    echo [2/4] 正在创建虚拟环境 .venv（第一次需要一点时间）...
    python -m venv .venv
    if errorlevel 1 goto :venv_fail
) else (
    echo [2/4] 虚拟环境已存在，跳过创建
)
if not exist ".venv\Scripts\python.exe" goto :venv_fail

rem ---------- 第 3 步：安装依赖 ----------
echo [3/4] 正在安装依赖（需要联网，约几分钟；可重复运行）...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :pip_fail

rem ---------- 第 4 步：首次运行自动指向随包 library（已存在配置则跳过） ----------
".venv\Scripts\python.exe" -c "from contest_generator.config import write_bootstrap_config as _w; _w(r'%~dp0library\modules', r'%~dp0library\masters')"
if errorlevel 1 (
    echo [4/4] 自动配置库目录失败（不影响安装）；可稍后到「设置 → 库目录」手动填入
) else (
    echo [4/4] 库目录已就绪：首次安装自动指向随包 library（已有配置则未改动）
)
rem ---------- 自检 ----------
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, pypdf, PIL, fitz"
if errorlevel 1 goto :check_fail

echo.
echo ============================================
echo  安装完成！请双击 start-app.vbs 启动
echo  （浏览器会自动打开 http://127.0.0.1:8000）
echo ============================================
echo.
pause
exit /b 0

:need_python
echo [错误] 没有找到 Python。
echo 请先安装 Python 3.13 或更新版本，下载地址：
echo   https://www.python.org/downloads/
echo 安装时勾选 "Add python.exe to PATH"，装完重新运行本脚本。
pause
exit /b 1

:old_python
echo [错误] 找到的 Python 版本太旧（需要 3.13 或更新）。
echo 请到 https://www.python.org/downloads/ 下载新版安装，装完重新运行本脚本。
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
