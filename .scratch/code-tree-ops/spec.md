# 代码树操作（新建 / 重命名 / 删除）+ 保存全部

> 会话/系列 slug：code-tree-ops。立项：2026-08-31（用户拍板）：
> ①文件树增删改 = 树头部「新建文件 / 新建文件夹」按钮（输入模态复用
> confirmModal 的 extra 输入）+ 每行 hover ✎/🗑 图标；②删除 = 文件 +
> 空目录（非空目录拒绝，中文提示）；③保存全部 = 仅「保存全部」按钮
> （状态栏）+ Ctrl+Shift+S（复用 saveAllDirtyTabs），「关闭全部」不做。

## 问题陈述

「代码」tab 现在只能浏览 / 编辑 / 保存既有文件（code-viewer-editor +
code-tab-compile）。学生拿到生成工程后经常要加自己的 .c/.h（写传感器驱动、
调试桩）、重命名文件、清理无用文件——现在必须去磁盘管理器操作再回代码栏
刷新，断链。本特性给文件树补齐最小增删改闭环 + 保存全部，让「打开就能用」
的 IDE 手感闭环。

## 方案

### 1. 后端三端点（codeview.py + webapp.py `/api/code/tree/*`）

全部复用 `_resolve_in_root` 单源（is_unsafe_path + resolve 在 root 内），
失败均 400 中文 `CodeViewError`（errors.py 既有表项）：

- `POST /api/code/tree/create` `{dir, type: "file"|"dir", path}`：
  path = 相对目录的 POSIX 路径（可含子目录，前端由「当前展开目录 + 名称」
  拼接）；`type="file"` → 创建空文件（`mkdirs` 父级 + 原子空写），已存在 →
  400「已存在」；`type="dir"` → `os.makedirs(exist_ok=False)`，已存在 → 400。
  文件返回 `{path, size_bytes, mtime_ns}`（mtime_ns 字符串，与 save 同口径
  ——创建即得基准，前端打开该文件直接进入编辑态）；目录返回 `{path}`。
- `POST /api/code/tree/rename` `{dir, path, new_name}`：new_name 为**单段**
  文件名/目录名（前端校验 + 后端兜底：非空、不含 `/ \ : * ? " < > |`、
  不为 `.` / `..`）；目标 = 父目录 / new_name；源不存在或目标已存在 →
  400 中文；`os.rename` 原子改名（目录可改，子树随之移动；rename 不改
  mtime）；返回 `{path: 新相对路径, mtime_ns}`（文件带 mtime_ns，目录仅
  path）。
- `POST /api/code/tree/delete` `{dir, path}`：文件 → `os.remove`；目录 →
  仅空目录可删 `os.rmdir`，非空 → 400「目录非空，请先清空（或删除其中
  文件）」；不存在 → 400。返回 `{removed: true}`。

端点契约保持与既有 /api/code/* 同风格：`dir` 走 `_require_str`，路径校验
全部前置在盘操作之前；新建/改名/删除成功后前端自行刷新树。

### 2. 树 UI（fx/code-tree-ops.js 纯件 + ui/code-tree-ops.js）

- 树面板头部（`#code-tree` 顶）新增「新建文件」「新建文件夹」两个小按钮
  （.code-pane-action 区域，复用文件选择按钮左侧）；每行 hover 出 ✎/🗑
  图标按钮（文件与目录行都有；移到行上显示，移出隐藏——CSS hover）。
- 输入模态：复用 `confirmModal` 的 extra 输入框（`[data-confirm-value]`，
  confirm.js 既有支持）：标题「新建文件 / 新建文件夹 / 重命名」，默认值 =
  新建空 / 当前名称；校验失败 → 模态内错误提示（复用既有错误文案机制，
  无则 toast 中文后不关模态——以 confirmModal 返回值为准，实现时若无法
  阻止关闭则改为「校验先于弹窗：非法名直接 toast」两段式）。
- 删除确认：confirmModal 两键「删除 / 取消」，文案含路径（中文）；
  非空目录删除 → toast 后端 400 中文。
- **tab 联动**（纯件可测）：
  - 成功后 `openCodeViewer(dir)` 重载树（保持现有点击/展开状态不额外处理）；
  - 新建文件 → 自动打开该文件 tab（走既有 openEditorFile 流程：GET
    /api/code/file 取空内容 + mtime 基准，进入可编辑态）；
  - 重命名 → 对已打开 tab 做路径前缀映射（`path` 更新为新路径；tab 标签 /
    活动路径同步；脏状态与 mtime 基准不变——内容没变，磁盘也没变）；目录
    改名同理作用于其下所有已打开 tab；
  - 删除 → 关闭受影响 tab（若该 tab 脏 → **先两键提示**「有未保存修改：
    保存全部并继续 / 取消」，取消则中止删除；确认 → saveAllDirtyTabs 后
    删——与 code-write-guard 同思路，但树操作不受「生成上下文」限制，
    凡受影响 tab 有脏即提示）；
  - main.c 特例：重命名/删除涉及生成上下文的 main.c 时，完成后调
    `refreshMainCDiskState()`（既有导出）同步步骤 8 磁盘状态行。
- **保存全部**（工单 03）：状态栏（#code-statusbar）「保存全部」按钮 +
  全局 Ctrl+Shift+S；复用 `saveAllDirtyTabs`；无脏 → toast「没有未保存的
  修改」；「关闭全部」不做（样式按钮不出现，避免歧义）。

### 3. 纯件（fx/code-tree-ops.js）

- `treeNameValidate(name)`：非空、非纯空白、长度 ≤ 120、不含
  `/ \ : * ? " < > |`、不为 `.` / `..` → 返回 `{ok, msg}`（msg 中文）。
- `treeAffectedPaths(path, op)`：返回受影响的旧路径集合（op ∈
  rename/delete）：文件 → {path}；目录 → {path} ∪ {path + "/" + 任意
  子路径}（前缀匹配）。
- `treeRenamedPath(path, oldPath, newPath)`：path 以 oldPath 为目录前缀 →
  替换前缀返回新路径；否则返回原 path。
- `treeOpConfirmTitle/message`：树操作确认文案（删除/重命名/新建含
  名称回显）。
- `treeTabOpenPaths(tabs)`：从 tabs 提取打开文件的路径（tab 含 path 字段
  时）——与 codeeditor tabs 结构对齐，供联动判定。

## 用户故事

1. 作为学生，我生成工程后在代码栏树里点「新建文件」，输入 `sensor.c`，
   代码栏立即打开新 tab 可编辑，Ctrl+S 保存后工程里就有这个文件。
2. 作为学生，我把 `main.c` 点 ✎ 改成 `app.c`，树与已打开 tab 同步改名，
   不用去磁盘管理器。
3. 作为学生，我点 🗑 删掉不要的 `old.c`（或清空后的 `old/` 目录），树
   刷新、打开的 tab 被关闭；若我有未保存修改，会先被提示保存。
4. 作为改了很多文件的学生，我点状态栏「保存全部」（或 Ctrl+Shift+S），
   所有脏标签一次落盘，冲突照常弹 409 模态。

## 实现决策

- 后端三端点集中在 codeview.py（与 read/save 同文件同安全单源），不新增
  errors 表项（400 中文 CodeViewError 既有；无 409 语义）。
- create 用「mkdirs + 空文件写」而非仅 touch——父目录可一次建出（前端只
  要展示新建位置）；不覆盖已存在（400）防误操作。
- 重命名目标 = 父目录 + new_name，天然限制在 root 内（_resolve_in_root
  二次确认）；不允许跨目录移动（new_name 单段）。
- 树操作失败（权限 / 占用 / 不存在）→ 400 中文 toast；成功后前端重载树
  （简单可靠，不做原地 DOM 补丁）。
- tab 联动做**路径映射**而非关掉重开：内容/mtime/脏状态都保真；仅删除
  关 tab。
- 删除/重命名前脏保护与 code-write-guard 语义区分：树操作只在**受影响
  tab 有脏**时提示（不是全部脏标签），且不要求目录 = 生成上下文。
- 保存全部使用既有 saveAllDirtyTabs 单源，不新写保存循环；无脏 toast 中文
  反馈（避免「点了没反应」）。

## 测试决策

- node：`tests/js/code-tree-ops.test.mjs`（treeNameValidate 边界：空/
  空白/超长/非法字符/`.`/`..`/合法中文名；treeAffectedPaths 文件与目录
  前缀；treeRenamedPath 前缀替换与非命中原样；treeOpConfirm 文案含名称
  回显）；fx-guard 登记 code-tree-ops.js。
- pytest：`tests/test_webapp.py` 扩展——create 文件（新/已存在 400/嵌套
  路径/越界路径 400）、create 目录（新/已存在 400）、rename（成功+目标
  存在 400+源不存在 400+非法名 400+目录改名）、delete（文件/空目录/非空
  目录 400/不存在 400/越界 400）。
- CDP 冒烟：`.scratch/code-tree-ops/smoke.mjs`——真实 API + 真实磁盘样本
  （.scratch/code-tree-ops/sample-proj，git 忽略，结束后清理）：
  新建文件 → 树出现 + 自动打开 tab + 输入 + 保存落盘；新建文件夹 → 树
  出现；重命名文件 → 树新名 + tab 路径更新；重命名目录 → 子树 tab 路径
  更新；删除文件 → 树消失 + tab 关闭；删除空目录 → 树消失；非空目录删除
  → toast 400；脏文件删除 → 弹两键确认；Ctrl+Shift+S → 全脏落盘 + 计数。
- 回归：node 全量 + pytest 全量；提交/工单/CHANGELOG 中文。

## 范围外

- 拖拽移动 / 复制 / 剪贴板操作（仅按拍板做最小增删改）。
- 跨目录移动文件（rename 只改单段名，移动=删除+新建，用户自行）。
- 「关闭全部」标签（拍板不做；Ctrl+K 等 IDE 快捷键不跟）。
- 树节点上下文菜单（右键菜单）——只用 hover 图标＋头部按钮，保持与
  既有 UI 风格一致。
- 大文件 / 二进制新文件（新建一律空文本 UTF-8；后续保存走既有守卫）。

## 补充说明

- 新建/重命名/删除成功后不写 git（生成工程目录非库目录，无版本语义）。
- 目录重命名影响生成上下文时（output_dir 下结构变化），步骤 8 的
  main.c 磁盘状态行依赖 refreshMainCDiskState 的差异检测——本期只对
  main.c 做联动，其余路径变化由用户操作与任务流程自然覆盖。
