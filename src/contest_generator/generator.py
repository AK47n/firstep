"""工程生成器核心 —— 生成流程的接缝（generate_project）与落盘步骤（generate）。

generate_project 是完整流程入口：选模块（加载库 + 展开依赖 + 平台警告）→
定位母版 → generate 落盘 → 只读摘要，webapp 与测试都经它驱动；generate 是
内部落盘步骤（母版文件复制、模块文件按平台版本复制到 modules/<slug>/、
main.c 落位（落位前静态自检：门禁全貌在 GENERATION_GATES 表——文件齐全 /
路径不跨模块重复 / 调用可解析 / 模块自包含 / include 可解析 / 宏不冲突 /
绑定合法 / 骨架定时器不撞绑定 pwm / 骨架不内联引脚，装配唯一出处 = 表 +
run_generation_gates）、平台修改器经注册表委托）。

所有校验失败都在创建输出目录之前发生，绝不产出残缺工程。
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Mapping, Sequence

from .boards import Board, board_for_platform
from .compile_runner import CCS_NOT_FOUND_HINT, CcsTools
from .library import list_modules
from .llm import LLMError
from .makefiles import write_makefile_set
from .manifest import ManifestSummary, ModuleManifest, build_manifest_summaries
from .master_store import master_project_dir
from .patchers import (
    PatcherRegistry,
    default_registry,
    external_headers,
    include_search_dirs,
)
from .pin_bindings import PinBindingError, ResolvedBinding, resolve_bindings
from .pinwriter import apply_pin_bindings
from .platforms import PLATFORM_MSPM0, PLATFORM_STM32
from .reference_library import ReferenceEntry, ReferenceError, read_fulltext
from .selection import (
    REFERENCE_SOURCE_MANUAL,
    ReferenceSuggestion,
    associated_references,
    filter_manifests_by_platform,
    manual_reference_admission,
    reference_suggestions,
    resolve_selection,
)
from .clex import (
    extract_quoted_includes,
    fence_line_indices,
    strip_comments,
    top_level_defines,
)
from .skeleton import (
    format_interface_blocks,
    is_header_path,
    read_module_sources,
    verify_main_c_interfaces,
)
from .topic_library import (
    TopicEntry,
    TopicError,
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


class DuplicateFilePathError(GeneratorError):
    """所选模块集内跨模块同名平台文件路径（或同一模块重复声明），拒绝产出
    链接期冲突工程（UV4 L6200E multiply defined 判例）。"""


class PinLiteralInMainError(GeneratorError):
    """main.c 内联了引脚字面量（注释剥离后判定），拒绝产出换板即错的骨架。"""


class TimerConflictError(GeneratorError):
    """绑定 pwm 角色的 TIM 实例与骨架调度定时器（tim_interrupt_ms_init）冲突，
    拒绝产出编译绿运行坏的工程（工单 pin-unlock-stm32/01）。"""


class ExtiLineConflictError(GeneratorError):
    """绑定 enc/exti 角色异口同线互斥（EXTI 线号 = 脚号 mod 16，PA5/PB5 同
    线 5）——同线两个 handler 会互相清 PR 位，编译绿运行坏，生成前拦截
    （工单 pin-full-unlock/01，ADR 0012）。"""


# 工程树外由 C 标准库提供的头（引号形式同样由编译器按库路径解析；两平台
# 同名同集，平台无关，归门禁）。工具链外部头（STM32F1xx DFP 提供、CCS
# SysConfig 构建时生成）是平台事实，在 keil.py / ccs.py 各自声明、经
# patchers.external_headers 分派——本模块不持有平台工具链知识（工单 03）。
# 门禁豁免 = 本集合 | 平台外部头。
_LIBC_HEADERS = frozenset(
    {
        "math.h", "stdio.h", "stdlib.h", "string.h", "stdint.h", "stdbool.h",
        "stddef.h", "limits.h", "float.h", "assert.h", "errno.h", "ctype.h",
        "time.h", "inttypes.h", "stdarg.h", "setjmp.h", "signal.h", "locale.h",
        "wchar.h", "wctype.h", "complex.h", "fenv.h", "tgmath.h", "iso646.h",
        "stdatomic.h", "threads.h", "uchar.h",
    }
)

# 引脚字面量形态（骨架门禁 _check_no_pin_literals_in_main 用）：PAx/PBx/
# PCx/PDx… + 库级字面量 Pin_N / GPIO_<口> / Keil 旧式 GPIO_PIN_N。前缀允许
# 字母数字之外的字符（_ 也算）——EXTI_PA2 / GPIO_Pin_13 里的 PA2 / Pin_13
# 前缀是 _，\b 会漏；尾 \b 挡宏名后缀（PA12_PORT 里的 PA12 后是 _ 不算）。
# 注释剥离后判定，注释字样不误伤（历史产物注释里出现过 PA11 字样——spec
# 关键事实）。
_PIN_LITERAL_RE = re.compile(
    r"(?:^|[^A-Za-z0-9])(?:P[A-H]\d{1,2}|Pin_\d+|GPIO_[A-H]|GPIO_PIN_\d+)\b"
)

# 骨架调度定时器调用形态（门禁 _check_timer_instance_conflicts 用）：
# tim_interrupt_ms_init(TIM_3, 10, 0) / (TIM2, 1, 0)——TIM_2/TIM2 两写法
# （ml_tim 枚举名 TIM_2 与 LLM 换写 TIM2 兼容）；只吃 2/3/4（ml_tim 只注册
# 这三个，TIM1 不可用——spec 关键事实）。注释剥离后判定。
_SKELETON_TIMER_RE = re.compile(r"tim_interrupt_ms_init\s*\(\s*TIM_?([234])\b")

# 绑定 pwm 实例前段（TIM3_CH1 → 3，喂定时器冲突门禁；TIMG0_C0 等 mspm0
# 形态不命中 = 自然不拦）
_PWM_TIMER_INSTANCE_RE = re.compile(r"TIM([234])_")

# 引脚名尾号（喂 EXTI 线冲突门禁：PA5 → 5、PC13 → 13 mod 16）
_PIN_TRAILING_DIGITS_RE = re.compile(r"(\d+)$")


@dataclass(frozen=True)
class TopicContext:
    """历史赛题入口的完整生成素材（唯一装配点）。

    一次解析产出：题面全文 + 关联素材（完整条目）+ 两级注入所需的一切（清单
    段 suggestions、第二级全文 reader、模块库摘要行）——webapp 只调用不装配
    协议细节，推荐 / 骨架 / 生成三阶段共享同一解析。长 PDF 题面全文只在选
    了该赛题时进上下文——problem_text 即题面全文；关联素材 = 锚定该题或候选
    模块套件的参考文件（候选 = 模块库全量，套件 = 模块 kit 词表——套件锚定
    的参考文件不依赖任何"题专用模块"存在）。模块库扫描在装配点内只发生
    一次（候选清单同时供套件词表、摘要行两用）。
    """

    key: str
    problem_text: str
    references: tuple[ReferenceEntry, ...]  # 关联参考文件（完整条目）
    manifest_summaries: tuple[ManifestSummary, ...]  # 模块库摘要对象（与 references 同一次扫库产出）
    suggestions: tuple[ReferenceSuggestion, ...]  # 两级注入第一级（清单段）
    read_fulltext: Callable[[str], str]  # 两级注入第二级（按清单段条目 id 回读全文）
    manual_references: tuple[ReferenceEntry, ...] = ()  # 手动选参考资料（完整条目，追加准入）
    manual_fulltexts: Mapping[str, str] | None = None  # 手动选参考资料全文（id → 全文，直读）


def resolve_topic_context(
    *,
    llm: LLM | None,
    topic_key: str,
    problem_text: str,
    module_library_dir: Path,
    topic_library_dir: Path,
    reference_library_dir: Path,
    reference_ids: Sequence[str] = (),
    platform: str = "",
) -> TopicContext:
    """生成入口素材装配：显式编号或粘贴题面中的编号（AI 理解）→ 完整赛题上下文。

    永远返回完整 TopicContext，key 非空 = 识别到历史赛题。两条入口：
    topic_key 显式给出（查无此条大声报错——不猜测编造）；否则从粘贴的
    problem_text 里 AI 提取编号（llm.topic_extract_number，自动识别尽力而
    为——提取失败 / 库中没有该题按 no-topic 形走，不阻断生成入口，与显式
    编号的查无此条大声报错相对——刻意取舍，工单 Comments 留痕）。
    no-topic 形 = key="" 哨兵 + 题面原样 + 空关联 / 建议 + 全模块摘要 +
    空集回读器（见 _no_topic_context）。

    手动选参考资料（工单 01）：reference_ids = 用户显式指定的条目 id，准入 =
    锚定命中 ∪ 手动选（追加语义，锚定两级照旧）。手动条目全文直读（装配点
    一次读好，manual_fulltexts），清单段带来源标注（suggestions 混排，锚定
    与手动重合的条目只出现一次、标注手动）。幻觉 id / 重复 id 大声失败
    （manual_reference_admission）。

    platform（工单 01 平台属性）：锚定命中按生成平台过滤（any 全进）；手动
    选不过平台过滤（用户显式意图，UI 标注平台让用户自判）；模块候选同样按
    平台过滤（工单 ref-platform-filter 模块侧对偶——本平台没有的模块不进
    候选，摘要行同源同滤，需求走库外建议）。recommend 传请求体 platform；
    skeleton / generate 不注入参考文件，传缺省（空串 = 不过滤）。
    """
    manual_entries = (
        manual_reference_admission(reference_library_dir, reference_ids)
        if reference_ids
        else ()
    )
    manual_fulltexts = (
        {entry.id: read_fulltext(reference_library_dir, entry) for entry in manual_entries}
        if manual_entries
        else None
    )
    if topic_key:
        entry = _resolve_topic_entry(topic_library_dir, topic_key)
    elif llm is not None:
        try:
            extracted = llm.topic_extract_number(problem_text)
        except LLMError:
            return _no_topic_context(
                problem_text,
                module_library_dir,
                reference_library_dir,
                manual_entries,
                manual_fulltexts,
                platform,
            )  # 自动识别尽力而为：AI 提取失败不阻断粘贴题面流程
        if not extracted:
            return _no_topic_context(
                problem_text,
                module_library_dir,
                reference_library_dir,
                manual_entries,
                manual_fulltexts,
                platform,
            )
        try:
            entry = _resolve_topic_entry(topic_library_dir, extracted)
        except TopicError:
            return _no_topic_context(
                problem_text,
                module_library_dir,
                reference_library_dir,
                manual_entries,
                manual_fulltexts,
                platform,
            )  # 库中没有该题：自动识别查无此条静默降级（不猜测编造）
    else:
        return _no_topic_context(
            problem_text,
            module_library_dir,
            reference_library_dir,
            manual_entries,
            manual_fulltexts,
            platform,
        )

    candidates = list_modules(module_library_dir) if module_library_dir.is_dir() else []
    # 参考锚定用全量候选收集套件词表（kit 锚定是参考文件机制，不随模块平台
    # 过滤——条目自身有平台属性，any 条目按现有语义注入）
    references = associated_references(
        reference_library_dir,
        topic_key=entry.key,
        manifests=candidates,
        platform=platform,
    )
    # 推荐层平台过滤（工单 ref-platform-filter 模块侧对偶）：模块候选只含本
    # 平台有实现的模块——摘要行（模型可见，可勾选）同源同滤；本平台没有的
    # 模块需求走库外建议（suggestions）。空串 = 不过滤（骨架 / 生成传缺省，
    # 现状保持；未知平台在 generate 入口经 patcher_registry.get 失败）。
    candidates = list(filter_manifests_by_platform(candidates, platform))
    # 并集去重：锚定命中照旧自动进；手动条目若同时被锚定命中，清单只出现
    # 一次（标注 manual——全文已直读，模型无需点名），全文仍直读（manual_fulltexts 全量）
    anchored_ids = {ref.id for ref in references}
    manual_ids = {ref.id for ref in manual_entries}
    anchored_only = [ref for ref in references if ref.id not in manual_ids]
    manual_flagged = [ref for ref in references if ref.id in manual_ids]
    manual_extra = [ref for ref in manual_entries if ref.id not in anchored_ids]
    suggestions = [
        *reference_suggestions(anchored_only),
        *reference_suggestions(
            [*manual_flagged, *manual_extra], source=REFERENCE_SOURCE_MANUAL
        ),
    ]
    return TopicContext(
        key=entry.key,
        problem_text=entry.problem_text,
        references=references,
        manifest_summaries=tuple(build_manifest_summaries(candidates)),
        suggestions=tuple(suggestions),
        read_fulltext=_make_fulltext_reader(reference_library_dir, references),
        manual_references=manual_entries,
        manual_fulltexts=manual_fulltexts,
    )


def _no_topic_context(
    problem_text: str,
    module_library_dir: Path,
    reference_library_dir: Path,
    manual_entries: Sequence[ReferenceEntry] = (),
    manual_fulltexts: Mapping[str, str] | None = None,
    platform: str = "",
) -> TopicContext:
    """no-topic 形上下文（key="" 哨兵 = 未识别到历史赛题，路由零 fallback）。

    题面原样 + 空关联 / 建议 + 全模块摘要（无该题时候选清单就是全模块库，
    与显式路径同一次扫库）+ 空集回读器（任何 id 抛 ReferenceError——
    suggestions 恒空所以永不被调，诚实 no-op）。手动选参考资料是 no-topic
    唯一准入：suggestions = 手动条目（来源标注 manual），全文直读
    （manual_fulltexts）；未选 = 现行为（零参考）。回读器对手动条目 id 可
    回读（模型若点名已全文的条目也不崩，读回同一全文无害），其它 id 仍抛。
    platform（工单 ref-platform-filter 模块侧对偶）与显式路径同款：候选模块
    按平台过滤，空串 = 不过滤（缺省，现状保持）。
    """
    candidates = list_modules(module_library_dir) if module_library_dir.is_dir() else []
    candidates = list(filter_manifests_by_platform(candidates, platform))
    return TopicContext(
        key="",
        problem_text=problem_text,
        references=(),
        manifest_summaries=tuple(build_manifest_summaries(candidates)),
        suggestions=reference_suggestions(manual_entries, source=REFERENCE_SOURCE_MANUAL),
        read_fulltext=_make_fulltext_reader(reference_library_dir, (), manual_entries),
        manual_references=tuple(manual_entries),
        manual_fulltexts=manual_fulltexts,
    )


def _resolve_topic_entry(topic_library_dir: Path, topic_key: str) -> TopicEntry:
    """历史赛题条目（唯一解析点：查库，不猜测编造）。"""
    return resolve_number(topic_library_dir, topic_key)


def _make_fulltext_reader(
    reference_root: Path,
    references: Sequence[ReferenceEntry],
    manual_entries: Sequence[ReferenceEntry] = (),
) -> Callable[[str], str]:
    """两级注入第二级回读器：清单段条目 id → 全文（键映射与读取在同一处，
    装配进上下文的唯一实现——webapp 不再自建 reader 闭包）。

    键覆盖锚定清单 ∪ 手动条目——手动条目已全文直读、模型无需点名，但万一
    点名也不崩（读回同一全文无害）；清单外 id 仍大声失败（幻觉 / 库损坏）。
    """

    def reader(entry_id: str) -> str:
        for entry in (*references, *manual_entries):
            if entry.id == entry_id:
                return read_fulltext(reference_root, entry)
        raise ReferenceError(f"参考文件条目不存在：{entry_id!r}")

    return reader


@dataclass(frozen=True)
class GenerationSummary:
    """生成结果摘要（界面呈现用）：工程结构 / include path / 各模块文件清单。

    build_hint（工单 mspm0-build-makefiles/01）：mspm0 生成时未探测到 CCS
    工具链 → 中文提示（命令行构建不可用，可设置页填 ccs_* 覆盖），生成本身
    照常；stm32 与探测命中时为空串。
    """

    output_dir: Path
    structure: tuple[str, ...]  # 相对工程目录的文件路径（POSIX），排序
    include_dirs: tuple[str, ...]  # 已去重，按首次出现顺序
    modules: tuple[tuple[str, tuple[str, ...]], ...]  # (slug, 该平台文件列表)
    build_hint: str = ""


def describe_generation(
    output_dir: Path,
    manifests: Sequence[ModuleManifest],
    platform: str,
    include_dirs: Sequence[str],
    build_hint: str = "",
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
        build_hint=build_hint,
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
    ccs_tools: CcsTools | None = None,
    bindings: Mapping[str, str] | None = None,
) -> GenerationSummary:
    """完整生成流程：选模块 → 定位母版 → 生成 → 摘要，一步到位的接缝。

    生成前的组合操作（加载库 + 展开依赖 + 平台警告 → 母版目录 → 复制打补丁
    → 只读摘要）只有一个入口，webapp 与流程级测试都经它驱动；母版库布局
    （masters_dir/<platform>）归母版模块所有（master_project_dir），这里只
    调用不另抄。所有校验失败都在创建输出目录之前发生。

    模块集 = 用户选择（含推荐链路结果）原样展开，历史赛题入口不再自动并入
    任何"题专用模块"（普适化后无题专用模块，推荐链路 AI 按题面能力推荐
    承担——工单 module-universalization/07，勿恢复）。

    ccs_tools（工单 mspm0-build-makefiles/01）：CCS 三件套探测结果由装配层
    （webapp）探好传入——本流程不自己探（探针需要 config 覆盖值，config 归
    装配层；直接调用方不传 = 不写 makefile 集，测试确定性）。mspm0 + None
    = 摘要 build_hint 提示（命令行构建不可用），生成不阻断。
    """
    resolved = resolve_selection(module_library_dir, platform, slugs)
    result_dir, include_dirs, build_hint = generate(
        platform=platform,
        manifests=resolved.manifests,
        module_library_dir=module_library_dir,
        master_project_dir=master_project_dir(masters_dir, platform),
        output_dir=output_dir,
        main_c_content=main_c_content,
        registry=registry,
        ccs_tools=ccs_tools,
        bindings=bindings,
    )
    return describe_generation(
        result_dir, resolved.manifests, platform, include_dirs, build_hint
    )


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
    """生成校验的内存语料：一次读盘，语料门禁共吃（文件路径查重门直接吃
    manifest 声明，不读盘——输入依赖在 GENERATION_GATES 表内声明）。

    modules 顺序与 manifests 一致（含平台条目缺失的模块，files 为空——
    缺失清单在 missing 里）；master_headers = 母版树全部 *.h（相对路径,
    文本，一次 rglob + 读盘）；master_search_dirs = 母版 IncludePath
    （keil 语义，构建时算好）；search_dir_headers = 每个搜索目录的 *.h
    基名集合（小写化，构建时一次 glob，目录不存在 = 空集——include 解析
    门纯集合成员判定）；main_c 直接进语料。测试可内存构造直喂门禁。
    """

    platform: str
    modules: tuple[tuple[str, tuple[ModuleFile, ...]], ...]
    missing_platforms: tuple[str, ...]  # 无该平台版本条目的 slug
    missing_files: tuple[tuple[str, str], ...]  # (slug, rel) 声明了但读不到
    master_headers: tuple[tuple[str, str], ...]
    master_search_dirs: tuple[Path, ...]
    search_dir_headers: tuple[tuple[Path, frozenset[str]], ...]  # 搜索目录 *.h 基名集合（小写化）
    master_project_dir: Path  # main.c 的 own_dir（最终工程根 = 母版根）
    main_c: str


def _search_dir_header_names(
    search_dirs: Sequence[Path],
) -> tuple[tuple[Path, frozenset[str]], ...]:
    """每个搜索目录的 *.h 基名集合（小写化，Windows 大小写不敏感对齐）。

    目录不存在（或不是目录）= 空集，与旧 is_file 判 False 同义；语料构建时
    一次 glob，门禁不再扫盘（工单 gate-corpus-closure/01）。
    """
    names: list[tuple[Path, frozenset[str]]] = []
    for d in search_dirs:
        if d.is_dir():
            names.append(
                (d, frozenset(p.name.lower() for p in d.glob("*.h") if p.is_file()))
            )
        else:
            names.append((d, frozenset()))
    return tuple(names)


def build_module_corpus(
    manifests: Sequence[ModuleManifest],
    platform: str,
    library_dir: Path,
    master_project_dir: Path,
    main_c_content: str,
) -> ModuleCorpus:
    """一次读盘构建校验语料：模块文件（存在性 + 文本）+ 母版头 + 搜索目录。

    模块文件读盘走 read_module_sources（骨架与门禁同读法，errors="replace"
    编码策略单源）；缺失不 raise——存在性由 _check_module_files 门报告
    （missing 清单记录，门禁职责不变）；母版 rglob 与 IncludePath 也在这里
    一次做完，门禁不再扫盘。
    """
    present, missing = read_module_sources(manifests, platform, library_dir)
    files_by_slug: dict[str, list[ModuleFile]] = {}
    for slug, rel, text, path in present:
        kind = (
            "h"
            if is_header_path(rel)
            else "c"
            if rel.lower().endswith(".c")
            else "other"
        )
        files_by_slug.setdefault(slug, []).append(
            ModuleFile(rel=rel, kind=kind, text=text, own_dir=path.parent)
        )
    modules: list[tuple[str, tuple[ModuleFile, ...]]] = []
    missing_platforms: list[str] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            missing_platforms.append(manifest.slug)
            modules.append((manifest.slug, ()))
            continue
        modules.append((manifest.slug, tuple(files_by_slug.get(manifest.slug, ()))))

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

    search_dirs = tuple(include_search_dirs(platform, master_project_dir))
    return ModuleCorpus(
        platform=platform,
        modules=tuple(modules),
        missing_platforms=tuple(missing_platforms),
        missing_files=tuple(missing),
        master_headers=tuple(master_headers),
        master_search_dirs=search_dirs,
        search_dir_headers=_search_dir_header_names(search_dirs),
        master_project_dir=master_project_dir,
        main_c=main_c_content,
    )


def build_output_tree_corpus(
    output_dir: Path, platform: str, search_dirs: Sequence[Path]
) -> ModuleCorpus:
    """从生成产物树重建校验语料（真机验收与门禁同源，工单 generate-check-parity/01）。

    真机验收脚本曾逐字重实现门禁（FENCE_RE / include 解析 / 豁免集），门禁
    一改脚本静默漂移，验收给假信心——重建语料后跑同一个 run_generation_gates，
    验收测的就是生产逻辑本身。产物树即生成成功态（generate 落盘后）：
    modules = output_dir/modules/<slug>/ 下文件（kind 判定与 build_module_corpus
    同规），modules 目录不存在 = 空；master_headers = 产物树 *.h 排除 modules/
    子树（模块头在 modules 里，语义同母版头段）；main_c 从产物树读盘；
    missing 两组取空（生成成功 = 文件俱在）；master_search_dirs = 调用方传入
    的产物 .uvprojx/.cproject IncludePath（补丁后的最终值——patch 没把模块
    目录写进 IncludePath，include 解析门在此失败）。纯函数，tmp_path 直构
    产物树可测。
    """
    modules: list[tuple[str, tuple[ModuleFile, ...]]] = []
    modules_dir = output_dir / MODULES_SUBDIR
    if modules_dir.is_dir():
        by_slug: dict[str, list[ModuleFile]] = {}
        for path in iter_project_files(modules_dir):
            rel = path.relative_to(modules_dir).as_posix()
            slug, _, file_rel = rel.partition("/")
            kind = (
                "h"
                if is_header_path(file_rel)
                else "c"
                if file_rel.lower().endswith(".c")
                else "other"
            )
            by_slug.setdefault(slug, []).append(
                ModuleFile(
                    rel=file_rel,
                    kind=kind,
                    text=path.read_text(encoding="utf-8", errors="replace"),
                    own_dir=path.parent,
                )
            )
        modules = [
            (slug, tuple(files)) for slug, files in sorted(by_slug.items())
        ]

    master_headers: list[tuple[str, str]] = []
    for path in iter_project_files(output_dir, pattern="*.h"):
        rel = path.relative_to(output_dir).as_posix()
        if rel.startswith(MODULES_SUBDIR + "/"):
            continue  # 模块头在 modules 语料里，母版头段只收母版树
        try:
            master_headers.append(
                (
                    rel,
                    path.read_text(encoding="utf-8", errors="replace"),
                )
            )
        except OSError:
            continue

    try:
        main_c = (output_dir / "main.c").read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        main_c = ""

    search_dir_list = tuple(search_dirs)
    return ModuleCorpus(
        platform=platform,
        modules=tuple(modules),
        missing_platforms=(),
        missing_files=(),
        master_headers=tuple(master_headers),
        master_search_dirs=search_dir_list,
        search_dir_headers=_search_dir_header_names(search_dir_list),
        master_project_dir=output_dir,
        main_c=main_c,
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
    ccs_tools: CcsTools | None = None,
    bindings: Mapping[str, str] | None = None,
) -> tuple[Path, tuple[str, ...], str]:
    """生成完整工程目录，返回（输出目录, include 目录清单 POSIX 相对路径,
    build_hint）。

    include 目录 = _copy_module_files 实际复制出的目录（摘要消费同一来源，
    不再二次推导——见 describe_generation）。

    bindings（工单 pin-board-config/02）：可选板级引脚绑定载荷
    `{"<slug>.<role_id>": "<PIN>"}`——缺省 / 空 = 全默认（旧行为逐字节）。
    带绑定时：板定义 + resolve_bindings 预校验（PinBindingError → 400，
    在创建输出目录之前发生；pin_bindings 门禁以原始载荷再校验一遍，同一
    纯函数两处调用是刻意的——门禁是唯一校验出口，generate 拿解析结果喂
    写侧），copytree 后 apply_pin_bindings 覆写 pin_config.h / 改写 syscfg
    （文本无变化不落盘，缺省路径完全不进写侧）。

    mspm0 构建脚本（工单 mspm0-build-makefiles/01）：产物完整后（patcher 之后）
    从复制产物推导模块源集（过滤 .c，子目录 = rel 父目录——manifest 单源，
    不维护静态 MODULES 表）写 CCS 标准 Debug/makefile 集（write_makefile_set，
    路径全部参数化）；ccs_tools 未探测到（None）→ 跳过 + build_hint 提示，
    不阻断生成。stm32 零改动（无构建脚本、hint 空）。
    """
    patcher_registry = registry or default_registry()
    patcher = patcher_registry.get(platform)  # 未知平台在这里失败

    if not master_project_dir.is_dir():
        raise MasterNotFoundError(f"母版工程目录不存在：{master_project_dir}")

    if output_dir.exists() and any(output_dir.iterdir()):
        raise OutputDirNotEmptyError(f"输出目录已存在且非空，拒绝覆盖：{output_dir}")

    # 绑定预解析（工单 02）：板定义 + 载荷校验都在创建输出目录之前；解析
    # 结果喂写侧（门禁对原始载荷独立再校验——见 docstring）。
    board: Board | None = None
    resolved_bindings: tuple[ResolvedBinding, ...] = ()
    if bindings:
        board = board_for_platform(platform)  # 板数据缺失 = BoardError 500（白名单）
        resolved_bindings = resolve_bindings(manifests, platform, board, bindings)

    corpus = build_module_corpus(
        manifests, platform, module_library_dir, master_project_dir, main_c_content
    )
    run_generation_gates(
        corpus,
        manifests,
        platform,
        GateContext(bindings=bindings or {}, board=board),
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

        # copytree 后按绑定覆写板级引脚配置（工单 02 写侧；缺省路径不进写侧）
        if resolved_bindings:
            apply_pin_bindings(output_dir, platform, resolved_bindings)

        patcher.patch(output_dir, copied_files, include_dirs)

        build_hint = ""
        if platform == PLATFORM_MSPM0:
            if ccs_tools is None:
                build_hint = CCS_NOT_FOUND_HINT
            else:
                write_makefile_set(
                    output_dir,
                    _module_sources(copied_files),
                    sdk_dir=str(ccs_tools.sdk_dir),
                    compiler_dir=str(ccs_tools.compiler_dir),
                    sysconfig_cli=str(ccs_tools.sysconfig_cli),
                )
    except Exception:
        # 复制中途失败不要留下半成品
        shutil.rmtree(output_dir, ignore_errors=True)
        raise

    return output_dir, tuple(p.as_posix() for p in include_dirs), build_hint


def _module_sources(
    copied_files: Sequence[Path],
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """复制产物（modules/<slug>/... 相对路径）→ makefiles 的模块源形状
    （(slug, 子目录, (源文件名, ...))，只收 .c，子目录 = 文件在模块目录下的
    父目录、空 = 平铺；顺序 = 复制顺序即 manifest 顺序）。空 files 平台条目
    （实现内嵌母版）不复制 → 天然不进 makefile 集；纯 .h 模块不产生编译
    条目（无源码可编）。"""
    order: list[tuple[str, str]] = []
    by_key: dict[tuple[str, str], list[str]] = {}
    for rel in copied_files:
        parts = rel.parts
        if len(parts) < 3 or parts[0] != MODULES_SUBDIR:
            continue  # 模块文件恒为 modules/<slug>/<rel> 形态，防御性跳过
        if not rel.name.lower().endswith(".c"):
            continue
        key = (parts[1], "/".join(parts[2:-1]))
        if key not in by_key:
            order.append(key)
            by_key[key] = []
        by_key[key].append(rel.name)
    return tuple(
        (slug, subdir, tuple(by_key[(slug, subdir)])) for slug, subdir in order
    )


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

    接口集 = 模块头 + 母版头（corpus.master_headers 已收集，直接并入）——
    main.c 调母版内嵌实现的 ml_* API 不再误报未定义（工单 02，骨架阶段
    已把母版头喂给 LLM，门禁必须认同一套；mspm0 母版无 .h，并入为空）。
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
    headers.extend(("母版", rel, text) for rel, text in corpus.master_headers)
    interfaces = format_interface_blocks(headers)
    # 母版内嵌实现（空 files 平台条目）的函数在母版头里声明——接口集并入
    # 母版头，main.c 调 ml_* / OLED_* 等母版 API 不再误报未定义（mspm0
    # 母版无 .h，并入为空，无副作用）
    interfaces.extend(
        format_interface_blocks(
            [("母版", rel, text) for rel, text in corpus.master_headers]
        )
    )
    undefined = verify_main_c_interfaces(corpus.main_c, interfaces)
    if undefined:
        raise UndefinedCallsError(
            "main.c 调用了所选模块头文件中不存在的函数："
            + "、".join(undefined)
            + " —— 请改用真实接口，或让骨架阶段自检改写为注释占位"
        )


def _check_unresolved_includes(corpus: ModuleCorpus) -> None:
    """生成前静态校验：main.c 与模块源码的每个引号 include 都必须在最终工程里可解析。

    C 预处理器语义：#include "x.h" 先找当前文件所在目录，再按 IncludePath 顺序找
    （模块代码目录自动追加 + 母版自带）；工程内找不到且不在豁免集合（C 标准
    库头 + 平台工具链头）→ 拒绝生成（判例：库模块 pid.c 引用了从未入库的
    digit_uart.h，Keil 报 cannot open source input file，真机编译失败）。检查
    在创建输出目录之前发生，不产出残缺工程。解析是纯集合成员判定：own_dir
    兄弟头名（模块文件按 own_dir 分组 + 母版根头）∪ 搜索目录头名单（语料
    构建时一次 glob，search_dir_headers）∪ 豁免集合——门禁只吃语料不碰盘。
    """
    # own_dir 兄弟头名：模块文件按 own_dir 分组取基名（小写化，Windows 大小写
    # 不敏感语义）；模块目录同时是搜索目录（IncludePath 自动追加模块代码目录）。
    grouped: dict[str, set[str]] = {}
    for _, files in corpus.modules:
        for f in files:
            grouped.setdefault(str(f.own_dir).lower(), set()).add(
                Path(f.rel).name.lower()
            )
    module_dir_names = {key: frozenset(names) for key, names in grouped.items()}

    # 母版根兄弟头名：main.c 的 own_dir = 母版根，兄弟头 = 相对母版根无父目录的头
    root_names = frozenset(
        Path(rel).name.lower() for rel, _ in corpus.master_headers if "/" not in rel
    )
    master_root_key = str(corpus.master_project_dir).lower()

    # 豁免 = C 标准库头（平台无关）+ 平台工具链头（keil/ccs 声明，patchers
    # 分派），循环前算一次
    exemptions = _LIBC_HEADERS | external_headers(corpus.platform)

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
        own_names = module_dir_names.get(str(own_dir).lower(), frozenset())
        if str(own_dir).lower() == master_root_key:
            own_names = own_names | root_names
        stripped = strip_comments(code, keep_preprocessor=True)
        for header in extract_quoted_includes(stripped):
            lowered = header.lower()
            if lowered in own_names:
                continue
            if any(lowered in names for names in module_dir_names.values()):
                continue
            if any(lowered in names for _, names in corpus.search_dir_headers):
                continue
            if lowered in exemptions:
                continue
            problems.append(f"{label} 引用了最终工程中不存在的头文件 {header}")
    if problems:
        raise UnresolvedIncludeError(
            "生成工程无法编译（include 解析失败）：\n- " + "\n- ".join(problems)
            + "\n —— 请将该头文件所属模块一并选中，或补录模块库条目"
        )


def _check_module_self_include(corpus: ModuleCorpus) -> None:
    """生成前静态校验：模块 .c 必须 include 本模块自己的至少一个头文件。

    C 预处理器语义：模块 .c 不 include 自己的 .h 时，符号声明只存在于原始工程的
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

    C 预处理器语义：#define 同名不同值 = #47-D incompatible redefinition 警告
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


def _check_file_path_conflicts(
    manifests: Sequence[ModuleManifest], platform: str
) -> None:
    """生成前静态校验：所选模块（含依赖展开后）的平台文件相对路径不得跨模块重复。

    生成器把模块文件复制到 modules/<slug>/ 命名空间目录，文件本身不互相覆盖，
    但跨模块同名文件 = 同源代码重复进工程，符号定义必然重复——UV4 链接期
    L6200E multiply defined 判例：zigbee_uart 与 zigbee_uart_key 曾同声明
    code/zigbee_uart.c/.h，五道静态门静默通过、真机编译才炸。库内不变量
    （tests/test_module_collision.py 全库跨模块重复路径即红）只管数据层，本门
    管生成时组合——新补录模块撞既有路径、用户组合出冲突时，生成前大声失败
    （400 中文），同类冲突不再等真机编译暴露。files 空（实现内嵌母版）跳过；
    只查选中平台条目；同一模块内 manifest 重复声明同查（parse 侧已防，防御
    内存构造路径）。
    """
    by_path: dict[str, str] = {}
    problems: list[str] = []
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue  # 无该平台版本条目由 _check_module_files 报，这里跳过
        for rel in entry.files:
            owner = by_path.get(rel)
            if owner is None:
                by_path[rel] = manifest.slug
            elif owner == manifest.slug:
                problems.append(f"模块 {manifest.slug} 重复声明文件 {rel}")
            else:
                problems.append(
                    f"模块 {manifest.slug} 与模块 {owner} 都声明文件 {rel}"
                )
    if problems:
        raise DuplicateFilePathError(
            "所选模块存在同名文件冲突（生成工程链接期会报 UV4 L6200E "
            "multiply defined）：\n- " + "\n- ".join(problems)
            + " —— 请检查模块选择，或补录库条目唯一化文件路径"
        )


def _check_pin_bindings(
    corpus: ModuleCorpus,
    manifests: Sequence[ModuleManifest],
    platform: str,
    context: "GateContext",
) -> None:
    """绑定载荷校验（工单 02）：键格式 / 未知角色 / 未知引脚 / 能力 / mspm0
    槽位冲突——全部在创建输出目录之前发生，非法即 PinBindingError 400 中文。

    空载荷（bindings 缺省）直过 = 全默认；resolve_bindings 是校验唯一实现
    （generate 预解析与写侧同吃）。重复绑定不拦（同引脚多角色共享合法）。
    """
    if not context.bindings:
        return
    if context.board is None:
        raise PinBindingError(
            "绑定校验缺少板定义（装配层未传入）——请检查 boards 数据或生成入口"
        )
    resolve_bindings(manifests, platform, context.board, context.bindings)


def _check_no_pin_literals_in_main(
    corpus: ModuleCorpus,
    manifests: Sequence[ModuleManifest],
    platform: str,
    context: "GateContext",
) -> None:
    """骨架不内联引脚（工单 02）：clex 注释剥离后 main.c 不得含引脚字面量
    （PAx/PBx/PCx/PDx…/GPIO_Pin_N）——守住"骨架只调模块接口，引脚归接线
    单源（pin_config.h / mspm0.syscfg）"的现状性质，换板才不用重写骨架。

    历史产物注释里出现过 PA11 字样（spec 关键事实），必须注释剥离后判定才
    不误伤；字符串字面量同样被 clex 剥掉（printf 里提到引脚名无害）。
    """
    stripped = strip_comments(corpus.main_c)
    hits = sorted(set(_PIN_LITERAL_RE.findall(stripped)))
    if hits:
        raise PinLiteralInMainError(
            "main.c 不得内联引脚字面量（引脚归接线单源 pin_config.h / "
            "mspm0.syscfg，骨架只调模块接口宏）："
            + "、".join(hits)
            + " —— 请改用模块接口宏（如 GRAY_D1_PIN / DC_MOTOR_AA_PORT），"
            "或让骨架阶段自检改写"
        )


def _check_timer_instance_conflicts(
    corpus: ModuleCorpus,
    manifests: Sequence[ModuleManifest],
    platform: str,
    context: "GateContext",
) -> None:
    """骨架定时器 × 绑定 pwm 实例冲突（工单 pin-unlock-stm32/01，ADR 0011）：
    main_c 经 clex 注释剥离后扫 tim_interrupt_ms_init(TIM_x（x∈2/3/4，TIM_2/
    TIM2 两写法），与**用户改动过**的绑定 pwm 角色 TIM 实例前段（TIM3_CH1 →
    3）冲突 → TimerConflictError 400 中文——同一 TIM 被骨架调度占用（2026H
    TIM_3 调度 / 2026C TIM_2 滴答），编译绿运行坏，生成前拦截。

    只查用户绑定且绑定 ≠ 默认值（no-op 不触发——默认组合冲突是现状性质不拦，
    spec 留痕）；识别不到（LLM 换写法）不拦——漏报优于误报。mspm0 pwm 实例
    形态（TIMG0_C0/TIMA0_C3）不命中 TIM[234] 正则，天然不拦。
    """
    if not context.bindings or context.board is None:
        return
    resolved = resolve_bindings(manifests, platform, context.board, context.bindings)
    bound_timers: dict[int, tuple[ResolvedBinding, str]] = {}
    for binding in resolved:
        if (
            binding.declaration.type != "pwm"
            or binding.pin == binding.declaration.default
        ):
            continue
        for instance in binding.instances:
            match = _PWM_TIMER_INSTANCE_RE.match(instance)
            if match:
                timer_no = int(match.group(1))
                bound_timers.setdefault(timer_no, (binding, instance))
                break
    if not bound_timers:
        return
    skeleton_timers = {
        int(number) for number in _SKELETON_TIMER_RE.findall(strip_comments(corpus.main_c))
    }
    for timer_no, (binding, instance) in bound_timers.items():
        if timer_no in skeleton_timers:
            raise TimerConflictError(
                f"PWM 绑定 {instance}（{binding.role_key}）与骨架调度定时器"
                f" TIM_{timer_no} 冲突（tim_interrupt_ms_init 已占用该定时器"
                f"——请换绑其它 TIM 通道的引脚）"
            )


def _check_exti_line_conflicts(
    corpus: ModuleCorpus,
    manifests: Sequence[ModuleManifest],
    platform: str,
    context: "GateContext",
) -> None:
    """绑定 enc/exti 角色异口同线互斥（工单 pin-full-unlock/01，ADR 0012）：
    EXTI 线号 = 脚号 mod 16（PA5/PB5 同线 5、PC13 线 13）——同线两角色分属
    两个 handler（motor 条件编译）会互相清 PR 位 = 编译绿运行坏，生成前
    400。两两只查绑定项；同脚共享不查（提示语义）；mspm0 无 EXTI 线语义
    不适用（enc 走 GPIO 组中断）。
    """
    if platform != PLATFORM_STM32 or not context.bindings or context.board is None:
        return
    resolved = resolve_bindings(manifests, platform, context.board, context.bindings)
    candidates = [b for b in resolved if b.declaration.type in ("enc", "exti")]
    for i, first in enumerate(candidates):
        for second in candidates[i + 1 :]:
            if first.pin == second.pin:
                continue  # 同脚共享 = 提示语义，不查
            first_line = _exti_line_of(first.pin)
            second_line = _exti_line_of(second.pin)
            if first_line == second_line:
                raise ExtiLineConflictError(
                    f"绑定冲突：{first.role_key}（{first.pin}）与"
                    f" {second.role_key}（{second.pin}）同 EXTI 线"
                    f" {first_line}，异口同线互斥（共线 handler 互相清 PR 位，"
                    f"编译绿运行坏）——请换绑不同线号的引脚"
                )


def _exti_line_of(pin: str) -> int:
    """引脚名尾号 → EXTI 线号（PA5 → 5、PC13 → 13 mod 16）。"""
    match = _PIN_TRAILING_DIGITS_RE.search(pin)
    assert match is not None, f"非引脚名 {pin!r} 无尾号（板数据漂移）"
    return int(match.group(1)) % 16


@dataclass(frozen=True)
class GenerationGate:
    """一道生成门禁的装配描述：key（表内唯一，测试钉死顺序）+ check（小型
    闭包选择该门的自然输入——谓词函数签名与实现零改动，表只做输入选择）。"""

    key: str
    check: Callable[
        [ModuleCorpus, Sequence[ModuleManifest], str, "GateContext"], None
    ]


@dataclass(frozen=True)
class GateContext:
    """门禁的请求级输入（工单 02）：板定义 + 绑定载荷——pin_bindings /
    no_pin_literals_in_main 两条新门禁用，存量门禁忽略。

    缺省空上下文 = 无绑定（generate_check 产物复核与存量测试同此形态，
    两条新门禁空转直过）。board 只随 bindings 传入（缺省路径不加载板数据）。
    """

    bindings: Mapping[str, str] = field(default_factory=dict)
    board: Board | None = None


# 门禁表。顺序即 generate 的校验顺序（现状调用顺序，结构测试钉死）；顺序有
# 语义：file_path_conflicts 跳过无该平台版本条目（由 module_files 先报），
# 必须先跑 module_files；timer_instance_conflicts / exti_line_conflicts
# 依赖 pin_bindings 先校验载荷（resolve 才能成功）。新增门禁 = 表加一条 +
# 谓词（照 categories.RULE_CATEGORIES 先例）——顺序 / 输入依赖 / 门禁全貌
# 只此一处可见。5 道吃 corpus（纯谓词，内存直构可测）；file_path_conflicts
# 吃 manifests + platform（manifest 声明，不读盘）；工单 02 新两条 + 工单
# pin-unlock-stm32/01 一条 + 工单 pin-full-unlock/01 一条吃 context
# （bindings + board——绑定校验 / 骨架引脚字面量 / 骨架定时器冲突 / EXTI
# 线冲突）。签名统一 4 参，存量谓词忽略第 4 参。
GENERATION_GATES: tuple[GenerationGate, ...] = (
    GenerationGate(
        "module_files",
        lambda corpus, manifests, platform, context: _check_module_files(corpus),
    ),
    GenerationGate(
        "file_path_conflicts",
        lambda corpus, manifests, platform, context: _check_file_path_conflicts(
            manifests, platform
        ),
    ),
    GenerationGate(
        "main_calls",
        lambda corpus, manifests, platform, context: _check_main_calls(corpus),
    ),
    GenerationGate(
        "module_self_include",
        lambda corpus, manifests, platform, context: _check_module_self_include(
            corpus
        ),
    ),
    GenerationGate(
        "unresolved_includes",
        lambda corpus, manifests, platform, context: _check_unresolved_includes(
            corpus
        ),
    ),
    GenerationGate(
        "macro_conflicts",
        lambda corpus, manifests, platform, context: _check_macro_conflicts(
            corpus
        ),
    ),
    GenerationGate(
        "pin_bindings",
        lambda corpus, manifests, platform, context: _check_pin_bindings(
            corpus, manifests, platform, context
        ),
    ),
    GenerationGate(
        "timer_instance_conflicts",
        lambda corpus, manifests, platform, context: _check_timer_instance_conflicts(
            corpus, manifests, platform, context
        ),
    ),
    GenerationGate(
        "exti_line_conflicts",
        lambda corpus, manifests, platform, context: _check_exti_line_conflicts(
            corpus, manifests, platform, context
        ),
    ),
    GenerationGate(
        "no_pin_literals_in_main",
        lambda corpus, manifests, platform, context: _check_no_pin_literals_in_main(
            corpus, manifests, platform, context
        ),
    ),
)


def run_generation_gates(
    corpus: ModuleCorpus,
    manifests: Sequence[ModuleManifest],
    platform: str,
    context: GateContext | None = None,
) -> None:
    """按表序跑全部生成门禁（装配唯一出口）：首个失败即抛，不产出残缺工程。

    generate 不再自写门禁循环；新增 / 重排门禁只改表。context 缺省 = 空
    （无绑定形态，generate_check 产物复核 / 存量测试同此）。
    """
    ctx = context or GateContext()
    for gate in GENERATION_GATES:
        gate.check(corpus, manifests, platform, ctx)


def _copy_module_files(
    manifests: Sequence[ModuleManifest],
    platform: str,
    library_dir: Path,
    output_dir: Path,
) -> tuple[list[Path], list[Path]]:
    """复制模块文件到 modules/<slug>/ 下，返回（相对工程目录的文件列表、include 目录列表）。

    空 files 平台条目（实现内嵌母版）不复制、不加 include 目录——files 为
    空时内层循环天然跳过，生成物只含母版自带的实现，无需注册。
    """
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
