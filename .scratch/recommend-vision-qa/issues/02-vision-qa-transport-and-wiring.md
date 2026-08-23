# 02 — 视觉问答传输层 + 装配（真视觉接线）

**要做什么：** 把 01 的供给回调接上真视觉：新模块把「条目 PDF + 题面 + 问题」变成答案（渲染题面页 → 视觉模型针对性作答 → 否定回答/失败判无），缓存键升级支持同图不同问题，装配点带出条目 PDF，`/api/recommend` 在视觉已配置且条目有原图时注入回调——用户走库内赛题推荐时，「走廊宽度」这类图内问题被真视觉自动消化。

**被谁阻塞：** 01 — 回调签名与编排已就位

**状态：** resolved

- [x] 新模块 `vision_qa.py`（薄传输层，照 vision.py 先例，不 import 生成流程）：`answer_figure_question(pdf_path, problem_text, question, *, render 与 vision 调用可注入) -> str | None`——`extraction.locate_topic_pages` 定位页范围 → `_render_page_png` 逐页渲染 → `describe_image_cached(png, "image/png", prompt=question)`（问题即 prompt）；回答含否定词（「没有」「未找到」「图上无」「无法」「不确定」）→ None；渲染/网络异常捕获 → None；多页答案拼接
- [x] `vision.describe_image_cached` 缓存键由 `sha256(image)` 升级为 `sha256(image + prompt)`（进程内缓存，无落盘兼容负担；现有调用方同图同 prompt 行为不变，既有 vision 测试全绿；新增同图异 prompt 双调用两次请求的测试）
- [x] `generator.TopicContext` 新增字段 `figure_pdf: Path | None = None`；`resolve_topic_context` 装配点：key 非空且条目带 original_pdf → 条目目录 + original_pdf 解析为路径带出；no-topic 形 / 无 original_pdf → None（缺省 None，旧调用方零改动）
- [x] `webapp.py` `/api/recommend`：视觉已配置（effective_vision_api_key 非空）且 `topic.figure_pdf` 非空 → 构造 `vision_qa` 闭包注入 `run_recommendation`；否则不注入（None）
- [x] `tests/test_vision_qa.py`：假 transport（照 vision.py 先例）验证「渲染 → 调用（prompt=问题）→ 答案返回 / 否定词判 None / 异常判 None」；`tests/test_generator.py` 或既有装配测试补 figure_pdf 装配用例（有 PDF 带出 / 无 PDF None / no-topic None）

## Comments

实施记录（2026-08）：

- 实现：`vision_qa.py` 新模块（`answer_figure_question`：locate_topic_pages 定位 → 逐页 `_render_page_png` → `describe_image_cached(prompt=问题引导)`；`VISION_NEGATIVE_PATTERNS` 七词表判无；逐页异常静默跳过；多页答案换行拼接；定位失败/定位抛错 → None，绝不抛出）；`vision.describe_image_cached` 缓存键升级 `sha256(image + prompt)`（同图多问各问独立）；`TopicContext.figure_pdf` 字段 + `_entry_figure_pdf` 装配（original_pdf 非空且文件存在才带出）；`webapp.py` /api/recommend 注入（`_resolve_vision` + `vision_configured` 判定，独立 vision-qa 观测器 finally 结算，未配置/无图 → None 零改动）。
- 测试：`tests/test_vision_qa.py` 16 用例（定位 1 页/多页、只渲染定位页开区间、否定词参数化、定位失败/定位抛错、渲染失败跳过、视觉抛错、多页拼接、全否定）；`tests/test_vision.py` +1（同图异 prompt 两次请求 + 同图同 prompt 命中）；`tests/test_generator.py` +3（带 PDF 带出、文件缺失 None、no-topic None）；`tests/test_webapp.py` +2 端到端（视觉配置 + 条目带 PDF → 问题被消化无 question 事件、答案进收敛澄清历史；视觉配置但 no-topic → 不注入照旧问用户）。
- Review（双轴自审）：Standards——中文注释/命名/常量单源合规；Spec——验收五条全满足。发现并修复：定位抛错（坏 PDF）未防御 → 包 try/except → None + 测试；vision.py 缓存注释键语义过时 → 同步更新。
- 回归：全量 2243 passed（含既有 2221 零回归；新增 22 用例）。
