# 环境体检中心（E10）——规格说明

## 问题陈述

环境问题排查全靠四处拼接：编译中心一行「工具链：Keil UV4 ✅/gmake ❌」、首页 banner（`api_configured`）、设置页视觉卡的自检按钮。最关键的**主 LLM 文本通道从未验证**——`api_configured` 只表示「保存过配置」：key 失效、网络不通、模型名写错都只能在第一次生成时才发现（烧掉一次完整生成流程）。模块库能否加载、母版是否齐备、桌面输出目录是否存在可写，同样没有集中可视的入口。「打开就知道环境行不行」的能力缺失。

## 方案

设置页新增「环境体检」卡（折叠卡，`data-collapse-id="env-check"`），一键查看环境全貌：

- **静态探测**（秒回，零 LLM 调用）：`GET /api/env/status` 聚合——配置状态、LLM 参数、工具链（Keil/gmake，含探测到的路径与是否覆盖配置）、两平台母版状态、模块库（目录、可加载模块计数、加载错误）、母版目录/桌面输出目录存在与可写性。
- **双通道真实自检**（各 1 次极简调用）：「一键体检」按钮并行触发——
  - 主 LLM **文本通道**：新增 `POST /api/llm/selfcheck`（云端主通道直连，无本地路由——本地路由只服务摘要类调用，主通道才是一切流程的底座；`thinking_disabled` + 极小 `max_tokens` 单次探针，成本可忽略）。
  - 视觉通道：复用既有 `POST /api/vision/selfcheck`（端点不动，体检卡独立触发）。
- **逐项结果行**：状态徽章 + 名称 + 详情（路径/耗时/错误描述），每行实时更新（加载中/成功/失败）；真实自检项各带「再测」入口（一键按钮同时覆盖全部）。

## 用户故事

1. 作为用户，我想打开设置页就看一眼环境体检卡，以便不用翻代码就知道环境有没有问题。
2. 作为用户，我想一键体检（静态 + 主 LLM 文本 + 视觉三组一次跑完），以便所有状态一次到手。
3. 作为用户，我想实际验证主 LLM 配置可用（不是只看「已保存」），以便在开始生成前发现 key 失效/模型名错误/网络不通。
4. 作为用户，我想看到工具链的探测路径与是否用了配置覆盖，以便知道为何一键编译置灰。
5. 作为用户，我想看到模块库可加载的模块数与加载错误，以便发现畸形 manifest 及时修复。
6. 作为用户，我想看到两平台母版是否齐备（ready/no-master），以便判断哪些平台可以生成。
7. 作为用户，我想看到桌面输出目录是否存在/可写，以便生成前发现磁盘/权限问题。
8. 作为用户，体检失败时我想看到中文原因，以便知道该去哪改（设置页/路径/网络）。
9. 作为用户，体检不修改任何配置，以便放心反复点击。

## 实现决策

### 后端（webapp.py，新增两路由；复用探测单源）

- `GET /api/env/status`（静态聚合，无 LLM 调用、无网络）：
  - `api_configured`（`_current_config` 非 None）；`llm`：`{base_url, model, local_llm_base_url}`（config 字段直读）。
  - `toolchains`：`{stm32: {found, path, override}, mspm0: {found, path, override}}`——`find_uv4(dirs.uv4_path)` / `find_make(dirs.gmake_path)`（compile_runner.py 单源探测），`path`=探测到的 Path 字符串或 None；`override`=`config.uv4_path/gmake_path` 非空。
  - `platforms`：`[{id, name, status: ready|no-master}]`——复用 `/api/state` 的 `list_masters` 逻辑（母版平台集合判定）。
  - `module_library`：`{dir, exists, count, error}`——`list_modules(dirs.module_library_dir)`（试装载，异常捕获后 `error` = 中文描述，绝不 500——体检语义 = 报问题而非炸端点）；目录不存在 → `exists: false`。
  - `masters_dir`：`{dir, exists}`；`output_dir`：`{dir, exists, writable}`（`context.desktop_dir()` + `os.access(dir, W_OK)`；不存在则不测可写）。
- `POST /api/llm/selfcheck`（主 LLM 文本通道自检，镜像 vision_selfcheck 契约）：
  - config None → 400「请先保存主 API key 配置」；主 key 空（未配置 API key）→ 400 引导设置页。
  - 实现：`DeepSeekLLM(config)` 直接构造（**不走** `context.llm_factory`/RoutingLLM——自检只测云端主通道），`_chat_once([{"role": "user", "content": "请只回复：PONG"}], operation="llm_selfcheck", max_tokens=16, thinking_disabled=True)` 单次探针（不重试——探测语义）。
  - `LLMError` → 400 `文本通道自检失败：{e}`（中文原因）；成功 → `{ok: true, elapsed_ms, model, reply}`（reply = 响应摘录，限长）。
  - 未配置（无 key）与调用失败分开对待（vision-selfcheck/01 评审先例）。
- 依赖：webapp.py 新增 `from .llm import DeepSeekLLM`（测试 mock 绑定 = `monkeypatch.setattr(webapp, "DeepSeekLLM", fake)`，同 `webapp.describe_image` 先例）。

### 前端（index.html，设置页新增卡）

- 新卡位置：视觉通道卡之后、「最近 LLM 工作流」卡之前；`<div class="card" data-collapse-id="env-check">`，标题「环境体检」；头部按钮「一键体检」+ 说明；容器 `#env-check-results`。
- 纯函数 `envCheckStatusHTML(status)`（自包含内联 esc，同 moduleGridHTML 范式）→ 逐行渲染：徽章类 `env-ok` / `env-warn` / `env-err`（分别 ok/warn/danger 色系）+ 名称 + 详情（mono 路径/错误文本）；缺省字段不渲染行。
- `envCheckRun()`：置 busy → `GET /api/env/status` → 渲染静态行（同时清空真实调用行 → 「检查中…」）→ `Promise.allSettled([POST /api/llm/selfcheck, POST /api/vision/selfcheck])` → 各自行更新结果（成功：`✓ 耗时 Xms 模型 Y`；失败：400 提取中文 message，同 handle() 错误提取语义）→ 结束 busy。
- 视觉行「再测」与一键按钮共用 `envCheckRun()`（简单为先：一键 = 全部；单行再测 = 同函数重跑，不做行级局部——第一个切片直接一键）。
- 既有 `btn-vision-selfcheck`（视觉卡内）不动——体检卡是另一个入口，同一端点。

### 错误文案

- 文本自检未配置：400「请先保存主 API key 配置」/「主 LLM 未配置：到设置页填写 API key」；视觉未配置沿用 vision_selfcheck 既有文案。
- 模块库加载错误：`error` = 异常中文描述（如「manifest 解析失败：…」），行显示 ⚠ 而非 ✗（其他功能可用，仅库异常）。

## 测试决策

- **后端 pytest（test_webapp.py，seam 先例齐备）**：
  - `GET /api/env/status`：context 注入临时 config（replace `module_library_dir`/`masters_dir` 到 tmp_path + 假模块库 fixture 先例：tests/test_webapp.py:325「给假模块库补 k230 + coord_detect」）→ 断言 `api_configured` / `toolchains` 结构（未配置时 found=None） / `module_library.count` / 畸形 manifest → `error` 非空且 200 / `output_dir.exists+writable`（`desktop_dir=lambda tmp_path`，E2 先例）。
  - `POST /api/llm/selfcheck`：`monkeypatch.setattr(webapp, "DeepSeekLLM", FakeLLM)`（`_chat_once` 返回 PONG）→ 200 `{ok, model, reply}`；config None → 400 中文；FakeLLM `_chat_once` raise `LLMError` → 400 中文含原因。
- **前端 JS 单测（tests/js/env-check-center.test.mjs，括号配平抽取 + 兄弟注入先例）**：`envCheckStatusHTML`——各状态行渲染/徽章类/路径显示/错误显示/缺省字段隐藏/esc 转义。
- **headless 冒烟（.scratch/env-check-center/smoke.mjs，CDP + webapp 8000 + reload 标记防护先例）**：设置页 tab → 展开 env-check 卡 → 静态行渲染断言（真实数据）→ 点「一键体检」→ 文本/视觉行出现终态（✓ 或 ✗ 任一，不硬编码成功——真实环境视觉可能未配置；文本行若环境有真实 key 则 ✓，冒烟只断言「两行均非检查中」）。
- **回归**：全量 pytest 绿 + 全量 tests/js 绿；`/api/vision/selfcheck` 与设置页原按钮零改动（回归由既有测试覆盖）。

## 范围外

- LLM 余额查询（用户未选；DeepSeek `/user/balance` 只对官方端点有效）。
- 本地路由（RoutingLLM / Ollama）自检——自检固定云端主通道。
- 自动定时/启动时体检（手动按钮触发）。
- 系统级体检（磁盘/内存/网络 ping——文本自检已隐式覆盖网络）。
- 工具链真实编译验证（编译冒烟属生成流程；体检只探测路径存在）。
- 体检结果持久化/历史（只读瞬态）。

## 补充说明

- 体检零写操作（不读改配置、不建目录）——`output_dir` 只查存在与可写。
- 一键体检的文本/视觉自检总成本 = 2 次极简调用（≤200 tokens 级），体检查不看用量地跑可接受；冒烟脚本的文本自检同成本。
- vision_selfcheck 端点与按钮维持现状不动（本特性只新增读端点 + 一个文本自检端点）。
