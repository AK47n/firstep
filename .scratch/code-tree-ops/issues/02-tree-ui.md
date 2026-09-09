# 02 — 树 UI：新建 / 重命名 / 删除 + tab 联动

**要做什么：** fx/code-tree-ops.js 纯件（treeNameValidate / treeAffectedPaths /
treeRenamedPath / treeOpConfirmTitle+Message / treeTabOpenPaths）+ 新
ui/code-tree-ops.js（新建文件/文件夹输入模态、每行 hover ✎/🗑、重命名、
删除确认、成功后 openCodeViewer 重载树 + tab 路径映射/关闭联动 + 脏保护
两键、main.c 特例 refreshMainCDiskState）+ index.html 树头部按钮与 CSS +
fx-guard 登记 + node 单测。

**被谁阻塞：** 01（后端端点可用）。

**状态：** resolved

- [x] 验收 1：树头部「新建文件 / 新建文件夹」按钮就位；输入模态复用
  confirmModal extra 输入，名称校验失败中文提示（非法名不关闭/不落盘）。
- [x] 验收 2：每行 hover ✎/🗑（文件与目录行）；✎ → 重命名模态（默认值 =
  当前名称）；🗑 → 删除确认（文案含路径）。
- [x] 验收 3：新建文件成功后树刷新 + 自动打开该文件 tab（空内容，可编辑，
  可保存）；新建文件夹成功后树刷新（无 tab 打开）。
- [x] 验收 4：重命名成功 → 树新名；已打开 tab 路径映射（标签/活动路径同步，
  脏状态与 mtime 基准不变）；目录改名 → 子树 tab 一并映射。
- [x] 验收 5：删除成功 → 受影响 tab 关闭；受影响 tab 有脏 → 先两键提示
  （保存全部并继续 / 取消），取消则中止；非空目录删除 → toast 400 中文。
- [x] 验收 6：main.c（生成上下文）被改名/删除 → 完成后 refreshMainCDiskState
  同步步骤 8 状态行。
- [x] 验收 7：node 单测（纯件边界）+ fx-guard 登记全绿。

**结论：** 已落地。fx/code-tree-ops.js（treeNameValidate / treeOpAffected /
treeOpTitle / createPromptMessage / renamePromptMessage / treeOpConfirmMessage /
treeNamePromptHTML / CODE_TREE_NAME_ILLEGAL / CODE_TREE_NAME_MAX + window 桥）；
ui/code-tree-ops.js（guardTreeOpWrite 两键脏保护、treeCreate / treeRename /
treeDelete、initCodeTreeOps 树内委托 + 树头部两按钮）；codeview.js buildCodeTree
支持 is_dir 条目；codeeditor.js closeTab(force) / remapOpenTabPaths /
invalidateFileCache / dirtyTabPaths / openTabPaths / fileCacheKey 单源；
codeview.js refreshCodeTreeOnly / getCodeTreeDir / getCodeTreeFiles；index.html
树头部按钮 + 每行 ✎/🗑 + CSS（.code-tree-actions 行 hover 显示）。测试：
tests/js/code-tree-ops.test.mjs 8 测试、fx-guard DOMAINS 登记、node 全量
1016 全绿；CDP 冒烟（票 03）覆盖树操作全链路。

**接受偏差（双轴评审记录）：** ① spec §3 纯件命名走样——treeAffectedPaths(path,
op)（返回受影响集合）/ treeOpConfirmTitle+Message / treeTabOpenPaths(tabs)
未按名兑现，实现为布尔谓词 treeOpAffected(tabPath, targetPath, isDir) + 拆分
文案函数 + codeeditor 既有 openTabPaths()/dirtyTabPaths()（功能等效；fx 不耦合
ui tab 结构，tab 集合由既有单源给出；测试与 fx-guard 走新名）；② 输入模态校验
失败→模态内错误提示未做，走 spec 预留「非法名 toast」两段式（合法合规）；
③ 删除确认按钮文案「确认删除」（spec 字面「删除 / 取消」，冒烟按实现断言）；
④ createPromptMessage(kind, parentPath) 的 parentPath 恒为 ""（后端 create
路径可含子目录；本期 UI 新建仅在根目录，参数为后续扩展留口）；⑤ 新建成功后
刷新用 refreshCodeTreeOnly()（只重拉树不碰标签）而非 spec 所述 openCodeViewer
（后者清全部标签，疑 spec 笔误）；⑥ rename 不做脏保护（spec 仅在删除路径规定；
rename 脏状态/mtime 不变、无数据风险——评审整改已删初版 guardTreeOpWrite
调用）；⑦ treeOpIsDir 保留在 fx 导出 + fx-guard + 单测（评审仅要求删 ui 层
死 import，已删）。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
