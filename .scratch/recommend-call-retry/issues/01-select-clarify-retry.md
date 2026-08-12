# 01 — select_modules / clarify 整次重试兜底（对齐 _retry_parse）

**What to build:** DeepSeek 偶发返回空内容（真机 2026C：4 次 recommend 2 次"模型返回的不是 JSON："，空 detail = 响应 content 为空）——`select_modules` 与 `clarify` 是手写 `_chat` + parse 单次调用，遇空/畸形输出即抛 LLMError → error 终态，收敛中途整个推荐流程报废重跑。仓库已有整次调用级重试原语 `_retry_parse`（LLM 异常或输出畸形整次重问，最多 SUMMARY_RETRY_LIMIT 轮，仍失败大声抛错）——归档判定 / 参考简介 / 模块简介都在用，唯独推荐链路两个方法漏了。目标：`select_modules` / `clarify` 改走 `_retry_parse` 原语（或同款循环），空内容这类瞬时异常自动重问，不再一枪毙命。

**Status:** resolved（2026-08-11，pytest 1087 绿 + mypy 干净 + 真机 2026C 全流程闭环）

## 实施记录（2026-08-11）

- **llm.py**：`select_modules`（576-625）与 `clarify`（627-648）改走既有 `_retry_parse` 原语（713-745，SUMMARY_RETRY_LIMIT=3 轮，仍失败抛"连续 3 次调用失败"）——user_prompt 构造逐字不变（`_selection_user_prompt` / `_clarify_user_prompt` 原样），`json_mode=True` 透传。`select_modules` 的 parse 闭包 = `extract_module_selection_data` → `build_module_selection`，**SelectionError→LLMError 翻译留在闭包内**（selection 不 import LLMError，防 import 环；重试循环吃的是翻译后的 LLMError，SelectionError 路径因此自动纳入重试覆盖）；`clarify` 的 parse = `parse_clarify_questions`（原严格解析不变）。两方法 docstring 补"瞬时失败整次重问（_retry_parse）"句。空内容响应（真机 2026C 偶发形态）落点 = JSON 解析失败抛 LLMError → 被 `_retry_parse` 捕获整次重问——语义与单次失败完全对齐，只是多花最多 2 次调用。
- **测试**（+6，基线 1081 → 1087）：
  - test_llm.py：`SequenceTransport` 空 content ×2 → 成功（断言 3 次调用）；全空 ×3 → `模块选择连续 3 次调用失败` / `澄清连续 3 次调用失败`（文案含"连续"）；畸形输出（非 JSON）×1 → 成功；**SelectionError 路径在重试覆盖内**（未知 slug 被 build_module_selection 拒绝 → 翻译 → 整次重问 → 成功，断言 2 次调用）。
  - 既有 select/clarify 契约测试零改动全绿（135 项中 12 项相关：请求形状 / prompt 契约 / 畸形拒绝 / 空选择合法——单次失败的最终文案含原错误语义，match 断言全部保持）。
- **CONTEXT.md**：收敛循环词条补"select_modules / clarify 走 _retry_parse 整次重试兜底（瞬时空内容/畸形输出自动重问，最多 3 轮）"。
- 不动：`_retry_parse` 原语本身、selection.py / webapp.py / generate_check.py（--clarify 映射走同一 run_recommendation 路径，自动受益）、events.py / errors.py。

## 真机验收记录（2026-08-11，已闭环）

- 8000 服务已重启（杀旧 PID 51448 → 新进程 53244，装载 llm.py 新代码，`/api/tabs/register` 探活 422 = 路由在场；服务启动 23:25:14 < llm.py 修改 23:23:43，旧进程必载旧代码——按服务手册必须重启）。
- `python generate_check.py 2026C --clarify clarify_2026C.json`（stm32/Keil 线，题面已补全 + clarify_2026C.json 映射预置）：**推荐 4 轮 → done（9 模块：zigbee_uart_key/zigbee_uart 双选 + zone/lock_control/oled/uwb_uart/filter/led_beep/config，topic_id=2026C 识别、功能需求层 12 条、参考资料 1 条）→ 骨架 main.c 7469 字符、拦截幻觉 0 处 → 生成 44 文件 → 产物门禁全过（产物树语料重建，与生成同源）→ UV4 命令行构建 exit=0（0 错误）**，汇总 2026C ✓ 通过。
- 重试痕迹：本次运行 DeepSeek 未返回空内容（重试路径未实际触发，机制由单测钉死：空内容 ×2 → 3 次调用成功、全空 → "连续 3 次调用失败"）。另注：recommend SSE 流 4 轮收敛每轮是一次真实 DeepSeek 调用（分钟级），流期间连接长开、uvicorn 访问日志提前打 200——首次误判为"挂起"杀掉了首跑，实为正常慢调用（与上一工单真机"SSE 探针 3 次"同经历）；中途一次 400 是旧 out 目录未清（脚本不清理，22:48 遗留目录挡路），删目录重跑即过——两者均为操作事项，非代码缺陷。

## 现状（已核实，2026-08-11）

- `_retry_parse`（llm.py:713-745）：整次调用级重试原语，`_chat` + parse 包循环，捕获 LLMError 重试至多 SUMMARY_RETRY_LIMIT=3 轮，仍失败抛 `LLMError("...连续 3 次调用失败...")`——服务"一次调用一个产物"的契约（归档判定 / 参考文件简介 / 模块简介 validate_module_description 已用）。
- `select_modules`（llm.py:576-625）：手写 `_chat`（597-613）+ `extract_module_selection_data`（614）+ `build_module_selection`（616-621，SelectionError → LLMError 翻译在 622-625）——无重试。
- `clarify`（627-648）：手写 `_chat` + `parse_clarify_questions`——无重试。
- 空内容响应的落点：content 为空 → JSON 解析失败抛 LLMError → 无重试直接向上 → run_recommendation error 终态。套 `_retry_parse` 即可覆盖（空串进 parse 抛 LLMError，被捕获重试）。
- 预算哲学（ADR 0001 补充 / _retry_parse docstring）：宁可多花一次调用，也不带病进流程——重试成本用户已认可。
- 需要保留的既有行为：select_modules 的 SelectionError→LLMError 翻译（626-625 注释：selection 不 import LLMError，防 import 边成环）——翻译必须在 parse 层内，重试循环吃的是翻译后的 LLMError。

## 实施

1. **llm.py** 两处改走 `_retry_parse`：
   - `select_modules`：构造 user_prompt（_selection_user_prompt 现有逻辑不变）→ `_retry_parse(system_prompt=SELECT_SYSTEM_PROMPT, user_prompt=..., parse=..., label="模块选择", json_mode=True)`；parse 闭包 = extract_module_selection_data → build_module_selection，SelectionError→LLMError 翻译留在闭包内（翻译后 _retry_parse 才能捕获重试）。
   - `clarify`：同款改走 `_retry_parse`（parse = parse_clarify_questions，label="澄清", json_mode=True）。
   - 行为不变：缺省参数、prompt 构造、翻译、错误文案（"连续 N 次调用失败"是新增包装，原单次失败文案语义保留在 last_error 里）。
2. **测试**（tests/test_llm.py）：
   - 空内容重试：SequenceTransport / 记录型假 Transport 依次返回空 content 2 次 → 成功 → 断言 3 次调用、最终成功解析；全部空 → 抛"连续 3 次调用失败"。
   - 畸形输出重试：非 JSON 2 次 → 成功；SelectionError 路径（build_module_selection 拒绝）也在重试覆盖内（翻译 → LLMError → 重试）。
   - 既有 select/clarify 契约测试全部保持绿（prompt / 解析 / FakeLLM 零改动）。
3. **CONTEXT.md**：llm 词条或相关词条补一句——"select_modules / clarify 走 _retry_parse 整次重试兜底（瞬时空内容/畸形输出自动重问，最多 3 轮）"。

## 文件边界

- src/contest_generator/llm.py —— select_modules / clarify 两方法改用 _retry_parse（含 parse 闭包与翻译）
- tests/test_llm.py —— 空内容/畸形重试用例
- CONTEXT.md —— 词条一句
- **不动**：_retry_parse 原语本身、selection.py / webapp.py / generate_check.py、其余协议（已有兜底或批内补问）

## 验收

- [x] pytest 全绿（1081 基线 + 新增 6 = 1087，无回归）+ `mypy src` 干净（32 文件）。
- [x] 空内容重试用例证明：瞬时空响应自动重问成功（`test_select_modules_retries_on_empty_content_then_succeeds` / `test_clarify_retries_on_empty_content_then_succeeds`，断言 3 次调用）；全空大声失败（`..._exhausts_retries_on_empty_content`，错误文案含"连续 3 次调用失败"）。
- [x] 翻译保留：SelectionError→LLMError 翻译在 parse 闭包内（llm.py 注释标明防 import 环；`test_select_modules_retries_when_selection_rejected` 证明拒绝 → 翻译 → 整次重问 → 成功；既有 select/clarify 契约测试零改动全绿）。
- [x] 真机：重跑 2026C（stm32/Keil 线，clarify 映射预置）→ 推荐 4 轮 done → 骨架 → 生成 44 文件 → 产物门禁全过 → **UV4 命令行构建 0 错误**（本次未遇空内容偶发，重试路径未触发——机制由单测钉死，见上）。
- [x] 工单补实施记录 + 验收勾选，Status implemented。
