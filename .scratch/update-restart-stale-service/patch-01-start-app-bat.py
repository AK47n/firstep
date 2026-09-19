# -*- coding: utf-8 -*-
"""一次性：把「旧进程判据」接进 `start-app.bat`（工单 `update-restart-stale-service/01`）。

**已经跑过了**（2026-09-18）。留在这里是为了记下这次改动**怎么做的**：`start-app.bat` 是
**GBK 无 BOM + CRLF**，用 UTF-8 编辑器改会把中文注释写坏（cmd 按 ANSI 解码），所以唯一安全
的姿势是「读字节 → decode gbk → 改文本 → encode gbk → 写字节」，并且每一步都断言锚点**唯一命中**。

幂等性：第二次跑会在第一个锚点处报错退出（旧锚点已经不存在）——它拒绝把同一段接两遍。

用法::

    python .scratch/update-restart-stale-service/patch-01-start-app-bat.py          # dry-run，只打印
    python .scratch/update-restart-stale-service/patch-01-start-app-bat.py --write  # 落盘
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BAT = ROOT / "start-app.bat"

# ---- 锚点 1：留痕脚本路径旁边，登记判据脚本的路径（同一个 %~dp0 口径）----
ANCHOR_PATHS = "set LAUNCHER_LOG_PS1=%~dp0tools\\launcher-log.ps1"
PATCH_PATHS = "\r\n".join([
    ANCHOR_PATHS,
    "rem 旧进程判据脚本的绝对路径（同一个 %~dp0 口径）",
    "set LAUNCHER_STALE_PY=%~dp0tools\\launcher-stale.py",
])

# ---- 锚点 2：身份判定那两行 —— 从「直接复用」改成「先确认身份、再问一句版本」----
# 锚点必须是**两行**：原来第一行是「是本应用就跳 already_running」，第二行是「否则 port_busy」。
# 只替换第一行会**把身份判据整个删掉**（别的程序占着端口也会被当成自己人）——第一版就是这么错的，
# 被 `test_bat_still_gates_the_kill_on_identity_and_keeps_reason_codes` 拦下。
ANCHOR_IDENTITY = (
    'if /i "%FIRSTEP_HEALTH_APP%"=="contest-generator" goto :already_running'
    "\r\ngoto :port_busy"
)
PATCH_IDENTITY = "\r\n".join([
    'if /i not "%FIRSTEP_HEALTH_APP%"=="contest-generator" goto :port_busy',
    "rem 身份是本应用：再比一次版本。更新换的是盘上的文件，跑着的进程不会跟着变——",
    "rem 旧进程还占着端口时，光看身份会把它当成「已在运行」（真机演练实测：盘上 1.2.1、服务仍 1.1.1）。",
    "rem 版本比较不在这里手写（批处理只会比字符串与整数），问 tools\\launcher-stale.py：",
    "rem 它打印 stale / fresh / unknown 三选一，不是 stale（空、unknown、其它）一律走原来的复用路径。",
    "rem usebackq 不能省：不加它时反引号不是「执行命令」而是**文件名**，循环一次都不跑、",
    "rem 判据静默失效（真机演练第一次就是这么红的——文件名的静默空转比报错更难看出来）。",
    "set FIRSTEP_STALE=",
    "set FIRSTEP_STALE_NOTE=",
    'for /f "usebackq tokens=1,*" %%a in (`%PYEXE% "%LAUNCHER_STALE_PY%" --port %FIRSTEP_LAUNCHER_PORT% 2^>nul`) do (',
    "    set FIRSTEP_STALE=%%a",
    "    set FIRSTEP_STALE_NOTE=%%b",
    ")",
    'if /i "%FIRSTEP_STALE%"=="stale" goto :stale_service',
    "goto :already_running",
])

# ---- 锚点 3：起服务那个标签之前，插入「踢旧进程」的落点 ----
ANCHOR_START = "\r\n:start_service\r\n"
PATCH_START = "\r\n".join([
    "",
    ":stale_service",
    "rem 端口上那个是本应用的旧进程（文件换了、进程没停）：踢掉它，再走下面原本的起服务流程。",
    "rem 身份已经在这条路的上游确认过，所以这里按本端口杀，不会被别的程序误伤。",
    'for /f "tokens=5" %%p in (\'netstat -ano ^| findstr ":%FIRSTEP_LAUNCHER_PORT%" ^| findstr "LISTENING"\') do taskkill /F /PID %%p >nul 2>&1',
    "rem 等一拍再起：刚被杀的进程要放开端口，抢这一拍会让新进程绑不上、误报启动超时",
    '"%SystemRoot%\\System32\\ping.exe" -n 2 127.0.0.1 >nul 2>&1',
    "",
    ":start_service",
    "",
])

# ---- 锚点 4/5：两条留痕带上 CLI 给的版本字段（空值就地消失，不会写出空 key）----
ANCHOR_LOG_ALREADY = "-Reason already_running port=%FIRSTEP_LAUNCHER_PORT%"
PATCH_LOG_ALREADY = ANCHOR_LOG_ALREADY + " %FIRSTEP_STALE_NOTE%"
ANCHOR_LOG_STARTED = "-Reason started tries=%tries% port=%FIRSTEP_LAUNCHER_PORT%"
PATCH_LOG_STARTED = ANCHOR_LOG_STARTED + " %FIRSTEP_STALE_NOTE%"

# ---- 锚点 6（第二轮补的）：起服务之前先把数据目录建出来 ----
# 为什么（真机演练用一次红的换来的）：`:start_service` 那条 `start` 把日志重定向进
# `%USERPROFILE%\.contest_generator\webapp.log`。**目录不在时 cmd 直接报「系统找不到指定的路径」，
# 服务根本不会起**——演练把 USERPROFILE 重定向到一次性目录，那里没有这个目录，于是
# `launcher.log` 记 `timeout`、`webapp.log` 压根不存在。真实用户那边这个目录由 install.bat 的
# bootstrap 配置建出来（用户手动删掉配置目录就没这一层了），所以启动器自己保证它存在。
ANCHOR_START_SERVICE = "rem 后台启动服务，日志追加到用户配置目录"
PATCH_START_SERVICE = "\r\n".join([
    "rem 数据目录必须先存在：下面这条启动命令把日志重定向进用户配置目录下的 webapp.log——",
    "rem 目录不在时 cmd 直接报「系统找不到指定的路径」，服务根本不会起（真机演练的重定向 profile 撞上过；",
    "rem 真实用户那边这个目录由 install.bat 的 bootstrap 配置建出来，用户手动删过就没了）。",
    'if not exist "%USERPROFILE%\\.contest_generator" mkdir "%USERPROFILE%\\.contest_generator"',
    ANCHOR_START_SERVICE,
])

REPLACEMENTS = [
    (ANCHOR_PATHS, PATCH_PATHS),
    (ANCHOR_IDENTITY, PATCH_IDENTITY),
    (ANCHOR_START, PATCH_START),
    (ANCHOR_LOG_ALREADY, PATCH_LOG_ALREADY),
    (ANCHOR_LOG_STARTED, PATCH_LOG_STARTED),
    (ANCHOR_START_SERVICE, PATCH_START_SERVICE),
]


def main() -> int:
    write = "--write" in sys.argv[1:]
    target = BAT
    if "--bat" in sys.argv[1:]:
        target = Path(sys.argv[sys.argv.index("--bat") + 1])
    raw = target.read_bytes()
    text = raw.decode("gbk")

    for old, _new in REPLACEMENTS:
        hits = text.count(old)
        if hits != 1:
            print(f"[拒绝] 锚点命中 {hits} 次（应为 1 次）：{old[:60]!r}", file=sys.stderr)
            print("       ——旧锚点可能已经改过了；本脚本只跑一次。", file=sys.stderr)
            return 2

    patched = text
    for old, new in REPLACEMENTS:
        patched = patched.replace(old, new, 1)

    if patched == text:
        print("[拒绝] 改完与改前一样——锚点选错了", file=sys.stderr)
        return 2
    # CRLF 不许被改坏（cmd 对裸 LF 的容忍度不如 CRLF，且既有守卫钉着它）
    naked = patched.replace("\r\n", "").count("\n")
    if naked:
        print(f"[拒绝] 改完出现 {naked} 处裸 LF", file=sys.stderr)
        return 2

    print(f"改前 {len(text)} 字符 / 改后 {len(patched)} 字符（+{len(patched) - len(text)}）")
    for old, new in REPLACEMENTS:
        print(f"  · {old.splitlines()[0][:64]!r} → {len(new.splitlines())} 行")

    if not write:
        print("\n（dry-run：加 --write 才落盘）")
        return 0

    # 原文件的换行口径也核一遍：不加 BOM、保留 CRLF
    target.write_bytes(patched.encode("gbk"))
    back = target.read_bytes()
    assert back[:3] != b"\xef\xbb\xbf", "写坏了：出现 UTF-8 BOM"
    assert back.decode("gbk") == patched, "写坏了：GBK 往返不一致"
    print(f"\n已落盘：{target}（{len(back)} 字节）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
