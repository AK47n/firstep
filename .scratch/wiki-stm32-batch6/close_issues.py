# -*- coding: utf-8 -*-
"""wiki-stm32-batch6 七张工单回填（Status resolved + checkbox + 结论）。
机械替换：仅动状态行/复选框/验收标准前插入结论段。"""
from pathlib import Path

ISSUES = Path(".scratch/wiki-stm32-batch6/issues")

# slug -> (文件名, 结论段, 提交号)
DATA = {
    "mq3": ("01-module-mq3.md", "结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc：mq3_init = adc_init(ADC_1, MQ3_AO_CH) + 5 次 adc_get 快平均——零寄存器/标准库调用）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，**ADC 共享组**：本批 7 件并入 batch5 的 PA5 共读组（flame + 8 + 7 = 16 ADC 角色同脚），ml_adc 顺序调用无扰；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MQ3_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq3_init + mq3_read_percent，float 0-100% 正向 value/4095×100——酒精/汽油蒸汽，相对值非 ppm 精标，需预热）；页面 SAMPLES 30×5ms→5 次快平均 + C99 for 改 uint8_t；DO 未用不声明（PA1 IPU 演示未用）；verified=true（UV4 矩阵 0 error/0 module warning，2026-09-06）+ kit/source_url（地阔星 wiki 原页）+ notes（手册/网盘/检测对象/共享组/未上板）；测试扩展（形状/宏/单选生成/mspm0 零改动/守卫）；wordlist 零补录；mspm0 条目零改动；提交 6b3a4f43（中文）。", "6b3a4f43"),
    "mq4": ("02-module-mq4.md", "结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组：并入 batch5 PA5 共读组——16 ADC 角色同脚；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MQ4_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq4_init + mq4_read_percent——甲烷/天然气正向 value/4095×100）；**页面 DO 注释「酒精值」MQ-3 模板串台**——notes 记录不落码（源码零字面量守卫）；SAMPLES 30→5 快平均 + C99 改 uint8_t；DO 未用不声明；verified=true（UV4 0/0，2026-09-06）+ kit/source_url + notes；wordlist 零补录；mspm0 零改动；提交 17b3f4ee（中文）。", "17b3f4ee"),
    "mq6": ("03-module-mq6.md", "结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组并入 batch5 PA5 共读组——16 ADC 角色同脚；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MQ6_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq6_init + mq6_read_percent——液化气/丙烷正向 value/4095×100）；「酒精值」串台 notes 记录不落码；SAMPLES 30→5 快平均 + C99 改 uint8_t；DO 未用不声明；verified=true（UV4 0/0，2026-09-06）+ kit/source_url + notes；wordlist 零补录；mspm0 零改动；提交 4daa102e（中文）。", "4daa102e"),
    "mq7": ("04-module-mq7.md", "结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组并入 batch5 PA5 共读组——16 ADC 角色同脚；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MQ7_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq7_init + mq7_read_percent——CO 正向 value/4095×100）；**高低温循环检测但 4Pin AO 单路输出说明**（低温 1.5V 测 CO、高温 5.0V 清洗——本件只读 AO 单路百分比，双通道区分需模块级温控/标定——notes）；「酒精值」串台 notes；SAMPLES 30→5 快平均 + C99 改 uint8_t；DO 未用不声明；verified=true（UV4 0/0，2026-09-06）+ kit/source_url + notes；wordlist 零补录；mspm0 零改动；提交 7b70ec4c（中文）。", "7b70ec4c"),
    "mq8": ("05-module-mq8.md", "结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组并入 batch5 PA5 共读组——16 ADC 角色同脚；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MQ8_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq8_init + mq8_read_percent——氢气正向 value/4095×100）；「酒精值」串台 notes 记录不落码；SAMPLES 30→5 快平均 + C99 改 uint8_t；DO 未用不声明；verified=true（UV4 0/0，2026-09-06）+ kit/source_url + notes；wordlist 零补录；mspm0 零改动；提交 b6a20199（中文）。", "b6a20199"),
    "mq9": ("06-module-mq9.md", "结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组并入 batch5 PA5 共读组——16 ADC 角色同脚；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MQ9_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（mq9_init + mq9_read_percent——CO/可燃气正向 value/4095×100）；**器件双温循环原理说明**（低温 1.5V 测 CO、高温 5.0V 测可燃气并清洗——页面驱动仅单 AO 单路百分比、4Pin 模块无加热控制脚，双通道区分需模块级温控/标定；与 mq7/mq6 分工——notes）；「酒精值」串台 notes；SAMPLES 30→5 快平均 + C99 改 uint8_t；DO 未用不声明；verified=true（UV4 0/0，2026-09-06）+ kit/source_url + notes；wordlist 零补录；mspm0 零改动；提交 09f2d0ef（中文）。", "09f2d0ef"),
    "ms1100": ("07-module-ms1100.md", "结论回填（2026-09-06）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组并入 batch5 PA5 共读组——16 ADC 角色同脚；同一物理脚只能接一件器件——多件同测需外部分路器/分时切换；白名单 PA5 组登记）；MS1100_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（ms1100_init + ms1100_read_percent——**页面无百分比函数，由 demo 电压式 value/4095×3.3 推导归一 read_percent（Vref 3.3V——notes 记录推导）**，VOC/甲醛/苯系正向 value/4095×100；预热 3-5 分钟）；DOUT 未用不声明（4K 可调电阻比较）；与 sgp30/ags10 数字量 VOC 分工 notes；SAMPLES 30×3ms→5 快平均；verified=true（UV4 0/0，2026-09-06）+ kit/source_url + notes；wordlist 零补录；mspm0 零改动；提交 2f6d1b21（中文）。", "2f6d1b21"),
}

for slug, (fname, conclusion, commit) in DATA.items():
    p = ISSUES / fname
    text = p.read_text(encoding="utf-8")
    assert "**状态：** claimed" in text, f"{fname} 状态行缺失"
    text = text.replace("**状态：** claimed", "**状态：** resolved", 1)
    text = text.replace("- [ ]", "- [x]")
    anchor = "**验收标准：**"
    assert anchor in text, f"{fname} 验收标准锚缺失"
    block = f"**{conclusion}**\n\n"
    text = text.replace(anchor, block + anchor, 1)
    p.write_text(text, encoding="utf-8", newline="\n")
    print(f"{fname} 回填完成 -> {commit}")
