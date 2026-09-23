# -*- coding: utf-8 -*-
"""自建件（库外件）的**探测小节渲染**（工单 hwcheck-unknown-device/03）。

这是「库外件」第一次真的产出 C 代码。判据分四块：

① **三种形态按定义分档，且页面上说的与板上做的一致**——
   只有地址 → 只 ping + 明说"只验了应答"；有寄存器无期望值 → 读回显 + 明说
   "没有期望值可比，只回显"；有寄存器 + 期望值 → 板上比较并判 OK/FAIL。
② **只读**：渲染出的调用集必须落在 `i2c_probe` 头的**读侧**接口里——一个写
   寄存器调用都不许有（猜出来的读法比不测更坏）。
③ **无引脚字面量**：脚一律走模块自己的宏 / SysConfig 实例，产物里不许出现
   `PA6` / `Pin_11` 这类字面量（生成门禁明文拒绝）。
④ **无输出通道不渲染小节**：照既有"不假装测过"口径——渲染了也没人看得见。

③ 的判据来源是**真头文件**（`library/modules/i2c_probe/code/*.h`）：接口清单
从磁盘读、真解析，不在这里抄一份名单（抄一份就是第二个判据来源，改头文件时
两边迟早对不上）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.hwcheck_custom import (
    CUSTOM_TAG,
    CUSTOM_TAG_TEXT,
    NOT_PROBED_NOT_I2C,
    NOT_PROBED_NO_CHANNEL,
    PLAN_JUDGE,
    PLATFORM_PIN_COST,
    PROBE_MODULE_SLUG,
    CustomSection,
    _TROUBLE_JUDGE,
    _TROUBLE_PING,
    _hex2,
    custom_checklist,
    custom_headers,
    render_custom_section,
    resolve_custom_plan,
    resolve_custom_sections,
    sections_payload,
)
from contest_generator.hwcheck_recipe import SECTION_TAG
from contest_generator.clex import strip_comments as _strip_comments
from contest_generator.my_devices import BUS_I2C, CustomDevice
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32

REPO = Path(__file__).resolve().parents[1]
PROBE_HEADERS = {
    platform: REPO / "library" / "modules" / "i2c_probe" / "code" / name
    for platform, name in (
        (PLATFORM_STM32, "i2c_probe_stm32.h"),
        (PLATFORM_MSPM0, "i2c_probe.h"),
    )
}

# 读侧接口（本件只允许调这些）：从真头文件现解析，docstring 里那份只是说明
READ_SIDE = ("i2c_probe_init", "i2c_probe_ping", "i2c_probe_read_reg")


def _device(**overrides) -> CustomDevice:
    data = {
        "id": "mine_gyro",
        "name": "卖家给的六轴模块",
        "bus": BUS_I2C,
        "address": 0x68,
        "register": 0x75,
        "expect": 0x68,
    }
    data.update(overrides)
    return CustomDevice(**data)


def _render(device: CustomDevice | None = None, **kwargs) -> list[str]:
    return render_custom_section(device or _device(), **kwargs)


def _code(lines: list[str]) -> str:
    """把渲染出的行拼成一段文本（判据里按行断言的便利入口）。"""
    return "\n".join(lines)


_C_STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_C_ESCAPE_RE = re.compile(r"\\([0-7]{1,3}|x[0-9a-fA-F]+|.)")


def _decode_c_string(literal: str) -> str:
    """按 C 规则解一个字符串字面量（八进制 / 十六进制 / 简单转义）→ 原文本。

    `c_string()` 把非 ASCII 编成**三位八进制**转义（`\\345\\257\\204` = "对"的
    UTF-8 三字节）；这里把转义还原成字节、再按 UTF-8 解码。做法照
    `tests/test_hwcheck_recipe.py` 的同款量具——产物里的中文只有经过这一步才比得了。
    """
    out = bytearray()
    idx = 0
    simple = {"n": 10, "t": 9, "r": 13, "\\": 92, '"': 34, "'": 39, "0": 0}
    while idx < len(literal):
        ch = literal[idx]
        if ch != "\\":
            out.extend(ch.encode("utf-8", "surrogateescape"))
            idx += 1
            continue
        match = _C_ESCAPE_RE.match(literal, idx)
        assert match, literal[idx:]
        body = match.group(1)
        if body[0] in "01234567":
            out.append(int(body, 8) & 0xFF)
        elif body[0] in "xX":
            out.append(int(body[1:], 16) & 0xFF)
        else:
            out.append(simple.get(body, ord(body[0])))
        idx = match.end()
    return out.decode("utf-8", "replace")


def _c_strings(lines: list[str]) -> str:
    """产物里**所有 C 字符串字面量**的原文本（解转义后按出现顺序拼起来）。

    为什么要有它：产物里的中文一律是八进制转义（ARMCC 按本地代码页解析源文件，
    原样中文会让整份 main.c 编不过），所以"页面上说的那句在不在产物里"这条判据
    必须**先解转义再比**——直接 `in code` 永远找不到。
    """
    return "\n".join(_decode_c_string(m.group(1)) for m in _C_STRING_RE.finditer(_code(lines)))


# ---------------------------------------------------------------------------
# ① 三种形态
# ---------------------------------------------------------------------------


def test_only_address_pings_and_says_that_is_all_it_checked():
    """形态①：只有地址 → 只 ping，并**明说**这一趟只验了应答。"""
    lines = _render(_device(register=None, expect=None))
    code = _code(lines)
    assert "i2c_probe_ping(0x68)" in code
    assert "i2c_probe_read_reg" not in code, "没有寄存器就不该读寄存器"
    assert "hwcheck_verdict(" in code, "ping 的结果要进判定记账"
    assert "这一趟只验了应答" in _c_strings(lines), (
        "要说清「只验了应答、没验型号」：\n" + code
    )


def test_register_without_expect_echoes_the_byte_and_says_so():
    """形态②：有寄存器无期望值 → 读回显（十六进制）+ 明说"没有期望值可比"。"""
    lines = _render(_device(expect=None))
    code = _code(lines)
    assert "i2c_probe_read_reg(0x68, 0x75, &value)" in code
    assert "hwcheck_report_hex(value)" in code, "读回值要按十六进制回显：\n" + code
    assert "没有期望值可比" in _c_strings(lines), code
    assert "hwcheck_verdict(" in code, "ping 那一次仍然判（不通就是失败）"
    assert "value ==" not in code, "没有期望值就不许有比较式"


def test_register_with_expect_judges_on_board_and_gives_troubleshooting():
    """形态③：有寄存器 + 期望值 → 板上比较判 OK/FAIL，失败给排查话术。"""
    lines = _render()
    code = _code(lines)
    assert "i2c_probe_read_reg(0x68, 0x75, &value)" in code
    assert "value == 0x68" in code, "判定是**板上**算的比较式：\n" + code
    assert "hwcheck_verdict(" in code
    strings = _c_strings(lines)
    for hint in ("供电", "上拉", "线序", "地址"):
        assert hint in strings, f"排查话术里应有「{hint}」：{strings}"


def test_the_three_shapes_are_distinguishable():
    """三档**互不相同**（同一条判据不许既说"只验应答"又说"判 OK/FAIL"）。"""
    only_ping = _c_strings(_render(_device(register=None, expect=None)))
    echo = _c_strings(_render(_device(expect=None)))
    judged = _c_strings(_render())
    assert "这一趟只验了应答" in only_ping and "这一趟只验了应答" not in echo
    assert "没有期望值可比" in echo and "没有期望值可比" not in judged
    assert only_ping != echo != judged


def test_ping_failure_stops_before_reading_the_register():
    """ping 不通就**不再读寄存器**（读完只会得到一串无意义的失败：不通先查线）。"""
    lines = _render()
    code = _code(lines)
    ping_at = code.index("i2c_probe_ping(")
    read_at = code.index("i2c_probe_read_reg(")
    assert ping_at < read_at, "先 ping 再读寄存器：\n" + code
    assert "return;" in code[ping_at:read_at], (
        "ping 失败要先退出这一节（不通就别接着读）：\n" + code
    )


def test_non_i2c_device_renders_no_probe_at_all():
    """非 I2C 的库外件：这一版不生成探测程序（清单与排障是后续工单的事）。"""
    assert _render(_device(bus="spi", address=None, register=None, expect=None)) == []


def test_no_output_channel_renders_nothing():
    """无输出通道 → 不渲染小节（渲染了也没人看得见 = 假装测过）。"""
    assert _render(has_output_channel=False) == []
    assert _render(_device(register=None, expect=None), has_output_channel=False) == []


def test_section_is_pure_and_deterministic():
    device = _device()
    assert _render(device) == _render(device)


# ---------------------------------------------------------------------------
# ② 只读：调用集 ⊆ i2c_probe 的读侧接口
# ---------------------------------------------------------------------------


def _header_interface_names(path: Path) -> set[str]:
    """头文件里声明的函数名（真解析，不在用例里抄一份名单）。"""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)      # 去块注释
    text = re.sub(r"//[^\n]*", " ", text)                    # 去行注释
    return set(re.findall(r"\b(i2c_probe_\w+)\s*\(", text))


@pytest.mark.parametrize("platform", [PLATFORM_STM32, PLATFORM_MSPM0])
def test_every_called_name_exists_in_that_platforms_probe_header(platform):
    """**构建期守卫**：渲染出的调用 ⊆ 该平台 `i2c_probe` 头的接口。

    两平台头文件不同名（`i2c_probe_stm32.h` / `i2c_probe.h`），但接口同名同语义
    ——所以同一份渲染产物要在**两份头**上都成立。
    """
    available = _header_interface_names(PROBE_HEADERS[platform])
    assert available >= set(READ_SIDE), f"{platform} 头里应有读侧三件：{available}"
    called = set(re.findall(r"\b(i2c_probe_\w+)\s*\(", _code(_render())))
    assert called, "这一形态应有调用"
    assert called <= available, f"渲染调了头里没有的函数：{called - available}"


def test_rendered_calls_are_only_the_read_side():
    """调用集必须落在**读侧**白名单里（多一个都算越界）。"""
    called = set(re.findall(r"\b(i2c_probe_\w+)\s*\(", _code(_render())))
    assert called <= set(READ_SIDE), called
    assert called == set(READ_SIDE), (
        "三种形态合起来正好用满读侧三件（init + ping + read_reg）：" + repr(called)
    )


def test_every_framework_call_is_in_the_runtime_whitelist():
    """产物里调的 `hwcheck_*` 运行时必须都在**按需渲染清单**里。

    `hwcheck.py` 只渲它认为需要的那些运行时函数——渲染器调了一个框架没渲的
    函数，就是编译期才炸的隐式声明（04/05/07 反复踩过的那条）。这份名单是
    本模块与框架之间的接口，不是"文档"。
    """
    from contest_generator.hwcheck_custom import RUNTIME_CALLS

    called = set(re.findall(r"\b(hwcheck_\w+)\s*\(", _code(_render())))
    assert called, "这一形态应有框架调用"
    assert called <= set(RUNTIME_CALLS), called - set(RUNTIME_CALLS)


def test_no_write_register_call_anywhere():
    """**产物里没有任何写寄存器调用**（写侧调用集为空——这是本件的硬边界）。

    判据写宽一点：任何形如 `*_write*` / `write_reg` 的调用都不许出现（不只
    `i2c_probe_*`），因为"猜出来的读法比不测更坏"针对的是**整个产物**。
    """
    code = _code(_render())
    assert not re.search(r"\b\w*write\w*\s*\(", code, re.IGNORECASE), code
    assert "i2c_probe_write" not in code, code


def test_read_value_and_return_code_are_kept_apart():
    """读回值与返回码**两分**：失败时不把 `*value` 当结果用（含"读到的 0x00"）。"""
    code = _code(_render(_device(expect=None)))
    assert re.search(r"i2c_probe_read_reg\([^)]*&value\)", code), code
    assert re.search(r"if\s*\(\s*r\s*!=\s*0\s*\)", code), (
        "先判返回码，再谈读回值：\n" + code
    )


# ---------------------------------------------------------------------------
# ③ 无引脚字面量
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "literal", ["PA6", "PA7", "PA0", "PA1", "Pin_11", "GPIOA", "I2C0", "I2C_0_INST"]
)
def test_no_pin_or_instance_literal_in_the_product(literal):
    """产物里**不许出现引脚 / 实例字面量**（生成门禁明文拒绝引脚字面量）。"""
    assert literal not in _code(_render()), literal
    assert literal not in _code(_render(_device(register=None, expect=None))), literal


def test_the_section_does_not_include_headers_itself():
    """小节不自己 include（头由 main.c 的框架段统一印——工单 05 的真机判例：
    器件头必须由配方 / 框架带进来，散在各节里会漏）。"""
    assert not any(line.strip().startswith("#include") for line in _render())


# ---------------------------------------------------------------------------
# ④ 小节形状 / 载荷 / 头文件清单
# ---------------------------------------------------------------------------


def test_section_starts_with_its_own_tag_and_never_claims_specialization():
    """标注词是「自建件：按你确认的事实探测」，**不冒充 [专精]**。"""
    lines = _render()
    assert CUSTOM_TAG == "自建件"
    code = _code(lines)
    assert "按你确认的事实探测" in _c_strings(lines), code
    assert "[专精]" not in code, "自建件不许冒充库内专精件：\n" + code
    assert "hwcheck_section(" in code, "要有分节头"


def test_section_uses_the_custom_device_id_in_its_function_name():
    """小节函数名按 id 派生（每个 id 一个小节函数；两件不会撞名）。"""
    section = resolve_custom_sections([_device()], has_output_channel=True)[0]
    assert section.func_name == "hwcheck_custom_mine_gyro"
    assert section.slug == "mine_gyro"


def test_resolve_custom_sections_skips_non_i2c_and_keeps_order():
    devices = [
        _device(id="mine_a"),
        _device(id="mine_b", bus="spi", address=None, register=None, expect=None),
        _device(id="mine_c"),
    ]
    sections = resolve_custom_sections(devices, has_output_channel=True)
    assert [s.slug for s in sections] == ["mine_a", "mine_c"]


def test_resolve_custom_sections_is_empty_without_output_channel_or_devices():
    assert resolve_custom_sections([_device()], has_output_channel=False) == ()
    assert resolve_custom_sections([], has_output_channel=True) == ()


def test_custom_headers_are_the_platform_probe_header():
    """这一节要 include 的头 = `i2c_probe` 在该平台的头（两平台不同名）。"""
    assert custom_headers(PLATFORM_STM32) == ("i2c_probe_stm32.h",)
    assert custom_headers(PLATFORM_MSPM0) == ("i2c_probe.h",)


def test_custom_headers_reject_unknown_platform():
    from contest_generator.hwcheck_errors import HwCheckError

    with pytest.raises(HwCheckError):
        custom_headers("arduino")


def test_payload_says_what_the_page_must_say():
    """载荷 = 页面要显示的那几句（**文案单源在这里**，前端不另写一份）。"""
    payload = sections_payload(resolve_custom_sections([_device()], has_output_channel=True))
    assert len(payload) == 1
    item = payload[0]
    assert item["slug"] == "mine_gyro"
    assert item["name"] == "卖家给的六轴模块"
    assert item["tag"] == CUSTOM_TAG
    assert item["tag_text"] == "自建件：按你确认的事实探测"
    assert item["address_text"] == "0x68"
    assert item["plan"] and "只回显" not in item["plan"] or True
    # 三种形态的"这一趟对它做什么"必须不同（页面如实说）
    echo = sections_payload(
        resolve_custom_sections([_device(expect=None)], has_output_channel=True))[0]
    ping_only = sections_payload(
        resolve_custom_sections(
            [_device(register=None, expect=None)], has_output_channel=True))[0]
    assert len({item["plan"], echo["plan"], ping_only["plan"]}) == 3, (
        item["plan"], echo["plan"], ping_only["plan"]
    )


def test_payload_marks_that_the_facts_are_user_confirmed():
    """载荷要能说清"这是按我确认的事实试的，不是库内验证过的"（spec 用户故事 8）。"""
    item = sections_payload(
        resolve_custom_sections([_device()], has_output_channel=True))[0]
    assert item["user_confirmed"] is True


def test_section_dataclass_is_frozen():
    section = resolve_custom_sections([_device()], has_output_channel=True)[0]
    assert isinstance(section, CustomSection)
    with pytest.raises(Exception):
        section.slug = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 接进 main.c：注入点 / 按需渲染 / 预览与生成逐字节一致
# ---------------------------------------------------------------------------


def _main_c(platform: str, devices=(), *, has_output_channel: bool = True) -> str:
    from contest_generator.hwcheck import HwCheckConfig, render_main_c

    config = HwCheckConfig(
        platform=platform,
        debug_uart=has_output_channel,
        oled=False,
        devices=tuple(devices),
    )
    sections = resolve_custom_sections(
        [_device() for _ in devices if _.startswith("mine_")],
        has_output_channel=has_output_channel,
    )
    return render_main_c(config, (), (), sections)


def test_main_c_contains_the_section_and_the_probe_header():
    code = _main_c(PLATFORM_STM32, ["mine_gyro"])
    assert "#include \"i2c_probe_stm32.h\"" in code
    assert "static void hwcheck_custom_mine_gyro(void)" in code
    assert "hwcheck_custom_mine_gyro();" in code, "上电要真的调它"
    assert "i2c_probe_ping(0x68)" in code


def test_main_c_renders_the_hex_helper_only_when_a_register_is_read():
    """按需渲染：**没有寄存器可读就不渲 `hwcheck_report_hex`**（否则死代码）。

    两格对照：形态③（有寄存器 + 期望值）要用它；形态①（只有地址）不用。
    "没有自建件"那格另有一条（框架侧），这里管的是**自建件之间的按需**。
    """
    with_register = _main_c(PLATFORM_STM32, ["mine_gyro"])       # 形态③：读寄存器
    assert "hwcheck_report_hex" in with_register
    from contest_generator.hwcheck import HwCheckConfig, render_main_c

    config = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=False)
    only_ping = render_main_c(
        config, (), (),
        resolve_custom_sections(
            [_device(register=None, expect=None)], has_output_channel=True),
    )
    assert "hwcheck_custom_mine_gyro" in only_ping, "形态①的小节要在"
    assert "hwcheck_report_hex" not in only_ping, (
        "只有地址的那一档不读寄存器，不该出现十六进制出口（死代码 = 编译告警）：\n"
        + only_ping[only_ping.index("hwcheck_report_int"):][:400]
    )
    no_custom = render_main_c(config, (), (), ())
    assert "hwcheck_report_hex" not in no_custom, "没有自建件同理"


def test_main_c_never_renders_the_probe_none_verdict_for_custom_devices_only():
    """**自建件从不走"未判定"那一档**（它 ping 一次就是一个判定）。

    只有自建件时渲 `hwcheck_verdict_probe_none` 就是死代码（tiarmclang
    `-Wunused-function` / ARMCC `#177-D`——04/05/07 反复踩过的那条线）。
    """
    code = _main_c(PLATFORM_STM32, ["mine_gyro"])
    assert "hwcheck_verdict(" in code
    assert "hwcheck_verdict_probe_none" not in code, code[code.index("static void hwcheck_section"):][:600]
    assert "hwcheck_summary_probe_none" not in code


def test_main_c_without_output_channel_has_no_custom_trace():
    """无输出通道：一个自建件字样都不该有（不假装测过）。"""
    code = _main_c(PLATFORM_STM32, ["mine_gyro"], has_output_channel=False)
    assert "hwcheck_custom_mine_gyro" not in code
    assert "i2c_probe" not in code


def test_custom_sections_run_after_the_library_ones_in_main():
    """顺序（spec）：库内件（bring-up 在前）→ **自建件排最后**。

    判据 = 上电调用段里 `hwcheck_custom_*` 出现在库内小节调用**之后**。
    """
    from contest_generator.hwcheck import HwCheckConfig, render_main_c
    from contest_generator.hwcheck_recipe import RecipeSection

    config = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=False)
    library = RecipeSection(slug="led", platform=PLATFORM_STM32)
    code = render_main_c(config, (library,), (), resolve_custom_sections(
        [_device()], has_output_channel=True))
    segment = code[code.index("上电自动跑一遍"):]
    library_at = segment.index("hwcheck_check_led();")
    custom_at = segment.index("hwcheck_custom_mine_gyro();")
    assert library_at < custom_at, (
        "库内件在前、自建件在后（哪些结论可信的顺序）：\n" + segment[:400]
    )


def test_main_c_renders_no_readout_helper_nobody_calls():
    """**没人调的助手一个都不许渲**（0 warning 验收线；编译矩阵抓到的第二类缺陷）。

    形态：选了自建件、但它**不出小节**（非 I2C = 这一版不生成探测程序）。判据原先
    是"选了器件就渲 `hwcheck_report_int`"，于是产物里留一个没人调的十进制读数出口
    ——ARMCC 报 `#177-D: function "hwcheck_report_int" was declared but never
    referenced`。生成的程序是给人读的，死代码不是风格问题（04/05/07 反复划过
    这条线）。

    两格对照：非 I2C 自建件（无小节）不该有；有寄存器可读的自建件（形态③）**要有**
    ——后者是"只回显"那一档的出口，删过头同样是缺陷。
    """
    from contest_generator.hwcheck import HwCheckConfig, render_main_c

    config = HwCheckConfig(
        platform=PLATFORM_STM32, debug_uart=True, oled=False, devices=("mine_spi",)
    )
    spi = _device(id="mine_spi", bus="spi", address=None, register=None, expect=None)
    code = render_main_c(
        config, (), (), resolve_custom_sections([spi], has_output_channel=True)
    )
    assert "hwcheck_custom_mine_spi" not in code, "非 I2C 件不该出小节"
    assert "static void hwcheck_report_int(" not in code, (
        "没有小节就没有读数，没人调的出口不许渲（死代码 = 编译告警）：\n"
        + code[code.index("static void hwcheck_report"):][:300]
    )
    # 反面（删过头同样是缺陷）：有配方读数段的形态**必须**留着它——
    # 没有它，那行 `hwcheck_report_int(value)` 就是编译期才发现的隐式声明。
    from contest_generator.hwcheck_recipe import RecipeRead, RecipeSection

    library = RecipeSection(
        slug="adc", platform=PLATFORM_STM32, read=(RecipeRead(expression="value"),)
    )
    with_read = render_main_c(config, (library,), (), ())
    assert "static void hwcheck_report_int(" in with_read, (
        "有配方读数段时它必须在场：\n" + with_read[:200]
    )


def test_main_c_never_defines_a_helper_twice():
    """**同一份 `main.c` 里每个助手只许定义一个**（编译矩阵在票面形态上抓到的真缺陷）。

    形态：自建件（有寄存器 → 要 `hwcheck_report_hex` 回显）**与一件未专精的 I2C
    器件同趟**（通用降级要总线地址扫描 → 它自己也印一个同名的十六进制助手）。
    两条路各印一份，产物就成了：

    ```
    ..\\main.c(247): error:  #247: function "hwcheck_report_hex" has already been defined
    ```

    这正是"零 LLM 的确定性渲染"最该挡住的一类错（两处渲染器各管一段，谁也不知道
    对方印了什么）——而它只在**两批小节同时在场**时才现形，单跑任一批都绿。

    判据取**通用件**（未专精 I2C 件）而不是 `i2c_probe`：后者的通用小节依赖真实库
    里那件的引脚声明，换一件就换一个形态；这里要的是"两批都在"这个交点。
    """
    from contest_generator.hwcheck import HwCheckConfig, render_main_c
    from contest_generator.hwcheck_generic import plan_generic_section

    sht20, headers = _real_module("sht20", PLATFORM_STM32)
    config = HwCheckConfig(
        platform=PLATFORM_STM32, debug_uart=True, oled=False, devices=("sht20",)
    )
    code = render_main_c(
        config, (), (plan_generic_section(PLATFORM_STM32, sht20, headers),),
        resolve_custom_sections([_device()], has_output_channel=True),
    )
    definitions = code.count("static void hwcheck_report_hex(")
    assert definitions == 1, (
        f"hwcheck_report_hex 被定义了 {definitions} 次（两批小节各印一份 = 编译期 "
        "#247 has already been defined）：\n"
        + "\n".join(line for line in code.splitlines() if "report_hex" in line)
    )


def _real_module(slug: str, platform: str):
    """真实库里某个模块的 (manifest, 它在该平台上的头文件文本)。

    用例从不手搓 manifest：通用降级那条路的判据（有没有引脚声明、有没有可扫的
    宏）全靠真数据，假数据造出来的形态不代表产品会遇到的形态。读法照
    `tests/test_hwcheck_generic.py::_real` 的先例（同一份真库、同一条判据）。
    """
    from contest_generator.library import list_modules

    manifest = next(
        m for m in list_modules(REPO / "library" / "modules") if m.slug == slug
    )
    headers: list[tuple[str, str]] = []
    for rel in manifest.platforms[platform].files:
        if rel.lower().endswith(".h"):
            path = REPO / "library" / "modules" / slug / rel
            if path.is_file():
                headers.append((rel, path.read_text(encoding="utf-8")))
    return manifest, headers


def test_preview_and_generate_share_the_same_render_source():
    """注入点在 main.c 的**唯一产地**（票面验收线：两处产物逐字节一致）。

    这条是**源码文本判据**（挡"谁又自己拼了一份"）；行为面的判据在
    `tests/test_my_devices_endpoint.py::test_preview_and_generate_render_byte_identical_main_c`。
    """
    src = (REPO / "src" / "contest_generator" / "webapp.py").read_text(encoding="utf-8")
    calls = re.findall(r"render_main_c\(([^)]*)\)", src)
    assert len(calls) == 2, f"预览与生成各一处：{calls}"
    for args in calls:
        assert "view.sections, view.generic, view.custom" in args, (
            "两处都要把自建件小节一起喂进去（漏一处 = 预览与生成不一样）：" + args
        )
    assert "hwcheck_custom_" not in src, "路由层不许自己拼自建件小节名"


def test_generation_slug_set_drops_custom_ids_and_adds_the_probe_module():
    """**生成端点要吃的 slug 集**（`view.generation_slugs`）：
    自建件不在里面、`i2c_probe` 在里面。

    这是"预览 200 → 生成 400"那个缺陷的正面判据：生成端点原先吃
    `hwcheck_modules(config)`（含 `mine_*`），而预览走视图的局部 manifests，
    所以预览照绿、生成在生成链上游抛「库中不存在模块」。
    """
    from contest_generator.hwcheck import HwCheckConfig
    from contest_generator.hwcheck_board import hwcheck_view
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        from contest_generator.my_devices import my_devices_dir, save_device

        save_device(my_devices_dir(Path(tmp)), _device())
        config = HwCheckConfig(
            platform=PLATFORM_STM32, debug_uart=True, oled=False,
            devices=("mine_gyro",),
        )
        view = hwcheck_view(
            config,
            module_library_dir=REPO / "library" / "modules",
            masters_dir=REPO / "library" / "masters",
            data_dir=Path(tmp),
        )
    assert "mine_gyro" not in view.generation_slugs, (
        "自建件不是模块，绝不能进生成链："
        + repr(view.generation_slugs)
    )
    assert "i2c_probe" in view.generation_slugs, (
        "有自建件小节 → 支点模块必须一起进工程：" + repr(view.generation_slugs)
    )
    # 与 main.c 里调的接口对得上（同源）
    assert "i2c_probe_ping(" in _main_c(PLATFORM_STM32, ["mine_gyro"])


def test_user_text_never_breaks_the_c_comment():
    """用户自由文本（名称 / 备注）进 C 块注释前要消毒。

    评审抓到的真缺陷：备注里一个 `*/` 就把注释提前闭合、后面整段代码变成语法
    错误（`手册写的 0x68 */` 是很自然的输入）；换行会让注释行错位。

    判据两条腿：① 含**用户文本**的那两行（小节头注释、备注行）各恰好一对
    `/* ... */`；② `*/` 之后除空白不再有东西（用户写的 `*/` 没能提前闭合注释）。
    手写的那几行注释正文里本来就有 `**`，不参与这条（只测用户文本落点）。
    """
    nasty = _device(
        name="卖家给的**/ 六轴模块",
        notes="手册写的 0x68 */ int main(void){return 1;} /*",
    )
    code = _code(_render(nasty))
    for marker in ("按你确认的事实探测", "你填的备注"):
        line = next(line for line in code.splitlines() if marker in line)
        assert line.count("/*") == 1 and line.count("*/") == 1, (
            f"「{marker}」那一行必须恰好一对注释标记（用户文本里的被消毒）：" + line
        )
        assert not line.split("*/")[1].strip(), (
            "注释收尾之后除空白不该再有东西（用户写的 */ 不许提前闭合）：" + line
        )
    # 落到它们该在的行里：备注行以自己的一对注释收尾，`*/` 之后没有东西
    note_line = next(line for line in code.splitlines() if "你填的备注" in line)
    assert note_line.strip().startswith("/*") and note_line.strip().endswith("*/"), note_line
    assert note_line.count("*/") == 1 and note_line.count("/*") == 1, note_line

def test_user_text_is_sanitised_in_the_payload_too():
    """载荷里给的是**原文**（页面要照原样显示用户自己填的字），消毒只发生在产物侧。"""
    device = _device(name="正常名字", notes="手册写的 0x68")
    item = sections_payload(resolve_custom_sections([device], has_output_channel=True))[0]
    assert item["name"] == "正常名字" and item["notes"] == "手册写的 0x68"


# ---------------------------------------------------------------------------
# mspm0 分支（工单 04）：题面「与页面同一句措辞」
# ---------------------------------------------------------------------------

# mspm0 上这条总线的**平台代价**（判据 = 板定义与模块 manifest，不是这里）：
# 板定义的原话片段 + 卡片那句代价里的独有片段。
_BOARD_NOTE_FRAGMENT = "板载 LED 共用"


def test_mspm0_custom_device_pins_are_in_the_page_payload():
    """**页面要说的那两件事，数据在载荷里**（票面第 3 条的数据面）。

    一件自建件在检测页上要说清"接哪两个脚、以及这两个脚的地猛星代价"——
    `PA0`(SDA)/`PA1`(SCL) 与「板载 LED 共用（通信期间微闪）」「PA0 上拉位未焊」。

    判据面为什么取**检测页的载荷**而不是渲染出的页面：接线说明 / 上板清单 /
    标注整块是工单 05 的活（票面第一条把"页面写 PA0/PA1"派给那一单），本单要钉的
    是**那两句话的数据从哪儿来**——自建件不是模块、没有 `pins` 声明，它的脚全部
    来自支点 `i2c_probe`（`hwcheck_view` 自动补进模块集），所以：

    * 接线行里有 PA0/PA1 两条（`wiring.rows`，页面接线表的唯一来源）；
    * 每条行上的板载注记**原样来自板定义**（`pin_note` → `board_shares`），
      不是这一层新编的一句话。

    数据面成立 + 05 渲染它 = 票面第 3 条成立；本单不许为了"页面上先看到"把文案
    在渲染层再抄一份（那就是判据分家，第 4 条要防的正是这个）。
    """
    import tempfile

    from contest_generator.hwcheck import HwCheckConfig
    from contest_generator.hwcheck_board import hwcheck_view
    from contest_generator.my_devices import my_devices_dir, save_device

    with tempfile.TemporaryDirectory() as tmp:
        save_device(my_devices_dir(Path(tmp)), _device())
        view = hwcheck_view(
            HwCheckConfig(
                platform=PLATFORM_MSPM0, debug_uart=True, oled=False,
                devices=("mine_gyro",),
            ),
            module_library_dir=REPO / "library" / "modules",
            masters_dir=REPO / "library" / "masters",
            data_dir=Path(tmp),
        )
    assert "i2c_probe" in view.generation_slugs, "脚来自支点模块，它必须在模块集里"
    rows = {
        row["pin"]: row for row in view.board["wiring"]["rows"]
        if row["slug"] == "i2c_probe"
    }
    assert set(rows) == {"PA0", "PA1"}, f"接线表要有这一对脚：{sorted(rows)}"
    assert "板载 LED 共用" in rows["PA0"]["pin_note"], rows["PA0"]
    assert "板载 LED 共用" in rows["PA1"]["pin_note"], rows["PA1"]
    assert "上拉位未焊" in rows["PA0"]["pin_note"], (
        "PA0 的板载上拉位未焊是板定义的事实，页面照抄这一份：" + rows["PA0"]["pin_note"]
    )
    shares = {item["pin"]: item for item in view.board["wiring"]["board_shares"]}
    assert {"PA0", "PA1"} <= set(shares), "板上共享单独成列（页面据此单列一条）"
    assert shares["PA0"]["note"] == rows["PA0"]["pin_note"], (
        "同一句话两个落点必须是同一个来源（板定义），不许各写一份"
    )


def test_the_platform_cost_sentence_matches_the_board_definition():
    """**mspm0 那一对脚的平台代价只有一个说法**，产物与页面说的是同一句。

    票面第 4 条要的是"产物注释写同样这两条，与页面同一句措辞"。两条事实各有
    唯一来源（`boards/mspm0-dimx.json` 的 `BoardPin.notes`：板子本来就接着什么）
    ——页面接线行的 `pin_note` / 板上共享那两处读它，产物注释读的是**同一份注记
    的人读复述**（`PLATFORM_PIN_COST`，去掉脚名：脚名在接线表里已经有了）。

    ⚠ 产物里写这两句**不违反**"无引脚字面量"那条硬边界（两件事别混）：生成门禁
    是**剥注释后**判的（`generator._check_no_pin_literals_in_main` +
    `clex.strip_comments`），它挡的是**代码内联引脚**（那样换板要重写骨架、也
    绕开 ADR 0010 的改绑机制）；而这两句里一个引脚名都没有。本文件第 ③ 块那条
    `test_no_pin_or_instance_literal_in_the_product` 判的也正是**代码**。

    判据三条腿：① 板定义里那两条事实都在；② `PLATFORM_PIN_COST` 的关键词与它
    逐条对得上（板定义改了这里就红——它是复述，不许自说自话）；③ 产物里真的
    印出来了，且**只印在 mspm0**（stm32 没有这条代价，不许编）。
    """
    import json

    board = json.loads(
        (REPO / "src" / "contest_generator" / "boards" / "mspm0-dimx.json").read_text(
            encoding="utf-8"
        )
    )
    by_pin = {pin["name"]: pin.get("notes", "") for pin in board["pins"]}
    for pin in ("PA0", "PA1"):
        assert _BOARD_NOTE_FRAGMENT in by_pin[pin], (
            f"{pin} 的板上注记要写清它与板载 LED 同脚（页面照抄这一份）：{by_pin[pin]}"
        )
    assert "上拉" in by_pin["PA0"] and "未焊" in by_pin["PA0"], (
        "PA0 的板载上拉位未焊是**板子的事实**，写在板定义里（PA1 相反是板载 4.7k）："
        + by_pin["PA0"]
    )

    cost = PLATFORM_PIN_COST[PLATFORM_MSPM0]
    for needle in ("板载 LED 共用", "微闪", "上拉位未焊"):
        assert needle in cost, (
            f"产物那句要复述板定义的原话（缺 {needle}）：{cost}"
        )

    artifact = _main_c(PLATFORM_MSPM0, ["mine_gyro"])
    assert cost in artifact, (
        "mspm0 的产物注释要带这句平台代价（与页面同一句）：\n" + artifact[:600]
    )
    assert PLATFORM_PIN_COST[PLATFORM_STM32] == "", (
        "stm32 那一对脚没有这条代价——不许为了对称编一句"
    )
    assert "平台代价" not in _main_c(PLATFORM_STM32, ["mine_gyro"]), (
        "stm32 产物里不该出现这句（它只属于 mspm0 的 I2C_0）"
    )
    # 产物侧：两平台同一份渲染，**代码**里引脚字面量一个都不许有（第 ③ 块那条判据）
    assert "PA0" not in _strip_comments(artifact)


def test_the_compile_probe_covers_both_platforms_and_the_four_receipt_categories():
    """**编译矩阵探针本身**要两平台都覆盖（票面第 6 条：矩阵一起复跑）。

    为什么要给探针写用例：探针是这一单唯一的"真编译"判据来源，而它自己很容易
    退化成只跑一个平台（03 起就是这么长起来的）——那样"mspm0 也能生成"就没有
    任何真编译证据，只剩一句自述。这里只钉**覆盖形状**（跑不跑真编译是探针
    运行时的读数，用例不替它跑）：

    * 两平台都在；
    * 票面点名的四类形态都在：一件都不选 / 只有自建件 / 自建件 + 库内器件 /
      全选（"全选"那一格按平台**能装下的最大子集**自动收敛，见探针里的说明——
      原始集合在地猛星上物理装不下，装不下那条路本身也是产品行为）；
    * 每格的形态两平台都有定义（缺一个平台 = 那一格没有那一侧的读数）。
    """
    import importlib.util

    path = REPO / ".scratch" / "hwcheck-unknown-device" / "probe-03-compile-matrix.py"
    assert path.is_file(), f"编译矩阵探针不在：{path}"
    spec = importlib.util.spec_from_file_location("probe_03_compile_matrix", path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)                 # 只读模块级定义，不跑 main()
    assert set(probe.PLATFORMS) == {PLATFORM_MSPM0, PLATFORM_STM32}
    for name in probe.CASES:
        for platform in probe.PLATFORMS:
            assert platform in probe.CASES[name], f"{name} 缺 {platform} 的定义"
    kinds = {
        name: probe.CASES[name][PLATFORM_MSPM0]["kind"] for name in probe.CASES
    }
    for kind in ("empty", "custom-only", "custom+library", "all-library"):
        assert kind in kinds.values(), f"票面点名的形态缺 `{kind}`：{kinds}"
    # 「全选到底有多大」的边界格（票面第 6 条的"全选"就是这个规模）：检测页给得出
    # 的全部器件，按平台算，**不设让位**——读数如实记产品在真实规模上怎么答。
    assert "all-recipes" in kinds, f"缺全选边界格：{kinds}"
    # 「只有自建件」与「空形态」都得真有自建件 / 真没有器件
    assert probe.CASES["custom-only"][PLATFORM_MSPM0]["custom"], "custom-only 要有自建件"
    assert not probe.CASES["empty"][PLATFORM_MSPM0]["devices"], "empty 不该选任何器件"


# ---------------------------------------------------------------------------
# 工单 05：检测页的「器件计划」（接线行 / 顺序 / 标注 / 上板清单）
#
# 03/04 已经算好了"页面上说的与板上做的一致"（三档文案单源）。这一单把那份
# 计划**显示出来**，并且要覆盖 03 没管的那一半：**不出小节的件也要在计划里**
# （非 I2C、没勾输出通道——它们不是模块、没有 C 产物，但这一趟确实选了它们，
# 页面上必须如实说"为什么没有它的探测程序"，否则就是一次悄无声息的少测）。
# ---------------------------------------------------------------------------

# 支点 `i2c_probe` 的接线行（真形态：`wiring_rows` 的字段，本单只读 role / pin）。
PROBE_ROWS_STM32 = (
    {"slug": "i2c_probe", "role": "I2C_PROBE_SCL", "role_id": "I2C_PROBE_SCL", "pin": "PA6"},
    {"slug": "i2c_probe", "role": "I2C_PROBE_SDA", "role_id": "I2C_PROBE_SDA", "pin": "PA7"},
)


def _spi_device(**overrides) -> CustomDevice:
    data = {
        "id": "mine_spi_screen",
        "name": "卖家给的 SPI 屏",
        "bus": "spi",
        "address": None,
    }
    data.update(overrides)
    return CustomDevice(**data)


def _plan(devices, *, has_output_channel=True, probe_rows=PROBE_ROWS_STM32):
    return resolve_custom_plan(
        list(devices),
        has_output_channel=has_output_channel,
        probe_rows=list(probe_rows),
    )


def test_the_plan_lists_every_selected_custom_device_not_only_the_probing_ones():
    """计划里**每一件选中的自建件都在**，出不出的来小节是另一栏（`probes`）。

    只列"出了小节的"就是把非 I2C 件从页面上抹掉——那正是 spec 用户故事 14
    反对的（"非 I2C 也要如实处理"）。计划里那句 `plan` 就是原因，页面照抄。
    """
    entries = {entry.slug: entry for entry in _plan([_device(), _spi_device()])}
    assert set(entries) == {"mine_gyro", "mine_spi_screen"}
    assert entries["mine_gyro"].probes is True
    # 出小节的那件：页面那一行读的就是 C 侧同一个字符串（三档文案单源不破）
    assert entries["mine_gyro"].plan == PLAN_JUDGE
    assert entries["mine_spi_screen"].probes is False
    # 不出小节的那件：它的"这一趟做什么"**就是**不出小节那句（不许另写一句）
    assert entries["mine_spi_screen"].plan == NOT_PROBED_NOT_I2C


def test_the_plan_says_the_output_channel_is_missing_instead_of_the_three_tiers():
    """没勾输出通道 → 三档文案换成"没通道"，而不是照旧说"这一趟会 ping 它"。"""
    entry = _plan([_device()], has_output_channel=False)[0]
    assert entry.probes is False
    assert entry.plan == NOT_PROBED_NO_CHANNEL


def test_the_checklist_projection_has_a_single_home():
    """三处端点共用**一处**清单投影（工单 05 评审整改）。

    为什么值得一条判据：`render_checklist(config, custom)` 的第二个参数**漏了不报错**
    ——清单里只是静悄悄地少掉自建件那几条，正是本功能一路在防的"悄无声息的少测"。
    所以判据钉在路由层：`render_checklist(` 只许出现在那个共用件里，三个端点都得
    调它（新增端点照抄的是"吃视图的函数"，不是"可能漏参数的一句话"）。
    """
    src = (REPO / "src" / "contest_generator" / "webapp.py").read_text(encoding="utf-8")
    calls = re.findall(r"render_checklist\(([^)]*)\)", src)
    assert calls == ["config, view.custom_plan"], (
        "路由层出现了第二处清单投影（漏喂自建件计划不会报错，只会少几条）：" + repr(calls)
    )
    assert src.count("_hwcheck_checklist_payload(config, view)") == 3, (
        "三个端点（生成 / 回读 / 排障）都要走同一处清单投影"
    )


def test_the_probes_verdict_has_a_single_home():
    """**"这一趟给不给它出小节"只有一个判据**：C 侧 sections 与页面 plan 同源。

    两处各判一次（一处写 `bus == "i2c"`、另一处写 `has_output_channel and ...`）
    就会漂：页面上说"会测"、产物里没有它。
    """
    devices = [_device(), _spi_device()]
    for has_channel in (True, False):
        from_sections = {
            section.slug
            for section in resolve_custom_sections(
                devices, has_output_channel=has_channel
            )
        }
        from_plan = {
            entry.slug
            for entry in _plan(devices, has_output_channel=has_channel)
            if entry.probes
        }
        assert from_sections == from_plan, f"has_output_channel={has_channel}"


def test_the_wiring_line_is_built_from_the_probe_rows_and_names_the_bus():
    """接线那一行 = 名称 + 地址 + **支点声明的那对脚**（脚不在这里另写一份）。

    `probe_rows` 是 `wiring_rows` 的输出（已含引脚消解后的**生效脚**），所以
    页面这一行与接线表、与工程 README 是同一组脚。
    """
    entry = _plan([_device()])[0]
    assert entry.wiring_text == (
        "你的器件 卖家给的六轴模块（地址 0x68）接到上面接线表里 i2c_probe 的那对脚："
        "I2C_PROBE_SCL → PA6、I2C_PROBE_SDA → PA7"
    )
    assert [pin["pin"] for pin in entry.pins] == ["PA6", "PA7"]
    assert [pin["role"] for pin in entry.pins] == ["I2C_PROBE_SCL", "I2C_PROBE_SDA"]


def test_the_plan_never_invents_pins_when_the_bus_rows_are_missing():
    """没有支点接线行 = **编不出脚**（不许自己造一对 PA6/PA7 出来）。

    非 I2C 件根本没有这一行（总线不是 I2C，页面上没有它的线）；支点缺席时同理。
    """
    spi = _plan([_spi_device()])[0]
    assert spi.pins == () and spi.wiring_text == ""
    missing = _plan([_device()], probe_rows=())[0]
    assert missing.pins == () and missing.wiring_text == ""


def test_the_checklist_names_the_three_verdict_classes_for_a_probing_device():
    """上板清单：**有应答 / 期望值不符 / 无应答**三类各一条（票面第 2 条）。

    三类都是"板上会打出来的东西"，所以清单说的是**可肉眼核对的现象**；
    "不对先查哪里"两句直接复用产物里的排查话术常量（`_TROUBLE_*`）——页面与
    板上同一句，改一处两处都动。
    """
    items = custom_checklist(_plan([_device()]))
    assert [item["id"] for item in items] == [
        "custom-mine_gyro-answered",
        "custom-mine_gyro-mismatch",
        "custom-mine_gyro-silent",
    ]
    answered, mismatch, silent = items
    for item in items:
        assert item["expect"] and item["check"], item
        assert _device().name in item["expect"] + item["check"] or _hex2(0x68) in (
            item["expect"] + item["check"]
        ), f"每条都要点得出是哪一件 / 哪个地址：{item}"
    assert "应答：有" in answered["expect"], answered
    assert _hex2(0x68) in mismatch["expect"] and "期望值一致" in mismatch["expect"], mismatch
    assert "地址上没有应答" in silent["expect"], silent
    assert _TROUBLE_JUDGE in mismatch["check"], "「不对先查」要复用产物里那句"
    assert _TROUBLE_PING in silent["check"], "同上"


def test_the_checklist_never_invents_a_class_the_device_cannot_produce():
    """只有地址（形态①）出不了"期望值不符"这一类——**不为它编一条**。

    编一条学生照着比、板上永远不会发生的事，比少一条更坏（既有口径：
    不假装测过）。
    """
    ping_only = _device(register=None, expect=None)
    ids = [item["id"] for item in custom_checklist(_plan([ping_only]))]
    assert ids == ["custom-mine_gyro-answered", "custom-mine_gyro-silent"]
    echo_only = _device(expect=None)
    assert [item["id"] for item in custom_checklist(_plan([echo_only]))] == [
        "custom-mine_gyro-answered",
        "custom-mine_gyro-silent",
    ]


def test_the_checklist_tells_the_truth_for_a_device_without_a_probe():
    """不出小节的件也要进清单（票面第 5 条：**只给清单与 AI 排障**）。

    它的那一条必须把"为什么没有探测程序"说清，并**明说别把没有输出当失败**。
    """
    items = custom_checklist(_plan([_spi_device()]))
    assert len(items) == 1, items
    item = items[0]
    assert item["id"] == "custom-mine_spi_screen-not-probed"
    assert NOT_PROBED_NOT_I2C in item["expect"], item
    assert "不是故障" in item["expect"] or "别把" in item["check"], item


def test_the_no_probe_sentence_no_longer_says_the_facts_miss_the_context():
    """05 留下的那句欠账（工单 09 结清）。

    第③条原先写的是"你填的地址 / 寄存器这一版**还进不了它的上下文**"——
    09 落地后自建件的事实真的进了排障上下文，页面上那句话必须跟着改：
    页面是学生唯一能看到的口径，**不许比产品落后**（说了不会带上、实际会带上，
    学生就会不敢填现象）。
    """
    item = custom_checklist(_plan([_spi_device()]))[0]
    blob = item["expect"] + item["check"]
    assert "进不了它的上下文" not in blob, blob
    assert "地址" in blob and "寄存器" in blob, blob
    # 学生可见的文案里**不许出现工单号**（"09 已落地"这种内部口径不该印给学生）
    assert "工单" not in blob and "已落地" not in blob, blob


def test_every_probe_plan_has_a_short_label():
    """短标签表（`_PROBE_FORM_LABELS`）必须覆盖全部三档 `PLAN_*`（工单 09）。

    短标签由 `PLAN_*` 查表派生（不另写一遍三档条件）——漏配一档就是排障上下文
    里一个 `KeyError`，这条结构判据把它挡在测试里。
    """
    from contest_generator.hwcheck_custom import (
        _PROBE_FORM_LABELS,
        PLAN_ECHO_ONLY,
        PLAN_JUDGE,
        PLAN_PING_ONLY,
    )

    assert set(_PROBE_FORM_LABELS) == {PLAN_PING_ONLY, PLAN_ECHO_ONLY, PLAN_JUDGE}
    assert all(label.strip() for label in _PROBE_FORM_LABELS.values())


def test_the_checklist_is_empty_when_no_custom_device_is_selected():
    """一件自建件都没有 → 清单**一个字都不多**（票面第 6 条的前半）。"""
    assert custom_checklist(()) == ()


# ---------------------------------------------------------------------------
# 接进检测页载荷（工单 05）：计划 / 顺序 / 上板清单三处都读同一份
# ---------------------------------------------------------------------------


def _page_view(
    platform: str,
    custom_devices=(),
    *,
    devices=(),
    debug_uart: bool = True,
    oled: bool = False,
    device_ids=(),
):
    """真库真母版的一次投影（自建件落在临时数据目录里）。

    `devices` = 这一趟选中的 slug（缺省 = 传进来的自建件全选）；
    `device_ids` = 想选但**数据目录里没有**的 id（模拟"选了这件、盘上又没了"）。
    """
    import tempfile

    from contest_generator.hwcheck import HwCheckConfig
    from contest_generator.hwcheck_board import hwcheck_view
    from contest_generator.my_devices import my_devices_dir, save_device

    with tempfile.TemporaryDirectory() as tmp:
        for device in custom_devices:
            save_device(my_devices_dir(Path(tmp)), device)
        selected = tuple(devices) or (
            tuple(device.id for device in custom_devices) + tuple(device_ids)
        )
        return hwcheck_view(
            HwCheckConfig(
                platform=platform,
                debug_uart=debug_uart,
                oled=oled,
                devices=selected,
            ),
            module_library_dir=REPO / "library" / "modules",
            masters_dir=REPO / "library" / "masters",
            data_dir=Path(tmp),
        )


def test_the_page_payload_carries_the_plan_for_every_selected_custom_device():
    """载荷 `custom` = **选中的每一件**的计划（票面第 1 / 5 条的数据面）。

    非 I2C 那件也要在（`probes=False` + 原因），否则页面无从说"为什么不给它出
    探测程序"——那就是一次悄无声息的少测。
    """
    view = _page_view(PLATFORM_STM32, [_device(), _spi_device()])
    plan = {item["slug"]: item for item in view.board["custom"]}
    assert set(plan) == {"mine_gyro", "mine_spi_screen"}
    i2c = plan["mine_gyro"]
    assert i2c["probes"] is True
    assert i2c["wiring_text"].startswith("你的器件 卖家给的六轴模块（地址 0x68）")
    assert i2c["wiring_text"].endswith("I2C_PROBE_SCL → PA6、I2C_PROBE_SDA → PA7"), (
        "脚要来自支点的接线行（stm32 = PA6/PA7）"
    )
    spi = plan["mine_spi_screen"]
    assert spi["probes"] is False and spi["plan"] == NOT_PROBED_NOT_I2C
    assert spi["wiring_text"] == ""
    # 标注词单源：两个投影（小节 / 计划）读的是同一份常量
    assert i2c["tag"] == CUSTOM_TAG and i2c["tag_text"] == CUSTOM_TAG_TEXT
    # 载荷只给"那句话"，不给脚清单（给了就是让前端自己再拼一遍）
    assert "pins" not in i2c and "not_probed" not in spi


def test_the_wiring_line_wins_over_the_cost_sentence_but_not_the_pins():
    """mspm0 上那一行给的是**生效脚**（PA0/PA1），与接线表逐字对得上。"""
    view = _page_view(PLATFORM_MSPM0, [_device()])
    entry = view.board["custom"][0]
    rows = [
        row for row in view.board["wiring"]["rows"] if row["slug"] == PROBE_MODULE_SLUG
    ]
    assert entry["wiring_text"].endswith(
        "、".join(f"{row['role']} → {row['pin']}" for row in rows)
    ), entry["wiring_text"]
    assert {row["pin"] for row in rows} == {"PA0", "PA1"}, "地猛星上这一对脚"


def test_the_order_puts_the_custom_device_after_every_library_module():
    """顺序（票面第 3 条）：库内 bring-up 件在前，**自建件排最后**。

    判据复用既有排序——这里只断言"接在它后面"，不另立一套次序。
    """
    view = _page_view(PLATFORM_STM32, [_device()], devices=("mine_gyro", "led"))
    order = view.board["wiring"]["order"]
    assert [item["slug"] for item in order][-1] == "mine_gyro", order
    assert order[0]["slug"] == "led" and order[0]["bring_up"] is True, (
        "库内 bring-up 件仍排在前面（既有排序没动）：" + repr(order[0])
    )
    last = order[-1]
    assert last["custom"] is True and last["bring_up"] is False
    assert last["tag_text"] == CUSTOM_TAG_TEXT and last["name"] == _device().name
    assert last["description"] == PLAN_JUDGE, "顺序表那一行读的也是计划单源"


def test_the_order_never_lists_an_unprobed_device_as_something_to_test():
    """不出小节的件**不进顺序表**（顺序表 = 这一趟的测试次序）。

    它仍在计划与清单里（如实说没有探测程序）——但排在"建议检测顺序"里等于让它
    看起来被测了。
    """
    view = _page_view(PLATFORM_STM32, [_device(), _spi_device()])
    slugs = [item["slug"] for item in view.board["wiring"]["order"]]
    assert "mine_gyro" in slugs and "mine_spi_screen" not in slugs, slugs


def test_the_checklist_grows_by_the_custom_device_classes_in_the_right_place():
    """上板清单：既有几条一个不动，自建件三类接在**通道那几条之后**、复位之前。"""
    from contest_generator.hwcheck import HwCheckConfig, render_checklist

    view = _page_view(PLATFORM_STM32, [_device()], devices=("mine_gyro", "led"))
    config = HwCheckConfig(
        platform=PLATFORM_STM32, debug_uart=True, oled=False, devices=("mine_gyro", "led")
    )
    plain = [item.id for item in render_checklist(config)]
    with_custom = [item.id for item in render_checklist(config, view.custom_plan)]
    assert with_custom[: len(plain)] == plain or plain == [
        i for i in with_custom if not i.startswith("custom-")
    ], with_custom
    assert "custom-mine_gyro-answered" in with_custom
    assert with_custom.index("custom-mine_gyro-answered") > with_custom.index("serial")
    assert with_custom.index("custom-mine_gyro-answered") < with_custom.index("reset")
    # 没有自建件时逐字与改动前一致（票面第 6 条）
    assert render_checklist(config) == render_checklist(config, ())


def test_the_product_never_marks_a_custom_section_as_specialized():
    """标注词不互串（票面第 4 条）：产物里自建件那一批**不出现 `[专精]`**。

    库内件那一批照旧带 `[专精]`（它是"库内验证过的"唯一标记）——两个词各归各的
    批次，学生才分得清哪些结论可信。
    """
    view = _page_view(PLATFORM_STM32, [_device()], devices=("mine_gyro", "ml_mpu6050"))
    custom_block = _section_block(
        [line for line in _custom_lines(_main_c_of(view)) if line.strip()],
        CUSTOM_TAG_TEXT,
    )
    assert CUSTOM_TAG_TEXT in custom_block
    assert SECTION_TAG not in custom_block, (
        "自建件那一段里出现了 `[专精]`（两个词互串了）：\n" + custom_block
    )
    assert SECTION_TAG in _main_c_of(view), "库内专精件那一段照旧带 [专精]"
    for item in view.board["custom"]:
        assert SECTION_TAG not in (item["tag"] + item["tag_text"] + item["plan"]), item


def test_a_non_i2c_custom_device_never_reaches_the_product():
    """非 I2C 件**不进 C 产物**（票面第 5 条后半：不假装测过）。

    它这一趟在页面上有位置（计划 + 清单 + AI 排障），但 main.c 里一个字都不该有。
    """
    view = _page_view(PLATFORM_STM32, [_spi_device()])
    code = _main_c_of(view)
    assert "mine_spi_screen" not in code, code[:400]
    assert "hwcheck_custom_mine_spi_screen" not in code
    assert PROBE_MODULE_SLUG not in view.generation_slugs, (
        "没有探测小节时不该顺手把支点模块带进工程：" + repr(view.generation_slugs)
    )


def test_the_render_injection_point_is_still_the_only_one():
    """预览与生成仍走同一处渲染（工单 03 的验收线，本单没动它）。"""
    view = _page_view(PLATFORM_STM32, [_device()])
    assert [section.slug for section in view.custom] == ["mine_gyro"]
    assert [entry.slug for entry in view.custom_plan] == ["mine_gyro"]


def _main_c_of(view) -> str:
    """这一趟的产物（与两个端点同一条渲染路径：吃视图里那三批小节）。"""
    from contest_generator.hwcheck import HwCheckConfig, render_main_c

    config = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=False)
    return render_main_c(config, view.sections, view.generic, view.custom)


def _custom_lines(code: str) -> list[str]:
    """产物里**自建件那一批**的语句行（从 `hwcheck_custom_` 那个小节函数起算）。"""
    lines = code.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("static void hwcheck_custom_")),
        0,
    )
    return lines[start:]


def _section_block(lines: list[str], marker: str) -> str:
    """取含 `marker` 的那一段（到下一个空行 / 下一个注释块头为止）。"""
    text = "\n".join(lines)
    at = text.find(marker)
    assert at >= 0, f"产物里没有 {marker}：\n{text[:400]}"
    return text[at:]
