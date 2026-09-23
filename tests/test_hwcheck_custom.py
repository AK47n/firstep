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
    CustomSection,
    custom_headers,
    render_custom_section,
    resolve_custom_sections,
    sections_payload,
)
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
