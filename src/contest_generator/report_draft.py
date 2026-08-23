"""随工程生成「设计报告草稿」—— 确定性模板层 + LLM 文本注入层。

工单 report-draft-demo/02：生成工程时可选附带 设计报告草稿.md。render_report_draft
是纯函数（平台 / 板名 / 依赖展开后的 manifest 集 / LLM 文本 / 绑定解析结果 /
多实例计划 → 完整报告草稿文本），LLM 文本是入参（生成侧先产出、再传入，本
模块不做任何 LLM 调用——骨架先例）。

章节结构（确定性章节全渲染，LLM 层只有两节）：
- 工程概览：平台 / 板名（板名取不到不显示行）；
- 系统框图：依赖树（文本层次图，manifest 序即依赖先于使用者）+ 引脚连接表；
- 模块选型表：slug / 描述 / 依赖；
- 引脚分配表：与 README「引脚接线表」同源（复用 readme._pin_rows，绑定覆盖
  与多实例行口径一致），表尾固定尾注——防漂移由结构测试钉住；
- 测试记录模板：验证顺序与 README「验证顺序清单」同源（复用
  readme.sort_verification_order，bring-up 前置）；
- 系统方案论证 / 软件流程设计：LLM 文本注入（report_draft_text 入参）。

report_draft_text 契约 = LLM 结构化输出 {rationale, workflow} 顺序拼接的
文本：按 `\\n\\n` 分段，最后一段 = 软件流程，其余段 = 方案论证（llm.py 提示词
约束 workflow 为最后一段且内部不用空行）；空文本 = 两节中文占位提示（报告仍
渲染，不缺失章节、不阻断生成）。utf-8、尾部换行、不含时间戳——同一输入两次
调用产出逐字节一致。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Sequence

from .manifest import ModuleManifest
from .readme import (
    PLATFORM_TITLES,
    _append_pin_table,
    sort_verification_order,
)

if TYPE_CHECKING:
    from .pin_bindings import ResolvedBinding
    from .selection import ExpandedInstance

# 报告草稿输出文件名（生成写侧单源，generator 消费）
REPORT_DRAFT_FILENAME = "设计报告草稿.md"

# LLM 节空文本占位（spec 失败策略逐字规定：报告仍写、LLM 节中文占位）
PLACEHOLDER = "本节 AI 生成失败，请手动补充"

# 报告头部声明（草稿性质 + 提交前修订提醒）
_HEADER = """# 设计报告草稿

> 本报告由生成器按工程配置确定性渲染 + AI 方案文本组合而成，为草稿；
> 提交前请按实际电路、实测数据与赛题要求核对修订。
"""


def render_report_draft(
    platform: str,
    board_name: str | None,
    manifests: Sequence[ModuleManifest],
    report_draft_text: str = "",
    resolved_bindings: Sequence[ResolvedBinding] | None = None,
    instance_plans: Mapping[str, Sequence[ExpandedInstance]] | None = None,
) -> str:
    """渲染设计报告草稿完整文本（确定性模板 + LLM 文本注入）。

    report_draft_text = LLM 结构化输出 {rationale, workflow} 顺序拼接文本
    （按 `\\n\\n` 分段，最后一段 = 软件流程，其余 = 方案论证）；空 = 两节占位。
    resolved_bindings / instance_plans = 引脚分配表同源入参（README 口径：
    绑定覆盖生效引脚 / 多实例每实例一行），缺省 = 声明默认值（README 缺省
    路径一致）。返回文本恒以单个尾部换行收尾（幂等——同输入两次调用逐字节
    一致）。
    """
    rationale, workflow = _split_llm_text(report_draft_text)
    lines: list[str] = [_HEADER.rstrip("\n")]

    # 工程概览
    lines.append("")
    lines.append("## 工程概览")
    lines.append("")
    lines.append(f"- 平台：{PLATFORM_TITLES.get(platform, platform)}")
    if board_name:
        lines.append(f"- 开发板：{board_name}")

    # 系统框图：依赖树（文本层次图，缩进 = 依赖层级）+ 引脚连接表（与 README
    # 同源）
    lines.append("")
    lines.append("## 系统框图")
    lines.append("")
    lines.append("依赖树（缩进 = 依赖层级，依赖先于使用者）：")
    depths = _dependency_depths(manifests)
    for manifest in manifests:
        prefix = "  " * depths[manifest.slug]
        if manifest.dependencies:
            lines.append(
                f"{prefix}- {manifest.slug}：{manifest.description}"
                f"（依赖：{'、'.join(manifest.dependencies)}）"
            )
        else:
            lines.append(f"{prefix}- {manifest.slug}：{manifest.description}")
    lines.append("")
    lines.append("引脚连接：")
    _append_pin_table(lines, platform, manifests, resolved_bindings, instance_plans)

    # 模块选型表
    lines.append("## 模块选型表")
    lines.append("")
    lines.append("| 模块 | 描述 | 依赖 |")
    lines.append("|---|---|---|")
    for manifest in manifests:
        deps = "、".join(manifest.dependencies) if manifest.dependencies else ""
        lines.append(f"| {manifest.slug} | {manifest.description} | {deps} |")
    lines.append("")

    # 引脚分配表（与 README「引脚接线表」同源，尾注同源）
    lines.append("## 引脚分配表")
    lines.append("")
    _append_pin_table(lines, platform, manifests, resolved_bindings, instance_plans)

    # 测试记录模板（验证顺序与 README「验证顺序清单」同源）
    lines.append("## 测试记录模板")
    lines.append("")
    lines.append("按顺序逐个验证，前一个过了再接下一个（与 README 验证顺序清单同源）：")
    for manifest in sort_verification_order(manifests):
        lines.append(f"- [ ] {manifest.slug} — {manifest.description}")
    lines.append("")

    # LLM 文本注入层（两节；空文本 = 占位，报告不缺失章节）
    lines.append("## 系统方案论证")
    lines.append("")
    lines.append(rationale if rationale else PLACEHOLDER)
    lines.append("")
    lines.append("## 软件流程设计")
    lines.append("")
    lines.append(workflow if workflow else PLACEHOLDER)

    # 恒以单个尾部换行收尾（幂等）
    return "\n".join(lines).rstrip("\n") + "\n"


def _dependency_depths(manifests: Sequence[ModuleManifest]) -> dict[str, int]:
    """依赖深度（框图缩进层级）：无依赖 = 0，其余 = 1 + 最长依赖链深度
    （DFS 后序保证依赖先于使用者，直接递推即可；依赖环已被生成门禁拦截）。"""
    depths: dict[str, int] = {}
    for manifest in manifests:
        depths[manifest.slug] = 1 + max(
            (depths[dep] for dep in manifest.dependencies if dep in depths),
            default=0,
        )
    return depths


def _split_llm_text(text: str) -> tuple[str, str]:
    """report_draft_text → (方案论证, 软件流程)：按 `\\n\\n` 分段，最后一段 =
    软件流程、其余 = 方案论证（契约见模块 docstring）；空 = 两段皆空；单段 /
    契约外输入 = 整段作论证、流程空（该节缺内容 → 调用方走占位降级）。"""
    if not text:
        return "", ""
    parts = text.split("\n\n")
    if len(parts) == 1:
        return parts[0], ""
    return "\n\n".join(parts[:-1]), parts[-1]
