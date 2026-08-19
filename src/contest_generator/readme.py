"""随工程生成「上手即战」README —— 纯确定性模板渲染，不吃 LLM。

工单 project-readme/01 + 02 + 03：生成工程时自动附带 README.md。render_readme
是纯函数（platform / 板名 / 依赖展开后的 manifest 集 / 绑定解析结果 / 多实例
计划 → 完整 README 文本），五章：工程概览 / 快速上手：编译 + 烧录 / 引脚接线表 /
模块清单与依赖 / 验证顺序清单。utf-8、尾部换行、不含时间戳——同一输入两次调用
产出逐字节一致。

快速上手章 = 平台静态步骤文本（QUICK_START_STEPS 固定话术预写，不做逐模块
拼装，生成不依赖 ccs_tools 探测结果）；验证顺序清单章 = 以 manifest 集顺序
（resolve_dependencies DFS 后序）为基底做稳定分区排序（BRING_UP_SLUGS 前置、
保持相互间依赖序，其余原序），渲染 checkbox 清单 + 固定引导语。

引脚接线章数据源 = 各模块该平台 manifest pins 声明：模块 / 角色（label 不同
时附注）/ 生效引脚（工单 03 起 = 绑定载荷覆盖值，否则声明默认值；多实例计划
每实例追加一行，角色 = 通道宏名、引脚 = 实例 pin）/ 说明（类型 + required
必接标记）。未声明 pins 的模块不硬猜，表尾固定尾注
（PIN_TABLE_FOOTNOTE 兜底声明）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Sequence

# manifest 是轻量模型模块（先例：既有运行时依赖），PinDeclaration 随
# ModuleManifest 同源引入；pin_bindings / selection 较重，仅注解需用
# → TYPE_CHECKING（selection.py 先例）。
from .manifest import ModuleManifest, PinDeclaration

if TYPE_CHECKING:
    from .pin_bindings import ResolvedBinding
    from .selection import ExpandedInstance, ScorePoint

# README 输出文件名（生成写侧单源，generator 消费）
README_FILENAME = "README.md"

# 平台 → 主控/工具链中文名（工程概览章静态映射；文案 = spec 逐字规定
# 「STM32F103C8T6 / Keil5」「TI MSPM0G3507 / CCS」，与 webapp 的
# PLATFORM_DISPLAY_NAMES（板身份全称，界面 chip）是两种展示文案，各自独立）
PLATFORM_TITLES = {
    "stm32": "STM32F103C8T6 / Keil5",
    "mspm0": "TI MSPM0G3507 / CCS",
}

# 引脚接线表尾注：未声明 pins 的模块不硬猜，其余外设引脚以工程内配置文件
# 为准（pin_config.h = stm32 板级引脚单源；mspm0.syscfg = mspm0 外设布局）
PIN_TABLE_FOOTNOTE = (
    "其余外设引脚以工程内 pin_config.h（stm32）/ mspm0.syscfg 为准"
)

# 快速上手章：平台静态步骤文本（固定话术预写，不做逐模块拼装；纯静态文本，
# 生成不依赖 ccs_tools 探测结果，与是否写 makefile 无关）。文案 = 工单逐字
# 规定：mspm0 = CCS 打开工程/构建/下载；stm32 = Keil5 打开 uvprojx/编译/
# ST-Link 下载。未知平台（生成前置校验已拦截）缺省空元组。
QUICK_START_STEPS: dict[str, tuple[str, ...]] = {
    "stm32": (
        "用 Keil MDK（uVision5）打开工程：双击 user/Project.uvprojx",
        "编译：点击 Build（Project → Build Target，或按 F7）生成可烧录固件",
        "烧录：接好 ST-Link，点击 Download（或按 F8）下载到 STM32F103C8T6",
    ),
    "mspm0": (
        "用 TI Code Composer Studio（CCS）打开工程：File → Open Project 选择工程目录",
        "构建：点击 Build（或按 Ctrl+B）生成可烧录固件",
        "下载：接好调试器，点击 Debug（或按 F11）下载到 MSPM0G3507",
    ),
}

# 验证顺序清单章：bring-up 模块（先把最小系统点亮的外设核心）固定前置，其余
# 保持原序。前置组内保持相互间依赖序——manifests 已按 resolve_dependencies
# DFS 后序（依赖先于使用者）排列，稳定分区天然保住 delay 在 led_beep 前等序。
BRING_UP_SLUGS = ("delay", "debug_uart", "led", "led_beep")

# 验证清单固定引导语（工单逐字规定）
VERIFICATION_GUIDE = "按顺序逐个验证，前一个过了再接下一个"


def sort_verification_order(
    manifests: Sequence[ModuleManifest],
) -> list[ModuleManifest]:
    """验证顺序清单的稳定分区排序：bring-up 模块（BRING_UP_SLUGS）前置、
    保持相互间相对序（= 输入依赖序，依赖先于使用者），其余模块保持原序。

    输入 = resolve_dependencies DFS 后序的 manifest 集，故前置组内直接保持
    相对序即可满足「delay 在 led_beep 前」等依赖序；无 bring-up 模块 =
    原序不变；空集 = 空列表（不崩）。
    """
    bring_up = [m for m in manifests if m.slug in BRING_UP_SLUGS]
    others = [m for m in manifests if m.slug not in BRING_UP_SLUGS]
    return [*bring_up, *others]


def render_readme(
    platform: str,
    board_name: str | None,
    manifests: Sequence[ModuleManifest],
    resolved_bindings: Sequence[ResolvedBinding] | None = None,
    instance_plans: Mapping[str, Sequence[ExpandedInstance]] | None = None,
    score_points: Sequence[ScorePoint] | None = None,
) -> str:
    """渲染工程 README 完整文本（五章，确定性模板）。

    manifests = 依赖展开后的 manifest 集（顺序 = resolve_dependencies DFS
    后序，依赖先于使用者——模块清单章按此顺序渲染；验证顺序清单章在其上做
    bring-up 前置的稳定分区）。板名取不到传 None = 工程概览章不显示板名行
    （生成方已优雅降级，不阻断生成）。快速上手章 = 平台静态步骤文本，不依赖
    模块集。引脚接线章（工单 03 起）：
    - 生效引脚 = resolved_bindings 覆盖值，否则声明默认值（两平台统一；未绑
      角色保持 decl.default，绑定只改 pin 值，不新增行、不改行序）；
    - instance_plans（dict[slug, ExpandedInstance…]）每实例追加一行：角色 =
      通道宏名（LED_RED / LED_1…）、引脚 = 实例 pin，追加在对应模块声明行之后；
    - 两者缺省 / 空 = 工单 01/02 现状逐字节不变（回归护栏）。
    未声明 pins 的模块不硬猜，表尾固定尾注。
    返回文本恒以单个尾部换行收尾（幂等——同输入两次调用逐字节一致）。
    """
    lines: list[str] = []
    lines.append("# 工程说明")
    lines.append("")
    lines.append("## 工程概览")
    lines.append("")
    lines.append(f"- 平台：{PLATFORM_TITLES.get(platform, platform)}")
    if board_name:
        lines.append(f"- 开发板：{board_name}")
    lines.append("")

    lines.append("## 快速上手：编译 + 烧录")
    lines.append("")
    for step in QUICK_START_STEPS.get(platform, ()):
        lines.append(step)
    lines.append("")

    lines.append("## 引脚接线表")
    lines.append("")
    rows = _pin_rows(platform, manifests, resolved_bindings, instance_plans)
    if rows:
        lines.append("| 模块 | 角色 | 引脚 | 说明 |")
        lines.append("|---|---|---|---|")
        for slug, role, pin, remark in rows:
            lines.append(f"| {slug} | {role} | {pin} | {remark} |")
    else:
        lines.append("本工程所选模块未声明引脚接线。")
    lines.append("")
    lines.append(f"> {PIN_TABLE_FOOTNOTE}")
    lines.append("")

    lines.append("## 模块清单与依赖")
    lines.append("")
    for manifest in manifests:
        if manifest.dependencies:
            lines.append(
                f"- {manifest.slug}：{manifest.description}"
                f"（依赖：{'、'.join(manifest.dependencies)}）"
            )
        else:
            lines.append(f"- {manifest.slug}：{manifest.description}")
    lines.append("")

    if score_points:
        lines.append("## 评分点验收清单")
        lines.append("")
        lines.append("| 编号 | 分区 | 分值 | 原文句子 | 描述 |")
        lines.append("|---|---|---|---|---|")
        for row in _score_point_rows(score_points):
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    lines.append("## 验证顺序清单")
    lines.append("")
    lines.append(VERIFICATION_GUIDE)
    lines.append("")
    for manifest in sort_verification_order(manifests):
        lines.append(f"- [ ] {manifest.slug} — {manifest.description}")

    # 恒以单个尾部换行收尾（幂等）：rstrip 去尾部空行再补一个 \n——空 manifest
    # 等尾段无内容时也不会留下多余空行，同输入两次调用逐字节一致。
    return "\n".join(lines).rstrip("\n") + "\n"


def _pin_rows(
    platform: str,
    manifests: Sequence[ModuleManifest],
    resolved_bindings: Sequence[ResolvedBinding] | None = None,
    instance_plans: Mapping[str, Sequence[ExpandedInstance]] | None = None,
) -> list[tuple[str, str, str, str]]:
    """引脚接线表行（模块 slug / 角色 / 生效引脚 / 说明）。

    角色列 = 声明 id，label 不同时附注（如 `KEY_START（启动按键）`；parse 侧
    已把 label==id 归一为空串，非空 label 必为附注形态）；生效引脚 = 绑定载荷
    覆盖值（resolved_bindings 给 (slug, decl.id) → 生效 pin），否则声明默认值
    ——两平台统一，绑定只改 pin 值，不新增行、不改行序（行顺序 = manifest
    顺序 × pins 声明顺序，确定性）；说明 = 类型 + required 必接标记。多实例
    计划（instance_plans[slug]）每实例追加一行：角色 = 通道宏名（LED_RED /
    LED_1…）、引脚 = 实例 pin、说明 = 模块首个声明的类型（仅类型，不带必接
    标记——必接是角色声明属性，不随实例通道继承；未声明 pins 的模块 = 空串）
    ——追加在对应模块声明行之后。未声明 pins 的模块不产生声明行（不硬猜），
    表尾尾注兜底。
    """
    bindings: dict[tuple[str, str], str] = {}
    if resolved_bindings:
        bindings = {(b.slug, b.declaration.id): b.pin for b in resolved_bindings}
    plans = instance_plans or {}

    rows: list[tuple[str, str, str, str]] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue  # 无该平台版本条目由生成门禁先报，渲染侧跳过
        for decl in entry.pins:
            role = f"{decl.id}（{decl.label}）" if decl.label else decl.id
            pin = bindings.get((manifest.slug, decl.id), decl.default)
            rows.append((manifest.slug, role, pin, _pin_remark(decl)))
        inst_remark = entry.pins[0].type if entry.pins else ""
        for inst in plans.get(manifest.slug, ()):
            rows.append((manifest.slug, inst.macro, inst.pin, inst_remark))
    return rows


def _pin_remark(decl: PinDeclaration) -> str:
    """说明列 = 类型 + required 必接标记（仅声明行；实例行只带类型，见
    _pin_rows）。"""
    return decl.type + ("（必接）" if decl.required else "")


def _score_point_rows(
    score_points: Sequence[ScorePoint],
) -> list[tuple[str, str, str, str, str]]:
    """评分点表格行：编号 / 分区 / 分值 / 题面句号引用 / 描述。"""
    rows: list[tuple[str, str, str, str, str]] = []
    for point in score_points:
        rows.append(
            (
                point.id,
                _score_part_label(point.part),
                _score_value_text(point.score),
                _sentence_refs_text(point.sentence_refs),
                point.description,
            )
        )
    return rows


def _score_part_label(part: str) -> str:
    if part == "basic":
        return "基础"
    if part == "development":
        return "发挥"
    return "未分区"


def _score_value_text(score: float | None) -> str:
    if score is None:
        return "未标分"
    return f"{score:g} 分"


def _sentence_refs_text(refs: Sequence[int]) -> str:
    if not refs:
        return "未关联原文"
    return "句子 " + "、".join(str(ref) for ref in refs)
