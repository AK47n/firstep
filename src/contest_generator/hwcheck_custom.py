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
from typing import Any, Mapping, Sequence

from .hwcheck_errors import HwCheckError
from .hwcheck_recipe import c_string
from .my_devices import BUS_I2C, CustomDevice, address_forms
from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32

__all__ = [
    "CUSTOM_TAG",
    "CUSTOM_TAG_TEXT",
    "NOT_PROBED_NOT_I2C",
    "NOT_PROBED_NO_CHANNEL",
    "PLAN_ECHO_ONLY",
    "PLAN_JUDGE",
    "PLAN_PING_ONLY",
    "PROBE_HEADERS",
    "PROBE_MODULE_SLUG",
    "RUNTIME_CALLS",
    "CustomPlanEntry",
    "CustomSection",
    "custom_checklist",
    "custom_headers",
    "plan_order_rows",
    "plan_payload",
    "render_custom_section",
    "resolve_custom_plan",
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

# 「不出小节」的两句（工单 05：页面计划也要覆盖这些件，见 `resolve_custom_plan`）。
# 两句同样是"这一趟对它做什么"，所以与小节的三档**并列**而不是另起一套话术：
# 页面那一行读的永远是 `CustomPlanEntry.plan`，是不是探测小节由 `probes` 说明。
NOT_PROBED_NOT_I2C = (
    "这一版只对 I2C 器件生成探测程序：它这一趟没有探测小节"
    "（清单与 AI 排障照旧，不假装测过）"
)
NOT_PROBED_NO_CHANNEL = (
    "这一趟没有勾输出通道：探测小节渲染了也没人看得见，所以不出"
    "（想测就在上面勾上「调试串口」或「OLED」再预览）"
)

# 探测形态的**短标签**（排障上下文的「本次探测形态」那一行读它，工单 09）：
# 与长句 `PLAN_*` 同判据、两处写法——改三档判据时这一张表跟着 `_plan_for` 一起
# 看（`_probe_form` 按 `PLAN_*` 查表，缺一档 = KeyError 大声失败）。
_PROBE_FORM_LABELS = {
    PLAN_PING_ONLY: "只 ping",
    PLAN_ECHO_ONLY: "只回显",
    PLAN_JUDGE: "板上判定",
}
NO_PROBE_FORM_LABEL = "这一趟没有它的探测小节"

# 失败时的排查话术（贴在判定行下面）。四件事按"最可能先出错"的顺序排：
# 供电 / 上拉是硬件、线序是接线、地址写法是最常见的一处填错（7 位 vs 8 位）。
_TROUBLE_PING = (
    "没有应答：先查供电与上拉电阻，再查 SDA/SCL 线序，最后核对地址写法"
    "（手册里的 7 位地址）"
)
_TROUBLE_READ = "寄存器读失败：先核对寄存器地址，再查器件是否要求别的读法"
_TROUBLE_JUDGE = "读到的不等于你填的期望值：先核对寄存器地址与期望值，再查供电 / 上拉 / 线序"

# **板上会打出来的那几段文本**（工单 05：上板清单要学生拿着这几段去比对，所以
# 清单与产物必须是同一份字面量——两边各写一遍就是"改一处忘一处"）。
_ANSWER_LABEL = "应答："
_ANSWER_YES = "有"
_ANSWER_NO = "没有"
_MATCH_YES = "（与期望值一致）"
_MATCH_NO = "（与期望值不一致）"

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
        """小节函数名（按 id 派生：id 文法只收 C 标识符字符——判据单源在
        `my_devices.DEVICE_ID_PATTERN`，工单 12；这里不必再验一遍）。"""
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
        return _device_facts(self.device, self.plan)


def _device_facts(device: CustomDevice, plan: str) -> dict[str, Any]:
    """自建件的**事实面**载荷（两个投影共用：探测小节 / 检测页计划）。

    页面渲染只读这些键——所以它只有一处出处：改字段名时两个投影一起动，
    不会出现"小节载荷改了、计划载荷没跟上"。
    """
    return {
        "slug": device.id,
        "name": device.name,
        "tag": CUSTOM_TAG,
        "tag_text": CUSTOM_TAG_TEXT,
        "plan": plan,
        "address_text": _hex2(device.address),
        "register_text": _hex2(device.register),
        "expect_text": _hex2(device.expect),
        "echo_only": device.echo_only,
        "notes": device.notes,
        # 用户故事 8：页面要说清"这是按我确认的事实试的"，不是库内验证过的结论
        "user_confirmed": True,
    }


@dataclass(frozen=True)
class CustomPlanEntry:
    """一件**选中的**自建件在检测页上的计划（工单 05：接线行 / 顺序 / 清单那一栏）。

    与 `CustomSection` 的分工：小节是"进产物的那几件"（C 侧真源，`probes=True`）；
    计划是"**这一趟选中的每一件**"——不出小节的件（非 I2C、没勾输出通道）也在里面，
    `plan` 那句就是"为什么没有它的探测小节"。页面读计划，产物读小节，判据只有一处
    （`_probes`，两个函数共用）。

    `pins` / `wiring_text` = **支点 `i2c_probe` 的那对脚**（取自接线行，含引脚消解
    后的生效脚）——这件不是模块、没有 `pins` 声明，脚只能来自支点；`wiring_text`
    是页面那一行的人读句，前端一个字不另写。`pins` 只在这里用（拼那句话），
    **不进载荷**：页面要的是那句话，给它一份脚清单等于让它自己再拼一遍。
    """

    device: CustomDevice
    plan: str
    probes: bool
    pins: tuple[dict[str, str], ...] = ()
    wiring_text: str = ""

    @property
    def slug(self) -> str:
        return self.device.id

    def to_payload(self) -> dict[str, Any]:
        forms = address_forms(self.device.address)
        return {
            **_device_facts(self.device, self.plan),
            "probes": self.probes,
            "wiring_text": self.wiring_text,
            # 地址的 8 位读写形式 + 探测形态（工单 09：AI 排障的「自建器件事实」
            # 段读这份载荷——手册两种写法都能对上，模型才知道 0x68 与 0xD0 是
            # 同一个地址）。派生单源 `my_devices.address_forms` / `_probe_form`。
            "read8": forms["read8"],
            "write8": forms["write8"],
            "probe_form": _probe_form(self.device, probes=self.probes),
        }


def custom_headers(platform: str) -> tuple[str, ...]:
    """这一节要 include 的头（`i2c_probe` 在该平台的头文件名）。"""
    if platform not in KNOWN_PLATFORMS:
        known = "、".join(sorted(KNOWN_PLATFORMS))
        raise HwCheckError(f"未知平台 {platform!r}，已注册的平台：{known}")
    return (PROBE_HEADERS[platform],)


def _probes(device: CustomDevice, *, has_output_channel: bool) -> bool:
    """这一趟给不给它出探测小节（**判据单源**：C 侧小节与页面计划共用）。

    两条都要：勾了输出通道（否则渲染了也没人看得见）且是 I2C 件（这一版只对
    I2C 生成探测程序）。两处各判一次就会漂——页面上说"会测"、产物里没有它。
    """
    return has_output_channel and device.bus == BUS_I2C


def resolve_custom_sections(
    devices: Sequence[CustomDevice], *, has_output_channel: bool
) -> tuple[CustomSection, ...]:
    """选中的自建件 → 探测小节清单（保序；空 / 无输出通道 / 非 I2C = 不出小节）。

    **只有 I2C 件出小节**：这一版只对 I2C 生成探测程序（spi / uart / 单总线 /
    模拟类只给清单与排障，那是工单 05 的事）——不假装测过。
    """
    return tuple(
        CustomSection(device=device, plan=_plan_for(device))
        for device in devices
        if _probes(device, has_output_channel=has_output_channel)
    )


def resolve_custom_plan(
    devices: Sequence[CustomDevice],
    *,
    has_output_channel: bool,
    probe_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[CustomPlanEntry, ...]:
    """选中的自建件 → **检测页计划**（保序，每一件都在，含不出小节的那几件）。

    `probe_rows` = 支点 `i2c_probe` 的接线行（`wiring_rows` 的输出，含引脚消解后
    的生效脚）。只读 `role` / `pin` 两列——**不在这里另写一份脚**：接线表那一行
    是同一份数据，页面这一行与工程 README 因此是同一组脚。
    """
    rows = tuple(
        {"role": str(row.get("role", "")), "pin": str(row.get("pin", ""))}
        for row in probe_rows
    )
    entries: list[CustomPlanEntry] = []
    for device in devices:
        probing = _probes(device, has_output_channel=has_output_channel)
        plan = (
            _plan_for(device)
            if probing
            else _not_probed_reason(device, has_output_channel=has_output_channel)
        )
        pins = rows if probing else ()
        entries.append(
            CustomPlanEntry(
                device=device,
                plan=plan,
                probes=probing,
                pins=pins,
                wiring_text=_wiring_text(device, pins),
            )
        )
    return tuple(entries)


def plan_payload(entries: Sequence[CustomPlanEntry]) -> list[dict[str, Any]]:
    """计划 → 页面载荷（前端只渲染，不另写一句文案）。"""
    return [entry.to_payload() for entry in entries]


def plan_order_rows(entries: Sequence[CustomPlanEntry]) -> list[dict[str, Any]]:
    """计划里**出小节**的那几件 → 建议顺序表的追加行（**接在库内排序之后**）。

    形状与库内那几行同形（`{slug, description, bring_up}`，票面："判据复用既有排序，
    不另立一套"），多三个前端渲染用得上的键：`custom`（是自建件，不许冒充库内件）、
    `name` / `tag_text`（标注词单源）。

    **不出小节的那几件不进顺序表**：顺序表是"这一趟的测试次序"，把它排进去等于让
    学生以为它被测了（它们仍在计划与上板清单里，如实说没有探测程序）。
    """
    return [
        {
            "slug": entry.slug,
            "description": entry.plan,
            "bring_up": False,
            "custom": True,
            "name": entry.device.name,
            "tag_text": CUSTOM_TAG_TEXT,
        }
        for entry in entries
        if entry.probes
    ]


def sections_payload(sections: Sequence[CustomSection]) -> list[dict[str, Any]]:
    """小节 → 页面载荷（前端只渲染，不另写一句文案）。"""
    return [section.to_payload() for section in sections]


# 上板清单里自建件那几条的 id 尾巴（**稳定键**：勾选态按它存本地备忘、刷新回显；
# 渲染文案改了也不会串位——与既有 `ChecklistItem.id` 同一条约定）。三类的判据在
# `custom_checklist` 里（`answered` / `mismatch` / `silent`，外加不出小节的
# `not-probed`），**不为它单立一张表**：id 只在这一个模块里拼，前端照渲染不认名字。

# 「不出小节」那一条的排查话术：三条按"学生最可能做错的动作"排（把它当坏了 /
# 去等一个不会出现的输出 / 白白扔掉一次能问 AI 的机会）。
#
# 第③条说的"AI 会带上你填的事实"**现在是真话**（工单 09 落地：排障上下文新增
# 「自建器件事实」段；05 那一版这里挂过一句"还进不了它的上下文"的旧措辞，已随 09
# 改口）——改这句话之前先确认排障侧还在带这些事实（判据在
# `hwcheck_triage.build_triage_context` 与 tests/test_hwcheck_triage.py 的自建件段）。
_CHECK_NOT_PROBED = (
    "① 别把「没有它的输出」当成它坏了——这一趟本来就没给它出探测小节；"
    "② 接线照它自己的手册接（这一版没有自动检测）；"
    "③ 现象照常填到下面的「现象回填与排障」里——AI 会带上你填的总线 / 地址 / "
    "寄存器一起给排查方向"
)


def custom_checklist(
    entries: Sequence[CustomPlanEntry],
) -> tuple[dict[str, str], ...]:
    """检测页**上板清单**里自建件那几条（`{id, expect, check}`，形状同 `ChecklistItem`）。

    为什么在域层：这三条说的是"板上会打出什么"，与产物里那几句判定**必须同一句**——
    所以应看到的那几段文本直接复用渲染用的那几个常量（`_ANSWER_YES` /
    `_MATCH_YES` / `_ping_trouble`），"不对先查"复用 `_TROUBLE_PING` /
    `_TROUBLE_JUDGE`；页面不另写一遍。形状是 dict 而不是 `ChecklistItem`：那个
    类型住在 `hwcheck.py`，而 `hwcheck` 已经 import 本模块（反向 import 就是环）。

    **不为一件器件编它产生不了的类**：只有地址（形态①）与有寄存器无期望值（形态②）
    都没有"期望值不符"这一档——编一条学生照着比、板上永远不会发生的事，比少一条更坏。
    """
    items: list[dict[str, str]] = []
    for entry in entries:
        device = entry.device
        name = device.name
        prefix = f"custom-{entry.slug}-"
        if not entry.probes:
            items.append(
                {
                    "id": prefix + "not-probed",
                    "expect": (
                        f"「你的器件 {name}」这一趟没有探测小节：{entry.plan}"
                        "——串口 / 屏上不会出现它的任何结论，这是说好的，不是故障"
                    ),
                    "check": _CHECK_NOT_PROBED,
                }
            )
            continue
        address_text = _hex2(device.address)
        items.append(
            {
                "id": prefix + "answered",
                "expect": (
                    f"你的器件「{name}」（地址 {address_text}）那一节打出"
                    f"「{_ANSWER_LABEL}{_ANSWER_YES}」"
                ),
                "check": (
                    "一条都没打 = 程序没跑到那一节（先看上面「灯在闪」「串口有字」两条）；"
                    f"打的是「{_ANSWER_LABEL}{_ANSWER_NO}」→ 看下面「无应答」那一条"
                ),
            }
        )
        if device.expect is not None:
            items.append(
                {
                    "id": prefix + "mismatch",
                    "expect": (
                        f"读回的字节等于你填的期望值 {_hex2(device.expect)}"
                        f"（那一节会打出「{_MATCH_YES}」）"
                    ),
                    "check": _TROUBLE_JUDGE,
                }
            )
        items.append(
            {
                "id": prefix + "silent",
                "expect": f"不出现「{_ping_trouble(device)}」",
                "check": _TROUBLE_PING,
            }
        )
    return tuple(items)


def _wiring_text(
    device: CustomDevice, pins: Sequence[Mapping[str, str]]
) -> str:
    """「你的器件 X（地址 0xNN）接到 i2c_probe 的那对脚」那一行（**文案单源**）。

    没有支点接线行 = **空串**（不编一对脚出来）：非 I2C 件在页面上根本没有它的线。
    """
    if not pins:
        return ""
    bus = "、".join(f"{pin.get('role', '')} → {pin.get('pin', '')}" for pin in pins)
    return (
        f"你的器件 {device.name}（地址 {_hex2(device.address)}）"
        f"接到上面接线表里 {PROBE_MODULE_SLUG} 的那对脚：{bus}"
    )


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
    ping_trouble = _ping_trouble(device)
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
    out.append(f"    hwcheck_report({c_string('  ' + _ANSWER_LABEL)});")
    out.append(
        f"    hwcheck_report((r == 0) ? {c_string(_ANSWER_YES)} : {c_string(_ANSWER_NO)});"
    )
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
        f"{c_string(_MATCH_YES)} : {c_string(_MATCH_NO)});"
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


def _probe_form(device: CustomDevice, *, probes: bool) -> str:
    """探测形态的**短标签**（排障上下文那一行；判据 = `_plan_for`，工单 09）。

    短标签与长句（`PLAN_*`）是**同一判据的两个写法**，所以按 `PLAN_*` 查表派生，
    不另写一遍三档条件——多一份条件链就是"改一处忘一处"的下一个现场。新增一档
    却忘了配标签 = `KeyError` 大声失败（`test_every_probe_plan_has_a_short_label`
    在结构面钉着），不静默印一个空标签给模型看。
    """
    if not probes:
        return NO_PROBE_FORM_LABEL
    return _PROBE_FORM_LABELS[_plan_for(device)]


def _ping_trouble(device: CustomDevice) -> str:
    """「X：地址上没有应答」那一句（**产物与上板清单同一份**）。

    产物里它在失败支与通过支是同一个常量（通过支不打印它）；上板清单的"无应答"
    那一条则要学生**去找它有没有出现**——两处各写一遍就是改一处忘一处。
    """
    return f"{device.name}{_COLON}地址上没有应答"


def _not_probed_reason(device: CustomDevice, *, has_output_channel: bool) -> str:
    """没有探测小节时的那一句（**与三档并列的单源**，不是另写一套话术）。

    排序：先判总线——非 I2C 件**不管勾没勾通道**都出不来小节（那是这一版的能力
    边界，学生该知道的是这条，而不是"你没勾串口"）。
    """
    if device.bus != BUS_I2C:
        return NOT_PROBED_NOT_I2C
    assert not has_output_channel, "I2C 件 + 有通道却没出小节：判据 `_probes` 漂了"
    return NOT_PROBED_NO_CHANNEL


def _hex2(value: int | None) -> str:
    """一个字节 → `0xNN`（大写两位）；None = 空串（不编一个 0x00 出来）。"""
    return f"0x{value:02X}" if value is not None else ""
