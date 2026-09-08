# -*- coding: utf-8 -*-
"""重建批次 7 提交历史：从最终状态推导各工单中间态（只改工作区文件，用完即被提交）。

state1 = commit 01（mq135）：母版 syscfg = 五通道（endAdd=4、MEM4、adcPin6=PB20、
注释 五通道/batch7/01），INSTANCE_CONSUMERS ADC12_0 元组只含 mq135，wordlist
只含 MQ-135 方案 + models。
后续状态直接 git checkout 旧提交版本的仓库文件（790da233/2cf892c6/3e8f62b0）。
"""
import re
import shutil
from pathlib import Path

MASTER = Path("library/masters/mspm0/mspm0.syscfg")
INST = Path("src/contest_generator/syscfg_instances.py")
WL = Path("src/contest_generator/wordlist.json")

# ---- 母版 syscfg：六通道 → 五通道（去 mq5 行，endAdd 回 4，注释回 batch7/01 版本）
m = MASTER.read_text(encoding="utf-8")
m = m.replace('ADC12_0.adcMem5chansel             = "DL_ADC12_INPUT_CHAN_5";\n', "")
m = m.replace("ADC12_0.endAdd                     = 5;", "ADC12_0.endAdd                     = 4;")
m = m.replace('ADC12_0.peripheral.adcPin5.$assign = "PB24";\n', "")
m = m.replace(
    " *   ADC12_0 六通道：MEM0 = PA24(A0_3)",
    " *   ADC12_0 五通道：MEM0 = PA24(A0_3)",
)
m = m.replace(
    " *   测距与灰度巡线同选概率最低），MEM4 = PB20(A0_6) 归 mq135、MEM5 =\n"
    " *   PB24(A0_5) 归 mq5（两件均独立通道，\n"
    " *   与 DC_MOTOR BB/SYN6288 TX、STEP_MOTOR RST2/SR04 TRIG/HC05 KEY/AT24C02 SCL\n"
    " *   重叠——MQ 系与运动控制/语音/记录常见同框概率最低；多路气体同选时物理\n"
    " *   通道独立、无共读冲突——mq2 为 MEM0 薄封装\n"
    " *   共读同槽，2026-09-08 实证 MEM4-7 通道/脚全合法）",
    " *   测距与灰度巡线同选概率最低），MEM4 = PB20(A0_6) 归 mq135（独立通道，\n"
    " *   与 DC_MOTOR BB 编码器/SYN6288 TX 重叠——MQ 系与运动控制/语音常见同框\n"
    " *   概率最低；多路气体同选时物理通道独立、无共读冲突——mq2 为 MEM0 薄封装\n"
    " *   共读同槽，2026-09-08 实证 MEM4-7 通道/脚全合法）",
)
m = m.replace(
    "// wiki-modules-batch7/01/02：",
    "// wiki-modules-batch7/01：",
)
m = m.replace(
    "// （手册原脚），MEM4=PB20/A0_6 归 mq135、MEM5=PB24/A0_5 归 mq5（独立通道\n"
    "// ——与 mq2 的 MEM0 薄封装不同：多路气体同选时各器件物理通道独立、无共读\n"
    "// 冲突；2026-09-08 SysConfig CLI 实证 MEM4-7 通道/脚全合法）；轮询读取不配\n"
    "// 中断。",
    "// （手册原脚），MEM4=PB20/A0_6 归 mq135（独立通道——与 mq2 的 MEM0 薄封装\n"
    "// 不同：多路气体同选时各器件物理通道独立、无共读冲突；2026-09-08 SysConfig\n"
    "// CLI 实证 MEM4-7 通道/脚全合法）；轮询读取不配中断。",
)
assert "adcMem5chansel" not in m
assert "endAdd                     = 4;" in m
assert "adcPin5.$assign" not in m
assert "六通道" not in m
# SGP30/AGS10 实例块属状态 3/4——state1 移除（注释 + 实例生成行）
for marker_comment, marker_last_pin, marker_inst in (
    ("// SGP30 空气 TVOC/CO2e 气体传感（sgp30 模块：",
     'SGP30.associatedPins[1].pin.$assign  = "PB9";',
     "const SGP30 = GPIO.addInstance();"),
    ("// AGS10 有害气体（TVOC）传感（ags10 模块：",
     'AGS10.associatedPins[1].pin.$assign  = "PA14";',
     "const AGS10 = GPIO.addInstance();"),
):
    start = m.find(marker_comment)
    end = m.find("\n", m.find(marker_last_pin)) + 1
    assert start >= 0 and end > start, marker_inst
    m = m[:start] + m[end:]
assert "const SGP30" not in m and "const AGS10" not in m
MASTER.write_text(m, encoding="utf-8")
print("master state1 OK")

# ---- INSTANCE_CONSUMERS：ADC 元组只含 mq135
i = INST.read_text(encoding="utf-8")
assert '    "ADC12_0": ("adc", "joystick", "us016", "ir_distance", "mq2", "mq135", "mq5"),' in i
i = i.replace(
    '    "ADC12_0": ("adc", "joystick", "us016", "ir_distance", "mq2", "mq135", "mq5"),',
    '    "ADC12_0": ("adc", "joystick", "us016", "ir_distance", "mq2", "mq135"),',
)
assert '"ADC12_0": ("adc", "joystick", "us016", "ir_distance", "mq2", "mq135"),' in i
# SGP30/AGS10 行属状态 3/4——state1 移除
i = i.replace('    "SGP30": ("sgp30",),\n', "")
i = i.replace('    "AGS10": ("ags10",),\n', "")
assert '    "SGP30": (' not in i and '    "AGS10": (' not in i
INST.write_text(i, encoding="utf-8")
print("inst state1 OK")

# ---- wordlist：去 MQ-5/SGP30/AGS10 solution + models（字符串级删除，保留原格式）
w = WL.read_text(encoding="utf-8")
for name in (
    "MQ-5 液化气/天然气传感器",
    "SGP30 空气质量传感器（TVOC/CO2e）",
    "AGS10 有害气体传感器（TVOC）",
):
    start = w.find(f'      {{\n        "name": "{name}",')
    end = w.find('      {\n        "name": "', start + 1)
    if end < 0:
        end = w.find('    }\n  }\n]', start)
    assert start >= 0 and end > start, name
    w = w[:start] + w[end:]
w = w.replace('"MQ-2", "MQ-135", "MQ-5", "SGP30", "AGS10", "TTP224"', '"MQ-2", "MQ-135", "TTP224"')
w = w.replace('"MQ-2", "MQ-135", "SGP30", "AGS10", "TTP224"', '"MQ-2", "MQ-135", "TTP224"')
# 去残留的 SGP30/AGS10 引用（方案 note 里的分工描述属于 state3/4 的文案）
assert '"MQ-5 液化气' not in w
assert '"SGP30 空气质量' not in w
assert '"AGS10 有害气体' not in w
WL.write_text(w, encoding="utf-8")
print("wordlist state1 OK")
