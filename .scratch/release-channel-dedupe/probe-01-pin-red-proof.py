# -*- coding: utf-8 -*-
"""真红证：把**收走前**（本工单落地之前那个提交）的三个模块喂给同一套判据
（工单 release-channel-dedupe/01）。

只读：用 `git show <base>:<path>` 取收走前的源码，不碰工作区、不改仓库文件。

**base 不能写 HEAD**（工单 01 评审整改）：本工单提交之后 HEAD 就是收走后的代码，
拿 HEAD 当"收走前"会让红证静默失效（实测：提交后重跑，② 段凭空变绿）。
缺省 base = `update.py` 的**倒数第二次**改动提交（即本次收走之前的版本），
并自校验"base 里还没有共享机制"——选错就大声失败，不产出假绿。

用法：
    python .scratch/release-channel-dedupe/probe-01-pin-red-proof.py
    python .scratch/release-channel-dedupe/probe-01-pin-red-proof.py --base <rev>
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests"))

from test_release_channel_home import (  # noqa: E402
    _ASSET_LOOKUP_FINGERPRINT,
    _SHARED_CODES,
    _SHARED_MECHANISMS,
    asset_lookup_sites,
    defined_code_literals,
    defines_function,
    imports_module,
    imports_urllib,
    version_fallback_sites,
)

FILES = {
    "update.py": "src/contest_generator/update.py",
    "full_update.py": "src/contest_generator/full_update.py",
    "materials_update.py": "src/contest_generator/materials_update.py",
}
UPDATE_PATH = "src/contest_generator/update.py"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout


def default_base() -> str:
    """收走前的最后一个提交：`update.py` 的倒数第二次改动（跳过本工单那次）。"""
    return git("log", "--skip=1", "--format=%H", "-1", "--", UPDATE_PATH).strip()


def base_source(rev: str, path: str) -> str:
    return git("show", f"{rev}:{path}")


def census(sources: dict[str, str]) -> list[str]:
    """收走前的重复普查（人读的读数，不是判据）。"""
    rows = []
    asset_defs = [n for n, s in sources.items() if re.search(r"^def _asset_url\(", s, re.M)]
    rows.append(f"  `_asset_url` 定义处：{len(asset_defs)}（{', '.join(asset_defs)}）")
    fetch_defs = [n for n, s in sources.items() if re.search(r"^def _fetch_(releases|text)\(", s, re.M)]
    rows.append(f"  `_fetch_releases` / `_fetch_text` 定义处：{len(fetch_defs)}（{', '.join(fetch_defs)}）")
    private_edges = sum(1 for n, s in sources.items() if n == "full_update.py" and "from .materials_update import" in s)
    rows.append(f"  `full_update` → `materials_update` 私有 import：{private_edges}")
    rows.append("  版本比较降级 idiom 出现次数：" + "，".join(f"{n}={version_fallback_sites(s)}" for n, s in sources.items()))
    fingerprint = "，".join(f"{n}={asset_lookup_sites(s)}" for n, s in sources.items())
    rows.append(f"  机制指纹（{_ASSET_LOOKUP_FINGERPRINT}）：{fingerprint}")
    rows.append("  直接 import urllib 的模块：" + (", ".join(n for n, s in sources.items() if imports_urllib(s)) or "（无）"))
    dup = sorted({c for n, s in sources.items() if n != "update.py" for c in defined_code_literals(s)})
    rows.append(f"  功能模块里各自定义的错误码字面量：{dup or '（无）'}")
    return rows


def violations(sources: dict[str, str]) -> list[str]:
    """同一套判据（收走前的三个模块 → 应红；当前工作树 → 应绿）。"""
    out = []
    for name in ("full_update.py", "materials_update.py"):
        src = sources[name]
        named = [n for n in _SHARED_MECHANISMS if defines_function(src, n)]
        if named:
            out.append(f"{name}: 又定义发布通道机制 {named}")
        if asset_lookup_sites(src):
            out.append(f"{name}: 自己取资产下载地址（指纹 {_ASSET_LOOKUP_FINGERPRINT}）")
        if imports_urllib(src):
            out.append(f"{name}: 直接 import urllib")
        if version_fallback_sites(src):
            out.append(f"{name}: 又写了一遍版本比较降级")
        dup_codes = defined_code_literals(src) & set(_SHARED_CODES)
        if dup_codes:
            out.append(f"{name}: 又定义共享错误码 {sorted(dup_codes)}")
    if imports_module(sources["full_update.py"], "materials_update"):
        out.append("full_update.py: import 了 materials_update")
    return out


def main() -> int:
    args = sys.argv[1:]
    base = args[args.index("--base") + 1] if "--base" in args else default_base()

    head = {name: base_source(base, path) for name, path in FILES.items()}
    now = {name: (REPO / path).read_text(encoding="utf-8") for name, path in FILES.items()}

    # base 自校验：收走前的 update.py 里不该已经有共享机制（否则 base 选错 → 假绿）
    if defines_function(head["update.py"], "asset_url"):
        print(f"✗ base {base[:8]} 里已经有 update.asset_url —— 这不是收走前的提交，换 --base")
        return 2

    print(f"== ① base={base[:8]}（收走前）的重复普查 ==")
    for row in census(head):
        print(row)

    red = violations(head)
    print(f"\n== ② 同一套判据作用在 base 上（应红）：{len(red)} 条 ==")
    for line in red:
        print("  ✗ " + line)

    green = violations(now)
    print("\n== ③ 同一套判据作用在当前工作树上（应绿）==")
    print("  （无违规）" if not green else "\n".join("  ✗ " + line for line in green))

    ok = bool(red) and not green
    print("\n" + ("RED→GREEN 成立（红证 + 绿证同源）" if ok else "异常：红或绿不符合预期"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
