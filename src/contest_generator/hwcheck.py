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
   `hwcheck_verdict` / "失败"档（ARMCC `#177-D`）；**一件小节都没有时**不渲染
   `hwcheck_report_int`（它有两个消费者：配方的 `read` 段与结尾汇总——两批小节
   都没有，两个消费者也就一起没了）；整趟都是带判定的探头时不留
   `hwcheck_verdict_probe_none`（tiarmclang `-Wunused-function`，05 实测）。
   生成的程序是给学生读的，死代码会让人以为漏调了什么。

还有一处**平台垫片**（`_PLATFORM_FILE_SCOPE`，05 的读源码判例）：mspm0 母版没有
SysTick 服务函数，而库内 DMP 端口会自己打开 SysTick 中断——不补一个空的
`SysTick_Handler` 就会掉进启动文件的 `Default_Handler` 死循环（灯都不闪）。

工单 06 补的一件事：**交互式串口命令台**（`hwcheck_console.py` 是那半命令的
所有者——命令表 / 纯解析 / C 分派都在那边）。本模块只负责把它插进框架、并守住
两条顺序判据（两条都真跑证过，别改）：

1. **命令台排在逐件小节之后**：`switch` 里直接调 `hwcheck_check_<slug>()`
   （自建件那一批调它们自己的 `hwcheck_custom_<id>()`），排在前面就是隐式声明
   （真机 0 warning 的验收线）。
2. **主循环里先 `hwcheck_console_poll()` 再 `debug_cmd_poll()`**：反过来的话，
   库内 poll 会先把命令缓冲清空，配方命令永远认不出来——现象是"敲了没反应、
   既有命令照常"，最难查的一类静默失效。
   `.scratch/module-hwcheck/probe-06-console-behaviour.py` 有这条的真跑反证
   （同一份命令台代码，只换顺序就复测不了）。

渲染条件也在这里：**有串口就渲染命令台**（不看有没有命令可敲——固定的帮助命令
永远在表里，学生更需要有人告诉他"能敲什么、既有那五条还在不在"；见 `render_main_c`
里 `console_rendered` 的注释）；没有串口时文件头与检测页都**明说**"不能交互式
复测"（不静默降级）。

命令表吃两批（工单 hwcheck-unknown-device/06）：**库内专精件**（配方声明字符）
与 **自建件**（没有配方、字符由 `hwcheck_console` 分配，复测入口 = 它自己的探测
小节函数——命令台因此与上电那一遍**同一措辞**）。通用件不进表（没有配方就没有
命令字符可敲，见下条）。

工单 07 补的一件事：**通用降级小节**（`render_main_c(config, sections, generic)`）
——没有配方的那些件（库内 168 个「模块 × 平台」格）不再"什么都不做"，而是走
`hwcheck_generic.py` 的通用路径（初始化 + I2C 类件的总线地址扫描）。本模块只负责
把它插进框架，三条判据在这里：

1. **两批互斥且专精在前**：一件走配方就不再出通用小节（`resolve_generic_sections`
   按 `specialized` 过滤）；顺序是"真测了的在前、走过场的在后"，学生一眼看得出
   哪些结论可信。
2. **命令表吃专精件与自建件，不吃通用件**（`build_console_table(sections, custom)`）：
   通用件没有配方，就没有命令字符可敲——把它塞进命令表会出现"页面没这个命令、
   板上却认"的分家（自建件反过来：它们的探测小节就是"复测"，一律进表）。
3. **共用运行时按需渲染，且必须算上通用件**：通用小节会调 `hwcheck_section` /
   `hwcheck_detail` / `hwcheck_verdict_probe_none` / `hwcheck_summary`，所以
   `needs_probe_none` 要 `or bool(generic)`——漏了就是**调用一个从未定义的函数**
   （编译期才发现；本单的判据强度探针 P 条实测抓到过，而当时的用例只查"名字在不在
   产物里"，是摆设——现在按调用/定义两面查）。

还有一条真机判例（宿主机真编译探针 `probe-07-scan-behaviour.py` 第一次跑就撞上）：
**扫描要用工程根的引脚宏，而 `headfile.h` 不带 `pin_config.h`**（模块自己的 .c
各自 include）——所以有扫描件时产物必须自己 include 它，否则 `main.c` 里那几个宏
是未声明的标识符（ARMCC 直接报错）。

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
from .hwcheck_custom import (
    CUSTOM_TAG_TEXT,
    CustomPlanEntry,
    CustomSection,
    custom_checklist,
    custom_headers,
    render_custom_section,
)
from .hwcheck_console import (
    ConsoleTable,
    build_console_table,
    render_console_runtime,
)
from .hwcheck_generic import (
    GENERIC_LABEL,
    GenericSection,
    render_generic_runtime,
    render_generic_section,
)
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
    "CustomPlanEntry",
    "CustomSection",
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
        # 工程根引脚宏（`SHT20_SCL_GPIO` / `I2C_GPIO` 这些）：**母版的 headfile.h
        # 不 include 它**（模块自己的 .c 各自 include），所以通用降级的扫描要显式
        # 带上——不然 `main.c` 里那几个宏是未声明的标识符（本单真机判例：宿主机
        # 真编译探针 `probe-07-scan-behaviour.py` 当场报 undeclared）。
        "pin_config": "pin_config.h",
    },
    PLATFORM_MSPM0: {
        "entry": "ti_msp_dl_config.h",
        "serial": "debug_uart_mspm0.h",
        "oled": "oled.h",
        "delay": "delay.h",
        "led": "led.h",
        # mspm0 的引脚是 SysConfig 实例生成的，没有 pin_config.h
        "pin_config": None,
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


def render_checklist(
    config: HwCheckConfig,
    custom: Sequence["CustomPlanEntry"] = (),
) -> tuple[ChecklistItem, ...]:
    """上板确认清单（3-6 条，随平台与通道形态变化；自建件另加几条）。

    为什么要清单：本功能要回答的是"我不知道怎么看它正常不正常"——只给一段
    代码和一个"检测通过"的断言，学生仍然只能猜。清单把**可肉眼核对的现象**
    与**最常见的三个原因**摆出来，勾选态本地留着，下次进来还知道自己走到哪。

    `custom`（工单 hwcheck-unknown-device/05）= 这一趟选中的自建件**计划**
    （`hwcheck_custom.resolve_custom_plan`）：出小节的件加三类（有应答 /
    期望值不符 / 无应答，"不对先查"复用产物里那两句排查话术），不出小节的件加
    一条如实说明。**文案一个字都不在这里写**——全部来自 `hwcheck_custom`
    （那三条的形状是 `{id, expect, check}`，这里只把它装成 `ChecklistItem`）。
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
    # 自建件（工单 hwcheck-unknown-device/05）：位置在**通道形态那几条之后、
    # `reset` 之前**——学生的阅读次序 = 板子活着 → 往哪儿看 → 我这件看到什么 →
    # 复位再来一遍。文案全部来自 `hwcheck_custom.custom_checklist`（单源）。
    items.extend(
        ChecklistItem(id=raw["id"], expect=raw["expect"], check=raw["check"])
        for raw in custom_checklist(custom)
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


def _ordered_includes(
    groups: Sequence[Sequence[str]], skip: Sequence[str] = ()
) -> tuple[str, ...]:
    """若干组头名 → **保序去重**的头名元组（工单 04 / 07 共用一处判据）。

    `skip` = 前面已经印过的头名（框架固定的那几行、上一批器件小节）：撞名时不再
    印第二遍——重复 include 有包含卫士兜着不出错，但生成的程序是给学生读的，
    同一行印两遍像是有意为之。

    两批消费方各给一组：
    * 专精小节给配方 `include` 段（人指定）；
    * 通用小节给 manifest 平台条目里**声明过的** `.h`（工单 07；没有配方数据可读，
      而通用件要调 `sht20_init()`，不 include 就是隐式声明——工单 05 的真机判例）。
    """
    out: list[str] = []
    for group in groups:
        for header in group:
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


def _recipe_runtime(
    *,
    needs_verdict: bool,
    needs_probe_none: bool,
    needs_hex: bool = False,
) -> list[str]:
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
    generic: Sequence["GenericSection"] = (),
    custom: Sequence["CustomSection"] = (),
) -> str:
    """渲染检测程序 main.c（框架 + 逐件专精小节 + 通用降级小节，全程零 LLM）。

    产物形态（确定性，逐字节可断言）：

    * 头部注释说明"这是硬件检测程序、不是赛题工程"，并说清**这一趟要测哪几件**
      （专精件与通用件分开列，措辞不同）；
    * 按形态 include：进门头恒在，通道 / 延时 / LED 头只在相关时才进，各件的头
      （配方 `include` 段 / 通用件的 manifest 平台条目 `.h`）随小节进；
    * 有输出通道时定义报告三件套（`hwcheck_report` / `_newline` / `_int`）与
      判定记账（`hwcheck_section` / `_detail` / `_verdict` / `_verdict_probe_none`
      / `_summary`，工单 04：判定在**板上**算，渲染期只生成比较式）；
      没有通道时**不定义也不调用**（防"定义了却没人调"的死代码）；
    * `main()`：平台初始化 → 通道初始化 → 上电先报一遍 → **逐件专精小节**
      （`sections`）→ **通用降级小节**（`generic`，工单 07）→ 结尾汇总 →
      while(1) 闪灯 +（有串口时）`hwcheck_console_poll()` + `debug_cmd_poll()`。

    两批小节的关系（工单 07）：

    * **互斥**：一件走专精就不会再出通用小节（`resolve_generic_sections` 按
      `specialized` 过滤）——一件两条小节 = 两个同名 C 函数，编不过；
    * **顺序**：专精件在前。它们带板端判定，是这一趟的主结果；通用件是走过场
      （只验总线和初始化），排在后面学生一眼看得出哪些是真测的；
    * **命令表只认专精件与自建件**：通用件没有配方，就没有命令字符可敲（工单 06 的
      接口备忘），所以 `build_console_table(sections, custom)` 吃两批、不吃 `generic`。

    `sections` / `generic` 缺省空 = 只出框架（工单 02 的"零器件最小硬件检测"形态）。
    有通道才渲染小节——没有输出通道时渲染了也没人看得见，那是"假装测过"。

    `custom`（工单 hwcheck-unknown-device/03）= **自建件**（库外件）的探测小节，
    排在库内两批之后：它的判据来自用户确认的事实、不是库内配方，所以排在最后
    （"哪些结论可信"的顺序照旧：bring-up → 库内器件 → 按你给的事实试的）。
    与另外两批的关系同 07 那条：**互斥**（自建件不进 `sections` / `generic`）、
    **头文件由框架统一印**（`custom_headers` 给的那一份）。

    平台词表外抛 HwCheckError（路由转 400 中文）；未知平台在这里就出不去，
    所以下面的分支是穷尽的。
    """
    headers = _PLATFORM_HEADERS[config.platform]
    # 命令表（工单 06）：配方声明的复测字符 + 自建件分配的字符 + 固定帮助命令。
    # **无条件构建**（不只是有串口的形态）——字符冲突 / 形状不对是**库内数据**
    # 或**分配结果**的错，该在每一次构建期红，而不是"这次没勾串口所以放它过去"。
    # 两批进表、通用件不进：通用件没有配方自然没有 `console` 段（07 的接口备忘）；
    # 自建件（工单 hwcheck-unknown-device/06）没有配方、没人声明字符，命令空间
    # 自己分一个（分配与保留字判据都在 `hwcheck_console`）。
    console = build_console_table(sections, custom)
    # 命令台的渲染条件（工单 06）：**有串口就有**（不看有没有配方命令）。
    # 为什么不是"有配方命令才渲染"：检测页那句提示写着"命令循环里敲 ? 看帮助"
    # ——命令台不在，那句话就是假的（评审抓到的假话）；而且一件命令都没声明时，
    # 学生更需要有人告诉他"能敲什么、既有那五条还在不在"。固定的帮助命令是
    # 命令表的一部分，命令表为空它也在。
    console_rendered = bool(config.debug_uart)
    # 「这一趟有没有要扫总线的通用件」——三处消费（引脚宏 include / 十六进制出口 /
    # 共用运行时的渲染条件），算一次：判据各写一遍就会静默漂移（评审点名的
    # Duplicated Code）。
    scan_rendered = any(section.scan is not None for section in generic)
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
    # 通用降级的扫描要用工程根的引脚宏（`SHT20_SCL_GPIO` 这类，manifest 声明的
    # 那对宏）——**headfile.h 不带它**（模块自己的 .c 各自 include），不显式 include
    # 就是未声明标识符（本单真机判例）。只有真有扫描件时才印：没有扫描的形态
    # 不需要它，多一行 include 会让人以为"这工程依赖引脚宏"。
    if scan_rendered and headers["pin_config"]:
        framework_headers.append(str(headers["pin_config"]))
    lines: list[str] = [
        "/**",
        " * @file main.c",
        " * @brief 硬件检测程序 —— 确定性渲染，非 AI 生成",
        " *",
        *_header_brief(config, sections, console=console, generic=generic),
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
    if scan_rendered and headers["pin_config"]:
        lines.append(
            f'#include "{headers["pin_config"]}"  /* 通用降级总线扫描的引脚宏'
            "（SHT20_SCL_GPIO 这类，值在 pin_config.h） */"
        )
    # 器件模块自己的头（配方 `include` 段，工单 05）：检测程序直接调模块函数，
    # 而上面那几行只覆盖通道与心跳——不 include 就会被当成隐式声明（真机判例：
    # stm32 侧 7 个 error：`#223-D function declared implicitly` +
    # `#20 identifier undefined`）。跨模块前置调用的头（如 ml_i2c.h）也走这里。
    device_headers = _ordered_includes(
        [section.include for section in sections], skip=framework_headers)
    for header in device_headers:
        lines.append(f'#include "{header}"')
    # 通用降级小节的头（工单 07）：判据 = 该模块 manifest 平台条目声明的 .h。
    # 器件小节的头先印，通用件与它撞名时不再印第二遍。
    generic_headers = _ordered_includes(
        [section.headers for section in generic],
        skip=[*framework_headers, *device_headers],
    )
    for header in generic_headers:
        lines.append(f'#include "{header}"')
    # 自建件小节的头（工单 03）：`i2c_probe` 在该平台的头（两平台不同名）。
    # 判据 = **这一趟真有自建件小节**才印——没有它就不该出现这一行（多一行会
    # 让人以为这工程依赖总线原语）。有 custom 却没有头 = 平台词表外，直接抛。
    # `skip` 必须带上**前面两批**（器件批 + 通用批）：用户可以把 `i2c_probe`
    # 自己选上，那样它已经在上面印过了——漏掉通用批就是同一行印两遍
    # （本单实测复现，评审抓到）。
    for header in _ordered_includes(
        [custom_headers(config.platform) if custom else ()],
        skip=[*framework_headers, *device_headers, *generic_headers],
    ):
        lines.append(f'#include "{header}"')

    lines.append("")
    lines.append("/* 心跳周期（毫秒）：改这里改闪灯快慢 */")
    lines.append(f"#define {_HEARTBEAT_MACRO} {HEARTBEAT_MS}")
    lines.append("")

    any_section = bool(sections) or bool(generic) or bool(custom)
    if config.has_output_channel:
        lines.extend(_report_outputs(config))
        lines.append("")
        lines.extend(_report_function(
            config,
            # 十进制读数出口的**消费者有两个**（工单 04 真编译矩阵逼出来的判据）：
            # ① 库内配方的 `read` 段（`hwcheck_recipe` 的
            #    `hwcheck_report_int(<表达式>)`）；② **结尾汇总**——板上一有判定
            #    项就逐档打「通过 N 项 / 未判定 N 项」，那三行也走这个出口。
            # 所以判据 = 「这台程序里有没有小节」（`any_section`），不是"有没有
            # 选器件"：选了件但一件小节都没出的形态（非 I2C 自建件、本平台没有
            # 配方的件）原先会渲出一个没人调的 `hwcheck_report_int`，ARMCC 报
            # `#177-D: function "hwcheck_report_int" was declared but never
            # referenced`，0 warning 验收线当场破（矩阵抓到的真缺陷）。
            needs_int=any_section,
            # 十六进制出口的**两个消费者**：自建件里"有寄存器、无期望值"那一档
            # 要回显读到的字节；通用降级的**总线地址扫描**要把地址打成 0x3C
            # （那一批原先自己印一个同名助手——两批小节同趟时产物里就出现两个
            # `hwcheck_report_hex` 定义，ARMCC 报 `#247: has already been
            # defined`，同一个矩阵抓到的另一条）。
            # 现在它只有这一个产地：判据 = **这台程序里有没有人要它**。
            needs_hex=(
                any(section.reads_register for section in custom) or scan_rendered
            ),
        ))
        lines.append("")
        if any_section:
            # 通用件一律"判不了通断"（没有探头就是没有），所以它们参与时
            # `hwcheck_verdict_probe_none` 必须在场——否则通用小节调用一个
            # 从未定义的函数（编译期才发现）。
            # **自建件相反**：它 ping 一次就是一个判定，从不走"未判定"那一档。
            lines.extend(_recipe_runtime(
                needs_verdict=_needs_verdict(sections) or bool(custom),
                needs_probe_none=_needs_probe_none(sections) or bool(generic),
            ))
            lines.append("")
        # 通用降级的共用运行时（I2C 地址 ping）：只有真有扫描件时才渲染
        # ——按需渲染是 04/05 定下的 0 warning 验收线（见 render_generic_runtime）。
        generic_runtime = render_generic_runtime(generic)
        if generic_runtime:
            lines.extend(generic_runtime)
            lines.append("")

    if sections and config.has_output_channel:
        lines.append("/* ---- 逐件检测小节（按库内配方渲染；未专精件走通用降级）---- */")
        for section in sections:
            lines.append(f"static void hwcheck_check_{section.slug}(void)")
            lines.append("{")
            lines.extend(render_recipe_section(section))
            lines.append("}")
            lines.append("")

    # 通用降级小节（工单 07）：排在专精小节之后（见 docstring「顺序」），
    # 且必须在 `render_generic_runtime` 之后——C 要求调用点之前有定义。
    if generic and config.has_output_channel:
        lines.append(f"/* ---- 通用降级小节（{GENERIC_LABEL}；工单 07）---- */")
        for section in generic:
            lines.append(f"static void hwcheck_generic_{section.slug}(void)")
            lines.append("{")
            lines.extend(render_generic_section(section))
            lines.append("}")
            lines.append("")

    # 自建件小节（工单 03）：排在库内两批**之后**——它的判据来自用户确认的事实、
    # 不是库内配方，所以学生在页面上读到的顺序是"库内验证过的 → 按你给的事实试的"。
    if custom and config.has_output_channel:
        lines.append(f"/* ---- 自建件小节（{CUSTOM_TAG_TEXT}；工单 03）---- */")
        for section in custom:
            lines.append(f"static void {section.func_name}(void)")
            lines.append("{")
            lines.extend(
                render_custom_section(section.device, platform=config.platform)
            )
            lines.append("}")
            lines.append("")

    # 串口命令台（工单 06）：排在逐件小节**之后**——`switch` 里直接调
    # `hwcheck_check_<slug>()`，排在前面就是隐式声明（真机口径 0 warning 的要求）
    if console_rendered:
        lines.extend(render_console_runtime(console))
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
    if any_section and config.has_output_channel:
        lines.append("    /* ---- 上电自动跑一遍逐件检测 ---- */")
        for section in sections:
            lines.append(f"    hwcheck_check_{section.slug}();")
        for section in generic:
            lines.append(f"    hwcheck_generic_{section.slug}();")
        for section in custom:
            lines.append(f"    {section.func_name}();")
        lines.append("")
        if sections:
            lines.extend(render_recipe_summary(_section_reports(sections)))
        elif custom:
            # 只有自建件：库内那批没有"万一判失败先查哪里"可印（它们不判），
            # 但自建件会产生判定 → 汇总照旧要印（它如实数通过 / 失败）。
            lines.append("    /* 这一趟只有自建件：判定由自建件小节产生，汇总照旧。 */")
            lines.append("    hwcheck_summary();")
        else:
            # 只有通用件：没有"万一判失败先查哪里"可印（通用件不判），
            # 但汇总要印——它如实数出"未判定 N 项"（不假装测过）。
            lines.append("    /* 这一趟只有未专精件：板上没有判定项，汇总如实计入「未判定」。 */")
            lines.append("    hwcheck_summary();")
        lines.append("")
    lines.append("    while (1)")
    lines.append("    {")
    if config.debug_uart:
        if console_rendered:
            # 先 peek 我们的命令，再让库内 poll 处理既有命令——反了的话库内
            # `debug_cmd_poll()` 会先把缓冲清空，配方命令永远认不出来
            lines.append("        hwcheck_console_poll();  /* 配方命令：复测不用重烧 */")
        lines.append("        debug_cmd_poll();  /* 串口命令通道：复测不用重烧 */")
    lines.append(f"        led_toggle({_LED_CHANNEL});")
    lines.append(f"        delay_ms({_HEARTBEAT_MACRO});")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _header_brief(
    config: HwCheckConfig,
    sections: Sequence["RecipeSection"] = (),
    *,
    console: ConsoleTable | None = None,
    generic: Sequence["GenericSection"] = (),
) -> list[str]:
    """文件头"这一趟做什么"的说明行——**按通道形态与器件集说实话**。

    有输出通道：三件事（闪灯 + 上电先报一句 + 逐件小节）。
    没有输出通道：**只有闪灯一件事**——文件头若照抄"每一段结果写到输出通道"，
    而全文一个打印调用都没有（见 render_main_c 的分支），那份自述就是撒谎
    （与 OUTPUT_HINT_NONE 的"这一趟不打印任何检测结果"直接矛盾）。

    串口这一路还要说清**命令台**（工单 06）：有命令（配方声明的 / 自建件分到的）
    就逐条列出，没有串口就明说"不能交互式复测"——这两句是学生判断"我敲了没反应
    是不是坏了"的唯一线索，不能留在页面上、代码里却不写。

    器件分两批如实列（工单 07）：专精件带 `SECTION_TAG`，通用件带
    `GENERIC_LABEL` 与"这一趟对它做什么"——**标注在检测页与产出注释里同时
    出现、措辞同一句**（票面验收线），学生才知道哪些结论可信。
    """
    lines = [" * 这一趟用来确认「板子活着 + 烧录链路通」："]
    if config.has_output_channel:
        lines.append(" *   1. 板载 LED 按固定周期闪烁（心跳，肉眼可见）；")
        lines.append(" *   2. 上电先报一句「板子活着」，随后逐件跑检测小节。")
    else:
        lines.append(" *   1. 板载 LED 按固定周期闪烁（心跳，肉眼可见）。")
        lines.append(" *   本形态没有输出通道，因此**不打印任何检测结果**——")
        lines.append(" *   代码里也没有打印调用（不假装测过）。")
    table = console if console is not None else ConsoleTable()
    if config.debug_uart:
        lines.append(" *")
        lines.append(" * 上电跑完一遍后进**串口命令台**（复测不用重烧，边动线边看现象）：")
        if table.entries:
            for entry in table.entries:
                lines.append(
                    f" *   - {entry.command}  复测 {entry.label}：{entry.detail}"
                )
        else:
            # ⚠ 这两句**保持改动前的字面量**（同 `hwcheck_console` 里那句帮助行）：
            # 自建件从不声明字符，所以"没有配方命令"在新世界里仍然为真；而票面第 5 条
            # 要求"一件自建件都没有时命令台产物逐字与改动前一致"——统一措辞就得动它。
            lines.append(" *   - 这一趟没有配方命令（选的器件都没声明复测字符）：")
            lines.append(" *     命令循环里只有帮助与下面那几条既有命令。")
        lines.append(
            f" *   - {table.help_command}  显示全部命令（含下面那几条既有命令）"
        )
        lines.append(
            " * 既有 r / y / g / o / b<N>（点灯 / 蜂鸣）**语义不变**——"
            "它们仍由库内 debug_cmd_poll() 执行。"
        )
    else:
        lines.append(" *")
        lines.append(" * 本形态**没有串口**：跑完上面这一遍就只剩心跳，")
        lines.append(" * **不能交互式复测**（没有命令循环）——想边动线边看现象，")
        lines.append(" * 请回到检测页勾上「调试串口」重新生成一次。")
    if sections and config.has_output_channel:
        lines.append(" *")
        lines.append(" * 逐件检测小节（按库内配方渲染，非 AI 生成）：")
        for section in sections:
            lines.append(
                f" *   - {SECTION_TAG} {section.slug}（配方："
                f"{_section_recipe_brief(section)}）"
            )
    # 通用降级小节（工单 07）：**与检测页同一句措辞**（GENERIC_LABEL）——
    # 学生拿串口上的输出对检测页时，两边说的是同一件事。这里不写 `SECTION_TAG`
    # 那个字面量：产物里出现它就该是"这一节真测了"，一句否定式说明会让
    # "通用件不带专精标记"这条结构守卫变得没法机械断言（本单实测踩到）。
    if generic and config.has_output_channel:
        lines.append(" *")
        lines.append(f" * 通用降级小节（{GENERIC_LABEL}——**不是**专精小节）：")
        for section in generic:
            lines.append(f" *   - {section.slug}：{section.plan_text}")
    if not sections and not generic and config.has_output_channel:
        lines.append(" *")
        lines.append(" * 这一趟**一件器件都没测**：只确认板子与烧录链路是活的。")
        lines.append(" * （选中的器件若不在本平台，会在检测页被点名，不在这里。）")
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

    **行尾策略（工单 06 定，04 的备忘点名叫这一单定）：串口每行补 `\\r\\n`。**
    裸 LF 在串口助手里只换行不回列，下一行会接着上一行的尾巴写（多行帮助 /
    逐件回显挤成一团）；库内自己的消息就是 `\\r\\n`（`debug_uart.c` 的
    `DEBUG_PRINTF("LED: RED (lock)\\r\\n")`），检测程序与它同口径才不打架。
    **只加在串口出口**：OLED 是显存式整行刷新（`oled_show_text`），行尾不是它的
    概念，`\\r\\n` 进去只会白占两格显存。
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
            "    /* 每行补 CRLF（行尾策略，工单 06）：串口助手上裸 LF 不回列，",
            "     * 下一行会接着上一行的尾巴写。库内既有消息也是 \\r\\n 结尾。 */",
            '    DEBUG_PRINTF("%s\\r\\n", s);',
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
    config: HwCheckConfig, *, needs_int: bool = True, needs_hex: bool = False
) -> list[str]:
    """自检报告三件套：写文本 / 换行 / 写一个整数（+ 按需的十六进制一个字节）。

    三个出口都**只做"把这段文本送到所有在场通道"**：通道差异只在各自的
    `hwcheck_write_*` 里出现，框架与逐件小节都不必知道自己往哪儿写。

    `needs_int`（真机编译矩阵实测）：一件小节都没有的形态（不选器件）不渲染
    `hwcheck_report_int`——它是"读数回显"的出口，没人调时 ARMCC 报 `#177-D:
    declared but never referenced`（生成的程序是给人读的，死代码会让人以为
    漏调了什么）。判据是 `any_section`（**有消费者才渲**）：消费者有两个——
    配方的 `read` 段，以及**结尾汇总**那三行（通过 / 失败 / 未判定各要一个十进制
    数，`_recipe_runtime` 里恒引用它）；两批小节都没有时两个消费者一起消失，
    所以"有没有小节"就是"有没有人要它"。

    `needs_hex`（工单 hwcheck-unknown-device/03，04 补齐第二个消费者）同一条口径：
    它是**唯一产地**（通用降级批次原先自己印一个同名助手，两批同趟时产物里就出现
    两个定义 = 编译期 `#247`）。消费者有两个：自建件里"有寄存器、无期望值"那一档
    要按十六进制回显一个字节；通用降级的**总线地址扫描**要把地址打成 `0x3C`。
    两个都没有时不渲染它——同一条按需渲染纪律。

    ⚠ 两个出口**互相独立**（04 实测踩到）：`needs_hex` 的渲染不能串在
    `needs_int` 的提前 return 之后——"只有自建件读寄存器"的形态里 `needs_int`
    恰好是 False，串起来就永远不渲它，而产物里那行调用照样在。
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
    # ⚠ 两个出口**互相独立**（工单 04 实测踩到）：`needs_hex` 的判据不再是
    # `needs_int` 的后续——形态"只有自建件读寄存器"里 `needs_int` 恰好是 False
    # （没有配方 `read` 段），把 hex 段接在 `needs_int` 的提前 return 之后就等于
    # 永远不渲它，而产物里那行 `hwcheck_report_hex(value)` 照样在（编译期才发现）。
    if needs_int:
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
    if not needs_hex:
        return out
    out.extend([
        "",
        "/** 把一个字节写成 `0xNN`（大写两位；自建件「只回显」那一档用）。 */",
        "static void hwcheck_report_hex(uint8_t value)",
        "{",
        '    static const char digits[] = "0123456789ABCDEF";',
        '    hwcheck_report("0x");',
        "    {",
        "        char hi[2];",
        "        char lo[2];",
        "        hi[0] = digits[(value >> 4) & 0x0F];",
        "        hi[1] = 0;",
        "        lo[0] = digits[value & 0x0F];",
        "        lo[1] = 0;",
        "        hwcheck_report(hi);",
        "        hwcheck_report(lo);",
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

