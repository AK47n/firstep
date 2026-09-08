# -*- coding: utf-8 -*-
"""调试：shiki_lines 对 stdio.h 行的处理。"""
import re

from contest_generator.wiki_md import shiki_lines

raw = ('<span class="line"><span style="--shiki-light:#D73A49;--shiki-dark:#F97583;">#include</span>'
       '<span style="--shiki-light:#032F62;--shiki-dark:#9ECBFF;"> &lt;stdio.h&gt;</span></span>')
print("direct:", shiki_lines(raw))

raw2 = ('<span class="line"><span style="--shiki-light:#D73A49;">#include</span>'
        '<span style="--shiki-light:#032F62;"> &lt;stdio.h&gt;</span></span>'
        '<span class="line"><span style="--shiki-light:#D73A49;">#include</span>'
        '<span style="--shiki-light:#032F62;"> &quot;bsp_sht30.h&quot;</span></span>')
print("two lines:", shiki_lines(raw2))

# 模拟 handle_data 路径：data 已经被 html.parser 处理成什么？
from html.parser import HTMLParser


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_data(self, d):
        self.out.append(d)


p = P()
p.feed('<span style="x"> &lt;stdio.h&gt;</span>')
print("parser data:", p.out)
