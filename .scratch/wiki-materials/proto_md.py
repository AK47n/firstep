# -*- coding: utf-8 -*-
"""原型：wiki 页 <main> → 规范 Markdown（按原页顺序穿插正文/代码/图片）。

验证转换器算法的关键假设：
1. Shiki 代码块 = 每行一个 <span class="line">，行号在兄弟 div 里（不进代码）；
2. 标题含 <a class="header-anchor"> 锚点 + \\u200b（要剥掉）；
3. flex 包装 div（style="display:flex"）要透明化；
4. custom-block（info/warning/tip）转引用块；
5. 图片（SSR 内嵌的）下载后内嵌引用。

运行：python .scratch/wiki-materials/proto_md.py <url> [slug]
"""

from __future__ import annotations

import html as html_mod
import re
import sys
import urllib.request
from html.parser import HTMLParser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://wiki.lckfb.com"


def shiki_lines(raw: str) -> list[str]:
    """<pre><code> 内部原始 HTML → 逐行代码文本（以 <span class="line"> 为锚）。

    Shiki HTML 形态：<span class="line"><span style="...">tok</span>...</span>
    —— 行号在 <div class="line-numbers-wrapper">（<pre> 的兄弟节点，根本进不来）。
    """
    s = re.sub(r'<span class="line">', "\x00", raw)
    s = re.sub(r"</?span[^>]*>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html_mod.unescape(s)
    if not s.startswith("\x00"):
        return []
    parts = s.split("\x00")[1:]
    lines = [p.strip("\r\n").rstrip() for p in parts]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


# 行内标记 → 开/闭文本
_INLINE_MARKS = {"strong": ("**", "**"), "em": ("*", "*"), "del": ("~~", "~~")}


class WikiToMD(HTMLParser):
    """一次性 <main> → Markdown 转换器（块级 + 行内）。

    状态机：_heading（标题收集模式）/ _in_pre（代码原样收集）/ _list_stack
    （列表层级）/ _link_stack（链接包装起点）/ _in_li（li 内 p 透明）。
    """

    def __init__(self, slug: str, img_urls: list[str]):
        super().__init__(convert_charrefs=True)
        self.slug = slug
        self.img_urls = img_urls
        self.lines: list[str] = []
        self._cur: list[str] = []
        self._heading = 0            # 0=非标题；2..6 = hN 收集模式
        self._hd_buf: list[str] = []
        self._skip_h1 = False
        self._in_pre = False
        self._pre_raw = ""
        self._pre_lang = "c"
        self._list_stack: list[str] = []   # "ol"/"ul"；ol 用计数标记
        self._ol_idx: list[int] = []
        self._in_li = 0
        self._link_pos: list[int] = []     # _cur 内链接内容起点
        self._img_map: dict[str, str] = {}
        self._pending_p = False

    # —— 产出工具 ——
    def _flush_p(self) -> None:
        """段落结束：把 _cur 作为段落输出（减掉 $cur 的裸标记差异）。"""
        t = "".join(self._cur).strip()
        self._cur = []
        if t:
            self.lines.append(t)

    def _flush_li(self) -> None:
        t = "".join(self._cur).strip()
        self._cur = []
        if t:
            depth = max(0, len(self._list_stack) - 1)
            if self._list_stack:
                if self._list_stack[-1] == "ol":
                    idx = self._ol_idx[-1]
                    marker = f"{idx}. "
                    self._ol_idx[-1] += 1
                else:
                    marker = "- "
            else:
                marker = "- "
            self.lines.append("  " * depth + marker + t)

    def _emit_inline_marks(self, tag: str) -> None:
        open_mark, close_mark = _INLINE_MARKS[tag]
        self._cur.append(open_mark)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag == "h1":
            self._skip_h1 = True
            return
        if tag in ("h2", "h3", "h4", "h5", "h6"):
            self._flush_p()
            self._heading = int(tag[1])
            self._hd_buf = []
            return
        if self._in_pre:
            # <pre> 内所有标签原样进 raw（含 span.line / style span 的标签文本）
            self._pre_raw += self.get_starttag_text() or "<" + tag + ">"
            return
        if tag == "p":
            if self._in_li:
                return                      # li 内 p 透明：内容直接进 _cur
            self._pending_p = False
            return
        if tag == "pre":
            self._in_pre = True
            self._pre_raw = ""
            return
        if tag == "li":
            self._in_li += 1
            self._flush_li()
            return
        if tag == "ol":
            self._list_stack.append("ol")
            self._ol_idx.append(1)
            return
        if tag == "ul":
            self._list_stack.append("ul")
            self._ol_idx.append(0)
            return
        if tag == "br":
            self._cur.append(" ")
            return
        if tag == "img":
            if self._skip_h1 or self._heading:
                return
            src = a.get("src", "")
            url = src if src.startswith("http") else BASE + src
            if url not in self._img_map:
                self._img_map[url] = f"img{len(self._img_map) + 1}"
                self.img_urls.append(url)
            alt = re.sub(r"[\[\]()]", "", a.get("alt") or "img")
            self._cur.append(f"![{alt}](images/{self.slug}/{self._img_map[url]}.png)")
            return
        if tag == "a":
            if "header-anchor" in cls.lower():
                return                      # 页面内锚点：整个忽略
            # 非锚点链接（正文里才处理；标题里跳过）
            if self._heading or self._skip_h1:
                self._cur.append("")        # 标题内链接文本照常收集（无包装）
                return
            if self._in_pre:
                return
            self._link_pos.append(len(self._cur))
            self._cur.append("\x01link\x01" + (a.get("href") or ""))
            return
        if tag in _INLINE_MARKS:
            if not (self._skip_h1 or self._heading):
                self._emit_inline_marks(tag)
            return
        if tag == "code" and not (self._skip_h1 or self._heading):
            self._cur.append("`")
            return
        if tag in ("table", "tr", "thead", "tbody", "td", "th", "div", "button",
                   "span", "b", "i", "u", "s", "sub", "sup"):
            return                          # 透明标签（本批页面无表格）

    def handle_endtag(self, tag):
        if tag == "h1":
            self._skip_h1 = False
            return
        if tag in ("h2", "h3", "h4", "h5", "h6"):
            self._flush_p()
            depth = int(tag[1])
            text = "".join(self._hd_buf).strip()
            self.lines.append("#" * depth + " " + text if text else "")
            self._heading = 0
            self._hd_buf = []
            return
        if self._in_pre:
            if tag == "code":
                return
            if tag == "pre":
                self._in_pre = False
                code_lines = shiki_lines(self._pre_raw)
                # 围栏整体作为单个块（join 用 \n\n，内部行连接用 \n）
                self.lines.append("```" + self._pre_lang + "\n"
                                  + "\n".join(code_lines) + "\n```")
            return
        if tag == "p":
            if self._in_li:
                return
            self._flush_p()
            return
        if tag == "li":
            self._flush_li()
            self._in_li -= 1
            return
        if tag in ("ol", "ul"):
            if self._list_stack:
                self._list_stack.pop()
                if self._ol_idx:
                    self._ol_idx.pop()
            return
        if tag == "a":
            if self._link_pos:
                start = self._link_pos.pop()
                # 收集 [start+1:] 片段；第一个片段含 \x01link\x01href 前缀
                head = self._cur[start]
                href = head[len("\x01link\x01"):] if head.startswith("\x01link\x01") else ""
                body = self._cur[start + 1:]
                text = "".join(body)
                clean = "".join(body).strip()
                if clean and href:
                    self._cur[start:] = [f"[{clean}]({href})"]
                elif clean:
                    self._cur[start:] = [clean]
                else:
                    self._cur[start:] = []
            return
        if tag in _INLINE_MARKS:
            if not (self._skip_h1 or self._heading):
                self._emit_inline_marks(tag)
            return
        if tag == "code":
            self._cur.append("`")
            return

    def handle_data(self, data):
        if self._in_pre:
            self._pre_raw += data
            return
        if self._skip_h1:
            return
        data = data.replace("\u200b", "").replace("\xa0", " ").replace("\u3000", "　")
        if self._heading:
            if data.strip():
                self._hd_buf.append(data)
            return
        if data.strip():
            self._cur.append(data)

    def handle_comment(self, data):
        return

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self._cur.append(" ")
        elif tag == "img":
            self.handle_starttag(tag, attrs)

    # —— 行内标记开闭计数（简化：直接栈化）——
    def _emit_inline_marks_stack(self, tag: str):
        pass


_cur_open: dict = {}


def _reset_marks():
    _cur_open.clear()
    for t in _INLINE_MARKS:
        _cur_open[t] = False


def convert(main_html: str, slug: str) -> tuple[str, list[str]]:
    img_urls: list[str] = []
    _reset_marks()
    p = WikiToMD(slug, img_urls)
    p.feed(main_html)
    p.close()
    text = "\n\n".join(x for x in p.lines if x.strip() != "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, img_urls


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def main():
    url = sys.argv[1]
    slug = sys.argv[2] if len(sys.argv) > 2 else "probe"
    html = fetch(url)
    main = re.search(r"<main[^>]*>([\s\S]*?)</main>", html).group(1)
    md, imgs = convert(main, slug)
    print(f"—— 图片：{len(imgs)} ——")
    for u in imgs:
        print(" ", u)
    print("—— 转换输出（前 4000 字符）——")
    print(md[:4000])
    print("—— 代码块行数抽样 ——")
    for m in re.finditer(r"```c\n([\s\S]*?)```", md):
        print("  fence lines:", len(m.group(1).splitlines()))
    import collections
    print("—— 首行词频（token-per-line 应不存在）——")
    bad = [l for l in md.splitlines() if re.fullmatch(r"\s*[#]?\s*include|^\s*(double|int|void)\s*$", l)]
    print("  疑似孤立 token 行:", len(bad))


if __name__ == "__main__":
    main()
