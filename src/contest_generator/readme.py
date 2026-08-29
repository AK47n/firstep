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

import re
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

# 引脚接线表章节标题（渲染与解析共同的定位锚点：parse_pin_table 用此锚恢复
# 同源 rows——工单 task-wiring-diagram/05，单一出处防标题漂移）
PIN_TABLE_HEADING = "## 引脚接线表"

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

    lines.append(PIN_TABLE_HEADING)
    lines.append("")
    _append_pin_table(lines, platform, manifests, resolved_bindings, instance_plans)

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


def _append_pin_table(
    lines: list[str],
    platform: str,
    manifests: Sequence[ModuleManifest],
    resolved_bindings: Sequence[ResolvedBinding] | None = None,
    instance_plans: Mapping[str, Sequence[ExpandedInstance]] | None = None,
) -> None:
    """引脚接线表（表头 + 数据行 + 空回退文案 + 尾注）追加进 lines。

    README「引脚接线表」与报告草稿「系统框图·引脚连接 / 引脚分配表」共用
    （工单 report-draft-demo/02 单一出处，防漂移）——行数据源 = _pin_rows，
    本函数只负责表格外壳（含无行时的占位句与固定尾注）。
    """
    rows = _pin_rows(platform, manifests, resolved_bindings, instance_plans)
    if rows:
        lines.append("| 模块 | 角色 | 引脚 | 说明 |")
        lines.append("|---|---|---|---|")
        for row in rows:
            lines.append(_pin_row_text(row))
    else:
        lines.append("本工程所选模块未声明引脚接线。")
    lines.append("")
    lines.append(f"> {PIN_TABLE_FOOTNOTE}")
    lines.append("")


def _pin_row_text(row: tuple[str, str, str, str]) -> str:
    """单行引脚表（行格式单一出处：README / 报告草稿 / LLM 引脚表摘要共用，
    改列格式只动这里）。"""
    slug, role, pin, remark = row
    return f"| {slug} | {role} | {pin} | {remark} |"


def _row_role_text(role_id: str, role_label: str) -> str:
    """角色列文本：label 非空附注（如 `KEY_START（启动按键）`），否则裸 id。

    单一出处——README 接线表（_pin_rows）与接线快照行（wiring.wiring_rows）
    共用，防两端角色文本漂移（工单 task-wiring-diagram/01）。
    """
    return f"{role_id}（{role_label}）" if role_label else role_id


def _pin_row_items(
    platform: str,
    manifests: Sequence[ModuleManifest],
    resolved_bindings: Sequence[ResolvedBinding] | None = None,
    instance_plans: Mapping[str, Sequence[ExpandedInstance]] | None = None,
) -> list[tuple[str, str, str, str, str]]:
    """引脚接线行结构化推导（slug / role_id / role_label / pin / remark）。

    接线表与接线快照的**同源单一推导**（工单 task-wiring-diagram/01：图上
    不会出现与 README 表格矛盾的线）：role_id = 声明 id（实例行 = 通道宏名）、
    role_label = 声明 label（parse 侧已把 label==id 归一为空串；实例行空）、
    pin = 绑定载荷覆盖值否则声明默认值（实例行 = 实例 pin）、remark = 类型 +
    required 必接标记（实例行 = 模块首个声明类型，未声明 pins = 空串）。行序 =
    manifest 顺序 × pins 声明顺序，确定性；多实例行追加在对应模块声明行之后；
    未声明 pins 的模块不产生声明行（不硬猜）。
    """
    bindings: dict[tuple[str, str], str] = {}
    if resolved_bindings:
        bindings = {(b.slug, b.declaration.id): b.pin for b in resolved_bindings}
    plans = instance_plans or {}

    items: list[tuple[str, str, str, str, str]] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue  # 无该平台版本条目由生成门禁先报，渲染侧跳过
        for decl in entry.pins:
            pin = bindings.get((manifest.slug, decl.id), decl.default)
            items.append(
                (manifest.slug, decl.id, decl.label, pin, _pin_remark(decl))
            )
        inst_remark = entry.pins[0].type if entry.pins else ""
        for inst in plans.get(manifest.slug, ()):
            items.append((manifest.slug, inst.macro, "", inst.pin, inst_remark))
    return items


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
    表尾尾注兜底。行推导在 _pin_row_items（与接线快照同源）。
    """
    return [
        (slug, _row_role_text(role_id, role_label), pin, remark)
        for slug, role_id, role_label, pin, remark in _pin_row_items(
            platform, manifests, resolved_bindings, instance_plans
        )
    ]


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


# ---------------------------------------------------------------------------
# 引脚接线表解析（工单 task-wiring-diagram/05：旧工程无接线快照时，从 README
# 恢复 rows——README 表由 _pin_row_text 渲染（与快照同一推导 _pin_row_items），
# 本函数是其文本逆操作：同源恢复，不做任何猜测）
# ---------------------------------------------------------------------------

_PIN_TABLE_HEADER_CELLS = ("模块", "角色", "引脚", "说明")


def _table_cells(line: str) -> list[str]:
    """表格行 → 列值（strip 首尾管道，按 | 拆分，去空格）；非 4 列表格行
    由调用方按上下文丢弃。"""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    return [c.strip() for c in stripped.strip("|").split("|")]


def _is_header_row(cells: list[str]) -> bool:
    return len(cells) == 4 and tuple(cells) == _PIN_TABLE_HEADER_CELLS


def _is_separator_row(cells: list[str]) -> bool:
    """markdown 分隔行（---|---|）：全列由 -/: 组成。"""
    return len(cells) == 4 and all(
        not c.replace("-", "").replace(":", "").strip() for c in cells
    )


def _split_role(role_text: str) -> tuple[str, str]:
    """角色列文本 → (role_id, role_label)：渲染侧 `id（label）` 合成（见
    _row_role_text），无 label = 裸 id。

    label==id（如 `LED（LED）`）归一为空串——与 manifest 解析侧同一规则
    （标志性产物该形态理论不可达，解析侧防御兜底，保「非空 label 必为附注
    形态」契约跨输入成立；评审打磨：工单 task-wiring-diagram/05）。
    """
    m = re.fullmatch(r"(.+)（(.+)）", role_text)
    if m:
        role_id, role_label = m.group(1), m.group(2)
        return (role_id, "") if role_label == role_id else (role_id, role_label)
    return role_text, ""


def parse_pin_table(text: str) -> list[dict] | None:
    """README 引脚接线表 → rows（与接线快照行同形：slug/role/role_id/
    role_label/pin/remark）。

    只在 `{PIN_TABLE_HEADING}` 章节段内解析：先表头（模块/角色/引脚/说明），
    后数据行（跳过 ---| 分隔行；列数不足 / slug 或 pin 空的坏行丢弃其余
    保留）；段外同形表格（报告草稿「引脚分配表」等）不误收。**同源**：解析
    即恢复生成时同一推导的输出（含多实例通道行与 label 附注），图上不会出现
    表格之外的线。无表格段 / 表头缺失 / 无有效数据行 → None（调用方按空
    处理，维持既有退化）。
    """
    rows: list[dict] = []
    seen_heading = False
    collecting = False
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if collecting:
                break  # 表格段结束（下一章标题）
            seen_heading = stripped == PIN_TABLE_HEADING
            continue
        if not seen_heading:
            continue
        if collecting:
            if stripped.startswith(">"):
                break  # 尾注行（PIN_TABLE_FOOTNOTE）＝表段结束
            cells = _table_cells(stripped)
            if not cells:
                continue
            if _is_separator_row(cells):
                continue
            if len(cells) != 4:
                continue
            slug, role_text, pin, remark = cells
            if not slug or not pin:
                continue
            role_id, role_label = _split_role(role_text)
            rows.append(
                {
                    "slug": slug,
                    "role": role_text,
                    "role_id": role_id,
                    "role_label": role_label,
                    "pin": pin,
                    "remark": remark,
                }
            )
        else:
            if _is_header_row(_table_cells(stripped)):
                collecting = True
    return rows if rows else None
