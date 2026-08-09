"""提炼确认的归档步骤（master.confirm_distillation 的归档段）：母版入库后把
报告 archive 段的源工程文件复制进参考文件库（归档 = 字节复制入库、锚定该题、
内容自持）。

独立成模块的原因：归档需要参考文件库（archive_reference）与赛题编号文法
（validate_topic_key），而 master 不 import 参考库族——防 import 链
（master → reference_library → topic_library → library 4 跳收敛，工单 C3）。
本模块模块级 import master（错误类型与对比模型），master 在
confirm_distillation 内函数级延迟导入本模块——避开 master ↔ archive
模块级环（本模块只在归档确认时加载）。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Mapping, Sequence

from .autocommit import commit_after_write
from .entry_store import discard_entry_dirs
from .master import ProjectComparison
from .master_store import MasterError
from .reference_library import archive_reference
from .report import DistillationReport, ReferenceCandidate
from .topic_library import validate_topic_key

if TYPE_CHECKING:
    from .llm import LLM  # 仅类型注解用（llm 运行时依赖 selection → reference_library，不反向）


def prepare_archive(
    report: DistillationReport,
    comparison: ProjectComparison,
    llm_factory: Callable[[], LLM] | None,
    reference_library_dir: Path | None,
) -> dict[str, str]:
    """归档前置：校验配置与锚定、LLM 判定归档价值并生成条目简介（不写盘）。

    全部失败都在写盘前大声报错（MasterError，中文说明）：归档需要 AI 服务与
    参考文件库目录配置；锚定赛题编号格式非法（格式与赛题库 key 同源校验，
    查库确认 / 查无此条拒绝未接线——留待素材区接线工单）；AI 判定不配归档的
    文件被拒绝（一次性杂物 / 配置噪声不配归档）。
    条目简介 = LLM 对文件全文的摘要（与参考文件库录入草稿同一协议方法
    reference_summarize）。归档路径的合法性（判定范围内、类别文件不配归档）
    由 apply_distillation 的处置校验先拦住——本函数只做归档自身的校验。
    """
    if llm_factory is None or reference_library_dir is None:
        raise MasterError(
            "归档动作需要 AI 服务与参考文件库目录（未提供），无法提交"
        )
    project_dir_by_name = {p.name: p.project_dir for p in comparison.projects}
    candidates: list[ReferenceCandidate] = []
    for decision in report.archive:
        message = validate_topic_key(decision.topic)
        if message:
            raise MasterError(message) from None
        holders = comparison.by_path.get(decision.path)
        if not holders:
            # 覆盖校验应先拦住（判定范围外路径）；兜底大声失败，不猜测不编造
            raise MasterError(f"没有任何工程含文件 {decision.path}")
        source = holders[0]
        content = (project_dir_by_name[source] / Path(decision.path)).read_text(
            encoding="utf-8", errors="replace"
        )
        candidates.append(
            ReferenceCandidate(
                path=decision.path, content=content, reason=decision.reason
            )
        )
    llm = llm_factory()
    archivable = set(llm.reference_judge_archivable(candidates))
    rejected = [c.path for c in candidates if c.path not in archivable]
    if rejected:
        raise MasterError(
            "以下文件未被 AI 判定为值得归档（可去掉归档动作后重新确认）："
            + "、".join(rejected)
        )
    return {c.path: llm.reference_summarize(c.content) for c in candidates}


def write_archive_entries(
    report: DistillationReport,
    comparison: ProjectComparison,
    reference_library_dir: Path,
    summaries: Mapping[str, str],
) -> None:
    """归档条目落盘（在母版入库之后）：源工程文件字节复制入库、锚定该题。

    批回滚：任一条目写入失败，删除本批已建条目目录并大声报错（中文说明）——
    不留半成品（母版已入库且归档条目相互独立，重试确认即可：import 幂等、
    归档重跑是全新条目）。归档 = 复制入库（内容自持）：源工程删除不丢。
    """
    project_dir_by_name = {p.name: p.project_dir for p in comparison.projects}
    created: list[Path] = []
    try:
        for decision in report.archive:
            holders = comparison.by_path[decision.path]
            source = holders[0]
            entry = archive_reference(
                reference_library_dir,
                source=project_dir_by_name[source] / Path(decision.path),
                rel_path=decision.path,
                title=f"{decision.path}（{source}）",
                description=summaries[decision.path],
                anchor_topic=decision.topic,
            )
            created.append(reference_library_dir / entry.id)
    except Exception as exc:
        discard_entry_dirs(created)
        raise MasterError(
            f"母版已入库，但归档写入失败（已回滚本次归档条目，可重试确认）：{exc}"
        ) from exc
    commit_after_write(
        reference_library_dir,
        "lib: archive reference " + "、".join(d.path for d in report.archive),
    )
