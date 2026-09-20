# -*- coding: utf-8 -*-
"""PDF 资料库真重复回收（白名单式，2026-09-20）。

请求：「PDF资料库里面看看是否真的重复，如果是真的重复就删掉」。

依据：`probe-01-verify.py` 全量 SHA256 复算——应用判据（同名+同大小，
static/js/fx/pdf.js:pdfDupGroups）在真实库上 15 组**全部**内容逐字节相同，
0 组假重复；全库内容分组也只有这 15 组（改名重复 0 组）。

形态：两组 lcdwiki 模块包（MSP2807 / ili9341 与 MSP3520 / ili9488）**各自
随包带一份同名通用文档**，这是原厂打包方式，不是抓取失误。故按「保留一份
删其余」处理。

**保留 ili9341 侧**：工单 `.scratch/wiki-stm32-batch10/issues/06-module-ili9341.md`
按名记录了该侧 `6-User_Manual/STM32_Keil_Use_Illustration_CN.pdf`；ili9488 侧
同文件无逐名引用。两侧内容逐字节相同，保留哪侧不影响可读性。

做法：移入 `sources/.trash-pdf/<日期>/<rel_path 镜像>`——**与应用「删除」
按钮同一条回收语义**（可手动恢复；`sources/materials` 未被 git 跟踪，
真删不可回滚）。脚本先逐组校验 SHA256 相同才动手，缺件/不一致 => 报告而非
猜测。

用法：
    python .scratch/pdf-dup-verify/probe-02-apply.py --check   # 只校验
    python .scratch/pdf-dup-verify/probe-02-apply.py           # 执行回收
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MATERIALS = REPO / "sources" / "materials"
TRASH = REPO / "sources" / ".trash-pdf"

# 两个 lcdwiki 模块包根（保留侧 / 回收侧）——下面 15 条相对路径在两侧镜像同名。
KEEP_ROOT = "lckfb-地阔星移植手册/网盘下载/ili9341/2.8inch_SPI_Module_ILI9341_MSP2807_V1.1"
DROP_ROOT = "lckfb-地阔星移植手册/网盘下载/ili9488/3.5inch_SPI_Module_ILI9488_MSP3520_V1.1"

# 白名单：15 条经 SHA256 证实逐字节相同的相对路径（每条 = 一组，回收 DROP 侧）
DUP_RELS: list[str] = [
    "6-User_Manual/STM32_Keil_Use_Illustration_CN.pdf",
    "6-User_Manual/STM32_Keil_Use_Illustration_EN.pdf",
    "6-User_Manual/PCtoLCD2002_Use_Illustration_CN.pdf",
    "6-User_Manual/PCtoLCD2002_Use_Illustration_EN.pdf",
    "6-User_Manual/C51_Keil&stc-isp_Use_Illustration_CN.pdf",
    "6-User_Manual/C51_Keil&stc-isp_Use_Illustration_EN.pdf",
    "6-User_Manual/Arduino_IDE_Use_Illustration_CN.pdf",
    "6-User_Manual/Arduino_IDE_Use_Illustration_EN.pdf",
    "6-User_Manual/Image2Lcd_Use_Illustration_CN.pdf",
    "6-User_Manual/Image2Lcd_Use_Illustration_EN.pdf",
    "Demo_Arduino/libs/LCDWIKI_GUI/Document/LCDWIKI GUI lib Manual.pdf",
    "Demo_Arduino/libs/LCDWIKI_SPI/Document/LCDWIKI SPI lib Manual.pdf",
    "Demo_Arduino/libs/LCDWIKI_TOUCH/Document/LCDWIKI TOUCH lib Manual.pdf",
    "Demo_Arduino/libs/LCDWIKI_SPI/Document/LCDWIKI SPI lib Supported display modules&controllers.pdf",
    "Demo_Arduino/libs/LCDWIKI_SPI/Document/LCDWIKI SPI lib Requirements.pdf",
]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只校验不动文件")
    args = parser.parse_args()

    date = time.strftime("%Y-%m-%d")
    problems: list[str] = []
    reclaimed = 0
    done = 0

    print("=" * 78)
    print("PDF 资料库真重复回收 · 白名单 15 组（保留 ili9341 侧）"
          + (" · 校验模式（不动文件）" if args.check else ""))
    print("=" * 78)

    for rel in DUP_RELS:
        keep = MATERIALS / KEEP_ROOT / rel
        drop = MATERIALS / DROP_ROOT / rel
        if not keep.is_file():
            problems.append(f"保留件缺失，拒绝动：{KEEP_ROOT}/{rel}")
            continue
        if not drop.is_file():
            print(f"  跳过（回收件已不在）：{rel}")
            continue
        keep_sha, drop_sha = sha256_of(keep), sha256_of(drop)
        if keep_sha != drop_sha:
            problems.append(f"内容不一致，拒绝动：{rel}（keep={keep_sha[:12]} drop={drop_sha[:12]}）")
            continue
        size = drop.stat().st_size
        reclaimed += size
        print(f"\n  保留 {KEEP_ROOT}/{rel}")
        print(f"        {size:>10,} B  sha={keep_sha[:12]}")
        print(f"  回收 {DROP_ROOT}/{rel}")
        if args.check:
            continue
        target = TRASH / date / DROP_ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():  # 同日重复回收：加数字后缀，不覆盖旧件（同 pdf_library.trash_pdf）
            counter = 1
            while True:
                candidate = target.with_name(f"{target.stem}_{counter}{target.suffix}")
                if not candidate.exists():
                    target = candidate
                    break
                counter += 1
        shutil.move(str(drop), str(target))
        done += 1
        print(f"        → {target.relative_to(REPO).as_posix()}")

    print()
    if problems:
        print("有问题，未完成：")
        for item in problems:
            print("  ✗", item)
        return 1
    if args.check:
        print(f"校验通过：{len(DUP_RELS)} 组内容逐字节相同，可回收 "
              f"{reclaimed / 1048576:.2f} MB（未动文件）")
        return 0
    print(f"完成：回收 {done} 个文件 / {reclaimed / 1048576:.2f} MB → "
          f"{TRASH.relative_to(REPO).as_posix()}/{date}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
