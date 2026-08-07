# 03 — 选模块摘要行带套件身份

**What to build:** 选模块 AI 读到的候选清单行带上套件信息——格式变为 `- slug: 简介（套件: kit; 依赖: …）`，让 AI 推荐时能分辨"哪个套件的 UWB"、看懂简介里的赛题专用性。反向解析与正向格式保持同步（两处格式耦合）。

**Blocked by:** 01 — 硬件身份字段 + 新录入强制

**Status:** resolved

- [x] 候选清单行包含套件信息（有 kit 则显示，无 kit 不显示该段）
- [x] 选模块结果反解析出的 slug 与正向格式一致（不丢、不串）
- [x] FakeLLM 断言喂给 AI 的清单文本包含套件信息
- [x] 既有摘要行为（依赖显示、无依赖模块）不受影响

## Comments

- 2026-08-07 工单 03 完成（分支 ticket-module-desc-03，feat feafbcc，已合 main）。
  实现：摘要行 `- slug: 简介（套件: kit; 依赖: ...）`——套件段聚合平台条目
  kit（去重保序、有 kit 才显示）、source_url 不进摘要行；`_summary_slugs`
  反向解析与正向格式同步（round-trip 契约测试 + select_modules 实路径解析）；
  FakeLLM 断言清单文本含套件信息。
- 并发事故：本分支从 02 分支切出（共享检出竞态），历史含 02 的 1b9afbf；
  先合 02 再合 03 fast-forward 收尾，改动文件无重叠（本工单仅
  llm.py/test_llm.py）。
