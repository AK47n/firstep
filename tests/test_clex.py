"""C 词法层：围栏剥离 / 行号检测、注释剥离（# 行透传轴）、include 提取、顶层 #define。

词法层唯一出处（clex.py）——两义剥离器合一后，本文件按 keep_preprocessor
语义轴并排覆盖，防"改一处忘另一处"分叉回归。
"""

from contest_generator.clex import (
    extract_quoted_includes,
    fence_line_indices,
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
