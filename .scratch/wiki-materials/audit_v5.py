# -*- coding: utf-8 -*-
"""审计 v5（严格版）：70 篇手册 — 页内是否完整自洽。

对每篇：
1. 代码块提取 + 花括号配平（未配平 = 疑似截断）；
2. 全页符号解析：
   - defs   = 有函数体的定义
   - protos = 无函数体的声明（...); 结尾）
   - macros = #define 名称（含带参宏）
   - calls  = 代码（去注释后）中所有 `name(` 调用
   - missing = calls - defs - protos - macros - ALLOW - 类型/关键字
3. 输出每页：块数、未配平块、missing 符号清单。
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
PROTO_RE = re.compile(
    r"^\s*(?:extern\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*;",
    re.M,
)
MACRO_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)", re.M)
CALL_RE = re.compile(r"(?<![\w.#>])[A-Za-z_]\w*\s*\(")

KEYWORDS = {
    "if", "for", "while", "switch", "return", "else", "do", "sizeof", "case",
    "int", "char", "void", "unsigned", "signed", "const", "volatile", "static",
    "extern", "register", "struct", "union", "enum", "typedef", "short", "long",
    "float", "double", "uint8_t", "uint16_t", "uint32_t", "int8_t", "int16_t",
    "int32_t", "u8", "u16", "u32", "u64", "s8", "s16", "s32", "bool", "true",
    "false", "sizeof", "main", "NULL",
}
# 标准库 / board.h 常规 / SysConfig 生成宏函数 / 库内已知模块延时
ALLOW = {
    # 标准 C
    "printf", "sprintf", "snprintf", "memset", "memcpy", "memmove", "strlen",
    "strcpy", "strncpy", "strcmp", "strncmp", "strcat", "strchr", "strstr",
    "atoi", "atol", "atof", "malloc", "free", "abs", "sqrt", "pow", "sin",
    "cos", "tan", "atan2", "floor", "ceil", "fabs", "fmod", "putchar", "puts",
    # 板级 / SysConfig 生成
    "board_init", "delay_ms", "delay_us", "Delay_ms", "Delay_us", "Delay",
    "SysTick_Delay", "delay_1ms", "delay(1)",
    # DL 驱动宏（SysConfig 生成，宏可能是函数式）
    "DL_GPIO_setPins", "DL_GPIO_clearPins", "DL_GPIO_togglePins",
    "DL_GPIO_readPins", "DL_GPIO_initDigitalOutput", "DL_GPIO_initDigitalInput",
    "DL_GPIO_setPinsMask", "DL_GPIO_clearPinsMask", "DL_GPIO_writePins",
    "DL_UART_transmitData", "DL_UART_receiveData", "DL_UART_enableInterrupt",
    "DL_UART_disableInterrupt", "DL_UART_clearInterruptStatus",
    "DL_UART_getPendingInterrupt", "DL_UART_init", "DL_UART_setClockConfig",
    "DL_ADC12_startConversion", "DL_ADC12_getMemResult", "DL_ADC12_enableConversions",
    "DL_ADC12_initMem", "DL_ADC12_setSampleTime",
    "DL_TimerA_startCounter", "DL_TimerG_startCounter", "DL_TimerA_enableInterrupt",
    "DL_TimerA_setCaptureCompareValue", "DL_TimerG_setCaptureCompareValue",
    "DL_TimerA_initPWMMode", "DL_TimerG_initPeriodMode",
    "DL_Interrupt_registerInterrupt", "DL_Interrupt_enable", "DL_Interrupt_setPriority",
    "DL_Timer_getTimerCount", "DL_Common_updatePowerState",
    "DL_I2C_enableController", "DL_I2C_fillControllerTXFIFO",
    "DL_I2C_getControllerStatus", "DL_I2C_getTXFIFOStatus",
    "DL_I2C_startControllerTransfer", "DL_I2C_clearControllerStatus",
    "DL_I2C_enableInterrupt", "DL_I2C_initController",
    "DL_SPI_transmitData8", "DL_SPI_receiveData8", "DL_SPI_init",
    "DL_SPI_setClockConfig", "DL_SPI_enable", "DL_SPI_disable",
    "DL_SPI_transmitData", "DL_SPI_receiveData",
    "DL_GPIO_enableClock", "DL_GPIO_reset", "DL_GPIO_setPortLevel",
    "DL_SYSCFG_enableIO", "DL_SYSCFG_setIOMUX", "DL_SYSCFG_IOMUX",
    "DL_SYSCFG_IOMUX_INDEX", "DL_SYSCFG_unlockIOMUX",
    "DL_SYSCFG_initIOMUX", "DL_SYSCFG_setPinIomux",
    "DL_Common_resetDevice", "DL_Common_enablePowerState",
    "DL_Common_disablePowerState", "DL_Common_syncToPowerSavingMode",
    "DL_Common_wakeUp", "DL_Common_setDeepSleepMode",
    "DL_DMA_startTransfer", "DL_DMA_setChannelControl",
    "DL_CRC32_init", "DL_CRC32_compute", "DL_CRC32_getResult",
    "DL_GPIO_setLowerPins", "DL_GPIO_setUpperPins",
    "DL_GPIO_clearLowerPins", "DL_GPIO_clearUpperPins",
    "DL_GPIO_emptyOutput", "DL_GPIO_emptyInput",
    "DL_GPIO_initAnalogFunction", "DL_GPIO_initPeripheralOutputFunction",
    "DL_GPIO_initPeripheralInputFunction",
    "GPIOB", "GPIOA", "GPIOB_OUT", "GPIOA_OUT", "GPIOB_IN",
    # TI 驱动库常见
    "SySTemClockInit", "SysTick_Init", "SystemClock_Config",
    # 头文件提供
    "u8", "u16", "u32",
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
    return code


def main() -> None:
    files = sorted(f for f in BATCH.glob("*.md") if f.name not in ("模块索引.md", "网盘索引.md"))
    problems: dict[str, list[str]] = {}
    clean: list[str] = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        blks = blocks(text)
        note = []
        # 1) 花括号配平
        for bi, b in enumerate(blks):
            o, c = b.count("{"), b.count("}")
            if o != c:
                # 允许 main 示范代码块自带 while(1) 平衡 == 还是必须配平；若整体差说明截断
                note.append(f"块{bi} 括号不配平 {{={o} }}={c}")
        code = "\n".join(blks)
        code_nc = strip_comments(code)
        defs = {m.group(1) for m in FUNC_DEF_RE.finditer(code_nc)}
        protos = {m.group(1) for m in PROTO_RE.finditer(code_nc)}
        macros = {m.group(1) for m in MACRO_RE.finditer(code)}
        calls = {m.group(0).split("(", 1)[0].strip() for m in CALL_RE.finditer(code_nc)}
        missing = calls - defs - protos - macros - KEYWORDS - ALLOW
        # 去掉自包含的 SysConfig 宏风格（GPIO 端口/引脚宏已被宏集合覆盖；IGPIO 宏在 macros 中）
        # 但仍需人工看 missing（宏未记录的写法如 DL_GPIO_readPins 已在 ALLOW）
        if missing:
            note.append("missing: " + ", ".join(sorted(missing)[:20]))
        if note:
            problems[f.stem] = note
        else:
            clean.append(f.stem)

    def cat(slug: str) -> str:
        for c in ("control", "rf", "screen", "sensor"):
            if (BATCH / f"{c}--{slug}.md").exists():
                return c
        return "?"

    print(f"== 严格自洽（{len(clean)} 篇）：所有调用符号页内可解 ==")
    for slug in sorted(clean):
        print("  " + slug)
    print()
    print(f"== 有疑点（{len(problems)} 篇）==")
    for slug, note in sorted(problems.items()):
        print(f"- {slug}")
        for n in note:
            print(f"    {n}")


if __name__ == "__main__":
    main()
