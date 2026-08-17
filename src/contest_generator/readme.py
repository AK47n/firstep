"""随工程生成「上手即战」README —— 纯确定性模板渲染，不吃 LLM。

工单 project-readme/01：生成工程时自动附带 README.md。render_readme 是纯函数
（platform / 板名 / 依赖展开后的 manifest 集 → 完整 README 文本），本工单三章：
工程概览 / 引脚接线表 / 模块清单与依赖。utf-8、尾部换行、不含时间戳——同一
输入两次调用产出逐字节一致；快速上手 / 验证顺序清单章 = 后续工单范围。

引脚接线章数据源 = 各模块该平台 manifest pins 声明：模块 / 角色（label 不同
时附注）/ 生效引脚（本工单 = 声明默认值，绑定覆盖 = 工单 02 范围）/ 说明
（类型 + required 必接标记）。未声明 pins 的模块不硬猜，表尾固定尾注
（PIN_TABLE_FOOTNOTE 兜底声明，另两章同源渲染）。
"""

from __future__ import annotations

from typing import Sequence

from .manifest import ModuleManifest

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


def render_readme(
    platform: str,
    board_name: str | None,
    manifests: Sequence[ModuleManifest],
) -> str:
    """渲染工程 README 完整文本（三章，确定性模板）。

    manifests = 依赖展开后的 manifest 集（顺序 = resolve_dependencies DFS
    后序，依赖先于使用者——模块清单章按此顺序渲染）。板名取不到传 None =
    工程概览章不显示板名行（生成方已优雅降级，不阻断生成）。引脚接线章取各
    模块该平台 pins 声明的默认引脚；未声明 pins 的模块不硬猜，表尾固定尾注。
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

    lines.append("## 引脚接线表")
    lines.append("")
    rows = _pin_rows(platform, manifests)
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

    # 恒以单个尾部换行收尾（幂等）：rstrip 去尾部空行再补一个 \n——空 manifest
    # 等尾段无内容时也不会留下多余空行，同输入两次调用逐字节一致。
    return "\n".join(lines).rstrip("\n") + "\n"


def _pin_rows(
    platform: str, manifests: Sequence[ModuleManifest]
) -> list[tuple[str, str, str, str]]:
    """引脚接线表行（模块 slug / 角色 / 生效引脚 / 说明）。

    角色列 = 声明 id，label 不同时附注（如 `KEY_START（启动按键）`；parse 侧
    已把 label==id 归一为空串，非空 label 必为附注形态）；生效引脚 = 声明默认
    值（绑定覆盖 = 工单 02 范围）；说明 = 类型 + required 必接标记。未声明
    pins 的模块不产生行（不硬猜），表尾尾注兜底。行顺序 = manifest 顺序 ×
    平台条目 pins 声明顺序（确定性）。
    """
    rows: list[tuple[str, str, str, str]] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue  # 无该平台版本条目由生成门禁先报，渲染侧跳过
        for decl in entry.pins:
            role = f"{decl.id}（{decl.label}）" if decl.label else decl.id
            remark = decl.type + ("（必接）" if decl.required else "")
            rows.append((manifest.slug, role, decl.default, remark))
    return rows
