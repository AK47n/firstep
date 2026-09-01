# 03 — 「磁盘变更」面板（底部可折叠 + 条目跳转 + main.c diff + 清空已看）

**要做什么：** 代码 tab 底部新增可折叠「磁盘变更」面板（与编译面板并列）：
内容 = 基线 vs 磁盘对比结果的文件级条目（状态 新增/修改/消失 + 相对路径 +
修改时间 / 大小）；点击新增/修改条目 → 跳转打开对应文件；消失条目置灰不可点；
main.c 条目展开显示既有确定性 diff（复用 main_diff 渲染，默认折叠）；
「清空并确认已看」按钮 → 基线更新为当前磁盘快照、条目清空；无变更时面板
显示空态文案并可整体收起。条目渲染为 fx 纯件（node 单测）。

**被谁阻塞：** 01（基线对比纯件）；与 02 串行（同区域文件改动，避免冲突）。

**状态：** ready-for-agent

- [ ] 验收 1：打开目录后无变更 → 面板空态（或收起）；出现变更后（外部 /
  AI 写盘）切回 → 面板列出三类条目，状态徽章区分。
- [ ] 验收 2：点击新增/修改条目 → 打开对应文件（若有未保存编辑走既有保存
  守卫提示）；点击消失条目 → 无动作（置灰）。
- [ ] 验收 3：main.c 修改条目 → 展开显示 diff 统计 + hunks（复用 mainDiff 渲染）；
  无差异/无 diff 数据 → 占位文案。
- [ ] 验收 4：「清空并确认已看」→ 基线更新为当前快照，面板条目清空；再切走
  切回不误报。
- [ ] 验收 5：面板与编译面板并排、可折叠、不互相覆盖；窄屏不溢出。
- [ ] 验收 6：条目渲染纯件 node 单测全绿；CDP 冒烟覆盖面板出现/跳转/清空主路径。

**结论：** 已落地（双轴评审整改后）。

**新 fx 纯件**：`fx/mainc-diff.js`——main.c 行级确定性 diff 计算（行级 LCS
DP + hunk 分组（n=2、块间距 ≤4 合并）+ TODO 标题三规则），与后端 deepen.py
main_diff **逐条对齐**（splitlines 尾空行、@@ 起始行 = ctx 起点、TODO/注释
标题；两套实现需同步维护——spec 评审确认记录）；MAINc_DIFF_MAX_CELLS（400
万单元格）超限 → null 占位。`fx/change-panel.js`——面板条目渲染（三类状态
徽章「新/变/消失」+ 路径 + 时间/大小；added/modified 为按钮 data-change-path
交事件层跳转；removed 为 span 置灰）；summary 计数摘要；main.c 修改条目带
行级 diff 区（details 默认折叠，渲染复用 fx/diff.js mainDiffHTML 单源；
无数据/无差异 → 中性占位文案）。

**ui 胶水（codeview.js）**：模块态 `codeDiskChanges`（变更集单源——面板
数据 + 树徽章同形状；changesOf/emptyChanges 构造单源）；基线 store 每目录
`maincContent` 内容快照（cap 256KB → 占位；baselineCommitDisk async fetch
一次 /api/code/file；baselineUpdateFile 保存 main.c 时推进用户确认版）；
`renderChangePanel`（条目 + 摘要 + 面板显隐；main.c 行级 diff = 快照 vs 当前
磁盘）；`clearCodeDiskChanges`（「清空并确认已看」：基线整体推进（含快照）+
待看清零 + 树/标签徽章清空 + toast）；各路径（check/load/refresh/onFileSaved）
的变更集维护与面板联动。

**面板 DOM/CSS（index.html）**：`#code-change-panel` 与编译面板同型并列
（共用 .code-compile-head/.code-compile-status + `#code-compile-panel,
#code-change-panel` 公共选择器；.collapsed 独立收起）；条目 CSS 全走令牌。

**评审整改（s3 双轴）**：standards——④Middle Man isMaincEntry 删除（直接
isMainCPath）、⑤cap 判空抽 maincSnap 单源、⑥变更集构造抽 changesOf、
mk→makeEntry 命名、MAINc_DIFF_MAX_CELLS 命名保持（模块体系一致）；spec
轴——①( c1) 占位文案区分「内容未变化/无快照/差异过大」、②(c2) baselineCommitDisk
else 分支落盘（防旧 mainc 快照残留）、③(a1) 面板「实时」语义 = 跟随感知
刷新（不做独立 watcher——spec 括号语义）与④空态=收起（issue 验收 1「或
收起」）与⑤双实现同步约束/存储预算/hunk 边界低危 → spec.md「评审确认」
段文档化；(a2) CDP 冒烟 → smoke-03.mjs 14 项全 PASS。

**测试**：node 全量 1038 全绿（mainc-diff 6 用例 + change-panel 6 用例）；
SMOKE-03 14/14 全 PASS（三类条目/摘要/置灰/diff 区/TODO 标题/点击跳转/
清空收敛/清空后重新感知）；SMOKE-02 回归全绿（03 未破坏 02）。后端零改动
（pytest 不涉）。验收 1-6 全部满足。

- [x] 验收 1：打开目录后无变更 → 面板空态（收起——issue「或收起」）；出现
  变更后切回 → 面板列出三类条目，状态徽章区分。
- [x] 验收 2：点击新增/修改条目 → 打开对应文件；点击消失条目 → 无动作（置灰）。
- [x] 验收 3：main.c 修改条目 → 展开显示 diff 统计 + hunks（mainDiff 渲染）；
  无差异/无 diff 数据 → 占位文案（区分「内容未变化/无快照/差异过大」）。
- [x] 验收 4：「清空并确认已看」→ 基线更新为当前快照，面板条目清空；再切走
  切回不误报。
- [x] 验收 5：面板与编译面板并排、可折叠、互不覆盖（同型 head + 独立
  collapsed；窄屏同编译面板行为）。
- [x] 验收 6：条目渲染纯件 node 单测全绿；CDP 冒烟覆盖面板出现/跳转/清空主路径。
