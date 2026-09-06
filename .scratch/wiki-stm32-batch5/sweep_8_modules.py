# -*- coding: utf-8 -*-
"""wiki-stm32-batch5 八件收官一致性快检（提交前只读扫描，stm32 线版）。

镜像 .scratch/wiki-stm32-batch4/sweep_4_modules.py 的检查面（stm32 侧）+ 本批
特有面：8 件 ADC 薄封装形态——stm32 条目存在性 / verified / hardware_bound /
wordlist lib_modules 挂接 / kit+source_url（地阔星 wiki 原页判据）/ 依赖正检
（用 delay_us 必须依赖 delay——gp2y）/ 引脚宏值（8×AO_CH + gp2y LED 2 宏）/
pins 形状（adc 默认 PA5 共享组、gp2y 另 gpio_out PB5）/ 成对守卫（rain 正向
「1.0f - 不得出现」× photoresistance 反向「必须出现」）/ 缺陷守卫（s12sd 档位
表 0-11 上界、gp2y 时序宏 280/40/9680 + 5 次快平均无 30、无 printf/GPIO_Init/
RCC_/delay_1ms/stdio 残余、pins 无 DO）/ notes（手册路径 / 未上板 / ADC 共享组
物理约束 / 各件串台记录）/ mspm0 条目零改动（比对文件存在性）。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")
from contest_generator.clex import strip_comments  # noqa: E402

MOD = Path("library/modules")
PIN_CFG = Path("library/masters/stm32/pin_config.h").read_text(
    encoding="utf-8", errors="replace"
)
wl = json.load(open("src/contest_generator/wordlist.json", encoding="utf-8"))
libmods = set()
for g in wl:
    for s in g.get("solutions", []):
        libmods.update(s.get("lib_modules", []))

# slug -> (pins 期望, 宏值表, 依赖, 换算/缺陷守卫正则元组)
EXPECT = {
    "mq2": {
        "pins": [("MQ2_AO", "adc", "PA5")],
        "macros": [("MQ2_AO_CH", "ADC_Channel_5")],
        "deps": ["adc"],
        "needles": ["PA27", "SAMPLES 30"],
    },
    "mq135": {
        "pins": [("MQ135_AO", "adc", "PA5")],
        "macros": [("MQ135_AO_CH", "ADC_Channel_5")],
        "deps": ["adc"],
        "needles": ["酒精值", "SAMPLES 30"],
    },
    "mq5": {
        "pins": [("MQ5_AO", "adc", "PA5")],
        "macros": [("MQ5_AO_CH", "ADC_Channel_5")],
        "deps": ["adc"],
        "needles": ["酒精值", "SAMPLES 30"],
    },
    "photoresistance": {
        "pins": [("PHOTORESISTANCE_AO", "adc", "PA5")],
        "macros": [("PHOTORESISTANCE_AO_CH", "ADC_Channel_5")],
        "deps": ["adc"],
        "needles": ["最亮 100 最暗 0", "反向"],
    },
    "rain": {
        "pins": [("RAIN_AO", "adc", "PA5")],
        "macros": [("RAIN_AO_CH", "ADC_Channel_5")],
        "deps": ["adc"],
        "needles": ["方向修正", "GPIOC"],
    },
    "s12sd": {
        "pins": [("S12SD_AO", "adc", "PA5")],
        "macros": [("S12SD_AO_CH", "ADC_Channel_5")],
        "deps": ["adc"],
        "needles": ["档位表", "IRtracking"],
    },
    "soil": {
        "pins": [("SOIL_AO", "adc", "PA5")],
        "macros": [("SOIL_AO_CH", "ADC_Channel_5")],
        "deps": ["adc"],
        "needles": ["DMA", "可燃气体", "15k"],
    },
    "gp2y1014au": {
        "pins": [
            ("GP2Y1014_AO", "adc", "PA5"),
            ("GP2Y1014_LED", "gpio_out", "PB5"),
        ],
        "macros": [
            ("GP2Y1014_AO_CH", "ADC_Channel_5"),
            ("GP2Y1014_LED_GPIO", "GPIO_B"),
            ("GP2Y1014_LED_PIN", "Pin_5"),
        ],
        "deps": ["adc", "delay"],
        "needles": ["SAMPLES 30", "10ms", "PB5"],
    },
}

batch = list(EXPECT)
print("批次件数:", len(batch))
bad = 0
for slug in batch:
    expect = EXPECT[slug]
    m = json.load(open(MOD / slug / "manifest.json", encoding="utf-8"))
    st = m.get("platforms", {}).get("stm32")
    flags = []
    if st is None:
        flags.append("缺stm32条目")
        print(f"{slug:18s} " + "; ".join(flags))
        bad += 1
        continue
    if st.get("verified") is not True:
        flags.append("stm32 verified非true")
    if st.get("hardware_bound") is not False:
        flags.append("stm32 hardware_bound异常")
    if not st.get("kit"):
        flags.append("stm32 缺kit")
    su = st.get("source_url", "")
    if not re.match(r"https://wiki\.lckfb\.com/zh-hans/dkx-stm32f103c8t6/", su):
        flags.append("source_url非地阔星wiki原页")
    deps = m.get("dependencies", [])
    joined = ""
    for f in st.get("files", []):
        p = MOD / slug / f
        if not p.is_file():
            flags.append(f"缺文件{f}")
            continue
        joined += p.read_text(encoding="utf-8", errors="replace")
    code_only = strip_comments(joined, keep_preprocessor=True)
    if re.search(r"\bdelay_(us|ms|cycles)\s*\(", code_only) and "delay" not in deps:
        flags.append("stm32用delay未依赖")
    # 依赖正检（adc 必含）
    for need_dep in expect["deps"]:
        if need_dep not in deps:
            flags.append(f"依赖缺{need_dep}")
    # 引脚宏 + pins 类型/默认脚
    for macro, want in expect["macros"]:
        if not re.search(rf"#define\s+{macro}\s+{want}", PIN_CFG):
            flags.append(f"pin_config缺{macro}={want}")
    pins = st.get("pins", [])
    got = {p["id"]: p for p in pins}
    for role, want_type, want_pin in expect["pins"]:
        p = got.get(role)
        if p is None:
            flags.append(f"缺pins {role}")
        elif p.get("type") != want_type or p.get("default") != want_pin:
            flags.append(f"{role} 类型/默认异常")
        elif "DO" in role or "DO" in (p.get("id") or ""):
            flags.append(f"{role} 出现 DO（应不声明）")
    if "DO" in st.get("notes", "") and "不声明" not in st.get("notes", ""):
        if slug not in ("s12sd", "gp2y1014au"):
            flags.append("notes 出现 DO 但无不声明说明")
        elif "无 DO" not in st.get("notes", ""):
            flags.append("无 DO 页 notes 未注明（3 Pin/4 线无 DO 脚）")
    # 通用代码守卫：无标准库/寄存器/演示残留
    for pat in [r"\bprintf\b", r"\bGPIO_Init\b", r"\bRCC_\w+\s*\(", r"\bdelay_1ms\b",
                r"stm32f10x\.h", r"stm32f4xx\.h", r"\bIRQHandler\b"]:
        if re.search(pat, code_only):
            flags.append(f"代码残留 {pat}")
    if "stdio.h" in code_only:
        flags.append("stdio 残余 include")
    # 成对守卫：rain 正向（反向式不得出现）× photoresistance 反向（必须出现）
    if slug == "rain":
        if re.search(r"1\.0f - ", code_only):
            flags.append("rain 百分比公式出现反向式（防回潮守卫）")
        if "100.0f" not in code_only or "RAIN_ADC_MAX" not in code_only:
            flags.append("rain 正向公式缺失")
    if slug == "photoresistance":
        if "1.0f - " not in code_only:
            flags.append("photoresistance 反向式缺失（自洽保留守卫）")
    # s12sd 档位表 0-11 上界
    if slug == "s12sd":
        for b in ("227u", "318u", "408u", "503u", "606u", "696u",
                  "795u", "881u", "976u", "1079u", "1170u"):
            if b not in code_only:
                flags.append(f"档位表缺上界 {b}")
        if "* 100.0f" in code_only:
            flags.append("s12sd 出现百分比公式（应为档位表）")
    # gp2y 时序宏 + 5 次快平均（无 30）+ 0.17 系数
    if slug == "gp2y1014au":
        for b in ("GP2Y1014_LED_SETTLE_US", "GP2Y1014_LED_SAMPLE_TAIL_US",
                  "GP2Y1014_LED_CYCLE_TAIL_US"):
            if b not in code_only:
                flags.append(f"gp2y 缺时序宏 {b}")
        if "0.17f * (float)value - 0.1f" not in code_only:
            flags.append("gp2y 缺 0.17 系数原式")
        if "GP2Y1014_ADC_SAMPLES" not in code_only:
            flags.append("gp2y 缺 5 次快平均宏")
        if re.search(r"\b30\b", code_only):
            flags.append("gp2y 出现 30 字面量（SAMPLES 矛盾回潮）")
    # notes 必含：手册路径 / 未上板 / ADC 共享组物理约束 / 各件串台词
    notes = st.get("notes", "")
    if "地阔星移植手册" not in notes:
        flags.append("notes缺手册路径")
    if "未上板" not in notes:
        flags.append("notes未注明未上板")
    if "外部分路器" not in notes and "分时切换" not in notes:
        flags.append("notes缺ADC共享组物理约束")
    for needle in expect["needles"]:
        if needle not in notes:
            flags.append(f"notes缺 {needle}")
    if slug not in libmods:
        flags.append("wordlist未挂接")
    # mspm0 条目零改动（文件齐）
    msp = m.get("platforms", {}).get("mspm0")
    if msp is None:
        flags.append("缺mspm0条目")
    else:
        for f in msp.get("files", []):
            if not (MOD / slug / f).is_file():
                flags.append(f"mspm0缺文件{f}")
    line = f"{slug:18s} " + ("OK" if not flags else "; ".join(flags))
    print(line)
    if flags:
        bad += 1
print("异常件数:", bad)
sys.exit(0 if bad == 0 else 1)
