# -*- coding: utf-8 -*-
"""批次 11 工单收尾：回填结论 + 状态 resolved。"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "issues"

BODY = {
    "mq3": (
        "2026-09-11 完成并提交。ADC 薄封装（依赖 adc 模块共享 ADC12_0 MEM0，默认 PA24，"
        "无新 $assign 行）；mq3_init + mq3_read_percent（5 次快平均 → value/4095×100 出 "
        "0-100% 相对浓度——正向映射页面原式+正文取证，与 mq2 定稿方向一致）；页面 ADC "
        "中断（IRQHandler + gCheckADC）改依赖 adc 模块轮询（共享实例强符号唯一）；页面 "
        "Get_MQ3_DO_value/MQ_DO（LM393 阈值）未用于演示不声明 DO 角色；默认 PA24 与批次 5 "
        "tcs34725 SDA 重叠系 MEM0 槽位唯一所致；notes 写明 MQ 系相对值非 ppm 精标 + 预热 "
        "3-5 分钟/湿度影响 + 多路气体同选共读 MEM0 物理通道限制（MEM 8/8 已满）+ 手册原脚 "
        "PA27 绑定复现；词表感知传感器 +MQ-3；单选生成 → SysConfig CLI → gmake 0 error/"
        "0 warning（PASS，verified=true）；code-review 双轴通过（同构对仗核对；本件非随机"
        "深审件）；未上板。"
    ),
    "mq4": (
        "2026-09-11 完成并提交。ADC 薄封装（依赖 adc 模块共享 ADC12_0 MEM0，默认 PA24，"
        "无新 $assign 行）；同构照抄 mq3；mq4_init + mq4_read_percent（value/4095×100 "
        "正向映射）；页面 ADC 中断改轮询；页面 Get_MQ4_DO_value/MQ_DO 未用于演示不声明 DO "
        "角色；notes 写明 MQ 系相对值非 ppm + 预热/湿度 + 多路气体同选共读 MEM0 限制 + "
        "页面函数注释「酒精值」模板残留错字（本件应为甲烷/天然气）记录；单选生成 → "
        "SysConfig CLI → gmake 0 error/0 warning（PASS，verified=true）；code-review 双轴"
        "通过（同构对仗核对）；未上板。"
    ),
    "mq6": (
        "2026-09-11 完成并提交。ADC 薄封装（依赖 adc 模块共享 ADC12_0 MEM0，默认 PA24，"
        "无新 $assign 行）；同构照抄 mq3；mq6_init + mq6_read_percent（value/4095×100 "
        "正向映射）；页面 ADC 中断改轮询；页面 Get_MQ6_DO_value/MQ_DO 未用于演示不声明 DO "
        "角色；notes 写明 MQ 系相对值非 ppm + 预热/湿度 + 多路气体同选共读 MEM0 限制 + "
        "页面函数注释「酒精值」模板残留错字（本件应为液化气/丙烷）记录；单选生成 → "
        "SysConfig CLI → gmake 0 error/0 warning（PASS，verified=true）；code-review 双轴"
        "通过（同构对仗核对）；未上板。"
    ),
    "mq7": (
        "2026-09-11 完成并提交。ADC 薄封装（依赖 adc 模块共享 ADC12_0 MEM0，默认 PA24，"
        "无新 $assign 行）；同构照抄 mq3；mq7_init + mq7_read_percent（value/4095×100 "
        "正向映射——页面含「电导率随 CO 浓度增加而增大」，器件高低温循环检测但 4Pin 模块"
        "AO 单路输出，notes 记录）；页面 ADC 中断改轮询；页面 Get_MQ7_DO_value/MQ_DO 未用于"
        "演示不声明 DO 角色；notes 写明 MQ 系相对值非 ppm + 预热/湿度 + 多路气体同选共读 "
        "MEM0 限制 + 页面函数注释「酒精值」模板残留错字（本件应为一氧化碳）记录；单选生成 "
        "→ SysConfig CLI → gmake 0 error/0 warning（PASS，verified=true）；code-review 双轴"
        "通过（同构对仗核对）；未上板。"
    ),
    "mq8": (
        "2026-09-11 完成并提交。ADC 薄封装（依赖 adc 模块共享 ADC12_0 MEM0，默认 PA24，"
        "无新 $assign 行）；mq8_init + mq8_read_percent（value/4095×100 正向映射页面原式）；"
        "页面 ADC 中断改轮询；页面 Get_MQ8_DO_value/MQ_DO 未用于演示不声明 DO 角色；notes "
        "写明 MQ 系相对值非 ppm + 预热/湿度 + 多路气体同选共读 MEM0 限制 + 页面函数注释"
        "「酒精值」模板残留错字（本件应为氢气）记录；单选生成 → SysConfig CLI → gmake 0 "
        "error/0 warning（PASS，verified=true）；**code-review 随机深审件（标准+规格双轴" 
        "通过，见 spec 实施结论）**；未上板。"
    ),
    "mq9": (
        "2026-09-11 完成并提交。ADC 薄封装（依赖 adc 模块共享 ADC12_0 MEM0，默认 PA24，"
        "无新 $assign 行）；mq9_init + mq9_read_percent（value/4095×100 正向映射——方向"
        "取证「电导率随 CO 浓度增加而增大」）；页面 ADC 中断改轮询；页面 Get_MQ9_DO_value/"
        "MQ_DO 未用于演示不声明 DO 角色；notes 写明 MQ 系相对值非 ppm + 预热/湿度 + 多路"
        "气体同选共读 MEM0 限制 + **器件双温循环**（低温 1.5V 测 CO、高温 5.0V 测可燃气并"
        "清洗——页面驱动仅单 AO、4Pin 模块无加热控制脚，双通道区分需模块级温控/标定；与 "
        "mq7/mq6 分工）+ 页面函数注释「酒精值」模板残留错字（本件应为一氧化碳/可燃气体）"
        "记录；单选生成 → SysConfig CLI → gmake 0 error/0 warning（PASS，verified=true）；"
        "code-review 双轴通过（同构对仗核对）；未上板。"
    ),
    "ms1100": (
        "2026-09-11 完成并提交。ADC 薄封装（依赖 adc 模块共享 ADC12_0 MEM0，默认 PA24，"
        "无新 $assign 行）；ms1100_init + ms1100_read_percent（value/4095×100——**页面无"
        "百分比函数**，由页面 demo 电压式 value/4095×3.3 推导归一（Vref 3.3V），正向映射"
        "正文取证「AOUT 随气体量变化、清洁空气 <1V」；5 次快平均——页面 30×3ms）；页面 ADC "
        "中断改轮询；页面 Get_DO_Num/MS1100_DO 未用于演示不声明 DO 角色（页面仅述可调电阻"
        "比较——无 LM393 依据）；notes 写明相对值非 ppm 精标 + **预热 3-5 分钟（页面原文）** "
        "+ 多路气体同选共读 MEM0 限制 + 与 sgp30/ags10（ppb/ppm 数字量）及 MQ 系分工；词表"
        "感知传感器 +MS1100；单选生成 → SysConfig CLI → gmake 0 error/0 warning（PASS，"
        "verified=true）；**code-review 随机深审件（标准+规格双轴通过，见 spec 实施结论）**；"
        "未上板。"
    ),
}

FILES = [
    "01-module-mq3.md", "02-module-mq4.md", "03-module-mq6.md",
    "04-module-mq7.md", "05-module-mq8.md", "06-module-mq9.md",
    "07-module-ms1100.md",
]

for slug, body, fname in zip(BODY, BODY.values(), FILES):
    p = OUT / fname
    t = p.read_text(encoding="utf-8")
    old_status = "**状态：** claimed"
    assert old_status in t, p
    t = t.replace(old_status, "**状态：** resolved")
    t = t.replace("**结论：** （实施后回填）", f"**结论：** {body}")
    p.write_text(t, encoding="utf-8")
    print("resolved:", slug)
