"""joystick 双轴摇杆模块：真实库 + 真实母版不变量与双平台单选生成。

与 ws2812 / hx711 / aht10 / sr04 同款结构测试：manifest 形状（双平台、
无依赖、mspm0 三角色默认 = 母版 syscfg 由 test_pins.py / test_pin_bindings.py
守）、mspm0 单选生成（syscfg 裁剪保留 JOYSTICK + ADC12_0、模块文件落盘、
main.c 调 init/读轴/读键过静态门禁）与 stm32 单选生成（wiki-stm32-batch7/03）。
摇杆 X/Y 与 adc 模块共享 ADC12_0 实例（sequence 八通道——MEM1=PA26/A0_1、
MEM2=PA25/A0_2；MEM3 归 ir_distance，wiki-modules-batch2/04；MEM4=PB20/A0_6
归 mq135、MEM5=PB24/A0_5 归 mq5，wiki-modules-batch7/01/02；MEM6=PA22/A0_7
归 flame、MEM7=PA14/A0_12 归 soil——槽位 8/8 用满，wiki-modules-batch8/01/02），
SW 独立 GPIO 输入（PA9）。stm32：API 全套 6 函数与 mspm0 joystick.h 的六个声明
同名同型（read_x/read_y = uint16_t 12bit raw、read_x_percent/y_percent =
uint16_t 整数 0-100%——非 float、read_sw = uint8_t）+ JOYSTICK_SW_PRESSED_LEVEL 0
宏沿名；守卫无 MQ2 字面量/SW 低有效注释/无 printf/GPIO_Init/RCC_。
全程无 LLM、无服务。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contest_generator.clex import strip_comments
from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import (  # noqa: E402
    PLATFORM_MSPM0,
    PLATFORM_STM32,
)
from contest_generator.selection import resolve_selection  # noqa: E402

from tests._c_macros import c_defines, c_functions, c_int

def _read(rel: str) -> str:
    """读库内相对路径的文本（照 test_module_servo.py 同款小助手）。"""
    return (LIBRARY_ROOT / rel).read_text(encoding="utf-8", errors="replace")


MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "joystick.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    joystick_init();\n"
    "    uint16_t x = joystick_read_x_percent();\n"
    "    uint16_t y = joystick_read_y_percent();\n"
    "    uint8_t sw = joystick_read_sw();\n"
    "    (void)x;\n"
    "    (void)y;\n"
    "    (void)sw;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_joystick_manifest_shape_mspm0():
    """joystick：仅 mspm0 平台条目；无依赖；X(adc PA26) + Y(adc PA25) + SW(gpio_in PA9)。"""
    manifest = ModuleManifest.load(MODULES / "joystick")
    assert manifest.slug == "joystick"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["joystick.c", "joystick.h"]
    for rel in mspm0.files:
        assert (MODULES / "joystick" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("JOYSTICK_X_CH1", "adc", "PA26", True, ()),
        ("JOYSTICK_Y_CH2", "adc", "PA25", True, ()),
        ("JOYSTICK_SW", "gpio_in", "PA9", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_joystick_mspm0_syscfg_instances():
    """mspm0 母版：JOYSTICK GPIO 实例（SW=PA9 上拉输入）+ ADC12_0 八通道
    sequence（adcPin1=PA26/A0_1、adcPin2=PA25/A0_2、adcPin3=PA24/A0_3、
    adcPin0=PA27/A0_0——MEM3 归 ir_distance，wiki-modules-batch2/04；
    MEM4=PB20/A0_6 归 mq135、MEM5=PB24/A0_5 归 mq5，wiki-modules-batch7；
    MEM6=PA22/A0_7 归 flame、MEM7=PA14/A0_12 归 soil——槽位 8/8 用满，
    wiki-modules-batch8/01/02）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const JOYSTICK = GPIO.addInstance();" in syscfg
    assert 'JOYSTICK.associatedPins[0].$name            = "SW";' in syscfg
    assert 'JOYSTICK.associatedPins[0].direction        = "INPUT";' in syscfg
    assert 'JOYSTICK.associatedPins[0].internalResistor = "PULL_UP";' in syscfg
    assert 'JOYSTICK.associatedPins[0].pin.$assign  = "PA9";' in syscfg
    assert 'ADC12_0.samplingOperationMode      = "sequence";' in syscfg
    assert 'ADC12_0.adcMem1chansel             = "DL_ADC12_INPUT_CHAN_1";' in syscfg
    assert 'ADC12_0.adcMem2chansel             = "DL_ADC12_INPUT_CHAN_2";' in syscfg
    assert 'ADC12_0.peripheral.adcPin1.$assign  = "PA26";' in syscfg
    assert 'ADC12_0.peripheral.adcPin2.$assign  = "PA25";' in syscfg


def test_joystick_mspm0_single_select_generation(tmp_path):
    """joystick mspm0 单选生成：syscfg 只留 JOYSTICK+ADC12_0、模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["joystick"])
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
    assert "const JOYSTICK = GPIO.addInstance();" in syscfg
    assert "const ADC12_0 = ADC12.addInstance();" in syscfg
    assert 'JOYSTICK.associatedPins[0].pin.$assign  = "PA9";' in syscfg
    assert 'ADC12_0.adcMem2chansel             = "DL_ADC12_INPUT_CHAN_2";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART",
        "ZIGBEE_UART", "OLED", "I2C_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/joystick/code/joystick.c").is_file()
    assert (out / "modules/joystick/code/joystick.h").is_file()


def test_joystick_mspm0_untouched():
    """mspm0 零改动守卫（wiki-stm32-batch7/03）：mspm0 源不含 stm32 侧宏名
    （JOYSTICK_X_CH 等）与 PA1/PA0 字面量（mspm0 走 MEM1/MEM2）。"""
    source = (MODULES / "joystick" / "code" / "joystick.c").read_text(encoding="utf-8")
    assert "ADC12_0_ADCMEM_1" in source
    assert "JOYSTICK_X_CH" not in source
    assert "JOYSTICK_Y_CH" not in source
    assert "JOYSTICK_SW_GPIO" not in source


# ---------------------------------------------------------------------------
# driver-defect-fixes/01：mspm0 侧 ADC 超时判据 = 时间，不是自旋圈数
# ---------------------------------------------------------------------------

JOYSTICK_C = "modules/joystick/code/joystick.c"
JOYSTICK_H = "modules/joystick/code/joystick.h"


def _syscfg_adc_facts() -> tuple[int, int]:
    """→ (ADC12_0 的槽数, 每槽采样时间 µs)——判据取自母版 syscfg 的事实。"""
    text = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    start = int(re.search(r"ADC12_0\.startAdd\s*=\s*(\d+)\s*;", text).group(1))
    end = int(re.search(r"ADC12_0\.endAdd\s*=\s*(\d+)\s*;", text).group(1))
    sample_us = int(
        re.search(r'ADC12_0\.sampleTime0\s*=\s*"(\d+)\s*us"', text).group(1)
    )
    assert end >= start
    return end - start + 1, sample_us


def test_joystick_mspm0_timeout_is_a_time_budget_not_a_spin_count():
    """driver-defect-fixes/01 判据①：超时上限是**时间**（≥ 一次完整 sequence
    转换时间 × 安全系数），且算式里的槽数 / 每槽时间就是 syscfg 的事实。

    旧实现是「50 次寄存器轮询」——几微秒~几十微秒，远小于一次序列的 ~1000µs
    ⇒ 按常量核算每轮都在第一轮就提前超时。这里独立复算一遍，量具本身不照抄
    实现表达式。
    """
    slots, sample_us = _syscfg_adc_facts()
    defines = c_defines(_read(JOYSTICK_C))

    conversion_us = slots * sample_us  # 判据面：一次 startConversion 跑满整个序列
    assert conversion_us >= 1000, "母版 ADC12_0 的序列时长不该短于 1ms"

    assert c_int(defines, "JOYSTICK_ADC_SEQ_SLOTS") == slots, "槽数常量与 syscfg 不符"
    assert c_int(defines, "JOYSTICK_ADC_SLOT_US") == sample_us, "每槽时长与 syscfg 不符"
    timeout_us = c_int(defines, "JOYSTICK_ADC_TIMEOUT_US")
    assert timeout_us >= conversion_us * 2, (
        f"超时上限 {timeout_us}µs 不够一次完整序列（{conversion_us}µs）的安全系数"
    )
    # 轮询步长必须是「时间」：由 SysConfig 生成的 CPU 频率折出 1µs 的周期数
    assert "DL_Common_delayCycles(JOYSTICK_ADC_CYCLES_PER_US)" in _read(JOYSTICK_C)
    assert re.search(
        r"#define\s+JOYSTICK_ADC_CYCLES_PER_US\s+\(\s*CPUCLK_FREQ\s*/", _read(JOYSTICK_C)
    ), "轮询步长没有挂在 SysConfig 的 CPUCLK_FREQ 上"
    # **循环的退出界必须是这个时间预算**：常量算对了但循环里写别的数（例如老病的
    # 字面量 50）等于没修——这一条把「算式」与「真的等」绑在一起。
    wait_loop = c_functions(strip_comments(_read(JOYSTICK_C), keep_preprocessor=True))[
        "_joystick_adc_read"
    ]
    assert re.search(
        r"waited_us\s*>=\s*JOYSTICK_ADC_TIMEOUT_US", wait_loop
    ), "等 ADC 的循环没有拿 JOYSTICK_ADC_TIMEOUT_US 当退出界"
    assert re.search(
        r"waited_us\s*\+\+", wait_loop
    ), "等 ADC 的循环没有按「µs 步进」计数（那样等待就不是时间）"


def test_joystick_mspm0_timeout_never_masquerades_as_a_reading():
    """driver-defect-fixes/01 判据②：超时分支不再把「没采到」当成「采到 0」。

    0 是合法读数（raw 0 = 杆推到端点 / percent 0 = 0%），所以失败必须另有出口：
    本实现**先重试**（一圈没采到换下一圈），**一圈都没采到时返回
    `JOYSTICK_ADC_INVALID`**——它在 raw(0-4095) 与 percent(0-100) 两个合法域之外。
    """
    source = _read(JOYSTICK_C)
    header = _read(JOYSTICK_H)
    code_only = strip_comments(source, keep_preprocessor=True)
    functions = c_functions(code_only)
    defines = c_defines(header)

    # 旧判据不许回来：没有「50 圈自旋」这回事了
    assert not re.search(r"JOYSTICK_ADC_TIMEOUT\b(?!_US)", code_only)
    # 采样函数的返回出口**只许有两个**：本次无效哨兵 + 真采到样本时的均值。
    # 只查 `return 0` 是不够的——老实现写的是 `return sum / (i ? i : 1)`，
    # 首圈（i=0）算出来同样是 0，照样是「拿 0 冒充读数」。
    sampler = functions["_joystick_adc_read"]
    assert "return 0" not in sampler, "超时分支仍在用 0 冒充读数"
    returns = {expr.strip() for expr in re.findall(r"\breturn\s+([^;]+);", sampler)}
    assert returns == {"(uint16_t)(sum / got_samples)", "JOYSTICK_ADC_INVALID"}, (
        f"采样函数的返回出口应当只有「均值」与「本次无效哨兵」，实得 {sorted(returns)}"
    )

    sentinel = c_int(defines, "JOYSTICK_ADC_INVALID")
    assert sentinel > c_int(c_defines(source), "JOYSTICK_ADC_MAX"), "哨兵值落在 raw 合法域内"
    assert sentinel > 100, "哨兵值落在 percent 合法域内"
    assert "JOYSTICK_ADC_INVALID" in functions["_joystick_adc_read"], (
        "没采到样时没有如实上报「本次无效」"
    )

    # 百分比换算**只有一处出口**，它必须带哨兵守卫；两个 _percent 入口都必须走到它
    conv = {name: body for name, body in functions.items() if "* 100u" in body}
    assert len(conv) == 1, f"百分比换算应当只有一处，实得 {sorted(conv)}"
    conv_name, conv_body = next(iter(conv.items()))
    assert "JOYSTICK_ADC_INVALID" in conv_body, f"{conv_name} 把「本次无效」算成了数字"
    for fn in ("joystick_read_x_percent", "joystick_read_y_percent"):
        assert fn in functions, f"缺函数 {fn}"
        assert "JOYSTICK_ADC_INVALID" in functions[fn] or conv_name in functions[fn], (
            f"{fn} 没走到带守卫的换算出口"
        )


# ---------------------------------------------------------------------------
# wiki-stm32-batch7/03：stm32 平台条目（页面 ADC 序列收敛 ml_adc + SW gpio_in）
# ---------------------------------------------------------------------------

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "joystick_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    joystick_init();\n"
    "    (void)joystick_read_x();\n"
    "    (void)joystick_read_y();\n"
    "    (void)joystick_read_x_percent();\n"
    "    (void)joystick_read_y_percent();\n"
    "    (void)joystick_read_sw();\n"
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
    (r"stm32f4xx\.h", "stm32f4xx.h"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bdelay_1ms\b", "delay_1ms（ml_delay 无此 API）"),
    (r"\bIRQHandler\b", "IRQHandler（页面 ADC 中断改轮询）"),
    (r"\bMQ2\b", "MQ2（页面注释串台——不落码）"),
]


def test_joystick_manifest_shape_stm32():
    """stm32 条目：三角色 X=adc PA1 / Y=adc PA0（macros = 通道宏，与 adc 模块
    ADC_CH1/CH0 共享组）/ SW=gpio_in PA10（macros = GPIO/PIN 对，叠 UART RX）。"""
    manifest = ModuleManifest.load(MODULES / "joystick")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "joystick_stm32.c",
        "joystick_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "joystick" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("JOYSTICK_X", "adc", "PA1", True, ("JOYSTICK_X_CH",)),
        ("JOYSTICK_Y", "adc", "PA0", True, ("JOYSTICK_Y_CH",)),
        ("JOYSTICK_SW", "gpio_in", "PA10", True, ("JOYSTICK_SW_GPIO", "JOYSTICK_SW_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/control/two-axis-keystroke-rocker-module.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/control--two-axis-keystroke-rocker-module.md",
        "MQ2",
        "60ms",
        "未上板",
        "外部分路器",
    ):
        assert needle in stm32.notes


def test_joystick_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：4 宏必须在母版 pin_config.h（X=ADC_Channel_1、Y=通道 0、
    SW=GPIO_A/Pin_10）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+JOYSTICK_X_CH\s+ADC_Channel_1", text)
    assert re.search(r"#define\s+JOYSTICK_Y_CH\s+ADC_Channel_0", text)
    assert re.search(r"#define\s+JOYSTICK_SW_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+JOYSTICK_SW_PIN\s+Pin_10", text)


def test_joystick_stm32_single_select_generation(tmp_path):
    """joystick stm32 单选生成：依赖空（顶层 dependencies=() 保持 mspm0 现状；
    ml_adc/ml_gpio 内嵌母版）、静态门禁通过、模块文件落盘、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["joystick"])
    assert {m.slug for m in resolved.manifests} == {"joystick"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/joystick/code/joystick_stm32.c").is_file()
    assert (out / "modules/joystick/code/joystick_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("joystick_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_joystick_stm32_code_guards():
    """stm32 代码层守卫：API 全套 6 函数与 mspm0 joystick.h 的六个声明同名同型
    （read_x/read_y = uint16_t raw、percent = uint16_t 整数——非 float、read_sw
    = uint8_t）+ JOYSTICK_SW_PRESSED_LEVEL 0 宏沿名；换算口径照 mspm0
    joystick.c 逐行（整数 percent = raw×100/4095、SW 低有效）。"""
    c = (MODULES / "joystick" / "code" / "joystick_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "joystick" / "code" / "joystick_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "MQ2" in c  # 页面缺陷记录（注释：原页注释串台）
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert re.search(r"#define\s+JOYSTICK_ADC_MAX\s+4095u", h)
    assert re.search(r"#define\s+JOYSTICK_ADC_SAMPLES\s+4u", h)
    assert re.search(r"#define\s+JOYSTICK_SW_PRESSED_LEVEL\s+0\b", h)
    # API 全套 6 函数（同名同型 mspm0 joystick.h 的六个声明）
    assert re.search(r"void joystick_init\(void\);", h)
    assert re.search(r"uint16_t joystick_read_x\(void\);", h)
    assert re.search(r"uint16_t joystick_read_y\(void\);", h)
    assert re.search(r"uint16_t joystick_read_x_percent\(void\);", h)
    assert re.search(r"uint16_t joystick_read_y_percent\(void\);", h)
    assert re.search(r"uint8_t joystick_read_sw\(void\);", h)
    # 实现：整数 percent 换算（照 mspm0 joystick.c 的换算出口逐行——非 float 100.0f）
    assert "* 100u" in code_only and "/ JOYSTICK_ADC_MAX" in code_only
    assert "100.0f" not in code_only
    # 4 次快平均 + SW 低有效（1=按下）
    assert "JOYSTICK_ADC_SAMPLES" in code_only
    assert "JOYSTICK_SW_PRESSED_LEVEL" in code_only
    # 只吃母版 ml_adc/ml_gpio API + 引脚宏（无 ADC_Channel_1/0 字面量）
    assert "adc_get(ADC_1, channel)" in code_only
    assert "adc_init(ADC_1, JOYSTICK_X_CH)" in code_only
    assert "adc_init(ADC_1, JOYSTICK_Y_CH)" in code_only
    assert "gpio_get(JOYSTICK_SW_GPIO, JOYSTICK_SW_PIN)" in code_only
