"""母版提炼核心：多旧工程 → 对比 → AI 判定 → 报告 → 确认 → 母版入库。

流程（spec US 18/19 + "母版提炼"实现决策）：用户导入多个同平台旧工程 →
scan_project 逐个生成结构快照（平台检测 + 文件清单 + 配置摘要）→
compare_projects 做结构对比与配置对比（公共 / 冲突 / 独有）→ distill_master
把全部文件（公共 + 冲突 + 独有，公共不等于基础建设必需，同样逐个判）连同
文件全文交给 LLM（两阶段：读全文出摘要 → 基于摘要判定），残留（构建产物 /
备份 / 临时文件 / IDE 用户选项）按扩展名 / 模式规则识别、二进制文件（非源码
素材）按内容规则识别，确定性剔除，旧工程 main.c 一律不进母版（ADR 0002：
母版 main.c 由确定性模板提供），启动文件（.s）与链接脚本（.ld/.sct/.cmd）
按扩展名规则确定性保留、启动文件跨工程去重（至多一份，优先 _md，决策 2），
工程配置文件（.uvprojx / .cproject / .project）移出 AI 判定（工单 09：
判例 09 治本——AI 手写整合 XML 结构残缺照样入库，stm32 的 .uvprojx 由
确定性渲染器现写，结构一致性由构造保证；mspm0 保留首份原样）→ 得到完整
提炼报告（保留 / 整合 / 剔除清单 + 理由，残留与 main.c 条目带规则化原因，
整合产物全文 + 说明，模板 main.c 全文预览，.uvprojx 全文预览）→ 用户一次
审查、可修改动作 → apply_distillation 按确认后的最终集合重新校验并落盘母版
候选（复制 / 写整合产物 / 剔除 + 写平台模板 main.c + stm32 的 .uvprojx 由
渲染器现写到 user/Project.uvprojx：设备块 C8T6 硬编码、文件树引用全部保留
.c/.s、IncludePath = 保留 .h 所在目录，密度守卫——保留启动文件非 _md 大声
失败）→ import_master 做结构分析后入库（每平台一个母版，可更换 / 删除）。

职责划分（架构深化 v5 三轴拆块，工单 01）：文件类别的识别规则与生命周期
（RULE_CATEGORIES / classify / 启动文件去重）唯一出处 = categories.py，
本模块只消费不定义；母版库 CRUD、元数据与 MasterError 唯一出处 =
master_store.py；蒸馏侧平台行为（摘要读 / 渲染 / 启动候选谓词）经
distill_adapters 适配器按平台取（工单 04，守卫翻译在缝内归 MasterError），
本模块不直连 keil / ccs。母版库：磁盘目录即数据库，库根下每平台一个目录
（工程文件本体）+ 同名 <platform>.json 元数据（提炼来源、入库时结构分析
的警告）。元数据放目录外的平级文件：母版目录会被生成器整体复制，内部带
json（如 master.json）会污染生成的工程。任何从平台名拼路径的操作都先校验
平台名合法性，杜绝借平台名逃出母版库的路径穿越。
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Sequence

from .categories import (
    INFRASTRUCTURE_REASON,
    RULE_CATEGORIES,
    STARTUP_REPLACEMENT_REASON,
    RuleCategory,
    _pick_startup,
    _validate_startup_disposition,
    classify,
)
from .distill_adapters import get_distill_adapter
from .master_store import (
    MasterError,
    MasterMeta,
    _find_config_files,
    _require_str,
    _validate_known_platform,
    import_master,
)
from .platforms import KNOWN_PLATFORMS, PLATFORM_CONFIG_FILE_SUFFIXES
from .treewalk import iter_project_files

if TYPE_CHECKING:
    # 仅类型注解用（llm 运行时依赖 selection → reference_library，运行时导入
    # 会把参考库族拖进 master 的 import 闭包，工单 C3 链收敛；library.py 先例）
    from .events import ProgressEmitter
    from .llm import LLM
from .report import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    DistillationReport,
    FileDecision,
    FileVersion,
    JudgmentFile,
    ProjectComparison,
    ProjectStructure,
    ReportError,
)

# 模板 main.c（ADR 0002）：母版 = 空的最小系统板工程，main.c 由确定性平台模板
# 提供（时钟初始化 + while(1) 空循环 + TODO 区），能直接编译烧录；旧工程 main.c
# 一律不进母版。模板内容在 templates/ 目录（与 webapp 的 static/ 同一加载模式），
# 按平台词表命名。旧 main.c 的识别与剔除原因唯一出处 = categories.py
# （main_c_reason / MAIN_C_TEMPLATE_REASON）。
TEMPLATES_DIR = Path(__file__).parent / "templates"
MAIN_C_TEMPLATE_PATH = "main.c"  # 模板 main.c 在母版里的落位路径（母版根）


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


# ---------------------------------------------------------------------------
# 工程扫描与对比
# ---------------------------------------------------------------------------


def scan_project(project_dir: Path) -> ProjectStructure:
    """扫描单个工程：平台检测 + 文件清单（含内容哈希）+ 平台配置摘要。

    平台由工程配置文件判定：有 .uvprojx 为 stm32，有 .cproject 为 mspm0；
    两者都有或都没有抛 MasterError。工程文件在任意层级可识别（正点原子风格
    在 USER/ 子目录），.git 目录除外。.git / Debug / Release 等非母版内容的
    顶层目录不进清单。残留（构建产物 / 备份 / 临时文件 / IDE 用户选项）单独
    记录在 residues、不进扫描清单也不读内容（可能是二进制）；旧 main.c（任意
    层级）单独记录在 main_c_files（模板替代，ADR 0002）、不进扫描清单也不读
    内容；启动文件候选（startup_stm32f10x_*.s，跨工程去重）单独记录在
    startup_files、其余链接脚本 / 非启动 .s 记录在 infrastructure——确定性
    保留、不进扫描清单也不读内容；工程配置文件（.uvprojx/.cproject/.project，
    工单 09）单独记录在 config_files、确定性规则处理、不进扫描清单也不读
    内容；二进制文件（内容判据：文件头含 NUL）单独记录在 binaries、确定性
    剔除、不进扫描清单也不读全文（可能是几十 MB 的模型 / 压缩包）；
    config_summary 提取设备 / include path / 编译宏等配置对比素材（XML 解析
    失败只记一行，扫描不因单个工程带病中断）。类别判定按表序由
    categories.classify 完成（表遍历知识唯一出处）。
    """
    if not project_dir.is_dir():
        raise MasterError(f"工程目录不存在：{project_dir}")
    platform = _detect_platform(project_dir)
    files: list[str] = []
    startup_files: list[str] = []  # 启动文件候选（决策 2：表内钩子，单独记录）
    hashes: dict[str, str] = {}
    category_lists: dict[str, list[str]] = {
        cat.key: [] for cat in RULE_CATEGORIES
    }
    for path in iter_project_files(project_dir):
        rel = path.relative_to(project_dir).as_posix()
        key, is_startup = classify(rel, path, platform)
        if key is not None:
            # 类别互斥、按表序判定（残留 → main.c → 基础设施 → 二进制 →
            # 工程配置文件）：命中即分类、不读全文（二进制探针只读文件头）。
            # 表内钩子：基础设施命中且是启动文件候选（startup_*.s）时
            # 单列到 startup_files——跨工程去重（决策 2），不进基础设施组
            if is_startup:
                startup_files.append(rel)
            else:
                category_lists[key].append(rel)
        else:
            files.append(rel)
            hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return ProjectStructure(
        project_dir=project_dir,
        name=project_dir.name,
        platform=platform,
        files=tuple(files),
        file_hashes=hashes,
        config_summary=_config_summary(project_dir, platform),
        startup_files=tuple(startup_files),
        residues=tuple(category_lists["residues"]),
        main_c_files=tuple(category_lists["main_c_files"]),
        infrastructure=tuple(category_lists["infrastructure"]),
        binaries=tuple(category_lists["binaries"]),
        config_files=tuple(category_lists["config_files"]),
    )


def compare_projects(projects: Sequence[ProjectStructure]) -> ProjectComparison:
    """结构 + 配置对比：按路径分类公共 / 冲突 / 独有，平台必须一致。

    公共 = 所有工程都有且内容完全一致；冲突 = 同路径内容不一致；独有 =
    只出现在部分工程。by_path 记录每个路径出现在哪些工程（出现顺序），
    供报告确认后的落盘取源。判定范围 = 公共 + 冲突 + 独有（全部文件，
    ADR 0001：不看重复次数与出现范围——公共 ≠ 基础建设必需，也进 AI 判定）。
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
        judgment=(
            tuple(sorted(common)) + tuple(sorted(conflicts)) + tuple(sorted(unique))
        ),
        # 类别分组并集（残留 / main.c / 基础设施 / 二进制 / 工程配置文件，
        # 遍历类别表）+ 启动文件候选（表内钩子，决策 2）
        **{
            cat.key: tuple(
                sorted({v for p in projects for v in getattr(p, cat.key)})
            )
            for cat in RULE_CATEGORIES
        },
        startup_files=tuple(
            sorted({s for p in projects for s in p.startup_files})
        ),
    )


def build_judgment_files(comparison: ProjectComparison) -> tuple[JudgmentFile, ...]:
    """待判文件（公共 + 冲突 + 独有，全部文件）的全文素材：路径 + 每个内容
    版本及其持有工程。

    兑现 ADR 0001 的"读内容判断"——AI 判定前先看到文件全文。公共文件（所有
    工程内容一致）是一个单版本条目；同一路径在多个工程里内容不同（冲突）时
    每个内容版本都进素材；内容一致的工程合并为一个版本（按扫描时的内容哈希
    分组，版本工程名不重不漏）。读取用 UTF-8 容错：旧工程可能是 GBK 等编码，
    宁可摘要含乱码也不让提炼因单个文件中断。
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
    progress_emitter: ProgressEmitter | None = None,
) -> DistillationReport:
    """提炼流程：对比 → LLM 判定（读全文 → 摘要 → 判定）→ 拼装完整报告。

    全部文件（公共 + 冲突 + 独有）连同全文交给 AI（llm 内部先逐文件读全文
    出摘要，再基于摘要判定）——公共文件只是"每份内容一样"，不等于基础建设
    必需，同样逐个判（ADR 0001：不看重复次数与出现范围）。覆盖不全或出现
    未知路径抛 MasterError——宁可不放行也不带病进入确认流程。
    progress_emitter 透传给 llm.distill_master（工单 01 的发射 seam）：
    webapp 层把它接到 SSE 流上；默认 None 不发射，行为与现状一致。
    """
    comparison = compare_projects(projects)
    _validate_platform_match(platform, comparison)
    project_names = tuple(p.name for p in projects)
    decisions = llm.distill_master(
        platform,
        project_names,
        build_judgment_files(comparison),
        build_comparison_summary(comparison),
        progress_emitter,
    )
    return assemble_report(platform, project_names, comparison, decisions)


def assemble_report(
    platform: str,
    project_names: Sequence[str],
    comparison: ProjectComparison,
    decisions: Sequence[FileDecision],
) -> DistillationReport:
    """把 AI 判定、规则化残留剔除、旧 main.c 模板替代、配置文件与启动去重
    拼成完整报告，并校验覆盖。

    判据是内容（基础建设必需性），分类不直接决定动作：公共文件（所有工程
    内容一致）AI 判 keep 或 exclude 都合法——"每份内容一样"不等于基础建设
    必需，业务 .c/.h 即使所有工程共享也按内容判除（ADR 0001：不看重复次数
    与出现范围）；冲突文件可以 merge（整合出通用版本）也可以 exclude，只有
    keep 被禁止（keep 没有"取哪份内容"的信息，落盘时会静默取第一个工程）；
    merge 必须带整合产物全文与整合说明（选一份只是特例）。残留（构建产物 /
    备份 / 临时文件 / IDE 用户选项）、旧 main.c（ADR 0002：母版 main.c 由
    确定性模板提供）与二进制文件（内容判据，非源码素材）机器识别、确定性
    剔除：不进 AI 判定素材（AI 给出这类路径的判定是越界，拒绝），报告
    exclude 清单自动带规则化原因（ADR 0001：不做黑盒消失）。
    启动文件 / 链接脚本（基础设施）同模式、确定性保留：不进 AI 判定素材，
    AI 判定即越界，报告 keep 清单自动带规则化原因——这些文件判错（剔除）
    会直接断掉空工程的编译链。启动文件候选跨工程去重（决策 2）：保留份进
    keep、落选份进 exclude（"启动文件替代"原因），各不可改动作。工程配置
    文件（.uvprojx/.cproject/.project，工单 09 判例 09 治本）同模式进 keep
    带规则化原因——stm32 的 .uvprojx 由确定性渲染器现写，报告同时携带
    .uvprojx 全文预览（与 main_c_preview 同款：确认回传时按平台重推导，
    客户端回传值不可信；mspm0 无现写，预览为空串）。以上在确认前就拦住，
    兑现"不带病进入确认流程"。
    """
    scoped: list[FileDecision] = []
    startup_files = set(comparison.startup_files)
    for decision in decisions:
        for cat in RULE_CATEGORIES:
            if decision.path in getattr(comparison, cat.key):
                # 类别由规则确定性处置（剔除 / 保留 / 模板替代），AI 从未在
                # 素材里见过它——判定即越界，确认前拦住，兑现"不带病进入确认流程"
                raise MasterError(
                    cat.out_of_scope_message.format(path=decision.path)
                )
        if decision.path in startup_files:
            # 启动文件候选跨工程去重（决策 2）：表内钩子，AI 从未在素材里见过它
            raise MasterError(f"启动文件由规则处理，无需 AI 判定：{decision.path}")
        scoped.append(decision)
    decided = {d.path for d in scoped}
    _validate_judgment_coverage(decided=decided, judgment=set(comparison.judgment))
    _validate_merge_sources(scoped, comparison)

    # 类别文件自动进报告（带规则化原因，ADR 0001：不做黑盒消失）。顺序与旧
    # 行为一致：keep 的类别文件排前（旧：基础设施、配置文件先拼），exclude
    # 的排后（旧：AI 判定先拼）
    category_keep: list[FileDecision] = []
    category_exclude: list[FileDecision] = []
    for cat in RULE_CATEGORIES:
        for path in getattr(comparison, cat.key):
            reason = cat.report_reason(path)
            if reason is None:
                # 对比结果由扫描分类产生，类别路径必命中规则；手动构造的对比
                # 带病也要在此大声失败，而不是把 None 理由带进报告
                raise MasterError(f"{cat.name}未命中规则：{path}")
            decision = FileDecision(
                path,
                ACTION_KEEP if cat.disposition == "keep" else ACTION_EXCLUDE,
                reason=reason,
            )
            (category_keep if cat.disposition == "keep" else category_exclude).append(
                decision
            )
    keep: list[FileDecision] = category_keep
    startup = _pick_startup(comparison.startup_files, platform)
    if startup is not None:
        # 启动文件去重保留份（决策 2）：基础设施同款确定性保留
        keep.append(FileDecision(startup, ACTION_KEEP, reason=INFRASTRUCTURE_REASON))
    keep += [d for d in scoped if d.action == ACTION_KEEP]
    merge: list[FileDecision] = [d for d in scoped if d.action == ACTION_MERGE]
    exclude: list[FileDecision] = [d for d in scoped if d.action == ACTION_EXCLUDE]
    exclude += category_exclude
    if startup is not None:
        for path in sorted(set(comparison.startup_files) - {startup}):
            exclude.append(
                FileDecision(path, ACTION_EXCLUDE, reason=STARTUP_REPLACEMENT_REASON)
            )
    return DistillationReport(
        platform=platform,
        projects=tuple(project_names),
        keep=tuple(keep),
        merge=tuple(merge),
        exclude=tuple(exclude),
        main_c_preview=main_c_template(platform),
        # 预览与落盘同源：直接用拼好的 keep + merge（含规则添加的启动文件 /
        # 基础设施 / 配置文件条目），与 apply_distillation 的 _render_inputs
        # 输入一致——报告预览 = 实际落盘渲染产物
        uvprojx_preview=_config_preview(platform, (*keep, *merge), comparison),
    )


def _render_inputs(
    platform: str,
    decisions: Sequence[FileDecision],
    comparison: ProjectComparison,
) -> tuple[list[str], str | None, list[str]]:
    """渲染器输入推导：保留源码（.c/.s）+ 启动文件（去重后）+ 保留 .h 所在目录。

    预览（_config_preview）与落盘（apply_distillation）共用——同一份最终
    决策集必然渲染出同一份 .uvprojx，报告预览 = 实际落盘内容。platform
    透传给 _pick_startup（启动谓词按平台取，工单 04）。
    """
    sources = [
        d.path
        for d in decisions
        if Path(d.path).suffix.lower() in (".c", ".s")
    ]
    include_dirs = sorted(
        {
            str(Path(d.path).parent)
            for d in decisions
            if Path(d.path).suffix.lower() == ".h"
        }
    )
    return sources, _pick_startup(comparison.startup_files, platform), include_dirs


def _config_preview(
    platform: str, decisions: Sequence[FileDecision], comparison: ProjectComparison
) -> str:
    """.uvprojx 全文预览（决策 7）：经蒸馏适配器按平台渲染（stm32 由确定性
    渲染器推导，与 main_c_preview 同款——确认回传时按平台重推导，客户端
    回传值不可信）；mspm0 显式无操作（无现写，保留首份原样），返回空串。"""
    return get_distill_adapter(platform).render_config(
        *_render_inputs(platform, decisions, comparison)
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
    母版 = 空的最小系统板工程，旧工程 main.c 一律不进母版）；工程配置文件
    经蒸馏适配器按平台处置（工单 04）：stm32 的 .uvprojx 由确定性渲染器
    现写（工单 09，判例 09 治本：不再从源工程复制也无需引用重写——渲染
    产物按保留集合构造，结构一致性由构造保证，落位 user/Project.uvprojx；
    密度守卫在渲染器，翻译在适配器缝内归 MasterError：保留启动文件非 _md
    大声失败，目标板 STM32F103C8T6 中密度）；非渲染平台（mspm0）保留首份
    原样（判例 09）——复制是编排层通用操作，非平台能力。报告的路径集合
    必须与对比的判定范围完全一致（确认环节可能被用户修改动作与内容，但
    路径集合不变）。落盘中途失败不留半成品。
    """
    _validate_report(report, comparison)
    project_dir_by_name = {p.name: p.project_dir for p in comparison.projects}
    config_paths = set(comparison.config_files)

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        for decision in (*report.keep, *report.merge):
            if decision.path in config_paths:
                continue  # 工程配置文件不走复制：stm32 现写 / mspm0 保留首份，见下
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
        adapter = get_distill_adapter(report.platform)
        if adapter.renders_config:
            adapter.write_config(
                output_dir,
                *_render_inputs(
                    report.platform, (*report.keep, *report.merge), comparison
                ),
            )
        else:
            for decision in report.keep:
                if decision.path not in config_paths:
                    continue
                dst = output_dir / Path(decision.path)
                dst.parent.mkdir(parents=True, exist_ok=True)
                source_project = _source_project(decision, comparison)
                src = project_dir_by_name[source_project] / Path(decision.path)
                shutil.copy2(src, dst)
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise
    return output_dir


def _validate_report(report: DistillationReport, comparison: ProjectComparison) -> None:
    """报告必须恰好覆盖判定范围（公共 + 冲突 + 独有，全部文件）。

    公共文件必须保留或剔除（keep / exclude）——AI 判 keep 或 exclude 都合法，
    用户确认时也可以改；merge 词表约束（merge 只用于冲突文件）由
    _validate_merge_sources 统一校验；报告的来源工程必须与传入的对比结果
    一致——传错对比就是拿错误范围校验。
    """
    if set(report.projects) != {p.name for p in comparison.projects}:
        raise MasterError("报告与对比结果不匹配（来源工程不一致）")
    _validate_platform_match(report.platform, comparison)
    # 归档条目（工单 02）与判定条目一起计入覆盖：路径集合 = keep + merge +
    # exclude + archive，恰好覆盖判定范围且不重复——归档 = 该文件不进母版但
    # 复制入库参考文件库，同样是一次"判定"
    dispositions = (*report.keep, *report.merge, *report.exclude)
    paths = [d.path for d in dispositions] + [d.path for d in report.archive]
    if len(set(paths)) != len(paths):
        raise MasterError("报告里同一路径被多次判定")
    common = set(comparison.common)
    misplaced_commons = common - {d.path for d in report.keep} - {
        d.path for d in report.exclude
    } - {d.path for d in report.archive}
    if misplaced_commons:
        raise MasterError(
            "公共文件必须保留或剔除：" + "、".join(sorted(misplaced_commons))
        )
    # 类别文件（残留 / 旧 main.c / 基础设施 / 二进制 / 工程配置文件）不在
    # 判定范围（规则识别、确定性处置），从覆盖校验中扣除；它们必须恰好按
    # 各自 disposition 处置，由 _validate_category_disposition 逐类校验（遍历
    # 类别表）——归档条目也逃不过：残留 / 二进制等类别文件必须剔除，不配归档。
    # 启动文件候选（决策 2 表内钩子）同样不在判定范围：保留份必须 keep、
    # 落选份必须 exclude，由 _validate_startup_disposition（categories.py）
    # 单独校验。
    category_paths = {
        path
        for cat in RULE_CATEGORIES
        for path in getattr(comparison, cat.key)
    }
    _validate_judgment_coverage(
        decided=set(paths) - category_paths - set(comparison.startup_files),
        judgment=set(comparison.judgment),
    )
    for cat in RULE_CATEGORIES:
        _validate_category_disposition(cat, report, comparison)
    _validate_startup_disposition(report, comparison.startup_files)
    _validate_merge_sources(dispositions, comparison)


def _validate_category_disposition(
    category: RuleCategory,
    report: DistillationReport,
    comparison: ProjectComparison,
) -> None:
    """类别文件必须恰好按 disposition 处置一次（保留 / 剔除）。

    规则识别的确定性处置：用户确认也不能改成别的动作或删掉（删掉 = 黑盒
    消失，ADR 0001；基础设施被剔除 = 空工程编译链断裂）。两种问题一次报全，
    各自带原因。
    """
    forced = set(getattr(comparison, category.key))
    expected = ACTION_KEEP if category.disposition == "keep" else ACTION_EXCLUDE
    section = report.keep if expected == ACTION_KEEP else report.exclude
    moved = sorted(
        forced
        & {
            d.path
            for d in (*report.keep, *report.merge, *report.exclude)
            if d.action != expected
        }
    )
    missing = sorted(forced - {d.path for d in section})
    if moved or missing:
        moved_verbs = "保留/整合" if expected == ACTION_EXCLUDE else "整合/剔除"
        problems = [f"{path}（被改为{moved_verbs}）" for path in moved]
        problems += [f"{path}（报告中缺失）" for path in missing]
        raise MasterError(
            f"{category.disposition_message}：" + "、".join(problems)
        )


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
    """keep 取第一个含该文件的工程（merge 由整合产物全文落盘，不取源）。

    keep 类别的文件（基础设施 / 工程配置文件）与启动文件去重保留份（决策 2）
    不在扫描清单（by_path 不含它们），从工程快照的对应类别清单取源。
    """
    holders = comparison.by_path.get(decision.path, ())
    if holders:
        return holders[0]
    for project in comparison.projects:
        if any(
            decision.path in getattr(project, cat.key)
            for cat in RULE_CATEGORIES
            if cat.disposition == "keep"
        ):
            return project.name
        if decision.path in project.startup_files:
            return project.name
    raise MasterError(f"没有任何工程含文件 {decision.path}")


def confirm_distillation(
    masters_dir: Path,
    project_dirs: Sequence[Path],
    payload: dict[str, Any],
    *,
    llm_factory: Callable[[], LLM] | None = None,
    reference_library_dir: Path | None = None,
) -> MasterMeta:
    """确认报告并落库：重扫 → 重比 → 重建报告 → 暂存 → 落盘 → 入库，一次事务。

    确认请求里的 project_dirs 与报告同样不可信：落库前重新扫描对比、按报告
    模型重建（形状校验在 report.DistillationReport.from_dict，容器形状错误
    在此转成 MasterError——HTTP 层只认这一种），暂存目录在函数内部自生自灭
    ——任何一步失败都不留半成品，既有母版在任意失败点都完好（import_master
    自带备份回滚）。webapp 只收请求、调这里、转 JSON。

    归档动作（工单 02，报告 archive 段）：随确认事务一起提交——报告校验与
    暂存（apply_distillation，类别文件不配归档在此被拦）→ LLM 判定归档价值
    并生成条目简介（全部在任何真写盘前，失败即整体中止、母版库与参考库都不
    被触碰）→ 母版先入库（既有事务语义不变）→ 归档条目复制入库（每条目
    原子，批量失败回滚本批已建条目并大声报错：母版已入库、可重试——import
    幂等，归档重跑是全新条目）。归档步骤在 archive.py（工单 C3：master 不
    import 参考库族，防 import 链）。llm_factory / reference_library_dir 只在
    报告含归档动作时按需取用（无归档的确认不要求 AI 配置，与现状一致）。
    """
    # 函数级延迟导入：归档辅助要 import 参考库族与赛题库文法（master 不 import
    # 它们），模块级导入会经 archive 拉入参考库族、破坏 import 链收敛（工单 C3；
    # 环已拆——对比模型已迁 report，不存在 master ↔ archive 模块级环）——只在
    # 归档确认时加载
    from .archive import prepare_archive, write_archive_entries

    projects = tuple(scan_project(project_dir) for project_dir in project_dirs)
    comparison = compare_projects(projects)
    if not isinstance(payload, dict):
        raise MasterError("提炼报告必须是 JSON 对象")
    platform = _require_str(payload, "platform")
    try:
        report = DistillationReport.from_dict(
            payload,
            # 预览是确定性素材（落盘永远写 main_c_template(platform) 与
            # _config_preview(...)）：客户端回传值不可信，按平台重推导；平台
            # 非法由模板加载大声失败
            main_c_preview=main_c_template(platform),
            uvprojx_preview="",
        )
    except ReportError as exc:
        raise MasterError(str(exc)) from exc
    # .uvprojx 预览按确认后的最终决策集重推导（stm32 渲染全文 / mspm0 空串）
    report = replace(
        report,
        uvprojx_preview=_config_preview(
            report.platform, (*report.keep, *report.merge), comparison
        ),
    )
    staging = Path(tempfile.mkdtemp(prefix="master-staging-"))
    try:
        preview = apply_distillation(report, comparison, staging / "preview")
        if report.archive:
            # LLM 调用在暂存之后、任何真写盘之前：失败只清暂存，什么都不碰
            summaries = prepare_archive(
                report, comparison, llm_factory, reference_library_dir
            )
        else:
            summaries = {}
        meta = import_master(
            masters_dir, report.platform, preview, sources=report.projects
        )
        if report.archive:
            # prepare_archive 已拒绝 None（归档需要参考库目录）；此处为类型
            # 窄化断言，运行期恒真
            assert reference_library_dir is not None
            write_archive_entries(
                report, comparison, reference_library_dir, summaries
            )
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return meta


# ---------------------------------------------------------------------------
# 校验与辅助
# ---------------------------------------------------------------------------


def _config_suffixes_text() -> str:
    """全平台工程配置文件后缀，顿号 + "与" 连接（报错文案从识别表推导，工单 03）。"""
    suffixes = [
        suffix
        for platform in KNOWN_PLATFORMS
        for suffix in PLATFORM_CONFIG_FILE_SUFFIXES[platform]
    ]
    if len(suffixes) == 1:
        return suffixes[0]
    return "、".join(suffixes[:-1]) + " 与 " + suffixes[-1]


def _detect_platform(project_dir: Path) -> str:
    """平台由工程配置文件判定：遍历 KNOWN_PLATFORMS ×
    PLATFORM_CONFIG_FILE_SUFFIXES（识别知识单源 = platforms.py，工单 04）。
    有 .uvprojx 为 stm32，有 .cproject/.project 为 mspm0；两者都有或都没有
    抛 MasterError（文案全后缀列出，由表推导）。工程文件在任意层级可识别
    （正点原子风格在 USER/ 子目录）。"""
    found = [
        platform
        for platform in KNOWN_PLATFORMS
        if any(
            _find_config_files(project_dir, f"*{suffix}")
            for suffix in PLATFORM_CONFIG_FILE_SUFFIXES[platform]
        )
    ]
    if len(found) > 1:
        raise MasterError(f"工程同时含 {_config_suffixes_text()}，无法判定平台")
    if found:
        return found[0]
    raise MasterError(f"工程里没有 {_config_suffixes_text()}，无法判定平台")


def _config_summary(project_dir: Path, platform: str) -> tuple[str, ...]:
    """平台配置摘要行：设备 / include path / 编译宏（配置对比的 AI 素材）。

    经蒸馏适配器按平台取（格式知识归 keil.py / ccs.py，工单 04）；软失败
    语义（多配置文件等转成一行摘要）在适配器内，扫描不因单个工程带病中断。
    """
    return get_distill_adapter(platform).config_summary(project_dir)
