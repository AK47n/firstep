"""硬件检测（常用模块 bring-up 自检）的域层：检测程序渲染。

**这是本仓库第一个"渲染出的程序不靠 AI"的生成形态**（spec「检测程序怎么来」：
检测程序 = 确定性渲染 + 库内配方数据——ADR 待写，见工单 09）：框架（LED 心跳、
输出通道自报、逐件小节、结尾汇总）永远由本模块确定性渲染，「每一件怎么测」
来自库内配方数据（后续工单），没有配方的模块走通用降级。全程零 LLM。

模块边界（工单 module-hwcheck/01）：

* 纯函数，字符串进 / 字符串出——不读盘、不写盘、不碰 LLM，故可在内存里直测；
* 只负责"这一段 C 代码长什么样"，落盘走既有生成内核（不新开第二条写盘路径）；
* 平台差异（头文件名 / 初始化函数 / 打印宏）是**渲染期的事实**，集中在
  `_PLATFORM_HEADERS` 与各渲染函数的分支里，不让它散到前端。

为什么要按通道分形态渲染，而不是"全渲染 + 运行时判断"：没有输出通道的构建
必须**一个打印调用都不产生**——渲染出来却跑不到，学生会以为"程序报了结果、
只是我没看到"，而真相是这里根本没测（spec 判据「不假装测过」）。所以通道形态
是渲染输入，不是运行期开关。
"""

from __future__ import annotations

from dataclasses import dataclass

from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32

__all__ = [
    "OUTPUT_HINT_NONE",
    "OUTPUT_HINT_OLED",
    "OUTPUT_HINT_SERIAL",
    "OUTPUT_HINT_SERIAL_OLED",
    "HwCheckConfig",
    "HwCheckError",
    "render_main_c",
    "render_output_hint",
]


class HwCheckError(Exception):
    """硬件检测的域错误（登记 errors.py → 400 中文）。

    平台词表外 / 通道开关不是布尔值这类"请求形状非法"在此抛出，路由只取参
    转调（对照 SkeletonError 先例，工单 route-orchestration-homing/01）。
    """


# 心跳周期（毫秒）：主循环里 LED 翻转的间隔。够慢到肉眼看得见、够快到
# 「我改了线、想立刻知道板子还在跑」。单源常量——渲染文本里印同一数值。
HEARTBEAT_MS = 200

_HEARTBEAT_MACRO = "HWCHECK_HEARTBEAT_MS"

# 各平台的"进门头"与通道头（库内真实文件名，不猜）：
#   entry  = 母版聚合头（stm32 headfile.h 拉齐 ml_* 库）/ SysConfig 生成头（mspm0）
#   serial = debug_uart 模块的平台条目头文件名
#   oled   = oled 模块的平台条目头文件名
#   delay  = delay 模块的平台条目头文件名（两平台同名）
_PLATFORM_HEADERS: dict[str, dict[str, str]] = {
    PLATFORM_STM32: {
        "entry": "headfile.h",
        "serial": "debug_uart.h",
        "oled": "oled.h",
        "delay": "delay.h",
        "led": "led_instances.h",
    },
    PLATFORM_MSPM0: {
        "entry": "ti_msp_dl_config.h",
        "serial": "debug_uart_mspm0.h",
        "oled": "oled.h",
        "delay": "delay.h",
        "led": "led.h",
    },
}

# 各平台启动时的既有初始化动作（生成工程里"别的东西已经做了这件事"）：
# stm32 启动文件调 SystemInit，这里显式再调一次确保时钟就绪（母版模板 main.c
# 同款）；mspm0 的外设初始化就是 SYSCFG_DL_init()。
_PLATFORM_BOOT_LINES: dict[str, str] = {
    PLATFORM_STM32: "    SystemInit();  /* 时钟初始化（启动文件已调用，这里显式确保就绪） */",
    PLATFORM_MSPM0: "    SYSCFG_DL_init();  /* SysConfig 生成的外设初始化 */",
}

_LED_CHANNEL = "LED_RED"  # 两平台通用的通道宏（mspm0 单实例默认 1 通道、stm32 三通道）

# 输出通道形态的「应看到什么」（检测页明示；后端给文案，前端只渲染）
OUTPUT_HINT_SERIAL_OLED = (
    "输出通道：调试串口（115200）+ OLED 屏。程序跑起来后串口会打印每一段自检结果，"
    "OLED 上也能看到同样的分段内容。"
)
OUTPUT_HINT_SERIAL = "输出通道：只有调试串口（115200）。请打开串口助手看分段打印的结果。"
OUTPUT_HINT_OLED = "输出通道：只有 OLED 屏。结果分屏显示在屏幕上，不接串口也能看。"
OUTPUT_HINT_NONE = (
    "没有输出通道（既没选调试串口也没选 OLED），只能看板载 LED 闪："
    "灯在闪 = 程序在跑。这一趟不打印任何检测结果。"
)


@dataclass(frozen=True)
class HwCheckConfig:
    """检测程序形态：平台 + 两个输出通道开关。

    检测程序**不依赖生成流程任何状态**（spec：不需要赛题、不需要已选模块集），
    所以这里的输入只有"给谁做、往哪儿报"。
    """

    platform: str
    debug_uart: bool
    oled: bool

    def __post_init__(self) -> None:
        if self.platform not in KNOWN_PLATFORMS:
            known = ", ".join(sorted(KNOWN_PLATFORMS))
            raise HwCheckError(
                f"未知平台 {self.platform!r}，已注册的平台：{known}"
            )
        for name, value in (("debug_uart", self.debug_uart), ("oled", self.oled)):
            if not isinstance(value, bool):
                raise HwCheckError(
                    f"通道开关 {name} 必须是布尔值（有 / 无），收到 {value!r}"
                )

    @property
    def has_output_channel(self) -> bool:
        return self.debug_uart or self.oled


def render_output_hint(config: HwCheckConfig) -> str:
    """「应看到什么」的输出通道部分（纯函数，页面直接展示）。"""
    if config.debug_uart and config.oled:
        return OUTPUT_HINT_SERIAL_OLED
    if config.debug_uart:
        return OUTPUT_HINT_SERIAL
    if config.oled:
        return OUTPUT_HINT_OLED
    return OUTPUT_HINT_NONE


def render_main_c(config: HwCheckConfig) -> str:
    """渲染检测程序 main.c（零器件最小自检：心跳 + 通道自报 + 汇总）。

    产物形态（确定性，逐字节可断言）：

    * 头部注释说明"这是硬件检测程序、不是赛题工程"；
    * 按形态 include：进门头恒在，通道 / 延时 / LED 头只在相关时才进；
    * 有输出通道时定义 `hwcheck_report(line)`（把一行字写到所有在场通道），
      没有通道时**不定义也不调用**（防"定义了却没人调"的死代码）；
    * `main()`：平台初始化 → 通道初始化 → 上电先报一遍 → while(1) 闪灯 +
      （有串口时）`debug_cmd_poll()` 让模块自带的命令通道继续活着。

    平台词表外抛 HwCheckError（路由转 400 中文）；未知平台在这里就出不去，
    所以下面的分支是穷尽的。
    """
    headers = _PLATFORM_HEADERS[config.platform]
    lines: list[str] = [
        "/**",
        " * @file main.c",
        " * @brief 硬件检测程序（最小自检）—— 确定性渲染，非 AI 生成",
        " *",
        *_header_brief(config),
        " *",
        " * 检测没过是正常结果：要么接线不对，要么库内驱动有问题。",
        " */",
        f'#include "{headers["entry"]}"',
    ]
    if config.debug_uart:
        lines.append(f'#include "{headers["serial"]}"')
    if config.oled:
        lines.append(f'#include "{headers["oled"]}"')
    lines.append(f'#include "{headers["delay"]}"  /* 心跳节拍 */')
    lines.append(f'#include "{headers["led"]}"  /* 通道宏 {_LED_CHANNEL} */')

    lines.append("")
    lines.append(f"/* 心跳周期（毫秒）：改这里改闪灯快慢 */")
    lines.append(f"#define {_HEARTBEAT_MACRO} {HEARTBEAT_MS}")
    lines.append("")

    if config.has_output_channel:
        lines.extend(_report_function(config))
        lines.append("")

    lines.append("int main(void)")
    lines.append("{")
    lines.append(_PLATFORM_BOOT_LINES[config.platform])
    if config.debug_uart:
        lines.append("    debug_uart_init();")
    if config.oled:
        lines.append("    OLED_Init();")
        lines.append("    OLED_Clear();")
    lines.append(f"    led_init({_LED_CHANNEL});")
    lines.append("")
    if config.has_output_channel:
        lines.append('    hwcheck_report("上电：板子活着，检测程序开始跑");')
    else:
        lines.append("    /* 没有输出通道：只闪灯，不打印（看到灯闪 = 程序在跑） */")
    lines.append("")
    lines.append("    while (1)")
    lines.append("    {")
    if config.debug_uart:
        lines.append("        debug_cmd_poll();  /* 串口命令通道：复测不用重烧 */")
    lines.append(f"        led_toggle({_LED_CHANNEL});")
    lines.append(f"        delay_ms({_HEARTBEAT_MACRO});")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _header_brief(config: HwCheckConfig) -> list[str]:
    """文件头"这一趟做什么"的说明行——**按通道形态说实话**。

    有输出通道：两件事（闪灯 + 把自检结果写到通道）。
    没有输出通道：**只有闪灯一件事**——文件头若照抄"每一段结果写到输出通道"，
    而全文一个打印调用都没有（见 render_main_c 的分支），那份自述就是撒谎
    （与 OUTPUT_HINT_NONE 的"这一趟不打印任何检测结果"直接矛盾）。
    """
    lines = [" * 这一趟用来确认「板子活着 + 烧录链路通」："]
    if config.has_output_channel:
        lines.append(" *   1. 板载 LED 按固定周期闪烁（心跳，肉眼可见）；")
        lines.append(" *   2. 每一段自检结果写到在场的输出通道（串口 / OLED）。")
    else:
        lines.append(" *   1. 板载 LED 按固定周期闪烁（心跳，肉眼可见）。")
        lines.append(" *   本形态没有输出通道，因此**不打印任何检测结果**——")
        lines.append(" *   代码里也没有打印调用（不假装测过）。")
    return lines


def _report_function(config: HwCheckConfig) -> list[str]:
    """自检报告函数：把一行字写到所有在场的输出通道。

    骨架期只有两个通道（串口 / OLED）；后续工单往里加"逐件小节"时继续走
    这一个出口——输出通道的差异只在这里出现，检测逻辑不必知道自己往哪儿写。
    """
    lines = [
        "/** 自检结果出口：一行字写到所有在场的输出通道。 */",
        "static void hwcheck_report(const char *line)",
        "{",
    ]
    if config.debug_uart:
        lines.append('    DEBUG_PRINTF("%s\\r\\n", line);')
    if config.oled:
        lines.append("    /* 本屏 16×8 字符网格、可见 4 行：固定写第 0 行，保证每次都看得见 */")
        lines.append("    oled_show_text(0, 0, line);")
        lines.append("    oled_refresh();")
    lines.append("}")
    return lines
