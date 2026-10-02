# -*- coding: utf-8 -*-
"""引脚配色 04 单 · **真文件反证**：删掉亮色块里一个色件 → 腿⑪ 当场红 → 复原（sha256 一致）。

注入的就是 `--pin-fixed-pad` 那次的**历史原样**：亮色块只覆盖焊盘的一部分，
其余沿用暗色值——`contrast-residue/03` 之前盘上真是这样，而当时**没有任何判据会红**。

跑法：

    python .scratch\\pin-type-contrast\\probe-06-red-proof.py
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "src" / "contest_generator" / "static" / "index.html"
GUARD = "tests/js/css-tokens.test.mjs"

#: 注入：把亮色块里 `--pin-fixed-pad` 这一条定义删掉（`--pin-pad` / `--pin-pcb` 留着）
INJECT_RE = re.compile(r"\s*--pin-fixed-pad:\s*#afb8c1;")


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
    if not INJECT_RE.search(text):
        raise SystemExit("注入锚点不在盘上（亮色块的 `--pin-fixed-pad`）——本脚本要跟着产品面改")

    out: list[str] = []
    out.append("=" * 96)
    out.append("引脚配色 04 · 真文件反证：亮色覆盖缺一个色件 → 腿⑪ 判红")
    out.append(f"靶子 = {TARGET.relative_to(REPO)}；sha256（改前）= {before_sha}")
    out.append("=" * 96)

    print("[1/3] 基线：跑一次门禁（应当是绿的）…")
    code, log = run_guard()
    out.append(f"① 基线门禁：exit={code}（期望 0）")
    if code != 0:
        out.append(log[-2000:])
        print("\n".join(out))
        return 1

    print("[2/3] 注入（删掉亮色块里的 `--pin-fixed-pad`）…")
    TARGET.write_text(INJECT_RE.sub("", text, count=1), encoding="utf-8", newline="")
    code, log = run_guard()
    hit = "没有成套覆盖" in log and "--pin-fixed-pad" in log
    out.append(f"② 注入后门禁：exit={code}（期望非 0）；命中腿⑪ = {hit}")
    for line in log.splitlines():
        if "没有成套覆盖" in line:
            out.append(f"    {line.strip()[:170]}")
    if code == 0 or not hit:
        out.append("**反证失败**：删掉一个色件，门禁却没红（或红在别处）——腿⑪ 没看着这个面")
        TARGET.write_bytes(original)
        out.append(f"（已复原；sha256 = {sha256(TARGET)}）")
        print("\n".join(out))
        return 1

    print("[3/3] 复原并复核 …")
    TARGET.write_bytes(original)
    after_sha = sha256(TARGET)
    code2, _log2 = run_guard()
    out.append(f"③ 复原：sha256 = {after_sha}（与改前一致 = {after_sha == before_sha}）；"
               f"门禁 exit={code2}（期望 0）")
    ok = after_sha == before_sha and code2 == 0
    out.append(f"判定：{'✅ 反证成立（红→复原→绿，字节一致）' if ok else '⚠ 复核没过'}")
    body = "\n".join(out)
    dest = Path(__file__).with_name("probe-06-red-proof.txt")
    dest.write_text(body + "\n", encoding="utf-8")
    print(body)
    print(f"\n[落盘] {dest}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
