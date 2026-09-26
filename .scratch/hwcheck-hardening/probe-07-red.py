# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/07 的判据强度反证：把"失败时清掉旧 main.c"撤掉 → 结构钉必须红。

撤的是 ui 失败分支里那一行 `hwcheckUI.preview = "";`（工单 07 的核心修复：
失败之后留着的那份 main.c 属于**上一组器件**，照着它编译烧录就是烧错东西）。

判据 = `tests/js/hwcheck.test.mjs::ui 的三处清预览…`（前端门禁里）。
端到端行为另有一条真浏览器用例（`tests/browser/hwcheck.spec.mjs` 的"预览失败"那条，实测 22/22 绿）。

纪律：逐字节读写；跑之前验干净性；跑完复原并复核 sha256；与测试套件不同时跑。
读数落 `.scratch/hwcheck-hardening/probe-07-red.txt`。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
UI = ROOT / "src" / "contest_generator" / "static" / "js" / "ui" / "hwcheck.js"
OUT = pathlib.Path(__file__).with_name("probe-07-red.txt")
CMD = ["node", "--test", "tests/js/hwcheck.test.mjs"]
# 失败分支里那一行（**逐字节无关换行**：这个检出是 CRLF，用 \r?\n 匹配）
# 唯一性靠 previewError 那一行收尾（只有失败分支有它）。
NEEDLE = re.compile(
    r'      hwcheckUI\.preview = "";\r?\n'
    r'(      hwcheckUI\.outputHint = "";\r?\n'
    r'      hwcheckUI\.previewError = e && e\.message)'
)


def _run_js() -> tuple[int, str]:
    done = subprocess.run(
        CMD, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=180,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}, shell=True,
    )
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def main() -> int:
    lines: list[str] = []
    original = UI.read_bytes()
    before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    lines.append(f"ui/hwcheck.js sha256（跑之前）= {before}")

    if len(NEEDLE.findall(text)) != 1:
        lines.append(
            f"✗ 前置干净性检查失败：失败分支不清 main.c，或锚点不唯一"
            f"（{len(NEEDLE.findall(text))} 处）。"
        )
        OUT.write_text("\n".join(lines), encoding="utf-8")
        return 2
    lines.append("✓ 前置干净性检查：失败分支确实清了 main.c（唯一一处）")

    verdict = 0
    try:
        # 撤掉清预览这一行（保留 outputHint 的清空，模拟"只回退这一半修复"）
        broken = NEEDLE.sub(lambda m: m.group(1), text, count=1)
        UI.write_bytes(broken.encode("utf-8"))
        code, output = _run_js()
        lines.append(f"撤掉清预览后跑前端用例：exit={code}")
        lines.append("—— node --test 输出（尾部 10 行）——")
        lines.extend(output.strip().splitlines()[-10:])
        lines.append("判据结论 = " + ("✓ 用例红了（结构钉有强度）" if (code == 1 and "fail" in output) else "✗ 用例照样绿（守卫是摆设）"))
        if not (code == 1 and "fail" in output):
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
