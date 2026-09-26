# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/05 的判据强度反证：把补上的池位撤掉 → "全勾满"守卫必须红。

撤的是本单给每条 `console.candidates` **纯追加**的那 6 个没人用过的池位（`4 5 6 7 8 9`）。
判据 = `tests/test_hwcheck_console.py::test_the_whole_specialized_set_of_one_platform_builds_one_console_table`
（两平台各一条）。

纪律：逐字节读写（LF 保持）；跑之前验干净性；跑完复原并复核 sha256；与测试套件不同时跑。
读数落 `.scratch/hwcheck-hardening/probe-05-red.txt`。
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECIPE = ROOT / "library" / "hwcheck_recipes.json"
OUT = pathlib.Path(__file__).with_name("probe-05-red.txt")
TEST = ("tests/test_hwcheck_console.py"
        "::test_the_whole_specialized_set_of_one_platform_builds_one_console_table")
ADD = ("4", "5", "6", "7", "8", "9")
BLOCK = re.compile(r'("candidates": \[)(?P<body>[^\]]*?)(?P<closing>\n(?P<indent>[ \t]*)\])')


def _run_test() -> tuple[int, str]:
    done = subprocess.run(
        [os.sys.executable, "-m", "pytest", TEST, "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def strip_pool(text: str) -> tuple[str, int]:
    """把追加过的池位从每个 candidates 数组里摘掉（已有候选一个不动）。"""
    removed = 0

    def shrink(match: re.Match[str]) -> str:
        nonlocal removed
        body = match.group("body")
        lines = body.split("\n")
        kept: list[str] = []
        for line in lines:
            stripped = line.strip().rstrip(",")
            if stripped and json.loads(stripped) in ADD:
                removed += 1
                continue
            kept.append(line)
        if kept:
            kept[-1] = kept[-1].rstrip().rstrip(",")
        return match.group(1) + "\n".join(kept) + match.group("closing")

    return BLOCK.sub(shrink, text), removed


def main() -> int:
    lines: list[str] = []
    original = RECIPE.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines.append(f"配方文件 sha256（跑之前）= {before}")

    if text.count('"4"') == 0:
        lines.append("✗ 前置干净性检查失败：池位 `4` 本来就不在候选里，反证没有意义。")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2
    lines.append("✓ 前置干净性检查：追加过的池位在候选面里")

    verdict = 0
    try:
        stripped, removed = strip_pool(text)
        lines.append(f"撤掉 {removed} 处追加的池位（应当 = 57 格 × 6 个字符）")
        RECIPE.write_bytes(stripped.encode("utf-8"))
        code, output = _run_test()
        lines.append(f'撤掉池位后跑「全勾满」守卫：exit={code}')
        lines.append("—— pytest 输出（尾部 8 行）——")
        lines.extend(output.strip().splitlines()[-8:])
        lines.append("判据结论 = " + ("✓ 用例红了（守卫有强度）" if code != 0 else "✗ 用例照样绿（守卫是摆设）"))
        if code == 0:
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
