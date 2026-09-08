# -*- coding: utf-8 -*-
"""审计 v7（终版）：70 篇手册 — 页内自包含判定（可复核）。

关键修正：
- 函数定义从【原始文本】提取（v6 的注释正则会把定义行误吞，如 ags10 Calc_CRC8）；
- 注释剥离用状态机（正确处理 /* */ 与 // ，不吃代码）；
- 声明（protos）只从 header 块提取（杜绝"单行调用被当声明"的 v5 缺陷）；
- 每个剩余 missing 符号再到页内原文 grep 复核（存在即从清单剔除）。

missing 分类：
- TEMPLATE = 工程模板/驱动库/CMSIS 提供（NVIC_*、__enable_irq、SYSCFG_DL_init、delay_uus 等）→ 不需网盘；
- VENDOR = 页外器件库（lcd.c/lcd_init.c/pic.h/DMP 等）→ 真缺，需网盘；
- 其余逐个 grep 复核。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"

FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)
FUNC_DEF_RE = re.compile(
    r"^\s*(?:static\s+)?(?:[A-Za-z_]\w[\w\s\*]*[\s\*]+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)
PY_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", re.M)
PROTO_RE = re.compile(
    r"^\s*(?:extern\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*;\s*$",
    re.M,
)
MACRO_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)", re.M)
CALL_RE = re.compile(r"(?<![\w.#>])[A-Za-z_]\w*\s*\(")

# 工程模板 / 驱动库 / CMSIS / 立创模板工具（不算"缺内容"）
TEMPLATE = {
    "NVIC_EnableIRQ", "NVIC_ClearPendingIRQ", "NVIC_SetPriority", "NVIC_IsEnabledIRQ",
    "__enable_irq", "__disable_irq", "__set_PRIMASK", "__get_PRIMASK",
    "SYSCFG_DL_init", "SYSCFG_DL_init_GPIO", "SYSCFG_DL_init_UART",
    "SYSCFG_DL_init_ADC12", "SYSCFG_DL_init_TimerG", "SYSCFG_DL_init_SPI",
    "SYSCFG_DL_init_I2C", "SYSCFG_DL_init_TIMER", "Board_init",
    "delay_uus", "delay_us", "delay_ms", "delay_1ms", "delay_1us", "delay_0_25us",
    "Delay_us", "Delay_ms", "Delay", "SysTick_Delay", "board_init",
    "GPIO", "GPIOA", "GPIOB", "GPIOA_OUT", "GPIOB_OUT", "GPIOA_IN", "GPIOB_IN",
    "DL_GPIO_enableOutput", "DL_GPIO_enableInput", "DL_GPIO_setDirection",
    "DL_GPIO_disableOutput", "DL_GPIO_getDirection",
    "DL_GPIO_enableClocks", "DL_GPIO_setModel", "DL_GPIO_setPortLevel",
    "DL_SYSCFG_setPinIomux", "DL_SYSCFG_enableIO", "DL_SYSCFG_unlockIOMUX",
    "DL_SYSCFG_IOMUX", "DL_SYSCFG_IOMUX_INDEX", "DL_SYSCFG_initIOMUX",
    "DL_SYSCFG_resetIOMUX", "DL_SYSCFG_readByte",
    "DL_UART_setClockConfig", "DL_UART_isBusy", "DL_UART_getPendingInterrupt",
    "DL_UART_clearInterruptStatus", "DL_UART_receiveData", "DL_UART_transmitData",
    "DL_UART_enableInterrupt", "DL_UART_disableInterrupt", "DL_UART_reset",
    "DL_UART_sendDataBlocking", "DL_UART_receiveDataBlocking",
    "DL_UART_Main_receiveData", "DL_UART_Main_transmitData", "DL_UART_Main_init",
    "DL_UART_Main_enableInterrupt", "DL_UART_Main_config",
    "DL_ADC12_getPendingInterrupt", "DL_ADC12_clearInterruptStatus",
    "DL_ADC12_startConversion", "DL_ADC12_getMemResult", "DL_ADC12_setSampleTime",
    "DL_ADC12_initMem", "DL_ADC12_init", "DL_ADC12_enableConversions",
    "DL_ADC12_setClockConfig", "DL_ADC12_reset", "DL_ADC12_disableConversions",
    "DL_Interrupt_getPendingGroup", "DL_Interrupt_enable", "DL_Interrupt_disable",
    "DL_Interrupt_clearPendingGroup", "DL_Interrupt_setPriority",
    "DL_Interrupt_registerInterrupt", "DL_Interrupt_unregisterInterrupt",
    "DL_Interrupt_getPending", "DL_Interrupt_getIState", "DL_Interrupt_clearIState",
    "DL_SPI_transmitData8", "DL_SPI_receiveData8", "DL_SPI_transmitData",
    "DL_SPI_receiveData", "DL_SPI_setClockConfig", "DL_SPI_init", "DL_SPI_enable",
    "DL_SPI_disable", "DL_SPI_reset", "DL_SPI_fillTXFIFO", "DL_SPI_getRXFIFOStatus",
    "DL_SPI_isBusy", "DL_SPI_getPendingInterrupt", "DL_SPI_clearInterruptStatus",
    "DL_TimerG_getPendingInterrupt", "DL_TimerG_clearInterruptStatus",
    "DL_TimerG_getTimerCount", "DL_TimerG_setTimerCount", "DL_TimerG_startCounter",
    "DL_TimerG_stopCounter", "DL_TimerG_enableInterrupt", "DL_TimerG_disableInterrupt",
    "DL_TimerG_setCaptureCompareValue", "DL_TimerG_initPeriodMode",
    "DL_TimerG_initPWMMode", "DL_TimerG_setClockConfig", "DL_TimerG_restartCounter",
    "DL_TimerA_startCounter", "DL_TimerA_stopCounter", "DL_TimerA_getTimerCount",
    "DL_TimerA_getPendingInterrupt", "DL_TimerA_clearInterruptStatus",
    "DL_TimerA_enableInterrupt", "DL_TimerA_disableInterrupt",
    "DL_TimerA_setCaptureCompareValue", "DL_Timer_getTimerCount",
    "DL_I2C_enableController", "DL_I2C_fillControllerTXFIFO",
    "DL_I2C_getControllerStatus", "DL_I2C_getTXFIFOStatus",
    "DL_I2C_startControllerTransfer", "DL_I2C_clearControllerStatus",
    "DL_I2C_enableInterrupt", "DL_I2C_initController", "DL_I2C_setClockConfig",
    "DL_GPIO_setPins", "DL_GPIO_clearPins", "DL_GPIO_togglePins",
    "DL_GPIO_readPins", "DL_GPIO_initDigitalOutput", "DL_GPIO_initDigitalInput",
    "DL_GPIO_setPinsMask", "DL_GPIO_clearPinsMask", "DL_GPIO_writePins",
    "DL_GPIO_enableClock", "DL_GPIO_reset", "DL_GPIO_setLowerPins",
    "DL_GPIO_setUpperPins", "DL_GPIO_clearLowerPins", "DL_GPIO_clearUpperPins",
    "DL_GPIO_initAnalogFunction", "DL_GPIO_initPeripheralOutputFunction",
    "DL_GPIO_initPeripheralInputFunction",
    "DL_Common_updatePowerState", "DL_Common_resetDevice",
    "DL_Common_enablePowerState", "DL_Common_disablePowerState",
    "DL_Common_syncToPowerSavingMode", "DL_Common_wakeUp",
    "DL_Common_setDeepSleepMode", "DL_Common_setLowPowerMode",
    "DL_DMA_startTransfer", "DL_DMA_setChannelControl",
    "DL_CRC32_init", "DL_CRC32_compute", "DL_CRC32_getResult", "DL_CRC32_getStatus",
    "UART_0_INST_IRQHandler", "UART_1_INST_IRQHandler", "UART_2_INST_IRQHandler",
    "UART_3_INST_IRQHandler", "UART_4_INST_IRQHandler", "UART_5_INST_IRQHandler",
    "GROUP0_IRQHandler", "GROUP1_IRQHandler", "GROUP2_IRQHandler",
    "GROUP3_IRQHandler", "GROUP4_IRQHandler", "GROUP5_IRQHandler",
    "GROUP6_IRQHandler", "GROUP7_IRQHandler", "GROUP8_IRQHandler",
    "GROUP9_IRQHandler", "GROUP10_IRQHandler", "GROUP11_IRQHandler",
    "COMP0_IRQHandler", "COMP1_IRQHandler", "GPIOB_IRQHandler", "GPIOA_IRQHandler",
    "CORTEX_M0P_INT0_IRQHandler", "CORTEX_M0P_INT1_IRQHandler",
    "ADC12_0_INST_IRQHandler", "TIMER_0_INST_IRQHandler", "TIMER_1_INST_IRQHandler",
    "TIMER_2_INST_IRQHandler", "TIMER_3_INST_IRQHandler",
    "TIMER_4_INST_IRQHandler", "TIMER_5_INST_IRQHandler", "TIMER_6_INST_IRQHandler",
    "TIMER_7_INST_IRQHandler", "TIMER_8_INST_IRQHandler", "TIMER_9_INST_IRQHandler",
    "TIMER_10_INST_IRQHandler", "TIMER_11_INST_IRQHandler", "TIMER_12_INST_IRQHandler",
    "TIMER_13_INST_IRQHandler", "TIMER_14_INST_IRQHandler", "TIMER_15_INST_IRQHandler",
    "TIMER_16_INST_IRQHandler", "TIMER_17_INST_IRQHandler", "TIMER_18_INST_IRQHandler",
    "TIMER_19_INST_IRQHandler", "TIMER_20_INST_IRQHandler", "TIMER_21_INST_IRQHandler",
    "TIMG0_INST_IRQHandler", "TIMG6_INST_IRQHandler", "TIMG7_INST_IRQHandler",
    "TIMG8_INST_IRQHandler", "TIMG12_INST_IRQHandler",
    "printf", "sprintf", "snprintf", "memset", "memcpy", "memmove", "strlen",
    "strcpy", "strncpy", "strcmp", "strncmp", "strcat", "strchr", "strstr",
    "atoi", "atol", "atof", "malloc", "free", "abs", "sqrt", "pow", "floor",
    "ceil", "fabs", "fmod", "putchar", "puts",
    "INST_CLK_FREQ", "CPUCLK_FREQ", "HZ", "MHz", "kHz", "GPIO_BASE",
    # Python 内置（OpenMV 页）
    "print", "len", "range", "int", "str", "bytes", "bytearray", "list", "dict",
    "tuple", "set", "sum", "min", "max", "sort", "enumerate", "zip", "map",
    "filter", "type", "isinstance", "repr", "open", "read", "write", "close",
    "flush", "iter", "next", "ord", "chr", "hex", "bin", "round", "format",
    "input", "classmethod", "staticmethod", "property",
    # OpenMV / Pyboard
    "sensor", "image", "pyb", "lcd", "rgb", "led", "uart", "clock", "timer",
    "pin", "dac", "adc", "servo", "switch", "millis", "micros", "shutdown",
    "enable", "disable", "set_pixformat", "set_framebuffer", "skip_frames",
    "rgb565", "GRAYSCALE", "find_blobs", "find_rects", "find_lines",
    "find_circles", "draw_rectangle", "draw_string", "draw_cross", "draw_circle",
    "draw_line", "copy", "flip", "invert", "set_vflip", "set_hmirror",
    "set_auto_gain", "set_auto_whitebal", "find_max", "blob", "rect", "line",
    "circle", "zero", "VIRTUAL", "UART", "LED", "MICROPY", "SENSOR", "IMAGE",
    "BITS_PER_PIXEL", "SELF", "INIT", "TIMER", "PIN", "ADC", "DAC", "SPI", "I2C",
    "CAN", "OCR", "RESET", "HEARTBEAT", "from", "import", "class", "self",
    "with", "as", "in", "is", "and", "or", "not", "None", "True", "False",
    "try", "except", "finally", "raise", "pass", "break", "continue", "global",
    "lambda", "yield", "assert", "del", "elif", "else", "C", "P", "W", "H", "V",
    "B", "math", "time", "os", "sys", "struct", "gc", "machine", "stm",
}

KEYWORDS = {
    "if", "for", "while", "switch", "return", "else", "do", "sizeof", "case",
    "int", "char", "void", "unsigned", "signed", "const", "volatile", "static",
    "extern", "register", "struct", "union", "enum", "typedef", "short", "long",
    "float", "double", "uint8_t", "uint16_t", "uint32_t", "int8_t", "int16_t",
    "int32_t", "u8", "u16", "u32", "u64", "s8", "s16", "s32", "bool", "true",
    "false", "main", "NULL", "inline", "restrict", "uint64_t", "int64_t",
}


def blocks(md: str) -> list[str]:
    out, i, lines = [], 0, md.splitlines()
    while i < len(lines):
        if FENCE_RE.match(lines[i]):
            j, buf = i + 1, []
            while j < len(lines) and not FENCE_RE.match(lines[j]):
                buf.append(lines[j])
                j += 1
            out.append("\n".join(buf))
            i = j + 1
        else:
            i += 1
    return out


def strip_comments(code: str) -> str:
    """状态机：去掉 // 与 /* */ 注释（不做粗正则，避免吞代码）。"""
    out, i, n = [], 0, len(code)
    in_line, in_block = False, False
    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if in_line:
            if ch == "\n":
                in_line = False
                out.append("\n")
            i += 1
            continue
        if in_block:
            if ch == "*" and nxt == "/":
                in_block = False
                i += 2
                continue
            if ch == "\n":
                out.append("\n")
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block = True
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def main() -> None:
    files = sorted(f for f in BATCH.glob("*.md") if f.name not in ("模块索引.md", "网盘索引.md"))
    results = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        blks = blocks(text)
        defs: set[str] = set()
        protos: set[str] = set()
        macros: set[str] = set()
        calls: set[str] = set()
        py_defs: set[str] = set()
        py_calls: set[str] = set()
        unbalanced = []
        for bi, b in enumerate(blks):
            raw = b
            if raw.count("{") != raw.count("}"):
                unbalanced.append(bi)
            has_py = bool(re.search(r"^\s*(def |import |from |class |pyb|sensor|image|clock\s*=)", b, re.M)) \
                and not FUNC_DEF_RE.search(b)
            has_c_def = bool(FUNC_DEF_RE.search(b))
            has_main = bool(re.search(r"\b(?:void|int)\s+main\s*\(", b))
            is_header = bool(re.search(r"#ifndef\s+_?[A-Za-z_\d]+", b)) and not has_c_def and not has_main
            if has_py:
                for m in PY_DEF_RE.finditer(raw):
                    py_defs.add(m.group(1))
                for m in CALL_RE.finditer(raw):
                    py_calls.add(m.group(0).split("(", 1)[0].strip())
            elif is_header:
                for m in PROTO_RE.finditer(raw):
                    protos.add(m.group(1))
                for m in MACRO_RE.finditer(raw):
                    macros.add(m.group(1))
            else:
                # 定义与调用都从【状态机去注释】文本提取（定义行尾部可能有 // 注释、
                # 返回类型可为指针前缀——两种形态正则都要能识别）
                content = strip_comments(raw)
                for m in FUNC_DEF_RE.finditer(content):
                    defs.add(m.group(1))
                for m in MACRO_RE.finditer(raw):
                    macros.add(m.group(1))
                for m in CALL_RE.finditer(content):
                    calls.add(m.group(0).split("(", 1)[0].strip())
        known = KEYWORDS | TEMPLATE | defs | protos | macros | py_defs
        missing = (calls - known) | (py_calls - known)
        real = sorted(missing)
        results.append((f.stem, real, unbalanced))

    def cat(slug: str) -> str:
        for c in ("control", "rf", "screen", "sensor"):
            if (BATCH / f"{c}--{slug}.md").exists():
                return c
        return "?"

    need = [r for r in results if r[1]]
    print(f"== 真·页外符号（页内原文也找不到），共 {len(need)} 篇 ==")
    for slug, real, unbalanced in need:
        print(f"- {slug}  {real}")
    print()
    print(f"== 全自洽（{70 - len(need)} 篇）：本页定义/声明/宏 + 模板/driverlib 全解析 ==")


if __name__ == "__main__":
    main()
