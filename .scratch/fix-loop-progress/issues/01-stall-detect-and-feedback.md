# 01 — 修复循环停滞检测 + 上轮应用结果回喂

**What to build:** 修复中心循环（编译 → AI 修复 → 重编译 ≤3 轮）的两个质量缺口：① **停滞检测**——本轮 0 applied（LLM 空修复 / 全部 skipped / 降级无上下文）时，文件没有变化，重编译输出必与上轮相同、下一轮 LLM 输入也几乎相同（snippet 协议下模型大概率原样重试）——纯浪费 40s 编译 + 分钟级 LLM，应立即停循环并如实说明；② **回喂**——把上一轮逐处应用结果（applied/skipped + 原因）拼进下一轮修复请求，让模型看到自己哪些 old_snippet 没匹配上（最常见失败 = 与文件逐字不符），修正后重试或放弃，而不是无信息重试。

**Status:** claimed

**Blocked by:** 无（与 mspm0-build-makefiles/01、gen-check-fix-loop/01 无文件重叠，可并行 worktree）

## 现状证据（2026-08-13 已核实）

- 循环只查 passed，不查进展：`index.html:1767-1791` 每轮 `await runFixOnce(...)` 返回值被忽略（1771 行），0 applied 也重编译 + 再跑一轮相同输入的 LLM 调用。
- 回喂不存在：`run_fix_round`（fix_errors.py:640）无 previous 入参；第 N+1 轮 user prompt 与第 N 轮相同（除 applied 改过的文件内容），模型不知道 skipped 的原因。
- 真机先例：compile-error-fix/01 历史第 1 轮全 skipped（fix-snippet-match/real_fix.py 注释记录）——正是无回喂时"原样重试"的浪费形态。

## 决策记录（代决，用户可 grilling）

1. **停滞判定 = 本轮 applied == 0**（含 LLM 返回空 fixes、全部 skipped、degraded 无文件上下文）——立即停，文案写具体（"本轮未应用任何修复（全部 skipped / 无修复建议），停止循环——可贴文本手动修复或改工程后重试"）。**不做"错误签名未变"判定**：级联错误（一个缺头文件 → 几十条报错）两轮才消是正常形态，签名判停会误停（T1 讨论时已议，此处落定）。
2. **回喂内容 = 上一轮 done 载荷的 fixes 数组**（[{file, line, status, reason}]，reason 即 _reason_for 单源文案——未应用原因已写具体）。前端循环把它作为 `previous_fixes` 传给下一轮 /api/fix-errors；LLM 提示词加独立段"上一轮修复应用结果"，FIX_SYSTEM_PROMPT 补约束（见实施）。applied 的文件下一轮行号会漂移——提示词明确 line 只作提示、old_snippet 以文件内容为准（既有约束 2 语义不变）。
3. **传递路径与校验**：路由只透传 raw 数组（`_optional_str` 系列不适用，数组形状校验归域层）→ `run_fix_round(previous_fixes=...)` 做形状校验（每项 dict + file/line/status/reason 字段类型，非法 → FixError 400 中文——域判决归域模块既定方向）→ 传给 `llm.fix_compile_errors`。**缺省空 = 行为与现有一致**（贴文本模式、旧调用零改动）。
4. **停滞检测落位 = 前端循环**（循环状态机在前端，index.html:1767）；`runFixOnce` 已返回 done 载荷（含 fixes），循环算 applied 数即可。服务端不做（循环是前端状态机，既定架构）。
5. **范围外（不混入本工单）**：错误签名停滞 / 报错去重压缩 / 上下文预算调整 / 3 轮后"继续修复"按钮 / CLI 侧循环（gen-check-fix-loop/01 独立实现，可并行）；T4 真机校准数据在本工单验收时顺手收集。

## 实施

1. **`fix_errors.py`**：`run_fix_round` 加 `previous_fixes: Sequence[Mapping[str, Any]] = ()` 参数——形状校验（每项 dict；file/status/reason 字符串、line 整数；status ∈ {applied, skipped}）非法 → FixError（登记 errors.py → 400）；校验后转传给 `llm.fix_compile_errors(previous_fixes=...)`。done 载荷不动（追加不破坏旧前端）。
2. **`llm.py`**：`fix_compile_errors` 加 `previous_fixes` 参数透传 `_fix_errors_user_prompt`；渲染独立段"上一轮修复应用结果"（逐条 file:line + status + reason；空列表 = 无该段，零回归）；`FIX_SYSTEM_PROMPT` 补约束：看到上一轮未应用原因时，old_snippet 与文件逐字对齐后重试该条或放弃该条，不要重复输出一模一样的建议。
3. **`webapp.py`**：`/api/fix-errors` 请求体收 `previous_fixes`（可选，数组原样透传 run_fix_round，路由不做形状判决）。
4. **`index.html`**：循环改两处——每轮 `const done = await runFixOnce(errorText, outputDir, lastFixDone)`（把上一轮 done 载荷透传）；修复后算 `applied = done.fixes.filter(f => f.status === "applied").length`，0 → 停循环按决策 1 文案；>0 → 照旧重编译验证。
5. **测试**：`tests/test_fix_errors.py` 补 run_fix_round 形状校验用例（非法项 400 / 空列表零回归）；`tests/test_llm.py` 补提示词断言（带 previous → 渲染段逐条在场、空 → 无该段）；既有对偶测试（FIX_SYSTEM_PROMPT 与域协议双端断言）随约束改动同步；路由级 fake 端到端（previous 透传 → 第二轮回喂可见）。
6. **不动**：compile_runner.py / makefiles.py / generator.py / config.py / generate_check.py / 门禁 / 事件词表（fix 事件无新增）。

### 实施注

- `run_fix_round` 的 emit 事件序列不变（parse_done → fix_start → apply_result…），previous 只进 LLM 素材不进事件。
- LLM 提示词段的位置：文件上下文之后、约束之前（独立段标题固定，测试可断言）。
- 前端无单测基建（既有约定：node 语法过 + 真机人工验收）。

## 验收标准

- [ ] pytest 全绿 + `mypy src` 干净 + node --check 内联 JS 通过
- [ ] 单测：形状校验（非法 400）/ 空列表提示词零回归 / 带 previous 渲染段断言 / 对偶测试随约束同步
- [ ] 真机（收集 T4 数据）：2026C 注错（复用 fix-snippet-match/real_fix.py 场景，行尾注释干扰）→ 一键编译修复：第 1 轮 skipped → 第 2 轮回喂后 applied（记录每轮 applied/skipped 分布入工单）或 0 applied 即停（不再白跑第 3 轮重编译）——两种终态都算闭环，数据记 Comments
- [ ] 真机回归：正常生成无错工程 → 一键编译修复首编即过，循环不启动（零改动路径不受影响）
- [ ] `git status` 只出现预期文件（fix_errors.py / llm.py / webapp.py / index.html / 既有测试 5 件）

## Comments
