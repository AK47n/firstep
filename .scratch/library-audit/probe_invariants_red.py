"""临时探针：新收敛的库不变量「确实能红」（注入三类破坏，只读工作区）。

做法：把 `library/modules` 复制到临时目录，在副本里注入破坏，再用 monkeypatch
把测试模块的 LIBRARY_MODULES / MANIFESTS 指向副本重跑——工作区零改动。
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import tests.test_library_invariants as inv  # noqa: E402


def rebuild(module, library_root: Path) -> None:
    """把测试模块的模块表指向副本。"""
    module.LIBRARY_MODULES = library_root
    module.MANIFESTS = {
        m.slug: m
        for m in (
            inv.ModuleManifest.load(d)
            for d in sorted(library_root.iterdir())
            if d.is_dir()
        )
    }


def run(name: str, test) -> None:
    try:
        test()
    except AssertionError as exc:
        print(f"RED   {name}: {str(exc).splitlines()[0][:110]}")
    else:
        print(f"GREEN {name}（预期红却绿）")


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "modules"

    # 破坏 1：依赖悬空
    shutil.copytree(ROOT / "library" / "modules", root)
    manifest_path = root / "oled" / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["dependencies"] = ["ghost_module"]
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rebuild(inv, root)
    run("依赖悬空", inv.test_module_dependencies_resolve_inside_library)

    # 破坏 2：声明了不存在的文件
    data["dependencies"] = []
    data["platforms"]["stm32"]["files"] = ["code/ghost.c"]
    manifest_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rebuild(inv, root)
    run("声明文件缺失", inv.test_declared_platform_files_exist)

    # 破坏 3：依赖成环（motor ↔ pid 互依赖）
    shutil.rmtree(root)
    shutil.copytree(ROOT / "library" / "modules", root)
    for slug, dep in (("motor", "pid"), ("pid", "motor")):
        path = root / slug / "manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["dependencies"] = [dep]
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    rebuild(inv, root)
    run("依赖成环", inv.test_module_dependency_graph_is_acyclic)

    # 破坏 4（多实例声明不完整）已删除：manifest 加载器本身就拒（max 必须正整数、
    # variant 必须非空）——该不变量由加载器强制，测试属冗余，已从测试文件移除。

    # 破坏 5：简介清空
    shutil.rmtree(root)
    shutil.copytree(ROOT / "library" / "modules", root)
    path = root / "dht11" / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["description"] = "  "
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    rebuild(inv, root)
    run("模块缺简介", inv.test_modules_have_descriptions)

importlib.reload(inv)  # 复原（工作区未被改动）
