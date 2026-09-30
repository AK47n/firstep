"""浅色调色板轮的**公共骨架**：口径（令牌 / 亮度 / 合成 / 规则切分 / 取色对）+ 注入-复原工具。

## 为什么有这个文件

这一轮的判据在**两个语言里各跑一半**：

| | 住哪 | 谁在跑 | 管什么 |
|---|---|---|---|
| **JS** | `tests/js/css-tokens.test.mjs` 的腿⑧ | 前端门禁 | 盘上 ↔ 例外表双向对账（闸门） |
| **Python** | 本文件 | 探针 / 生成器 | 把比值**量出来**、把例外表**生成出来** |

两侧的**口径**（阈值两档、大字判据、亮度公式、合成公式、合成基色）是同一份数据在两个语言里
各写了一遍——漂移就会造出"**腿绿而读数红**"这类最难查的假账。故：
**常量集中在本文件顶部**，JS 侧同样集中（`CONTRAST_*`），由 `tests/test_contrast_mirror.py` 逐项对拍。
探针不许自己另抄一份公式（`probe-01` 已改为 import 本文件）。

## 口径（三句话）

1. **底 = 元素自己那层背景合成后的颜色**：`rgba` 淡底要叠到祖先不透明底上，
   合成基色 = `--panel`（卡片）。**不是**祖先底本身——上一轮那三个乐观数（6.11 / 5.19 / 3.39）
   就是"跳过淡底直接取祖先底"量出来的（本轮更正，见 `spec.md` 问题陈述一）。
2. **阈值按规则自己的字号/字重定**：≥24px，或 ≥18.66px 且 bold ⇒ 3.0；否则 4.5。
   未声明 = 继承 body 14px = 小字。
3. **认人键 = (主题, 剥注释后的选择器)**：选择器不带前导块注释、空白归一
   （与描边那轮的认人键同一条纪律）。
"""

from __future__ import annotations

import re
import sys
from math import floor as _floor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"

sys.path.insert(0, str(ROOT / ".scratch" / "ui-density-sitewide"))  # 探针们的公共入口仍在那边

try:  # 探针自己 reconfigure，GBK 控制台下也不乱码
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

# ===========================================================================
# 口径常量（**单源**：JS 侧同名常量必须与这里逐项相同，镜像守卫钉住）
# ===========================================================================

CONTRAST_THRESHOLDS = {"small": 4.5, "large": 3.0}
LARGE_TEXT = {"px": 24, "bold_px": 18.66, "bold_weight": 700}
CONTRAST_LUM = {
    "scale": 255,
    "lin_split": 0.03928,
    "lin_div": 12.92,
    "gamma_add": 0.055,
    "gamma_div": 1.055,
    "gamma_exp": 2.4,
    "w_r": 0.2126,
    "w_g": 0.7152,
    "w_b": 0.0722,
}
CONTRAST_RATIO_OFFSET = 0.05
CONTRAST_BASE_TOKEN = "--panel"

#: 例外**两类**（与守卫 `CONTRAST_KINDS` 逐项同源）。`text` / `nontext` 是**阈值档位**
#: （在 `CONTRAST_FAMILY_KINDS` 与 `CONTRAST_TOKEN_BASES` 里选），不是"允许不达标"的理由。
CONTRAST_KINDS = [
    ("debt", "明确记账的不达标：本轮不修，但现算值必须与冻结值一致（不许静默恶化）"),
    ("skip", "静态口径不适用（::selection 这类反白块 / 底在有色父元素上）：登记理由，不参与比值判据"),
]
#: 阈值档位（族表与令牌表都用它选阈值）；令牌面多一档 `skip`（底不在静态射程内）。
CONTRAST_FAMILY_KINDS = ["text", "nontext"]
CONTRAST_TOKEN_KINDS = CONTRAST_FAMILY_KINDS + ["skip"]

#: 代码页高亮色的 **rgb 令牌**（配方 `<底>+hl.<角色>` 用它）。
#: **与 JS 守卫的 `CONTRAST_CODE_HL_TOKEN` 同源**（镜像守卫钉住）。
CONTRAST_CODE_HL_TOKEN = "--code-hl-rgb"

#: 代码页上「文字会压到的底」：`(名字, alpha, 几何)`。
#: **与 JS 守卫的 `CODE_LAYERS` 逐项同源**（镜像守卫钉住）。
#:
#: 名字用**语义**（`hl.选区`）而不是 alpha 数字——改 alpha 不该动认人键。
#: `alpha = None`：`--code-bg` 那条是底本身；`+--danger-dim` 那条用令牌自带的 alpha。
#:
#: **几何**（`behind` = 垫在字下 / `over` = 压在字上）是本轮补的：
#: `.scratch/code-contrast/probe-02-paint-order.mjs` 用真 Chromium 像素实测——选区（textarea，
#: z-index 1）与标记层（`.code-marks`，z-index 0）**都画在 `.code-hl` 文字之上**，
#: 半透明色把**字形本身**也染了；只有行元素自己那两层（`.active` / `.flash`）垫在字下。
#: `over` 层的判据因此是 `contrast(over(tint,fg), over(tint,base))`——比"压在合成底上"更严。
CODE_LAYERS = [
    ("--code-bg", None, "behind"),
    ("--code-bg+hl.当前行", 0.07, "behind"),
    ("--code-bg+hl.词命中", 0.12, "over"),
    ("--code-bg+hl.搜索命中", 0.18, "over"),
    ("--code-bg+hl.选区", 0.20, "over"),
    ("--code-bg+hl.当前命中", 0.24, "over"),
    ("--code-bg+--danger-dim", None, "over"),
]

#: 代码页那几层底的**名字**（JS 侧族表用 `CODE_LAYERS.map(([n]) => n)` 复用，不另抄一份）
CODE_LAYERS_NAMES = [n for n, _a, _g in CODE_LAYERS]

#: 层配方：`<底>+hl.<角色>` / `<底>+<rgba 令牌>`（**与 JS 的 `CONTRAST_LAYER_RE` 逐字同源**）。
#: 尾段是**角色名**（`选区` / `当前命中`…），只作可读性——**alpha 一律查层表**，
#: 名字里写数字不算数（要临时改档就换层表：`layer_colors(..., layers=...)`）。
LAYER_RE = re.compile(r"^(--[a-z0-9-]+)\+(hl|--[a-z0-9-]+)(?:\..+)?$")

#: **第三面**：无底规则（`color:` 有、底在基类或祖先）里当文字色用的令牌。
#: 形状 `[令牌字面, 假定底列表, 阈值档位, 理由]`；空底列表 = 静态判不了（登记理由后跳过判据）。
#: **与 JS 守卫的 `CONTRAST_TOKEN_BASES` 逐项同源**（镜像守卫钉住）。
CONTRAST_TOKEN_BASES = [
    ("var(--text)", ["--bg", "--panel", "--panel-2"], "text", "正文色：三种底都过"),
    ("var(--accent-text)", ["--bg", "--panel", "--panel-2"], "text",
     "accent 当文字色：浅色 2.99——02 单改走 --accent-text"),
    ("var(--on-accent)", ["--accent"], "text", "实心 accent 块上的字（底就是 accent）"),
    ("var(--muted)", ["--bg", "--panel", "--panel-2"], "text", "次要说明色"),
    ("var(--danger-text)", ["--bg", "--panel", "--panel-2"], "text", "危险语义色当文字"),
    ("var(--danger-text, #e5484d)", ["--bg", "--panel", "--panel-2"], "text",
     "带兜底值的 var()：兜底不生效（--danger 存在），按 --danger 算"),
    ("var(--ok-text)", ["--bg", "--panel", "--panel-2"], "text",
     "完成语义色当文字（--ok 与 --ok-bright 两族共用这一档——02 单合并）"),
    ("var(--warn-text)", ["--bg", "--panel", "--panel-2"], "text", "警示语义色当文字"),
    ("var(--info-text)", ["--bg", "--panel", "--panel-2"], "text", "信息语义色当文字"),
    ("var(--code-text)", ["--code-bg"], "text", "代码正文色（底是代码底）"),
    ("#fff", ["--ok", "--warn", "--danger"], "text",
     "语义实心底上的白字（.env-badge）：底不是卡片，而是那三种实心语义色"),
    ("var(--on-accent-deep)", ["--accent"], "text", "实心 accent 上的深字（步骤点）"),
    ("var(--border-strong)", ["--bg", "--panel"], "nontext",
     "装饰分隔符 ·（描边色当字形用）：非文字档 3:1"),
    ("var(--accent-dim)", ["--code-bg"], "nontext",
     "代码 gutter 的折叠占位字形（装饰性，alpha .12 叠在代码底上）"),
    ("inherit", [], "skip", "`color: inherit` 不是取色：不参与比值判据"),
    ("transparent", [], "skip", "透明：不参与比值判据"),
    ("var(--fg)", [], "skip",
     "**未定义的令牌（笔误）**：浏览器按 inherit 处理，实际渲染是继承色——本轮不改观感，记为待办"),
]
#: `--tok-*` 那十个：底是代码页那五层，已由族面逐格算过（这里登记为"已覆盖"，不重复判）
for _t in ("com", "str", "pre", "kw", "num", "tag", "attr", "val", "fn", "const"):
    CONTRAST_TOKEN_BASES.append((f"var(--tok-{_t})", [], "skip", "已由族面 `--tok-* × 代码底` 覆盖"))
#: 族表：机械抽取**抓不到**的已知族（底来自祖先或图形属性）。
#: 形状 `[标签, 令牌选取, 底列表, 阈值档位, 理由]`；令牌选取 = 前缀，或 `=` 开头的精确令牌名。
#: **与 JS 守卫的 `CONTRAST_FAMILIES` 逐项同源**（镜像守卫钉住）。
CONTRAST_FAMILIES = [
    ("--tok-* × 代码底（含 5 层高亮 + 错误行）", "--tok-", list(CODE_LAYERS_NAMES), "text",
     "语法高亮族：十个令牌 × 七层，**几何感知**（压在字上的层连字形一起染）。见 probe-00 的整张矩阵"),
    ("--code-text × 括号彩虹底（8 色）", "=--code-text",
     [f"--code-bg+--bracket-rainbow-{i}" for i in range(8)], "text",
     "括号彩虹只压括号字形（括号在语法高亮里没有 token 类，字色是 --code-text）——实测全过，登记为覆盖"),
    ("--accent-text 焦点环 / 定位环", "=--accent-text", ["--bg", "--panel", "--panel-2"], "nontext",
     "键盘焦点环与定位环（03 单提到 3:1 以上）：看不见焦点环 = 键盘用户找不到焦点"),
    ("--accent 控件描边 / 语义左条", "=--accent", ["--bg", "--panel", "--panel-2"], "nontext",
     "控件普通描边与语义左条：装饰性强于信息性，**大面积改深会动整页观感**——记债不修（03 单的判断）"),
]


# ===========================================================================
# 规则切分（对比度这一面的口径，**与 JS 侧逐字同源**）
#
# ⚠ 与描边那一面**故意不同**：这边先把 `<style>` 块里的 CSS 注释剥掉再切规则。
# 为什么：
#   · 注释里含 `{` / `}` 会把朴素切分带偏，切出"选择器是一段中文注释"的假规则
#     （实测 `.param-card-head .param-label` 那一带的注释就制造过一条）；
#   · 注释正文里常出现 `color: …` 这类**伪声明**，剥掉它才不会把散文当判据；
#   · 描边那面的认人键建立在"不剥注释"的历史口径上（115 条登记簿），故那边不动。
# 剥注释同时让两侧解析面一致：**都只吃 `<style>` 块**（JS 侧若吃整个文件，
# `<head>` 那 14 段内联脚本的 `{}` 也会配成规则，两侧就对不上了）。
# ===========================================================================

STYLE_BLOCK_RE = re.compile(r"<style>(.*?)</style>", re.S)
CSS_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)


def contrast_style_text(text: str) -> str:
    """对比度面的解析面 = `<style>` 块内容，**注释已剥**（与 JS `contrastCss()` 同一变换）。"""
    m = STYLE_BLOCK_RE.search(text)
    if not m:
        raise SystemExit("页面里找不到 `<style>` 块——格式变了，别拿空表当读数")
    return CSS_COMMENT_RE.sub(" ", m.group(1))


def css_rules(css: str):
    """切规则：`[(选择器, 声明体)]`，选择器空白归一（与 JS `cssRules` 同一正则）。"""
    return [(" ".join(m.group(1).split()), m.group(2)) for m in RULE_RE.finditer(css)]


# ===========================================================================
# 颜色数学（与 JS 侧同一份公式，常量全部走 CONTRAST_LUM）
# ===========================================================================

def srgb_to_lin(v: float) -> float:
    s = v / CONTRAST_LUM["scale"]
    if s <= CONTRAST_LUM["lin_split"]:
        return s / CONTRAST_LUM["lin_div"]
    return ((s + CONTRAST_LUM["gamma_add"]) / CONTRAST_LUM["gamma_div"]) ** CONTRAST_LUM["gamma_exp"]


def luminance(rgb) -> float:
    r, g, b = (srgb_to_lin(c) for c in rgb[:3])
    return CONTRAST_LUM["w_r"] * r + CONTRAST_LUM["w_g"] * g + CONTRAST_LUM["w_b"] * b


def contrast(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + CONTRAST_RATIO_OFFSET) / (lo + CONTRAST_RATIO_OFFSET)


def over(fg, bg):
    """带 alpha 的前景叠到不透明底上。

    ⚠ 取整**必须与 JS 侧的 `Math.round` 一致**：Python 内建 `round()` 是银行家舍入
    （`.5` 向偶数靠），JS 是"半上"（`.5` 向上）——在 `.5` 那一格会分叉，
    而分叉出来的差会以"腿绿而读数红"的形式出现（双轴评审点过这条）。
    """
    if len(fg) < 4 or fg[3] >= 1:
        return tuple(fg[:3])
    a = fg[3]
    return tuple(int(_floor(v + 0.5)) for v in (a * fg[i] + (1 - a) * bg[i] for i in range(3)))


def hexs(rgb) -> str:
    return "#%02x%02x%02x" % tuple(rgb[:3])


# ===========================================================================
# 令牌解析（`:root` = 暗色；`html[data-theme="light"]` = 亮色覆盖）
# ===========================================================================

BLOCK_ROOT = re.compile(r"\n {2}:root \{([\s\S]*?)\n {2}\}", re.S)
BLOCK_LIGHT = re.compile(r'\n {2}html\[data-theme="light"\] \{([\s\S]*?)\n {2}\}', re.S)
TOKEN_RE = re.compile(r"(--[a-z0-9-]+):\s*([^;]+);")
TRIPLET_RE = re.compile(r"^(\d+)\s*,\s*(\d+)\s*,\s*(\d+)$")
HEX_RE = re.compile(r"^#([0-9a-fA-F]{6})$")
SHORT_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3})$")
RGBA_RE = re.compile(r"^rgba?\(([\s\S]*)\)$", re.S)
VAR_RE = re.compile(r"^var\((--[a-z0-9-]+)(?:\s*,[^)]*)?\)$")  # 允许 `var(--x, 兜底)`：兜底不参与解析


class Tokens:
    """两主题的令牌表（亮色未覆盖的键沿用 `:root`，与浏览器层叠同语义）。"""

    def __init__(self, text: str):
        self.raw: dict[str, dict[str, str]] = {"dark": {}, "light": {}}
        m = BLOCK_ROOT.search(text)
        if not m:
            raise SystemExit("解析不到 `:root {` 令牌块——格式变了，别拿空表当读数")
        for name, val in TOKEN_RE.findall(m.group(1)):
            self.raw["dark"][name] = val.strip()
        m = BLOCK_LIGHT.search(text)
        if not m:
            raise SystemExit('解析不到 `html[data-theme="light"] {` 令牌块——格式变了')
        for name, val in TOKEN_RE.findall(m.group(1)):
            self.raw["light"][name] = val.strip()

    def names(self) -> list[str]:
        return list(self.raw["dark"])

    def value(self, name: str, theme: str, seen=()):
        """令牌 → RGBA 四元组；解不出返回 None（**不猜**）。"""
        if name in seen:
            return None
        raw = self.raw[theme].get(name)
        if raw is None:
            raw = self.raw["dark"].get(name)
        if raw is None:
            return None
        return self.parse(raw, theme, seen + (name,))

    def parse(self, raw: str, theme: str, seen=()):
        raw = raw.strip()
        m = TRIPLET_RE.match(raw)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)), 1.0)
        m = HEX_RE.match(raw)
        if m:
            h = m.group(1)
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
        m = SHORT_HEX_RE.match(raw)
        if m:
            h = m.group(1)
            return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 1.0)
        m = VAR_RE.match(raw)
        if m:
            return self.value(m.group(1), theme, seen)
        m = RGBA_RE.match(raw)
        if m:
            parts = [p.strip() for p in m.group(1).split(",")]
            nums: list[float] = []
            for p in parts:
                if p.startswith("var("):
                    inner = p[4:-1].strip()
                    raw_inner = (self.raw[theme].get(inner)
                                 or self.raw["dark"].get(inner, "")).strip()
                    trip = TRIPLET_RE.match(raw_inner)
                    if trip:  # `rgba(var(--accent-rgb), .12)`：通道三元组直接摊开
                        nums.extend(float(trip.group(i)) for i in (1, 2, 3))
                        continue
                    sub = self.value(inner, theme, seen)
                    if sub is None:
                        return None
                    nums.append(float(sub[0]))
                else:
                    nums.append(float(p))
            if len(nums) == 3:
                nums.append(1.0)
            if len(nums) < 4:
                return None
            return (int(nums[0]), int(nums[1]), int(nums[2]), float(nums[3]))
        return None


# ===========================================================================
# 规则切分与取色对
# ===========================================================================

DECL_RE = re.compile(r"(?:^|;)\s*([a-z-]+)\s*:\s*([^;]+)")
SIZE_RE = re.compile(r"([0-9.]+)px")
DEAD_BG = ("none", "transparent", "inherit")


def decls(body: str) -> dict[str, str]:
    """规则声明体 → {属性: 值}（**首次出现优先**，与 JS 侧 `firstDecl` 同语义）。"""
    out: dict[str, str] = {}
    for name, val in DECL_RE.findall(body):
        out.setdefault(name.strip(), val.strip())
    return out


def bg_of_rule(d: dict[str, str]):
    """规则声明的底（渐变 / none / transparent / url → None，表示"底不在这条规则里"）。"""
    raw = d.get("background-color") or d.get("background")
    if not raw or raw in DEAD_BG or "gradient" in raw or "url(" in raw:
        return None
    return raw


def is_large(d: dict[str, str]) -> bool:
    m = SIZE_RE.search(d.get("font-size", ""))
    px = float(m.group(1)) if m else 14.0
    if px >= LARGE_TEXT["px"]:
        return True
    weight = d.get("font-weight", "")
    bold = weight in ("bold", "bolder") or (weight.isdigit()
                                           and int(weight) >= LARGE_TEXT["bold_weight"])
    return px >= LARGE_TEXT["bold_px"] and bold


class Pair:
    """一条「文字色 × 底」配对（机械抽取的产物）。"""

    __slots__ = ("theme", "selector", "fg_raw", "bg_raw", "fg_hex", "bg_hex",
                 "ratio", "need", "kind", "large")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def key(self):
        return (self.theme, self.selector)

    def __repr__(self):
        return (f"<Pair {self.theme} {self.selector} {self.fg_hex} on {self.bg_hex} "
                f"{self.ratio:.2f}/{self.need}>")


def base_of(tok: Tokens, theme: str):
    v = tok.value(CONTRAST_BASE_TOKEN, theme)
    if v is None:
        raise SystemExit(f"合成基色 {CONTRAST_BASE_TOKEN} 解不出来（{theme}）——口径变了")
    return v[:3]


def contrast_pairs(text: str, tok: Tokens | None = None):
    """机械抽取：同一条规则里既有 `color:` 又有 `background:` → 两主题各一条配对。

    底的口径 = **元素自己那层背景合成到 `--panel` 上**（见文件头第 1 条）。
    解析面 = 剥注释的 `<style>` 块（见 `contrast_style_text`）。
    """
    tok = tok or Tokens(text)
    out: list[Pair] = []
    for sel, body in css_rules(contrast_style_text(text)):
        d = decls(body)
        if "color" not in d:
            continue
        bg_raw = bg_of_rule(d)
        if bg_raw is None:
            continue
        for theme in ("dark", "light"):
            fg = tok.parse(d["color"], theme)
            bg = tok.parse(bg_raw, theme)
            if fg is None or bg is None:
                continue
            base = base_of(tok, theme)
            bg_eff = over(bg, base)
            fg_eff = over(fg, bg_eff)
            large = is_large(d)
            out.append(Pair(theme=theme, selector=sel, fg_raw=d["color"],
                            bg_raw=bg_raw, fg_hex=hexs(fg_eff), bg_hex=hexs(bg_eff),
                            ratio=contrast(fg_eff, bg_eff),
                            need=CONTRAST_THRESHOLDS["large"] if large
                            else CONTRAST_THRESHOLDS["small"],
                            kind="text", large=large))
    return out


def tok_family_matrix(tok: Tokens):
    """`--tok-*` 族 × 代码页各层 → {(theme, layer, token): ratio}（**几何感知**）。"""
    out = {}
    for theme in ("dark", "light"):
        for name, _a, _g in CODE_LAYERS:
            for token in [n for n in tok.names() if n.startswith("--tok-")]:
                v = tok.value(token, theme)
                if v is None:
                    continue
                r = contrast_on_layer(v, name, theme, tok)
                if r is not None:
                    out[(theme, name, token)] = r
    return out


def layer_parts(name: str):
    """层名 → 配方两段（`None` = 这个名字不是层配方，是个普通令牌名）。

    ⚠ **alpha 不在名字里**：名字里的尾段只是**角色名**（`hl.当前行`），alpha 查 `CODE_LAYERS`
    那一行。要临时改档就换层表（`layers=` 参数）——名字里写 `.20` 不算数（省得两侧各写一套
    数字谓词：Python 的 `str.isdigit()` 认全角/阿拉伯数字，JS 的 `/^\\d+$/` 不认，那种分叉
    会让同一条层名在两侧算出不同的格）。
    """
    m = LAYER_RE.match(name)
    if not m:
        return None
    return {"base": m.group(1), "color": m.group(2)}


def layer_alpha_of(name: str, layers=None):
    """层名 → 表里登记的 alpha（不是浮点数、或不在表里 → `None`）。"""
    for n, a, _g in (CODE_LAYERS if layers is None else layers):
        if n == name:
            return a if isinstance(a, float) else None
    return None


def layer_geometry(name: str, layers=None) -> str:
    """层名 → 几何。

    · 表里登记过的按表（**表是已知层的单源**）；
    · **带 tint 的配方**（`<底>+hl…` / `<底>+--某令牌`）但表里没有 → 按 **`over`**：
      没分类的高亮一律假设它**压在字上**。默认值取严格那一侧是这一轮买的教训——
      乐观的默认（`behind`）会让"没登记进来的一层"静默变好看（括号彩虹就是这么错了 2.5）；
    · 其余（纯令牌名、根本没有 tint）→ `behind`（没有 tint 就没有染色这件事）。
    """
    for n, _a, g in (CODE_LAYERS if layers is None else layers):
        if n == name:
            return g
    return "over" if layer_parts(name) else "behind"


def layer_tint(name: str, theme: str, tok: Tokens, layers=None):
    """层的 tint（rgba 四元组）：`hl` → `rgba(var(--code-hl-rgb), α)`；`--x` → 该令牌自带 alpha。"""
    p = layer_parts(name)
    if p is None:
        return None
    if p["color"] != "hl":
        return tok.value(p["color"], theme)
    v = tok.value(CONTRAST_CODE_HL_TOKEN, theme)
    if v is None:
        return None
    alpha = layer_alpha_of(name, layers)
    if alpha is None:
        return None
    return (v[0], v[1], v[2], alpha)


def layer_colors(name: str, theme: str, tok: Tokens, layers=None):
    """层名 → `(base, bg, tint, geometry)`。

    · `base` = 底令牌本身（不过 tint）；`bg` = 合成后的**不透明**底；
    · `tint` = 层的 rgba（没有层的名字 → `None`）；`geometry` = `behind` / `over`。
    """
    p = layer_parts(name)
    if p is None:
        return tok.value(name, theme), tok.value(name, theme), None, "behind"
    base = tok.value(p["base"], theme)
    tint = layer_tint(name, theme, tok, layers)
    if base is None or tint is None:
        return base, None, tint, layer_geometry(name, layers)
    return base, over(tint, base[:3]), tint, layer_geometry(name, layers)


def layer_color(name: str, theme: str, tok: Tokens, layers=None):
    """层的**不透明**合成底（旧调用点沿用这个名字；不认识的层名 = 普通令牌取值）。"""
    return layer_colors(name, theme, tok, layers)[1]


def contrast_on_layer(fg, name: str, theme: str, tok: Tokens, layers=None):
    """**几何感知**的层内比值。

    · `behind` 层：字形不动，只换底 → `contrast(fg, bg)`；
    · `over` 层：字形先落到**不过 tint 的底**上、再被同一层半透明色染一遍
      → `contrast(over(tint, over(fg, base)), bg)`（`over` 负责把带 alpha 的字色也收进来）。
    """
    base, bg, tint, geom = layer_colors(name, theme, tok, layers)
    if bg is None or fg is None:
        return None
    fg_eff = over(fg, base[:3]) if base is not None else tuple(fg[:3])
    if geom == "over" and tint is not None:
        fg_eff = over(tint, fg_eff)
    return contrast(fg_eff, bg)


def contrast_family_cells(text: str, tok: Tokens | None = None, families=None):
    """族表展开成逐格检查：`[{theme, label, token, layer, kind, why, ratio, need}]`。

    ⚠ 比值走 `contrast_on_layer`（**几何感知**）：压在字上的层连字形一起染。
    """
    tok = tok or Tokens(text)
    names = tok.names()
    out = []
    for label, pick, layers, kind, why in (CONTRAST_FAMILIES if families is None else families):
        tokens = [pick[1:]] if pick.startswith("=") else [n for n in names if n.startswith(pick)]
        for theme in ("dark", "light"):
            for token in tokens:
                for layer in layers:
                    fg = tok.value(token, theme)
                    r = contrast_on_layer(fg, layer, theme, tok)
                    if fg is None or r is None:
                        continue
                    out.append(dict(theme=theme, label=label, token=token, layer=layer,
                                    kind=kind, why=why, ratio=r,
                                    need=CONTRAST_THRESHOLDS["large"] if kind == "nontext"
                                    else CONTRAST_THRESHOLDS["small"]))
    return out


def contrast_family_key(label: str) -> str:
    """族面的认人键（与 JS `contrastFamilyKey` 同一形态）。"""
    return "族：" + label


def contrast_token_key(literal: str) -> str:
    """令牌面的认人键（与 JS `contrastTokenKey` 同一形态）。"""
    return "令牌：" + literal


def unbased_color_tokens(text: str) -> list[str]:
    """无底规则（有 `color:`、底在基类或祖先）里当文字色用的令牌字面（去重、保序）。"""
    out: list[str] = []
    for sel, body in css_rules(contrast_style_text(text)):
        d = decls(body)
        if "color" not in d or bg_of_rule(d) is not None:
            continue
        if d["color"] not in out:
            out.append(d["color"])
    return out


def contrast_token_cells(text: str, tok: Tokens | None = None,
                         table=None):
    """令牌面展开成逐格检查：`[{theme, literal, layer, ratio, need, kind}]`。"""
    tok = tok or Tokens(text)
    table = CONTRAST_TOKEN_BASES if table is None else table
    out = []
    for literal, layers, kind, _why in table:
        for theme in ("dark", "light"):
            for layer in layers:
                fg = tok.parse(literal, theme)
                r = contrast_on_layer(fg, layer, theme, tok)
                if fg is None or r is None:
                    continue
                out.append(dict(theme=theme, literal=literal, layer=layer, kind=kind,
                                ratio=r,
                                need=CONTRAST_THRESHOLDS["large"] if kind == "nontext"
                                else CONTRAST_THRESHOLDS["small"]))
    return out


def read_page() -> str:
    """逐字节保真读（`newline=""`——描边那轮的纪律：别让文本模式归一换行）。

    ⚠ 这里**故意不提供 `write_page`**：腿⑧ 的判据是"吃源码文本 → 返回问题清单"的纯函数，
    红证走**内存注入**（把改过的文本直接喂给判据），比"就地改盘 + `finally` 复原"更干净
    （描边那轮 `probe-05/06` 的复原链就留下过"mtime 晚于读数"的尾巴）。
    """
    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


# ===========================================================================
# 从守卫源码解析那两张表（单源：探针不另抄一份）
# ===========================================================================

def guard_text() -> str:
    if not GUARD.is_file():
        raise SystemExit(f"守卫不在：{GUARD}")
    return GUARD.read_text(encoding="utf-8")


ROW_RE = re.compile(r'^\s*\[("(?:[^"\\]|\\.)*"(?:\s*,\s*"(?:[^"\\]|\\.)*")*)\],\s*$', re.M)


def _table_rows(js: str, name: str) -> list[list[str]]:
    m = re.search(rf"const {name} = \[(.*?)\n\];", js, re.S)
    if not m:
        raise SystemExit(f"守卫里找不到 `const {name} = [...];`——格式变了")
    rows = []
    for line in m.group(1).splitlines():
        line = line.split("//")[0].rstrip()
        if not line.strip().startswith("["):
            continue
        items = re.findall(r'"((?:[^"\\]|\\.)*)"', line)
        if not items:
            continue
        # 末格可能是**裸数字**（冻结比值），字符串正则抓不到它
        tail = re.search(r",\s*([0-9.]+)\]\s*,?\s*$", line)
        if tail:
            items.append(tail.group(1))
        rows.append(items)
    return rows


def load_exceptions() -> list[list[str]]:
    """`CONTRAST_EXCEPTIONS`：`[主题, 认人键, 类别, 理由, 冻结比值]`。"""
    return _table_rows(guard_text(), "CONTRAST_EXCEPTIONS")


def load_exceptions_raw() -> str:
    """例外表的**原文**（不含 `const … = [` 与 `];`）——`--check` 与同源断言按行比要用它。"""
    m = re.search(r"const CONTRAST_EXCEPTIONS = \[(.*?)\n\];", guard_text(), re.S)
    if not m:
        raise SystemExit("守卫里找不到 `const CONTRAST_EXCEPTIONS = [...];`——格式变了")
    return m.group(1)


def load_families() -> list[list[str]]:
    """从**守卫源码**解析族表 `[[标签, 令牌选取, [底…], 档位, 理由], …]`。

    读数走这里，不走 `probe_lib.CONTRAST_FAMILIES` 那份 Python 副本——
    副本与守卫的一致性由 `tests/test_contrast_mirror.py` 钉住，但**读数要有直接出处**。
    """
    js = guard_text()
    m = re.search(r"const CONTRAST_FAMILIES = \[([\s\S]*?)\n\];", js)
    if not m:
        raise SystemExit("守卫里找不到 `const CONTRAST_FAMILIES = [...];`——格式变了")
    body = "\n".join(ln.split("//")[0].rstrip() for ln in m.group(1).splitlines())
    rows = []
    for chunk in re.split(r"\n\s*(?=\[\")", body):
        if not chunk.strip().startswith("["):
            continue
        items = re.findall(r'"((?:[^"\\]|\\.)*)"', chunk)
        layers = list(CODE_LAYERS_NAMES) if "CODE_LAYERS.map" in chunk else [
            n for n in re.findall(r'"([^"]+)"', (re.findall(r"\[([^\[\]]*)\]", chunk) or [""])[0])]
        rows.append([items[0], items[1], layers, items[-2], items[-1]])
    if not rows:
        raise SystemExit("族表解析出 0 条——格式变了，别拿空表当读数")
    return rows


def contrast_gradient_key(fg: str, bg: str) -> str:
    """渐变端点面的认人键（与 JS `contrastGradientKey` 同一形态）。"""
    return f"渐变：{fg} on {bg}"


def contrast_gradient_cells(text: str, tok: Tokens | None = None, table=None):
    """**渐变端点**展开成逐格检查（形状同族面：每端点一格）。

    `bg_of_rule` 对渐变返回 None ⇒ 机械面看不见"文字压在渐变上"这一格；
    这一面按 `CONTRAST_GRADIENT_ENDS` 逐端点算（表与 JS 侧逐项同源）。
    """
    tok = tok or Tokens(text)
    table = CONTRAST_GRADIENT_ENDS if table is None else table
    out = []
    for theme, fg_name, layers, why in table:
        for layer in layers:
            fg = tok.parse(f"var({fg_name})", theme)
            bg = tok.value(layer, theme)
            if fg is None or bg is None:
                continue
            out.append(dict(theme=theme, fg=fg_name, layer=layer, why=why,
                            ratio=contrast(over(fg, bg[:3]), bg[:3]),
                            need=CONTRAST_THRESHOLDS["small"]))
    return out


#: **渐变端点检查**（02 单 Spec 轴评审补的盲区）：形状 `[主题, 前景令牌, 底令牌列表, 理由]`；
#: **与 JS 的 `CONTRAST_GRADIENT_ENDS` 逐项同源**（镜像守卫钉住）。
CONTRAST_GRADIENT_ENDS = [
    ("light", "--on-ok", ["--ok", "--ok-text"], "步骤点 / 阶号压在 ok 渐变上（亮色那档）"),
    ("dark", "--on-ok", ["--ok-bright", "--ok"], "同上（暗色那档：渐变两端与亮色不同）"),
    ("light", "--on-accent-deep", ["--accent-hi", "--accent-lo"], "当前步骤点压在 accent 渐变上"),
    ("dark", "--on-accent-deep", ["--accent-hi", "--accent-lo"], "同上（两主题同款渐变）"),
]


def load_token_bases() -> list[list[str]]:
    """从**守卫源码**解析第三面的令牌表 `[[字面, [底…], 档位, 理由], …]`。"""
    js = guard_text()
    m = re.search(r"const CONTRAST_TOKEN_BASES = \[([\s\S]*?)\n\];", js)
    if not m:
        raise SystemExit("守卫里找不到 `const CONTRAST_TOKEN_BASES = [...];`——格式变了")
    body = "\n".join(ln.split("//")[0].rstrip() for ln in m.group(1).splitlines())
    rows = []
    for chunk in re.split(r"\n\s*(?=\[\")", body):
        if not chunk.strip().startswith("["):
            continue
        items = re.findall(r'"((?:[^"\\]|\\.)*)"', chunk)
        layers = [n for n in re.findall(
            r'"([^"]+)"', (re.findall(r"\[([^\[\]]*)\]", chunk) or [""])[0])]
        rows.append([items[0], layers, items[-2], items[-1]])
    if not rows:
        raise SystemExit("令牌表解析出 0 条——格式变了，别拿空表当读数")
    return rows
