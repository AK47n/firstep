# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/04 的判据强度反证：把长量纲塞回读数行 → 行缓冲守卫必须红。

塞的是 `debug_uart × stm32` 那条 249 字节的原量纲（本单挪进平台说明的那段）。

纪律：逐字节读写；跑之前验干净性；跑完复原并复核 sha256；与测试套件不同时跑。
读数落 `.scratch/hwcheck-hardening/probe-04-red.txt`。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECIPE = ROOT / "library" / "hwcheck_recipes.json"
OUT = pathlib.Path(__file__).with_name("probe-04-red.txt")
TEST = ("tests/test_hwcheck_recipe.py"
        "::test_every_real_read_line_fits_the_device_line_buffer")
SHORT = "RX 脚电平（1 = 空闲高，0 = 没拉高）"
LONG = ("RX（PA3）脚电平：1 = 对端 TX 正空闲拉高（线通、对端上电）；"
        "0 = 这根 RX 上没人拉高（没接 / 对端没上电 / 接错脚）——它证的是线，不是帧")


def _run_test() -> tuple[int, str]:
    done = subprocess.run(
        [os.sys.executable, "-m", "pytest", TEST, "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=180,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def main() -> int:
    lines: list[str] = []
    original = RECIPE.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines.append(f"配方文件 sha256（跑之前）= {before}")
    lines.append(f"换行形态 = {'CRLF' if bytes([13, 10]) in original else 'LF'}（逐字节读写，不改换行）")

    import json
    short_q = json.dumps(SHORT, ensure_ascii=False)
    long_q = json.dumps(LONG, ensure_ascii=False)
    if text.count(short_q) != 1:
        lines.append("✗ 前置干净性检查失败：短量纲串不唯一（配方被改过？），反证没有意义。")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2
    if text.count(LONG) != 1:
        lines.append(
            "✗ 前置干净性检查失败：长口径应当**恰好出现一次**（已被挪进平台说明），"
            f"实际 {text.count(LONG)} 次——配方被改过，反证没有意义。"
        )
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2
    lines.append("✓ 前置干净性检查：行上是短量纲；长口径只剩平台说明里那一处")

    verdict = 0
    try:
        RECIPE.write_bytes(text.replace(short_q, long_q, 1).encode("utf-8"))
        code, output = _run_test()
        lines.append(f"塞回长量纲后跑守卫：exit={code}")
        lines.append("—— pytest 输出（尾部 8 行）——")
        lines.extend(output.strip().splitlines()[-8:])
        lines.append("判据结论 = " + ("✓ 用例红了（守卫有强度）" if (code == 1 and "fail" in output) else "✗ 用例照样绿（守卫是摆设）"))
        if not (code == 1 and "fail" in output):
            verdict = 1
    finally:
        RECIPE.write_bytes(original)

    after = hashlib.sha256(RECIPE.read_bytes()).hexdigest()
    lines.append(f"配方文件 sha256（复原后）= {after}")
    lines.append("复原复核 = " + ("✓ 逐字节相同" if after == before else "✗ 字节不同"))
    code2, _ = _run_test()
    lines.append(f"复原后跑守卫：exit={code2}（应为 0）")
    if after != before or code2 != 0:
        verdict = 1

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
