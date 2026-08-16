# 01 — 校验端点（validate-bindings）

**What to build:** 新增校验端点，跑 `resolve_bindings` 返回结构化结果；前端离开引脚配置步骤（进入生成前）调用，失败阻断并展示中文错误。修 green→400。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] 端点给定 {platform, slugs, bindings} 返回 {ok:true} 或 {ok:false, error}（error 与 generate 400 文案逐字一致，走同一 `resolve_bindings`，不复制文案）
- [x] 前端在进入生成前调用；ok:false 时内联展示错误并阻断，不发起 generate
- [x] 跨角色冲突（槽位 / GPIO 同端口 / PWM 通道对 / 成对实例）经此端点在生成前暴露
- [x] 空 bindings / 全默认绑定 = ok:true（旧行为，不误拦）

**实施记录：**

- 端点 `POST /api/bindings/validate`（webapp.py，`_map_errors` 包裹）：`resolve_selection` + `board_for_platform` 与 generate 同源取 manifests/board，跑 `resolve_bindings`；`PinBindingError` 捕获返回 `{"ok": false, "error": str(exc)}`，否则 `{"ok": true}`。`error` = `str(PinBindingError)` = `error_entry(PinBindingError)` 的 message = generate 400 的 detail——同一实现零文案复制。
- 前端：抽 `collectBindings(selectedSlugs, bindings, instanceMap)` 纯函数（bindings 载荷单源，validate 与 generate 必须发同一份，否则校验通过但生成撞 400）；generate handler 在 `apiPost("/api/generate")` 前先调 validate，`check.ok === false` 内联展示 `check.error` 并 `return`（`finally` 仍复位按钮）。
- 测试：后端 `test_bindings_validate_*`（真库 `library/modules`，逐字比对 `_resolve_verdict`）；前端 `tests/js/collect-bindings.test.mjs`（node:test 函数抽取，照 sse-parser.test.mjs 先例——本仓库无 jsdom）。
- 验收：全量 pytest 1719 绿（+4）；`node --test tests/js/*.test.mjs` 13 绿；`mypy src/contest_generator/webapp.py` 干净。
- 留痕：02（裁决端点）是否做、何时做，合完 01 再定。
