# -*- coding: utf-8 -*-
"""wiki-stm32-batch9 七件收官一致性快检（提交前只读扫描，stm32 线版）。

镜像 .scratch/wiki-stm32-batch8/sweep_6_modules.py 的检查面（stm32 侧）+ 本批
特有面：7 件（jq8900/syn6288 软 UART TX 件 + fingerprint/l298n 真实外设件 +
neo_6m/esp01s/ec01g B 类件）——stm32 条目存在性 / verified（UV4 0/0 后回写）/
hardware_bound / wordlist lib_modules 挂接（B 类 3 件）/ kit+source_url（地阔星
wiki 原页判据）/ 依赖（jq8900/syn6288/fingerprint/l298n 按 mspm0 现状、
B 类照实际）/ 引脚宏值 / pins 形状 / 守卫（软 UART 件：无 USART/UART_1 实例
字面量 + 104us；fingerprint：57600 + rx_handler 聚合 + 精确收 12/16；l298n：
2000u + TIM3_CH1/CH2；B 类：rx_handler 聚合 + 缺陷修正）/ notes（手册路径 /
未上板 / 关键记录）/ mspm0 条目零改动（A 类仅存在性、B 类无 mspm0）。
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
ISR_C = Path("library/masters/stm32/isr.c").read_text(encoding="utf-8")
PINWRITER = Path("src/contest_generator/pinwriter.py").read_text(encoding="utf-8")
wl = json.load(open("src/contest_generator/wordlist.json", encoding="utf-8"))
libmods = set()
for g in wl:
    for s in g.get("solutions", []):
        libmods.update(s.get("lib_modules", []))

# slug -> (pins 期望, 宏值表, 依赖期望, notes 必含 needles, 代码守卫, mspm0 期望)
EXPECT = {
    "jq8900": {
        "pins": [("JQ8900_TX", "gpio_out", "PA15")],
        "macros": [("JQ8900_GPIO", "GPIO_A"), ("JQ8900_PIN", "Pin_15")],
        "deps": ["delay"],
        "needles": ["104", "互替", "不占串口实例", "未上板"],
        "guard": [
            ("104us宏", r"JQ8900_UART_BIT_US   104u"),
            ("0xAA帧头", r"0xAAu"),
            ("求校验和", r"\(uint8_t\)\(sum \+ frame\[i\]\)"),
            ("软UART位时序", r"delay_us\(JQ8900_UART_BIT_US\)"),
            ("无UART实例", r"\bUART_[123]\b", None),
            ("无rx_handler", r"rx_handler", None),
        ],
        "mspm0": True,
    },
    "syn6288": {
        "pins": [("SYN6288_TX", "gpio_out", "PC14")],
        "macros": [("SYN6288_GPIO", "GPIO_C"), ("SYN6288_PIN", "Pin_14")],
        "deps": ["delay"],
        "needles": ["104", "200", "互替", "不占串口实例", "未上板"],
        "guard": [
            ("104us宏", r"SYN6288_UART_BIT_US   104u"),
            ("200上限", r"SYN6288_TEXT_MAX      200u"),
            ("0xFD帧头", r"0xFDu"),
            ("异或校验", r"xor_check \^ frame_head\[i\]"),
            ("无UART实例", r"\bUART_[123]\b", None),
            ("无rx_handler", r"rx_handler", None),
        ],
        "mspm0": True,
    },
    "fingerprint": {
        "pins": [
            ("FINGERPRINT_TX", "uart_tx", "PA9"),
            ("FINGERPRINT_RX", "uart_rx", "PA10"),
            ("FINGERPRINT_TOUCH", "gpio_in", "PB5"),
        ],
        "macros": [
            ("FINGERPRINT_UART", "UART_1"),
            ("FINGERPRINT_UART_INST", "USART1"),
            ("FINGERPRINT_UART_TX_GPIO", "GPIO_A"),
            ("FINGERPRINT_UART_TX_Pin", "Pin_9"),
            ("FINGERPRINT_UART_RX_GPIO", "GPIO_A"),
            ("FINGERPRINT_UART_RX_Pin", "Pin_10"),
            ("FINGERPRINT_TOUCH_GPIO", "GPIO_B"),
            ("FINGERPRINT_TOUCH_PIN", "Pin_5"),
        ],
        "deps": ["delay"],
        "needles": ["57600", "UART_1", "互替", "fingerprint_rx_handler", "精确收 12/16",
                    "无上限越界修正", "未上板"],
        "guard": [
            ("57600宏", r"FINGERPRINT_BAUDRATE     57600"),
            ("帧头", r"0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF"),
            ("Len大端", r"\(uint16_t\)_rx\[7\] << 8"),
            ("精确12/16", r"_wait_response\(12u\)"),
            ("无UARTxIRQHandler定义", r"void\s+USART[123]_IRQHandler", None),
        ],
        "mspm0": True,
    },
    "l298n": {
        "pins": [
            ("L298N_IN1", "pwm", "PA6"),
            ("L298N_IN2", "pwm", "PA7"),
        ],
        "macros": [
            ("L298N_IN1_TIM", "TIM_3"),
            ("L298N_IN1_CH", "TIM3_CH1"),
            ("L298N_IN2_TIM", "TIM_3"),
            ("L298N_IN2_CH", "TIM3_CH2"),
        ],
        "deps": [],
        "needles": ["TIM3_CH1", "互替", "物理冲突", "默认×默认不拦", "未上板"],
        "guard": [
            ("2000u宏", r"L298N_PWM_PERIOD 2000u"),
            ("限幅", r"L298N_PWM_PERIOD - 1u"),
            ("方向互切", r"l298n_dir == 1"),
            ("pwm换算", r"pwm_init\(L298N_IN1_TIM, L298N_IN1_CH"),
            ("无EN", r"\bL298N_EN\b", None),
        ],
        "mspm0": True,
    },
    "neo_6m": {
        "pins": [
            ("NEO_6M_TX", "uart_tx", "PA9"),
            ("NEO_6M_RX", "uart_rx", "PA10"),
        ],
        "macros": [
            ("NEO_6M_UART", "UART_1"),
            ("NEO_6M_UART_INST", "USART1"),
            ("NEO_6M_UART_TX_GPIO", "GPIO_A"),
            ("NEO_6M_UART_TX_Pin", "Pin_9"),
            ("NEO_6M_UART_RX_GPIO", "GPIO_A"),
            ("NEO_6M_UART_RX_Pin", "Pin_10"),
        ],
        "deps": [],
        "needles": ["B 类：无 mspm0 条目", "9600", "UART_1", "互替", "neo_6m_rx_handler",
                    "255", "未上板"],
        "guard": [
            ("256缓冲", r"NEO_6M_RX_BUF_SIZE      256u"),
            ("截断保护", r"NEO_6M_RX_BUF_SIZE - 1u"),
            ("帧头判定", r"_rx\[3\] == 'R' && _rx\[4\] == 'M'"),
            ("GPRMC换算", r"min / 60\.0f"),
            ("无[255]越界", r"\[255\]", None),
        ],
        "mspm0": False,
    },
    "esp01s": {
        "pins": [
            ("ESP01S_TX", "uart_tx", "PA9"),
            ("ESP01S_RX", "uart_rx", "PA10"),
        ],
        "macros": [
            ("ESP01S_UART", "UART_1"),
            ("ESP01S_UART_INST", "USART1"),
            ("ESP01S_UART_TX_GPIO", "GPIO_A"),
            ("ESP01S_UART_TX_Pin", "Pin_9"),
            ("ESP01S_UART_RX_GPIO", "GPIO_A"),
            ("ESP01S_UART_RX_Pin", "Pin_10"),
        ],
        "deps": [],
        "needles": ["B 类：无 mspm0 条目", "115200", "UART_1", "互替", "esp01s_rx_handler",
                    "回绕", "未上板"],
        "guard": [
            ("200缓冲", r"ESP01S_RX_BUF_SIZE     200u"),
            ("按长度终结", r"_rx\[_rx_len\] = 0;"),
            ("有界扫IPD", r"i \+ 5u <= _rx_len"),
            ("OK匹配", r'_buf_contains\("OK"\)'),
            ("无%200回绕", r"%\s*ESP01S_RX_BUF_SIZE", None),
        ],
        "mspm0": False,
    },
    "ec01g": {
        "pins": [
            ("EC01G_TX", "uart_tx", "PB10"),
            ("EC01G_RX", "uart_rx", "PB11"),
        ],
        "macros": [
            ("EC01G_UART", "UART_3"),
            ("EC01G_UART_INST", "USART3"),
            ("EC01G_UART_TX_GPIO", "GPIO_B"),
            ("EC01G_UART_TX_Pin", "Pin_10"),
            ("EC01G_UART_RX_GPIO", "GPIO_B"),
            ("EC01G_UART_RX_Pin", "Pin_11"),
        ],
        "deps": [],
        "needles": ["B 类：无 mspm0 条目", "9600", "UART_3", "互替", "ec01g_rx_handler",
                    "无 GPS 代码", "未上板"],
        "guard": [
            ("256缓冲", r"EC01G_RX_BUF_SIZE     256u"),
            ("空指针保护", r"cmd == NULL"),
            ("有界扫", r"i \+ \(uint16_t\)nlen <= _rx_len"),
            ("OK匹配", r'_buf_contains\("OK"\)'),
            ("无%2096回绕", r"%\s*2096", None),
        ],
        "mspm0": False,
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
        print(f"{slug:14s} " + "; ".join(flags))
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
    for pat in [r"\bprintf\b", r"\bGPIO_Init\b", r"\bRCC_\w+\s*\(", r"\bdelay_1ms\b",
                r"stm32f10x\.h", r"stm32f4xx\.h", r"\bboard_init\b"]:
        if re.search(pat, code_only):
            flags.append(f"代码残留 {pat}")
    if "stdio.h" in code_only:
        flags.append("stdio 残余 include")
    uart_slugs = ("fingerprint", "neo_6m", "esp01s", "ec01g")
    if slug in uart_slugs and f"{slug}_rx_handler" not in str(st.get("notes", "")):
        flags.append("notes缺rx_handler聚合记录")
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
    for needle in expect["needles"]:
        if needle not in notes:
            flags.append(f"notes缺 {needle}")
    if expect["mspm0"]:
        msp = m.get("platforms", {}).get("mspm0")
        if msp is None:
            flags.append("缺mspm0条目")
        else:
            for f in msp.get("files", []):
                if not (MOD / slug / f).is_file():
                    flags.append(f"mspm0缺文件{f}")
    else:
        if "mspm0" in m.get("platforms", {}):
            flags.append("B 类不应有 mspm0 条目")
        if slug not in libmods:
            flags.append("wordlist未挂接")
    line = f"{slug:14s} " + ("OK" if not flags else "; ".join(flags))
    print(line)
    if flags:
        bad += 1
# 聚合断言（isr.c/pinwriter 全局登记——防漏登记）
for stem, handler in (
    ("FINGERPRINT", "fingerprint_rx_handler"),
    ("NEO_6M", "neo_6m_rx_handler"),
    ("ESP01S", "esp01s_rx_handler"),
    ("EC01G", "ec01g_rx_handler"),
):
    if f'"__weak void {handler}(void) {{}}"' not in ISR_C.replace('__weak void', '"__weak void'):
        # 简化存在性检查（__weak 行 + 聚合宏 + pinwriter 登记另验）
        pass
    if handler not in ISR_C:
        print(f"isr.c 缺 {handler}")
        bad += 1
    if f'"{stem}_UART", "{handler}"' not in PINWRITER:
        print(f"pinwriter 缺 {stem}_UART 登记")
        bad += 1
print("异常件数:", bad)
sys.exit(0 if bad == 0 else 1)
