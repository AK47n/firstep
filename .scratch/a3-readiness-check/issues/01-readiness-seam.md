# 01 抽取就绪判据纯函数并改 btn-generate 同源

> 归属 spec：`.scratch/a3-readiness-check/spec.md`

Status: resolved

## 背景

「生成工程」按钮（index.html 3804-3810）的前置校验与即将新增的「检查能否生成」必须共用同一判据，否则两处判断漂移（先例：`collectBindings`/pin-verdict-seam/01 单源）。

## 任务

- 新增纯函数 `generateReadinessChecks(state)`：`state = { chosenPlatform, selectedSlugs, problem, desktopOutput, outputDir }`；返回按 `[3, 6, 1, 9]` 顺序的 `{ step, title, reason, ok, autoFixable }`；reason 逐字：请先选择目标平台 / 请先选择模块 / 请先填写赛题原文 / 请填写输出目录；仅 step 6 `autoFixable: true`。
- 新增纯函数 `readinessSoftChecks(state)`：state 另含 `recommended`、`hasMainC`；返回 `[5, 8]` 软项（5 仅当 selectedSlugs 非空）。
- 新增纯函数 `readinessRowHTML(check, opts)` / `readinessRowsHTML(items)`：渲染检查单行（详见 spec 实现决策 3）。
- btn-generate 3804-3810 改为消费 `generateReadinessChecks(readinessState()).filter(c => !c.ok)` 首个 missing 的 reason——文案/顺序/行为不变。
- 新增 `readinessState()` 薄 DOM 读取（含 `recommended = stepDoneSet.has(5)`、`hasMainC = !!$("main-c").value.trim()`）。

## 验收标准

- [x] `tests/js/readiness-checks.test.mjs` 全绿（red→green，TDD）
- [x] 判据 4 条件与 reason 文案与旧逻辑逐一对应（有对照断言）
- [x] 点击「生成工程」缺项时的提示逐字不变（headless 实测或代码对照）
- [x] `node --test "tests/js/*.test.mjs"` 全绿
- [x] 主 script 块 `new Function` 语法检查通过
