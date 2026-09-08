# -*- coding: utf-8 -*-
"""立创·地阔星 STM32F103C8T6 wiki 模块移植手册批量抓取（工单 wiki-stm32 前置）。

与 fetch_wiki.py（地猛星 dmx 版）同管线复用：URL 清单在 dkx-module-urls.txt，
转换器 = contest_generator.wiki_md，抓取/解析/图片下载函数全部从 fetch_wiki 导入；
仅输出目录、索引标题与 URL 清单不同。

输出目录：资料库批次 sources/materials/lckfb-地阔星移植手册/
  - <cat>--<slug>.md   单页转文档（元数据头 + 正文 + 网盘索引）
  - images/<slug>/     页面图片
  - 模块索引.md         全部模块清单（分类/名称/链接/图片数/代码块数/网盘）
  - 网盘索引.md         全部网盘链接+提取码汇总

运行：python .scratch/materials-wiki/fetch_wiki_dkx.py [--limit N] [--only slug] [--force]
幂等：已存在的 .md 跳过（--force 重抓）；已存在的图片跳过；失败重试 3 次。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 与 fetch_wiki.py 同款处理：先允许脚本直接运行时导入仓库域模块
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 复用同目录地猛星版抓取器：funcs only（其 main 不随 import 执行）
from fetch_wiki import (  # noqa: E402
    BASE,
    build_md,
    cat_label,
    code_block_count,
    download_img,
    fetch,
    img_ext,
    parse_page,
    slug_of,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

URLS_TXT = Path(__file__).parent / "dkx-module-urls.txt"
# 与「lckfb-地猛星移植手册」对偶命名（用户拍板）
OUT_ROOT = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地阔星移植手册"
INDEX_TITLE = "立创·地阔星 STM32F103C8T6 模块移植手册索引"


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

    if full_run:
        index_lines = [f"# {INDEX_TITLE}", "",
                       f"- 共 {len(manifest)} 个模块页（抓取成功 {ok}，失败 {fail}）", ""]
        by_cat: dict[str, list] = {}
        for m in manifest:
            by_cat.setdefault(m["cat"], []).append(m)
        for cat in sorted(by_cat):
            index_lines.append(f"## {cat_label(cat)}")
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
        print("（调试模式：跳过索引重建）")

    print(f"\n完成：成功 {ok}，失败 {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
