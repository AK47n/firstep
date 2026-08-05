"""母版提炼核心：多旧工程 → 对比 → AI 判定 → 报告 → 确认 → 母版入库。

流程（spec US 18/19 + "母版提炼"实现决策）：用户导入多个同平台旧工程 →
scan_project 逐个生成结构快照（平台检测 + 文件清单 + 配置摘要）→
compare_projects 做结构对比与配置对比（公共 / 冲突 / 独有）→ distill_master
把需要判定的路径（冲突 + 独有）交给 LLM，公共文件按"所有工程内容一致"确定
保留 → 得到完整提炼报告（保留 / 合并 / 剔除清单 + 理由）→ 用户审查、可修改
报告 → apply_distillation 按确认后的报告落盘母版候选 → import_master 做结构
分析后入库（每平台一个母版，可更换 / 删除）。

母版库：磁盘目录即数据库，母版库根下每个平台一个目录（工程文件本体）+ 同名
<platform>.json 元数据（提炼来源、入库时结构分析的警告）。元数据放目录外的
平级文件：母版目录会被生成器整体复制，内部带 json（如 master.json）会污染
生成的工程。

任何从平台名拼路径的操作（浏览 / 删除 / 入库）都先校验平台名合法性，杜绝
借平台名逃出母版库的路径穿越。母版库的物理位置由调用方传入（后续工单接入
本机配置），测试用 tmp_path。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .ccs import CcsProjectError, extract_config_summary as extract_ccs_config_summary
from .keil import KeilProjectError, extract_config_summary as extract_keil_config_summary
from .llm import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    FileDecision,
    LLM,
    LLMError,
)
from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32

# 扫描时忽略的顶级目录：版本库与构建产物不是母版内容
BUILD_ARTIFACT_DIRS = frozenset({"Debug", "Release"})
IGNORED_TOP_LEVEL_DIRS = frozenset({".git"}) | BUILD_ARTIFACT_DIRS

# 各平台 IDE 打开工程必需的配置文件：结构分析时校验存在性
PLATFORM_CONFIG_FILES = {
    PLATFORM_STM32: (".uvprojx",),
    PLATFORM_MSPM0: (".cproject", ".project"),
}

_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")


class MasterError(ValueError):
    """母版提炼 / 管理失败，message 说明具体问题。"""


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectStructure:
    """单个工程的结构快照：平台、文件清单（相对路径 + 内容哈希）、配置摘要。"""

    project_dir: Path
    name: str  # 工程名（目录名）
    platform: str  # 检测到的平台
    files: tuple[str, ...]  # 相对路径（POSIX 分隔），排序
    file_hashes: Mapping[str, str]  # path -> sha256 hex（对比内容是否一致）
    config_summary: tuple[str, ...]  # 平台配置摘要行（配置对比的 AI 素材）


@dataclass(frozen=True)
class ProjectComparison:
    """多工程的结构 + 配置对比结果。"""

    projects: tuple[ProjectStructure, ...]
    common: tuple[str, ...]  # 所有工程都有且内容完全一致
    conflicts: tuple[str, ...]  # 同路径、内容不一致
    unique: tuple[str, ...]  # 只出现在部分工程
    by_path: Mapping[str, tuple[str, ...]]  # path -> 含该文件的工程名（出现顺序）
    judgment: tuple[str, ...]  # 需要 AI 判定的路径（冲突 + 独有）


@dataclass(frozen=True)
class DistillationReport:
    """提炼报告：保留 / 整合 / 剔除清单（确认后交给 apply_distillation）。

    清单条目复用 llm.FileDecision（path / action / content / explanation /
    source / reason 同一套字段，不另造一个同形类型）。来源工程名在 projects
    里——确认后的报告要落盘、母版入库元数据要用。
    """

    platform: str
    projects: tuple[str, ...]  # 提炼来源工程名
    keep: tuple[FileDecision, ...]
    merge: tuple[FileDecision, ...]
    exclude: tuple[FileDecision, ...]

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容 dict（提炼报告的 wire format，确认请求回传同形）。"""
        return {
            "platform": self.platform,
            "projects": list(self.projects),
            "keep": [d.to_dict() for d in self.keep],
            "merge": [d.to_dict() for d in self.merge],
            "exclude": [d.to_dict() for d in self.exclude],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DistillationReport":
        """从确认请求的 JSON 重建报告（形状校验；语义校验归 apply_distillation）。

        条目形状校验与 llm.parse_distillation_report 同一标准；来源工程与
        路径覆盖等语义问题在落盘前由 _validate_report 拦截。
        """
        if not isinstance(data, dict):
            raise MasterError("提炼报告必须是 JSON 对象")
        platform = _require_str(data, "platform")
        projects = tuple(_require_str_list(data, "projects"))
        if not projects:
            raise MasterError("报告缺少来源工程：projects 不能为空")

        def decisions(key: str) -> tuple[FileDecision, ...]:
            raw = data.get(key)
            if not isinstance(raw, list):
                raise MasterError(f"{key} 必须是列表")
            try:
                return tuple(FileDecision.from_dict(item) for item in raw)
            except LLMError as exc:
                raise MasterError(f"报告 {key} 条目非法：{exc}") from exc

        return cls(
            platform=platform,
            projects=projects,
            keep=decisions("keep"),
            merge=decisions("merge"),
            exclude=decisions("exclude"),
        )


@dataclass(frozen=True)
class StructureAnalysis:
    """入库时的结构分析结果。"""

    platform: str
    warnings: tuple[str, ...]  # 非致命问题（构建产物残留等）


@dataclass(frozen=True)
class MasterMeta:
    """母版元数据（母版库根下的 <platform>.json）。"""

    platform: str
    sources: tuple[str, ...]  # 提炼来源工程名
    warnings: tuple[str, ...]  # 入库时结构分析的警告

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "sources": list(self.sources),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MasterMeta":
        platform = _require_str(data, "platform")
        sources = _require_str_list(data, "sources")
        warnings = _require_str_list(data, "warnings")
        return cls(
            platform=platform, sources=tuple(sources), warnings=tuple(warnings)
        )


# ---------------------------------------------------------------------------
# 工程扫描与对比
# ---------------------------------------------------------------------------


def scan_project(project_dir: Path) -> ProjectStructure:
    """扫描单个工程：平台检测 + 文件清单（含内容哈希）+ 平台配置摘要。

    平台由工程配置文件判定：有 .uvprojx 为 stm32，有 .cproject 为 mspm0；
    两者都有或都没有抛 MasterError。工程文件在任意层级可识别（正点原子风格
    在 USER/ 子目录），.git 目录除外。.git / Debug / Release 等非母版内容的
    顶层目录不进清单。config_summary 提取设备 / include path / 编译宏等
    配置对比素材（XML 解析失败只记一行，扫描不因单个工程带病中断）。
    """
    if not project_dir.is_dir():
        raise MasterError(f"工程目录不存在：{project_dir}")
    platform = _detect_platform(project_dir)
    files: list[str] = []
    hashes: dict[str, str] = {}
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(project_dir).as_posix()
        if _is_ignored(rel):
            continue
        files.append(rel)
        hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return ProjectStructure(
        project_dir=project_dir,
        name=project_dir.name,
        platform=platform,
        files=tuple(files),
        file_hashes=hashes,
        config_summary=_config_summary(project_dir, platform),
    )


def compare_projects(projects: Sequence[ProjectStructure]) -> ProjectComparison:
    """结构 + 配置对比：按路径分类公共 / 冲突 / 独有，平台必须一致。

    公共 = 所有工程都有且内容完全一致；冲突 = 同路径内容不一致；独有 =
    只出现在部分工程。by_path 记录每个路径出现在哪些工程（出现顺序），
    供报告确认后的落盘取源。
    """
    if not projects:
        raise MasterError("至少导入一个工程")
    platforms = {p.platform for p in projects}
    if len(platforms) > 1:
        raise MasterError(
            "导入的工程必须是同一平台：" + "、".join(sorted(platforms))
        )
    names = [p.name for p in projects]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise MasterError(
            "工程名重复，请区分目录名后重试：" + "、".join(duplicates)
        )

    by_path: dict[str, list[str]] = {}
    hashes_by_path: dict[str, dict[str, str]] = {}  # path -> 工程名 -> 内容哈希
    for project in projects:
        for path in project.files:
            by_path.setdefault(path, []).append(project.name)
            hashes_by_path.setdefault(path, {})[project.name] = project.file_hashes[path]

    common: list[str] = []
    conflicts: list[str] = []
    unique: list[str] = []
    for path in sorted(by_path):
        project_hashes = hashes_by_path[path]
        if len(project_hashes) == len(projects):
            if len(set(project_hashes.values())) == 1:
                common.append(path)
            else:
                conflicts.append(path)
        else:
            unique.append(path)

    return ProjectComparison(
        projects=tuple(projects),
        common=tuple(common),
        conflicts=tuple(conflicts),
        unique=tuple(unique),
        by_path={path: tuple(names) for path, names in by_path.items()},
        judgment=tuple(sorted(conflicts)) + tuple(sorted(unique)),
    )


def build_comparison_summary(comparison: ProjectComparison) -> str:
    """把对比结果格式化成喂给 LLM 的结构 + 配置对比文本。"""
    lines: list[str] = []
    if comparison.common:
        lines.append("公共文件（所有工程内容一致）：")
        lines.append("、".join(comparison.common))
    if comparison.conflicts:
        lines.append("冲突文件（同路径、内容不同）：")
        for path in comparison.conflicts:
            lines.append(f"- {path}（出现在：{'、'.join(comparison.by_path[path])}）")
    if comparison.unique:
        lines.append("独有文件（只出现在部分工程）：")
        for path in comparison.unique:
            lines.append(f"- {path}（出现在：{'、'.join(comparison.by_path[path])}）")
    lines.append("各工程配置摘要：")
    for project in comparison.projects:
        lines.append(f"- 工程 {project.name}：")
        for summary in project.config_summary:
            lines.append(f"  {summary}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 提炼：AI 判定 → 完整报告（用户确认前不落任何东西）
# ---------------------------------------------------------------------------


def distill_master(
    llm: LLM,
    platform: str,
    projects: Sequence[ProjectStructure],
) -> DistillationReport:
    """提炼流程：对比 → LLM 判定 → 拼装完整报告。

    公共文件确定保留（所有工程内容一致，无需 AI）；冲突与独有文件必须被
    AI 逐条判定，覆盖不全或出现未知路径抛 MasterError——宁可不放行也不带病
    进入确认流程。
    """
    comparison = compare_projects(projects)
    project_names = tuple(p.name for p in projects)
    decisions = llm.distill_master(
        platform, project_names, build_comparison_summary(comparison)
    )
    return assemble_report(platform, project_names, comparison, decisions)


def assemble_report(
    platform: str,
    project_names: Sequence[str],
    comparison: ProjectComparison,
    decisions: Sequence[FileDecision],
) -> DistillationReport:
    """把确定性公共文件与 AI 判定拼成完整报告，并校验判定覆盖完整。

    判据是内容（通用性 / 基础建设必需性），分类不直接决定动作：冲突文件可以
    merge（整合出通用版本）也可以 exclude，只有 keep 被禁止（keep 没有"取哪份
    内容"的信息，落盘时会静默取第一个工程）；公共文件确定保留——AI 重复判定
    keep 是冗余（忽略），判定 merge / exclude 是错误（公共文件必须保留），
    用户确认时可把公共文件改为剔除。merge 必须带整合产物全文与整合说明
    （选一份只是特例）。这些在确认前就拦住，兑现"不带病进入确认流程"。
    """
    common = set(comparison.common)
    judged: list[FileDecision] = []
    for decision in decisions:
        if decision.path in common:
            # 公共文件由确定性自动保留覆盖；AI 重复判定 keep 是冗余（忽略），
            # 判定 merge / exclude 是错误（公共文件必须保留），直接拒绝
            if decision.action != ACTION_KEEP:
                raise MasterError(f"公共文件必须保留：{decision.path}")
            continue
        judged.append(decision)
    decided = {d.path for d in judged}
    _validate_judgment_coverage(decided=decided, judgment=set(comparison.judgment))
    _validate_merge_sources(judged, comparison)

    keep: list[FileDecision] = [
        FileDecision(path, ACTION_KEEP, reason="所有导入工程内容一致，属公共骨架")
        for path in comparison.common
    ]
    merge: list[FileDecision] = []
    exclude: list[FileDecision] = []
    for decision in judged:
        if decision.action == ACTION_MERGE:
            merge.append(decision)
        elif decision.action == ACTION_EXCLUDE:
            exclude.append(decision)
        else:
            keep.append(decision)
    return DistillationReport(
        platform=platform,
        projects=tuple(project_names),
        keep=tuple(keep),
        merge=tuple(merge),
        exclude=tuple(exclude),
    )


def _validate_merge_sources(
    decisions: Sequence[FileDecision], comparison: ProjectComparison
) -> None:
    """词表约束：冲突文件 merge 或 exclude（keep 被禁）；merge 只用于冲突文件、
    必须带整合产物全文与整合说明（选一份只是特例，可附来源工程名）；来源工程
    必须是导入工程。"""
    names = {p.name for p in comparison.projects}
    conflicts = set(comparison.conflicts)
    for decision in decisions:
        if decision.path in conflicts and decision.action == ACTION_KEEP:
            raise MasterError(
                f"冲突文件（同路径不同内容）必须 merge 或 exclude：{decision.path}"
            )
        if decision.action != ACTION_MERGE:
            continue
        if decision.path not in conflicts:
            raise MasterError(
                f"merge 只用于同路径多份内容不同的冲突文件：{decision.path}"
            )
        if not decision.content.strip():
            raise MasterError(f"merge 必须带整合产物全文：{decision.path}")
        if not decision.explanation:
            raise MasterError(f"merge 必须带整合说明：{decision.path}")
        if decision.source and decision.source not in names:
            raise MasterError(f"合并来源工程未知：{decision.source}")


# ---------------------------------------------------------------------------
# 确认后落盘：报告 → 母版候选目录
# ---------------------------------------------------------------------------


def apply_distillation(
    report: DistillationReport,
    comparison: ProjectComparison,
    output_dir: Path,
) -> Path:
    """按确认后的报告把文件落盘到 output_dir（母版候选目录）。

    keep 从第一个含该文件的工程复制；merge 写入 AI 整合出的通用版本全文
    （content）；exclude 不复制。报告的路径集合必须与对比的判定范围完全一致
    （确认环节可能被用户修改动作与内容，但路径集合不变）。落盘中途失败不留
    半成品。
    """
    _validate_report(report, comparison)
    project_dir_by_name = {p.name: p.project_dir for p in comparison.projects}

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        for decision in (*report.keep, *report.merge):
            dst = output_dir / Path(decision.path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if decision.action == ACTION_MERGE:
                dst.write_text(decision.content, encoding="utf-8")
            else:
                source_project = _source_project(decision, comparison)
                src = project_dir_by_name[source_project] / Path(decision.path)
                shutil.copy2(src, dst)
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise
    return output_dir


def _validate_report(report: DistillationReport, comparison: ProjectComparison) -> None:
    """报告必须恰好覆盖判定范围（公共文件默认在 keep 里，不在 AI 判定范围）。

    公共文件必须保留或剔除（keep / exclude；merge 被禁）——用户确认时可以把
    公共文件改为剔除；merge 词表约束由 _validate_merge_sources 统一校验；报告
    的来源工程必须与传入的对比结果一致——传错对比就是拿错误范围校验。
    """
    if set(report.projects) != {p.name for p in comparison.projects}:
        raise MasterError("报告与对比结果不匹配（来源工程不一致）")
    dispositions = (*report.keep, *report.merge, *report.exclude)
    paths = [d.path for d in dispositions]
    if len(set(paths)) != len(paths):
        raise MasterError("报告里同一路径被多次判定")
    common = set(comparison.common)
    misplaced_commons = common - {d.path for d in report.keep} - {
        d.path for d in report.exclude
    }
    if misplaced_commons:
        raise MasterError(
            "公共文件必须保留或剔除：" + "、".join(sorted(misplaced_commons))
        )
    for decision in report.merge:
        if decision.path in common:
            raise MasterError(f"公共文件必须保留：{decision.path}")
    _validate_judgment_coverage(decided=set(paths) - common, judgment=set(comparison.judgment))
    _validate_merge_sources(dispositions, comparison)


def _validate_judgment_coverage(decided: set[str], judgment: set[str]) -> None:
    missing = judgment - decided
    if missing:
        raise MasterError("提炼报告缺少判定：" + "、".join(sorted(missing)))
    unknown = decided - judgment
    if unknown:
        raise MasterError("提炼报告含对比范围外的路径：" + "、".join(sorted(unknown)))


def _source_project(decision: FileDecision, comparison: ProjectComparison) -> str:
    """keep 取第一个含该文件的工程（merge 由整合产物全文落盘，不取源）。"""
    holders = comparison.by_path.get(decision.path, ())
    if not holders:
        raise MasterError(f"没有任何工程含文件 {decision.path}")
    return holders[0]


# ---------------------------------------------------------------------------
# 母版库：入库（结构分析 + 可更换）、浏览、删除
# ---------------------------------------------------------------------------


def analyze_structure(master_dir: Path, platform: str) -> StructureAnalysis:
    """入库前的结构分析：平台配置文件缺失硬失败，其余问题进警告。

    平台配置文件缺失说明母版无法被 IDE 打开，拒绝入库；构建产物目录等
    非母版内容只给警告（生成器复制时会忽略 .git，构建目录会原样带进新工程，
    建议清理）。
    """
    _validate_known_platform(platform)
    if not master_dir.is_dir():
        raise MasterError(f"母版目录不存在：{master_dir}")
    for suffix in PLATFORM_CONFIG_FILES[platform]:
        if not _find_config_files(master_dir, f"*{suffix}"):
            raise MasterError(
                f"母版缺少平台 {platform} 的工程配置文件（{suffix}），拒绝入库"
            )
    warnings: list[str] = []
    for name in sorted(BUILD_ARTIFACT_DIRS):
        if (master_dir / name).is_dir():
            warnings.append(f"母版含 {name}/ 构建产物目录，建议清理")
    return StructureAnalysis(platform=platform, warnings=tuple(warnings))


def import_master(
    masters_dir: Path,
    platform: str,
    source_dir: Path,
    sources: Sequence[str] = (),
) -> MasterMeta:
    """母版入库：结构分析 → 复制到临时目录 → 整体替换同平台旧母版。

    每平台一个母版：目标已存在时整体更换。先分析后动盘，分析失败不落任何
    文件；旧母版先挪到备份目录再换入新母版，中途失败把备份换回来——既有
    母版在任意失败点都完好。
    """
    _validate_store_key(platform)
    analysis = analyze_structure(source_dir, platform)
    masters_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = masters_dir / f".{platform}.importing"
    backup_dir = masters_dir / f".{platform}.backup"
    shutil.rmtree(temp_dir, ignore_errors=True)  # 清掉上次失败残留
    shutil.copytree(source_dir, temp_dir)
    target_dir = masters_dir / platform
    try:
        if target_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
            os.replace(target_dir, backup_dir)  # 旧母版先挪开
        os.replace(temp_dir, target_dir)  # 新母版原子换入
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        if backup_dir.exists():
            os.replace(backup_dir, target_dir)  # 回滚旧母版
        raise
    shutil.rmtree(backup_dir, ignore_errors=True)

    meta = MasterMeta(
        platform=platform,
        sources=tuple(sources),
        warnings=analysis.warnings,
    )
    _write_meta(masters_dir, meta)
    return meta


def list_masters(masters_dir: Path) -> list[MasterMeta]:
    """返回母版库中全部母版（按平台排序）；元数据缺失或损坏抛 MasterError。"""
    if not masters_dir.is_dir():
        return []
    metas: list[MasterMeta] = []
    for entry in sorted(masters_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue  # 散文件与导入中的临时目录不影响浏览
        metas.append(get_master(masters_dir, entry.name))
    return metas


def get_master(masters_dir: Path, platform: str) -> MasterMeta:
    """读取单个母版元数据；不存在或损坏抛 MasterError。"""
    _validate_store_key(platform)
    meta_path = masters_dir / f"{platform}.json"
    try:
        text = meta_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise MasterError(f"母版 {platform!r} 不存在") from None
    except OSError as exc:
        raise MasterError(f"母版 {platform!r} 的元数据无法读取：{exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MasterError(f"母版 {platform!r} 的元数据不是合法 JSON：{exc}") from exc
    if not isinstance(data, dict):
        raise MasterError(f"{meta_path} 必须是 JSON 对象")
    try:
        return MasterMeta.from_dict(data)
    except MasterError as exc:
        raise MasterError(f"母版 {platform!r} 的元数据不合法：{exc}") from exc


def delete_master(masters_dir: Path, platform: str) -> None:
    """删除母版：工程目录与元数据文件一并移除。"""
    _validate_store_key(platform)
    target_dir = masters_dir / platform
    if not target_dir.is_dir():
        raise MasterError(f"母版 {platform!r} 不存在")
    shutil.rmtree(target_dir)
    (masters_dir / f"{platform}.json").unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 校验与辅助
# ---------------------------------------------------------------------------


def _find_config_files(project_dir: Path, pattern: str) -> list[Path]:
    """递归查找工程配置文件：跳过 .git（任意层级）与 Debug/Release 等顶层
    非母版目录——与扫描清单同一套忽略规则。"""
    return [
        p
        for p in project_dir.rglob(pattern)
        if ".git" not in p.parts
        and p.relative_to(project_dir).parts[0] not in IGNORED_TOP_LEVEL_DIRS
    ]


def _detect_platform(project_dir: Path) -> str:
    has_uvprojx = bool(_find_config_files(project_dir, "*.uvprojx"))
    has_cproject = bool(_find_config_files(project_dir, "*.cproject"))
    if has_uvprojx and has_cproject:
        raise MasterError("工程同时含 .uvprojx 与 .cproject，无法判定平台")
    if has_uvprojx:
        return PLATFORM_STM32
    if has_cproject:
        return PLATFORM_MSPM0
    raise MasterError("工程里没有 .uvprojx 或 .cproject，无法判定平台")


def _is_ignored(rel: str) -> bool:
    return rel.split("/", 1)[0] in IGNORED_TOP_LEVEL_DIRS


def _config_summary(project_dir: Path, platform: str) -> tuple[str, ...]:
    """平台配置摘要行：设备 / include path / 编译宏（配置对比的 AI 素材）。

    格式知识归修改器适配器所有（keil.py / ccs.py 的 extract_config_summary），
    这里只做平台分发；适配器内部失败（多配置文件等）转成一行摘要，扫描不因
    单个工程带病中断。
    """
    try:
        if platform == PLATFORM_STM32:
            return extract_keil_config_summary(project_dir)
        return extract_ccs_config_summary(project_dir)
    except (KeilProjectError, CcsProjectError) as exc:
        return (f"{platform} 工程配置读取失败：{exc}",)


def _validate_store_key(platform: str) -> None:
    if not _SLUG_PATTERN.fullmatch(platform):
        raise MasterError(
            f"非法平台名：{platform!r}（只能含字母数字下划线连字符，且以字母或数字开头）"
        )


def _validate_known_platform(platform: str) -> None:
    if platform not in KNOWN_PLATFORMS:
        raise MasterError(f"未知平台 {platform!r}（已知：{'、'.join(KNOWN_PLATFORMS)}）")


def _write_meta(masters_dir: Path, meta: MasterMeta) -> None:
    """写元数据：先写临时文件再原子换入，写失败不会留下损坏的 json。"""
    target = masters_dir / f"{meta.platform}.json"
    temp = masters_dir / f".{meta.platform}.json.tmp"
    temp.write_text(
        json.dumps(meta.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp, target)


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise MasterError(f"缺少必填字段：{key}")
    return value


def _require_str_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise MasterError(f"{key} 必须是非空字符串列表")
    return value
