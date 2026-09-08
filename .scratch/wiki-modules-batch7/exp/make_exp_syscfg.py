# -*- coding: utf-8 -*-
"""实验：母版 syscfg 加 MEM4-7（通道 CH6/CH5/CH7/CH12 + 脚 PB20/PB24/PA22/PA14），
跑 SysConfig CLI 验证多通道 + 与既有默认布局重叠是否被接受。"""
import pathlib

src = pathlib.Path("library/masters/mspm0/mspm0.syscfg").read_text(encoding="utf-8")
src = src.replace(
    "ADC12_0.endAdd                     = 3;",
    "ADC12_0.endAdd                     = 7;",
)
src = src.replace(
    'ADC12_0.peripheral.adcPin0.$assign = "PA27";',
    'ADC12_0.peripheral.adcPin0.$assign = "PA27";\n'
    'ADC12_0.adcMem4chansel             = "DL_ADC12_INPUT_CHAN_6";\n'
    'ADC12_0.adcMem5chansel             = "DL_ADC12_INPUT_CHAN_5";\n'
    'ADC12_0.adcMem6chansel             = "DL_ADC12_INPUT_CHAN_7";\n'
    'ADC12_0.adcMem7chansel             = "DL_ADC12_INPUT_CHAN_12";\n'
    'ADC12_0.peripheral.adcPin6.$assign = "PB20";\n'
    'ADC12_0.peripheral.adcPin5.$assign = "PB24";\n'
    'ADC12_0.peripheral.adcPin7.$assign = "PA22";\n'
    'ADC12_0.peripheral.adcPin12.$assign = "PA14";',
)
out = pathlib.Path(".scratch/wiki-modules-batch7/exp")
out.mkdir(parents=True, exist_ok=True)
(out / "exp.syscfg").write_text(src, encoding="utf-8")
print("written")
