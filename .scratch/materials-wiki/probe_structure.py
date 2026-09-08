# -*- coding: utf-8 -*-
"""探测 wiki 页面正文容器结构（一次性的结构调研）。"""
import re
import urllib.request

url = "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mpu6050-six-axis-sensor.html"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")

for pat in [
    r"<main[^>]*>",
    r'class="[^"]*VPDoc[^"]*"',
    r'class="[^"]*vp-doc[^"]*"',
    r'class="[^"]*VPContent[^"]*"',
    r'class="[^"]*theme-default-content[^"]*"',
    r'id="[^"]*content[^"]*"',
]:
    ms = re.findall(pat, html)
    print(pat, "->", ms[:3])

# main 标签上下文（正文边界）
m_main = re.search(r"<main[\s\S]*?</main>", html)
print("main len:", len(m_main.group(0)) if m_main else "no main")
if m_main:
    seg = m_main.group(0)
    # main 内第一个 h1/h2 标题
    heads = re.findall(r"<h[12][^>]*>(.*?)</h[12]>", seg, re.S)
    cleaned = [re.sub(r"<[^>]+>", "", h).strip() for h in heads[:5]]
    print("main 内标题:", cleaned)
    # main 内是否含网盘/代码
    print("main 含 pan:", "pan.baidu" in seg, "| 含 pre:", "<pre" in seg)
