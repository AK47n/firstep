"""身份字段双向守卫红证脚本（工单 identity-fields/02）。

做法：把真实 `library/modules` 复制到临时目录，注入两类破坏，用与
`tests/test_library_invariants.py` **同一判据函数**扫描副本，证明守卫真的会红；
真实库全程只读、脚本自恢复（临时目录用完即删）。

用法：
  $env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; python .scratch/library-audit/probe_identity_guard_red.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "library" / "modules"

sys.path.insert(0, str(ROOT / "src"))

from contest_generator.library import (  # noqa: E402
    MODULE_KIND,
    ModuleKind,
    requires_identity,
)


def _identity_problems(modules_dir: Path, slugs, kind: str) -> list[str]:
    """与 tests/test_library_invariants.py::_identity_problems 同判据（副本目录版）。"""
    problems: list[str] = []
    for slug in sorted(slugs):
        manifest_path = modules_dir / slug / "manifest.json"
        if not manifest_path.is_file():
            continue
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        for platform, entry in sorted((data.get("platforms") or {}).items()):
            kit = str(entry.get("kit") or "").strip()
            url = str(entry.get("source_url") or "").strip()
            if kind == ModuleKind.DEVICE:
                missing = [
                    name for name, value in (("kit", kit), ("source_url", url)) if not value
                ]
                if missing:
                    problems.append(f"{slug}/{platform} 缺 {'、'.join(missing)}")
                elif not url.startswith("http"):
                    problems.append(f"{slug}/{platform} 的 source_url 非 URL：{url!r}")
            elif kit or url:
                filled = [name for name, value in (("kit", kit), ("source_url", url)) if value]
                problems.append(f"{slug}/{platform} 不该有身份字段：{'、'.join(filled)}")
    return problems


def _patch(manifest_path: Path, *, kit: str | None = None) -> None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in (data.get("platforms") or {}).values():
        entry["kit"] = kit if kit is not None else ""
        if kit:
            entry["source_url"] = "https://example.invalid/red-proof"
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "modules"
        shutil.copytree(MODULES, copy)

        print("=== 破坏①：给内部件 delay 填 kit（豁免守卫应红）")
        _patch(copy / "delay" / "manifest.json", kit="伪造套件")
        internal = [
            slug for slug, kind in MODULE_KIND.items() if kind != ModuleKind.DEVICE
        ]
        problems = _identity_problems(copy, internal, ModuleKind.INTERNAL)
        print("   红？", bool(problems))
        for problem in problems:
            print("   -", problem)

        # 还原
        _patch(copy / "delay" / "manifest.json", kit="")

        print("=== 破坏②：清空真器件 motor 的 kit（器件守卫应红）")
        _patch(copy / "motor" / "manifest.json", kit="")
        devices = [slug for slug in MODULE_KIND if requires_identity(slug)]
        unregistered = [
            p.name
            for p in sorted(copy.iterdir())
            if p.is_dir() and p.name not in MODULE_KIND
        ]
        problems = _identity_problems(copy, [*devices, *unregistered], ModuleKind.DEVICE)
        print("   红？", bool(problems), "（缺口条数", len(problems), "）")
        for problem in problems[:5]:
            print("   -", problem)

    print("=== 真实库未被触碰：")
    real = _identity_problems(
        MODULES,
        [slug for slug, kind in MODULE_KIND.items() if kind != ModuleKind.DEVICE],
        ModuleKind.INTERNAL,
    )
    print("   内部件/协议切片身份字段违规数 =", len(real))
    motor = json.loads((MODULES / "motor" / "manifest.json").read_text(encoding="utf-8"))
    print(
        "   motor/stm32 kit 仍在：",
        bool(motor["platforms"]["stm32"].get("kit")),
        "| motor/mspm0 kit：",
        repr(motor["platforms"]["mspm0"].get("kit")),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
