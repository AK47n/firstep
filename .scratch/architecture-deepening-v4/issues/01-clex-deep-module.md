# 01 — 架构深化 v4：clex 深模块——C 词法知识单源化（候选 1，Strong）

**What to build:** 第四轮架构深化（2026-08-08 grilling 共识，候选 1）。C 词法知识散在 skeleton.py 与 generator.py 两处：围栏正则逐字两份（skeleton.py:55 / generator.py:85，generator 注释自认"同一形态"）、两个注释剥离器（`_strip_comments_and_strings` / `_strip_comments_keep_preprocessor`，实现约 90% 相同，唯一差异 = `#` 行透传分支）、include 提取正则（generator.py:88）、顶层 #define 扫描（generator.py:501）。生成器还 import 骨架私有函数（generator.py:34）。新模块 clex.py 成为唯一所有者，两处调用方只走公开字符串接口。

1. **新建 `src/contest_generator/clex.py`**（纯词法层，接口 = 字符串进 / 字符串出，无盘上文件）：
   - `strip_code_fences(code)`——围栏剥离（自 skeleton.py:58 迁入，语义逐字不变，判例 docstring 保留）；
   - `fence_line_indices(code)`——含围栏的行号 + 行文本（供生成门禁 `_check_main_calls` 报行号用，`_FENCE_LINE_RE` 唯一出处收进 clex）；
   - `strip_comments(code, *, keep_preprocessor=False)`——两个剥离器合一：唯一语义轴 = `#` 行是否整行透传（keep_preprocessor=True 时透传——include 文件名在引号里，不能当普通字符串剥掉，判例 pid.c 第 2 行 #include 保留 docstring）；默认行为 = 原 `_strip_comments_and_strings`（字符串照剥）；
   - `extract_quoted_includes(stripped)`——引号 include 头文件名（自 generator.py:88 迁入）；
   - `top_level_defines(code)`——无条件顶层 #define 扫描（自 generator.py:501 迁入，含 #if 深度跟踪 / #undef 排除 / 续行合并 / 函数式宏值文本比较，语义逐字不变）。
2. **skeleton.py 瘦身**：删 `_FENCE_LINE_RE` / `strip_code_fences` / `_strip_comments_and_strings` / `_strip_comments_keep_preprocessor`，改 import clex；调用形态正则（`_DECL_OR_DEF_RE` / `_MACRO_DEF_RE` / `_DEFINE_RE` / `_IDENT_CALL_RE` / `_CONTROL_KEYWORDS`）**刻意留在 skeleton**（"什么算一个函数名"是自检语义判断，非词法）。`_replace_undefined_calls` 的 `_skip_string` / `_at_line_start_after_ws` 留在 skeleton（透传语义属自检改写，非词法切分）。
3. **generator.py 瘦身**：删 `_FENCE_LINE_RE` / `_INCLUDE_QUOTED_RE` / `_top_level_defines`，`_check_main_calls` 围栏检查改用 `fence_line_indices`，注释剥离改 `strip_comments(..., keep_preprocessor=True)`，私有 import `_strip_comments_keep_preprocessor` 删除。
4. **测试迁移**：test_skeleton.py 的 strip_code_fences 用例改从 clex import（公开接口，不再经骨架转发）；`_strip_comments_keep_preprocessor` 用例改 `clex.strip_comments(..., keep_preprocessor=True)`；补 strip_comments 默认行为与 flag 分支的并排用例（两语义轴一份实现）。行为零变化，防漂移断言原样过。

**明确不动的（边界，勿越）**：调用形态正则与骨架自检函数（find_undefined_calls / sanitize_skeleton / build_skeleton_interfaces / verify_main_c）；`_replace_undefined_calls` 的透传辅助；webapp.py / keil.py / ccs.py / llm.py 零改动；错误类型与文案契约逐字不变。

**Status:** resolved

## 验收

- [x] 全量 pytest 绿（783，基线 773，净增 14 个 clex 用例：15 新增 − 5 迁移去重）；错误文案逐字不变（既有断言原样过）
- [x] `grep -rn "_FENCE_LINE_RE\|_strip_comments_and_strings\|_strip_comments_keep_preprocessor\|_INCLUDE_QUOTED_RE\|_top_level_defines" src` 只剩 clex.py 内定义与消费点（无第二份定义）
- [x] `grep -rn "from .skeleton import" src/contest_generator/generator.py` 不再含下划线私有名（只余 `verify_main_c`）
- [x] test_skeleton.py 不再 import 骨架私有名（围栏 / 注释用例全部直导 clex 公开接口）
- [x] mypy 干净（26 文件）——顺带修掉预存的循环变量复用告警（main 上同错，工单 09 引入，纯改名零行为变化）

## Comments

（2026-08-08 立项，grilling 共识：候选 1 clex 深模块。范围 = 纯词法（围栏 / 注释 / include / define），调用形态正则留骨架；两个剥离器合一为 strip_comments(keep_preprocessor=)。顺序：01 → 02（语料遍历，依赖 clex 原语）→ 03（摘要协议，独立）。）

（2026-08-08 实施完成，refactor 提交 + merge PR。要点：

- **clex.py 新模块**：strip_code_fences / fence_line_indices（门禁报行号用，与剥离同源）/ strip_comments(keep_preprocessor=)（两剥离器合一，语义轴 = # 行透传，判例 docstring 保留）/ extract_quoted_includes / top_level_defines（逐字迁入，深度跟踪 / #undef / 续行合并语义零变化）。
- **skeleton.py / generator.py 瘦身**：词法定义与私有 import 全清；generator 的 `_check_main_calls` 围栏检查改用 fence_line_indices（行号 + 已 strip 文本，原 line.strip() 逻辑等价）；`re` import 从 generator 移除。
- **测试迁移**：围栏 4 例 + keep_preprocessor 判例 + include 提取 + top_level_defines 共 15 例入 test_clex.py；test_skeleton 删迁移 5 例（4 围栏 + 1 注释剥离判例）。**过程教训**：第一批编辑误落主检出（Read 用的是主检出路径，worktree 切换后未更新），已还原主检出（git checkout -- tests/test_skeleton.py）并重做——后续编辑一律先确认 cwd 在 worktree。
- **行为零变化**：787 基线用例（773 + 我首批的 14 新增，其中 5 个后来从 test_skeleton 去重）逐字过；mypy 从"1 预存错误"到 26 文件干净。）
