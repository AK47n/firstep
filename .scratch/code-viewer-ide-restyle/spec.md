# spec — 代码查看器 IDE 化改版（对照 CCS 观感）

## 问题陈述

用户原话：「现在代码查看器太丑了，你可以自己打开ccs查看类比，搞得好看一点」。
「代码」tab 的只读代码查看器当前是**三张悬浮卡片**（左树 / 中编辑器 / 右侧栏各自
带边框圆角与 10px 缝隙），编辑器行号列底色割裂、当前文件标签像一枚 chip、语法
高亮只有 5 类（关键字/注释/字符串/数字/预处理），对比 Code Composer Studio
（Theia/VS Code 系 IDE 观感）差距明显：IDE 是**一体的编辑面**——面板与编辑器
无缝拼接、tab 条与编辑器连通、行号淡色、当前行整行强调、语法颜色成族。

## 方案

把查看器从「三卡片」改为「一张 IDE 工作台」：保留页面层 .card 外框与工具栏，
其下的三栏改为**无缝拼接**（grid 无 gap、面板去边框圆角、1px 分隔线），左侧
「文件」树与右侧「大纲/搜索」面板共用 --panel 底、编辑器列用更深的 --code-bg
底 + 顶部通讯 tab 条（活动 tab 与编辑器同底色、顶边 accent 线、上下无断缝）；
行号淡色、当前行整行 rgba(accent,.07) + 左侧 2px accent 竖线、行号 accent 加粗；
树与大纲命中行改为「flat 行 + 左 2px accent 竖线 + 淡色底」的活动态，面板标题
改为 section 头（小字、muted、面板-2 底、底部 1px 分隔、sticky）。语法高亮在
现有 5 类基础上补 **函数名**（.tok-fn）与**全大写宏常量**（.tok-const）两类，
`#define NAME …` 行拆分着色（#include/#pragma/条件编译仍整行）。所有颜色走
既有 token 体系（:root 的 --tok-* 族新增两成员，双主题各一套），不写死色值。

对照基准：CCS 20（Theia）运行实况截图已取得——VS Code Dark+ 色彩结构：编辑器
#1E1E1E、侧栏/面板 #252526、tab 条与侧栏同底、活动 tab 与编辑器同底、语法
颜色成族（函数淡黄、宏常量紫、关键字蓝、注释绿、字符串暖橙、数字浅绿）。

## 用户故事

1. 作为参赛学生，我打开「代码」tab 看工程时，想要一眼看出这是 IDE 式工作台
   （而非网页卡片堆叠），以便感觉「这就是 CCS 里打开工程的样子」。
2. 作为参赛学生，我想要当前行有整行高亮 + 行号加亮，以便跳行/大纲点击后
   目光立刻定位。
3. 作为参赛学生，我想要文件树里当前打开的文件有鲜明的活动态，以便确认
   「我现在看的哪个文件」。
4. 作为参赛学生，我想要函数名与全大写宏有独立颜色，以便比现在更易扫读
   TI 风格 C 代码（大量 GPIO_PORT_x / #define 宏）。
5. 作为亮色主题用户，我想要改版后亮暗两套主题都协调（同一结构性改动，
   两套 --tok-* / --panel 自动适配）。

## 实现决策

- **只改 CSS + fx 纯函数 + token 定义，零行为变更**：不动 ui/codeview.js 胶水、
  DOM 结构（唯一例外：允许为 section 头补充少量包装结构，若无必要不改）、
  后端 API。现有冒烟（smoke.mjs 全链路断言）必须原样通过。
- **用户拍板（2026 商量轮）**：编辑器底色用现有 --code-bg（最深 #0a0e14）；
  高亮补函数名 + 宏常量两类；**外层卡片整个去掉**——#tab-code 贴边全屏
  （margin 0、height calc(100vh - header)），.card 去 bg/边框/圆角/内边距，
  工具栏改为页面工具条（padding 10px 16px + 底 1px 分隔）；行号列与编辑器
  同底。其余 tab 页面卡片风不动。
- **布局**：`.code-layout` grid 模板不变（--code-tree-w / 1fr / 300px），gap 10px → 0；
  `.code-pane` 去 border/radius/padding/卡片底，改为 bg: var(--panel)；
  中列 bg: var(--code-bg)（tab 条 bg: var(--panel-2)），左右与中列之间用
  1px var(--border) 分隔线（col 自身 border 或分隔伪元素，实现取 CSS 差异小者）。
- **编辑器**：`.code-view` 去 border/radius，bg: var(--code-bg)；`.code-gutter`
  bg 透明（与编辑器同底）去右分隔线，行号 var(--muted)；✅ 当前行
  `.code-pre-line.active` = rgba(var(--accent-rgb), .07) 整行 + inset 2px 左 accent
  竖线（box-shadow inset），`.code-gutter-line.active` accent 加粗（保留现状增强）。
- **tab 条**：`.code-file-path` 改为 tab 条（bg panel-2、底 1px 分隔、padding
  收紧），`.code-file-tab` 改为「接线 tab」：bg = --code-bg（与编辑器连通）、
  顶边 2px accent、左右 1px border、底无边、radius 6px 6px 0 0、无 margin/
  vertical-align 间距；路径文本右侧 muted 省略显示，「返回预览」按钮保持。
- **树**：`.code-pane-title`（文件）→ section 头；`.code-tree-file button.on` =
  rgba(accent,.10) + inset 2px accent 竖线 + accent 文字；hover 保持 panel-2；
  保留拖拽手柄（位置随 gap 归零微调到分隔线上）。
- **右侧栏**：`.code-side-tabs` 改为 Theia 式视图 tab（无底色按钮行，on =
  下划 2px accent + accent 文字；行底 1px 分隔）；列表行 hover/flat 同树。
- **高亮扩展**（fx/code.js cHighlight，机械法）：标识符非关键字且其后
  （允许空白）紧跟 `(` → .tok-fn；全大写标识符（含 ≥1 下划线，长度 ≥2）
  → .tok-const（宏常量惯例；`#define NAME …` 行改为整行 tok-pre 内 NAME 段
  tok-const 拆分，其余预处理行保持整行 tok-pre）；关键字/注释/字符串/数字
  分支不动。新 class 经 highlightCodeLines 的跨行 stack 机制天然兼容。
- **新 token**（:root 与 light 各一套）：`--tok-fn`（深 #dcdcaa / 亮 #953800）、
  `--tok-const`（深 #c586c0 / 亮 #6639ba）——取 CCS Dark+ 系函数/常量色，
  与现有 --tok-* 族（com/str/num/kw/pre）同一挂载点。

## 测试决策

- 单测（tests/js，node --test 现有先例 code-highlight.test.mjs）：
  - cHighlight 新增用例：函数调用/定义 → tok-fn；关键字 + ( 仍 tok-kw；
    非函数标识符不着 tok-fn；`#define FOO(x)`/全大写 → tok-const；
    `#include` 行仍整行 tok-pre；宏名在注释/字符串内不受影响。
  - 纯函数单测只测外部输出（HTML class 序列），不测实现细节。
- 既有断言兼容性：code-highlight.test.mjs 现有用例（int/return/void 仍 kw、
  #include 整行 tok-pre、GPIO_setConfig 排序）必须原样通过——含
  `assert.doesNotMatch` 的非行首 # 用例。
- CDP 冒烟：.scratch/code-viewer/smoke.mjs 全链路原样通过（DOM 断言均不假定
  卡片样式）；新增视觉验收 = before/after 深色 + 亮色截图存档
  （.scratch/code-viewer-ide-restyle/）。
- 亮/暗两主题各截一张（html[data-theme] 本地存储切换），人工对比验收。

## 范围外

- 不改后端（codeview.py / webapp.py 端点）、不改 ui 胶水行为、不引入编辑器
  组件（monaco/codemirror）、不做多 tab 文件并行打开、不做 minimap、不做
  行内 diff/查找高亮、不改 main.c 编辑框（生成步骤 8，另属主编辑器观感）。
- 不做「编辑器内代码折叠/括号配对」等语义功能。

## 补充说明

- 用户授权自行对照 CCS（已启动并截图取色）；CCS 为本地 C:\ti\ccs2050 安装。
- 仓库惯例：spec/工单/提交信息中文；纯函数 esc 单源；新 class .code-* 前缀；
  不新造颜色值原则本次以「--tok-* 族新增成员」方式落实（族内先例：
  tok-tag/tok-attr/tok-val 即属同一挂载模式）。
