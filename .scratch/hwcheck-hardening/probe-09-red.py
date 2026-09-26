# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/09 的判据强度反证：把三处同源里的**任意一处**改掉 → 对应用例必须红。

三条腿各撤一次（每次都逐字节复原再撤下一条）：
  ① 页面那句（`fx/hwcheck.js`）——判据 `test_unverified_sentence_is_verbatim_the_same_on_page_and_readme`
  ② README 那句——同一条判据
  ③ 某一格配方的末条子句（`servo × stm32`）——判据 `test_every_real_recipe_note_marks_unverified_with_the_same_clause`

纪律：逐字节读写（**CRLF 无关**：本检出是 CRLF，锚点里用 `\\r?\\n` 或纯片段）；
跑之前验干净性；跑完复原并复核 sha256；与测试套件不同时跑。
读数落 `.scratch/hwcheck-hardening/probe-09-red.txt`。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
FX = ROOT / "src" / "contest_generator" / "static" / "js" / "fx" / "hwcheck.js"
README = ROOT / "README.md"
RECIPE = ROOT / "library" / "hwcheck_recipes.json"
OUT = pathlib.Path(__file__).with_name("probe-09-red.txt")

SENTENCE = "本栏目的配方与探测小节尚未在真板上验证过：现有证据只到「能生成 + 能编译」这一步。"
CLAUSE = "真机上板验证还没做"
CASES = (
    ("页面那句", FX, SENTENCE, "本栏目这一批检测还没在真板上验证过：现有证据只到「能生成 + 能编译」这一步。",
     "tests/test_hwcheck.py::test_unverified_sentence_is_verbatim_the_same_on_page_and_readme"),
    ("README 那句", README, SENTENCE, "这一栏的检测还没上过真板：现有证据只到「能生成 + 能编译」这一步。",
     "tests/test_hwcheck.py::test_unverified_sentence_is_verbatim_the_same_on_page_and_readme"),
    ("配方末条子句", RECIPE, CLAUSE, "上板验证留待以后", 
     "tests/test_hwcheck_recipe.py::test_every_real_recipe_note_marks_unverified_with_the_same_clause"),
)


def _run_test(node: str) -> tuple[int, str]:
    done = subprocess.run(
        [os.sys.executable, "-m", "pytest", node, "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=180,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def main() -> int:
    lines: list[str] = []
    verdict = 0
    for label, path, needle, broken_text, node in CASES:
        original = path.read_bytes()
        before = hashlib.sha256(original).hexdigest()
        text = original.decode("utf-8")
        lines.append(f"—— 撤「{label}」（{path.name}，sha256 {before[:12]}…）——")

        count = text.count(needle)
        # 配方那条只撤**第一处**（servo × stm32）：出现多次是正常的（57 格里都在用）
        if count == 0:
            lines.append(f"✗ 前置干净性检查失败：锚点「{needle[:24]}…」不在文件里。")
            verdict = 1
            continue
        try:
            replaced = text.replace(needle, broken_text, 1)
            path.write_bytes(replaced.encode("utf-8"))
            code, output = _run_test(node)
            lines.append(f"   注入后跑用例：exit={code}（锚点在文件里出现 {count} 次，只改第一处）")
            lines.extend("   " + line for line in output.strip().splitlines()[-4:])
            # 判据要的是"**用例真的失败**"：退出码 1 且输出里有 failed（收集错误 exit 2/5 不算通过）
            real_red = code == 1 and "failed" in output
            lines.append("   判据结论 = " + ("✓ 用例红了（守卫有强度）" if real_red else "✗ 没红（守卫是摆设）"))
            if not real_red:
                verdict = 1
        except subprocess.TimeoutExpired:
            lines.append("   ✗ 用例超时（180s）——探针不留脏：下面照常复原")
            verdict = 1
        finally:
            path.write_bytes(original)

        after = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append("   复原复核 = " + ("✓ 逐字节相同" if after == before else "✗ 字节不同"))
        code2, _ = _run_test(node)
        lines.append(f"   复原后跑用例：exit={code2}（应为 0）")
        if after != before or code2 != 0:
            verdict = 1
        lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
