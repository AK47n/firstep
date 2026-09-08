# -*- coding: utf-8 -*-
"""wiki-stm32-batch8 六件收官一致性快检（提交前只读扫描，stm32 线版）。

镜像 .scratch/wiki-stm32-batch7/sweep_5_modules.py 的检查面（stm32 侧）+ 本批
特有面：6 件（as32/hc05 UART 件 + nrf24l01/rc522 软 SPI 件 + ir_remote/
ir_remote_tx 红外件）——stm32 条目存在性 / verified（UV4 0/0 后回写）/
hardware_bound / wordlist lib_modules 挂接 / kit+source_url（地阔星 wiki
原页判据）/ 依赖（UART 件=[]、软 SPI/红外件=["delay"]）/ 引脚宏值 /
pins 形状 / 守卫（UART 件：as32 轮询关 RXNEIE + cap 截断、hc05 环形缓冲 +
9600 + hc05_rx_handler；软 SPI 件：位操作 gpio_set/get 宏 + rc522 delay_us(200)
+ nrf 无 SPI1 残留；红外件：ir_remote 20us 拍 + 反码校验 + 无 EXTI/TIM、
ir_remote_tx delay_us(13) 半周期 + MSB 先）/ notes（手册路径 / 未上板 /
互替件同脚 / 各件缺陷记录）/ mspm0 条目零改动（仅存在性）。
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

# slug -> (pins 期望, 宏值表, 依赖期望, notes 必含 needles, 代码守卫, 允许 delay?)
EXPECT = {
    "as32": {
        "pins": [
            ("AS32_UART_TX", "uart_tx", "PB10"),
            ("AS32_UART_RX", "uart_rx", "PB11"),
        ],
        "macros": [
            ("AS32_UART", "UART_3"),
            ("AS32_UART_INST", "USART3"),
            ("AS32_UART_TX_GPIO", "GPIO_B"),
            ("AS32_UART_TX_Pin", "Pin_10"),
            ("AS32_UART_RX_GPIO", "GPIO_B"),
            ("AS32_UART_RX_Pin", "Pin_11"),
        ],
        "deps": [],
        "needles": ["9600", "UART_3", "互替", "轮询", "cap 截断", "未上板"],
        "guard": [
            ("RX_BUF_MAX 300", r"AS32_RX_BUF_MAX 300u"),
            ("关RXNEIE", r"CR1 &= \(uint16_t\)~0x20u"),
            ("SR轮询", r"AS32_UART_INST->SR & 0x20u"),
            ("无rx_handler", r"rx_handler", None),
            ("无%MAX回绕", r"% AS32_RX_BUF_MAX", None),
        ],
        "allow_delay": False,
    },
    "hc05": {
        "pins": [
            ("HC05_TX", "uart_tx", "PA9"),
            ("HC05_RX", "uart_rx", "PA10"),
            ("HC05_STATE", "gpio_in", "PA8"),
            ("HC05_KEY", "gpio_out", "PB4"),
        ],
        "macros": [
            ("HC05_UART", "UART_1"),
            ("HC05_UART_INST", "USART1"),
            ("HC05_UART_TX_GPIO", "GPIO_A"),
            ("HC05_UART_TX_Pin", "Pin_9"),
            ("HC05_UART_RX_GPIO", "GPIO_A"),
            ("HC05_UART_RX_Pin", "Pin_10"),
            ("HC05_STATE_GPIO", "GPIO_A"),
            ("HC05_STATE_PIN", "Pin_8"),
            ("HC05_KEY_GPIO", "GPIO_B"),
            ("HC05_KEY_PIN", "Pin_4"),
        ],
        "deps": [],
        "needles": ["9600", "UART_1", "互替", "hc05_rx_handler", "聚合", "未上板"],
        "guard": [
            ("RX_BUF_SIZE 128", r"HC05_RX_BUF_SIZE   128u"),
            ("9600宏", r"HC05_BAUDRATE      9600"),
            ("环形缓冲", r"% HC05_RX_BUF_SIZE"),
            ("rx_handler定义", r"void hc05_rx_handler\(void\)"),
            ("无USARTx_IRQHandler", r"void\s+USART[123]_IRQHandler", None),
        ],
        "allow_delay": False,
    },
    "nrf24l01": {
        "pins": [
            ("NRF24L01_CLK", "gpio_out", "PB10"),
            ("NRF24L01_MOSI", "gpio_out", "PB11"),
            ("NRF24L01_MISO", "gpio_in", "PB4"),
            ("NRF24L01_CSN", "gpio_out", "PB12"),
            ("NRF24L01_CE", "gpio_out", "PB13"),
            ("NRF24L01_IRQ", "gpio_in", "PB5"),
        ],
        "macros": [
            ("NRF24L01_PORT", "GPIO_B"),
            ("NRF24L01_CLK_PIN", "Pin_10"),
            ("NRF24L01_MOSI_PIN", "Pin_11"),
            ("NRF24L01_MISO_PIN", "Pin_4"),
            ("NRF24L01_CSN_PIN", "Pin_12"),
            ("NRF24L01_CE_PIN", "Pin_13"),
            ("NRF24L01_IRQ_PIN", "Pin_5"),
        ],
        "deps": ["delay"],
        "needles": ["软 SPI", "互替", "零延时", "不注册", "DYNAMIC_PACKET", "未上板"],
        "guard": [
            ("软SPI位操作", r"gpio_set\(NRF24L01_PORT, NRF24L01_CLK_PIN"),
            ("MISO读", r"gpio_get\(NRF24L01_PORT, NRF24L01_MISO_PIN\)"),
            ("无SPI1", r"\bSPI1\b", None),
            ("无EXTI中断", r"EXTI\w*_IRQHandler", None),
            ("无IRQHandler", r"\bIRQHandler\b", None),
        ],
        "allow_delay": True,
    },
    "rc522": {
        "pins": [
            ("RC522_CS", "gpio_out", "PB0"),
            ("RC522_RST", "gpio_out", "PB1"),
            ("RC522_SCK", "gpio_out", "PB6"),
            ("RC522_MOSI", "gpio_out", "PB4"),
            ("RC522_MISO", "gpio_in", "PB5"),
        ],
        "macros": [
            ("RC522_PORT", "GPIO_B"),
            ("RC522_CS_PIN", "Pin_0"),
            ("RC522_RST_PIN", "Pin_1"),
            ("RC522_SCK_PIN", "Pin_6"),
            ("RC522_MOSI_PIN", "Pin_4"),
            ("RC522_MISO_PIN", "Pin_5"),
        ],
        "deps": ["delay"],
        "needles": ["200us", "UID", "4 字节", "CalulateCRC", "未上板"],
        "guard": [
            ("200us半周期", r"delay_us\(200\)"),
            ("UID复制4字节", r"for \(uc = 0; uc < 4; uc\+\+\) \{\n        buf\[uc \+ 8\]"),
            ("无SPI", r"\bSPI\b", None),
            ("无IRQHandler", r"\bIRQHandler\b", None),
        ],
        "allow_delay": True,
    },
    "ir_remote": {
        "pins": [("IR_REMOTE_OUT", "gpio_in", "PA10")],
        "macros": [
            ("IR_REMOTE_PORT", "GPIO_A"),
            ("IR_REMOTE_OUT_PIN", "Pin_10"),
        ],
        "deps": ["delay"],
        "needles": ["20us", "PA10", "PA9", "轮询", "反码", "未上板"],
        "guard": [
            ("20us拍", r"#define IR_TICK_US     20u"),
            ("忙等步进", r"delay_us\(IR_TICK_US\)"),
            ("反码校验", r"\(uint8_t\)~value\[1\] != value\[0\]"),
            ("无EXTI", r"EXTI\w*_IRQHandler", None),
            ("无TIM", r"\bTIM\d\b", None),
        ],
        "allow_delay": True,
    },
    "ir_remote_tx": {
        "pins": [("IR_TX_OUT", "gpio_out", "PA9")],
        "macros": [
            ("IR_TX_PORT", "GPIO_A"),
            ("IR_TX_OUT_PIN", "Pin_9"),
        ],
        "deps": ["delay"],
        "needles": ["delay_us(13)", "PA9", "PA10", "MSB", "UART 指令", "未上板"],
        "guard": [
            ("38kHz宏", r"#define IR_TX_FREQ_HZ 38000u"),
            ("半周期13us", r"#define IR_TX_HALF_PERIOD_US\(\) delay_us\(13\)"),
            ("周期公式", r"us \* IR_TX_FREQ_HZ / 1000000u"),
            ("MSB先", r"#define IR_TX_MSB_FIRST 1"),
            ("无TIM/PWM", r"\bTIM\d\b|\bPWM\b", None),
            ("无USART", r"\bUSART\w*\b", None),
        ],
        "allow_delay": True,
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
    if not expect["allow_delay"] and re.search(r"\bdelay_(us|ms|cycles)\s*\(", code_only):
        flags.append("stm32用delay（UART 件无 delay 依赖）")
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
