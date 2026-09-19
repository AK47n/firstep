"""硬件检测（常用模块 bring-up 自检）的域层：检测程序渲染 + 上板清单。

**这是本仓库第一个"渲染出的程序不靠 AI"的生成形态**（spec「检测程序怎么来」：
检测程序 = 确定性渲染 + 库内配方数据——ADR 待写，见工单 09）：框架（LED 心跳、
输出通道自报、逐件小节、结尾汇总）永远由本模块确定性渲染，「每一件怎么测」
来自库内配方数据（后续工单），没有配方的模块走通用降级。全程零 LLM。

模块边界（工单 module-hwcheck/01）：

* 纯函数，字符串进 / 字符串出——不读盘、不写盘、不碰 LLM，故可在内存里直测；
* 只负责"这一段 C 代码长什么样"，落盘走既有生成内核（不新开第二条写盘路径）；
* 平台差异（头文件名 / 初始化函数 / 打印宏）是**渲染期的事实**，集中在
  `_PLATFORM_HEADERS` 与各渲染函数的分支里，不让它散到前端。

"落点与回读"（目录命名 / 扫最近 / 把一个已有目录读回配置）是盘侧的事，归
`hwcheck_store.py`——本模块不碰盘，这个边界是刻意的（工单 02）。

为什么要按通道分形态渲染，而不是"全渲染 + 运行时判断"：没有输出通道的构建
必须**一个打印调用都不产生**——渲染出来却跑不到，学生会以为"程序报了结果、
只是我没看到"，而真相是这里根本没测（spec 判据「不假装测过」）。所以通道形态
是渲染输入，不是运行期开关。

工单 02 补的两件事：

1. **include 按平台的真实工程认**。stm32 侧 `oled.h` / `delay.h` **不存在**
   （delay / led / oled 由母版聚合头 `headfile.h` 拉齐 `ml_*.h`），工单 01
   照 mspm0 的名字渲染 stm32，喂真生成内核直接 UnresolvedIncludeError。
2. **mspm0 的 SysConfig 初始化只能是注释占位**：`SYSCFG_DL_init` 不在任何
   头文件里（`ti_msp_dl_config.h` 构建期生成），生成内核的「main.c 不许调
   不存在的接口」门禁会判它未定义。这是既有生成链的已知限制，本单如实
   输出注释占位 + 说明（文件头、清单第一条都写明"上板前取消注释"），
   不假装测过、也不偷改生成门禁（另开单）。
"""

from __future__ import annotations

from dataclasses import dataclass

from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32

__all__ = [
    "OUTPUT_HINT_NONE",
    "OUTPUT_HINT_OLED",
    "OUTPUT_HINT_SERIAL",
    "OUTPUT_HINT_SERIAL_OLED",
    "ChecklistItem",
    "HwCheckConfig",
    "HwCheckError",
    "HWCHECK_CHANNELS",
    "HWCHECK_FRAMEWORK_MODULES",
    "hwcheck_modules",
    "render_checklist",
    "render_main_c",
    "render_output_hint",
]


class HwCheckError(Exception):
    """硬件检测的域错误（登记 errors.py → 400 中文）。

    平台词表外 / 通道开关不是布尔值这类"请求形状非法"在此抛出，路由只取参
    转调（对照 SkeletonError 先例，工单 route-orchestration-homing/01）。
    盘侧的同类错误（父目录不存在 / 不是检测工程）也复用本类——同一个功能的
    用户可见失败面只走一条错误通道。
    """


# 心跳周期（毫秒）：主循环里 LED 翻转的间隔。够慢到肉眼看得见、够快到
# 「我改了线、想立刻知道板子还在跑」。单源常量——渲染文本里印同一数值。
HEARTBEAT_MS = 200

_HEARTBEAT_MACRO = "HWCHECK_HEARTBEAT_MS"

# 各平台的"进门头"与通道头（**库内真实文件名，按平台认，不猜**）：
#   entry  = 母版聚合头（stm32 headfile.h 拉齐 ml_* 库）/ SysConfig 生成头（mspm0）
#   serial = debug_uart 模块在**该平台**的头文件名
#   oled   = oled 模块在该平台的头；None = 该平台由进门头提供，不另 include
#   delay  = delay 模块在该平台的头；None = 同上（stm32 的 delay_ms 在 ml_delay.h）
#   led    = LED 通道宏头（两平台都随 led 模块/母版进工程）
#
# ⚠ stm32 的 oled / delay 是 None（工单 02 更正）：stm32 工程里没有 oled.h /
# delay.h，写它们会被生成内核的 include 解析门当场拒（工单 01 的平台盲守卫
# 放过了这个错，真机口径一来就现形）。
_PLATFORM_HEADERS: dict[str, dict[str, str | None]] = {
    PLATFORM_STM32: {
        "entry": "headfile.h",
        "serial": "debug_uart.h",
        "oled": None,
        "delay": None,
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
# 同款，声明在母版 sys/system_stm32f10x.h，生成门禁认母版头）；mspm0 的外设
# 初始化是 SYSCFG_DL_init()——但它由 SysConfig 构建期生成的头声明，生成门禁
# 不认（见模块头注释），故**注释占位**输出。
_PLATFORM_BOOT_LINES: dict[str, str] = {
    PLATFORM_STM32: "    SystemInit();  /* 时钟初始化（启动文件已调用，这里显式确保就绪） */",
    PLATFORM_MSPM0: (
        "    /* 本平台的 SysConfig 外设初始化：暂时注释——生成链还没有把这一行\n"
        "     * 注入出来（见文件头说明）。上板前先取消注释，否则串口 / LED 都不会\n"
        "     * 初始化（灯不闪不是板子坏）。 */\n"
        "    /* SYSCFG_DL_init(); */"
    ),
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

# 框架自带的模块（心跳）：检测程序恒调 led_init / led_toggle / delay_ms，
# 所以这两个模块**必须真的进工程**（生成门禁要求"调的函数在所选模块头里"）。
HWCHECK_FRAMEWORK_MODULES: tuple[str, ...] = ("led", "delay")

# 通道 → 该通道要带进工程的模块（顺序 = 进工程顺序，依赖展开由生成内核做）。
# 通道**词表**（= 前端勾选框的键）单源从这里投影：`HWCHECK_CHANNELS` 由前端
# `fx/hwcheck.js` 的 `HWCHECK_CHANNEL_KEYS` 镜像（跨语言守卫用例钉住，
# 照 library.MODULE_KIND 的镜像先例）——两边各写一份会让"勾了没反应"成为静默失效。
_CHANNEL_MODULES: tuple[tuple[str, str], ...] = (
    ("debug_uart", "debug_uart"),
    ("oled", "oled"),
)

# 通道词表（顺序 = 页面勾选框顺序）
HWCHECK_CHANNELS: tuple[str, ...] = tuple(channel for channel, _ in _CHANNEL_MODULES)



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


def hwcheck_modules(config: HwCheckConfig) -> tuple[str, ...]:
    """这个形态的检测工程要带进哪些模块（判据单源，前端不参与推导）。

    渲染出的 main.c 会调 `led_init` / `led_toggle` / `delay_ms` /
    `debug_uart_init` / `DEBUG_PRINTF` / `OLED_*`——生成内核的「调用的函数必须
    在所选模块头里」与「include 必须可解析」两道门禁要求这些模块**真的被选中**。
    故检测工程不是"零模块"：框架自带 `led` + `delay`（心跳），两个输出通道各
    带自己的模块（oled 的 delay 依赖由生成内核自动展开）。

    "一个器件都不选也能生成"指的是不选**器件**（本单还没有器件可选）。
    """
    modules = list(HWCHECK_FRAMEWORK_MODULES)
    for channel, slug in _CHANNEL_MODULES:
        if getattr(config, channel):
            modules.append(slug)
    return tuple(modules)


@dataclass(frozen=True)
class ChecklistItem:
    """上板清单的一条：应看到什么（expect）+ 不对先查哪里（check）。

    两栏而不是一句混写：学生拿手机照着比的时候，"正常是什么样"和"不对时看哪儿"
    是两个动作（spec 用户故事 12）。`id` 是人可读的稳定键——前端勾选态按它
    存本地备忘，刷新后靠它回显；渲染文案改了也不会串位。
    """

    id: str
    expect: str
    check: str

    def to_dict(self) -> dict[str, str]:
        """JSON 载荷形态（`/api/hwcheck/generate` 与 `/api/hwcheck/project` 共用）。

        投影只写这一处：字段名是前后端契约，两个端点各写一遍就是双源——改一处
        忘另一处，前端静默读不到清单项。
        """
        return {"id": self.id, "expect": self.expect, "check": self.check}


# 平台差异项：mspm0 侧 SysConfig 初始化还不在生成链里（既有生成链限制，
# 见模块头注释）——上板前必须手动取消注释，否则外设不初始化。
_MSPM0_BOOT_ITEM = ChecklistItem(
    id="syscfg-init",
    expect=(
        "mspm0 专属：打开工程根 main.c，确认 `SYSCFG_DL_init();` 那一行**已取消注释**"
        "（本平台的生成链暂时没有把这一行注入出来）"
    ),
    check=(
        "没取消注释 = 串口 / LED 都没初始化，灯不会闪、串口不会有字——"
        "这不是板子坏，把 `/* SYSCFG_DL_init(); */` 的注释去掉再编译烧录一次"
    ),
)


def render_checklist(config: HwCheckConfig) -> tuple[ChecklistItem, ...]:
    """上板确认清单（3-6 条，随平台与通道形态变化）。

    为什么要清单：本功能要回答的是"我不知道怎么看它正常不正常"——只给一段
    代码和一个"检测通过"的断言，学生仍然只能猜。清单把**可肉眼核对的现象**
    与**最常见的三个原因**摆出来，勾选态本地留着，下次进来还知道自己走到哪。
    """
    items: list[ChecklistItem] = [
        ChecklistItem(
            id="flash",
            expect="烧录工具最后报成功（Keil 的 Programming Done / Verify OK，或 DSLite 的 Success）",
            check=(
                "① 探针 / 下载线有没有插好、板子有没有单独供电；"
                "② 下载口被别的程序占用（串口助手、另一个 IDE）会写不进去；"
                "③ 目标芯片型号要与板子一致（stm32 选 STM32F103C8，mspm0 选 MSPM0G3507）"
            ),
        ),
        ChecklistItem(
            id="heartbeat",
            expect=f"板载 LED 按约 {HEARTBEAT_MS} 毫秒的节奏规律闪烁（一亮一灭，不是常亮也不是全灭）",
            check=(
                "① 先按一次复位，看是不是根本没跑起来；"
                "② stm32 板载三色 LED 在 PC13/PC14/PC15（本程序用红灯通道 LED_RED），"
                "地猛星用户 LED 是 PA15；"
                "③ 灯常亮或常灭不动 = 程序卡住了（多半卡在外设初始化）"
            ),
        ),
    ]
    if config.debug_uart:
        items.append(
            ChecklistItem(
                id="serial",
                expect="串口助手（115200 / 8 / 无校验 / 1 停止位）出现一行「上电：板子活着，检测程序开始跑」",
                check=(
                    "① 串口号选错（拔插一次，看哪个口消失）；"
                    "② TX/RX 要交叉接、GND 必须与板子共地；"
                    "③ 波特率不对就是乱码——固定 115200；"
                    "④ 板子没复位 / 没烧进去"
                ),
            )
        )
    if config.oled:
        items.append(
            ChecklistItem(
                id="oled",
                expect="OLED 屏上出现同一行「上电：板子活着…」（屏是亮的，不是全黑也不是全白）",
                check=(
                    "① SCL/SDA 接反或没接（本工程的默认脚见工程 README 的接线表）；"
                    "② 屏供电 3.3V；③ 0.96 寸 SSD1306 与 1.3 寸屏初始化序列不同，换屏要改驱动"
                ),
            )
        )
    if not config.has_output_channel:
        items.append(
            ChecklistItem(
                id="no-channel",
                expect="**本形态只有灯闪，一个字符都不会打印**（这是故意的，不是故障）",
                check=(
                    "想看到检测结果 → 回到上面勾上「调试串口」或「OLED」再生成一次；"
                    "这一趟的作用只是确认板子和烧录链路是活的"
                ),
            )
        )
    items.append(
        ChecklistItem(
            id="reset",
            expect="按一下复位键，现象从头再来一遍（灯继续闪、输出通道再打一次那一行）",
            check=(
                "① 复位键没接 / 按下没反应 → 直接断电重新上电；"
                "② 只打印一次就停 = 程序进了死循环或硬件异常（HardFault）"
            ),
        )
    )
    if config.platform == PLATFORM_MSPM0:
        items.append(_MSPM0_BOOT_ITEM)
    return tuple(items)


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
    if config.oled and headers["oled"]:
        lines.append(f'#include "{headers["oled"]}"  /* OLED 屏 */')
    if headers["delay"]:
        lines.append(f'#include "{headers["delay"]}"  /* 心跳节拍 */')
    if headers["led"]:
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
    if config.platform == PLATFORM_MSPM0:
        lines.append(" *")
        lines.append(" * ⚠ 本平台已知限制：SysConfig 外设初始化（SYSCFG_DL_init）还没有被")
        lines.append(" *   生成链注入出来，所以下面那行初始化是**注释状态**。")
        lines.append(" *   上板前请先取消注释再重新编译，否则串口 / LED 都不会初始化")
        lines.append(" *   （灯不闪 ≠ 板子坏）。")
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
