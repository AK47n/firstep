"""自建件（库外件）的**探测小节**：定义 → C 语句 + 页面文案（工单 hwcheck-unknown-device/03）。

「我的器件」那一半（工单 02）让库外件在工具里存在；这一半让它**真的上板测一次**：
借 `i2c_probe` 那对脚与那条总线，ping 一次地址、（可选）读一个身份寄存器。

## 三条硬边界

1. **只读**（spec「不写寄存器、不读数据」）：渲染出的调用集必须落在 `i2c_probe`
   的**读侧**三件里（`i2c_probe_init` / `_ping` / `_read_reg`）——一个写寄存器
   调用都不许有。猜出来的读法比不测更坏。
2. **无引脚字面量**：脚由模块自己的宏（stm32）或 SysConfig 实例（mspm0）决定，
   这一层一个字都不提 `PA6` / `Pin_11` / `I2C_0_INST`——生成门禁明文拒绝引脚
   字面量，而且引脚是可改绑的（ADR 0010），写死在这里就等于绕开那套机制。
3. **页面上说的与板上做的一致**（三种形态如实分档）：

   | 定义 | 板上做 | 页面 / 板上都说 |
   |---|---|---|
   | 只有地址 | 只 ping | 「这一趟只验了应答」 |
   | 有寄存器、无期望值 | ping + 读回显 | 「没有期望值可比，只回显」 |
   | 有寄存器 + 期望值 | ping + 读 + 板上比较 | OK / FAIL + 排查话术 |

   三档的文案**单源在这里**（`CustomSection.plan`）：页面读 `sections_payload`，
   注释写进产物同一句——绝不两处各写一遍。

## 为什么单独一个模块

`hwcheck.py` 的边界是"框架长什么样"（心跳 / 通道 / 分节 / 汇总），`hwcheck_recipe.py`
是"库内配方怎么变成小节"。自建件既不是配方（它没有库内数据），也不是框架——它是
**用户确认的事实**变成的一段探测代码。三者的产物形状相近（都是 C 语句行），
但判据来源完全不同：一个来自库内 JSON、一个来自用户的 `device.json`。混在一起
之后"这条规则改哪边"就没有答案了。

## 与渲染框架的关系

本模块只产出**一节里的 C 语句行**（缩进好、纯函数、可逐字断言），把它插进
`main.c` 是 `hwcheck.render_main_c` 的事——注入点在 main.c 的**唯一产地**，
所以预览与生成两处产物逐字节一致（票面验收线）。

`RUNTIME_CALLS` = 这一节能调用的**框架运行时**白名单（`hwcheck_section` 这类由
`hwcheck.py` 渲染出来的函数）：渲染产物里出现的 `hwcheck_*` 调用必须都在名单里，
否则框架没渲那个函数、产物编不过（"按需渲染"那条验收线的负向判据）。

平台差异只有一处：`i2c_probe` 在该平台的头文件名（stm32 = `i2c_probe_stm32.h`、
mspm0 = `i2c_probe.h`）——接口同名同语义，所以**同一份渲染产物在两平台都成立**。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .hwcheck_errors import HwCheckError
from .hwcheck_recipe import c_string
from .my_devices import CustomDevice
from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32

__all__ = [
    "CUSTOM_TAG",
    "CUSTOM_TAG_TEXT",
    "PLAN_ECHO_ONLY",
    "PLAN_JUDGE",
    "PLAN_PING_ONLY",
    "PROBE_HEADERS",
    "PROBE_MODULE_SLUG",
    "RUNTIME_CALLS",
    "CustomSection",
    "custom_headers",
    "render_custom_section",
    "resolve_custom_sections",
    "sections_payload",
]

# 自建件探测要用的**库内模块**：`i2c_probe`（工单 01 的支点）。
# 有自建件小节时它必须进模块集——检测程序调它的函数，而生成门禁要求"调的函数
# 在被选模块的头里真实存在"（mspm0 上更是硬要求：main.c 只准调库内真实接口）。
PROBE_MODULE_SLUG = "i2c_probe"


# 标注词：**单独一个词**，且**不冒充库内专精件的 `[专精]`**（spec 用户故事 8：
# 学生要知道哪些结论是库内验证过的、哪些只是"按我给的地址试了一下"）。
CUSTOM_TAG = "自建件"
CUSTOM_TAG_TEXT = "自建件：按你确认的事实探测"

# `i2c_probe` 在平台上的头文件名（本模块要告诉框架 include 哪一个）。
# 接口两平台同名同语义（工单 01 定稿），所以渲染产物不分平台。
PROBE_HEADERS: dict[str, str] = {
    PLATFORM_STM32: "i2c_probe_stm32.h",
    PLATFORM_MSPM0: "i2c_probe.h",
}

# **这一对脚的平台代价**（工单 04 验收项 4：产物注释与页面同一句措辞）。
#
# 为什么产物里可以写它、而引脚字面量不行（两件事别混）：生成门禁
# （`generator._check_no_pin_literals_in_main`）是**剥注释后**判的（`clex.strip_comments`），
# 注释与字符串里的针脚名无害——它挡的是"代码内联引脚"（那样换板就得重写骨架、
# 也绕开了 ADR 0010 的改绑机制）。而下面这两句里**一个引脚名都没有**，说的是
# 板子上的既有接线与焊接事实，正是学生照表接线时会撞上的那颗暗雷。
#
# 判据来源（**不许在这里另写一份**）：板定义 `boards/mspm0-dimx.json` 的
# `BoardPin.notes`（PA0/PA1）——页面接线行的 `pin_note` 与工程 README 读的是同一份。
# 这两句是那份注记的**人读复述**（去掉引脚名，因为脚名在接线表里已经有了），
# `tests/test_hwcheck_custom.py::test_the_platform_cost_sentence_matches_the_board_definition`
# 按关键词逐条对账，板定义改了它就会红。
PLATFORM_PIN_COST: dict[str, str] = {
    PLATFORM_MSPM0: (
        "与板载 LED 共用（通信期间 LED 微闪属正常）；"
        "SDA 那根的板载上拉位未焊，依赖模块板自带的上拉电阻"
    ),
    PLATFORM_STM32: "",
}

# 这一节可以调的**框架运行时**（由 hwcheck.py 按需渲染）。多一个都不行：
# 框架没渲那个函数时产物编不过，而这正是"按需渲染"验收线的负向判据。
RUNTIME_CALLS: tuple[str, ...] = (
    "hwcheck_section",
    "hwcheck_detail",
    "hwcheck_verdict",
    "hwcheck_report",
    "hwcheck_report_hex",
    "hwcheck_newline",
)

# 三档的"这一趟对它做什么"（**文案单源**：页面与产物注释读同一句）。
PLAN_PING_ONLY = "只 ping 地址：这一趟只验了应答，没有验型号"
PLAN_ECHO_ONLY = "ping 地址 + 读身份寄存器：没有期望值可比，只回显读到的字节"
PLAN_JUDGE = "ping 地址 + 读身份寄存器并与期望值比较：板上判 OK / FAIL"

# 失败时的排查话术（贴在判定行下面）。四件事按"最可能先出错"的顺序排：
# 供电 / 上拉是硬件、线序是接线、地址写法是最常见的一处填错（7 位 vs 8 位）。
_TROUBLE_PING = (
    "没有应答：先查供电与上拉电阻，再查 SDA/SCL 线序，最后核对地址写法"
    "（手册里的 7 位地址）"
)
_TROUBLE_READ = "寄存器读失败：先核对寄存器地址，再查器件是否要求别的读法"
_TROUBLE_JUDGE = "读到的不等于你填的期望值：先核对寄存器地址与期望值，再查供电 / 上拉 / 线序"

# 版式符号（半角 + 全角各一处：C 字符串里的说明句与注释里的分隔）
_COLON = "："

# 用户自由文本进 C 注释前的长度上限（注释是给人读的，不是放手册的地方）
_COMMENT_MAX_CHARS = 120


@dataclass(frozen=True)
class CustomSection:
    """一件自建件的探测小节（渲染输入 = **用户确认过的事实**，没有一项推导）。

    `plan` 是"这一趟对它做什么"的**单源文案**：页面（`sections_payload`）与产物
    注释都读它，两处绝不会说不一样的话。
    """

    device: CustomDevice
    plan: str

    @property
    def slug(self) -> str:
        return self.device.id

    @property
    def func_name(self) -> str:
        """小节函数名（按 id 派生：id 是 slug 形，天然是合法 C 标识符片段）。"""
        return f"hwcheck_custom_{self.device.id}"

    @property
    def reports_verdict(self) -> bool:
        """这一节会不会产生板上判定（ping 总判）。

        三档都判：ping 不通 = FAIL（线 / 供电问题是最常见的失败），所以自建件
        从来不"只动一下不判"——这一点与通用降级件（判不了通断）正好相反。
        """
        return True

    @property
    def reads_register(self) -> bool:
        """这一节会不会读寄存器（决定框架要不要渲 `hwcheck_report_hex`）。

        这个判断**属于小节**，不属于调用方：`needs_hex` 那处原先隔着一层去读
        `section.device.register`（评审点名的 Feature Envy），改规则时得同时知道
        两边的形状。
        """
        return self.device.register is not None

    def to_payload(self) -> dict[str, Any]:
        device = self.device
        return {
            "slug": self.slug,
            "name": device.name,
            "tag": CUSTOM_TAG,
            "tag_text": CUSTOM_TAG_TEXT,
            "plan": self.plan,
            "address_text": _hex2(device.address),
            "register_text": _hex2(device.register),
            "expect_text": _hex2(device.expect),
            "echo_only": device.echo_only,
            "notes": device.notes,
            # 用户故事 8：页面要说清"这是按我确认的事实试的"，不是库内验证过的结论
            "user_confirmed": True,
        }


def custom_headers(platform: str) -> tuple[str, ...]:
    """这一节要 include 的头（`i2c_probe` 在该平台的头文件名）。"""
    if platform not in KNOWN_PLATFORMS:
        known = "、".join(sorted(KNOWN_PLATFORMS))
        raise HwCheckError(f"未知平台 {platform!r}，已注册的平台：{known}")
    return (PROBE_HEADERS[platform],)


def resolve_custom_sections(
    devices: Sequence[CustomDevice], *, has_output_channel: bool
) -> tuple[CustomSection, ...]:
    """选中的自建件 → 小节清单（保序；空 / 无输出通道 = 不出小节）。

    **只有 I2C 件出小节**：这一版只对 I2C 生成探测程序（spi / uart / 单总线 /
    模拟类只给清单与排障，那是工单 05 的事）——不假装测过。
    """
    if not has_output_channel:
        return ()
    return tuple(
        CustomSection(device=device, plan=_plan_for(device))
        for device in devices
        if device.bus == "i2c"
    )


def sections_payload(sections: Sequence[CustomSection]) -> list[dict[str, Any]]:
    """小节 → 页面载荷（前端只渲染，不另写一句文案）。"""
    return [section.to_payload() for section in sections]


def _comment_text(text: str) -> str:
    """用户填的自由文本 → **能安全放进 C 块注释**的一行。

    为什么必须有它（评审抓到的真缺陷）：`name` / `notes` 是用户随手填的，
    注释里一个 `*/` 就把这一段提前闭合、后面整段代码变成语法错误；换行会让
    注释行错位。注释与字符串字面量是**两条路**：字符串走 `c_string` 转义，
    注释只能消毒——把会终结注释的序列与所有换行 / 控制字符换掉，再收白 + 截断。

    这不是"防注入"级别的严格（本机单用户工具），是**产物能不能编译**的问题：
    备注里写一句 `手册写的 0x68 */` 是很自然的输入。
    """
    cleaned = str(text or "")
    for bad in ("*/", "/*", "\r", "\n", "\t"):
        cleaned = cleaned.replace(bad, " ")
    cleaned = "".join(ch if ch.isprintable() else " " for ch in cleaned)
    cleaned = " ".join(cleaned.split())      # 连续空白收成一个空格
    return cleaned[:_COMMENT_MAX_CHARS]


def render_custom_section(
    device: CustomDevice,
    *,
    has_output_channel: bool = True,
    platform: str = "",
) -> list[str]:
    """一件自建件的探测小节 → 缩进好的 C 语句行（纯函数，可逐字断言）。

    `has_output_channel=False` 或非 I2C 件 = 空清单（**不渲染小节**）：渲染了也没
    人看得见 —— 那是"假装测过"（既有口径，工单 02/04/05 一脉相承）。

    产物形态（确定性）：

    1. 注释块说明这是**按用户确认的事实**探测的（不是库内驱动、不是 AI 写的）；
       平台词表内还带一句**这一对脚的平台代价**（`PLATFORM_PIN_COST`，工单 04
       验收项 4：与页面同一句措辞——学生在产物里读到的与在检测页读到的是同一条
       硬件事实，不必回页面才想起来"LED 怎么在闪"）；
    2. `hwcheck_section(...)` 分节头；
    3. `i2c_probe_init()` → `i2c_probe_ping(0xNN)`：不通就报 FAIL、给排查话术、
       **直接 return**（不通还接着读寄存器只会得到一串无意义的失败）；
    4. 有寄存器：读回值与返回码**两分**；有期望值就板上比较 → `hwcheck_verdict`，
       没有就**只回显**（十六进制）并明说"没有期望值可比"。

    `platform` 缺省空 = 不印代价那句（纯设备侧渲染的既有调用方照旧；平台词表外
    同样不印——产物的**结构**仍与平台无关，多出来的只是一句人读注释）。

    ⚠ **字面量一律经 `c_string` 转义**（非 ASCII → 三位八进制）：ARMCC 5.06 按
    本地代码页解析源文件，原样中文会让整份 main.c 编不过（工单 05 真机判例）。
    注释里保留中文——那是给人读的，不影响解析。
    """
    if not has_output_channel or device.bus != "i2c" or device.address is None:
        return []
    address_text = _hex2(device.address)
    name_text = _comment_text(device.name)
    # 「地址上没有应答」那句在失败支与通过支**是同一个常量**（通过支不打印它，
    # 但两支传的是同一句话——抄两份就会改一处忘一处）。
    ping_trouble = f"{device.name}{_COLON}地址上没有应答"
    out: list[str] = [
        f"    /* ---- {CUSTOM_TAG_TEXT}：{name_text}（地址 {address_text}）---- */",
        "    /* 这是**你自己填的事实**，不是库内验证过的驱动：只 ping 地址、只读一个",
        "       寄存器，不写任何寄存器（猜出来的读法比不测更坏）。总线与引脚由",
        "       i2c_probe 决定——接线见检测页与工程 README。 */",
    ]
    if cost := PLATFORM_PIN_COST.get(platform, ""):
        # 与页面同一句措辞（接线行 / 板上共享那两处的注记原文的人读复述）
        out.append(f"    /* 这一对脚的平台代价（与检测页同一句）：{cost}。 */")
    if device.notes:
        out.append(f"    /* 你填的备注：{_comment_text(device.notes)} */")
    out.append(
        f"    hwcheck_section({c_string(f'{CUSTOM_TAG_TEXT}{_COLON}{device.name}')});"
    )
    out.append("    i2c_probe_init();")
    out.append("    int r;")
    out.append(f"    r = i2c_probe_ping({address_text});")
    out.append(f"    hwcheck_report({c_string('  应答：')});")
    out.append(f"    hwcheck_report((r == 0) ? {c_string('有')} : {c_string('没有')});")
    out.append("    hwcheck_newline();")
    out.append("    if (r != 0)")
    out.append("    {")
    out.append(f"        hwcheck_detail({c_string(_TROUBLE_PING)});")
    out.append(f"        hwcheck_verdict(0, {c_string(ping_trouble)});")
    out.append("        return;")
    out.append("    }")
    # 通过那一支：判定行由 `hwcheck_verdict` 记账（`ok==0` 时它才印 trouble），
    # 但那句 trouble 是**同一个字符串常量**——不在这里另抄一份（评审点名的复制
    # 粘贴陷阱：抄一份之后改一处忘一处，失败时的文案就与页面说的不是同一句）。
    out.append(f"    hwcheck_verdict(1, {c_string(ping_trouble)});")
    if device.register is None:
        out.append(
            f"    hwcheck_detail({c_string('这一趟只验了应答——没有填身份寄存器，')});"
        )
        out.append(
            "    hwcheck_detail("
            + c_string("所以看不出型号对不对（要判型号请填寄存器与期望值）。")
            + ");"
        )
        return out
    register_text = _hex2(device.register)
    out.append("    uint8_t value = 0;")
    out.append(f"    r = i2c_probe_read_reg({address_text}, {register_text}, &value);")
    out.append("    if (r != 0)")
    out.append("    {")
    out.append(f"        hwcheck_detail({c_string(_TROUBLE_READ)});")
    out.append(
        f"        hwcheck_verdict(0, {c_string(f'{device.name}{_COLON}读寄存器失败')});"
    )
    out.append("        return;")
    out.append("    }")
    out.append(f"    hwcheck_report({c_string('  读回：')});")
    out.append("    hwcheck_report_hex(value);")
    if device.expect is None:
        out.append("    hwcheck_newline();")
        out.append(
            f"    hwcheck_detail({c_string('没有期望值可比，只回显读到的字节——')});"
        )
        out.append(
            "    hwcheck_detail("
            + c_string("它不是「通过」，只是这一件确实应答、并且读回了东西。")
            + ");"
        )
        return out
    expect_text = _hex2(device.expect)
    out.append(
        f"    hwcheck_report((value == {expect_text}) ? "
        f"{c_string('（与期望值一致）')} : {c_string('（与期望值不一致）')});"
    )
    out.append("    hwcheck_newline();")
    out.append(
        f"    hwcheck_verdict((value == {expect_text}), "
        + c_string(f"{device.name}{_COLON}{_TROUBLE_JUDGE}")
        + ");"
    )
    return out


def _plan_for(device: CustomDevice) -> str:
    """这一件的"这一趟对它做什么"（**三档文案单源**）。"""
    if device.register is None:
        return PLAN_PING_ONLY
    if device.expect is None:
        return PLAN_ECHO_ONLY
    return PLAN_JUDGE


def _hex2(value: int | None) -> str:
    """一个字节 → `0xNN`（大写两位）；None = 空串（不编一个 0x00 出来）。"""
    return f"0x{value:02X}" if value is not None else ""
