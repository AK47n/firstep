"""红证/绿证探针：同一份「同功能两件同时被推荐」载荷，看两件是否同时进顶层 modules。

用法：
  $env:PYTHONPATH='src'; python .scratch/exclusive-group-gap-audit/probe-group-convergence.py

只读、零额度：真库 manifest → build_module_selection（生产解析层）→ 打印
顶层 modules 与被剔成员。红 = 同组两件同时在顶层；绿 = 只剩一件 + 另一件进
dropped_exclusive_members。

已并入组的样例（attitude-hold，jy61p 那单修好后的基准）作对照，证明探针能
分辨红/绿——否则「全绿」可能是探针本身没接上收敛链路。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "library" / "modules"

# (标签, 组 id, 期望同组的两件, 载荷需求层)
CASES: list[tuple[str, str, tuple[str, str], list[dict]]] = [
    (
        "对照·姿态组（已并入，应绿）",
        "attitude-hold",
        ("imu_uart", "jy61p"),
        [
            {"sentence": 4, "requirement": "沿直线与半圆弧路径自动行驶"},
            {"sentence": 12, "requirement": "无引导标记直线段航向保持"},
        ],
    ),
    (
        "候1·测距组",
        "distance",
        ("us016", "ir_distance"),
        [
            {"sentence": 3, "requirement": "测量车前障碍物距离并避障（超声波测距）"},
            {"sentence": 9, "requirement": "非接触测距判断落点（红外测距）"},
        ],
    ),
    (
        "候2·显示组",
        "display",
        ("lcd", "max7219"),
        [
            {"sentence": 2, "requirement": "彩屏显示实时数据与界面菜单"},
            {"sentence": 7, "requirement": "数码管显示比赛计时与得分"},
        ],
    ),
    (
        "候3·气压/海拔组",
        "barometer",
        ("bmp180", "ms5611"),
        [
            {"sentence": 5, "requirement": "气压海拔检测与爬楼计层"},
            {"sentence": 11, "requirement": "无人机定高闭环需要高精度气压计"},
        ],
    ),
    (
        "候4·声提示组",
        "sound-prompt",
        ("beep", "jq8900"),
        [
            {"sentence": 1, "requirement": "到点蜂鸣器提示报警"},
            {"sentence": 8, "requirement": "语音播报比赛成绩"},
        ],
    ),
    (
        "待拍板·LoRa × Zigbee",
        "?无线",
        ("as32", "zigbee_link"),
        [
            {"sentence": 6, "requirement": "双车之间远距离无线数据通信（LoRa 数传）"},
            {"sentence": 10, "requirement": "双机无线透传收发数据（Zigbee 链路）"},
        ],
    ),
    (
        "待拍板·定位组",
        "?定位",
        ("uwb_uart", "neo_6m"),
        [
            {"sentence": 13, "requirement": "室内定位测量坐标（UWB 基站）"},
            {"sentence": 14, "requirement": "室外卫星定位获取经纬度（GPS）"},
        ],
    ),
    (
        "待拍板·手机遥控链路",
        "?遥控",
        ("hc05", "esp01s"),
        [
            {"sentence": 15, "requirement": "手机蓝牙遥控小车（蓝牙串口）"},
            {"sentence": 16, "requirement": "手机 WiFi 遥控与数据上报（ESP-01S）"},
        ],
    ),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, str(ROOT / "src"))
    from contest_generator.manifest import (
        ModuleManifest,
        build_manifest_summaries,
        collect_exclusive_groups,
    )
    from contest_generator.selection import build_module_selection

    manifests = [
        ModuleManifest.load(p) for p in sorted(MODULES.iterdir()) if p.is_dir()
    ]
    summaries = build_manifest_summaries(manifests)
    known = [m.slug for m in manifests]

    print("真库组声明：")
    for group in collect_exclusive_groups(manifests):
        print(f"  {group.id}: {[m.slug for m in group.members]}")
    print()

    member_of: dict[str, str] = {}
    for group in collect_exclusive_groups(manifests):
        for member in group.members:
            member_of[member.slug] = group.id

    red = 0
    for label, group_id, pair, requirements in CASES:
        left, right = pair
        raw = {
            "requirements": [
                {
                    "sentence": req["sentence"],
                    "requirement": req["requirement"],
                    "modules": [
                        {
                            "slug": slug,
                            "reason": f"{req['requirement']}——用 {slug} 实现",
                        }
                    ],
                }
                for req, slug in zip(requirements, pair)
            ],
            "references": [],
            "questions": [],
        }
        selection = build_module_selection(
            raw, known_slugs=known, manifest_summaries=tuple(summaries)
        )
        both = left in selection.modules and right in selection.modules
        verdict = "红（两件同时在顶层 modules）" if both else "绿（只剩一件）"
        if both:
            red += 1
        gid_left = member_of.get(left)
        gid_right = member_of.get(right)
        print(f"[{label}] {left} × {right}")
        print(f"  同组：{left}={gid_left} {right}={gid_right}")
        print(f"  顶层 modules = {list(selection.modules)}")
        print(f"  dropped = {selection.dropped_exclusive_members}")
        print(f"  → {verdict}")
        print()

    print(f"红计数 = {red} / {len(CASES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
