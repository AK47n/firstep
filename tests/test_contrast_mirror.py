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

九组（口径的每一块都点到）：

1. `CONTRAST_THRESHOLDS`（小字 / 大字两档）；
2. `LARGE_TEXT`（24px / 18.66px+bold 那三个常量）；
3. `CONTRAST_LUM`（亮度公式的九个数：255 / 0.03928 / 12.92 / 0.055 / 1.055 / 2.4 / 三通道系数）；
4. `CONTRAST_RATIO_OFFSET` 与 `CONTRAST_BASE_TOKEN`（合成基色 = `--panel` 这条口径本身）；
5. **十三条解析正则**（`<style>` 块 / 剥注释 / 切规则 / 取声明 / 令牌 / 两个主题块 / 三元组 /
   两种十六进制 / rgba / var（含兜底）/ 字号）——认人键、合成底与阈值分档全建立在它们上面；
6. `CODE_LAYERS`（代码页那五层底的名字与 alpha）；
7. `CONTRAST_FAMILIES`（族表的标签 / 令牌选取 / 底列表 / 阈值档位）；
8. `CONTRAST_FAMILY_KINDS` 与 `CONTRAST_TOKEN_KINDS`（阈值档位词表）；
9. `CONTRAST_TOKEN_BASES`（**第三面**：无底规则里的文字令牌 + 假定底 + 档位）——
   两张表今天各有一份副本，任何一侧单独改都是漂移。
   再加一条 **`--check` 的同源断言**：守卫里那张例外表必须等于生成器**现在**算出来的那张。

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
])
def test_parse_regexes_match(js, py, js_name, py_attr):
    """⑤ 十三条解析正则：认人键（切规则 / 取声明）、合成底（令牌 / 色值）与阈值分档（字号）全建立在它们上面。"""
    js_src = _norm(_js_regex(js, js_name))
    py_src = _norm(getattr(py, py_attr).pattern)
    assert js_src == py_src, (
        f"{js_name} 两侧不一致——两条腿会在解析面上分叉（腿绿而读数红）：\n"
        f"  JS     : {js_src!r}\n  Python : {py_src!r}"
    )


def test_code_layers_match(js, py):
    """⑥ 代码页那五层底：名字与 alpha 两侧一致（`--tok-*` 族的最坏格靠它算）。"""
    m = re.search(r"const CODE_LAYERS = \[([\s\S]*?)\n\];", js)
    assert m, "守卫里找不到 `const CODE_LAYERS = [...];`"
    js_rows = [(n, None if a == "null" else float(a))
               for n, a in re.findall(r'\["([^"]+)",\s*(null|[0-9.]+)\]', m.group(1))]
    py_rows = [(n, None if a is None else float(a)) for n, a in py.CODE_LAYERS]
    assert js_rows == py_rows, f"代码页那几层底两侧不一致：\n  JS {js_rows}\n  Python {py_rows}"


def _js_family_rows(js: str):
    """抠出 `CONTRAST_FAMILIES` 的行：`[(标签, 令牌选取, 底列表, 档位)]`。

    ⚠ 底列表有两种写法：字面数组（`["--bg", …]`）与 `CODE_LAYERS.map(([n]) => n)`
    （`--tok-*` 那族复用上面的层表，不另抄一份名字）。第二种要去查 `CODE_LAYERS`，
    否则会把箭头函数里的 `[n]` 当成底列表（本文件第一版就是这么错的）。
    """
    m = re.search(r"const CONTRAST_FAMILIES = \[([\s\S]*?)\n\];", js)
    assert m, "守卫里找不到 `const CONTRAST_FAMILIES = [...];`"
    code_layers = re.search(r"const CODE_LAYERS = \[([\s\S]*?)\n\];", js)
    assert code_layers, "守卫里找不到 `const CODE_LAYERS = [...];`"
    layer_names = [n for n, _a in re.findall(r'\["([^"]+)",\s*(null|[0-9.]+)\]', code_layers.group(1))]
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
