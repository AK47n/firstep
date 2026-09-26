# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/03 的判据强度反证：把「分屏显示」那句塞回去 → 口径守卫必须红。

塞的是 `OUTPUT_HINT_OLED` 的旧话术（产品里学生看得到的那句）。判据 = 
`tests/test_hwcheck.py::test_oled_copy_never_promises_more_than_the_screen_can_do`。

纪律：逐字节读写；跑之前验干净性；跑完复原并复核 sha256；与测试套件不同时跑。
读数落 `.scratch/hwcheck-hardening/probe-03-red.txt`。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "contest_generator" / "hwcheck.py"
OUT = pathlib.Path(__file__).with_name("probe-03-red.txt")
TEST = "tests/test_hwcheck.py::test_oled_copy_never_promises_more_than_the_screen_can_do"
# 旧句（工单 03 删掉的那句）挂在当前 OUTPUT_HINT_OLED 的定义之后
OLD = 'OUTPUT_HINT_OLED = "输出通道：只有 OLED 屏。结果分屏显示在屏幕上，不接串口也能看。"\n'


def _run_test() -> tuple[int, str]:
    done = subprocess.run(
        [os.sys.executable, "-m", "pytest", TEST, "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=180,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def main() -> int:
    lines: list[str] = []
    original = SRC.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines.append(f"hwcheck.py sha256（跑之前）= {before}")

    if "分屏" in text.split("OUTPUT_HINT_SERIAL_OLED")[0] and OLD in text:
        lines.append("✗ 前置干净性检查失败：旧句本来就在，这次反证没有意义。")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2
    if "def render_output_hint(" not in text:
        lines.append("✗ 找不到 render_output_hint，探针锚点要更新。")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2
    lines.append("✓ 前置干净性检查：旧话术当前不在产品文案里")

    verdict = 0
    try:
        # 在 render_output_hint 定义之前插入一个**覆盖定义**（后定义者胜），模拟"那句话悄悄回来"
        injected = text.replace("def render_output_hint(", OLD + "\n\ndef render_output_hint(", 1)
        SRC.write_bytes(injected.encode("utf-8"))
        code, output = _run_test()
        lines.append(f"塞回旧话术后跑口径守卫：exit={code}")
        lines.append("—— pytest 输出（尾部 8 行）——")
        lines.extend(output.strip().splitlines()[-8:])
        lines.append("判据结论 = " + ("✓ 用例红了（守卫有强度）" if (code == 1 and "fail" in output) else "✗ 用例照样绿（守卫是摆设）"))
        if not (code == 1 and "fail" in output):
            verdict = 1
    finally:
        SRC.write_bytes(original)

    after = hashlib.sha256(SRC.read_bytes()).hexdigest()
    lines.append(f"hwcheck.py sha256（复原后）= {after}")
    lines.append("复原复核 = " + ("✓ 逐字节相同" if after == before else "✗ 字节不同"))
    code2, _ = _run_test()
    lines.append(f"复原后跑口径守卫：exit={code2}（应为 0）")
    if after != before or code2 != 0:
        verdict = 1

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
