# -*- coding: utf-8 -*-
"""把「安装收尾创建桌面快捷方式」补进 install.bat（工单 beginner-shortcut/01）。

可重复运行：锚点是**原始** install.bat 的字面片段，找不到就先用 git 恢复原文再打
（避免「改一次就跑不了第二次」）。想改负载就改下面的 PAYLOAD 再跑本脚本。

硬约束：install.bat 必须保持 GBK(cp936) + 无 BOM + CRLF。本脚本用精确编码读写，
并在改动后做字节级自检（不得出现 U+FFFD，行尾必须仍为 CRLF）。
"""
from __future__ import annotations

import base64
import subprocess
from pathlib import Path

BAT = Path(r"C:\Users\luoji\Desktop\firstep\install.bat")
REPO = BAT.parent

PAYLOAD = """$ErrorActionPreference = 'Stop'
$root = $env:FIRSTEP_ROOT.TrimEnd('\\')
$p = Join-Path ([Environment]::GetFolderPath('Desktop')) 'firstep.lnk'
if (Test-Path $p) { exit 0 }
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p)
$s.TargetPath = "$env:SystemRoot\\System32\\wscript.exe"
$s.Arguments = '"' + $root + '\\start-app.vbs"'
$s.WorkingDirectory = $root
$s.Description = 'firstep'
$s.Save()"""

b64 = base64.b64encode(PAYLOAD.encode("utf-16-le")).decode("ascii")
assert all(c.isalnum() or c in "+/=" for c in b64), "负载必须纯 ASCII Base64"

ANCHOR = "rem ---------- 第 4 步：首次运行自动指向随包 library"
ALREADY_PATCHED = "[5/5]"  # 只在新版本里出现，用于判断「已打过补丁」

text = BAT.read_bytes().decode("gbk")
if ALREADY_PATCHED in text:  # 已打过补丁 → 先回到原文再打，保证幂等
    print("install.bat 已是打过补丁的状态 → 先用 git 恢复原文")
    subprocess.run(["git", "checkout", "--", "install.bat"], cwd=REPO, check=True)
    text = BAT.read_bytes().decode("gbk")
assert ANCHOR in text, "install.bat 不是预期的原文（锚点缺失）"

REPLACEMENTS: list[tuple[str, str]] = [
    # 0) 文件头注释里的流程概述补上「快捷方式」
    (
        "rem firstep 一键安装：检测 Python → 创建虚拟环境 → 安装依赖 → 自检 → 首次库目录\r\n",
        "rem firstep 一键安装：检测 Python → 创建虚拟环境 → 安装依赖 → 首次库目录 → 桌面快捷方式 → 自检\r\n",
    ),
    # 1) 工具根：cmd 的 set 不导出给子进程，必须显式设，否则负载里 $env:FIRSTEP_ROOT 为空
    (
        'chcp 936 >nul\r\ncd /d "%~dp0"\r\n',
        'chcp 936 >nul\r\ncd /d "%~dp0"\r\n'
        "rem 工具根（快捷方式负载要用）：cmd 的 set 不自动导出给子进程，必须显式设\r\n"
        'set "FIRSTEP_ROOT=%~dp0"\r\n',
    ),
    # 2) 步骤编号 4 步 → 5 步
    ("echo [1/4] Python 检查通过", "echo [1/5] Python 检查通过"),
    ("echo [2/4] 正在创建虚拟环境", "echo [2/5] 正在创建虚拟环境"),
    ("echo [2/4] 虚拟环境已存在", "echo [2/5] 虚拟环境已存在"),
    ("echo [3/4] 正在安装依赖", "echo [3/5] 正在安装依赖"),
    ("echo [4/4] 自动配置库目录失败", "echo [4/5] 自动配置库目录失败"),
    ("echo [4/4] 库目录已就绪", "echo [4/5] 库目录已就绪"),
    # 3) 新增第 5 步：桌面快捷方式（放在依赖自检之前）
    (
        "rem ---------- 自检 ----------",
        "rem ---------- 第 5 步：桌面快捷方式（可选，失败不阻断安装）----------\r\n"
        "rem 负载用 -EncodedCommand 传（Base64 UTF-16LE）：直接 -Command 在本机实测会被\r\n"
        "rem cmd 吃掉内层引号（$s.Arguments 的引号）→ ParseError。负载内幂等：已存在即跳过。\r\n"
        f"set FIRSTEP_SHORTCUT_PS={b64}\r\n"
        'if defined FIRSTEP_SHORTCUT_PS (\r\n'
        '    echo [5/5] 正在创建桌面快捷方式...\r\n'
        '    "%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile '
        '-ExecutionPolicy Bypass -EncodedCommand "%FIRSTEP_SHORTCUT_PS%"\r\n'
        "    if errorlevel 1 (\r\n"
        '        echo [5/5] 桌面快捷方式创建失败（不影响使用）：双击本目录的 start-app.vbs 即可启动\r\n'
        "    ) else (\r\n"
        '        echo [5/5] 桌面快捷方式已就绪（已存在则不重复创建）\r\n'
        "    )\r\n"
        ") else (\r\n"
        '    echo [5/5] 跳过桌面快捷方式\r\n'
        ")\r\n"
        "rem ---------- 自检 ----------",
    ),
    # 4) 完成提示：两个入口都告诉用户
    (
        "echo  安装完成！请双击 start-app.vbs 启动\r\necho  （浏览器会自动打开 http://127.0.0.1:8000）",
        "echo  安装完成！双击桌面的 firstep 快捷方式启动\r\n"
        "echo  （也可以双击本目录的 start-app.vbs；浏览器会自动打开 http://127.0.0.1:8000）",
    ),
]

for old, new in REPLACEMENTS:
    hits = text.count(old)
    assert hits == 1, f"锚点命中 {hits} 次（应为 1）：{old[:48]!r}"
    text = text.replace(old, new)

out = text.encode("gbk")
assert not out.startswith(b"\xef\xbb\xbf"), "不得引入 BOM"
assert b"\xef\xbf\xbd" not in out, "出现 U+FFFD —— 编码往返有损"
assert out.count(b"\n") == out.count(b"\r\n"), "行尾必须全部为 CRLF"
BAT.write_bytes(out)
print(f"install.bat 已打补丁：{len(out)} bytes，负载 {len(b64)} chars")
