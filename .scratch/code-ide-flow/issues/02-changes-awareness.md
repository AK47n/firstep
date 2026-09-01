# 02 — 切回感知：干净标签自动重载 + 脏标签「磁盘已变更」徽章 + 树同步

**要做什么：** 代码 tab 打开目录时记录基线（persist 到 localStorage，按目录
隔离）；每次树刷新 / 切回「代码」tab 时重扫磁盘对比基线，命中变更后：
干净标签（无未保存编辑）自动重载磁盘版 + toast「N 个文件已被外部更新，已自动
重载」；脏标签绝不静默重载——标签加「磁盘已变更」徽章，点击弹既有保存冲突
三选模态（覆盖我的修改 / 加载磁盘版 / 取消）；文件树同步刷新，新增条目带
「新」徽章、修改条目带「变」徽章、消失条目从树移除。main.c 变更继续走既有
`refreshMainCDiskState()`。端到端验证（外部编辑器改文件 → 切回 → 感知）。

**被谁阻塞：** 01（基线对比纯件）。

**状态：** resolved

**结论：** 已落地（评审整改后）。

**后端（spec「零后端改动」的必要例外，s2 评审确认）**：`codeview.py
list_code_tree` 文件条目补 `mtime_ns`（st_mtime_ns 字符串，一次 stat 同喂
size——原有 /api/code/open 树清单无 mtime，整树对比无事实源）；tests/
test_codeview.py + test_webapp.py 断言更新（成员匹配 + mtime 字符串断言）。

**前端感知链路（ui/codeview.js 胶水）**：localStorage 键 `firstep.codeBaseline`
（store = {dir → {ts, files}}，LRU 8 目录）；基线语义 = **用户最后确认点**——
推进仅：首次打开建立 / 保存·树操作后 / 「清空并确认已看」（03）；对比纯计算
不推进（否则变更集被吞——审查：打开即推进违背用户故事 2）。`probeDiskBaseline(dir)`
抽为 loadCodeDir 与 checkCodeDiskChanges 共用探测序（评审 #1：防双份漂移）；
`applyDiskChanges(diff)` 联动：干净标签 `reloadTabFromDisk`（mtime 相同 →
"already" 零动作防重复 toast）/ 脏标签 `setDiskChanged` 徽章 / 树「新·变」
徽章（TREE_CHANGE_NEW/MODIFIED 常量单源，评审 #3）/ main.c 走
refreshMainCDiskState() / toast「N 个文件已被外部更新，已自动重载」。

**编辑器侧（ui/codeeditor.js）**：tab.diskChanged 态 + fx codeTabStripHTML
渲染「!」徽章（data-tab-disk 事件层，点徽章 stopPropagation 弹**既有**三选
`openDiskConflict`→showConflictModal，Promise 路径与 saveAllDirtyTabs 同源）；
applySavedState / applyDiskState 清磁盘态标志；setDiskChanged 仅 renderTabs
（评审 #6：只刷必要面）。

**触发点**：index.html tab 切换钩子（`btn.dataset.tab === "code"` →
checkCodeDiskChanges）+ loadCodeDir 成功 + refreshCodeTreeOnly（树操作后整体
对齐基线——本 IDE 改盘不算外部变更）。

**spec.md 措辞更正（评审）**：①「零后端改动」→ 记录 mtime_ns 补充例外；
②「基线更新点 = 打开目录/清空」→ 细化为：首次建立 / 保存单文件 / 树操作 /
清空，打开已有基线不推进；③「消失条目」标签保留**可编辑**（不置只读——用户
可从旧内容复制走后保存；保存时报后端既有文件缺失中文文案，验收 4「不崩溃」
满足，评审 a1 判断）。

**评审整改（code-review 双轴）**：standards #1 探测序抽共享 + #2 渲染双次
收敛（无变更一次/有变更 apply 内一次）+ #3 徽章类型常量 + #4 跨目录徽章
残留（diff null/无变更 → codeTreeChanges = {}）+ #5 注释对齐 + #6 setDisk
粒度；spec 轴 a2（CDP 冒烟）→ smoke-02.mjs 11 项全 PASS（写盘感知/自动重载
/toast/树徽章/脏保护/徽章三选）；a1 判断如上；b1/b2/c2 → spec.md 文档化；
reference.json/素材清单.txt 为工作区既有噪音，未纳入提交。

**测试**：node 全量 1026 全绿（含新增 codeview/codeeditor 徽章用例）；pytest
全量 3101 全绿；SMOKE-02 11/11 PASS。验收 1-7 全部满足。

- [x] 验收 1：打开目录即写基线；再次打开同目录不误报（无变更）。
- [x] 验收 2：外部修改磁盘（干净标签）→ 切回 tab → 标签内容已更新 +
  toast 出现；文件树同步（新文件即现 + 「新」徽章）。
- [x] 验收 3：脏标签（有未保存编辑）+ 外部修改 → 切回 tab → 标签内容**不变**
  （不静默重载）+ 「磁盘已变更」徽章出现；点徽章弹既有三选模态，三选行为
  与保存冲突一致（覆盖 = 我的编辑写盘 / 重载 = 加载磁盘版 / 取消 = 维持现状）。
- [x] 验收 4：文件消失（磁盘删除）→ 树上移除；已打开该文件的 tab 仍可查看
  旧内容（只读态不崩溃——不置只读保留可编辑 + 保存报后端既有中文文案兜底），
  保存时报既有错误文案。
- [x] 验收 5：main.c 被外部修改 → 步骤 8 状态行照旧联动（既有行为不回归）。
- [x] 验收 6：切换目录 → 基线随目录切换；回到旧目录基线仍在（不串台、不误报）。
- [x] 验收 7：CDP 冒烟覆盖 2/3 主路径（smoke-02.mjs 11 项全 PASS），全量回归绿。
