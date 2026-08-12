# 01 — 修复会话单轮编排归位（run_fix_round 入域，对照 run_recommendation 先例）

**What to build:** 架构评审卡 1（修复会话编排入域）grilling 定案的最小忠实实现：`/api/fix-errors` 路由闭包内的五步管线（parse_compile_errors → collect_candidate_paths → read_file_contexts → llm.fix_compile_errors → apply_fixes + 事件发射 + done 载荷拼装）收进域函数 `run_fix_round`（落 fix_errors.py），路由恢复「取参 + 校验 + 转调 + SSE 包装」（对照 selection.run_recommendation 归位先例，PR #44 同款形态）。行为零变化：事件序列、done 载荷形状、回滚、前端全部不动。

**Status:** resolved

**决策记录（grilling 2026-08-12，用户授权代决）**

1. **范围：A1 只入单轮，不做 A2 会话流 / A3 前端直测**——
   - 不做 A2（run_fix_session 服务端循环 + 一条 SSE 流）理由：编译与修复是两条独立生命周期（编译不依赖 LLM、修复依赖），合并成会话流会捆死「无 key 编译看结果」（compile-verdict-align/01 刚解除的门控）与「断线丢一轮可重试」的细粒度；事件契约需加轮次维度（词表复杂度上升）；「≤3 轮不变量在服务端」在本地单用户工具是架构洁癖——不变量自上线未破过，真正的回归防线是测试而非落点。
   - 不做 A3（前端循环抽函数直测）理由：循环决策仅 3 个终止 if（timed_out / passed / 上限），测试价值低，却需建 tests/js 基建。
   - 做 A1 理由：五步管线 + done 载荷形状有家（对照 run_recommendation 同款形态：域判决 + 编排在域、路由只转调）；域函数脱离 HTTP/SSE 可单测；webapp import 面收敛可结构钉住。
2. **回滚粒度：保持现状**——每轮 fix 一个备份（report.backup_id），前端「回滚本次修复」回滚最近一轮；run_fix_round 照常返回 backup_id。会话级回滚 ≈ 重新生成（可重复），价值低，不做。
3. **触发链 / 贴文本模式 / 守卫：保持不动**——生成后自动触发、手动按钮、无工具链回退、贴文本模式全不动；LLM 守卫仍在路由（_require_config，修复必须 LLM，现状合理）；run_fix_round 签名直接收 llm 参数（路由装配 _llm 传入），域内不碰配置。
4. **事件发射：域内走旁路 ProgressEmitter**——parse_done / fix_start / apply_result 在 run_fix_round 内发射（_emit 同款旁路，发射失败不影响主流程）；done 载荷作为函数返回值，由路由 emit.done 收尾（run_sse 终态保证语义不变）。

## 实施（文件边界）

1. **`src/contest_generator/fix_errors.py`** 新增 `run_fix_round`（放模块尾部，风格对照 compile_runner.collect_build_log 的深函数样式）：
   - 签名：`run_fix_round(llm, *, error_text, output_dir, backup_root, problem_text, platform, module_slugs, main_c, emit=None) -> dict`——output_dir / backup_root 收 Path，其余收 str；emit 收 ProgressEmitter（默认 None = 旁路跳过）；
   - 体 = 现 webapp.py:734-779 五步迁移：parse → collect → read（dropped 保留）→ emit parse_done → emit fix_start → llm.fix_compile_errors → apply_fixes → 逐条 emit apply_result → 返回 done 载荷 dict（形状逐字 = 现 766-779：output_dir / backup_id / degraded / parsed / fixes）；
   - docstring 写明事件序列契约 + done 载荷形状（形状的家从这里来，webapp docstring 改指向本函数）。
2. **`src/contest_generator/webapp.py`**（/api/fix-errors，705-786）：
   - 路由保留：取参、`output_dir.is_dir()` 校验、`_require_config`、`fix_backup_root(...)` 推导、`_llm(context)` 装配；
   - run 闭包瘦身为：`emit.done(run_fix_round(llm, error_text=..., ...))`；删路由内对 parse_compile_errors / collect_candidate_paths / read_file_contexts / apply_fixes 的直接调用与 import（import 面收敛到 run_fix_round + fix_backup_root + 类型）；
   - docstring 补一句「编排在 run_fix_round（对照 run_recommendation 先例），路由只取参 + 转调 + SSE 包装」。
3. **测试**：
   - `tests/test_fix_errors.py`（或既有 fix 测试文件）新增 run_fix_round 单测：假 llm（先例：既有假 LLM 模式）+ 临时目录真实语料（main.c 等）→ 断言事件序列（parse_done → fix_start → apply_result×n，经捕获 emitter）+ done 载荷形状（keys 全等 + degraded / parsed / fixes 语义）——不依赖 HTTP/SSE；
   - 结构钉（对照 recommend 归位工单模式）：断言 webapp 模块不再直接引用 parse_compile_errors / collect_candidate_paths / read_file_contexts / apply_fixes 符号（import 面钉住防回退）；
   - 既有 test_webapp `_fix_stream` 端到端保持全绿（行为不变验证）。
4. **不动**：compile_runner / llm / sse / events / 生成器 / 前端 index.html（循环、横幅、回滚按钮全不动）/ 贴文本模式 / 触发链。

## 验收

- [x] `pytest` 全绿（基线 1242 + 新增）+ `mypy src` 干净 + index.html node 语法过（前端零改动也应过）——1247 全绿 + mypy Success 36 files + node --check OK
- [x] test_webapp `_fix_stream` 端到端不回归（事件时序 + 载荷形状与实施前逐字节一致）——8 例全绿
- [x] run_fix_round 单测绿（假 llm + 临时目录，红证：迁移前无此函数可测）——3 例
- [x] 结构钉绿（webapp 不再 import fix_errors 内部原语）——2 例（import 面钉 + 路由体钉）
- [ ] 真机（可选）：贴文本修复一次真实调用（既有 2026C 产物 + 报错文本），事件流与回滚与实施前一致——未做（迁移零行为变化，_fix_stream 端到端已覆盖同语义）

## 实施记录

（2026-08-12 实施）**Status: resolved**

- fix_errors.py：新增 `run_fix_round`（模块尾部，深函数样式）——五步管线
  （parse → collect → read → llm.fix_compile_errors → apply_fixes）逐字迁移自
  路由闭包，事件经 `_emit` 旁路发射（events 叶子契约，emit=None 跳过），done
  载荷作为返回值（形状的家在此，docstring 写明事件序列 + 载荷形状）；模块
  docstring 同步更新（编排归位 + 依赖方向补 events）；LLM 仅 TYPE_CHECKING
  （library.py 先例，llm 反向依赖本模块 FixSuggestion，禁止运行时导入）。
- webapp.py：/api/fix-errors 路由瘦身为取参 + 校验 + 装配 + 单行转调
  （`emit.done(run_fix_round(..., emit=emit.progress))`，对照 recommend 路由
  同款形态）；import 面收敛——删 apply_fixes / collect_candidate_paths /
  read_file_contexts 与 EVENT_PARSE_DONE / EVENT_FIX_START / EVENT_APPLY_RESULT，
  加 run_fix_round；**parse_compile_errors / summarize_compile_output 保留**
  （/api/compile 的 parsed_errors / summary 展示层字段仍用，compile-verdict-align
  面，工单文件边界的删 import 表述按此修正）；docstring + 段注释指向
  run_fix_round。
- 测试 +5（1242 → 1247 全绿）：run_fix_round 单测 3（事件序列 + done 载荷
  keys 全等 / 降级模式 + emit=None / 发射器抛错旁路吞掉——假 LLM FakeLLM +
  临时目录真实语料，直调不依赖 HTTP/SSE）+ 结构钉 2（import 面钉：webapp 的
  fix_errors import 不再含管线内部原语且含 run_fix_round；路由体钉：fix_errors
  路由函数体内无五步直接调用，对照 recommend-orchestration-homing 同款 AST
  切片风格）。红证：实施前 run_fix_round 不存在（单测即红）、webapp 直调五步
  （结构钉即红）。
- 验证：pytest 1247 全绿 + `mypy src` Success 36 files + index.html 内联 JS
  node --check OK（前端零改动）；test_webapp `_fix_stream` 端到端 8 例全绿
  （事件时序 parse_done → fix_start → apply_result → done + done 载荷逐字节
  不变 + 回滚链路照常）。
- 未做：真机贴文本修复一次真实调用（可选验收项，既有 2026-08-12 真机产物
  未重验；迁移零行为变化，_fix_stream 端到端已覆盖同语义）。
