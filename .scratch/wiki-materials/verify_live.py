# -*- coding: utf-8 -*-
"""在线验证：当前 wiki 页面 fence 1 行数 = 产物文件 fence 1 行数。"""
import re
import sys
import urllib.request

from contest_generator.wiki_md import shiki_lines

FENCE_RE = re.compile(r"<pre[^>]*><code>([\s\S]*?)</code></pre>")

req = urllib.request.Request(
    "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/sht30-temp-humi-sensor.html",
    headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
m = re.search(r"<main[^>]*>([\s\S]*?)</main>", html, flags=re.I)
main = m.group(0)

# 直接对 <code> 内部跑 shiki_lines（绕过 parser 的实体还原差异 —— 用 html.parser 同路）
from html.parser import HTMLParser


class Raw(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.codes = []
        self._buf = None
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "code" and self._buf is None:
            self._buf = []
            self._depth = 1
        elif tag == "code":
            self._depth += 1

    def handle_endtag(self, tag):
        if tag == "code" and self._buf is not None:
            self._depth -= 1
            if self._depth == 0:
                self.codes.append("".join(self._buf))
                self._buf = None

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_data(self, d):
        if self._buf is not None:
            self._buf.append(d)
        # 注：span 等开始/结束标签在此解析器里未记录 —— 只收集 data，
        # 与 _WikiToMD 用 get_starttag_text 拼复原文不同；这里做近似对照。


r = Raw()
r.feed(main)
print("live code blocks:", len(r.codes))
print("live fence1 lines:", len(shiki_lines(r.codes[0]).__str__().splitlines()) if r.codes else 0)

# 产物文件
from pathlib import Path
s = Path("sources/materials/lckfb-地猛星移植手册/sensor--sht30-temp-humi-sensor.md").read_text(encoding="utf-8")
fences = re.findall(r"^```c\n([\s\S]*?)\n^```", s, re.M)
print("file fence1 lines:", len(fences[0].splitlines()))
print("fence1 首行:", fences[0].splitlines()[0])
print("fence1 末行:", fences[0].splitlines()[-1])
