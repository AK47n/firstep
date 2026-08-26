# 20 — 收尾：host 瘦身 + 结构钉盘点 + 全量双绿 + 词表

**要做什么：** 阶段 2 收尾：index.html 主体收敛为「fx imports + app.js import + ui 各模块 imports + 页签分发器 + 启动 IIFE + init\* 调用」；审计全部结构钉（JS 与 pytest）重指向完备；`node --test` + pytest 双绿；真浏览器冒烟；CONTEXT.md 词表补充；中文提交 + CHANGELOG。

**被谁阻塞：** 01-19 全部

**状态：** 已实施（resolved）

## 检查表

- [x] index.html 主体瘦身：核对 import 段（18 fx + app.js + 17 ui 模块）+ 页签分发器 + 启动 IIFE（init）+ init\* 调用段；目标主体 ~150 行；**运行 git diff --stat 前后行数对比**（应在预期内）
- [x] 结构钉全盘点（grep tests/js + tests/ 中引用 index.html 的断言）：确认重指向新模块文件、无哑断言（断言目标文件存在）
- [x] fx-guard DOMAINS 表核对：本阶段新增 fx 名（truncate / fmtSeconds / fmtClock / fmtDuration / decisionItem / archiveItem 等——按实际迁移）全部登记；ui 模块名不进 DOMAINS（DOMAINS 只管 fx 纯函数单源）
- [x] 全量回归：`node --test "tests/js/*.test.mjs"`（基线 434 → 按新增单测计数）+ `pytest` 全绿
- [x] diag.mjs 零 EXC；smoke.mjs 11/11 全绿
- [x] 每 tab 实况探针（或按可用探针脚本汇总）：8 tab 渲染一把过
- [x] CONTEXT.md「前端纯函数单源」bullet 更新：增补「DOM 胶水单源 = static/js/ui/*.js（阶段 2）」与 index.html 主体角色
- [x] 中文提交 + CHANGELOG 记录（阶段 2 完成）

## 实施记录（工单 20 —— 阶段 2 收尾）

### 主体瘦身（最后一块补迁）
index.html 主体在 19 后仍剩最大胶水块 = **btn-generate 覆盖重发监听器（2353-2466，~114 行）**——工单 15 因依赖 host 内联 readinessState 留 host；19 迁出 readiness 后障碍解除 → **本票补迁 ui/generate-core.js**（模块顶层绑定；imports 补 readinessState / generateReadinessChecks / collectBindings / generationOutputDirPayload / genStageTexts / fmtWait / isConflictError / conflictDirName / markStepUndone / pythonTemplates / lastRecommend）。
- host 2246 import 行**收敛为 `import { initScoreChecklist } from "/js/ui/generate-core.js";`**（grep 复核：generateMain / renderGenerateSuccess / desktopTopicOutputEnabled / renderScoreChecklist / scoreChecklistSyncCurrent / scoreChecklistExportNow 在 host 均零调用点——readiness 模块化后 desktopTopicOutputEnabled 也由模块直接 import）。
- index.html 2725 → 2613 行；**主体（script 内）零 `^function` / 零顶层监听（除页签分发器）**——最终形态 = fx/app/ui imports（39 行）+ 页签分发器 + 启动 IIFE（init 装载 + setClusterDeps / setSettingsDeps 注册）+ init\* 调用段 + 各节「已迁」注记。

### 结构钉盘点（全绿）
- tests/js 引用 index.html 者 9 件：btn-icons（按钮 markup id）/ fx-guard（已搬名不得再定义）/ generate-overwrite（CONFLICT_MSG_PREFIX 单源 = fx）/ price-reference-clear（定价表 tbody，markup）/ recent-workflows-format（仪表盘文案，markup）/ recommend-telemetry（id 不动）/ score-points-format（#res-score-points markup + coreSrc 重指向）/ topic-cards / topic-detail（topic UI）。全部断言目标在 markup 或已重指向模块 ✓。
- pytest test_generate_check_contract.py：FIX_MAX_ROUNDS / 续跑文案 / fixLoop.resume 三钉已重指向 generate-fix.js（工单 16）；btn-fix-continue 按钮钉 = markup ✓。
- fx-guard DOMAINS：阶段 2 新增 fx 名 = fmtSeconds（工单 16，generate.js 域 + 补测 2 条）已登记 ✓；其余（truncate / fmtClock / fmtDuration / decisionItem / archiveItem）为阶段 1 已登记。

### 词表
CONTEXT.md「前端纯函数单源」bullet 更新：DOM 胶水单源 = static/js/ui/*.js（阶段 2 完成：03-11 各 tab 簇 + 12-20 generate 八簇）；index.html 主体角色（imports + 页签分发器 + 启动 + init\*）；接缝 / 所有权 / 无环 / 无 window 桥约定入词表。

### 验证矩阵（全绿）
- node --test "tests/js/*.test.mjs"：444/444；pytest：2465 passed（3 warnings 既有噪声）；diag 零 EXC；smoke 11/11。
- probe-20.mjs：6/6（core 动态 import / btn-generate 前置校验「请先选择目标平台」/ 填题面+平台+OLED 模块后进入生成流——「缺少必填字段：main_c」= 后端 400 中文（无骨架生成被拦的既有行为）/ 就绪面板 + 总览 chips 12 / 全程零 EXC / 无 HTTP>=400 异常）。
- 行数轨迹：阶段 1 基线 9046 → 工单 15 后 4374 → 16 后 3994 → 17 后 2975 → 18 后 2779 → 19 后 2725 → **20 后 2613**（markup ~2200 + 主体 ~400 含注释说明）。

### 踩坑记录（本轮）
- **`Array.prototype.findIndex(predicate, thisArg)` 第二参数不是 startIndex**——apply-20 初版把它当 startIndex 用，选区变成 a<b 空集（诊断脚本抓出）——改 slice+findIndex。本次八簇中唯一一次误用（其余脚本均为 fresh findIndex ✓）。
- 行尾 CRLF 混存事实复核：工作区 ui/*.js 行尾受 git checkout 策略影响（12/15 LF、16/18/19/20 CRLF）——运行时无影响，git 入库为 LF（autocrlf round-trip）；多行替换串一律 `\r?\n` 容错（16/18/19/20 多处踩坑记录在案）。

## 风险点

- 阶段 2 全程「纯搬家」；若收尾发现某票引入的行为漂移，回滚该票（git revert）而非带病收尾。
- index.html 行数验收：预期 9046 → ~600-800（含 markup + head + host）；host 脚本主体 ~150 行。
