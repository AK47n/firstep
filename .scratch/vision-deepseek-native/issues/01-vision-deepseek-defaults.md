# 01 — 视觉通道默认切 DeepSeek：默认值 + key 复用 + BMP 报错 + 观测/文案

**What to build:** 视觉通道（src/contest_generator/vision.py）默认端点从智谱 GLM-4.6V-Flash 切换到 DeepSeek 官方视觉模型 `deepseek-v4-flash-vision-exp`；视觉 key 留空时在装配层自动复用主 DeepSeek key（守卫：仅当视觉 base_url 为 DeepSeek 官方端点）；.bmp 直接上传给友好中文报错；观测 provider 标签与未配置文案同步去智谱化。spec：`.scratch/vision-deepseek-native/spec.md`（用户已确认方案与测试决策）。

**Status:** resolved

## 背景

用户已有 DeepSeek key（主 LLM 即 DeepSeek）；此前视觉通道默认智谱，需单独注册智谱账号配第二套 key（「给 DeepSeek 装眼睛」）。DeepSeek 2026-08-21 上线视觉模型 `deepseek-v4-flash-vision-exp`（OpenAI 兼容 /chat/completions，`https://api.deepseek.com`，仅 JPEG/PNG/GIF/WebP，单图 384 token 封顶）。请求协议与现有 vision.py 逐字兼容，传输/重试/缓存/解析零改动。

赛题库 PDF 实测（.scratch/vision-deepseek-native/pdf_image_scan.py，261 页长 PDF + 2026C + 2021F）：**BMP 0 处**；长 PDF 472 张图 = JPEG 230 + PNG 230 + **JPEG2000(.jp2) 12**（DeepSeek 不支持 → 按既有「单张失败静默跳过」降级，约 2.5%，可接受，不引入新依赖转换）。

## 实施决策（spec 已定，实现照此）

- 默认值单源：`vision.DEFAULT_VISION_BASE_URL` → `"https://api.deepseek.com"`，`vision.DEFAULT_VISION_MODEL` → `"deepseek-v4-flash-vision-exp"`；config 层沿用既有导入，不新增配置键。
- key 复用 helper：`effective_vision_api_key(vision_api_key, main_api_key, vision_base_url)`——视觉 key 非空 → 原样；空 + base_url ∈ DeepSeek 官方端点（`https://api.deepseek.com` / `https://api.deepseek.com/v1`，容忍尾斜杠）→ 返回主 key；空 + 自定义端点 → 空串（自定义服务须自备 key，不把主 key 发给别家）。helper 定义在 vision.py（端点知识归属），**在 webapp 装配层调用**（config 保持「原始值」语义，设置页回显不因复用失真）。
- 四个装配点改用有效 key：/api/extract 图片路径与 PDF 路径、/api/topics/split 的视觉图注、/api/topics/{key} 存量补图注；后两处的「配了视觉 key」守卫改为按有效 key 判定。
- 观测 provider 标签 `"zhipu"` → `"deepseek"`；`VisionNotConfiguredError` 文案改为引导「填写视觉 key 或复用主 key」，保留「未配置」字样（既有测试 match 依赖）；429 不重试维持；限流文案去掉「免费层」暗示。
- .bmp 直接上传：`extract_image` 入口拦截，`ExtractionError` 中文提示转存 PNG/JPEG（`IMAGE_FILE_SUFFIXES` 保留 .bmp 以走图片路由 → 友好报错；PDF 内嵌 bmp 的 mime 映射不变，失败静默跳过）。
- 注释/文档字符串去 GLM 化：vision.py 模块 docstring、config.py L54 注释、extraction.py L47/L313、topic_library.py L217。

## 测试决策（spec 已定 seam：vision.Transport 假件 + config tmp_path + webapp TestClient 夹具）

- 更新既有断言：tests/test_config.py L105-107 与 L186-202（默认 base/model 字面量）、tests/test_webapp.py `test_settings_vision_fields_roundtrip_and_mask`（GET 默认值字面量）。
- 新增：`effective_vision_api_key` 三分支（空 key + DeepSeek base → 主 key；空 key + 自定义 base → 空；显式 key 优先）；.bmp 上传 → ExtractionError 中文提示（400）。
- **行为语义更新（实现时发现的 spec 未列项，照 spec 行为约定修正）**：key 复用后「未配视觉 key + 默认 DeepSeek base + 主 key 在」= 视觉生效，故：
  - `test_extract_image_without_vision_key_returns_actionable_error` 改为「自定义视觉 base + 无视觉 key」场景（守卫应拒绝复用，仍 400 可操作提示）；
  - `test_topics_split_without_vision_key_stays_plain_text` 改为「自定义视觉 base + 无视觉 key」场景（保持纯文本断言）。
- 不更新（显式传自定义值，行为不变）：tests/test_extraction.py 图注用例的 `vision_model="glm-4.6v-flash"` / 空串参数、test_topic_library.py 视觉参数。

## 文件边界

- src：`src/contest_generator/vision.py`（默认值/helper/provider/文案/docstring）、`webapp.py`（4 装配点 + 守卫 + 注释）、`extraction.py`（BMP 拦截 + 注释）、`config.py`（仅注释）、`topic_library.py`（仅注释）。
- tests：`tests/test_vision.py`、`tests/test_config.py`、`tests/test_webapp.py`、`tests/test_extraction.py`。
- 不动：请求形状、重试参数、429 策略、sha256 缓存、8 张/4MB 上限、设置页三字段结构（文案归工单 02）、index.html、CONTEXT.md。

## 验收标准

- [x] 红证先行：helper 三分支测试先写（不存在 → 红）；BMP 拦截测试先写（当前会发请求 → 红）；行为语义两测试先改（复用后 → 红）
- [x] 全量 pytest 绿 + `mypy src` 干净
- [x] 默认值字面量断言 = DeepSeek 官方端点与模型名；config 回写/掩码语义不变
- [x] 显式视觉 key 优先于复用（既有显式 key 用例全绿）；自定义 base 不把主 key 发出去

## 实施提示词（新会话粘贴）

> 工单：`.scratch/vision-deepseek-native/issues/01-vision-deepseek-defaults.md`（先读全文）+ spec：`.scratch/vision-deepseek-native/spec.md`。
> 任务：视觉通道默认切 DeepSeek（默认值 + effective_vision_api_key 复用 + BMP 拦截 + provider/文案去智谱化 + webapp 4 装配点）。
> 文件边界：src 只动 vision.py / webapp.py / extraction.py / config.py(注释) / topic_library.py(注释)；tests 动 test_vision / test_config / test_webapp / test_extraction。index.html 与 CONTEXT.md 不动（工单 02）。
> 验收：红证先行（helper 三分支、BMP 拦截、两个行为语义测试）→ 绿 + 全量 pytest + `mypy src`；完成后证据写 Comments，Status 改 resolved。

## Comments

**2026-08-21 实施闭环（TDD 红证 → 绿 + 双轴 code-review 全项落实）**

### 红证（先写先跑）

- test_vision.py：`effective_vision_api_key` 三分支测试先写 → ImportError 红（helper 不存在）；provider 观测测试（FakeObservationCollector 断言 provider="deepseek"）。
- test_extraction.py：`.bmp` 直传拦截测试（哨兵 lambda「不该走到这里」+ raises，当前 DID NOT RAISE 红）；PDF 内嵌 BMP 跳过测试（当前会把 BMP 发出 → 图注 2 条红）。
- test_webapp.py：`test_extract_image_reuses_main_key_when_vision_key_blank` / `test_topics_split_reuses_main_key_when_vision_key_blank` 端到端红证（旧装配不复用 → 400 / 纯文本），装配改后转绿。

### 行为语义更新（spec 测试决策的补充，实现时发现）

key 复用后「未配视觉 key + 默认 DeepSeek base + 主 key 在」= 视觉生效，三个「未配 key = 关闭」语义测试改为**自定义视觉 base 场景**（守卫拒绝复用、主 key 不发给别家）：`test_extract_image_without_vision_key_returns_actionable_error`、`test_topics_split_without_vision_key_stays_plain_text`、`test_topic_get_without_vision_key_returns_plain`。

### 实现（src 5 文件）

- vision.py：默认值两常量切 DeepSeek；`DEEPSEEK_VISION_BASE_URLS` 白名单（官方端点 + /v1 形态）+ `effective_vision_api_key` 三分支；provider zhipu→deepseek；429 文案去「免费层」；未配置文案引导复用（评审微调：加「主 key 已配置时」防主 key 也空时失真）；模块 docstring 重写。
- webapp.py：**`_resolve_vision(config)` 装配 helper**（评审 Duplicated Code 项：原 3+4 处重复收拢为单点）——返回 (base_url, api_key, model)，四消费点（/api/extract 图片+PDF、/api/topics/split、/api/topics/{key}）共用；后两处守卫按有效 key 判定。
- extraction.py：`extract_image` 入口 .bmp 拦截（400 中文引导转存）；`pdf_image_notes` 发送前按后缀跳过 .bmp（评审功能缺口项：DeepSeek 必拒 BMP 不白费调用，计 skipped 标注）；`_IMAGE_MIME_BY_SUFFIX` 保留 .bmp 条目（PDF 结构兼容），注释修正矛盾表述。
- config.py / topic_library.py：仅注释去 GLM/智谱化。

### 测试（全量 2123 绿 92s + mypy src 57 文件干净）

- 更新：test_config 默认值字面量 ×2 处、test_webapp 设置项字面量 + 掩码语义不变（roundtrip 段保留智谱值 = 旧配置读回验证）、行为语义 3 测试改自定义 base。
- 新增：helper 三分支 + provider 观测（test_vision +4）、BMP 直传拦截（test_extraction +1）、PDF 内嵌 BMP 跳过（test_extraction +1）、复用端到端（test_webapp +2：extract / split）、topic_get 复用正向（test_webapp +1，Spec 轴建议）、.bmp webapp 层 400 断言（test_webapp +1，Spec 轴建议）。

### 双轴 code-review（并行子代理）

- **Spec 轴：符合 spec，可合**。仅测试粒度建议 2 项（均已补）：topic_get 复用正向、.bmp webapp 层 400 断言。
- **Standards 轴：无硬违规**（语言规范 / 中文注释全过）。判断项 4 项全落实：① webapp 装配重复 → `_resolve_vision` 收拢；② extraction.py:47 注释过度声称 → 改写并说明 .bmp 条目保留原因；③ PDF 内嵌 BMP 仍白发请求 → 发送前跳过；④ 未配置文案主 key 空时失真 → 加「主 key 已配置时」。
- 范围外提示：index.html:1127-1131 设置页智谱残留 → 归工单 02（已确认在 02 范围内）。

### 未做

- 设置页 / 上传区文案与 CONTEXT.md（工单 02，被本工单阻塞，01 resolved 后开工）。
- 真机验证：DeepSeek 视觉 API 真实调用（需用户配置 key 后上传 PDF/图片验收）；赛题库 JPEG2000 12 张按既有降级语义静默跳过（实测长 PDF 472 张图无 BMP，见 .scratch/vision-deepseek-native/pdf_image_scan.py 结果）。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
