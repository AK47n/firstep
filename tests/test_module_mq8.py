"""mq8 MQ-8 氢气模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 mq2 同款结构测试：manifest 形状（仅 mspm0、依赖 adc、单角色
MQ8_AO_CH0 = adc PA24——与 adc/us016/mq2/批次 9 四件共享 ADC12_0 MEM0 槽位
薄封装，无新 ADC 通道）、mspm0 单选生成（syscfg 裁剪保留 ADC12_0、
mq8 + 依赖 adc 模块文件落盘、main.c 调 init/read_percent 过静态门禁）。
百分比公式（**正向映射**——value/4095×100 页面原式）与「无 ADC
中断」源码守卫钉死（页面 ADC 中断改轮询——共享实例 IRQHandler 强符号唯一）。
全程无 LLM、无服务。
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
    '#include "mq8.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    mq8_init();\n"
    "    float percent = mq8_read_percent();\n"
    "    (void)percent;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_mq8_manifest_shape_mspm0():
    """mq8：仅 mspm0 平台条目；依赖 adc；单角色 = adc PA24（MEM0 槽位）。"""
    manifest = ModuleManifest.load(MODULES / "mq8")
    assert manifest.slug == "mq8"
    assert manifest.dependencies == ("adc",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["mq8.c", "mq8.h"]
    for rel in mspm0.files:
        assert (MODULES / "mq8" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("MQ8_AO_CH0", "adc", "PA24", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # MQ 系相对值非 ppm 精标说明必须写入 notes
    assert "相对值" in mspm0.notes
    assert "ppm" in mspm0.notes
    assert "预热" in mspm0.notes



def test_mq8_mspm0_single_select_generation(tmp_path):
    """mq8 mspm0 单选生成：syscfg 保留 ADC12_0（adc 消费实例）、
    mq8 + 依赖 adc 模块文件落盘、静态门禁过；无独立 GPIO 实例（薄封装）。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["mq8"])
    assert {m.slug for m in resolved.manifests} == {"mq8", "adc"}
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
    assert 'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' in syscfg
    assert "const MQ8 = " not in syscfg  # 薄封装：无独立 GPIO 实例
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/mq8/code/mq8.c").is_file()
    assert (out / "modules/mq8/code/mq8.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()


def test_mq8_percent_formula_guard():
    """百分比公式与轮询守卫（防回潮）：value/4095×100（页面原式——
    正向映射）、ADC_Channel_0（MEM0 薄封装）、无 ADC 中断
    （共享实例 IRQHandler 强符号唯一——页面 IRQHandler 不可回潮）。"""
    source = (MODULES / "mq8" / "code" / "mq8.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "mq8" / "code" / "mq8.h").read_text(
        encoding="utf-8"
    )
    assert "MQ8_ADC_MAX" in header
    assert "4095u" in header
    assert "* 100.0f" in source
    assert "/ (float)MQ8_ADC_MAX" in source
    assert "ADC_Channel_0" in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source
