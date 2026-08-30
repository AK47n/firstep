# 代码查看器——IDE 式只读工程浏览（文件树 + 行号 + 高亮 + 大纲 + 搜索）

> 会话/系列 slug：code-viewer。立项 2026-08-27（用户截图 Code Composer Studio：
> 左侧工程文件树 / 中间 C 代码编辑器带行号与高亮 / 右侧 minimap——已确认
> 缩略图不做）。用户原话大意：「既然这个工具淡化了 IDE，我们需要的全都能
> 在这里面解决，那应该再加入一个类似 IDE 的代码查看」。实施按竖切工单
> 逐张落地（见 issues/）。

## 问题陈述

工具生成完工程后，学生核对 / 阅读代码有两个选择：打开 CCS / Keil（重工具、
慢、英文界面、还要等索引），或用文件管理器翻目录（没有高亮、没有行号）。
工具本身已「淡化 IDE」——编译 / 烧录 / 修复 / 深化全部内聚在网页里，唯独
「看代码」这一环还留在 IDE：生成后想快速确认「main.c 长什么样」「某个模块
的接口是啥」「syscfg 配了哪些实例」，没有入口。想读生成工程之外的目录
（如套件例程 / 自己写的实验代码）也没有统一视图。

## 方案

新增顶层「代码」标签页，IDE 式三栏只读视图：

- **左栏**：文件树（目录可收起、噪音目录不出现——.git / Debug / Release /
  Listings / Objects 与母版浏览同口径跳过；目录在前、同级码点序）。
- **中栏**：代码视图——行号栏 + 语法高亮（C / XML 复用既有高亮单源；
  无 minimap，用户明确不要）+ 只读（不放编辑框，改代码仍走任务推进 /
  深化或 IDE）。
- **右栏**：侧栏两个切换面板——**大纲**（当前 C 文件的函数 / 顶层宏 /
  include，点击跳行；非 C 文件显示「当前文件无大纲」）与**工程搜索**
  （跨文件子串搜索，结果列表点击跳转文件+行）。
- **入口**：① 代码 tab 顶部「选择文件夹」（服务端原生文件夹对话框，复用
  /api/pick-directory）；② 最近生成记录卡新增「查看代码」按钮，一键打开
  该 output_dir（与「复制路径」并列）。
- 读取限制与母版树文件端点同拒绝面（路径安全 + 二进制拒绝 + 1MB 上限 +
  utf-8 errors=replace），零写侧、零落盘。

## 用户故事

1. 作为学生，我想要打开「代码」标签页并选择一个文件夹（或从最近生成
   记录一键打开上次生成的工程），以便直接在工具里浏览整个工程结构。
2. 作为学生，我想要左侧文件树目录可收起、噪音目录（.git / 编译产物）不
   出现、目录在前排序确定，以便像 IDE 一样快速定位到想看的位置。
3. 作为学生，我想要点树内任意文本文件即在中间打开带行号与语法高亮的
   只读视图，以便读代码时不再需要开 CCS / Keil。
4. 作为学生，我想要 C 文件右侧有大纲面板（函数 / 顶层宏 / include 清单，
   点击跳到对应行），以便快速了解一个文件的结构并跳转。
5. 作为学生，我想要侧栏工程搜索：输入关键词跨文件查找（跳过噪音与二进制
   与大文件），结果按「文件:行号 + 上下文」列出，点击跳转到文件并高亮
   该行，以便改代码前找到所有相关位置。
6. 作为学生，我想要代码视图内 Ctrl+F 文件内搜索（浏览器默认查找框被
   拦截，走面板内搜索），以便在当前文件内快速定位。
7. 作为学生，我想要二进制 / NUL 文件、超大文件（>1MB）给出中文说明而
   不是乱码 / 卡顿，以便视图行为可预期。
8. 作为学生，我想要跨文件搜索在目录很大时也有明确结果上限与中文报错，
   以便不会因一两个病态目录拖垮整个工具。

## 实现决策

### 后端（新域模块 codeview.py，webapp 只转调）

- 新错误类 `CodeViewError` 登记 errors.py（照 MasterError 先例 → 400 中文；
  未登记异常 = 真 bug → 500 不变量不变）。
- `list_code_tree(root: Path) -> list[dict]`：root 必须存在且是目录（否 400）；
  文件清单走 treewalk.iter_project_files（统一噪音跳过、确定性排序）一次
  算好 `{path, size_bytes}` 扁平清单（目录由前端从路径推导）；条目数上限
  `CODE_TREE_MAX_ENTRIES = 5000`（超限 400 中文「目录文件过多」——防病态
  目录拖垮前端渲染）。
- `read_code_file(root, rel_path) -> dict`：路径安全三约束与
  read_master_tree_file 同拒绝面（entry_store.is_unsafe_path 同款——首字符
  `/`、`:`（NTFS ADS）、`\`、任意层级 `..` 与空段；resolve 后必须落在
  root 内兜底；NUL 二进制拒绝；`CODE_FILE_MAX_BYTES = 1024*1024` 超限拒绝；
  读取 utf-8 errors="replace" + 换行归一化 \r\n→\n）。返回 `{path, size_bytes,
  content, language, outline}`；language 由扩展名判定（.c/.h→c、
  .syscfg/.uvprojx/.cproject/.xml→xml、其余 plain）；outline 仅 .c/.h 提供，
  形状 `[{kind: function|define|include, name, line}]`（line = 1 基源行号）。
- `search_code_files(root, q) -> dict`：q 必须非空字符串（空 → 400 中文）；
  扫描 root 下全部文件（iter_project_files 同噪音跳过），逐文件跳过 = 二进制
  （NUL 探测，读 512 字节即可）+ 超过 1MB；匹配 = 大小写不敏感子串（中文
  不受影响）；命中记录 {path, line, text}（text 为命中行裁剪，前后各约 60
  字符、空白压缩）；总数上限 `CODE_SEARCH_MAX_HITS = 200`（到达即停并置
  truncated 标志）。返回 {hits, truncated, files_scanned}。
- API（照既有路由风格，webapp.py 内注册）：
  - `POST /api/code/open` body `{dir}` → 树清单；dir = 最近记录 output_dir
    或 /api/pick-directory 返回值（服务器本地绝对路径，与 /api/masters/import
    同风险面）。
  - `GET /api/code/file?dir=&path=` → 文件内容 + 大纲。
  - `GET /api/code/search?dir=&q=` → 命中列表。

### C 大纲（clex.py 单源扩展，机械法 best-effort）

- clex.py 新增 `top_level_functions(text) -> list[dict]`：先 strip_comments
  （keep_preprocessor=True）→ 走 iter_c_regions 的 code 区域 → 花括号深度 0
  处形如 `ident ( ... ) {` 的模式即函数定义（ident 排除 C 关键字
  if/for/while/switch/return/sizeof/do/else/goto/break/continue；`(` 后
  match_bracket 配平、再遇 `{`）；返回 {name, line}。机械法已知假阳性：
  宏体续行 `do {`（宏展开成 do-while）——best-effort 可接受，不做语义
  校验，注释进 docstring 与工单验收。
- 顶层宏复用 top_level_defines（已存在，无条件顶层 #define，含行号）；
  include 复用 extract_quoted_includes（对 keep_preprocessor=True 后的文本，
  注意：该函数是「quoted include 提取器」——实现期核对它返回的行号语义，
  若不含行号则大纲 include 条目至少给出 name，行号尽力而为；验收以函数/
  宏为准）。
- 大纲只挂 .c/.h；XML（syscfg/uvprojx）不做大纲（范围外）。

### 前端（fx 纯函数下沉，ui 胶水）

- 新 `fx/codeview.js`（纯函数，约定同 fx/core.js 头部；末尾
  Object.assign(window, …) 兼容）：
  - `buildCodeTree(files)` / `codeTreeHTML(nodes)`：扁平清单 → 嵌套节点 →
    原生 details/summary 树（目录在前、同级码点序 —— 与母版树同构；
    不 import fx/master.js，避免「母版」文案与上下文耦合——实现期若签名
    完全一致才考虑复用，否则同构新写）。
  - `codeLineNumbersHTML(count)`：1..n 行号栏 HTML。
  - `codeViewHTML(content, lang)`：行号 + 高亮（fx/highlight.js
    highlightText 单源；整段 token 化再渲染，行号栏独立、`white-space:
    pre` 不换行、同一 font/line-height，保证行对齐）。
  - `outlineHTML(outline)` / `outlineEmptyHTML()`：大纲面板（kind 徽标 /
    name / 行号），非 C 空态文案。
  - `searchListHTML(hits, activeFile)` / `fileFindFilter(lines, q)`：跨文件
    结果列表 + 文件内搜索纯函数（当前文件全文已在内存，客户端过滤）。
- 新 `ui/codeview.js`（DOM 胶水）：
  - `initCodeViewer()`：tab 常驻绑定；「选择文件夹」按钮 → apiPost
    /api/pick-directory（取消 = 静默）→ openCodeViewer(path)；
    tree 点击委托（文件 → apiGet /api/code/file → 渲染 + memo（key =
    dir+path）；目录 → 展开收起原生行为）；侧栏切换（大纲 / 搜索）；
    搜索框提交 → apiGet /api/code/search → 结果列表 → 点击跳文件+行；
    Ctrl+F 拦截（tab 内）→ 文件内搜索面板；跳行 = 行元素
    scrollIntoView + 高亮 flash（data-line 属性，主行号与内容行同 data
    键）；加载三态 + 中文错误 toast。
  - `openCodeViewer(dir)`：公共桥（window 挂载或模块导出），供最近记录
    入口调用。
- 最近记录卡：fx/recent.js 的 recentChipHTML 加「查看代码」小按钮
  （class .code-open-btn，data-dir，stopPropagation——点击不触发整卡复制
  路径行为）；ui/recent.js 点委托加分支 → openCodeViewer(dir)。入口属性
  复用 chip 既有 data-dir。
- index.html：导航 <button data-tab="code">（「代码」，title 一句话）；新
  tab-code 区（左树容器 + 中视图容器 + 右侧栏容器 + 顶部工具栏：选择
  文件夹 / 当前目录路径展示 / 侧栏切换）；宿主 module script import
  ui/codeview.js 并 initCodeViewer()。

### 模式变更 / 架构决策

- 新读面「本地任意目录」：与母版树端点同一种「显式根 + 相对路径安全收窄」
  模式（三约束），打开的根只来自最近记录或服务端原生对话框——API 仍以
  包含校验兜底，不放开任意文件系统访问。
- 无新依赖；零写侧；只读端点不落盘；不新建 SSE / 后台任务（同步处理，
  搜索有上限保证）。
- 母版树 = 管理视角（看母版库本身，白名单墙并存）；代码 tab = 工程视角
  （看生成结果 / 任意目录）——两个读面对齐但不互相调用。
- 渲染不做「编辑器」：不用 textarea / contenteditable，直接 pre + 行号栏
  （只读语义 + 行对齐简单可靠；main.c 预览的 textarea 工具轮是另一件事，
  不动）。
- CONTEXT.md 增「代码查看器」词条。

## 测试决策

- 后端主 seam = pytest：新增 tests/test_codeview.py（tmp_path 造树——list
  噪音跳过 / 上限 400 / 不存在目录 400；read 三类 400——穿越 / 二进制 /
  超限 + outline 形状与 C/非 C 分支；search 命中 / 上限 truncated / 二进制
  与大文件跳过 / 空 q 400）；tests/test_clex.py 增 top_level_functions 用例
  （函数定义多形态：返回类型分行 / 指针 / static；排除 if/for/while 等；
  宏续行 do{ 假阳性记录）；tests/test_webapp.py 增 /api/code/open|file|
  search 的 200/400。
- 前端主 seam = tests/js node:test 纯函数单测（extract 范式）：新增
  codeview.test.mjs（buildCodeTree 排序与嵌套 / codeLineNumbersHTML /
  codeViewHTML 行数一致与高亮分发 / outlineHTML / searchListHTML /
  fileFindFilter）；既有 highlight.test.mjs 不破。
- 交互层延续 CDP 冒烟范式（.scratch/code-viewer/smoke.mjs）：打开 tab →
  用临时样本工程目录 → 点树文件加载 → 大纲跳行 → 搜索命中跳转 → 最近卡
  「查看代码」按钮（不真生成）。
- 全量回归：pytest 全量 + tests/js 全量保持绿。

## 范围外

- **编辑 / 保存 / 写回**（只读；改代码走任务推进 / 深化 / IDE）。
- minimap / 右侧缩略图（用户明确不要）。
- 多文件 tab 并行 / 文件对比 / diff；跳转定义引用（深层语义）。
- 二进制 / 图片 / PDF 预览（拒绝面给中文说明即可）。
- 搜索替换 / 正则 / 跨文件全文索引（子串扫描 + 上限已够）。
- 大纲只覆盖 .c/.h 函数 / 宏 / include；XML / 其它语言大纲。
- 文件名过滤 / 树内搜索 / 收藏。
- IDE 深色主题专项（跟随既有 CSS token，不做单独主题系统）。

## 补充说明

- 生成工程编译后会出现 Debug/ 等构建产物目录——树噪音跳过使视图聚焦源码，
  产物文件不可见（与母版浏览同口径，可接受）。
- 大纲机械法 best-effort：宏体续行 do{ 之类假阳性已知并记录，不做语义
  校验（无 clang 依赖）。
- 行号对齐用「同一容器内 gutter + pre、同一 font/line-height、white-space:
  pre 不换行」实现；超宽行整容器横向滚动，gutter sticky 左（实现期验证，
  不行则退化为整体一起滚——对齐仍保序）。
- **实现期偏差（比 spec 更简化/更严格，理由=单源）**：① /api/code/file 载荷
  不含 `language` 字段——前端用既有 fx/highlight.js 的 languageOf(path) 单源
  判定渲染语言，后端不重复映射（大纲所需 .c/.h 判定留在后端自有
  _is_c_source）；② include 大纲条目行号做成了精确值（clex 新
  quoted_include_lines 直走 iter_c_regions 预处理行区域取 1 基行号，比
  「name 保底」更强，且注释行伪装 include 不误收）；③ 宏续行假阳性未复现
  （top_level_functions 按「前一行为反斜杠结尾」整行跳过宏续行，防范于前）；
  「查看代码」入口按钮最终 class 为 .recent-code-open（spec 拟名
  .code-open-btn，实现期随 chip 既有命名约定）。
- 所有文案中文；spec / 工单 / 提交信息 / CHANGELOG 遵循仓库语言规范。
