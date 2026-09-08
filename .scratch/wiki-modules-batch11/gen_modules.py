# -*- coding: utf-8 -*-
"""批次 11 七个模块条目生成（mq3/mq4/mq6/mq7/mq8/mq9/ms1100）。

每个模块写入 library/modules/<slug>/{manifest.json, code/<slug>.c, code/<slug>.h}。
verified 初始 false；编译矩阵 PASS 后由回填脚本置 true + notes 追加编译记录。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODS = ROOT / "library" / "modules"

DATA_URL = "https://pan.baidu.com/s/1B8WhPIzTmWwQsFFVayRpAA?pwd=9966"

# slug → 参数
MQ = [
    dict(
        slug="mq3", fn="mq3", up="MQ3",
        title="MQ-3 酒精/汽油蒸汽检测传感器",
        page="sensor--mq-3-sensor.md",
        url="https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-3-sensor.html",
        data_url=DATA_URL, data_pwd="9966",
        case_url="https://pan.baidu.com/s/1DI7-87rM3XmLUu1BMuA1lw?pwd=yk3j", case_pwd="yk3j",
        gas="酒精/汽油蒸汽",
        body="酒精浓度越高气敏电导率越大、AO 电压越高、百分比越高",
        page_body="「传感器的电导率随空气中酒精蒸气浓度的增加而增大」",
        func_src="Get_MQ3_Percentage_value",
        func_demo="酒精含量",
        kit="MQ-3 酒精检测传感器模块（4Pin：VCC/GND/DO/AO；工作 3.3-5V、150mA；AO 模拟量输出，DO 数字量阈值由模块可调电阻控制；对酒精灵敏度高、抗汽油/烟雾/水蒸气干扰）",
        capability="酒精/汽油蒸汽检测、酒驾呼气检测、酒精浓度报警（相对值）",
        wl_name="MQ-3 酒精/汽油蒸汽传感器",
        wl_note="库内 mq3 已打通（mspm0：mq3_init + mq3_read_percent 出 0-100% 相对浓度——**正向映射**（浓度越高 ADC 值越高），与 adc 模块共享 ADC12_0 MEM0、默认 PA24——同选时经引脚绑定消解；**多路气体同选共读 MEM0 物理通道限制**：每路只能接一个器件到 PA24）；**读数是相对值非 ppm 精标**（MQ 系随加热/环境（湿度）/老化漂移，真实 ppm 需标准气体标定）；模块上电必须预热 3-5 分钟否则输出不准；DO 阈值由模块可调电阻控制（库内未声明 DO 角色，需要时经 GPIO 输入自读）；对酒精/汽油蒸汽灵敏（抗汽油/烟雾/水蒸气干扰）；5V 供电",
        wl_suit="酒精/汽油蒸汽检测/酒驾呼气检测/酒精浓度报警/化工环境监测",
    ),
    dict(
        slug="mq4", fn="mq4", up="MQ4",
        title="MQ-4 甲烷/天然气检测传感器",
        page="sensor--mq-4-sensor.md",
        url="https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-4-sensor.html",
        data_url=DATA_URL, data_pwd="9966",
        case_url="https://pan.baidu.com/s/1n8hYw9Oyf_6J-aK26LSzuw?pwd=za8j", case_pwd="za8j",
        gas="甲烷/天然气",
        body="可燃气体浓度越高气敏电导率越大、AO 电压越高、百分比越高",
        page_body="「传感器的电导率随空气中可燃气体浓度的增加而增大」",
        func_src="Get_MQ4_Percentage_value",
        func_demo="甲烷含量",
        kit="MQ-4 天然气传感器模块（4Pin：VCC/GND/DO/AO；工作 3.3-5V、150mA；AO 模拟量输出，DO 数字量阈值由模块可调电阻控制；对甲烷灵敏度高、对丙烷/丁烷较好；抗酒精等干扰）",
        capability="甲烷/天然气泄漏检测、燃气安全监测、可燃气体浓度报警（相对值）",
        wl_name="MQ-4 甲烷/天然气传感器",
        wl_note="库内 mq4 已打通（mspm0：mq4_init + mq4_read_percent 出 0-100% 相对浓度——**正向映射**（浓度越高 ADC 值越高），与 adc 模块共享 ADC12_0 MEM0、默认 PA24——同选时经引脚绑定消解；**多路气体同选共读 MEM0 物理通道限制**：每路只能接一个器件到 PA24）；**读数是相对值非 ppm 精标**（MQ 系随加热/环境（湿度）/老化漂移，真实 ppm 需标准气体标定）；模块上电必须预热 3-5 分钟否则输出不准；DO 阈值由模块可调电阻控制（库内未声明 DO 角色，需要时经 GPIO 输入自读）；对甲烷/天然气灵敏（对丙烷/丁烷较好）；5V 供电",
        wl_suit="甲烷/天然气泄漏检测/燃气安全监测/可燃气体浓度报警",
    ),
    dict(
        slug="mq6", fn="mq6", up="MQ6",
        title="MQ-6 液化气/丙烷检测传感器",
        page="sensor--mq-6-sensor.md",
        url="https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-6-sensor.html",
        data_url=DATA_URL, data_pwd="9966",
        case_url="https://pan.baidu.com/s/1__HTGRmlCbF24DRAgl0KTg?pwd=jgu3", case_pwd="jgu3",
        gas="液化气/丙烷",
        body="可燃气体浓度越高气敏电导率越大、AO 电压越高、百分比越高",
        page_body="「传感器的电导率随空气中可燃气体浓度的增加而增大」",
        func_src="Get_MQ6_Percentage_value",
        func_demo="可燃气体含量",
        kit="MQ-6 液化气传感器模块（4Pin：VCC/GND/DO/AO；工作 3.3-5V、150mA；AO 模拟量输出，DO 数字量阈值由模块可调电阻控制；对丁烷/丙烷/甲烷灵敏度高，特别适合液化气（丙烷））",
        capability="液化气/丙烷泄漏检测、燃气安全监测、可燃气体浓度报警（相对值）",
        wl_name="MQ-6 液化气/丙烷传感器",
        wl_note="库内 mq6 已打通（mspm0：mq6_init + mq6_read_percent 出 0-100% 相对浓度——**正向映射**（浓度越高 ADC 值越高），与 adc 模块共享 ADC12_0 MEM0、默认 PA24——同选时经引脚绑定消解；**多路气体同选共读 MEM0 物理通道限制**：每路只能接一个器件到 PA24）；**读数是相对值非 ppm 精标**（MQ 系随加热/环境（湿度）/老化漂移，真实 ppm 需标准气体标定）；模块上电必须预热 3-5 分钟否则输出不准；DO 阈值由模块可调电阻控制（库内未声明 DO 角色，需要时经 GPIO 输入自读）；对液化气（丙烷）/丁烷/甲烷灵敏；5V 供电",
        wl_suit="液化气/丙烷泄漏检测/燃气安全监测/可燃气体浓度报警",
    ),
    dict(
        slug="mq7", fn="mq7", up="MQ7",
        title="MQ-7 一氧化碳检测传感器",
        page="sensor--mq-7-sensor.md",
        url="https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-7-sensor.html",
        data_url=DATA_URL, data_pwd="9966",
        case_url="https://pan.baidu.com/s/1PUEsbO8ZdNNtxIfaUp4H0g?pwd=m2y4", case_pwd="m2y4",
        gas="一氧化碳",
        body="一氧化碳浓度越高气敏电导率越大、AO 电压越高、百分比越高",
        page_body="「采用高低温循环检测方式低温（1.5V加热）检测一氧化碳，传感器的电导率随空气中一氧化碳气体浓度增加而增大」",
        func_src="Get_MQ7_Percentage_value",
        func_demo="一氧化碳含量",
        kit="MQ-7 一氧化碳传感器模块（4Pin：VCC/GND/DO/AO；工作 3.3-5V、150mA；AO 模拟量输出，DO 数字量阈值由模块可调电阻控制；高低温循环检测（低温 1.5V 测 CO、高温 5.0V 清洗），对一氧化碳灵敏度高）",
        capability="一氧化碳检测、CO 报警、燃气不完全燃烧监测（相对值）",
        wl_name="MQ-7 一氧化碳传感器",
        wl_note="库内 mq7 已打通（mspm0：mq7_init + mq7_read_percent 出 0-100% 相对浓度——**正向映射**（浓度越高 ADC 值越高），与 adc 模块共享 ADC12_0 MEM0、默认 PA24——同选时经引脚绑定消解；**多路气体同选共读 MEM0 物理通道限制**：每路只能接一个器件到 PA24）；**读数是相对值非 ppm 精标**（MQ 系随加热/环境（湿度）/老化漂移，真实 ppm 需标准气体标定）；模块上电必须预热 3-5 分钟否则输出不准；DO 阈值由模块可调电阻控制（库内未声明 DO 角色，需要时经 GPIO 输入自读）；器件高低温循环检测（页面驱动仅单 AO——双通道区分需模块级温控/标定）；对一氧化碳灵敏；5V 供电",
        wl_suit="一氧化碳检测/CO 报警/燃气不完全燃烧监测/地下车库通风联动",
    ),
    dict(
        slug="mq8", fn="mq8", up="MQ8",
        title="MQ-8 氢气检测传感器",
        page="sensor--mq-8-sensor.md",
        url="https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-8-sensor.html",
        data_url=DATA_URL, data_pwd="9966",
        case_url="https://pan.baidu.com/s/11I33nBFpygcLNb9XM4nWIQ?pwd=kpr3", case_pwd="kpr3",
        gas="氢气",
        body="氢气浓度越高气敏电导率越大、AO 电压越高、百分比越高",
        page_body="「传感器的电导率随氢气浓度的增加而增大」",
        func_src="Get_MQ8_Percentage_value",
        func_demo="氢气含量",
        kit="MQ-8 氢气传感器模块（4Pin：VCC/GND/DO/AO；工作 3.3-5V、150mA；AO 模拟量输出，DO 数字量阈值由模块可调电阻控制；对氢气灵敏度高、可检测氢能源相关泄漏）",
        capability="氢气检测、氢能源安全监测、氢气浓度报警（相对值）",
        wl_name="MQ-8 氢气传感器",
        wl_note="库内 mq8 已打通（mspm0：mq8_init + mq8_read_percent 出 0-100% 相对浓度——**正向映射**（浓度越高 ADC 值越高），与 adc 模块共享 ADC12_0 MEM0、默认 PA24——同选时经引脚绑定消解；**多路气体同选共读 MEM0 物理通道限制**：每路只能接一个器件到 PA24）；**读数是相对值非 ppm 精标**（MQ 系随加热/环境（湿度）/老化漂移，真实 ppm 需标准气体标定）；模块上电必须预热 3-5 分钟否则输出不准；DO 阈值由模块可调电阻控制（库内未声明 DO 角色，需要时经 GPIO 输入自读）；对氢气灵敏；5V 供电",
        wl_suit="氢气检测/氢能源安全监测/氢气泄漏报警",
    ),
    dict(
        slug="mq9", fn="mq9", up="MQ9",
        title="MQ-9 一氧化碳/可燃气体检测传感器",
        page="sensor--mq-9-sensor.md",
        url="https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-9-sensor.html",
        data_url=DATA_URL, data_pwd="9966",
        case_url="https://pan.baidu.com/s/1oEguSddIoC8ylQPQ55EKVA?pwd=9k5m", case_pwd="9k5m",
        gas="一氧化碳/可燃气体",
        body="气敏电导率随检测气体浓度增加而增大、AO 电压越高、百分比越高",
        page_body="「采用高低温循环检测方式低温（1.5V加热）检测一氧化碳……高温（5.0V加热）检测可燃气体甲烷、丙烷」",
        func_src="Get_MQ9_Percentage_value",
        func_demo="可燃气体含量",
        kit="MQ-9 一氧化碳/可燃气体传感器模块（4Pin：VCC/GND/DO/AO；工作 3.3-5V、150mA；AO 模拟量输出，DO 数字量阈值由模块可调电阻控制；高低温循环检测——低温测 CO、高温测可燃气并清洗）",
        capability="一氧化碳/可燃气体检测、燃气与 CO 报警（相对值）",
        wl_name="MQ-9 一氧化碳/可燃气体传感器",
        wl_note="库内 mq9 已打通（mspm0：mq9_init + mq9_read_percent 出 0-100% 相对浓度——**正向映射**（浓度越高 ADC 值越高），与 adc 模块共享 ADC12_0 MEM0、默认 PA24——同选时经引脚绑定消解；**多路气体同选共读 MEM0 物理通道限制**：每路只能接一个器件到 PA24）；**读数是相对值非 ppm 精标**（MQ 系随加热/环境（湿度）/老化漂移，真实 ppm 需标准气体标定）；模块上电必须预热 3-5 分钟否则输出不准；DO 阈值由模块可调电阻控制（库内未声明 DO 角色，需要时经 GPIO 输入自读）；器件双温循环（低温 CO/高温可燃气）——页面驱动仅单 AO、4Pin 模块无加热控制脚，双通道区分需模块级温控/标定；与 mq7（CO 专一）/mq6（可燃气专一）分工；5V 供电",
        wl_suit="一氧化碳/可燃气体检测/燃气与 CO 报警/地下车库与厨房安全监测",
    ),
]

MS = dict(
    slug="ms1100", fn="ms1100", up="MS1100",
    title="MS1100 VOC 气体检测传感器（甲醛/苯系）",
    page="sensor--ms1100-gas-sensor.md",
    url="https://wiki.lckfb.com/zh-hans/dmx/module/sensor/ms1100-gas-sensor.html",
    data_url="https://pan.baidu.com/s/16hOBTKXWejzmklAeRxfmTg", data_pwd="ixqv",
    case_url="https://pan.baidu.com/s/1upHo8zWHao9Hj80uPWB6Pg?pwd=2ale", case_pwd="2ale",
    gas="VOC（甲醛/甲苯/苯系）",
    body="VOC 浓度越高 AOUT 电压越高、百分比越高（清洁空气电压 <1V）",
    page_body="「AOUT : 模拟输出量，芯片检测到的气体量对应的电压值变化」「清洁空气中电压 < 1V」",
    func_src="（页面无百分比函数——demo 电压式 value/4095×3.3 推导）",
    func_demo="Voltage = %d.%02d",
    kit="CJMCU-1100 MS1100 VOC 气体传感器模块（4Pin：VCC/GND/DOUT/AOUT；工作 5V、<50uA；AOUT 模拟量输出，DOUT 数字量阈值与 4K 可调电阻比较；对甲醛/甲苯/苯等 VOC 灵敏、可侦测 0.1ppm 以上）",
    capability="VOC/甲醛/苯系检测、室内空气质量监测、浓度报警（相对值）",
    wl_name="MS1100 VOC 气体传感器（甲醛/苯系）",
    wl_note="库内 ms1100 已打通（mspm0：ms1100_init + ms1100_read_percent 出 0-100% 相对浓度——read_percent 由页面 demo 电压式推导（value/4095×3.3 → percent=value/4095×100，Vref 3.3V 归一；**正向映射**：浓度越高 AOUT 电压越高），与 adc 模块共享 ADC12_0 MEM0、默认 PA24——同选时经引脚绑定消解；**多路气体同选共读 MEM0 物理通道限制**：每路只能接一个器件到 PA24）；**读数是相对值非 ppm 精标**（页面未给电压-浓度换算表，真实浓度需标定）；**上电预热 3-5 分钟**（页面原文）再测量；DOUT 阈值由模块可调电阻控制（库内未声明 DO 角色，需要时经 GPIO 输入自读）；对甲醛/甲苯/苯等 VOC 灵敏（半导体型）；5V 供电；与 sgp30/ags10（ppb/ppm 数字量）分工：要数字绝对量用后两者、只要相对报警/低成本用本件",
    wl_suit="VOC/甲醛/苯系检测/室内空气质量监测/通风净化联动",
)


def mq_c(p: dict) -> str:
    f = p["fn"]
    u = p["up"]
    slug = p["slug"]
    gas = p["gas"]
    body = p["body"]
    src = p["func_src"]
    page = p["page"]
    return f'''#include "{f}.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM0（薄封装） */

/* {p["title"]}（mspm0 纯驱动薄封装）：
 * - 依赖 adc 模块读 ADC12_0 MEM0 槽位（默认 PA24/A0_3）——不新开 ADC 通道；
 * - 换算 percent = value/4095×100（页面 {src} 原式——
 *   **正向映射**：{body}；相对值非
 *   ppm 精标；模块上电后 AO 电压随加热漂移，需预热/标定）；
 * - 轮询读取，无 ADC 中断（共享 ADC12_0 实例：多模块同选时 IRQHandler 强
 *   符号须唯一，joystick/adc 先例）；
 * - 5 次快速平均（立创原版 30 次 ×5ms 太慢，us016 快平均先例）。 */

float {f}_read_percent(void)
{{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < {u}_ADC_SAMPLES; i++) {{
        sum += adc_get(ADC_1, ADC_Channel_0);
    }}
    return (float)(sum / {u}_ADC_SAMPLES) / (float){u}_ADC_MAX * 100.0f;
}}

void {f}_init(void)
{{
    adc_init(ADC_1, ADC_Channel_0); /* 外设配置由 SYSCFG_DL_init() 完成 */
}}
'''


def mq_h(p: dict) -> str:
    f = p["fn"]
    u = p["up"]
    slug = p["slug"]
    title = p["title"]
    page = p["page"]
    gas = p["gas"]
    page_body = p["page_body"]
    return f'''#ifndef {u}_H
#define {u}_H

#include <stdint.h>

/* {title}驱动（mspm0 纯驱动薄封装，ADR 0009）：
 * - 薄封装：依赖库内 adc 模块读 ADC12_0 MEM0（adc_get(ADC_1, ADC_Channel_0)），
 *   不新开 ADC 通道——{slug} 与 adc/us016/mq2/批次 9 四件共享 MEM0 槽位
 *   （默认 PA24/A0_3）；
 * - 输出电压 → 浓度百分比：percent = value/4095×100（页面原式——**正向映射**：
 *   浓度越高 ADC 值越高、百分比越高；**相对值**，非 ppm 精标；模块上电需预热
 *   3-5 分钟、湿度影响读数、真实 ppm 需标准气体标定）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 30 次×5ms，按 us016 快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/{page}
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、DO 数字量阈值未声明——页面 Get_{slug.upper()}_DO_value
 * 仅定义未用于演示）。多路气体同选共读 MEM0 现实约束：同一引脚 PA24 只能接
 * 一个器件；多路同时测需外部分路或换独立通道（MEM 槽位已满 8/8）。
 * 取证：{page_body} */

/* 百分比换算：12bit 满量程 4095（页面 adc_max 原值），输出 0-100% 相对值 */
#define {u}_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，us016 快平均先例改 5 次） */
#define {u}_ADC_SAMPLES 5u

/* {f}_init：使能 ADC12_0 转换（薄封装——adc_init 即 MEM0 轮询初始化）。 */
void {f}_init(void);

/* {f}_read_percent：读 AO 电压对应浓度百分比（0-100% 相对值——MQ 系读数
 * 随环境/老化漂移，非 ppm 精标；模块预热后读数才稳定）。 */
float {f}_read_percent(void);

#endif /* {u}_H */
'''


def ms_c(p: dict) -> str:
    f = p["fn"]
    u = p["up"]
    return f'''#include "{f}.h"
#include "adc_mspm0.h" /* adc_init / adc_get：共享 ADC12_0 MEM0（薄封装） */

/* MS1100 VOC 气体检测（mspm0 纯驱动薄封装）：
 * - 依赖 adc 模块读 ADC12_0 MEM0 槽位（默认 PA24/A0_3）——不新开 ADC 通道；
 * - 换算 percent = value/4095×100（页面 demo 电压式 value/4095×3.3 推导——
 *   页面无百分比函数；Vref 3.3V 满量程归一 → percent = voltage/3.3×100；
 *   **正向映射**：VOC 浓度越高 AOUT 电压越高、百分比越高；相对值非 ppm
 *   精标；模块上电必须预热 3-5 分钟否则输出不准）；
 * - 轮询读取，无 ADC 中断（共享 ADC12_0 实例：多模块同选时 IRQHandler 强
 *   符号须唯一，joystick/adc 先例）；
 * - 5 次快速平均（立创原版 30 次 ×3ms 太慢，us016 快平均先例）。 */

float {f}_read_percent(void)
{{
    uint32_t sum = 0;
    uint8_t i;

    for (i = 0; i < {u}_ADC_SAMPLES; i++) {{
        sum += adc_get(ADC_1, ADC_Channel_0);
    }}
    return (float)(sum / {u}_ADC_SAMPLES) / (float){u}_ADC_MAX * 100.0f;
}}

void {f}_init(void)
{{
    adc_init(ADC_1, ADC_Channel_0); /* 外设配置由 SYSCFG_DL_init() 完成 */
}}
'''


def ms_h(p: dict) -> str:
    f = p["fn"]
    u = p["up"]
    slug = p["slug"]
    title = p["title"]
    page = p["page"]
    return f'''#ifndef {u}_H
#define {u}_H

#include <stdint.h>

/* {title}驱动（mspm0 纯驱动薄封装，ADR 0009）：
 * - 薄封装：依赖库内 adc 模块读 ADC12_0 MEM0（adc_get(ADC_1, ADC_Channel_0)），
 *   不新开 ADC 通道——{slug} 与 adc/us016/mq2/批次 9 四件共享 MEM0 槽位
 *   （默认 PA24/A0_3）；
 * - 输出电压 → 浓度百分比：percent = value/4095×100（**页面无百分比函数**，
 *   由页面 demo 电压式 value/4095×3.3 推导——Vref 3.3V 满量程归一；
 *   **正向映射**：浓度越高 AOUT 电压越高、百分比越高；**相对值**，非 ppm
 *   精标；模块上电必须预热 3-5 分钟、真实浓度需标定）；
 * - 轮询读取（无 ADC 中断——共享 ADC12_0 实例，IRQHandler 强符号须唯一）；
 * - 5 次快速平均（立创原版 30 次×3ms，按 us016 快平均先例）。
 * 对应手册：sources/materials/lckfb-地猛星移植手册/{page}
 * （立创 wiki 地猛星移植手册；代码按模块库规范改写：去 main/printf、函数名
 * 规范化、ADC 中断改轮询、DO 数字量阈值未声明——页面 Get_DO_Num/MS1100_DO
 * 仅定义未用于演示）。多路气体同选共读 MEM0 现实约束：同一引脚 PA24 只能接
 * 一个器件；多路同时测需外部分路或换独立通道（MEM 槽位已满 8/8）。
 * 取证：「AOUT 为芯片检测到的气体量对应的电压值变化」「清洁空气中电压 < 1V」 */

/* 百分比换算：12bit 满量程 4095（页面 demo 分母），输出 0-100% 相对值 */
#define {u}_ADC_MAX 4095u

/* 快速平均采样次数（页面 SAMPLES 30 次累加，us016 快平均先例改 5 次） */
#define {u}_ADC_SAMPLES 5u

/* {f}_init：使能 ADC12_0 转换（薄封装——adc_init 即 MEM0 轮询初始化）。 */
void {f}_init(void);

/* {f}_read_percent：读 AOUT 电压对应浓度百分比（0-100% 相对值——非 ppm 精标；
 * 模块预热 3-5 分钟后读数才稳定）。 */
float {f}_read_percent(void);

#endif /* {u}_H */
'''


def mq_notes(p: dict) -> str:
    f = p["fn"]
    u = p["up"]
    slug = p["slug"]
    gas = p["gas"]
    page = p["page"]
    return (
        "薄封装：无独立 syscfg 实例——依赖 adc 模块共享 ADC12_0 实例 MEM0 槽位"
        f"（默认 PA24/A0_3，与 adc/us016/mq2/批次 9 四件共读同槽；绑定换引脚 = "
        f"改写 adcPin*.$assign + adcMem*chansel，模块零改动；手册原脚 PA27/A0_0 "
        f"经绑定即可复现——绑 PA27 时改写器按通道号换 adcPin3→adcPin0 + "
        f"adcMem0chansel→CHAN_0）。轮询读取（adc_get 忙等）无 ADC 中断——共享 "
        f"ADC12_0 实例，IRQHandler 强符号须唯一（joystick/adc 先例）。换算 "
        f"percent = value/4095×100（页面 {p['func_src']} 原式——**正向映射**："
        f"{p['body'].split('、')[0]}、百分比越高；页面正文取证"
        f"「{p['page_body'].strip('「」')}」"
        f"与代码一致，与 mq2 定稿方向相同；**相对值非 ppm 精标**：MQ 系读数随"
        f"加热/环境（湿度）/老化漂移，真实 ppm 需标准气体标定；模块上电必须预热 "
        f"3-5 分钟否则输出不准）。页面 Get_Adc_{slug.upper()}_Value 30 次累加×5ms "
        f"改 5 次快速平均（us016 快平均先例）；页面 ADC 中断（ADC12_0_INST_IRQHandler "
        f"+ gCheckADC 标志位）改依赖 adc 模块轮询（共享实例 IRQHandler 强符号唯一）；"
        f"页面 Get_{slug.upper()}_DO_value/MQ_DO 宏（DO 数字量阈值输出，LM393 比较）"
        f"未用于演示 → 不声明 DO 角色（阈值由模块可调电阻控制，需要经引脚绑定 GPIO "
        f"输入自行读取）。**多路气体同选共读 MEM0 物理通道限制**：薄封装模式每路只能"
        f"接一个器件到 PA24——多路同选场景需外部分路或换独立通道（ADC12_0 MEM 槽位"
        f"已满 8/8，板上无剩余通道，现实约束）。\n"
        f"wiki 手册来源：sources/materials/lckfb-地猛星移植手册/{page}"
        f"（原页 {p['url']}；网盘资料 {p['data_url']} 提取码 {p['data_pwd']}；"
        f"移植成功案例 {p['case_url']} 提取码 {p['case_pwd']}）。改造要点：去掉 "
        f"main.c 演示与 printf；函数名规范化（{f}_init/read_percent）；"
        f"ADC_MQ{f[2:].upper()}_Init/ADC_GET/Get_Adc_{slug.upper()}_Value/"
        f"{p['func_src']} 归一；ADC 中断改轮询；DO 宏未用不声明；默认 PA24 与批次 5 "
        f"tcs34725 SDA 重叠系 ADC12_0 MEM0 槽位唯一所致（同选经引脚绑定消解——"
        f"tcs34725 SDA 换脚即可）。\n"
    )


def ms_notes(p: dict) -> str:
    f = p["fn"]
    u = p["up"]
    slug = p["slug"]
    page = p["page"]
    return (
        "薄封装：无独立 syscfg 实例——依赖 adc 模块共享 ADC12_0 实例 MEM0 槽位"
        "（默认 PA24/A0_3，与 adc/us016/mq2/批次 9 四件共读同槽；绑定换引脚 = "
        "改写 adcPin*.$assign + adcMem*chansel，模块零改动；手册原脚 PA27/A0_0 "
        "经绑定即可复现——绑 PA27 时改写器按通道号换 adcPin3→adcPin0 + "
        "adcMem0chansel→CHAN_0）。轮询读取（adc_get 忙等）无 ADC 中断——共享 "
        "ADC12_0 实例，IRQHandler 强符号须唯一（joystick/adc 先例）。换算 "
        "percent = value/4095×100（**页面无百分比函数**——由页面 demo 电压式 "
        "voltage=(value/4095)×3.3 推导：Vref 3.3V 满量程归一 → percent = "
        "voltage/3.3×100 = value/4095×100；**正向映射**：VOC 浓度越高 AOUT 电压"
        "越高、百分比越高（正文「AOUT 为芯片检测到的气体量对应的电压值变化」"
        "「清洁空气中电压 < 1V」）；**相对值非 ppm 精标**：页面未给电压-浓度换算"
        "表（对应关系为图片无图注），真实浓度需标定；**模块上电必须预热 3-5 分钟"
        "（页面原文）否则输出不准**）。页面 Get_ADC_Value 30 次累加×3ms 改 5 次"
        "快速平均（us016 快平均先例）；页面 ADC 中断（ADC12_0_INST_IRQHandler + "
        "gCheckADC 标志位）改依赖 adc 模块轮询（共享实例 IRQHandler 强符号唯一）；"
        "页面 Get_DO_Num/MS1100_DO 宏（DOUT 与 4K 可调电阻比较阈值，LM393 比较）"
        "未用于演示 → 不声明 DO 角色（阈值由模块可调电阻控制，需要经引脚绑定 GPIO "
        "输入自行读取）。**多路气体同选共读 MEM0 物理通道限制**：薄封装模式每路只能"
        "接一个器件到 PA24——多路同选场景需外部分路或换独立通道（ADC12_0 MEM 槽位"
        "已满 8/8，板上无剩余通道，现实约束）。与库内分工：MS1100 对甲醛/甲苯/苯等 "
        "VOC 灵敏（半导体型、5V、<50uA），sgp30/ags10 为数字量 ppb/ppm 绝对读数"
        "（要数字绝对量用后两者、只要相对报警/低成本用本件）；MQ 系偏可燃气体。\n"
        f"wiki 手册来源：sources/materials/lckfb-地猛星移植手册/{page}"
        f"（原页 {p['url']}；网盘资料 {p['data_url']} 提取码 {p['data_pwd']}；"
        f"移植成功案例 {p['case_url']} 提取码 {p['case_pwd']}）。改造要点：去掉 "
        f"main.c 演示与 printf；函数名规范化（{f}_init/read_percent）；"
        "MS1100_Init/ADC_GET/Get_ADC_Value 归一；ADC 中断改轮询；DO 宏未用不声明；"
        "默认 PA24 与批次 5 tcs34725 SDA 重叠系 ADC12_0 MEM0 槽位唯一所致（同选经"
        "引脚绑定消解——tcs34725 SDA 换脚即可）。\n"
    )


def manifest_of(p: dict, notes: str, desc: str, kit: str, wl_name: str) -> dict:
    slug = p["slug"]
    return {
        "slug": slug,
        "description": desc,
        "dependencies": ["adc"],
        "platforms": {
            "mspm0": {
                "files": [f"code/{slug}.c", f"code/{slug}.h"],
                "verified": False,
                "hardware_bound": False,
                "notes": notes,
                "kit": kit,
                "source_url": p["url"],
                "pins": [
                    {
                        "id": f"{slug.upper()}_AO_CH0",
                        "type": "adc",
                        "default": "PA24",
                        "required": True,
                    }
                ],
            }
        },
    }


def write_entry(p: dict, notes: str, desc: str, kit: str, c: str, h: str) -> None:
    d = MODS / p["slug"]
    (d / "code").mkdir(parents=True, exist_ok=True)
    (d / "code" / f"{p['slug']}.c").write_text(c, encoding="utf-8")
    (d / "code" / f"{p['slug']}.h").write_text(h, encoding="utf-8")
    man = manifest_of(p, notes, desc, kit, p["wl_name"])
    (d / "manifest.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("written:", p["slug"])


for i, p in enumerate(MQ, start=1):
    write_entry(
        p,
        mq_notes(p),
        (
            f"{p['title']}驱动（mspm0 纯驱动薄封装，ADR 0009）：依赖库内 adc 模块共享 "
            f"ADC12_0 MEM0 槽位读数（不新开 ADC 通道），{p['fn']}_init + "
            f"{p['fn']}_read_percent 出 0-100% 浓度百分比（相对值非 ppm 精标）；"
            f"适用于{p['capability']}等赛题功能。"
        ),
        p["kit"],
        mq_c(p),
        mq_h(p),
    )

write_entry(
    MS,
    ms_notes(MS),
    (
        "MS1100 VOC 气体检测传感器驱动（mspm0 纯驱动薄封装，ADR 0009）：依赖库内 "
        "adc 模块共享 ADC12_0 MEM0 槽位读数（不新开 ADC 通道），ms1100_init + "
        "ms1100_read_percent 出 0-100% 浓度百分比（相对值非 ppm 精标；页面无百分比"
        "函数——由 demo 电压式推导）；适用于 VOC/甲醛/苯系检测、室内空气质量监测、"
        "浓度报警等赛题功能。"
    ),
    MS["kit"],
    ms_c(MS),
    ms_h(MS),
)
