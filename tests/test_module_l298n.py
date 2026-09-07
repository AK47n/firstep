"""l298n 大电流电机驱动模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 motor / joystick 同款结构测试：manifest 形状（仅 mspm0、无依赖、
PWM C0/C1 + EN 三角色 = PA14/PB24/PA27——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
L298N_PWM + L298N、模块文件落盘、main.c 调 init/set_duty/set_direction 过
静态门禁）。页面 AO_Control 方向/调速形态与库风格 API 拆分源码守卫钉死
（dir=1 → C0=0/C1=duty；与 motor 分工写入 notes）。
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
    '#include "l298n.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    l298n_init();\n"
    "    l298n_set_duty(1000);\n"
    "    l298n_set_direction(1);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_l298n_manifest_shape_mspm0():
    """l298n mspm0 条目（stm32 条目见下方 stm32 段）：无依赖；PWM C0/C1 + EN。"""
    manifest = ModuleManifest.load(MODULES / "l298n")
    assert manifest.slug == "l298n"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["l298n.c", "l298n.h"]
    for rel in mspm0.files:
        assert (MODULES / "l298n" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("L298N_PWM_C0", "pwm", "PA14", True, ()),
        ("L298N_PWM_C1", "pwm", "PB24", True, ()),
        ("L298N_EN", "gpio_out", "PA27", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 与库内 motor(TB6612) 的分工说明必须写入 notes
    assert "motor" in mspm0.notes
    assert "TB6612" in mspm0.notes


def test_l298n_mspm0_syscfg_instances():
    """mspm0 母版：L298N_PWM（TIMG12 C0/C1）+ L298N GPIO（EN）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const L298N_PWM = PWM.addInstance();" in syscfg
    assert 'L298N_PWM.peripheral.$assign = "TIMG12";' in syscfg
    assert 'L298N_PWM.peripheral.ccp0Pin.$assign = "PA14";' in syscfg
    assert 'L298N_PWM.peripheral.ccp1Pin.$assign = "PB24";' in syscfg
    assert "const L298N = GPIO.addInstance();" in syscfg
    assert 'L298N.associatedPins[0].$name            = "EN";' in syscfg
    assert 'L298N.associatedPins[0].direction        = "OUTPUT";' in syscfg
    assert 'L298N.associatedPins[0].pin.$assign      = "PA27";' in syscfg


def test_l298n_mspm0_single_select_generation(tmp_path):
    """l298n mspm0 单选生成：syscfg 只留 L298N_PWM + L298N、文件落盘、门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["l298n"])
    assert {m.slug for m in resolved.manifests} == {"l298n"}
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
    assert "const L298N_PWM = PWM.addInstance();" in syscfg
    assert "const L298N = GPIO.addInstance();" in syscfg
    assert 'L298N_PWM.peripheral.ccp0Pin.$assign = "PA14";' in syscfg
    assert 'L298N_PWM.peripheral.ccp1Pin.$assign = "PB24";' in syscfg
    assert 'L298N.associatedPins[0].pin.$assign      = "PA27";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "BH1750", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "SHT30", "SHT20", "JY61P", "PWMAB",
        "SERVO_PWM", "OPENMV4_UART",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/l298n/code/l298n.c").is_file()
    assert (out / "modules/l298n/code/l298n.h").is_file()


def test_l298n_ao_control_shapes_and_calls_guards():
    """页面 AO_Control 方向/调速形态守卫（防回潮）：dir=1 → C0=0/C1=duty、
    dir=0 → C0=duty/C1=0；DL_Timer_setCaptureCompareValue + C0/C1 IDX 宏；
    限幅 L298N_PWM_PERIOD-1；EN 置高；无编码器/无 GPIO 中断。"""
    source = (MODULES / "l298n" / "code" / "l298n.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "l298n" / "code" / "l298n.h").read_text(
        encoding="utf-8"
    )
    # 页面形态：dir=1 分支 C0=0/C1=duty；dir=0 分支 C0=duty/C1=0
    assert "l298n_dir == 1" in source
    assert source.count("L298N_PWM_C0_IDX") >= 2
    assert source.count("L298N_PWM_C1_IDX") >= 2
    assert "DL_Timer_setCaptureCompareValue" in source
    # 库 API 三函数 + 页面 A 端口范围说明
    for fn in ("l298n_init", "l298n_set_duty", "l298n_set_direction"):
        assert fn in header
    # 限幅
    assert "L298N_PWM_PERIOD - 1u" in source
    assert "L298N_PWM_PERIOD" in header
    # EN 使能置高（页面 5V 使能高有效）
    assert "L298N_EN_PIN" in source
    # 无编码器脚 / 无 GPIO 中断（GROUP1 保留给 motor 编码器先例）
    assert "encoder" not in source
    assert "IRQHandler" not in source
    assert "printf" not in source


# ---------------------------------------------------------------------------
# wiki-stm32-batch9/04：stm32 平台条目（PWM×2 方向互切——TIM3_CH1/CH2=PA6/PA7
# 页面原脚；TIM 门禁默认×默认不拦 notes；I2C 总线同脚冲突 ⚠）
# ---------------------------------------------------------------------------

import re  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

from contest_generator.clex import strip_comments  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402

STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"  # noqa: E402

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "l298n_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    l298n_init();\n"
    "    l298n_set_duty(1000);\n"
    "    l298n_set_direction(1);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bTIM_TimeBaseInit\b", "TIM_TimeBaseInit（走 ml_pwm）"),
    (r"\bTIM_OC1Init\b", "TIM_OC1Init（走 ml_pwm）"),
    (r"\bEN\b", "EN（页面无 EN 代码——范围外）"),
]


def test_l298n_manifest_shape_stm32():
    """stm32 条目：IN1(pwm PA6)/IN2(pwm PA7)，各带 TIM/CH 宏。"""
    manifest = ModuleManifest.load(MODULES / "l298n")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "l298n_stm32.c",
        "l298n_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "l298n" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("L298N_IN1", "pwm", "PA6", True, ("L298N_IN1_TIM", "L298N_IN1_CH")),
        ("L298N_IN2", "pwm", "PA7", True, ("L298N_IN2_TIM", "L298N_IN2_CH")),
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/control/l298n-motor-drive-module.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/control--l298n-motor-drive-module.md",
        "TIM3_CH1",
        "互替",
        "物理冲突",
        "默认×默认不拦",
        "未上板",
    ):
        assert needle in stm32.notes


def test_l298n_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：l298n 四宏在母版 pin_config.h（TIM_3/TIM3_CH1/CH2）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    assert re.search(r"#define\s+L298N_IN1_TIM\s+TIM_3", text)
    assert re.search(r"#define\s+L298N_IN1_CH\s+TIM3_CH1", text)
    assert re.search(r"#define\s+L298N_IN2_TIM\s+TIM_3", text)
    assert re.search(r"#define\s+L298N_IN2_CH\s+TIM3_CH2", text)


def test_l298n_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：模块文件落盘、uvprojx 注册 l298n_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["l298n"])
    assert {m.slug for m in resolved.manifests} == {"l298n"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/l298n/code/l298n_stm32.c").is_file()
    assert (out / "modules/l298n/code/l298n_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("l298n_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_l298n_stm32_code_guards():
    """stm32 代码层守卫：L298N_PWM_PERIOD 2000u、set_duty/set_direction、
    pwm_init/pwm_update 换算（TIM/CH 宏，零引脚字面量）、无 EN/printf。"""
    c = (MODULES / "l298n" / "code" / "l298n_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "l298n" / "code" / "l298n_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert "#define L298N_PWM_PERIOD 2000u" in h
    assert "#define L298N_PWM_FREQ   500" in h
    # 方向互切形态（页面 AO_Control 原样）：dir=1 → CH1=0/CH2=duty
    assert "l298n_dir == 1" in code_only
    assert "pwm_update(L298N_IN1_TIM, L298N_IN1_CH, 0);" in code_only
    assert "pwm_update(L298N_IN2_TIM, L298N_IN2_CH, (uint16_t)l298n_duty);" in code_only
    assert "L298N_PWM_PERIOD - 1u" in code_only  # 限幅（页面 speed 无上限修正）
    assert "pwm_init(L298N_IN1_TIM, L298N_IN1_CH, L298N_PWM_FREQ);" in code_only
    assert "pwm_init(L298N_IN2_TIM, L298N_IN2_CH, L298N_PWM_FREQ);" in code_only
    # 库 API 三函数
    for fn in ("l298n_init", "l298n_set_duty", "l298n_set_direction"):
        assert f"void {fn}(" in code_only, fn
    assert "PA6" not in code_only and "PA7" not in code_only
    # TIM 门禁注意项记录在头注释（默认×默认不拦——现状口径）
    assert "默认×默认不拦" in h
