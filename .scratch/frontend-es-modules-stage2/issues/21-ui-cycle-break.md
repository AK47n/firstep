# 21 — 断环：desktopTopicOutputEnabled 归位 ui/generate-readiness.js

**要做什么：** 消除 ui 模块双向 import 环 `generate-core ↔ generate-readiness`（评审发现 1，backlog 4.1）——把「桌面输出开关」判定 `desktopTopicOutputEnabled`（纯 DOM 读：`$("desktop-topic-output").checked ?? true`）从 generate-core.js 移入 generate-readiness.js 并导出；它是 readinessState「检查能否生成」判据输入（desktopOutput 字段），语义归位。生成簇 ui 依赖恢复单向：core / steps → readiness（core 保留 →readiness 单向 import；readiness 不再 import core）。

**被谁阻塞：** 无——评审收尾发现，backlog 已记录

**状态：** resolved

## 背景（代码事实）

- 环两条边：`generate-core.js:35` `import { readinessState } from "/js/ui/generate-readiness.js"`（btn-generate 监听器前置校验，工单 20 补迁引入）；`generate-readiness.js:21` `import { desktopTopicOutputEnabled } from "/js/ui/generate-core.js"`（readinessState() L36 使用）。
- 第三消费方 `generate-steps.js:27` 也从 core import desktopTopicOutputEnabled（L109 outputDirMissing 判定）——steps 另有 L24 `readinessState` 自 readiness，改名即并。
- core 本地使用点：L133（desktop-topic-output change 监听器）/ L137-138（初始 disabled）。
- 运行时安全（函数级 live binding、无顶层互调），但违反 spec.md 桥接约定 3「ui 模块之间允许单向依赖」与 CONTEXT.md「ui 模块间允许单向静态 import」（A↔ST 先例 spec L59-63 拆 step-state 消环）。

## 验收标准

- [ ] 新增 `tests/js/ui-cycle.test.mjs`：静态解析 `static/js/ui/*.js` 全部 ui→ui import 边 → 环检测 → 断言无环（先红后绿；实现前当前环必须触发断言失败）
- [ ] desktopTopicOutputEnabled 定义移入 generate-readiness.js（readinessState 上方）并加入导出块；generate-core.js 删本地定义（L125-128）+ 导出面移除（L567）；generate-steps.js:27 并入 L24 readiness import
- [ ] 全库 grep：generate-core.js 零定义/零导出；index.html 与两个簇头部注记同步（desktopTopicOutputEnabled 归属文本更新）
- [ ] node --test 全绿 + pytest 2465 passed + diag 零 EXC + smoke 11/11
- [ ] 中文提交（不经 --no-verify）

## 实施记录

- desktopTopicOutputEnabled 定义移入 ui/generate-readiness.js（readinessState 上方，L33-39 区域，含注记）并加入导出块；generate-core.js 删本地定义（原 L125-128）+ 导出面移除（原 L567）；core 的 L36 改 `import { readinessState, desktopTopicOutputEnabled } from "/js/ui/generate-readiness.js"`；generate-steps.js 的 L27 删除、L24 并入同名 import；index.html 两处「已迁」注记同步（工单 20 后 host 实际只 import initScoreChecklist）。
- 新守卫 tests/js/ui-cycle.test.mjs：静态解析 ui/ 目录全部 ui→ui import 边 + Kahn 拓扑判环——实现前红（seen 9/19，断言报告环成员），实现后绿；全量 node --test 445/445。
- review-import-graph.mjs 复核：模块 import 环 =（无环）；app.js 无 ui 依赖 ✓；host import 39 行不变（只 initScoreChecklist 自 core）。
- diag 零 EXC（pwsh-26）+ smoke 11/11（pwsh-27 在工单 23 后亦复跑 ✓）。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
