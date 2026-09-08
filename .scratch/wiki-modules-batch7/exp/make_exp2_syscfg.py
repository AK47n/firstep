# -*- coding: utf-8 -*-
"""实验 2：裁剪后的 mq2 单选 syscfg 加 MEM4/MEM5 通道行 + 引脚行，跑 SysConfig CLI。
验证：a) 多 MEM 序列 + 新通道合法；b) mq135/mq5 候选脚（PB20/PB24/PA22/PA14）
在「无其它共享实例」的裁剪上下文里是否被接受（真实生成场景）。"""
import pathlib

src = pathlib.Path(
    ".scratch/wiki-modules-batch6/matrix/mq2/mspm0.syscfg"
).read_text(encoding="utf-8")
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
(out / "exp2.syscfg").write_text(src, encoding="utf-8")
print("written")
