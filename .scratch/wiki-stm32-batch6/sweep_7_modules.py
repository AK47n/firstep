# -*- coding: utf-8 -*-
"""wiki-stm32-batch6 七件收官一致性快检（提交前只读扫描，stm32 线版）。

镜像 .scratch/wiki-stm32-batch5/sweep_8_modules.py 的检查面（stm32 侧）+ 本批
特有面：7 件 MQ 系收尾（mq3/mq4/mq6/mq7/mq8/mq9/ms1100）——stm32 条目存在性 /
verified / hardware_bound / wordlist lib_modules 挂接 / kit+source_url（地阔星
wiki 原页判据）/ 依赖 ["adc"] / 引脚宏值（7×AO_CH = ADC_Channel_5）/ pins 形状
（adc 默认 PA5——ADC 共享组并入 batch5 PA5 共读组）/ 守卫（无 printf/GPIO_Init/
RCC_/delay_1ms/stdio 残余、pins 无 DO、正向公式「1.0f - 不得出现」、ms1100
推导 notes）/ notes（手册路径 / 未上板 / 外部分路器物理约束 / 各件检测对象与
串台记录）/ mspm0 条目零改动（比对文件存在性）。
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

# slug -> (pins 期望, 宏值表, notes 必含 needles)
EXPECT = {
    "mq3": {
        "pins": [("MQ3_AO", "adc", "PA5")],
        "macros": [("MQ3_AO_CH", "ADC_Channel_5")],
        "needles": ["酒精", "SAMPLES 30"],
    },
    "mq4": {
        "pins": [("MQ4_AO", "adc", "PA5")],
        "macros": [("MQ4_AO_CH", "ADC_Channel_5")],
        "needles": ["酒精值", "SAMPLES 30"],
    },
    "mq6": {
        "pins": [("MQ6_AO", "adc", "PA5")],
        "macros": [("MQ6_AO_CH", "ADC_Channel_5")],
        "needles": ["酒精值", "SAMPLES 30"],
    },
    "mq7": {
        "pins": [("MQ7_AO", "adc", "PA5")],
        "macros": [("MQ7_AO_CH", "ADC_Channel_5")],
        "needles": ["酒精值", "高低温循环", "SAMPLES 30"],
    },
    "mq8": {
        "pins": [("MQ8_AO", "adc", "PA5")],
        "macros": [("MQ8_AO_CH", "ADC_Channel_5")],
        "needles": ["酒精值", "SAMPLES 30"],
    },
    "mq9": {
        "pins": [("MQ9_AO", "adc", "PA5")],
        "macros": [("MQ9_AO_CH", "ADC_Channel_5")],
        "needles": ["酒精值", "双温循环", "SAMPLES 30"],
    },
    "ms1100": {
        "pins": [("MS1100_AO", "adc", "PA5")],
        "macros": [("MS1100_AO_CH", "ADC_Channel_5")],
        "needles": ["推导", "3-5 分钟", "VOC"],
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
    if "adc" not in deps:
        flags.append("依赖缺adc")
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
        elif "DO" in role:
            flags.append(f"{role} 出现 DO（应不声明）")
    for pat in [r"\bprintf\b", r"\bGPIO_Init\b", r"\bRCC_\w+\s*\(", r"\bdelay_1ms\b",
                r"stm32f10x\.h", r"stm32f4xx\.h", r"\bIRQHandler\b"]:
        if re.search(pat, code_only):
            flags.append(f"代码残留 {pat}")
    if "stdio.h" in code_only:
        flags.append("stdio 残余 include")
    # 正向公式守卫（7 件全部正向——mq2 定稿方向；无反向式）
    if re.search(r"1\.0f - ", code_only):
        flags.append("百分比公式出现反向式（应正向）")
    if "100.0f" not in code_only or f"{slug.upper()}_ADC_MAX" not in code_only:
        flags.append("正向公式/宏缺失")
    # ms1100 推导 notes 必含
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
