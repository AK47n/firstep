"""多实例渲染层（module-multi-instance/03）：按 slug 注册的渲染 hook + led 首例。

照 patchers.PatcherRegistry 先例：通用层只认识 slug，led 的「通道宏命名 +
引脚渲染」具体语义全在 led hook 里（beep/key/motor 以后挂各自的渲染 hook，
不动这套机制——spec User Story 11）。渲染输入 = selection.expand_instances 的
计划（02 纯函数，同输入同输出），渲染输出 = 生成工程里的 led_instances.h
（stm32 工程根 / mspm0 modules/led/code/）+ mspm0 syscfg 新实例。骨架侧经
instance_interface_blocks 把同一份渲染文本喂进接口块——LLM 见到的通道宏清单
= 工程里实际生成的宏，静态自检不误占位。

单实例（空计划）零写侧变化：stm32 母版默认 led_instances.h 随 copytree 就位、
mspm0 库内默认随模块复制就位——渲染层不写。默认文本与盘上默认文件的逐字节
一致性由 tests/test_module_multi_instance.py 钉死（渲染常量漂移即红）。

写盘纪律（pinwriter 先例）：mspm0.syscfg 只碰 $assign 引号值 + 追加新实例块，
其余行逐字节保留；行尾 CRLF 原样接回。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from .boards import Board, board_for_platform
from .manifest import ModuleManifest
from .patchers import UnknownPlatformError
from .pinwriter import MSPM0_SYSCFG_FILENAME
from .platforms import PLATFORM_MSPM0, PLATFORM_STM32
from .selection import ExpandedInstance, ModuleInstance, expand_instances

LED_SLUG = "led"
LED_INSTANCES_HEADER = "led_instances.h"

# stm32 落工程根（与 pin_config.h 同级，ml_libs 经 IncludePath 解析到）；mspm0
# 落 led.c 同目录（引号 include 自目录优先，零 include path 改动）
MSPM0_LED_HEADER_REL = "modules/led/code/led_instances.h"

# 单实例默认 led_instances.h 全文（与盘上默认文件逐字节一致——stm32 母版根 /
# mspm0 库内 modules/led/code/，测试钉死）。stm32 默认引脚取 pin_config.h 宏
# （接线单源，config.LED_* 绑定照旧驱动三内置灯）；mspm0 默认 1 通道 PA15
# （LED_YELLOW/GREEN=1/2 越界钳回首通道，与旧三别名同脚行为一致）。
STM32_DEFAULT_LED_INSTANCES = """/* led_instances.h —— LED 通道宏 + 每通道 (port, pin) 表（生成器多实例渲染产物，
 * module-multi-instance/03）。选中 led 且带实例清单时生成器按实例计划覆写本文件
 * （工程根、与 pin_config.h 同级）；本文件 = 单实例默认：三通道 PC13/14/15，
 * 引脚取 pin_config.h（接线单源——改板载 LED 引脚只改 pin_config.h）。 */
#ifndef _led_instances_h_
#define _led_instances_h_

#define LED_CHANNEL_COUNT 3

// 通道索引（led_init/led_on/led_off/led_toggle 的 channel 实参；两平台一致：
// RED=0 / YELLOW=1 / GREEN=2 / LED_1=3 …；越界自动钳回首通道）
#define LED_RED     0
#define LED_YELLOW  1
#define LED_GREEN   2

// 每通道 (port, pin)：ml_led.c 读 LED_PIN_TABLE 建表
#define LED_CHANNEL_0_PORT LED_PORT
#define LED_CHANNEL_0_PIN  LED_RED_PIN
#define LED_CHANNEL_1_PORT LED_PORT
#define LED_CHANNEL_1_PIN  LED_YELLOW_PIN
#define LED_CHANNEL_2_PORT LED_PORT
#define LED_CHANNEL_2_PIN  LED_GREEN_PIN

#define LED_PIN_TABLE { {LED_CHANNEL_0_PORT, LED_CHANNEL_0_PIN}, {LED_CHANNEL_1_PORT, LED_CHANNEL_1_PIN}, {LED_CHANNEL_2_PORT, LED_CHANNEL_2_PIN} }

// 便捷控制宏（LED 一脚接地、另一脚接 MCU 引脚：拉电流接法，led_on = 亮）
#define LED_RED_ON()     led_on(LED_RED)
#define LED_RED_OFF()    led_off(LED_RED)
#define LED_YELLOW_ON()  led_on(LED_YELLOW)
#define LED_YELLOW_OFF() led_off(LED_YELLOW)
#define LED_GREEN_ON()   led_on(LED_GREEN)
#define LED_GREEN_OFF()  led_off(LED_GREEN)

#endif
"""

MSPM0_DEFAULT_LED_INSTANCES = """/* led_instances.h —— LED 通道宏 + 每通道 (port, pin) 表（生成器多实例渲染产物，
 * module-multi-instance/03）。选中 led 且带实例清单时生成器按实例计划覆写本文件
 * （led.c 同目录，随模块复制进工程）；本文件 = 单实例默认：地猛星 1 个用户 LED
 * （PA15，LED_BEEP 组——改引脚改 syscfg 不改这里）。 */
#ifndef _led_instances_h_
#define _led_instances_h_

#define LED_CHANNEL_COUNT 1

// 通道索引（led_init/led_on/led_off/led_toggle 的 channel 实参；两平台一致：
// RED=0 / YELLOW=1 / GREEN=2 / LED_1=3 …；越界自动钳回首通道——单实例下
// YELLOW/GREEN 仍指 PA15，与旧三别名同脚行为一致）
#define LED_RED     0
#define LED_YELLOW  1
#define LED_GREEN   2

// 每通道 (port, pin)：led.c 读 LED_PIN_TABLE 建表（LED_BEEP 宏由 SysConfig
// 按 mspm0.syscfg 生成）
#define LED_CHANNEL_0_PORT LED_BEEP_PORT
#define LED_CHANNEL_0_PIN  LED_BEEP_LED_PIN

#define LED_PIN_TABLE { {LED_CHANNEL_0_PORT, LED_CHANNEL_0_PIN} }

// 便捷控制宏（LED 一脚接地、另一脚接 MCU 引脚：拉电流接法，led_on = 亮）
#define LED_RED_ON()     led_on(LED_RED)
#define LED_RED_OFF()    led_off(LED_RED)
#define LED_YELLOW_ON()  led_on(LED_YELLOW)
#define LED_YELLOW_OFF() led_off(LED_YELLOW)
#define LED_GREEN_ON()   led_on(LED_GREEN)
#define LED_GREEN_OFF()  led_off(LED_GREEN)

#endif
"""

# syscfg $assign 行形态（syscfg_model._SYSCFG_ASSIGN_RE 同款，只服务于 LED_BEEP
# 通道 0 落点行——path 前置检查后逐组还原，head/tail/eol 原样保留）
_LED_BEEP_ASSIGN_RE = re.compile(
    r'^(?P<head>\s*(?P<path>LED_BEEP\.associatedPins\[0\]\.pin)\.\$assign\s*=\s*)'
    r'"(?P<pin>[A-Za-z0-9]+)"(?P<tail>.*?)(?P<eol>\r?\n)?$'
)


class InstanceRenderer(Protocol):
    """slug 级渲染 hook：实例计划 → 生成工程文件 / 骨架接口块。

    通用层（generate / build_skeleton_interfaces）只认识 slug 与计划，平台
    落点与命名语义归实现。
    """

    @property
    def managed_headers(self) -> frozenset[str]:
        """渲染接管文件（相对模块目录的 rel 路径）——生成工程里这些文件的内容
        由渲染决定，骨架接口块剔除库内基线文本（否则 LLM 同时看到默认与计划
        两份互相矛盾的通道宏）。"""
        ...

    def render(
        self,
        project_dir: Path,
        plan: Sequence[ExpandedInstance],
        platform: str,
    ) -> None: ...

    def inject_blocks(
        self, plan: Sequence[ExpandedInstance], platform: str
    ) -> list[str]: ...


class InstanceRenderRegistry:
    """slug -> 渲染 hook 的映射（照 patchers.PatcherRegistry 先例）。

    未注册 slug（非多实例模块）= 无渲染，get 返回 None——与平台注册表不同，
    多数模块本来就不需要渲染。
    """

    def __init__(self) -> None:
        self._renderers: dict[str, InstanceRenderer] = {}

    def register(self, slug: str, renderer: InstanceRenderer) -> None:
        """注册渲染 hook；同 slug 重复注册以后者为准。"""
        self._renderers[slug] = renderer

    def get(self, slug: str) -> InstanceRenderer | None:
        return self._renderers.get(slug)


class LedInstanceRenderer:
    """led 渲染 hook（variant=color 首例）：通道宏 + (port, pin) 表 + syscfg。

    stm32：工程根 led_instances.h 覆写为计划内容（全通道具体 GPIO_x/Pin_y 对
    ——多实例实例脚是权威，config.LED_* 绑定只服务单实例默认）。mspm0：通道 0
    复用母版 LED_BEEP（计划脚 ≠ 现值时改写 $assign）、其余通道新 GPIO 实例
    LED_<实例号>（关联 pin $name LED<实例号>——SysConfig pin 名全局唯一判例——
    生成 <INSTANCE>_PORT / <INSTANCE>_LED<实例号>_PIN 宏）。
    空计划 = 单实例默认：不写任何文件（默认已随复制就位）。
    """

    @property
    def managed_headers(self) -> frozenset[str]:
        """mspm0 侧 led_instances.h 是库内默认（随模块复制）+ 渲染覆写的双态
        文件——接口块剔除基线文本，只注入渲染计划/默认通道宏块。"""
        return frozenset({"code/led_instances.h"})

    def render(
        self,
        project_dir: Path,
        plan: Sequence[ExpandedInstance],
        platform: str,
    ) -> None:
        if not plan:
            return  # 单实例默认：零写侧变化（默认文件已就位）
        if platform == PLATFORM_STM32:
            path = project_dir / LED_INSTANCES_HEADER
        elif platform == PLATFORM_MSPM0:
            path = project_dir / MSPM0_LED_HEADER_REL
        else:
            raise UnknownPlatformError(
                f"未知平台 {platform!r}，已注册的平台："
                f"{PLATFORM_STM32}, {PLATFORM_MSPM0}"
            )
        path.write_text(
            render_led_instances_text(plan, platform), encoding="utf-8"
        )
        if platform == PLATFORM_MSPM0:
            _write_syscfg_for_plan(project_dir, plan)

    def inject_blocks(
        self, plan: Sequence[ExpandedInstance], platform: str
    ) -> list[str]:
        """骨架 / 冒烟接口块：喂给 LLM 的通道宏清单 = 工程里实际生成的文件全文
        + 逐个初始化提示（静态自检只认函数名，宏名不参与占位判定）。"""
        text = render_led_instances_text(plan, platform)
        return [
            f"### 模块 led 通道宏（{LED_INSTANCES_HEADER} 生成内容）\n{text}\n"
            "（每个通道宏对应一个已配好引脚的 LED 实例，请在初始化序列中逐个"
            "调用 led_init(<通道宏>)）\n"
        ]


def default_render_registry() -> InstanceRenderRegistry:
    """默认注册表：led 是首个多实例模块（spec 首例），新模块多实例 = 这里加一条。"""
    registry = InstanceRenderRegistry()
    registry.register(LED_SLUG, LedInstanceRenderer())
    return registry


def expand_instance_plans(
    manifests: Sequence[ModuleManifest],
    instances: Mapping[str, Sequence[ModuleInstance]] | None,
    platform: str,
    board: Board | None = None,
) -> dict[str, tuple[ExpandedInstance, ...]]:
    """选中且声明 multi_instance 的模块 → (slug, 展开计划) 聚合（generate 与
    骨架注入同源入口）。

    无 instances 清单（或清单不含该 slug）= 空计划——单默认实例，渲染走默认
    文件、注入走默认通道宏（与 expand_instances 空清单契约一致）；未选中
    slug 的清单项忽略（请求层校验归 04）。非空清单需要板定义（默认脚分配）：
    board 缺省时现加载（board_for_platform，板数据缺失 = BoardError 500）——
    调用方已为绑定加载过板时显式传入，避免二次读盘。
    """
    payload = instances or {}
    plans: dict[str, tuple[ExpandedInstance, ...]] = {}
    for manifest in manifests:
        if manifest.multi_instance is None:
            continue
        entries = tuple(payload.get(manifest.slug, ()))
        if entries and board is None:
            board = board_for_platform(platform)
        if entries:
            assert board is not None, "实例展开需要板定义（board 缺失——装配层错误）"
            plans[manifest.slug] = expand_instances(
                manifest, entries, platform, board
            )
        else:
            plans[manifest.slug] = ()
    return plans


def render_instances(
    project_dir: Path,
    plans: Mapping[str, Sequence[ExpandedInstance]],
    platform: str,
    registry: InstanceRenderRegistry | None = None,
) -> None:
    """生成挂钩：对每个有渲染 hook 的选中模块调用 render（空计划 = 单实例默认，
    hook 自判零写侧变化）。"""
    registry = registry or default_render_registry()
    for slug, plan in plans.items():
        renderer = registry.get(slug)
        if renderer is not None:
            renderer.render(project_dir, plan, platform)


def instance_interface_blocks(
    plans: Mapping[str, Sequence[ExpandedInstance]],
    platform: str,
    registry: InstanceRenderRegistry | None = None,
) -> list[str]:
    """骨架 / 冒烟接口块注入：「生成了哪些通道宏」喂给 LLM（与渲染同源文本）。"""
    registry = registry or default_render_registry()
    blocks: list[str] = []
    for slug, plan in plans.items():
        renderer = registry.get(slug)
        if renderer is not None:
            blocks.extend(renderer.inject_blocks(plan, platform))
    return blocks


def managed_header_rels(
    plans: Mapping[str, Sequence[ExpandedInstance]],
    registry: InstanceRenderRegistry | None = None,
) -> frozenset[str]:
    """计划内 slug 的渲染 hook 声明的接管文件（相对模块目录 rel 路径）——模块
    接口块要剔除这些文件的库内基线文本（生成工程里的内容由渲染决定）。"""
    registry = registry or default_render_registry()
    managed: set[str] = set()
    for slug in plans:
        renderer = registry.get(slug)
        if renderer is not None:
            managed.update(renderer.managed_headers)
    return frozenset(managed)


def render_led_instances_text(
    plan: Sequence[ExpandedInstance], platform: str
) -> str:
    """实例计划 → led_instances.h 全文（纯函数，字符串进字符串出）。

    空计划 = 单实例默认（与盘上默认文件逐字节一致，测试钉死）；多实例 = 全
    通道按计划序：stm32 具体 (GPIO_x, Pin_y) 对、mspm0 通道 0 LED_BEEP 宏 +
    其余 LED_<实例号> 实例宏。通道索引两平台一致（RED=0 / YELLOW=1 /
    GREEN=2 / LED_1=3 …，02 命名规则产出）。
    """
    if platform == PLATFORM_STM32:
        return STM32_DEFAULT_LED_INSTANCES if not plan else _render_multi_stm32(plan)
    if platform == PLATFORM_MSPM0:
        return MSPM0_DEFAULT_LED_INSTANCES if not plan else _render_multi_mspm0(plan)
    raise UnknownPlatformError(
        f"未知平台 {platform!r}，已注册的平台：{PLATFORM_STM32}, {PLATFORM_MSPM0}"
    )


def _render_multi_stm32(plan: Sequence[ExpandedInstance]) -> str:
    """多实例 stm32 全文：全通道具体 (GPIO_x, Pin_y) 对（实例计划脚是权威——
    config.LED_* 角色绑定只服务单实例默认）。"""
    channel_lines = "".join(
        f"#define LED_CHANNEL_{i}_PORT {_stm32_port(entry.pin)}\n"
        f"#define LED_CHANNEL_{i}_PIN  {_stm32_pin(entry.pin)}\n"
        for i, entry in enumerate(plan)
    )
    return _render_multi_text(plan, channel_lines)


def _render_multi_mspm0(plan: Sequence[ExpandedInstance]) -> str:
    """多实例 mspm0 全文：通道 0 复用 LED_BEEP 宏、通道 k≥1 引用新 syscfg 实例
    LED_<实例号> 的 <INSTANCE>_PORT / <INSTANCE>_LED_PIN 宏（SysConfig 生成）。"""
    channel_lines = "".join(
        f"#define LED_CHANNEL_{i}_PORT {_mspm0_port_macro(entry)}\n"
        f"#define LED_CHANNEL_{i}_PIN  {_mspm0_pin_macro(entry)}\n"
        for i, entry in enumerate(plan)
    )
    return _render_multi_text(plan, channel_lines)


def _render_multi_text(
    plan: Sequence[ExpandedInstance], channel_lines: str
) -> str:
    """多实例全文骨架（双平台共用）：COUNT + 通道索引 + 通道表 + LED_PIN_TABLE
    + 每通道便捷宏。"""
    count = len(plan)
    entries = ", ".join(
        f"{{LED_CHANNEL_{i}_PORT, LED_CHANNEL_{i}_PIN}}" for i in range(count)
    )
    convenience = "".join(
        f"#define {entry.macro}_ON()     led_on({entry.macro})\n"
        f"#define {entry.macro}_OFF()    led_off({entry.macro})\n"
        for entry in plan
    )
    return (
        "/* led_instances.h —— 生成器多实例渲染产物（module-multi-instance/03）："
        "LED 通道宏 + 每通道 (port, pin) 表。改接线改这里（stm32：直接改"
        " GPIO_x/Pin_y 对；mspm0：改 syscfg 的 $assign）。 */\n"
        "#ifndef _led_instances_h_\n"
        "#define _led_instances_h_\n"
        "\n"
        f"#define LED_CHANNEL_COUNT {count}\n"
        "\n"
        "// 通道索引（led_init/led_on/led_off/led_toggle 的 channel 实参；"
        "两平台一致：RED=0 / YELLOW=1 / GREEN=2 / LED_1=3 …；越界自动钳回首通道）\n"
        + "".join(f"#define {entry.macro:<13}{i}\n" for i, entry in enumerate(plan))
        + "\n"
        "// 每通道 (port, pin)：驱动读 LED_PIN_TABLE 建表\n"
        + channel_lines
        + "\n"
        f"#define LED_PIN_TABLE {{ {entries} }}\n"
        "\n"
        "// 便捷控制宏（LED 一脚接地、另一脚接 MCU 引脚：拉电流接法，led_on = 亮）\n"
        + convenience
        + "#endif\n"
    )


def _stm32_port(pin: str) -> str:
    """PA0 → GPIO_A（ml_gpio GPIOn_enum）。"""
    assert (
        len(pin) >= 2 and pin[0] == "P" and pin[1].isalpha()
    ), f"非引脚名 {pin!r}（板数据漂移）"
    return "GPIO_" + pin[1]


def _stm32_pin(pin: str) -> str:
    """PA0 → Pin_0（ml_gpio Pinx_enum）。"""
    return "Pin_" + _digits(pin)


def _mspm0_port_macro(entry: ExpandedInstance) -> str:
    if entry.index == 1:
        return "LED_BEEP_PORT"
    return f"LED_{entry.index}_PORT"


def _mspm0_pin_macro(entry: ExpandedInstance) -> str:
    if entry.index == 1:
        return "LED_BEEP_LED_PIN"
    # 新实例的关联 pin $name = "LED<实例号>"（SysConfig 要求全局唯一，真机
    # 编译判例：同名 LED 撞 LED_BEEP 的 pin 名 → 4 error）→ 生成宏
    # LED_2_LED2_PIN 形态
    return f"LED_{entry.index}_LED{entry.index}_PIN"


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def rewrite_syscfg_for_led_instances(
    text: str, plan: Sequence[ExpandedInstance]
) -> str:
    """mspm0 多实例 syscfg 改写（纯函数）：通道 0 计划脚 ≠ 现值 → 改写
    LED_BEEP.associatedPins[0].pin.$assign；通道 1+ 追加 LED_<实例号> GPIO
    实例块（关联 pin $name LED → SysConfig 生成 <INSTANCE>_LED_PIN）。空计划
    原样返回（单实例零写侧变化）。其余行逐字节保留（行尾 CRLF 原样接回）。
    """
    if not plan:
        return text
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if "LED_BEEP.associatedPins[0].pin.$assign" not in line:
            continue
        m = _LED_BEEP_ASSIGN_RE.match(line)
        assert m is not None, "母版 mspm0.syscfg 的 LED_BEEP 落点行形态漂移"
        if m.group("pin") != plan[0].pin:
            lines[i] = (
                f'{m.group("head")}"{plan[0].pin}"'
                f'{m.group("tail")}{m.group("eol") or ""}'
            )
        break
    else:
        raise AssertionError(
            "母版 mspm0.syscfg 缺 LED_BEEP.associatedPins[0].pin.$assign 落点"
            "（母版漂移）"
        )

    eol = "\r\n" if "\r\n" in text else "\n"
    additions = [
        "// LED 多实例通道（module-multi-instance/03 渲染产物：实例名 LED_<实例号>，"
        "改引脚只改 $assign）" + eol
    ]
    for entry in plan[1:]:
        additions.append(
            _syscfg_instance_block(
                f"LED_{entry.index}", f"LED{entry.index}", entry.pin, eol
            )
        )
    # 原文缺尾换行时补一个（追加块不与末行粘连——判例：追加文本粘尾行）
    separator = "" if text.endswith(("\n", "\r")) else eol
    return "".join(lines) + separator + "".join(additions)


def _syscfg_instance_block(
    instance: str, pin_name: str, pin_assign: str, eol: str
) -> str:
    """单个 GPIO 实例块（与母版 LED_BEEP 同款配置：OUTPUT + CLEARED）。

    pin_name = associatedPins[0].$name，全局唯一（SysConfig 判例：多实例同
    pin 名 LED → Duplicate name 4 error）——LED2 形态，与实例名 LED_2 对应；
    pin_assign = 引脚名（$assign 引号值）。"""
    return (
        f"const {instance} = GPIO.addInstance();" + eol
        + f'{instance}.$name = "{instance}";' + eol
        + f"{instance}.associatedPins.create(1);" + eol
        + f'{instance}.associatedPins[0].$name        = "{pin_name}";' + eol
        + f'{instance}.associatedPins[0].direction    = "OUTPUT";' + eol
        + f'{instance}.associatedPins[0].initialValue = "CLEARED";' + eol
        + f'{instance}.associatedPins[0].pin.$assign  = "{pin_assign}";' + eol
    )


def _write_syscfg_for_plan(
    project_dir: Path, plan: Sequence[ExpandedInstance]
) -> None:
    """生成挂钩：读输出目录 syscfg、改写、文本有变化才落盘（不变不写）。"""
    path = project_dir / MSPM0_SYSCFG_FILENAME
    assert path.is_file(), f"mspm0 输出树缺 {MSPM0_SYSCFG_FILENAME}（母版漂移）"
    original = path.read_text(encoding="utf-8", newline="")
    rendered = rewrite_syscfg_for_led_instances(original, plan)
    if rendered != original:
        path.write_text(rendered, encoding="utf-8", newline="")
