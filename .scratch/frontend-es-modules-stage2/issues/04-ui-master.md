# 04 — 母版页 + 更新记录试点：static/js/ui/master.js（含 distPanel / 报告 / 扫描）+ loadChangelog

**要做什么：** 母版 tab 全部 DOM 胶水迁入 `static/js/ui/master.js`（含 distPanel 实例与提炼事件回调、扫描/暂存目录、报告渲染、母版库表格、文件查看、删除确认、loadChangelog 更新记录——changelog 为独立小 tab，随母版合入同一文件）。本票是 ui 模块化第一张完整 tab 切片，验证「02 app.js 共享壳 + 03 progress.js 共享件 + 04 域模块」三层结构成立。

**被谁阻塞：** 02（app.js）+ 03（progress.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 区段 = 母版页 7334-7926（含 changelog 7902-7926）；markup @1948-2015（tab-master）+ 项目目录 @1952-1959（#project-dirs / #staged-dirs / #scan-msg / #scan-result / #distill-progress / #report，均在母版 section——markup 零改动）。
- 函数/状态：scannedProjects 7337 / currentReport 7338 / stagedDirs 7339；projectDirs 7341；renderStagedDirs 7346；pick-dirs + btn-pick-dirs + btn-scan 监听 7360-7406（top-level，随迁）；distPanel const 7415 + PHASE_LABEL 7413 + 事件回调 7420-7470；decisionItem 7666 / archiveItem 7677 / renderReport 7685；openMasterDeleteConfirm 7777 / loadMasterFileState 7824 / renderMasterFileContent 7839 / openMasterFile 7850 / openMasterDetail 7862 / loadMasters 7886；loadChangelog 7902。
- 共享件引用：`$` / handle / apiPost / apiGet（app.js）；setStep / addLogLine / addBatchLine / updateBatch / startProgress / finishProgress / failProgress / MAX_LOG_LINES（progress.js）；makeProgressPanel（progress.js，实例化 distPanel）；esc（fx/core.js）；master 域纯件（fx/master.js：masterTableRowHTML / masterDetailHTML 等——迁出后经 import 绑定调用，调用点零改动）。
- 母版保存/提炼 API 端点：POST /api/masters/stage（整夹上传）、POST /api/masters/scan、distill 相关——后端不动。

## 检查表

- [ ] 新建 `static/js/ui/master.js`：上述件逐字搬移 + import（app.js / progress.js / fx 域模块）+ export（loadMasters / loadChangelog / renderReport / openMasterDetail 等 host 与探针需要面）+ 头部注释
- [ ] index.html：CRLF 感知行区间删除（**物理升序**；区段内 distPanel 回调与共享件交错——本票只删母版专属行，progress 共享件已由工单 03 先搬）+ 顶部 import 行追加
- [ ] host 页签分发器 import loadMasters / loadChangelog；启动 init 若涉母版（无 init*）核对
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 母版 tab 实况探针（probe-04 先例：loadMasters 后表格行数 > 0；window 桥不新增）
- [ ] grep 零残留：index.html 无 `function loadMasters(` / `function renderReport(` 等定义
- [ ] 中文提交

## 风险点

- 本票是试点：确认「top-level addEventListener 随迁后事件绑定时机 = import 时（module 先于主体求值）」成立——与阶段 1 桥接约定一致，冒烟与探针双重验证。
- renderReport / decisionItem / archiveItem 若被其他 tab 引用（如生成结果区），grep 后补 import 边。
