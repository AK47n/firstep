"""真机验收（工单 pin-conflict-gate/01）：真库 + 真母版 + 真机炸过的模块集 → 生成前拦下。

不经 webapp（与 probe-16 同款做法）：直接调产品自己的 `generator.generate`，
输入 = `.scratch/real-run/cache/recommend_2026H.json` 里那份真实推荐（12 模块，
真机 2026H/mspm0 用它生成后编译 exit=2、7 条 Resource conflict）——期望**在创建
输出目录之前**抛 `SyscfgPinConflictError`，输出目录不产生（不产出编不过的工程）。

用法：
    $env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
    python .scratch/pin-conflict-gate/probe-02-real-machine.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.generator import SyscfgPinConflictError, generate  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

CACHE = REPO / ".scratch" / "real-run" / "cache" / "recommend_2026H.json"
OUT = REPO / ".scratch" / "pin-conflict-gate" / "out-shadow"


def main() -> int:
    cached = json.loads(CACHE.read_text(encoding="utf-8"))
    slugs = [m["slug"] for m in cached["done"]["modules"]]
    platform = cached["platform"]
    print(f"[真机] 复用真实推荐：topic={cached['topic_key']} platform={platform}")
    print(f"[真机] 选中 {len(slugs)} 模块：{', '.join(slugs)}")

    resolved = resolve_selection(REPO / "library" / "modules", platform, slugs)
    print(f"[真机] 依赖展开后 {len(resolved.manifests)} 个模块；"
          f"平台警告 {len(resolved.warnings)} 条")

    if OUT.exists():
        import shutil

        shutil.rmtree(OUT)
    try:
        generate(
            platform=platform,
            manifests=resolved.manifests,
            module_library_dir=REPO / "library" / "modules",
            master_project_dir=REPO / "library" / "masters" / platform,
            output_dir=OUT,
            main_c_content="int main(void) { while (1); }\n",
        )
    except SyscfgPinConflictError as exc:
        print("\n[真机] ✓ 生成前拦下（SyscfgPinConflictError）：")
        print(str(exc))
        print(f"\n[真机] 输出目录是否产生：{OUT.exists()}（期望 False = 不产出残缺工程）")
        return 0 if not OUT.exists() else 1
    print("\n[真机] ✗ 没有拦下——工程已产出（预期外）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
