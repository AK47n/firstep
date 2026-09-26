# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/01 的判据强度反证：把旧指令塞回配方 → 新守卫必须红。

纪律（照本仓库既有先例）：
* 逐字节读写（`rb` / `wb`），不让文本模式把 LF 归一成 CRLF；
* 跑之前先验"干净性"（那条措辞当前不在文件里），跑完复原并**复核 sha256 相同**；
* 与测试套件**不同时跑**（探针会真改库内文件）。

读数落 `.scratch/hwcheck-hardening/probe-01-red.txt`。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECIPE = ROOT / "library" / "hwcheck_recipes.json"
OUT = pathlib.Path(__file__).with_name("probe-01-red.txt")

# 注入的旧形态：就是工单 01 修掉的那句（只取判据命中的那半句即可）
INJECT = "⚠ **上板前先把 main.c 里 SYSCFG_DL_init() 那一行的注释去掉**"
# 注入锚点：该格 note 的 key_init 那一条（行首唯一）
ANCHOR = '"key_init() 在本平台是**空实现**'
TEST = "tests/test_hwcheck_recipe.py::test_real_recipe_file_never_asks_students_to_edit_generated_code"


def _run_test() -> tuple[int, str]:
    done = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-q"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def main() -> int:
    lines: list[str] = []
    original = RECIPE.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines.append(f"配方文件 sha256（跑之前）= {before}")
    lines.append(f"换行形态 = {'CRLF' if b'\\r\\n' in original else 'LF'}，字节数 = {len(original)}")

    if INJECT in text:
        lines.append("✗ 前置干净性检查失败：旧形态本来就在文件里，这次反证没有意义。")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2
    lines.append("✓ 前置干净性检查：旧形态当前不在配方文件里")

    if ANCHOR not in text:
        lines.append(f"✗ 注入锚点找不到（{ANCHOR}）——配方被改过，探针要跟着更新。")
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2

    try:
        # 注入成一**合法 JSON** 的一行（真换行，不是字面 \n）：这样"用例红"只可能来自
        # 措辞判据，不可能来自 JSON 解析失败——红证才说明守卫真有强度。
        injected = text.replace(ANCHOR, '"' + INJECT + '",\n          ' + ANCHOR, 1)
        RECIPE.write_bytes(injected.encode("utf-8"))
        code, output = _run_test()
        lines.append(f"注入后跑守卫用例：exit={code}")
        lines.append("—— pytest 输出（尾部 12 行）——")
        lines.extend(output.strip().splitlines()[-12:])
        lines.append("判据结论 = " + ("✓ 用例红了（守卫有强度）" if code != 0 else "✗ 用例照样绿（守卫是摆设）"))
        verdict = 0 if code != 0 else 1
    finally:
        RECIPE.write_bytes(original)

    after = hashlib.sha256(RECIPE.read_bytes()).hexdigest()
    lines.append(f"配方文件 sha256（复原后）= {after}")
    lines.append("复原复核 = " + ("✓ 逐字节相同" if after == before else "✗ 字节不同（文件被改动）"))
    code2, _ = _run_test()
    lines.append(f"复原后跑守卫用例：exit={code2}（应为 0）")
    if after != before or code2 != 0:
        verdict = 1

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return verdict


if __name__ == "__main__":
    raise SystemExit(main())
