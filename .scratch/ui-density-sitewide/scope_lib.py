r"""本轮施工脚本共用的**作用域解析**（单一出处，给 04–07 单直接用）。

为什么要有它（03 单双轴评审的 Findings）：03 的四支施工脚本 + 明细 dump 各自抄了一份
`load_scopes` / `scope_of` / `rules_of`（`rules_of` 四份逐字相同）——就是标准的
Duplicated Code。**03 那四支已经跑完、锚点已被消费掉**，回头重写它们等于让"已执行的证据"
变成"只能读、不能再跑"的中间态（评审没法再复算），所以那四支按 01/02 的既有形态留在原样，
**新脚本一律从这里 import**。

口径与守卫 `tests/js/css-tokens.test.mjs` **同一处**：
  · 分区表 `PAGE_SCOPES` 从守卫源码解析（`["id", /正则/],` 一行一条）；
  · 归属先剥选择器前面的块注释（02 单评审抓到的真漏洞：注释里提到别的页的类名会把规则判走）；
  · 规则行号 = 守卫/探针口径（规则起点前那个换行所在的行号），**与 `probe-01` 的读数一致**；
  · **描边登记簿**（border-guard/01）也在这里读：`load_border_kinds()` / `load_border_register()`
    从守卫源码解析那两张表，`full_border_entries()` 给"盘上那一边"的认人形态
    ——腿⑥ 与读数因此共用一份数据、一套判据。

用法：
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from scope_lib import (PAGE, GUARD, load_scopes, scope_of, rules_of, rules_in,
                           read_page, write_page, bare_fonts, bare_token_spaces, full_borders,
                           strip_lead_comments, full_border_entries,
                           load_border_kinds, load_border_register,
                           js_files, js_inline_border_entries, load_js_border_register)
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

    ⚠ 返回的选择器**带前导块注释**（这条样式块大量规则写成「注释 + 选择器」）——
    它适合"给人看 / 按行号施工"，**不适合当认人键**。要认人用 `full_border_entries()`
    （border-guard/01 加的：剥注释 + 空白归一 + 带作用域与类别）。
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


# ---------------------------------------------------------------------------
# 描边登记簿（工单 border-guard/01）：**判据仍住在 `tests/js/css-tokens.test.mjs`**，
# 这里只做"从守卫源码把那张数据表读回来"——单一出处，探针不另抄一份
# （照 `load_scopes()` / `load_backlog()` 的既有形状；格式变了就大声失败）。
# ---------------------------------------------------------------------------

LEAD_COMMENT_RE = re.compile(r"^(?:/\*.*?\*/\s*)+", re.S)
BORDER_TRANSPARENT_RE = re.compile(r"(?:^|\s)transparent(?:\s|$)")
# 登记项固定形状：一行一条 `["作用域", "选择器", "类别"],`（分组注释与空行一律忽略）
# ⚠ 必须带 `re.M`：不带 MULTILINE 时 `^` / `$` 只认整串首尾，一条都匹配不上（第一版就踩了）。
BORDER_ENTRY_RE = re.compile(r'^\s*\["([\w-]+)",\s*"([^"]+)",\s*"([a-z-]+)"\],\s*$', re.M)
BORDER_KIND_RE = re.compile(r'^\s*\["([a-z-]+)",\s*"([^"]+)"\],\s*$', re.M)


def strip_lead_comments(sel: str) -> str:
    """剥掉选择器**前面**那段块注释（与守卫 `stripLeadComments` 逐字同口径）。"""
    return LEAD_COMMENT_RE.sub("", sel).strip()


def _guard_block(name: str) -> str:
    """把守卫里 `const <name> = [ … ];` 之间的正文抠出来（找不到就大声失败）。"""
    text = GUARD.read_text(encoding="utf-8")
    m = re.search(rf"const {name} = \[(.*?)\n\];", text, re.S)
    if not m:
        raise SystemExit(f"守卫里找不到 {name} —— 格式变了，改 scope_lib 的解析")
    return m.group(1)


def load_border_kinds() -> list[tuple[str, str]]:
    """描边类别表 → [(id, 判据)]；解析不出任何一条就大声失败（别拿空表当读数）。"""
    out = [(m.group(1), m.group(2)) for m in BORDER_KIND_RE.finditer(_guard_block("BORDER_KINDS"))]
    if not out:
        raise SystemExit("BORDER_KINDS 解析出 0 条 —— 格式变了")
    return out


def load_border_register() -> list[tuple[str, str, str]]:
    """描边登记簿 → [(作用域, 剥注释的选择器, 类别)]；**逐行严格**，坏行大声失败。"""
    body = _guard_block("BORDER_REGISTER")
    out: list[tuple[str, str, str]] = []
    for i, line in enumerate(body.splitlines(), start=1):
        if not line.strip() or line.strip().startswith("//"):
            continue
        m = BORDER_ENTRY_RE.match(line)
        if not m:
            raise SystemExit(f"BORDER_REGISTER 第 {i} 行不是登记项形状：{line!r}")
        out.append((m.group(1), m.group(2), m.group(3)))
    if not out:
        raise SystemExit("BORDER_REGISTER 解析出 0 条 —— 格式变了")
    return out


def full_border_entries(text: str) -> list[dict[str, object]]:
    """盘上的整圈完整框，**带认人键**：`{line, scope, sel, value, transparent}`。

    与 `full_borders()` 同一判据（站在它上面，不另立一套），只多两步：
      · 选择器剥掉前导块注释 + 空白归一（守卫 `fullBorderEntries` 的同口径镜像）；
      · 附上作用域归属与"取值含不含 transparent"（`placeholder` 不变量要用的那一位）。
    行号仍是 `full_borders()` 的行号口径（规则起点前那个换行所在的行）。
    """
    scopes = load_scopes()
    out: list[dict[str, object]] = []
    for line, sel, value in full_borders(text):
        out.append({
            "line": line,
            "scope": scope_of(sel, scopes),
            "sel": " ".join(strip_lead_comments(sel).split()),
            "value": value,
            "transparent": bool(BORDER_TRANSPARENT_RE.search(value)),
        })
    return out


# ---------------------------------------------------------------------------
# 渲染方（`static/js/**`）内联整圈框（工单 border-guard/02）：认人键 = `(文件, 行内锚点)`。
# 判据仍住在守卫里，这里只是它的 Python 镜像 + 登记簿读回（探针复算用）。
# ---------------------------------------------------------------------------

JS_DIR = ROOT / "src" / "contest_generator" / "static" / "js"
# ⚠ **与样式块面那条不是同一条**：内联样式写在 HTML 属性里，取值可能以 `"` 收尾而不是 `;`
#   （`style="…border:1px dashed var(--warn)">`）；而且**两种拼法都认**（CSS 串 + JS 属性，
#   照守卫第五条腿 `jsInlineFontOffenders` 的先例）。两侧由 test_border_register_mirror.py 钉住。
#   单引号写成 `\u0027` 是为了让这条正则的**正文在两个语言里逐字相同**（能直接对拍）。
JS_BORDER_LINE_RE = re.compile(
    r'(?<![\w-])border\s*:\s*([^;"]+)|\.border\s*=\s*["\u0027]([^"\u0027]+)["\u0027]')
JS_BORDER_ENTRY_RE = re.compile(r'^\s*\["([^"]+)",\s\'(.*)\',\s*"([a-z-]+)"\],\s*$', re.M)


def js_files() -> list[tuple[str, str]]:
    """`static/js/**` 全部 .js → [(相对路径, 全文)]，按路径排序（确定性）。"""
    out: list[tuple[str, str]] = []
    for p in sorted(JS_DIR.rglob("*.js")):
        out.append((p.relative_to(JS_DIR).as_posix(),
                    p.read_text(encoding="utf-8", newline="")))
    return out


def js_inline_border_entries(files: list[tuple[str, str]] | None = None) -> list[dict[str, object]]:
    """渲染方里**内联写出来的**整圈完整框：`{file, line, raw, value}`（逐行扫，不跨行拼）。"""
    out: list[dict[str, object]] = []
    for rel, text in (js_files() if files is None else files):
        for i, raw in enumerate(text.split("\n"), start=1):
            for m in JS_BORDER_LINE_RE.finditer(raw):
                value = (m.group(1) or m.group(2) or "").strip()
                if not value or value.split()[0] in DEAD_BORDER:
                    continue
                out.append({"file": rel, "line": i, "raw": raw, "value": value})
    return out


def load_js_border_register() -> list[tuple[str, str, str]]:
    """渲染方登记簿 → [(文件, 锚点, 类别)]；**逐行严格**，坏行大声失败。"""
    body = _guard_block("JS_BORDER_REGISTER")
    out: list[tuple[str, str, str]] = []
    for i, line in enumerate(body.splitlines(), start=1):
        if not line.strip() or line.strip().startswith("//"):
            continue
        m = JS_BORDER_ENTRY_RE.match(line)
        if not m:
            raise SystemExit(f"JS_BORDER_REGISTER 第 {i} 行不是登记项形状：{line!r}")
        out.append((m.group(1), m.group(2), m.group(3)))
    if not out:
        raise SystemExit("JS_BORDER_REGISTER 解析出 0 条 —— 格式变了")
    return out
