# -*- coding: utf-8 -*-
"""立创·地猛星 MSPM0G3507 wiki 模块移植手册批量抓取（工单 materials-wiki/01）。

从 wiki.lckfb.com 抓取全部模块页（screen/sensor/rf/control 四个分类）：
- 每页：标题 / 正文规范 Markdown（按原页顺序，wiki_md 转换）/ 图片（下载到
  images/<slug>/）/ 百度网盘链接与提取码
- 输出目录：资料库批次 sources/materials/lckfb-地猛星移植手册/
  - <slug>.md          单页转文档（元数据头 + 正文 + 网盘索引）
  - images/<slug>/    页面图片
  - 模块索引.md        全部模块清单（分类/名称/链接/图片数/代码块数/网盘）
  - 网盘索引.md        全部网盘链接+提取码汇总

运行：python .scratch/materials-wiki/fetch_wiki.py [--limit N] [--only slug] [--force]
幂等：已存在的 .md 跳过（--force 重抓）；已存在的图片跳过；失败重试 3 次；
日志打印进度。转换器 = contest_generator.wiki_md（Shiki 逐行还原 / 原页顺序 /
行号 wrapper 隔离），见 src/contest_generator/wiki_md.py。
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path

# 允许本脚本直接运行时导入仓库域模块（sys.path[0] = 脚本目录，不含仓库根）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contest_generator.wiki_md import build_markdown, code_block_count, img_ext, parse_main  # noqa: E402

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


def parse_page(html: str, slug: str) -> dict:
    """单页解析：标题 / 正文（wiki_md 转换）/ 图片 / 网盘。

    正文边界 = `<main class="main">`（VuePress 真实内容区，含四章节 /
    代码 / 图片 / 网盘；`content-body` 是全页壳不可用）。正文与图片由
    contest_generator.wiki_md 统一转换（Shiki 逐行还原 / 原页顺序），
    客户端懒加载图片（SSR HTML 中是 <!---->）抓不到，属已知局限。
    """
    title_m = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
    title = title_m.group(1).strip() if title_m else ""

    main_m = re.search(r"<main[^>]*>([\s\S]*?)</main>", html, flags=re.I)
    main_html = main_m.group(1) if main_m else html

    md_body, img_urls = parse_main(main_html, slug)
    pan_links = extract_pan_links(main_html)
    return {"title": title, "md_body": md_body, "img_urls": img_urls,
            "pan_links": pan_links}


def build_md(slug: str, cat: str, page: dict, url: str) -> str:
    """单篇手册：元数据头 + 正文（原页顺序）+ 网盘小节（wiki_md 统一组装）。"""
    return build_markdown(
        slug=slug,
        cat=cat,
        url=BASE + url,
        title=page["title"],
        md_body=page["md_body"],
        img_urls=page["img_urls"],
        pan_links=page["pan_links"],
    )


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
        page = parse_page(html, slug)
        # 下载图片（与 wiki_md 同规则命名：img{序号}{扩展名}；已存在跳过——幂等）
        img_ok = 0
        if page["img_urls"]:
            for i, img_url in enumerate(page["img_urls"], 1):
                dest = OUT_ROOT / "images" / slug / f"img{i}{img_ext(img_url)}"
                if dest.exists():
                    img_ok += 1
                    continue
                if download_img(img_url, dest):
                    img_ok += 1
        md_path.write_text(build_md(slug, cat, page, url), encoding="utf-8")
        manifest.append({"slug": slug, "cat": cat, "url": url,
                         "codes": code_block_count(page["md_body"]),
                         "imgs": img_ok,
                         "pan_links": page["pan_links"]})
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
                    f"图 {m.get('imgs', 0)}｜网盘 {len(m.get('pan_links') or [])}"
                )
            index_lines.append("")
        (OUT_ROOT / "模块索引.md").write_text("\n".join(index_lines), encoding="utf-8")

        pan_lines = ["# 网盘下载索引（百度网盘，需登录下载）", "",
                     f"- 共 {sum(len(m.get('pan_links') or []) for m in manifest)} 个网盘链接", ""]
        for m in sorted(manifest, key=lambda x: (x["cat"], x["slug"])):
            for link in m.get("pan_links") or []:
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
