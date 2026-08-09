"""工程生成器核心 —— 生成流程的接缝（generate_project）与落盘步骤（generate）。

generate_project 是完整流程入口：选模块（加载库 + 展开依赖 + 平台警告）→
定位母版 → generate 落盘 → 只读摘要，webapp 与测试都经它驱动；generate 是
内部落盘步骤（母版文件复制、模块文件按平台版本复制到 modules/<slug>/、
main.c 落位（落位前静态自检：引用的函数必须在所选模块头文件中、main.c 与
模块源码的每个引号 include 必须在最终工程里能解析）、平台修改器经注册表委托）。

所有校验失败都在创建输出目录之前发生，绝不产出残缺工程。
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Sequence

from .keil import include_search_dirs
from .library import list_modules
from .llm import LLMError, build_manifest_summaries
from .manifest import ManifestSummary, ModuleManifest
from .master import master_project_dir
from .patchers import PatcherRegistry, default_registry
from .reference_library import ReferenceEntry, ReferenceError
from .selection import (
    ReferenceSuggestion,
    associated_references,
    read_reference_fulltext,
    reference_suggestions,
    resolve_selection,
)
from .clex import (
    extract_quoted_includes,
    fence_line_indices,
    strip_comments,
    top_level_defines,
)
from .skeleton import format_interface_blocks, verify_main_c_interfaces
from .topic_library import (
    TopicEntry,
    TopicError,
    related_module_slugs,
    resolve_number,
)
from .treewalk import iter_project_files

if TYPE_CHECKING:
    # 仅类型注解用（skeleton.py 同规：生成流程不该在运行时拉进 LLM 栈）
    from .llm import LLM

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


class FencedMainCError(GeneratorError):
    """main.c 含 Markdown 代码围栏（LLM 围栏输出未剥离），拒绝产出残缺工程。"""


class UnresolvedIncludeError(GeneratorError):
    """main.c 或模块源码引用了最终工程里不存在的头文件，拒绝产出残缺工程。"""


class ModuleSelfIncludeError(GeneratorError):
    """模块 .c 未 include 本模块自己的头文件，拒绝产出残缺工程。"""


class MacroRedefinitionError(GeneratorError):
    """模块配置 / main.c 重定义了母版库接口宏（同名不同值），拒绝产出带
    编译警告的工程（Keil #47-D incompatible redefinition 判例：config.h
    的 LED_GPIO 撞 ml_led.h）。"""


# Keil 在工程外也能解析的头：ARMCC 标准库（引号形式同样走库搜索）与器件包
# （stm32f10x_conf.h 由 STM32F1xx DFP 提供，工程树里没有）。缺了会误报。
_EXTERNAL_HEADERS = frozenset(
    {
        "math.h", "stdio.h", "stdlib.h", "string.h", "stdint.h", "stdbool.h",
        "stddef.h", "limits.h", "float.h", "assert.h", "errno.h", "ctype.h",
        "time.h", "inttypes.h", "stdarg.h", "setjmp.h", "signal.h", "locale.h",
        "wchar.h", "wctype.h", "complex.h", "fenv.h", "tgmath.h", "iso646.h",
        "stdatomic.h", "threads.h", "uchar.h", "stm32f10x_conf.h",
    }
)


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
    manifest_summaries: tuple[ManifestSummary, ...]  # 模块库摘要对象（与 references 同一次扫库产出）
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
    候选清单筛——装配点只此一处，生成接缝消费装配结果不再扫库）。"""
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
    output_dir: Path,
    manifests: Sequence[ModuleManifest],
    platform: str,
    include_dirs: Sequence[str],
) -> GenerationSummary:
    """生成完成后的只读摘要：结构清单直接读输出目录；include 目录消费
    _copy_module_files 的实际复制结果（同一来源，不再从 manifest 二次推导
    ——同一流程两套推导改一处忘另一处即漂移）。模块根目录下的文件（parent
    为空）对应 modules/<slug>/。
    """
    structure = tuple(
        p.relative_to(output_dir).as_posix()
        for p in iter_project_files(output_dir)
    )
    modules: list[tuple[str, tuple[str, ...]]] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        files = tuple(entry.files) if entry is not None else ()
        modules.append((manifest.slug, files))
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
    related_modules: Sequence[str] = (),
) -> GenerationSummary:
    """完整生成流程：选模块 → 定位母版 → 生成 → 摘要，一步到位的接缝。

    生成前的组合操作（加载库 + 展开依赖 + 平台警告 → 母版目录 → 复制打补丁
    → 只读摘要）只有一个入口，webapp 与流程级测试都经它驱动；母版库布局
    （masters_dir/<platform>）归母版模块所有（master_project_dir），这里只
    调用不另抄。所有校验失败都在创建输出目录之前发生。

    历史赛题入口：related_modules = 该题专用模块 slug（推荐 / 骨架阶段已由
    resolve_topic_context 装配进上下文，webapp 把装配结果透传过来——本接缝
    只消费不重扫库、不重解析条目；生成物与用户手选等价）。"""
    slugs = prepend_related_modules(related_modules, slugs)  # 该题专用模块并入（前置去重保序）
    resolved = resolve_selection(module_library_dir, platform, slugs)
    result_dir, include_dirs = generate(
        platform=platform,
        manifests=resolved.manifests,
        module_library_dir=module_library_dir,
        master_project_dir=master_project_dir(masters_dir, platform),
        output_dir=output_dir,
        main_c_content=main_c_content,
        registry=registry,
    )
    return describe_generation(result_dir, resolved.manifests, platform, include_dirs)


@dataclass(frozen=True)
class ModuleFile:
    """模块文件条目：rel 路径 / 类别（c/h/other）/ 文本 / 所在目录。

    文本与目录在语料构建时一次读好——门禁只吃语料，不再碰盘。
    """

    rel: str
    kind: str  # "c" / "h" / "other"
    text: str
    own_dir: Path  # library_dir/<slug>/<rel 的父目录>（include 解析的 own_dir）


@dataclass(frozen=True)
class ModuleCorpus:
    """生成校验的内存语料：一次读盘，五道门共吃。

    modules 顺序与 manifests 一致（含平台条目缺失的模块，files 为空——
    缺失清单在 missing 里）；master_headers = 母版树全部 *.h（相对路径,
    文本，一次 rglob + 读盘）；master_search_dirs = 母版 IncludePath
    （keil 语义，构建时算好）；main_c 直接进语料。测试可内存构造直喂门禁。
    """

    platform: str
    modules: tuple[tuple[str, tuple[ModuleFile, ...]], ...]
    missing_platforms: tuple[str, ...]  # 无该平台版本条目的 slug
    missing_files: tuple[tuple[str, str], ...]  # (slug, rel) 声明了但读不到
    master_headers: tuple[tuple[str, str], ...]
    master_search_dirs: tuple[Path, ...]
    master_project_dir: Path  # main.c 的 own_dir（最终工程根 = 母版根）
    main_c: str


def build_module_corpus(
    manifests: Sequence[ModuleManifest],
    platform: str,
    library_dir: Path,
    master_project_dir: Path,
    main_c_content: str,
) -> ModuleCorpus:
    """一次读盘构建校验语料：模块文件（存在性 + 文本）+ 母版头 + 搜索目录。

    文件缺失不 raise——存在性由 _check_module_files 门报告（missing 清单
    记录，门禁职责不变）；母版 rglob 与 IncludePath 也在这里一次做完，
    门禁不再扫盘。
    """
    modules: list[tuple[str, tuple[ModuleFile, ...]]] = []
    missing_platforms: list[str] = []
    missing_files: list[tuple[str, str]] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            missing_platforms.append(manifest.slug)
            modules.append((manifest.slug, ()))
            continue
        files: list[ModuleFile] = []
        for rel in entry.files:
            path = library_dir / manifest.slug / rel
            if not path.is_file():
                missing_files.append((manifest.slug, rel))
                continue
            kind = (
                "c"
                if rel.lower().endswith(".c")
                else "h"
                if rel.lower().endswith(".h")
                else "other"
            )
            files.append(
                ModuleFile(
                    rel=rel,
                    kind=kind,
                    text=path.read_text(encoding="utf-8", errors="replace"),
                    own_dir=path.parent,
                )
            )
        modules.append((manifest.slug, tuple(files)))

    master_headers: list[tuple[str, str]] = []
    for path in iter_project_files(master_project_dir, pattern="*.h"):
        try:
            master_headers.append(
                (
                    path.relative_to(master_project_dir).as_posix(),
                    path.read_text(encoding="utf-8", errors="replace"),
                )
            )
        except OSError:
            continue

    return ModuleCorpus(
        platform=platform,
        modules=tuple(modules),
        missing_platforms=tuple(missing_platforms),
        missing_files=tuple(missing_files),
        master_headers=tuple(master_headers),
        master_search_dirs=tuple(include_search_dirs(master_project_dir)),
        master_project_dir=master_project_dir,
        main_c=main_c_content,
    )


def generate(
    *,
    platform: str,
    manifests: Sequence[ModuleManifest],
    module_library_dir: Path,
    master_project_dir: Path,
    output_dir: Path,
    main_c_content: str,
    registry: PatcherRegistry | None = None,
) -> tuple[Path, tuple[str, ...]]:
    """生成完整工程目录，返回（输出目录, include 目录清单 POSIX 相对路径）。

    include 目录 = _copy_module_files 实际复制出的目录（摘要消费同一来源，
    不再二次推导——见 describe_generation）。"""
    patcher_registry = registry or default_registry()
    patcher = patcher_registry.get(platform)  # 未知平台在这里失败

    if not master_project_dir.is_dir():
        raise MasterNotFoundError(f"母版工程目录不存在：{master_project_dir}")

    if output_dir.exists() and any(output_dir.iterdir()):
        raise OutputDirNotEmptyError(f"输出目录已存在且非空，拒绝覆盖：{output_dir}")

    corpus = build_module_corpus(
        manifests, platform, module_library_dir, master_project_dir, main_c_content
    )
    _check_module_files(corpus)
    _check_main_calls(corpus)
    _check_module_self_include(corpus)
    _check_unresolved_includes(corpus)
    _check_macro_conflicts(corpus)

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

        if not main_c_content.endswith("\n"):
            main_c_content += "\n"  # 尾部换行幂等兜底（LLM 输出常漏，Keil 报 #1-D）
        (output_dir / "main.c").write_text(main_c_content, encoding="utf-8")

        patcher.patch(output_dir, copied_files, include_dirs)
    except Exception:
        # 复制中途失败不要留下半成品
        shutil.rmtree(output_dir, ignore_errors=True)
        raise

    return output_dir, tuple(p.as_posix() for p in include_dirs)


def _check_module_files(corpus: ModuleCorpus) -> None:
    missing: list[str] = []
    for slug in corpus.missing_platforms:
        missing.append(f"模块 {slug} 没有平台 {corpus.platform} 的版本条目")
    for slug, rel in corpus.missing_files:
        missing.append(f"模块 {slug} 缺文件：{rel}")
    if missing:
        raise MissingModuleFilesError(
            "所选模块文件不齐全，拒绝生成残缺工程：\n- " + "\n- ".join(missing)
        )


def _check_main_calls(corpus: ModuleCorpus) -> None:
    """静态自检兜底：main.c 引用的每个函数必须存在于所选模块头文件。

    自检实现归 skeleton.verify_main_c_interfaces（与骨架阶段共用同一份
    接口块格式化与提取逻辑）——"不存在的调用"只有一个实现、两种出口：
    骨架阶段改写为注释占位，走到这里的 main.c 若仍含不存在的调用（用户
    手改等），明确报错，拒绝产出无法编译的工程。main.c 含 Markdown 代码
    围栏同样明确报错（骨架阶段已剥离，走到这里说明输入绕过骨架阶段或
    手改带入）。
    """
    for i, line in fence_line_indices(corpus.main_c):
        raise FencedMainCError(
            f"main.c 第 {i} 行是 Markdown 代码围栏（{line}），不是 C 代码"
            " —— 骨架阶段会剥离 LLM 围栏输出，请直接用纯 C 代码"
        )
    headers: list[tuple[str, str, str]] = [
        (slug, f.rel, f.text)
        for slug, files in corpus.modules
        for f in files
        if f.kind == "h"
    ]
    interfaces = format_interface_blocks(headers)
    undefined = verify_main_c_interfaces(corpus.main_c, interfaces)
    if undefined:
        raise UndefinedCallsError(
            "main.c 调用了所选模块头文件中不存在的函数："
            + "、".join(undefined)
            + " —— 请改用真实接口，或让骨架阶段自检改写为注释占位"
        )


def _check_unresolved_includes(corpus: ModuleCorpus) -> None:
    """生成前静态校验：main.c 与模块源码的每个引号 include 都必须在最终工程里可解析。

    Keil 语义：#include "x.h" 先找当前文件所在目录，再按 IncludePath 顺序找
    （模块代码目录自动追加 + 母版自带）；工程内找不到且不是标准库 / 器件包
    头 → 拒绝生成（判例：库模块 pid.c 引用了从未入库的 digit_uart.h，Keil
    报 cannot open source input file，真机编译失败）。检查在创建输出目录
    之前发生，不产出残缺工程。搜索目录在语料构建时算好（母版 IncludePath +
    各模块代码目录），门禁只吃语料不碰盘。
    """
    search_dirs: list[Path] = list(corpus.master_search_dirs)
    seen: set[str] = {str(d).lower() for d in search_dirs}
    for _, files in corpus.modules:
        for f in files:
            key = str(f.own_dir).lower()
            if key not in seen:
                seen.add(key)
                search_dirs.append(f.own_dir)

    checks: list[tuple[str, Path, str]] = [
        ("main.c", corpus.master_project_dir, corpus.main_c)
    ]
    for slug, files in corpus.modules:
        for f in files:
            if f.kind not in ("c", "h"):
                continue
            checks.append((f"模块 {slug} 的 {f.rel}", f.own_dir, f.text))

    problems: list[str] = []
    for label, own_dir, code in checks:
        stripped = strip_comments(code, keep_preprocessor=True)
        for header in extract_quoted_includes(stripped):
            if any((d / header).is_file() for d in (own_dir, *search_dirs)):
                continue
            if header.lower() in _EXTERNAL_HEADERS:
                continue
            problems.append(f"{label} 引用了最终工程中不存在的头文件 {header}")
    if problems:
        raise UnresolvedIncludeError(
            "生成工程无法编译（include 解析失败）：\n- " + "\n- ".join(problems)
            + "\n —— 请将该头文件所属模块一并选中，或补录模块库条目"
        )


def _check_module_self_include(corpus: ModuleCorpus) -> None:
    """生成前静态校验：模块 .c 必须 include 本模块自己的至少一个头文件。

    Keil 语义：模块 .c 不 include 自己的 .h 时，符号声明只存在于原始工程的
    自定义 headfile.h 聚合里——生成工程用母版 headfile.h 替换后，类型 / 变量 /
    函数全部未声明（pid_t / yaw_gyro / D1..D8 / g_systick 判例，真机编译
    35 错）。include 解析校验只查"引用的头存在"，不查"该引用的头在不在"，
    此规则补上：引用解析 + 自包含两条件都过，生成工程才有编译基础。
    """
    problems: list[str] = []
    for slug, files in corpus.modules:
        own_headers = [Path(f.rel).name for f in files if f.kind == "h"]
        if not own_headers:
            continue  # 纯 .c 模块（无头文件可自含）跳过
        for f in files:
            if f.kind != "c":
                continue
            stripped = strip_comments(f.text, keep_preprocessor=True)
            included = set(extract_quoted_includes(stripped))
            if not (set(own_headers) & included):
                problems.append(
                    f"模块 {slug} 的 {f.rel} 没有 include 本模块自己的头"
                    f"（{', '.join(sorted(own_headers))}）"
                )
    if problems:
        raise ModuleSelfIncludeError(
            "生成工程无法编译（模块未自包含）：\n- " + "\n- ".join(problems)
            + "\n —— 请在该 .c 顶部补上本模块头文件的 include"
            "（生成工程用母版 headfile.h，原始工程的聚合头不会跟进来）"
        )


def _check_macro_conflicts(corpus: ModuleCorpus) -> None:
    """生成前静态校验：模块头 / main.c 不得重定义母版库接口宏（同名不同值）。

    Keil 语义：#define 同名不同值 = #47-D incompatible redefinition 警告
    （判例：config.h 的 LED_GPIO=GPIO_C 撞母版 ml_led.h 的 LED_GPIO=GPIO_A，
    真机编译 4 处 warning）。库接口宏是母版命名空间，模块配置想表达不同
    引脚必须换自定义宏名——门禁在创建输出目录之前拒绝生成，不留 warning
    工程。母版头文本在语料构建时一次 rglob + 读盘，门禁只吃语料。
    """
    master_defines: dict[str, tuple[str, int, str]] = {}
    for rel, text in corpus.master_headers:
        for name, (value, line) in top_level_defines(text).items():
            if name not in master_defines:
                master_defines[name] = (value, line, rel)

    problems: list[str] = []
    sources: list[tuple[str, str | None, str]] = [("main.c", None, corpus.main_c)]
    for slug, files in corpus.modules:
        for f in files:
            if f.kind != "h":
                continue
            sources.append((f"模块 {slug} 的 {f.rel}", f.rel, f.text))

    for label, source_rel, text in sources:
        for name, (value, line) in top_level_defines(text).items():
            master = master_defines.get(name)
            if master is not None and master[0] != value:
                problems.append(
                    f"{label} 第 {line} 行重定义了母版接口宏 {name}"
                    f"（母版 {master[2]}:{master[1]} 定义为 {master[0]}，"
                    f"此处定义为 {value}）"
                    " —— 库接口宏不可覆盖，请改用自定义宏名（如 LED_PORT）"
                )
    if problems:
        raise MacroRedefinitionError(
            "生成工程会带编译警告（宏重定义，Keil #47-D）：\n- " + "\n- ".join(problems)
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
