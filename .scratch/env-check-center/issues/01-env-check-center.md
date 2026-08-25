# 01 — 环境体检中心（设置页新卡 + 静态聚合 + 双通道真实自检）

**要做什么：** 设置页新增「环境体检」折叠卡：「一键体检」并行跑——静态探测（`GET /api/env/status`：配置/LLM 参数/工具链路径与覆盖/平台母版/模块库计数与错误/输出目录存在可写）+ 主 LLM 文本通道自检（新增 `POST /api/llm/selfcheck`，云端主通道单次探针）+ 视觉通道自检（复用既有 `POST /api/vision/selfcheck`）；逐项徽章行实时更新（检查中/成功/失败+中文原因），体检零写操作。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

## 验收记录（提交信息见 git log「工单 env-check-center/01」）

- 实现：webapp.py `GET /api/env/status`（/api/state 之后：config→dirs、list_masters 母版平台集、find_uv4/find_make、模块库 try/except 报错不 500、desktop_dir 可写性 os.access W_OK）+ `POST /api/llm/selfcheck`（DeepSeekLLM 直构造走 `_chat_once` 单次探针 operation="llm_selfcheck" max_tokens=16 thinking_disabled=True；未配置/LLMError 400 中文，与 vision_selfcheck 契约同构）；index.html 设置页视觉卡后插 `data-collapse-id="env-check"` 卡（一键体检按钮 + `#env-check-results`），纯函数 `envCheckStatusHTML(status, textCh, visionCh)` + `envChannelHTML` + `envRowHTML`（自包含内联 esc、徽章 env-ok/env-warn/env-err、data-env-row 行标记、缺字段不渲染行），`envCheckRun()`（busy → GET 静态渲染 → Promise.allSettled 双通道 → 终态行更新）；既有 btn-vision-selfcheck / /api/vision/selfcheck 零改动。
- 测试：tests/test_webapp.py +6（聚合/畸形模块库 200/未配置形状/selfcheck ok/未配置 400/LLMError 400）；tests/js/env-check-center.test.mjs 12 项绿。
- headless 冒烟 11 项全 PASS（真实 webapp 8000：10 行渲染、双通道终态——文本 deepseek-v4-flash PONG 611ms、视觉 1147ms、按钮恢复）。
- 全量 pytest 2355 绿（2349 基线 + 6）；全量 tests/js 271 绿（259 基线 + 12）。
- 环境注意：webapp 8000 为旧 Python 进程（静态文件实时读≠Python 热更），新增后端端点后需重启 `python -m contest_generator.webapp`。

- [x] `GET /api/env/status` 静态聚合（api_configured/llm/toolchains{found,path,override}/platforms 母版/module_library{dir,exists,count,error}/masters_dir/output_dir{exists,writable}；模块库异常捕获不 500；find_uv4/find_make 单源）
- [x] `POST /api/llm/selfcheck`（DeepSeekLLM 直构造不走 RoutingLLM；`_chat_once` 单次探针 thinking_disabled+max_tokens=16；成功 ok/elapsed_ms/model/reply；未配置 400 中文 / LLMError 400 中文，与 vision_selfcheck 契约同构）
- [x] 设置页新卡（`data-collapse-id="env-check"`，视觉卡后）：「一键体检」按钮 + `#env-check-results` 逐项行
- [x] 纯函数 `envCheckStatusHTML(status)`（自包含内联 esc）+ `envCheckRun()`（GET status 渲染 → Promise.allSettled 双通道 → 各行实时更新；busy 态）
- [x] 既有 `btn-vision-selfcheck` 与 `/api/vision/selfcheck` 零改动（回归）
- [x] pytest：env/status 聚合（假库 fixture/畸形 manifest→error/可写性）；llm/selfcheck 三分支（ok/未配置 400/LLMError 400，monkeypatch webapp.DeepSeekLLM）
- [x] tests/js/env-check-center.test.mjs 纯函数单测（徽章/路径/错误/缺省隐藏/转义）
- [x] headless 冒烟 `.scratch/env-check-center/smoke.mjs` 全 PASS（开卡→静态行断言→一键→两行终态非「检查中」）
- [x] 全量 pytest 绿（基线 2349）与全量 tests/js 绿（基线 259）
- [x] 中文提交信息（CHANGELOG 由 post-commit hook 自动补录）
