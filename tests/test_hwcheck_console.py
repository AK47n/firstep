# -*- coding: utf-8 -*-
"""硬件检测：交互式串口命令台（工单 module-hwcheck/06）。

**为什么这样测**：命令台的三块判据都是域层纯函数（字符串进 / 结果出）——

* **命令表**（`build_console_table`）：配方声明的命令字符 + 固定的帮助命令。首选被
  别的器件占用时按 `console.candidates` **让位**（工单 hwcheck-specialize/01）；让不开、
  或抢了库内既有 `r/y/g/o/b` / 帮助 `?`、或形状不对（多字符 / 空白 / 引号），必须
  **构建期**红，不是运行时静默覆盖；
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
    COMMAND_POOL,
    HELP_COMMAND,
    LEGACY_COMMANDS,
    RESERVED_COMMANDS,
    ConsoleEntry,
    ConsoleTable,
    build_console_table,
    console_capacity_note,
    CONSOLE_CAPACITY_WARN_REMAINING,
    console_hint,
    console_payload,
    parse_console_command,
    render_console_runtime,
)
from contest_generator.hwcheck_custom import (
    CUSTOM_TAG,
    PLAN_JUDGE,
    PLAN_PING_ONLY,
    CustomSection,
    resolve_custom_sections,
)
from contest_generator.hwcheck_errors import HwCheckError
from contest_generator.hwcheck_recipe import (
    RecipeConsole,
    RecipeProbe,
    RecipeRead,
    RecipeSection,
)
from contest_generator.my_devices import BUS_I2C, CustomDevice
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
    candidates: tuple[str, ...] = (),
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
        console=None if command is None else RecipeConsole(
            command, description, candidates),
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


# ---------------------------------------------------------------------------
# 候选字符让位（工单 hwcheck-specialize/01）：首选被占时按候选顺序让位，
# 而不是把"两件都想用同一个字符"直接兑换成一次 400
# ---------------------------------------------------------------------------


def test_a_taken_character_falls_back_to_the_declared_candidate():
    """首选被占 → 让位到候选：学生勾两件传感器不再是"生成不出来"。"""
    table = build_console_table([
        _section("led", "l", "复测 LED"),
        _section("sht20", "l", "复测 SHT20", candidates=("t", "w")),
    ])
    assert [entry.command for entry in table.entries] == ["l", "t"]
    assert [entry.slug for entry in table.entries] == ["led", "sht20"]
    assert table.entries[1].description == "复测 SHT20"


def test_candidates_are_tried_in_the_declared_order():
    """让位顺序 = **声明顺序**（不排序、不随机）：同一份配方恒定同一结果。"""
    table = build_console_table([
        _section("led", "t", "占掉 t"),
        _section("oled", "w", "占掉 w"),
        _section("sht20", "t", "复测 SHT20", candidates=("w", "z")),
    ])
    assert [entry.command for entry in table.entries] == ["t", "w", "z"]


def test_a_recipe_without_candidates_still_collides_loudly():
    """不带候选的老配方**行为逐字不变**：没有候选可让 → 还是构建期红。

    向后兼容的判据是"老配方一个字节不改、结果一模一样"——让位只在**声明了候选**
    的那一件身上发生，不会顺手替没声明的配方做决定。
    """
    with pytest.raises(HwCheckError) as excinfo:
        build_console_table([
            _section("led", "l", "复测 LED"),
            _section("sht20", "l", "复测 SHT20"),
        ])
    assert "sht20" in str(excinfo.value)


def test_running_out_of_candidates_fails_loudly_with_the_numbers():
    """候选也用完 = 构建期大声失败，**不静默少一条**，且数字要对得上。

    报错要能直接回答三个问题：哪一件排不上号、池子多大、已经被谁占了——
    只说"撞车了"的报错会让学生在两件之间反复换字符试。
    """
    with pytest.raises(HwCheckError) as excinfo:
        build_console_table([
            _section("led", "l", "占掉 l"),
            _section("oled", "d", "占掉 d"),
            _section("sht20", "l", "复测 SHT20", candidates=("d",)),
        ])
    message = str(excinfo.value)
    assert "sht20" in message
    assert f"一共 {len(COMMAND_POOL)} 个" in message, "池子多大要说出来"
    assert "已经占了 2 个" in message, "已被占几个要说出来（两个：l 与 d）"
    assert "'led'" in message and "'oled'" in message, "占位的是谁要点名"
    assert "候选" in message, "出路之一 = 多加几个候选字符"


def test_a_reserved_candidate_is_rejected_even_when_the_first_choice_is_free():
    """候选里也不许出现保留字——**声明即判**，不看这次用不用得上。

    为什么不在"轮到它时"才判：那样同一份配方会因为旁边勾了哪几件而时而报错、
    时而静默通过，"保留字永不被抢"就成了一条看运气的判据。配方写错就该当场红。
    """
    for reserved in sorted(RESERVED_COMMANDS):
        with pytest.raises(HwCheckError) as excinfo:
            build_console_table([
                _section("led", "l", "复测 LED", candidates=(reserved,)),
            ])
        assert reserved in str(excinfo.value)


def test_the_assignment_is_a_pure_function_of_the_selection():
    """同一选中集 → 同一张表（页面与板上各建一次，必须逐字相同）。

    顺带钉住让位的**连锁**：`sht20` 的首选 `l` 被 `led` 占了 → 它拿走候选里的
    `t`；于是后面 `sht30` 的首选 `t` 也没了 → 它再让到 `e`。两件都还是一件
    一个字符，谁都没被静默丢掉。
    """
    def build():
        return build_console_table([
            _section("led", "l", "复测 LED"),
            _section("sht20", "l", "复测 SHT20", candidates=("t", "w")),
            _section("sht30", "t", "复测 SHT30", candidates=("e",)),
        ])

    first, again = build(), build()
    assert first == again
    assert [entry.command for entry in first.entries] == ["l", "t", "e"]


def test_two_recipes_declaring_the_same_candidates_each_get_their_own():
    """两条配方声明**同一组候选**时各拿各的、不撞（验收第 6 条）。

    为什么单列一条：这是让位机制最容易写成"第二个把第一个挤掉"的地方——两边
    候选表一样，实现若按集合而不是按顺序分配、或先算后写，就会给出同一个字符。
    判据 = 两件都在表里、字符互不相同、且**都没被静默丢掉**。
    """
    table = build_console_table([
        _section("led", "l", "占掉 l"),
        _section("sht20", "l", "复测 SHT20", candidates=("w", "z")),
        _section("sht30", "l", "复测 SHT30", candidates=("w", "z")),
    ])
    assert [entry.command for entry in table.entries] == ["l", "w", "z"]
    assert len({entry.command for entry in table.entries}) == 3


def test_the_page_and_the_board_both_show_the_assigned_character():
    """页面载荷与板上分派读的是**分配后**的字符（不是配方里写的首选）。

    否则会出现最坏的那种错位：检测页写着"敲 t 复测 sht20"，板上却把 `t` 分给了
    另一件——学生敲下去复测的是别人。
    """
    table = build_console_table([
        _section("led", "t", "占掉 t"),
        _section("sht20", "t", "复测 SHT20", candidates=("w", "z")),
    ])
    payload = console_payload(True, table)
    assert [(item["slug"], item["command"]) for item in payload["commands"]] == [
        ("led", "t"), ("sht20", "w")]
    code = _rendered(table)
    assert "case 'w':" in code
    assert "hwcheck_check_sht20();" in code
    assert "case 'z':" not in code, "没轮到的候选不许出现在产物里"


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


def test_main_header_lists_the_assigned_console_character():
    """文件头那条配料行与上面那张命令表写的是**同一个**字符（单源不破）。

    首选被占、这一件让位到候选之后，两处若各读各的（表读分配值、配料行读配方声明值），
    产物里就会同时出现 `敲 w 复测 oled` 与 `控制台命令 'l'`——学生照注释敲，板上不认。
    """
    sections = (
        _section("led", "l", "复测 LED"),
        _section("oled", "l", "复测 OLED", candidates=("w", "z")),
    )
    text = unescape_c_string(render_main_c(WITH_CONSOLE, sections))
    oled_brief = next(
        line for line in text.splitlines() if "oled（配方：" in line
    )
    assert "控制台命令 'w'" in oled_brief, oled_brief
    assert "'l'" not in oled_brief, "让位后的那一格不许再写首选字符"


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


# ---------------------------------------------------------------------------
# 自建件也进命令台（工单 hwcheck-unknown-device/06）：库外件没有配方，没人给它
# 声明字符——命令空间**自己分**一个，分不出就构建期大声失败（不静默少一条）
# ---------------------------------------------------------------------------


def _device(**overrides) -> "CustomDevice":
    """一件自建件（定义全是**事实**：地址 / 寄存器 / 期望值）。"""
    data: dict = {
        "id": "mine_gyro",
        "name": "卖家给的六轴模块",
        "bus": BUS_I2C,
        "address": 0x68,
        "register": 0x75,
        "expect": 0x68,
    }
    data.update(overrides)
    return CustomDevice(**data)


def _custom(*devices) -> tuple[CustomSection, ...]:
    """自建件定义 → 探测小节（走 `resolve_custom_sections` 真路径：三档文案单源）。

    **不手搓 `CustomSection`**：`plan` 那句与页面 / 产物同一份，手搓一份就等于
    在用例里造了第二个判据来源。
    """
    return resolve_custom_sections(
        devices or (_device(),), has_output_channel=True
    )


def test_a_custom_device_gets_a_free_command_character_from_its_id():
    """自建件分到一个复测字符，且**取自它自己的 id**（可记：hall → h）。

    它是命令表里的一等公民（与配方命令同一张表、同一个 `ConsoleEntry` 形状），
    差别只有一处：它没有配方，所以字符是分出来的、复测入口是自建件的小节函数。
    """
    table = build_console_table((), _custom(_device(id="mine_hall", name="霍尔传感器")))
    assert [entry.command for entry in table.entries] == ["h"]
    entry = table.entries[0]
    assert entry.slug == "mine_hall"
    assert entry.custom is True
    assert entry.name == "霍尔传感器"
    assert entry.description == PLAN_JUDGE      # 描述 = 这一趟对它做什么（单源）
    assert entry.func_name == "hwcheck_custom_mine_hall"


def test_a_custom_character_never_takes_a_reserved_or_declared_one():
    """保留字（`r/y/g/o/b/?`）与配方声明的字符都**不许被自建件抢走**。

    三种落点各判一条：
    ① id 里的字母全是保留字（`mine_gyro` 的 g/y/r/o）→ 退到兜底池，仍不碰保留字；
    ② 配方已经声明了那个字符 → 自建件让开（配方是库内已上过板的那份数据）；
    ③ 分出来的字符永远不会是保留字（逐条对 `RESERVED_COMMANDS` 断言）。
    """
    gyro = build_console_table((), _custom(_device()))
    assert gyro.entries[0].command == "a", "g/y/r/o 全被保留，退到兜底池第一个空闲字符"
    assert gyro.entries[0].command.lower() not in RESERVED_COMMANDS

    taken = build_console_table(
        [_section("library_hall", "h", "库内也有一件 hall")],
        _custom(_device(id="mine_hall", name="霍尔传感器")),
    )
    assert [entry.command for entry in taken.entries] == ["h", "a"], "配方的 h 优先"
    assert [entry.slug for entry in taken.entries] == ["library_hall", "mine_hall"]
    for entry in taken.entries:
        assert entry.command.lower() not in RESERVED_COMMANDS


def test_the_custom_retest_runs_the_same_section_as_the_power_on_pass():
    """板上敲那个字符 = 重跑这一件的小节，**与上电那一遍同一个函数**。

    这是票面"输出与上电那一遍同一措辞"的结构证据：命令台不是把那一段 C 抄一遍
    （抄一份就会改一处忘一处），而是调同一个 `hwcheck_custom_<id>()`——文案只有
    一个产地，两处的输出逐字节相同。
    """
    custom = _custom()
    entry = build_console_table((), custom).entries[0]
    code = render_main_c(WITH_CONSOLE, (), (), custom)
    block = _case_block(code, f"case '{entry.command}':")
    # 三段回显：小节头 + 细节行 + **那一件的小节体**（多一个少一个都红）
    assert _called_names(block) == {
        "hwcheck_section", "hwcheck_detail", entry.call_target,
    }
    auto = code[code.index("上电自动跑一遍逐件检测"):code.index("while (1)")]
    assert f"{entry.call_target}();" in auto, "上电那一遍调的就是它"
    assert code.count(f"static void {entry.call_target}(void)") == 1, (
        "小节只定义一处（命令台不许自带一份副本）"
    )
    # 命令台排在自建件小节**之后**（switch 里直接调它，排在前面就是隐式声明）
    assert code.index(f"static void {entry.call_target}(void)") < code.index(
        "static void hwcheck_console_poll(void)"
    )


def test_custom_rows_are_marked_as_such_in_the_help_and_the_header():
    """帮助与文件头里"哪一件"那一栏：自建件带标注词，库内件那一行一个字不动。

    spec 用户故事 8：学生要一眼看出哪些结论是库内验证过的、哪些只是"按你确认的
    事实试的"。标注词读 `hwcheck_custom` 的单源（`CUSTOM_TAG`），这里不另写一份。
    """
    sections = [_section("led", "l", "复测板载 LED")]
    table = build_console_table(sections, _custom())
    help_text = table.help_text()
    assert "  l  led：复测板载 LED" in help_text, help_text
    assert f"  a  mine_gyro（{CUSTOM_TAG}）：{PLAN_JUDGE}" in help_text, help_text
    code = unescape_c_string("\n".join(render_console_runtime(table)))
    for line in table.help_lines():
        assert line in code, line
    header = unescape_c_string(render_main_c(WITH_CONSOLE, sections, (), _custom()))
    assert f"{table.entries[0].command}  复测 {table.entries[0].label}：" in header
    assert f"{table.entries[1].command}  复测 {table.entries[1].label}：" in header


def test_a_custom_help_line_still_fits_the_line_buffer():
    """**行缓冲守卫**（照 `tests/test_hwcheck.py` 那条先例）：自建件那几行也不许超。

    板上是 `hwcheck_line[128]` 的行缓冲（框架的溢出保护），超了会截断——中文在
    UTF-8 下一字 3 字节，截在字中间就是半个乱码。自建件那一行的长度 = 字符 +
    id + 标注词 + 三档文案之一，三档各判一条（id 取常规长度）。
    """
    devices = (
        _device(id="mine_gyro", register=None, expect=None),      # 只 ping
        _device(id="mine_echo", expect=None),                     # 只回显
        _device(id="mine_judge"),                                 # 板上判定
    )
    table = build_console_table((), _custom(*devices))
    assert len(table.entries) == 3
    for line in table.help_lines():
        size = len(line.encode("utf-8"))
        assert size < 128, f"这一行 {size} 字节，会撞上行缓冲：{line!r}"


def test_console_payload_marks_custom_rows_without_touching_library_rows():
    """检测页载荷：库内件那几项**逐字不动**，自建件多带标注词与名称。

    为什么多出来的键只在自建件那几行（不是每条都补一个 `custom: false`）：
    载荷形状是既有页面与用例的契约，多两个键就改了一次契约；前端按"有没有
    `tag`"读——与 `fx/module.js` 那处"旧载荷无字段 = 保守按库内件"同一条口径。
    """
    sections = [_section("led", "l", "复测板载 LED")]
    payload = console_payload(True, build_console_table(sections, _custom()))
    assert payload["commands"][0] == {
        "command": "l", "slug": "led",
        "description": "复测板载 LED", "echo": "测的是：复测板载 LED",
    }
    assert payload["commands"][1] == {
        "command": "a", "slug": "mine_gyro",
        "description": PLAN_JUDGE, "echo": f"测的是：{PLAN_JUDGE}",
        "tag": CUSTOM_TAG, "name": "卖家给的六轴模块",
    }
    # 没有自建件时载荷逐字与改动前一致（票面第 5 条：既有命令台用例全绿）
    recipe_only = console_payload(True, build_console_table(sections))
    assert recipe_only == console_payload(
        True, build_console_table(sections, ())
    )
    assert [item["command"] for item in recipe_only["commands"]] == ["l"]


def test_two_custom_devices_get_distinct_characters_deterministically():
    """两件自建件各分一个字符，且**纯函数**：同一份输入 → 同一张表。

    分配只依赖输入（配方小节 + 自建件小节的顺序），所以页面（预览）与板上
    （生成）两次装配读到的是同一组字符——不会有"页面说 g、板上认 h"。
    """
    devices = (_device(id="mine_hall", name="霍尔传感器"), _device(id="mine_gyro"))
    first = build_console_table((), _custom(*devices))
    again = build_console_table((), _custom(*devices))
    assert first == again
    assert [entry.command for entry in first.entries] == ["h", "a"]
    assert {entry.slug for entry in first.entries} == {"mine_hall", "mine_gyro"}


def test_running_out_of_command_characters_fails_loudly_at_build_time():
    """分不出字符 = 构建期大声失败，**不静默少一条**（票面第 1 条的后半句）。

    静默少一条的下场：页面上这件写着"敲这个复测"，板上敲了没反应——学生只会
    以为线没插好。所以这里是 400 中文点名是哪一件排不上号。
    """
    devices = tuple(_device(id=f"mine_dev{i}") for i in range(1, 32))
    table = build_console_table((), _custom(*devices))
    assert len(table.entries) == 31, (
        "31 个可用字符刚好分完（36 个字母数字减掉 5 个在池子里的保留字）"
    )
    with pytest.raises(HwCheckError) as excinfo:
        build_console_table((), _custom(*devices, _device(id="mine_overflow")))
    message = str(excinfo.value)
    assert "mine_overflow" in message
    assert "分不到复测字符" in message
    assert "去掉几件" in message, "要给一条出路（不然学生只能猜）"
    # 两个数都要**对得上**（评审抓过：只扣保留字、不扣已占用的，报错读数就是假的）
    assert "一共 31 个" in message, message
    assert "已经占了 31 个" in message, message


def test_a_run_without_custom_devices_keeps_the_old_console_text():
    """一件自建件都没有时，命令台那几行**逐字还是改动前那几句**（票面第 5 条）。

    判据是**改动前的字面量**（不是"新代码等于新代码"——那种断言改前改后都绿，
    评审点名它是摆设）：命令表为空时板上帮助那句、产物文件头那句，本单一个字节
    都不许动。自建件从不声明字符，所以"没有配方命令"在新世界里仍然为真；
    要"统一三处措辞"就得动它们，那就破了票面——取舍记在 `hwcheck_console`
    帮助行那段注释与本工单结论里。
    """
    rendered = render_main_c(SERIAL_NO_COMMAND, _sections_without_commands())
    text = unescape_c_string(rendered)
    assert "这一趟没有配方命令（配方里没声明复测字符）" in text, text
    assert "这一趟没有配方命令（选的器件都没声明复测字符）" in text, text
    # 空自建件参数 = 与改动前的调用形状逐字相同（两条腿：默认参数 / 显式空元组）
    assert render_main_c(SERIAL_NO_COMMAND, _sections_without_commands(), (), ()) == rendered
    assert render_main_c(SERIAL_NO_COMMAND, _sections_without_commands()) == rendered
    assert build_console_table(_sections_without_commands(), ()) == build_console_table(
        _sections_without_commands()
    )


def test_the_library_commands_stay_untouched_with_a_custom_device_in_the_run():
    """既有 `r/y/g/o/b` 那一组**一个字节不动**：自建件进场也只走"追加"这一条路。

    判据同既有那条：那一组 `case` 底下只有 `return;`（原样留给库内
    `debug_cmd_poll()`），而且九个大写 / 小写标签一个不少。
    """
    code = render_main_c(
        WITH_CONSOLE, [_section("led", "l", "复测板载 LED")], (), _custom()
    )
    legacy_block = _case_block(code, "case 'r':")
    assert _called_names(legacy_block) == set(), "既有命令的分支里不许有动作"
    assert "return;" in legacy_block
    for label in ("case 'R':", "case 'y':", "case 'Y':", "case 'g':",
                  "case 'G':", "case 'o':", "case 'O':", "case 'b':", "case 'B':"):
        assert label in code, label


@pytest.mark.parametrize("platform", [PLATFORM_STM32, PLATFORM_MSPM0])
def test_real_library_recipes_and_a_custom_device_share_one_table(platform):
    """真库三件配方 + 一件自建件 = 四个互不相同的字符（读真数据，不手写替身）。"""
    table = build_console_table(_real_sections(platform), _custom())
    assert len(table.entries) == 4
    assert len({entry.command for entry in table.entries}) == 4
    assert table.entries[-1].custom is True
    assert table.entries[-1].slug == "mine_gyro"
    assert table.entries[-1].func_name == "hwcheck_custom_mine_gyro"
    for entry in table.entries[:3]:
        assert entry.custom is False and entry.func_name == ""


# ---------------------------------------------------------------------------
# 组合下的字符分配（工单 hwcheck-specialize/07 立的守卫）
# ---------------------------------------------------------------------------
#
# 为什么单独立一条：`build_console_table` 的让位是**逐件**分配的，"两件不撞"不等于
# "三件不撞"。批次 E（工单 07）落地时把**六件**一起勾就撞死过一组真组合
# （`ads1115` + `at24c02` + `bmp180` + `pca9685` + `sgp30` + `sht30`：`sht30` 的
# 首选 `e` 被 `at24c02` 拿走、候选 `n` / `z` 又分别被 `pca9685` / `sgp30` 拿走 ⇒
# 构建期 400）。根因不是哪一件写错，而是**候选池整体太浅**——修法 = 每条配方补一个
# 共享后备池（`probe-console-combos.py` 的第 1 问就是这条守卫的量具）。
#
# 射程取 `|S| <= 3` 全子集 + 固定种子的更大组合抽样：全子集穷举到 6 要跑 45 万组、
# 单条用例跑不完（那件事归探针），而**任何**一组的撞车都要能被这一条抓住——
# 抽样是固定种子的，红了就是可复现的红，不是随机闪。
#
# ⚠ **抽样规模封顶 8 件，不跟着库内专精件数长**：字符池一共 31 个（还要扣掉 6 个保留字），
# "把库里二十几件全勾上"这条**容量天花板**是既有边界（本批前就撞，见 `backlog.md`
# 的字符池账），不是这条守卫该断言的事——把封顶写成 `len(slugs)` 会让用例随库长大的
# 某一天突然红在一个与本条无关的理由上。

_CONSOLE_MATRIX_MAX = 3        # 全子集穷举的规模上界
_CONSOLE_MATRIX_SAMPLE_MAX = 8  # 抽样组合的规模上界（见下）
_CONSOLE_MATRIX_TRIALS = 60    # 更大组合的抽样次数（固定种子）
_CONSOLE_MATRIX_SEED = 20260925


def _real_catalog():
    """真库 → （配方目录, manifest 清单）。两平台共用，加载一次。"""
    from contest_generator.hwcheck_recipe import load_recipes
    from contest_generator.library import list_modules

    modules = REPO / "library" / "modules"
    manifests = list_modules(modules)
    return load_recipes(modules, manifests), manifests


def _specialized(platform: str, catalog, manifests) -> list[str]:
    from contest_generator.hwcheck_recipe import resolve_sections

    every = [m.slug for m in manifests]
    return [section.slug for section in resolve_sections(platform, every, catalog, manifests)]


@pytest.mark.parametrize("platform", [PLATFORM_STM32, PLATFORM_MSPM0])
def test_the_whole_specialized_set_of_one_platform_builds_one_console_table(platform):
    """**全勾满**也要建得出命令表（工单 hwcheck-hardening/05）。

    为什么单独立一条：上面那条只穷举 `|S| <= 3` + 固定种子抽样到 8 件——小规模全绿，
    而"把库里该平台的专精件**一次全勾上**"这一档**必然撞车**（实测 stm32 到第 23 件、
    mspm0 到第 26 件就排不上号，报错只说"去掉几件"），学生连一次验完整套硬件都做不到。

    根因不是哪一件写错：命令空间 31 个字符里，**只有 25 个**被任何配方声明过
    （`4 5 6 7 8 9` 六个池位没人用过）——本单把没人用过的池位**纯追加**进候选面，
    这一档从此建得出表。判据 = 全平台专精件一次全选，表内字符互不相同、
    且**每一件**都拿到字符（不是"前面几件有、后面几件没有"）。
    """
    from contest_generator.hwcheck_recipe import resolve_sections

    catalog, manifests = _real_catalog()
    slugs = _specialized(platform, catalog, manifests)
    assert len(slugs) >= 25, f"{platform} 专精件太少（{len(slugs)}），这条守卫没意义了"
    sections = resolve_sections(platform, list(slugs), catalog, manifests)
    table = build_console_table(sections)
    commands = [entry.command for entry in table.entries]
    assert len(commands) == len(slugs), (
        f"{platform} 全勾 {len(slugs)} 件，只有 {len(commands)} 件拿到字符"
    )
    assert len(set(commands)) == len(commands), f"{platform} 全勾时字符撞车：{commands}"


def test_command_pool_size_in_the_error_copy_is_the_real_allocatable_count():
    """报错文案里那个「可用字符一共 N 个」的 N，必须是**真能分配**的字符数（工单 hwcheck-hardening/05）。

    为什么单独立一条：`_pool_description()` 报的是 `len(COMMAND_POOL)`（31），而分配只能在
    **各配方声明过的**首选 / 候选里挑——本单之前只声明了 25 个，于是那句话把池子说大了 6 个，
    正好把人往"还能再勾几件"引（实测撞车就在第 23 / 26 件）。

    判据 = 真库全部配方的声明面并集 == 命令池本身。少一个字符当场红：不是"配方写错了"，
    而是**那句文案在撒谎**——要么把这个池位写进某条配方的候选，要么把文案改成实报可分配数。
    """
    catalog, _manifests = _real_catalog()
    declared: set[str] = set()
    for catalog_entry in catalog.values():
        for section in catalog_entry.sections.values():
            if section.console is None:
                continue
            declared.add(section.console.command.lower())
            declared.update(char.lower() for char in section.console.candidates)
    pool = set(COMMAND_POOL)
    assert declared <= pool, f"配方声明了池子外的字符：{sorted(declared - pool)}"
    missing = sorted(pool - declared)
    assert not missing, (
        f"命令池里有 {len(missing)} 个字符从没被任何配方声明过：{missing}——"
        "报错文案说的「可用字符一共 N 个」会因此比实际能分配的多，学生照着它判断还能不能加件"
    )


@pytest.mark.parametrize("platform", [PLATFORM_STM32, PLATFORM_MSPM0])
def test_console_capacity_note_speaks_only_when_the_pool_is_nearly_used_up(platform):
    """余量提示三条口径（工单 hwcheck-hardening/05）：平时不吭声 / 快满时说真数 / 分不出来时不说话。

    为什么要有这一句：字符分不出来是**生成前 400**，学生在那之前没有任何信号——
    只有按了「生成」才知道。但也不能常驻一句警告：平时它必须是空串。
    """
    from contest_generator.hwcheck_recipe import resolve_sections

    catalog, manifests = _real_catalog()
    slugs = _specialized(platform, catalog, manifests)

    # ① 小组合（两件）：离上限很远 → 不吭声
    few = resolve_sections(platform, list(slugs[:2]), catalog, manifests)
    assert console_capacity_note(few) == ""

    # ② 全勾满：提示的有无严格跟着阈值走，且出现时四个数都如实（占了几件 / 池子多大 / 还剩几个）
    every = resolve_sections(platform, list(slugs), catalog, manifests)
    table = build_console_table(every)
    used = len(table.entries)
    remaining = len(COMMAND_POOL) - used
    note = console_capacity_note(every)
    if remaining > CONSOLE_CAPACITY_WARN_REMAINING:
        assert note == "", f"还剩 {remaining} 个字符（阈值 {CONSOLE_CAPACITY_WARN_REMAINING}）不该吭声"
    else:
        assert note, f"{platform} 全勾 {used} 件、只剩 {remaining} 个字符，应当事前提示"
        assert f"这一趟 {used} 件" in note and f"只剩 {remaining} 个" in note
        assert f"可用字符一共 {len(COMMAND_POOL)} 个" in note
        assert "去掉" in note or "换一组" in note, "要给一条出路（点名留给 400 那份文案）"

    # ③ 阈值本身要**小**：不然每勾一件都挂着一句警告，学生会当噪音
    assert 1 <= CONSOLE_CAPACITY_WARN_REMAINING <= 4


def test_console_capacity_note_is_silent_when_allocation_itself_fails():
    """分不出来时**不吭声**：端点会走 400 的完整点名（谁排不上号 / 被谁占 / 出路）。

    构造：两件都声明同一个字符、都没有候选 → 分配必然失败（`build_console_table` 抛红）。
    页面这时候不该再说一句"字符快用完了"——那会与 400 那份文案变成两个口径。
    """
    def only(char: str, slug: str) -> RecipeSection:
        return RecipeSection(
            slug=slug, platform=PLATFORM_STM32,
            console=RecipeConsole(command=char, description="复测"),
        )

    sections = [only("l", "led"), only("l", "beep")]
    with pytest.raises(HwCheckError):
        build_console_table(sections)
    assert console_capacity_note(sections) == "", (
        "分不出来的时候页面不该再说一句——400 那份文案已经把谁排不上号、被谁占、出路都点名了"
    )


@pytest.mark.parametrize("platform", [PLATFORM_STM32, PLATFORM_MSPM0])
def test_any_small_selection_of_real_recipes_builds_one_console_table(platform):
    """真库**任意小组合**（|S| <= 3 全子集）都建得出命令表，且分配自洽。

    自洽的三条（任一不成立都是"页面上写着敲 x、板上不认 x"这类错位）：

    1. 一表之内字符互不相同；
    2. 每件拿到的字符在**它自己声明的**首选 / 候选里（让位只在声明面内让）；
    3. 页面载荷（`console_payload`）与板上分派（`render_console_runtime` 的 `case`）
       读到的是**同一个**分配后的字符。
    """
    import itertools
    import random

    from contest_generator.hwcheck_recipe import resolve_sections

    catalog, manifests = _real_catalog()
    slugs = _specialized(platform, catalog, manifests)
    assert len(slugs) >= 3, f"{platform} 专精件太少（{len(slugs)}），这条守卫没意义了"

    rng = random.Random(_CONSOLE_MATRIX_SEED)
    picks = [list(combo) for size in range(2, _CONSOLE_MATRIX_MAX + 1)
             for combo in itertools.combinations(slugs, size)]
    for _ in range(_CONSOLE_MATRIX_TRIALS):
        size = rng.randint(_CONSOLE_MATRIX_MAX + 1,
                           min(_CONSOLE_MATRIX_SAMPLE_MAX, len(slugs)))
        picks.append(rng.sample(slugs, size))

    for picked in picks:
        sections = resolve_sections(platform, picked, catalog, manifests)
        table = build_console_table(sections)           # 撞车 = 这里当场抛 HwCheckError
        commands = [entry.command for entry in table.entries]
        assert len(set(commands)) == len(commands), (
            f"{platform} 组合 {'、'.join(picked)} 里有两件分到同一个字符：{commands}"
        )
        shown = {item["slug"]: item["command"]
                 for item in console_payload(True, table)["commands"]}
        code = "\n".join(render_console_runtime(table))
        for entry in table.entries:
            declared = entry.slug
            section = next(s for s in sections if s.slug == declared)
            allowed = {section.console.command.lower(),
                       *(c.lower() for c in section.console.candidates)}
            assert entry.command in allowed, (
                f"{platform} 组合 {'、'.join(picked)}：{entry.slug} 拿到 {entry.command!r}，"
                f"不在它声明的 {sorted(allowed)} 里"
            )
            assert shown[entry.slug] == entry.command, (
                f"{platform} 组合 {'、'.join(picked)}：{entry.slug} 页面显示 "
                f"{shown[entry.slug]!r}、板上认 {entry.command!r}"
            )
            assert f"case '{entry.command}':" in code, (
                f"{platform} 组合 {'、'.join(picked)}：{entry.slug} 的 {entry.command!r} "
                "在板上分派里没有对应的 case（敲了不会认）"
            )


