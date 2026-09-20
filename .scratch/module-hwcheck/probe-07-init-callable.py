# -*- coding: utf-8 -*-
"""量具（工单 module-hwcheck/07 开工前）第五跑：初始化调用**能不能无参调**。

通用降级要生成 `<name>();`——只有头文件里声明成 `name(void)` / `name()` 的
才保证编得过（`led_init(uint8_t)` 那种传参会直接编译报错）。本跑把三级判据
与"无参声明"这条合起来，统计最终能拿到初始化的格数。
"""

from __future__ import annotations

import io
import re
import sys
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = Path(__file__).resolve().parent / "probe-07-init-callable.txt"

from contest_generator.hwcheck_recipe import load_recipes  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import KNOWN_PLATFORMS  # noqa: E402

LIBRARY = ROOT / "library" / "modules"
MASTERS = ROOT / "library" / "masters"

_DECL = re.compile(
    r"\b(?P<name>[A-Za-z_]\w*)\s*\((?P<params>[^;{)]*)\)\s*;"
)


def declarations(texts) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for _rel, text in texts:
        for match in _DECL.finditer(text):
            params = re.sub(r"\s+", " ", match.group("params")).strip()
            out.setdefault(match.group("name"), set()).add(params)
    return out


def zero_param(decls: dict[str, set[str]], name: str) -> bool:
    forms = decls.get(name)
    return bool(forms) and all(f in ("", "void") for f in forms)


def header_texts(manifest, platform: str, master: bool):
    entry = manifest.platforms[platform]
    out = []
    if master:
        root = MASTERS / platform
        if root.is_dir():
            out = [(p.relative_to(root).as_posix(),
                    p.read_text(encoding="utf-8", errors="replace"))
                   for p in sorted(root.rglob("*.h"))]
        return out
    for rel in entry.files:
        if rel.lower().endswith(".h"):
            path = LIBRARY / manifest.slug / rel
            if path.is_file():
                out.append((rel, path.read_text(encoding="utf-8", errors="replace")))
    return out


def main() -> None:
    manifests = list_modules(LIBRARY)
    recipes = load_recipes(LIBRARY, manifests)
    specialized = {
        (slug, platform) for slug, catalog in recipes.items()
        for platform in catalog.sections
    }
    tiers: Counter[str] = Counter()
    detail: list[str] = []
    for manifest in sorted(manifests, key=lambda m: m.slug):
        for platform in sorted(KNOWN_PLATFORMS):
            if manifest.platforms.get(platform) is None:
                continue
            if (manifest.slug, platform) in specialized:
                continue
            own = declarations(header_texts(manifest, platform, False))
            master = declarations(header_texts(manifest, platform, True))
            exact = f"{manifest.slug}_init"
            tier = ""
            if zero_param(own, exact):
                tier = "1 精确 <slug>_init（模块头，无参）"
            else:
                uniq = [n for n in own
                        if n.lower().endswith("_init") and zero_param(own, n)]
                if len(uniq) == 1:
                    tier = "2 唯一 *_init（模块头，无参）"
                elif zero_param(master, exact):
                    tier = "3 精确 <slug>_init（母版头，无参）"
                else:
                    tier = "0 认不出"
                    cands = sorted(n for n in own if n.lower().endswith("_init"))
                    detail.append(
                        f"  {manifest.slug:<14} {platform:<6} "
                        f"模块头 *_init={cands[:4]} 无参={uniq[:3]} "
                        f"母版有<{exact}>={exact in master}")
            tiers[tier] += 1
    for key in sorted(tiers):
        print(f"{key}: {tiers[key]}")
    print()
    print("认不出的格：")
    print("\n".join(detail) if detail else "  （无）")


if __name__ == "__main__":
    # UTF-8 落盘（别用 PowerShell 的 `*>`：会按本机 GBK 写）
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    text = buffer.getvalue()
    OUT.write_text(text, encoding="utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    print(text)
