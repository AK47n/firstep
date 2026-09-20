# -*- coding: utf-8 -*-
"""量具（工单 module-hwcheck/07 开工前）第三跑：认不出初始化的那 12 格，
它们的 `<slug>_init` 在**母版头**里存在吗？（决定判据要不要并母版面）"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = Path(__file__).resolve().parent / "probe-07-missing-init.txt"

from contest_generator.hwcheck_recipe import (  # noqa: E402
    interface_names,
    load_recipes,
)
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.platforms import KNOWN_PLATFORMS  # noqa: E402
from contest_generator.skeleton import (  # noqa: E402
    extract_header_functions,
    format_interface_blocks,
)

LIBRARY = ROOT / "library" / "modules"
MASTERS = ROOT / "library" / "masters"
SUSPECTS = (
    ("adc", "stm32"), ("config", "mspm0"), ("config", "stm32"),
    ("delay", "mspm0"), ("delay", "stm32"), ("huidu", "mspm0"),
    ("k230", "mspm0"), ("k230", "stm32"), ("ntb_time", "mspm0"),
    ("ntb_time", "stm32"), ("uart", "mspm0"), ("uart", "stm32"),
)


def master_headers(platform: str):
    root = MASTERS / platform
    return [
        (path.relative_to(root).as_posix(),
         path.read_text(encoding="utf-8", errors="replace"))
        for path in sorted(root.rglob("*.h"))
    ] if root.is_dir() else []


def main() -> None:
    manifests = list_modules(LIBRARY)
    recipes = load_recipes(LIBRARY, manifests)
    specialized = {
        (slug, platform) for slug, catalog in recipes.items()
        for platform in catalog.sections
    }
    print(f"（本跑只为复核 {len(SUSPECTS)} 格；已专精格 {sorted(specialized)}）\n")
    for slug, platform in SUSPECTS:
        manifest = next(m for m in manifests if m.slug == slug)
        mh = master_headers(platform)
        master_names = set(extract_header_functions(format_interface_blocks(
            [("母版", rel, text) for rel, text in mh])))
        interfaces = interface_names(manifests, LIBRARY, platform, mh)
        names = set(interfaces.get(slug, frozenset()))
        exact = f"{slug}_init"
        entry = manifest.platforms[platform]
        own = [rel for rel in entry.files if rel.lower().endswith(".h")]
        print(f"{slug:<10} {platform:<6} files={list(entry.files)}")
        print(f"    own_headers={own}")
        print(f"    `<{exact}>` 在母版头里? {exact in master_names}"
              f"   在该平台接口集里? {exact in names}")
        hint = sorted(n for n in names
                      if n.lower().endswith("_init") and n.isascii())[:8]
        print(f"    接口集里的 *_init 候选（前 8）：{hint}")


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
