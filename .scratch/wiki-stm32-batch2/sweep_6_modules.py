# -*- coding: utf-8 -*-
"""wiki-stm32-batch2 六件收官一致性快检（提交前只读扫描，stm32 线版）。

镜像 .scratch/wiki-stm32-batch1/sweep_6_modules.py 的检查面（stm32 侧）：
stm32 条目存在性 / verified / hardware_bound / wordlist lib_modules 挂接 /
kit+source_url（wiki 原页判据）/ 依赖正检（用 delay_us/ms 必须依赖 delay）；
批次 2 新增面：软 I2C 总线件共总线不变量——每件 4 宏都在 pin_config.h 且
SCL=GPIO_A/Pin_6、SDA=GPIO_A/Pin_7（六件共总线 PA6/PA7）、pins 类型 =
i2c_scl/i2c_sda、页面默认脚（PB8/PB9）全部不照抄、无 ml_i2c 调用；
mspm0 条目零改动（保持原状）。
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

batch_slugs = ["aht10", "bh1750", "sht20", "sht30", "at24c02", "ags10"]
PIN_CFG = Path("library/masters/stm32/pin_config.h").read_text(
    encoding="utf-8", errors="replace"
)

print("批次件数:", len(batch_slugs))
bad = 0
for slug in batch_slugs:
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
    code_only = ""
    for f in st.get("files", []):
        p = MOD / slug / f
        if not p.is_file():
            flags.append(f"缺文件{f}")
            continue
        joined += p.read_text(encoding="utf-8", errors="replace")
    code_only = strip_comments(joined, keep_preprocessor=True)
    if re.search(r"\bdelay_(us|ms|cycles)\s*\(", code_only) and "delay" not in deps:
        flags.append("stm32用delay未依赖")
    # 软 I2C 总线件共总线不变量：4 宏 + 值 = PA6/PA7 + 类型/默认脚 + 零 ml_i2c
    for suffix, want in (("SCL_GPIO", "GPIO_A"), ("SCL_PIN", "Pin_6"),
                         ("SDA_GPIO", "GPIO_A"), ("SDA_PIN", "Pin_7")):
        macro = f"{slug.upper()}_{suffix}"
        if not re.search(rf"#define\s+{macro}\s+{want}", PIN_CFG):
            flags.append(f"pin_config缺{macro}={want}")
    pins = st.get("pins", [])
    got = {p["id"]: p for p in pins}
    for role, want_type, want_pin in (
        (f"{slug.upper()}_SCL", "i2c_scl", "PA6"),
        (f"{slug.upper()}_SDA", "i2c_sda", "PA7"),
    ):
        p = got.get(role)
        if p is None:
            flags.append(f"缺pins {role}")
        elif p.get("type") != want_type or p.get("default") != want_pin:
            flags.append(f"{role} 类型/默认异常")
    if re.search(r"\bI2C_Init\b|\bI2C_Start\b|\bI2C_Stop\b|\bI2C_SendByte\b", code_only):
        flags.append("调用了母版 ml_i2c（本批自实现原语）")
    if slug not in libmods:
        flags.append("wordlist未挂接")
    if "地阔星移植手册" not in st.get("notes", ""):
        flags.append("notes缺手册路径")
    if "未上板" not in st.get("notes", ""):
        flags.append("notes未注明未上板")
    line = f"{slug:18s} " + ("OK" if not flags else "; ".join(flags))
    print(line)
    if flags:
        bad += 1
print("异常件数:", bad)
