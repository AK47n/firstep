# -*- coding: utf-8 -*-
"""wiki-stm32-batch4 四件收官一致性快检（提交前只读扫描，stm32 线版）。

镜像 .scratch/wiki-stm32-batch3/sweep_7_modules.py 的检查面（stm32 侧）：
stm32 条目存在性 / verified / hardware_bound / wordlist lib_modules 挂接 /
kit+source_url（wiki 原页判据）/ 依赖正检（用 delay_us/ms 必须依赖 delay）；
批次 4 新增面：软 I2C 两件（bmp180/ms5611）共总线不变量——每件 4 宏都在
pin_config.h 且 SCL=GPIO_A/Pin_6、SDA=GPIO_A/Pin_7（共总线 PA6/PA7 + 页面
默认脚全部不照抄）、pins 类型 = i2c_scl/i2c_sda、**SCL OUT_OD 初始化守卫**
（防批次 2 式缺陷回潮）、无 ml_i2c 调用、**64 位换算守卫**（ms5611 dT 含
long long、无 uint32_t dT 式）+ 0xEE 同址互替 notes；单总线两件（dht11/
ds18b20）独立不变量——DATA=GPIO_B/Pin_3、GPIO_B/Pin_1、pins 类型 gpio_out、
时间轴常量单源 .h（dht11 19/28/27/74、ds18b20 750/15/200/240/2+60/2+12+50
+ 0.0625f + CONVERT_MS 750）、无 delay_uus（dht11）、无 MLX90614 串台
（ds18b20 源码零）；mspm0 条目零改动（比对 stm32 新增不触碰 mspm0 文件）。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")
from contest_generator.clex import strip_comments  # noqa: E402

MOD = Path("library/modules")
wl = json.load(open("src/contest_generator/wordlist.json", encoding="utf-8"))
libmods = set()
for g in wl:
    for s in g.get("solutions", []):
        libmods.update(s.get("lib_modules", []))

# slug -> (pins 期望表, 宏值表)
I2C_EXPECT = {
    "bmp180": {
        "pins": [("BMP180_SCL", "i2c_scl", "PA6"), ("BMP180_SDA", "i2c_sda", "PA7")],
        "macros": [("BMP180_SCL_GPIO", "GPIO_A"), ("BMP180_SCL_PIN", "Pin_6"),
                   ("BMP180_SDA_GPIO", "GPIO_A"), ("BMP180_SDA_PIN", "Pin_7")],
    },
    "ms5611": {
        "pins": [("MS5611_SCL", "i2c_scl", "PA6"), ("MS5611_SDA", "i2c_sda", "PA7")],
        "macros": [("MS5611_SCL_GPIO", "GPIO_A"), ("MS5611_SCL_PIN", "Pin_6"),
                   ("MS5611_SDA_GPIO", "GPIO_A"), ("MS5611_SDA_PIN", "Pin_7")],
    },
}
ONE_WIRE_EXPECT = {
    "dht11": {
        "pins": [("DHT11_DATA", "gpio_out", "PB3")],
        "macros": [("DHT11_GPIO", "GPIO_B"), ("DHT11_PIN", "Pin_3")],
    },
    "ds18b20": {
        "pins": [("DS18B20_DATA", "gpio_out", "PB1")],
        "macros": [("DS18B20_GPIO", "GPIO_B"), ("DS18B20_PIN", "Pin_1")],
    },
}

PIN_CFG = Path("library/masters/stm32/pin_config.h").read_text(
    encoding="utf-8", errors="replace"
)

batch = list(I2C_EXPECT) + list(ONE_WIRE_EXPECT)
print("批次件数:", len(batch))
bad = 0
for slug in batch:
    expect = I2C_EXPECT[slug] if slug in I2C_EXPECT else ONE_WIRE_EXPECT[slug]
    m = json.load(open(MOD / slug / "manifest.json", encoding="utf-8"))
    st = m["platforms"].get("stm32")
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
    # 批次 3 回修口径：I2C 件 init 必须含 SCL OUT_OD 初始化 + 置高
    if slug in I2C_EXPECT:
        scl_macro = f"{slug.upper()}_SCL"
        gpio_macro = f"{scl_macro}_GPIO"
        pin_macro = f"{scl_macro}_PIN"
        if not re.search(
            rf"gpio_init\({gpio_macro}, {pin_macro}, OUT_OD\)", code_only
        ):
            flags.append("SCL OUT_OD 初始化守卫缺失")
        if not re.search(rf"{scl_macro}\(1\)", code_only):
            flags.append("SCL 置高缺失")
        if "0xEE" not in st.get("notes", "") or "互替" not in st.get("notes", ""):
            flags.append("notes缺0xEE互替记录")
        # 64 位换算守卫：ms5611 dT long long + 无 uint32_t dT 式
        if slug == "ms5611":
            if not re.search(r"long long\s+dT", code_only):
                flags.append("dT 缺 long long（64 位换算）")
            if re.search(r"uint32_t\s+dT", code_only):
                flags.append("dT 出现 uint32_t 式（回潮）")
            if "temp / 100.0f" not in code_only:
                flags.append("温度出参缺 TEMP/100.0（0.01℃）")
        if slug == "bmp180":
            if "0xFFFC" in code_only:
                flags.append("出现 & 0xFFFC 掩码（反向守卫）")
            if not re.search(r"b7 < 0x80000000", code_only):
                flags.append("B7 uint32_t 双分支缺失")
    # 单总线件面
    if slug in ONE_WIRE_EXPECT:
        if re.search(r"\bdelay_uus\b", code_only):
            flags.append("delay_uus 页外函数残留")
        if "extern" in code_only:
            flags.append("extern 全局泄漏")
        if slug == "dht11":
            if not re.search(r"delay_ms\(DHT11_START_MS\)", code_only):
                flags.append("缺 19ms 起始常量")
            if not re.search(r"delay_us\(DHT11_CHECK_TIME_US\)", code_only):
                flags.append("缺 28us 位分界常量")
            if "return 1;" not in code_only:
                flags.append("超时返回 1 缺失")
        if slug == "ds18b20":
            if re.search(r"MLX90614", code_only):
                flags.append("MLX90614 串台残留（源码零）")
            if "delay_ms(DS18B20_CONVERT_MS)" not in code_only:
                flags.append("0x44 后 750ms 转换等待缺失")
            if re.search(r"DS18B20_Reset", code_only):
                flags.append("页外声明 DS18B20_Reset 残留")
    if re.search(r"\bI2C_Init\b|\bI2C_Start\b|\bI2C_Stop\b|\bI2C_SendByte\b", code_only):
        flags.append("调用了母版 ml_i2c（本批自实现原语）")
    if slug not in libmods:
        flags.append("wordlist未挂接")
    if "地阔星移植手册" not in st.get("notes", ""):
        flags.append("notes缺手册路径")
    if "未上板" not in st.get("notes", ""):
        flags.append("notes未注明未上板")
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
