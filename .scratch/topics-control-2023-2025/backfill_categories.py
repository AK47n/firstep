"""工单 topics-control-2023-2025/02：15 条老条目分类补标（一次性脚本）。

只改每条的 manifest.json（read_json → {**data, "category": value} →
write_json 原语，保留既有字段），不动 topic.md / PDF / programs /
hint_module_groups；不走 update_topic（它是题面/程序全量保存）。

幂等：目标条目 category 已是目标值 → 跳过；已标词表外 / 冲突值 → 失败退出
（人工介入），不覆盖。

不调 commit_after_write（其 git add 限定 library/ 子域，会把工作区遗留的
reference.json / 素材清单.txt 变更卷入）；改完由人工精确 add 15 个
manifest.json 统一提交（工单允许「统一一次提交」）。

用法：python .scratch/topics-control-2023-2025/backfill_categories.py [--dry-run]
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from contest_generator.entry_store import read_json, write_json  # noqa: E402
from contest_generator.manifest import MANIFEST_FILENAME  # noqa: E402
from contest_generator.topic_library import (  # noqa: E402
    TOPIC_CATEGORIES,
    validate_topic_category,
)

# 判定依据 = 各条目 topic.md 题名/正文（逐条复核一致，见工单记录）
BACKFILL: dict[str, str] = {
    "2018C": "control",  # 无线充电电动小车（本科）
    "2019A": "control",  # 电动小车动态无线充电系统（A 题）
    "2020C": "control",  # 坡道行驶电动小车（C 题）
    "2021F": "control",  # 智能送药小车（F题）
    "2022C": "control",  # 小车跟随行驶系统（C 题）
    "2022H": "control",  # 小车跟随行驶系统（H 题）【高职高专组】
    "2024H": "control",  # 自动行驶小车（H 题）【本科组/高职高专组】
    "2026A": "other",  # AC-AC变换电路（A题）
    "2026B": "other",  # "无源"交流电流表及无线读表器（B题）
    "2026C": "other",  # 基于无线通信的数字钥匙实验系统（C题）
    "2026D": "control",  # 陆空协同无人机系统（D题）
    "2026E": "control",  # 拼图装置（E题）
    "2026F": "other",  # 李萨如图形显示控制装置（F题）
    "2026G": "other",  # 周期信号测量分析装置（G题）
    "2026H": "control",  # 车载平衡滚球运动控制系统（H 题）
}


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    topics_root = REPO_ROOT / "library" / "topics"
    if not topics_root.is_dir():
        print(f"题库目录缺失：{topics_root}")
        return 1
    changed = 0
    skipped = 0
    for key, value in BACKFILL.items():
        entry_dir = topics_root / key
        if not (entry_dir / MANIFEST_FILENAME).is_file():
            print(f"[错误] {key}: manifest 不存在，跳过")
            return 1
        if value not in TOPIC_CATEGORIES:
            print(f"[错误] {key}: 目标 {value!r} 不在词表 {TOPIC_CATEGORIES}")
            return 1
        data = read_json(entry_dir, MANIFEST_FILENAME)
        current = data.get("category", "")
        if current == value:
            print(f"[跳过] {key}: category 已是 {value!r}")
            skipped += 1
            continue
        if current:
            # 已标了别的值（词表内）：人工介入，不覆盖
            print(f"[冲突] {key}: 现 category {current!r} != 目标 {value!r}，不覆盖")
            return 1
        validate_topic_category(value)  # 词表外（含空串）拒写
        if dry_run:
            print(f"[试跑] {key}: category '' -> {value!r}")
            changed += 1
            continue
        write_json(entry_dir, MANIFEST_FILENAME, {**data, "category": value})
        print(f"[已改] {key}: category '' -> {value!r}")
        changed += 1
    print(f"完成：改动 {changed} 条，跳过 {skipped} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
