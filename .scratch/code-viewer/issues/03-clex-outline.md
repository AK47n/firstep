# 03 — C 大纲：clex 函数扫描器 + outline 载荷

**要做什么：** 打开 .c/.h 文件时，右侧大纲有东西可显示——函数 / 顶层宏 / include 清单，点击可跳到对应行。端到端：`GET /api/code/file` 对 .c/.h 返回 `outline: [{kind: function|define|include, name, line}]`（line = 1 基源行号）；非 C 文件 outline 保持 null（前端显示「当前文件无大纲」）。

**被谁阻塞：** 01（outline 挂在 file 端点上）。

**状态：** ready-for-agent

- [x] clex.py 增 `top_level_functions(text) -> [{name, line}]`：strip_comments(keep_preprocessor=True) → iter_c_regions 的 code 区域 → 花括号深度 0 处 `ident ( … ) {`（ident 排除 if/for/while/switch/return/sizeof/do/else/goto/break/continue；`(` 后 match_bracket 配平再遇 `{`）；机械法 best-effort，宏体续行 `do {` 假阳性记录进 docstring。
- [x] read_code_file 装配 outline：functions（新扫描器）+ defines（复用 top_level_defines）+ includes（复用 extract_quoted_includes，行号尽力而为——若该函数无行号则 include 条目 name 保底）；仅 .c/.h。
- [x] tests/test_clex.py 增 top_level_functions 用例（返回类型分行/指针/static 多形态；排除关键字；宏续行 do{ 假阳性记录）+ test_codeview.py outline 形状与 C/非 C 分支；全量 pytest 绿。
