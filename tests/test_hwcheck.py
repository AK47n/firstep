# -*- coding: utf-8 -*-
"""硬件检测：最小自检 main.c 渲染 + 输出通道形态（工单 module-hwcheck/01）。

**为什么这样测**：域层是纯函数（字符串进 / 字符串出、零 LLM、零配方），
所以判据全部落在文本结构上——「心跳段在不在」「通道自报段在不在」「两个
通道都没有时到底有没有产生打印调用」。最后一条是**防假装测过**的结构
断言：没有输出通道却渲染出打印调用，等于声称检测了却没人看得见结果。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.clex import strip_comments
from contest_generator.hwcheck import (
    OUTPUT_HINT_NONE,
    OUTPUT_HINT_OLED,
    OUTPUT_HINT_SERIAL,
    OUTPUT_HINT_SERIAL_OLED,
    HwCheckConfig,
    HwCheckError,
    render_main_c,
    render_output_hint,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32

BOTH = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=True)
SERIAL_ONLY = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=False)
OLED_ONLY = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=False, oled=True)
LAMP_ONLY = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=False, oled=False)


_CONTROL_KEYWORDS = frozenset({"while", "if", "for", "switch", "return", "sizeof"})


def _called_names(code: str) -> set[str]:
    """main.c 里真实出现的调用名（先剥注释，注释里的"调用"不算；控制关键字不算）。"""
    names = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", strip_comments(code)))
    return names - _CONTROL_KEYWORDS


def _declared_names(code: str) -> set[str]:
    """main.c 自己声明/定义的函数名（自检报告函数属框架自带）。"""
    return set(re.findall(r"^\s*static\s+void\s+(\w+)\s*\(", strip_comments(code), re.MULTILINE))


# ---------------------------------------------------------------------------
# 三种通道形态：渲染产物与「应看到什么」逐一对上
# ---------------------------------------------------------------------------


def test_stm32_serial_and_oled_render_both_report_paths():
    """串口 + OLED 都在：两个通道各有一段自报，且各自 include 自己的头。"""
    code = render_main_c(BOTH)
    assert '#include "headfile.h"' in code
    assert '#include "debug_uart.h"' in code  # stm32 版调试串口头
    assert "led_instances.h" in code
    assert "debug_uart_init()" in code
    assert "debug_cmd_poll()" in code
    assert "DEBUG_PRINTF" in code
    assert "OLED_Init()" in code
    assert "oled_show_text(" in code


def test_mspm0_uses_its_own_driver_header_and_init():
    """同名模块在两平台的头文件名与初始化不同——渲染器必须按平台取。"""
    code = render_main_c(
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=True)
    )
    assert '#include "debug_uart_mspm0.h"' in code
    assert '#include "debug_uart.h"' not in code
    assert "SYSCFG_DL_init()" in code
    assert "DEBUG_UART_INST_IRQHandler" not in code  # 模块内已定义，main.c 不得再定义


def test_debug_uart_only_has_no_oled_calls():
    """只有串口：不得出现任何 OLED 调用（没接的屏不写）。"""
    code = render_main_c(SERIAL_ONLY)
    assert "DEBUG_PRINTF" in code
    assert not [name for name in _called_names(code) if name.startswith("OLED_")]
    assert "oled_show_text" not in code
    assert "#include \"oled.h\"" not in code
    assert '#include "debug_uart.h"' in code


def test_oled_only_has_no_serial_calls():
    """只有 OLED：不得出现串口调用，也不得 include 串口头。"""
    code = render_main_c(OLED_ONLY)
    assert "oled_show_text(" in code
    assert "DEBUG_PRINTF" not in code
    assert "debug_uart_init" not in code
    assert '#include "debug_uart.h"' not in code
    assert '#include "oled.h"' in code


def test_no_channel_renders_no_print_call_at_all():
    """**防"假装测过"的结构断言**：两个通道都没有 → 一句打印调用都不许有。

    这条不是风格洁癖：没有输出通道却渲染出打印调用，学生看到的就是
    「程序在跑但什么都看不到」，而代码声称它报了结果。
    """
    code = render_main_c(LAMP_ONLY)
    called = _called_names(code)
    assert "DEBUG_PRINTF" not in called
    assert not [name for name in called if name.startswith("OLED_")]
    assert "oled_show_text" not in code
    assert "debug_uart_send" not in code
    assert "debug_cmd_poll" not in code  # 没有串口就没有可复测的控制台
    # 框架自带的自检报告函数同理不得出现（定义了却没人调 = 死代码）
    assert "hwcheck_report" not in code


def test_heartbeat_section_present_in_every_form():
    """心跳段与汇总段在任何形态下都在（这是"板子活着"的唯一凭据）。"""
    for config in (BOTH, SERIAL_ONLY, OLED_ONLY, LAMP_ONLY):
        code = render_main_c(config)
        assert "led_init(LED_RED)" in code
        assert "led_toggle(LED_RED)" in code
        assert "HWCHECK_HEARTBEAT_MS" in code
        assert "delay_ms(" in code


def test_header_comment_matches_the_form_it_renders():
    """文件头自述必须与产物一致：没通道的形态不许自称"结果写到输出通道"。

    这条抓的是一类看不见的谎：代码里一个打印调用都没有（下面那条结构断言保证），
    但文件头照抄模板写着"每一段结果写到输出通道"——学生读代码会以为报了结果。
    """
    with_channel = render_main_c(SERIAL_ONLY)
    assert "写到在场的输出通道" in with_channel
    lamp_only = render_main_c(LAMP_ONLY)
    assert "写到在场的输出通道" not in lamp_only
    assert "不打印任何检测结果" in lamp_only


def test_summary_report_is_the_first_line_of_output():
    """上电先跑一遍：逐件自报之前先出「板子活着」那行（bring-up 顺序）。"""
    for config in (BOTH, SERIAL_ONLY, OLED_ONLY):
        code = render_main_c(config)
        first_call = re.search(r"hwcheck_report\(([^)]*)\);", code)
        assert first_call is not None, "应至少有一次自检报告调用"
        assert "上电" in first_call.group(1) or "板子" in first_call.group(1)


# ---------------------------------------------------------------------------
# 只调真实存在的接口（防幻觉调用）
# ---------------------------------------------------------------------------

# 母版 / 工具链"外部事实"白名单：这些名字的出处**不在模块库里**，逐条写明依据。
# 每条 = (名字, (出处文件, …))——出处必须真存在且真含该名字（下面有用例核对）。
# 为什么允许这样一张小表：母版工程根的头（headfile.h / ti_msp_dl_config.h）不在
# 库的 modules/ 下，判据读不到它们；但表要小、要可核对，且不许当后门长大。
_MASTER_EXTERNAL_FACTS: dict[str, tuple[str, ...]] = {
    "SYSCFG_DL_init": ("library/masters/mspm0/main.c",),
    "SystemInit": (
        "library/masters/stm32/sys/system_stm32f10x.h",
        "library/masters/stm32/main.c",
    ),
}
# 库内**另一处**的真实出处（模块 code/ 目录之外、但确实在库内）：
#   stm32 母版工程根 led_instances.h → LED_RED 等通道宏（生成器多实例渲染产物）
#   mspm0 led 模块 code/led_instances.h → 同上（模块自带基线）
_MASTER_ROOT_HEADERS = {
    PLATFORM_STM32: ("library/masters/stm32/led_instances.h",),
    PLATFORM_MSPM0: ("library/modules/led/code/led_instances.h",),
}
_CHANNEL_CALL_NAMES = frozenset({"main", "sprintf", "snprintf"})


def _library_header_functions(platform: str) -> set[str]:
    """库内**该平台**的头文件里声明的函数名 / 函数式宏名（真实库，不手写清单）。

    范围 = delay + debug_uart + oled + led 四个模块的 code/ 目录（本单渲染会碰到的
    全部模块）+ stm32 母版 ml_libs/（stm32 的 led / delay / oled 由母版提供）。
    平台过滤按库内既有约定：mspm0 版头文件名含 `_mspm0`（debug_uart 先例）。
    """
    library = Path(__file__).resolve().parents[1] / "library"
    roots = [library / "modules" / slug / "code"
             for slug in ("delay", "debug_uart", "oled", "led")]
    if platform == PLATFORM_STM32:
        roots.append(library / "masters" / "stm32" / "ml_libs")
    names: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.h")):
            if platform == PLATFORM_STM32 and "_mspm0" in path.name:
                continue
            if platform == PLATFORM_MSPM0 and path.name.startswith("ml_"):
                continue
            text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
            names |= set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", text))
            names |= set(re.findall(r"#define\s+([A-Za-z_]\w*)", text))
    return names


@pytest.mark.parametrize("platform", [PLATFORM_STM32, PLATFORM_MSPM0])
def test_every_called_name_comes_from_the_real_library(platform):
    """渲染出的每个调用名都必须能在**该平台的库内头文件**里找到（或母版外部白名单）。

    判据不是手写函数名清单，而是判据读盘：`library/modules/{delay,debug_uart,oled,led}`
    与该平台的母版头。所以「换个平台渲染出 stm32 才有的头 / 调用」当场红——
    这条正是本工单「渲染出的程序必须真能编译」的最小机械保证。
    """
    for debug_uart in (True, False):
        for oled in (True, False):
            config = HwCheckConfig(platform=platform, debug_uart=debug_uart, oled=oled)
            code = render_main_c(config)
            known = _library_header_functions(platform)
            known |= set(_MASTER_EXTERNAL_FACTS) | set(_CHANNEL_CALL_NAMES)
            unknown = sorted(_called_names(code) - _declared_names(code) - known)
            assert unknown == [], f"{config} 渲染出了库内没有出处的调用：{unknown}"


def test_master_external_whitelist_entries_have_real_evidence():
    """白名单里的每条都必须在仓库里找得到出处（防止白名单被当成后门慢慢长大）。"""
    repo = Path(__file__).resolve().parents[1]
    for name, sources in _MASTER_EXTERNAL_FACTS.items():
        assert sources, f"{name} 没写出处"
        for rel in sources:
            path = repo / rel
            assert path.is_file(), f"{name} 的出处文件不存在：{rel}"
    # 至少一处出处里真含这个名字（不能全是"文件名像但内容无关"）
    for name, sources in _MASTER_EXTERNAL_FACTS.items():
        texts = [
            (repo / rel).read_text(encoding="utf-8", errors="replace") for rel in sources
        ]
        assert any(name in text for text in texts), (
            f"{name} 在登记的出处里一个都找不到：{sources}"
        )


@pytest.mark.parametrize(
    "config",
    [
        HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=True),
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=True),
        HwCheckConfig(platform=PLATFORM_STM32, debug_uart=False, oled=False),
    ],
)
def test_every_include_resolves_to_a_real_library_header(config):
    """渲染出的每个 `#include "x.h"` 都要在库内真实存在（防"头文件名写错"）。

    判据 = 库内（modules/*/code/ 或 masters/*/ml_libs/ 或母版工程根）真有这个名字的
    头文件；母版进门头（stm32 headfile.h / mspm0 ti_msp_dl_config.h）按母版事实承认。
    """
    library = Path(__file__).resolve().parents[1] / "library"
    entry_headers = {
        PLATFORM_STM32: {"headfile.h"},
        PLATFORM_MSPM0: {"ti_msp_dl_config.h"},
    }[config.platform]
    code = render_main_c(config)
    for header in re.findall(r'#include\s+"([^"]+)"', code):
        if header in entry_headers:
            continue
        hits = [
            path for path in library.rglob(header)
            if "/code/" in path.as_posix() or path.parent.name == "ml_libs"
        ]
        assert hits, f"{config} 引用了库内不存在的头：{header}"


# ---------------------------------------------------------------------------
# 通道形态的「应看到什么」（页面明示，后端给文案）
# ---------------------------------------------------------------------------


def test_output_hint_names_the_channels_that_exist():
    assert render_output_hint(BOTH) == OUTPUT_HINT_SERIAL_OLED
    assert render_output_hint(SERIAL_ONLY) == OUTPUT_HINT_SERIAL
    assert render_output_hint(OLED_ONLY) == OUTPUT_HINT_OLED


def test_output_hint_says_lamp_only_when_no_channel():
    """两个通道都没有：明示「只能看灯闪」，且**不是报错**（照常渲染）。"""
    hint = render_output_hint(LAMP_ONLY)
    assert hint == OUTPUT_HINT_NONE
    assert "灯" in hint


def test_every_hint_is_chinese_and_nonempty():
    for config in (BOTH, SERIAL_ONLY, OLED_ONLY, LAMP_ONLY):
        hint = render_output_hint(config)
        assert hint.strip()
        assert re.search(r"[\u4e00-\u9fff]", hint)


# ---------------------------------------------------------------------------
# 域错误与形状守卫
# ---------------------------------------------------------------------------


def test_unknown_platform_raises_domain_error_with_platform_list():
    with pytest.raises(HwCheckError) as excinfo:
        render_main_c(HwCheckConfig(platform="nope", debug_uart=True, oled=False))
    message = str(excinfo.value)
    assert "nope" in message
    assert PLATFORM_STM32 in message and PLATFORM_MSPM0 in message


def test_render_is_pure_and_deterministic():
    """同一配置两次渲染逐字节相同（纯函数：无时间戳、无随机、无全局态）。"""
    assert render_main_c(BOTH) == render_main_c(BOTH)
    assert render_output_hint(LAMP_ONLY) == render_output_hint(LAMP_ONLY)


def test_config_rejects_non_boolean_channel_flags():
    with pytest.raises(HwCheckError):
        HwCheckConfig(platform=PLATFORM_STM32, debug_uart="yes", oled=False)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 端点（POST /api/hwcheck/preview）：零 LLM，不依赖生成流程任何状态
# ---------------------------------------------------------------------------


@pytest.fixture()
def hwcheck_client(tmp_path):
    """已配置的假上下文（复用 test_webapp 的搭法）+ TestClient，记录 holder 里的假 LLM。

    这个端点**不该碰 LLM**（spec：渲染零 LLM），所以假 LLM 的作用是"证明它没被调用"。
    """
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app
    from tests.fakes import FakeLLM, make_fake_module_library

    config_path = tmp_path / "cfg" / "config.json"
    library_dir = make_fake_module_library(tmp_path / "module_library")
    holder = {"llm": FakeLLM()}
    ctx = AppContext(
        config_path=config_path,
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=library_dir,
            masters_dir=tmp_path / "masters",
        ),
        llm_factory=lambda config: holder["llm"],
    )
    return TestClient(create_app(ctx)), holder


def test_preview_endpoint_returns_main_c_without_llm(hwcheck_client):
    """预览端点：给平台 → 拿 main.c 文本 + 应看到什么；一个 LLM 调用都不发生。"""
    client, holder = hwcheck_client
    response = client.post("/api/hwcheck/preview", json={"platform": PLATFORM_STM32})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["platform"] == PLATFORM_STM32
    assert body["debug_uart"] is True and body["oled"] is True  # 缺省 = 两个通道都在场
    assert "hwcheck_report" in body["main_c"]
    assert body["output_hint"] == OUTPUT_HINT_SERIAL_OLED
    # 零 LLM：FakeLLM 上所有职责的调用记录都必须是空的
    fake = holder["llm"]
    assert fake.skeleton_calls == []
    assert fake.smoke_calls == []
    assert fake.select_calls == []


def test_preview_endpoint_honours_channel_flags(hwcheck_client):
    """通道开关随请求走（页面明示「只能看灯闪」那条路也走同一个端点）。"""
    client, _ = hwcheck_client
    body = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": False, "oled": False},
    ).json()
    assert body["debug_uart"] is False and body["oled"] is False
    assert body["output_hint"] == OUTPUT_HINT_NONE
    assert "DEBUG_PRINTF" not in body["main_c"]


def test_preview_endpoint_rejects_unknown_platform_400_chinese(hwcheck_client):
    """平台词表外 → 400 中文（带已注册平台清单，用户能直接改对）。"""
    client, _ = hwcheck_client
    response = client.post("/api/hwcheck/preview", json={"platform": "arduino"})
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "arduino" in detail
    assert PLATFORM_STM32 in detail and PLATFORM_MSPM0 in detail


def test_preview_endpoint_rejects_non_boolean_channel_400(hwcheck_client):
    """debug_uart 传字符串 → 400（路由层的 _optional_bool，不进域层）。"""
    client, _ = hwcheck_client
    response = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": "yes"},
    )
    assert response.status_code == 400, response.text
    assert "debug_uart" in response.json()["detail"]


def test_hwcheck_error_registered_as_400():
    """域错误按 400 登记在 errors.py 的唯一表里（未登记 = 500 真 bug 兜底）。"""
    from contest_generator.errors import error_entry

    status, message = error_entry(HwCheckError("未知平台 'nope'，已注册的平台：mspm0, stm32"))
    assert status == 400
    assert "nope" in message

