"""contrast-residue 轮 · 10 号探针：**收口前的三发真文件反证**（工单 06 的双轴评审整改）。

三发都改**真文件**（产品面或守卫），跑门禁核红，再逐字节复原（sha256 前后一致）：

1. **`opacity` 全量登记**（工单 04 的判据②）：往一条**没登记**的规则里插 `opacity: .5`
   ⇒ 期望红在「这条 …的活规则没有登记」；
2. **`var(--fg)` 笔误**（工单 02 的腿⑩）：把 `.pin-subtitle` 的 `color: var(--text)`
   改回 `var(--fg)` ⇒ 期望**两条腿各红各的**（腿⑩ + 令牌面）；
3. **第二个 `:root` 块**（工单 01 的解析面）：把第二个 `:root` 改名 ⇒ 期望红在页面冻结那条。

跑法（仓库根）：`python .scratch\\contrast-residue\\probe-10-closeout-red-proofs.py`
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"

#: 三个注入：`(标签, 文件, 查找串, 替换串, 期望出现在门禁输出里的串)`
CASES = [
    ("① opacity 没登记（判据②全量口径）", PAGE,
     "  .pin-intro { font-size: var(--fs-body);",
     "  .pin-intro { opacity: .5; font-size: var(--fs-body);",
     "没有登记"),
    ("② var(--fg) 笔误（腿⑩ + 令牌面）", PAGE,
     "letter-spacing: .3px; color: var(--text); }",
     "letter-spacing: .3px; color: var(--fg); }",
     "无兜底的 var(--fg)"),
    ("③ 第二个 `:root` 改名（解析面页面冻结）", PAGE,
     "\n  :root {", "\n  :root-x {",
     "只解析到 1 个 `:root` 块"),
]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest().upper()


def run_guard() -> str:
    p = subprocess.run(["node", "--test", "tests/js/css-tokens.test.mjs"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (p.stdout or "") + (p.stderr or "")


def main() -> None:
    fails = 0
    for label, path, needle, broken, expect in CASES:
        mine = path.read_bytes()
        text = mine.decode("utf-8")
        if needle not in text:
            print(f"{label}：**锚点不在盘上**（{needle[:40]!r}）——这一发无从做起")
            fails += 1
            continue
        if label.startswith("③"):
            at = text.index(needle)                          # 第一处
            at = text.index(needle, at + 1)                  # 第二处（页面里有两个 `:root`）
            new = text[:at] + broken + text[at + len(needle):]
        else:
            new = text.replace(needle, broken, 1)
        print("=" * 88)
        print(f"{label}")
        print("=" * 88)
        print(f"  注入前 sha256 = {sha(mine)}")
        try:
            path.write_bytes(new.encode("utf-8"))
            out = run_guard()
            red = expect in out
            print(f"  门禁：{'✅ 按预期红' if red else '❌ 没红（这一发在空转）'}——期望串 {expect!r}")
            if not red:
                fails += 1
                for line in out.splitlines():
                    if "没有登记" in line or "无兜底的" in line or "只解析到" in line:
                        print("    " + line.strip()[:120])
        finally:
            path.write_bytes(mine)
            back = sha(path.read_bytes())
            ok = back == sha(mine)
            print(f"  复原 sha256 = {back}　{'✅ 逐字节一致' if ok else '❌ 不一致！'}")
            if not ok:
                fails += 1
        # 复原之后门禁必须转绿（证明红是注入带来的，不是树本来就红）
        out = run_guard()
        green = "ℹ fail 0" in out
        print(f"  复原后门禁：{'✅ 绿' if green else '❌ 仍红——树本来就有问题'}")
        if not green:
            fails += 1
    print()
    print(f"三发反证：{'✅ 全部按预期' if not fails else f'❌ {fails} 处不符'}")


if __name__ == "__main__":
    main()
