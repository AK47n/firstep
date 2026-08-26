# 19 — 生成页 · 就绪检查：static/js/ui/generate-readiness.js

**要做什么：** generate tab 的「就绪检查面板」簇迁入 `static/js/ui/generate-readiness.js`（readinessState / renderReadinessPanel / refreshReadinessPanel / initReadinessCheck）。**被谁阻塞：** 02 + 18（stepDoneSet import 读）

**状态：** 已实施（resolved）

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数（8739-8797）：readinessState 8739（`stepDoneSet.has(5)` @8746 —— import 自 ui/generate-steps.js）/ renderReadinessPanel 8750 / refreshReadinessPanel 8760 / initReadinessCheck 8763。
- 依赖：`$`（app.js）；fx/readiness.js（generateReadinessChecks / readinessSoftChecks / readinessRowHTML / readinessRowsHTML）+ fx/draft.js?（stepProgress——grep 复核）；stepDoneSet（ui/generate-steps.js）。
- markup：#readiness-* 容器 id 不动；host init* 清单含 initReadinessCheck。

## 检查表

- [x] 新建 `static/js/ui/generate-readiness.js`：4 函数逐字搬移 + import（app.js / fx/readiness.js / ui/generate-steps.js）+ export（readinessState / renderReadinessPanel / refreshReadinessPanel / initReadinessCheck）+ 头部注释
- [x] index.html：CRLF 感知行区间删除（8739-8797；**物理升序**）+ 顶部 import 行追加
- [x] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 就绪面板实况（initReadinessCheck 后行数 > 0）
- [x] grep 零残留：index.html 无 `function readinessState(` 等 4 名定义
- [x] 中文提交

## 实施记录（工单 19 —— generate 八簇收尾票）

### 行号复核
簇体实际位于 2626-2686（检查能否生成 section 注释 → Toast 注释区，不含后者）：readinessState 2634（`stepDoneSet.has(5)` @2641）/ renderReadinessPanel 2645 / refreshReadinessPanel 2655 / initReadinessCheck 2658。issue 正文行号（8739-8797）为阶段 1 时代编号。

### 清单校正
- **stepDoneSet / stepCard 真身在 ui/step-state.js（工单 12 拥有）**——issue 所述「import 自 ui/generate-steps.js」不实（18 的模块不含它们）；本模块 import 自 step-state。链无环：readiness → step-state/A/core；steps → readiness（readiness 不 import steps）✓。
- **本票是工单 18 接缝的既定衔接点**：generate-steps.js 的 `stepsDeps/setStepsDeps`（18 建）**删除**，refreshGenOverview 改直接调用 `readinessState()`（静态 import 自 generate-readiness.js）；host 的 setStepsDeps 注册行删除、2249 import 行去 setStepsDeps。与 15→16（setGenerateCoreDeps）同构闭环。
- host 顶部 import（generate-steps 之后）三名：readinessState（btn-generate 监听器 2357 前置校验用）/ refreshReadinessPanel（setOnStepChange 回调）/ initReadinessCheck（启动区 2766）。

### 验证矩阵（全绿）
- node --test：444/444；pytest：2465 passed（后台任务 pwsh-21）；diag 零 EXC；smoke 11/11。
- probe-19.mjs：8/8（动态 import / 就绪面板展开 + 行数 5 + innerHTML 1132 / markStepDone → 总览联动（steps→readiness 静态 import 链）/ btn-generate 前置校验「请先选择目标平台」/ 全程零 EXC）。
- grep 零残留：4 名零定义；setStepsDeps 全库已清；markup（btn-readiness-check / readiness-check 容器）未动。

### 踩坑记录（本轮）
- **行尾坑**：generate-steps.js 全 CRLF（edit 工具/环境 CRLF 化）——apply-19 的多行替换串（`\n` 假设）三处未命中（seam 块 / header 注释 / export 尾部）——一律用 `\r?\n` 容错；另注记文本自含「setStepsDeps」字样导致 residual 检查误报（上一轮同类坑）。
- apply-19 曾对已改写的 steps 非幂等（二次运行 seam 块不存在）——幂等化：`steps.includes("stepsDeps")` 才进改写分支。

## 风险点

- 本簇是 generate 八簇最后一票——收尾前用 `node --test` 全量确认 stepDoneSet 读方（host 分发器 @2321）import 链完整。
