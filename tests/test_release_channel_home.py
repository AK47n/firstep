# -*- coding: utf-8 -*-
"""发布通道公共件归位的结构钉（工单 release-channel-dedupe/01）。

**为什么单独一个文件**：这条不变量管的是**模块边界与线上契约**（机制定义在哪、错误码从哪来、
前端按码分支的字面量是否还在后端声明的集合里），不是某条通道的载荷行为——跟
`test_full_update.py` / `test_materials_update.py` 的用例住一起，会让"改模块边界"与"改载荷"
两件事抢同一个文件（同款先例：`tests/test_hwcheck_assembly_home.py`、`tests/test_llm_run.py`）。
判据是纯函数，红证可喂合成片段或 HEAD 版源码，不必手改仓库文件。

不变量：**发布通道的机制只有一处定义，在 `update.py`**——三条通道（小发版 / 完整包 / 资料库）
的载荷形状与中文文案各写各的，但「找 release / 取资产地址 / 版本比较降级 / HTTP 面 / 错误码」
回功能模块重新定义，就等于机制又被抄了一份（工单收走的就是它们）。

真红证见 `.scratch/release-channel-dedupe/probe-01-pin-red-proof.py`（把 HEAD 版三个模块
喂给同一套判据 → 报出收走前的那批重复）。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "contest_generator"

UPDATE_PATH = SRC / "update.py"
FULL_PATH = SRC / "full_update.py"
MATERIALS_PATH = SRC / "materials_update.py"

# 机制名 → 只许在 update.py 定义（其余模块只能 import 用）
_SHARED_MECHANISMS = ("asset_url", "latest_release", "compare_versions_or_text", "http_json", "http_text")

# 通道区分字面量 → 同样只许在 update.py 定义
# （完整包按它排除资料库 tag、资料库按它筛选、比较版本前还要剥它）
_SHARED_CONSTANTS = ("MATERIALS_TAG_PREFIX",)

# 错误码：线上契约（前端按这些字符串分支）→ 字面量只许在 update.py 定义
_SHARED_CODES = ("network", "no-asset", "no-release", "bad-manifest")

_JS_ERROR_SWITCHES = (
    REPO / "src" / "contest_generator" / "static" / "js" / "fx" / "update.js",
    REPO / "src" / "contest_generator" / "static" / "js" / "fx" / "materials-update.js",
)


# ---------------------------------------------------------------------------
# 判据（纯函数：源码进，事实出）
# ---------------------------------------------------------------------------


def defines_function(source: str, name: str) -> bool:
    """源码里是否**定义**了顶层 `def name`（import 不算）。"""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return True
    return False


def imports_module(source: str, module: str) -> bool:
    """源码里是否 import 了 `module`（`from .x import …` / `import x`，按末段比）。"""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[-1] == module:
                return True
        elif isinstance(node, ast.Import):
            if any(alias.name.split(".")[-1] == module for alias in node.names):
                return True
    return False


def imports_urllib(source: str) -> bool:
    """源码是否直接 import urllib（HTTP 实现住在 update.py，功能模块只留委托壳）。"""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "urllib" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "urllib":
            return True
    return False


def defined_code_literals(source: str) -> set[str]:
    """源码里定义出来的错误码字面量（`ERROR_X = "network"` 这类）。"""
    out: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not any(t.startswith("ERROR_") for t in targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            out.add(node.value.value)
    return out


def assigns_constant(source: str, name: str) -> bool:
    """源码里是否给顶层名字 `name` 赋了值（`X = …`；import 不算）。"""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return True
    return False


def js_error_literals(source: str) -> set[str]:
    """前端按 `error` 码分支时写的字面量（`check.error === "network"`）。"""
    return set(re.findall(r'\.error\s*===\s*"([^"]+)"', source))


def version_fallback_sites(source: str) -> int:
    """源码里「版本比较降级」idiom 的出现次数（`(b > a) - (b < a)`）。

    这是本次收走的重复：同一兜底此前散在 4 处（`update.py` / `full_update.py` ×2 /
    `materials_update.py`），现在只在 `update.compare_versions_or_text` 一处。
    """
    return len(re.findall(r"\([A-Za-z_][\w.]* > [A-Za-z_][\w.]*\) - \(", source))


# ---------------------------------------------------------------------------
# 守卫
# ---------------------------------------------------------------------------


def test_shared_mechanisms_are_defined_only_in_update_module():
    """机制（取资产 / 找最新 release / 版本比较降级 / HTTP 面）与通道区分字面量只在 update.py 定义。"""
    for path in (FULL_PATH, MATERIALS_PATH):
        source = path.read_text(encoding="utf-8")
        redefined = [name for name in _SHARED_MECHANISMS if defines_function(source, name)]
        assert not redefined, f"{path.name} 又定义了一份发布通道机制：{redefined}"
        assert not imports_urllib(source), f"{path.name} 直接 import urllib（HTTP 实现应在 update.py）"
        dup_consts = [name for name in _SHARED_CONSTANTS if assigns_constant(source, name)]
        assert not dup_consts, f"{path.name} 又定义了一份通道区分字面量：{dup_consts}"
        # 形状型判据（正则数 idiom）：带合成红证，见 test_pin_is_not_vacuous
        assert version_fallback_sites(source) == 0, (
            f"{path.name} 又写了一遍版本比较降级（应在 update.compare_versions_or_text）"
        )


def test_full_update_does_not_reach_into_materials_update():
    """完整包通道不再 import 资料库通道（跨功能私有依赖退场）。"""
    source = FULL_PATH.read_text(encoding="utf-8")
    assert not imports_module(source, "materials_update"), "full_update 又 import 了 materials_update"


def test_error_codes_are_defined_once_and_are_the_same_objects():
    """错误码字面量只许在 update.py 定义；功能模块导出的必须是**同一个对象**。"""
    for path in (FULL_PATH, MATERIALS_PATH):
        literals = defined_code_literals(path.read_text(encoding="utf-8")) & set(_SHARED_CODES)
        assert not literals, f"{path.name} 又定义了一份共享错误码：{sorted(literals)}"

    from contest_generator import full_update as fu
    from contest_generator import materials_update as mu
    from contest_generator import update as up

    for name in ("ERROR_NETWORK", "ERROR_NO_RELEASE", "ERROR_BAD_MANIFEST"):
        assert getattr(mu, name) is getattr(up, name), f"materials_update.{name} 不是 update 的同一对象"
    for name in ("ERROR_NETWORK", "ERROR_NO_RELEASE", "ERROR_BAD_MANIFEST", "ERROR_NO_ASSET"):
        assert getattr(fu, name) is getattr(up, name), f"full_update.{name} 不是 update 的同一对象"
    assert fu.RELEASES_URL is up.RELEASES_URL, "两条通道的列表端点不是同一个常量"
    assert mu.RELEASES_URL is up.RELEASES_URL, "两条通道的列表端点不是同一个常量"


def test_frontend_error_switches_stay_inside_the_backend_codes():
    """前端按 `error` 码分支的字面量必须都在后端声明的码集合内（跨语言契约对账）。"""
    from contest_generator import materials_update as mu
    from contest_generator import update as up

    declared = set(_SHARED_CODES) | {mu.ERROR_BASELINE_MISSING}
    assert declared == {
        getattr(up, name) for name in dir(up) if name.startswith("ERROR_")
    } | {mu.ERROR_BASELINE_MISSING}, "后端声明的错误码集合与预期不符（新增/改名要同步本守卫）"

    for path in _JS_ERROR_SWITCHES:
        unknown = js_error_literals(path.read_text(encoding="utf-8")) - declared
        assert not unknown, f"{path.name} 按未声明的 error 码分支：{sorted(unknown)}"


# ---------------------------------------------------------------------------
# 守卫不是摆设（合成红证）
# ---------------------------------------------------------------------------


def test_pin_is_not_vacuous():
    """把机制/错误码/字面量抄回功能模块的片段喂进判据 → 当场认出（真红证见 .scratch 探针）。

    每条判据都要有自己的合成红证（先例 `test_hwcheck_assembly_home.py:78`）——
    形状型判据尤其：排版一变就可能静默空转。
    """
    dup = (
        'from .materials_update import _fetch_releases\n'
        'MATERIALS_TAG_PREFIX = "materials-"\n'
        'def asset_url(release, name):\n'
        '    return ""\n'
        'def latest_release(releases, matches):\n'
        '    return None\n'
        'ERROR_NETWORK = "network"\n'
        'ERROR_NO_RELEASE = "no-release"\n'
    )
    assert defines_function(dup, "asset_url")
    assert defines_function(dup, "latest_release")
    assert imports_module(dup, "materials_update")
    assert assigns_constant(dup, "MATERIALS_TAG_PREFIX")
    assert defined_code_literals(dup) & set(_SHARED_CODES) == {"network", "no-release"}
    assert imports_urllib("import urllib.request\n") is True

    # 形状型判据的合成红证：把旧 idiom 写回去必须数得出来
    assert version_fallback_sites("cmp = (tag_b > tag_a) - (tag_b < tag_a)\n") == 1
    assert version_fallback_sites("return (b > a) - (b < a)\n") == 1
    assert version_fallback_sites("cmp = compare_versions_or_text(a, b)\n") == 0

    # 前端写了个后端没声明的码 → 对账当场认出
    assert js_error_literals('if (check.error === "no-realase") {}') == {"no-realase"}
