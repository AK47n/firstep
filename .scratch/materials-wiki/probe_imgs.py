# -*- coding: utf-8 -*-
"""查正文内的图片真实形态（picture/srcset/lazy/base64）。"""
import re
import urllib.request

BASE = "https://wiki.lckfb.com"
url = f"{BASE}/zh-hans/dmx/module/sensor/grayscale-sensor.html"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
main = re.search(r"<main[^>]*>([\s\S]*?)</main>", html, flags=re.I)
seg = main.group(1) if main else html

print("=== picture 标签 ===")
for m in re.findall(r"<picture[\s\S]*?</picture>", seg)[:2]:
    print(m[:300])
    print("---")
print("=== img 标签全量（属性） ===")
for m in re.findall(r"<img[^>]+>", seg)[:8]:
    print(m[:250])
    print("---")
print("=== srcset ===")
print(re.findall(r"srcset=\"([^\"]+)\"", seg)[:3])
print("=== base64 内嵌 ===")
print("data:image 出现次数:", len(re.findall(r"data:image", seg)))
print("=== 视频/iframe ===")
print(re.findall(r"<(?:video|iframe)[^>]*>", seg)[:3])
