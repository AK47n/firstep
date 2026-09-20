# -*- coding: utf-8 -*-
"""检测页装配归位的结构钉（工单 webapp-consolidation/01）。

**为什么单独一个文件**：这条不变量管的是 **webapp 的 import 面**，不是板侧投影的
行为——它跟 `hwcheck_board` 的用例一起住会让"改 webapp import"与"改板侧投影"
两件事抢同一个文件（同款先例：`tests/test_download_sequence_home.py` 一条守卫一个
文件）。判据是纯函数，红证可喂合成片段或 HEAD 版源码，不必手改仓库文件。

不变量：**检测页装配住在域层，webapp 只经 `hwcheck_view` 拿它**——那批装配原语
（配方装载 / 接口清单 / 小节载荷 / 板侧投影 / 引脚消解 / 通用降级 / 命令台）回
webapp 的 import 面，就等于域函数被架空（工单迁走的就是它们）。
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WEBAPP_PATH = REPO / "src" / "contest_generator" / "webapp.py"

# webapp 允许从 hwcheck 族拿的名字（模块末段 → 白名单）。改这张表要有理由：
# 它同时是"装配住在域里"这条不变量的判据。
_ALLOWED_HWCHECK_IMPORTS: dict[str, frozenset[str]] = {
    "hwcheck": frozenset({
        "HwCheckConfig", "HwCheckError", "hwcheck_devices", "hwcheck_modules",
        "render_checklist", "render_main_c", "render_output_hint",
    }),
    "hwcheck_board": frozenset({"hwcheck_view"}),
    "hwcheck_console": frozenset(),
    "hwcheck_generic": frozenset(),
    "hwcheck_recipe": frozenset(),
    "hwcheck_store": frozenset({
        "DEFAULT_RECENT_LIMIT", "list_hwcheck_projects", "read_hwcheck_project",
        "resolve_hwcheck_output_dir",
    }),
    "hwcheck_triage": frozenset({
        "build_triage_context", "fallback_advice", "read_hwcheck_record",
        "record_with_advice", "record_with_checked", "record_with_symptom",
        "write_hwcheck_record",
    }),
}


def _hwcheck_imports(source: str) -> set[tuple[str, str]]:
    """源码里从 hwcheck 族 import 的 `(模块末段, 名字)` 对（判据纯函数）。"""
    out: set[tuple[str, str]] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        module = node.module.split(".")[-1]
        if module not in _ALLOWED_HWCHECK_IMPORTS:
            continue
        for alias in node.names:
            out.add((module, alias.asname or alias.name))
    return out


def _hwcheck_import_leaks(source: str) -> set[str]:
    """白名单外的那些，形如 `hwcheck_recipe.load_recipes`（红证喂合成片段 / HEAD 源码）。"""
    return {
        f"{module}.{name}"
        for module, name in _hwcheck_imports(source)
        if name not in _ALLOWED_HWCHECK_IMPORTS[module]
    }


def test_webapp_import_surface_keeps_the_assembly_in_the_domain():
    """webapp 只经 `hwcheck_view` 拿检测页装配；装配原语回 import 即红。"""
    source = WEBAPP_PATH.read_text(encoding="utf-8")
    leaks = _hwcheck_import_leaks(source)
    assert not leaks, f"检测页装配原语回 webapp import：{sorted(leaks)}"
    assert ("hwcheck_board", "hwcheck_view") in _hwcheck_imports(source), (
        "webapp 未走域层装配入口（hwcheck_view）"
    )


def test_hwcheck_import_pin_is_not_vacuous():
    """红证（合成片段）：把装配原语 import 回去 → 判据当场认出（守卫不是摆设）。

    真源码那份红证见 `.scratch/webapp-consolidation/probe-01-pin-red-proof.py`
    （把 HEAD 版 webapp.py 喂给同一个判据 → 11 条泄漏）。
    """
    fake = (
        "from .hwcheck_recipe import SECTION_TAG, load_recipes, resolve_sections\n"
        "from .hwcheck_board import hwcheck_board_view, hwcheck_pin_plan, hwcheck_view\n"
        "from .hwcheck_console import build_console_table, console_payload\n"
    )
    assert _hwcheck_import_leaks(fake) == {
        "hwcheck_recipe.SECTION_TAG",
        "hwcheck_recipe.load_recipes",
        "hwcheck_recipe.resolve_sections",
        "hwcheck_board.hwcheck_board_view",
        "hwcheck_board.hwcheck_pin_plan",
        "hwcheck_console.build_console_table",
        "hwcheck_console.console_payload",
    }
    assert ("hwcheck_board", "hwcheck_view") in _hwcheck_imports(fake)
