# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/06 的判据强度反证：停用新形态识别 → 用例必须红。

做法：把 `_TOOLCHAIN_DIAG_RE` 换成一个**永不命中**的正则（`(?!)`），模拟"这条识别被撤掉"。
判据 = `tests/test_fix_errors.py::test_parse_linker_form_diagnostic_without_file_reference`。

纪律：逐字节读写；跑之前验干净性；跑完复原并复核 sha256；与测试套件不同时跑。
读数落 `.scratch/hwcheck-hardening/probe-06-red.txt`。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "contest_generator" / "fix_errors.py"
OUT = pathlib.Path(__file__).with_name("probe-06-red.txt")
TEST = ("tests/test_fix_errors.py"
        "::test_parse_linker_form_diagnostic_without_file_reference")
NEEDLE = 'r"^(?P<level>warning|error)\\s+#(?P<code>\\d+)-[A-Za-z]:\\s*(?P<text>\\S.*)$",'


def _run_test() -> tuple[int, str]:
    done = subprocess.run(
        [os.sys.executable, "-m", "pytest", TEST, "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def main() -> int:
    lines: list[str] = []
    original = SRC.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines.append(f"fix_errors.py sha256（跑之前）= {before}")

    if NEEDLE not in text:
        lines.append("✗ 找不到 `_TOOLCHAIN_DIAG_RE` 的正则字面量——锚点要跟着实现更新。")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2
    if text.count(NEEDLE) != 1:
        lines.append(f"✗ 锚点不唯一（{text.count(NEEDLE)} 次）。")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2
    lines.append("✓ 前置干净性检查：新形态的识别在现场且唯一")

    verdict = 0
    try:
        broken = text.replace(NEEDLE, 'r"(?!)",', 1)
        SRC.write_bytes(broken.encode("utf-8"))
        code, output = _run_test()
        lines.append(f"停用识别后跑用例：exit={code}")
        lines.append("—— pytest 输出（尾部 8 行）——")
        lines.extend(output.strip().splitlines()[-8:])
        lines.append("判据结论 = " + ("✓ 用例红了（守卫有强度）" if code != 0 else "✗ 用例照样绿（守卫是摆设）"))
        if code == 0:
            verdict = 1
    finally:
        SRC.write_bytes(original)

    after = hashlib.sha256(SRC.read_bytes()).hexdigest()
    lines.append(f"fix_errors.py sha256（复原后）= {after}")
    lines.append("复原复核 = " + ("✓ 逐字节相同" if after == before else "✗ 字节不同"))
    code2, _ = _run_test()
    lines.append(f"复原后跑用例：exit={code2}（应为 0）")
    if after != before or code2 != 0:
        verdict = 1

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
