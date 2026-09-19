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
    HWCHECK_CHANNELS,
    HwCheckConfig,
    HwCheckError,
    hwcheck_modules,
    render_checklist,
    render_main_c,
    render_output_hint,
)
from contest_generator.manifest import ModuleManifest
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


