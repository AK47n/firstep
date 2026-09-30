"""代码配色族轮 · **真文件反证**（工单 code-contrast/03）：禁用态那条结构判据在**盘上的真文件**里
也会响吗？

## 为什么要有它

守卫里那三条禁用态红证是**内存注入**（把改过的源码文本喂给纯函数）——它们证的是"判据函数有牙"。
`light-contrast/05` 收口时立过一条规矩：**两者缺一不可**，还得有一条"改真产品文件、跑真闸门"的反证：

    内存红证 = 判据有牙；真文件红证 = 闸门在真文件上也会响。

本脚本按那个先例做两条（对 `src/contest_generator/static/index.html` 的样式块）：

1. **① `opacity: .45` 放回禁用态** → 前端门禁必须判红，且文案里点到"禁用态不许用 opacity 表达"；
2. **③ `.disabled` 类形态**（注入一条假规则 `.tmp-probe.disabled { opacity: .5; }`）→ 同样判红。

每一步都在 `finally` 里按**原始字节**复原，并逐字节校验 sha256 —— 真文件不留痕。

跑法（仓库根；**它跑的时候别同时跑别的门禁**）：

    python .scratch\\code-contrast\\probe-04-real-file-red-proof.py
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"

#: 判红的期望片段（守卫那条判据的文案）；出现即算这一条反证成立。
WANT = "禁用态不许用 opacity 表达"


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run_gate() -> tuple[int, str]:
    """跑前端门禁（只这一道），返回（退出码, 输出）。"""
    proc = subprocess.run(["node", "--test", "tests/js/*.test.mjs"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", shell=False)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def one(title: str, inject) -> bool:
    """注入 → 跑门禁 → 复原 → 校验。返回这条反证有没有成立。"""
    original = PAGE.read_bytes()
    before = digest(original)
    text = original.decode("utf-8")
    patched = inject(text)
    assert patched != text, f"[{title}] 注入没生效——锚点变了，这条反证会静默空转"
    try:
        PAGE.write_bytes(patched.encode("utf-8"))
        code, out = run_gate()
        hit = WANT in out
    finally:
        PAGE.write_bytes(original)
    after = digest(PAGE.read_bytes())
    ok = code != 0 and hit and after == before
    print(f"\n{'=' * 96}\n## {title}\n")
    print(f"  门禁退出码 {code}（要 ≠ 0）　文案命中「{WANT}」：{'是' if hit else '否'}")
    print(f"  复原后 sha256 与注入前{'一致 ✅' if after == before else '不一致 ❌'}（{after[:16]}…）")
    for line in out.splitlines():
        if WANT in line:
            print("  闸门原文：" + line.strip()[:200])
    print(f"  —— 这条反证{'**成立**' if ok else '**不成立**'}")
    return ok


def main() -> int:
    print("=" * 96)
    print("代码配色族轮 · 真文件反证（禁用态：闸门在盘上的真文件里也会响）")
    print(f"目标：{PAGE.relative_to(ROOT)}；注入 → 跑前端门禁 → 原字节复原 → sha256 校验")
    print("=" * 96)

    def inject_opacity(text: str) -> str:
        anchor = "box-shadow: none; cursor: not-allowed; }"
        return text.replace(anchor, "box-shadow: none; opacity: .45; cursor: not-allowed; }", 1)

    def inject_class_rule(text: str) -> str:
        return text.replace("<style>", "<style>\n  .tmp-probe.disabled { opacity: .5; }", 1)

    results = [
        one("① 把 `opacity: .45` 放回禁用态（`:disabled` 那一半）", inject_opacity),
        one("③ 注入一条 `.disabled` 类形态的假规则（类那一半）", inject_class_rule),
    ]
    print(f"\n{'=' * 96}")
    print(f"合计 **{sum(results)}/{len(results)}** 条真文件反证成立"
          + ("——闸门在真文件上也会响" if all(results) else "——有反证没成立，别当闸门有效"))
    print("=" * 96)
    return 0 if all(results) else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
