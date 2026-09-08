# -*- coding: utf-8 -*-
"""syscfg 探针：验证 LQFP-64(PM) 设备数据下 ADC12 第二/第三通道 + JOYSTICK GPIO 是否可行。

产出 .scratch/wiki-modules-batch1/syscfg-probe/mspm0.syscfg（母版副本 + 摇杆配置），
再由 sysconfig_cli 编译验证；本脚本只做文本插入。
"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[2]
MASTER = REPO / "library" / "masters" / "mspm0" / "mspm0.syscfg"
OUT = REPO / ".scratch" / "wiki-modules-batch1" / "syscfg-probe"
OUT.mkdir(parents=True, exist_ok=True)
DEST = OUT / "mspm0.syscfg"

text = MASTER.read_text(encoding="utf-8", newline="")
eol = "\r\n" if "\r\n" in text else "\n"

# 1) GPIO 实例声明：SR04 之后插入 JOYSTICK
text = text.replace(
    "const SR04 = GPIO.addInstance();" + eol,
    "const SR04 = GPIO.addInstance();" + eol
    + "const JOYSTICK = GPIO.addInstance();" + eol,
    1,
)

# 2) JOYSTICK 配置块：AHT10 配置块之后插入
anchor = "AHT10.associatedPins[1].pin.$assign  = \"PB7\";" + eol
assert anchor in text
joy_block = (
    "// 双轴摇杆按键（joystick 模块：SW 输入，上拉低有效 = 按下；默认 PA9——与"
    + eol
    + "// DIGIT_UART RX 重叠，同选时经引脚绑定消解——手动摇杆与 K230 视觉同选概率"
    + eol
    + "// 最低）" + eol
    + "JOYSTICK.$name = \"JOYSTICK\";" + eol
    + "JOYSTICK.associatedPins.create(1);" + eol
    + "JOYSTICK.associatedPins[0].$name            = \"SW\";" + eol
    + "JOYSTICK.associatedPins[0].direction        = \"INPUT\";" + eol
    + "JOYSTICK.associatedPins[0].internalResistor = \"PULL_UP\";" + eol
    + "JOYSTICK.associatedPins[0].pin.$assign      = \"PA9\";" + eol
)
text = text.replace(anchor, anchor + joy_block, 1)

# 3) ADC12_0 增加 MEM1(A0_1=PA26)、MEM2(A0_2=PA25)
text = text.replace(
    'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' + eol,
    'ADC12_0.adcMem0chansel             = "DL_ADC12_INPUT_CHAN_3";' + eol
    + 'ADC12_0.adcMem1chansel             = "DL_ADC12_INPUT_CHAN_1";' + eol
    + 'ADC12_0.adcMem2chansel             = "DL_ADC12_INPUT_CHAN_2";' + eol
    + 'ADC12_0.peripheral.adcPin1.$assign  = "PA26";' + eol
    + 'ADC12_0.peripheral.adcPin2.$assign  = "PA25";' + eol,
    1,
)

DEST.write_text(text, encoding="utf-8", newline="")
print("probe syscfg written:", DEST)
