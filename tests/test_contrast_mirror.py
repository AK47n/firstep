"""跨语言镜像守卫：**对比度口径**在两侧必须逐字同源（工单 light-contrast/01）。

## 为什么要有这个文件

"文字压底过不过 AA"这条线有两个实现，各自服务一半的判据：

| | 住哪 | 谁在跑 | 管什么 |
|---|---|---|---|
| **JS** | `tests/js/css-tokens.test.mjs` 的腿⑧（`contrastProblems` 等） | 前端门禁 | 盘上 ↔ 例外表双向对账（闸门） |
| **Python** | `.scratch/light-contrast/probe_lib.py` | 探针 / 生成器 | 把比值**量出来**、把例外表**生成出来** |

两侧的口径（阈值两档、大字判据、亮度公式的五组常量、合成基色、四条解析正则、代码页那五层底、
两张族表）是同一份数据在两个语言里各写了一遍。漂移就会出现最难查的一类假账：
**腿绿而读数红**（或反过来）——守卫说"对得上"，探针说"差 3 条"，而两份输出各自内部都自洽。

本仓对跨语言镜像的既有惯例就是**配一条结构守卫**（`tests/test_border_register_mirror.py`、
`tests/test_pin_share_mirror.py`、`tests/test_library_invariants.py`）。这条照那个惯例立。

## 它判什么

十一组（口径的每一块都点到）：

1. `CONTRAST_THRESHOLDS`（小字 / 大字两档）；
2. `LARGE_TEXT`（24px / 18.66px+bold 那三个常量）；
3. `CONTRAST_LUM`（亮度公式的九个数：255 / 0.03928 / 12.92 / 0.055 / 1.055 / 2.4 / 三通道系数）；
4. `CONTRAST_RATIO_OFFSET` 与 `CONTRAST_BASE_TOKEN`（合成基色 = `--panel` 这条口径本身）；
5. **十五条正则**（`<style>` 块 / 剥注释 / 切规则 / 取声明 / 令牌 / 两个主题块 / 三元组 /
   两种十六进制 / rgba / var（含兜底）/ 字号 / **关键帧选择器** / **`:disabled` 认人面**）——
   认人键、合成底、阈值分档与"这条 `opacity` 算不算活规则 / 算不算禁用形态"全建立在它们上面；
6. `CODE_LAYERS`（代码页那五层底的名字与 alpha）；
7. `CONTRAST_FAMILIES`（族表的标签 / 令牌选取 / 底列表 / 阈值档位）；
8. `CONTRAST_FAMILY_KINDS` 与 `CONTRAST_TOKEN_KINDS`（阈值档位词表）；
9. `CONTRAST_TOKEN_BASES`（**第三面**：无底规则里的文字令牌 + 假定底 + 档位）——
   两张表今天各有一份副本，任何一侧单独改都是漂移。
   再加一条 **`--check` 的同源断言**：守卫里那张例外表必须等于生成器**现在**算出来的那张。
10. `CONTRAST_DISABLED_FORMS` / `CONTRAST_DISABLED_FORM_KINDS`
   （不可选形态 / 弱化的**登记表**，工单 `disabled-forms/01`；工单 `contrast-residue/04` 改成**全量驱动**）
   ——登记表逐条一致：只改一侧的话，探针会算出"这条规则没在册"而守卫说"在册"，
   正是最难查的那种假账。⚠ 同轮**退役**了 `CONTRAST_DISABLED_HINTS` / `CONTRAST_HINT_VECTORS`
   （反向嫌疑词法 + 它的行为向量表）：全量登记之后那套词法不再参与任何判据，镜像腿一并删掉。
11. **令牌解析面的行为向量表**（工单 `contrast-residue/01`）：`CONTRAST_TOKEN_VALUE_VECTORS`
   （取值面：**合并全部 `:root` 块**、后者覆盖前者 / 亮色覆盖只对亮色 / 沿用 `:root` /
   解不出仍是 `null`）与 `CONTRAST_TOKEN_DEFINED_VECTORS`（定义面：类作用域定义算定义、
   注释里的不算、带兜底的不算定义）。解析面从"只取第一个块"改成"合并全部块"时
   **正则正文一个字没变、变的是行为**——只有这张表拦得住。

**它不判**：不跑 JS、不跑 node（前端门禁才是跑它的地方，见 `docs/agents/workflow.md` 的闸门表）
——这里只钉"两侧写的是不是同一把尺"。
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD_JS = ROOT / "tests" / "js" / "css-tokens.test.mjs"
PROBE_LIB = ROOT / ".scratch" / "light-contrast" / "probe_lib.py"


def _load_probe_lib():
    """从 `.scratch/` 里加载口径模块（照 `tests/test_border_register_mirror.py` 的既有写法）。"""
    assert PROBE_LIB.is_file(), f"口径模块不在：{PROBE_LIB}（本仓入库文件，缺了就是被删了）"
    spec = importlib.util.spec_from_file_location("_contrast_probe_lib", PROBE_LIB)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def js() -> str:
    assert GUARD_JS.is_file(), f"守卫不在：{GUARD_JS}"
    return GUARD_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def py():
    return _load_probe_lib()


def _js_regex_literal(seg: str, anchor: str) -> str:
    """从 `seg` 里抠出**第一个正则字面量**的正文（正确跳过 `\\/` 这类转义定界符）。"""
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


def _js_regex(js: str, name: str) -> str:
    """取 `const <name> = /…/flags;` 里的正则正文。"""
    anchor = f"const {name} = "
    at = js.index(anchor)
    return _js_regex_literal(js[at + len(anchor):], name)


def _js_numbers_dict(js: str, name: str) -> dict[str, float]:
    m = re.search(rf"const {name} = \{{([\s\S]*?)\}};", js)
    assert m, f"守卫里找不到 `const {name} = {{...}};`"
    out = {}
    for k, v in re.findall(r"([a-z_]+)\s*:\s*([0-9.]+)", m.group(1)):
        out[k] = float(v)
    assert out, f"{name} 里一个数都没解析出来——格式变了"
    return out


def _norm(rx: str) -> str:
    """两处方言归一（**只动方言，不动语义**）：JS 的 `\\/` 转义、`[\\s\\S]`（Python 惯用 `.` + re.S）。"""
    return rx.replace("\\/", "/").replace(r"[\s\S]", ".")


def test_thresholds_and_large_text_match(js, py):
    """① 两档阈值 + 余量；② 大字判据三个常量。"""
    assert _js_numbers_dict(js, "CONTRAST_THRESHOLDS") == {
        k: float(v) for k, v in py.CONTRAST_THRESHOLDS.items()
    }, "阈值两档（小字 4.5 / 大字 3.0）或余量两侧不一致"
    assert _js_numbers_dict(js, "LARGE_TEXT") == {
        k: float(v) for k, v in py.LARGE_TEXT.items()
    }, "大字判据（≥24px / ≥18.66px+bold）两侧不一致"


def test_luminance_constants_match(js, py):
    """③ 亮度公式的九个数：差一个系数，所有比值都会静默偏移。"""
    assert _js_numbers_dict(js, "CONTRAST_LUM") == {
        k: float(v) for k, v in py.CONTRAST_LUM.items()
    }, "WCAG 亮度公式的常量两侧不一致（0.2126/0.7152/0.0722 与 0.03928 分段那几项）"


def test_ratio_offset_and_base_token_match(js, py):
    """④ `+0.05` 与合成基色 `--panel`：后者是"底 = 元素自己那层背景"这条口径的落点。"""
    m = re.search(r"const CONTRAST_RATIO_OFFSET = ([0-9.]+);", js)
    assert m, "守卫里找不到 `const CONTRAST_RATIO_OFFSET = ...;`"
    assert float(m.group(1)) == float(py.CONTRAST_RATIO_OFFSET), "对比度公式的 +0.05 两侧不一致"
    m = re.search(r'const CONTRAST_BASE_TOKEN = "([^"]+)";', js)
    assert m, "守卫里找不到 `const CONTRAST_BASE_TOKEN = \"...\";`"
    assert m.group(1) == py.CONTRAST_BASE_TOKEN, "合成基色令牌两侧不一致"


@pytest.mark.parametrize(("js_name", "py_attr"), [
    ("CONTRAST_STYLE_RE", "STYLE_BLOCK_RE"),
    ("CONTRAST_COMMENT_RE", "CSS_COMMENT_RE"),
    ("CONTRAST_RULE_RE", "RULE_RE"),
    ("CONTRAST_DECL_RE", "DECL_RE"),
    ("CONTRAST_TOKEN_RE", "TOKEN_RE"),
    ("CONTRAST_ROOT_RE", "BLOCK_ROOT"),
    ("CONTRAST_LIGHT_RE", "BLOCK_LIGHT"),
    ("CONTRAST_TRIPLET_RE", "TRIPLET_RE"),
    ("CONTRAST_HEX_RE", "HEX_RE"),
    ("CONTRAST_SHORT_HEX_RE", "SHORT_HEX_RE"),
    ("CONTRAST_RGBA_RE", "RGBA_RE"),
    ("CONTRAST_VAR_RE", "VAR_RE"),
    ("CONTRAST_SIZE_RE", "SIZE_RE"),
    ("CONTRAST_KEYFRAME_SEL_RE", "KEYFRAME_SEL_RE"),
    ("CONTRAST_DISABLED_RE", "CONTRAST_DISABLED_RE"),
])
def test_parse_regexes_match(js, py, js_name, py_attr):
    """⑤ 十五条正则：认人键（切规则 / 取声明）、合成底（令牌 / 色值）、阈值分档（字号）、
    "这条 `opacity` 算不算活规则"（关键帧）与"这条规则算不算禁用形态"（`:disabled` / `.disabled`）
    全建立在它们上面。"""
    js_src = _norm(_js_regex(js, js_name))
    py_src = _norm(getattr(py, py_attr).pattern)
    assert js_src == py_src, (
        f"{js_name} 两侧不一致——两条腿会在解析面上分叉（腿绿而读数红）：\n"
        f"  JS     : {js_src!r}\n  Python : {py_src!r}"
    )


def _js_code_layers(js: str):
    """抠出 `CODE_LAYERS` 的三元组：`[(名字, alpha 或 None, 几何), …]`。"""
    m = re.search(r"const CODE_LAYERS = \[([\s\S]*?)\n\];", js)
    assert m, "守卫里找不到 `const CODE_LAYERS = [...];`"
    return [(n, None if a == "null" else float(a), g)
            for n, a, g in re.findall(r'\["([^"]+)",\s*(null|[0-9.]+),\s*"([a-z]+)"\]', m.group(1))]


def test_code_layers_match(js, py):
    """⑥ 代码页那**七层**底：名字 / alpha / **几何** 三元组两侧一致。

    几何（`behind` = 垫在字下 / `over` = 压在字上）是本轮补的口径——真像素实测出来的
    （`.scratch/code-contrast/probe-02-paint-order.mjs`）。两侧漂移就会出现"腿绿而读数红"：
    一边按"压在合成底上"算（乐观），一边按"字形也被染"算（真实），而两边各自内部都自洽。
    """
    js_rows = _js_code_layers(js)
    py_rows = [(n, None if a is None else float(a), g) for n, a, g in py.CODE_LAYERS]
    assert js_rows == py_rows, f"代码页那几层底两侧不一致：\n  JS {js_rows}\n  Python {py_rows}"
    assert len(js_rows) == 7, f"代码页的层数应为 7（实际 {len(js_rows)}）——层表被动过就同步这里"
    assert {g for _n, _a, g in js_rows} == {"behind", "over"}, "几何词表只能是 behind / over"


def test_code_hl_token_and_layer_recipe_match(js, py):
    """⑥′ 代码页高亮色令牌名 + 层配方正则：两侧同源（配方认不出名字 → 整排格子静默消失）。"""
    m = re.search(r'const CONTRAST_CODE_HL_TOKEN = "([^"]+)";', js)
    assert m, "守卫里找不到 `const CONTRAST_CODE_HL_TOKEN = \"...\";`"
    assert m.group(1) == py.CONTRAST_CODE_HL_TOKEN, "代码页高亮色令牌名两侧不一致"
    assert _norm(_js_regex(js, "CONTRAST_LAYER_RE")) == py.LAYER_RE.pattern, (
        "层配方正则两侧不一致（尾段既收角色名也收显式 alpha）：\n"
        f"  JS     : {_norm(_js_regex(js, 'CONTRAST_LAYER_RE'))!r}\n  Python : {py.LAYER_RE.pattern!r}"
    )


def _js_family_rows(js: str):
    """抠出 `CONTRAST_FAMILIES` 的行：`[(标签, 令牌选取, 底列表, 档位)]`。

    ⚠ 底列表有两种写法：字面数组（`["--bg", …]`）与 `CODE_LAYERS.map(([n]) => n)`
    （`--tok-*` 那族复用上面的层表，不另抄一份名字）。第二种要去查 `CODE_LAYERS`，
    否则会把箭头函数里的 `[n]` 当成底列表（本文件第一版就是这么错的）。
    """
    m = re.search(r"const CONTRAST_FAMILIES = \[([\s\S]*?)\n\];", js)
    assert m, "守卫里找不到 `const CONTRAST_FAMILIES = [...];`"
    layer_names = [n for n, _a, _g in _js_code_layers(js)]
    rows = []
    for row in re.split(r"\n\s*(?=\[\")", m.group(1)):   # 一行不够：有的族行折了行
        if not row.strip().startswith("["):
            continue
        items = re.findall(r'"((?:[^"\\]|\\.)*)"', row)
        if "CODE_LAYERS.map" in row:
            layers = list(layer_names)
        else:
            inner = re.findall(r"\[([^\[\]]*)\]", row)   # 行内嵌的底列表（行自己那层括号不算）
            assert inner, f"族行里找不到底列表：{row.strip()[:70]}"
            layers = re.findall(r'"([^"]+)"', inner[0])
        # 形状：[标签, 令牌选取, [底…], 档位, 理由] —— 档位是**倒数第二个**字符串（理由在最后）
        rows.append((items[0], items[1], layers, items[-2]))
    return rows


def test_families_match(js, py):
    """⑦ 两张族表：标签 / 令牌选取 / 底列表 / 阈值档位（**最坏格**就是按它们算的）。"""
    js_rows = _js_family_rows(js)
    py_rows = [(label, pick, list(layers), kind) for label, pick, layers, kind, _why in py.CONTRAST_FAMILIES]
    assert len(js_rows) == len(py_rows), f"族数两侧不一致：JS {len(js_rows)} / Python {len(py_rows)}"
    assert [r[0] for r in js_rows] == [r[0] for r in py_rows], "族标签两侧不一致"
    assert [r[1] for r in js_rows] == [r[1] for r in py_rows], "族的令牌选取两侧不一致"
    assert [r[2] for r in js_rows] == [r[2] for r in py_rows], "族的底列表两侧不一致"
    assert [r[3] for r in js_rows] == [r[3] for r in py_rows], "族的阈值档位（text / nontext）两侧不一致"


def test_family_kinds_match(js, py):
    """⑧ 阈值档位词表（`text` / `nontext`，令牌面多一档 `skip`）两侧一致。"""
    m = re.search(r"const CONTRAST_FAMILY_KINDS = \[([^\]]*)\];", js)
    assert m, "守卫里找不到 `const CONTRAST_FAMILY_KINDS = [...];`"
    js_kinds = re.findall(r'"([^"]+)"', m.group(1))
    assert js_kinds == list(py.CONTRAST_FAMILY_KINDS), (
        f"族表阈值档位两侧不一致：JS {js_kinds} / Python {list(py.CONTRAST_FAMILY_KINDS)}"
    )
    m = re.search(r"const CONTRAST_TOKEN_KINDS = \[\.\.\.CONTRAST_FAMILY_KINDS, ([^\]]*)\];", js)
    assert m, "守卫里找不到 `const CONTRAST_TOKEN_KINDS = [...CONTRAST_FAMILY_KINDS, ...];`"
    js_token_kinds = js_kinds + re.findall(r'"([^"]+)"', m.group(1))
    assert js_token_kinds == list(py.CONTRAST_TOKEN_KINDS), (
        f"令牌面阈值档位两侧不一致：JS {js_token_kinds} / Python {list(py.CONTRAST_TOKEN_KINDS)}"
    )


def _js_rows(js: str, name: str):
    """抠出守卫里一张表的数据行（与 `probe_lib._table_rows` 同一形态）。"""
    m = re.search(rf"const {name} = \[([\s\S]*?)\n\];", js)
    assert m, f"守卫里找不到 `const {name} = [...];`"
    rows = []
    for row in re.split(r"\n\s*(?=\[\")", m.group(1)):
        if not row.strip().startswith("["):
            continue
        rows.append(re.findall(r'"((?:[^"\\]|\\.)*)"', row))
    return rows


def test_token_bases_match(js, py):
    """⑨ **第三面**的令牌表：字面 / 假定底 / 阈值档位 三格必须逐条一致。

    这张表是"无底规则里的文字令牌"的唯一判据来源（01 单评审点名的覆盖缺口就是它补的）——
    两侧漂移会让"哪些令牌算过线"在两处给出不同答案。
    """
    m = re.search(r"const CONTRAST_TOKEN_BASES = \[([\s\S]*?)\n\];", js)
    assert m, "守卫里找不到 `const CONTRAST_TOKEN_BASES = [...];`"
    block = "\n".join(ln.split("//")[0].rstrip() for ln in m.group(1).splitlines())  # 注释里有引号，先剥
    js_rows = []
    for row in re.split(r"\n\s*(?=\[\")", block):
        if not row.strip().startswith("["):
            continue
        items = re.findall(r'"((?:[^"\\]|\\.)*)"', row)
        inner = re.findall(r"\[([^\[\]]*)\]", row)
        layers = re.findall(r'"([^"]+)"', inner[0]) if inner else []
        js_rows.append((items[0], layers, items[-2]))
    py_rows = [(lit, list(layers), kind) for lit, layers, kind, _why in py.CONTRAST_TOKEN_BASES]
    assert js_rows == py_rows, (
        "第三面的令牌表两侧不一致（字面 / 假定底 / 档位）：\n"
        + "\n".join(f"  JS {a}  vs  Python {b}" for a, b in zip(js_rows, py_rows) if a != b)
    )


def test_disabled_forms_register_matches(js, py):
    """⑫ **不可选形态 / 弱化的登记表**（工单 `disabled-forms/01`）：登记表逐条一致 + 类别表一致。

    为什么单列一条：这张表是判据②的**认人键**——两侧各写一份、只改一侧，
    就会出现"守卫说这条规则在册、探针算出来它不在册"（或反过来）的假账，
    而这种假账**两边各自内部都自洽**（腿绿而读数红，正是本文件存在的理由）。
    理由文本**不参与**比对（它是给人读的，两侧措辞可以不同），但必须非空。

    ⚠ 工单 `contrast-residue/04` 把判据②改成**全量驱动**，原"反向嫌疑词法"
    （`CONTRAST_DISABLED_HINTS` / `class_hint_hits` / `CONTRAST_HINT_VECTORS`）连同它的镜像腿
    **整条退役**——那张词法表不再参与任何判据，留着就是第二套口径。
    """
    js_rows = _js_rows(js, "CONTRAST_DISABLED_FORMS")
    assert js_rows, "守卫里解析不出 CONTRAST_DISABLED_FORMS 的行——格式变了"
    js_keys = [(r[0], r[1], r[2]) for r in js_rows]
    py_keys = [(scope, sel, kind) for scope, sel, kind, _why in py.CONTRAST_DISABLED_FORMS]
    assert js_keys == py_keys, (
        "不可选形态登记表两侧不一致（作用域 / 选择器 / 类别）：\n"
        + "\n".join(f"  JS {a}  vs  Python {b}" for a, b in zip(js_keys, py_keys) if a != b)
    )
    assert all(r[3].strip() for r in js_rows), "不可选形态登记项必须写理由（两侧都要有）"
    assert all(why.strip() for _s, _sel, _k, why in py.CONTRAST_DISABLED_FORMS), "同上（Python 侧）"

    m = re.search(r"const CONTRAST_DISABLED_FORM_KINDS = \[([\s\S]*?)\n\];", js)
    assert m, "守卫里找不到 `const CONTRAST_DISABLED_FORM_KINDS = [...];`"
    js_kinds = re.findall(r'\["([^"]+)"', m.group(1))
    assert js_kinds == [k for k, _why in py.CONTRAST_DISABLED_FORM_KINDS], (
        f"形态类别表两侧不一致：JS {js_kinds} / Python {[k for k, _ in py.CONTRAST_DISABLED_FORM_KINDS]}"
    )


def test_token_face_vectors_match(js, py):
    """⑭ **令牌解析面的行为向量表**（工单 `contrast-residue/01`）：

    本单把解析面从"只取**第一个** `:root`"改成"**合并全部定义块**（后者覆盖前者）"——
    改的是**行为**。镜像既有那十五条正则只比**正文**（flags 都比不到），挡不住
    "一边 `findall` 合并、一边还在 `search`"这种漂移；而它的表现正是本文件开头那段
    "腿绿而读数红"。所以两张表**两侧共用**：JS 侧由守卫自证（`tokenFaceProblems`），
    这里解析同一张表再喂给 Python 侧（`probe_lib.Tokens` / `probe_lib.defined_token_names`）。

    两张表：`CONTRAST_TOKEN_VALUE_VECTORS`（取值面：覆盖顺序 / 亮色只对亮色 / 沿用 `:root` /
    解不出仍是 `null`）与 `CONTRAST_TOKEN_DEFINED_VECTORS`（定义面：类作用域算定义、
    注释里的不算、带兜底的不算定义）。
    """
    def rows_of(name: str, row_re: str):
        m = re.search(rf"const {name} = \[([\s\S]*?)\n\];", js)
        assert m, f"守卫里找不到 `const {name} = [...];`"
        return re.findall(row_re, m.group(1), re.S)

    # 行数组里的每条 CSS 行：**单双引号都收**（`html[data-theme="light"]` 那一行用了单引号，
    # 里面自带 `]`——所以内层数组的收尾只能靠"后面紧跟主题/令牌那一格"来锚，别用 `[^\]]*`）。
    quoted = r'(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\')'

    def lines_of(inner: str) -> str:
        got = [a or b for a, b in re.findall(quoted, inner)]
        return "\n".join(s.replace('\\"', '"') for s in got)

    value_rows = rows_of("CONTRAST_TOKEN_VALUE_VECTORS", (
        r'\["((?:[^"\\]|\\.)*)",\s*\[([\s\S]*?)\],\s*"(\w+)",\s*"(--[a-z0-9-]+)",\s*'
        r'(null|"((?:[^"\\]|\\.)*)")\]'))
    assert len(value_rows) >= 4, f"取值向量表只解析出 {len(value_rows)} 条（格式变了？）"
    for why, lines_src, theme, token, want_raw, want_lit in value_rows:
        got = py.Tokens(lines_of(lines_src)).value(token, theme)
        got_s = None if got is None else ",".join(f"{c:g}" for c in got)
        want = None if want_raw == "null" else want_lit
        assert got_s == want, (
            f"令牌取值面两侧给出不同答案：{why} —— {token} @ {theme} "
            f"JS/表 {want} / Python {got_s}（合并全部块这个行为漂了）"
        )

    defined_rows = rows_of("CONTRAST_TOKEN_DEFINED_VECTORS", (
        r'\["((?:[^"\\]|\\.)*)",\s*\[([\s\S]*?)\],\s*"(--[a-z0-9-]+)",\s*(true|false)\]'))
    assert len(defined_rows) >= 3, f"定义面向量表只解析出 {len(defined_rows)} 条（格式变了？）"
    for why, lines_src, token, want in defined_rows:
        got = token in py.defined_token_names(lines_of(lines_src))
        assert got == (want == "true"), (
            f"定义面两侧给出不同答案：{why} —— {token} 表里要求 {want} / Python 判 {got}"
        )


def test_theme_coverage_match(js, py):
    """⑮ **腿⑪ 的颜色族亮色覆盖**（工单 `pin-type-contrast/04`）：三条口径两侧同源。

    这一腿判的是"**族**"（名字第一段）与"**成套**"（亮色块里有自己的定义）两件事，
    两侧只要有一边口径不同（按令牌算 / 合并两块算 / 把尺寸族也算进来），
    读数与闸门就会各答各的——所以正则、豁免表、**行为向量表**三件都钉住。
    """
    import re as _re

    for name in ("THEME_COLOR_VALUE_RE", "THEME_GRADIENT_RE"):
        js_rx = _norm(_js_regex(js, name))
        py_rx = _norm(getattr(py, name).pattern)
        assert js_rx == py_rx, (
            f"{name} 两侧不一致：「颜色令牌」的判定会分叉（腿绿而读数红）：\n"
            f"  JS     : {js_rx!r}\n  Python : {py_rx!r}"
        )
    # 豁免表（[族名, 理由]）：逐条一致（含"今天为空"这件事）
    m = _re.search(r"const THEME_INDEPENDENT_FAMILIES = \[([\s\S]*?)\n\];", js)
    assert m, "守卫里找不到 `const THEME_INDEPENDENT_FAMILIES = [...];`"
    block = "\n".join(ln.split("//")[0].rstrip() for ln in m.group(1).splitlines())
    js_rows = [list(r) for r in _re.findall(r'\["([^"]*)",\s*"([^"]*)"\]', block)]
    py_rows = [list(r) for r in py.THEME_INDEPENDENT_FAMILIES]
    assert js_rows == py_rows, f"亮色覆盖豁免表两侧不一致：JS {js_rows} / Python {py_rows}"
    # 行为向量表：说明 / 行数组 / 豁免族 / 期望条数 四格逐条一致，且两侧都算得出同样的结果
    m = _re.search(r"const THEME_COVERAGE_VECTORS = \[([\s\S]*?)\n\];", js)
    assert m, "守卫里找不到 `const THEME_COVERAGE_VECTORS = [...];`"
    # ⚠ 行数组里**自己带方括号**（`html[data-theme="light"]`），所以内层用非贪婪 `[\s\S]*?`
    #   锚到"后面紧跟着豁免串 + 数字"，别用 `[^\]]*`（那会在第一个 `]` 处断掉）。
    js_vec = _re.findall(
        r'\["((?:[^"\\]|\\.)*)",\s*\[([\s\S]*?)\],\s*"([^"]*)",\s*(\d+)\]', m.group(1))
    quoted = r'(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\')'
    js_vec = [(why, [a or b for a, b in _re.findall(quoted, lines)], exempt, want)
              for why, lines, exempt, want in js_vec]
    py_vec = [(why, list(lines), exempt, str(want))
              for why, lines, exempt, want in py.THEME_COVERAGE_VECTORS]
    assert len(js_vec) >= 5, f"亮色覆盖向量表只解析出 {len(js_vec)} 条（格式变了？）"
    assert [v[0] for v in js_vec] == [v[0] for v in py_vec], "向量表的说明列两侧不一致"
    assert [v[1] for v in js_vec] == [v[1] for v in py_vec], "向量表的 CSS 行数组两侧不一致"
    assert [v[2] for v in js_vec] == [v[2] for v in py_vec], "向量表的豁免列两侧不一致"
    assert [v[3] for v in js_vec] == [v[3] for v in py_vec], "向量表的期望条数两侧不一致"
    for why, lines, exempt, want in py_vec:
        got = py.theme_coverage_problems("\n".join(lines),
                                         [(exempt, "两侧同源自证")] if exempt else [])
        assert len(got) == int(want), (
            f"亮色覆盖向量表在 Python 侧算出不同答案：{why} —— 期望 {want} 条，实际 {len(got)} 条"
            f"（{'；'.join(got) or '无'}）"
        )


def test_gradient_ends_match(js, py):
    """⑪ **渐变端点**表：主题 / 前景令牌 / 底列表 三格逐条一致（02 单补的盲区检查）。"""
    m = re.search(r"const CONTRAST_GRADIENT_ENDS = \[([\s\S]*?)\n\];", js)
    assert m, "守卫里找不到 `const CONTRAST_GRADIENT_ENDS = [...];`"
    block = "\n".join(ln.split("//")[0].rstrip() for ln in m.group(1).splitlines())
    js_rows = []
    for row in re.split(r"\n\s*(?=\[\")", block):
        if not row.strip().startswith("["):
            continue
        items = re.findall(r'"((?:[^"\\]|\\.)*)"', row)
        inner = re.findall(r"\[([^\[\]]*)\]", row)
        layers = re.findall(r'"([^"]+)"', inner[0]) if inner else []
        js_rows.append((items[0], items[1], layers))
    py_rows = [(t, fg, list(layers)) for t, fg, layers, _why in py.CONTRAST_GRADIENT_ENDS]
    assert js_rows == py_rows, (
        "渐变端点表两侧不一致：\n"
        + "\n".join(f"  JS {a}  vs  Python {b}" for a, b in zip(js_rows, py_rows) if a != b)
    )


def test_family_cell_count_freeze_matches_python(js, py):
    """⑦′ 守卫里冻结的**族面总格数**必须等于 Python 侧现在算出来的那一份。

    为什么单列一条：族面只把**最坏格**纳入对账——从 `CODE_LAYERS` 或某条族里摘掉一层，
    最坏格会**变好**、腿照样绿。冻结值是这个"少算一排"的唯一防线，而它自己也要有人看着
    （改了两侧任一张表却忘了改它 → 这里红）。
    """
    m = re.search(r"const CONTRAST_FAMILY_CELL_COUNT = ([0-9]+);", js)
    assert m, "守卫里找不到 `const CONTRAST_FAMILY_CELL_COUNT = ...;`"
    cells = py.contrast_family_cells(py.read_page())
    assert int(m.group(1)) == len(cells), (
        f"冻结的族面格数 {m.group(1)} ≠ 现算 {len(cells)}——两张表里有一侧被改过，"
        "同步 CONTRAST_FAMILY_CELL_COUNT 并在票尾写清改了哪张表"
    )
    per_family = {}
    for c in cells:
        per_family[c["label"]] = per_family.get(c["label"], 0) + 1
    assert len(py.CONTRAST_FAMILIES) == 13, (
        f"族数应为 13（实际 {len(py.CONTRAST_FAMILIES)}）——"
        "5 条老族 + 工单 pin-type-contrast/02 的 8 条引脚族（一族一行，非文字档 3:1）"
    )
    assert per_family.get("--tok-* × 代码底（含 5 层高亮 + 错误行）") == 10 * 7 * 2, (
        f"--tok-* 族应有 10 × 7 × 2 = 140 格（实际 {per_family.get('--tok-* × 代码底（含 5 层高亮 + 错误行）')}）"
    )
    # 禁用态那族（工单 code-contrast/03）：1 令牌（--muted）× 2 底（panel-2 / panel）× 2 主题。
    assert per_family.get("--muted × 禁用态底（panel-2 / panel）") == 1 * 2 * 2, (
        "禁用态族应有 1 × 2 × 2 = 4 格（实际 "
        f"{per_family.get('--muted × 禁用态底（panel-2 / panel）')}）——"
        "少一格就等于「禁用态坐在另一种底上」没人看（那是本单的判据面）"
    )
    # 引脚族（工单 pin-type-contrast/02）：8 族 × 1 令牌 × 1 底（--panel-2）× 2 主题。
    # 那八族的文字档走**令牌面**（一族一行、三条假定底 = 三种真实几何），不重复进族面。
    for _fam in ("gpio", "pwm", "enc", "uart", "i2c", "spi", "adc", "exti"):
        _label = f"--pin-{_fam} 色点 / 焊盘描边"
        assert per_family.get(_label) == 1 * 1 * 2, (
            f"引脚族「{_label}」应有 1 × 1 × 2 = 2 格（实际 {per_family.get(_label)}）——"
            "少一格就等于「色点坐在另一种底上」没人看"
        )


def test_tok_worst_freeze_matches_python(js, py):
    """⑦″ `--tok-*` 族的**最坏格冻结值**必须等于 Python 侧现在算出来的那一对（±0.01）。

    它与 `CONTRAST_PAIR_COUNT` / `CONTRAST_FAMILY_CELL_COUNT` **不是同一物种**：那两个是**形状数**
    （表的结构对不对），这一对是**读数快照**——02 单把债还清之后，族面不再有 `debt` 行可对账，
    "少一层 / 几何写反 / 强度回退"这类坏法只会让最坏格**变好**，`contrastProblems` 反而无话可说；
    这一对就是那道闸，所以它自己也要有人现算复核（Standards 轴评审点名）。
    """
    m = re.search(r"const CONTRAST_TOK_WORST = \{([^}]*)\};", js)
    assert m, "守卫里找不到 `const CONTRAST_TOK_WORST = {...};`"
    js_vals = {k: float(v) for k, v in re.findall(r"([a-z]+):\s*([0-9.]+)", m.group(1))}
    assert set(js_vals) == {"dark", "light"}, f"CONTRAST_TOK_WORST 的键应为 dark / light：{js_vals}"
    text = py.read_page()
    tok = py.Tokens(text)
    cells = [c for c in py.contrast_family_cells(text, tok) if c["label"].startswith("--tok-")]
    for theme in ("dark", "light"):
        sub = [c for c in cells if c["theme"] == theme]
        assert sub, f"--tok-* 族在 {theme} 下一格都没有——判据在空转"
        worst = min(sub, key=lambda c: c["ratio"])
        assert abs(js_vals[theme] - worst["ratio"]) <= 0.01, (
            f"{theme} 最坏格冻结 {js_vals[theme]} ≠ Python 现算 {worst['ratio']:.3f}"
            f"（{worst['token']} on {worst['layer']}）——层表/族表/几何/令牌值有一处被改过；"
            "确实该改就两侧一起改并在票尾写清"
        )


def test_pair_count_freeze_matches_python(js, py):
    """⑦‴ 守卫里冻结的**机械面配对数**必须等于 Python 侧现在抽出来的那一份。

    与 ⑦′（族面格数）同一物种、同一条理由：`CONTRAST_PAIR_COUNT` 拦的是"抽取面变了、判据在空转"，
    而抽取面本身有**两份实现**（JS 的 `contrastPairsFromStylesheet` / Python 的 `contrast_pairs`）。
    两侧的正则虽由 ⑤ 钉住，遍历与"哪条规则算一对"的判断仍是各自写的——只改一侧，
    就会出现"守卫说 394、探针说 393"这种腿绿而读数红的账（工单 `disabled-forms/01` 把 392 改成 394 时立的）。
    """
    m = re.search(r"const CONTRAST_PAIR_COUNT = ([0-9]+);", js)
    assert m, "守卫里找不到 `const CONTRAST_PAIR_COUNT = ...;`"
    pairs = py.contrast_pairs(py.read_page())
    assert int(m.group(1)) == len(pairs), (
        f"冻结的机械面配对数 {m.group(1)} ≠ Python 现算 {len(pairs)}——"
        "要么同步 CONTRAST_PAIR_COUNT（并在票尾写清改了哪条规则），要么两侧的抽取逻辑漂了"
    )


def test_exception_table_matches_generator(js, py):
    """⑩ 守卫里那张例外表必须等于生成器**现在**算出来的那张（`--check` 的同源断言）。

    为什么放进 pytest 而不是只留一条命令（Standards 轴评审点名"`--check` 无人调用"）：
    命令靠人记得跑，测试是闸门。它挡的坏法是"改了生成器的口径、忘了重写表"——
    那种漂移**任何一面的腿都不会红**（表与盘上仍然自洽，只是表不再是生成物的样子）。
    """
    import importlib.util

    gen_path = ROOT / ".scratch" / "light-contrast" / "generate-01-contrast-register.py"
    assert gen_path.is_file(), f"生成器不在：{gen_path}"
    spec = importlib.util.spec_from_file_location("_contrast_register_gen", gen_path)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    rows = gen.build_rows()
    want = [ln.strip() for ln in gen.render(rows).strip().splitlines() if ln.strip()]
    got = [ln.strip() for ln in py.load_exceptions_raw().strip().splitlines() if ln.strip()]
    assert got == want, (
        "守卫里的例外表与生成器现在算出来的不一致——跑 "
        "`python .scratch/light-contrast/generate-01-contrast-register.py --write` 重写，"
        "并复核差在哪几条"
    )
