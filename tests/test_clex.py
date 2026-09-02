"""C 词法层：围栏剥离 / 行号检测、注释剥离（# 行透传轴）、include 提取、顶层 #define。

词法层唯一出处（clex.py）——两义剥离器合一后，本文件按 keep_preprocessor
语义轴并排覆盖，防"改一处忘另一处"分叉回归。工单 C 深化新增语句级切分
原语（iter_c_regions / match_bracket / next_significant，skeleton 第二套
词法唯一替代）。
"""

from contest_generator.clex import (
    extract_quoted_includes,
    fence_line_indices,
    iter_c_regions,
    match_bracket,
    next_significant,
    quoted_include_lines,
    strip_all_code_fences,
    strip_code_fences,
    strip_comments,
    top_level_defines,
    top_level_functions,
)


# ---------------------------------------------------------------------------
# strip_code_fences：LLM 围栏输出剥离（判例：围栏落盘 → Keil unrecognized token）
# ---------------------------------------------------------------------------


def test_strip_code_fences_removes_leading_and_trailing_fence():
    raw = "```c\nint main(void) { return 0; }\n```\n"

    assert strip_code_fences(raw) == "int main(void) { return 0; }\n"


def test_strip_code_fences_handles_tilde_fence_and_no_lang():
    raw = "~~~\nint main(void) {}\n~~~"

    assert strip_code_fences(raw) == "int main(void) {}\n"


def test_strip_code_fences_passthrough_without_fences():
    code = "int main(void) { return 0; }\n"

    assert strip_code_fences(code) == code


def test_strip_code_fences_does_not_touch_middle_fence_lines():
    # 围栏在中间 = 不是包裹形态（可能是注释里的示例代码），不剥
    code = "// ```c\nint main(void) {}\n"

    assert strip_code_fences(code) == code


# ---------------------------------------------------------------------------
# fence_line_indices：任意围栏行 + 行号（生成门禁报错用）
# ---------------------------------------------------------------------------


def test_strip_all_code_fences_removes_every_fence_line():
    """全剥：LLM 三重围栏（首尾剥后仍残留）→ 无围栏行（skeleton 出稿兜底）。"""
    code = "```c\n```\nint main(void) { return 0; }\n```\n"

    assert strip_all_code_fences(code) == "int main(void) { return 0; }\n"


def test_fence_line_indices_reports_all_fence_lines():
    code = "```c\nint main(void) {}\n```\n// ~~~\n"

    assert fence_line_indices(code) == [(1, "```c"), (3, "```")]


def test_fence_line_indices_empty_without_fences():
    assert fence_line_indices("int main(void) {}\n") == []


# ---------------------------------------------------------------------------
# strip_comments：keep_preprocessor 语义轴（合一前两个剥离器的并排覆盖）
# ---------------------------------------------------------------------------


def test_strip_comments_default_strips_strings_and_comments():
    code = 'int x = 1; // 注释\n/* 块 */\nchar *s = "// not comment";\n'

    stripped = strip_comments(code)

    assert "// not comment" not in stripped
    assert "int x = 1;" in stripped
    assert "char *s =" in stripped


def test_strip_comments_keep_preprocessor_preserves_include_filename_on_later_lines():
    """判例：pid.c 第 2 行的 #include 文件名曾因行首判断失误被当字符串剥掉。"""
    code = (
        '#include "headfile.h"\n'
        '#include "digit_uart.h"\n'
        '// #include "commented.h"\n'
        'void f(void) {}\n'
    )

    stripped = strip_comments(code, keep_preprocessor=True)

    assert '"digit_uart.h"' in stripped
    assert '"headfile.h"' in stripped
    assert "commented.h" not in stripped  # 注释里的 include 不算数


def test_strip_comments_default_keeps_include_line_but_strips_filename():
    # 默认轴：# 行按普通文本处理，字符串（include 文件名）照剥
    stripped = strip_comments('#include "headfile.h"\nvoid f(void) {}\n')

    assert "#include" in stripped
    assert '"headfile.h"' not in stripped


def test_strip_comments_keep_preprocessor_preserves_later_preprocessor_lines():
    """行首判定只认换行——第 2 行起的 # 行不能误判（判例：include 门禁漏检）。"""
    code = "int x;\n#define FOO 1\nint y;\n"

    stripped = strip_comments(code, keep_preprocessor=True)

    assert "#define FOO 1" in stripped


# ---------------------------------------------------------------------------
# extract_quoted_includes：引号 include 提取（对 keep_preprocessor 剥离后的文本）
# ---------------------------------------------------------------------------


def test_extract_quoted_includes_from_stripped_text():
    stripped = strip_comments(
        '#include "headfile.h"\n#include "digit_uart.h"\nvoid f(void) {}\n',
        keep_preprocessor=True,
    )

    assert extract_quoted_includes(stripped) == ["headfile.h", "digit_uart.h"]


def test_extract_quoted_includes_ignores_commented_include():
    stripped = strip_comments(
        '// #include "commented.h"\n#include "real.h"\n', keep_preprocessor=True
    )

    assert extract_quoted_includes(stripped) == ["real.h"]


# ---------------------------------------------------------------------------
# top_level_defines：无条件顶层 #define（条件块 / #undef / 续行排除）
# ---------------------------------------------------------------------------


def test_top_level_defines_collects_unconditional_defines():
    code = (
        "#ifndef GUARD\n"
        "#define GUARD\n"
        "#endif\n"
        "#define FOO 1\n"
        "int x;\n"
    )

    defines = top_level_defines(code)

    assert defines == {"FOO": ("1", 4)}  # GUARD 在 #ifndef 块内（深度 1）不收


def test_top_level_defines_keeps_first_define_after_undef():
    # #undef 后的重定义跳过（合法覆盖模式不收），首次定义仍保留——原行为
    # 逐字迁移，宏冲突门禁以首次定义为准比对
    code = "#define FOO 1\n#undef FOO\n#define FOO 2\n"

    defines = top_level_defines(code)

    assert defines == {"FOO": ("1", 1)}


def test_top_level_defines_merges_backslash_continuation():
    code = "#define SUM(a, b) \\\n    ((a) + (b))\n"

    defines = top_level_defines(code)

    # 函数式宏：名字取到左括号前，参数表并入值参与文本比较
    assert "SUM" in defines
    assert defines["SUM"] == ("(a, b) ((a) + (b))", 1)


# ---------------------------------------------------------------------------
# iter_c_regions / match_bracket / next_significant（工单 C 深化原语）：
# skeleton 手写第二套词法（_match_paren/_match_brace/_skip_ws_and_comments
# 等约 160 行）的唯一替代，行为逐字迁移
# ---------------------------------------------------------------------------


def _kinds(code: str, **kwargs) -> list[str]:
    return [kind for kind, _, _ in iter_c_regions(code, **kwargs)]


def test_iter_c_regions_splits_comments_strings_and_code():
    code = 'int x; // 行注释\n/* 块注释 */ char *s = "str";\n#define F 1\n'
    regions = [(k, code[s:e]) for k, s, e in iter_c_regions(code)]
    assert regions == [
        ("code", "int x; "),
        ("line_comment", "// 行注释\n"),
        ("block_comment", "/* 块注释 */"),
        ("code", ' char *s = '),
        ("string", '"str"'),
        ("code", ";\n"),
        ("preprocessor", "#define F 1\n"),
    ]


def test_iter_c_regions_string_escapes_and_unterminated_eat_to_end():
    code = 'printf("a\\"b"); // 尾注释不闭合'
    regions = [(k, code[s:e]) for k, s, e in iter_c_regions(code)]
    assert regions == [
        ("code", "printf("),
        ("string", '"a\\"b"'),
        ("code", "); "),
        ("line_comment", "// 尾注释不闭合"),
    ]
    # 不闭合块注释 / 字符串：吃到结尾（与剥离器同源语义）
    assert _kinds("/* 不闭合") == ["block_comment"]
    assert _kinds('"不闭合') == ["string"]


def test_iter_c_regions_preprocessor_axis():
    # 默认（严格行首）：缩进 # 行按普通文本，其字符串照剥（pid.c 判例语义）
    code = '  #include "headfile.h"\nint x;\n'
    kinds = _kinds(code)
    assert "preprocessor" not in kinds
    assert _kinds(code, preprocessor=False) == _kinds(code)
    # preprocessor_indented=True：缩进 # 行整行透传（骨架替换走查语义，
    # 区域从 # 起，前导空白是 code 段）
    regions = [(k, code[s:e]) for k, s, e in iter_c_regions(code, preprocessor_indented=True)]
    assert regions == [
        ("code", "  "),
        ("preprocessor", '#include "headfile.h"\n'),
        ("code", "int x;\n"),
    ]
    # 反斜杠续行里的下一行 # 不因前一行尾字符被误判（strict 的意义）
    code2 = "#define X \\" + "\n" + '  #include "h.h"\n'
    assert _kinds(code2, preprocessor_indented=True).count("preprocessor") == 2


def test_match_bracket_nests_and_ignores_comments_and_strings():
    code = 'foo(bar(baz(1)), "a(b");  /* ) */ '
    close = match_bracket(code, code.index("("), "(", ")")
    assert code[close] == ")"
    assert code[: close + 1] == 'foo(bar(baz(1)), "a(b")'
    # { } 轴与 ( ) 轴同一实现
    block = "while(1) { if (x) { y(); } /* } */ }"
    close = match_bracket(block, block.index("{"), "{", "}")
    assert block[close] == "}"
    assert block[: close + 1] == "while(1) { if (x) { y(); } /* } */ }"


def test_match_bracket_unbalanced_returns_minus_one():
    assert match_bracket("foo(", 3, "(", ")") == -1
    assert match_bracket("while(1) { if (x) {", 8, "{", "}") == -1


def test_match_bracket_skips_preprocessor_line_with_parens():
    # 行首 # 预处理行的括号不计数（与 iter_c_regions 切分同语义）
    code = '#define F(x) x\nfoo(a, b)\n'
    open_at = code.index("foo") + 3
    close = match_bracket(code, open_at, "(", ")")
    assert code[close] == ")"
    assert code[: close + 1] == "#define F(x) x\nfoo(a, b)"


def test_match_bracket_early_stop_does_not_scan_past_close():
    # 早停修复（工单 code-page-vscode-overhaul/08）：闭合后的大量内容不参与
    # 扫描——配平位置紧邻括号（旧实现经 iter_c_regions 会扫到文件尾）
    code = "f(a)" + " " * 100000
    assert match_bracket(code, code.index("("), "(", ")") == 3


def test_top_level_functions_5000_functions_fast():
    # 性能回归（工单 code-page-vscode-overhaul/08 前置）：5000 函数合成文件
    # 旧实现 84s（match_bracket 逐候选 O(剩余文件)）；早停后毫秒级。8s 界线
    # 宽容（防 CI 抖动），回归数倍以上仍能拦住。
    import time

    src = "\n".join(f"int fn_{i}(int x) {{ return x + {i}; }}  // line {i}" for i in range(5000))
    t0 = time.time()
    funcs = top_level_functions(src)
    elapsed = time.time() - t0
    assert len(funcs) == 5000
    assert elapsed < 8, f"top_level_functions 5000 函数耗时 {elapsed:.2f}s（早停修复前约 84s）"


def test_next_significant_skips_whitespace_and_comments():
    code = "while(1) { }   /* 注释 */  \n // 行注释\n return 0;"
    pos = next_significant(code, 12)
    assert code[pos : pos + 6] == "return"
    # 字符串是有效内容，不跳
    code2 = '  "str" x'
    assert code2[next_significant(code2, 0)] == '"'


# ---------------------------------------------------------------------------
# quoted_include_lines：引号 include 的 (名称, 行号)（工单 code-viewer/03）
# ---------------------------------------------------------------------------


def test_quoted_include_lines_returns_names_with_line_numbers():
    code = '#include "headfile.h"\n// #include "no.h"\n#  include  "spaced.h"\nint x;\n'

    assert quoted_include_lines(code) == [
        ("headfile.h", 1),  # 行号 = # 行在原文的位置（注释行不挤占行数）
        ("spaced.h", 3),
    ]


# ---------------------------------------------------------------------------
# top_level_functions：顶层函数定义形态扫描（工单 code-viewer/03，机械法
# best-effort：ident ( … ) { @ 括号深度 0；关键字 / 字符串 / 注释 / 宏续行排除）
# ---------------------------------------------------------------------------


def test_top_level_functions_returns_name_and_line():
    code = (
        "#include <stdint.h>\n"
        "\n"
        "static uint32_t\n"
        "init_uart(uint32_t baud)\n"
        "{\n"
        "    return baud;\n"
        "}\n"
        "\n"
        "void *get_buffer(void) {\n"
        "    return 0;\n"
        "}\n"
        "\n"
        "int main(void) {\n"
        "    while (1) {\n"
        "        delay_ms(10);\n"
        "    }\n"
        "}\n"
    )

    assert top_level_functions(code) == [
        {"name": "init_uart", "line": 4},  # 返回类型分行：函数名所在行
        {"name": "get_buffer", "line": 9},  # 指针返回类型
        {"name": "main", "line": 13},
    ]


def test_top_level_functions_skips_keywords_calls_and_prototypes():
    code = (
        "void setup(void);\n"  # 原型（; 结尾）不收
        "int main(void) {\n"
        "    if (x) { y(); }\n"
        "    for (;;) { break; }\n"
        "    do { i++; } while (i < 10);\n"
        "    switch (k) { case 1: break; }\n"
        "    return 0;\n"
        "}\n"
        "static inline int clamp(int v) { return v; }\n"
    )

    assert top_level_functions(code) == [
        {"name": "main", "line": 2},
        {"name": "clamp", "line": 9},
    ]


def test_top_level_functions_skips_comments_and_strings():
    code = (
        "// void commented(void) { }\n"
        'const char *s = "void in_string(void) {";\n'
        "void real(void) { }\n"
    )

    assert top_level_functions(code) == [{"name": "real", "line": 3}]


def test_top_level_functions_skips_macro_continuation_lines():
    # 宏续行（前一行为反斜杠结尾）里的 `static void name##_init(void) {` 形态
    # 是已知误收风险——整行跳过；宏外第一个函数不受影响
    code = (
        "#define DECL(name) \\\n"
        "    static void name##_init(void) { \\\n"
        "        x++; \\\n"
        "    }\n"
        "void after(void) { }\n"
    )

    assert top_level_functions(code) == [{"name": "after", "line": 5}]


def test_top_level_functions_skips_typedef_and_function_pointer():
    code = (
        "typedef struct {\n"
        "    int x;\n"
        "} Point;\n"
        "int (*handler)(void);\n"
        "int main(void) {\n"
        "}\n"
    )

    assert top_level_functions(code) == [{"name": "main", "line": 5}]
