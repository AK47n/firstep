# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/10 的补课反证：给**两条原先没有反证的守卫**各撤一次。

Standards 轴评审点名：02 的数据守卫（57/57 末条「未上板」）与 03 的值优先顺序守卫
此前只有"守卫在跑"的记录，没有"撤掉修复 → 用例必须红"的实测。本探针补这两条。

纪律：逐字节读写（CRLF 无关：本检出的 .py / .json 换行形态不一，锚点一律用 `\\r?\\n` 或纯片段）；
跑之前验干净性；跑完复原并复核 sha256；与测试套件不同时跑；subprocess 带 timeout。
读数落 `.scratch/hwcheck-hardening/probe-10-red.txt`。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECIPE = ROOT / "library" / "hwcheck_recipes.json"
RENDER = ROOT / "src" / "contest_generator" / "hwcheck_recipe.py"
OUT = pathlib.Path(__file__).with_name("probe-10-red.txt")

MARKER = "**未上板**：本格的结论只到"
ORDER_GUARD = ("tests/test_hwcheck_recipe.py"
               "::test_read_line_puts_the_value_before_the_source_expression")
DATA_GUARD = ("tests/test_hwcheck_recipe.py"
              "::test_every_real_recipe_cell_discloses_its_on_board_status")


def _run(node: str) -> tuple[int, str]:
    done = subprocess.run(
        [os.sys.executable, "-m", "pytest", node, "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=180,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def _leg(lines: list[str], label: str, path: pathlib.Path, inject, node: str) -> int:
    """撤一次 → 跑守卫 → 复原 → 复核。返回 0 = 这一段成立（真红 + 真复原）。"""
    original = path.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines.append(f"—— 撤「{label}」（{path.name}，sha256 {before[:12]}…）——")
    broken = inject(text)
    if broken is None:
        lines.append("✗ 前置干净性检查失败：锚点不在或形态变了。")
        return 1
    verdict = 0
    try:
        path.write_bytes(broken.encode("utf-8"))
        code, output = _run(node)
        lines.append(f"   撤掉修复后跑守卫：exit={code}")
        lines.extend("   " + line for line in output.strip().splitlines()[-4:])
        real_red = code == 1 and "fail" in output
        lines.append("   判据结论 = " + ("✓ 用例红了（守卫有强度）" if real_red else "✗ 没红（守卫是摆设）"))
        if not real_red:
            verdict = 1
    except subprocess.TimeoutExpired:
        lines.append("   ✗ 用例超时（180s）")
        verdict = 1
    finally:
        path.write_bytes(original)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    lines.append("   复原复核 = " + ("✓ 逐字节相同" if after == before else "✗ 字节不同"))
    code2, _ = _run(node)
    lines.append(f"   复原后跑守卫：exit={code2}（应为 0）")
    if after != before or code2 != 0:
        verdict = 1
    lines.append("")
    return verdict


def drop_marker(text: str) -> str | None:
    """撤掉第一格末条的「**未上板**」标记（57/57 那条守卫必须红）。"""
    if text.count(MARKER) < 1:
        return None
    return text.replace(MARKER, "本格的结论只到", 1)


def reverse_read_order(text: str) -> str | None:
    """把读数行顺序换回「横幅在前」（03 的顺序守卫必须红）。

    锚点按**文件自己的换行形态**拼（本检出的 .py 是 CRLF；写死 \\n 会让前置检查直接失败——
    这正是 probe-02 踩过的坑，见工单 10）。
    """
    eol = "\r\n" if "\r\n" in text else "\n"
    value_line = '        out.append(f"    hwcheck_report_int({item.expression});")' + eol
    # 锚点必须带**读数段独有**的那一行：`hwcheck_newline();` 那一句在框架里也有一份（出现两次），
    # 只有"来源表达式那一行 + 紧接的 newline"这对才是读数段独有的。
    source_line = ('        out.append(f"    hwcheck_report({c_string('
                   'f\' ({item.expression})\')});")')
    pair = source_line + eol + '        out.append("    hwcheck_newline();")'
    if text.count(value_line) != 1 or text.count(pair) != 1:
        return None
    without = text.replace(value_line, "", 1)
    return without.replace(pair, source_line + eol + value_line
                           + '        out.append("    hwcheck_newline();")', 1)


def main() -> int:
    lines = ["=== 工单 hwcheck-hardening/10：两条守卫的补课反证 ===", ""]
    verdict = _leg(lines, "数据守卫：撤掉一格的「未上板」标记", RECIPE, drop_marker, DATA_GUARD)
    verdict |= _leg(lines, "顺序守卫：把读数行换回「横幅在前」", RENDER, reverse_read_order, ORDER_GUARD)
    lines.append("总结论 = " + ("✓ 两条守卫都真红、都逐字节复原" if verdict == 0 else "✗ 有段落不成立"))
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
