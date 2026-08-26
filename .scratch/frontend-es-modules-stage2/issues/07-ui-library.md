# 07 — 模块库 tab：static/js/ui/library.js

**要做什么：** 模块库 tab 全部 DOM 胶水迁入 `static/js/ui/library.js`（chips/stats/表格/过滤器/工具栏/加载/描述编辑/模块编辑弹窗/删除/新建载荷）；`state.modules` 属性写点随簇。**被谁阻塞：** 02（app.js）+ 06（files.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 区段 = 5704-6197：renderLibraryChips 5704 / renderLibraryStats 5719 / renderLibraryTable 5725 / clearLibraryFilter 5753 / initAddSections 5761 / initLibraryToolbar 5772 / loadLibrary 5795（`state.modules = ...` @5800）/ editDescription 5813 / editModule 5876（`state.modules` 写 @5850）/ deleteModule 6053（@5960）/ newModulePayload 6132（组合 collectFiles——import 自 files.js + 表单项）。
- 模块库纯件已迁 fx/module.js（28 函数：moduleRowHTML / libChipRowHTML / moduleGridHTML / libStats 等）——胶水经 import 调用；esc 自 fx/core.js。
- 文件件 addFileRow/collectFiles 等本簇用点（editModule / newModulePayload）——import 自 ui/files.js（工单 06 已迁）。
- markup：tab-library @1707-1785；#library-root / #add-sections / 工具栏 / 表格 / 编辑弹窗 id 全不动。
- host 页签分发器 import loadLibrary；清单尾部 init* 含 initLibraryToolbar / initAddSections（host import 调用）。

## 检查表

- [ ] 新建 `static/js/ui/library.js`：上述 12 函数逐字搬移 + import（app.js / fx/module.js / fx/core.js / ui/files.js）+ export（loadLibrary / initLibraryToolbar / initAddSections / editModule / deleteModule 等）+ 头部注释（含状态写点说明：state.modules 属性写）
- [ ] index.html：CRLF 感知行区间删除（5704-6197 内 12 名 + 区段注释；**物理升序**；files 件 6062-6131 已由 06 搬出，本票区间避开）+ 顶部 import 行追加（主体中 files.js 代理 import 名若不再被胶水使用，删代理）
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 模块库 tab 实况探针（loadLibrary 后行数 > 0 + 编辑弹窗渲染）
- [ ] grep 零残留：index.html 无 `function loadLibrary(` 等 12 名定义
- [ ] 中文提交

## 风险点

- editModule（5876-6052，近 180 行大函数）含绑定收集与新模块载荷组装——若引用主体顶层常量（如平台选项表），grep 后随迁或补 import。
- group-cards 相关测试（推荐区接线断言）不属于本簇，不重指向。
