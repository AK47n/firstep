# -*- coding: utf-8 -*-
"""母版 mspm0.syscfg 增补摇杆（joystick）：JOYSTICK GPIO 实例 + ADC12_0 三通道。

CRLF 保留。四处改动：
1. 文件头注释加 JOYSTICK/ADC 方案说明；
2. GPIO 实例声明 const JOYSTICK；
3. JOYSTICK 配置块（SW 输入上拉 = PA9）；
4. ADC12_0 增 sequence 三通道（MEM1=PA26/A0_1、MEM2=PA25/A0_2）并改写注释。
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MASTER = Path(__file__).resolve().parents[2] / "library" / "masters" / "mspm0" / "mspm0.syscfg"
text = MASTER.read_text(encoding="utf-8", newline="")
eol = "\r\n" if "\r\n" in text else "\n"
orig = text

# 1) 文件头注释
anchor1 = " *   LED2+15k 到地，PWM 输出时 LED 微亮，可忽略）" + eol
assert anchor1 in text
ins1 = (
    " *   JOYSTICK：SW = PA9（摇杆按键，上拉输入低有效；与 DIGIT_UART RX 默认" + eol
    + " *   重叠——手动摇杆与 K230 视觉同选概率最低，同选时经引脚绑定消解）；" + eol
    + " *   ADC12_0 三通道：MEM0 = PA24(A0_3) 归 adc 模块，MEM1 = PA26(A0_1) /" + eol
    + " *   MEM2 = PA25(A0_2) 归 joystick 摇杆 X/Y（与 ZIGBEE_UART 默认重叠——" + eol
    + " *   手动摇杆与无线身份/信标同选概率最低，同选时经引脚绑定消解；多 MEM" + eol
    + " *   必须 sequence 模式，2026-09-05 SysConfig CLI 实证）" + eol
)
text = text.replace(anchor1, anchor1 + ins1, 1)

# 2) 实例声明
anchor2 = "const SR04 = GPIO.addInstance();" + eol
assert anchor2 in text
text = text.replace(anchor2, anchor2 + "const JOYSTICK = GPIO.addInstance();" + eol, 1)

# 3) JOYSTICK 配置块（AHT10 块之后）
anchor3 = "AHT10.associatedPins[1].pin.$assign  = \"PB7\";" + eol
assert anchor3 in text
ins3 = (
    "// 双轴摇杆按键（joystick 模块：SW 输入上拉低有效；实例名 JOYSTICK →" + eol
    + "// JOYSTICK_PORT 宏；引脚名 SW → JOYSTICK_SW_PIN；默认 PA9——仅与" + eol
    + "// DIGIT_UART RX 默认重叠（K230 视觉串口），同选时经引脚绑定消解。" + eol
    + "// X/Y 两轴走 ADC12_0 MEM1/MEM2（见 ADC 段），SW 独立 GPIO）" + eol
    + "JOYSTICK.$name = \"JOYSTICK\";" + eol
    + "JOYSTICK.associatedPins.create(1);" + eol
    + "JOYSTICK.associatedPins[0].$name            = \"SW\";" + eol
    + "JOYSTICK.associatedPins[0].direction        = \"INPUT\";" + eol
    + "JOYSTICK.associatedPins[0].internalResistor = \"PULL_UP\";" + eol
    + "JOYSTICK.associatedPins[0].pin.$assign      = \"PA9\";" + eol
)
text = text.replace(anchor3, anchor3 + ins3, 1)

# 4) ADC12_0 注释 + 配置
old_cmt = (
    "// adc 模块：ADC12 单通道（b1-adc-servo/01；MEM0=PA24/A0_3，轮询读取，不配中断；"
    + eol
    + "// 第二通道的 adcPinN 槽位在 LQFP-64(PM) 设备数据不存在，双通道留后续）" + eol
)
assert old_cmt in text
new_cmt = (
    "// adc 模块 + 摇杆共享 ADC12_0（b1-adc-servo/01 + wiki-modules-batch1/01："
    + eol
    + "// MEM0=PA24/A0_3 归 adc，MEM1=PA26/A0_1、MEM2=PA25/A0_2 归 joystick X/Y；"
    + eol
    + "// 轮询读取不配中断。多 MEM 必须 sequence 模式（startAdd..endAdd = 启用"
    + eol
    + "// MEM 集合）——单发模式只启用 startAdd 槽位，adcPin1/2 由此不可用（原注释"
    + eol
    + "// 「槽位不存在」系误判，2026-09-05 SysConfig CLI 实证）" + eol
)
text = text.replace(old_cmt, new_cmt, 1)

old_cfg = (
    'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' + eol
    + 'ADC12_0.peripheral.$assign         = "ADC0";' + eol
    + 'ADC12_0.peripheral.adcPin3.$assign = "PA24";' + eol
)
assert old_cfg in text
new_cfg = (
    'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' + eol
    + 'ADC12_0.adcMem1chansel             = "DL_ADC12_INPUT_CHAN_1";' + eol
    + 'ADC12_0.adcMem2chansel             = "DL_ADC12_INPUT_CHAN_2";' + eol
    + 'ADC12_0.samplingOperationMode      = "sequence";' + eol
    + 'ADC12_0.startAdd                   = 0;' + eol
    + 'ADC12_0.endAdd                     = 2;' + eol
    + 'ADC12_0.peripheral.$assign         = "ADC0";' + eol
    + 'ADC12_0.peripheral.adcPin3.$assign = "PA24";' + eol
    + 'ADC12_0.peripheral.adcPin1.$assign  = "PA26";' + eol
    + 'ADC12_0.peripheral.adcPin2.$assign  = "PA25";' + eol
)
text = text.replace(old_cfg, new_cfg, 1)

assert text != orig
MASTER.write_text(text, encoding="utf-8", newline="")
print("母版 syscfg 已更新（CRLF 保持:", (eol == "\r\n"), "）")
