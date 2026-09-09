# 08 — 变更面板行级 diff 泛化（去 main.c 特例）

**要做什么：** 三期收口：change-panel 行级 diff 区从「仅 main.c」泛化为
「任何 modified 且 snapshotAvailable（content 快照存在且 256KB 内）的
条目」：
- fx/change-panel.js：isMainCPath 判定移除 → 条目字段
  `hasLineDiff`（调用方计算传入；按当前行级渲染逻辑初始化）；面板无路径
  特判（main.c 与其它文件同一渲染）。
- ui/codeview.js renderChangePanel：diff 计算对象从「main.c modified +
  快照」扩为「任意 modified + 快照在」；快照取用统一 getBaselineContent(dir,
  path)（工单 07 的 content 字段，maincContent 特例删除后同源）。
- 占位文案/折叠/details 结构不变（标题行「行级改动（path）」）。
- main.c 行为回归：此前 main.c 必有行级区——现在同样满足（快照存在），
  无可见变化。

**被谁阻塞：** 07（content 快照）。

**状态：** resolved

- [ ] 验收 1：打开过的非 main.c 文件 external 修改 → 面板展开行级 diff 区
  （stats+hunks/TODO 标题照常）；未打开 → 无行级区。
- [ ] 验收 2：main.c 行为与 03 期一致（行级区始终在）。
- [ ] 验收 3：maincContent 特例删除后无引用残留（grep 校验）；node +
  smoke-03/**smoke-05 新增用例**全绿。

**结论：** 已实现（待双轴评审整改确认）：
- **模块/函数改名**（泛化后命名体系一致——评审判断项预整改）：
  fx/mainc-diff.js → fx/line-diff.js；maincDiffCompute → lineDiffCompute；
  MAINc_DIFF_MAX_CELLS → LINE_DIFF_MAX_CELLS；tests/js/mainc-diff.test.mjs
  → tests/js/line-diff.test.mjs（git mv 保历史）。
- fx/change-panel.js：changeEntryHTML `isMainCPath(e.path)` 移除 →
  条目字段 `e.hasLineDiff`（调用方计算传；无路径特判——非 main.c 文件
  同一渲染）；summary/占位文案路径泛化（「行级改动（path）」/「path
  行级差异不可用…」）；isMainCPath import 删。
- ui/codeview.js：新增 getBaselineContent(dir, path)（基线条目 content
  快照统一读取——07 字段单源）；renderChangePanel 泛化——任何 modified
  且基线有 content 快照的条目 hasLineDiff=true → lineDiffCompute(旧快照,
  当前磁盘)——main.c 与其它打开过的文件同一渲染。
- ui/code-ai-chat.js：maincDiffCompute 引用同步（lineDiffCompute——
  预览 AI 改动同样经泛化后的计算）。
- 测试：tests/js/line-diff.test.mjs 6 用例（改名同步）；tests/js/
  change-panel.test.mjs 增 2 用例（非 main.c 同样带行级区/占位文案路径
  泛化）——8 用例全绿；node 全量 1083 全绿。
- smoke-03 追加 08 泛化场景：打开 src/app.h → 外部改 → 面板行级区
  （summary 含「行级改动（src/app.h）」+ diff-hunk + diff-stats）——
  SMOKE-03 全 PASS（含原 14 项回归——此冒烟同时覆盖验收 2 main.c
  行为回归）；smoke-02/04/05/06/07/08 回归全 PASS。
- 踩坑：CDP Runtime.evaluate 中 `:scope + details` 选择器不匹配（疑似
  Element.querySelector 的 :scope 解析差异）→ 改遍历 details 集合 +
  summary 文本匹配；Eval 顶层 return 需 IIFE；样本目录实际只有
  src/app.h（无 src/app.c——resetSample fixture 核对）。
- 已知语义记录：验收 2「main.c 行为与 03 期一致（行级区始终在）」——
  以「快照存在」（= main.c 打开过）为前提——07 起 main.c 快照随打开建立
  （03 期为每次推进 fetch）；生成上下文目录实操中 main.c 必然打开过，
  可见行为一致（smoke-03 原 14 项含 main.c 行级区场景全 PASS）。
- **双轴评审整改（s8）**：①hasLineDiff → hasLineDiffSource（实义「基线
  有快照 → 可试渲染」；issue 原字段名记录偏离）②fx/diff.js 占位
  「未改动 main.c」泛化为「未改动文件」（3 测试断言同步）③
  line-diff.test.mjs BOM 剔除（PowerShell 误写）④change-panel 占位文案
  矛盾修复（「无旧版本快照」→「内容未变化、当前内容读取失败或差异过大」
  ——hasLineDiffSource=true 时快照必在）⑤getBaselineContent 加可选
  loaded 参数（渲染循环外 load 一次——评审：循环内 O(n) 重复解析）
  ⑥spec 三期段「mainc-diff.js 无需改」矛盾改述为 line-diff.js。

- [x] 验收 1：打开过的非 main.c 文件 external 修改 → 面板展开行级 diff 区
  （stats+hunks/TODO 标题照常）；未打开 → 无行级区。
- [x] 验收 2：main.c 行为与 03 期一致（行级区始终在——「快照在」前提，
  见结论语义记录）。
- [x] 验收 3：maincContent 特例删除后无引用残留（grep 校验——残留仅在
  migrateBaselineStore 兼容层与注释）；node + smoke-03 新增用例全绿。

（双轴评审记录见 spec.md「评审确认」段，整改后更新。）

## Comments

- 2026-09-09 补标 resolved（代码事实盘点，复核工单自述）：
  `src/contest_generator/static/js/fx/change-panel.js`——`changeEntryHTML`（52）
  第 69 行 `if (st === "modified" && e.hasLineDiffSource)`，**无 `isMainCPath`
  路径特判**（grep 该文件 isMainCPath 零命中）；`static/js/fx/line-diff.js`
  存在（`lineDiffCompute` 90、`LINE_DIFF_MAX_CELLS` 18、TODO 标题 62），
  `fx/mainc-diff.js` 已不存在。
  `static/js/ui/codeview.js`——`getBaselineContent(dir, path, loaded)`（313）、
  `renderChangePanel` 泛化（337-345：任意 modified 且基线有 content 快照 →
  `hasLineDiffSource = true` → `lineDiffCompute(旧快照, 当前磁盘)`）。
  测试：`tests/js/change-panel.test.mjs:49`（非 main.c 文件同样带行级区，
  断言 `src/app.c` 的 details/summary）、`:40`（hasLineDiffSource 带区）、
  `:56`（无快照 → 无区）；`tests/js/line-diff.test.mjs` 6 用例；
  实测 `node --test` 四文件 39 passed / 0 fail。
  验收逐条对照：① 非 main.c 打开过 → 行级区（:49）✓ ② main.c 行为一致
  （:40 + smoke-03 原 14 项）✓ ③ maincContent 特例无引用残留——grep
  `src/contest_generator/static/js/**` 命中仅 `migrateBaselineStore` 兼容层
  （disk-baseline.js:86-108）与 `maincContentEmpty`（另一个函数，fx/code.js:109，
  非基线字段），无残留 ✓。
