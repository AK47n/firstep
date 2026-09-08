# 06 — 括号配对与自动闭合

**要做什么：** 输入代码时获得 VSCode 式括号体验：自动闭合、右括号跳过、空括号对退格删除、光标在括号上时配对高亮。

**被谁阻塞：** 04（配对高亮复用标记层；自动闭合纯件本身可不依赖，但本单统一实现）

**状态：** resolved

**实现笔记：**

- 交付：自动闭合（无选区插对居中 / 选区包裹——bracketOpen）、右括号跳过与成对选区整对替换（bracketClose）、空括号对一次退格删对（bracketBackspace）、配对高亮（bracketPairAt：一次正向配对表扫描 + 深度匹配 + 跳过字符串/字符/行注释/块注释内假括号，返回两段标记——`kind:"bracket"` 下划线样式）；keydown 分支挂既有 Tab/Enter 链；配对高亮仅 .c/.h 与 xml 且非只读。
- 评审处置：Standards 轴 1 硬项（syncEditorAfterInput 守卫取反——update* 改为只算不渲染后必须无条件重画）已修；判断项：bracketPairAt 前置短路（光标不在括号免全文档扫描）已修，其余（activeEditor 助手、字符串规范化、openChar 防御冗余、重复注释、keydown else-if 链）留档。Spec 轴：plain 语言未门控（keydown 加 lang ∈ c/xml/md 守卫）、只读标签未排除（updateBracketMarks 加 tab.readonly）、IME 组合未保护（新分支加 !e.isComposing && !composing）——三项全部落实。
- 测试：tests/js/code-brackets.test.mjs 11 组；node --test 全量绿（除 07 红灯）；smoke-06.mjs 8/8。

- [ ] 输入 `(` `[` `{` 自动闭合：无选区 → 插入括号对、光标居中；有选区 → 用括号对包裹选区（VSCode 行为）
- [ ] 输入右括号：光标紧邻同款右括号 → 跳过（不重复输入）；选区被 `(`…`)` 等包裹时输入右括号 → 整对替换为新括号对（typing over pair）
- [ ] 退格：光标位于空括号对中间 → 一次退格删除整对
- [ ] 配对高亮：光标紧邻或位于括号上时，配对括号加标记（淡 accent）；无配对不亮
- [ ] 配对扫描跳过字符串 / 字符 / 单行注释 / 块注释内的假括号；嵌套正确；跨行可配对
- [ ] 启用范围：.c/.h 与 xml 编辑态启用全部；.md 编辑源码态仅自动闭合/跳过/退格删对，不启用配对高亮；只读标签不启用任何
- [ ] undo 语义：全部经既有 applyEdit 单路径（textarea 值 + 选区），Ctrl+Z 走浏览器原生
- [ ] 既有 Tab / Enter 缩进、IME 组合输入保护不受影响
- [ ] tests/js：自动闭合（空光标 / 选区包裹 / 嵌套）、右括号跳过、typing over pair、退格删对、配对深度扫描（字符串注释内假括号、跨行、多对嵌套）单测
- [ ] CDP 冒烟：输入 `{` → 出现 `{}` 且光标居中；输入 `)` 跳过；光标在 `(` 上时配对 `)` 有标记 class

**补充：** 全部纯件输入 / 输出（值 + 选区位），胶水只在 keydown 拦对应键调纯件后走 applyEdit；配对高亮标记清单经 04 标记层渲染入口。
