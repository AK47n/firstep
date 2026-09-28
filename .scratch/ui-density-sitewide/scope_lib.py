r"""本轮施工脚本共用的**作用域解析**（单一出处，给 04–07 单直接用）。

为什么要有它（03 单双轴评审的 Findings）：03 的四支施工脚本 + 明细 dump 各自抄了一份
`load_scopes` / `scope_of` / `rules_of`（`rules_of` 四份逐字相同）——就是标准的
Duplicated Code。**03 那四支已经跑完、锚点已被消费掉**，回头重写它们等于让"已执行的证据"
变成"只能读、不能再跑"的中间态（评审没法再复算），所以那四支按 01/02 的既有形态留在原样，
**新脚本一律从这里 import**。

口径与守卫 `tests/js/css-tokens.test.mjs` **同一处**：
  · 分区表 `PAGE_SCOPES` 从守卫源码解析（`["id", /正则/],` 一行一条）；
  · 归属先剥选择器前面的块注释（02 单评审抓到的真漏洞：注释里提到别的页的类名会把规则判走）；
  · 规则行号 = 守卫/探针口径（规则起点前那个换行所在的行号），**与 `probe-01` 的读数一致**。

用法：
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from scope_lib import (PAGE, GUARD, load_scopes, scope_of, rules_of, rules_in,
                           read_page, write_page, bare_fonts, bare_token_spaces, full_borders)
"""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAGE = ROOT / "src" / "contest_generator" / "static" / "index.html"
GUARD = ROOT / "tests" / "js" / "css-tokens.test.mjs"

FONT_RE = re.compile(r"font-size:\s*([0-9.]+)px")
SPACE_RE = re.compile(r"(?:padding|margin|gap)(?:-top|-right|-bottom|-left)?:\s*([^;]+);")
SPACE_NUM_RE = re.compile(r"(?<![\w.-])(\d+)px")
SPACE_TOKEN = {4: "--space-1", 8: "--space-2", 12: "--space-3",
               16: "--space-4", 20: "--space-5", 24: "--space-6"}
# **整圈完整框**（03 单立的施工口径）：完整 `border:` 声明、值不是 none/0。
# ⚠ 它**不是**探针 `--kind borders` 那一栏：那边把单边分隔线（`border-top: 1px dashed`）
# 与 `border: 0` 也算进去，所以"74 处描边"从来不是"74 个盒子"（03 单账第 1 条）。
FULL_BORDER_RE = re.compile(r"(?<![\w-])border:\s*([^;]+);")
DEAD_BORDER = ("none", "0")


def load_scopes() -> list[tuple[str, re.Pattern[str]]]:
    """全站分区表（单一出处 = 守卫源码）。"""
    text = GUARD.read_text(encoding="utf-8")
    block = re.search(r"const PAGE_SCOPES = \[(.*?)\n\];", text, re.S)
    if not block:
        raise SystemExit("守卫里找不到 PAGE_SCOPES —— 解析失败，别拿空表当读数")
    scopes = [(m.group(1), re.compile(m.group(2)))
              for m in re.finditer(r'\["([\w-]+)", /(.*?)/\]', block.group(1))]
    if not scopes:
        raise SystemExit("PAGE_SCOPES 解析出 0 条 —— 格式变了")
    return scopes


def scope_of(sel: str, scopes: list[tuple[str, re.Pattern[str]]]) -> str:
    """规则归谁：先剥掉选择器前面那段块注释（与守卫 `scopeOf` 同一口径）。"""
    clean = re.sub(r"^(?:/\*.*?\*/\s*)+", "", sel, flags=re.S).strip()
    for name, rx in scopes:
        if rx.search(clean):
            return name
    return scopes[-1][0]


def rules_of(text: str) -> list[tuple[int, str, int, int]]:
    """[(行号, 选择器, 声明体起, 声明体止)]——行号口径与探针/守卫一致。

    **只在 `<style>` 块里解析**（与 `probe-01-scope-draft.py` 完全同口径）：整文件解析会
    被 `<head>` 那段内联主题脚本的 `{}` 带偏，遇到含花括号的 CSS 注释时括号配对就分叉
    ——实测多出/漏掉一条"规则"（本模块第一版就多算了一条，`generate` 410 vs 探针 409）。
    声明体的起止是**原文件**里的下标，调用方可以直接 `text[b0:b1]`。
    """
    m = re.search(r"<style>(.*?)</style>", text, re.S)
    css, base = (m.group(1), m.start(1)) if m else (text, 0)
    offset = text[:base].count("\n") + 1 if m else 0
    out = []
    for r in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, re.S):
        out.append((offset + css[: r.start()].count("\n"),
                    " ".join(r.group(1).split()),
                    base + r.start(2), base + r.end(2)))
    return out


def read_page() -> str:
    """逐字节保真读（`newline=""`——01/02 的纪律：别让文本模式归一换行）。"""
    with PAGE.open("r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_page(text: str) -> None:
    """逐字节保真写（同上）。"""
    with PAGE.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def rules_in(text: str, scope: str) -> list[tuple[int, str, int, int]]:
    scopes = load_scopes()
    return [r for r in rules_of(text) if scope_of(r[1], scopes) == scope]


def bare_fonts(text: str, scope: str) -> list[tuple[int, str]]:
    """该作用域现算的裸 px 字号：**每处一条** [(行号, 取值)]。"""
    out: list[tuple[int, str]] = []
    for line, sel, b0, b1 in rules_in(text, scope):
        out.extend((line, v) for v in FONT_RE.findall(text[b0:b1]))
    return out


def bare_token_spaces(text: str, scope: str) -> list[tuple[int, str, str]]:
    """该作用域现算的"等于令牌却裸写"的间距：[(行号, 选择器, 取值px)]。"""
    out: list[tuple[int, str, str]] = []
    for line, sel, b0, b1 in rules_in(text, scope):
        for m in SPACE_RE.finditer(text[b0:b1]):
            for n in re.findall(r"(\d+)px", m.group(1)):
                if int(n) in SPACE_TOKEN:
                    out.append((line, sel, n))
    return out


def tokenize_space_decl(decl: str) -> str | None:
    """把一条 `padding` / `margin` / `gap` 声明里等于令牌的裸 px 换成 `var(--space-N)`。

    **单一出处**：04b 与 05b 各有一份逐字相同的实现（`NUM_RE` + `tokenize()`）——05 单评审
    按 README「公共件从 `scope_lib.py` import，别再各抄一份（03 单评审的账）」点了名。
    那两支**已执行完、锚点已消费**（03 账第 6 条），不回头改写；**06 起的新脚本用这个**。
    没有可换的返回 `None`；`calc(` 的值一律不碰——要例外就**逐条点名**，别留恒空的表
    （05b 原来那个恒空的 `CALC_ALLOW` 就是反面例子，评审点名后已删）。
    """
    m = SPACE_RE.match(decl)
    if not m or "calc(" in m.group(1):
        return None
    body = m.group(1)
    changed = SPACE_NUM_RE.sub(lambda mm: f"var({SPACE_TOKEN[int(mm.group(1))]})"
                               if int(mm.group(1)) in SPACE_TOKEN else mm.group(0), body)
    if changed == body:
        return None
    return decl[:m.start(1)] + changed + decl[m.end(1):]


def load_backlog() -> list[str]:
    """进度清单（页面尺）——**条目数本身就是进度**；单一出处 = 守卫源码。

    08 单从 `probe-01` / `probe-04` 两份逐字相同的实现里提上来的（07 单评审点的名：
    同一段解析抄两份）。⚠ 解析的是 `new Set([ … ])` 里的**引号串**——所以守卫注释里
    写作用域名别用 ASCII 双引号（07 单踩过，见 README 坑 29）。
    """
    text = GUARD.read_text(encoding="utf-8")
    block = re.search(r"const SITEWIDE_BACKLOG = new Set\(\[(.*?)\]\);", text, re.S)
    if not block:
        raise SystemExit("守卫里找不到 SITEWIDE_BACKLOG —— 格式变了，改 scope_lib")
    # **先剥注释再抽引号串**（08 单评审 Standards：坑 29 的病根是"注释里也抽"。
    # 07 单是靠"注释里改用「」"绕过去的，这里把机制拆掉——注释里写什么都不再算条目）
    body = re.sub(r"//[^\n]*", "", block.group(1))
    return re.findall(r'"([\w-]+)"', body)


def full_borders(text: str, scope: str | None = None) -> list[tuple[int, str, str]]:
    """**整圈完整框**：完整 `border:` 声明且值不是 none/0 → [(行号, 选择器, 取值)]。

    `scope=None` = 全站（跨作用域）。施工脚本（FIX/KEEP 两张表的对账）与取证探针
    **共用这一处**——03 单的 apply-03c 把它写在脚本里、04 单的取证脚本又抄了一份，
    04 单评审按 README「公共件从 scope_lib import」把口径提到这里（apply-04c 已执行完、
    不回头改写；05–07 起的新脚本一律用本函数）。
    """
    scopes = load_scopes()
    out: list[tuple[int, str, str]] = []
    for line, sel, b0, b1 in rules_of(text):
        if scope is not None and scope_of(sel, scopes) != scope:
            continue
        for m in FULL_BORDER_RE.finditer(text[b0:b1]):
            value = m.group(1).strip()
            if value.split()[0] in DEAD_BORDER:
                continue
            out.append((line, sel, value))
    return out
