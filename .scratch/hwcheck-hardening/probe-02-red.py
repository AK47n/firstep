# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/02 的判据强度反证：撤掉那句总口径的**渲染** → 结构钉必须红。

撤的是 ui 初始化路径上那一行调用（不是 fx 里的函数）——因为"函数写好了但没人调用"
正是这一栏出过的坏法（点了没反应 / 首帧空白），也是本单最容易悄悄退回去的形态。

纪律：逐字节读写；跑之前验干净性；跑完复原并复核 sha256；与测试套件不同时跑。
读数落 `.scratch/hwcheck-hardening/probe-02-red.txt`。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
UI = ROOT / "src" / "contest_generator" / "static" / "js" / "ui" / "hwcheck.js"
OUT = pathlib.Path(__file__).with_name("probe-02-red.txt")
CALL = "  renderHwcheckUnverifiedNote();\n"


def _run_js() -> tuple[int, str]:
    done = subprocess.run(
        ["node", "--test", "tests/js/hwcheck.test.mjs"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        shell=True,
    )
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def main() -> int:
    lines: list[str] = []
    original = UI.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines.append(f"ui/hwcheck.js sha256（跑之前）= {before}")

    if CALL not in text:
        lines.append("✗ 前置干净性检查失败：那一行调用本来就不在，反证没有意义。")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2
    lines.append("✓ 前置干净性检查：初始化路径上确实调了 renderHwcheckUnverifiedNote()")

    verdict = 0
    try:
        UI.write_bytes(text.replace(CALL, "", 1).encode("utf-8"))
        code, output = _run_js()
        lines.append(f"撤掉渲染后跑前端用例：exit={code}")
        lines.append("—— node --test 输出（尾部 10 行）——")
        lines.extend(output.strip().splitlines()[-10:])
        lines.append("判据结论 = " + ("✓ 用例红了（结构钉有强度）" if code != 0 else "✗ 用例照样绿（守卫是摆设）"))
        if code == 0:
            verdict = 1
    finally:
        UI.write_bytes(original)

    after = hashlib.sha256(UI.read_bytes()).hexdigest()
    lines.append(f"ui/hwcheck.js sha256（复原后）= {after}")
    lines.append("复原复核 = " + ("✓ 逐字节相同" if after == before else "✗ 字节不同"))
    code2, _ = _run_js()
    lines.append(f"复原后跑前端用例：exit={code2}（应为 0）")
    if after != before or code2 != 0:
        verdict = 1

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
