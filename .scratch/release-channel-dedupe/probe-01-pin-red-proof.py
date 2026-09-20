# -*- coding: utf-8 -*-
"""真红证：把**收走前**（HEAD 版）的三个模块喂给同一套判据（工单 release-channel-dedupe/01）。

只读：用 `git show HEAD:<path>` 取收走前的源码，不碰工作区、不改仓库文件。
输出三段：① HEAD 上的重复普查（当时到底抄了几份）② 同一套判据在 HEAD 上报红
③ 当前工作树上同一套判据报绿——红绿同源，守卫不是摆设。

用法：python .scratch/release-channel-dedupe/probe-01-pin-red-proof.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests"))

from test_release_channel_home import (  # noqa: E402
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


def head_source(path: str) -> str:
    return subprocess.run(
        ["git", "show", f"HEAD:{path}"], cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", check=True,
    ).stdout


def census(sources: dict[str, str]) -> list[str]:
    """HEAD 上的重复普查（人读的读数，不是判据）。"""
    rows = []
    asset_defs = [n for n, s in sources.items() if re.search(r"^def _asset_url\(", s, re.M)]
    rows.append(f" `_asset_url` 定义处：{len(asset_defs)}（{', '.join(asset_defs)}）")
    fetch_defs = [n for n, s in sources.items() if re.search(r"^def _fetch_(releases|text)\(", s, re.M)]
    rows.append(f" `_fetch_releases` / `_fetch_text` 定义处：{len(fetch_defs)}（{', '.join(fetch_defs)}）")
    private_edges = sum(
        1 for n, s in sources.items() if n == "full_update.py" and "from .materials_update import" in s
    )
    rows.append(f" `full_update` → `materials_update` 私有 import：{private_edges}")
    rows.append(
        " 版本比较降级 idiom 出现次数："
        + "，".join(f"{n}={version_fallback_sites(s)}" for n, s in sources.items())
    )
    urllib_mods = [n for n, s in sources.items() if imports_urllib(s)]
    rows.append(f" 直接 import urllib 的模块：{', '.join(urllib_mods) or '（无）'}")
    codes = {n: sorted(defined_code_literals(s)) for n, s in sources.items()}
    dup = sorted({c for n, cs in codes.items() if n != "update.py" for c in cs})
    rows.append(f" 功能模块里各自定义的错误码字面量：{dup or '（无）'}")
    return rows


def main() -> int:
    head = {name: head_source(path) for name, path in FILES.items()}
    now = {name: (REPO / path).read_text(encoding="utf-8") for name, path in FILES.items()}

    print("== ① HEAD（收走前）的重复普查 ==")
    for row in census(head):
        print(row)

    print("\n== ② 同一套判据作用在 HEAD 上（应红）==")
    red = []
    for name in ("full_update.py", "materials_update.py"):
        src = head[name]
        if defines_function(src, "asset_url") or version_fallback_sites(src):
            red.append(f"{name}: 机制自备（asset_url / 版本比较降级）")
        if imports_urllib(src):
            red.append(f"{name}: 直接 import urllib")
        dup_codes = defined_code_literals(src) & {"network", "no-asset", "no-release", "bad-manifest"}
        if dup_codes:
            red.append(f"{name}: 又定义共享错误码 {sorted(dup_codes)}")
    if imports_module(head["full_update.py"], "materials_update"):
        red.append("full_update.py: import 了 materials_update")
    for line in red:
        print("  ✗ " + line)

    print("\n== ③ 同一套判据作用在当前工作树上（应绿）==")
    green_violations = []
    for name in ("full_update.py", "materials_update.py"):
        src = now[name]
        if defines_function(src, "asset_url") or version_fallback_sites(src) or imports_urllib(src):
            green_violations.append(name)
        if defined_code_literals(src) & {"network", "no-asset", "no-release", "bad-manifest"}:
            green_violations.append(name + "（错误码）")
    if imports_module(now["full_update.py"], "materials_update"):
        green_violations.append("full_update.py（import 面）")
    print("  （无违规）" if not green_violations else "  ✗ " + ", ".join(green_violations))

    ok = bool(red) and not green_violations
    print("\n" + ("RED→GREEN 成立（红证 + 绿证同源）" if ok else "异常：红或绿不符合预期"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
