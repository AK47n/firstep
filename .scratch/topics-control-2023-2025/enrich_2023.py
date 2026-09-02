"""工单 topics-control-2023-2025/03 步骤 7：触发 enrich_topic_image_notes 补图注。

三级降级链（视觉优先）：渲染视觉（未配置 → 失败静默）→ 文字标注兜底
（零额度，坐标重建布局）→ 内嵌图视觉（未配置 → 失败静默）。幂等，失败
不写回不抛。题面已含 [图N 标注] 后跳过。

注：webapp GET /api/topics/{key} 在 vision_configured 为假时不调 enrich
（视觉 gate）；本脚本直接调函数走完整三级降级链（视觉失败自动降级）。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import contest_generator.topic_library as _topic_lib  # noqa: E402
from contest_generator.topic_library import enrich_topic_image_notes  # noqa: E402

# 写回 topic.md 时的库内自动提交会 git add library/ 子域（卷入遗留变更），
# 改由人工精确提交——打桩为 no-op。
_topic_lib.commit_after_write = lambda *args, **kwargs: None

TOPICS_ROOT = REPO_ROOT / "library" / "topics"

for key in ("2023E", "2023G", "2023I"):
    before = (TOPICS_ROOT / key / "topic.md").read_text(encoding="utf-8")
    entry = enrich_topic_image_notes(
        TOPICS_ROOT,
        key,
        vision_base_url="",
        vision_api_key="",
        vision_model="",
    )
    after = (TOPICS_ROOT / key / "topic.md").read_text(encoding="utf-8")
    delta = len(after) - len(before)
    tail = after[len(before):].strip()[-160:] if delta else ""
    print(f"{key}: {'追加图注 ' + str(delta) + ' chars' if delta else '无新增'}")
    if delta:
        print(f"    图注段尾部: {tail!r}")
