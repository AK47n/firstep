# -*- coding: utf-8 -*-
"""审计 v6（可解释版）：70 篇手册 — 页内自包含判定。

块分类：
- header 块：含 #ifndef 守卫 / #include <自身头> / 大量 #define（无函数体）→ 提取声明（protos）与宏；
- source 块：含函数定义 / main → 提取定义（defs）与调用（calls）；
- python 块：含 `def ` 或 `import ` / `from `（OpenMV 页）→ 按 Python 处理（defs + 内置白名单）。

missing = calls - defs - header_protos - macros - ALLOW(标准库/driverlib/SysConfig/Python内置)。

输出：每页 missing（按原因分组标注），并给出「真实缺页外符号」的最终清单。
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
    r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)
PY_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", re.M)
# 声明：行尾 `);` 且行首无 `#`；从 header 块提取
PROTO_RE = re.compile(
    r"^\s*(?:extern\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*;\s*$",
    re.M,
)
MACRO_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)", re.M)
CALL_RE = re.compile(r"(?<![\w.#>])[A-Za-z_]\w*\s*\(", re.M)
PY_CALL_RE = re.compile(r"(?<![\w.#>])[A-Za-z_]\w*\s*\(", re.M)

KEYWORDS = {
    "if", "for", "while", "switch", "return", "else", "do", "sizeof", "case",
    "int", "char", "void", "unsigned", "signed", "const", "volatile", "static",
    "extern", "register", "struct", "union", "enum", "typedef", "short", "long",
    "float", "double", "uint8_t", "uint16_t", "uint32_t", "int8_t", "int16_t",
    "int32_t", "u8", "u16", "u32", "u64", "s8", "s16", "s32", "bool", "true",
    "false", "main", "NULL", "volatile", "inline", "restrict",
}

DRIVERLIB = {
    # SysConfig 模板生成包装（empty.syscfg 模板：UART_Main / UART_1 等实例包装）
    "DL_UART_Main_receiveData", "DL_UART_Main_transmitData", "DL_UART_Main_init",
    "DL_UART_Main_enableInterrupt", "DL_UART_Main_config", "DL_UART_Main_setClockConfig",
    "UART_0_INST_IRQHandler", "UART_1_INST_IRQHandler", "UART_2_INST_IRQHandler",
    "UART_3_INST_IRQHandler", "UART_4_INST_IRQHandler", "UART_5_INST_IRQHandler",
    "ADC12_0_INST_IRQHandler", "TIMER_0_INST_IRQHandler", "TIMER_1_INST_IRQHandler",
    "TIMG0_INST_IRQHandler", "TIMG6_INST_IRQHandler", "TIMG7_INST_IRQHandler",
    "TIMG8_INST_IRQHandler", "TIMG12_INST_IRQHandler",
    # driverlib 函数
    "DL_UART_isBusy", "DL_UART_receiveData", "DL_UART_transmitData",
    "DL_UART_getPendingInterrupt", "DL_UART_clearInterruptStatus",
    "DL_UART_enableInterrupt", "DL_UART_disableInterrupt",
    "DL_UART_setClockConfig", "DL_UART_init", "DL_UART_sendDataBlocking",
    "DL_UART_receiveDataBlocking", "DL_UART_reset", "DL_UART_restore",
    "DL_ADC12_getPendingInterrupt", "DL_ADC12_clearInterruptStatus",
    "DL_ADC12_startConversion", "DL_ADC12_getMemResult",
    "DL_ADC12_setSampleTime", "DL_ADC12_initMem", "DL_ADC12_init",
    "DL_ADC12_enableConversions", "DL_ADC12_setClockConfig",
    "DL_Interrupt_getPendingGroup", "DL_Interrupt_enable", "DL_Interrupt_disable",
    "DL_Interrupt_clearPendingGroup", "DL_Interrupt_setPriority",
    "DL_Interrupt_registerInterrupt", "DL_Interrupt_unregisterInterrupt",
    "DL_Interrupt_getPending", "DL_Interrupt_getIState", "DL_Interrupt_clearIState",
    "DL_SPI_isBusy", "DL_SPI_transmitData8", "DL_SPI_receiveData8",
    "DL_SPI_transmitData", "DL_SPI_receiveData", "DL_SPI_setClockConfig",
    "DL_SPI_init", "DL_SPI_enable", "DL_SPI_disable", "DL_SPI_reset",
    "DL_SPI_fillTXFIFO", "DL_SPI_getRXFIFOStatus",
    "DL_TimerG_getPendingInterrupt", "DL_TimerG_clearInterruptStatus",
    "DL_TimerG_getTimerCount", "DL_TimerG_startCounter", "DL_TimerG_stopCounter",
    "DL_TimerG_enableInterrupt", "DL_TimerG_disableInterrupt",
    "DL_TimerG_setCaptureCompareValue", "DL_TimerG_initPeriodMode",
    "DL_TimerG_initPWMMode", "DL_TimerG_setClockConfig", "DL_TimerG_restartCounter",
    "DL_TimerA_startCounter", "DL_TimerA_stopCounter", "DL_TimerA_getTimerCount",
    "DL_TimerA_getPendingInterrupt", "DL_TimerA_clearInterruptStatus",
    "DL_TimerA_enableInterrupt", "DL_TimerA_disableInterrupt",
    "DL_TimerA_setCaptureCompareValue",
    "DL_GPIO_setPins", "DL_GPIO_clearPins", "DL_GPIO_togglePins",
    "DL_GPIO_readPins", "DL_GPIO_initDigitalOutput", "DL_GPIO_initDigitalInput",
    "DL_GPIO_setPinsMask", "DL_GPIO_clearPinsMask", "DL_GPIO_writePins",
    "DL_GPIO_enableClock", "DL_GPIO_reset", "DL_GPIO_setLowerPins",
    "DL_GPIO_setUpperPins", "DL_GPIO_clearLowerPins", "DL_GPIO_clearUpperPins",
    "DL_GPIO_initAnalogFunction", "DL_GPIO_initPeripheralOutputFunction",
    "DL_GPIO_initPeripheralInputFunction", "DL_GPIO_setPortLevel",
    "DL_SYSCFG_enableIO", "DL_SYSCFG_setIOMUX", "DL_SYSCFG_unlockIOMUX",
    "DL_SYSCFG_initIOMUX", "DL_SYSCFG_IOMUX", "DL_SYSCFG_IOMUX_INDEX",
    "DL_SYSCFG_setPinIomux", "DL_SYSCFG_resetIOMUX",
    "DL_Common_updatePowerState", "DL_Common_resetDevice",
    "DL_Common_enablePowerState", "DL_Common_disablePowerState",
    "DL_Common_syncToPowerSavingMode", "DL_Common_wakeUp",
    "DL_Common_setDeepSleepMode", "DL_Common_setLowPowerMode",
    "DL_I2C_enableController", "DL_I2C_fillControllerTXFIFO",
    "DL_I2C_getControllerStatus", "DL_I2C_getTXFIFOStatus",
    "DL_I2C_startControllerTransfer", "DL_I2C_clearControllerStatus",
    "DL_I2C_enableInterrupt", "DL_I2C_initController", "DL_I2C_setClockConfig",
    "DL_I2C_transmitControllerData", "DL_I2C_receiveControllerData",
    "DL_I2C_fillControllerRXFIFO", "DL_I2C_getControllerPendingInterrupt",
    "DL_I2C_clearControllerPendingInterrupt", "DL_I2C_enableDMA",
    "DL_DMA_startTransfer", "DL_DMA_setChannelControl",
    "DL_CRC32_init", "DL_CRC32_compute", "DL_CRC32_getResult", "DL_CRC32_getStatus",
    "DL_MATH_sqrt", "DL_MATH_rsqrt",
    "DL_Timer_getTimerCount",
    # 板级
    "board_init", "delay_ms", "delay_us", "Delay_ms", "Delay_us", "Delay",
    "SysTick_Delay", "delay_1ms", "delay_1us",
    # 标准 C
    "printf", "sprintf", "snprintf", "memset", "memcpy", "memmove", "strlen",
    "strcpy", "strncpy", "strcmp", "strncmp", "strcat", "strchr", "strstr",
    "atoi", "atol", "atof", "malloc", "free", "abs", "sqrt", "pow", "floor",
    "ceil", "fabs", "fmod", "putchar", "puts", "uint8_t", "uint16_t",
    # 工程模板 / SysConfig 头内
    "INST_CLK_FREQ", "CPUCLK_FREQ", "HZ", "MHz", "kHz", "GPIO_BASE",
    # Python 内置 / 库（OpenMV 页）
    "print", "len", "range", "int", "float", "str", "bytes", "bytearray",
    "list", "dict", "tuple", "set", "sum", "min", "max", "abs", "sort",
    "enumerate", "zip", "map", "filter", "type", "isinstance", "repr", "open",
    "read", "write", "close", "flush", "iter", "next", "ord", "chr", "hex",
    "bin", "round", "memoryview", "format", "input",
    # OpenMV/Pyboard
    "sensor", "image", "pyb", "lcd", "rgb", "led", "uart", "clock", "timer",
    "pin", "dac", "adc", "servo", "switch", "delay", "millis", "micros",
    "shutdown", "enable", "disable", "set_pixformat", "set_framebuffer",
    "skip_frames", "rgb565", "GRAYSCALE", "find_blobs", "find_rects",
    "find_lines", "find_circles", "find_blobs", "draw_rectangle", "draw_string",
    "draw_cross", "draw_circle", "draw_line", "copy", "flip", "invert",
    "set_vflip", "set_hmirror", "set_auto_gain", "set_auto_whitebal",
    "find_max", "blob", "rect", "line", "circle", "zero", "VIRTUAL", "UART",
    "LED", "MICROPY", "SENSOR", "IMAGE", "BITS_PER_PIXEL", "SELF", "INIT",
    "TIMER", "PIN", "ADC", "DAC", "SPI", "I2C", "CAN",
    "from", "import", "class", "self", "with", "as", "in", "is", "and",
    "or", "not", "None", "True", "False", "try", "except", "finally",
    "raise", "pass", "break", "continue", "global", "lambda", "yield",
    "assert", "del", "elif", "else", "C", "P", "W", "H", "V", "B",
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
    code = re.sub(r"/\*[\s\S]*?\*/", "", code)
    code = re.sub(r"//[^\n]*", "", code)
    # Python 行内 # 注释（仅对 # 后无 include/define 的行）
    code = re.sub(r"^\s*#\s*(?!include|define|ifndef|ifdef|endif|elif|\w)", "", code)
    return code


def main() -> None:
    files = sorted(f for f in BATCH.glob("*.md") if f.name not in ("模块索引.md", "网盘索引.md"))
    rows = []
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
            if b.count("{") != b.count("}"):
                unbalanced.append(bi)
            content = strip_comments(b)
            has_py = bool(re.search(r"^\s*(def |import |from |class )", b, re.M)) or bool(
                re.search(r"^\s*[A-Za-z_]\w*\s*=\s*(?:sensor|image|pyb|clock)\.", b, re.M)
            )
            has_c_def = bool(FUNC_DEF_RE.search(content))
            has_main = bool(re.search(r"\b(?:void|int)\s+main\s*\(", content))
            is_header = bool(re.search(r"#ifndef\s+_?[A-Za-z_\d]+", b)) and not has_c_def
            if has_py and not has_c_def and not has_main:
                for m in PY_DEF_RE.finditer(b):
                    py_defs.add(m.group(1))
                for m in re.finditer(r"(?<![\w.#>])[A-Za-z_]\w*\s*\(", b):
                    py_calls.add(m.group(0).split("(", 1)[0].strip())
            elif is_header:
                for m in PROTO_RE.finditer(content):
                    protos.add(m.group(1))
                for m in MACRO_RE.finditer(b):
                    macros.add(m.group(1))
            else:
                for m in FUNC_DEF_RE.finditer(content):
                    defs.add(m.group(1))
                for m in MACRO_RE.finditer(b):
                    macros.add(m.group(1))
                if is_header and len([l for l in b.splitlines() if l.strip()]) > 0:
                    for m in PROTO_RE.finditer(content):
                        protos.add(m.group(1))
                for m in re.finditer(r"(?<![\w.#>])[A-Za-z_]\w*\s*\(", content):
                    calls.add(m.group(0).split("(", 1)[0].strip())
        known = KEYWORDS | DRIVERLIB | defs | protos | macros | py_defs
        missing = (calls - known) | (py_calls - known)
        rows.append((f.stem, sorted(missing), unbalanced))

    def cat(slug: str) -> str:
        for c in ("control", "rf", "screen", "sensor"):
            if (BATCH / f"{c}--{slug}.md").exists():
                return c
        return "?"

    print("== 逐页 missing（不在本页定义/声明/宏、也不在 driverlib/Python 白名单的符号）==")
    for slug, missing, unbalanced in rows:
        if missing or unbalanced:
            print(f"- {slug}  [括号未配平块: {unbalanced if unbalanced else '-'}]")
            print(f"    missing: {', '.join(missing)}")
    print()
    real_need = [r for r in rows if r[1]]
    print(f"有页外符号的页：{len(real_need)} / 70")


if __name__ == "__main__":
    main()
