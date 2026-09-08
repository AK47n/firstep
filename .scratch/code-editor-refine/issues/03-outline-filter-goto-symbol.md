# 03 — 大纲符号过滤 + Ctrl+Shift+O 唤起定位

**要做什么：** 大纲面板顶部加过滤输入框：对符号条目（函数/宏/include 等，数据来自既有 outline）做大小写不敏感子串匹配，实时过滤列表；Enter 选中/下一个、点击条目跳转行；Ctrl+Shift+O 展开右侧栏、切到大纲页签并聚焦过滤框（无符号时空态提示）。纯前端，不新增后端。

**被谁阻塞：** 02（Ctrl+Shift+O 键位注册依赖 02 的 keydown 骨架与真机验证结论）。

**Type:** task
**Status:** resolved

## Answer

已实现并验证（提交 5fff0eb9，CHANGELOG 自动 1dc2779a）：

- fx/codeview.js 新纯件 symbolFilter(entries, query)：name/kind 大小写不敏感子串匹配；排序键字典序元组 = 函数优先 → 名称命中质量（精确 > 前缀 > 其余）→ 行号升序；空 query 原序副本；window 导出同步；
- ui/codeview.js：大纲面板过滤框（index.html `#code-outline-filter`，样式并入 .code-search-row 组）+ `renderOutline` 读过滤态；当前选中态 outlineSelIdx（输入回 0、↑/↓ 循环移动、Enter 跳选中、点击同步选中并跳行、Esc 清空恢复）；无匹配「无匹配符号」空态；复用 outlineHTML 渲染与既有点击委托；
- Ctrl+Shift+O（02 keydown 骨架加 key==="o"&&shiftKey 分支）：展开侧栏 + setCodeSide("outline") + 聚焦过滤框全选；不沿用 Ctrl+B 输入框豁免（全局拉焦点为有意取舍，注释说明）；
- 双轴审核整改：Spec (a)-1「函数优先」排序补实现、(a)-2「Enter 选中/下一个」补当前选中+上下导航；命名对齐工单 symbolFilter（同时缓解 Standards Mysterious Name）；kind/持久化/ Esc = 良性（kind 超集含 heading、persist 与 Ctrl+B 一致、Esc 惯例平行）；Standards 硬违规 0（归一化重复=既有 fileFindFilter 风格，judgement）；
- 验证：node 单测 27/27（5 组新用例）；全量 1215 pass；CDP 冒烟 smoke-03 12/12（Ctrl+Shift+O 展开/聚焦、函数优先、选中/↑↓/Enter、空态、Esc、点击跳行）。

## 实现要点

- 新 fx 纯件 symbolFilter(entries, query)：子串匹配 + 排序（函数优先、名称前缀优先），node 单测。
- 大纲面板 DOM：过滤输入 + 空态 + 条目；过滤与跳转复用既有 outline 点击/行跳转逻辑。
- Ctrl+Shift+O：复用 02 注册点，行为 = 展开 rail + 激活大纲页签 + 聚焦过滤框并全选文本（类 VSCode 符号搜索）。

## 验收 checklist

- [ ] 过滤输入逐键过滤函数/宏/include 混合列表；无匹配显示空态；清空恢复全列表。
- [ ] Enter 跳转当前选中符号行；点击条目跳转行。
- [ ] Ctrl+Shift+O 展开 + 聚焦过滤框；再次按下不与框内输入冲突。
- [ ] node 单测 symbolFilter（子串/前缀/大小写/空 query/无匹配）；CDP 冒烟 smoke-03。
