"""不可选形态轮 · **真文件反证**（工单 disabled-forms/03）：判据⑥扩面之后，那些新判据在**盘上的
真文件**里也会响吗？

## 为什么要有它

守卫里那几条红证（`n1`–`n6`）是**内存注入**（把改过的源码文本喂给纯函数）——它们证的是
"判据函数有牙"。`light-contrast/05` 收口时立过一条规矩：**两者缺一不可**，还得有一条
"改真产品文件、跑真闸门"的反证：

    内存红证 = 判据有牙；真文件红证 = 闸门在真文件上也会响。

## 它做四条（都对 `src/contest_generator/static/index.html` 的样式块）

1. **①** 把 `opacity: .55` 放回 `.module-card.off` → 正向判据（认人面 = 登记表 `disabled` 档）；
2. **②** 把 `opacity: .5` 放回 `.pin-menu-list li.cant` → 同上；
3. **③** 把 `opacity: .65` 放回 `.param-stale` → 同上（三处目标各来一次，别只挑一处）；
4. **④** 注入一条**新的** `.tmp-probe.off { opacity: .4; }`（不在册、类名词法命中）→ **反向判据**
   （"嫌疑规则必须登记"）——这一条是本轮新加的闸，红证里也得有它。

每一步都在 `finally` 里按**原始字节**复原，并逐字节校验 sha256 —— 真文件不留痕。

跑法（仓库根；**它跑的时候别同时跑别的门禁**）：

    python .scratch\\disabled-forms\\probe-03-real-file-red-proof.py
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run_gate() -> tuple[int, str]:
    """跑前端门禁（只这一道），返回（退出码, 输出）。"""
    proc = subprocess.run(["node", "--test", "tests/js/*.test.mjs"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", shell=False)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def one(title: str, inject, want: list[str], sel: str) -> bool:
    """注入 → 跑门禁 → 复原 → 校验。返回这条反证有没有成立。"""
    original = PAGE.read_bytes()
    before = digest(original)
    text = original.decode("utf-8")
    patched = inject(text)
    assert patched != text, f"[{title}] 注入没生效——锚点变了，这条反证会静默空转"
    try:
        PAGE.write_bytes(patched.encode("utf-8"))
        code, out = run_gate()
        hits = [w for w in want if w in out]
        named = sel in out
    finally:
        PAGE.write_bytes(original)
    after = digest(PAGE.read_bytes())
    ok = code != 0 and len(hits) == len(want) and named and after == before
    print(f"\n{'=' * 96}\n## {title}\n")
    print(f"  门禁退出码 {code}（要 ≠ 0）　文案命中 {hits}（要 {len(want)}/{len(want)}）"
          f"　点名的选择器「{sel}」：{'是' if named else '否'}")
    print(f"  复原后 sha256 与注入前{'一致 ✅' if after == before else '不一致 ❌'}（{after[:16]}…）")
    for line in out.splitlines():
        if any(w in line for w in want):
            print("  闸门原文：" + line.strip()[:220])
    print(f"  —— 这条反证{'**成立**' if ok else '**不成立**'}")
    return ok


def main() -> int:
    print("=" * 96)
    print("不可选形态轮 · 真文件反证（判据⑥扩面：闸门在盘上的真文件里也会响）")
    print(f"目标：{PAGE.relative_to(ROOT)}；注入 → 跑前端门禁 → 原字节复原 → sha256 校验")
    print("=" * 96)

    forms = [
        ("① `.module-card.off` 放回 `opacity: .55`（登记表 `disabled` 档）",
         "  .module-card.off { background: var(--panel); border-style: dashed; cursor: not-allowed; }",
         lambda s: s.replace("  .module-card.off { background: var(--panel); border-style: dashed; cursor: not-allowed; }",
                             "  .module-card.off { opacity: .55; background: var(--panel); border-style: dashed; cursor: not-allowed; }", 1),
         ".module-card.off"),
        ("② `.pin-menu-list li.cant` 放回 `opacity: .5`",
         "  .pin-menu-list li.cant { background: var(--panel-2); color: var(--muted); cursor: not-allowed; }",
         lambda s: s.replace("  .pin-menu-list li.cant { background: var(--panel-2); color: var(--muted); cursor: not-allowed; }",
                             "  .pin-menu-list li.cant { opacity: .5; background: var(--panel-2); color: var(--muted); cursor: not-allowed; }", 1),
         ".pin-menu-list li.cant"),
        ("③ `.param-stale` 放回 `opacity: .65`",
         "  .param-stale { outline: 1px dashed var(--warn-border); }",
         lambda s: s.replace("  .param-stale { outline: 1px dashed var(--warn-border); }",
                             "  .param-stale { opacity: .65; outline: 1px dashed var(--warn-border); }", 1),
         ".param-stale"),
    ]
    results = [one(t, inj, ["不可选形态不许用 opacity 表达"], sel) for t, _a, inj, sel in forms]
    results.append(one(
        "④ 注入一条**新的** `.tmp-probe.off { opacity: .4 }`（不在册、词法命中）→ 反向判据",
        lambda s: s.replace("<style>", "<style>\n  .tmp-probe.off { opacity: .4; }", 1),
        ["没有登记", "把它登记进 CONTRAST_DISABLED_FORMS"], ".tmp-probe.off"))

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
