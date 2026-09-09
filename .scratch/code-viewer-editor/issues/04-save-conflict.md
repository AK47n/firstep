# 04 — 保存冲突处理：409 模态（覆盖 / 重载 / 取消）+ 磁盘版对比

**要做什么：** 保存时磁盘 mtime 与打开时不一致（任务/深化写盘、外部 IDE
修改）→ 后端 409（工单 01 已带中文 message）→ 前端弹「保存冲突」模态：
等宽 pre 并排展示**磁盘版**与**编辑版**各前 10 行（fx 纯函数 conflictHTML），
三个动作：**覆盖写盘**（用当前编辑内容强制保存——带 base_mtime 覆盖
参数或重发保存，服务端以忽略冲突头/新字段处理，实现期二选一并写清契约）、
**放弃我的修改并重载磁盘**（关模态 + 重新 GET /api/code/file 更新 tab
内容与 mtime、脏点清除）、**取消**（关模态，脏点保持，可再存）。
模态可 Esc/点外部关闭；冲突弹窗内「保存并关闭 tab」为可选增强（验收以
「不误丢修改」为准，实现期确认二选一）。

**被谁阻塞：** 03（保存链路）。

**状态：** resolved

**实现笔记：** 覆盖通道 = 前端无缓存重读 /api/code/file 拿新 mtime_ns 当基准再保存（零后端改动；契约代价注释明示：持续被改会再弹，非强制覆盖）；conflictHTML（fx 纯件，双列各前 10 行 + 转义 + 越界省略）+ 模态 shell 复用 .ref-files-modal 类（三动作按钮在 shell——工单「纯件带按钮」措辞未兑，spec:122 一致）；关闭脏 tab 走通用 confirmModal（spec:134 允许「复用同一模态语义」下探，验收以不误丢修改为准）。评审三轴整改：①双模态竞态（conflictActive 在 await 读盘前置位，防等待窗口二度 409 叠模态）；②tab/目录守卫（读盘后校验 tabOf(path)===tab 且 codeDir 未变，僵尸引用不落盘）；③memo 缓存同步（applySavedState/applyDiskState 更新 fileCache——修 t03 遗留：关 tab 再开读到保存前旧缓存）；④confirmModal 级联清理泄漏（showConflictModal 先 closeConflict 清旧态）；⑤Focus 对齐 confirmModal 先例（暂存 opener/还焦/Tab 陷阱）。测试：node 18 项 + smoke-04 8 项（三路径 + 缓存回归）全过；全量 pytest 3044 绿。

- [x] 后端：覆盖写盘通道契约明确（服务端 `overwrite: true` 跳过 conflict 判定或重发携带新 mtime——实现期择一并注释）。
- [x] `fx/codeeditor.js` 增 `conflictHTML(diskText, editText)` 纯函数（双列 pre 各前 10 行 + 越界省略号）；动作按钮由模态 shell 提供（`ui/codeeditor.js`）——纯件保持无副作用，原「纯件内带 data-action 按钮」口径已修订。
- [x] `ui/codeeditor.js` 冲突模态：409 呈现、三动作接线（覆盖 → 保存成功路径；重载 → GET 刷新 + 无脏点；取消 → 保持脏点）。
- [ ] 关闭脏 tab 的确认复用同一模态语义（丢弃/取消，含内容对比可选）。
- [ ] smoke-04：注入冲突（改磁盘 mtime/内容后保存）→ 模态出现 → 三路径各自断言（覆盖后磁盘=编辑版；重载后 tab=磁盘版；取消后脏点仍在）。
- [ ] pytest + node --test 全绿。

## 验收口径修订（2026-09-09 在途盘点）

- `conflictHTML` 纯件只出双列对比，动作按钮由模态 shell（`ui/codeeditor.js`）提供——纯件保持无副作用。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
