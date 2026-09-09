# 02 — 代码栏「保存全部脏标签」+ 冲突模态可等待

**要做什么：** ui/codeeditor.js 新增导出 `saveAllDirtyTabs()`（→ Promise<{ok, canceled}>）：遍历全部标签，对脏且非只读的逐个写盘（跳过非脏/只读）；保存冲突弹既有冲突模态并**等待**用户三选一（覆盖/重载/取消）后继续/中止；单文件 Ctrl+S 保存行为不变。

**被谁阻塞：** 无——可立即开始（真实编译流程在 03 接上）。

**状态：** resolved

**结论：** 已落地。saveAllDirtyTabs()（遍历 dirtySavableTabs 纯件筛选的脏且非只读标签，逐个 await；取消/保存失败 → {ok:false,canceled:true} 并停止）；showConflictModal 改为返回 Promise（覆盖=写盘成功后 resolve / 重载 / 取消·×·Esc·遮罩，Promise 永不 reject——Ctrl+S 不 await 行为不变）；postSave 载荷单源（评审整改）。node 全量 1001 全绿 + smoke-04 8/8 回归全绿。

- [x] 验收 1：saveAllDirtyTabs 保存所有脏标签（写盘成功 → 脏点清除、mtime_ns 基准更新、onFileSaved 通知，与 saveActiveTab 同路径）。
- [x] 验收 2：冲突时弹既有冲突模态，用户选「覆盖写盘」→ 覆盖后继续（返回 ok）；「放弃并重新加载」→ 加载磁盘版后继续（返回 ok）；「取消」→ 中止并返回 canceled（不继续保存其余标签）。
- [x] 验收 3：只读（非 UTF-8）/非脏标签被跳过，不产生任何请求。
- [x] 验收 4：Ctrl+S 单文件保存路径行为回归不变（含 409 弹模态）；node tests/js 全量绿（含 codeeditor / 冲突相关）+ smoke-04 回归绿。
- [x] 验收 5：无脏标签时立即返回 {ok: true, canceled: false}，零请求。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
