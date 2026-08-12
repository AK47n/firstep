"""归档 pid 模块剥离出的决策层素材（ADR 0009，工单 module-universalization/03）。

决策逻辑（stm32 十字路口/路由/K230 动态路口/远端导航/药房状态机/路径记忆；
mspm0 LAP 启停线一圈停车状态机）已从 library/modules/pid 剥离归生成骨架。
原工程全文保留在 sources/contest/{2021F,2026H}，本脚本把可编译决策源码
归档进参考文件库（只读不编译，LLM 生成骨架时学习素材）——与 car-1-1 先例同款。

条目：
- 21F-巡线送药决策例程（platform=stm32，锚定 2021F）
- 26H-滚球巡线决策例程（platform=mspm0，锚定 2026H——26H 生成线为 mspm0，
  素材是 stm32 Keil 源工程，描述已注明；决策逻辑经移植为 pid_mspm0 驱动）
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from contest_generator import config  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    ANCHOR_KIND_TOPIC,
    ARCHIVE_ENTRY_TYPE,
    add_reference,
    get_reference,
    list_references,
)

REFERENCE_ROOT = config.reference_library_dir(REPO_ROOT / "library" / "modules")

# 决策层可编译源码（原工程全文），相对 sources/contest/<year>/<dir>/
ENTRIES = [
    {
        "title": "21F-巡线送药决策例程",
        "anchor_value": "2021F",
        "src_dir": REPO_ROOT / "sources" / "contest" / "2021F" / "21F",
        "files": [
            "code/pid.c",
            "code/pid.h",
            "code/gray_track.c",
            "code/gray_track.h",
            "user/isr.c",
            "user/main.c",
        ],
        "description": (
            "2021F 巡线送药小车决策层源码（stm32 Keil 原工程，决策素材）："
            "pid.c 含十字路口状态机与路由表（路径记忆返程）、K230 动态路口决策"
            "（top2 置信度）、远端导航（大T/小T 字路口 + 返程）、药房送达/掉头"
            "状态机；gray_track.c 含十字/T字/返程T字路口检测与停车区黑白块检测；"
            "isr.c 含 TIM3 10ms 调度（编码器 → 速度闭环）。决策逻辑已按 ADR 0009 "
            "从 pid 模块剥离归生成骨架，本条目为 LLM 学习素材（只读不编译）。"
        ),
        "platform": PLATFORM_STM32,
    },
    {
        "title": "26H-滚球巡线决策例程",
        "anchor_value": "2026H",
        "src_dir": REPO_ROOT / "sources" / "contest" / "2026H" / "26H",
        "files": [
            "code/pid.c",
            "code/pid.h",
            "code/gray_track.c",
            "code/gray_track.h",
            "user/isr.c",
            "user/main.c",
        ],
        "description": (
            "2026H 滚球题一圈巡线决策层源码（stm32 Keil 原工程，决策素材；"
            "26H 生成线为 mspm0，决策逻辑经移植为 pid_mspm0 驱动）：pid.c 含 "
            "LAP 启停线一圈停车状态机（IDLE→LEAVING_START→RUNNING→STOPPING→"
            "STOPPED，启停线消抖/离场冷却）+ 运行计时 + K230 钢珠坐标消费；"
            "gray_track.c 含启停线检测（≥4 路黑）与停车区黑白块检测。决策逻辑"
            "已按 ADR 0009 从 pid 模块剥离归生成骨架，本条目为 LLM 学习素材"
            "（只读不编译）。"
        ),
        "platform": PLATFORM_MSPM0,
    },
]


def main() -> None:
    existing = {e.id for e in list_references(REFERENCE_ROOT)}
    for spec in ENTRIES:
        files: dict[str, str] = {}
        for rel in spec["files"]:
            path = spec["src_dir"] / rel
            if not path.is_file():
                print(f"[跳过] 文件缺失：{path}")
                continue
            files[rel] = path.read_text(encoding="utf-8", errors="replace")
        if not files:
            print(f"[跳过] 无文件可入库：{spec['title']}")
            continue
        entry = add_reference(
            REFERENCE_ROOT,
            title=spec["title"],
            type=ARCHIVE_ENTRY_TYPE,
            description=spec["description"],
            anchor_kind=ANCHOR_KIND_TOPIC,
            anchor_value=spec["anchor_value"],
            files=files,
            kit_vocabulary=(),
            platform=spec["platform"],
        )
        print(
            f"[入库] {entry.id}  type={entry.type}  platform={entry.platform}  "
            f"anchor={entry.anchor_kind}:{entry.anchor_value}  文件 {len(files)} 个"
        )
        print(f"       校验回读：{get_reference(REFERENCE_ROOT, entry.id).title}")


if __name__ == "__main__":
    main()
