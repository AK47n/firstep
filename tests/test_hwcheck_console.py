# -*- coding: utf-8 -*-
"""硬件检测：交互式串口命令台（工单 module-hwcheck/06）。

**为什么这样测**：命令台的三块判据都是域层纯函数（字符串进 / 结果出）——

* **命令表**（`build_console_table`）：配方声明的命令字符 + 固定的帮助命令；
  字符冲突（两件抢同一个字符、或抢了库内既有 `r/y/g/o/b`）必须**构建期**红，
  不是运行时静默覆盖；
* **命令解析**（`parse_console_command`）：合法命令 / 未知命令 / 多字符参数 /
  空输入四类，都在内存里直测；
* **回显格式**（渲染出的 C）：三段固定（这是哪件 / 测的是什么 / 结论·数值）。

它们合起来的用户可见行为是：**不用重烧就能复测**，而既有的五条命令
（`r/y/g/o/b`）由库内 `debug_cmd_poll()` 原样执行——本单不碰它的语义。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.clex import iter_c_regions, match_bracket, strip_comments
from contest_generator.hwcheck import HwCheckConfig, render_main_c
from contest_generator.hwcheck_console import (
    HELP_COMMAND,
    LEGACY_COMMANDS,
    RESERVED_COMMANDS,
    ConsoleEntry,
    ConsoleTable,
    build_console_table,
    console_hint,
    console_payload,
    parse_console_command,
    render_console_runtime,
)
from contest_generator.hwcheck_errors import HwCheckError
from contest_generator.hwcheck_recipe import (
    RecipeConsole,
    RecipeProbe,
    RecipeRead,
    RecipeSection,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from tests._c_escape import decode_c_string

REPO = Path(__file__).resolve().parents[1]

_CONTROL_KEYWORDS = frozenset({"while", "if", "for", "switch", "return", "sizeof"})


def unescape_c_string(text: str) -> str:
    """渲染产物里的 ASCII 转义（三位八进制）→ 人能读的字符（解码器单源在
    `tests/_c_escape.py`，工单 05 起两个测试文件共用）。"""
    return decode_c_string(text)


def _called_names(code: str) -> set[str]:
    """一段 C 里真实出现的调用名（先剥注释；控制关键字不算）。"""
    names = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", strip_comments(code)))
    return names - _CONTROL_KEYWORDS



def _section(
    slug: str,
    command: str | None = None,
    description: str = "",
    *,
    platform: str = PLATFORM_STM32,
    init: tuple[str, ...] = (),
    init_expect: str = "",
    probe: RecipeProbe | None = None,
    read: tuple[RecipeRead, ...] = (),
) -> RecipeSection:
    """造一节配方（命令台的判据只读 `console` + "测的是什么"那几段）。"""
    return RecipeSection(
        slug=slug,
        platform=platform,
        init=init,
        init_expect=init_expect,
        probe=probe,
        read=read,
        console=None if command is None else RecipeConsole(command, description),
    )


# ---------------------------------------------------------------------------
# 命令表：配方声明 + 固定帮助 + 构建期冲突
# ---------------------------------------------------------------------------


def test_table_collects_recipe_commands_and_the_fixed_help_command():
    """命令表 = 每件声明的字符（保序）+ 固定的帮助命令（不可被配方占用）。"""
    table = build_console_table([
        _section("led", "l", "复测板载 LED"),
        _section("ml_mpu6050", "m", "复测 MPU6050 通信"),
    ])
    assert [entry.command for entry in table.entries] == ["l", "m"]
    assert [entry.slug for entry in table.entries] == ["led", "ml_mpu6050"]
    assert table.help_command == HELP_COMMAND
    assert table.entries[1].description == "复测 MPU6050 通信"


def test_table_is_empty_when_no_recipe_declares_a_command():
    """一件都没声明命令 = 空表（帮助命令照旧在，不是错误）。"""
    table = build_console_table([_section("led"), _section("oled")])
    assert table.entries == ()
    assert table.help_command == HELP_COMMAND
    assert "?" in table.help_text()


def test_two_devices_may_not_share_a_command_character():
    """两件抢同一个字符 = 构建期红，点名两件与那个字符（不是运行时静默覆盖）。"""
    with pytest.raises(HwCheckError) as excinfo:
        build_console_table([
            _section("led", "l", "复测 LED"),
            _section("oled", "l", "复测 OLED"),
        ])
    message = str(excinfo.value)
    assert "l" in message and "led" in message and "oled" in message
    assert "命令" in message


def test_recipe_may_not_take_over_a_library_command_character():
    """配方不得占用库内既有命令字符（`r/y/g/o/b`）与帮助字符——否则既有行为被抢。"""
    for reserved in sorted(RESERVED_COMMANDS):
        with pytest.raises(HwCheckError) as excinfo:
            build_console_table([_section("led", reserved, "抢字符")])
        assert reserved in str(excinfo.value)


def test_legacy_command_set_is_the_library_protocol():
    """既有五条命令的**单源**：字符与含义与库内 `debug_cmd_poll()` 一致。"""
    assert [command for command, _ in LEGACY_COMMANDS] == ["r", "y", "g", "o", "b"]
    assert HELP_COMMAND == "?"
    assert RESERVED_COMMANDS == frozenset({"r", "y", "g", "o", "b", "?"})


def test_uppercase_declaration_clashes_with_its_lowercase_twin():
    """大小写不敏感：`l` 与 `L` 是同一个命令（库内既有命令也是两写都收）。"""
    with pytest.raises(HwCheckError):
        build_console_table([
            _section("led", "l", "复测 LED"),
            _section("oled", "L", "复测 OLED"),
        ])


def test_uppercase_declaration_is_normalized_to_the_canonical_form():
    """声明 `L` 就是声明 `l`：表里只有一个小写形态，产物里也只出一对 `case`。

    这条抓的是一类"编不过"：渲染器为每个命令出 `case 'x': case 'X':` 两个标签
    ——声明要是大写，两个标签就都是 `case 'L':`（重复标签，编译器直接报错）。
    规范化到小写之后，两种声明的产物逐字节相同。
    """
    table = build_console_table([_section("led", "L", "复测 LED")])
    assert table.entries[0].command == "l"
    code = _rendered(table)
    assert code.count("case 'l':") == 1 and code.count("case 'L':") == 1
    # 两种声明渲染出同一份分派（大小写不敏感是"同一个命令"，不是两个）
    assert code == _rendered(
        build_console_table([_section("led", "l", "复测 LED")]))


def test_command_must_be_one_printable_ascii_character():
    """命令字符的形状判据（多字符 / 空白 / 非 ASCII 都当场红，带中文理由）。"""
    for bad in ("lm", " ", "\t", "中"):
        with pytest.raises(HwCheckError) as excinfo:
            build_console_table([_section("led", bad, "形状不对")])
        assert "led" in str(excinfo.value)


def test_command_may_not_be_a_quote_or_backslash():
    """`'` 与 `\\` 不能当命令字符：它们进不了 C 字符字面量（评审实测编不过）。

    渲染器把命令落成 `case 'x':`，`'` 会变成 `case ''':`、`\\` 会变成 `case '\\':`
    ——**编译器直接报错**（`#8: missing closing quote` 那一类的近亲），而构建期
    那句中文判据却放它过去了：等于把"配方写错当场红"的承诺在这两个字符上打洞。
    （想用它就得转义成 `'\\''`，但串口上敲单引号本来就不该是命令——判据刻意窄。）
    """
    for bad in ("'", "\\"):
        with pytest.raises(HwCheckError) as excinfo:
            build_console_table([_section("led", bad, "危险字符")])
        message = str(excinfo.value)
        assert "led" in message and bad in message
        assert "C" in message   # 理由要说清是"进不了 C 字符字面量"


def test_help_text_lists_legacy_recipe_and_help_commands():
    """帮助文案：既有五条 + 本趟配方命令 + 帮助自己——三条都在，一条都不许漏。"""
    table = build_console_table([_section("led", "l", "复测板载 LED")])
    text = table.help_text()
    for command, _meaning in LEGACY_COMMANDS:
        assert command in text
    assert HELP_COMMAND in text
    assert "l" in text and "led" in text and "复测板载 LED" in text


def test_build_console_table_is_pure_and_deterministic():
    sections = [_section("led", "l", "复测板载 LED")]
    assert build_console_table(sections) == build_console_table(sections)


# ---------------------------------------------------------------------------
# 命令解析（纯函数：字符串进 / 结果出）
# ---------------------------------------------------------------------------


def _table() -> ConsoleTable:
    return build_console_table([
        _section("led", "l", "复测板载 LED"),
        _section("ml_mpu6050", "m", "复测 MPU6050 通信"),
    ])


def test_parse_treats_an_empty_line_as_nothing_to_do():
    """空输入（按键还没收到东西）不是命令，也不是错误——什么都不做。

    ⚠ **只认空串**，空白不算：板上 `line[0]` 是原样第一个字符，库内既有命令
    也是 `cmd_buf[0]`——这里要是先 `strip()`，`" l"` 在 Python 侧是复测、在板上
    是未知命令，两条实现就分家了（评审实测的错位）。
    """
    table = _table()
    result = parse_console_command("", table)
    assert result.kind == "empty"
    assert result.entry is None
    for line in ("   ", "\t", " l"):
        assert parse_console_command(line, table).kind == "unknown", line


def test_parse_maps_a_declared_character_to_its_device():
    result = parse_console_command("l", _table())
    assert result.kind == "retest"
    assert result.slug == "led"
    assert result.entry == ConsoleEntry("l", "led", "复测板载 LED")


def test_parse_is_case_insensitive_for_recipe_commands():
    """`L` 与 `l` 同一条命令（照库内既有命令 `r`/`R` 两写都收的先例）。"""
    assert parse_console_command("L", _table()).slug == "led"


def test_parse_ignores_trailing_characters_after_the_command():
    """命令粒度 = 首字符（库内既有的 `r50` 也是红灯，同一口径）：

    `m12` 是"复测 ml_mpu6050"并忽略尾巴，**不是**未知命令——手滑多敲一个
    字符就"命令不认"才是让人骂街的行为。
    """
    result = parse_console_command("m12", _table())
    assert result.kind == "retest" and result.slug == "ml_mpu6050"


def test_parse_leaves_the_library_commands_alone():
    """既有五条命令照旧归库内 `debug_cmd_poll()` 处理——**含多字符参数** `b50`。"""
    table = _table()
    for line in ("r", "R", "y", "g", "o", "b", "b50", "B200"):
        result = parse_console_command(line, table)
        assert result.kind == "legacy", line
        assert result.entry is None


def test_parse_recognizes_the_help_command():
    result = parse_console_command(HELP_COMMAND, _table())
    assert result.kind == "help"
    assert result.entry is None


def test_parse_reports_an_unknown_command_without_guessing():
    """未知命令如实报"不认识"——不猜成某一件（猜错会让学生以为测了那一件）。"""
    table = _table()
    for line in ("z", "Z9", "1"):
        result = parse_console_command(line, table)
        assert result.kind == "unknown", line
        assert result.entry is None
        assert result.command == line[0]


def test_parse_never_returns_a_command_outside_the_table():
    """结果里的命令一定是表里的（帮助 / 既有 / 配方 / 未知四类之一，无第五类）。"""
    table = _table()
    kinds = {
        parse_console_command(line, table).kind
        for line in ("", "l", "?", "r", "z")
    }
    assert kinds == {"empty", "retest", "help", "legacy", "unknown"}


def test_parse_and_the_rendered_dispatch_agree_on_every_kind():
    """**两份实现必须一致**：纯解析函数（域层，票面要求的那条缝）说的四类，
    渲染出的 C 分派树必须逐条对上。

    为什么要这条：C 侧分派是渲染出的文本，Python 侧解析是"这一行算什么"的
    可执行规格——两者各写一份就迟早漂（漂的后果是"页面/单测说能复测、板上不认"）。
    这条把两个实现钉在一起：任何一侧改了分派口径，这里当场红。
    """
    table = build_console_table([_section("led", "l", "复测板载 LED")])
    code = _rendered(table)
    # retest：解析说是哪一件 → 分派树里那个字符下面调的就是那一件的小节
    # （三段回显的调用面 = 小节头 + 细节行 + 那一件的小节体，多一个少一个都红）
    retest = parse_console_command("l", table)
    assert retest.kind == "retest"
    assert _called_names(_case_block(code, f"case '{retest.command}':")) == {
        "hwcheck_section", "hwcheck_detail", f"hwcheck_check_{retest.slug}",
    }
    # help：解析说是帮助 → 分派树里那个字符下面调帮助函数
    help_ = parse_console_command("?", table)
    assert help_.kind == "help"
    assert "hwcheck_console_help" in _called_names(
        _case_block(code, f"case '{help_.command}':"))
    # legacy：解析说交给库内 → 分派树里那一组只有 return（没有任何动作）
    legacy = parse_console_command("b50", table)
    assert legacy.kind == "legacy"
    legacy_block = _case_block(code, f"case '{legacy.command}':")
    assert _called_names(legacy_block) == set() and "return;" in legacy_block
    # unknown：解析说认不出来 → 分派树的 default 印「未知命令」+ 帮助
    unknown = parse_console_command("z", table)
    assert unknown.kind == "unknown"
    assert "hwcheck_console_help" in _called_names(_case_block(code, "default:"))
    # empty：解析说没东西可做 → 分派树最前面就 return（连 switch 都进不去）
    assert parse_console_command("", table).kind == "empty"
    assert "if (line[0] == '\\0')" in code
    # 边界口径也要对得上：前导空白是"未知命令"（不是复测）——C 侧看 line[0]，
    # Python 侧因此**不能** strip（评审实测的错位就出在这条）
    assert parse_console_command(" l", table).kind == "unknown"
    unknown_block = _case_block(code, "default:")
    assert "hwcheck_report(line)" in unknown_block, "未知命令要把原样那一行回显出来"



# ---------------------------------------------------------------------------
# 渲染出的 C：分派 + 三段回显 + 既有命令原样留给库
# ---------------------------------------------------------------------------


def _rendered(table: ConsoleTable) -> str:
    return "\n".join(render_console_runtime(table))


def _case_block(code: str, label: str) -> str:
    """摘出某个 `case` 标签所在的**整组**（前导标签 + 它的分支体，到下一个标签止）。

    一组 = 连着写的几个 `case` 标签（如 `case 'l': case 'L':`）加同一段分支体
    ——只看单个标签会得到空串。
    """
    lines = code.splitlines()
    index = next(i for i, line in enumerate(lines) if line.strip() == label)
    while index > 0 and lines[index - 1].strip().startswith("case "):
        index -= 1  # 回退到这组标签的第一个（大小写成对写的那种）
    out: list[str] = []
    seen_body = False
    for line in lines[index:]:
        stripped = line.strip()
        is_label = stripped.startswith("case ") or stripped.startswith("default:")
        if is_label and seen_body:
            break
        if not is_label:
            seen_body = True
        out.append(line)
    return "\n".join(out)


def test_console_runtime_dispatches_each_recipe_command_to_its_section():
    table = build_console_table([
        _section("led", "l", "复测板载 LED"),
        _section("ml_mpu6050", "m", "复测 MPU6050 通信"),
    ])
    code = _rendered(table)
    assert "debug_cmd_peek()" in code
    assert "debug_cmd_consume()" in code
    assert "hwcheck_check_led()" in code
    assert "hwcheck_check_ml_mpu6050()" in code
    assert "case 'l':" in code and "case 'L':" in code
    assert "case 'm':" in code and "case 'M':" in code


def test_console_retest_echo_has_the_three_fixed_segments():
    """回显格式固定三段：① 这是哪件 ② 测的是什么 ③ 结论 / 数值（跑那一节）。

    ⚠ 第三段用 `_called_names`（**先剥注释**）判：判据强度探针实测过——直接子串
    匹配 `"hwcheck_check_led();"` 会被注释掉的同一行骗过（`/* hwcheck_…(); */`
    里照样有这个子串），那条断言等于没写。
    """
    table = build_console_table([_section("led", "l", "复测板载 LED")])
    block = _case_block(_rendered(table), "case 'l':")
    assert 'hwcheck_section("' in block
    assert "led" in unescape_c_string(block)
    assert 'hwcheck_detail("' in block
    assert "测的是：复测板载 LED" in unescape_c_string(block)
    assert "hwcheck_check_led" in _called_names(block), "第三段必须是真调用（不是注释）"


def test_console_runtime_hands_the_library_commands_back_untouched():
    """既有 `r/y/g/o/b`（两种大小写）**只 return**，一个动作都不做。

    这条是本单"语义一个字节不动"的**结构证据**：分派表里那几条字符底下没有
    任何重写（没有点灯 / 蜂鸣调用），原样交给库内 `debug_cmd_poll()`。
    """
    code = _rendered(build_console_table([_section("led", "l", "复测板载 LED")]))
    legacy_block = _case_block(code, "case 'r':")
    body_calls = _called_names(legacy_block)
    assert body_calls == set(), f"既有命令的分支里不许有动作：{body_calls}"
    assert "return;" in legacy_block
    for label in ("case 'R':", "case 'y':", "case 'Y':", "case 'g':",
                  "case 'G':", "case 'o':", "case 'O':", "case 'b':", "case 'B':"):
        assert label in code, label


def test_console_runtime_help_lists_legacy_recipe_and_help_commands():
    """帮助是**固定命令**：既有五条 + 配方命令 + 帮助自己，行行都在产物里。"""
    table = build_console_table([_section("led", "l", "复测板载 LED")])
    code = unescape_c_string(_rendered(table))
    for line in table.help_lines():
        assert line in code, line


def test_console_runtime_reports_unknown_commands_with_a_help_line():
    """未知命令：原样回显学生敲的那一行 + 印帮助（不静默吞掉）。

    "印帮助"要单独判（判据强度探针实测：只断言 `[未知命令]` 与 `hwcheck_report(line)`
    时，把 default 分支里那句 `hwcheck_console_help()` 删掉也不会红——探针抓到的
    一条摆设守卫）。
    """
    code = _rendered(build_console_table([_section("led", "l", "复测板载 LED")]))
    text = unescape_c_string(code)
    assert "[未知命令]" in text
    assert "hwcheck_report(line)" in text
    unknown_block = _case_block(code, "default:")
    assert "hwcheck_console_help" in _called_names(unknown_block), (
        "未知命令必须把帮助打出来（否则学生只知道敲错了，不知道能敲什么）"
    )


def test_console_runtime_renders_even_with_no_recipe_commands():
    """一件都没声明命令也要有命令台：帮助命令是固定的（能查"有什么命令"）。"""
    code = _rendered(build_console_table([_section("led")]))
    assert "debug_cmd_peek()" in code
    assert "case '?':" in code
    assert "hwcheck_console_help()" in code


# ---------------------------------------------------------------------------
# 接进 main.c：命令循环在自动那遍之后、既有 poll 之前
# ---------------------------------------------------------------------------

WITH_CONSOLE = HwCheckConfig(
    platform=PLATFORM_STM32, debug_uart=True, oled=False, devices=("led",)
)
NO_SERIAL = HwCheckConfig(
    platform=PLATFORM_STM32, debug_uart=False, oled=True, devices=("led",)
)
SERIAL_NO_COMMAND = HwCheckConfig(
    platform=PLATFORM_STM32, debug_uart=True, oled=False, devices=("oled",)
)


def _sections_for_main():
    return (
        _section("led", "l", "复测板载 LED"),
        _section("oled", None, ""),
    )


def _sections_without_commands():
    return (_section("oled", None, ""),)


def test_main_keeps_the_automatic_pass_and_then_enters_the_command_loop():
    """自动那遍照旧（逐件自报 + 汇总）在前，命令循环在后——顺序不能反。"""
    code = render_main_c(WITH_CONSOLE, _sections_for_main())
    auto = code.index("hwcheck_check_led();")
    loop = code.index("while (1)")
    assert auto < loop
    assert "hwcheck_console_poll();" in code[loop:]


def test_main_polls_our_console_before_the_library_poll():
    """顺序硬要求：先 peek 我们的命令，再让库内 poll 处理既有命令。

    反了会怎样：库内 `debug_cmd_poll()` 先把缓冲清空，配方命令永远认不出来
    ——现象是"敲了没反应、既有命令照常"，最难查的一类静默失效。
    """
    code = render_main_c(WITH_CONSOLE, _sections_for_main())
    loop = code[code.index("while (1)"):]
    assert loop.index("hwcheck_console_poll();") < loop.index("debug_cmd_poll();")


def test_main_defines_the_console_after_the_section_functions():
    """命令台在逐件小节**之后**：switch 里直接调 `hwcheck_check_<slug>()`。"""
    code = render_main_c(WITH_CONSOLE, _sections_for_main())
    assert code.index("static void hwcheck_check_led(void)") < code.index(
        "static void hwcheck_console_poll(void)"
    )


def test_main_without_serial_says_interactive_retest_is_impossible():
    """无串口 = 只跑自动那遍，且**明说**不能交互复测（不静默降级）。"""
    code = render_main_c(NO_SERIAL, _sections_for_main())
    assert "hwcheck_console_poll" not in code
    assert "debug_cmd_peek" not in code
    assert "debug_cmd_poll" not in code
    text = unescape_c_string(code)
    assert "不能交互式复测" in text


def test_main_with_serial_but_no_recipe_command_still_has_the_help_command():
    """有串口但一件都没声明命令：命令台**仍在**（固定的帮助命令是表的一部分）。

    为什么不"一个字都不加"：检测页那句提示写着"命令循环里敲 ? 看帮助"——命令台
    不在，那句话就成了假话（评审抓到的）；而且没有配方命令时，学生更需要有人
    告诉他"能敲什么、既有那五条还在不在"。
    """
    code = render_main_c(SERIAL_NO_COMMAND, _sections_without_commands())
    assert "debug_cmd_peek()" in code and "debug_cmd_consume()" in code
    assert "hwcheck_console_poll();" in code
    assert "case '?':" in code
    assert "case 'l':" not in code       # 没有配方命令 → 没有配方 case
    assert "debug_cmd_poll();" in code   # 既有命令照旧由库内执行


def test_main_header_lists_the_console_commands_when_they_exist():
    """文件头（给人读）说实话：有配方命令就列出来，没有就说清只剩帮助与既有命令。"""
    with_console = unescape_c_string(render_main_c(WITH_CONSOLE, _sections_for_main()))
    assert "复测板载 LED" in with_console
    without = unescape_c_string(
        render_main_c(SERIAL_NO_COMMAND, _sections_without_commands())
    )
    assert "复测板载 LED" not in without
    assert "?" in without, "没有配方命令时也要说清帮助命令在哪"
    assert "没有配方命令" in without or "只有帮助" in without


def test_main_raises_at_build_time_when_two_devices_share_a_command():
    """字符冲突在**构建期**红（渲染 main.c 这一步），不是运行时静默覆盖。"""
    conflicting = (
        _section("led", "l", "复测 LED"),
        _section("oled", "l", "复测 OLED"),
    )
    with pytest.raises(HwCheckError) as excinfo:
        render_main_c(WITH_CONSOLE, conflicting)
    message = str(excinfo.value)
    assert "led" in message and "oled" in message


# ---------------------------------------------------------------------------
# 库侧接口（工单 06 选的 A 方案）：把收到的命令交出来，poll 一个字节不动
# ---------------------------------------------------------------------------

DEBUG_UART_CODE = REPO / "library" / "modules" / "debug_uart" / "code"
DEBUG_UART_SOURCES = (
    ("debug_uart.h", "debug_uart.c"),
    ("debug_uart_mspm0.h", "debug_uart_mspm0.c"),
)


def _source_without_comments(text: str) -> str:
    """只剥注释（**保留**字符 / 字符串字面量）。

    不能用 `clex.strip_comments`：它连字符字面量一起剥，而本节的判据恰恰要
    读 `c == 'r'` 里的那个 `'r'`。
    """
    return "".join(
        text[start:end]
        for kind, start, end in iter_c_regions(text, preprocessor=True)
        if kind not in ("line_comment", "block_comment")
    )


def _function_body(source: str, name: str) -> str:
    """摘出一个函数定义的花括号体（机械配平，不猜语义）。"""
    marker = source.index(f"{name}(void)")
    open_brace = source.index("{", marker)
    close_brace = match_bracket(source, open_brace, "{", "}")
    assert close_brace != -1, f"{name} 的花括号不配平"
    return source[open_brace:close_brace]


@pytest.mark.parametrize("header_name,source_name", DEBUG_UART_SOURCES)
def test_library_hands_the_received_command_to_the_application(header_name, source_name):
    """两平台都加 `debug_cmd_peek()` / `debug_cmd_consume()`（工单 06 定的 A 方案）。

    为什么不自己重写那五条命令：既有语义住在库内 `debug_cmd_poll()` 里，命令台
    只**看一眼**再决定认不认领——所以库侧要交出"收到了什么"。
    """
    header = (DEBUG_UART_CODE / header_name).read_text(encoding="utf-8")
    source = _source_without_comments((DEBUG_UART_CODE / source_name).read_text(encoding="utf-8"))
    for name in ("debug_cmd_peek", "debug_cmd_consume"):
        assert name in header, f"{header_name} 没声明 {name}"
        assert f"{name}(void)" in source, f"{source_name} 没定义 {name}"


def test_library_peek_is_read_only_and_consume_is_the_only_consumer():
    """`peek` 只读（不碰缓冲），`consume` 才清空——生成侧靠这个分工做"认领"。

    反了会怎样：peek 顺手清空 → 既有 `r/y/g/o/b` 永远收不到（库内 poll 拿到
    空串），已上过板的点灯 / 蜂鸣命令全体静默失效。
    """
    for _header, source_name in DEBUG_UART_SOURCES:
        source = _source_without_comments(
            (DEBUG_UART_CODE / source_name).read_text(encoding="utf-8")
        )
        peek = _function_body(source, "debug_cmd_peek")
        assert "cmd_buf" in peek
        assert "=" not in peek.split("return", 1)[0], f"{source_name} 的 peek 里有赋值"
        consume = _function_body(source, "debug_cmd_consume")
        assert "cmd_buf" in consume and "=" in consume


@pytest.mark.parametrize("_header,source_name", DEBUG_UART_SOURCES)
def test_our_legacy_command_mirror_matches_the_library_dispatch(_header, source_name):
    """**parity 守卫**：本模块登记的既有命令 = 库内 `debug_cmd_poll()` 真分派的那几条。

    **两个平台的判据面不同，如实分开**（评审核对过：早先 mspm0 那一支是空转的，
    只断言了"正文里有 DEBUG_PRINTF"，等于没判）：

    * **stm32**：逐字符核对分派（`c == 'r'` 那一串 if-else）——镜像漏登记一条，
      配方就可能抢走那条既有命令（学生敲 r 不再点灯）；
    * **mspm0**：**没有逐字符分派**（只回显整行 `CMD: %s`），没有可比的字符集；
      但它的**契约**仍要钉住——回显 + **消费缓冲**（命令台"原样留给库内"的前提
      正是库内那份自己会消费，否则命令会一直重复执行）。
    """
    source = _source_without_comments(
        (DEBUG_UART_CODE / source_name).read_text(encoding="utf-8")
    )
    body = _function_body(source, "debug_cmd_poll")
    if "c == 'r'" not in body:
        assert "DEBUG_PRINTF" in body, "mspm0 版应回显命令"
        assert "cmd_buf[0] = '\\0'" in body, "mspm0 版应消费缓冲（否则重复执行）"
        return
    dispatched = {match.lower() for match in re.findall(r"c\s*==\s*'(.)'", body)}
    assert dispatched == {command for command, _meaning in LEGACY_COMMANDS}


# ---------------------------------------------------------------------------
# 检测页载荷（页面与产物读同一张表）
# ---------------------------------------------------------------------------


def test_console_hint_says_out_loud_when_there_is_no_serial():
    """无串口 = **不能交互式复测**（票面：明说，不静默降级）。"""
    table = build_console_table([_section("led", "l", "复测板载 LED")])
    hint = console_hint(False, table)
    assert "不能交互式复测" in hint
    assert "勾上" in hint  # 给出下一步：怎么才能复测


def test_console_hint_with_serial_points_at_the_help_command():
    table = build_console_table([_section("led", "l", "复测板载 LED")])
    for entries in (table, build_console_table([_section("led")])):
        hint = console_hint(True, entries)
        assert HELP_COMMAND in hint
        assert "复测" in hint


def test_console_payload_carries_the_table_and_the_legacy_commands():
    """载荷 = 页面要看的一切：配方命令 + 既有命令 + 帮助 + 可用性 + 那句提示。"""
    table = build_console_table([_section("led", "l", "复测板载 LED")])
    payload = console_payload(True, table)
    assert payload["available"] is True
    assert payload["help_command"] == HELP_COMMAND
    assert payload["commands"] == [{
        "command": "l",
        "slug": "led",
        "description": "复测板载 LED",
        "echo": "测的是：复测板载 LED",
    }]
    assert [item["command"] for item in payload["legacy"]] == ["r", "y", "g", "o", "b"]
    assert payload["hint"] == console_hint(True, table)


def test_console_payload_marks_availability_false_without_serial():
    table = build_console_table([_section("led", "l", "复测板载 LED")])
    payload = console_payload(False, table)
    assert payload["available"] is False
    assert "不能交互式复测" in payload["hint"]
    # 命令表照给：学生勾上串口再生成就能用，页面不必等下一次请求才知道敲什么
    assert [item["command"] for item in payload["commands"]] == ["l"]


# ---------------------------------------------------------------------------
# 真库真配方：pilot 三件都声明了复测命令，且互不冲突（读盘，不手写替身）
# ---------------------------------------------------------------------------


def _real_sections(platform: str):
    """真库 → 该平台的小节（判据读真数据：库内配方 + 真接口清单）。"""
    from contest_generator.hwcheck_recipe import interface_names, load_recipes, resolve_sections
    from contest_generator.library import list_modules
    from contest_generator.master_store import master_project_dir
    from contest_generator.treewalk import iter_project_files

    modules = REPO / "library" / "modules"
    manifests = list_modules(modules)
    interfaces = {}
    for name in (PLATFORM_STM32, PLATFORM_MSPM0):
        master = master_project_dir(REPO / "library" / "masters", name)
        headers = [] if not master.is_dir() else [
            (path.relative_to(master).as_posix(),
             path.read_text(encoding="utf-8", errors="replace"))
            for path in iter_project_files(master, pattern="*.h")
        ]
        interfaces[name] = interface_names(manifests, modules, name, headers)
    recipes = load_recipes(modules, manifests, interfaces)
    return resolve_sections(
        platform, ("led", "oled", "ml_mpu6050"), recipes, manifests
    )


@pytest.mark.parametrize("platform", [PLATFORM_STM32, PLATFORM_MSPM0])
def test_real_library_recipes_declare_distinct_console_commands(platform):
    """真库的 pilot 三件都声明了复测命令，且**互不冲突**（表建得出来）。

    这是"页面上的命令表"与"板上真认的命令"同源的地位断言：配方改了字符，
    这里跟着变；两件抢字符，这里当场红（而不是等学生上板敲了没反应）。
    """
    table = build_console_table(_real_sections(platform))
    assert {entry.slug for entry in table.entries} == {"led", "oled", "ml_mpu6050"}
    assert len({entry.command.lower() for entry in table.entries}) == len(table.entries)
    for entry in table.entries:
        assert entry.description, f"{entry.slug} 的命令没写说明（回显会变成空话）"






