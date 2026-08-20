"""修订影响分析与确定性 diff（工单 revise-deepen/02）。

**确定性 diff**：`compute_module_diff` 纯函数——新旧 slugs 集合差 → 增 / 删 /
不变清单（AI 只解释"为什么"，不负责"算差异"，spec 关键决策）。

**影响分析**：`build_impact_analysis` 把 LLM 输出解析校验为 ImpactAnalysis
（每条 Q&A 的影响结论 + 建议模块集）；`run_impact_analysis` 是完整编排——
LLM 调用（传输层自带重试）→ 解析 → diff → 平台警告重算（resolve_selection
复用）→ done 载荷。Q&A 以独立段注入（收敛循环先例：不并入题面）。

**错误契约**：任何结构 / 内容问题（缺数组、未知 slug、字段类型错）抛
ImpactError（400 中文，登记 errors.py）——模型输出不可信，宁可大声失败也
不带病进修订执行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .manifest import ManifestSummary
from .selection import PlatformWarning, resolve_selection

if TYPE_CHECKING:
    from .llm import LLM  # 仅类型注解（llm 运行时依赖本层，反向禁止）
    from .sse import SseEmitter


class ImpactError(ValueError):
    """影响分析输出非法（缺数组 / 未知 slug / 字段类型错），400 中文。"""


@dataclass(frozen=True)
class QaImpact:
    """单条新 Q&A 的影响结论（模型输出，域判决后）。

    qa_index = 新 Q&A 的序号（1 起，用户粘贴顺序）；requirement_refs = 受
    影响的功能需求描述（requirements 层的 requirement 文本，原样引用）；
    add / remove = 建议增删的模块 slug（库内）；reason = 中文理由。
    """

    qa_index: int
    requirement_refs: tuple[str, ...] = ()
    add: tuple[str, ...] = ()
    remove: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "qa_index": self.qa_index,
            "requirement_refs": list(self.requirement_refs),
            "add": list(self.add),
            "remove": list(self.remove),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ImpactAnalysis:
    """影响分析结果：逐条 Q&A 影响 + 建议模块集（完整集，diff 由工具算）。"""

    impacts: tuple[QaImpact, ...] = ()
    suggested_slugs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "impacts": [impact.to_dict() for impact in self.impacts],
            "suggested_slugs": list(self.suggested_slugs),
        }


@dataclass(frozen=True)
class ModuleDiff:
    """新旧模块集的确定性 diff（集合差，纯函数计算）。"""

    added: tuple[str, ...] = ()  # 新集新增（保持新集顺序）
    removed: tuple[str, ...] = ()  # 旧集移除（保持旧集顺序）
    unchanged: tuple[str, ...] = ()  # 交集（保持旧集顺序）

    def to_dict(self) -> dict[str, Any]:
        return {
            "added": list(self.added),
            "removed": list(self.removed),
            "unchanged": list(self.unchanged),
        }


def compute_module_diff(old_slugs: Sequence[str], new_slugs: Sequence[str]) -> ModuleDiff:
    """新旧 slugs 集合差 → 确定性 diff（纯函数，可内存直构测试）。

    增 / 删 / 不变分别保持输入顺序（新集序 / 旧集序）——稳定可复述；空集 /
    相同集 = 空 diff（不崩）。AI 不参与计算：spec「新旧模块集差异是确定性
    diff（集合差），AI 只负责解释为什么，不负责算差异」。
    """
    old_list = list(old_slugs)
    new_list = list(new_slugs)
    old_set = set(old_list)
    new_set = set(new_list)
    return ModuleDiff(
        added=tuple(slug for slug in new_list if slug not in old_set),
        removed=tuple(slug for slug in old_list if slug not in new_set),
        unchanged=tuple(slug for slug in old_list if slug in new_set),
    )


# ---------------------------------------------------------------------------
# 模型输出 → ImpactAnalysis 解释链（域判决单址，对照 build_module_selection）
# ---------------------------------------------------------------------------


def build_impact_analysis(
    raw: Mapping[str, Any], *, known_slugs: Sequence[str]
) -> ImpactAnalysis:
    """把模型输出的原始 JSON（llm 已解析为 dict）解析校验为 ImpactAnalysis。

    形状契约：
    {"impacts": [{"qa_index": N, "requirement_refs": [...], "add": [...],
      "remove": [...], "reason": "..."}], "suggested_slugs": [...]}

    校验：顶层对象；impacts 数组（qa_index 正整数、reason 非空字符串、
    add / remove 已知 slug、requirement_refs 字符串数组）；suggested_slugs
    数组且全部已知 slug（库外 = 幻觉大声失败，宁严勿假绿）。缺字段 = 补空
    （旧版本模型输出容忍），但 suggested_slugs 缺失 / 非数组 = 大声失败
    （diff 与修订执行必需）。
    """
    if not isinstance(raw, Mapping):
        raise ImpactError("影响分析输出必须是 JSON 对象")
    known = set(known_slugs)

    raw_impacts = raw.get("impacts", [])
    if not isinstance(raw_impacts, list):
        raise ImpactError("影响分析缺少 impacts 数组")
    impacts: list[QaImpact] = []
    for index, item in enumerate(raw_impacts, 1):
        if not isinstance(item, Mapping):
            raise ImpactError(f"影响分析第 {index} 条不是对象")
        qa_index = item.get("qa_index")
        if (
            not isinstance(qa_index, int)
            or isinstance(qa_index, bool)
            or qa_index < 1
        ):
            raise ImpactError(f"影响分析第 {index} 条的 qa_index 必须是正整数")
        reason = item.get("reason", "")
        if not isinstance(reason, str) or not reason.strip():
            raise ImpactError(f"影响分析第 {index} 条缺少理由（reason）")
        refs = item.get("requirement_refs", [])
        if not isinstance(refs, list) or any(not isinstance(r, str) for r in refs):
            raise ImpactError(f"影响分析第 {index} 条的 requirement_refs 必须是字符串数组")
        add = _slug_list(item.get("add"), known, f"影响分析第 {index} 条的 add")
        remove = _slug_list(
            item.get("remove"), known, f"影响分析第 {index} 条的 remove"
        )
        impacts.append(
            QaImpact(
                qa_index=qa_index,
                requirement_refs=tuple(refs),
                add=add,
                remove=remove,
                reason=reason.strip(),
            )
        )

    raw_slugs = raw.get("suggested_slugs")
    if not isinstance(raw_slugs, list) or any(
        not isinstance(slug, str) or not slug for slug in raw_slugs
    ):
        raise ImpactError("影响分析缺少 suggested_slugs 数组（模块 slug 字符串）")
    unknown = [slug for slug in raw_slugs if slug not in known]
    if unknown:
        raise ImpactError(
            "建议模块集含库外模块：" + "、".join(unknown) + " —— 请核对模块库"
        )
    return ImpactAnalysis(
        impacts=tuple(impacts), suggested_slugs=tuple(raw_slugs)
    )


def _slug_list(
    raw: Any, known: set[str], label: str
) -> tuple[str, ...]:
    """slug 数组解析（add / remove 共用）：非数组 / 非字符串 / 库外 → 大声失败。"""
    if raw is None:
        return ()
    if not isinstance(raw, list) or any(not isinstance(s, str) or not s for s in raw):
        raise ImpactError(f"{label} 必须是 slug 字符串数组")
    unknown = [slug for slug in raw if slug not in known]
    if unknown:
        raise ImpactError(f"{label} 含库外模块：" + "、".join(unknown))
    return tuple(raw)


# ---------------------------------------------------------------------------
# 编排：LLM 调用 → 解析 → diff → 平台警告 → done 载荷（对照 run_recommendation）
# ---------------------------------------------------------------------------


def run_impact_analysis(
    *,
    llm: LLM,
    problem_text: str,
    requirements: Sequence[Mapping[str, Any]],
    current_slugs: Sequence[str],
    manifest_summaries: Sequence[ManifestSummary],
    new_qa_text: str,
    platform: str,
    library_dir: Path,
    emit: SseEmitter,
) -> dict[str, Any]:
    """/api/revise/analyze 的两段编排（工单 02 第一段：分析）。

    影响分析（LLM，分钟级）→ 确定性 diff（集合差纯函数）→ 平台警告按建议
    模块集重算（resolve_selection 复用——缺版本 / 未验证 / 硬件绑定三类）。
    进度事件：impact_analyzing（LLM 调用开始）→ diff_ready（diff 就绪）。
    返回 done 载荷（终态由路由 emit.done 收尾，终态保证归运行器）：
    {"impacts": [...], "suggested_slugs": [...], "diff": {...},
    "warnings": [...], "platform": ...}——JSON 形状稳定，前端可渲染可放弃。
    """
    emit.progress(_impact_event("impact_analyzing"))
    analysis = llm.analyze_impact(
        problem_text=problem_text,
        requirements=requirements,
        current_slugs=current_slugs,
        manifest_summaries=manifest_summaries,
        new_qa_text=new_qa_text,
    )
    diff = compute_module_diff(current_slugs, analysis.suggested_slugs)
    warnings = resolve_selection(
        library_dir, platform, analysis.suggested_slugs
    ).warnings
    emit.progress(_impact_event("diff_ready"))
    return {
        "impacts": [impact.to_dict() for impact in analysis.impacts],
        "suggested_slugs": list(analysis.suggested_slugs),
        "diff": diff.to_dict(),
        "warnings": [warning_to_dict(warning) for warning in warnings],
        "platform": platform,
    }


def warning_to_dict(warning: PlatformWarning) -> dict[str, Any]:
    """平台警告 → JSON（slug / kind / message，前端展示用）。"""
    return {
        "slug": warning.slug,
        "kind": warning.kind,
        "message": warning.message,
    }


def _impact_event(event_type: str):
    """影响分析进度事件（事件词表唯一出处 = events.py；本层只装配）。"""
    from .events import ProgressEvent

    return ProgressEvent(type=event_type)
