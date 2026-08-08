"""工程生成器核心 —— 生成流程的接缝（generate_project）与落盘步骤（generate）。

generate_project 是完整流程入口：选模块（加载库 + 展开依赖 + 平台警告）→
定位母版 → generate 落盘 → 只读摘要，webapp 与测试都经它驱动；generate 是
内部落盘步骤（母版文件复制、模块文件按平台版本复制到 modules/<slug>/、
main.c 落位（落位前静态自检：引用的函数必须在所选模块头文件中、main.c 与
模块源码的每个引号 include 必须在最终工程里能解析）、平台修改器经注册表委托）。

所有校验失败都在创建输出目录之前发生，绝不产出残缺工程。
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .keil import include_search_dirs
from .library import list_modules
from .llm import LLM, LLMError, build_manifest_summaries
from .manifest import ModuleManifest
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
from .skeleton import _strip_comments_keep_preprocessor, verify_main_c
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


# Markdown 代码围栏行（与 skeleton.strip_code_fences 同一形态）：main.c 手改
# 或旧流程产物若带围栏，Keil 报 unrecognized token（判例见 strip_code_fences）
_FENCE_LINE_RE = re.compile(r"^\s*(`{3,}|~{3,})[a-zA-Z0-9_-]*\s*$")

# 引号 include 提取（注释/字符串剔除后匹配，见 _check_unresolved_includes）
_INCLUDE_QUOTED_RE = re.compile(r'#\s*include\s*"([^"]+)"')

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
    _check_module_self_include(manifests, platform, module_library_dir)
    _check_unresolved_includes(
        main_c_content, manifests, platform, module_library_dir, master_project_dir
    )
    _check_macro_conflicts(
        main_c_content, manifests, platform, module_library_dir, master_project_dir
    )

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
    无法编译的工程。main.c 含 Markdown 代码围栏同样明确报错（骨架阶段已
    剥离，走到这里说明输入绕过骨架阶段或手改带入）。
    """
    for i, line in enumerate(main_c_content.splitlines(), 1):
        if _FENCE_LINE_RE.match(line):
            raise FencedMainCError(
                f"main.c 第 {i} 行是 Markdown 代码围栏（{line.strip()}），不是 C 代码"
                " —— 骨架阶段会剥离 LLM 围栏输出，请直接用纯 C 代码"
            )
    undefined = verify_main_c(main_c_content, manifests, platform, library_dir)
    if undefined:
        raise UndefinedCallsError(
            "main.c 调用了所选模块头文件中不存在的函数："
            + "、".join(undefined)
            + " —— 请改用真实接口，或让骨架阶段自检改写为注释占位"
        )


def _check_unresolved_includes(
    main_c_content: str,
    manifests: Sequence[ModuleManifest],
    platform: str,
    library_dir: Path,
    master_project_dir: Path,
) -> None:
    """生成前静态校验：main.c 与模块源码的每个引号 include 都必须在最终工程里可解析。

    Keil 语义：#include "x.h" 先找当前文件所在目录，再按 IncludePath 顺序找
    （模块代码目录自动追加 + 母版自带）；工程内找不到且不是标准库 / 器件包
    头 → 拒绝生成（判例：库模块 pid.c 引用了从未入库的 digit_uart.h，Keil
    报 cannot open source input file，真机编译失败）。检查在创建输出目录
    之前发生，不产出残缺工程。
    """
    # 搜索目录 = 母版 IncludePath + 各模块代码目录（_copy_module_files 会把
    # 这些目录追加进 uvprojx IncludePath，与 Keil 实际搜索范围一致）
    search_dirs: list[Path] = list(include_search_dirs(master_project_dir))
    seen: set[str] = {str(d).lower() for d in search_dirs}
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for rel in entry.files:
            parent = (library_dir / manifest.slug / Path(rel)).parent.resolve()
            key = str(parent).lower()
            if key not in seen:
                seen.add(key)
                search_dirs.append(parent)

    checks: list[tuple[str, Path, str]] = [(f"main.c", master_project_dir, main_c_content)]
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for rel in entry.files:
            if not rel.lower().endswith((".c", ".h")):
                continue
            path = library_dir / manifest.slug / rel
            if not path.is_file():  # 文件缺失由 _check_module_files 兜底
                continue
            label = f"模块 {manifest.slug} 的 {rel}"
            checks.append((label, path.parent, path.read_text(encoding="utf-8", errors="replace")))

    problems: list[str] = []
    for label, own_dir, code in checks:
        stripped = _strip_comments_keep_preprocessor(code)
        for m in _INCLUDE_QUOTED_RE.finditer(stripped):
            header = m.group(1)
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


def _check_module_self_include(
    manifests: Sequence[ModuleManifest], platform: str, library_dir: Path
) -> None:
    """生成前静态校验：模块 .c 必须 include 本模块自己的至少一个头文件。

    Keil 语义：模块 .c 不 include 自己的 .h 时，符号声明只存在于原始工程的
    自定义 headfile.h 聚合里——生成工程用母版 headfile.h 替换后，类型 / 变量 /
    函数全部未声明（pid_t / yaw_gyro / D1..D8 / g_systick 判例，真机编译
    35 错）。include 解析校验只查"引用的头存在"，不查"该引用的头在不在"，
    此规则补上：引用解析 + 自包含两条件都过，生成工程才有编译基础。
    """
    problems: list[str] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        own_headers = [Path(rel).name for rel in entry.files if rel.lower().endswith(".h")]
        if not own_headers:
            continue  # 纯 .c 模块（无头文件可自含）跳过
        for rel in entry.files:
            if not rel.lower().endswith(".c"):
                continue
            path = library_dir / manifest.slug / rel
            if not path.is_file():  # 文件缺失由 _check_module_files 兜底
                continue
            code = path.read_text(encoding="utf-8", errors="replace")
            stripped = _strip_comments_keep_preprocessor(code)
            included = set(_INCLUDE_QUOTED_RE.findall(stripped))
            if not (set(own_headers) & included):
                problems.append(
                    f"模块 {manifest.slug} 的 {rel} 没有 include 本模块自己的头"
                    f"（{', '.join(sorted(own_headers))}）"
                )
    if problems:
        raise ModuleSelfIncludeError(
            "生成工程无法编译（模块未自包含）：\n- " + "\n- ".join(problems)
            + "\n —— 请在该 .c 顶部补上本模块头文件的 include"
            "（生成工程用母版 headfile.h，原始工程的聚合头不会跟进来）"
        )


def _top_level_defines(code: str) -> dict[str, tuple[str, int]]:
    """无条件顶层 #define 清单：{宏名: (规范化值, 行号)}。

    只收不在任何 #if/#ifdef/#ifndef 块内的 #define——include guard 的定义
    在 #ifndef 块内（深度 1）天然排除；条件块里可能生效也可能不生效的宏
    跳过（宁可放过、不可误杀，编译器的 warning 兜底）。同一文件 #undef
    后再定义的不收（合法覆盖模式）。函数宏名字取到左括号前，参数表并入
    值参与文本比较。反斜杠续行在预处理行内合并。
    """
    stripped = _strip_comments_keep_preprocessor(code)
    lines = stripped.split("\n")
    defines: dict[str, tuple[str, int]] = {}
    undefed: set[str] = set()
    depth = 0
    i = 0
    while i < len(lines):
        text = lines[i].strip()
        lineno = i + 1
        if not text.startswith("#"):
            i += 1
            continue
        while text.endswith("\\") and i + 1 < len(lines):  # 续行合并
            i += 1
            text = text[:-1] + " " + lines[i].strip()
        if text.startswith("#if"):
            depth += 1
        elif text.startswith("#endif"):
            depth = max(0, depth - 1)
        elif text.startswith("#undef"):
            m = re.match(r"#\s*undef\s+([A-Za-z_]\w*)", text)
            if m:
                undefed.add(m.group(1))
        elif text.startswith("#define") and depth == 0:
            m = re.match(r"#\s*define\s+([A-Za-z_]\w*)", text)
            if m:
                name = m.group(1)
                if name not in undefed:
                    value = re.sub(r"\s+", " ", text[m.end():].strip())
                    defines[name] = (value, lineno)
        i += 1
    return defines


def _check_macro_conflicts(
    main_c_content: str,
    manifests: Sequence[ModuleManifest],
    platform: str,
    library_dir: Path,
    master_project_dir: Path,
) -> None:
    """生成前静态校验：模块头 / main.c 不得重定义母版库接口宏（同名不同值）。

    Keil 语义：#define 同名不同值 = #47-D incompatible redefinition 警告
    （判例：config.h 的 LED_GPIO=GPIO_C 撞母版 ml_led.h 的 LED_GPIO=GPIO_A，
    真机编译 4 处 warning）。库接口宏是母版命名空间，模块配置想表达不同
    引脚必须换自定义宏名——门禁在创建输出目录之前拒绝生成，不留 warning
    工程。
    """
    master_defines: dict[str, tuple[str, int, str]] = {}
    for rel in sorted(p.relative_to(master_project_dir).as_posix() for p in master_project_dir.rglob("*.h")):
        path = master_project_dir / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name, (value, line) in _top_level_defines(text).items():
            if name not in master_defines:
                master_defines[name] = (value, line, rel)

    problems: list[str] = []
    sources: list[tuple[str, str | None, Path]] = [("main.c", None, master_project_dir / "main.c")]
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for rel in entry.files:
            if not rel.lower().endswith(".h"):
                continue
            path = library_dir / manifest.slug / rel
            if not path.is_file():  # 文件缺失由 _check_module_files 兜底
                continue
            sources.append((f"模块 {manifest.slug} 的 {rel}", rel, path))

    for label, rel, path in sources:
        if rel is None:  # main.c：内容来自参数，与母版文件无关
            text = main_c_content
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
        for name, (value, line) in _top_level_defines(text).items():
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
