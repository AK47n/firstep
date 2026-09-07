# -*- coding: utf-8 -*-
"""wiki-stm32-batch7 五件收官一致性快检（提交前只读扫描，stm32 线版）。

镜像 .scratch/wiki-stm32-batch6/sweep_7_modules.py 的检查面（stm32 侧）+ 本批
特有面：5 件（us016/ir_distance/joystick ADC 件 + ec11/key_matrix B 类件）——
stm32 条目存在性 / verified / hardware_bound / wordlist lib_modules 挂接 /
kit+source_url（地阔星 wiki 原页判据）/ 依赖（ADC 件 == mspm0 现状：us016/
ir_distance=["adc"]、joystick=[]；B 类=[]）/ 引脚宏值（US016_AO_CH 等
ADC_Channel_5、JOYSTICK_X_CH=Channel_1/Y_CH=Channel_0、EC11 6 宏、KEY_MATRIX
16 宏）/ pins 形状（ADC 件默认 PA5/PA1/PA0+SW PA10；B 类 3/8 脚）/ 守卫（无
printf/GPIO_Init/RCC_/delay_1ms/stdio 残余、ADC 件无 DO、us016 双量程 0.25f/
0.75f、ir_distance 3.3f 无 3.5f、joystick 整数 ×100u、ec11 无 EXTI/NVIC/TIM3、
key_matrix i*4+j+1）/ notes（手册路径 / 未上板 / 共享组物理约束 / 各件缺陷
记录）/ mspm0 条目零改动（仅存在性；B 类 mspm0 缺 = 预期）。
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

# slug -> (pins 期望, 宏值表, 依赖期望, B类?, notes 必含 needles, 代码守卫)
EXPECT = {
    "us016": {
        "pins": [("US016_AO", "adc", "PA5")],
        "macros": [("US016_AO_CH", "ADC_Channel_5")],
        "deps": ["adc"],
        "needles": ["3096", "500ms", "互替", "外部分路器", "未上板"],
        "guard": [
            ("US016_ADC_SAMPLES 5", r"#define\s+US016_ADC_SAMPLES\s+5"),
            ("0.75f系数", r"0\.75f"),
            ("0.25f系数", r"0\.25f"),
            ("无0.769式", r"0\.769", None),  # None = 否定（不得出现）
        ],
    },
    "ir_distance": {
        "pins": [("IR_DISTANCE_AO", "adc", "PA5")],
        "macros": [("IR_DISTANCE_AO_CH", "ADC_Channel_5")],
        "deps": ["adc"],
        "needles": ["3.5", "非线性", "互替", "未上板", "外部分路器"],
        "guard": [
            ("IR_DIST_ADC_SAMPLES 10", r"#define\s+IR_DIST_ADC_SAMPLES\s+10"),
            ("3.3f宏化", r"IR_DIST_VREF_V\s+3\.3f"),
            ("无3.5f落码", r"3\.5f", None),
            ("powf公式", r"60\.374f\s*\*\s*powf"),
        ],
    },
    "joystick": {
        "pins": [
            ("JOYSTICK_X", "adc", "PA1"),
            ("JOYSTICK_Y", "adc", "PA0"),
            ("JOYSTICK_SW", "gpio_in", "PA10"),
        ],
        "macros": [
            ("JOYSTICK_X_CH", "ADC_Channel_1"),
            ("JOYSTICK_Y_CH", "ADC_Channel_0"),
            ("JOYSTICK_SW_GPIO", "GPIO_A"),
            ("JOYSTICK_SW_PIN", "Pin_10"),
        ],
        "deps": [],
        "needles": ["MQ2", "60ms", "共享组", "未上板", "外部分路器"],
        "guard": [
            ("4次快平均", r"#define\s+JOYSTICK_ADC_SAMPLES\s+4u"),
            ("整数percent", r"\*\s*100u.*JOYSTICK_ADC_MAX"),
            ("SW极性宏", r"JOYSTICK_SW_PRESSED_LEVEL\s+0"),
            ("无100.0f", r"100\.0f", None),
        ],
    },
    "ec11": {
        "pins": [
            ("EC11_A", "gpio_in", "PA4"),
            ("EC11_B", "gpio_in", "PB5"),
            ("EC11_SW", "gpio_in", "PB0"),
        ],
        "macros": [
            ("EC11_A_GPIO", "GPIO_A"),
            ("EC11_A_PIN", "Pin_4"),
            ("EC11_B_GPIO", "GPIO_B"),
            ("EC11_B_PIN", "Pin_5"),
            ("EC11_SW_GPIO", "GPIO_B"),
            ("EC11_SW_PIN", "Pin_0"),
        ],
        "deps": [],
        "b_class": True,
        "needles": ["B 类", "无 mspm0", "轮询", "TIM3", "按代码", "未上板"],
        "guard": [
            ("增量语义", r"int16_t\s+ec11_get_delta"),
            ("A相跳变采样B", r"ec11_prev_a"),
            ("无EXTI", r"\bEXTI\b", None),
            ("无NVIC", r"\bNVIC\b", None),
            ("无TIM3", r"\bTIM3\b", None),
            ("无delay_ms", r"\bdelay_ms\b", None),
            ("SW低有效", r"ec11_read_sw"),
        ],
    },
    "key_matrix": {
        "pins": [
            ("KEY_MATRIX_ROW1", "gpio_out", "PB12"),
            ("KEY_MATRIX_ROW4", "gpio_out", "PB15"),
            ("KEY_MATRIX_COL1", "gpio_in", "PA9"),
            ("KEY_MATRIX_COL2", "gpio_in", "PA10"),
            ("KEY_MATRIX_COL3", "gpio_in", "PB10"),
            ("KEY_MATRIX_COL4", "gpio_in", "PB11"),
        ],
        "macros": [
            ("KEY_MATRIX_ROW1_GPIO", "GPIO_B"),
            ("KEY_MATRIX_ROW1_PIN", "Pin_12"),
            ("KEY_MATRIX_ROW4_PIN", "Pin_15"),
            ("KEY_MATRIX_COL1_GPIO", "GPIO_A"),
            ("KEY_MATRIX_COL1_PIN", "Pin_9"),
            ("KEY_MATRIX_COL2_PIN", "Pin_10"),
            ("KEY_MATRIX_COL3_GPIO", "GPIO_B"),
            ("KEY_MATRIX_COL3_PIN", "Pin_10"),
            ("KEY_MATRIX_COL4_PIN", "Pin_11"),
        ],
        "deps": [],
        "b_class": True,
        "needles": ["B 类", "无 mspm0", "互替", "8 脚分配", "防抖", "bsp_mh100x", "未上板"],
        "guard": [
            ("i*4+j+1", r"i\s*\*\s*4\s*\+\s*j\s*\+\s*1"),
            ("行列扫描", r"key_matrix_row_set"),
            ("无delay_ms", r"\bdelay_ms\b", None),
            ("无while等待", r"\bwhile\b", None),
        ],
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
    deps = list(m.get("dependencies", []))
    if deps != expect["deps"]:
        flags.append(f"依赖{deps} != {expect['deps']}")
    joined = ""
    for f in st.get("files", []):
        p = MOD / slug / f
        if not p.is_file():
            flags.append(f"缺文件{f}")
            continue
        joined += p.read_text(encoding="utf-8", errors="replace")
    all_code = joined
    code_only = strip_comments(joined, keep_preprocessor=True)
    if re.search(r"\bdelay_(us|ms|cycles)\s*\(", code_only):
        flags.append("stm32用delay未声明（防抖/延时归调用方）")
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
    for label, pat, *rest in expect["guard"]:
        negate = rest and rest[0] is None
        if negate:
            if re.search(pat, code_only):
                flags.append(f"守卫失败：{label}")
        elif not re.search(pat, all_code) and not re.search(pat, code_only):
            flags.append(f"守卫失败：{label}（代码或注释缺失）")
    notes = st.get("notes", "")
    if "地阔星移植手册" not in notes:
        flags.append("notes缺手册路径")
    if "未上板" not in notes:
        flags.append("notes未注明未上板")
    if not expect.get("b_class") and (
        "外部分路器" not in notes and "分时切换" not in notes
    ):
        flags.append("notes缺ADC共享组物理约束")
    for needle in expect["needles"]:
        if needle not in notes:
            flags.append(f"notes缺 {needle}")
    if slug not in libmods:
        flags.append("wordlist未挂接")
    msp = m.get("platforms", {}).get("mspm0")
    if expect.get("b_class"):
        if msp is not None:
            flags.append("B类有mspm0条目（应为缺）")
    else:
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
