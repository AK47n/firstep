# -*- coding: utf-8 -*-
"""工单 module-hwcheck/09 的**判据强度探针**（仓库纪律：每条新守卫都要有一次
"停用后用例必须变红"的实测）。

四处停用，各自点名该红的用例：

1. **配方数据少一格**（从 `library/hwcheck_recipes.json` 里删掉 beep）→ 地板断言红；
2. **地板清单被改小**（`tests/test_hwcheck_recipe.py` 的 PILOT 少一行）→ 条数断言红；
3. **枚举常量 / typedef 名不进白名单**（`hwcheck_recipe.interface_names` 去掉
   `_enum_and_typedef_names`）→ adc 配方（read 里直接写枚举常量）当场红；
4. **给单平台件补一格别的平台**（sr04 加 stm32 配方）→ 引用校验红（该平台没有条目）。

做法：逐处最小替换 → 跑点名用例 → 要求变红 → **逐字节复原**并复核
（`file_bytes == original`）。任何一步不符就当场报 FAIL，末尾打印 PASS/FAIL 清单。

用法：`python .scratch/module-hwcheck/probe-09-guard-strength.py`（约 1 分钟）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_RECIPES = "library/hwcheck_recipes.json"
_FLOOR_TESTS = (
    "tests/test_hwcheck_recipe.py::test_real_library_has_a_recipe_for_every_pilot_slot",
)


@dataclass(frozen=True)
class Mutation:
    """一处停用：文件 + 原文 + 替换文 + 期望变红的用例。"""

    name: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]


def _drop_recipe(name: str) -> Mutation:
    """把某件从配方文件里删掉（JSON 层面：先取文本，再删它的整块）。"""
    return Mutation(
        name=f"配方少一格（删掉 {name}）",
        path=_RECIPES,
        old="",          # 由 apply() 特判（JSON 结构操作，不是文本替换）
        new=name,
        tests=_FLOOR_TESTS,
    )


MUTATIONS: tuple[Mutation, ...] = (
    _drop_recipe("beep"),
    Mutation(
        name="地板清单被改小（PILOT 少一行）",
        path="tests/test_hwcheck_recipe.py",
        old='         ("beep", PLATFORM_STM32), ("beep", PLATFORM_MSPM0),\n',
        new="",
        tests=("tests/test_hwcheck_recipe.py::test_pilot_floor_covers_every_v1_slot",),
    ),
    Mutation(
        name="枚举常量 / typedef 名不进白名单",
        path="src/contest_generator/hwcheck_recipe.py",
        # 停用的是**唯一的补充提取器入口**（`_header_names`）：母版头与模块头两条
        # 路径都走它，所以这一刀同时盖住两条（评审整改前只摘了母版侧那一行，
        # 模块头那条路还活着，4/4 PASS 其实没覆盖到）。
        old="    return _define_names(headers) | _extern_names(headers) | _enum_and_typedef_names(headers)",
        new="    return _define_names(headers) | _extern_names(headers)",
        tests=(
            "tests/test_hwcheck_recipe.py::test_enum_constants_and_typedefs_are_real_interface_names",
            "tests/test_hwcheck_recipe.py::test_real_library_recipes_reference_only_real_interfaces",
        ),
    ),
    Mutation(
        name="给单平台件补一格别的平台（sr04 加 stm32）",
        path=_RECIPES,
        old="",
        new="sr04-add-stm32",
        tests=(
            "tests/test_hwcheck_recipe.py::test_real_library_recipes_reference_only_real_interfaces",
            "tests/test_hwcheck_recipe.py::test_single_platform_pilot_modules_have_no_other_platform_recipe",
        ),
    ),
)


def _apply(mutation: Mutation, text: str) -> str | None:
    """按形态生成停用后的文本；无法应用返回 None。"""
    if mutation.new == "beep" and mutation.old == "":
        data = json.loads(text)
        if "beep" not in data:
            return None
        data.pop("beep")
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if mutation.new == "sr04-add-stm32" and mutation.old == "":
        data = json.loads(text)
        cell = data.get("sr04", {}).get("mspm0")
        if not cell or "stm32" in data["sr04"]:
            return None
        data["sr04"]["stm32"] = json.loads(json.dumps(cell))  # 照抄一格（不该存在）
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    newline = "\r\n" if "\r\n" in text else "\n"
    old = mutation.old.replace("\n", newline)
    new = mutation.new.replace("\n", newline)
    if text.count(old) != 1:
        return None
    return text.replace(old, new)


def run_tests(tests: tuple[str, ...]) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    return proc.returncode != 0, (tail[-1] if tail else "")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    verdicts: list[str] = []
    for mutation in MUTATIONS:
        path = REPO / mutation.path
        original = path.read_bytes()
        mutated = _apply(mutation, original.decode("utf-8"))
        if mutated is None:
            verdicts.append(f"FAIL  {mutation.name}：停用没能应用（原文不匹配 / 已经停用？）")
            continue
        try:
            path.write_bytes(mutated.encode("utf-8"))
            red, tail = run_tests(mutation.tests)
        finally:
            path.write_bytes(original)
        restored = path.read_bytes() == original
        verdicts.append(
            f"{'PASS' if (red and restored) else 'FAIL'}  {mutation.name}"
            f"（变红={red} / 逐字节复原={restored}）  {tail}"
        )
    print("\n".join(verdicts))
    return 0 if all(v.startswith("PASS") for v in verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
