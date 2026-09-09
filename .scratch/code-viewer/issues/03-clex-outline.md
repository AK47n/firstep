# 03 — C 大纲：clex 函数扫描器 + outline 载荷

**要做什么：** 打开 .c/.h 文件时，右侧大纲有东西可显示——函数 / 顶层宏 / include 清单，点击可跳到对应行。端到端：`GET /api/code/file` 对 .c/.h 返回 `outline: [{kind: function|define|include, name, line}]`（line = 1 基源行号）；非 C 文件 outline 保持 null（前端显示「当前文件无大纲」）。

**被谁阻塞：** 01（outline 挂在 file 端点上）。

**状态：** resolved

- [x] clex.py 增 `top_level_functions(text) -> [{name, line}]`：strip_comments(keep_preprocessor=True) → iter_c_regions 的 code 区域 → 花括号深度 0 处 `ident ( … ) {`（ident 排除 if/for/while/switch/return/sizeof/do/else/goto/break/continue；`(` 后 match_bracket 配平再遇 `{`）；机械法 best-effort，宏体续行 `do {` 假阳性记录进 docstring。
- [x] read_code_file 装配 outline：functions（新扫描器）+ defines（复用 top_level_defines）+ includes（复用 extract_quoted_includes，行号尽力而为——若该函数无行号则 include 条目 name 保底）；仅 .c/.h。
- [x] tests/test_clex.py 增 top_level_functions 用例（返回类型分行/指针/static 多形态；排除关键字；宏续行 do{ 假阳性记录）+ test_codeview.py outline 形状与 C/非 C 分支；全量 pytest 绿。

## Comments

- 2026-09-09 补标 resolved（代码事实盘点）：`src/contest_generator/clex.py` 有
  `top_level_functions`（掩码切分 + 括号深度 0 处 `ident ( … ) {` + 关键字排除 +
  宏续行整行跳过，docstring 记录 best-effort 假阳性）与 `quoted_include_lines`
  （1 基行号）。装配 `src/contest_generator/codeview.py:225 _outline_for`
  （function 来自 top_level_functions、define 来自 top_level_defines、include 来自
  quoted_include_lines，按行号 `sorted` 归并），接入点 `read_code_file` 第 174 行
  `_outline_for(content) if _is_c_source(rel_path) else None`（`_is_c_source` 187-190
  认 .c/.h 大小写宽容）。
  测试：`tests/test_clex.py:319`（name+line）、`:347`（排除关键字/调用/原型）、
  `:366`（跳过注释与字符串）、`:376`（跳过宏续行）、`:390`（typedef 与函数指针）、
  `:276`（5000 函数性能）；`tests/test_codeview.py:171`（outline 三类归并排序）与
  `:192`（非 C 为 null）。
  验收逐条对照：① top_level_functions 形态与排除 ✓ ② read_code_file 装配三类 ✓
  ③ 测试与 pytest 绿 ✓。
