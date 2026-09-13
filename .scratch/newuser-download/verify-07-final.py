"""最终确认：用**真身原版** install.bat 在干净演练环境跑一次全链路（工单 newuser-download/07）。

与 `verify-02-L2.py` 的区别：那份跑的是一整份真实完整包（含包内说明书）；这份只关心
`install.bat` 自身的行为（端口联动、五步全过、完成提示），用真身仓库的文件拼一个最小工具根，
省掉 770 MB 打包。

（本文件是"把内联 Python 写成文件"的又一次实践：PowerShell 会吞掉 `python -c "..."` 里的引号，
所以凡是有引号的脚本一律落盘再跑。）
"""

from __future__ import annotations

import os
import shutil
import subprocess
import venv
from pathlib import Path

REPO = Path(r"C:\Users\luoji\Desktop\firstep")
STAGE = Path(os.environ["TEMP"]) / "firstep-final"
TOOL = STAGE / "tool"
PROFILE = STAGE / "profile"


def main() -> int:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    TOOL.mkdir(parents=True)
    (PROFILE / "Desktop").mkdir(parents=True)
    for name in ("install.bat", "start-app.bat", "start-app.vbs",
                 "stop-firstep.bat", "stop-firstep.vbs", "pyproject.toml"):
        shutil.copy2(REPO / name, TOOL / name)
    shutil.copytree(REPO / "src", TOOL / "src")
    shutil.copytree(REPO / "library", TOOL / "library", dirs_exist_ok=True)
    venv.create(str(TOOL / ".venv"), with_pip=True, system_site_packages=True)

    env = dict(os.environ)
    env["USERPROFILE"] = str(PROFILE)
    env["FIRSTEP_LAUNCHER_PORT"] = "8020"
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONPATH", None)
    r = subprocess.run(["cmd.exe", "/c", "install.bat"], cwd=str(TOOL), env=env,
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=1800)
    out = r.stdout.decode("gbk", errors="replace")
    (STAGE / "raw.txt").write_text(f"exit={r.returncode}\n{out}", encoding="utf-8")

    print(f"  退出码：{r.returncode}")
    for line in out.splitlines():
        s = line.strip()
        if s and any(k in s for k in ("[1/5]", "[2/5]", "[3/5]", "[4/5]", "[5/5]",
                                      "安装完成", "127.0.0.1", "以后每次启动", "快捷方式", "错误")):
            print(f"    {s}")

    checks = {
        "五步全过": all(f"[{i}/5]" in out for i in range(1, 6)),
        "完成提示报 8020（K6 修复）": "127.0.0.1:8020" in out,
        "提示「不用再运行本脚本」（工单 04）": "不用再运行本脚本" in out,
        "退出码 0": r.returncode == 0,
    }
    print()
    bad = 0
    for label, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        bad += 0 if ok else 1
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
