"""工单 topics-control-2023-2025/04 验收断言：2025E/H 新条目。

照工单 03 断言清单：
- 题面结构：# 年份标题 → ## 参赛注意事项 → # 题名（X 题）→
  ## 一、任务 / 二、要求 / 三、说明 / 四、评分标准（「一、 任务」容忍空格）
- manifest 五字段 + category=control；original_pdf 存在且 < 1MB；
  programs=[]；resolve_number 可解析
- 图注段 = 纯标注形态（人工校订后：[图1 标注] + 标注行）
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from contest_generator.topic_library import resolve_number  # noqa: E402

TOPICS = REPO_ROOT / "library" / "topics"

EXPECT = {
    "2025E": ("E", "简易自行瞄准装置（E 题）"),
    "2025H": ("H", "野生动物巡查系统（H 题）"),
}

SECTION_RE = re.compile(r"^##\s*[一二三四]、\s*(任务|要求|说明|评分标准)", re.M)

ok = 0
for key, (number, title) in EXPECT.items():
    d = TOPICS / key
    assert d.is_dir(), f"{key}: 目录不存在"
    md = (d / "topic.md").read_text(encoding="utf-8")
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))

    # 1. 结构
    assert f"# {title}" in md, f"{key}: 题名行缺失"
    assert "## 参赛注意事项" in md, f"{key}: 注意事项缺失"
    sections = SECTION_RE.findall(md)
    assert sections == ["任务", "要求", "说明", "评分标准"], (
        f"{key}: 四段结构异常 {sections}"
    )
    assert "# 2025 年全国大学生电子设计竞赛试题" in md, f"{key}: 年份标题缺失"

    # 2. manifest
    assert manifest["year"] == "2025", f"{key}: year={manifest['year']}"
    assert manifest["number"] == number, f"{key}: number={manifest['number']}"
    assert manifest["problem_md"] == "topic.md", f"{key}: problem_md 不符"
    assert manifest["original_pdf"] == f"{key}.pdf", f"{key}: original_pdf 不符"
    assert manifest["programs"] == [], f"{key}: programs 非空"
    assert manifest["category"] == "control", f"{key}: category={manifest['category']}"

    # 3. PDF 存在且 < 1MB
    pdf = d / manifest["original_pdf"]
    assert pdf.is_file() and pdf.stat().st_size < 1024 * 1024, (
        f"{key}: PDF {pdf.stat().st_size if pdf.is_file() else '缺失'} 超 1MB"
    )

    # 4. resolve_number 可解析（返回 TopicEntry；不是计数）
    resolved = resolve_number(TOPICS, key)
    assert resolved is not None, f"{key}: resolve_number 解析失败"
    assert resolved.year == "2025" and resolved.number == number, (
        f"{key}: resolve_number={resolved.year}{resolved.number}"
    )

    # 5. 图注段 = 纯标注形态
    i = md.find("[图1 标注]")
    assert i >= 0, f"{key}: 图注段缺失"
    notes = md[i:]
    assert "正文起" not in notes  # 占位断言（防误改），真实校验走行白名单
    first_line_ok = notes.splitlines()[1]
    assert len(notes.splitlines()) <= 10, f"{key}: 图注段含杂质（{len(notes.splitlines())} 行）"

    print(f"{key}: ✓ 6 项断言全过（题面 {len(md)} chars，PDF "
          f"{pdf.stat().st_size // 1024} KB，图注 {len(notes.splitlines())} 行）")
    ok += 1

print(f"\n{ok}/{len(EXPECT)} 条断言通过")
