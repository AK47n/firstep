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
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence

from .events import (
    EVENT_CONVERGED,
    EVENT_ROUND,
    ProgressEmitter,
    ProgressEvent,
    _emit,
)
from .boards import Board, pin_supports
from .entry_store import StoreError
from .library import list_modules
from .manifest import (
    ExclusiveGroup,
    ExclusiveGroupMember,
    ManifestSummary,
    ModuleManifest,
    collect_kits,
    scope_group_members,
)
from .platforms import PLATFORM_MSPM0, PLATFORM_STM32
from .reference_library import (
    PLATFORM_ANY,
    ReferenceEntry,
    ReferenceError,
    get_reference,
    search_references,
)
from .sse import SseEmitter  # 终端事件发射面（sse 是叶子模块，运行时导入无环）
from .wordlist import (
    HardwareWordGroup,
    SolutionOption,
)

if TYPE_CHECKING:
    from .generator import TopicContext  # 装配点素材（generator 运行时依赖本层，仅类型注解）
    from .llm import LLM  # 仅类型注解用（selection 不运行时依赖 LLM 客户端，library.py 先例）

WARNING_MISSING = "missing"  # 无目标平台版本条目，生成必失败
WARNING_UNVERIFIED = "unverified"  # 有版本但未验证过，可能无法编译
WARNING_HARDWARE_BOUND = "hardware_bound"  # 绑定硬件，换平台需移植

# 图内信息问题关键词（工单 recommend-vision-qa/01 + clarify-vision-relax/01）：
# 与「问题点名题面引用过的图号」互为**析取**分支——题面引用过图时，点名图号
# 或命中本表任一关键词即交视觉通道从原题渲染页找答案。放宽后误判（交互/实现
# 细节类问题误入视觉）由视觉消化安全网兜底：答不上（否定词/空答案）→ 照旧
# 转问用户，代价 = 一次缓存视觉调用而非丢问题。「多少/多大」是通用子串，
# 题面引用过图时纯正文问题也可能进视觉——spec 明示不改本表内容并接受该代价。
VISION_ANSWERABLE_KEYWORDS = (
    "尺寸",
    "宽度",
    "长度",
    "走廊",
    "门口",
    "位置",
    "走向",
    "标注",
    "距离",
    "坐标",
    "多大",
    "多少",
    "面积",
    "高度",
)


class SelectionError(ValueError):
    """选择 / 依赖解析失败，message 说明具体问题。"""


class UnknownModuleError(SelectionError):
    """选择了库中不存在的模块（或依赖引用了未知 slug）。"""


class ManualReferenceError(SelectionError):
    """手动选参考资料校验失败（不存在 / 重复——生成时用户显式点名的严格校验）。"""


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
    """选择解析结果：依赖展开后的完整模块集 + 平台可用性警告 + 实例清单。

    instances = 多实例实例清单（slug → 实例元组），透传自生成请求——缺省
    空 dict = 单默认实例（旧行为）。
    """

    manifests: tuple[ModuleManifest, ...]
    warnings: tuple[PlatformWarning, ...]
    instances: dict[str, tuple[ModuleInstance, ...]] = field(default_factory=dict)


def resolve_selection(
    library_dir: Path,
    platform: str,
    slugs: Sequence[str],
    instances: Mapping[str, Sequence[ModuleInstance]] | None = None,
) -> ResolvedSelection:
    """加载模块库 → 展开依赖 → 平台警告 → 透传实例清单，一步到位。

    webapp 的展开 / 骨架 / 生成三个端点共用这一组合操作——"所选模块最终
    解析成什么"只有一个答案来源，单独跑 expand 与生成前的结果必然一致。
    instances 缺省 = 空（单默认实例，旧行为）；传入则保序归一为元组透传，
    展开 / 默认脚分配（工单 02）在此之后消费。
    """
    by_slug = {m.slug: m for m in list_modules(library_dir)}
    manifests = resolve_dependencies(slugs, by_slug)
    warnings = check_platform_warnings([m.slug for m in manifests], platform, by_slug)
    resolved_instances = {
        slug: tuple(insts) for slug, insts in (instances or {}).items()
    }
    return ResolvedSelection(
        manifests=manifests,
        warnings=warnings,
        instances=resolved_instances,
    )


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

# 清单段条目的来源标注（工单 01 手动选参考资料）：auto = 锚定命中自动进清单
# （两级：清单 → 点名 → 回读）；manual = 用户手动指定（全文直读，无需点名）。
REFERENCE_SOURCE_AUTO = "auto"
REFERENCE_SOURCE_MANUAL = "manual"


def associated_references(
    reference_root: Path,
    *,
    topic_key: str = "",
    manifests: Sequence[ModuleManifest] = (),
    platform: str = "",
) -> tuple[ReferenceEntry, ...]:
    """该赛题 / 套件关联的参考文件（候选清单的参考段，两级注入第一级的素材）。

    关联判据 = 锚定值匹配赛题编号（topic_key）或套件型号（kit 词表收集走
    manifest.collect_kits 单源——候选模块的套件身份与模块简介同源，参考文件
    ↔ 套件链接可靠）。按 id 去重排序：search_references 的锚定过滤是子串
    匹配，同一条目可能被多个锚定值命中（如 kit 名含编号）。参考库目录不存在
    返回空。

    platform 过滤（工单 01）：topic 命中与 kit 命中统一按条目平台属性过滤——
    不匹配跳过；any 条目全进（平台无关）；platform 空串 = 不过滤（向后兼容，
    skeleton / generate 等不注入参考文件的调用方传缺省即可）。
    """
    if not reference_root.is_dir():
        return ()
    kits = collect_kits(manifests)
    entries: dict[str, ReferenceEntry] = {}
    for anchor in (topic_key, *kits):
        if anchor:
            for reference in search_references(reference_root, anchor=anchor):
                if _platform_matches(reference, platform):
                    entries.setdefault(reference.id, reference)
    return tuple(entries.values())


def _platform_matches(reference: ReferenceEntry, platform: str) -> bool:
    """条目平台属性匹配：any 全进；platform 空串 = 不过滤（向后兼容）；否则
    条目平台必须与生成平台一致。

    公开名 platform_matches（工单 topic-framework/04 起 cross-module 复用）；
    两者同实现，只读谓词。"""
    return platform_matches(reference, platform)


def platform_matches(reference: ReferenceEntry, platform: str) -> bool:
    """条目平台属性匹配（公开）：any 全进；platform 空串 = 不过滤（向后兼容）；
    否则条目平台必须与生成平台一致。单一判据——associated_references /
    build_topic_framework_info / filter_manifests_by_platform 共用，防分叉。"""
    return (
        not platform
        or reference.platform == PLATFORM_ANY
        or reference.platform == platform
    )


def filter_manifests_by_platform(
    manifests: Sequence[ModuleManifest], platform: str
) -> tuple[ModuleManifest, ...]:
    """模块候选按平台过滤（工单 ref-platform-filter 模块侧对偶）。

    与 _platform_matches（参考库条目平台属性）同判据：platform 空串 = 不过滤
    （向后兼容——骨架 / 生成不注入推荐候选，传缺省）；否则只留 platforms 含
    该平台的条目（无任何平台版本的模块在任意平台生成必失败，不列为候选，
    与参考库"any 全进、带平台只进对应平台"对齐）。过滤在装配点执行（生成
    接缝 resolve_topic_context，摘要行与关联模块同源同滤）；未知平台在
    generate 入口经 patcher_registry.get 失败。
    """
    if not platform:
        return tuple(manifests)
    return tuple(
        manifest for manifest in manifests if platform in manifest.platforms
    )


def reference_suggestions(
    entries: Sequence[ReferenceEntry],
    *,
    source: str = REFERENCE_SOURCE_AUTO,
) -> tuple[ReferenceSuggestion, ...]:
    """候选清单的参考段形状：参考文件（标题 + 一句话简介），喂给选模块 AI。

    source = 来源标注（自动锚定 / 手动指定，prompt 清单行按它区分——手动条目
    已全文直读，标注后模型无需点名）。
    """
    return tuple(
        ReferenceSuggestion(id=entry.id, title=entry.title, description=entry.description, source=source)
        for entry in entries
    )


def manual_reference_admission(
    reference_root: Path, reference_ids: Sequence[str]
) -> tuple[ReferenceEntry, ...]:
    """手动选参考资料准入（追加语义，工单 01）：请求的 id → 完整条目，保序。

    手动选条目必须真实存在于参考库——幻觉 id / 格式非法大声失败
    （ManualReferenceError，对齐 _parse_reference_ids 的严格精神：宁可大声
    失败也不带坏数据进上下文）；同一次请求重复 id 同样拒绝。准入 = 锚定
    命中 ∪ 手动选（并集去重由装配点做，这里只校验单请求自身）。
    """
    entries: list[ReferenceEntry] = []
    seen: set[str] = set()
    for entry_id in reference_ids:
        if entry_id in seen:
            raise ManualReferenceError(f"重复选择参考文件：{entry_id}")
        try:
            entry = get_reference(reference_root, entry_id)
        except (ReferenceError, StoreError) as exc:
            # 查无此条（ReferenceError）与键非法（StoreError——条目 id 即目录名，
            # 文法非法同不存在）统一收口成手动选校验失败，不裸漏 500
            raise ManualReferenceError(
                f"手动选择的参考文件不存在：{entry_id}"
            ) from exc
        seen.add(entry_id)
        entries.append(entry)
    return tuple(entries)


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
    solutions = 买件指引的可选方案（词表确定性知识，工单 buy-guide/01）——
    展示层亮全部方案；selected = LLM 从 solutions.name 里选的「AI 建议」
    （词表外 → 置空不高亮，编造不阻断导览）。
    """

    name: str
    examples: tuple[str, ...] = ()
    degraded: bool = False  # 词表外型号 → 降级为类别名显示
    solutions: tuple[SolutionOption, ...] = ()  # 买件指引方案（词表知识）
    selected: str = ""  # LLM 选出的 AI 建议方案名（词表 solutions 内才保留）

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "examples": list(self.examples),
            "degraded": self.degraded,
            "solutions": [solution.to_dict() for solution in self.solutions],
            "selected": self.selected,
        }


# 已定方案的 judgment 词表（工单 buy-discuss/02）：source = 结论来源
# （wordlist = 词表方案内选款；custom = 用户自定想法——用户说话是猜想，
# AI 校核后仍可确定，UI 注明「自定」）；verdict 词表（可行/有风险/不可行）
# 与 llm.BUY_VERDICTS 同值（llm 层从本模块 import，防环反向）。
BUY_DECISION_SOURCES = ("wordlist", "custom")
BUY_VERDICTS = ("feasible", "risky", "infeasible")


class BuyError(ValueError):
    """买件方案商量请求非法（工单 buy-discuss/03，登记 errors.py → 400 中文）。"""


@dataclass(frozen=True)
class SuggestionDecision:
    """库外建议的「已定方案」结论（工单 buy-discuss/02，形状契约单源）。

    前端与 AI 商量后确定的买件结论：source = wordlist（词表方案内选款）|
    custom（用户自定想法）；name = 方案名（wordlist 内）或自定标题；note =
    自定想法描述 / 补充说明；verdict = AI 可行性审核意见（feasible | risky |
    infeasible，空 = 无审核——AI 是顾问非裁判，verdict 不阻断用户确定）。
    结论是载荷增强（前端附加，不走 OutOfLibrarySuggestion 构造域——那个域
    是 LLM 输出解析），此模型只保证形状契约：parse_decision 词表外修正后
    返回 None 表示「无结论」。
    """

    source: str
    name: str
    note: str = ""
    verdict: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "name": self.name,
            "note": self.note,
            "verdict": self.verdict,
        }


def parse_decision(raw: Any) -> SuggestionDecision | None:
    """载荷 `decision` 字段的解析（形状契约；损坏 = None 不阻断导览）。

    非 dict / 缺 name / name 空白 = None（宁缺毋编：没有结论就不标注）；
    source 词表外 → 修正 custom（自定想法是兜底语义）；verdict 词表外 → 置空
    （审核意见缺失不误导）。仅展示增强，不参与任何域判决。
    """
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    if not name:
        return None
    source = str(raw.get("source", "")).strip()
    if source not in BUY_DECISION_SOURCES:
        source = "custom"
    verdict = str(raw.get("verdict", "")).strip()
    if verdict not in BUY_VERDICTS:
        verdict = ""
    return SuggestionDecision(
        source=source,
        name=name,
        note=str(raw.get("note", "")).strip(),
        verdict=verdict,
    )


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
class ScorePoint:
    """题面评分点的结构化投影，不参与模块推荐判决。"""

    id: str
    part: str
    description: str
    score: float | None
    sentence_refs: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "part": self.part,
            "description": self.description,
            "score": self.score,
            "sentence_refs": list(self.sentence_refs),
        }


def parse_score_points(raw: Any) -> tuple[ScorePoint, ...]:
    """解析可选评分点；形状不完整时降级为空，不阻断推荐主链。"""
    if raw in (None, [], ()) or not isinstance(raw, list):
        return ()
    points: list[ScorePoint] = []
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            return ()
        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            return ()
        raw_id = item.get("id", f"score-{index}")
        if not isinstance(raw_id, str) or not raw_id.strip():
            return ()
        part = item.get("part", "unknown")
        if part not in ("basic", "development"):
            part = "unknown"
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            score = None
        elif not isfinite(score):
            score = None
        raw_refs = item.get("sentence_refs", [])
        if not isinstance(raw_refs, list) or any(
            isinstance(ref, bool) or not isinstance(ref, int) or ref < 1
            for ref in raw_refs
        ):
            return ()
        points.append(
            ScorePoint(
                id=raw_id.strip(),
                part=part,
                description=description.strip(),
                score=float(score) if score is not None else None,
                sentence_refs=tuple(raw_refs),
            )
        )
    return tuple(points)


@dataclass(frozen=True)
class ModuleInstance:
    """多实例选择里的单个实例。

    name = 显示名（自由中文）；variant = 变体（led = 颜色，内置 red/yellow/
    green，空串 = 非内置色）；pin = 显式引脚覆盖，空串 = 自动分配默认脚
    （请求解析层把 null 归一为空串，本模型只认空串语义）。
    """

    name: str
    variant: str = ""
    pin: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "variant": self.variant, "pin": self.pin}


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
    instances = 多实例实例清单（slug → 实例元组），缺省空 dict = 单默认
    实例（旧行为）。
    """

    modules: tuple[str, ...]  # 模块 slug（AI 推荐顺序）
    reasons: dict[str, str]  # slug -> 推荐理由
    reference_ids: tuple[str, ...] = ()  # 两级注入第一级：想读全文的参考文件 id
    requirements: tuple[FunctionRequirement, ...] = ()  # 功能需求层
    score_points: tuple[ScorePoint, ...] = ()  # 题面评分点（可选增强信息）
    questions: tuple[str, ...] = ()  # 向用户补问（非空 → 暂停分析）
    instances: dict[str, tuple[ModuleInstance, ...]] = field(default_factory=dict)
    converged: bool = False  # 核验轮短标记（工单 01）：模型自报与上一轮一致
    # （无需求层可判——短标记形态跳过域判决；仅核验轮允许，第 1 轮出现当空结果）


@dataclass(frozen=True)
class ReferenceSuggestion:
    """两级注入的清单段：一个参考文件（标题 + 一句话简介），供选模块 AI 判断是否取全文。

    清单段由 selection 层装配（associated_references → reference_suggestions）；
    id 与参考文件库条目的 id 一致——AI 点名要读的 id 就是全文回读的键。
    source = 来源标注（auto 锚定 / manual 手动指定），prompt 清单行按它标注。
    """

    id: str
    title: str
    description: str
    source: str = REFERENCE_SOURCE_AUTO


# ---------------------------------------------------------------------------
# 模型输出 → ModuleSelection 解释链（工单 06 拆层）：域判决单址
#
# 模型输出的 JSON 由 llm 做机械形状提取（extract_module_selection_data，
# 只 JSON 解析 + 顶层对象校验）后传到这里；需求→模块机械派生、词表硬约束
# （库外建议 name 校验 / 降级 / 拒收）、DeepSeek json 怪癖（sentence 数字
# 字符串强转）等域判决整体在本层——llm 只做传输。任何结构 / 内容问题都抛
# SelectionError（错误文案与拆层前逐字一致）。
# ---------------------------------------------------------------------------


def build_module_selection(
    raw: dict[str, Any],
    *,
    known_slugs: Sequence[str],
    known_reference_ids: Sequence[str] = (),
    hardware_words: Sequence[HardwareWordGroup] = (),
    multi_instance_slugs: Sequence[str] = (),
) -> ModuleSelection:
    """把模型输出的原始 JSON 数据（llm 已解析为 dict）解析校验为 ModuleSelection。

    任何结构 / 内容问题（缺模块数组、未知 slug、重复、字段类型错）都抛
    SelectionError——模型输出不可信，宁可大声失败也不要带病进入生成流程。
    references 数组（两级注入第一级，可选）同样严格：没给参考文件清单时模型
    报 references = 幻觉（大声失败）；给了则必须全部在清单内、不重复——要求
    阅读清单外的参考文件也是幻觉，读它 = 把没校验过的内容带进上下文。
    非 JSON / 顶层非对象这两处机械检查在 llm 侧（extract_module_selection_data）。

    新契约（工单 10）：模型输出 requirements（功能需求层）时，顶层 modules
    由库内命中的并集机械派生（保序、首见理由）——模块必有需求支撑，顶层与
    需求层永不漂移；模型同批输出的 modules 数组被忽略（派生为准）。requirements
    缺省时退化为旧契约（modules 数组原样解析）。库外建议 suggestions 的 name
    受硬件词表约束：词表内条目（类别或型号）→ 显示；词表外型号 → 模型给出
    词表内类别名（category 字段）时降级为类别显示，否则拒收（大声失败）。
    questions（向用户补问）非空时暂停分析，不以推荐收尾。

    多实例推荐（工单 module-multi-instance/06）：模块条目可带 instances 数组
    （{name, variant}，pin 归自动、AI 不猜）→ 聚合进 ModuleSelection.instances。
    只对多实例模块收 instances——multi_instance_slugs = 多实例能力清单（llm
    层从 ManifestSummary 同源取），带 instances 的 slug 不在清单内 = 没有能力
    证据，大声失败（宁严勿假绿，与 references 幻觉同款口径）；未提供清单
    （空）同样拒绝。数量不设硬上限（上限守卫是 expand_instances 的活）。
    """
    known = set(known_slugs)
    multi_instance = set(multi_instance_slugs)
    questions = _parse_questions(raw.get("questions"))
    raw_requirements = raw.get("requirements")
    if raw_requirements is not None:
        requirements, modules, reasons, instances = _parse_requirements(
            raw_requirements, known, hardware_words, multi_instance
        )
    elif isinstance(raw.get("modules"), list):
        modules, reasons, instances = _parse_plain_modules(
            raw["modules"], known, multi_instance
        )
        requirements = ()
    elif questions:
        # 纯补问输出（{"questions": [...]}）：没有需求层也没有模块，合法
        modules, reasons = [], {}
        requirements = ()
        instances = {}
    else:
        raise SelectionError("模型输出缺少 modules 数组")

    reference_ids = _parse_reference_ids(raw.get("references", []), known_reference_ids)
    return ModuleSelection(
        modules=tuple(modules),
        reasons=reasons,
        reference_ids=reference_ids,
        requirements=requirements,
        score_points=parse_score_points(raw.get("score_points")),
        questions=questions,
        instances=instances,
    )


def _parse_model_instances(
    raw: Any, slug: str, multi_instance: set[str], path: str
) -> tuple[ModuleInstance, ...]:
    """模型输出的 instances 数组解析（工单 module-multi-instance/06，AI 推荐侧）。

    形状：[{"name": 显示名, "variant": 变体}]——name 非空字符串、variant 字符串
    （null 归一空串 = 非内置色）；pin 不解析（AI 不猜，恒自动分配）。只对
    多实例模块收 instances：slug 不在能力清单内 = 没有能力证据，大声失败
    （宁严勿假绿，与 references 幻觉同款口径）。字段缺省 / null = 无实例
    （单默认实例，旧行为；null = 无声明语义，DeepSeek 常对非多实例模块
    补显式 null，不能当幻觉打——空数组则照打：显式声明了数组形状）。任何
    形状问题抛 SelectionError。
    """
    if raw is None:
        return ()
    if slug not in multi_instance:
        raise SelectionError(f"模块 {slug} 不支持多实例，不能带 instances")
    if not isinstance(raw, list):
        raise SelectionError(f"{path} 的 instances 必须是数组")
    if not raw:
        return ()
    parsed: list[ModuleInstance] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SelectionError(f"{path} instances[{index}] 必须是对象")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise SelectionError(f"{path} instances[{index}] 缺 name 或为空")
        variant = item.get("variant")
        if variant is None:
            variant = ""
        elif not isinstance(variant, str):
            raise SelectionError(f"{path} instances[{index}] 的 variant 必须是字符串")
        parsed.append(ModuleInstance(name=name.strip(), variant=variant.strip()))
    return tuple(parsed)


def _record_instances(
    instances: dict[str, tuple[ModuleInstance, ...]],
    slug: str,
    parsed: tuple[ModuleInstance, ...],
) -> None:
    """实例聚合（跨需求条目）：同 slug 的实例清单取并集（键 = name+variant，
    保首见顺序）。两条需求可各提一部分灯（题面拆分：一条说红灯、一条说黄灯
    = 题面要两灯），与旧版"不一致 = 模型自相矛盾 → 大声失败"相比并集宁多勿少——
    多出的实例用户可在实例卡删除，失败则整次推荐卡死（2021F + stm32 真跑 3/3
    被拦判例，工单 recommend-exclusive-groups/05）。完全相同清单（模型常把同一
    灯幂等挂在多条需求下）接受；缺省（无 instances）不覆盖已记清单。"""
    if not parsed:
        return
    existing = instances.get(slug)
    if existing is None:
        instances[slug] = parsed
        return
    seen = {(e.name, e.variant) for e in existing}
    merged: list[ModuleInstance] = list(existing)
    for e in parsed:
        key = (e.name, e.variant)
        if key not in seen:
            seen.add(key)
            merged.append(e)
    instances[slug] = tuple(merged)


def _parse_plain_modules(
    raw_modules: Sequence[Any], known: set[str], multi_instance: set[str]
) -> tuple[list[str], dict[str, str], dict[str, tuple[ModuleInstance, ...]]]:
    """旧契约的 modules 数组解析（无功能需求层时的顶层模块）。"""
    modules: list[str] = []
    reasons: dict[str, str] = {}
    instances: dict[str, tuple[ModuleInstance, ...]] = {}
    for index, item in enumerate(raw_modules):
        if not isinstance(item, dict):
            raise SelectionError(f"modules[{index}] 必须是对象")
        slug = item.get("slug")
        if not isinstance(slug, str) or not slug:
            raise SelectionError(f"modules[{index}] 缺 slug")
        if slug not in known:
            raise SelectionError(f"模型推荐了库中不存在的模块：{slug}")
        if slug in modules:
            raise SelectionError(f"模型重复推荐模块：{slug}")
        reason = item.get("reason", "")
        if not isinstance(reason, str):
            raise SelectionError(f"模块 {slug} 的 reason 必须是字符串")
        _record_instances(
            instances,
            slug,
            _parse_model_instances(item.get("instances"), slug, multi_instance, f"modules[{index}]"),
        )
        modules.append(slug)
        reasons[slug] = reason
    return modules, reasons, instances


def _parse_requirements(
    raw: Sequence[Any],
    known: set[str],
    hardware_words: Sequence[HardwareWordGroup],
    multi_instance: set[str],
) -> tuple[
    tuple[FunctionRequirement, ...],
    list[str],
    dict[str, str],
    dict[str, tuple[ModuleInstance, ...]],
]:
    """功能需求层解析 + 顶层 modules 派生（库内命中并集，保序、首见理由）。

    需求形状：requirement（非空文本）、sentence（正整数——逐句对照的题面
    句子编号，找不出对应句的需求即脑补）、modules（库内命中，slug 必须
    在库内且需求内不重复，条目可带 instances 数组——多实例推荐，工单
    module-multi-instance/06）、suggestions（库外建议，name 词表校验）。
    """
    if not isinstance(raw, list):
        raise SelectionError("requirements 必须是数组")
    requirements: list[FunctionRequirement] = []
    modules: list[str] = []
    reasons: dict[str, str] = {}
    instances: dict[str, tuple[ModuleInstance, ...]] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SelectionError(f"requirements[{index}] 必须是对象")
        requirement = item.get("requirement")
        if not isinstance(requirement, str) or not requirement.strip():
            raise SelectionError(f"requirements[{index}] 缺 requirement 或为空")
        sentence = item.get("sentence")
        # DeepSeek json_object 模式实测把数字标量序列化为字符串（"1"）——数字
        # 字符串按语义无损强转（sentence 语义 = 正整数，不是形状）；非数字字符串 /
        # 布尔 / 浮点照旧大声失败（脑补与乱编仍拒收）
        if isinstance(sentence, bool) or not isinstance(sentence, int):
            if isinstance(sentence, str) and sentence.strip().isdigit():
                sentence = int(sentence)
            else:
                raise SelectionError(f"requirements[{index}] 的 sentence 必须是正整数")
        if sentence < 1:
            raise SelectionError(f"requirements[{index}] 的 sentence 必须是正整数")
        raw_modules = item.get("modules", [])
        if not isinstance(raw_modules, list):
            raise SelectionError(f"requirements[{index}] 的 modules 必须是数组")
        slugs: list[str] = []
        for m_index, module in enumerate(raw_modules):
            if not isinstance(module, dict):
                raise SelectionError(
                    f"requirements[{index}] modules[{m_index}] 必须是对象"
                )
            slug = module.get("slug")
            if not isinstance(slug, str) or not slug:
                raise SelectionError(
                    f"requirements[{index}] modules[{m_index}] 缺 slug"
                )
            if slug not in known:
                raise SelectionError(f"模型推荐了库中不存在的模块：{slug}")
            if slug in slugs:
                raise SelectionError(
                    f"requirements[{index}] 重复推荐模块：{slug}"
                )
            reason = module.get("reason", "")
            if not isinstance(reason, str):
                raise SelectionError(f"模块 {slug} 的 reason 必须是字符串")
            _record_instances(
                instances,
                slug,
                _parse_model_instances(
                    module.get("instances"),
                    slug,
                    multi_instance,
                    f"requirements[{index}] modules[{m_index}]",
                ),
            )
            slugs.append(slug)
            if slug not in reasons:
                reasons[slug] = reason
        suggestions = _parse_suggestions(item.get("suggestions", []), index, hardware_words)
        requirements.append(
            FunctionRequirement(
                requirement=requirement,
                sentence_index=sentence,
                modules=tuple(slugs),
                suggestions=suggestions,
            )
        )
        for slug in slugs:
            if slug not in modules:
                modules.append(slug)
    return tuple(requirements), modules, reasons, instances


def _parse_suggestions(
    raw: Sequence[Any], req_index: int, hardware_words: Sequence[HardwareWordGroup]
) -> tuple[OutOfLibrarySuggestion, ...]:
    """库外建议解析（name 词表硬约束：不懂不编、编造降级）。

    命中词表条目（类别名或型号名）→ 原样显示；词表外型号 → 模型给出词表内
    类别名（category 字段）时降级为该类别显示；否则拒收（SelectionError）。
    没给词表时模型报建议 = 无法校验，同样大声失败。examples 自由（用户自行核实）。
    """
    if not isinstance(raw, list):
        raise SelectionError(f"requirements[{req_index}] 的 suggestions 必须是数组")
    if raw and not hardware_words:
        raise SelectionError("模型输出了库外建议但未提供硬件词表")
    suggestions: list[OutOfLibrarySuggestion] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SelectionError(
                f"requirements[{req_index}] suggestions[{index}] 必须是对象"
            )
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise SelectionError(
                f"requirements[{req_index}] suggestions[{index}] 缺 name"
            )
        examples = item.get("examples", [])
        if not isinstance(examples, list) or not all(
            isinstance(example, str) for example in examples
        ):
            raise SelectionError(
                f"requirements[{req_index}] suggestions[{index}] 的 examples "
                "必须是字符串数组"
            )
        matched = _solution_group(name, hardware_words)  # 命中判定单源（审查项）
        if matched is not None:
            suggestions.append(
                OutOfLibrarySuggestion(
                    name=name,
                    examples=tuple(examples),
                    solutions=matched.solutions,
                    selected=_resolve_selected(item, matched.solutions),
                )
            )
            continue
        # 词表外：降级为类别（模型给出词表内类别名时）或拒收
        category = item.get("category")
        if isinstance(category, str):
            matched = _solution_group(category, hardware_words)
            if matched is not None:
                suggestions.append(
                    OutOfLibrarySuggestion(
                        name=category,
                        examples=tuple(examples),
                        degraded=True,
                        solutions=matched.solutions,
                        selected=_resolve_selected(item, matched.solutions),
                    )
                )
                continue
        raise SelectionError(
            f"库外建议的硬件名不在硬件词表中：{name}（词表外型号请降级为"
            "词表内的类别名）"
        )
    return tuple(suggestions)


def _solution_group(
    name: str, hardware_words: Sequence[HardwareWordGroup]
) -> HardwareWordGroup | None:
    """词表行命中判定单源（审查项 buy-guide/01-1：原 _parse_suggestions 用
    categories/models 集合判定、_entry_solutions 又线性重扫一遍——同一命中
    语义两种写法）。类别名命中该行；型号名命中它所属的行（同行的 solutions
    全体展示——买件指引按类别给方案，型号不单独定义方案）；未命中 = None。
    """
    for group in hardware_words:
        if group.category == name or name in group.models:
            return group
    return None


def _solutions_for(
    name: str, hardware_words: Sequence[HardwareWordGroup]
) -> tuple[SolutionOption, ...]:
    """库外建议的买件指引方案：词表行命中 → 该行 solutions；未命中 = 空。"""
    matched = _solution_group(name, hardware_words)
    return matched.solutions if matched is not None else ()


def _resolve_selected(
    item: Mapping[str, Any], solutions: Sequence[SolutionOption]
) -> str:
    """LLM 可选的 `selected`（AI 建议方案名）：必须在词表 solutions.name 内。

    词表外 / 未提供 = 空串（不高亮、不阻断）——编造方案名不报错，只是
    展示层无「AI 建议」徽标（买件指引是导览，不是判决；宁缺毋编由词表
    solutions 保证，selected 只是高亮）。solutions 由调用方传入（命中行已
    知，不再重复查词表）。
    """
    raw = item.get("selected")
    if not isinstance(raw, str) or not raw:
        return ""
    for solution in solutions:
        if solution.name == raw:
            return raw
    return ""


def _parse_reference_ids(
    raw: Sequence[Any], known_reference_ids: Sequence[str]
) -> tuple[str, ...]:
    """references 数组解析（两级注入第一级，可选；严格校验与旧契约一致）。"""
    if not isinstance(raw, list):
        raise SelectionError("references 必须是数组")
    if not known_reference_ids and raw:
        raise SelectionError("模型输出了未提供的参考文件 id（没给清单却要点名读全文）")
    reference_ids: list[str] = []
    known_refs = set(known_reference_ids)
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item:
            raise SelectionError(f"references[{index}] 必须是字符串")
        if item not in known_refs:
            raise SelectionError(f"模型要求阅读清单外的参考文件：{item}")
        if item in reference_ids:
            raise SelectionError(f"模型重复要求阅读参考文件：{item}")
        reference_ids.append(item)
    return tuple(reference_ids)


# 补问条数上限（工单 clarify-no-restriction/01）：「题目中没有提到 = 没有限制」
# 收紧后提问数应自然收敛到个位数，本常量是提示词与解析层共用的单一出处——
# llm 层系统提示词「最多 N 条」由它插值，解析层截尾兜底（模型被要求最多输出
# 该条数，超出即噪音，不轰炸用户）。
MAX_QUESTIONS = 5


def _parse_questions(raw: Any) -> tuple[str, ...]:
    """questions 数组解析：缺省 / 空 → ()；非空时必须是字符串数组（补问文本）。
    超出 MAX_QUESTIONS 条截尾保留前 N 条（与提示词同源，防问题轰炸）。"""
    if raw in (None, [], ()):
        return ()
    if not isinstance(raw, list) or not all(
        isinstance(question, str) and question for question in raw
    ):
        raise SelectionError("questions 必须是字符串数组")
    return tuple(raw[:MAX_QUESTIONS])


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
    """收敛轮（第 2 轮起）的赛题文本：上一轮功能需求层 + 核验式修订指令。

    逐条核验上一轮功能需求层，题面原文是唯一裁判：仅当有确凿题面证据表明
    错误（脑补 / 遗漏 / 覆盖错）才改对应条目，且只做最小改动；无证据的条目
    逐字照抄上一轮原文输出、句子编号照抄不改——改写措辞本身是脑补（工单
    recommend-speedup/01：旧"自检修订"让模型每轮都改、功能需求层永不重复，
    "两轮一致即停"拖到 4 轮封顶）。

    短标记提前停（工单 01）：**全部条目核验通过（无任何修订）时输出
    {"converged": true}**——驱动层收到即用上一轮结果提前收敛，省掉全量输出
    的核验轮（2-4 min → 秒级）；有任何修订才输出完整的新一轮功能需求层
    （不是增量）。短标记只允许出现在核验轮。
    """
    lines = [
        numbered_topic,
        "",
        "上一轮功能需求层（逐条核验，题面原文是唯一裁判：仅当有确凿题面证据"
        "表明错误——脑补 / 遗漏 / 覆盖错——才改对应条目，且只做最小改动；"
        "无证据的条目逐字照抄上一轮原文输出，句子编号照抄不改；无证据支持的"
        "改动（改写措辞也算）本身是脑补）。"
        "全部条目核验通过、无任何修订时，输出 {\"converged\": true}（不要再输出"
        "需求层——本轮无需重发）；有任何修订时输出完整的新一轮功能需求层：",
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


# 收敛判定键类型：需求文本 / 对照句 / 库内命中 slug / 库外建议名 /
# 每命中模块的实例清单（ModuleInstance 冻结结构相等——多实例推荐，工单 06）。
_FunctionalKey = tuple[
    tuple[
        str,
        int,
        tuple[str, ...],
        tuple[str, ...],
        tuple[tuple[ModuleInstance, ...], ...],
    ],
    ...,
]


def _functional_layer_key(selection: ModuleSelection) -> _FunctionalKey:
    """收敛判定的一致性键：需求文本 / 对照句 / 库内命中 slug / 库外建议名 /
    每命中模块的实例清单（工单 module-multi-instance/06）。

    examples（常识举例）自由发挥、用户自行核实，不参与收敛判定——模型重述
    examples 不算功能需求层变化（否则"K230/OpenMV" vs "K230"会拖到轮数上限）。
    实例清单同样参与：实例数量 / 名称 / 变体变化 = 功能需求层变化（否则
    led×4 与 led×3 会被判为一致提前收敛，实例猜测被第一轮锁死）；推荐侧
    pin 恒为空串（AI 不猜），不引入比较噪音。旧契约（无需求层）路径
    requirements 恒空 → 键恒空、实例不参与收敛——生产提示词恒走新契约，
    此退化无实际影响。
    """
    return tuple(
        (
            requirement.requirement,
            requirement.sentence_index,
            requirement.modules,
            tuple(suggestion.name for suggestion in requirement.suggestions),
            tuple(
                selection.instances.get(slug, ()) for slug in requirement.modules
            ),
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
    manual_fulltexts: Mapping[str, str] | None = None,
    clarifications: Sequence[tuple[str, str]] = (),
    qa_material: str = "",
) -> ModuleSelection:
    """题面驱动的收敛循环：功能需求层两轮一致即停，上限 max_rounds 轮。

    每一轮都是独立调用：第 1 轮 = 两级注入协议（参考文件先清单、点名全文后
    回读重选，协议已内联在下方循环体）；第 2 轮起带上一轮功能需求层
    （_revision_prompt 核验式修订指令）与已读全文，功能需求层与上一轮一致即
    收敛（_functional_layer_key，examples 不参与）。恰好两级：第 2 轮起不再
    注入新的参考全文（想要的已全给）。题面逐句编号在驱动层完成
    （_number_topic_sentences），编号跨轮稳定——收敛判定的对照句编号依赖它。

    手动选参考资料（工单 01）经 manual_fulltexts（id → 全文，装配点已读好）
    每轮直读进上下文：第 1 轮第一级就带（手动 = 全文直读强制，无需模型点名），
    点名回读的第二级与第 2 轮起的确认轮照旧带上（全文上下文不丢）。references
    与 manual_fulltexts 都缺时走旧签名（既有假 LLM 零改动）。

    clarifications = 澄清问答历史（工单 clarify-history-in-convergence）每轮
    透传给 select_modules：题面后的独立段（Q/A 逐条、不带编号），收敛阶段
    对同一证据不足点补问（selection.questions → 用户回答重推）后不再换措辞
    反复问——问答闭环贯穿两阶段。空历史不传对应关键字（既有假 LLM 零改动，
    与 manual_fulltexts 同规）。

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
    previous_selection: ModuleSelection | None = None  # 短标记提前停返回用
    previous_key: _FunctionalKey | None = None
    selection: ModuleSelection | None = None
    # 手动全文 / 澄清历史存在才传对应关键字——不传时保持旧签名（既有假 LLM
    # 零改动；缺省空 = 旧行为）。合并成单次 ** 展开：mypy 对多个异构 **dict
    # 的展开按位置错配参数（manual_fulltexts 单展开先例只容一个，加第二个
    # clarifications 即误报）。
    optional_kwargs: dict[str, Any] = {
        **({"manual_fulltexts": manual_fulltexts} if manual_fulltexts else {}),
        **({"clarifications": clarifications} if clarifications else {}),
        **({"qa_material": qa_material} if qa_material else {}),
    }
    for round_no in range(1, max_rounds + 1):
        _emit(
            progress_emitter,
            ProgressEvent(type=EVENT_ROUND, round=round_no, round_total=max_rounds),
        )
        round_topic = (
            _revision_prompt(numbered, previous) if round_no > 1 else numbered
        )
        if references or manual_fulltexts:
            if round_no == 1 and reader is not None and references:
                # 两级注入第一级：先清单；点名全文 → 回读（第二级），全文进上下文；
                # 手动全文第一级就带（全文直读强制，不依赖模型点名）
                first = llm.select_modules(
                    round_topic,
                    manifest_summaries,
                    references,
                    **optional_kwargs,
                )
                if first.reference_ids:
                    fulltexts = {
                        entry_id: reader(entry_id) for entry_id in first.reference_ids
                    }
                    selection = llm.select_modules(
                        round_topic,
                        manifest_summaries,
                        references,
                        fulltexts,
                        **optional_kwargs,
                    )
                else:
                    selection = first
            else:
                # 第 2 轮起：已读全文照旧带上（恰好两级，不再注入新全文）；
                # 没有想读的全文时保持清单级形状（空全文不进提示词）
                selection = llm.select_modules(
                    round_topic,
                    manifest_summaries,
                    references,
                    fulltexts or None,
                    **optional_kwargs,
                )
        else:
            selection = llm.select_modules(
                round_topic, manifest_summaries, **optional_kwargs
            )
        if selection.questions:
            return selection  # 补问：暂停收敛，向用户补问（不以推荐收尾）
        # 核验轮短标记（工单 01）：模型自报与上一轮一致 → 用上一轮结果提前停
        # （省掉全量输出核验轮的 2-4 min；第 1 轮出现 converged 当空结果忽略——
        # 模型违反"仅核验轮可输出"指令，requirements 空 → key 空照常比较）
        if selection.converged and previous_key is not None:
            _emit(
                progress_emitter,
                ProgressEvent(type=EVENT_CONVERGED, round=round_no),
            )
            assert previous_selection is not None  # previous_key 非空 ⇒ 已赋值
            return previous_selection
        key = _functional_layer_key(selection)
        if previous_key is not None and key == previous_key:
            _emit(
                progress_emitter,
                ProgressEvent(type=EVENT_CONVERGED, round=round_no),
            )
            return selection
        previous = selection.requirements
        previous_selection = selection
        previous_key = key
    assert selection is not None  # max_rounds ≥ 1，循环体必赋值
    return selection  # 上限轮次到：以最后一轮为准（不再多问）


# ---------------------------------------------------------------------------
# 推荐两阶段编排（工单 recommend-orchestration-homing/01）：澄清先行 → 收敛 →
# done 载荷组装。单域函数收口 /api/recommend 路由闭包的全部编排——路由只剩
# 取参 + 转调 + sse 包装；终态（question / done）一律由本函数发出，路由不分支。
# TopicContext 仅 TYPE_CHECKING（generator 运行时依赖本层，反向导入成环）。
# ---------------------------------------------------------------------------


def vision_answerable(question: str, problem_text: str) -> bool:
    """机械判定「图面信息问题」（工单 recommend-vision-qa/01 + clarify-vision-relax/01）。

    放宽后合取：①题面引用过图（题面含「图N」引用——`[图N 标注` 的图注尾巴
    同样算引用；未引用过图 = 纯正文问题，不打扰视觉通道）；②问题点名题面
    引用过的图号（双方都按「图N」正则提取编号再求交——子串匹配会把「图1」
    误命中「图10」）**或**命中图内信息关键词（VISION_ANSWERABLE_KEYWORDS
    单源）。

    放宽动机（真机 2021F 用户原话「这三个问题都是应该AI从之前的图片中就能
    找到答案的」）：未点名图但问的是图内信息（如「数字标号纸张放置在走廊
    什么位置？」）此前直接漏判转问用户；现在交视觉通道从原题渲染页找答案
    （渲染页含正文 + 图，答案往往就在页面上）。放宽的误判风险由视觉消化
    安全网兜底：答不上（否定词 / 空答案）→ 照旧转问用户——误判代价 = 一次
    缓存视觉调用，而不是丢问题。
    """
    if not question or not problem_text:
        return False
    topic_figures = set(re.findall(r"图\s*(\d+)", problem_text))
    if not topic_figures:
        return False
    question_figures = set(re.findall(r"图\s*(\d+)", question))
    if topic_figures & question_figures:
        return True
    return any(keyword in question for keyword in VISION_ANSWERABLE_KEYWORDS)


def _answer_vision_questions(
    questions: Sequence[str],
    vision_qa: Callable[[str], str | None] | None,
    problem_text: str,
    clarifications: Sequence[tuple[str, str]],
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """逐条尝试视觉消化（工单 recommend-vision-qa/01）。

    命中的图内问题交给 vision_qa：答出非空内容 → 从待问清单移除、以
    (问题, 答案) 并入澄清历史（与用户回答同构，题面后独立段）；答不上 /
    空答案 / 未注入回调 / 非图内问题 → 保留待问。返回 (剩余待问, 合并后的
    澄清历史)。纯函数，视觉失败永不阻塞主流程。
    """
    if not questions or vision_qa is None:
        return tuple(questions), tuple(clarifications)
    remaining: list[str] = []
    merged = list(clarifications)
    for question in questions:
        if vision_answerable(question, problem_text):
            answer = vision_qa(question)
            if answer and answer.strip():
                merged.append((question, answer.strip()))
                continue
        remaining.append(question)
    return tuple(remaining), tuple(merged)


def _group_card(
    group: ExclusiveGroup,
    members: Sequence[ExclusiveGroupMember],
    *,
    hint: bool,
    recommended: Sequence[str],
) -> dict[str, Any]:
    """选择卡 dict 构造（命中卡与 hint 卡共用）。"""
    return {
        "id": group.id,
        "label": group.label,
        "hint": hint,
        "members": [{"slug": m.slug, "role": m.role} for m in members],
        "recommended": list(recommended),
    }


def build_exclusive_groups(
    selection_modules: Sequence[str],
    group_defs: Sequence[ExclusiveGroup],
    platform: str,
    *,
    hint_module_groups: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """功能组选择卡派生（工单 recommend-exclusive-groups/02）：纯函数。

    输入 = AI 推荐 slug 集 + 库级组定义（collect_exclusive_groups 全平台
    视图）+ 目标平台。输出 = 出卡列表（命中卡在前按库登记顺序，hint-only
    卡按 hint 声明顺序在后）：
    - 命中卡：组内成员（scope_group_members 平台投影后）∩ 推荐集非空 →
      {id, label, hint: False, members: [{slug, role}], recommended:
      [命中 slug 按成员顺序]}
    - hint 卡：AI 未命中但赛题声明 hint_module_groups 的组 → hint: True、
      recommended 空（卡内无默认选中）；AI 已命中 = 只出命中卡不重复
    - 单成员组不出卡（无可选）；hint id 库内无对应组 → 静默忽略（不炸推荐）。
    """
    selected = set(selection_modules)
    hit_ids: set[str] = set()
    cards: list[dict[str, Any]] = []
    for group in group_defs:
        members = scope_group_members(group.members, platform)
        if len(members) < 2:
            continue  # 单成员组 = 无可选，不出卡
        recommended = [member.slug for member in members if member.slug in selected]
        if not recommended:
            continue  # 未命中：留给 hint 兜底（若有声明）
        hit_ids.add(group.id)
        cards.append(_group_card(group, members, hint=False, recommended=recommended))
    seen_hint: set[str] = set()
    for hint_id in hint_module_groups:
        if hint_id in hit_ids or hint_id in seen_hint:
            continue
        seen_hint.add(hint_id)
        hint_group = next((g for g in group_defs if g.id == hint_id), None)
        if hint_group is None:
            continue  # hint id 库内无对应组：静默忽略
        members = scope_group_members(hint_group.members, platform)
        if len(members) < 2:
            continue
        cards.append(_group_card(hint_group, members, hint=True, recommended=()))
    return cards


def run_recommendation(
    topic: TopicContext,
    llm: LLM,
    clarifications: Sequence[tuple[str, str]] = (),
    *,
    emit: SseEmitter,
    max_rounds: int = SELECT_CONVERGENCE_MAX_ROUNDS,
    platform: str = "",
    qa_material: str = "",
    vision_qa: Callable[[str], str | None] | None = None,
) -> None:
    """/api/recommend 的两阶段编排（工单 01 推荐先澄清后收敛）。

    首跑（无澄清历史）澄清阶段先行：先调 llm.clarify（只看题面），仍有疑问
    → question 事件收尾（不发 round——澄清阶段不属于收敛轮次，补问不再作废
    已跑轮次）；澄清空 = 澄清完成，才进收敛循环。有澄清历史时跳过澄清门
    （工单 recommend-speedup/01）：历史段 + 已答不重问已由 select_modules
    承载，clarify 的补问功能被收敛循环覆盖——每轮补问省一次串行 LLM 调用
    （约 2-4 min）；"一轮问全"（A 棱镜）摊薄"答案没清完疑问"的风险，
    select_modules 本身仍会补问，不会漏问。

    按需视觉问答（工单 recommend-vision-qa/01）：澄清门与收敛补问的待问
    问题在问用户之前，先经 vision_qa 回调逐条尝试视觉消化（vision_answerable
    机械判定图内信息问题 → 回调返回视觉答案 → 以 (问题, 答案) 并入澄清历史
    → 从待问清单移除）。剩余待问才发 question 事件；被视觉全部消化 → 带
    答案直接进收敛（澄清门场景）或重跑一轮收敛（收敛补问场景，最多一次——
    重跑后仍有疑问直接问用户，视觉已尽力，防问问题链死循环）。回调未注入
    （未配置视觉 / 无原图 / 调用方不接入）= 行为与现状逐字节一致。

    收敛循环（select_modules_convergent）：功能需求层两轮一致即停、上限 4 轮
    （成本 2-4 轮 × 2-4K token），轮次经 emit.progress 推送；循环内模型拿不准
    （罕见兜底）以 question 事件收尾（questions 数组，回答并入历史重发）。
    循环收敛成功 → done 载荷：顶层 modules[] 格式与旧契约一致（下游
    selectedSlugs / expand / generate 零改动）+ requirements（功能需求层：
    需求 / 对照句 / 库内命中 / 库外建议——库外建议仅展示、不进工程）；
    topic.key 非空（识别到历史赛题）才附加 topic_id；最终参考清单 = 锚定
    命中（auto）∪ 手动选（manual）并集去重，同一条目只出现一次且手动优先
    标注（用户显式选择），platform 随条目带出。

    装配素材（题面全文 / 清单段 / 全文回读 / 手动参考）全在 topic（装配点
    resolve_topic_context 一次备好），本函数只消费。返回 None——终态一律
    发出，路由不再分支（run 抛错由 sse 运行器补发 error 终态）。
    """
    # 首跑（无澄清历史）才走澄清门（工单 01）：只看题面，仍有疑问 → question
    # 事件收尾（不发 round——澄清阶段不属于收敛轮次，补问不再作废已跑轮次）；
    # 空 = 澄清完成，进收敛循环。有澄清历史时跳过 clarify（工单
    # recommend-speedup/01）：select_modules 已带历史段 + 已答不重问，补问
    # 功能被收敛循环覆盖——每轮补问省一次串行 LLM 调用；"一轮问全"（A 棱镜）
    # 摊薄"答案没清完疑问"的风险，select_modules 本身仍会补问、不会漏问。
    # 按需视觉问答（工单 recommend-vision-qa/01）：待问问题先过 vision_qa
    # 视觉消化（答案并入澄清历史），剩余才问用户。
    def _converge(clarifs: Sequence[tuple[str, str]]) -> ModuleSelection:
        """收敛循环局部装配（澄清历史每次带当前值——视觉消化后重跑同参）。"""
        return select_modules_convergent(
            llm,
            topic.problem_text,  # 识别到时题面用库内全文；no-topic 形 = 粘贴原样
            topic.manifest_summaries,
            references=topic.suggestions,
            reader=topic.read_fulltext,
            progress_emitter=emit.progress,
            manual_fulltexts=topic.manual_fulltexts,
            clarifications=clarifs,  # 澄清历史贯穿收敛循环（题面后独立段）
            max_rounds=max_rounds,  # 轮数上限可配置（工单 01，设置项透传）
            qa_material=qa_material,  # 赛题答疑 Q&A（工单 qa-material/01）
        )

    if not clarifications:
        pending = llm.clarify(topic.problem_text, clarifications)
        pending, clarifications = _answer_vision_questions(
            pending, vision_qa, topic.problem_text, clarifications
        )
        if pending:
            emit.question({"questions": list(pending)})
            return
    selection = _converge(clarifications)
    if selection.questions:
        remaining, clarifications = _answer_vision_questions(
            selection.questions, vision_qa, topic.problem_text, clarifications
        )
        if remaining:
            emit.question({"questions": list(remaining)})
            return
        # 视觉消化了全部补问：答案已并入历史 → 重跑收敛（"回答并入历史重发"
        # 既有语义）；重跑后仍有疑问直接问用户（视觉已尽力，防问问题链死循环）
        selection = _converge(clarifications)
        if selection.questions:
            emit.question({"questions": list(selection.questions)})
            return
    result: dict[str, Any] = {
        "modules": [
            {"slug": slug, "reason": selection.reasons.get(slug, "")}
            for slug in selection.modules
        ],
        "requirements": [
            requirement.to_dict()
            for requirement in selection.requirements
        ],
    }
    if selection.score_points:
        result["score_points"] = [
            point.to_dict() for point in selection.score_points
        ]
    # （前端据此回填实例卡，用户确认后仍可增删改）；无实例的选择不落键
    # （旧载荷逐字节不变 = 单默认实例旧行为）
    if selection.instances:
        result["instances"] = {
            slug: [instance.to_dict() for instance in instances]
            for slug, instances in selection.instances.items()
        }
    else:
        # 多实例默认兜底（工单 instance-default-fallback/01）：AI 没猜实例
        # （题面无数量）且命中多实例模块 → 按平台默认清单自动填入——与
        # 「不配置 = 单默认实例」的生成结果等价（stm32 红黄绿 / mspm0 单
        # 实例），实例卡直接可见可改；空 platform / 无多实例命中 = 不落键
        default_instances = _default_instances_for(
            selection.modules, topic.manifest_summaries, platform
        )
        if default_instances:
            result["instances"] = {
                slug: [instance.to_dict() for instance in instances]
                for slug, instances in default_instances.items()
            }
    if topic.key:
        result["topic_id"] = topic.key
    # 最终参考清单（透明闭环）：锚定命中 = auto，手动选 = manual；
    # 同一条目既锚定又手动只出现一次（手动优先标注——用户显式选择）；
    # platform（工单 01）随条目带出，前端按它显示平台标注
    manual_ids = {ref.id for ref in topic.manual_references}
    result["references"] = [
        {"id": ref.id, "title": ref.title, "source": "auto", "platform": ref.platform}
        for ref in topic.references
        if ref.id not in manual_ids
    ] + [
        {"id": ref.id, "title": ref.title, "source": "manual", "platform": ref.platform}
        for ref in topic.manual_references
    ]
    # 功能组选择卡（工单 recommend-exclusive-groups/02）：命中组 / hint 组
    # 机器侧派生（AI 输出契约不变——组不新增模型字段）；无组库或全空 →
    # 不落键（旧载荷逐字节兼容）
    group_cards = build_exclusive_groups(
        selection.modules,
        topic.exclusive_groups,
        platform,
        hint_module_groups=topic.hint_module_groups,
    )
    if group_cards:
        result["exclusive_groups"] = group_cards
    emit.done(result)


# ---------------------------------------------------------------------------
# 请求层 instances 载荷解析（工单 module-multi-instance/04）：纯函数，照
# build_module_selection 先例——webapp 只取参转调，域判决单址。
#
# instances 载荷形状（spec）：{slug: [{name, variant, pin}]}；缺省 / 空 =
# 空 dict（旧请求零改动 = 单默认实例）。null variant / pin 归一为空串
# （ModuleInstance 只认空串语义：空串 variant = 非内置色、空串 pin = 自动
# 分配默认脚）。上限守卫（>max）在 expand_instances，不在这里。
# ---------------------------------------------------------------------------


def default_instances_for_multi(
    multi_slugs: Sequence[str], platform: str
) -> dict[str, tuple[ModuleInstance, ...]]:
    """多实例 slug → 平台默认清单（default_instance_plan 单源，唯一决策点）。

    空 platform / 无平台默认的 slug → 不落键（旧载荷不变）。
    """
    if not platform:
        return {}
    result: dict[str, tuple[ModuleInstance, ...]] = {}
    for slug in multi_slugs:
        defaults = default_instance_plan(slug, platform)
        if defaults:
            result[slug] = defaults
    return result


def _default_instances_for(
    modules: Sequence[str],
    summaries: Sequence[ManifestSummary],
    platform: str,
) -> dict[str, tuple[ModuleInstance, ...]]:
    """AI 没猜实例时的平台默认清单（工单 instance-default-fallback/01）。

    命中模块里带 multi_instance 能力的 slug → 各自的平台默认清单
    （default_instance_plan 单源）；空 platform / 无多实例命中 / 该 slug 无
    平台默认 → 空 dict（不落键，旧载荷不变）。
    """
    if not platform:
        return {}
    multi = {summary.slug for summary in summaries if summary.multi_instance is not None}
    return default_instances_for_multi(
        [slug for slug in modules if slug in multi], platform
    )


def parse_instances(
    raw: Any,
    *,
    known_slugs: Sequence[str],
) -> dict[str, tuple[ModuleInstance, ...]]:
    """webapp 请求体 instances 字段 → {slug: (ModuleInstance, ...)}。

    严格校验（任何非法抛 SelectionError → 400 中文）：instances 必须是对象；
    每个键是非空 slug 且在最终进工程集内（选中 ∪ 依赖展开，工单
    instance-config-deps/01——依赖带入的多实例模块如 led_beep→led 也允许；
    未进工程 = 幻觉 / 乱编，大声失败）；每个值是对象数组；每个实例 name 非空
    字符串、variant/pin 为字符串（null 归一空串）。缺省 None / 空对象 = 空
    dict（旧行为）。
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SelectionError("instances 必须是对象")
    if not raw:
        return {}
    known = set(known_slugs)
    result: dict[str, tuple[ModuleInstance, ...]] = {}
    for slug, items in raw.items():
        if not isinstance(slug, str) or not slug:
            raise SelectionError("instances 的键必须是非空模块 slug")
        if slug not in known:
            raise SelectionError(f"实例清单包含未进工程的模块：{slug}")
        if not isinstance(items, list):
            raise SelectionError(f"实例清单 {slug} 必须是数组")
        parsed: list[ModuleInstance] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise SelectionError(f"实例 {slug}[{index}] 必须是对象")
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                raise SelectionError(f"实例 {slug}[{index}] 缺 name 或为空")
            variant = item.get("variant")
            if variant is None:
                variant = ""
            elif not isinstance(variant, str):
                raise SelectionError(f"实例 {slug}[{index}] 的 variant 必须是字符串")
            pin = item.get("pin")
            if pin is None:
                pin = ""
            elif not isinstance(pin, str):
                raise SelectionError(f"实例 {slug}[{index}] 的 pin 必须是字符串")
            parsed.append(
                ModuleInstance(
                    name=name.strip(),
                    variant=variant.strip(),
                    pin=pin.strip(),
                )
            )
        result[slug] = tuple(parsed)
    return result


# ---------------------------------------------------------------------------
# 实例展开 + 默认脚分配（工单 module-multi-instance/02）：纯函数，确定性
#
# resolve_selection 之后对声明了 multi_instance 的模块执行「实例展开」：给定
# 实例清单，合成每个具体实例的 (slug, 实例号, 宏名, 默认脚) 计划。通用层只
# 做「合成具体实例 + 分配默认脚」，不产代码（渲染归 instance_render 的 hook）。
#
# 命名与默认脚的具体语义（内置色 / 功能变体 → 宏名、指定脚、首实例脚）按
# slug 落策略表（INSTANCE_POLICIES，key-multi-instance/01 下沉）：led 行 =
# 内置色 red/yellow/green → LED_RED/LED_YELLOW/LED_GREEN、同名第 2 次起
# _2/_3 后缀、非内置按创建顺序 LED_1..n；默认脚 stm32 红/黄/绿优先 PC13/14/15、
# mspm0 首个实例优先 PA15，其余按 board 顺序取第一个未被本模块占用且非指定脚
# 的 io 脚（同模块内去重，不跨模块全局扫描——spec D3）。key 行在 04 加入。
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiInstancePolicy:
    """一个多实例模块的展开策略：宏命名规则 + 默认脚规则 + 可用脚能力。

    builtin_macros = 变体 token → 通道宏名（red → LED_RED；start → KEY_START）；
    builtin_pins = 平台 → {变体 token → 变体指定默认脚}（led 三色 stm32
        PC13/14/15——仅「变体语义」分配；位置语义见 first_pin）；
    first_pin = 平台 → 首实例默认脚（位置语义：led mspm0 PA15；key 双平台
        PB3/PA2——首个实例 = 板载默认键脚）；
    pin_capability = 自动分配的可用脚能力（gpio_out / gpio_in …，照角色类型）；
    macro_prefix = 非内置回退宏前缀（LED_ / KEY_ …）；
    variant_label = 变体中文标签（提示词可见文案；led = 颜色、key = 功能——
        词表与标签同源在策略行，改名只改这一处）。
    """

    builtin_macros: Mapping[str, str]
    builtin_pins: Mapping[str, Mapping[str, str]]
    first_pin: Mapping[str, str]
    pin_capability: str
    macro_prefix: str
    variant_label: str


# 字面量单源：宏名映射 / 指定脚 / 首实例脚 / 变体标签只写在这里（改词表只改
# 这一处）；声明了 multi_instance 但未登记 slug = 大声失败（防半吊子 manifest，
# 见 expand_instances）。
INSTANCE_POLICIES: Mapping[str, MultiInstancePolicy] = {
    "led": MultiInstancePolicy(
        builtin_macros={
            "red": "LED_RED",
            "yellow": "LED_YELLOW",
            "green": "LED_GREEN",
        },
        builtin_pins={
            PLATFORM_STM32: {"red": "PC13", "yellow": "PC14", "green": "PC15"},
        },
        first_pin={PLATFORM_MSPM0: "PA15"},
        pin_capability="gpio_out",
        macro_prefix="LED_",
        variant_label="颜色",
    ),
    "key": MultiInstancePolicy(
        builtin_macros={
            "start": "KEY_START",
            "stop": "KEY_STOP",
            "mode": "KEY_MODE",
            "set": "KEY_SET",
        },
        builtin_pins={},
        first_pin={PLATFORM_STM32: "PB3", PLATFORM_MSPM0: "PA2"},
        pin_capability="gpio_in",
        macro_prefix="KEY_",
        variant_label="功能",
    ),
}


def multi_instance_vocab() -> Mapping[str, tuple[str, ...]]:
    """多实例模块的内置变体 token 词表（策略表投影，按策略登记序）。

    提示词可见契约与解析校验同源消费：改词表只改 INSTANCE_POLICIES 一行
    （key-multi-instance/05 泛化替代了 led 单表时代的 LED_COLOR_MACROS）。
    """
    return {
        slug: tuple(policy.builtin_macros)
        for slug, policy in INSTANCE_POLICIES.items()
    }


def multi_instance_labels() -> Mapping[str, str]:
    """多实例模块的变体中文标签（策略表投影：led → 颜色、key → 功能）。

    提示词可见文案与词表同源在策略行（标签与 token 一起改，无第二处真源）。
    """
    return {
        slug: policy.variant_label for slug, policy in INSTANCE_POLICIES.items()
    }


@dataclass(frozen=True)
class ExpandedInstance:
    """实例展开计划的一行：一个具体实例的通道宏名 + 默认脚。

    slug = 模块 slug（回显，渲染器据此找模块）；index = 实例号（1 起，同模块
    内唯一，渲染器据此命名每实例 pin 宏）；macro = 通道宏名（LED_RED /
    LED_RED_2 / LED_1 …）；pin = 默认脚（显式 pin 覆盖优先，否则自动分配）。
    """

    slug: str
    index: int
    macro: str
    pin: str


def default_instance_plan(
    slug: str, platform: str
) -> tuple[ModuleInstance, ...]:
    """多实例模块的平台默认实例（工单 instance-default-fallback/01 单源 +
    key-multi-instance/04 泛化）。

    与「不配置 = 单默认实例」的生成结果等价（渲染零回归）：led — stm32 =
    红黄绿 3 实例（对应母版默认 led_instances.h 三通道）、mspm0 = 单实例无
    颜色（LED_1 通用编号 + 默认脚，对应库内默认单通道）；key — 双平台各
    1 实例（「按键」/ start，对应板载启动键 + 默认 key_instances.h 单通道）；
    未知 slug / 空平台 = 空（不兜底）。
    """
    if slug == "led":
        if platform == PLATFORM_STM32:
            return (
                ModuleInstance(name="红灯", variant="red"),
                ModuleInstance(name="黄灯", variant="yellow"),
                ModuleInstance(name="绿灯", variant="green"),
            )
        if platform == PLATFORM_MSPM0:
            return (ModuleInstance(name="LED", variant=""),)
        return ()
    if slug == "key":
        if platform in (PLATFORM_STM32, PLATFORM_MSPM0):
            return (ModuleInstance(name="按键", variant="start"),)
        return ()
    return ()


def expand_instances(
    manifest: ModuleManifest,
    instances: Sequence[ModuleInstance],
    platform: str,
    board: Board,
) -> tuple[ExpandedInstance, ...]:
    """实例清单 → (slug, 实例号, 宏名, 默认脚) 计划（纯函数，同输入同输出）。

    manifest.multi_instance 缺省（不支持多实例）时，非空实例清单 = 调用方错误
    （SelectionError）；空实例清单 = 单默认实例（旧行为，返回空计划，调用方
    走单实例路径）。声明了 multi_instance 但策略表未登记 slug = 大声失败
    （含空清单——破损 manifest 不静默走单实例，防半吊子声明，key-multi-instance/01）。
    实例数 > max = 上限守卫（SelectionError，中文可读）。

    显式 pin 覆盖优先；自动分配只做同模块内去重（不跨模块全局扫描）——与
    母版固定占用 / 其他模块默认脚冲突留给用户重绑 + generate-time 门禁当
    安全网（spec D3，不新增「找不到空闲脚」的硬 400）。
    """
    spec = manifest.multi_instance
    if spec is None:
        if instances:
            raise SelectionError(f"模块 {manifest.slug} 不支持多实例")
        return ()
    policy = INSTANCE_POLICIES.get(manifest.slug)
    if policy is None:
        raise SelectionError(
            f"模块 {manifest.slug} 声明了多实例但未登记展开策略"
            "（宏名 / 默认脚语义必须显式登记）"
        )
    if len(instances) > spec.max:
        raise SelectionError(
            f"模块 {manifest.slug} 实例数 {len(instances)} 超过上限 {spec.max}"
        )
    designated = _designated_pins(policy, platform)
    plan: list[ExpandedInstance] = []
    used: set[str] = set()
    builtin_counts: dict[str, int] = {}
    non_builtin_seq = 0
    for index, instance in enumerate(instances, 1):
        variant = (instance.variant or "").strip()
        occurrence = 0
        if variant in policy.builtin_macros:
            builtin_counts[variant] = builtin_counts.get(variant, 0) + 1
            occurrence = builtin_counts[variant]
            macro = policy.builtin_macros[variant]
            if occurrence > 1:
                macro = f"{macro}_{occurrence}"
        else:
            non_builtin_seq += 1
            macro = f"{policy.macro_prefix}{non_builtin_seq}"
        pin = instance.pin or _default_instance_pin(
            policy, platform, variant, index, occurrence, board, used, designated
        )
        used.add(pin)
        plan.append(
            ExpandedInstance(slug=manifest.slug, index=index, macro=macro, pin=pin)
        )
    return tuple(plan)


def _designated_pins(
    policy: MultiInstancePolicy, platform: str
) -> frozenset[str]:
    """策略的「指定脚集合」：变体指定脚（该平台维度）∪ 平台首实例脚——

    board 顺序扫描跳过（重复变体 / 非内置不抢占指定脚，led 先例）。
    """
    by_platform = policy.builtin_pins.get(platform, {})
    designated = set(by_platform.values())
    if platform in policy.first_pin:
        designated.add(policy.first_pin[platform])
    return frozenset(designated)


def _default_instance_pin(
    policy: MultiInstancePolicy,
    platform: str,
    variant: str,
    index: int,
    occurrence: int,
    board: Board,
    used: set[str],
    designated: frozenset[str],
) -> str:
    """实例默认脚（显式 pin 之外的自动分配）。

    优先级：变体指定脚（首次出现）→ 平台首实例脚（位置语义，index 1）→
    board 顺序首个可用能力脚（跳过指定脚 + 同模块已用）。occurrence 对非
    内置变体无意义（= 0）。
    """
    if occurrence == 1 and variant in policy.builtin_pins.get(platform, {}):
        return policy.builtin_pins[platform][variant]
    if index == 1 and platform in policy.first_pin:
        return policy.first_pin[platform]
    return _next_available_pin(policy, board, used, designated)


def _next_available_pin(
    policy: MultiInstancePolicy,
    board: Board,
    used: set[str],
    designated: frozenset[str],
) -> str:
    """board 顺序首个可用能力脚：未被本模块占用、非指定脚、能力命中
    （gpio_out / gpio_in …）。耗尽 = 不变量破坏（max 8 远小于排针 io 脚数），
    大声失败。"""
    for pin in board.pins:
        if (
            pin.name not in used
            and pin.name not in designated
            and pin_supports(pin, policy.pin_capability)
        ):
            return pin.name
    raise SelectionError("没有可用的 io 脚（模块实例数超出排针可用脚）")
