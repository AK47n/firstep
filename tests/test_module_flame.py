"""flame 红外火焰传感器模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 mq135 同款结构测试：manifest 形状（仅 mspm0、依赖 adc、单角色
FLAME_AO_CH6 = adc PA22——ADC12_0 sequence 七通道 MEM6 独立通道）、mspm0
单选生成（syscfg 裁剪保留 ADC12_0、flame + 依赖 adc 模块文件落盘、main.c 调
init/read_percent 过静态门禁）。百分比公式（页面原式**反向映射**
（1 − value/4095）×100）与「无 ADC 中断」源码守卫钉死（页面 ADC 中断改轮询
——共享实例 IRQHandler 强符号唯一）。全程无 LLM、无服务。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "flame.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    flame_init();\n"
    "    float percent = flame_read_percent();\n"
    "    (void)percent;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_flame_manifest_shape_mspm0():
    """flame：仅 mspm0 平台条目；依赖 adc；单角色 = adc PA22（MEM6 独立
    通道——与 mq2 的 MEM0 薄封装不同：与其它模拟量件同选时物理通道独立）。"""
    manifest = ModuleManifest.load(MODULES / "flame")
    assert manifest.slug == "flame"
    assert manifest.dependencies == ("adc",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["flame.c", "flame.h"]
    for rel in mspm0.files:
        assert (MODULES / "flame" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("FLAME_AO_CH6", "adc", "PA22", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 反向映射 + 波段说明 + 相对值说明必须写入 notes
    assert "反向映射" in mspm0.notes
    assert "700-1000nm" in mspm0.notes


def test_flame_mspm0_master_syscfg_shared_facts():
    """母版 ADC12_0 七通道共享事实（endAdd 5→6（flame MEM6 开通道后）、
    adcMem6chansel=CHAN_7、adcPin7=PA22 归 flame——ir_distance/joystick/mq135
    相关断言同步）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert 'ADC12_0.endAdd                     = 6;' in syscfg
    assert 'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_7";' in syscfg
    assert 'ADC12_0.peripheral.adcPin7.$assign = "PA22";' in syscfg


def test_flame_mspm0_single_select_generation(tmp_path):
    """flame mspm0 单选生成：syscfg 保留 ADC12_0（七通道 + flame 通道行）、
    flame + 依赖 adc 模块文件落盘、静态门禁过；无独立 GPIO 实例。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["flame"])
    assert {m.slug for m in resolved.manifests} == {"flame", "adc"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_MSPM0,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=MSPM0_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_MSPM0,
    )
    syscfg = (out / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const ADC12_0 = ADC12.addInstance();" in syscfg
    assert 'ADC12_0.endAdd                     = 6;' in syscfg
    assert 'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_7";' in syscfg
    assert 'ADC12_0.peripheral.adcPin7.$assign = "PA22";' in syscfg
    assert "const FLAME = " not in syscfg  # 无独立 GPIO 实例（独立 ADC 通道）
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/flame/code/flame.c").is_file()
    assert (out / "modules/flame/code/flame.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()


def test_flame_percent_formula_guard():
    """百分比公式与轮询守卫（防回潮）：页面原式**反向映射**
    （1 − value/4095）×100（红外光越强 ADC 值越小、百分比越高）、
    ADC_Channel_6（MEM6 独立通道）、无 ADC 中断（共享实例 IRQHandler 强符号
    唯一——页面 IRQHandler 不可回潮）、adc 模块 API 通道守卫已扩展至 MEM6
    （adc_get 支持 flame）。"""
    source = (MODULES / "flame" / "code" / "flame.c").read_text(encoding="utf-8")
    header = (MODULES / "flame" / "code" / "flame.h").read_text(encoding="utf-8")
    assert "FLAME_ADC_MAX" in header
    assert "4095u" in header
    assert "* 100.0f" in source
    assert "1.0f - " in source  # 反向映射（火焰 = 页面原式，非 mq2/soil 正向）
    assert "/ (float)FLAME_ADC_MAX" in source
    assert "ADC_Channel_6" in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source
    adc_source = (MODULES / "adc" / "code" / "adc_mspm0.c").read_text(
        encoding="utf-8"
    )
    assert "> ADC_Channel_6" in adc_source  # adc_get 守卫扩展至 MEM6
