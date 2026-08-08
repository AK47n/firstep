"""判定模型：提炼报告的判定条目与容器 + AI 判定素材（schema 的唯一所有者）。

FileDecision 与 DistillationReport（判定输出）同时出现在三条路径上——AI
判定输出（llm 解析）、确定性规则拼装（master 拼装报告）、确认请求回传
（webapp 往返）——因此条目与容器的形状、序列化与不变量（merge 必须带整合
产物全文与整合说明、main_c_preview 由平台重推导）在这里只定义一次：llm 层
只负责 AI JSON 契约（提示词 + decisions 数组解析），master 层只负责对比语义
校验（路径范围 / 来源工程 / 模板 main.c 内容），形状校验都落到 from_dict。

JudgmentFile 与 FileVersion（判定输入素材，master 构造、llm 消费）同归此
处——依赖倒置：llm 层依赖模型层取素材类型，master 不再从 llm 导入模型。
版本分组不变量（版本工程名组不重不漏）在这里唯一声明与校验。

提炼第一阶段产物（FileSummary / VersionSummary：待判文件各内容版本的摘要，
第二阶段判定的输入素材）同为判定素材模型，同归此处——两阶段的素材形状在
模型层只定义一次，llm 层只负责 AI JSON 解析。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ReportError(ValueError):
    """报告条目 / 报告形状非法，message 说明具体问题。"""


ACTION_KEEP = "keep"  # 保留：通用且基础建设必需
ACTION_MERGE = "merge"  # 整合：同路径多份内容不同，AI 读多份产出通用版本
ACTION_EXCLUDE = "exclude"  # 剔除：不通用 / 残留

# 注意：归档（工单 02）不进此词表——FileDecision 是提炼报告逐文件判定的
# 条目（keep/merge/exclude），"归档为该题参考文件"是动作表上的独立一档，
# 走 ArchiveDecision 模型（见下）：判定词表与归档动作互不混淆（既有契约
# 测试把 "archive" 钉死为 FileDecision 非法动作，不得放回此表）。

# 判定动作词表：llm 提示词与 master 拼装共用，各自硬编码会静默漂移
DISTILL_ACTIONS = (ACTION_KEEP, ACTION_MERGE, ACTION_EXCLUDE)


@dataclass(frozen=True)
class FileDecision:
    """母版提炼时单个文件的判定：保留 / 整合（AI 产出通用版本）/ 剔除。

    merge 携带整合产物全文（content）与整合说明（explanation），选一份只是
    特例——可附 source 说明选了哪份，但落盘一律写 content。覆盖判定范围全部
    路径（公共 + 冲突 + 独有——ADR 0001：内容一致不等于基础建设必需，公共
    文件同样进 AI 判定，可保留可剔除）。
    """

    path: str  # 相对工程目录的路径（与扫描清单同一套词表）
    action: str  # ACTION_KEEP / ACTION_MERGE / ACTION_EXCLUDE
    content: str = ""  # merge 时 AI 整合出的通用版本全文（其余动作必须为空）
    explanation: str = ""  # merge 时的整合说明（选一份时说明为何选它）
    source: str = ""  # merge 选一份特例时的来源工程名（其余动作必须为空）
    reason: str = ""  # AI 的中文理由（残留 / 模板替代条目为规则化原因）

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容 dict（确认请求按同一形状回传）。"""
        return {
            "path": self.path,
            "action": self.action,
            "content": self.content,
            "explanation": self.explanation,
            "source": self.source,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileDecision":
        """从 JSON 重建单个判定（形状校验唯一实现，AI 解析与确认报告共用）。

        任何结构 / 内容问题（非对象、缺 path、action 非法、merge 缺整合产物或
        整合说明、非 merge 带 content/explanation/source）都抛 ReportError——
        AI 输出与确认报告同样不可信，宁可大声失败也不要带病进入落盘流程。
        来源工程名是否真实含该文件由 master 层校验。
        """
        if not isinstance(data, dict):
            raise ReportError("判定条目必须是对象")
        path = data.get("path")
        if not isinstance(path, str) or not path:
            raise ReportError("判定条目缺少必填字段：path")
        action = data.get("action")
        if action not in DISTILL_ACTIONS:
            raise ReportError(f"判定条目的 action 非法：{action!r}")
        reason = data.get("reason", "")
        if not isinstance(reason, str):
            raise ReportError("判定条目的 reason 必须是字符串")
        content = data.get("content", "")
        explanation = data.get("explanation", "")
        source = data.get("source", "")
        if not isinstance(content, str):
            raise ReportError("判定条目的 content 必须是字符串")
        if not isinstance(explanation, str):
            raise ReportError("判定条目的 explanation 必须是字符串")
        if not isinstance(source, str):
            raise ReportError("判定条目的 source 必须是字符串")
        if action == ACTION_MERGE:
            if not content.strip():
                raise ReportError(
                    f"判定条目 {path!r} 的 merge 必须指定 content（整合产物全文）"
                )
            if not explanation.strip():
                raise ReportError(
                    f"判定条目 {path!r} 的 merge 必须指定 explanation（整合说明）"
                )
        elif content or explanation or source:
            raise ReportError(
                f"判定条目 {path!r} 只有 merge 才能带 content / explanation / source"
            )
        return cls(
            path=path,
            action=action,
            content=content,
            explanation=explanation,
            source=source,
            reason=reason,
        )


@dataclass(frozen=True)
class ArchiveDecision:
    """归档动作：被剔除的业务代码一键复制入库、锚定该题（内容自持，工单 02）。

    提炼报告动作表上独立于 keep/merge/exclude 的一档（"归档为该题参考文件"）：
    归档文件不落母版，以源工程文件副本入库参考文件库（复制入库——源工程删除
    不丢）。条目只对判定范围内（公共 + 冲突 + 独有）的文件合法——残留 / 旧
    main.c / 基础设施 / 二进制 / 工程配置文件由规则确定性处置、不配归档
    （master 层处置校验拒绝）。topic = 锚定赛题编号（如 2026C）：格式与
    查库校验在参考文件库模块（本模型只保证形状，语义归确认流程）。
    """

    path: str  # 相对工程目录的路径（与扫描清单同一套词表）
    topic: str  # 锚定赛题编号（归档为该题参考文件）
    reason: str = ""  # 原剔除理由（AI 判定理由）

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容 dict（确认请求按同一形状回传）。"""
        return {"path": self.path, "topic": self.topic, "reason": self.reason}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArchiveDecision":
        """从 JSON 重建归档动作（形状校验唯一实现，AI 解析与确认报告共用）。"""
        if not isinstance(data, dict):
            raise ReportError("归档条目必须是对象")
        path = data.get("path")
        if not isinstance(path, str) or not path:
            raise ReportError("归档条目缺少必填字段：path")
        topic = data.get("topic")
        if not isinstance(topic, str) or not topic.strip():
            raise ReportError("归档条目缺少必填字段：topic（锚定赛题编号）")
        reason = data.get("reason", "")
        if not isinstance(reason, str):
            raise ReportError("归档条目的 reason 必须是字符串")
        return cls(path=path, topic=topic, reason=reason)


@dataclass(frozen=True)
class DistillationReport:
    """提炼报告容器：保留 / 整合 / 剔除清单 + 归档清单 + 模板 main.c 预览 + .uvprojx 预览。

    清单条目复用 FileDecision（同一套字段，不另造同形类型）；归档清单用
    ArchiveDecision（动作表独立一档，工单 02——由用户在确认时指定，AI 判定
    词表不含归档）；来源工程名在 projects 里——确认后的报告要落盘、母版入库
    元数据要用。main_c_preview 是确定性模板 main.c 全文（ADR 0002：母版
    main.c 由模板提供）；uvprojx_preview 是确定性渲染的 .uvprojx 全文（工单
    09：stm32 由渲染器现写，mspm0 无现写为空串）。两个预览给用户在确认前看；
    落盘仍写 main_c_template(platform) 与确定性渲染产物（内容归属母版模块），
    预览不参与落盘。
    """

    platform: str
    projects: tuple[str, ...]  # 提炼来源工程名
    keep: tuple[FileDecision, ...]
    merge: tuple[FileDecision, ...]
    exclude: tuple[FileDecision, ...]
    main_c_preview: str  # 模板 main.c 全文预览（确定性，由平台推导，必填）
    uvprojx_preview: str  # .uvprojx 全文预览（stm32 确定性渲染；mspm0 无现写为空串，必填）
    archive: tuple[ArchiveDecision, ...] = ()  # 归档动作（确认时由用户指定，缺省空）

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容 dict（提炼报告的 wire format，确认请求回传同形）。

        archive 键只在非空时带出：AI 出稿的报告（archive 恒空，动作由用户在
        确认时指定）保持既有 wire 形状不变（契约测试钉死七键）；含归档动作
        的确认回传才出现 archive 段。from_dict 两种形状都接受（缺省空）。
        """
        data: dict[str, Any] = {
            "platform": self.platform,
            "projects": list(self.projects),
            "keep": [d.to_dict() for d in self.keep],
            "merge": [d.to_dict() for d in self.merge],
            "exclude": [d.to_dict() for d in self.exclude],
            "main_c_preview": self.main_c_preview,
            "uvprojx_preview": self.uvprojx_preview,
        }
        if self.archive:
            data["archive"] = [d.to_dict() for d in self.archive]
        return data

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, main_c_preview: str, uvprojx_preview: str = ""
    ) -> "DistillationReport":
        """从确认请求的 JSON 重建报告（形状校验；语义校验归 master 落盘前）。

        条目形状校验与 llm.parse_distillation_report 同一标准（FileDecision.
        from_dict）；来源工程与路径覆盖等语义问题在落盘前由 master 层拦截。
        main_c_preview / uvprojx_preview 是确定性素材（落盘永远写
        main_c_template(platform) 与确定性渲染产物），客户端回传值不可信——
        由调用方按平台重推导传入，保证报告里的预览 = 实际落盘内容；平台非法
        由调用方（模板加载）大声失败。
        """
        if not isinstance(data, dict):
            raise ReportError("提炼报告必须是 JSON 对象")
        platform = data.get("platform")
        if not isinstance(platform, str) or not platform:
            raise ReportError("缺少必填字段：platform")
        projects = data.get("projects")
        if not isinstance(projects, list) or not all(
            isinstance(item, str) and item for item in projects
        ):
            raise ReportError("projects 必须是非空字符串列表")
        if not projects:
            raise ReportError("报告缺少来源工程：projects 不能为空")
        if not isinstance(main_c_preview, str):
            raise ReportError("main_c_preview 必须是字符串")
        if not isinstance(uvprojx_preview, str):
            raise ReportError("uvprojx_preview 必须是字符串")

        def decisions(key: str) -> tuple[FileDecision, ...]:
            raw = data.get(key)
            if not isinstance(raw, list):
                raise ReportError(f"{key} 必须是列表")
            try:
                return tuple(FileDecision.from_dict(item) for item in raw)
            except ReportError as exc:
                raise ReportError(f"报告 {key} 条目非法：{exc}") from exc

        def archive_entries(key: str) -> tuple[ArchiveDecision, ...]:
            raw = data.get(key, [])
            if not isinstance(raw, list):
                raise ReportError(f"{key} 必须是列表")
            try:
                return tuple(ArchiveDecision.from_dict(item) for item in raw)
            except ReportError as exc:
                raise ReportError(f"报告 {key} 条目非法：{exc}") from exc

        return cls(
            platform=platform,
            projects=tuple(projects),
            keep=decisions("keep"),
            merge=decisions("merge"),
            exclude=decisions("exclude"),
            main_c_preview=main_c_preview,
            uvprojx_preview=uvprojx_preview,
            archive=archive_entries("archive"),
        )


# ---------------------------------------------------------------------------
# 判定素材（AI 判定流程的输入）：master 构造、llm 消费
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceCandidate:
    """归档判定素材：一个被剔除文件的路径 + 全文 + 剔除理由（工单 02）。

    与 JudgmentFile / FileVersion 同归判定素材模型层（master 构造、llm 消费）：
    llm 层只消费类型、不拥有——归档判定协议（reference_judge_archivable）的
    参数类型在此定义（依赖倒置，CONTEXT「判定素材模型归模型层」）。
    """

    path: str
    content: str
    reason: str = ""


@dataclass(frozen=True)
class JudgmentFile:
    """待判文件素材：路径 + 每个内容版本及其持有工程（AI 判定前先读全文出摘要）。

    覆盖 master 判定范围（公共 + 冲突 + 独有，全部文件）。同一路径内容不同
    的每个版本都传（AI 读全部版本后判定）；内容一致的工程合并为一个版本。
    """

    path: str
    versions: tuple[FileVersion, ...]

    @property
    def version_groups(self) -> tuple[frozenset[str], ...]:
        """版本分组（唯一出处）：每个内容版本一组持有工程名。

        分组是判定素材模型的不变量——组与组互不重叠（一个工程在同一路径只有
        一个内容版本），组并集 = 该路径全部持有工程。解析词表 / 合并拆分各处
        复用本属性，不再手抄 frozenset 推导。
        """
        return tuple(frozenset(version.projects) for version in self.versions)

    def __post_init__(self) -> None:
        """版本分组不变量校验：版本非空、各组非空、组间不重叠。

        不变量由 build_judgment_files（按内容哈希分组）保证；手工构造的素材
        带病在此大声失败，不让畸形分组流到解析词表 / 合并拆分逻辑。
        """
        if not self.versions:
            raise ReportError(f"判定素材 {self.path!r} 缺少内容版本")
        seen: set[str] = set()
        for version in self.versions:
            group = frozenset(version.projects)
            if not group:
                raise ReportError(f"判定素材 {self.path!r} 有内容版本无持有工程")
            overlap = group & seen
            if overlap:
                raise ReportError(
                    f"判定素材 {self.path!r} 的内容版本工程名重叠："
                    + "、".join(sorted(overlap))
                )
            seen |= group


@dataclass(frozen=True)
class FileVersion:
    """同一路径下的一个内容版本：全文 + 持该版本的工程名。"""

    content: str
    projects: tuple[str, ...]


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
