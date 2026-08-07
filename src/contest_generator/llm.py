"""LLM 客户端抽象与生产实现。

生产实现 DeepSeekLLM 走 DeepSeek Chat Completions API（base_url / api_key /
模型来自本机配置文件 config.py）；HTTP 传输可注入假件，网络调用不进测试。
LLM 承担四个职责：赛题→模块选择、main.c 骨架生成、模块简介生成与校验、
母版提炼判定（冲突/独有文件 → 保留/合并/剔除；两阶段：先读全文出摘要，
再基于摘要判定）。请求体有大小控制：所有嵌内容调用（赛题 / 接口块 / 文件
全文）超长截断（带标注，AI 知道读到的是截断内容）、摘要阶段多文件按预算
分批发送、发送前有序列化体积断言兜底——DeepSeek 网关对请求体有硬性大小
限制，一次性全发会 413。
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence, TypeVar

from .config import AppConfig
from .manifest import ModuleManifest
from .report import ACTION_MERGE, FileDecision, JudgmentFile, ReportError

# ---------------------------------------------------------------------------
# 截断标注契约（唯一出处）
#
# 所有嵌内容调用（赛题 / 接口块 / 文件全文）截断时都带标注；标注措辞的
# 唯一出处在此。系统提示词与用户提示词必须包含它（双端契约测试断言）——
# 只改一处会让模型在另一侧消息里以为读到的是完整内容（ticket 06 的
# 双端漂移教训：曾只改系统提示词、漏改用户提示词，提炼当场失败）。
# ---------------------------------------------------------------------------
TRUNCATION_NOTICE = "按所见内容判断，不要脑补缺失部分"

SELECT_SYSTEM_PROMPT = (
    "你是电子设计竞赛（电赛）嵌入式开发助手，熟悉 MSPM0G3507（CCS）与 "
    "STM32F103C8T6（Keil5）两条平台线。根据赛题在给定的模块库中选择合适的"
    "现成模块（赛题文本过长可能被截断，见末尾标注，" + TRUNCATION_NOTICE
    + "），为每个推荐给出简短理由（中文）。只输出 JSON 对象。"
)

SKELETON_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。为赛题生成 main.c 骨架（赛题文本 / 模块接口过长"
    "可能被截断，见末尾标注，" + TRUNCATION_NOTICE + "）：按所选模块的头文件"
    "接口排好初始化序列，带注释说明与预留编写区（TODO）。只调用给定接口中"
    "真实存在的函数，绝不凭空造函数；不确定的调用写成注释占位，保证骨架可编译。"
)

SUMMARY_SYSTEM_PROMPT = "你是嵌入式 C 工程师。用中文一句话总结这段代码的功能，作为模块库简介。"

# 专用性检查要求的唯一表述：系统提示词与用户提示词在同一个 API 调用里都要说
# 这件事（ticket 06 双端漂移教训：判定范围曾只改系统提示词、漏改用户提示词，
# 模型按用户消息跳过公共文件当场失败）。此常量是唯一出处：改专用性检查只动
# 这里（契约测试 test_llm 双端断言）。
VALIDATION_SPECIFICITY_RULE = (
    "同时检查专用性声明：简介声称\"XX 题专用\"时，代码必须有对应的赛题专用逻辑"
    "（题目参数、判定流程、赛题数据结构等）。简介称专用但代码是通用驱动（无任何"
    "赛题相关逻辑）→ 判为不一致，issues 指出具体差异；代码明显是赛题专用逻辑"
    "（绑定具体赛题）而简介未标注\"XX 题专用\" → 同样判为不一致，issues 提示"
    "在简介中补充专用性标注。"
)

VALIDATION_SYSTEM_PROMPT = (
    "你是嵌入式 C 工程师。判断给定的模块简介与实际代码是否一致：简介描述的功能、"
    "接口、行为是否与代码相符。"
    + VALIDATION_SPECIFICITY_RULE
    + "不一致时用中文指出具体差异。只输出 JSON 对象。"
)

JUDGMENT_SUMMARY_SYSTEM_PROMPT = (
    "你是嵌入式开发工程整理助手。导入的多个同平台旧工程里，有些文件需要判定"
    "去留：同一路径在不同工程里内容不同（冲突），或只出现在部分工程（独有），"
    "或所有工程内容一致（公共，同样要判）。逐文件读全文（超长文件已截断并在"
    "末尾标注，" + TRUNCATION_NOTICE + "）后，为每个内容版本用"
    "中文写一段简短摘要：说明它实现什么功能、是否通用、是否基础建设必需。"
    "必须为列出的每个文件输出摘要，一个都不能少。只输出 JSON 对象。"
)

# 判定范围与判据的唯一表述：系统提示词与用户提示词在同一个 API 调用里都要
# 说这件事，各自硬编码会静默漂移——ticket 06 曾只改系统提示词、漏改用户提示
# 词，模型按用户消息跳过公共文件，多工程提炼当场失败（"提炼报告缺少判定"）。
# 此常量是唯一出处：改判定范围 / 判据只动这里（契约测试 test_llm 双端断言）。
JUDGMENT_SCOPE = (
    "判定范围 = 公共 + 冲突 + 独有（全部文件）逐个判定。判定唯一判据：读文件"
    "内容后判断它是否通用、是否基础建设必需（ADR 0001）——官方外设库（STM32 "
    "标准外设库 / TI driverlib）、平台基础设施（启动 / system / CMSIS / 链接"
    "脚本 / 工程配置）、通用基础封装（如 delay 延时，写任何工程都要用）→ "
    "keep；具体项目 / 具体硬件相关的业务代码（传感器驱动、外设封装、赛题逻辑）"
    "→ exclude。不看重复次数与出现范围——公共文件（所有工程内容一致）同样"
    "逐个判定，可保留可剔除，内容一样不等于基础建设必需。工程配置文件"
    "（.uvprojx / .uvoptx / .cproject / .project 等）由确定性规则处理、不参与"
    "判定（ADR 0003）——AI 给出这类路径的判定是越界，会被系统拒绝。"
)

DISTILL_SYSTEM_PROMPT = (
    "你是嵌入式开发工程整理助手。用户导入了多个同平台旧工程，你需要根据文件"
    "内容摘要与结构配置对比判定哪些文件应该进母版（母版 = 空的最小系统板工程，"
    "能直接编译烧录）。"
    + JUDGMENT_SCOPE
    + "动作词表：keep（保留）/ merge（整合：同一路径多份内容不同时，读多份后"
    "整合出通用版本，选一份只是特例，必须给出整合产物全文与整合说明）/ "
    "exclude（剔除）。必须为每个待判文件给出动作，一个都不能少。只输出 JSON 对象。"
)

# 判定素材内容上限（字符）：第一阶段提示词把每个内容版本全文嵌入，真实旧
# 工程里的巨型源码（如 stm32f10x.h ~800KB 标准库头）全文嵌入会撑爆上下文
# （判例 08：三个真实工程修复前判定素材 47.6M 字符，修复后按此上限嵌入
# 29 万字符）。截断只影响发送素材（文件头足以判断性质），keep 落盘仍复制
# 工程原文全文，不受截断影响。该上限同时是所有嵌内容调用（赛题 / 接口块 /
# 简介校验代码）的统一截断上限——_truncate_content 走这里。
JUDGMENT_CONTENT_CAP = 4000

# 两阶段输出的补问上限：模型一次输出大量 JSON 条目时偶发丢条目（判例 08：
# 115 个文件一次返回漏了 1 个），严格解析失败后只对缺失路径补问，最多补问
# 这么轮；仍缺失就大声失败——宁可失败也不带病进下一阶段。
SUMMARY_RETRY_LIMIT = 3

# 判定分批大小：一次问太多文件，模型会系统性漏掉小配置文件 / 点文件
# （判例 08：115 个文件一次返回漏 30 个，补问也不收敛——不是偶发，是批量
# 超载）。按此大小分批问，总输入 token 不变（每个文件只嵌入一次），漏判
# 从"必现"降为"偶发"，交给补问机制兜底。摘要阶段的分批同时受文件数上限
# （本常量，模型可靠性）与字符预算（MAX_SUMMARY_BATCH_CHARS，请求体上限）
# 双重约束，见 _judgment_batches。
JUDGMENT_BATCH_SIZE = 25

# 请求体预算（413 修复）：DeepSeek 网关对请求体有硬性大小限制（超限返回
# "413 Request Entity Too Large"），导入带标准外设库 / driverlib 的完整工程
# 时，摘要阶段把全部文件全文一次塞进一个请求必然超限。批预算远小于网关
# 限制，提示词开销与 JSON 转义不占预算余量。
MAX_SUMMARY_BATCH_CHARS = 24000  # 每批摘要请求的内容字符预算
MAX_REQUEST_BYTES = 128 * 1024  # 发送前断言：序列化请求体超过此字节数即大声失败（兜底）


def _truncate_content(content: str) -> str:
    """单内容截断（带标注）：超长内容只送前 JUDGMENT_CONTENT_CAP 字符。

    标注让 AI 明确知道读到的是截断内容（TRUNCATION_NOTICE，措辞唯一出处），
    并注明原文总长——模型不会被误导以为文件就这么短，也不脑补缺失部分。
    截断只影响发送素材（赛题 / 接口块 / 文件全文），不改数据模型；未超长
    原样返回。
    """
    if len(content) <= JUDGMENT_CONTENT_CAP:
        return content
    return (
        content[:JUDGMENT_CONTENT_CAP]
        + f"\n……（内容过长，已截断：仅展示前 {JUDGMENT_CONTENT_CAP} 字符，"
        f"原文共 {len(content)} 字符；{TRUNCATION_NOTICE}）……\n"
    )


def _extract_good_summaries(
    content: str, batch: Sequence[JudgmentFile]
) -> list[FileSummary]:
    """从一次失败的批量摘要输出里挖出能通过严格校验的条目（补问只问缺失的）。

    逐文件粒度校验（判例 08：deploy_config.json 把多内容版本合并成一条，曾让
    同批 14 个合法摘要连坐、整批重问 3 轮全废）：一个文件输出畸形只让它自己
    重问，其他文件的合法摘要照常收下；输出里非本轮批次的路径条目忽略（补问
    轮模型偶发复述已覆盖路径，不该拖累本批校验）。
    """
    try:
        data = json.loads(content)
        wanted = {f.path for f in batch}
        entries = [
            item
            for item in data.get("summaries", [])
            if isinstance(item, dict) and item.get("path") in wanted
        ]
    except (json.JSONDecodeError, AttributeError):
        return []
    good: list[FileSummary] = []
    for f in batch:
        f_entries = [e for e in entries if e.get("path") == f.path]
        if not f_entries:
            continue
        try:
            good.extend(parse_summary_report(json.dumps({"summaries": f_entries}), [f]))
            continue
        except LLMError:
            pass
        # 模型把多内容版本合并成一条（判例 08：deploy_config.json 两版内容过于
        # 相似，模型屡次合并、补问不收敛）→ 确定性拆分回逐版本条目再校验
        reconciled = _split_merged_versions(f, f_entries)
        if reconciled is not None:
            try:
                good.extend(
                    parse_summary_report(json.dumps({"summaries": reconciled}), [f])
                )
            except LLMError:
                continue
    return good


def _split_merged_versions(
    file: JudgmentFile, entries: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """模型把多内容版本合并成一条摘要（projects 列了多个版本的全部工程名）。

    拆分条件严格：该路径发送词表含多个内容版本组，输出恰好一条条目、且其
    projects 恰好等于各版本组工程名的并集（不多不少）——此时模型读多份后
    写了一条"通用"摘要，拆回逐版本条目（摘要复制）。并集不匹配或形状不对
    则不拆（宁缺毋滥，留给补问轮）。拆出的版本摘要相同会让第二阶段看不出
    版本差异、倾向 exclude/keep 而非 merge——对内容高度相似的版本是合理近似
    （模型本来就认为差异可忽略）。
    """
    if len(file.versions) < 2 or len(entries) != 1:
        return None
    groups = file.version_groups
    union = frozenset().union(*groups)
    entry = entries[0]
    raw_versions = entry.get("versions")
    if not isinstance(raw_versions, list) or len(raw_versions) != 1:
        return None
    merged = raw_versions[0]
    if not isinstance(merged, dict):
        return None
    projects = merged.get("projects")
    summary = merged.get("summary")
    if (
        not isinstance(projects, list)
        or frozenset(projects) != union
        or not isinstance(summary, str)
        or not summary
    ):
        return None
    # 一条条目、多条 versions（模型契约：同一路径只出现一次，版本在 versions 里）
    return [
        {
            "path": file.path,
            "versions": [
                {"projects": sorted(group), "summary": summary} for group in groups
            ],
        }
    ]


def _extract_good_decisions(
    content: str,
    project_names: Sequence[str],
    batch: Sequence[FileSummary],
) -> tuple[FileDecision, ...]:
    """从一次失败的批量判定输出里挖出能通过严格校验的条目（补问只问缺失的）。

    与 _extract_good_summaries 同款逐文件粒度：一个条目畸形（如 merge 缺整合
    产物全文）只让它自己重问，好条目不连坐；输出里非本轮批次的路径条目忽略。
    """
    try:
        data = json.loads(content)
        entries = [item for item in data.get("decisions", []) if isinstance(item, dict)]
    except (json.JSONDecodeError, AttributeError):
        return ()
    good: list[FileDecision] = []
    for f in batch:
        entry = next((e for e in entries if e.get("path") == f.path), None)
        if entry is None:
            continue
        try:
            good.extend(
                parse_distillation_report(
                    json.dumps({"decisions": [entry]}), project_names
                )
            )
        except LLMError:
            continue
    return tuple(good)



class LLMError(Exception):
    """LLM 调用或输出解析失败，message 说明具体问题。"""


@dataclass(frozen=True)
class ModuleSelection:
    """赛题 → 模块选择结果（AI 的原始推荐，未展开依赖）。

    依赖展开与生成前的增删由 selection.resolve_dependencies 在用户确认后
    统一处理——AI 输出后用户还可能增删，先展开的集合无法代表最终选择。
    """

    modules: tuple[str, ...]  # 模块 slug（AI 推荐顺序）
    reasons: dict[str, str]  # slug -> 推荐理由


@dataclass(frozen=True)
class ValidationResult:
    """模块简介与实际代码的一致性校验结果。"""

    consistent: bool  # 简介与代码是否一致
    issues: str = ""  # 不一致时 AI 指出的具体差异（一致时为空）


@dataclass(frozen=True)
class VersionSummary:
    """第一阶段摘要产物：一个内容版本的摘要 + 持该版本的工程名。"""

    projects: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class FileSummary:
    """第一阶段摘要产物：一个待判文件各内容版本的摘要（第二阶段的判定素材）。"""

    path: str
    versions: tuple[VersionSummary, ...]


# 分批 / 重试循环的条目类型限定：两阶段各自只有一对输入 / 输出类型（摘要
# 阶段：待判文件 → 摘要；判定阶段：摘要 → 判定）。用限定 TypeVar 表达而非
# Protocol——mypy 2.3.0 在 from __future__ import annotations 下对 Protocol
# 属性约束的结构匹配实测不生效。
I = TypeVar("I", JudgmentFile, FileSummary)  # 批内输入条目
R = TypeVar("R", FileSummary, FileDecision)  # 批处理输出条目
T = TypeVar("T", JudgmentFile, FileSummary)


def _file_chars(file: JudgmentFile) -> int:
    """一个待判文件的发送字符数：各内容版本截断后合计（分批预算按此近似）。"""
    return sum(len(_truncate_content(version.content)) for version in file.versions)


def _split_versions(file: JudgmentFile) -> list[JudgmentFile]:
    """单文件多版本合计超预算时按版本拆成单版本条目（批内路径不重复）。"""
    return [JudgmentFile(file.path, (version,)) for version in file.versions]


def _batches(
    items: Sequence[T],
    *,
    max_chars: int | None,
    size_of: Callable[[T], int] | None = None,
    split_oversized: Callable[[T], Sequence[T]] | None = None,
) -> tuple[tuple[T, ...], ...]:
    """按文件数上限（JUDGMENT_BATCH_SIZE）分批；max_chars 给定时同时受字符预算约束。

    两个约束各自对应一个判例：预算约束防请求体超网关限制（413）；文件数上限
    防单批超载导致模型系统性漏判小配置文件（判例 08：一次问 115 个文件漏 30
    个，补问不收敛）。两个不变量同时成立——漏判从"必现"降为"偶发"，交给
    补问机制兜底。分批只按"截断后内容字符数"近似——提示词开销与 JSON 转义
    远小于网关限制，预算本身留了余量。顺序保持输入顺序：摘要产物按批拼接后
    与发送顺序一致。

    摘要阶段（max_chars=MAX_SUMMARY_BATCH_CHARS）：批内各版本全文（截断后）
    合计不超预算、文件数不超上限，单文件多版本合计超预算时按版本拆批
    （split_oversized，同批内不出现同一路径两次——parse_summary_report 按
    路径校验批次覆盖，同批重复路径会让模型输出无法自证）。
    判定阶段（max_chars=None）：摘要产物已小，无请求体预算约束（见
    _decide_distillation 的分批说明）——只按文件数上限分批。
    """
    batches: list[list[T]] = []
    current: list[T] = []
    size = 0
    for item in items:
        if max_chars is not None:
            if size_of is None or split_oversized is None:
                raise ValueError(
                    "max_chars 给定时必须同时提供 size_of 与 split_oversized"
                )
            item_size = size_of(item)
            if item_size > max_chars:
                # 单文件多版本合计超预算：按版本拆批（同批内不重复路径）
                for unit in split_oversized(item):
                    unit_size = size_of(unit)
                    if current and (
                        size + unit_size > max_chars
                        or len(current) >= JUDGMENT_BATCH_SIZE
                        or any(f.path == item.path for f in current)
                    ):
                        batches.append(current)
                        current = []
                        size = 0
                    current.append(unit)
                    size += unit_size
                continue
            if current and (
                size + item_size > max_chars
                or len(current) >= JUDGMENT_BATCH_SIZE
            ):
                batches.append(current)
                current = []
                size = 0
            current.append(item)
            size += item_size
        else:
            if current and len(current) >= JUDGMENT_BATCH_SIZE:
                batches.append(current)
                current = []
            current.append(item)
    if current:
        batches.append(current)
    return tuple(tuple(batch) for batch in batches)


# ---------------------------------------------------------------------------
# 提炼进度事件契约（唯一出处，契约测试断言；spec「事件契约」+ ADR 0004）
#
# 发射 seam：distill_master 的可选 progress_emitter 参数（默认 None，不接不
# 影响行为；测试假 LLM 与真 LLM 走同一参数）。发射点在批次循环层。done /
# error 由 webapp 层（工单 02）发射——本契约只管到 phase_done 为止。事件类型
# 集合预留 token 级流式扩展位（本次不做，spec Out of Scope）。
# ---------------------------------------------------------------------------

# 阶段名与事件类型（webapp 层 / 前端按这些键消费，改动须同步测试契约）
PHASE_SUMMARY = "summary"  # 阶段 1：逐文件读全文出摘要
PHASE_DECIDE = "decide"  # 阶段 2：基于摘要判定

EVENT_START = "start"
EVENT_BATCH_START = "batch_start"
EVENT_BATCH_DONE = "batch_done"
EVENT_RETRY = "retry"
EVENT_PHASE_DONE = "phase_done"


@dataclass(frozen=True)
class ProgressEvent:
    """提炼进度事件（事件契约的代码形态，唯一出处）。

    每个事件类型只用字段子集：start 用 judgment_count / summary_batch_count /
    decide_batch_count（均由入口先算定）；batch_start 用 phase / batch_index
    （批号，1 起）/ batch_count / paths（阶段 1 = 待判文件路径、阶段 2 = 摘要
    路径）；batch_done 用 phase / batch_index / processed_count（本阶段累计已
    处理文件数——前端直接显示"已读 X/115"，无需累加状态）；retry 用 phase /
    batch_index / retry_round（补问轮次，1 起——首次补问 = 1）/ missing_count
    （该轮要补问的缺失文件数）；phase_done 用 phase / file_count（本阶段文件数）。
    """

    type: str
    judgment_count: int = 0
    summary_batch_count: int = 0
    decide_batch_count: int = 0
    phase: str = ""
    batch_index: int = 0
    batch_count: int = 0
    paths: tuple[str, ...] = ()
    processed_count: int = 0
    retry_round: int = 0
    missing_count: int = 0
    file_count: int = 0


ProgressEmitter = Callable[[ProgressEvent], None]


def _emit(emitter: ProgressEmitter | None, event: ProgressEvent) -> None:
    """旁路发射进度事件：发射器调用失败不影响提炼主流程（spec「发射 seam」）。

    选旁路而非透传的理由：提炼的主产物是完整报告（10-15 分钟 API 调用），进度
    只是观察通道——UI 消费失败（如前端断开）最多丢进度，不该让整个提炼陪葬。
    吞掉的异常不外抛也不记录（本地单用户工具，进度通道无诊断需求）。
    """
    if emitter is None:
        return
    try:
        emitter(event)
    except Exception:
        pass


class LLM(Protocol):
    def select_modules(
        self, problem_text: str, manifest_summaries: Sequence[str]
    ) -> ModuleSelection: ...

    def generate_main_skeleton(
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str: ...

    def summarize_module(self, code: str) -> str: ...

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult: ...

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None = None,
    ) -> tuple[FileDecision, ...]: ...


def build_manifest_summaries(manifests: Sequence[ModuleManifest]) -> list[str]:
    """模块库 manifest 摘要行（喂给 LLM 的可用模块清单）。

    行格式：`- slug: description（套件: kit; 依赖: ...）`——套件段聚合各平台
    条目的 kit（去重保序，有 kit 才显示，AI 靠它分辨"哪个套件的 UWB"）；依赖
    段有依赖才显示。行格式与 _summary_slugs 的反向解析耦合：改动格式须同步两处。
    """
    lines = []
    for manifest in manifests:
        line = f"- {manifest.slug}: {manifest.description}"
        kits: list[str] = []
        seen: set[str] = set()
        for entry in manifest.platforms.values():
            if entry.kit and entry.kit not in seen:
                seen.add(entry.kit)
                kits.append(entry.kit)
        if kits:
            line += f"（套件: {'、'.join(kits)}"
            if manifest.dependencies:
                line += f"; 依赖: {', '.join(manifest.dependencies)}"
            line += "）"
        elif manifest.dependencies:
            line += f"（依赖: {', '.join(manifest.dependencies)}）"
        lines.append(line)
    return lines


class Transport(Protocol):
    """HTTP 传输接缝：生产用 urllib，测试注入假件。"""

    def post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> tuple[int, str]:
        """POST JSON，返回（HTTP 状态码, 响应体文本）。"""


class UrllibTransport:
    """基于标准库 urllib 的传输实现（项目零第三方依赖）。"""

    def post(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> tuple[int, str]:
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            # 4xx/5xx 是业务失败，状态码透传给调用方转成 LLMError
            return exc.code, exc.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as exc:
            raise LLMError(f"无法连接 LLM 服务 {url}: {exc}") from exc


class DeepSeekLLM:
    """生产 LLM：调用 DeepSeek Chat Completions，结构化输出解析为 ModuleSelection。"""

    # 大批量判定 JSON 的生成时间实测可超 120 秒（判例 08：真实工程一批 25 个
    # 文件读全文出摘要，DeepSeek 生成 JSON 需要 2-5 分钟）——120 秒读超时会让
    # 提炼流程整段失败。300 秒对单批生成足够，网络瞬断仍是偶发失败（大声报错）。
    TIMEOUT_SECONDS = 300

    def __init__(self, config: AppConfig, transport: Transport | None = None) -> None:
        self._config = config
        self._transport = transport or UrllibTransport()

    def select_modules(
        self, problem_text: str, manifest_summaries: Sequence[str]
    ) -> ModuleSelection:
        content = self._chat(
            [
                {"role": "system", "content": SELECT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _selection_user_prompt(problem_text, manifest_summaries),
                },
            ],
            json_mode=True,
        )
        return parse_module_selection(content, known_slugs=_summary_slugs(manifest_summaries))

    def generate_main_skeleton(
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str:
        return self._chat(
            [
                {"role": "system", "content": SKELETON_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _skeleton_user_prompt(problem_text, module_interfaces),
                },
            ]
        )

    def summarize_module(self, code: str) -> str:
        return self._chat(
            [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"```c\n{_truncate_content(code)}\n```",
                },
            ]
        )

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult:
        content = self._chat(
            [
                {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _validation_user_prompt(description, code),
                },
            ],
            json_mode=True,
        )
        return parse_validation_result(content)

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None = None,
    ) -> tuple[FileDecision, ...]:
        """两阶段判定：先逐文件读全文出摘要，再基于摘要判定（两次 json_mode 调用）。

        兑现 ADR 0001 的"读内容判断"——判定素材含文件内容摘要，不再只有路径
        与配置摘要。第一阶段产物（摘要）只作为第二阶段输入，不进报告；判定
        条目的 reason 由 AI 带上摘要要点。两阶段产物都走严格解析，畸形 / 缺
        摘要抛 LLMError，宁可大声失败也不带病进确认流程。

        progress_emitter：可选进度发射器（默认 None 不发射，行为与现状一致）。
        start 由入口发射且总量先算定——阶段 1 批数 = _batches 算定的批数、
        阶段 2 批数 = ⌈待判文件数 / 批大小⌉；算定后同一批序列传给阶段循环，
        start 的批次总量与实际发射的批序列严格一致（契约测试断言）。
        发射失败是旁路（_emit），不影响提炼主流程。
        """
        summary_batches = _batches(
            judgment_files,
            max_chars=MAX_SUMMARY_BATCH_CHARS,
            size_of=_file_chars,
            split_oversized=_split_versions,
        )
        decide_batch_count = math.ceil(len(judgment_files) / JUDGMENT_BATCH_SIZE)
        _emit(
            progress_emitter,
            ProgressEvent(
                type=EVENT_START,
                judgment_count=len(judgment_files),
                summary_batch_count=len(summary_batches),
                decide_batch_count=decide_batch_count,
            ),
        )
        file_summaries = self._summarize_judgment_files(
            platform, project_names, judgment_files, summary_batches, progress_emitter
        )
        return self._decide_distillation(
            platform, project_names, file_summaries, comparison_summary, progress_emitter
        )

    def _summarize_judgment_files(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        summary_batches: Sequence[Sequence[JudgmentFile]],
        progress_emitter: ProgressEmitter | None,
    ) -> tuple[FileSummary, ...]:
        """第一阶段：逐文件读全文出摘要（json_mode），解析校验为 FileSummary。

        大批量素材一次问完时，模型输出偶发丢条目 / JSON 截断（判例 08：真实
        工程 115 个文件一次返回漏 1 个；更大批量甚至系统性漏小配置文件，补问
        不收敛）。按请求体预算（MAX_SUMMARY_BATCH_CHARS，防网关 413）与文件数
        上限（JUDGMENT_BATCH_SIZE，防模型批量超载）分批问（_batches 原语，
        总输入 token 不变），批内严格解析失败后挖出已覆盖的合法条目、只对
        缺失文件补问，最多 SUMMARY_RETRY_LIMIT 轮——宁可在补问上多花一次调用，
        也不带病进第二阶段。

        批次循环层发射进度事件（契约唯一出处见 ProgressEvent）：每批开始发
        batch_start（带该批文件路径清单）、批完成发 batch_done（累计已处理文件
        数）、阶段结束发 phase_done；批数为 0 时不发射任何批事件，阶段直接完成。
        """
        results: list[FileSummary] = []
        for batch_index, batch in enumerate(summary_batches, start=1):
            _emit(
                progress_emitter,
                ProgressEvent(
                    type=EVENT_BATCH_START,
                    phase=PHASE_SUMMARY,
                    batch_index=batch_index,
                    batch_count=len(summary_batches),
                    paths=tuple(f.path for f in batch),
                ),
            )
            results.extend(
                self._summarize_batch(
                    platform, project_names, batch, progress_emitter, batch_index
                )
            )
            _emit(
                progress_emitter,
                ProgressEvent(
                    type=EVENT_BATCH_DONE,
                    phase=PHASE_SUMMARY,
                    batch_index=batch_index,
                    processed_count=len(results),
                ),
            )
        _emit(
            progress_emitter,
            ProgressEvent(
                type=EVENT_PHASE_DONE, phase=PHASE_SUMMARY, file_count=len(results)
            ),
        )
        return tuple(results)

    def _retry_batch(
        self,
        *,
        system_prompt: str,
        user_prompt: Callable[[Sequence[I]], str],
        parse: Callable[[str, Sequence[I]], Sequence[R]],
        salvage: Callable[[str, Sequence[I]], Sequence[R]],
        phase_label: str,
        items: Sequence[I],
        progress_emitter: ProgressEmitter | None,
        batch_index: int,
        phase: str,
    ) -> list[R]:
        """一批条目的重试 + 补问循环（摘要 / 判定两阶段共用的唯一原语）。

        模型一次输出大量 JSON 条目时偶发丢条目（判例 08：115 个文件一次返回
        漏了 1 个），严格解析失败后不整批重来：挖出已通过逐文件校验的合法
        条目（salvage——一个文件输出畸形只让它自己重问，好条目不连坐，见
        _extract_good_summaries / _extract_good_decisions），只对缺失路径补问，
        最多 SUMMARY_RETRY_LIMIT 轮；仍缺失就大声失败（宁可失败也不带病进
        下一阶段）。严格解析不校验覆盖（master 层职责）；这里知道素材范围，
        漏判即补问。跨轮去重：补问轮的响应可能复述已覆盖路径，同一路径只
        保留第一次结果。每次开始补问轮（重新发请求前）发射 retry 事件（契约
        唯一出处见 ProgressEvent）：轮次 1 起、缺失数 = 该轮要补问的文件数。
        """
        remaining = list(items)
        results: list[R] = []
        retry_round = 0
        for _ in range(SUMMARY_RETRY_LIMIT):
            if not remaining:
                break
            if retry_round:
                _emit(
                    progress_emitter,
                    ProgressEvent(
                        type=EVENT_RETRY,
                        phase=phase,
                        batch_index=batch_index,
                        retry_round=retry_round,
                        missing_count=len(remaining),
                    ),
                )
            retry_round += 1
            content = self._chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt(remaining)},
                ],
                json_mode=True,
            )
            try:
                parsed = parse(content, remaining)
            except LLMError:
                # 输出整体不可用（非 JSON / 形状错）——挖出合法条目只补问坏的，
                # 一个都挖不出才整批重问
                parsed = salvage(content, remaining)
                if not parsed:
                    continue
            results.extend(
                x for x in parsed if x.path not in {r.path for r in results}
            )
            covered = {r.path for r in results}
            missing = [x for x in remaining if x.path not in covered]
            if not missing:
                remaining = []
                break
            remaining = missing  # 漏判部分——只补问缺失路径
        if remaining:
            raise LLMError(
                f"{phase_label}多次补问后仍缺失 "
                + "、".join(sorted(x.path for x in remaining))[:300]
            )
        return results

    def _summarize_batch(
        self,
        platform: str,
        project_names: Sequence[str],
        batch: Sequence[JudgmentFile],
        progress_emitter: ProgressEmitter | None,
        batch_index: int,
    ) -> list[FileSummary]:
        """一批文件的摘要 + 补问循环（见 _summarize_judgment_files 的分批说明）。

        参数化 _retry_batch（retry 事件发射在原语内，phase=summary）。
        """
        return self._retry_batch(
            system_prompt=JUDGMENT_SUMMARY_SYSTEM_PROMPT,
            user_prompt=lambda remaining: _summarize_user_prompt(
                platform, project_names, remaining
            ),
            parse=parse_summary_report,
            salvage=_extract_good_summaries,
            phase_label="第一阶段摘要",
            items=batch,
            progress_emitter=progress_emitter,
            batch_index=batch_index,
            phase=PHASE_SUMMARY,
        )

    def _decide_distillation(
        self,
        platform: str,
        project_names: Sequence[str],
        file_summaries: Sequence[FileSummary],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None,
    ) -> tuple[FileDecision, ...]:
        """第二阶段：基于摘要判定（json_mode），与第一阶段同款分批 + 补问机制。

        判定条数 = 待判文件数，同样可能被模型丢条目 / 截断（批量超载时系统性
        漏判，见 JUDGMENT_BATCH_SIZE）——按批问、批内漏判只补问缺失路径，
        保证返回的判定恰好覆盖全部待判文件（路径完整性由 master.assemble_
        report 再兜底校验）。
        判定按"已处理批的素材路径"过滤 + 全局去重（判例 08：提示词带完整结构
        对比清单，模型会幻觉复述其他批已判的路径、编造素材外路径（code/pid_
        debug.h）、或提前输出未处理批的路径——前两者让 assemble_report 的
        "多次判定"/"对比范围外路径"校验失败，提前输出则没读过该路径的摘要、
        判定不可信，还会挤掉该批正规判定）。只有"本批读过摘要"的判定收下；
        真实路径的漏判仍由批内补问兜底，过滤不会掩盖漏判。

        与第一阶段同款发射进度事件：批开始 batch_start（批文件清单 = 摘要路径）、
        批完成 batch_done（累计已处理文件数 = 已入批循环的文件累计数——判定
        会被素材范围过滤，不能按结果条数算）、阶段结束 phase_done。
        """
        results: list[FileDecision] = []
        seen: set[str] = set()
        batches = _batches(file_summaries, max_chars=None)
        processed = 0
        for batch_index, batch in enumerate(batches, start=1):
            _emit(
                progress_emitter,
                ProgressEvent(
                    type=EVENT_BATCH_START,
                    phase=PHASE_DECIDE,
                    batch_index=batch_index,
                    batch_count=len(batches),
                    paths=tuple(s.path for s in batch),
                ),
            )
            batch_paths = {s.path for s in batch}
            for decision in self._decide_batch(
                platform,
                project_names,
                batch,
                comparison_summary,
                progress_emitter,
                batch_index,
            ):
                if decision.path in batch_paths and decision.path not in seen:
                    seen.add(decision.path)
                    results.append(decision)
            processed += len(batch)
            _emit(
                progress_emitter,
                ProgressEvent(
                    type=EVENT_BATCH_DONE,
                    phase=PHASE_DECIDE,
                    batch_index=batch_index,
                    processed_count=processed,
                ),
            )
        _emit(
            progress_emitter,
            ProgressEvent(
                type=EVENT_PHASE_DONE,
                phase=PHASE_DECIDE,
                file_count=len(file_summaries),
            ),
        )
        return tuple(results)

    def _decide_batch(
        self,
        platform: str,
        project_names: Sequence[str],
        batch: Sequence[FileSummary],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None,
        batch_index: int,
    ) -> list[FileDecision]:
        """一批文件的判定 + 补问循环（见 _decide_distillation 的分批说明）。

        参数化 _retry_batch：判定阶段的严格解析不校验覆盖（master 层职责），
        补问只问缺失路径；素材范围外的判定由 _decide_distillation 按批过滤
        （retry 事件发射在原语内，phase=decide）。
        """
        return self._retry_batch(
            system_prompt=DISTILL_SYSTEM_PROMPT,
            user_prompt=lambda remaining: _distill_user_prompt(
                platform, project_names, remaining, comparison_summary
            ),
            parse=lambda content, remaining: parse_distillation_report(
                content, project_names
            ),
            salvage=lambda content, remaining: _extract_good_decisions(
                content, project_names, remaining
            ),
            phase_label="提炼判定",
            items=batch,
            progress_emitter=progress_emitter,
            batch_index=batch_index,
            phase=PHASE_DECIDE,
        )

    def _chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {"model": self._config.model, "messages": messages}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        body_bytes = json.dumps(payload).encode("utf-8")
        if len(body_bytes) > MAX_REQUEST_BYTES:
            # 体积断言兜底：所有嵌内容调用都应已截断 / 分批，仍超限说明有未兜底
            # 的长输入——请求发出前大声失败（可操作信息），而不是等网关 413
            raise LLMError(
                f"请求体过大（{len(body_bytes)} 字节 > {MAX_REQUEST_BYTES} 字节）："
                "嵌内容的调用应已按预算截断 / 分批，仍超限说明有未兜底的长输入"
                "（如异常巨大的赛题文本）——请减小输入或减少导入工程的文件大小"
            )
        url = self._config.base_url.rstrip("/") + "/chat/completions"
        status, body = self._transport.post(
            url,
            {
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            payload,
            self.TIMEOUT_SECONDS,
        )
        if status != 200:
            if status == 413:
                # 网关的请求体大小限制；嵌内容调用已截断分批，仍出现说明有未
                # 兜底的超长输入（如超大赛题文本）——给出可操作提示
                raise LLMError(
                    "DeepSeek API 返回 413：请求体过大。嵌内容素材已按预算截断 / "
                    "分批发送，若仍触发，请检查赛题文本是否异常巨大，或减少导入"
                    "工程的文件数量与单文件大小"
                )
            raise LLMError(f"DeepSeek API 返回 {status}：{body[:200]}")
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMError(f"DeepSeek API 响应不是合法 JSON：{body[:200]}") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(
                f"DeepSeek API 响应缺少 choices[0].message.content：{body[:200]}"
            ) from exc


def parse_module_selection(
    content: str, known_slugs: Sequence[str]
) -> ModuleSelection:
    """把模型返回的 JSON 文本解析校验为 ModuleSelection。

    任何结构 / 内容问题（非 JSON、缺模块数组、未知 slug、重复、字段类型错）
    都抛 LLMError——模型输出不可信，宁可大声失败也不要带病进入生成流程。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("modules"), list):
        raise LLMError("模型输出缺少 modules 数组")

    known = set(known_slugs)
    modules: list[str] = []
    reasons: dict[str, str] = {}
    for index, item in enumerate(data["modules"]):
        if not isinstance(item, dict):
            raise LLMError(f"modules[{index}] 必须是对象")
        slug = item.get("slug")
        if not isinstance(slug, str) or not slug:
            raise LLMError(f"modules[{index}] 缺 slug")
        if slug not in known:
            raise LLMError(f"模型推荐了库中不存在的模块：{slug}")
        if slug in modules:
            raise LLMError(f"模型重复推荐模块：{slug}")
        reason = item.get("reason", "")
        if not isinstance(reason, str):
            raise LLMError(f"模块 {slug} 的 reason 必须是字符串")
        modules.append(slug)
        reasons[slug] = reason
    return ModuleSelection(modules=tuple(modules), reasons=reasons)


def parse_distillation_report(
    content: str, project_names: Sequence[str]
) -> tuple[FileDecision, ...]:
    """把模型返回的提炼判定 JSON 文本解析校验为 FileDecision 列表。

    条目形状校验（action 词表、merge 必须带整合产物全文与说明等）委托
    report.FileDecision.from_dict——报告模型是唯一所有者；这里只做 AI 契约
    专属检查：JSON 外层、decisions 数组、来源工程必须在导入列表、路径不重复。
    任何问题都抛 LLMError——模型输出不可信，宁可大声失败也不要带病进入确认
    流程。路径与对比范围的完整性由 master.assemble_report 校验（llm 层
    不知道对比范围）。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("decisions"), list):
        raise LLMError("模型输出缺少 decisions 数组")

    names = set(project_names)
    decisions: list[FileDecision] = []
    seen: set[str] = set()
    for index, item in enumerate(data["decisions"]):
        if not isinstance(item, dict):
            raise LLMError(f"decisions[{index}] 必须是对象")
        try:
            decision = FileDecision.from_dict(item)
        except ReportError as exc:
            raise LLMError(f"decisions[{index}] {exc}") from exc
        if (
            decision.action == ACTION_MERGE
            and decision.source
            and decision.source not in names
        ):
            raise LLMError(
                f"decisions[{index}] 的来源工程不在导入列表中：{decision.source}"
            )
        if decision.path in seen:
            raise LLMError(f"模型重复判定文件：{decision.path}")
        seen.add(decision.path)
        decisions.append(decision)
    return tuple(decisions)


def parse_summary_report(
    content: str, judgment_files: Sequence[JudgmentFile]
) -> tuple[FileSummary, ...]:
    """把模型返回的第一阶段摘要 JSON 解析校验为 FileSummary 列表。

    任何结构 / 内容问题（非 JSON、缺 summaries、未知或重复路径、缺某个内容
    版本的摘要、摘要为空、版本工程名对不上）都抛 LLMError——摘要残缺会让
    第二阶段基于残缺素材判定，宁可大声失败也不要带病进第二阶段。版本按"持
    该版本的工程名"匹配发送的词表（内容一致的工程归一个版本，工程名是唯一
    不重不漏的分组键）。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("summaries"), list):
        raise LLMError("模型输出缺少 summaries 数组")

    expected: dict[str, tuple[frozenset[str], ...]] = {
        file.path: file.version_groups for file in judgment_files
    }
    seen_paths: set[str] = set()
    summaries: list[FileSummary] = []
    for index, item in enumerate(data["summaries"]):
        if not isinstance(item, dict):
            raise LLMError(f"summaries[{index}] 必须是对象")
        path = item.get("path")
        if not isinstance(path, str) or not path:
            raise LLMError(f"summaries[{index}] 缺 path")
        if path not in expected:
            raise LLMError(f"摘要里出现非待判文件：{path}")
        if path in seen_paths:
            raise LLMError(f"模型重复摘要文件：{path}")
        seen_paths.add(path)
        raw_versions = item.get("versions")
        if not isinstance(raw_versions, list):
            raise LLMError(f"{path} 的 versions 必须是列表")
        versions: list[VersionSummary] = []
        for v_index, version in enumerate(raw_versions):
            if not isinstance(version, dict):
                raise LLMError(f"{path} versions[{v_index}] 必须是对象")
            projects = version.get("projects")
            if not isinstance(projects, list) or not projects or not all(
                isinstance(p, str) and p for p in projects
            ):
                raise LLMError(f"{path} versions[{v_index}] 的 projects 非法")
            summary = version.get("summary")
            if not isinstance(summary, str) or not summary:
                raise LLMError(f"{path} versions[{v_index}] 缺摘要或摘要为空")
            versions.append(VersionSummary(projects=tuple(projects), summary=summary))
        summaries.append(FileSummary(path=path, versions=tuple(versions)))

    for path, groups in expected.items():
        if path not in seen_paths:
            raise LLMError(f"摘要缺少文件：{path}")
        entry = next(s for s in summaries if s.path == path)
        got_groups = [frozenset(v.projects) for v in entry.versions]
        # 版本必须不重不漏恰好覆盖发送的词表：缺一个版本或多报一个（同一组
        # 工程名出两份摘要）都是畸形输出，宁可大声失败也不带病进第二阶段
        for group in groups:
            if got_groups.count(group) != 1:
                raise LLMError(
                    f"{path} 缺少内容版本的摘要：{'、'.join(sorted(group))}"
                )
        for got in got_groups:
            if got not in groups:
                raise LLMError(
                    f"{path} 的摘要含未知内容版本：{'、'.join(sorted(got))}"
                )
    return tuple(summaries)


def parse_validation_result(content: str) -> ValidationResult:
    """把模型返回的校验 JSON 文本解析校验为 ValidationResult。

    任何结构 / 内容问题（非 JSON、缺 consistent、字段类型错）都抛 LLMError——
    模型输出不可信，宁可大声失败也不要放行未校验的简介入库。
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的不是 JSON：{content[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMError("校验结果必须是 JSON 对象")
    if "consistent" not in data:
        raise LLMError("校验结果缺少必填字段 consistent")
    if not isinstance(data["consistent"], bool):
        raise LLMError("校验结果的 consistent 必须是布尔值")
    issues = data.get("issues", "")
    if not isinstance(issues, str):
        raise LLMError("校验结果的 issues 必须是字符串")
    return ValidationResult(consistent=data["consistent"], issues=issues)


def _build_user_prompt(problem_text: str, heading: str, items: Sequence[str]) -> str:
    """赛题 + 清单的 user 消息拼装（模块选择 / main.c 骨架共用）。

    赛题文本与清单条目都走截断（_truncate_content，带标注）——模块选择与
    骨架生成的请求体同样受预算约束，未兜底的长赛题 / 大接口块不再 413。
    """
    lines = ["赛题：", _truncate_content(problem_text), "", heading]
    lines.extend(_truncate_content(item) for item in items)
    return "\n".join(lines)


def _selection_user_prompt(problem_text: str, manifest_summaries: Sequence[str]) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    prompt = _build_user_prompt(problem_text, "模块库可用模块：", manifest_summaries)
    return prompt + '\n只返回 json 格式的 JSON 对象：{"modules": [{"slug": "...", "reason": "..."}]}'


def _summarize_user_prompt(
    platform: str,
    project_names: Sequence[str],
    judgment_files: Sequence[JudgmentFile],
) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    names = "、".join(project_names)
    lines = [
        f"平台：{platform}",
        f"导入的工程：{names}",
        "",
        "需要判定的文件（同一路径出现多个内容版本 = 冲突；只出现在部分工程 = "
        "独有）。读全文（超长文件已截断，见文件末尾标注，" + TRUNCATION_NOTICE
        + "）后为每个内容版本写一段中文摘要。同一路径在多个工程里"
        "内容不同（冲突）时，每个内容版本必须各输出一条 versions 条目，projects "
        "精确列出持有该版本内容的工程——把不同内容的版本合并成一条是错误：",
    ]
    for file in judgment_files:
        multi = len(file.versions) > 1
        for index, version in enumerate(file.versions, start=1):
            label = (
                f"版本 {index}（{'、'.join(version.projects)}）"
                if multi
                else f"（{'、'.join(version.projects)}）"
            )
            lines.append(
                f"- {file.path} {label}：\n"
                f"```c\n{_truncate_content(version.content)}\n```"
            )
    lines.append(
        "只返回 json 格式的 JSON 对象："
        '{"summaries": [{"path": "...", "versions": [{"projects": ["工程名"], '
        '"summary": "中文摘要"}]}]}'
    )
    return "\n".join(lines)


def _distill_user_prompt(
    platform: str,
    project_names: Sequence[str],
    file_summaries: Sequence[FileSummary],
    comparison_summary: str,
) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    names = "、".join(project_names)
    lines = [
        f"平台：{platform}",
        f"导入的工程：{names}",
        "",
        "待判文件内容摘要（已读全文的要点）：",
    ]
    for summary in file_summaries:
        for version in summary.versions:
            lines.append(
                f"- {summary.path}（{'、'.join(version.projects)}）：{version.summary}"
            )
    lines.extend(
        [
            "",
            "结构与配置对比：",
            comparison_summary,
            "",
            "对每个需要判定的文件路径给出动作：keep（保留）/ merge（整合：同一路径"
            "多份内容不同时，读多份后整合出通用版本，选一份只是特例）/ exclude（剔除）。",
            JUDGMENT_SCOPE,
            "merge 必须给出整合产物全文 content 与整合说明 explanation（选一份时可附"
            "source 说明选了哪份）。判定理由带上摘要要点。只返回 json 格式的 JSON 对象：",
            '{"decisions": [{"path": "...", "action": "keep|merge|exclude", '
            '"content": "merge 时必填的整合产物全文", '
            '"explanation": "merge 时必填的整合说明（选一份时说明为何选它）", '
            '"source": "merge 选一份时可选填的来源工程名", "reason": "中文理由"}]}',
        ]
    )
    return "\n".join(lines)


def _validation_user_prompt(description: str, code: str) -> str:
    # 提示词必须含小写 "json"：DeepSeek 的 json_object 模式要求
    return (
        f"模块简介：\n{_truncate_content(description)}\n\n实际代码：\n"
        f"```c\n{_truncate_content(code)}\n```\n\n"
        + VALIDATION_SPECIFICITY_RULE
        + "\n判断简介与实际代码是否一致，只返回 json 格式的 JSON 对象："
        '{"consistent": true/false, "issues": "不一致时用中文指出差异，一致时为空字符串"}'
    )


def _skeleton_user_prompt(problem_text: str, module_interfaces: Sequence[str]) -> str:
    """main.c 骨架生成的 user 消息：赛题 + 所选模块头文件接口块（见 skeleton.py）。"""
    prompt = _build_user_prompt(
        problem_text,
        "所选模块的头文件接口（main.c 只调用这里真实存在的函数）：",
        module_interfaces,
    )
    return prompt + (
        "\n\n输出 main.c 骨架：按模块初始化序列排好调用，带注释与预留编写区（TODO），"
        "不确定的调用写成注释占位，不凭空造函数，保证可编译。"
    )


def _summary_slugs(manifest_summaries: Sequence[str]) -> list[str]:
    """从摘要行提取 slug（行首 "- " 后的第一个冒号前）。

    与 build_manifest_summaries 的行格式耦合：套件 / 依赖段都在冒号之后、不
    影响本解析；改动格式须同步两处（选模块结果的 known_slugs 靠它反解析）。
    """
    slugs = []
    for line in manifest_summaries:
        if not line.startswith("- "):
            continue
        slug = line[2:].split(":", 1)[0].strip()
        if slug:
            slugs.append(slug)
    return slugs
