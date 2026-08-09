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
    strip_code_fences,
    strip_comments,
    top_level_defines,
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


def test_next_significant_skips_whitespace_and_comments():
    code = "while(1) { }   /* 注释 */  \n // 行注释\n return 0;"
    pos = next_significant(code, 12)
    assert code[pos : pos + 6] == "return"
    # 字符串是有效内容，不跳
    code2 = '  "str" x'
    assert code2[next_significant(code2, 0)] == '"'
