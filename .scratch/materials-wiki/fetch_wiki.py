# -*- coding: utf-8 -*-
"""立创·地猛星 MSPM0G3507 wiki 模块移植手册批量抓取（工单 materials-wiki/01）。

从 wiki.lckfb.com 抓取全部模块页（screen/sensor/rf/control 四个分类）：
- 每页：标题 / 分类 / 正文纯文本（保留章节结构）/ 代码块（C 源码文本）/
  图片（下载到 images/<slug>/）/ 百度网盘链接与提取码
- 输出目录：资料库批次 sources/materials/lckfb-地猛星移植手册/
  - <slug>.md          单页转文档（正文+代码+网盘索引）
  - images/<slug>/    页面图片
  - 模块索引.md        全部模块清单（分类/名称/链接/图片数/代码块数/网盘）
  - 网盘索引.md        全部网盘链接+提取码汇总

运行：python .scratch/materials-wiki/fetch_wiki.py [--limit N] [--only slug]
幂等：已存在的 .md 跳过（--force 重抓）；失败重试 3 次；日志打印进度。
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path

# Windows 控制台默认 GBK：打印中文/UTF-8 字符（如 URL 中的非 ASCII）会
# UnicodeEncodeError 崩溃 —— 强制 UTF-8 输出（Py3.7+ 支持 reconfigure）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://wiki.lckfb.com"
URLS_TXT = Path(__file__).parent / "module-urls.txt"
OUT_ROOT = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) firstep-wiki-fetch"}


def fetch(url: str, retries: int = 3, timeout: int = 20) -> bytes | None:
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            if attempt == retries:
                print(f"  [失败] {url}：{exc}")
                return None
            time.sleep(2 * attempt)
    return None


def slug_of(url: str) -> tuple[str, str]:
    """URL → (分类, slug)。如 .../sensor/mpu6050...html → (sensor, mpu6050-...)。"""
    parts = url.rstrip("/").split("/")
    cat = parts[-2]
    slug = re.sub(r"\.html$", "", parts[-1])
    return cat, slug


def clean_text(html: str) -> str:
    """HTML → 纯文本（保留换行与空格；解码实体）。"""
    import html as html_mod

    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(p|div|h[1-6]|li|tr|pre)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def extract_codes(html: str) -> list[str]:
    """提取所有 <pre><code> 代码块文本（去除 span/行号噪音）。"""
    blocks = re.findall(r"<pre[^>]*><code[^>]*>([\s\S]*?)</code></pre>", html, flags=re.I)
    codes = []
    for block in blocks:
        # 去掉 <span ...> 标签（shiki 高亮），保留文本
        text = re.sub(r"</span>", "\n", block)
        text = re.sub(r"<span[^>]*>", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        import html as html_mod

        codes.append(html_mod.unescape(text).strip())
    return codes


def extract_imgs(html: str) -> list[str]:
    """提取正文图片 URL（绝对或相对路径）；过滤 logo/图标。"""
    imgs = re.findall(r'src="([^"]+\.(?:png|jpg|jpeg|webp|gif))"', html, flags=re.I)
    out = []
    for src in imgs:
        if "logo" in src.lower() or "icon" in src.lower():
            continue
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = BASE + src
        elif not src.startswith("http"):
            src = BASE + "/" + src
        out.append(src)
    # 去重保序
    seen, dedup = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup


def extract_pan_links(html: str) -> list[str]:
    """提取百度网盘链接（含 ?pwd= 提取码）。"""
    links = re.findall(r"https?://pan\.baidu\.com/s/[A-Za-z0-9_\-?=]+", html)
    seen, dedup = set(), []
    for l in links:
        if l not in seen:
            seen.add(l)
            dedup.append(l)
    return dedup


def download_img(url: str, dest: Path, retries: int = 2) -> bool:
    data = fetch(url, retries=retries)
    if data is None:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def parse_page(html: str) -> dict:
    """单页解析：标题 / 正文 / 代码 / 图片 / 网盘。

    正文边界 = `<main class="main">`（VuePress 真实内容区，含四章节 /
    代码 / 网盘；`content-body` 是全页壳不可用）。
    """
    title_m = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
    title = title_m.group(1).strip() if title_m else ""

    main_m = re.search(r"<main[^>]*>([\s\S]*?)</main>", html, flags=re.I)
    body_html = main_m.group(1) if main_m else html

    # 正文纯文本
    body_text = clean_text(body_html)
    codes = extract_codes(body_html)
    imgs = extract_imgs(body_html)
    pans = extract_pan_links(body_html)
    return {"title": title, "body": body_text, "codes": codes, "imgs": imgs, "pans": pans}


def build_md(slug: str, cat: str, page: dict, url: str) -> str:
    lines = [
        f"# {slug}",
        "",
        f"- 分类：{cat}",
        f"- 来源：{url}",
        f"- 标题：{page['title']}",
        f"- 代码块：{len(page['codes'])} 个 · 图片：{len(page['imgs'])} 张",
        "",
        "## 正文",
        "",
        page["body"] or "（正文提取为空）",
        "",
        "## 代码块",
        "",
    ]
    for i, code in enumerate(page["codes"], 1):
        lines.append(f"### 代码 {i}")
        lines.append("")
        lines.append("```c")
        lines.append(code)
        lines.append("```")
        lines.append("")
    if page["pans"]:
        lines.append("## 百度网盘下载")
        lines.append("")
        for link in page["pans"]:
            lines.append(f"- {link}")
        lines.append("")
    lines.append("## 图片")
    lines.append("")
    if page["imgs"]:
        for i, img in enumerate(page["imgs"], 1):
            lines.append(f"- ![img{i}](images/{slug}/img{i}.png)")
    else:
        lines.append("（无）")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只抓前 N 个（调试）")
    parser.add_argument("--only", default="", help="只抓 slug 含该子串的页面")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的 .md")
    args = parser.parse_args()

    urls = [u.strip().lstrip("\ufeff") for u in URLS_TXT.read_text(encoding="utf-8-sig").splitlines() if u.strip()]
    full_run = not (args.only or args.limit)
    if args.only:
        urls = [u for u in urls if args.only in u]
    if args.limit:
        urls = urls[: args.limit]

    print(f"共 {len(urls)} 页，输出根：{OUT_ROOT}")
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    ok = fail = 0
    for idx, url in enumerate(urls, 1):
        cat, slug = slug_of(url)
        md_path = OUT_ROOT / f"{cat}--{slug}.md"
        if md_path.exists() and not args.force:
            print(f"[{idx}/{len(urls)}] 跳过（已存在）：{slug}")
            manifest.append({"slug": slug, "cat": cat, "url": url})
            ok += 1
            continue
        print(f"[{idx}/{len(urls)}] 抓取：{slug}")
        raw = fetch(BASE + url)
        if raw is None:
            fail += 1
            continue
        html = raw.decode("utf-8", errors="replace")
        page = parse_page(html)
        # 下载图片
        img_ok = 0
        if page["imgs"]:
            for i, img_url in enumerate(page["imgs"], 1):
                ext = Path(img_url.split("?")[0]).suffix or ".png"
                dest = OUT_ROOT / "images" / slug / f"img{i}{ext}"
                if download_img(img_url, dest):
                    img_ok += 1
        md_path.write_text(build_md(slug, cat, page, BASE + url), encoding="utf-8")
        manifest.append({"slug": slug, "cat": cat, "url": url,
                         "codes": len(page["codes"]), "imgs": img_ok,
                         "pans": page["pans"]})
        ok += 1
        if idx % 5 == 0:
            print(f"  进度 {idx}/{len(urls)}（成功 {ok}，失败 {fail}）")

    # 索引文件（仅全量模式重建——--only/--limit 是调试抓取，避免覆盖全量索引）
    if full_run:
        index_lines = ["# 立创·地猛星 MSPM0G3507 模块移植手册索引", "",
                       f"- 共 {len(manifest)} 个模块页（抓取成功 {ok}，失败 {fail}）", ""]
        by_cat: dict[str, list] = {}
        for m in manifest:
            by_cat.setdefault(m["cat"], []).append(m)
        for cat in sorted(by_cat):
            index_lines.append(f"## {cat}")
            index_lines.append("")
            for m in sorted(by_cat[cat], key=lambda x: x["slug"]):
                index_lines.append(
                    f"- {m['slug']}：[原页]({BASE + m['url']})｜代码 {m.get('codes', 0)}｜"
                    f"图 {m.get('imgs', 0)}｜网盘 {len(m.get('pans') or [])}"
                )
            index_lines.append("")
        (OUT_ROOT / "模块索引.md").write_text("\n".join(index_lines), encoding="utf-8")

        pan_lines = ["# 网盘下载索引（百度网盘，需登录下载）", "",
                     f"- 共 {sum(len(m.get('pans') or []) for m in manifest)} 个网盘链接", ""]
        for m in sorted(manifest, key=lambda x: (x["cat"], x["slug"])):
            for link in m.get("pans") or []:
                pan_lines.append(f"- [{m['slug']}] {link}")
        (OUT_ROOT / "网盘索引.md").write_text("\n".join(pan_lines), encoding="utf-8")
    else:
        print("（调试模式：跳过索引重建，'模块索引.md' 保留全量版）")

    print(f"\n完成：成功 {ok}，失败 {fail}")
    print(f"索引：{OUT_ROOT / '模块索引.md'}")
    print(f"网盘：{OUT_ROOT / '网盘索引.md'}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
