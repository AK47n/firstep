"""工单 topics-control-2023-2025/05 步骤 1：后端断言（全库验收）。

- 全库 20 条：category ∈ {control, other} 且非空（list_topics 真库状态）
- 5 道新题（2023E/G/I、2025E/H）：topic.md 结构四段 + # 题名（X 题）；
  manifest 五字段 + category=control；original_pdf 存在且 < 1MB 且
  指向小题 PDF（文件名 = <KEY>.pdf，非 34MB 汇编副本）；resolve_number 可解析
- 图注：题面引用「图 N」的条目已含 [图N 标注 或 [示意图（enrich 幂等）；
  未引用图的条目合法跳过
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from contest_generator.topic_library import (  # noqa: E402
    TOPIC_CATEGORIES,
    list_topics,
    resolve_number,
)

TOPICS = REPO_ROOT / "library" / "topics"
NEW_KEYS = ("2023E", "2023G", "2023I", "2025E", "2025H")
NEW_TITLES = {
    "2023E": "运动目标控制与自动追踪系统（E 题）",
    "2023G": "空地协同智能消防系统（G 题）",
    "2023I": "气垫悬浮车（I 题）",
    "2025E": "简易自行瞄准装置（E 题）",
    "2025H": "野生动物巡查系统（H 题）",
}
SECTION_RE = re.compile(r"^##\s*[一二三四]、\s*(任务|要求|说明|评分标准)", re.M)

# 1. 全库 20 条 category 非空合法
entries = list_topics(TOPICS)
assert len(entries) == 20, f"全库条目数 = {len(entries)}（应 20）"
by_key = {e.key: e for e in entries}
for key, e in by_key.items():
    assert e.category in TOPIC_CATEGORIES and e.category, (
        f"{key}: category={e.category!r} 非空且 ∈ 词表"
    )
controls = sorted(k for k, e in by_key.items() if e.category == "control")
assert all(k in controls for k in NEW_KEYS), f"5 新题应全为 control：{controls}"
print(f"1. 全库 {len(entries)} 条 category 非空合法 ✓（control {len(controls)} 条）")

# 2. 5 新题结构 / manifest / PDF / resolve_number / 图注
for key in NEW_KEYS:
    d = TOPICS / key
    md = (d / "topic.md").read_text(encoding="utf-8")
    mf = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    # 结构
    assert re.search(rf"# {re.escape(NEW_TITLES[key])}", md), f"{key}: 题名行缺失"
    sections = SECTION_RE.findall(md)
    assert sections == ["任务", "要求", "说明", "评分标准"], (
        f"{key}: 四段结构异常 {sections}"
    )
    # manifest
    for field in ("year", "number", "problem_md", "original_pdf", "programs", "category"):
        assert field in mf, f"{key}: manifest 缺 {field}"
    assert mf["category"] == "control" and mf["programs"] == [], f"{key}: category/programs"
    # PDF 判据：文件名 = <KEY>.pdf（小题，非 34MB 汇编副本）
    assert mf["original_pdf"] == f"{key}.pdf", (
        f"{key}: original_pdf={mf['original_pdf']} 非小题 PDF"
    )
    pdf = d / mf["original_pdf"]
    assert pdf.is_file() and pdf.stat().st_size < 1024 * 1024, (
        f"{key}: 小题 PDF 缺失/超 1MB"
    )
    # resolve_number
    entry = resolve_number(TOPICS, key)
    assert entry is not None and entry.year == mf["year"] and entry.number == mf["number"], (
        f"{key}: resolve_number 解析失败"
    )
    # 图注：5 新题题面均引用「图 N」且已含 [图N 标注（enrich 幂等结果）。
    # 2023E/G/I = 视觉图注（GET /api/topics/{key} 触发 enrich，webapp 视觉
    # 通道可用，2026-09-02 12:36 起 3 题已自动补图注并提交，见 git log
    # b09968cd/29227009/b918e297）；2025E/H = 文字标注兜底 + 人工校订形态
    # （[图1 标注] + 标注行）。幂等：题面含 [图N 标注 前缀 → enrich 跳过，
    # 人工校订形态不会被覆盖。
    assert re.search(r"\[图\d+ 标注", md), f"{key}: 题面引图但无图注段"
    print(f"2. {key}: 结构/manifest/PDF {pdf.stat().st_size//1024}KB/"
          f"resolve_number/图注 ✓")

print("后端断言全部通过 ✓")
