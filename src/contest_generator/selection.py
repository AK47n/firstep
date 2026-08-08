"""模块选择与依赖解析 + 模块推荐域。

流程：AI 推荐（或用户手选）的 slug 集 → 生成前用户增删 → 按 manifest 递归
展开依赖 → 检查目标平台可用性 → 交给生成器。展开与检查都是纯函数：用户
增删选择后重跑一遍 resolve_selection（加载库 + 展开 + 警告的组合操作）即可，
无需维护中间状态。

平台警告分三类——缺版本（missing，生成必失败）、未验证（unverified，可能
无法编译）、硬件绑定（hardware_bound，换平台需移植）。前两类是风险提示，
缺版本在生成阶段会硬失败，这里提前暴露让用户改选择。

模块推荐域（工单 10，C1 归位）也归本层：推荐模型类（OutOfLibrarySuggestion /
FunctionRequirement / ModuleSelection / ReferenceSuggestion）与题面驱动的
收敛循环（select_modules_convergent）整体在 selection——llm 层运行时从本层
导入模型（report.py 先例：llm 依赖模型层而非反向），本层对 LLM 协议仅
TYPE_CHECKING（library.py 先例，避免 llm ↔ selection 运行时环）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence

from .events import (
    EVENT_CONVERGED,
    EVENT_ROUND,
    ProgressEmitter,
    ProgressEvent,
    _emit,
)
from .entry_store import is_unsafe_path
from .library import list_modules
from .manifest import ManifestSummary, ModuleManifest, collect_kits
from .reference_library import ReferenceEntry, ReferenceError, search_references

if TYPE_CHECKING:
    from .llm import LLM  # 仅类型注解用（selection 不运行时依赖 LLM 客户端，library.py 先例）

WARNING_MISSING = "missing"  # 无目标平台版本条目，生成必失败
WARNING_UNVERIFIED = "unverified"  # 有版本但未验证过，可能无法编译
WARNING_HARDWARE_BOUND = "hardware_bound"  # 绑定硬件，换平台需移植


class SelectionError(ValueError):
    """选择 / 依赖解析失败，message 说明具体问题。"""


class UnknownModuleError(SelectionError):
    """选择了库中不存在的模块（或依赖引用了未知 slug）。"""


class DependencyCycleError(SelectionError):
    """依赖成环。"""


@dataclass(frozen=True)
class PlatformWarning:
    """生成前的平台可用性警告。"""

    slug: str
    kind: str  # WARNING_MISSING / WARNING_UNVERIFIED / WARNING_HARDWARE_BOUND
    message: str


@dataclass(frozen=True)
class ResolvedSelection:
    """选择解析结果：依赖展开后的完整模块集 + 平台可用性警告。"""

    manifests: tuple[ModuleManifest, ...]
    warnings: tuple[PlatformWarning, ...]


def resolve_selection(
    library_dir: Path, platform: str, slugs: Sequence[str]
) -> ResolvedSelection:
    """加载模块库 → 展开依赖 → 平台警告，一步到位。

    webapp 的展开 / 骨架 / 生成三个端点共用这一组合操作——"所选模块最终
    解析成什么"只有一个答案来源，单独跑 expand 与生成前的结果必然一致。
    """
    by_slug = {m.slug: m for m in list_modules(library_dir)}
    manifests = resolve_dependencies(slugs, by_slug)
    warnings = check_platform_warnings([m.slug for m in manifests], platform, by_slug)
    return ResolvedSelection(manifests=manifests, warnings=warnings)


def resolve_dependencies(
    slugs: Sequence[str], by_slug: Mapping[str, ModuleManifest]
) -> tuple[ModuleManifest, ...]:
    """按 manifest 递归展开依赖，返回去重后的完整 manifest 集。

    结果顺序：依赖先于使用者（DFS 后序），同层按出现顺序；相互独立的
    选择保持传入顺序。成环（含自依赖）抛 DependencyCycleError，库中
    不存在的 slug（选择或依赖）抛 UnknownModuleError。
    """
    result: list[ModuleManifest] = []
    done: set[str] = set()
    visiting: list[str] = []  # 当前递归路径，用于环检测

    def visit(slug: str) -> None:
        if slug in done:
            return
        if slug in visiting:
            raise DependencyCycleError("依赖成环：" + " -> ".join([*visiting, slug]))
        visiting.append(slug)
        manifest = _get_manifest(by_slug, slug)
        for dep in manifest.dependencies:
            visit(dep)
        visiting.pop()
        done.add(slug)
        result.append(manifest)

    for slug in slugs:
        visit(slug)
    return tuple(result)


def check_platform_warnings(
    slugs: Sequence[str], platform: str, by_slug: Mapping[str, ModuleManifest]
) -> tuple[PlatformWarning, ...]:
    """检查所选模块（应传 resolve_dependencies 的结果）在目标平台的可直接使用性。

    每个模块至多两类风险提示（未验证 / 硬件绑定），缺平台版本单独一条
    missing 警告。警告按输入顺序排列。slug 未知抛 UnknownModuleError。
    """
    warnings: list[PlatformWarning] = []
    for slug in slugs:
        manifest = _get_manifest(by_slug, slug)
        entry = manifest.platforms.get(platform)
        if entry is None:
            warnings.append(
                PlatformWarning(
                    slug,
                    WARNING_MISSING,
                    f"模块 {slug} 缺少平台 {platform} 的版本，生成将失败——请移除或换模块",
                )
            )
            continue
        if not entry.verified:
            warnings.append(
                PlatformWarning(
                    slug,
                    WARNING_UNVERIFIED,
                    f"模块 {slug} 在平台 {platform} 上的版本未验证，可能无法编译",
                )
            )
        if entry.hardware_bound:
            warnings.append(
                PlatformWarning(
                    slug,
                    WARNING_HARDWARE_BOUND,
                    f"模块 {slug} 在平台 {platform} 上的版本硬件绑定，换平台需移植",
                )
            )
    return tuple(warnings)


def _get_manifest(by_slug: Mapping[str, ModuleManifest], slug: str) -> ModuleManifest:
    manifest = by_slug.get(slug)
    if manifest is None:
        raise UnknownModuleError(f"库中不存在模块：{slug}")
    return manifest


# ---------------------------------------------------------------------------
# 工单 03：候选清单带参考文件（两级注入第一级）+ 全文回读（第二级）
# ---------------------------------------------------------------------------


def associated_references(
    reference_root: Path,
    *,
    topic_key: str = "",
    manifests: Sequence[ModuleManifest] = (),
) -> tuple[ReferenceEntry, ...]:
    """该赛题 / 套件关联的参考文件（候选清单的参考段，两级注入第一级的素材）。

    关联判据 = 锚定值匹配赛题编号（topic_key）或套件型号（kit 词表收集走
    manifest.collect_kits 单源——候选模块的套件身份与模块简介同源，参考文件
    ↔ 套件链接可靠）。按 id 去重排序：search_references 的锚定过滤是子串
    匹配，同一条目可能被多个锚定值命中（如 kit 名含编号）。参考库目录不存在
    返回空。
    """
    if not reference_root.is_dir():
        return ()
    kits = collect_kits(manifests)
    entries: dict[str, ReferenceEntry] = {}
    for anchor in (topic_key, *kits):
        if anchor:
            for reference in search_references(reference_root, anchor=anchor):
                entries.setdefault(reference.id, reference)
    return tuple(entries.values())


def reference_suggestions(
    entries: Sequence[ReferenceEntry],
) -> tuple[ReferenceSuggestion, ...]:
    """候选清单的参考段形状：参考文件（标题 + 一句话简介），喂给选模块 AI。"""
    return tuple(
        ReferenceSuggestion(id=entry.id, title=entry.title, description=entry.description)
        for entry in entries
    )


def read_reference_fulltext(reference_root: Path, entry: ReferenceEntry) -> str:
    """参考文件条目全文（两级注入第二级的素材）：素材文件拼成带文件名标注的文本。

    二进制素材（说明书 PDF 等）读不了文本——跳过并标注（不让生成流程因个别
    不可读素材整体失败）；条目文件缺失 / 相对路径非法 = 库损坏，大声失败
    （ReferenceError，宁可大声失败也不把坏数据带进上下文）。
    """
    chunks: list[str] = []
    for rel in entry.files:
        if is_unsafe_path(rel):
            raise ReferenceError(
                f"参考文件条目 {entry.id!r} 的文件路径非法：{rel!r}"
            )
        path = reference_root / entry.id / rel
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReferenceError(
                f"参考文件条目 {entry.id!r} 的素材文件无法读取：{rel}: {exc}"
            ) from exc
        except UnicodeDecodeError:
            chunks.append(f"// ---- {rel} ----（二进制素材，未嵌入全文）\n")
            continue
        chunks.append(f"// ---- {rel} ----\n{content}")
    return "\n".join(chunks)


# ---------------------------------------------------------------------------
# 模块推荐域（工单 10，架构深化 C1 归位）：推荐模型类 + 题面驱动的收敛循环。
#
# 模型类与收敛工作流整体在本层（模块选择域）；llm.py 运行时从本层导入模型
# （report.py 先例：llm 层依赖模型层而非反向），本层对 LLM 协议仅 TYPE_CHECKING
# （library.py 先例，避免 llm ↔ selection 运行时环）。
# ---------------------------------------------------------------------------

# 模块推荐收敛循环（工单 10）：连续两轮功能需求层一致即收敛，上限这么轮防
# 死循环（ADR 0007：质量优先，成本为 2-4 轮 × 2-4K token，DeepSeek 可承受）。
SELECT_CONVERGENCE_MAX_ROUNDS = 4


@dataclass(frozen=True)
class OutOfLibrarySuggestion:
    """库外建议：无库内实现的功能的外设推荐（仅展示、不进工程、不参与生成）。

    name = 展示名：词表内条目（型号或类别）原样显示；词表外型号经解析器
    降级为其类别名（degraded=True）。examples 常识举例（用户自行核实）。
    """

    name: str
    examples: tuple[str, ...] = ()
    degraded: bool = False  # 词表外型号 → 降级为类别名显示

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "examples": list(self.examples),
            "degraded": self.degraded,
        }


@dataclass(frozen=True)
class FunctionRequirement:
    """功能需求层条目（工单 10）：题面证据驱动的能力/外设级需求。

    requirement = 能力/外设描述（声光提示 → LED/蜂鸣器），粒度贴题面关键词；
    sentence_index = 逐句对照的题面句子编号（1 起）——找不出对应句的需求即
    脑补；modules = 库内命中 slug（实现覆盖检查的命中分支，可勾选进工程）；
    suggestions = 库外建议（无命中分支，仅展示）。
    """

    requirement: str
    sentence_index: int
    modules: tuple[str, ...] = ()
    suggestions: tuple[OutOfLibrarySuggestion, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "sentence": self.sentence_index,
            "modules": list(self.modules),
            "suggestions": [suggestion.to_dict() for suggestion in self.suggestions],
        }


@dataclass(frozen=True)
class ModuleSelection:
    """赛题 → 模块选择结果（AI 的原始推荐，未展开依赖）。

    依赖展开与生成前的增删由 selection.resolve_dependencies 在用户确认后
    统一处理——AI 输出后用户还可能增删，先展开的集合无法代表最终选择。
    reference_ids 是两级注入第一级的产物：模型想读全文的参考文件 id（没给
    参考文件清单时恒为空）。
    requirements = 功能需求层（工单 10）：顶层 modules 由它机械派生（库内
    命中的并集，保序）——模块必有需求支撑，没挂需求句的模块是脑补；
    questions = 题面证据不足以判定时向用户补问的问题（非空 → 收敛循环暂停，
    以补问收尾，不产出推荐）。
    """

    modules: tuple[str, ...]  # 模块 slug（AI 推荐顺序）
    reasons: dict[str, str]  # slug -> 推荐理由
    reference_ids: tuple[str, ...] = ()  # 两级注入第一级：想读全文的参考文件 id
    requirements: tuple[FunctionRequirement, ...] = ()  # 功能需求层
    questions: tuple[str, ...] = ()  # 向用户补问（非空 → 暂停分析）


@dataclass(frozen=True)
class ReferenceSuggestion:
    """两级注入的清单段：一个参考文件（标题 + 一句话简介），供选模块 AI 判断是否取全文。

    清单段由 selection 层装配（associated_references → reference_suggestions）；
    id 与参考文件库条目的 id 一致——AI 点名要读的 id 就是全文回读的键。
    """

    id: str
    title: str
    description: str


# ---------------------------------------------------------------------------
# 模块推荐收敛循环（工单 10）：题面证据驱动 + 功能需求层两轮一致即收敛
# ---------------------------------------------------------------------------

# 题面句子切分（逐句对照的机械防漏）：中文句读（。！？；;）或换行后的
# 空白即句界。切分确定性——同一题面任何轮次编号一致（收敛判定的对照句编号
# 依赖它：编号漂移会让两轮"同一句"对不上号）。
_SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？；;\n])\s*")


def _number_topic_sentences(problem_text: str) -> str:
    """题面逐句编号：每句一行 "N. …"，功能需求的 sentence 字段引用这里的编号。

    逐句对照是防脑补的机械兜底（收敛的自检盲区 = 两轮一起漏，逐句表兜底）：
    题面按句编号，每句对应功能需求或"无功能"，找不出对应句的需求即脑补。
    """
    parts = [
        part.strip() for part in _SENTENCE_BOUNDARY.split(problem_text) if part.strip()
    ]
    if not parts:
        return problem_text
    return "\n".join(f"{index}. {part}" for index, part in enumerate(parts, 1))


def _revision_prompt(
    numbered_topic: str, previous: Sequence[FunctionRequirement]
) -> str:
    """收敛轮（第 2 轮起）的赛题文本：上一轮功能需求层 + 自检修订指令。

    以题面为裁判反复自检修订（删脑补 / 补遗漏 / 重查覆盖），输出完整的新一
    轮功能需求层（不是增量）——模型在完整重写里自己暴露并修正上一轮的缺陷；
    连续两轮一致时可保持不动（收敛判定在驱动层完成，这里只是给模型依据）。
    """
    lines = [
        numbered_topic,
        "",
        "上一轮功能需求层（以题面原文为裁判自检修订，输出完整的新一轮功能"
        "需求层，不是增量；连续两轮一致时可保持不动）：",
    ]
    for index, requirement in enumerate(previous, 1):
        detail = f"句子{requirement.sentence_index}「{requirement.requirement}」"
        if requirement.modules:
            detail += "，库内命中：" + "、".join(requirement.modules)
        if requirement.suggestions:
            detail += "，库外建议：" + "、".join(
                suggestion.name for suggestion in requirement.suggestions
            )
        lines.append(f"{index}. {detail}")
    return "\n".join(lines)


def _functional_layer_key(
    selection: ModuleSelection,
) -> tuple[tuple[str, int, tuple[str, ...], tuple[str, ...]], ...]:
    """收敛判定的一致性键：需求文本 / 对照句 / 库内命中 slug / 库外建议名。

    examples（常识举例）自由发挥、用户自行核实，不参与收敛判定——模型重述
    examples 不算功能需求层变化（否则"K230/OpenMV" vs "K230"会拖到轮数上限）。
    """
    return tuple(
        (
            requirement.requirement,
            requirement.sentence_index,
            requirement.modules,
            tuple(suggestion.name for suggestion in requirement.suggestions),
        )
        for requirement in selection.requirements
    )


def select_modules_convergent(
    llm: LLM,
    problem_text: str,
    manifest_summaries: Sequence[ManifestSummary],
    references: Sequence[ReferenceSuggestion] = (),
    reader: Callable[[str], str] | None = None,
    max_rounds: int = SELECT_CONVERGENCE_MAX_ROUNDS,
    progress_emitter: ProgressEmitter | None = None,
) -> ModuleSelection:
    """题面驱动的收敛循环：功能需求层两轮一致即停，上限 max_rounds 轮。

    每一轮都是独立调用：第 1 轮 = 两级注入协议（参考文件先清单、点名全文后
    回读重选，协议已内联在下方循环体）；第 2 轮起带上一轮功能需求层
    （_revision_prompt 自检修订指令）与已读全文，功能需求层与上一轮一致即
    收敛（_functional_layer_key，examples 不参与）。恰好两级：第 2 轮起不再
    注入新的参考全文（想要的已全给）。题面逐句编号在驱动层完成
    （_number_topic_sentences），编号跨轮稳定——收敛判定的对照句编号依赖它。

    模型拿不准（题面证据不足以判定）时输出 questions → 本轮即停、返回
    selection.questions 非空（向用户补问，由 webapp 层转补问终端事件收尾流）。

    轮次经 progress_emitter 旁路发射（EVENT_ROUND / EVENT_CONVERGED）——
    发射失败不影响主流程（与提炼进度同款 seam，_emit）。
    """
    if max_rounds < 1:
        raise ValueError(f"max_rounds 必须 ≥ 1：{max_rounds}")
    numbered = _number_topic_sentences(problem_text)
    fulltexts: dict[str, str] = {}
    previous: tuple[FunctionRequirement, ...] = ()
    previous_key: tuple[tuple[str, int, tuple[str, ...], tuple[str, ...]], ...] | None = None
    selection: ModuleSelection | None = None
    for round_no in range(1, max_rounds + 1):
        _emit(
            progress_emitter,
            ProgressEvent(type=EVENT_ROUND, round=round_no, round_total=max_rounds),
        )
        round_topic = (
            _revision_prompt(numbered, previous) if round_no > 1 else numbered
        )
        if references:
            if round_no == 1 and reader is not None:
                # 两级注入第一级：先清单；点名全文 → 回读（第二级），全文进上下文
                first = llm.select_modules(round_topic, manifest_summaries, references)
                if first.reference_ids:
                    fulltexts = {
                        entry_id: reader(entry_id) for entry_id in first.reference_ids
                    }
                    selection = llm.select_modules(
                        round_topic, manifest_summaries, references, fulltexts
                    )
                else:
                    selection = first
            else:
                # 第 2 轮起：已读全文照旧带上（恰好两级，不再注入新全文）；
                # 没有想读的全文时保持清单级形状（空全文不进提示词）
                selection = llm.select_modules(
                    round_topic, manifest_summaries, references, fulltexts or None
                )
        else:
            selection = llm.select_modules(round_topic, manifest_summaries)
        if selection.questions:
            return selection  # 补问：暂停收敛，向用户补问（不以推荐收尾）
        key = _functional_layer_key(selection)
        if previous_key is not None and key == previous_key:
            _emit(
                progress_emitter,
                ProgressEvent(type=EVENT_CONVERGED, round=round_no),
            )
            return selection
        previous = selection.requirements
        previous_key = key
    assert selection is not None  # max_rounds ≥ 1，循环体必赋值
    return selection  # 上限轮次到：以最后一轮为准（不再多问）
