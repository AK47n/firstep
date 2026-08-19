"""adc 模块（b1-adc-servo/01）：双平台 API 对偶 + 母版接线 + 类型级引脚绑定。

红证：adc 绑定 = 类型级（换引脚 = 换通道，实例随绑定引脚推导喂渲染器）——
stm32 宏值（ADC_Channel_N 随引脚）、mspm0 syscfg 的 adcPinN.$assign +
adcMem<N>chansel 通道行连带改写。A1_* 通道组 v1 不支持（rewrite 大声失败）。
"""

import re
from pathlib import Path

import pytest

from contest_generator.boards import (
    BOARDS_DIR,
    board_for_platform,
    load_boards,
    pin_capability_instances,
)
from contest_generator.library import list_modules
from contest_generator.pin_bindings import PinBindingError, resolve_bindings
from contest_generator.pinwriter import (
    PIN_CONFIG_FILENAME,
    render_pin_config,
    rewrite_syscfg,
)
from contest_generator.syscfg_model import MSPM0_SYSCFG_FILENAME, parse_syscfg

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
LIBRARY_MODULES = LIBRARY_ROOT / "modules"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"

BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}
ALL_MANIFESTS = list_modules(LIBRARY_MODULES)
ADC_MANIFEST = next(m for m in ALL_MANIFESTS if m.slug == "adc")


def _read(rel: str) -> str:
    return (LIBRARY_ROOT / rel).read_text(encoding="utf-8", errors="replace")


def _resolve(platform: str, bindings: dict[str, str]):
    return resolve_bindings(ALL_MANIFESTS, platform, BOARDS[platform], bindings)


# ---------------------------------------------------------------------------
# manifest 形状
# ---------------------------------------------------------------------------


def test_adc_manifest_loaded_and_capability_direction():
    assert ADC_MANIFEST.slug == "adc"
    assert "模拟" in ADC_MANIFEST.description  # 能力方向声明
    assert "20" not in ADC_MANIFEST.description  # 无题绑定（题号/年份机械拦截词）
    assert ADC_MANIFEST.dependencies == ()


def test_adc_pins_declared_both_platforms():
    stm32 = ADC_MANIFEST.platforms["stm32"]
    mspm0 = ADC_MANIFEST.platforms["mspm0"]
    assert [p.id for p in stm32.pins] == ["ADC_CH0", "ADC_CH1"]
    # mspm0 v1 单通道（LQFP-64(PM) 无第二通道 adcPinN 槽位，b1-adc-servo/01）
    assert [p.id for p in mspm0.pins] == ["ADC_CH0"]
    assert stm32.pins[0].type == "adc" and mspm0.pins[0].type == "adc"
    # stm32 宏名尾形 _CH（渲染器实例原样分派），值随绑定引脚
    assert stm32.pins[0].macros == ("ADC_0_CH",)
    assert stm32.pins[1].macros == ("ADC_1_CH",)


# ---------------------------------------------------------------------------
# 双平台 API 对偶
# ---------------------------------------------------------------------------


def test_adc_api_parity_both_platforms():
    ml_adc_h = _read("masters/stm32/ml_libs/ml_adc.h")
    adc_mspm0_h = _read("modules/adc/code/adc_mspm0.h")
    for fn in ("adc_init", "adc_get"):
        assert fn in ml_adc_h, f"stm32 ml_adc.h 缺 {fn}"
        assert fn in adc_mspm0_h, f"mspm0 adc_mspm0.h 缺 {fn}"
    # mspm0 头枚举兼容形态（ADCx_enum / ADCINx_enum 与 ml_adc 同名）
    assert "ADCx_enum" in adc_mspm0_h and "ADCINx_enum" in adc_mspm0_h


# ---------------------------------------------------------------------------
# 母版接线：stm32 pin_config.h 宏 + mspm0 syscfg ADC12_0 实例
# ---------------------------------------------------------------------------


def test_stm32_master_has_adc_macros():
    text = (STM32_MASTER / PIN_CONFIG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    assert re.search(r"#define\s+ADC_0_CH\s+ADC_Channel_0\b", text)
    assert re.search(r"#define\s+ADC_1_CH\s+ADC_Channel_1\b", text)


def test_mspm0_master_syscfg_has_adc12_instances():
    text = (MSPM0_MASTER / MSPM0_SYSCFG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    model = parse_syscfg(text)
    assert "ADC12_0" in model.instances
    assert re.search(r"ADC12_0\.adcMem0chansel\s*=\s*\"DL_ADC12_INPUT_CHAN_3\"", text)
    assert re.search(r"ADC12_0\.peripheral\.adcPin3\.\$assign\s*=\s*\"PA24\"", text)


# ---------------------------------------------------------------------------
# stm32 类型级绑定 + 渲染
# ---------------------------------------------------------------------------


def test_stm32_adc_type_level_binding_and_render():
    master = (STM32_MASTER / PIN_CONFIG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    # PA0 → PA5（ADC_Channel_0 → ADC_Channel_5）应成功
    resolved = _resolve("stm32", {"adc.ADC_CH0": "PA5"})
    assert resolved[0].pin == "PA5"
    assert resolved[0].instances == ("ADC_Channel_5",)
    rendered = render_pin_config(master, resolved)
    assert re.search(r"#define\s+ADC_0_CH\s+ADC_Channel_5\b", rendered)
    # 注释里的旧引脚字样同步替换
    assert "PA5" in rendered


def test_stm32_adc_binding_rejects_pin_without_adc_capability():
    # PB12（灰度脚）无 adc token → 类型级下限拒绝
    with pytest.raises(PinBindingError):
        _resolve("stm32", {"adc.ADC_CH0": "PB12"})


# ---------------------------------------------------------------------------
# mspm0 类型级绑定 + syscfg 改写（adcPinN.$assign + adcMem<N>chansel 连带）
# ---------------------------------------------------------------------------


def test_mspm0_adc_binding_rewrites_pin_and_channel():
    master = (MSPM0_MASTER / MSPM0_SYSCFG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    # PA24(A0_3) → PA26(A0_1)：槽位名 adcPin3 → adcPin1（通道变）+ 引脚值换脚
    # + adcMem0chansel 换通道（真机红证：只改值不改槽位名，SysConfig 路由失败）
    resolved = _resolve("mspm0", {"adc.ADC_CH0": "PA26"})
    assert resolved[0].pin == "PA26"
    assert resolved[0].instances == ("A0_1",)
    rewritten = rewrite_syscfg(master, resolved)
    assert re.search(
        r"ADC12_0\.peripheral\.adcPin1\.\$assign\s*=\s*\"PA26\"", rewritten
    )
    assert "adcPin3" not in rewritten
    assert re.search(
        r"ADC12_0\.adcMem0chansel\s*=\s*\"DL_ADC12_INPUT_CHAN_1\"", rewritten
    )


def test_mspm0_adc_binding_same_pin_is_noop():
    master = (MSPM0_MASTER / MSPM0_SYSCFG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    resolved = _resolve("mspm0", {"adc.ADC_CH0": "PA24"})  # = 默认值
    assert rewrite_syscfg(master, resolved) == master  # 不变不写


def test_mspm0_adc_a1_channel_group_rejected_at_rewrite():
    # PA15 = A1_0（v1 只支持 A0 组）：resolve 通过（类型级），rewrite 大声失败
    master = (MSPM0_MASTER / MSPM0_SYSCFG_FILENAME).read_text(
        encoding="utf-8", newline=""
    )
    resolved = _resolve("mspm0", {"adc.ADC_CH0": "PA15"})
    assert resolved[0].instances == ("A1_0",)
    with pytest.raises(PinBindingError):
        rewrite_syscfg(master, resolved)


# ---------------------------------------------------------------------------
# 骨架接口块
# ---------------------------------------------------------------------------


def test_adc_interfaces_available_to_skeleton():
    from contest_generator.skeleton import build_skeleton_interfaces

    blocks = build_skeleton_interfaces(
        [ADC_MANIFEST], "mspm0", LIBRARY_MODULES, MSPM0_MASTER
    )
    joined = "\n".join(blocks)
    assert "adc_mspm0.h" in joined and "adc_init" in joined and "adc_get" in joined
    blocks_stm32 = build_skeleton_interfaces(
        [ADC_MANIFEST], "stm32", LIBRARY_MODULES, STM32_MASTER
    )
    joined_stm32 = "\n".join(blocks_stm32)
    assert "ml_adc.h" in joined_stm32 and "adc_init" in joined_stm32
