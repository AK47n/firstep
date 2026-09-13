"""工单 newuser-download/07 的 install.bat 补丁（一次跑完、可重复跑）。

两处都是这次演练新发现的问题：

1. **完成提示写死 `http://127.0.0.1:8000`**（L2 卡点 K6）——端口被 `FIRSTEP_LAUNCHER_PORT`
   覆盖时（换端口 / 同机第二实例 / 验收）提示会指错地址。改法是**只说端口号**，
   与 `start-app.bat` 同一口径（同一环境变量、同一默认值），不引入第二套说法。
   注意不能在批处理里重复 `start-app.bat` 的端口校验逻辑：那边 `chcp 936` 在 set 之前，
   而中文提示在下面——顺序不能倒（上次这么写会乱码）。

2. **没装 Python 时无法在没有 Python 的机器上验证**——不引入自举/下载自动化
   （安全与体积问题），但把「怎么继续」写明：给官方下载页地址与两条提醒；
   再加一个**交互式暂停**（读一行再重查），这样用户可以先去装 Python、回来直接回车继续，
   不必重跑一遍已完成的步骤。

补丁只改文案与一处 `set /a`，且 `set /a` 在普通安装路径下**不改变任何行为**（PORT 未被设置时跳过）。
"""

from __future__ import annotations

from pathlib import Path

BAT = Path(__file__).resolve().parents[2] / "install.bat"

# 端口相关变量插在「工具根」之后（~dp0 已可用，且在任何 echo 之前）
ANCHOR_ROOT = 'set "FIRSTEP_ROOT=%~dp0"\r\n'
PORT_BLOCK = (
    'set "FIRSTEP_ROOT=%~dp0"\r\n'
    "\r\n"
    "rem ---------- 本次启动端口（与 start-app.bat 同一口径：只认 1..65535 的纯数字，缺省 8000）----------\r\n"
    "rem 只在完成提示里报给用户看；不做第二套校验逻辑（那边的校验在 start-app.bat 里，单一事实源）\r\n"
    "set PORT=8000\r\n"
    "if defined FIRSTEP_LAUNCHER_PORT set PORT=%FIRSTEP_LAUNCHER_PORT%\r\n"
    "echo %PORT%| findstr /r \"^[1-9][0-9]*$\" >nul 2>&1\r\n"
    "if errorlevel 1 set PORT=8000\r\n"
    "set /a PORT_OK=PORT\r\n"
    "if %PORT_OK% gtr 65535 set PORT=8000\r\n"
)

PATCHES: tuple[tuple[str, str, int], ...] = (
    # ---- 1. 完成提示：端口动态 ----
    (
        "echo  （也可以双击本目录的 start-app.vbs；浏览器会自动打开 http://127.0.0.1:8000）\r\n",
        "echo  （也可以双击本目录的 start-app.vbs；浏览器会自动打开 http://127.0.0.1:%PORT%）\r\n",
        1,
    ),
    # ---- 2. 没装 Python：给地址 + 让用户能回来继续 ----
    (
        ":need_python\r\n"
        "echo [错误] 没有找到 Python。\r\n"
        "echo 请先安装 Python 3.13 或更新版本，下载地址：\r\n"
        "echo   https://www.python.org/downloads/\r\n"
        'echo 安装时勾选 "Add python.exe to PATH"，装完重新运行本脚本即可。\r\n'
        "pause\r\n"
        "exit /b 1\r\n",
        ":need_python\r\n"
        "echo [错误] 没有找到 Python。本工具需要 Python 3.13 或更新版本。\r\n"
        "echo.\r\n"
        "echo   1) 打开这个地址下载安装：https://www.python.org/downloads/\r\n"
        'echo   2) 安装时务必勾选 "Add python.exe to PATH"\r\n'
        "echo   3) 装完回到这个窗口按一次回车，本脚本会重新检查并接着装；\r\n"
        "echo      也可以现在关掉窗口，之后再双击一次本脚本（已装好的步骤会自动跳过）。\r\n"
        "echo.\r\n"
        "pause\r\n"
        "call :recheck_python\r\n"
        "exit /b 1\r\n",
        1,
    ),
)

# 版本太旧的分支：同样给「回来继续」的路径
OLD_PYTHON_OLD = (
    ":old_python\r\n"
    "echo [错误] 找到的 Python 版本太旧（需要 3.13 或更新）。\r\n"
    "echo 请到 https://www.python.org/downloads/ 下载新版安装，装完重新运行本脚本即可。\r\n"
    "pause\r\n"
    "exit /b 1\r\n"
)
OLD_PYTHON_NEW = (
    ":old_python\r\n"
    "echo [错误] 找到的 Python 版本太旧（需要 3.13 或更新）。\r\n"
    "echo 请到 https://www.python.org/downloads/ 下载新版安装；装好后回到本窗口按回车继续，\r\n"
    "echo 或之后再双击一次本脚本（已装好的步骤会自动跳过）。\r\n"
    "pause\r\n"
    "call :recheck_python\r\n"
    "exit /b 1\r\n"
)

# 重查子过程：放在文件末尾（正常流程走不到，只被 call）。
# 用户在提示窗口里装好 Python 后按回车 → 重查一次版本 → 满足要求就跳去继续安装。
RECHECK = (
    "\r\n"
    "rem ---------- 子过程：用户装完 Python 后重查（被 :need_python / :old_python 调用）----------\r\n"
    "rem 只做「再查一次」这一件事：不重复安装逻辑、不改任何状态；查不过就如实说清下一步。\r\n"
    ":recheck_python\r\n"
    "where python >nul 2>&1\r\n"
    "if errorlevel 1 (\r\n"
    "    echo.\r\n"
    "    echo 还是没有找到 Python。两种可能：\r\n"
    '    echo   - 还没装完，或安装时没勾 "Add python.exe to PATH"；\r\n'
    "    echo   - PATH 变更对已经打开的窗口不生效——关掉本窗口、重新双击一次本脚本即可。\r\n"
    "    pause\r\n"
    "    exit /b 1\r\n"
    ")\r\n"
    'python -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)"\r\n'
    "if errorlevel 1 (\r\n"
    "    echo.\r\n"
    "    echo 找到了 Python，但版本仍然低于 3.13——请装 3.13 或更新版本。\r\n"
    "    echo 若系统里有多个 Python，可到 https://www.python.org/downloads/ 装新版后重开本窗口再跑一次。\r\n"
    "    pause\r\n"
    "    exit /b 1\r\n"
    ")\r\n"
    "echo.\r\n"
    "echo Python 就绪，继续安装……\r\n"
    "goto :step_python_ok\r\n"
)


def main() -> int:
    raw = BAT.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "install.bat 不应是 UTF-8 BOM"
    text = raw.decode("gbk")
    assert text.count("\n") - text.count("\r\n") == 0, "install.bat 必须全 CRLF"

    # 端口块
    assert text.count(ANCHOR_ROOT) == 1, "工具根锚点不唯一"
    text = text.replace(ANCHOR_ROOT, PORT_BLOCK)

    for old, new, expect in PATCHES:
        found = text.count(old)
        assert found == expect, f"锚点命中 {found} 次（期望 {expect}）：{old[:50]!r}"
        text = text.replace(old, new)

    assert text.count(OLD_PYTHON_OLD) == 1, "old_python 分支锚点不唯一"
    text = text.replace(OLD_PYTHON_OLD, OLD_PYTHON_NEW)

    # 第一个 Python 检查点要能被重查子过程跳回：给当前检查段加标号
    py_anchor = (
        "rem ---------- 第 1 步：检测 Python ----------\r\n"
        "where python >nul 2>&1\r\n"
        "if errorlevel 1 goto :need_python\r\n"
    )
    assert text.count(py_anchor) == 1, "Python 检查段锚点不唯一"
    text = text.replace(
        py_anchor,
        "rem ---------- 第 1 步：检测 Python ----------\r\n"
        ":step_python_ok\r\n"
        "rem 注：:recheck_python 会 goto 到这里——用户装完 Python 按回车就接着往下走\r\n"
        "where python >nul 2>&1\r\n"
        "if errorlevel 1 goto :need_python\r\n",
    )

    # 子过程放文件末尾
    assert text.rstrip().endswith("exit /b 1"), "文件末尾不是预期的失败分支结尾"
    text = text.rstrip("\r\n") + "\r\n" + RECHECK

    BAT.write_bytes(text.encode("gbk"))

    after = BAT.read_bytes()
    assert not after.startswith(b"\xef\xbb\xbf")
    again = after.decode("gbk")
    assert again.count("\n") - again.count("\r\n") == 0, "补丁后出现裸 LF"
    print(f"  已打补丁：端口动态 + 两条失败分支可续跑；字节 {len(raw)} → {len(after)}")
    print("  编码复验：GBK 无 BOM + 全 CRLF  OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
