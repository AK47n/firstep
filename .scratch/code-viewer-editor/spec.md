# 代码查看器 → 代码编辑器（多文件标签 + 直接写盘保存 + 冲突检测）

> 会话/系列 slug：code-viewer-editor。立项 2026-08-30（用户：「调整现在的只读
> 代码查看器为编辑器，具体样例可参照 ccs」——CCS = TI Code Composer Studio，
> Theia/VS Code 系 IDE，参照截图 `.scratch/ccs-ref/ccs-window.png`：多文件
> 标签条 / 标签脏点 / Explorer 树 / 底部面板）。用户拍板（澄清轮，全部选
> 推荐项）：①保存 = 直接写回磁盘（新增保存端点，Ctrl+S/按钮 + 脏点）；
> ②做多文件标签页（对齐 CCS：多文件并行、tab 可关闭、脏点）；③文件树
> 新建/重命名/删除本轮不做；④生成页步骤 8 的 main.c 编辑框保留，双入口
> 共存；⑤保存时磁盘被外部改动 → 检测并提示差异（覆盖/放弃/回载）；
> ⑥可编辑文件 = 所有文本文件（二进制 />1MB 拒绝面与现有查看器不变）。

## 问题陈述

「代码」tab 目前是 IDE 观感的**只读**查看器（工单 code-viewer 系列演进 7 轮：
文件树 + 行号高亮 + 大纲 + 搜索 + 缩放 + 树调宽 + IDE 一体化外观）。学生想
改代码（补一句注释、调一个参数、微调日志）仍有两个出口：回生成页步骤 8
只改 main.c，或打开 CCS/Keil 改任意文件。工具已内聚编译/烧录/修复/深化，
唯独「改代码」这一环还留在 IDE——与「淡化 IDE」的产品立场不一致。参照
CCS 的编辑器体验（多标签、脏点、Ctrl+S 直接落盘），把查看器升级为
**可编辑、可保存、多文件标签**的代码编辑器。

## 方案

「代码」tab 中栏从「单文件只读视图（pre + 行号栏）」升级为 **CCS 式编辑器**：

- **顶栏标签条**：多文件标签（语言徽标 + 文件名 + 脏点 ● + 关闭 ×），
  活动标签高亮（沿用现有 .code-file-tab 观感升级为接线 tab 条）；每个
  tab 保留自己的编辑内容 / 脏状态 / .md 两态；打开已开文件 = 激活既有
  tab（不重载）；上限 10 个，超出 toast 中文提示。
- **编辑层**：textarea 三明治（透明 textarea + 语法高亮层 + 行号列，
  三向滚动同步——生成页 main.c `.code-wrap` 同机制，单源 CSS 变量
  `--code-zoom` 缩放沿用）；Tab = 插入 4 空格（多行选择 = 整段缩进）、
  Enter = 自动缩进（拷贝前导空白）；光标行 = 当前行高亮（gutter 淡色 +
  左侧 accent，沿用现有 active 语义）；Ctrl/Cmd+滚轮缩放不变。
- **保存**：Ctrl/Cmd+S 与顶栏「保存」按钮（仅脏 tab 可见/可用）→
  `POST /api/code/save` 直接写回磁盘（UTF-8、\n 换行、原子写：临时文件 +
  os.replace）；成功后 toast、大纲刷新（服务端重算返回）、树节点大小
  更新、脏点清除；保存失败中文 toast（400/网络）。
- **冲突检测**：`GET /api/code/file` 载荷新增 `mtime_ns`（st_mtime_ns）；
  保存请求带 `base_mtime_ns`，与磁盘不一致 → 409 中文（带磁盘现状）；
  前端弹「保存冲突」模态：展示磁盘版与编辑版各前 10 行（等宽 pre），
  三个动作：**覆盖写盘** / **放弃我的修改并重载磁盘** / **取消**。
- **只读边界**：非 UTF-8 文件（严格解码失败）→ 仍可按现状只读显示
  （errors=replace），但 tab 标「只读（非 UTF-8）」、无脏点、禁止保存
  （保存尝试 → 中文 toast 说明）；二进制 / >1MB 拒绝面不变。
- **.md 两态**：默认渲染预览不变；预览态新增「编辑源码」按钮 → 切入
  编辑态（可编辑可保存）；大纲点击 / 搜索命中跳 .md = 自动切编辑态并
  跳行（取代原「只读临时源码态」语义）；「返回预览」保留。
- **跳行**：大纲 / 搜索命中 / 文件内查找点击 = 在 textarea
  setSelectionRange（复用 fx/code.js maincLineOffsetRange 纯函数；
  scroll-to-selection 抽通用版——现有 maincScrollToRange 硬编码
  #main-c-hl，编辑器版参数化传递高亮层元素）。
- **入口文案**：tab 按钮 title、「代码查看器（只读）」→「代码编辑器」、
  中栏空态措辞随能力更新；「文件」树 / 大纲 / 搜索 / 树调宽 / 缩放全部
  保留不动。
- **main.c 联动**：保存 main.c 且当前目录 = 生成上下文 → 调既有
  `refreshMainCDiskState()`（generate-mainc-sync 已 export）刷新步骤 8
  状态行（差异提示立即可见）；「去生成页编辑 main.c」桥保留（双入口）。

## 用户故事

1. 作为学生，我想要在「代码」tab 里直接修改文件内容并 Ctrl+S 保存到磁盘，
   以便改代码不再需要打开 CCS/Keil。
2. 作为学生，我想要多文件标签页（同时打开多个文件、切换保留编辑内容、
   tab 可关闭），以便像 CCS 一样对照着改多个文件。
3. 作为学生，我想要未保存的修改在标签上显示脏点、关闭脏 tab 时有确认，
   以便不会误丢修改。
4. 作为学生，我想要保存时若磁盘文件已被别的途径修改（任务/深化写盘、
   外部 IDE 修改）获得中文提示与「覆盖/放弃/取消」选择，以便不静默冲掉
   别人的工作。
5. 作为学生，我想要 Tab 缩进 4 空格、Enter 自动缩进、光标行高亮、行号与
   语法高亮持续正确，以便编辑手感接近 IDE。
6. 作为学生，我想要非 UTF-8 / 二进制 / 超大文件的只读与中文说明保持现状，
   以便不会保存后损坏文件。
7. 作为学生，我想要大纲/搜索结果点击在编辑器里选中并定位到对应行（含
   .md 自动切编辑态），以便看完结构直接动手改。
8. 作为学生，我想要保存 main.c 后生成页步骤 8 的状态行提示跟着刷新，
   以便两处入口看到同一个磁盘事实。
9. 作为学生，我想要保存后树里文件大小、大纲清单与新内容一致，
   以便视图不自欺。

## 实现决策

### 后端（codeview.py 扩展 + webapp.py 一个端点）

- `read_code_file` 返回增加两个字段：`mtime_ns`（`candidate.stat().st_mtime_ns`）
  与 `utf8`（`data.decode("utf-8", errors="strict")` 成功与否——二进制已在
  前拒绝，此处只判非 UTF-8 文本）；现有字段与拒绝面逐字节不变。
- 新错误类 `CodeViewConflictError(CodeViewError)`：errors.py 登记
  `_ErrorEntry((CodeViewConflictError,), 409, str)`（照 GenerationBusyError
  409 先例；CodeViewError 400 表项不动）。
- 新 `save_code_file(root, rel_path, content, base_mtime_ns) -> dict`：
  安全判定复用 `_resolve_in_root` 单源（路径 / resolve 在根内 / is_file——
  文件不存在 400「文件不存在」；不新建文件）；`len(content.encode("utf-8")) > `
  `CODE_FILE_MAX_BYTES` → 400 超限；`is_unsafe` 已有；**冲突**：磁盘现行
  `st_mtime_ns != base_mtime_ns` → 409（message 中文，带中文释义——
  「磁盘上的文件已被外部修改，请选择覆盖/放弃」）；一致 → 原子写
  （`tmp = candidate.with_suffix(candidate.suffix + ".tmp-pid")` →
  `write_text(content, encoding="utf-8", newline="\n")` → `os.replace`），
  失败 OSError 由既有 400 os_error_message 表项接住。返回
  `{path, size_bytes, mtime_ns, outline}`（outline 服务端重算，前端省一次
  GET）；`.c/.h` 才给 outline（沿用 `_outline_for`）。
- `POST /api/code/save`：`{dir, path, content, base_mtime_ns}`；content
  非字符串 / 缺 base_mtime_ns → 400 中文（`_require_str` 既有风格）；
  路由只转调域函数（照 /api/code/open|file 惯例）。
- `GET /api/code/file` 载荷新增字段（前述）；**读面其余不破**。

### 前端（新建 fx/codeeditor.js 与 ui/codeeditor.js；ui/codeview.js 改造）

- 新 `fx/codeeditor.js`（纯函数，约定同 fx/core.js 头部；末尾
  Object.assign(window, …)）：
  - `codeTabStripHTML(tabs, activePath)`：标签条（badge + 名 + 脏点 ● +
    ×；`data-tab-path` 交事件层；关闭按钮 `data-tab-close`；只读 tab 加
    .ro 标记与 title）。
  - `codeEditorHTML(content, lang, opts)`：textarea 三明治（行号列 + 高亮
    层 + 透明 textarea；高亮走 highlightText 单源；`opts.readonly` →
    textarea readonly + 提示条；md 编辑态复用）。
  - `codeDirtyEditorState`/纯函数 `tabDirty(tab)`、`caretLineOf(value, pos)`
    （1 基光标行——数 value 前 pos 个字符的换行数）、`indentLines(value,
    sel)` / `indentOnEnter(value, sel)`（Tab 4 空格整段缩进 / Enter 前导
    空白拷贝）、`conflictHTML(diskText, editText)`（双列各前 10 行 pre）。
  - 跳行：`editorLineRange(text, line)` 委托 fx/code.js `maincLineOffsetRange`
    单源（不复制实现）。
- 新 `ui/codeeditor.js`（DOM 胶水，编辑态所有权：tab 数组 / 活动 tab /
  脏状态 / 保存 / 冲突模态）：
  - `openEditorFile(path)` 由 ui/codeview.js 树点击委托调用（替代
    openCodeFile 的单文件渲染路径）；`initCodeEditor()` 绑定 tab 条点击
    委托（激活/关闭）、textarea input/scroll/keydown（Tab/Enter/光标行/
    三向滚动同步）、Ctrl+S 全局监听（仅 tab-code 活动）、保存按钮、
    冲突模态按钮。
  - 每个 tab state：`{path, lang, content, savedContent, outline,
    mtime_ns, utf8, mdMode(预览/编辑), scrollTop?}`；脏 = content !==
    savedContent；关闭脏 tab → 冲突式确认模态（放弃/取消）
    或复用保存冲突模态（含「保存并关闭」——以冲突模态三按钮 + 保存为
    第一项更省实现，实现期二选一，验收以「不误丢修改」为准）。
  - 保存成功：toast('ok','已保存 …')、大纲/树大小刷新、脏点清除、
    `isMainCPath(path) && codeDir === getMainCDiskDir()` →
    `refreshMainCDiskState()`。
  - 冲突 409（apiGet 风格错误对象带 status）：弹 conflictHTML 模态。
  - .md：预览态顶端「编辑源码」→ 该 tab mdMode=编辑 + 高亮层；「返回
    预览」保留。
- `ui/codeview.js` 改造：中栏渲染移交（openCodeFile → openEditorFile +
  tab 激活）；大纲/搜索/文件内查找跳行改调编辑器选区跳转；「只读」相关
  文案更新；其余（树/侧栏/调宽/缩放）不动。
- index.html：`#code-current-path` 位改 tab 条容器（`.code-tabs` +
  活动区 `#code-viewer` 同容器）；「保存」按钮 / 「编辑源码」按钮；
  h2 与 nav title 文案；空态文案。
- CSS（index.html 单源）：`.code-tabs`（横向滚动条式 tab 条 + 脏点 +
  关闭 ×）、textarea 三明治（沿 .code-wrap 三明治机制，gutter 与高亮层
  font 同源 `calc(13px * var(--code-zoom,1))`）、冲突模态。

### 不变式

- 零新依赖；不引第三方编辑器（Monaco/CodeMirror 均不入——textarea 三明治
  已满足行号/高亮/缩放/跳行，与主编辑器单源机制同族）。
- 读面拒绝面（路径安全单源 is_unsafe_path / 二进制 / 1MB）与搜索上限
  全不变；保存是唯一新写面，路径安全走同一 `_resolve_in_root`。
- main.c 步骤 8 编辑器零改动（双入口共存）。

## 测试决策

- 后端主 seam = pytest（tests/test_codeview.py 追加）：
  - save 正常：写盘 roundtrip（含 \n 归一）、返回 {path,size_bytes,
    mtime_ns,outline}、outline 仅 .c/.h；
  - save 拒绝面：路径穿越 / 不存在文件 / 超 1MB / 非 UTF-8（read 侧
    utf8 标志）→ 400 中文；
  - 冲突：base_mtime_ns 与磁盘不符 → 409 + message 中文；
  - read 载荷新增 mtime_ns / utf8 字段断言；既有用例不破。
- 前端主 seam = tests/js node:test：新增 codeeditor.test.mjs（tab 条
  HTML 脏点/只读标记、caretLineOf、indentLines/indentOnEnter、conflictHTML
  双列、editorLineRange 越界）；
  既有 codeview.test.mjs / highlight.test.mjs 不破。
- 交互层 = CDP 冒烟（.scratch/code-viewer-editor/smoke.mjs）：开样本目录 →
  点文件 → 编辑 → Ctrl+S → 服务端断言文件内容已变 + 页面 toast/脏点清除 →
  冲突注入（改磁盘 mtime/内容后保存 → 模态出现 → 「重新加载」路径）→
  多 tab 开关与脏点 → .md 编辑态 → main.c 保存后步骤 8 状态行刷新。
- 全量回归：pytest 全量 + tests/js 全量保持绿。

## 范围外

- 文件树新建 / 重命名 / 删除（用户拍板本轮不做，后续另立）。
- 撤销重做自实现（textarea 原生 Ctrl+Z 够用）；多级撤销栈不做。
- 查找替换（Ctrl+H）、正则搜索、跨文件替换。
- 代码折叠 / 括号配对 / 自动补全 / 智能提示（语义功能）。
- 文件对比合并三向 diff（冲突模态的「对比」仅并排展示前 10 行，不做
  合并器）。
- 底部面板（Problems/Output，CCS 四板）不引入——编译输出在生成页已有。
- 自动保存 / 定时保存 / 保存全部（Ctrl+Shift+S）。
- 修改外部 IDE 打开文件的自动感知轮询（保存时检测即可，见冲突）。

## 补充说明

- **实现期偏差（比 spec 更简化/更严格，理由=契约正确性，工单 01 评审记录）**：
  ① `mtime_ns` 以**字符串**传输（st_mtime_ns ≈1.7e18 超 JS
  Number.MAX_SAFE_INTEGER ≈9e15，JSON number 往返丢精度——读取与保存响应
  均字符串，保存端点接受 int 或数字字符串，前端原样回传）；②
  `CodeViewConflictError` **保留 CodeViewError 继承**，但 409 表项登记在
  errors.py 400 大元组**之前**（error_entry 按序 isinstance 匹配，排后会被
  CodeViewError 的 400 表项先吞——顺序即语义，注释说明在登记处）；③ 后端
  追加**非 UTF-8 原文件保存拒绝**（400 中文——前端 utf8 标志的后端兜底，
  errors=replace 已丢码点，UTF-8 覆盖 = 静默损坏）；④ content 参数不走
  `_require_str`（其返回 `value.strip()` 会吞代码首尾空白/空行——webapp
  内联 isinstance 类型闸，空串合法）；⑤ 保存检查顺序：路径/存在 →
  UTF-8 守卫 → 超限 → 冲突（超限先于冲突，spec 原序）；⑥ 临时文件名用
  `with_name(name + ".tmp-pid")`（与 with_suffix 在有扩展名文件上等价，
  点文件/无后缀更稳）。
- **实现期偏差（工单 02 评审记录，路线差异写明理由）**：⑦ 编辑器架构不走
  main.c 软换行三明治（pre-wrap + 三向滚动同步），改「无换行（white-space:
  pre）+ `.code-edit` width:max-content（pre.code-hl 静态流内自带量宽量高）
  + textarea absolute inset:0 同盒覆盖 + 容器 .code-view 滚动」——理由：
  软换行会破坏逐行 1:1 行号对齐（main.c 行号列对折行漂移），无换行 +
  逐行 span（.code-hl-line / .code-gutter-line 同 data-code-line 键）保留
  跳行/当前行/flash 全部既有语义，且零滚动同步；⑧ 跳行 = 行元素
  scrollIntoView + editorLineRange（fx 委托 maincLineOffsetRange 单源）
  setSelectionRange——等价但不参数化 maincScrollToRange（无换行下逐行元素
  定位即精确，无需 highlighter 探针量测）；⑨ 每 input 全量重高亮 + 行号
  重绘（与 main.c syncMainCHighlight 同口径；128KB–1MB 文件有卡顿风险，
  主编辑器先例接受）；⑩ IME 组合输入（compositionstart/end）期间不重置
  选区（防中文候选窗打断）；⑪ Ctrl+S 拦截占位 + toast（保存链路 = 工单
  03）；⑫ `.md` 源码态在 t02 仍只读（codeViewHTML），「编辑源码」可编辑
  = 工单 05；⑬ fx-guard 护栏表移除孤儿 codeFileTabHTML（重构后唯一调用点
  消失）、注册新 codeeditor.js 域；⑭ 只读 tab 有可见「只读」小标
  （.code-tab-ro）+ 编辑器右上 .code-ro-note 浮标（非 UTF-8）。
- **.md 三入口跳转行为（工单 05 评审记录，与工单文字差别的显式记录）**：
  大纲点击 = 预览内块级跳转（data-md-line 滚动，不切编辑态——文档导航
  无需行号）；搜索命中 / 文件内查找命中 / Ctrl+F = 自动切编辑态并选中跳行
  （行语义需要行号；未开过的 .md 经搜索命中以 mode="edit" 初始化，不再落
  预览态）。
- 非 UTF-8 只读判定放在读侧新增 `utf8` 字段：严格解码失败 → 前端只读
  标记；UTF-8 但含 BOM 的文件按 UTF-8 正常编辑（BOM 字符保留在内容里，
  保存不剥离——与现状读取口径一致，不新增 BOM 处理）。
- 保存冲突用 mtime_ns 精确比较（同 ns 视为未变：外部工具改回同内容但
  mtime 变 → 判冲突，用户按提示处理，宁提示勿静默覆盖）。
- 保存后大纲刷新 = 服务端在 save 响应里重算返回（比前端再发一次 GET 省
  一次往返；前端不自行重算 clex 逻辑——clex 是后端单源）。
- 编辑态下跳行高亮 = 选区（天然持续高亮，无需 flash 类——保持现有 flash
  视觉仍在，选中即高亮 1.2s 后可保留选区）。
- 「保持现有 code-viewer 只读能力作为回退」：实现期如编辑器异常（如
  非 UTF-8）可回退只读渲染（现有 codeViewHTML 保留，不删除）。
- 所有文案中文；spec / 工单 / 提交信息 / CHANGELOG 遵循仓库语言规范。
