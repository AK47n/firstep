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

工单 03 补的一件事：**器件选择**（`HwCheckConfig.devices`）进模块集——页面上
看到的接线表要与生成工程 README 的引脚接线表**同源**，前提是页面与工程用的是
同一个模块集。板侧投影（接线行 / 同脚冲突 / 建议顺序 / 缺平台条目）不在这里，
归 `hwcheck_board.py`（本模块继续只管"检测程序长什么样"）。

工单 04 补的一件事：**逐件专精小节**（`render_main_c(config, sections)`）——
"每一件怎么测"由 `hwcheck_recipe.py` 从库内配方数据解析（形状 / 校验 / 渲成 C
都在那边），本模块只负责把它插进框架、并渲染骨架期那套运行时（分节头 / 判定
记账 / 结尾汇总）。

工单 05 补的一件事：**平台不对称如实呈现**（`ml_mpu6050` 是第一件真·器件专精
件）。三条真机判例留在这里免得后人踩：

1. **所有 C 字面量都走 `hwcheck_recipe.c_string` 转义**（非 ASCII → **三位八进制**
   `\\302\\261`，工单 05 从 `\\xNN` 改过来）：ARMCC 5.06 按本地代码页解析源文件，
   中文字面量会把收尾引号吞掉 → `#8: missing closing quote`，整份 main.c 编不过
   （04 实测 22 error；量具 `.scratch/module-hwcheck/probe-04-armcc-utf8.py`）。
   改用八进制是因为 `\\x` 会**贪婪吃**后面的十六进制数字（`±2g` → `\\xb12` 越界，
   ARMCC 报 `#27-D`，05 实测）。
2. **器件模块的头由配方的 `include` 段带进来**：框架那几行只覆盖通道与心跳，
   检测程序直接调模块函数——不 include 就是隐式声明（05 实测 stm32 侧 7 error）。
3. **按需渲染**（每种形态都要 0 error / 0 warning）：一件带判定的都没有时不留
   `hwcheck_verdict` / "失败"档（ARMCC `#177-D`）；一件读数都没有时不渲染
   `hwcheck_report_int`；整趟都是带判定的探头时不留 `hwcheck_verdict_probe_none`
   （tiarmclang `-Wunused-function`，05 实测）。生成的程序是给学生读的，死代码
   会让人以为漏调了什么。

还有一处**平台垫片**（`_PLATFORM_FILE_SCOPE`，05 的读源码判例）：mspm0 母版没有
SysTick 服务函数，而库内 DMP 端口会自己打开 SysTick 中断——不补一个空的
`SysTick_Handler` 就会掉进启动文件的 `Default_Handler` 死循环（灯都不闪）。

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
from typing import Sequence

from .hwcheck_errors import HwCheckError
from .hwcheck_recipe import (
    SECTION_TAG,
    RecipeSection,
    c_string,
    render_recipe_section,
    render_recipe_summary,
)
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
    "dedup_slugs",
    "hwcheck_devices",
    "hwcheck_modules",
    "render_checklist",
    "render_main_c",
    "render_output_hint",
    "require_known_platform",
]


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

# 文件作用域的平台垫片（工单 module-hwcheck/05 的真机判例）。
#
# **mspm0 没有 SysTick 服务函数**：stm32 侧由母版 `ml_libs/ml_systick.c` 提供
# `SysTick_Handler`，mspm0 母版里一个都没有；而 TI 启动文件把 `SysTick_Handler`
# 弱别名到 `Default_Handler`，后者是 `while (1) { }`（实测源码：
# `C:\ti\ccs2051\mspm0_sdk_2_10_00_04\source\ti\devices\msp\m0p\
# startup_system_files\ticlang\startup_mspm0g350x_ticlang.c`）。于是**任何自己
# 打开 SysTick 中断的驱动**（库内 ml_mpu6050 的 DMP 端口：`mpu_port.c` 的
# `DMP_Init` 里 `SysTick_CTRL_TICKINT_Msk | __enable_irq()`）都会让检测程序在
# 那一句里掉进死循环——现象是"灯都不闪、串口一个字没有"，看着像板子坏了，
# 其实是缺一个中断服务函数。
#
# 所以检测程序（它就是那个"应用"）如实补上：空实现就够——本程序不用 SysTick
# 做记账（DMP 端口自己的 `sys_tick_ms` 时间戳没被声明在头里，应用侧引不到，
# 而它按模块自述"不递增仅影响 mget_ms 时间戳、不影响功能"）。与上面
# `_PLATFORM_BOOT_LINES` 同级：**平台事实**，不随选了哪几件而变。
_PLATFORM_FILE_SCOPE: dict[str, tuple[str, ...]] = {
    PLATFORM_STM32: (),
    PLATFORM_MSPM0: (
        "/* mspm0：SysTick 中断服务函数（母版没有提供，见文件头的平台说明——",
        " * 缺了它，自己打开 SysTick 中断的驱动会掉进启动文件的死循环）。 */",
        "void SysTick_Handler(void)",
        "{",
        "    /* 空实现就够：检测程序不用 SysTick 记账，只是别落进 Default_Handler。 */",
        "}",
        "",
    ),
}

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



def require_known_platform(platform: str) -> str:
    """平台词表校验（单源）：词表外 → HwCheckError（400 中文，列出已注册平台）。

    两处消费：`HwCheckConfig`（请求形状）与 `hwcheck_board.hwcheck_board_view_for`
    （直接按平台取板定义的调用方）——同一句话只写一次，免得两处各写一版。
    """
    if platform not in KNOWN_PLATFORMS:
        known = "、".join(sorted(KNOWN_PLATFORMS))
        raise HwCheckError(f"未知平台 {platform!r}，已注册的平台：{known}")
    return platform


@dataclass(frozen=True)
class HwCheckConfig:
    """检测程序形态：平台 + 两个输出通道开关 + 选中的器件。

    检测程序**不依赖生成流程任何状态**（spec：不需要赛题、不需要已选模块集），
    所以这里的输入只有"给谁做、往哪报、要测哪几件"。

    `devices`（工单 03）= 用户在检测页选中的器件 slug（保序，可重复——去重由
    `hwcheck_devices` 负责）。它们进工程（接线表与工程 README 同源的前提），
    逐件的检测小节由后续工单渲染；没有专精配方的器件走通用降级（spec）。
    """

    platform: str
    debug_uart: bool
    oled: bool
    devices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_known_platform(self.platform)
        for name, value in (("debug_uart", self.debug_uart), ("oled", self.oled)):
            if not isinstance(value, bool):
                raise HwCheckError(
                    f"通道开关 {name} 必须是布尔值（有 / 无），收到 {value!r}"
                )
        if isinstance(self.devices, str):
            # 裸字符串是可迭代的：不拦就会把 "ml_mpu6050" 逐个字符当器件，
            # 造出一串不存在的 slug（错得还很有迷惑性）
            raise HwCheckError(
                f"devices 必须是 slug 列表（字符串数组），收到单个字符串 {self.devices!r}"
            )
        for slug in self.devices:
            if not isinstance(slug, str) or not slug.strip():
                raise HwCheckError(
                    f"器件 slug 必须是非空字符串，收到 {slug!r}"
                )

    @property
    def has_output_channel(self) -> bool:
        return self.debug_uart or self.oled


def dedup_slugs(slugs: Sequence[str]) -> tuple[str, ...]:
    """slug 序列**保序去重**（空串丢掉）——单源。

    三处消费：`hwcheck_devices`（配置里的器件）、`hwcheck_board._missing_devices`
    （点名缺平台版本时不能重复点两遍）、生成侧的模块集。重复项不是无害的重复：
    依赖展开与接线行会照做两遍，同一根线画两次。
    """
    out: list[str] = []
    for slug in slugs:
        if isinstance(slug, str) and slug and slug not in out:
            out.append(slug)
    return tuple(out)


def hwcheck_devices(config: HwCheckConfig) -> tuple[str, ...]:
    """选中的器件（**保序去重**）。

    同一件选两次、或选了框架自带的模块（如 led），都只算一次——模块集是集合
    语义，重复项会让下游（依赖展开 / 接线行）把同一条线画两遍。
    """
    return dedup_slugs(config.devices)


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

    **选中的器件也进这个集合**（工单 03）：页面上的接线表要与**生成工程 README
    的引脚接线表**同源，前提就是页面上看到的模块集与工程里的模块集是同一个
    ——器件不进工程，README 里就没有它那几根线，页面说"接这儿"、工程里查无此线。
    "一个器件都不选也能生成"指的是不选**器件**时这一项为空，生成照旧。
    """
    modules = list(HWCHECK_FRAMEWORK_MODULES)
    for channel, slug in _CHANNEL_MODULES:
        if getattr(config, channel):
            modules.append(slug)
    for slug in hwcheck_devices(config):
        if slug not in modules:
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


def _section_includes(
    sections: Sequence["RecipeSection"], skip: Sequence[str] = ()
) -> tuple[str, ...]:
    """逐件小节声明的头文件（配方 `include` 段）→ **保序去重**的头名元组。

    `skip` = 框架已经印过的头名（进门头 / 通道 / 心跳那几行，见
    `_PLATFORM_HEADERS`）：配方与框架撞名时不再印第二遍——重复 include 有包含
    卫士兜着不出错，但生成的程序是给学生读的，同一行印两遍像是有意为之。
    """
    out: list[str] = []
    for section in sections:
        for header in section.include:
            if header not in out and header not in skip:
                out.append(header)
    return tuple(out)


def _needs_probe_none(sections: Sequence["RecipeSection"]) -> bool:
    """这一趟有没有"判不了通断"的小节 → 决定 `hwcheck_verdict_probe_none` 渲不渲。

    与 `_needs_verdict` 同一个理由（真机编译矩阵实测）：整趟都是带判定的探头
    （如只选 ml_mpu6050）时，那个函数声明了没人调——tiarmclang 报
    `-Wunused-function`（本单实测 1 warning），ARMCC 报 `#177-D`。
    """
    return any(
        not (section.probe and section.probe.expect) for section in sections
    )


def _needs_verdict(sections: Sequence["RecipeSection"]) -> bool:
    """这一趟有没有"能判出通过 / 失败"的小节（工单 04 编译矩阵实测的判据）。

    判定走 `hwcheck_verdict(ok, trouble)` 的只有两类：初始化带期望值、通信探头带
    期望值。一件都没有（如只选 led）时那个函数与"失败"计数就是死代码，ARMCC 会
    报 `#177-D: declared but never referenced`——生成的程序是给学生读的，留一个
    没人用的判定函数会让人以为漏调了什么。所以按需渲染。
    """
    return any(
        section.init_expect or (section.probe and section.probe.expect)
        for section in sections
    )


def _recipe_runtime(*, needs_verdict: bool, needs_probe_none: bool) -> list[str]:
    """逐件小节的运行时（工单 04）：分节头 / 细节行 / 判定记账 / 结尾汇总。

    为什么记账要放板上：规格判据三层里第②层是"板端通信判定"，而"这一趟到底
    真测了几件"取决于**运行时结果**（探头过没过）——渲染期只能列出"可能失败时
    该看哪里"。所以板上分三档数（通过 / 失败 / 没探头），**没探头的绝不算通过**
    （spec「不假装测过」）。

    失败时 `hwcheck_verdict` 自己把排查话术打出来（`· ` 开头的细节行）。
    这段运行时只在**有逐件小节**时渲染（见 render_main_c 的分支）。

    `needs_verdict`（真机编译矩阵实测）：**一件带判定的都没有时（如只选 led）
    不渲染 `hwcheck_verdict` 与"失败"那一档**——否则 ARMCC 报 `#177-D: function
    "hwcheck_verdict" was declared but never referenced`，学生读代码会以为漏调了
    什么（生成的程序是给人读的，死代码不是风格问题）。

    `needs_probe_none` 同理（工单 05 实测）：整趟都是带判定的探头时（如只选
    ml_mpu6050），`hwcheck_verdict_probe_none` 与"未判定"那一档声明了没人调，
    tiarmclang 报 `-Wunused-function`。两个开关互相独立（只选 oled 时反过来：
    有"未判定"档、没有"失败"档），所以都**由调用方显式算好传进来**——给默认值
    只会让"哪一档该在"这件事有一处看不见的分支。

    ⚠ **字面量一律经 `c_string` 转义**（非 ASCII → 三位八进制转义）：ARMCC 5.06 按
    本地代码页解析源文件，原样中文字面量会把收尾引号吞掉、整份 main.c 编不过
    （真机判例见 `hwcheck_recipe.escape_c_string`）。
    """
    out: list[str] = [
        "/* ---- 逐件小节运行时（判定在板上算，工单 module-hwcheck/04）---- */",
        "static int hwcheck_summary_ok;",
    ]
    if needs_verdict:
        out.append("static int hwcheck_summary_fail;")
    if needs_probe_none:
        out.append("static int hwcheck_summary_probe_none;")
    out.extend([
        "",
        "/** 小节头：空一行 + 标题（一串检测结果之间的分节）。 */",
        "static void hwcheck_section(const char *title)",
        "{",
        f"    hwcheck_report({c_string('')});",
        "    hwcheck_report(title);",
        "    hwcheck_newline();",
        "}",
        "",
        "/** 细节行（排查线索 / 平台说明）：行首缩进，和判定行区分开。 */",
        "static void hwcheck_detail(const char *text)",
        "{",
        f"    hwcheck_report({c_string('    · ')});",
        "    hwcheck_report(text);",
        "    hwcheck_newline();",
        "}",
        "",
    ])
    if needs_verdict:
        out.extend([
            "/** 记一次判定（1 = 通过，0 = 失败）；失败顺带把排查话术打出来。 */",
            "static void hwcheck_verdict(int ok, const char *trouble)",
            "{",
            "    if (ok)",
            "    {",
            "        hwcheck_summary_ok++;",
            "    }",
            "    else",
            "    {",
            "        hwcheck_summary_fail++;",
            "        hwcheck_detail(trouble);",
            "    }",
            "}",
            "",
        ])
    if needs_probe_none:
        out.extend([
            "/** 记一次「判不了」（没有读取型探头）：**不算通过**，只提示看现象。 */",
            "static void hwcheck_verdict_probe_none(const char *hint)",
            "{",
            "    hwcheck_summary_probe_none++;",
            "    hwcheck_detail(hint);",
            "}",
            "",
        ])
    out.extend([
        "/** 结尾汇总：三档分开数（没探头的绝不混进「通过」）。 */",
        "static void hwcheck_summary(void)",
        "{",
        f"    hwcheck_report({c_string('')});",
        f"    hwcheck_report({c_string('==== 检测汇总 ====')});",
        "    hwcheck_newline();",
        "    if (hwcheck_summary_ok > 0)",
        "    {",
        f"        hwcheck_report({c_string('  通过：')});",
        "        hwcheck_report_int(hwcheck_summary_ok);",
        f"        hwcheck_report({c_string(' 项')});",
        "        hwcheck_newline();",
        "    }",
    ])
    if needs_verdict:
        out.extend([
            "    if (hwcheck_summary_fail > 0)",
            "    {",
            f"        hwcheck_report({c_string('  失败：')});",
            "        hwcheck_report_int(hwcheck_summary_fail);",
            f"        hwcheck_report({c_string(' 项（排查线索见上面的 · 行）')});",
            "        hwcheck_newline();",
            "    }",
        ])
    if needs_probe_none:
        out.extend([
            "    if (hwcheck_summary_probe_none > 0)",
            "    {",
            f"        hwcheck_report({c_string('  未判定：')});",
            "        hwcheck_report_int(hwcheck_summary_probe_none);",
            f"        hwcheck_report({c_string(' 项——这些件没有读取型探头，板上判不了通断，')});",
            "        hwcheck_newline();",
            f"        hwcheck_report({c_string('    请对照检测页清单看现象（灯闪 / 屏亮）')});",
            "        hwcheck_newline();",
            "    }",
        ])
    out.extend([
        "    if (hwcheck_summary_ok == 0"
        + (" && hwcheck_summary_fail == 0" if needs_verdict else "")
        + (" && hwcheck_summary_probe_none == 0" if needs_probe_none else "")
        + ")",
        "    {",
        f"        hwcheck_report({c_string('  这一趟没有板上判定项：只确认了板子与烧录链路是活的')});",
        "        hwcheck_newline();",
        "    }",
        "}",
    ])
    return out


def _section_reports(sections: Sequence["RecipeSection"]) -> list[dict[str, object]]:
    """逐件小节的观测清单（渲染期知道的那部分：有没有探头 / 失败时查哪里）。

    "几件通过"要到板上才算得出，所以计数在 C 侧（`hwcheck_summary`）；这里只
    收集"可能失败时该看哪里"给 `render_recipe_summary` 渲成细节行。
    """
    reports: list[dict[str, object]] = []
    for section in sections:
        report: dict[str, object] = {}
        render_recipe_section(section, report)
        reports.append(report)
    return reports


def render_main_c(
    config: HwCheckConfig,
    sections: Sequence["RecipeSection"] = (),
) -> str:
    """渲染检测程序 main.c（框架 + 逐件专精小节，全程零 LLM）。

    产物形态（确定性，逐字节可断言）：

    * 头部注释说明"这是硬件检测程序、不是赛题工程"，并说清**这一趟要测哪几件**；
    * 按形态 include：进门头恒在，通道 / 延时 / LED 头只在相关时才进；
    * 有输出通道时定义报告三件套（`hwcheck_report` / `_newline` / `_int`）与
      判定记账（`hwcheck_section` / `_detail` / `_verdict` / `_verdict_probe_none`
      / `_summary`，工单 04：判定在**板上**算，渲染期只生成比较式）；
      没有通道时**不定义也不调用**（防"定义了却没人调"的死代码）；
    * `main()`：平台初始化 → 通道初始化 → 上电先报一遍 → **逐件专精小节**
      （`sections`，判据与顺序由 `hwcheck_recipe` 给）→ 结尾汇总 →
      while(1) 闪灯 +（有串口时）`debug_cmd_poll()`。

    `sections` 缺省空 = 只出框架（工单 02 的"零器件最小自检"形态，同时是
    工单 04 里"未专精件没有逐件小节"的如实表达）。有通道才渲染小节——没有
    输出通道时渲染了也没人看得见，那是"假装测过"。

    平台词表外抛 HwCheckError（路由转 400 中文）；未知平台在这里就出不去，
    所以下面的分支是穷尽的。
    """
    headers = _PLATFORM_HEADERS[config.platform]
    # 框架这一趟印了哪些头（器件小节的 include 段据此去重，见 _section_includes）
    framework_headers: list[str] = [str(headers["entry"])]
    if config.debug_uart:
        framework_headers.append(str(headers["serial"]))
    if config.oled and headers["oled"]:
        framework_headers.append(str(headers["oled"]))
    if headers["delay"]:
        framework_headers.append(str(headers["delay"]))
    if headers["led"]:
        framework_headers.append(str(headers["led"]))
    lines: list[str] = [
        "/**",
        " * @file main.c",
        " * @brief 硬件检测程序 —— 确定性渲染，非 AI 生成",
        " *",
        *_header_brief(config, sections),
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
    # 器件模块自己的头（配方 `include` 段，工单 05）：检测程序直接调模块函数，
    # 而上面那几行只覆盖通道与心跳——不 include 就会被当成隐式声明（真机判例：
    # stm32 侧 7 个 error：`#223-D function declared implicitly` +
    # `#20 identifier undefined`）。跨模块前置调用的头（如 ml_i2c.h）也走这里。
    for header in _section_includes(sections, skip=framework_headers):
        lines.append(f'#include "{header}"')

    lines.append("")
    lines.append("/* 心跳周期（毫秒）：改这里改闪灯快慢 */")
    lines.append(f"#define {_HEARTBEAT_MACRO} {HEARTBEAT_MS}")
    lines.append("")

    if config.has_output_channel:
        lines.extend(_report_outputs(config))
        lines.append("")
        lines.extend(_report_function(
            config, needs_int=bool(sections) or bool(config.devices)))
        lines.append("")
        if sections:
            lines.extend(_recipe_runtime(
                needs_verdict=_needs_verdict(sections),
                needs_probe_none=_needs_probe_none(sections),
            ))
            lines.append("")

    if sections and config.has_output_channel:
        lines.append("/* ---- 逐件检测小节（按库内配方渲染；未专精件本版不出小节）---- */")
        for section in sections:
            lines.append(f"static void hwcheck_check_{section.slug}(void)")
            lines.append("{")
            lines.extend(render_recipe_section(section))
            lines.append("}")
            lines.append("")

    # 平台垫片（文件作用域）：mspm0 的 SysTick 服务函数，见 _PLATFORM_FILE_SCOPE
    lines.extend(_PLATFORM_FILE_SCOPE[config.platform])
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
        lines.append(f"    hwcheck_report({c_string('上电：板子活着，检测程序开始跑')});")
        lines.append("    hwcheck_newline();")
    else:
        lines.append("    /* 没有输出通道：只闪灯，不打印（看到灯闪 = 程序在跑） */")
    lines.append("")
    if sections and config.has_output_channel:
        lines.append("    /* ---- 上电自动跑一遍逐件检测 ---- */")
        for section in sections:
            lines.append(f"    hwcheck_check_{section.slug}();")
        lines.append("")
        lines.extend(render_recipe_summary(_section_reports(sections)))
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


def _header_brief(
    config: HwCheckConfig, sections: Sequence["RecipeSection"] = ()
) -> list[str]:
    """文件头"这一趟做什么"的说明行——**按通道形态与器件集说实话**。

    有输出通道：三件事（闪灯 + 上电先报一句 + 逐件小节）。
    没有输出通道：**只有闪灯一件事**——文件头若照抄"每一段结果写到输出通道"，
    而全文一个打印调用都没有（见 render_main_c 的分支），那份自述就是撒谎
    （与 OUTPUT_HINT_NONE 的"这一趟不打印任何检测结果"直接矛盾）。
    """
    lines = [" * 这一趟用来确认「板子活着 + 烧录链路通」："]
    if config.has_output_channel:
        lines.append(" *   1. 板载 LED 按固定周期闪烁（心跳，肉眼可见）；")
        lines.append(" *   2. 上电先报一句「板子活着」，随后逐件跑检测小节。")
    else:
        lines.append(" *   1. 板载 LED 按固定周期闪烁（心跳，肉眼可见）。")
        lines.append(" *   本形态没有输出通道，因此**不打印任何检测结果**——")
        lines.append(" *   代码里也没有打印调用（不假装测过）。")
    if sections and config.has_output_channel:
        lines.append(" *")
        lines.append(" * 逐件检测小节（按库内配方渲染，非 AI 生成）：")
        for section in sections:
            lines.append(
                f" *   - {SECTION_TAG} {section.slug}（配方："
                f"{_section_recipe_brief(section)}）"
            )
    elif config.has_output_channel:
        lines.append(" *")
        lines.append(" * 这一趟**没有专精件**：只确认板子与烧录链路是活的。")
        lines.append(" * 选了器件却没有配方时会如实写在这里，不假装测过。")
    if config.platform == PLATFORM_MSPM0:
        lines.append(" *")
        lines.append(" * ⚠ 本平台已知限制：SysConfig 外设初始化（SYSCFG_DL_init）还没有被")
        lines.append(" *   生成链注入出来，所以下面那行初始化是**注释状态**。")
        lines.append(" *   上板前请先取消注释再重新编译，否则串口 / LED 都不会初始化")
        lines.append(" *   （灯不闪 ≠ 板子坏）。")
        lines.append(" *")
        lines.append(" * 另外本平台母版**没有 SysTick 服务函数**（stm32 侧由 ml_systick.c 提供）")
        lines.append(" *   ——文件末尾那个空的 SysTick_Handler 就是补这一格的：自己打开 SysTick")
        lines.append(" *   中断的驱动（如 ml_mpu6050 的 DMP 端口）没有它会掉进启动文件的")
        lines.append(" *   Default_Handler 死循环（现象是灯都不闪）。别删。")
    return lines


def _section_recipe_brief(section: "RecipeSection") -> str:
    """小节的一句话配料（文件头注释用）：初始化 / 探头 / 读数各有没有。"""
    parts: list[str] = []
    if section.init:
        parts.append("初始化" + ("带判定" if section.init_expect else ""))
    if section.probe is not None:
        parts.append("通信探头带判定" if section.probe.expect else "只做动作不判定")
    if section.read:
        parts.append(f"{len(section.read)} 项读数")
    if section.console is not None:
        parts.append(f"控制台命令 {section.console.command!r}")
    return "、".join(parts) if parts else "无动作"


def _report_outputs(config: HwCheckConfig) -> list[str]:
    """行缓冲：把一段一段文本攒成一行，再送到在场的每个出口。

    为什么要缓冲：逐件小节要打「初始化：OK」「读数 = 123」这种**半行 + 半行**
    的组合，而 OLED 是显存式的——逐字符/逐段刷屏既慢又闪。所以报告文本先攒进
    一块静态缓冲，遇到换行（或攒满）才整行送出去。

    缓冲**溢出保护**是刻意的：一行超长（配方写了超长路径之类）时丢掉溢出部分而
    不是踩内存——宁可截断一行，也不让检测程序自己跑飞。
    """
    lines: list[str] = [
        "static char hwcheck_line[128];",
        "static int hwcheck_line_len;",
        "",
    ]
    if config.debug_uart:
        lines.extend([
            "static void hwcheck_write_serial(const char *s)",
            "{",
            '    DEBUG_PRINTF("%s", s);',
            "}",
            "",
        ])
    if config.oled:
        lines.extend([
            "static void hwcheck_write_oled(const char *s)",
            "{",
            "    /* 本屏 16×8 字符网格、可见 4 行：整行从头写，保证每次都看得见。",
            "     * 超过 16 列的整行会被屏自己截掉尾部（屏就这么宽）——检测页那几",
            "     * 行文案都控制在 16 列内，超了也只是尾巴看不见，不影响判定。 */",
            "    oled_show_text(0, 0, s);",
            "    oled_refresh();",
            "}",
            "",
        ])
    lines.extend([
        "/** 把攒好的一行送到所有在场的输出通道。 */",
        "static void hwcheck_write_line(const char *line)",
        "{",
        *_report_dispatch(config),
        "}",
        "",
    ])
    return lines


def _report_function(
    config: HwCheckConfig, *, needs_int: bool = True
) -> list[str]:
    """自检报告三件套：写文本 / 换行 / 写一个整数。

    三个出口都**只做"把这段文本送到所有在场通道"**：通道差异只在各自的
    `hwcheck_write_*` 里出现，框架与逐件小节都不必知道自己往哪儿写。

    `needs_int`（真机编译矩阵实测）：一件读数都没有的形态（不选器件）不渲染
    `hwcheck_report_int`——它是"读数回显"的出口，没人调时 ARMCC 报 `#177-D:
    declared but never referenced`（生成的程序是给人读的，死代码会让人以为
    漏调了什么）。
    """
    out: list[str] = [
        "/** 自检结果出口：一段文本攒进当前行；遇到换行就整行送出。 */",
        "static void hwcheck_report(const char *text)",
        "{",
        "    int i = 0;",
        "    while (text[i] != 0)",
        "    {",
        "        char ch = text[i++];",
        "        if (ch == '\\n')",
        "        {",
        "            hwcheck_line[hwcheck_line_len] = 0;",
        "            hwcheck_write_line(hwcheck_line);",
        "            hwcheck_line_len = 0;",
        "            continue;",
        "        }",
        "        if (hwcheck_line_len < (int)sizeof(hwcheck_line) - 1)",
        "        {",
        "            hwcheck_line[hwcheck_line_len++] = ch;",
        "        }",
        "    }",
        "}",
        "",
        "/** 换行（把当前攒的这一行送出去）。 */",
        "static void hwcheck_newline(void)",
        "{",
        '    hwcheck_report("\\n");',
        "}",
    ]
    if not needs_int:
        return out
    out.extend([
        "",
        "/** 把一个整数写成十进制（读数回显用；不判阈值——数据合理性归人看）。 */",
        "static void hwcheck_report_int(int value)",
        "{",
        "    char buf[12];",
        "    int i = 0;",
        "    int neg = (value < 0);",
        "    unsigned int v = neg ? (unsigned int)(-value) : (unsigned int)value;",
        "    if (v == 0)",
        "    {",
        "        buf[i++] = '0';",
        "    }",
        "    while (v > 0)",
        "    {",
        "        buf[i++] = (char)('0' + (int)(v % 10u));",
        "        v /= 10u;",
        "    }",
        "    if (neg)",
        "    {",
        '        hwcheck_report("-");',
        "    }",
        "    while (i > 0)",
        "    {",
        "        char one[2];",
        "        one[0] = buf[--i];",
        "        one[1] = 0;",
        "        hwcheck_report(one);",
        "    }",
        "}",
    ])
    return out


def _report_dispatch(config: HwCheckConfig) -> list[str]:
    """`hwcheck_write_line` 的分派体：把一行文本送给每个在场的出口。"""
    lines: list[str] = []
    if config.debug_uart:
        lines.append("    hwcheck_write_serial(line);")
    if config.oled:
        lines.append("    hwcheck_write_oled(line);")
    return lines

