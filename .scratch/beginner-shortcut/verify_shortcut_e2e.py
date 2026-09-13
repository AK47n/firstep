# -*- coding: utf-8 -*-
"""真机 e2e：把 install.bat 第 5 步的负载真正跑一次，验证桌面快捷方式落地（工单 beginner-shortcut/01）。

口径：负载从 install.bat 原文提取（不复制粘贴），桌面已有的 firstep.lnk 先备份、测完恢复。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\luoji\Desktop\firstep")
BAT = ROOT / "install.bat"
PWSH = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
DESKTOP = Path(os.environ["USERPROFILE"]) / "Desktop"
LNK = DESKTOP / "firstep.lnk"
BACKUP = DESKTOP / "firstep.lnk.probe-backup"


def run(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, **kw)


m = re.search(r"set\s+FIRSTEP_SHORTCUT_PS=([\w+/=]+)", BAT.read_text(encoding="gbk"))
assert m, "install.bat 里没有快捷方式负载"
b64 = m.group(1)
print(f"从 install.bat 提取负载：{len(b64)} chars")

had_existing = LNK.exists()
if had_existing:
    shutil.move(str(LNK), str(BACKUP))
    print("已备份桌面上既有的 firstep.lnk")

env = dict(os.environ, FIRSTEP_ROOT=str(ROOT) + "\\")
try:
    # 第 1 跑：应当建出快捷方式
    r1 = run([str(PWSH), "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", b64], env=env)
    print(f"[第 1 跑] exit={r1.returncode}  created={LNK.exists()}")
    assert r1.returncode == 0, f"负载非零退出：{r1.stderr}"
    assert LNK.exists(), "桌面没有出现 firstep.lnk"

    # 读回属性（外部可观察行为）
    probe_b64 = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"
        + str(LNK)
        + "');'Target=' + $s.TargetPath;'Args=' + $s.Arguments;'WorkDir=' + $s.WorkingDirectory"
    )
    b = __import__("base64").b64encode(probe_b64.encode("utf-16-le")).decode("ascii")
    r2 = run([str(PWSH), "-NoProfile", "-EncodedCommand", b])
    print(r2.stdout.strip())
    assert "wscript.exe" in r2.stdout, "Target 不是 wscript.exe"
    assert "start-app.vbs" in r2.stdout, "Arguments 未指向 start-app.vbs"
    assert str(ROOT).lower() in r2.stdout.lower(), "WorkingDirectory 不是工具根"

    # 第 2 跑：幂等（改写 Description 后重跑，必须没被动过）
    mark_b64 = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"
        + str(LNK)
        + "');$s.Description='probe-sentinel';$s.Save()"
    )
    b2 = __import__("base64").b64encode(mark_b64.encode("utf-16-le")).decode("ascii")
    run([str(PWSH), "-NoProfile", "-EncodedCommand", b2])
    r3 = run([str(PWSH), "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", b64], env=env)
    chk_b64 = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"
        + str(LNK)
        + "');'Desc=' + $s.Description"
    )
    b3 = __import__("base64").b64encode(chk_b64.encode("utf-16-le")).decode("ascii")
    r4 = run([str(PWSH), "-NoProfile", "-EncodedCommand", b3])
    print(f"[第 2 跑] exit={r3.returncode}  {r4.stdout.strip()}")
    assert "probe-sentinel" in r4.stdout, "重跑覆盖了已有快捷方式（幂等失效）"
    print("PASS：目标/参数/工作目录正确，且重跑不覆盖")
finally:
    if LNK.exists():
        LNK.unlink()
    if had_existing:
        shutil.move(str(BACKUP), str(LNK))
        print("已恢复原有 firstep.lnk")
    else:
        print("已清理探针创建的 firstep.lnk（原本没有）")
