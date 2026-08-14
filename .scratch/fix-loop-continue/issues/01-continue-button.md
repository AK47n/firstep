# 01 — 3 轮后继续修复按钮：轮上限停死后只剩「重新来过」，回喂上下文丢失

**What to build:** 修复循环达 FIX_MAX_ROUNDS=3 上限仍有错/警时，给出「继续修复」按钮——再来一批 ≤3 轮，**不重跑初始编译、保留上一批的 previous_fixes 回喂上下文**（fix-loop-progress/01 的回喂是罕见路径安全网，重跑一键编译修复会 `lastFix = null; lastFixDone = null` 把回喂清零，模型失去「上一轮哪条没应用、原因是什么」的线索）。

**Status:** 待实施（实施提示词见文末）

## 现状证据（2026-08-14 读码核实）

- **轮上限终态**（index.html startFixCenter）：`"已达 3 轮上限，剩余 N 条 Error / M 条 Warning 见上方编译输出——可继续贴文本修复，或改工程后重试"`——按钮无，只能贴文本（丢自动上下文）或改工程。
- **重跑 = 失忆**：`startFixCenter` 开头 `lastFix = null; lastFixDone = null`（回喂清零）+ 必跑初始编译（第 0 步，冗余一轮编译耗时）——重跑一键编译修复是「全新生命周期」，不是「继续」。
- **0-applied 停滞终态**：`"本轮未应用任何修复（全部 skipped / 无修复建议），停止循环…"`——同文案无继续按钮；此态继续无意义（同输入必再停），本工单**不覆盖**（保留现有逃生口：贴文本 / 改工程）。
- **按钮 DOM 现状**：修复中心只有 `btn-fix-center`（一键编译修复）+ `btn-fix-rollback`（回滚，hidden 起）。`fixCenterBusy` 只管理 btn-fix-center 的禁用态。
- **CLI 无对偶需求**：generate_check.py 是非交互批处理工具，无按钮语义——本工单不动它；FIX_MAX_ROUNDS 双文本契约钉（test_generate_check_contract.py:320）不动。

## 修复方向（实施会话定措辞，红证先行）

1. **「继续修复」按钮**：`btn-fix-continue`（hidden 起），仅轮上限终态显示；文案如「继续修复（再来 3 轮）」；点击 → 从保存的续跑态进入新一轮批（≤3 轮），轮次条标注批次（如「继续批次 第 1/3 轮」）；成功 / 新循环开始即隐藏。fixCenterBusy 同步管理其禁用态。
2. **续跑态保存**：轮上限终态把 `errorText / lastSummary / lastFixDone` 存入模块级 resume 对象（如 `fixLoop.resume`），继续按钮消费；startFixCenter 内部把「初始编译」与「修复轮批」拆成可复用结构（如 `fixRounds(errorText, lastSummary, lastFixDone)`），一键编译修复 = 编译 + fixRounds，继续 = resume 直进 fixRounds（**不重跑编译、回喂不丢**）。
3. **文案更新**：轮上限终态补「可点「继续修复」再来一轮批」；0-applied / 超时终态文案不动（不覆盖）。
4. **结构钉红证**（tests/test_generate_check_contract.py，照 FIX_MAX_ROUNDS 双文本钉先例）：index.html 含 `id="btn-fix-continue"` + 轮上限终态文案含「继续修复」+ resume 状态变量在场——实施前全红。

## 实施边界

- src：`src/contest_generator/static/index.html`（按钮 DOM + 循环拆分 + resume 态 + 文案）。
- tests：`tests/test_generate_check_contract.py`（结构钉 3 条）。
- 零改动：`llm.py` / `webapp.py` / `fix_errors.py` / `generator.py` / `.scratch/real-run/generate_check.py`（CLI 非交互无对偶）。

## 验收标准

- [ ] 红证：结构钉 3 条先行跑红（按钮 id / 终态文案 / resume 态均不在）
- [ ] 实施后：结构钉绿 + 既有全绿 + `mypy src` 干净 + `node --check` 过
- [ ] 浏览器人工验收：2026C 产物正常流 0/0 收敛 → 按钮不出现；**cap 路径**：临时把 index.html 的 `FIX_MAX_ROUNDS` 改 1 → 注错 → 必现轮上限终态 + 继续按钮 → 点继续 → 修复完成 → 改回 3；继续批次期间 previous_fixes 回喂在场（抓 SSE 请求体或修复日志确认）
- [ ] `git status` 只出现预期文件

## 实施提示词（新会话粘贴）

> 工单：`.scratch/fix-loop-continue/issues/01-continue-button.md`（先读全文）。
> 任务：修复循环轮上限终态加「继续修复」按钮（再来 ≤3 轮，不重跑编译、保留 previous_fixes 回喂），红证先行，浏览器人工验收。
> 文件边界：只动 `src/contest_generator/static/index.html` + `tests/test_generate_check_contract.py`；`llm.py` / `webapp.py` / `fix_errors.py` / `generator.py` / `.scratch/real-run/generate_check.py` 零改动。
> 关键：续跑态（errorText / lastSummary / lastFixDone）模块级保存，startFixCenter 拆分「初始编译 + fixRounds 轮批」复用；按钮仅轮上限终态出现，0-applied / 超时终态不覆盖；FIX_MAX_ROUNDS 双文本契约钉不动；CLI 非交互无对偶。
> 验收：结构钉 3 条红→绿 + 既有全绿 + mypy 干净 + node --check 过 + 浏览器人工（FIX_MAX_ROUNDS 临时改 1 注错必现 cap → 继续按钮 → 修复完成改回 3）；证据写 Comments，Status 改 resolved，docs 提交推送。

## Comments
