"""gp2y1014au 粉尘传感器模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 mq2 同款结构测试：manifest 形状（仅 mspm0、依赖 adc+delay、双角色——
GP2Y1014_AO_CH0 = adc PA24（与 adc/us016/mq2 共享 ADC12_0 MEM0 槽位薄封装，
无新 ADC 通道）+ GP2Y1014_LED = gpio_out PA1（**器件必需例外**——LED 驱动
脉冲））、mspm0 单选生成（syscfg 裁剪保留 ADC12_0 + 新 GPIO 实例 GP2Y1014、
gp2y1014au + 依赖 adc/delay 模块文件落盘、main.c 调 init/read_dust 过静态
门禁）。换算公式（0.17×value−0.1）、LED 脉冲时序常量（280/40/9680us）、
滑动平均窗口（10）与「无 ADC 中断」源码守卫钉死（页面 ADC 中断改轮询——共享
实例 IRQHandler 强符号唯一）。全程无 LLM、无服务。
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
    '#include "gp2y1014au.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    gp2y1014_init();\n"
    "    float dust = gp2y1014_read_dust();\n"
    "    (void)dust;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_gp2y1014au_manifest_shape_mspm0():
    """gp2y1014au：仅 mspm0 平台条目；依赖 adc+delay；双角色 = adc PA24
    （MEM0 槽位）+ gpio_out PA1（LED 驱动——器件必需例外）。"""
    manifest = ModuleManifest.load(MODULES / "gp2y1014au")
    assert manifest.slug == "gp2y1014au"
    assert manifest.dependencies == ("adc", "delay")
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["gp2y1014au.c", "gp2y1014au.h"]
    for rel in mspm0.files:
        assert (MODULES / "gp2y1014au" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("GP2Y1014_AO_CH0", "adc", "PA24", True, ()),
        ("GP2Y1014_LED", "gpio_out", "PA1", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 非精标、LED 时序、滑动平均内嵌必须写入 notes
    assert "非精标" in mspm0.notes
    assert "LED" in mspm0.notes
    assert "滑动平均" in mspm0.notes


def test_gp2y1014au_mspm0_single_select_generation(tmp_path):
    """gp2y1014au mspm0 单选生成：syscfg 保留 ADC12_0（adc 消费实例）+ 新 GPIO
    输出实例 GP2Y1014（LED）、gp2y1014au + 依赖 adc/delay 模块文件落盘、静态
    门禁过；无其它 GPIO 实例。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["gp2y1014au"])
    assert {m.slug for m in resolved.manifests} == {"gp2y1014au", "adc", "delay"}
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
    assert "const GP2Y1014 = GPIO.addInstance();" in syscfg
    assert 'GP2Y1014.associatedPins[0].pin.$assign      = "PA1";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "HUMAN_IR", "MICROWAVE",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/gp2y1014au/code/gp2y1014au.c").is_file()
    assert (out / "modules/gp2y1014au/code/gp2y1014au.h").is_file()
    assert (out / "modules/adc/code/adc_mspm0.c").is_file()
    assert (out / "modules/adc/code/adc_mspm0.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()


def test_gp2y1014au_formula_and_timing_guard():
    """换算公式、LED 脉冲时序与轮询守卫（防回潮）：0.17×value−0.1（页面原式）、
    280/40/9680us 时序常量、10 点滑动平均窗口、delay_us 调用（依赖 delay）、
    ADC_Channel_0（MEM0 薄封装）、无 ADC 中断（共享实例 IRQHandler 强符号
    唯一——页面 IRQHandler 不可回潮）。"""
    source = (MODULES / "gp2y1014au" / "code" / "gp2y1014au.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "gp2y1014au" / "code" / "gp2y1014au.h").read_text(
        encoding="utf-8"
    )
    assert "0.17f * (float)value - 0.1f" in source
    assert "GP2Y1014_FILTER_WINDOW" in header
    assert "10u" in header
    assert "GP2Y1014_LED_SETTLE_US 280u" in header
    assert "GP2Y1014_LED_SAMPLE_TAIL_US 40u" in header
    assert "GP2Y1014_LED_CYCLE_TAIL_US 9680u" in header
    assert "delay_us(GP2Y1014_LED_SETTLE_US)" in source
    assert "delay_us(GP2Y1014_LED_CYCLE_TAIL_US)" in source
    assert "ADC_Channel_0" in source
    assert "ADC12_0_INST_IRQHandler" not in source  # 中断改轮询
    assert "gCheckADC" not in source
