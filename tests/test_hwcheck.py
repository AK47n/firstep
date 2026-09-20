# -*- coding: utf-8 -*-
"""硬件检测：最小自检 main.c 渲染 + 输出通道形态（工单 module-hwcheck/01）。

**为什么这样测**：域层是纯函数（字符串进 / 字符串出、零 LLM、零配方），
所以判据全部落在文本结构上——「心跳段在不在」「通道自报段在不在」「两个
通道都没有时到底有没有产生打印调用」。最后一条是**防假装测过**的结构
断言：没有输出通道却渲染出打印调用，等于声称检测了却没人看得见结果。
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from contest_generator.clex import strip_comments
from contest_generator.hwcheck import (
    OUTPUT_HINT_NONE,
    OUTPUT_HINT_OLED,
    OUTPUT_HINT_SERIAL,
    OUTPUT_HINT_SERIAL_OLED,
    HWCHECK_CHANNELS,
    HwCheckConfig,
    HwCheckError,
    hwcheck_modules,
    render_checklist,
    render_main_c,
    render_output_hint,
)
from contest_generator.hwcheck_generic import (
    GENERIC_LABEL,
    GenericSection,
    plan_generic_section,
)
from contest_generator.hwcheck_recipe import (
    SECTION_TAG,
    RecipeProbe,
    RecipeRead,
    RecipeSection,
    c_string,
    escape_c_string,
    render_recipe_section,
)
from contest_generator.library import list_modules
from contest_generator.manifest import ModuleManifest
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.readme import parse_pin_table
from tests._c_escape import decode_c_string

BOTH = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=True)
SERIAL_ONLY = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=False)
OLED_ONLY = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=False, oled=True)
LAMP_ONLY = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=False, oled=False)


_CONTROL_KEYWORDS = frozenset({"while", "if", "for", "switch", "return", "sizeof"})


def unescape_c_string(text: str) -> str:
    """渲染产物里的 ASCII 转义（`\\NNN` 八进制 / 历史 `\\xNN`）→ 人能读的字符。

    渲染器把非 ASCII 字面量转义成 UTF-8 字节（ARMCC 5.06 按本地代码页解析源
    文件，原样中文串会把收尾引号吞掉、整份 main.c 编不过——见 hwcheck_recipe
    的 escape_c_string 真机判例）。判据仍然要落在"学生看到的那句话"上，所以
    测试先还原再比。

    解码器本体单源在 `tests/_c_escape.py`（工单 05 起两个测试文件共用；此前是
    两份逐字相同的副本，评审抓到）。这里留这个名字是因为调用点很多。
    """
    return decode_c_string(text)


def _called_names(code: str) -> set[str]:
    """main.c 里真实出现的调用名（先剥注释，注释里的"调用"不算；控制关键字不算）。"""
    names = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", strip_comments(code)))
    return names - _CONTROL_KEYWORDS


def _declared_names(code: str) -> set[str]:
    """main.c 自己**定义**的函数名（检测报告函数、平台垫片都属框架自带）。

    判据认 `[static] <返回类型> 名字(`——工单 05 起还包括文件作用域的
    `void SysTick_Handler(void)`（mspm0 的平台垫片，**不能是 static**：它要顶掉
    启动文件里那个弱别名，内部链接的函数顶不掉，会照旧掉进 Default_Handler）。
    """
    return set(re.findall(
        r"^\s*(?:static\s+)?[A-Za-z_]\w*\s+\*?([A-Za-z_]\w*)\s*\(",
        strip_comments(code), re.MULTILINE,
    ))


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
    """同名模块在两平台的头文件名与初始化不同——渲染器必须按平台取。

    **SysConfig 初始化是注释占位（工单 02 更正）**：`SYSCFG_DL_init` 不在任何
    头文件里（`ti_msp_dl_config.h` 由 SysConfig 构建期生成），生成内核的
    「main.c 不许调不存在的接口」门禁会判它未定义——骨架 sanitize 今天就会把
    这行注释掉（既有生成链限制，见 `.scratch/architecture-deepening-v5/issues/08`）。
    所以渲染器如实输出注释占位 + 说明，**不输出一个过不了自己门禁的活调用**；
    上板前取消注释这条写在文件头与检测页清单里（不假装测过）。
    """
    code = render_main_c(
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=True)
    )
    assert '#include "debug_uart_mspm0.h"' in code
    assert '#include "debug_uart.h"' not in code
    assert "SYSCFG_DL_init" not in _called_names(code)
    assert "/* SYSCFG_DL_init(); */" in code
    assert "取消注释" in code
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
    # stm32 的 OLED 函数由母版聚合头提供（工程里没有 oled.h，见工单 02 更正）
    assert '#include "headfile.h"' in code


def test_serial_lines_end_with_crlf_so_a_terminal_does_not_overwrite():
    """**行尾策略 = 串口上一行一个 `\\r\\n`**（工单 06 定，04 的备忘点名叫这一单定）。

    为什么不能只发 `\\n`：串口助手（以及绝大多数串口终端）里裸 LF 只换行不回列，
    下一行会**接着上一行的尾巴写**——多行帮助 / 逐件回显挤成一团。库内自己的消息
    就是 `\\r\\n`（`debug_uart.c` 的 `DEBUG_PRINTF("LED: RED (lock)\\r\\n")`），
    检测程序的输出与它同口径才不打架。

    OLED 那一路**不受影响**：它是显存式整行刷新（`oled_show_text`），行尾不是它的
    概念——所以 `\\r\\n` 只加在串口出口上，不进搬运/换行逻辑（进了会被当成两个字符
    写进显存，白占两格）。
    """
    code = render_main_c(SERIAL_ONLY)
    assert 'DEBUG_PRINTF("%s\\r\\n", s);' in code, "串口出口要给每行补 CRLF"
    assert 'DEBUG_PRINTF("%s", s);' not in code
    oled_code = render_main_c(OLED_ONLY)
    assert "oled_show_text" in oled_code and "\\r\\n" not in oled_code


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
    # 框架自带的检测报告函数同理不得出现（定义了却没人调 = 死代码）
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
    assert "逐件跑检测小节" in with_channel
    lamp_only = render_main_c(LAMP_ONLY)
    assert "逐件跑检测小节" not in lamp_only
    assert "不打印任何检测结果" in lamp_only


def test_summary_report_is_the_first_line_of_output():
    """上电先跑一遍：逐件自报之前先出「板子活着」那行（bring-up 顺序）。

    判据抓的是 **main() 里第一次出字**（不是全文第一个 `hwcheck_report` 调用
    ——那是运行时的分派函数，跟"什么时候报什么"无关）。中文字面量是转义写法
    （`c_string`），所以断言先还原。
    """
    for config in (BOTH, SERIAL_ONLY, OLED_ONLY):
        code = render_main_c(config)
        body = code.split("int main(void)", 1)[1]
        first_call = re.search(r"hwcheck_report\((\"[^\n]*\")\);", body)
        assert first_call is not None, "main() 里应至少有一次检测报告调用"
        text = unescape_c_string(first_call.group(1).strip('"'))
        assert "上电" in text or "板子" in text, text


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


def _platform_master_headers(platform: str) -> set[str]:
    """该平台母版树里真实存在的头文件名（小写；生成内核的 include 解析门
    就是按"母版树 + IncludePath"认的）。"""
    root = Path(__file__).resolve().parents[1] / "library" / "masters" / platform
    if not root.is_dir():
        return set()
    return {path.name.lower() for path in root.rglob("*.h")}


def _platform_module_headers(platform: str) -> set[str]:
    """该平台**模块条目**里真实存在的头文件名（判据读盘：manifest 平台条目
    files → 名字）。

    **为什么不能"全库 rglob 同名头"**（工单 01 那条平台盲用例的教训）：
    `oled.h` / `delay.h` 在 mspm0 条目里有、在 stm32 条目里**没有**（stm32 侧
    delay/oled 由母版 `ml_delay.h` / `ml_oled.h` 提供）。全库找同名头会把
    mspm0 的头算成 stm32 的，于是 `#include "oled.h"` 被放过——真机口径下
    生成内核直接 UnresolvedIncludeError（工单 02 实测）。
    """
    modules_dir = Path(__file__).resolve().parents[1] / "library" / "modules"
    if not modules_dir.is_dir():
        return set()
    names: set[str] = set()
    for slug_dir in sorted(p for p in modules_dir.iterdir() if p.is_dir()):
        try:
            manifest = ModuleManifest.load(slug_dir)
        except Exception:
            continue  # 单条 manifest 损坏不影响本用例（库另有结构测试兜底）
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        names |= {
            Path(rel).name.lower() for rel in entry.files if rel.lower().endswith(".h")
        }
    return names


@pytest.mark.parametrize(
    "config",
    [
        HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=True),
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=True),
        HwCheckConfig(platform=PLATFORM_STM32, debug_uart=False, oled=False),
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=False, oled=False),
    ],
)
def test_every_include_resolves_in_that_platforms_real_project(config):
    """渲染出的每个 `#include "x.h"` 必须能在**该平台**的最终工程里解析（防"头名写错"）。

    判据 = 该平台母版树的头 ∪ 该平台模块条目的头 ∪ 工具链外部头
    （`ti_msp_dl_config.h`，patchers.external_headers 单源：构建期由 SysConfig
    生成，不在源码树里）。**平台过滤是本条的关键**——见 `_platform_module_headers`
    的教训说明。
    """
    known = _platform_master_headers(config.platform) | _platform_module_headers(
        config.platform
    )
    known.add("ti_msp_dl_config.h")  # 工具链外部头（构建期生成）
    code = render_main_c(config)
    unresolved = [
        header
        for header in re.findall(r'#include\s+"([^"]+)"', code)
        if header.lower() not in known
    ]
    assert unresolved == [], f"{config} 引用了该平台工程里没有的头：{unresolved}"


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
    """已配置的上下文 + TestClient，记录 holder 里的假 LLM。

    这个端点**不该碰 LLM**（spec：渲染零 LLM），所以假 LLM 的作用是"证明它没被调用"。
    模块库用**真库**：工单 03 起预览要投影接线表与冲突（判据是库内真 pins 声明 +
    真板定义），假库（dht11/oled/delay）连框架模块 `led` / `debug_uart` 都没有，
    造不出任何一条真实接线与冲突。
    """
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app
    from tests.fakes import FakeLLM

    repo = Path(__file__).resolve().parents[1]
    config_path = tmp_path / "cfg" / "config.json"
    holder = {"llm": FakeLLM()}
    ctx = AppContext(
        config_path=config_path,
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=repo / "library" / "modules",
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


# ---------------------------------------------------------------------------
# 工单 06：串口命令台的载荷（页面与产物读同一张表）+ 冲突在预览这一层就红
# ---------------------------------------------------------------------------


def test_preview_payload_carries_the_serial_console_table(real_library_client):
    """命令表进载荷，且与产物**同源**：页面说"敲 l 复测 led"，板上就一定认 l。"""
    client, _ = real_library_client
    body = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["led", "ml_mpu6050"]},
    ).json()
    console = body["console"]
    assert console["available"] is True
    assert {item["slug"]: item["command"] for item in console["commands"]} == {
        "led": "l", "ml_mpu6050": "m",
    }
    for item in console["commands"]:
        assert item["description"] and item["echo"] == f"测的是：{item['description']}"
    assert [item["command"] for item in console["legacy"]] == ["r", "y", "g", "o", "b"]
    assert console["help_command"] == "?"
    # 产物里真出现这两条分派 + 主循环里的命令台轮询（载荷不是另画的一张表）
    assert "case 'l':" in body["main_c"]
    assert "hwcheck_check_ml_mpu6050();" in body["main_c"]
    assert "hwcheck_console_poll();" in body["main_c"]


def test_preview_says_out_loud_when_there_is_no_serial(real_library_client):
    """无串口：页面**明说**不能交互式复测，产物里也没有命令循环（不静默降级）。"""
    client, _ = real_library_client
    body = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": False, "oled": True,
              "devices": ["led"]},
    ).json()
    assert body["console"]["available"] is False
    assert "不能交互式复测" in body["console"]["hint"]
    assert "hwcheck_console_poll" not in body["main_c"]
    # 命令表照给（勾上串口再生成就能用），只是这一趟不能用
    assert [item["command"] for item in body["console"]["commands"]] == ["l"]


def test_preview_400_when_two_devices_claim_the_same_command(
    real_library_client, tmp_path
):
    """两件抢同一个命令字符 = **构建期**红（预览这一层），点名两件与那个字符。

    注入只写 tmp 副本（不动真库那一份——`-n auto` 下别的 worker 正在读它，
    照 `test_preview_still_fails_loudly_when_the_recipe_file_is_broken` 的记账）。
    """
    from contest_generator.hwcheck_recipe import RECIPE_FILENAME

    client, ctx = real_library_client
    repo = Path(__file__).resolve().parents[1]
    original = (repo / "library" / RECIPE_FILENAME).read_text(encoding="utf-8")
    target = tmp_path / "recipes-command-clash.json"
    target.write_text(
        original.replace('"command": "d"', '"command": "l"', 1), encoding="utf-8"
    )
    ctx.hwcheck_recipe_path = target
    response = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["led", "oled"]},
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "led" in detail and "oled" in detail and "'l'" in detail
    assert (repo / "library" / RECIPE_FILENAME).read_text(
        encoding="utf-8") == original


# ---------------------------------------------------------------------------
# 工单 02：平台真实的 include 形态（工单 01 的平台盲守卫抓不到的那一类）
# ---------------------------------------------------------------------------


def test_stm32_does_not_include_headers_the_stm32_project_lacks():
    """stm32 侧 `oled.h` / `delay.h` 不存在——它们由母版聚合头 `headfile.h` 拉齐。

    这条是工单 02 的红证复现口：工单 01 渲染出的 stm32 main.c 引用了
    `oled.h` / `delay.h`，喂真生成内核直接 UnresolvedIncludeError。
    """
    code = render_main_c(BOTH)
    assert '#include "headfile.h"' in code  # 进门头：ml_delay / ml_led / ml_oled 都在里面
    assert '#include "debug_uart.h"' in code  # 模块提供
    assert '#include "led_instances.h"' in code  # 工程根通道宏
    assert '#include "oled.h"' not in code
    assert '#include "delay.h"' not in code


def test_stm32_rendering_never_names_mspm0_only_headers():
    for config in (BOTH, SERIAL_ONLY, OLED_ONLY, LAMP_ONLY):
        code = render_main_c(config)
        mspm0_only = {"ti_msp_dl_config.h", "debug_uart_mspm0.h", "oled.h", "delay.h", "led.h"}
        assert not (set(re.findall(r'#include\s+"([^"]+)"', code)) & mspm0_only), config


def test_mspm0_renders_its_own_module_headers_only():
    code = render_main_c(
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=True)
    )
    for header in (
        "ti_msp_dl_config.h",
        "debug_uart_mspm0.h",
        "oled.h",
        "delay.h",
        "led.h",
    ):
        assert f'#include "{header}"' in code, header
    assert '#include "headfile.h"' not in code  # 那是 stm32 母版聚合头


# ---------------------------------------------------------------------------
# 工单 02：检测工程实际要用哪些模块（不是"零模块"）
# ---------------------------------------------------------------------------


def test_hwcheck_modules_are_framework_plus_selected_channels():
    """检测程序调 led_init / delay_ms / DEBUG_PRINTF / OLED_* —— 这些模块必须真进工程。

    "一个器件都不选也能生成"指的是不选**器件**（本单还没有器件可选），
    不是"不选任何模块"：`led`（心跳）与 `delay`（节拍）是框架自带，两个通道
    各带自己的模块。判据单源在这里，前端不参与推导。
    """
    assert hwcheck_modules(BOTH) == ("led", "delay", "debug_uart", "oled")
    assert hwcheck_modules(SERIAL_ONLY) == ("led", "delay", "debug_uart")
    assert hwcheck_modules(OLED_ONLY) == ("led", "delay", "oled")
    assert hwcheck_modules(LAMP_ONLY) == ("led", "delay")


def test_channel_vocabulary_mirrors_the_frontend():
    """通道词表跨语言镜像（照 library.MODULE_KIND 的 JS 镜像守卫先例）。

    前端 `fx/hwcheck.js` 的 `HWCHECK_CHANNEL_KEYS` 是勾选框的键（`hwcheckPickState`
    按它过滤），后端按同一套通道名推导模块集。**两边各写一份而无人对账**的话，
    改了一边另一边会静默失效（勾了没反应 / 勾了不进工程）——故读真源码对账。
    """
    fx = (
        Path(__file__).resolve().parents[1]
        / "src" / "contest_generator" / "static" / "js" / "fx" / "hwcheck.js"
    ).read_text(encoding="utf-8")
    match = re.search(r"HWCHECK_CHANNEL_KEYS\s*=\s*\[([^\]]*)\]", fx)
    assert match, "fx/hwcheck.js 里应有 HWCHECK_CHANNEL_KEYS 字面量"
    js_keys = tuple(re.findall(r'"([a-z_]+)"', match.group(1)))
    assert js_keys == HWCHECK_CHANNELS, (
        f"前端通道词表 {js_keys} 与后端 {HWCHECK_CHANNELS} 不一致"
    )


# ---------------------------------------------------------------------------
# 工单 02：上板清单「应看到什么 / 不对先查哪里」（3-6 条，逐项可勾选）
# ---------------------------------------------------------------------------


def _all_configs():
    for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
        for debug_uart in (True, False):
            for oled in (True, False):
                yield HwCheckConfig(platform=platform, debug_uart=debug_uart, oled=oled)


def test_checklist_has_three_to_six_unique_chinese_items_for_every_form():
    for config in _all_configs():
        items = render_checklist(config)
        assert 3 <= len(items) <= 6, (config, len(items))
        assert len({item.id for item in items}) == len(items), "清单条目 id 必须唯一"
        for item in items:
            assert re.search(r"[\u4e00-\u9fff]", item.expect), item
            assert re.search(r"[\u4e00-\u9fff]", item.check), item


def test_checklist_follows_the_channels_that_are_actually_present():
    """清单不许提"看不到的东西"：没勾串口就不该有串口那一条。"""
    both = {item.id for item in render_checklist(BOTH)}
    assert "serial" in both and "oled" in both and "heartbeat" in both
    serial_only = {item.id for item in render_checklist(SERIAL_ONLY)}
    assert "serial" in serial_only and "oled" not in serial_only
    lamp_only = {item.id for item in render_checklist(LAMP_ONLY)}
    assert "serial" not in lamp_only and "oled" not in lamp_only
    assert "no-channel" in lamp_only, "没有输出通道时必须明说「只能看灯闪」，不许含糊"
    lamp_text = " ".join(
        item.expect + item.check for item in render_checklist(LAMP_ONLY)
    )
    assert "灯" in lamp_text


def test_checklist_always_covers_heartbeat_and_reset():
    """最小的两条在任何形态下都在：灯闪 = 程序在跑；复位重跑 = 现象可重复。"""
    for config in _all_configs():
        ids = {item.id for item in render_checklist(config)}
        assert {"flash", "heartbeat", "reset"} <= ids, config


def test_checklist_is_pure_and_deterministic():
    assert render_checklist(BOTH) == render_checklist(BOTH)


def test_mspm0_checklist_says_the_syscfg_init_must_be_uncommented():
    """mspm0 侧如实告知既有限制：不取消注释外设就不初始化（不假装测过）。"""
    ids = {item.id for item in render_checklist(
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=False)
    )}
    assert "syscfg-init" in ids
    assert "syscfg-init" not in {item.id for item in render_checklist(BOTH)}
    text = " ".join(
        item.expect + item.check
        for item in render_checklist(HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=False))
    )
    assert "SYSCFG_DL_init" in text and "注释" in text


def test_checklist_item_shape_is_a_frozen_dataclass():
    item = render_checklist(BOTH)[0]
    assert (item.id, item.expect, item.check) == (
        item.id, item.expect, item.check,
    )
    with pytest.raises(Exception):
        item.expect = "改不动"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 工单 02：端点（生成 / 最近 / 回读）——真库真母版，产出到 tmp
# ---------------------------------------------------------------------------


@pytest.fixture()
def real_library_client(tmp_path):
    """真库 + 真母版的 TestClient：生成落 tmp（桌面目录也重定向到 tmp）。

    为什么这里不用假库：本单要证的正是"渲染出的 main.c 能在**真库真母版**上过
    生成门禁"（工单 01 的假库用例抓不到 stm32 头名写错）。stm32 母版只有 43
    个文件 / 1 MB，生成一次很便宜；桌面目录重定向保证不碰用户桌面。
    """
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app
    from tests.fakes import FakeLLM

    repo = Path(__file__).resolve().parents[1]
    desktop = tmp_path / "desktop"
    desktop.mkdir()
    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=repo / "library" / "modules",
            masters_dir=repo / "library" / "masters",
        ),
        llm_factory=lambda config: FakeLLM(),
        desktop_dir=lambda: desktop,
    )
    return TestClient(create_app(ctx)), ctx


def test_generate_endpoint_writes_a_full_project_and_skips_contest_side_effects(
    real_library_client, tmp_path
):
    """生成端到端：新子目录里是完整工程；演示脚本不写；最近工程记录一条不落。"""
    from contest_generator.context_manifest import (
        CONTEXT_MANIFEST_FILENAME,
        read_context_fields,
    )
    from contest_generator.recent_jobs import recent_file

    client, ctx = real_library_client
    output_parent = tmp_path / "out"
    output_parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={
            "platform": PLATFORM_STM32,
            "debug_uart": True,
            "oled": True,
            "parent_dir": str(output_parent),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    project = Path(body["output_dir"])
    assert project.parent == output_parent
    assert re.fullmatch(r"hwcheck-stm32-\d{8}-\d{6}", project.name), project.name
    # 完整工程树：母版工程文件 + main.c + README + 上下文清单
    assert (project / "user" / "Project.uvprojx").is_file()
    assert (project / "README.md").is_file()
    assert (project / CONTEXT_MANIFEST_FILENAME).is_file()
    assert (project / "main.c").read_text(encoding="utf-8") == body["main_c"]
    assert body["main_c"] == render_main_c(
        HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=True)
    )
    # 演示脚本不写（spec：检测工程本来就没内容可演示）
    assert not (project / "演示脚本.md").exists()
    # 上下文清单：kind = hwcheck + 实际进工程的模块集（依赖展开后 ——
    # config 是 debug_uart 声明的依赖，展开由生成内核做，本单不重复推导）；
    # 判据用**包含**而不是精确相等：框架模块或依赖声明一增，这条不该假红
    # （工单 02 评审整改）。
    fields = read_context_fields(project)
    assert fields["kind"] == "hwcheck"
    assert fields["platform"] == PLATFORM_STM32
    slugs = set(fields["slugs"])
    assert {"led", "delay", "debug_uart", "oled"} <= slugs
    assert slugs - {"led", "delay", "debug_uart", "oled", "config"} == set(), (
        f"不该有别的模块进工程：{sorted(slugs)}"
    )
    assert list(fields["main_c"]) == list(body["main_c"])
    # 最近工程记录一条不落（票面硬要求：检测工程不污染赛题工作流）
    assert not recent_file(ctx.config_path).exists()
    assert client.get("/api/recent").json() == []


def test_generate_endpoint_each_run_gets_a_new_directory(real_library_client, tmp_path):
    """连生成两次 = 两个新目录，谁也不覆盖谁（不静默改名、也不复用）。"""
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    payload = {"platform": PLATFORM_STM32, "debug_uart": False, "oled": False,
               "parent_dir": str(parent)}
    first = Path(client.post("/api/hwcheck/generate", json=payload).json()["output_dir"])
    second = Path(client.post("/api/hwcheck/generate", json=payload).json()["output_dir"])
    assert first != second
    assert first.is_dir() and second.is_dir()
    assert (first / "main.c").is_file() and (second / "main.c").is_file()


def test_generate_endpoint_defaults_the_parent_to_the_desktop_dir(
    real_library_client,
):
    client, ctx = real_library_client
    body = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "debug_uart": False, "oled": False},
    ).json()
    assert Path(body["output_dir"]).parent == ctx.desktop_dir()


def test_generate_endpoint_rejects_a_missing_parent_directory_400(
    real_library_client, tmp_path
):
    client, _ = real_library_client
    response = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "parent_dir": str(tmp_path / "打错的路")},
    )
    assert response.status_code == 400, response.text
    assert "父目录" in response.json()["detail"]


def test_generate_endpoint_rejects_unknown_platform_400(real_library_client):
    client, _ = real_library_client
    response = client.post("/api/hwcheck/generate", json={"platform": "arduino"})
    assert response.status_code == 400, response.text
    assert "arduino" in response.json()["detail"]


def test_generate_endpoint_returns_the_board_checklist(real_library_client, tmp_path):
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    body = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "parent_dir": str(parent)},
    ).json()
    items = body["checklist"]
    assert 3 <= len(items) <= 6
    assert {"id", "expect", "check"} == set(items[0])
    assert [item["id"] for item in items] == [
        item.id for item in render_checklist(
            HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=False)
        )
    ]


def test_generate_endpoint_mspm0_serial_only(real_library_client, tmp_path):
    """mspm0 侧（未上真机验证，但端点必须能生成）：真库真母版 + 只开串口。

    只开串口是有原因的——mspm0 默认「串口 + OLED」会撞 PA22（OLED_SPI_RES 对
    DEBUG_UART RX），生成内核如实 400（见下一条用例）。本单不引引脚配置 UI，
    出路是用户在检测页取消勾选其中一个通道。
    """
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": False,
              "parent_dir": str(parent)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    project = Path(body["output_dir"])
    assert (project / "mspm0.syscfg").is_file()
    assert "SYSCFG_DL_init" not in _called_names(body["main_c"])


def test_generate_endpoint_mspm0_both_channels_conflict_is_reported_400(
    real_library_client, tmp_path
):
    """已知限制（如实记录，不假装）：mspm0 默认双通道撞 PA22 → 400 中文。

    ⚠ **后续工单若给检测页引入自动配置 / 引脚配置，这条用例应当改成"能生成"**。
    它现在钉的是"引擎如实报错、不静默产出一个编译不过的工程"。
    """
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": True,
              "parent_dir": str(parent)},
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "引脚冲突" in detail and "PA22" in detail


def test_recent_endpoint_lists_only_this_feature_projects(real_library_client, tmp_path):
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    (parent / "2024H_Auto_Car_STM32").mkdir()  # 赛题工程不进列表
    for _ in range(2):
        client.post(
            "/api/hwcheck/generate",
            json={"platform": PLATFORM_STM32, "debug_uart": False, "oled": False,
                  "parent_dir": str(parent)},
        )
    body = client.get("/api/hwcheck/recent", params={"parent_dir": str(parent)}).json()
    names = [item["name"] for item in body["items"]]
    assert len(names) == 2
    assert all(name.startswith("hwcheck-stm32-") for name in names)
    assert names == sorted(names, reverse=True), "新→旧"
    assert body["items"][0]["platform"] == PLATFORM_STM32

    assert client.get(
        "/api/hwcheck/recent", params={"parent_dir": str(tmp_path / "nope")}
    ).json() == {"items": []}


def test_recent_endpoint_rejects_a_bad_limit_400_chinese(real_library_client):
    """limit 非法 → **400 中文**（不是 FastAPI 的 422 + 英文 detail）。

    查询参数刻意收成字符串：`int` 参数校验失败会走 FastAPI 自己的错误通道，
    绕过 errors.py 的「中文 message 唯一出口」（工单 02 评审整改）。
    """
    client, _ = real_library_client
    for bad in ("abc", "0", "-1", "2.5"):
        response = client.get("/api/hwcheck/recent", params={"limit": bad})
        assert response.status_code == 400, (bad, response.status_code, response.text)
        detail = response.json()["detail"]
        assert "limit" in detail and "正整数" in detail
    assert client.get("/api/hwcheck/recent", params={"limit": "2"}).status_code == 200


def test_project_endpoint_renders_back_a_generated_project(real_library_client, tmp_path):
    """回读：给目录 → 平台 / 通道 / main.c / 清单（刷新回显的服务端真源）。"""
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": True,
              "parent_dir": str(parent)},
    ).json()
    response = client.get(
        "/api/hwcheck/project", params={"output_dir": generated["output_dir"]}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["output_dir"] == generated["output_dir"]
    assert body["platform"] == PLATFORM_STM32
    assert body["debug_uart"] is True and body["oled"] is True
    assert body["main_c"] == generated["main_c"]
    assert body["checklist"] == generated["checklist"]
    assert body["output_hint"] == generated["output_hint"]


def test_revise_context_rejects_a_hwcheck_project_400(real_library_client, tmp_path):
    """赛题侧入口不许把检测工程当赛题工程读（`kind` 的用途落地处）。

    修订 / 深化要题面与功能需求，检测工程两样都没有——不拦的话用户会看到一份
    "缺题面 / 缺需求"的残缺上下文，以为是自己生成错了。旧清单（缺 `kind`）=
    赛题工程，走兼容路径不受影响（tests/test_revision.py 全绿即证）。
    """
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "parent_dir": str(parent)},
    ).json()
    response = client.post(
        "/api/revise/context", json={"output_dir": generated["output_dir"]}
    )
    assert response.status_code == 400, response.text
    assert "检测工程" in response.json()["detail"]


def test_project_endpoint_rejects_a_contest_project_400(real_library_client, tmp_path):
    """赛题工程（kind 缺省 = contest）不能被当成检测工程回读。"""
    import json as _json

    from contest_generator.context_manifest import CONTEXT_MANIFEST_FILENAME

    client, _ = real_library_client
    contest = tmp_path / "2024H_Auto_Car_STM32"
    contest.mkdir()
    (contest / CONTEXT_MANIFEST_FILENAME).write_text(
        _json.dumps({"version": 1, "platform": PLATFORM_STM32, "slugs": ["led"]}),
        encoding="utf-8",
    )
    response = client.get("/api/hwcheck/project", params={"output_dir": str(contest)})
    assert response.status_code == 400, response.text
    assert "检测工程" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 工单 03：器件选择（配置形状 + 模块集 + 端点载荷）
# ---------------------------------------------------------------------------


def test_devices_default_to_empty_and_do_not_change_the_module_set():
    """不选器件 = 工单 02 的模块集逐项不变（旧调用点零回归）。"""
    config = HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=True)
    assert config.devices == ()
    assert hwcheck_modules(config) == ("led", "delay", "debug_uart", "oled")
    assert render_main_c(config) == render_main_c(
        HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=True, devices=())
    )


def test_selected_devices_join_the_module_set_after_the_channels():
    """选中的器件进工程（顺序：框架 → 通道 → 器件）——接线表才与工程 README 同源。"""
    config = HwCheckConfig(
        platform=PLATFORM_MSPM0, debug_uart=True, oled=False,
        devices=("ml_mpu6050", "sr04"),
    )
    assert hwcheck_modules(config) == ("led", "delay", "debug_uart", "ml_mpu6050", "sr04")


def test_device_list_is_deduplicated_and_order_preserving():
    """同一件选两次 / 与框架模块重名 = 只算一次（不因为重复把依赖展开跑两遍）。"""
    config = HwCheckConfig(
        platform=PLATFORM_STM32, debug_uart=False, oled=False,
        devices=("led", "ml_mpu6050", "led", "ml_mpu6050"),
    )
    assert config.devices == ("led", "ml_mpu6050", "led", "ml_mpu6050")
    assert hwcheck_modules(config) == ("led", "delay", "ml_mpu6050")


@pytest.mark.parametrize("bad", ["ml_mpu6050", ("", "led"), ("led", 3), ("led", None)])
def test_devices_must_be_nonempty_strings(bad):
    """器件是 slug 字符串：空串 / 非字符串一律 400 中文（不静默丢掉一个坏值）。"""
    with pytest.raises(HwCheckError):
        HwCheckConfig(
            platform=PLATFORM_STM32, debug_uart=False, oled=False, devices=bad
        )


def test_preview_payload_carries_the_board_view_for_the_selected_devices(
    real_library_client,
):
    """预览即带上板侧视图：接线行含所选器件、顺序里它的 bring_up=False。"""
    client, _ = real_library_client
    response = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": False,
              "devices": ["ml_mpu6050"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["devices"] == ["ml_mpu6050"]
    wiring = body["wiring"]
    pins = {(row["slug"], row["pin"]) for row in wiring["rows"]}
    assert ("ml_mpu6050", "PA1") in pins and ("ml_mpu6050", "PA0") in pins
    assert [item["slug"] for item in wiring["order"]][-1] == "ml_mpu6050"
    assert wiring["guide"] and wiring["reason"] and wiring["footnote"]


def test_preview_reports_a_device_without_this_platform_entry(real_library_client):
    """本平台没有条目的器件：预览就点名"无法检测"（不静默省略）。"""
    client, _ = real_library_client
    body = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": False, "oled": False,
              "devices": ["sr04"]},
    ).json()
    missing = body["wiring"]["missing"]
    assert [item["slug"] for item in missing] == ["sr04"]
    assert "无本平台版本" in missing[0]["message"]


def test_preview_rejects_a_device_that_is_not_in_the_library(real_library_client):
    """库外 slug → 400 中文（未知模块异常已登记；不静默当空）。"""
    client, _ = real_library_client
    response = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "devices": ["nope-不存在"]},
    )
    assert response.status_code == 400, response.text
    assert "nope-不存在" in response.json()["detail"]


def test_generate_wiring_rows_equal_the_generated_readme_pin_table(
    real_library_client, tmp_path
):
    """**票面硬要求端到端**：返回的接线行 = 落盘工程 README 的引脚接线表（逐格）。

    左边 = `/api/hwcheck/generate` 给页面的行，右边 = 真生成出来的 README.md 里
    那张表（解析回来）。两条路任何一处另写推导，这里立刻分叉。
    """
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": False,
              "devices": ["ml_mpu6050"], "parent_dir": str(parent)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    readme = (Path(body["output_dir"]) / "README.md").read_text(encoding="utf-8")
    table = parse_pin_table(readme)
    assert table, "生成的 README 里应有引脚接线表"
    core = ("slug", "role", "role_id", "role_label", "pin", "remark")
    assert [tuple(row[k] for k in core) for row in body["wiring"]["rows"]] == [
        tuple(row[k] for k in core) for row in table
    ]
    # 板载注记不改变行本体，但页面要能看到它（地猛星 PA0/PA1 与板载 LED 同脚）
    assert {row["pin_note"] for row in body["wiring"]["rows"] if row["pin"] == "PA0"}


def test_generate_records_devices_in_the_context_manifest(
    real_library_client, tmp_path
):
    """器件选择落进上下文清单（回读的服务端真源），slugs 里也真的含它。"""
    from contest_generator.context_manifest import read_context_fields

    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    body = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["ml_mpu6050"], "parent_dir": str(parent)},
    ).json()
    fields = read_context_fields(Path(body["output_dir"]))
    assert fields["kind"] == "hwcheck"
    assert fields["devices"] == ["ml_mpu6050"]
    assert "ml_mpu6050" in fields["slugs"]
    assert body["modules"] and "ml_mpu6050" in body["modules"]


def test_project_endpoint_restores_the_device_selection(real_library_client, tmp_path):
    """回读把器件选择一起读回来（刷新后 chip 与接线表仍然一致）。"""
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": False,
              "devices": ["ml_mpu6050"], "parent_dir": str(parent)},
    ).json()
    body = client.get(
        "/api/hwcheck/project", params={"output_dir": generated["output_dir"]}
    ).json()
    assert body["devices"] == ["ml_mpu6050"]
    assert body["wiring"]["rows"] == generated["wiring"]["rows"]
    assert body["wiring"]["order"] == generated["wiring"]["order"]


def test_project_endpoint_reports_mspm0_default_channel_conflict(
    real_library_client, tmp_path
):
    """默认双通道（mspm0）的 PA22 冲突：**生成之前**页面就能看见（工单 02 的 400 前置）。

    这条同时钉住"生成门禁与页面预警同判据"：生成会 400 报 PA22，页面预警也报 PA22。
    """
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_MSPM0, "debug_uart": False, "oled": False,
              "parent_dir": str(parent)},
    ).json()
    assert generated["wiring"]["groups"] == []  # 只开灯：默认集没有同脚
    conflict = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": True},
    ).json()["wiring"]["groups"]
    assert [g["pin"] for g in conflict if g["kind"] == "conflict"] == ["PA22"]
    refused = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": True,
              "parent_dir": str(parent)},
    )
    assert refused.status_code == 400
    assert "PA22" in refused.json()["detail"], "页面预警与生成门禁报的是同一个脚"


# ---------------------------------------------------------------------------
# 工单 module-hwcheck/04：逐件专精小节进检测程序（配方驱动、零 LLM）
# ---------------------------------------------------------------------------

LED_STM32 = RecipeSection(
    slug="led", platform=PLATFORM_STM32,
    init=("led_init(LED_RED)",),
    read=(RecipeRead(expression="LED_CHANNEL_COUNT"),),
    note=("stm32 三色通道",),
)


def test_sections_add_their_calls_and_a_summary_to_main():
    """有专精件：main() 里逐件调用 + 结尾汇总；文件头列出这一趟测了哪几件。"""
    code = render_main_c(SERIAL_ONLY, (LED_STM32,))
    body = code.split("int main(void)", 1)[1]
    assert "hwcheck_check_led();" in body          # 逐件小节被调用
    assert "hwcheck_summary();" in body            # 结尾汇总
    assert "上电：板子活着" in unescape_c_string(body)
    head = code.split("int main(void)", 1)[0]
    assert "[专精] led" in head                    # 文件头说清这一趟测了哪几件
    assert "hwcheck_check_led" in code             # 小节函数本体在
    assert "led_init(LED_RED)" in code


def test_no_sections_keeps_the_framework_only_form():
    """没有专精件：不渲染任何逐件小节，也不渲染假的"0 件通过"汇总。

    ⚠ 工单 07 改写了文件头那一句（原话是"选了器件却没有配方时会如实写在这里"
    ——通用降级落地后那句话**变成了假话**：没配方的器件现在真出小节，只是不带
    `[专精]`）。所以这里钉的是新实话："一件器件都没测"。陈旧文案当场修是本仓库
    的既有标准（04/05 的评审同款）。
    """
    code = render_main_c(SERIAL_ONLY, ())
    assert "hwcheck_check_" not in code
    assert "hwcheck_generic_" not in code
    assert "hwcheck_summary();" not in code
    assert "一件器件都没测" in code
    assert "hwcheck_section(" not in code


def test_sections_require_an_output_channel_to_be_rendered():
    """**不假装测过**：没有输出通道时不渲染逐件小节——渲染了也没人看得见。

    这条是工单 01 那条结构断言（没通道 = 一个打印调用都没有）在工单 04 上的
    延伸：小节里的判定全靠打印，没通道就等于"跑了但没有任何结论"。

    判据同时钉住**不留悬空调用**：小节与汇总都不渲染时，`hwcheck_summary()`
    这个调用也不许出现（否则生成的 main.c 会调用一个从未定义的函数——本次
    实测踩到过，编译期才会发现）。
    """
    code = render_main_c(LAMP_ONLY, (LED_STM32,))
    assert "hwcheck_check_led" not in code
    assert "hwcheck_report" not in code
    assert "hwcheck_summary" not in code
    assert "hwcheck_section" not in code
    assert "led_init(LED_RED)" in code   # 心跳仍在（那是框架）
    # 文件头不得列出"这一趟测了 led"——它不会被跑
    assert "[专精] led" not in code


# ---------------------------------------------------------------------------
# 工单 module-hwcheck/07：通用降级小节接进框架
# ---------------------------------------------------------------------------


def _generic_stm32(slug: str = "sht20") -> list[GenericSection]:
    """真实库的一格通用件（sht20 × stm32，含总线扫描）——判据用真数据。"""
    library = Path(__file__).resolve().parents[1] / "library" / "modules"
    manifest = next(m for m in list_modules(library) if m.slug == slug)
    entry = manifest.platforms[PLATFORM_STM32]
    headers = [
        (rel, (library / slug / rel).read_text(encoding="utf-8"))
        for rel in entry.files if rel.lower().endswith(".h")
    ]
    return [plan_generic_section(PLATFORM_STM32, manifest, headers)]


def test_generic_sections_render_with_their_own_header_and_no_specialized_tag():
    """通用小节：函数本体 + main() 里调用 + 自带 include + 文件头如实标注。

    `[专精]` 一个字都不许出现在通用件那一节（外观可区分是票面验收线）——
    专精标记只属于"真测了"的那几件。
    """
    code = render_main_c(SERIAL_ONLY, (), _generic_stm32())
    assert '#include "sht20_stm32.h"' in code
    assert "static void hwcheck_generic_sht20(void)" in code
    assert "sht20_init();" in code
    assert "hwcheck_i2c_scan(" in code
    body = code.split("int main(void)", 1)[1]
    assert "hwcheck_generic_sht20();" in body
    assert "hwcheck_summary();" in body
    head = code.split("int main(void)", 1)[0]
    assert GENERIC_LABEL in unescape_c_string(head)
    assert "sht20" in head
    assert SECTION_TAG not in code


def test_generic_only_form_renders_the_shared_runtime_but_not_the_recipe_one():
    """只有通用件时：共用运行时（分节 / 细节 / 汇总）照渲染，专精判定不渲染。

    判定走 `hwcheck_verdict` 的只有"初始化带期望"与"通信探头"两类，通用件
    一个都没有——渲染了就是死代码（ARMCC `#177-D`）。但 `hwcheck_section` /
    `hwcheck_detail` / `hwcheck_verdict_probe_none` / `hwcheck_summary` 必须
    在（通用小节真的会调它们，缺一个就是悬空调用）。

    ⚠ 断言必须钉**定义**（`static void hwcheck_verdict_probe_none(...)`）而不是
    "名字出现在产物里"：调用的那个名字也在产物里——只查名字的写法在本单的判据
    强度探针里被证明是**摆设**（注入"needs_probe_none 不算通用件"后它照样绿，
    见 `negative-verify-07.py` 的 P 条）。
    """
    code = render_main_c(SERIAL_ONLY, (), _generic_stm32())
    assert "static void hwcheck_section(const char *title)" in code
    assert "static void hwcheck_detail(const char *text)" in code
    assert "static void hwcheck_verdict_probe_none(const char *hint)" in code
    assert "static void hwcheck_summary(void)" in code
    assert "hwcheck_verdict(" not in code
    assert "hwcheck_summary_fail" not in code


def test_generic_only_artifact_calls_no_undefined_helper():
    """**悬空调用守卫**：产物里调用的每个 `hwcheck_*` 都必须有对应定义。

    这条抓的是一整类"两半对不上"的缺陷：调用侧渲染了、定义侧按需渲染时漏了
    ——生成的程序调用一个从未定义的函数，**编译期才发现**（学生那边就是一句
    `undefined symbol`，而生成的 main.c 是给他读的）。工单 07 的判据强度探针
    实测抓到过一次（`needs_probe_none` 忘了算上通用件），所以按调用/定义两面查。
    """
    for generic in (_generic_stm32("sht20"), _generic_stm32("beep")):
        code = render_main_c(SERIAL_ONLY, (), generic)
        defined = set(re.findall(
            r"^\s*static\s+[A-Za-z_]\w*\s+\*?([A-Za-z_]\w*)\s*\(",
            code, re.MULTILINE,
        ))
        called = {name for name in _called_names(code) if name.startswith("hwcheck_")}
        assert called <= defined, sorted(called - defined)


def test_every_reported_line_fits_the_line_buffer():
    """**行缓冲守卫**：任何一条整行文案都不许超过 `hwcheck_line[128]`。

    溢出保护是框架刻意的（宁可截一行，不让程序跑飞），但**截在哪儿**是学生看到
    的东西：中文在 UTF-8 下一字 3 字节，超长会截在字中间——工单 07 的行为探针
    真跑时抓到「无应答：…（有没有接反）」那一行末尾变成半个多字节字符（终端
    显示 `�`）。所以整行文案的字节数必须留出余量。

    判据 = 产物里每个 `hwcheck_report("…")` 的**字符串字面量**（八进制转义还原
    成原文再数字节；单个字符的碎片行也一并数，反正它们更短）。
    """
    buffer_bytes = 128
    variants = (
        (SERIAL_ONLY, (), _generic_stm32("sht20")),
        (SERIAL_ONLY, (), _generic_stm32("beep")),
        (SERIAL_ONLY, (), _generic_stm32("servo")),
        (SERIAL_ONLY, (LED_STM32,), _generic_stm32("sht20")),
        (SERIAL_ONLY, (LED_STM32,), ()),
        (SERIAL_ONLY, (_mpu_section(PLATFORM_STM32),), ()),
        (BOTH, (_mpu_section(PLATFORM_STM32), LED_STM32), _generic_stm32("sht20")),
    )
    for config, sections, generic in variants:
        code = render_main_c(config, sections, generic)
        for literal in re.findall(r'hwcheck_report\(("(?:[^"\\]|\\.)*")\)', code):
            text = decode_c_string(literal.strip('"'))
            size = len(text.encode("utf-8"))
            assert size < buffer_bytes, (
                f"这一行文案 {size} 字节，会撞上 {buffer_bytes} 字节的行缓冲："
                f"{text!r}"
            )


def test_generic_sections_require_an_output_channel_too():
    """没有输出通道时通用小节同样不渲染（渲染了也没人看得见，见 04 的同款判据）。"""
    code = render_main_c(LAMP_ONLY, (), _generic_stm32())
    assert "hwcheck_generic_sht20" not in code
    assert "hwcheck_report" not in code
    assert "hwcheck_summary" not in code
    assert "sht20_init();" not in code


def test_a_scan_less_generic_run_declares_no_ping_helper():
    """按需渲染：没有 I2C 扫描件时不留 ping 助手（0 warning 的验收线）。"""
    code = render_main_c(SERIAL_ONLY, (), _generic_stm32("ws2812"))
    assert "hwcheck_i2c_ping" not in code
    assert "hwcheck_i2c_scan" not in code
    assert "ws2812_init();" in code
    with_scan = render_main_c(SERIAL_ONLY, (), _generic_stm32("sht20"))
    assert "hwcheck_i2c_ping" in with_scan


def test_the_console_never_dispatches_a_generic_section():
    """通用件**不进命令表**（06 的接口备忘）：没有配方就没有命令字符可敲。

    判据 = 通用小节函数在产物里**只被 main() 调用一次**（命令台的 switch 里
    一次都不许出现）——出现了就是"页面没有这个命令、板上却有"的分家。
    """
    code = render_main_c(
        HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=False),
        (), _generic_stm32())
    assert "hwcheck_console_poll" in code          # 命令台在（有串口就有）
    assert code.count("hwcheck_generic_sht20();") == 1
    assert "hwcheck_check_sht20" not in code


def test_a_mix_of_specialized_and_generic_sections_renders_both_in_order():
    """两批同堂：先专精小节、再通用小节，两边都在 main() 里被调用。

    顺序不是风格问题：专精件带板端判定，是这一趟的主结果；通用件是走过场，
    排在后面学生一眼看得出"哪些是真测的"。
    """
    code = render_main_c(SERIAL_ONLY, (LED_STM32,), _generic_stm32())
    assert code.index("hwcheck_check_led") < code.index("hwcheck_generic_sht20")
    body = code.split("int main(void)", 1)[1]
    assert "hwcheck_check_led();" in body
    assert "hwcheck_generic_sht20();" in body
    assert "hwcheck_check_led();" in body.split("hwcheck_generic_sht20();")[0]
    head = code.split("int main(void)", 1)[0]
    assert "[专精] led" in head and "sht20" in head


def test_a_bus_scan_brings_in_pin_config_and_resolves_it():
    """**真机判例**：扫描要用工程根的引脚宏，而 `headfile.h` **不带** pin_config.h。

    宿主机行为探针（`.scratch/module-hwcheck/probe-07-scan-behaviour.py`）第一次跑
    就报 `SHT20_SCL_GPIO undeclared`——真机 UV4 同样编不过。所以有扫描件时产物必须
    自己 include `pin_config.h`，且这个头在**该平台的真实工程里解析得到**
    （判据与 `test_every_include_resolves_in_that_platforms_real_project` 同一处：
    母版树 ∪ 模块条目的头 ∪ 工具链外部头）。
    """
    code = render_main_c(SERIAL_ONLY, (), _generic_stm32("sht20"))
    assert '#include "pin_config.h"' in code
    known = (_platform_master_headers(PLATFORM_STM32)
             | _platform_module_headers(PLATFORM_STM32)
             | {"ti_msp_dl_config.h"})
    unresolved = [
        header for header in re.findall(r'#include\s+"([^"]+)"', code)
        if header.lower() not in known
    ]
    assert unresolved == [], unresolved
    # 没有扫描的形态不该平白多这一行（它不是这工程的一般依赖）
    no_scan = render_main_c(SERIAL_ONLY, (), _generic_stm32("beep"))
    assert '#include "pin_config.h"' not in no_scan


def test_preview_still_fails_loudly_when_the_recipe_file_is_broken(
    real_library_client, tmp_path
):
    """**不许用"取不到配方"换"能出接线表"**：库内配方坏了时，预览必须 400 点名
    ——不做"配方读失败就跳过、接线表照出"的降级。

    这条钉的是装配路径上的一处诱惑：接线表只需要模块库，于是很容易写成"配方
    读不到就算了"。那样坏配方会悄悄溜过去（学生在页面上什么异常都看不到），
    而这正是本单要防的「看着测了其实没测」。

    坏配方写进**本用例自己的 tmp 文件**（`AppContext.hwcheck_recipe_path` 覆盖），
    不动真库那一份——真 `library/hwcheck_recipes.json` 是全仓共享夹具，`-n auto`
    下别的 worker 正在读它（本轮实测：改真文件会让并行套件里另外两条生成用例
    转红、串行却全绿）。
    """
    client, ctx = real_library_client
    broken = tmp_path / "hwcheck_recipes.json"
    broken.write_text("{ 这不是 JSON", encoding="utf-8")
    ctx.hwcheck_recipe_path = broken
    response = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["led"]},
    )
    assert response.status_code == 400, response.text
    assert "hwcheck_recipes.json" in response.json()["detail"]


def test_every_platforms_recipe_is_judged_when_the_masters_are_configured(
    real_library_client, tmp_path
):
    """母版配齐时**两个平台都不免检**：任一处拼错，任何一次预览都 400。

    这条回答评审的一个合理追问（"没导入母版 = 全平台免检？"）：装配点对
    **每个已注册平台**都单独装一份接口 / 头名清单（`_hwcheck_recipes`），而
    `load_recipes` 校验的是**整份配方文件**——所以某一平台的配方段写错，
    即使用户当前选的是另一个平台，也会当场红（"配方写错就该当场红"）。

    判据用真库配方 + 真母版（`real_library_client`），只把注入的错**写进 tmp
    副本**：stm32 段一个函数名拼错、mspm0 段一个头名拼错，两边各验一次。
    """
    from contest_generator.hwcheck_recipe import RECIPE_FILENAME

    client, ctx = real_library_client
    repo = Path(__file__).resolve().parents[1]
    original = (repo / "library" / RECIPE_FILENAME).read_text(encoding="utf-8")
    mutations = (
        ("stm32 的函数名拼错", '"MPU6050_Init()"', '"MPU6050_InitX()"',
         "MPU6050_InitX"),
        ("mspm0 的头名拼错", '"mpu_port.h"', '"mpu_port_typo.h"',
         "mpu_port_typo.h"),
    )
    for label, old, new, needle in mutations:
        target = tmp_path / f"recipes-{needle}.json"
        target.write_text(original.replace(old, new, 1), encoding="utf-8")
        ctx.hwcheck_recipe_path = target
        for platform in (PLATFORM_STM32, PLATFORM_MSPM0):
            response = client.post(
                "/api/hwcheck/preview",
                json={"platform": platform, "debug_uart": True, "oled": False,
                      "devices": ["ml_mpu6050"]},
            )
            assert response.status_code == 400, (
                f"{label} 之后 {platform} 的预览应当 400，实际 "
                f"{response.status_code}：{response.text[:200]}")
            detail = response.json()["detail"]
            assert needle in detail, f"{label}：报错要点名那个名字：\n{detail}"
            assert "ml_mpu6050" in detail, f"{label}：报错要点名哪一件：\n{detail}"
    # 本用例从头到尾没动过真库那一份（注入只写 tmp 副本）
    assert (repo / "library" / RECIPE_FILENAME).read_text(
        encoding="utf-8") == original


def test_preview_works_when_the_master_library_is_not_configured(
    real_library_client, tmp_path
):
    """没配母版库也要能预览：配方校验在"拿不到接口清单"时**不冤枉好配方**
    （判不了就不判），页面照常给出接线表与检测计划。

    两种"没有母版"都要活：① 母版库目录在但里面是空的；② 母版库目录**根本
    不存在**（还没导入过任何母版——`rglob` 打在缺失目录上会抛，必须先判存在，
    否则检测页在没有母版的机器上直接 500）。

    ⚠ **不许动真身的 `library/masters`**：本用例把 app_config 的 masters_dir
    换成自己的 tmp_path 空目录——真目录是全仓共享的夹具，`-n auto` 下别的
    worker 正在读它（本轮实测：改真目录会让并行套件里另外两条生成用例转红、
    串行却全绿——典型的"用例把环境当夹具"，本仓库 2026-09-13 踩过同款）。
    """
    client, ctx = real_library_client
    fake_masters = tmp_path / "masters-none"
    (fake_masters / "stm32").mkdir(parents=True)
    ctx.config = replace(ctx.config, masters_dir=fake_masters)
    for label in ("目录在、里面空", "整个目录不存在"):
        response = client.post(
            "/api/hwcheck/preview",
            json={"platform": PLATFORM_STM32, "debug_uart": True,
                  "oled": False, "devices": ["led"]},
        )
        assert response.status_code == 200, f"{label}：{response.text}"
        payload = response.json()
        assert [item["slug"] for item in payload["sections"]] == ["led"], label
        assert "hwcheck_check_led();" in payload["main_c"], label
        if label == "目录在、里面空":
            shutil.rmtree(fake_masters)
    assert not fake_masters.exists()


def test_specialized_section_is_visually_distinct_from_the_framework():
    """票面验收线：专精件的段落外观可区分（[专精] 标记 + 注释块）。"""
    code = render_main_c(SERIAL_ONLY, (LED_STM32,))
    assert SECTION_TAG in code
    assert f'/* ---- {SECTION_TAG} led：按库内配方测这一件 ---- */' in code
    assert "按库内配方测这一件" in code


def test_summary_counts_three_buckets_on_the_board():
    """**不许把"没探头"算进"通过"**：三档分开数（板上算，渲染期只生成代码）。

    规格判据三层里第③层只是回显、不做板上阈值判决——所以没有读取型探头的件
    必须单独一档（"未判定"），否则学生会把"走过场"读成"测过了"。

    判据抓的**不只是文案在不在**，还包括"记账那一行真的在"：`未判定` 出现在
    汇总文案里而计数器没人加，学生看到的永远是 0 项未判定（比不写更坏）。
    """
    code = render_main_c(SERIAL_ONLY, (LED_STM32,))
    readable = unescape_c_string(code)
    assert "hwcheck_verdict_probe_none(" in code
    assert "hwcheck_summary_probe_none++;" in code   # 记账那一行真的在
    assert "未判定" in readable
    assert "没有读取型探头" in readable


def test_recipe_rendering_never_calls_a_model():
    """渲染全程零 LLM（票面验收项，结构断言）。

    判据：整条渲染路径只吃纯函数（配方解析 json / 小节渲染），`hwcheck.py` /
    `hwcheck_recipe.py` / `hwcheck_generic.py`（工单 07 的通用降级）**都不 import
    LLM 层**，`render_main_c` / `load_recipes` / `resolve_generic_sections` 的
    签名里也没有 llm 参数。
    """
    import inspect

    from contest_generator import hwcheck as hwcheck_module
    from contest_generator import hwcheck_generic as generic_module
    from contest_generator import hwcheck_recipe as recipe_module

    for module in (hwcheck_module, recipe_module, generic_module):
        source = inspect.getsource(module)
        assert "from .llm" not in source
        assert "import llm" not in source
        assert "llm." not in source
    for function in (
        hwcheck_module.render_main_c,
        recipe_module.load_recipes,
        generic_module.resolve_generic_sections,
        generic_module.plan_generic_section,
    ):
        params = inspect.signature(function).parameters
        assert not [name for name in params if "llm" in name.lower()], function


def test_preview_payload_carries_the_specialized_sections(real_library_client):
    """端点把"这一趟真测哪几件"回给页面：选中 led → 载荷里有它的专精小节。

    页面不重推判据（顺序与配方都是服务端的）：它只渲染 `sections`。
    """
    client, _ = real_library_client
    body = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["led"]},
    ).json()
    assert [item["slug"] for item in body["sections"]] == ["led"]
    section = body["sections"][0]
    assert section["tag"] == SECTION_TAG
    assert section["platform"] == PLATFORM_STM32
    assert section["note"] and section["has_probe"] is False
    assert section["init"] == ["led_init(LED_RED)"]
    # led_init 是 void：配方**不写** init_expect，载荷里也不许编一个期望值出来
    assert section["init_expect"] == ""
    assert section["read"] == [{"expression": "LED_CHANNEL_COUNT", "unit": ""}]
    # `console` 段（工单 06 起落地）：载荷里那一条命令要与**命令表**（页面用）
    # 同源——两个字段不是各写一份，是同一条通行证。04 那一版这里钉的是
    # `is None`（"命令表归工单 06"），06 落地后那句话过期了，改为钉内容。
    assert section["console"] == {
        "command": "l",
        "description": "板载 LED：重跑一次点灯初始化并回显本平台通道数",
    }
    assert body["console"]["commands"][0]["command"] == section["console"]["command"]
    assert body["console"]["commands"][0]["slug"] == section["slug"]


def test_preview_reports_devices_without_a_recipe_as_unspecialized(
    real_library_client,
):
    """没配方的器件如实标"未专精"，并说清这一趟对它做什么。

    ⚠ 夹具用的未专精件要挑**这一版真的还没有配方**的：工单 05 起
    `ml_mpu6050` 已经专精了（它正是那一单要闭环的器件），拿它当"未专精"的样本
    会变成一条假红——本用例改用 `beep`（本平台有条目、暂无配方）。

    ⚠ 工单 07 改了这条的口径：04 那一版这里钉的是"**不渲染**它的小节"
    （通用降级还没做，`unspecialized_message` 明说"本版检测程序不会给它出检测
    小节"）。07 落地后未专精件**真出小节**（只验总线和初始化），所以断言换成
    新的实话：官方标注 + 这一趟的真动作，且措辞与产物注释同一句（单源）。
    """
    client, _ = real_library_client
    body = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": False, "oled": False,
              "devices": ["led", "beep"]},
    ).json()
    assert [item["slug"] for item in body["sections"]] == ["led"]
    assert [item["slug"] for item in body["unspecialized"]] == ["beep"]
    entry = body["unspecialized"][0]
    assert entry["label"] == GENERIC_LABEL
    assert GENERIC_LABEL in entry["message"]
    assert "beep_init()" in entry["plan"]                 # 真动作，不是走过场话术
    # 没有输出通道 → 通用小节不渲染（渲染了也没人看得见，与专精件同一条判据）
    assert "hwcheck_generic_beep" not in body["main_c"]
    # 有串口那一趟：小节真进产物，检测页那句标注与产物注释**同一句**（单源）
    serial = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["led", "beep"]},
    ).json()
    code = serial["main_c"]
    assert c_string(GENERIC_LABEL) in code
    assert "hwcheck_generic_beep" in code
    assert "beep_init();" in code
    assert SECTION_TAG not in code.split("hwcheck_generic_beep")[1]


def test_preview_generic_i2c_device_carries_its_bus_scan(real_library_client):
    """端点这一层：软 I2C 件选进来就有"扫这一件那条总线"的小节与载荷。"""
    client, _ = real_library_client
    body = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["sht20"]},
    ).json()
    assert body["sections"] == []
    entry = body["unspecialized"][0]
    assert entry["slug"] == "sht20"
    assert "总线地址扫描" in entry["plan"]
    assert "hwcheck_i2c_scan(" in body["main_c"]
    assert "SHT20_SCL_GPIO" in body["main_c"]
    # 命令表里没有它（通用件没有配方 → 没有命令字符，06 的接口备忘）
    assert body["console"]["commands"] == []


def test_generate_writes_the_generic_sections_into_main_c(
    real_library_client, tmp_path
):
    """真生成：盘上的 main.c 里有通用小节，且与载荷逐字一致。"""
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["beep"], "parent_dir": str(parent)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    on_disk = (Path(body["output_dir"]) / "main.c").read_text(encoding="utf-8")
    assert on_disk == body["main_c"]
    assert body["main_c"].count("hwcheck_generic_beep();") == 1
    assert GENERIC_LABEL in unescape_c_string(body["main_c"])
    # 未专精件仍进工程（接线表与 README 同源的前提）
    assert "beep" in body["modules"]


def test_project_endpoint_reads_back_the_generic_sections(
    real_library_client, tmp_path
):
    """回读也带通用小节：刷新页面后"这一趟对它做什么"不丢。"""
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["beep"], "parent_dir": str(parent)},
    ).json()
    body = client.get(
        "/api/hwcheck/project", params={"output_dir": generated["output_dir"]},
    ).json()
    assert [item["slug"] for item in body["unspecialized"]] == ["beep"]
    assert "hwcheck_generic_beep" in body["main_c"]


def _strip_comments_keep_literals(code: str) -> str:
    """只剥注释、**保留字符串字面量内容**（守卫用的窄词法）。

    为什么不复用 `clex.strip_comments`：它同时剥字符串（那是"只看调用形态"的
    用途）——用它做本守卫会**把要查的东西一起删掉**，注入"不转义"的改动照样
    全绿（本轮实测踩到：守卫假绿）。
    """
    out: list[str] = []
    index = 0
    length = len(code)
    while index < length:
        char = code[index]
        nxt = code[index + 1] if index + 1 < length else ""
        if char == "/" and nxt == "*":
            end = code.find("*/", index + 2)
            index = length if end == -1 else end + 2
            continue
        if char == "/" and nxt == "/":
            end = code.find("\n", index)
            index = length if end == -1 else end
            continue
        if char in ('"', "'"):
            quote = char
            out.append(char)
            index += 1
            while index < length:
                out.append(code[index])
                if code[index] == "\\":
                    index += 2
                    if index - 1 < length:
                        out.append(code[index - 1])
                    continue
                if code[index] == quote:
                    index += 1
                    break
                index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


def test_generated_main_c_has_no_raw_non_ascii_outside_comments():
    """**真机编译判据**：产物里除注释外必须是纯 ASCII（中文字面量全部转义）。

    为什么这条是硬判据：Keil ARMCC 5.06 默认按本地代码页（本机 GBK）解析源文件，
    中文字面量以特定字节收尾时会把收尾引号当成前导字节的尾字节吞掉 →
    `#8: missing closing quote`，整份 main.c 编不过（实测 22 error，`.scratch/
    module-hwcheck/probe-04-compile-matrix.py` 与 `probe-04-armcc-utf8.py` 是
    复现量具）。渲染器因此把非 ASCII 一律转义成 ASCII 转义序列（工单 05 起是三位
    八进制 `\\302\\261`——`\\xNN` 会被后面的十六进制数字连读，`hwcheck_recipe.
    c_string`）。

    这条用例是那次事故的**回归守卫**：谁把渲染改回"原样输出中文"，这里立刻红
    （不用等真机编译）。
    """
    variants = (
        (BOTH, ()),
        (SERIAL_ONLY, ()),
        (OLED_ONLY, ()),
        (LAMP_ONLY, ()),
        (SERIAL_ONLY, (LED_STM32,)),
    )
    for config, sections in variants:
        code = render_main_c(config, sections)
        # 剥注释但**留着字面量**——要查的正是字面量里的裸中文
        code_only = _strip_comments_keep_literals(code)
        offenders = [
            f"{number}: {line}"
            for number, line in enumerate(code_only.splitlines(), 1)
            if any(ord(char) > 127 for char in line)
        ]
        assert not offenders, (
            f"{config.platform} / sections={len(sections)} 的产物代码里有裸非 ASCII：\n"
            + "\n".join(offenders[:5])
        )


def test_unjudgeable_sections_do_not_declare_dead_helpers():
    """一件带判定的都没有时（如只选 led）不许留死代码。

    真机编译实测：`hwcheck_verdict` / `hwcheck_summary_fail` / `hwcheck_report_int`
    在这类形态下"声明了没人调"，ARMCC 报 `#177-D`。生成的程序是给学生读的，
    死代码会让人以为漏调了什么——所以按需渲染（`_needs_verdict`）。
    """
    code = render_main_c(SERIAL_ONLY, (LED_STM32,))
    assert "hwcheck_verdict(" not in code          # 判定函数不渲染
    assert "hwcheck_summary_fail" not in code     # 失败档也不渲染
    assert "hwcheck_report_int" in code           # 但读数回显要留着（led 有读数）

    framework = render_main_c(SERIAL_ONLY, ())
    assert "hwcheck_report_int" not in framework  # 一件读数都没有：整数出口也不渲染
    assert "hwcheck_report(" in framework         # 但"板子活着"那句要留着


def test_generate_writes_the_specialized_sections_into_main_c(
    real_library_client, tmp_path
):
    """真生成一遍：写出的 main.c 里有专精小节，且盘上内容与载荷逐字一致。"""
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["led"], "parent_dir": str(parent)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    on_disk = (Path(body["output_dir"]) / "main.c").read_text(encoding="utf-8")
    assert on_disk == body["main_c"]
    assert f"{SECTION_TAG} led" in on_disk
    assert "hwcheck_check_led();" in on_disk


def test_project_endpoint_reads_back_the_specialized_sections(
    real_library_client, tmp_path
):
    """回读也带 sections（刷新页面后"这一趟测了哪几件"不丢）。"""
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    generated_response = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_MSPM0, "debug_uart": False, "oled": True,
              "devices": ["oled"], "parent_dir": str(parent)},
    )
    assert generated_response.status_code == 200, generated_response.text
    generated = generated_response.json()
    body = client.get(
        "/api/hwcheck/project", params={"output_dir": generated["output_dir"]}
    ).json()
    assert [item["slug"] for item in body["sections"]] == ["oled"]
    assert body["sections"][0]["tag"] == SECTION_TAG
    assert body["sections"] == generated["sections"]


# ---------------------------------------------------------------------------
# 工单 module-hwcheck/05：MPU6050 探头 + 平台差异（真库真配方，双平台各断言一次）
# ---------------------------------------------------------------------------


def _mpu_section(platform: str):
    """真库配方 → 该平台的 ml_mpu6050 小节（判据读真数据，不手写替身）。

    为什么要走真库：本单的交付物一半是**库内配方数据**——用替身小节测渲染，
    测的是渲染器而不是"这份数据对不对"。真库那一份过了引用校验（另一条用例
    钉住），这里再用它验渲染产物。
    """
    from contest_generator.hwcheck_recipe import (
        interface_names,
        load_recipes,
    )
    from contest_generator.library import list_modules
    from contest_generator.master_store import master_project_dir
    from contest_generator.treewalk import iter_project_files

    repo = Path(__file__).resolve().parents[1]
    modules = repo / "library" / "modules"
    manifests = list_modules(modules)

    def headers_for(name: str):
        master = master_project_dir(repo / "library" / "masters", name)
        if not master.is_dir():
            return []
        return [(path.relative_to(master).as_posix(),
                 path.read_text(encoding="utf-8", errors="replace"))
                for path in iter_project_files(master, pattern="*.h")]

    interfaces = {
        name: interface_names(manifests, modules, name, headers_for(name))
        for name in (PLATFORM_STM32, PLATFORM_MSPM0)
    }
    recipes = load_recipes(modules, manifests, interfaces)
    return recipes["ml_mpu6050"].for_platform(platform)


def test_mpu6050_stm32_renders_a_self_proving_probe_and_raw_axes():
    """stm32 侧渲染：前置起总线 → 初始化 → **自己读 WHO_AM_I 判通断** → 原始六轴。

    票面要求的三件事都在**渲染产物**上验一遍（不只是配方数据）：① 探头判 FAIL
    时打明确中文并**直接 return**（不继续打一堆无意义读数）；② 前置调用
    `I2C_Init()` 真的出现在小节里（既有驱动不初始化总线）；③ 读数回显的是
    `hwcheck_report_int(ax)` 这类整数路径。
    """
    section = _mpu_section(PLATFORM_STM32)
    code = "\n".join(render_recipe_section(section))
    readable = unescape_c_string(code)
    assert "I2C_Init();" in code                    # ① 前置调用进产物
    assert "MPU6050_Init();" in code
    assert "MPU6050_GetData();" in code             # 取数动作（六轴搬进全局量）
    assert "r = MPU6050_Read(WHO_AM_I);" in code    # ② 探头 = 身份寄存器读
    assert "== 0x68" in code                        # 期望值进比较式（板上算）
    assert "通信失败：先查供电 / 上拉 / 地址 / 线序" in readable
    assert "return;" in code                        # 不通就不再打读数
    assert "hwcheck_report_int(ax);" in code        # ③ 六轴走整数回显
    assert "hwcheck_report_int(gz);" in code
    # 本平台**不给角度**：产出的注释里也写明（学生读代码时同样看得到）
    assert "本平台（stm32）没有姿态解算" in readable


def test_mpu6050_mspm0_renders_dmp_init_probe_and_split_angles():
    """mspm0 侧渲染：声明 float → `DMP_Init` 判返回值 → DMP 探头 → 角度拆整数/小数。

    与 stm32 侧**同一次断言**（票面："双平台渲染文本各断言一次"）：这一侧出的是
    三维角度、但要拆成整数 + 小数第一位两次回显（本平台没有浮点显示接口）；
    平台差异文案（"没有浮点显示接口"）必须出现在产物里。
    """
    section = _mpu_section(PLATFORM_MSPM0)
    code = "\n".join(render_recipe_section(section))
    readable = unescape_c_string(code)
    assert "float pitch = 0;" in code                # 局部变量排在动作之前
    assert code.index("float pitch = 0;") < code.index("r = DMP_Init();")
    assert "r = DMP_Init();" in code                 # 初始化返回值 = 判定入口之一
    assert "r = DMP_Read_Data(&pitch, &roll, &yaw);" in code   # 探头（兼取数）
    assert "== 0" in code
    assert "hwcheck_report_int((int)pitch);" in code
    assert "hwcheck_report_int((int)((pitch - (int)pitch) * 10));" in code
    assert "没有浮点显示接口" in readable
    # 负例守卫：stm32 侧的六轴全局量在本平台**不该出现**（那是另一个平台的头）
    assert "MPU6050_GetData" not in code
    assert "hwcheck_report_int(ax)" not in code


def test_mspm0_main_gets_a_systick_service_and_stm32_gets_none():
    """**平台垫片**：mspm0 补空的 `SysTick_Handler`，stm32 不补（母版已有）。

    真机判例（读源码定性的，不是猜）：库内 ml_mpu6050 的 DMP 端口在
    `DMP_Init()` 里自己开 `SysTick_CTRL_TICKINT_Msk` + `__enable_irq()`，而
    mspm0 母版**没有** SysTick 服务函数、TI 启动文件把 `SysTick_Handler` 弱别名
    到 `Default_Handler`（`while (1) {}`）——缺这个空处理函数，检测程序会在
    DMP_Init() 里直接卡死（灯都不闪）。stm32 侧母版 `ml_systick.c` 已经提供了
    它，检测程序**不许**再定义一个（重复定义 = 链接期 E6200E）。
    """
    mspm0 = render_main_c(
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=False))
    assert "void SysTick_Handler(void)" in mspm0
    assert "SysTick_Handler" in _declared_names(mspm0)
    # 非 static：内部链接顶不掉启动文件里的弱别名
    assert "static void SysTick_Handler" not in mspm0
    assert "SysTick" in mspm0.split("int main(void)", 1)[0], "垫片要在文件作用域"
    stm32 = render_main_c(
        HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=False))
    assert "SysTick_Handler" not in stm32


def test_preview_payload_carries_locals_and_the_platform_note(real_library_client):
    """端点把"这一件要用什么变量 / 平台差异说什么"一起回给页面。

    `locals` 与 `note` 都是配方契约的可见面：页面不重推判据，只渲染服务端
    给的东西（note 直接印出来就是 spec 要的"平台不对称如实呈现"）。
    """
    client, _ = real_library_client
    mspm0 = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_MSPM0, "debug_uart": True, "oled": False,
              "devices": ["ml_mpu6050"]},
    ).json()["sections"]
    assert [item["slug"] for item in mspm0] == ["ml_mpu6050"]
    section = mspm0[0]
    assert section["locals"] == ["float pitch = 0", "float roll = 0", "float yaw = 0"]
    assert section["init_expect"] == "0"
    assert section["probe"] == {"calls": ["DMP_Read_Data(&pitch, &roll, &yaw)"],
                                "expect": "0"}
    notes = " ".join(section["note"])
    assert "没有浮点显示接口" in notes

    stm32 = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["ml_mpu6050"]},
    ).json()["sections"][0]
    assert stm32["locals"] == []
    assert stm32["prereq"] == ["I2C_Init()"]
    assert stm32["probe"]["expect"] == "0x68"
    assert [item["expression"] for item in stm32["read"]] == [
        "ax", "ay", "az", "gx", "gy", "gz"]
    assert "没有姿态解算" in " ".join(stm32["note"])


def test_preview_payload_carries_platform_scoped_exclusive_groups(
    real_library_client,
):
    """同组互斥（工单 05）：载荷带**按平台过滤**的库级功能组，成员取自整库。

    为什么成员要取自整库而不是"本次选中的模块集"：页面上的单选交换发生在点击的
    那一刻——用户点同组第二件时，它还没进模块集，只给选中集的成员会漏掉它。

    为什么按平台过滤 + 单成员组不出：`attitude-hold`（航向保持 / 姿态传感器）在
    mspm0 上有三件（imu_uart / jy61p / ml_mpu6050），而在 stm32 上**只有**
    ml_mpu6050 一件——一件没法互斥，`collect_exclusive_groups` 的单成员剔除与
    赛题侧生成链路同规（判据同一个函数）。
    """
    client, _ = real_library_client
    mspm0 = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_MSPM0, "debug_uart": False, "oled": False},
    ).json()["exclusive_groups"]
    attitude = [g for g in mspm0 if g["id"] == "attitude-hold"]
    assert len(attitude) == 1, mspm0
    assert {"imu_uart", "jy61p", "ml_mpu6050"} <= set(attitude[0]["members"])
    assert attitude[0]["label"]
    assert all(len(g["members"]) >= 2 for g in mspm0)

    stm32 = client.post(
        "/api/hwcheck/preview",
        json={"platform": PLATFORM_STM32, "debug_uart": False, "oled": False},
    ).json()["exclusive_groups"]
    assert [g["id"] for g in stm32 if g["id"] == "attitude-hold"] == [], (
        "stm32 上这一组只剩一件（ml_mpu6050）：单成员组不出，页面不该报互斥")


def test_generate_writes_the_mpu6050_section_into_main_c(
    real_library_client, tmp_path
):
    """真生成一遍：写出的 main.c 里有 MPU6050 小节，盘上内容与载荷逐字一致。"""
    client, _ = real_library_client
    parent = tmp_path / "out"
    parent.mkdir()
    response = client.post(
        "/api/hwcheck/generate",
        json={"platform": PLATFORM_STM32, "debug_uart": True, "oled": False,
              "devices": ["ml_mpu6050"], "parent_dir": str(parent)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    on_disk = (Path(body["output_dir"]) / "main.c").read_text(encoding="utf-8")
    assert on_disk == body["main_c"]
    assert "hwcheck_check_ml_mpu6050();" in on_disk
    assert "r = MPU6050_Read(WHO_AM_I);" in on_disk


def test_device_sections_bring_their_own_headers_into_main_c():
    """器件小节声明 include（配方 `include` 段）→ main.c 里真的 include 它们。

    真机判例（工单 05 的编译矩阵第一次跑）：产物里没有器件模块的头，ARMCC 报
    7 个 error（`#223-D function "MPU6050_Init" declared implicitly` +
    `#20 identifier "ax" / "WHO_AM_I" is undefined`）——检测程序直接调模块函数，
    而框架那套固定 include 只覆盖通道与心跳。
    """
    stm32 = render_main_c(
        HwCheckConfig(platform=PLATFORM_STM32, debug_uart=True, oled=False),
        (_mpu_section(PLATFORM_STM32),))
    assert '#include "ml_mpu6050.h"' in stm32
    assert '#include "ml_i2c.h"' in stm32      # 跨模块前置调用的头
    mspm0 = render_main_c(
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=False),
        (_mpu_section(PLATFORM_MSPM0),))
    assert '#include "mpu_port.h"' in mspm0
    # 另一平台的头不许串台（平台不对称，工单 05 的整条主线）
    assert "ml_mpu6050.h" not in mspm0
    # 同一件只印一次（两处 include 同一个头不重复印同一行）
    assert stm32.count('#include "ml_mpu6050.h"') == 1


@pytest.mark.parametrize(
    "platform,section_factory",
    [(PLATFORM_STM32, lambda: _mpu_section(PLATFORM_STM32)),
     (PLATFORM_MSPM0, lambda: _mpu_section(PLATFORM_MSPM0))],
)
def test_mpu_section_includes_resolve_in_that_platforms_real_project(
    platform, section_factory
):
    """MPU6050 小节的每个 `#include` 必须能在**该平台**的真实工程里解析。

    与框架形态那条同判据（母版头 ∪ 该平台模块条目的头 ∪ 工具链外部头），只是
    这回把器件小节一起渲染进去——配方声明的头名写错时当场红，不必等真编译。
    """
    known = _platform_master_headers(platform) | _platform_module_headers(platform)
    known.add("ti_msp_dl_config.h")  # 工具链外部头（构建期生成）
    code = render_main_c(
        HwCheckConfig(platform=platform, debug_uart=True, oled=False),
        (section_factory(),))
    unresolved = [
        header
        for header in re.findall(r'#include\s+"([^"]+)"', code)
        if header.lower() not in known
    ]
    assert unresolved == [], f"{platform} 引用了该平台工程里没有的头：{unresolved}"


def test_a_full_probe_run_does_not_declare_the_probe_none_helper():
    """整趟都是带判定的探头 → **不留没人调的** `hwcheck_verdict_probe_none`。

    真机判例（工单 05 的编译矩阵）：只选 ml_mpu6050 时那个函数声明了没人调，
    tiarmclang 报 `-Wunused-function`（ARMCC 报 `#177-D`）——检测程序的验收线是
    "0 error / 0 warning"，死代码不是风格问题（学生会以为漏调了什么）。
    反过来（只选 oled：没有读取型探头）它必须在，"未判定"那一档也要在。
    """
    mspm0 = render_main_c(
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=False),
        (_mpu_section(PLATFORM_MSPM0),))
    assert "hwcheck_verdict_probe_none" not in mspm0
    assert "hwcheck_summary_probe_none" not in mspm0
    assert "未判定" not in unescape_c_string(mspm0)
    assert "hwcheck_summary_fail" in mspm0        # 有判定 → 失败档要在

    oled = RecipeSection(
        slug="oled", platform=PLATFORM_MSPM0,
        init=("OLED_Init()",),
        probe=RecipeProbe(calls=('OLED_ShowString(0, 0, "OLED OK", 16)',)),
    )
    code = render_main_c(
        HwCheckConfig(platform=PLATFORM_MSPM0, debug_uart=True, oled=False),
        (oled,))
    assert "hwcheck_verdict_probe_none" in code
    assert "未判定" in unescape_c_string(code)
    assert "hwcheck_summary_fail" not in code     # 没有判定项 → 失败档不留


# ---------------------------------------------------------------------------
# 工单 08：现象回填 + AI 排障（本功能里唯一的 LLM 入口）
# ---------------------------------------------------------------------------


@pytest.fixture()
def triage_client(tmp_path):
    """真库 + 真母版 + **可检查的**假 LLM（holder 里那份）。

    为什么不用 `real_library_client`：那个 fixture 每次请求新建 FakeLLM，
    本单要断言"送进模型的是什么"（上下文 / 现象）与"模型失败时的降级行为"，
    必须抓住同一个实例。桌面重定向保证不碰用户桌面。
    """
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.webapp import AppContext, create_app
    from tests.fakes import FakeLLM

    repo = Path(__file__).resolve().parents[1]
    desktop = tmp_path / "desktop"
    desktop.mkdir()
    holder = {"llm": FakeLLM()}
    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=repo / "library" / "modules",
            masters_dir=repo / "library" / "masters",
        ),
        llm_factory=lambda config: holder["llm"],
        desktop_dir=lambda: desktop,
    )
    return TestClient(create_app(ctx)), ctx, holder


def _generate_hwcheck_project(client, parent: Path, **extra) -> dict:
    """生成一个检测工程（本单的每个端点用例都从"真工程"出发）。"""
    payload = {
        "platform": PLATFORM_STM32,
        "debug_uart": True,
        "oled": False,
        "devices": ["led"],
        "parent_dir": str(parent),
        **extra,
    }
    response = client.post("/api/hwcheck/generate", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_triage_endpoint_returns_advice_and_persists_the_record(triage_client, tmp_path):
    """一次排障：建议回给页面 + 现象 / 勾选 / 建议一起落盘（刷新可回显）。"""
    from contest_generator.hwcheck_triage import HWCHECK_RECORD_FILENAME

    client, _, holder = triage_client
    parent = tmp_path / "out"
    parent.mkdir()
    generated = _generate_hwcheck_project(client, parent)
    output_dir = generated["output_dir"]

    response = client.post(
        "/api/hwcheck/triage",
        json={
            "output_dir": output_dir,
            "symptom": "串口一行字都没有，灯也不闪",
            "checked_ids": ["flash"],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["degraded"] is False
    assert body["message"] == ""
    assert body["advice"]["verdict"] == "wiring"
    assert body["advice"]["causes"] == ["串口 TX/RX 没交叉接"]

    # 送进模型的上下文：现象原样、接线行的脚进了白名单（"不编造"的判据）
    context = holder["llm"].triage_calls[-1]
    assert context.symptom == "串口一行字都没有，灯也不闪"
    assert "PA15" in context.facts.pins  # 地猛星 stm32 的 led 默认脚
    assert "led" in context.facts.modules

    # 记录落盘（现象 + 勾选 + 建议三者都在同一份文件里）
    on_disk = json.loads(
        (Path(output_dir) / HWCHECK_RECORD_FILENAME).read_text(encoding="utf-8")
    )
    assert on_disk["symptom"] == "串口一行字都没有，灯也不闪"
    assert on_disk["checked_ids"] == ["flash"]
    assert on_disk["advice"]["verdict"] == "wiring"
    assert body["record"] == on_disk


def test_triage_endpoint_degrades_without_blocking_when_llm_fails(triage_client, tmp_path):
    """模型失败**不阻断**：200 + 兜底建议 + degraded，记录照常保留（可重试）。"""
    from contest_generator.hwcheck_triage import (
        FALLBACK_REASON_PREFIX,
        HWCHECK_RECORD_FILENAME,
    )
    from contest_generator.llm import LLMError

    client, _, holder = triage_client
    parent = tmp_path / "out"
    parent.mkdir()
    output_dir = _generate_hwcheck_project(client, parent)["output_dir"]
    holder["llm"] = type(holder["llm"])(
        triage_error=LLMError("连接被拒绝")
    )

    response = client.post(
        "/api/hwcheck/triage",
        json={"output_dir": output_dir, "symptom": "灯常亮不闪", "checked_ids": ["flash"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["degraded"] is True
    assert "连接被拒绝" in body["message"]
    assert FALLBACK_REASON_PREFIX in body["advice"]["summary"]
    assert "连接被拒绝" not in body["advice"]["summary"]  # 原因只在 message 里
    assert body["advice"]["degraded"] is True
    # 记录照常落盘：现象没丢，建议是兜底那份
    on_disk = json.loads(
        (Path(output_dir) / HWCHECK_RECORD_FILENAME).read_text(encoding="utf-8")
    )
    assert on_disk["symptom"] == "灯常亮不闪"
    assert on_disk["checked_ids"] == ["flash"]
    assert on_disk["advice"]["degraded"] is True


def test_triage_endpoint_rejects_facts_outside_the_context(triage_client, tmp_path):
    """事实约束真的在链路上生效：模型点出本次没有的脚 / 模块 → 降级，不照单全收。

    这里用**真 DeepSeekLLM + 假传输**（不是 FakeLLM）：事实判据住在
    `parse_triage_advice`，绕过它就把这条验收标准测空了。传输永远返回带
    `PA9`（本次接线表里没有）与 `jy61p`（本次没选的库内模块）的建议 →
    每轮都被拒 → 端点拿兜底建议，且**兜底文案里不含那些非法名字**。
    """
    from fastapi.testclient import TestClient

    from contest_generator.config import AppConfig
    from contest_generator.llm import DeepSeekLLM
    from contest_generator.webapp import AppContext, create_app
    from tests.fakes import FakeTransport

    repo = Path(__file__).resolve().parents[1]
    desktop = tmp_path / "desktop2"
    desktop.mkdir()
    illegal = {
        "verdict": "wiring",
        "summary": "把线插到 PA9 上试试",
        "causes": ["jy61p 那件没接好"],
        "steps": ["换成 PA9 再看一次"],
        "issue_hint": "",
    }
    transport = FakeTransport(body=json.dumps({"choices": [{"message": {"content": json.dumps(illegal)}}]}))
    llm = DeepSeekLLM(
        AppConfig(api_key="sk-test", module_library_dir=repo / "library" / "modules",
                  masters_dir=repo / "library" / "masters"),
        transport=transport,
    )
    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=repo / "library" / "modules",
            masters_dir=repo / "library" / "masters",
        ),
        llm_factory=lambda config: llm,
        desktop_dir=lambda: desktop,
    )
    client = TestClient(create_app(ctx))
    output_dir = _generate_hwcheck_project(client, desktop)["output_dir"]

    body = client.post(
        "/api/hwcheck/triage",
        json={"output_dir": output_dir, "symptom": "什么都没看到", "checked_ids": []},
    ).json()
    assert body["degraded"] is True
    assert "PA9" in body["message"] and "jy61p" in body["message"]  # 拒收理由点名
    assert "PA9" not in body["advice"]["summary"]
    assert all("PA9" not in step for step in body["advice"]["steps"])
    assert all("jy61p" not in cause for cause in body["advice"]["causes"])
    assert transport.calls  # 确实问过模型（不是没调就降级）


def test_triage_endpoint_400s_on_empty_symptom_and_unknown_dir(triage_client, tmp_path):
    """缺现象 / 目录不存在 / 不是检测工程 → 400 中文（域层与路由层各守一段）。"""
    client, _, _ = triage_client
    parent = tmp_path / "out"
    parent.mkdir()
    output_dir = _generate_hwcheck_project(client, parent)["output_dir"]

    empty = client.post(
        "/api/hwcheck/triage",
        json={"output_dir": output_dir, "symptom": "   "},
    )
    assert empty.status_code == 400, empty.text
    missing = client.post(
        "/api/hwcheck/triage",
        json={"output_dir": str(parent / "没有这个目录"), "symptom": "灯不亮"},
    )
    assert missing.status_code == 400, missing.text
    contest = tmp_path / "contest"
    contest.mkdir()
    (contest / ".contest_context.json").write_text(
        json.dumps({"kind": "contest", "platform": PLATFORM_STM32, "slugs": ["led"]}),
        encoding="utf-8",
    )
    wrong_kind = client.post(
        "/api/hwcheck/triage",
        json={"output_dir": str(contest), "symptom": "灯不亮"},
    )
    assert wrong_kind.status_code == 400, wrong_kind.text
    assert "检测工程" in wrong_kind.json()["detail"]
    # 勾选端点也守同一条判据：往赛题工程里写检测记录 = 把两类工程搅在一起
    wrong_kind_ticks = client.post(
        "/api/hwcheck/checklist",
        json={"output_dir": str(contest), "checked_ids": ["flash"]},
    )
    assert wrong_kind_ticks.status_code == 400, wrong_kind_ticks.text
    assert "检测工程" in wrong_kind_ticks.json()["detail"]
    assert not (contest / ".contest_hwcheck_record.json").exists()


def test_checklist_endpoint_persists_ticks_and_project_reads_them_back(
    triage_client, tmp_path
):
    """勾选落服务端真源：勾一条写一次；回读工程时现象 / 勾选 / 建议一起回来。"""
    client, _, _ = triage_client
    parent = tmp_path / "out"
    parent.mkdir()
    output_dir = _generate_hwcheck_project(client, parent)["output_dir"]
    client.post(
        "/api/hwcheck/triage",
        json={"output_dir": output_dir, "symptom": "屏全黑", "checked_ids": []},
    )

    saved = client.post(
        "/api/hwcheck/checklist",
        json={"output_dir": output_dir, "checked_ids": ["flash", "heartbeat"]},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["record"]["checked_ids"] == ["flash", "heartbeat"]
    # 勾选更新不吃掉现象与建议（同一个记录文件，三段互不覆盖）
    assert saved.json()["record"]["symptom"] == "屏全黑"
    assert saved.json()["record"]["advice"]["verdict"] == "wiring"

    reloaded = client.get("/api/hwcheck/project", params={"output_dir": output_dir})
    assert reloaded.status_code == 200, reloaded.text
    record = reloaded.json()["record"]
    assert record["checked_ids"] == ["flash", "heartbeat"]
    assert record["symptom"] == "屏全黑"
    assert record["advice"]["causes"] == ["串口 TX/RX 没交叉接"]


def test_fresh_project_has_an_empty_record(triage_client, tmp_path):
    """刚生成的工程没有记录 = 空记录（回显空态，不 400）。"""
    client, _, _ = triage_client
    parent = tmp_path / "out"
    parent.mkdir()
    output_dir = _generate_hwcheck_project(client, parent)["output_dir"]
    body = client.get("/api/hwcheck/project", params={"output_dir": output_dir}).json()
    assert body["record"]["symptom"] == ""
    assert body["record"]["checked_ids"] == []
    assert body["record"]["advice"] is None


def test_hwcheck_event_constant_is_registered_in_the_single_source():
    """事件词表单源：排障事件常量登记在 events.py（页面 / 观察面板按它消费）。"""
    from contest_generator import events

    assert events.EVENT_HWCHECK_TRIAGE == "hwcheck_triage"


