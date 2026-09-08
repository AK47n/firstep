# 09 — Ctrl+P 快速打开

**要做什么：** 代码 tab 内 Ctrl+P 弹快速打开 overlay：输入文件名/路径子串实时匹配当前工程树清单（/api/code/open 返回的扁平清单，前端缓存），匹配规则 = basename 子串（大小写不敏感）优先 → 路径子串 → 字符序模糊；上下键选择、Enter 打开（复用既有打开语义与 tab 上限/只读/md 两态）、Esc/点击空白关闭；无匹配空态；已打开文件 → 激活既有 tab。

**被谁阻塞：** 无。

**Type:** task
**Status:** resolved

## 实现要点

- 新 fx 纯件 quickOpenMatch(files, query) → 排序结果（截断 50 条），node 单测（basename/路径子串/模糊/大小写/空 query/中文路径）。
- overlay DOM：顶部输入 + 结果列表（文件图标 + 路径 + 命中子串高亮），浮层样式深浅主题一致（复用既有浮层 token）。
- 快捷键注册与 02/03 同管线；打开行为 = 既有 openEditorFile（含 EDITOR_TABS_MAX 上限语义）。

## 实现决策备注（双轴评审后回写，workflow.md step 4）

- **模态并发纪律（Standards hard 整改）**：quick-open 不叠开于 `.ref-files-overlay`（modal 优先）；浮层开启期间 capture 相吞其余 Ctrl 全局快捷键（Ctrl+F/H/W/B/O 不穿透到背后）——与 codeview 既有「模态开启不并发截获」管线对齐。
- **高亮单源（Standards judgment 整改）**：命中高亮下沉 fx `quickOpenHighlightParts(path, rank, idx, query)`（rank0 basename 段 / rank1 路径段切片，模糊与非法 idx 不亮）——UI 只做转义，不再 indexOf 重算；idx 成为真实契约（单测覆盖）。测试补 IDX/大小写/中文子串断言（原「中文」用例实际走模糊分支——已修）。
- **帮助数据单源（Spec (a)2 整改）**：fx/code-shortcuts.js SHORTCUT_GROUPS「视图」组新增 Ctrl+P 条目（03 的 Ctrl+Shift+O 缺失为延续漏项，记录）。
- **文件图标（Spec (a)1 整改）**：结果行补 fileIconHTML 图标（复用树行图标单源）。
- **Ctrl+Shift+P 豁免（Spec (c)1 整改）**：shiftKey 不拦截（预留命令面板语义）。
- **Tab 焦点陷阱 / × 关闭 / 焦点回归（Standards judgment 整改）**：输入框 Tab 保持焦点；框右上 × ；关闭后焦点回归触发位（confirm.js 先例）。
- **codeTabActive 单源（Standards judgment 整改）**：codeview 导出，quick-open 引用（删除本地副本 + 未用 `$` 导入）。
- **已知边缘（Spec (c)2 记录）**：高亮按 idx 长度切片，若路径含 toLowerCase 变长字符（U+0130 İ）会错位——中文/空格/ASCII 无碍，记录。
- **冒烟覆盖（Spec (a)3 记录）**：tab 上限语义与树点击同为 openEditorFile 路径（一致性成立），smoke 未实测上限场景（记录）。

## 验收 checklist

- [x] Ctrl+P 出 overlay；输入 `main` 出 main.c/main.h（样例含主/次命中，单测覆盖双命中层级）；Enter 打开；上下键选择；Esc/点击遮罩/×关闭。
- [x] 文件已开 → 激活既有 tab（smoke 场景 6：tab 数不变 2→2）；超 tab 上限行为与树点击一致（同一 openEditorFile）。
- [x] 无匹配空态；结果截断 50 条（单测 60 条 → 50）；中文/空格路径匹配正常（smoke 场景 7 + 单测）。
- [x] node 单测 quickOpenMatch/quickOpenHighlightParts；CDP 冒烟 smoke-09 12/12（日志存证）。全量单测 pass。
