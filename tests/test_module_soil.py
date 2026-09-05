"""soil 土壤湿度传感器模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 flame/mq135 同款结构测试：manifest 形状（仅 mspm0、依赖 adc、单角色
SOIL_AO_CH7 = adc PA14——ADC12_0 sequence 八通道 MEM7 独立通道、**MEM 槽位
已满（8/8）**）、mspm0 单选生成（syscfg 裁剪保留 ADC12_0、soil + 依赖 adc
模块文件落盘、main.c 调 init/read_percent 过静态门禁）。百分比公式（页面
原式**正向映射** value/4095×100——区别于 flame 反向）与「无 ADC 中断」源码
守卫钉死（页面 ADC 中断改轮询——共享实例 IRQHandler 强符号唯一）。全程无
LLM、无服务。
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
    '#include "soil.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    soil_init();\n"
    "    float percent = soil_read_percent();\n"
    "    (void)percent;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_soil_manifest_shape_mspm0():
    """soil：仅 mspm0 平台条目；依赖 adc；单角色 = adc PA14（MEM7 独立通道
    ——MEM 槽位已满（8/8）；与 mq2 的 MEM0 薄封装不同：与其它模拟量件同选时
    物理通道独立）。"""
    manifest = ModuleManifest.load(MODULES / "soil")
    assert manifest.slug == "soil"
    assert manifest.dependencies == ("adc",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["soil.c", "soil.h"]
    for rel in mspm0.files:
        assert (MODULES / "soil" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("SOIL_AO_CH7", "adc", "PA14", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 正向映射 + 15k 负载限制 + MEM0 共读决策必须写入 notes
    assert "正向映射" in mspm0.notes
    assert "15k" in mspm0.notes
    assert "MEM0" in mspm0.notes


def test_soil_mspm0_master_syscfg_shared_facts():
    """母版 ADC12_0 八通道共享事实（endAdd 6→7（soil MEM7 开通道后、槽位
    8/8 用满）、adcMem7chansel=CHAN_12、adcPin12=PA14 归 soil——flame/
    ir_distance/joystick/mq135 相关断言同步）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert 'ADC12_0.endAdd                     = 7;' in syscfg
    assert 'ADC12_0.adcMem7chansel             = "DL_ADC12_INPUT_CHAN_12";' in syscfg
    assert 'ADC12_0.peripheral.adcPin12.$assign = "PA14";' in syscfg


def test_soil_mspm0_single_select_generation(tmp_path):
    """soil mspm0 单选生成：syscfg 保留 ADC12_0（八通道 + soil 通道行）、
    soil + 依赖 adc 模块文件落盘、静态门禁过；无独立 GPIO 实例。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["soil"])
    assert {m.slug for m in resolved.manifests} == {"soil", "adc"}
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
    assert 'ADC12_0.endAdd                     = 7;' in syscfg
    assert 'ADC12_0.adcMem7chansel             = "DL_ADC12_INPUT_CHAN_12";' in syscfg
    assert 'ADC12_0.peripheral.adcPin12.$assign = "PA14";' in syscfg
    assert "const SOIL = " not in syscfg  # 无独立 GPIO 实例（独立 ADC 通道）
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/soil/code/soil.c").is_file()
    assert (out / "modules/soil/code/soil.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()


def test_soil_percent_formula_guard():
    """百分比公式与轮询守卫（防回潮）：页面原式**正向映射** value/4095×100
    （水分越足 ADC 值越大、百分比越高——无 `1.0f - ` 反向、区别于 flame）、
    ADC_Channel_7（MEM7 独立通道）、无 ADC 中断（共享实例 IRQHandler 强符号
    唯一——页面 IRQHandler 不可回潮）、adc 模块 API 通道守卫已扩展至 MEM7
    （adc_get 支持 soil）。"""
    source = (MODULES / "soil" / "code" / "soil.c").read_text(encoding="utf-8")
    header = (MODULES / "soil" / "code" / "soil.h").read_text(encoding="utf-8")
    assert "SOIL_ADC_MAX" in header
    assert "4095u" in header
    assert "* 100.0f" in source
    assert "1.0f - " not in source  # 正向映射（土壤 = 页面原式，非 flame 反向）
    assert "/ (float)SOIL_ADC_MAX" in source
    assert "ADC_Channel_7" in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source
    adc_source = (MODULES / "adc" / "code" / "adc_mspm0.c").read_text(
        encoding="utf-8"
    )
    assert "> ADC_Channel_7" in adc_source  # adc_get 守卫扩展至 MEM7
