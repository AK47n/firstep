"""立创 wiki 页面转换器：<main> 内容区 HTML → 规范 Markdown（单篇手册正文）。

wiki.lckfb.com（VitePress + Shiki）的「地猛星模块移植手册」页面结构（抓包实证）：

- 代码块 = <div class="language-c line-numbers-mode"><span class="lang">c</span>
  <pre class="shiki"><code>…每行一个 <span class="line"><span style>token</span>…</span>…</code></pre>
  行号在 <pre> 的兄弟节点 <div class="line-numbers-wrapper">（锚定 <span class="line"> 即天然隔离）；
- 标题 <h2-h6> 带 <a class="header-anchor"> 锚点与 \\u200b（剥掉）；
- 有序列表每个 li 独自一个 <ol start="N">（真实序号 = start 属性，连续 ol 应合并）；
- 提示块 = <div class="warning custom-block"><p class="custom-block-title">WARNING</p>…；
- SSR 内嵌图片仅部分页面有（懒加载组件是 <!---->，属于已知局限，不编造内容）。

本模块是纯函数域模块（无网络 / 无文件）：fetch_wiki.py 抓取后用本模块生成 .md，
测试用合成夹具覆盖全部结构分支（tests/test_wiki_md.py）。
"""

from __future__ import annotations

import html as html_mod
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

# 相对资源地址补齐域名（wiki 页面 src 形如 /storage/images/…）
BASE = "https://wiki.lckfb.com"

# 行内标记符（开/闭文本相同：**、*、~~）
_INLINE_MARKS = {"strong": "**", "em": "*", "del": "~~"}

# 正文行内文本需转义的 Markdown 特殊字符（我们的渲染器支持反斜杠转义）。
# 注意：_ 不转义——标识符里的词内下划线（bsp_sht30.h）按 CommonMark 词内
# 规则在标准渲染器与本 app 渲染器中都按字面处理，转义反而污染原文可读性。
_MD_SPECIAL_RE = re.compile(r"([\\*`\[])")


def _escape_md(text: str) -> str:
    """行内原文转义（\\ * _ ` [），保证出现的 Markdown 标记都是转换器自己产生的。"""
    return _MD_SPECIAL_RE.sub(r"\\\1", text)


def code_block_count(md_body: str) -> int:
    """Markdown 正文里的代码围栏数（``` 开闭对数）。"""
    return md_body.count("```") // 2


def img_ext(url: str) -> str:
    """图片 URL → 本地扩展名（小写；无扩展名回退 .png）。"""
    suffix = Path(urlparse(url).path).suffix
    return suffix.lower() if suffix else ".png"


def shiki_lines(raw: str) -> list[str]:
    """<pre><code> 内部原始 HTML → 逐行代码文本列表（以 <span class="line"> 为锚）。

    Shiki HTML 形态：<span class="line"><span style="--shiki-…">token</span>…</span>
    —— 行号在 <pre> 的兄弟节点，正常情况进不来；仍防御性剔除
    <span class="line-number">（万一混入代码区也不污染正文）。

    注意：本函数输入已过 html.parser（convert_charrefs=True），实体已被还原，
    代码文本可能含字面 <stdio.h> 这类尖括号 —— 不能做通用 <[^>]+> 剥标签，
    只剥 Shiki 的 span 包裹与 <br>。
    """
    s = re.sub(r'<span class="line-number">[\s\S]*?</span>', "", raw)
    s = re.sub(r'<span class="line">', "\x00", s)
    s = re.sub(r"</?span[^>]*>", "", s)
    s = re.sub(r"<br\s*/?>", "", s)
    s = html_mod.unescape(s)
    if not s.startswith("\x00"):
        return []
    parts = s.split("\x00")[1:]
    lines = [p.strip("\r\n") for p in parts]
    # 末尾残留（最后一个 \x00 之后到 </code> 间的换行）→ 空串收尾则剔除
    while lines and lines[-1] == "":
        lines.pop()
    return lines


class _ListCtx(NamedTuple):
    """列表上下文：kind = "ol"（start 起编号，idx 第几项）/ "ul"（start 占位）。"""

    kind: str
    start: int = 1
    idx: int = 0


class _WikiToMD(HTMLParser):
    """一次性 <main> → Markdown 块列表转换器。

    块 = 段落 / 标题 / 列表组（连续 li 合并为一块，内部 \\n 连接）/ 代码围栏 /
    引用块 / 自定义提示块；块间由 parse_main 用空行分隔。
    """

    def __init__(self, slug: str, base: str):
        super().__init__(convert_charrefs=True)
        self.slug = slug
        self.base = base
        self.blocks: list[str] = []        # 已完成块
        self.img_urls: list[str] = []      # 图片绝对 URL（去重保序）
        self._cur: list[str] = []          # 当前行内片段缓冲
        self._heading = 0                  # 0=非标题；2..6=hN 收集模式
        self._hd_buf: list[str] = []
        self._skip_h1 = False
        self._lang_capture = False         # <span class="lang"> 捕获代码语言
        self._pre_lang = "c"
        self._in_pre = False
        self._pre_raw = ""
        self._list_stack: list[_ListCtx] = []  # ol/ul 列表上下文
        self._list_group: list[str] = []   # 当前未落盘的列表组（连续 li 合并）
        self._in_li = 0
        self._in_bq = False                # <blockquote> 内（p 透明，收尾拼 > ）
        self._in_cb = False                # custom-block 内
        self._cb_title: list[str] = []     # custom-block 标题文本（p.custom-block-title）
        self._in_cb_title = False
        self._link_pos: list[int] = []     # 当前链接内容在 _cur 的起点（含 \x01link\x01href 前缀）
        self._img_map: dict[str, str] = {}  # 图片 URL → 本地文件名（imgN.ext）
        self._in_num_wrapper = False       # <div class="line-numbers-wrapper"> 内（行号数字不进正文）

    # —— 产出工具 ——

    def _in_meta_ctx(self) -> bool:
        """当前是否处于标题 / h1 跳过 / 提示块标题等元信息上下文（行内标记不落 _cur）。"""
        return self._skip_h1 or self._heading > 0 or self._in_cb_title

    def _flush_list_group(self) -> None:
        if self._list_group:
            self.blocks.append("\n".join(self._list_group))
            self._list_group = []

    def _emit_block(self, text: str) -> None:
        """落盘一个非列表块（先冲刷未完成的列表组，保持连续 li 合并）。"""
        self._flush_list_group()
        if text:
            self.blocks.append(text)

    def _flush_para(self) -> None:
        text = "".join(self._cur).strip()
        self._cur = []
        if text:
            self._emit_block(text)

    def _flush_li(self) -> None:
        text = "".join(self._cur).strip()
        self._cur = []
        if self._li_in_ol():
            ctx = self._list_stack[-1]
            marker = f"{ctx.start + ctx.idx}. "
            self._list_stack[-1] = ctx._replace(idx=ctx.idx + 1)
        else:
            marker = "- "
        indent = "  " * max(0, len(self._list_stack) - 1)
        self._list_group.append(indent + marker + text if text else indent + marker)

    def finish(self) -> None:
        """解析收尾：冲刷未落盘的段/列表组（如顶层裸 <img> 后直接 EOF）。"""
        self._flush_para()
        self._flush_list_group()

    def _li_in_ol(self) -> bool:
        return bool(self._list_stack) and self._list_stack[-1].kind == "ol"

    # —— 解析事件 ——

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag == "h1":
            self._skip_h1 = True
            return
        if tag in ("h2", "h3", "h4", "h5", "h6"):
            self._flush_para()
            self._heading = int(tag[1])
            self._hd_buf = []
            return
        if self._in_pre:
            if tag == "code":
                return  # <code> 壳不进 raw（shiki_lines 以 <span class="line"> 为锚）
            self._pre_raw += self.get_starttag_text() or "<" + tag + ">"
            return
        if tag == "pre":
            self._in_pre = True
            self._pre_raw = ""
            return
        if tag == "span" and "lang" in cls:
            self._lang_capture = True
            return
        if tag == "div" and "line-numbers-wrapper" in cls:
            self._in_num_wrapper = True
            return
        if tag == "p":
            if "custom-block-title" in cls and self._in_cb:
                self._in_cb_title = True
            return  # 段落结束由 </p> 冲刷；li/blockquote 内 p 透明
        if tag == "li":
            self._in_li += 1
            return
        if tag == "ol":
            try:
                start = int(a.get("start", "1"))
            except ValueError:
                start = 1
            self._list_stack.append(_ListCtx(kind="ol", start=start, idx=0))
            return
        if tag == "ul":
            self._list_stack.append(_ListCtx(kind="ul", start=1, idx=0))
            return
        if tag == "br":
            if self._in_num_wrapper:
                return
            self._cur.append(" ")
            return
        if tag == "img":
            if self._in_meta_ctx():
                return
            src = a.get("src", "")
            url = src if src.startswith("http") else ("https:" + src if src.startswith("//") else self.base.rstrip("/") + "/" + src.lstrip("/"))
            if url not in self._img_map:
                self._img_map[url] = f"img{len(self._img_map) + 1}{img_ext(url)}"
                self.img_urls.append(url)
            alt = re.sub(r"[\[\]()]", "", a.get("alt") or "img")
            self._cur.append(f"![{alt}](images/{self.slug}/{self._img_map[url]})")
            return
        if tag == "a":
            if "header-anchor" in cls.lower():
                return  # 页面内锚点：整个忽略
            if self._in_meta_ctx():
                return  # 标题/提示块标题内的链接：文本照常收集（不包链接）
            self._link_pos.append(len(self._cur))
            self._cur.append("\x01link\x01" + html_mod.unescape(a.get("href") or ""))
            return
        if tag in _INLINE_MARKS:
            if not self._in_meta_ctx():
                self._cur.append(_INLINE_MARKS[tag])
            return
        if tag == "code":
            if not self._in_meta_ctx():
                self._cur.append("`")
            return
        if tag == "blockquote":
            self._in_bq = True
            return
        if tag == "div" and "custom-block" in cls:
            self._in_cb = True
            self._cb_title = []
            return
        # 其余透明标签：div（flex 包装/壳）、span、button、table 等

    def handle_endtag(self, tag):
        if tag == "h1":
            self._skip_h1 = False
            return
        if tag in ("h2", "h3", "h4", "h5", "h6"):
            self._flush_para()
            depth = int(tag[1])
            text = "".join(self._hd_buf).strip()
            if text:
                self._emit_block("#" * depth + " " + text)
            self._heading = 0
            self._hd_buf = []
            return
        if self._in_pre:
            if tag == "code":
                return
            if tag == "pre":
                self._in_pre = False
                code_lines = shiki_lines(self._pre_raw)
                self._emit_block("```" + self._pre_lang + "\n"
                                 + "\n".join(code_lines) + "\n```")
            return
        if tag == "span" and self._lang_capture:
            self._lang_capture = False
            return
        if tag == "p":
            if self._in_cb_title:
                self._in_cb_title = False
                return
            if self._in_cb or self._in_li or self._in_bq:
                return  # 透明 p：内容已入 _cur
            self._flush_para()
            return
        if tag == "li":
            self._flush_li()
            self._in_li -= 1
            return
        if tag in ("ol", "ul"):
            # 列表组不在此处冲刷：连续 <ol>（每 li 一个）靠 _emit_block 边缘冲刷合并
            if self._list_stack:
                self._list_stack.pop()
            return
        if tag == "a":
            if self._link_pos:
                start = self._link_pos.pop()
                head = self._cur[start]
                href = head[len("\x01link\x01"):] if head.startswith("\x01link\x01") else ""
                body = "".join(self._cur[start + 1:]).strip()
                if body and href:
                    self._cur[start:] = [f"[{body}]({href})"]
                elif body:
                    self._cur[start:] = [body]
                else:
                    self._cur[start:] = []
            return
        if tag in _INLINE_MARKS:
            if not self._in_meta_ctx():
                self._cur.append(_INLINE_MARKS[tag])
            return
        if tag == "code":
            self._cur.append("`")
            return
        if tag == "blockquote":
            self._in_bq = False
            text = "".join(self._cur).strip()
            self._cur = []
            if text:
                self._emit_block("> " + text)
            return
        if tag == "div" and self._in_num_wrapper:
            self._in_num_wrapper = False
            return
        if tag == "div" and self._in_cb:
            self._in_cb = False
            title = "".join(self._cb_title).strip()
            body = "".join(self._cur).strip()
            self._cur = []  # 关键：正文已落盘引用块，清空不留到下一块
            if not title:
                title = "提示"
            if body:
                self._emit_block(f"> **{title}**：{body}")
            else:
                self._emit_block(f"> **{title}**")
            return

    def handle_data(self, data):
        if self._in_pre:
            self._pre_raw += data.replace("\u200b", "")
            return
        if self._in_num_wrapper:
            return
        if self._skip_h1:
            return
        if self._lang_capture:
            self._pre_lang = data.strip() or self._pre_lang
            return
        data = data.replace("\u200b", "")
        if self._heading:
            if data.strip():
                self._hd_buf.append(_escape_md(data))
            return
        if self._in_cb_title:
            self._cb_title.append(_escape_md(data))
            return
        if data.strip():
            self._cur.append(_escape_md(data))

    def handle_comment(self, data):
        return  # 丢弃 <!---->（VitePress SSR 占位）

    def handle_startendtag(self, tag, attrs):
        if self._in_pre:
            self._pre_raw += self.get_starttag_text() or "<" + tag + ">"
            return
        if self._in_num_wrapper:
            return
        if tag == "br":
            self._cur.append(" ")
        elif tag == "img":
            self.handle_starttag(tag, attrs)
        elif tag == "hr":
            self._emit_block("---")


def parse_main(main_html: str, slug: str, base: str = BASE) -> tuple[str, list[str]]:
    """<main> 内容区 HTML → (Markdown 正文, 图片绝对 URL 有序列表)。

    按原页顺序输出：标题（剥锚点/\\u200b）、段落（块间空行）、列表（连续 li
    合并、编号取 <ol start>）、代码围栏（Shiki 逐行还原）、提示块（> **标题**：正文）、
    内嵌图片（images/<slug>/imgN.ext 相对批次根，去重编号）。转换失败/无内容 → 空串。
    """
    parser = _WikiToMD(slug, base)
    parser.feed(main_html or "")
    parser.close()
    parser.finish()
    text = "\n\n".join(b for b in parser.blocks if b.strip())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, parser.img_urls


def build_markdown(
    slug: str,
    cat: str,
    url: str,
    title: str,
    md_body: str,
    img_urls: list[str],
    pan_links: list[str],
) -> str:
    """组装单篇手册：元数据头 + 正文（原页顺序）+ 「百度网盘下载」小节。

    代码块数 / 图片数按实际计数写入元数据（图片数 = 抓取到的内嵌图片数）。
    """
    body = md_body.strip() or "（正文提取为空）"
    fences = code_block_count(body)
    lines = [
        f"# {slug}",
        "",
        f"- 分类：{cat}",
        f"- 来源：{url}",
        f"- 标题：{title}",
        f"- 代码块：{fences} 个 · 图片：{len(img_urls)} 张",
        "",
        body,
        "",
    ]
    if pan_links:
        lines.append("## 百度网盘下载")
        lines.append("")
        for link in pan_links:
            lines.append(f"- {link}")
        lines.append("")
    return "\n".join(lines)
