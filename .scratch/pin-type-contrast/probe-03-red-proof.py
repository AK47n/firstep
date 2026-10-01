# -*- coding: utf-8 -*-
"""引脚配色 02 单 · **真文件反证**：把取色改回内联模板串 → 腿⑨ 正向判据当场红 → 复原（sha256 一致）。

## 为什么要有它（不是重复劳动）

守卫文件末尾那条**合成红证**喂的是内存里的假源（`[["ui/whatever.js", '…']]`）——它证明"判据函数
认得这种坏法"，但**不证明"盘上这个文件真被它看着"**。本仓的先例（`light-contrast` 轮、
`contrast-residue/02`）是两步都要：合成红证 + **真文件注入**。

这一发注入的是**这一族原来的写法**（`style="color:${st[0]};background:${st[1]};border:1px solid ${st[0]}"`），
也就是"补丁被回滚"的那种坏法；跑的是**真正的前端门禁**（`node --test tests/js/css-tokens.test.mjs`）。

跑法：

    python .scratch\\pin-type-contrast\\probe-03-red-proof.py
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "src" / "contest_generator" / "static" / "js" / "ui" / "generate-pins.js"
GUARD = "tests/js/css-tokens.test.mjs"

#: 注入点：02 单把这一行改成了"挂属性"；改回旧的内联模板串就是"补丁被回滚"。
INJECT_ANCHOR = '<span class="role-type"${famAttr}>${esc(r.decl.type)}</span>'
INJECTED = ('<span class="role-type" style="color:${st[0]};background:${st[1]};'
            'border:1px solid ${st[0]}">${esc(r.decl.type)}</span>')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_guard() -> tuple[int, str]:
    p = subprocess.run(["node", "--test", GUARD], cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    original = TARGET.read_bytes()
    before_sha = sha256(TARGET)
    text = original.decode("utf-8")
    if INJECT_ANCHOR not in text:
        raise SystemExit(f"注入锚点不在盘上（{INJECT_ANCHOR}）——本脚本要跟着产品面改")
    if text.count(INJECT_ANCHOR) < 1:
        raise SystemExit("注入锚点一处都没命中")

    out: list[str] = []
    out.append("=" * 96)
    out.append("引脚配色 02 · 真文件反证：内联模板取色 → 腿⑨ 正向判据")
    out.append(f"靶子 = {TARGET.relative_to(REPO)}；sha256（改前）= {before_sha}")
    out.append("=" * 96)

    print(f"[1/3] 基线：跑一次门禁（应当是绿的）…")
    code, log = run_guard()
    out.append(f"① 基线门禁：exit={code}（期望 0）")
    if code != 0:
        out.append(log[-2000:])
        print("\n".join(out))
        return 1

    print(f"[2/3] 注入（把第一处 `role-type` 改回内联模板串）…")
    TARGET.write_text(text.replace(INJECT_ANCHOR, INJECTED, 1), encoding="utf-8", newline="")
    code, log = run_guard()
    hit = "内联 style 里用模板变量拼取色" in log
    out.append(f"② 注入后门禁：exit={code}（期望非 0）；命中新判据的报错 = {hit}")
    for line in log.splitlines():
        if "模板变量拼取色" in line:
            out.append(f"    {line.strip()[:160]}")
    if code == 0 or not hit:
        out.append("**反证失败**：注入了坏写法，门禁却没红（或红在别处）——判据没看着这个文件")
        TARGET.write_bytes(original)
        out.append(f"（已复原；sha256 = {sha256(TARGET)}）")
        print("\n".join(out))
        return 1

    print(f"[3/3] 复原并复核 …")
    TARGET.write_bytes(original)
    after_sha = sha256(TARGET)
    code2, log2 = run_guard()
    out.append(f"③ 复原：sha256 = {after_sha}（与改前一致 = {after_sha == before_sha}）；"
               f"门禁 exit={code2}（期望 0）")
    ok = after_sha == before_sha and code2 == 0
    out.append(f"判定：{'✅ 反证成立（红→复原→绿，字节一致）' if ok else '⚠ 复核没过'}")
    body = "\n".join(out)
    dest = Path(__file__).with_name("probe-03-red-proof.txt")
    dest.write_text(body + "\n", encoding="utf-8")
    print(body)
    print(f"\n[落盘] {dest}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
