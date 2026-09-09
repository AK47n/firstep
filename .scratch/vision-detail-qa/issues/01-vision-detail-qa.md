# 01 后端核心：问答式精注记（vision-detail-qa）

Status: resolved

## 目标

视觉图注从单轮描述升级为"描述 + 一轮细节追问"：`extraction.py` 新增 `refine_image_description` 与 `DETAIL_QA_PROMPT` / `DETAIL_QA_NO_SUPPLEMENT`；`detail_qa: bool = True` 线程到 pdf_image_notes / pdf_page_render_notes / extract_image / extract_pdf_with_image_notes / enrich_topic_image_notes；`config.py` 新增 `vision_detail_qa: bool = True`；webapp 三处入口（/api/extract 图片+PDF、/api/topics/split、取题面增强）+ settings GET/PUT 接配置。

## 验收标准

- [x] `refine_image_description`：二轮有细节 → `描述；细节补充：<细节>`；二轮异常 / 空 / 否定（无补充/无需补充/没有补充/无更多）→ 原描述原样返回
- [x] `detail_qa=False` 时四个 extraction 函数零二轮调用（行为与现状一致）
- [x] `pdf_page_render_notes` 精注记在图文过滤之后（无图页不付二轮调用）
- [x] `config.py` `vision_detail_qa` 默认 True；非 bool 解析抛 ConfigError
- [x] settings GET 回 `vision_detail_qa`、PUT 解析 `_optional_bool(default=True)`
- [x] tests/test_extraction.py 新增 ≥4 用例、tests/test_config.py ≥1、tests/test_webapp.py ≥2，全绿
- [x] pytest 全量无回归

## 提交

中文提交信息；提交后 post-commit 自动补 CHANGELOG。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
