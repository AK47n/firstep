# 08 — 整套代码页视觉统一

**要做什么：** 文件树 / 侧栏 / 底部面板 / 状态栏 / 标签条做一致性整治：字号体系、间距节奏、hover 底色、焦点环、滚动条、分隔线、按钮观感统一，消除「拼装感」。

**被谁阻塞：** 01–07（所有新 UI 元素落地后再统一，避免反复改样式）

**状态：** resolved

**实现笔记：**

- 交付：按钮体系统一（信息条钮/面板头动作/状态栏按钮共享 panel 底 + 1px 边框 + radius-sm + hover accent——评审整改抽公共规则消灭三份逐字节拷贝）；focus-visible 焦点环统一（2px accent outline + 2px offset，覆盖树按钮/侧栏 tab/大纲/搜索/查找/编译错误/标签/状态栏/信息条等可交互元素）；树/侧栏/搜索/查找空态块级化（8px 10px 留白 + 12.5px + 行高 1.6）；状态栏按钮 disabled 态。
- 评审处置：Standards 轴 0 硬违反（css-tokens 守卫 8/8 过）；5 判断项中 3 项整改（按钮公共规则、死选择器 .code-pane-side > .muted → .code-search-results/.code-find-results 直子、.code-statusbar button 两条规则合并 + 注释与 12.5px 先例对齐）；2 项留档（focus-visible 长选择器列表——与既有每控件手写 outline 先例一致；注释措辞）。
- Spec 轴评审于提交时仍在运行（见会话记录；如有补充发现将以整改提交跟进）。
- 测试：node --test 全量绿（含 css-tokens 守卫）；smoke-08.mjs 4/4（焦点环 computed、三处按钮 borderRadius 非 0、字号 12.5/11px、深浅整页验收图 shot-ide-dark.png / shot-ide-light.png）。

- [ ] 字号体系统一：面板标题 11px 大写间距、正文 12–12.5px、代码 13px（可缩放）；无裸字号漂移
- [ ] 间距节奏统一：面板 padding（7px 10px 类）、行内 gap、列表行 padding 一致
- [ ] hover / 激活底色统一：树、大纲、搜索结果、编译错误、面板头按钮共用同一 hover 观感（--panel-2 / --accent-dim）
- [ ] 焦点环统一：可交互元素 focus-visible 一律 outline 2px accent + offset 2px（既有先例）
- [ ] 滚动条统一：树 / 侧栏 / 面板列表 / 编辑器共用细滚动条样式（含暗色）
- [ ] 按钮体系统一：信息条钮 / 面板头动作 / 状态栏钮共用边角（--radius-sm）与 hover（border accent + accent-dim 底）
- [ ] 分隔线统一：面板标题底、标签条底、面板边框全部 1px --border；无多余双线
- [ ] 空态文案与留白统一（树空态 / 侧栏空态 / 编辑器空态 / 面板空态）
- [ ] 图标统一：既有 15px stroke SVG 体系；无 emoji 混入（树操作行 ✎/🗑 为既有例外不扩散）
- [ ] 深浅主题各截全页验收图（shot-ide-light.png / shot-ide-dark.png）
- [ ] 回归：既有 CSS 选择器 / DOM 键不破坏；node --test + pytest 全量绿

**补充：** 本单只调样式与（必要的）类名微调；如发现结构性不一致需新增 wrapper，先与本单评审确认再动手。

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
