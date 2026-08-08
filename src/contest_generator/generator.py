"""工程生成器核心 —— 生成流程的接缝（generate_project）与落盘步骤（generate）。

generate_project 是完整流程入口：选模块（加载库 + 展开依赖 + 平台警告）→
定位母版 → generate 落盘 → 只读摘要，webapp 与测试都经它驱动；generate 是
内部落盘步骤（母版文件复制、模块文件按平台版本复制到 modules/<slug>/、
main.c 落位（落位前静态自检：引用的函数必须在所选模块头文件中）、平台
修改器经注册表委托）。

所有校验失败都在创建输出目录之前发生，绝不产出残缺工程。
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .library import list_modules
from .llm import LLM, LLMError, ReferenceSuggestion, build_manifest_summaries
from .manifest import ModuleManifest
from .master import master_project_dir
from .patchers import PatcherRegistry, default_registry
from .reference_library import ReferenceEntry, ReferenceError
from .selection import (
    associated_references,
    read_reference_fulltext,
    reference_suggestions,
    resolve_selection,
)
from .skeleton import verify_main_c
from .topic_library import (
    TopicEntry,
    TopicError,
    related_module_slugs,
    resolve_number,
)

MODULES_SUBDIR = "modules"


class GeneratorError(Exception):
    """生成失败，message 中说明具体问题。"""


class MasterNotFoundError(GeneratorError):
    """母版工程目录不存在。"""


class OutputDirNotEmptyError(GeneratorError):
    """输出目录已存在且非空，拒绝覆盖。"""


class MissingModuleFilesError(GeneratorError):
    """所选模块缺少目标平台版本的文件（或根本没有该平台的版本条目）。"""


class UndefinedCallsError(GeneratorError):
    """main.c 调用了所选模块头文件中不存在的函数，拒绝产出残缺工程。"""


@dataclass(frozen=True)
class TopicContext:
    """历史赛题入口的完整生成素材（唯一装配点）。

    一次解析产出：题面全文 + 关联素材（完整条目）+ 该题专用模块 + 两级注入
    所需的一切（清单段 suggestions、第二级全文 reader、模块库摘要行）——
    webapp 只调用不装配协议细节，推荐 / 骨架 / 生成三阶段共享同一解析。
    长 PDF 题面全文只在选了该赛题时进上下文——problem_text 即题面全文；关联
    素材 = 锚定该题或候选模块套件的参考文件（候选 = 模块库全量，套件 = 模块
    kit 词表——该题没有专用模块时套件锚定的参考文件仍能进清单）；该题专用
    模块复用简介"XX 题专用"标注自动发现，不新造链接字段。模块库扫描在
    装配点内只发生一次（候选清单同时供关联模块筛、套件词表、摘要行三用）。
    """

    key: str
    problem_text: str
    references: tuple[ReferenceEntry, ...]  # 关联参考文件（完整条目）
    related_modules: tuple[str, ...]  # 该题专用模块 slug（自动并入最终模块集）
    manifest_summaries: tuple[str, ...]  # 模块库摘要行（与 references 同一次扫库产出）
    suggestions: tuple[ReferenceSuggestion, ...]  # 两级注入第一级（清单段）
    read_fulltext: Callable[[str], str]  # 两级注入第二级（按清单段条目 id 回读全文）


def resolve_topic_context(
    *,
    llm: LLM | None,
    topic_key: str,
    problem_text: str,
    module_library_dir: Path,
    topic_library_dir: Path,
    reference_library_dir: Path,
) -> TopicContext | None:
    """生成入口素材装配：显式编号或粘贴题面中的编号（AI 理解）→ 完整赛题上下文。

    两条入口：topic_key 显式给出（查无此条大声报错——不猜测编造）；否则从
    粘贴的 problem_text 里 AI 提取编号（llm.topic_extract_number，自动识别
    尽力而为——提取失败 / 库中没有该题就按纯粘贴题面流程走，不阻断生成入口，
    与显式编号的查无此条大声报错相对——刻意取舍，工单 Comments 留痕）。
    返回 None = 没有可识别的历史赛题。
    """
    if topic_key:
        entry = _resolve_topic_entry(topic_library_dir, topic_key)
    elif llm is not None:
        try:
            extracted = llm.topic_extract_number(problem_text)
        except LLMError:
            return None  # 自动识别尽力而为：AI 提取失败不阻断粘贴题面流程
        if not extracted:
            return None
        try:
            entry = _resolve_topic_entry(topic_library_dir, extracted)
        except TopicError:
            return None  # 库中没有该题：自动识别查无此条静默降级（不猜测编造）
    else:
        return None

    candidates = list_modules(module_library_dir) if module_library_dir.is_dir() else []
    references = associated_references(
        reference_library_dir, topic_key=entry.key, manifests=candidates
    )
    return TopicContext(
        key=entry.key,
        problem_text=entry.problem_text,
        references=references,
        related_modules=related_module_slugs(candidates, entry.key),
        manifest_summaries=tuple(build_manifest_summaries(candidates)),
        suggestions=reference_suggestions(references),
        read_fulltext=_make_fulltext_reader(reference_library_dir, references),
    )


def _resolve_topic_entry(topic_library_dir: Path, topic_key: str) -> TopicEntry:
    """历史赛题条目（唯一解析点：查库，不猜测编造；关联模块由调用方用
    候选清单筛——装配上下文与生成流程各扫一次库，不互相复制解析逻辑）。"""
    return resolve_number(topic_library_dir, topic_key)


def _make_fulltext_reader(
    reference_root: Path, references: Sequence[ReferenceEntry]
) -> Callable[[str], str]:
    """两级注入第二级回读器：清单段条目 id → 全文（键映射与读取在同一处，
    装配进上下文的唯一实现——webapp 不再自建 reader 闭包）。"""

    def reader(entry_id: str) -> str:
        for entry in references:
            if entry.id == entry_id:
                return read_reference_fulltext(reference_root, entry)
        raise ReferenceError(f"参考文件条目不存在：{entry_id!r}")

    return reader


def prepend_related_modules(
    related: Sequence[str], slugs: Sequence[str]
) -> tuple[str, ...]:
    """该题专用模块并入用户选择：专用模块前置，去重保序（唯一形状，生成与
    骨架两处调用同款——改一处忘另一处即分叉）。"""
    return tuple(dict.fromkeys([*related, *slugs]))


@dataclass(frozen=True)
class GenerationSummary:
    """生成结果摘要（界面呈现用）：工程结构 / include path / 各模块文件清单。"""

    output_dir: Path
    structure: tuple[str, ...]  # 相对工程目录的文件路径（POSIX），排序
    include_dirs: tuple[str, ...]  # 已去重，按首次出现顺序
    modules: tuple[tuple[str, tuple[str, ...]], ...]  # (slug, 该平台文件列表)


def describe_generation(
    output_dir: Path, manifests: Sequence[ModuleManifest], platform: str
) -> GenerationSummary:
    """生成完成后的只读摘要：结构清单直接读输出目录；include 目录按目标平台
    条目推导，与 _copy_module_files 共享 MODULES_SUBDIR——子目录改名后界面
    与工程不会漂移。模块根目录下的文件（parent 为空）对应 modules/<slug>/。
    """
    structure = tuple(
        p.relative_to(output_dir).as_posix()
        for p in sorted(output_dir.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(output_dir).parts
    )
    include_dirs: list[str] = []
    modules: list[tuple[str, tuple[str, ...]]] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        files = tuple(entry.files) if entry is not None else ()
        modules.append((manifest.slug, files))
        for rel in files:
            parent = Path(rel).parent
            parts = (
                [MODULES_SUBDIR, manifest.slug, *parent.parts]
                if parent != Path(".")
                else [MODULES_SUBDIR, manifest.slug]
            )
            include_dir = Path(*parts).as_posix()
            if include_dir not in include_dirs:
                include_dirs.append(include_dir)
    return GenerationSummary(
        output_dir=output_dir,
        structure=structure,
        include_dirs=tuple(include_dirs),
        modules=tuple(modules),
    )


def generate_project(
    *,
    platform: str,
    slugs: Sequence[str],
    main_c_content: str,
    output_dir: Path,
    module_library_dir: Path,
    masters_dir: Path,
    registry: PatcherRegistry | None = None,
    topic_key: str = "",
    topic_library_dir: Path | None = None,
) -> GenerationSummary:
    """完整生成流程：选模块 → 定位母版 → 生成 → 摘要，一步到位的接缝。

    生成前的组合操作（加载库 + 展开依赖 + 平台警告 → 母版目录 → 复制打补丁
    → 只读摘要）只有一个入口，webapp 与流程级测试都经它驱动；母版库布局
    （masters_dir/<platform>）归母版模块所有（master_project_dir），这里只
    调用不另抄。所有校验失败都在创建输出目录之前发生。

    历史赛题入口：topic_key 给定时解析该题（题面全文与关联素材在推荐 / 骨架
    阶段经 resolve_topic_context 进上下文），该题专用模块自动并入最终模块集
    （复用"XX 题专用"标注自动发现，生成物与用户手选等价）；查无此条由
    topic_library.resolve_number 大声报错（不猜测编造）。
    """
    if topic_key:
        if topic_library_dir is None:
            raise GeneratorError("生成历史赛题工程必须给出 topic_library_dir")
        entry = _resolve_topic_entry(topic_library_dir, topic_key)
        related = related_module_slugs(
            list_modules(module_library_dir) if module_library_dir.is_dir() else [],
            entry.key,
        )
        slugs = prepend_related_modules(related, slugs)  # 该题专用模块并入（前置去重保序）
    resolved = resolve_selection(module_library_dir, platform, slugs)
    result_dir = generate(
        platform=platform,
        manifests=resolved.manifests,
        module_library_dir=module_library_dir,
        master_project_dir=master_project_dir(masters_dir, platform),
        output_dir=output_dir,
        main_c_content=main_c_content,
        registry=registry,
    )
    return describe_generation(result_dir, resolved.manifests, platform)


def generate(
    *,
    platform: str,
    manifests: Sequence[ModuleManifest],
    module_library_dir: Path,
    master_project_dir: Path,
    output_dir: Path,
    main_c_content: str,
    registry: PatcherRegistry | None = None,
) -> Path:
    """生成完整工程目录，返回输出目录路径。"""
    patcher_registry = registry or default_registry()
    patcher = patcher_registry.get(platform)  # 未知平台在这里失败

    if not master_project_dir.is_dir():
        raise MasterNotFoundError(f"母版工程目录不存在：{master_project_dir}")

    if output_dir.exists() and any(output_dir.iterdir()):
        raise OutputDirNotEmptyError(f"输出目录已存在且非空，拒绝覆盖：{output_dir}")

    _check_module_files(manifests, platform, module_library_dir)
    _check_main_calls(main_c_content, manifests, platform, module_library_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(
            master_project_dir,
            output_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        (output_dir / "main.c").unlink(missing_ok=True)  # 旧的 main 由新骨架替换

        copied_files, include_dirs = _copy_module_files(
            manifests, platform, module_library_dir, output_dir
        )

        (output_dir / "main.c").write_text(main_c_content, encoding="utf-8")

        patcher.patch(output_dir, copied_files, include_dirs)
    except Exception:
        # 复制中途失败不要留下半成品
        shutil.rmtree(output_dir, ignore_errors=True)
        raise

    return output_dir


def _check_module_files(
    manifests: Sequence[ModuleManifest], platform: str, library_dir: Path
) -> None:
    missing: list[str] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            missing.append(f"模块 {manifest.slug} 没有平台 {platform} 的版本条目")
            continue
        for rel in entry.files:
            if not (library_dir / manifest.slug / rel).is_file():
                missing.append(f"模块 {manifest.slug} 缺文件：{rel}")
    if missing:
        raise MissingModuleFilesError(
            "所选模块文件不齐全，拒绝生成残缺工程：\n- " + "\n- ".join(missing)
        )


def _check_main_calls(
    main_c_content: str,
    manifests: Sequence[ModuleManifest],
    platform: str,
    library_dir: Path,
) -> None:
    """静态自检兜底：main.c 引用的每个函数必须存在于所选模块头文件。

    自检实现归 skeleton.verify_main_c（与骨架阶段共用同一份接口块）——
    "不存在的调用"只有一个实现、两种出口：骨架阶段改写为注释占位，走到
    这里的 main.c 若仍含不存在的调用（用户手改等），明确报错，拒绝产出
    无法编译的工程。
    """
    undefined = verify_main_c(main_c_content, manifests, platform, library_dir)
    if undefined:
        raise UndefinedCallsError(
            "main.c 调用了所选模块头文件中不存在的函数："
            + "、".join(undefined)
            + " —— 请改用真实接口，或让骨架阶段自检改写为注释占位"
        )


def _copy_module_files(
    manifests: Sequence[ModuleManifest],
    platform: str,
    library_dir: Path,
    output_dir: Path,
) -> tuple[list[Path], list[Path]]:
    """复制模块文件到 modules/<slug>/ 下，返回（相对工程目录的文件列表、include 目录列表）。"""
    copied_files: list[Path] = []
    include_dirs: list[Path] = []
    seen_dirs: set[Path] = set()

    for manifest in manifests:
        entry = manifest.platforms[platform]
        for rel in entry.files:
            rel_path = Path(rel)
            src = library_dir / manifest.slug / rel_path
            dst = output_dir / MODULES_SUBDIR / manifest.slug / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

            rel_dst = dst.relative_to(output_dir)
            copied_files.append(rel_dst)
            parent = rel_dst.parent
            if parent not in seen_dirs:
                seen_dirs.add(parent)
                include_dirs.append(parent)

    return copied_files, include_dirs
