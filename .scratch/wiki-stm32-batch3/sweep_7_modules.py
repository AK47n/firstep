# -*- coding: utf-8 -*-
"""wiki-stm32-batch3 七件收官一致性快检（提交前只读扫描，stm32 线版）。

镜像 .scratch/wiki-stm32-batch2/sweep_6_modules.py 的检查面（stm32 侧）：
stm32 条目存在性 / verified / hardware_bound / wordlist lib_modules 挂接 /
kit+source_url（wiki 原页判据）/ 依赖正检（用 delay_us/ms 必须依赖 delay）；
批次 3 新增面：软 I2C 器件库五件共总线不变量——每件 4 宏都在 pin_config.h 且
SCL=GPIO_A/Pin_6、SDA=GPIO_A/Pin_7（五件共总线 PA6/PA7 + 页面默认脚全部
不照抄）、pins 类型 = i2c_scl/i2c_sda、**SCL OUT_OD 初始化守卫**（防批次 2
式缺陷回潮）、无 ml_i2c 调用；hx711 GPIO 双线件独立不变量——SCK=GPIO_B/
Pin_5、DT=GPIO_B/Pin_0、pins 类型 gpio_out/gpio_in；mspm0 条目零改动
（保持原状——仅比对 stm32 新增不触碰 mspm0 文件）。
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
    "ads1115": {
        "pins": [("ADS1115_SCL", "i2c_scl", "PA6"), ("ADS1115_SDA", "i2c_sda", "PA7")],
        "macros": [("ADS1115_SCL_GPIO", "GPIO_A"), ("ADS1115_SCL_PIN", "Pin_6"),
                   ("ADS1115_SDA_GPIO", "GPIO_A"), ("ADS1115_SDA_PIN", "Pin_7")],
    },
    "tcs34725": {
        "pins": [("TCS34725_SCL", "i2c_scl", "PA6"), ("TCS34725_SDA", "i2c_sda", "PA7")],
        "macros": [("TCS34725_SCL_GPIO", "GPIO_A"), ("TCS34725_SCL_PIN", "Pin_6"),
                   ("TCS34725_SDA_GPIO", "GPIO_A"), ("TCS34725_SDA_PIN", "Pin_7")],
    },
    "mlx90614": {
        "pins": [("MLX90614_SCL", "i2c_scl", "PA6"), ("MLX90614_SDA", "i2c_sda", "PA7")],
        "macros": [("MLX90614_SCL_GPIO", "GPIO_A"), ("MLX90614_SCL_PIN", "Pin_6"),
                   ("MLX90614_SDA_GPIO", "GPIO_A"), ("MLX90614_SDA_PIN", "Pin_7")],
    },
    "sgp30": {
        "pins": [("SGP30_SCL", "i2c_scl", "PA6"), ("SGP30_SDA", "i2c_sda", "PA7")],
        "macros": [("SGP30_SCL_GPIO", "GPIO_A"), ("SGP30_SCL_PIN", "Pin_6"),
                   ("SGP30_SDA_GPIO", "GPIO_A"), ("SGP30_SDA_PIN", "Pin_7")],
    },
    "pca9685": {
        "pins": [("PCA9685_SCL", "i2c_scl", "PA6"), ("PCA9685_SDA", "i2c_sda", "PA7")],
        "macros": [("PCA9685_SCL_GPIO", "GPIO_A"), ("PCA9685_SCL_PIN", "Pin_6"),
                   ("PCA9685_SDA_GPIO", "GPIO_A"), ("PCA9685_SDA_PIN", "Pin_7")],
    },
}
HX711_EXPECT = {
    "pins": [("HX711_SCK", "gpio_out", "PB5"), ("HX711_DT", "gpio_in", "PB0")],
    "macros": [("HX711_SCK_GPIO", "GPIO_B"), ("HX711_SCK_PIN", "Pin_5"),
               ("HX711_DT_GPIO", "GPIO_B"), ("HX711_DT_PIN", "Pin_0")],
}

PIN_CFG = Path("library/masters/stm32/pin_config.h").read_text(
    encoding="utf-8", errors="replace"
)

batch = list(I2C_EXPECT) + ["hx711"]
print("批次件数:", len(batch))
bad = 0
for slug in batch:
    expect = I2C_EXPECT.get(slug, HX711_EXPECT)
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
