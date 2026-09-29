"""跨语言镜像守卫：**描边口径**在两侧必须逐字同源（工单 border-guard/01）。

## 为什么要有这个文件

"整圈完整框"这条线有两个实现，各自服务一半的判据：

| | 住哪 | 谁在跑 | 管什么 |
|---|---|---|---|
| **JS** | `tests/js/css-tokens.test.mjs` 的 `fullBorderEntries()` / `borderRegisterProblems()` | 前端门禁（`node --test tests/js/*.test.mjs`） | 腿⑥：盘上 ↔ 登记簿双向对账 |
| **Python** | `.scratch/ui-density-sitewide/scope_lib.py` 的 `full_border_entries()` 等 | 探针（`.scratch/border-guard/probe-03-register.py`）与读数 | 把 115 这个数**量出来** |

两侧的**判据本体**是同一段文本（正则 + 那个 `["none", "0"]` 常量）在两个语言里各写了一遍。
两边一旦漂移，就会出现最难查的一类假账：**腿绿而读数红**（或反过来）——
守卫说"对得上"，探针说"差 3 条"，而两份输出**各自内部都自洽**。

本仓对跨语言镜像的既有惯例就是**配一条结构守卫**（`tests/test_library_invariants.py` 的
`test_js_module_kind_vocabulary_mirrors_python_enum`、`tests/test_pin_share_mirror.py`）。
这条就是照那个惯例给描边口径补的：JS 侧那几段文本，与 Python 侧的常量/regex **必须一致**。

## 它判什么

四条（口径的每一块都点到）：

1. `DEAD_BORDER` 的取值列表（"什么算撤框"）；
2. 整圈完整框那条正则（"什么算一条整圈完整框"）；
3. `transparent` 那条正则（`placeholder` 不变量的两半之一）；
4. 剥前导块注释那条正则（认人键稳不稳，全看它俩一致不一致）。

**它不判**：不跑 JS、不跑 node（前端门禁才是跑它的地方，见
`docs/agents/workflow.md` 的闸门表）——这里只钉"两侧写的是不是同一把尺"。
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD_JS = ROOT / "tests" / "js" / "css-tokens.test.mjs"
SCOPE_LIB = ROOT / ".scratch" / "ui-density-sitewide" / "scope_lib.py"


def _load_scope_lib():
    """从 `.scratch/` 里加载口径模块（照 `tests/test_tracker_audit_status.py` 的既有写法）。"""
    assert SCOPE_LIB.is_file(), f"口径模块不在：{SCOPE_LIB}（本仓入库文件，缺了就是被删了）"
    spec = importlib.util.spec_from_file_location("_border_scope_lib", SCOPE_LIB)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def js() -> str:
    assert GUARD_JS.is_file(), f"守卫不在：{GUARD_JS}"
    return GUARD_JS.read_text(encoding="utf-8")


def _js_regex_literal(seg: str, anchor: str) -> str:
    """从 `seg` 里抠出**第一个正则字面量**的正文（正确跳过 `\\/` 这类转义定界符）。

    ⚠ 别用 `/(.+?)/` 那种懒匹配：`stripLeadComments` 的正则里就有转义斜杠
    （`/^(\\/\\*[\\s\\S]*?\\*\\/\\s*)+/`），懒匹配会在第一个 `\\/` 上截断
    （本文件第一版就是这么把 `^(\\` 当成整条正则的）。
    """
    at = seg.index("/")
    i = at + 1
    while i < len(seg):
        if seg[i] == "\\":
            i += 2
            continue
        if seg[i] == "/":
            return seg[at + 1:i]
        i += 1
    raise AssertionError(f"在 {anchor!r} 后面找不到收尾的正则定界符——守卫变了，改这条自检")


def _js_regex_source(js: str, anchor: str) -> str:
    """抠出 `anchor` 之后**第一个** `/…/flags` 字面量里的正则正文（不带定界符与 flags）。"""
    at = js.index(anchor)
    return _js_regex_literal(js[at:at + 400], anchor)


def test_dead_border_values_match_across_languages(js):
    """① 什么算"撤框"：两侧的取值列表必须一样。"""
    m = re.search(r"const DEAD_BORDER = \[(.*?)\];", js)
    assert m, "守卫里找不到 `const DEAD_BORDER = [...];`"
    js_values = re.findall(r'"([^"]+)"', m.group(1))
    assert js_values == list(_load_scope_lib().DEAD_BORDER), (
        "DEAD_BORDER 两侧不一致——腿⑥ 与读数会在'什么算撤框'上分叉：\n"
        f"  JS     : {js_values}\n  Python : {list(_load_scope_lib().DEAD_BORDER)}"
    )


def test_full_border_regex_matches_across_languages(js):
    """② 什么算"一条整圈完整框"：两侧的正则正文必须逐字相同。"""
    js_src = _js_regex_source(js, "function fullBorderEntries(")
    py_src = _load_scope_lib().FULL_BORDER_RE.pattern
    assert js_src == py_src, (
        "整圈完整框那条正则两侧不一致——这正是'腿绿而读数红'的成因：\n"
        f"  JS     : {js_src!r}\n  Python : {py_src!r}"
    )


def test_transparent_regex_matches_across_languages(js):
    """③ `placeholder` 不变量的 transparent 判定：两侧必须一致。"""
    js_src = _js_regex_source(js, "const transparent = ")
    py_src = _load_scope_lib().BORDER_TRANSPARENT_RE.pattern
    assert js_src == py_src, (
        "transparent 判定两侧不一致——透明占位那条不变量会在两侧给出不同结论：\n"
        f"  JS     : {js_src!r}\n  Python : {py_src!r}"
    )


def test_lead_comment_regex_matches_across_languages(js):
    r"""④ 剥前导块注释（认人键的地基）：两侧必须一致。

    这一条**不能逐字比**——两个语言有各自的正则方言，同一条语义会写成不同文本：
      · JS 的正则**字面量**里必须把定界符转义成 `\\/`，Python 的原始字符串不必 → 归一掉；
      · "任意字符含换行"：JS 惯用 `[\\s\\S]`，Python 惯用 `.` 配 `re.S` → 归一掉；
      · 分组是否捕获：一侧写 `(?:`、另一侧可省 → 归一掉（对这条匹配结果没有影响）。
    归一只动这三处方言，**不动语义**；归完还不等 = 真漂移。
    """
    m = re.search(r"function stripLeadComments\(sel\) \{\s*return sel\.replace\(", js, re.S)
    assert m, "守卫里找不到 `stripLeadComments` 的 replace 调用——它改名了就改这条自检"
    js_src = _js_regex_literal(js[m.end():], "stripLeadComments")
    py_src = _load_scope_lib().LEAD_COMMENT_RE.pattern

    def norm(s: str) -> str:
        return s.replace("\\/", "/").replace(r"[\s\S]", ".").replace("(?:", "(")
    assert norm(js_src) == norm(py_src), (
        "剥前导块注释那条正则两侧不一致——**认人键**会在两侧分叉：\n"
        f"  JS     : {js_src!r}\n  Python : {py_src!r}\n"
        f"  归一后 : {norm(js_src)!r} vs {norm(py_src)!r}"
    )
