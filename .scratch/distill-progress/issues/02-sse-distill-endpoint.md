# 02 — 提炼端点改 SSE 流：进度事件 + 完整报告随流返回

**What to build:** `/api/masters/distill` 从"同步 POST → JSON 响应"改为 SSE 流（text/event-stream）。后端把工单 01 的发射器接到流上：`start` → 事件… → `done`（携带完整提炼报告，与现状响应同构）或 `error`（中文错误信息）→ 流结束。HTTP 状态 200 起流，失败以流内 `error` 事件收尾（客户端只认事件，不依赖状态码）。

要点：

- 报告必须随流返回：提炼确认前不落任何东西、服务端无状态，没有二次查询的可能（spec「传输」）
- 错误映射复用现有 `_error_response` 语义：`LLMError` → 502 中文 message、业务失败 → 400——但都作为流内 `error` 事件发出，而不是 HTTP 非 200
- 扫描 / 对比 / 拼装报告是瞬间步骤，不发事件，直接以 start（带总量）开头、done 收尾
- 断线（客户端关闭）时后端正常结束本次提炼（确认前不落任何东西，无副作用）
- 前端不接（工单 03）；本工单只保证流契约与测试

**Blocked by:** 01

**Status:** resolved

**Reference:** `.scratch/distill-progress/spec.md`（Implementation Decisions「传输」「事件契约」、Testing Decisions）、`docs/adr/0004`、CONTEXT.md「进度事件」词条

## Comments

- 2026-08-06 工单 02 完成（分支 ticket-02-sse-distill-endpoint，未合 main）。
  实现：`webapp.py` `/api/masters/distill` 改为 SSE 流（HTTP 200 +
  Content-Type: text/event-stream 起流，每事件 = `event: <type>\n` + `data:
  <JSON>\n` + 空行，线格式共享契约唯一实现点 `_sse_frame`）；`master.py`
  `distill_master` 增加 `progress_emitter` 参数并透传给 `llm.distill_master`
  （工单 01 只做了 LLM 层，master 层透传补在这里）。
- 事件流：start（带总量）由 llm 层发射器产生（工单 01 已算定）→ 进度事件原样
  透传（`dataclasses.asdict` 全字段，键名 = ProgressEvent 契约，start 的
  judgment_count 是前端"已处理 X/115"的总数来源）→ done（data = 完整报告
  `report.to_dict()`，与现状响应同构，前端报告渲染原样复用）或 error（data =
  `{"message": 中文错误信息}`）→ 流结束。扫描 / 对比 / 拼装是瞬间步骤不发事件。
- 错误映射：`_error_response` 拆出 `_error_message`（LLMError → "AI 服务调用
  失败：…"、业务失败 → 中文 message，映射只此一处两端共用），但作为流内 error
  事件发出、HTTP 保持 200 起流；payload 校验（缺 platform / project_dirs）与
  未配置 API 仍在起流前 400（请求畸形，不产生流）。
- 阻塞设计：提炼放独立线程（daemon），事件经 `queue.Queue(maxsize=100)` 送流
  生成器（sync generator，Starlette 线程池迭代，不占事件循环）。断线后队列无人
  消费：进度事件 put_nowait 满即丢（旁路，不堵提炼线程）、终端事件 put 超时
  （10s）后丢——后端照常结束本次提炼，确认前不落任何东西、无副作用。
- 测试（spec Testing Decisions）：注入脚本化发射假 LLM（ScriptedDistillLLM，
  走工单 01 的 progress_emitter 参数）→ TestClient 断言事件顺序 + done 载荷 =
  同素材同步提炼的 `report.to_dict()`（等价性）；LLMError / 扫描失败 → 流内
  error 收尾；无待判文件（全部规则处理）→ 无批事件直接 done（规则条目照常进
  报告）；断线路径可测：读到第一个事件后关闭响应，断言后端照常完成提炼（8 次
  复跑稳定）。全套 430 绿 + mypy 干净。
