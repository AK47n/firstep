"""执行「改名重复」文档类去重（工单请求，2026-09-13）。

范围**白名单式**：只处理下面 `PLAN` 里逐条点名的文件，不做任何自动判定——
上一版探针（probe-03）用「排除词」过滤原厂树，会把 `Libraries/CMSIS/` 下的
结构性重复也当成候选，那是错的。这里改成显式清单，跑多少次都只动这几条。

做法：把冗余副本**移入** `sources/.trash-dedup/<日期>/`（镜像原路径，可手动恢复），
不真删——`sources/materials` 未被 git 跟踪，删了不可回滚。

保留原则：留中文 / 带语义的名字，回收英文名与 `(1)` 副本。

用法：python .scratch/library-dedup-audit/probe-04-apply-doc-dups.py [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MATERIALS = REPO / "sources" / "materials"
TRASH = REPO / "sources" / ".trash-dedup"

# (保留, [回收...]) —— 每组内容必须逐字节相同，脚本会先校验再动
PLAN: list[tuple[str, list[str]]] = [
    (
        "k230资料/canmv-ide-4.0.7.exe",
        ["2026_06_电赛视觉资料/05_canmv-ide-4.0.7.exe"],
    ),
    (
        "C7-3-4L ESP32-CAM开发板资料/开发资料/ESP32技术参考手册(中文).pdf",
        ["C7-3-4L ESP32-CAM开发板资料/开发资料/esp32_technical_reference_manual_cn.pdf"],
    ),
    (
        "C7-3-4L ESP32-CAM开发板资料/开发资料/ESP32数据手册(中文).pdf",
        ["C7-3-4L ESP32-CAM开发板资料/开发资料/esp32_datasheet_cn.pdf"],
    ),
    (
        "C7-3-4L ESP32-CAM开发板资料/开发资料/OV2640摄像头传感器数据手册.pdf",
        ["C7-3-4L ESP32-CAM开发板资料/开发资料/摄像头ov2640_ds_1.8_.pdf"],
    ),
    (
        "无线串口模块资料/DL-43P/DL-43P尺寸图(详细).pdf",
        ["无线串口模块资料/DL-43P/DL-43尺寸图 -详细.pdf"],
    ),
    (
        "2026_04_地猛星电赛控制题配套资料/【小车】01_TB6612接线定义.pdf",
        ["2026_04_地猛星电赛控制题配套资料/10_TB6612接线定义.pdf"],
    ),
    (
        "2026_06_电赛视觉资料/换源后缀.txt",
        ["2026_06_电赛视觉资料/换源后缀(1).txt"],
    ),
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

    planned = [(keep, drop) for keep, drops in PLAN for drop in drops]
    total = 0
    problems: list[str] = []

    print("=" * 78)
    print("改名重复（文档类）去重" + (" · 校验模式" if args.check else ""))
    print("=" * 78)

    for keep_rel, drop_rel in planned:
        keep = MATERIALS / keep_rel
        drop = MATERIALS / drop_rel
        if not keep.is_file():
            problems.append(f"保留件缺失：{keep_rel}")
            continue
        if not drop.is_file():
            print(f"  跳过（回收件已不在）：{drop_rel}")
            continue
        keep_sha, drop_sha = sha256_of(keep), sha256_of(drop)
        if keep_sha != drop_sha:
            problems.append(f"内容不一致，拒绝动：{drop_rel}")
            continue
        size = drop.stat().st_size
        total += size
        print(f"\n  保留 {keep_rel}")
        print(f"     {size:>12,} B  sha={keep_sha[:12]}")
        print(f"  回收 {drop_rel}")
        if args.check:
            continue
        date = time.strftime("%Y-%m-%d")
        target = TRASH / date / drop_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(f"{target.stem}_1{target.suffix}")
        shutil.move(str(drop), str(target))
        print(f"     → {target.relative_to(REPO).as_posix()}")

    print()
    if problems:
        print("有问题，未完成：")
        for item in problems:
            print("  ✗", item)
        return 1
    if args.check:
        print(f"校验通过：{len(planned)} 组内容一致，可回收 {total / 1048576:.2f} MB（未动文件）")
        return 0
    print(f"完成：回收 {total / 1048576:.2f} MB → {TRASH.relative_to(REPO).as_posix()}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
