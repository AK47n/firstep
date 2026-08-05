"""母版提炼核心：多旧工程 → 对比 → AI 判定 → 报告 → 确认 → 母版入库。

流程（spec US 18/19 + "母版提炼"实现决策）：用户导入多个同平台旧工程 →
scan_project 逐个生成结构快照（平台检测 + 文件清单 + 配置摘要）→
compare_projects 做结构对比与配置对比（公共 / 冲突 / 独有）→ distill_master
把需要判定的路径（冲突 + 独有）连同文件全文交给 LLM（两阶段：读全文出摘要
→ 基于摘要判定），公共文件按"所有工程内容一致"确定保留，残留（构建产物 /
备份 / 临时文件）按扩展名 / 模式规则识别、确定性剔除，旧工程 main.c 一律
不进母版（ADR 0002：母版 main.c 由确定性模板提供）→ 得到完整提炼报告
（保留 / 整合 / 剔除清单 + 理由，残留与 main.c 条目带规则化原因，整合产物
全文 + 说明，模板 main.c 全文预览）→ 用户一次审查、可修改动作 →
apply_distillation 按确认后的最终集合重新校验并落盘母版候选（复制 / 写整合
产物 / 剔除 + 写平台模板 main.c）→ import_master 做结构分析后入库（每平台
一个母版，可更换 / 删除）。

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
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .ccs import CcsProjectError, extract_config_summary as extract_ccs_config_summary
from .keil import KeilProjectError, extract_config_summary as extract_keil_config_summary
from .llm import FileVersion, JudgmentFile, LLM
from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32
from .report import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    DistillationReport,
    FileDecision,
    ReportError,
)

# 扫描时忽略的顶级目录：版本库与构建产物不是母版内容
BUILD_ARTIFACT_DIRS = frozenset({"Debug", "Release"})
IGNORED_TOP_LEVEL_DIRS = frozenset({".git"}) | BUILD_ARTIFACT_DIRS

# 残留规则（保守名单，与 template-fit-check.md 的"建议清理"一致）：构建产物 /
# 备份 / 临时文件按扩展名与模式机器识别。命中即确定性剔除——不进扫描清单、
# 不进 AI 判定、不读全文，但进报告 exclude 清单并带规则化原因（ADR 0001：
# 不做黑盒消失）。
RESIDUE_RULES: tuple[tuple[str, str], ...] = (
    (".o", "构建产物：.o 文件"),
    (".axf", "构建产物：.axf 文件"),
    (".hex", "构建产物：.hex 文件"),
    (".map", "构建产物：.map 文件"),
    (".bak", "备份文件：.bak"),
    (".tmp", "临时文件：.tmp"),
    (".temp", "临时文件：.temp"),
    ("~", "备份文件：~ 结尾"),
)


def residue_reason(rel_path: str) -> str | None:
    """路径命中残留规则时返回规则化原因（如"构建产物：.o 文件"），否则 None。

    按路径后缀判定（大小写不敏感——Windows 下构建产物常大写，如 .HEX）。
    规则由路径决定：同一路径在任何工程里都是残留，不可能既是残留又是源码。
    """
    lowered = rel_path.lower()
    for suffix, reason in RESIDUE_RULES:
        if lowered.endswith(suffix):
            return reason
    return None


# 模板 main.c（ADR 0002）：母版 = 空的最小系统板工程，main.c 由确定性平台模板
# 提供（时钟初始化 + while(1) 空循环 + TODO 区），能直接编译烧录；旧工程 main.c
# 一律不进母版。模板内容在 templates/ 目录（与 webapp 的 static/ 同一加载模式），
# 按平台词表命名。与残留同模式：旧 main.c 不进扫描清单的公共 / 冲突 / 独有分类、
# 不进 AI 判定素材，但进报告 exclude 清单并带规则化原因（ADR 0001：不做黑盒消失）。
TEMPLATES_DIR = Path(__file__).parent / "templates"
MAIN_C_TEMPLATE_PATH = "main.c"  # 模板 main.c 在母版里的落位路径（母版根）
MAIN_C_TEMPLATE_REASON = (
    "旧工程 main.c 一律剔除：母版 main.c 由确定性模板提供（ADR 0002）"
)


def main_c_reason(rel_path: str) -> str | None:
    """旧工程 main.c 识别：任意层级的 main.c 都由模板替代，返回规则化原因。

    按文件名判定、大小写不敏感（与残留规则同理：Windows 文件系统大小写不
    敏感，MAIN.C 也是 main 文件；同一路径在任何工程里都是 main，不可能既是
    main 又是普通源码）。命中即确定性剔除——不进 AI 判定、不读全文，但进
    报告 exclude 清单并带规则化原因。
    """
    if Path(rel_path).name.lower() == "main.c":
        return MAIN_C_TEMPLATE_REASON
    return None


def main_c_template(platform: str) -> str:
    """确定性模板 main.c 全文（非 AI 生成）：按平台取 templates/ 下的模板。

    模板文件按平台词表命名（main_stm32.c / main_mspm0.c），未知平台直接
    拒绝——模板与平台词表不漂移。生成器仍会在生成时用按赛题的骨架 main.c
    覆盖它（generator.py 现状，不改）。
    """
    _validate_known_platform(platform)
    template = TEMPLATES_DIR / f"main_{platform}.c"
    try:
        return template.read_text(encoding="utf-8")
    except OSError as exc:
        raise MasterError(f"平台 {platform} 的模板 main.c 缺失：{template}") from exc

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
    """单个工程的结构快照：平台、文件清单（相对路径 + 内容哈希）、配置摘要、
    残留清单（规则识别、确定性剔除，不进 AI 判定）、旧 main.c 清单（模板
    替代，不进扫描清单）。"""

    project_dir: Path
    name: str  # 工程名（目录名）
    platform: str  # 检测到的平台
    files: tuple[str, ...]  # 相对路径（POSIX 分隔），排序
    file_hashes: Mapping[str, str]  # path -> sha256 hex（对比内容是否一致）
    config_summary: tuple[str, ...]  # 平台配置摘要行（配置对比的 AI 素材）
    residues: tuple[str, ...] = ()  # 残留相对路径（构建产物 / 备份 / 临时文件）
    main_c_files: tuple[str, ...] = ()  # 旧工程 main.c（模板替代，不进扫描清单）


@dataclass(frozen=True)
class ProjectComparison:
    """多工程的结构 + 配置对比结果。"""

    projects: tuple[ProjectStructure, ...]
    common: tuple[str, ...]  # 所有工程都有且内容完全一致
    conflicts: tuple[str, ...]  # 同路径、内容不一致
    unique: tuple[str, ...]  # 只出现在部分工程
    by_path: Mapping[str, tuple[str, ...]]  # path -> 含该文件的工程名（出现顺序）
    judgment: tuple[str, ...]  # 需要 AI 判定的路径（冲突 + 独有）
    residues: tuple[str, ...] = ()  # 全部工程的残留路径（并集，排序）
    main_c_files: tuple[str, ...] = ()  # 全部工程的旧 main.c（并集，排序，模板替代）


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
    顶层目录不进清单。残留（构建产物 / 备份 / 临时文件）单独记录在
    residues、不进扫描清单也不读内容（可能是二进制）；旧 main.c（任意层级）
    单独记录在 main_c_files（模板替代，ADR 0002）、不进扫描清单也不读内容；
    config_summary 提取设备 / include path / 编译宏等配置对比素材（XML 解析
    失败只记一行，扫描不因单个工程带病中断）。
    """
    if not project_dir.is_dir():
        raise MasterError(f"工程目录不存在：{project_dir}")
    platform = _detect_platform(project_dir)
    files: list[str] = []
    residues: list[str] = []
    main_c_files: list[str] = []
    hashes: dict[str, str] = {}
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(project_dir).as_posix()
        if _is_ignored(rel):
            continue
        if residue_reason(rel) is not None:
            residues.append(rel)
            continue
        if main_c_reason(rel) is not None:
            main_c_files.append(rel)
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
        residues=tuple(residues),
        main_c_files=tuple(main_c_files),
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
        residues=tuple(sorted({r for p in projects for r in p.residues})),
        main_c_files=tuple(sorted({m for p in projects for m in p.main_c_files})),
    )


def build_judgment_files(comparison: ProjectComparison) -> tuple[JudgmentFile, ...]:
    """待判文件（冲突 + 独有）的全文素材：路径 + 每个内容版本及其持有工程。

    兑现 ADR 0001 的"读内容判断"——AI 判定前先看到文件全文。同一路径在多个
    工程里内容不同（冲突）时每个内容版本都进素材；内容一致的工程合并为一个
    版本（按扫描时的内容哈希分组，版本工程名不重不漏）。读取用 UTF-8 容错：
    旧工程可能是 GBK 等编码，宁可摘要含乱码也不让提炼因单个文件中断。
    """
    projects_by_name = {p.name: p for p in comparison.projects}
    files: list[JudgmentFile] = []
    for path in comparison.judgment:
        holders = comparison.by_path[path]
        versions: list[FileVersion] = []
        seen_hashes: set[str] = set()
        for name in holders:
            project = projects_by_name[name]
            content_hash = project.file_hashes[path]
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            group = tuple(
                n for n in holders if projects_by_name[n].file_hashes[path] == content_hash
            )
            versions.append(
                FileVersion(
                    content=(project.project_dir / path).read_text(
                        encoding="utf-8", errors="replace"
                    ),
                    projects=group,
                )
            )
        files.append(JudgmentFile(path=path, versions=tuple(versions)))
    return tuple(files)


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
    """提炼流程：对比 → LLM 判定（读全文 → 摘要 → 判定）→ 拼装完整报告。

    公共文件确定保留（所有工程内容一致，无需 AI）；冲突与独有文件连同全文
    交给 AI（llm 内部先逐文件读全文出摘要，再基于摘要判定），覆盖不全或出现
    未知路径抛 MasterError——宁可不放行也不带病进入确认流程。
    """
    comparison = compare_projects(projects)
    _validate_platform_match(platform, comparison)
    project_names = tuple(p.name for p in projects)
    decisions = llm.distill_master(
        platform,
        project_names,
        build_judgment_files(comparison),
        build_comparison_summary(comparison),
    )
    return assemble_report(platform, project_names, comparison, decisions)


def assemble_report(
    platform: str,
    project_names: Sequence[str],
    comparison: ProjectComparison,
    decisions: Sequence[FileDecision],
) -> DistillationReport:
    """把确定性公共文件、规则化残留剔除、旧 main.c 模板替代与 AI 判定拼成完整
    报告，并校验覆盖。

    判据是内容（通用性 / 基础建设必需性），分类不直接决定动作：冲突文件可以
    merge（整合出通用版本）也可以 exclude，只有 keep 被禁止（keep 没有"取哪份
    内容"的信息，落盘时会静默取第一个工程）；公共文件确定保留——AI 重复判定
    keep 是冗余（忽略），判定 merge / exclude 是错误（公共文件必须保留），
    用户确认时可把公共文件改为剔除。残留（构建产物 / 备份 / 临时文件）与旧
    main.c（ADR 0002：母版 main.c 由确定性模板提供）机器识别、确定性剔除：
    不进 AI 判定素材（AI 给出这类路径的判定是越界，拒绝），报告 exclude 清单
    自动带规则化原因（ADR 0001：不做黑盒消失）。merge 必须带整合产物全文与
    整合说明（选一份只是特例）。这些在确认前就拦住，兑现"不带病进入确认流程"。
    """
    common = set(comparison.common)
    residues = set(comparison.residues)
    main_c_files = set(comparison.main_c_files)
    scoped: list[FileDecision] = []
    for decision in decisions:
        if decision.path in residues:
            # 残留由规则确定性剔除，AI 从未在素材里见过它——判定即越界
            raise MasterError(f"残留文件由规则剔除，无需 AI 判定：{decision.path}")
        if decision.path in main_c_files:
            # 旧 main.c 由模板确定性替代（ADR 0002），AI 从未在素材里见过它
            raise MasterError(f"旧工程 main.c 由模板替代，无需 AI 判定：{decision.path}")
        if decision.path in common:
            # 公共文件由确定性自动保留覆盖；AI 重复判定 keep 是冗余（忽略），
            # 判定 merge / exclude 是错误（公共文件必须保留），直接拒绝
            if decision.action != ACTION_KEEP:
                raise MasterError(f"公共文件必须保留：{decision.path}")
            continue
        scoped.append(decision)
    decided = {d.path for d in scoped}
    _validate_judgment_coverage(decided=decided, judgment=set(comparison.judgment))
    _validate_merge_sources(scoped, comparison)

    keep: list[FileDecision] = [
        FileDecision(path, ACTION_KEEP, reason="所有导入工程内容一致，属公共骨架")
        for path in comparison.common
    ]
    merge: list[FileDecision] = []
    exclude: list[FileDecision] = []
    for decision in scoped:
        if decision.action == ACTION_MERGE:
            merge.append(decision)
        elif decision.action == ACTION_EXCLUDE:
            exclude.append(decision)
        else:
            keep.append(decision)
    for path in comparison.residues:
        reason = residue_reason(path)
        if reason is None:
            # 对比结果由扫描分类产生，残留路径必命中规则；手动构造的对比
            # 带病也要在此大声失败，而不是把 None 理由带进报告
            raise MasterError(f"残留路径未命中规则：{path}")
        exclude.append(FileDecision(path, ACTION_EXCLUDE, reason=reason))
    for path in comparison.main_c_files:
        reason = main_c_reason(path)
        if reason is None:
            raise MasterError(f"旧工程 main.c 未命中规则：{path}")
        exclude.append(FileDecision(path, ACTION_EXCLUDE, reason=reason))
    return DistillationReport(
        platform=platform,
        projects=tuple(project_names),
        keep=tuple(keep),
        merge=tuple(merge),
        exclude=tuple(exclude),
        main_c_preview=main_c_template(platform),
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
    （content）；exclude 不复制。落盘完成后写平台模板 main.c（ADR 0002：
    母版 = 空的最小系统板工程，旧工程 main.c 一律不进母版）。报告的路径集合
    必须与对比的判定范围完全一致（确认环节可能被用户修改动作与内容，但路径
    集合不变）。落盘中途失败不留半成品。
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
        (output_dir / MAIN_C_TEMPLATE_PATH).write_text(
            main_c_template(report.platform), encoding="utf-8"
        )
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
    _validate_platform_match(report.platform, comparison)
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
    # 残留与旧 main.c 在报告里但不在判定范围（规则识别、确定性剔除），从覆盖
    # 校验中扣除；它们必须恰好出现在 exclude 里，由 _validate_residue_disposition
    # / _validate_main_c_disposition 单独校验
    _validate_judgment_coverage(
        decided=set(paths) - common - set(comparison.residues)
        - set(comparison.main_c_files),
        judgment=set(comparison.judgment),
    )
    _validate_residue_disposition(report, comparison)
    _validate_main_c_disposition(report, comparison)
    _validate_merge_sources(dispositions, comparison)


def _validate_residue_disposition(
    report: DistillationReport, comparison: ProjectComparison
) -> None:
    """残留必须恰好剔除一次：规则识别的确定性剔除（见 _validate_forced_exclusions）。"""
    _validate_forced_exclusions(
        set(comparison.residues), report, "残留文件必须剔除"
    )


def _validate_main_c_disposition(
    report: DistillationReport, comparison: ProjectComparison
) -> None:
    """旧工程 main.c 必须恰好剔除一次：模板替代的确定性剔除（ADR 0002，
    见 _validate_forced_exclusions）。"""
    _validate_forced_exclusions(
        set(comparison.main_c_files), report, "旧工程 main.c 必须剔除"
    )


def _validate_forced_exclusions(
    forced: set[str], report: DistillationReport, error_prefix: str
) -> None:
    """确定性剔除的文件必须恰好剔除一次：用户确认也不能改成保留 / 整合或
    删掉（删掉 = 黑盒消失，ADR 0001）。两种问题一次报全，各自带原因。"""
    moved = sorted(
        forced
        & {
            d.path
            for d in (*report.keep, *report.merge, *report.exclude)
            if d.action != ACTION_EXCLUDE
        }
    )
    missing = sorted(forced - {d.path for d in report.exclude})
    if moved or missing:
        problems = [f"{path}（被改为保留/整合）" for path in moved]
        problems += [f"{path}（报告中缺失）" for path in missing]
        raise MasterError(f"{error_prefix}：" + "、".join(problems))


def _validate_platform_match(platform: str, comparison: ProjectComparison) -> None:
    """报告 / 提炼的平台必须与工程的平台一致（平台交叉校验）。

    平台名来自调用方（webapp 从客户端 payload 取），工程平台由扫描判定；
    compare_projects 只保证工程之间同平台，不保证调用方给的平台与工程一致。
    不一致时报告会带着错误平台的模板 main.c 预览与错误落位路径，必须在确认
    前拦住。
    """
    projects_platform = comparison.projects[0].platform  # compare 已保证同平台
    if platform != projects_platform:
        raise MasterError(
            f"平台不一致：报告为 {platform!r}，工程为 {projects_platform!r}"
        )


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


def confirm_distillation(
    masters_dir: Path,
    project_dirs: Sequence[Path],
    payload: dict[str, Any],
) -> MasterMeta:
    """确认报告并落库：重扫 → 重比 → 重建报告 → 暂存 → 落盘 → 入库，一次事务。

    确认请求里的 project_dirs 与报告同样不可信：落库前重新扫描对比、按报告
    模型重建（形状校验在 report.DistillationReport.from_dict，容器形状错误
    在此转成 MasterError——HTTP 层只认这一种），暂存目录在函数内部自生自灭
    ——任何一步失败都不留半成品，既有母版在任意失败点都完好（import_master
    自带备份回滚）。webapp 只收请求、调这里、转 JSON。
    """
    projects = tuple(scan_project(project_dir) for project_dir in project_dirs)
    comparison = compare_projects(projects)
    if not isinstance(payload, dict):
        raise MasterError("提炼报告必须是 JSON 对象")
    platform = _require_str(payload, "platform")
    try:
        report = DistillationReport.from_dict(
            payload,
            # 预览是确定性素材（落盘永远写 main_c_template(platform)）：客户端
            # 回传值不可信，按平台重推导；平台非法由模板加载大声失败
            main_c_preview=main_c_template(platform),
        )
    except ReportError as exc:
        raise MasterError(str(exc)) from exc
    staging = Path(tempfile.mkdtemp(prefix="master-staging-"))
    try:
        preview = apply_distillation(report, comparison, staging / "preview")
        meta = import_master(
            masters_dir, report.platform, preview, sources=report.projects
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return meta


# ---------------------------------------------------------------------------
# 母版库：入库（结构分析 + 可更换）、浏览、删除
# ---------------------------------------------------------------------------


def master_project_dir(masters_dir: Path, platform: str) -> Path:
    """母版在库里的目录位置：<masters_dir>/<platform>（库布局的唯一出处）。

    import_master / get_master / delete_master 与生成流程共用这一条布局规则；
    平台名先过合法性校验——借平台名拼路径逃出母版库在入口处就被拦住。
    """
    _validate_store_key(platform)
    return masters_dir / platform


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
