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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

from .ccs import CcsProjectError, extract_config_summary as extract_ccs_config_summary
from .keil import (
    KeilProjectError,
    build_master_uvprojx,
    extract_config_summary as extract_keil_config_summary,
    is_md_startup,
    is_startup_candidate,
    render_master_uvprojx,
    validate_project_structure,
)
from .events import ProgressEmitter  # 进度发射器类型（契约在 events，仅类型引用）
from .llm import LLM  # AI 接缝协议（仅类型引用，实现与解析在 llm 层）
from .platforms import KNOWN_PLATFORMS, PLATFORM_MSPM0, PLATFORM_STM32
from .reference_library import (
    ReferenceError,
    archive_reference,
    validate_topic_anchor,
)
from .report import (
    ACTION_EXCLUDE,
    ACTION_KEEP,
    ACTION_MERGE,
    DistillationReport,
    FileDecision,
    FileVersion,
    JudgmentFile,
    ReferenceCandidate,
    ReportError,
)

# 扫描时忽略的目录：版本库与构建产物不是母版内容。Debug/Release（CCS 构建
# 输出）只在工程顶层出现，顶层匹配即可；Listings/Objects（Keil 默认输出目录）
# 建在 .uvprojx 所在目录——正点原子风格工程 .uvprojx 在 USER/ 下时，产物在
# USER/Listings、USER/Objects，必须按任意层级组件匹配（见 _is_ignored）。
# Keil 的 .d 依赖文件落在这些输出目录里，整目录忽略已覆盖，名单里不需要裸
# ".d" 规则（见 RESIDUE_RULES 注释）。
BUILD_ARTIFACT_DIRS = frozenset({"Debug", "Release", "Listings", "Objects"})
IGNORED_TOP_LEVEL_DIRS = frozenset({".git"}) | BUILD_ARTIFACT_DIRS

# 任意层级组件忽略的目录（其余忽略只在顶层生效，见 _is_ignored）
NESTED_IGNORE_DIRS = frozenset({"Listings", "Objects"})

# 残留规则（保守名单，与 template-fit-check.md 的"建议清理"一致）：构建产物 /
# 备份 / 临时文件 / IDE 用户选项按扩展名与模式机器识别。命中即确定性剔除——
# 不进扫描清单、不进 AI 判定、不读全文，但进报告 exclude 清单并带规则化原因
# （ADR 0001：不做黑盒消失）。IDE 用户选项（.uvoptx 断点 / 调试配置、.uvguix
# 窗口布局——2026C/21F 真实工程里成对出现）：非编译关键，Keil 编译时自动重建
# （工单 09 决策 5）。注意：刻意不含裸 ".d"（Keil/CCS 依赖文件）——.d 依赖
# 文件默认落在构建输出目录（Keil 的 Objects/Listings、CCS 的 Debug/Release），
# 目录级忽略（BUILD_ARTIFACT_DIRS，任意层级）已覆盖，名单不需要这条扩展名
# 规则。也不存在"截胡链接脚本"的问题：后缀匹配是整段 endswith，"startup.ld"
# / "link.cmd" 不以 ".d" 结尾。
RESIDUE_RULES: tuple[tuple[str, str], ...] = (
    (".o", "构建产物：.o 文件"),
    (".axf", "构建产物：.axf 文件"),
    (".hex", "构建产物：.hex 文件"),
    (".map", "构建产物：.map 文件"),
    (".lst", "构建产物：.lst 文件（Keil 列表文件）"),
    (".htm", "构建产物：.htm 文件（构建 / 链接日志）"),
    (".crf", "构建产物：.crf 文件（Keil 交叉引用文件）"),
    (".dep", "构建产物：.dep 文件（依赖文件）"),
    (".lnp", "构建产物：.lnp 文件（Keil 链接控制文件）"),
    (".out", "构建产物：.out 文件（CCS 链接产物）"),
    (".elf", "构建产物：.elf 文件（链接产物）"),
    (".uvoptx", "IDE 用户选项：编译时自动重建"),
    (".bak", "备份文件：.bak"),
    (".tmp", "临时文件：.tmp"),
    (".temp", "临时文件：.temp"),
    ("~", "备份文件：~ 结尾"),
)


def residue_reason(rel_path: str) -> str | None:
    """路径命中残留规则时返回规则化原因（如"构建产物：.o 文件"），否则 None。

    按路径后缀判定（大小写不敏感——Windows 下构建产物常大写，如 .HEX）；
    .bak 精确后缀之外，路径含 ".bak" 段的（pid.c.bak2 / pid.c.bak_consolidate
    ——真实旧工程备份习惯多样，判例 08）同样是备份。规则由路径决定：同一路径
    在任何工程里都是残留，不可能既是残留又是源码。
    """
    lowered = rel_path.lower()
    for suffix, reason in RESIDUE_RULES:
        if lowered.endswith(suffix):
            return reason
    if ".bak" in lowered:
        return "备份文件：.bak 变体（.bak2 / .bak_consolidate 等）"
    if ".uvguix" in lowered:
        # Keil 界面布局文件带用户名后缀（Project.uvguix.luoji，2026C/21F 真实
        # 工程成对出现）：按包含匹配，与 .uvoptx 同族规则剔除
        return "IDE 用户选项：Keil 界面布局，编译时自动重建"
    return None


# 二进制文件（内容判据）：文件头探针内含 NUL 字节即二进制。真实旧工程里混着
# 素材类文件——PDF / 图片 / 模型（.kmodel）/ 压缩包 / 可执行文件 / STEP 装配体，
# 它们不可能是编译链源码（母版 = 空的最小系统板工程，编译必需件只有文本），
# 且以 errors="replace" 读全文会产生几十 MB 乱码撑爆 LLM 上下文（判例 08：三个
# 真实工程判定素材 47.6M 字符，最大单文件 7.5M）。与残留同模式：规则识别、
# 确定性剔除、不进 AI 判定也不读全文，但进报告 exclude 清单并带规则化原因
# （ADR 0001：不做黑盒消失）。判据是内容不是扩展名——扩展名名单永远有尾
# （.kmodel/.STEP/.exe/.zip/...），NUL 探测覆盖任何二进制格式，且纯文本源码
# 不含 NUL，不会误伤。
BINARY_PROBE_BYTES = 8192
BINARY_FILE_REASON = "二进制文件：非源码素材（文档 / 图片 / 模型等），确定性剔除"


def _is_binary_file(path: Path) -> bool:
    """文件头（前 BINARY_PROBE_BYTES 字节）含 NUL 字节即判定为二进制。"""
    with path.open("rb") as file:
        return b"\x00" in file.read(BINARY_PROBE_BYTES)


def _binary_reason(rel_path: str, path: Path) -> str | None:
    """二进制类别识别（RuleCategory 统一签名）：内容判据命中返回规则化原因。"""
    return BINARY_FILE_REASON if _is_binary_file(path) else None


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


# 基础设施规则：启动文件（.s/.S）与链接脚本（.ld/.sct/.cmd）由规则识别、
# 确定性保留。电赛工程里这些就是官方标准件（startup_stm32f10x_hd.s 等），
# 格式固定、没有"项目特定"的可能；进 AI 判定只有判错风险（判 exclude →
# 空工程编译链断裂、编译失败，且重写 .uvprojx 时悬空引用会被静默删除）。
# 与残留同模式：不进扫描清单、不进 AI 判定素材、不读全文，但进报告 keep
# 清单并带规则化原因（ADR 0001：不做黑盒消失——保留方向同理）。
INFRASTRUCTURE_SUFFIXES = (".s", ".ld", ".sct", ".cmd")
INFRASTRUCTURE_REASON = "平台基础设施：启动文件 / 链接脚本，确定性保留"


def infrastructure_reason(rel_path: str) -> str | None:
    """基础设施识别：启动文件（.s）与链接脚本（.ld/.sct/.cmd）由规则保留。

    按路径后缀判定、大小写不敏感（Windows 文件系统大小写不敏感，.S 也是
    汇编启动文件）。命中即确定性保留——不进 AI 判定、不读全文，但进报告
    keep 清单并带规则化原因。注意：匹配 startup_stm32f10x_*.s 的启动文件
    候选单独记录（startup_files），由 assemble_report 跨工程去重后决定
    保留份与落选份。
    """
    lowered = rel_path.lower()
    for suffix in INFRASTRUCTURE_SUFFIXES:
        if lowered.endswith(suffix):
            return INFRASTRUCTURE_REASON
    return None


# ---------------------------------------------------------------------------
# 文件类别：残留 / 旧 main.c / 基础设施 / 二进制 / 工程配置文件——识别规则 +
# 生命周期唯一出处（启动文件候选是表内钩子，决策 2：跨工程去重）
# ---------------------------------------------------------------------------


# 工程配置文件（工单 09，判例 09 治本）：.uvprojx（stm32）由确定性渲染器
# 现写（keil.render_master_uvprojx，结构一致性由构造保证），.cproject/.project
# （mspm0，CCS 按目录编译、无文件引用问题，母版库尚无 mspm0 良好格式种子）
# 确定性保留首份原样、不现写不重写（决策 6）。与基础设施同模式：不进扫描
# 清单、不进 AI 判定素材、不读全文，但进报告 keep 清单并带规则化原因
# （ADR 0001：不做黑盒消失）；条目不可改动作（决策 7）。
UVPROJX_CONFIG_REASON = "工程配置文件：由确定性模板现写，保留文件全量入树"
CCS_CONFIG_REASON = "工程配置文件：由确定性规则保留首份原样（CCS 按目录编译）"
CONFIG_FILE_SUFFIXES = (
    ".uvprojx",  # stm32 / Keil
    ".cproject",  # mspm0 / CCS
    ".project",  # mspm0 / CCS（Eclipse 底座描述）
)


def config_file_reason(rel_path: str) -> str | None:
    """工程配置文件识别：按后缀判定、大小写不敏感，返回规则化原因。

    .uvprojx → 渲染现写；.cproject/.project → 保留首份原样。命中即确定性
    处理——不进 AI 判定（AI 给出这类路径的判定是越界，拒绝）、不读全文。
    """
    lowered = rel_path.lower()
    if lowered.endswith(".uvprojx"):
        return UVPROJX_CONFIG_REASON
    if lowered.endswith(".cproject") or lowered.endswith(".project"):
        return CCS_CONFIG_REASON
    return None


# 启动文件跨工程去重（决策 2）：同一器件只需一份启动文件——真实案例 2026C+21F
# 各带一份 md 启动（key/ 与 sys/），旧母版两份都保留（Reset_Handler 重复定义
# 风险）。文件名匹配 startup_stm32f10x_*.s 的 .s 是"启动文件候选"，至多保留
# 一份（优先 _md——与目标板 C8T6 中密度匹配，没有则按路径排序取第一份），
# 落选候选规则剔除、进报告 exclude 带本原因。
STARTUP_REPLACEMENT_REASON = "启动文件替代：同一器件只需一份启动文件"


def _pick_startup(comparison: "ProjectComparison") -> str | None:
    """跨工程启动文件去重（决策 2）：返回保留的那份，落选候选进 exclude。

    优先 startup_stm32f10x_md.s（与目标板 C8T6 中密度匹配）；没有 _md 则按
    路径排序取第一份（密度守卫在渲染器：保留份非 _md 时入库前大声失败）。
    确定性：同一输入必然同一结果。
    """
    candidates = comparison.startup_files
    if not candidates:
        return None
    md = sorted(c for c in candidates if is_md_startup(c))
    if md:
        return md[0]
    return sorted(candidates)[0]


@dataclass(frozen=True)
class RuleCategory:
    """一个文件类别的完整生命周期描述。

    类别 = 识别规则（reason_of，扫描时判定）+ 生命周期各环节的处置：扫描
    分类 → 对比并集 → 报告汇编（report_reason，此时已无文件内容可读，二进制
    类给常量原因）→ 越界拦截（AI 判定即报错）→ 校验（确认不能改成别的动作）。
    """

    key: str  # ProjectStructure / ProjectComparison 的字段名（类别分组）
    name: str  # 中文名（错误消息用）
    reason_of: Callable[[str, Path], str | None]  # (rel, path) → 规则化原因；None = 不命中
    report_reason: Callable[[str], str | None]  # 报告汇编取原因（按路径重算或常量）
    disposition: Literal["keep", "exclude"]  # 确定性处置：保留 / 剔除
    out_of_scope_message: str  # AI 判定即越界的报错文案，{path} 占位
    disposition_message: str  # 处置校验的报错前缀，如"残留文件必须剔除"


# 类别表。顺序即扫描的判定顺序：先便宜的后读文件内容的（二进制探针最后；
# 工程配置文件是纯后缀判定，放表尾——与残留 / 基础设施等类别互斥，顺序
# 不影响分类结果）。新增类别 = 在此加一条 + 给 ProjectStructure /
# ProjectComparison 补同名字段（声明式，不再复制六处逻辑）。启动文件候选
# 不进表（处置不是单一动作：跨工程至多保留一份，见 _pick_startup），由
# 扫描钩子单独记录、各流水线表外处理。
RULE_CATEGORIES: tuple[RuleCategory, ...] = (
    RuleCategory(
        key="residues",
        name="残留文件",
        reason_of=lambda rel, path: residue_reason(rel),
        report_reason=residue_reason,
        disposition="exclude",
        out_of_scope_message="残留文件由规则剔除，无需 AI 判定：{path}",
        disposition_message="残留文件必须剔除",
    ),
    RuleCategory(
        key="main_c_files",
        name="旧工程 main.c",
        reason_of=lambda rel, path: main_c_reason(rel),
        report_reason=main_c_reason,
        disposition="exclude",
        out_of_scope_message="旧工程 main.c 由模板替代，无需 AI 判定：{path}",
        disposition_message="旧工程 main.c 必须剔除",
    ),
    RuleCategory(
        key="infrastructure",
        name="基础设施",
        reason_of=lambda rel, path: infrastructure_reason(rel),
        report_reason=lambda _: INFRASTRUCTURE_REASON,
        disposition="keep",
        out_of_scope_message="基础设施由规则保留，无需 AI 判定：{path}",
        disposition_message="基础设施必须保留",
    ),
    RuleCategory(
        key="binaries",
        name="二进制文件",
        reason_of=_binary_reason,
        report_reason=lambda _: BINARY_FILE_REASON,
        disposition="exclude",
        out_of_scope_message="二进制文件由规则剔除，无需 AI 判定：{path}",
        disposition_message="二进制文件必须剔除",
    ),
    RuleCategory(
        key="config_files",
        name="工程配置文件",
        reason_of=lambda rel, path: config_file_reason(rel),
        report_reason=config_file_reason,
        disposition="keep",
        out_of_scope_message="工程配置文件由规则处理，无需 AI 判定：{path}",
        disposition_message="工程配置文件必须保留",
    ),
)
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
    替代，不进扫描清单）、工程配置文件（确定性规则处理，不进扫描清单）、
    启动文件候选（跨工程去重，不进 AI 判定）。"""

    project_dir: Path
    name: str  # 工程名（目录名）
    platform: str  # 检测到的平台
    files: tuple[str, ...]  # 相对路径（POSIX 分隔），排序
    file_hashes: Mapping[str, str]  # path -> sha256 hex（对比内容是否一致）
    config_summary: tuple[str, ...]  # 平台配置摘要行（配置对比的 AI 素材）
    residues: tuple[str, ...] = ()  # 残留相对路径（构建产物 / 备份 / 临时文件 / IDE 用户选项）
    main_c_files: tuple[str, ...] = ()  # 旧工程 main.c（模板替代，不进扫描清单）
    infrastructure: tuple[str, ...] = ()  # 基础设施（链接脚本 / 非启动 .s），确定性保留、不进 AI 判定
    startup_files: tuple[str, ...] = ()  # 启动文件候选（startup_stm32f10x_*.s），跨工程去重、不进 AI 判定
    config_files: tuple[str, ...] = ()  # 工程配置文件（.uvprojx/.cproject/.project），确定性规则处理、不进 AI 判定
    binaries: tuple[str, ...] = ()  # 二进制文件（内容判据，确定性剔除、不进 AI 判定）


@dataclass(frozen=True)
class ProjectComparison:
    """多工程的结构 + 配置对比结果。"""

    projects: tuple[ProjectStructure, ...]
    common: tuple[str, ...]  # 所有工程都有且内容完全一致
    conflicts: tuple[str, ...]  # 同路径、内容不一致
    unique: tuple[str, ...]  # 只出现在部分工程
    by_path: Mapping[str, tuple[str, ...]]  # path -> 含该文件的工程名（出现顺序）
    judgment: tuple[str, ...]  # 需要 AI 判定的路径（公共 + 冲突 + 独有）
    residues: tuple[str, ...] = ()  # 全部工程的残留路径（并集，排序）
    main_c_files: tuple[str, ...] = ()  # 全部工程的旧 main.c（并集，排序，模板替代）
    infrastructure: tuple[str, ...] = ()  # 全部工程的基础设施（并集，排序，确定性保留）
    startup_files: tuple[str, ...] = ()  # 全部工程的启动文件候选（并集，排序，去重后保留）
    config_files: tuple[str, ...] = ()  # 全部工程的工程配置文件（并集，排序，确定性规则处理）
    binaries: tuple[str, ...] = ()  # 全部工程的二进制文件（并集，排序，确定性剔除）


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
    失败只记一行，扫描不因单个工程带病中断）。
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
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(project_dir).as_posix()
        if _is_ignored(rel):
            continue
        for cat in RULE_CATEGORIES:
            if cat.reason_of(rel, path) is not None:
                # 类别互斥、按表序判定（残留 → main.c → 基础设施 → 二进制 →
                # 工程配置文件）：命中即分类、不读全文（二进制探针只读文件头）。
                # 表内钩子：基础设施命中且是启动文件候选（startup_*.s）时
                # 单列到 startup_files——跨工程去重（决策 2），不进基础设施组
                if cat.key == "infrastructure" and is_startup_candidate(rel):
                    startup_files.append(rel)
                else:
                    category_lists[cat.key].append(rel)
                break
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
    startup = _pick_startup(comparison)
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
    decisions: Sequence[FileDecision], comparison: ProjectComparison
) -> tuple[list[str], str | None, list[str]]:
    """渲染器输入推导：保留源码（.c/.s）+ 启动文件（去重后）+ 保留 .h 所在目录。

    预览（_config_preview）与落盘（apply_distillation）共用——同一份最终
    决策集必然渲染出同一份 .uvprojx，报告预览 = 实际落盘内容。
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
    return sources, _pick_startup(comparison), include_dirs


def _config_preview(
    platform: str, decisions: Sequence[FileDecision], comparison: ProjectComparison
) -> str:
    """.uvprojx 全文预览（决策 7）：stm32 由确定性渲染器推导（与 main_c_preview
    同款——确认回传时按平台重推导，客户端回传值不可信）；mspm0 无现写
    （保留首份原样），返回空串。"""
    if platform != PLATFORM_STM32:
        return ""
    return build_master_uvprojx(*_render_inputs(decisions, comparison))


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
    母版 = 空的最小系统板工程，旧工程 main.c 一律不进母版）；stm32 的
    .uvprojx 由确定性渲染器现写（工单 09，判例 09 治本：不再从源工程复制
    也无需引用重写——渲染产物按保留集合构造，结构一致性由构造保证，落位
    user/Project.uvprojx；密度守卫在渲染器：保留启动文件非 _md 大声失败，
    目标板 STM32F103C8T6 中密度）；mspm0 的 .cproject/.project 保留首份
    原样（CCS 按目录编译，无文件引用问题）。报告的路径集合必须与对比的
    判定范围完全一致（确认环节可能被用户修改动作与内容，但路径集合不变）。
    落盘中途失败不留半成品。
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
        if report.platform == PLATFORM_STM32:
            render_master_uvprojx(
                output_dir,
                *_render_inputs((*report.keep, *report.merge), comparison),
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
    # 落选份必须 exclude，由 _validate_startup_disposition 单独校验。
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
    _validate_startup_disposition(report, comparison)
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


def _validate_forced_exclusions(
    forced: set[str], report: DistillationReport, error_prefix: str
) -> None:
    """确定性剔除的文件必须恰好剔除一次：用户确认也不能改成保留 / 整合或
    删掉（删掉 = 黑盒消失，ADR 0001）。两种问题一次报全，各自带原因。

    类别表的确定性剔除由 _validate_category_disposition 泛化覆盖；本函数
    仅剩启动文件落选候选（决策 2：同一器件只需一份启动文件）在用。
    """
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


def _validate_startup_disposition(
    report: DistillationReport, comparison: ProjectComparison
) -> None:
    """启动文件去重结果不可改动作（决策 2）：保留份必须恰好保留一次，落选
    候选必须恰好剔除一次——同一器件只需一份启动文件（两份并存 = Reset_Handler
    重复定义），用户确认也不能改回或删掉。"""
    picked = _pick_startup(comparison)
    if picked is None:
        return
    if picked not in {d.path for d in report.keep}:
        raise MasterError(f"启动文件必须保留：{picked}")
    eliminated = sorted(set(comparison.startup_files) - {picked})
    _validate_forced_exclusions(
        set(eliminated), report, "落选启动文件必须剔除"
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
    幂等，归档重跑是全新条目）。llm_factory / reference_library_dir 只在报告
    含归档动作时按需取用（无归档的确认不要求 AI 配置，与现状一致）。
    """
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
            summaries = _prepare_archive(
                report, comparison, llm_factory, reference_library_dir
            )
        else:
            summaries = {}
        meta = import_master(
            masters_dir, report.platform, preview, sources=report.projects
        )
        if report.archive:
            # _prepare_archive 已拒绝 None（归档需要参考库目录）；此处为类型
            # 窄化断言，运行期恒真
            assert reference_library_dir is not None
            _write_archive_entries(
                report, comparison, reference_library_dir, summaries
            )
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return meta


def _prepare_archive(
    report: DistillationReport,
    comparison: ProjectComparison,
    llm_factory: Callable[[], LLM] | None,
    reference_library_dir: Path | None,
) -> dict[str, str]:
    """归档前置：校验配置与锚定、LLM 判定归档价值并生成条目简介（不写盘）。

    全部失败都在写盘前大声报错（MasterError，中文说明）：归档需要 AI 服务与
    参考文件库目录配置；锚定赛题编号格式非法（查库确认待赛题库工单 01 落地后
    接入）；AI 判定不配归档的文件被拒绝（一次性杂物 / 配置噪声不配归档）。
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
        try:
            validate_topic_anchor(decision.topic)
        except ReferenceError as exc:
            raise MasterError(str(exc)) from exc
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


def _write_archive_entries(
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
        for entry_dir in created:
            shutil.rmtree(entry_dir, ignore_errors=True)
        raise MasterError(
            f"母版已入库，但归档写入失败（已回滚本次归档条目，可重试确认）：{exc}"
        ) from exc


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
    """入库前的结构分析：平台配置文件缺失 / 编译链结构残缺硬失败，其余进警告。

    平台配置文件缺失说明母版无法被 IDE 打开，拒绝入库；Keil 母版还校验
    .uvprojx 的编译链完整性（配置节点齐全 + 工程树引用覆盖全部保留源码，
    见 _validate_keil_structure）——AI 整合出的 .uvprojx"XML 合法但结构残缺"
    曾照样入库，生成时才被 KeilPatcher 拒绝（判例 09）。构建产物目录等
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
    if platform == PLATFORM_STM32:
        _validate_keil_structure(master_dir)
    warnings: list[str] = []
    for name in sorted(BUILD_ARTIFACT_DIRS):
        if (master_dir / name).is_dir():
            warnings.append(f"母版含 {name}/ 构建产物目录，建议清理")
    return StructureAnalysis(platform=platform, warnings=tuple(warnings))


def _validate_keil_structure(master_dir: Path) -> None:
    """Keil 母版入库前的编译链结构校验（格式知识归 keil.py）。

    判例 09（用户实测）：AI 把两工程各自的 .uvprojx 判了 merge，整合产物
    XML 合法但组被清空（丢了启动文件 / system_stm32f10x.c 的引用）、连
    Cads/IncludePath 节点都没了——旧校验只查配置文件存在，坏母版照样入库、
    到生成时 KeilPatcher 才拒绝。校验失败在入库前大声拒绝（中文说明缺什么），
    兑现"绝不产出残缺工程"不变量。工程内保留源码清单按扫描同一套忽略规则
    计算（.git / 构建输出目录不进清单）。
    """
    expected: list[str] = []
    for path in sorted(master_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(master_dir).as_posix()
        if _is_ignored(rel):
            continue
        if path.suffix.lower() in (".c", ".s"):
            expected.append(rel)
    try:
        validate_project_structure(master_dir, expected)
    except KeilProjectError as exc:
        raise MasterError(f"母版 .uvprojx 结构不完整，拒绝入库：{exc}") from exc


def import_master(
    masters_dir: Path,
    platform: str,
    source_dir: Path,
    sources: Sequence[str] = (),
) -> MasterMeta:
    """母版入库：结构分析 → 复制到临时目录 → 整体替换同平台旧母版。

    每平台一个母版：目标已存在时整体更换。先分析后动盘，分析失败不落任何
    文件；旧母版先挪到备份目录再换入新母版，中途失败把备份换回来——既有
    母版在任意失败点都完好。旧母版被占用（Keil µVision / 文件资源管理器
    开着）时改名失败：绝不碰旧母版（rmtree 会把只锁住部分的旧母版删残，
    真实事故），抛中文占用说明。
    """
    _validate_store_key(platform)
    analysis = analyze_structure(source_dir, platform)
    masters_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = masters_dir / f".{platform}.importing"
    backup_dir = masters_dir / f".{platform}.backup"
    shutil.rmtree(temp_dir, ignore_errors=True)  # 清掉上次失败残留
    shutil.copytree(source_dir, temp_dir)
    target_dir = masters_dir / platform
    if target_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)
        if backup_dir.exists():
            # 备份目录清理不掉（被占用）：改名只会撞上非空目录，Windows 报
            # WinError 5，这里用中文讲清原因而不是裸抛拒绝访问
            raise MasterError(
                f"旧备份 {backup_dir.name} 目录清理失败（可能被占用），"
                "请先关闭占用程序后重试导入"
            )
    moved_to_backup = False
    try:
        if target_dir.exists():
            os.replace(target_dir, backup_dir)  # 旧母版先挪开
            moved_to_backup = True
        os.replace(temp_dir, target_dir)  # 新母版原子换入
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if moved_to_backup:
            # 旧母版已在备份目录：清掉半换入的新母版，把旧母版换回来
            shutil.rmtree(target_dir, ignore_errors=True)
            if backup_dir.exists():
                os.replace(backup_dir, target_dir)  # 回滚旧母版
            raise
        if target_dir.exists():
            # 旧母版从未挪动（改名失败）：绝不能碰它——rmtree 会把只锁住
            # 部分文件的旧母版删残（判例：真实事故，母版只剩空壳）
            raise MasterError(
                f"母版替换失败：旧母版目录 {target_dir.name} 被占用，无法挪动。"
                "通常是 Keil µVision 或文件资源管理器还打开着该目录，"
                "请先关闭再重试导入（杀毒软件扫描期间偶发，稍后重试亦可）"
            ) from None
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
    """递归查找工程配置文件：跳过 .git（任意层级）与构建产物目录——与扫描
    清单同一套忽略规则（_is_ignored：顶层 + Keil 输出目录任意层级）。"""
    return [
        p
        for p in project_dir.rglob(pattern)
        if ".git" not in p.parts
        and not _is_ignored(p.relative_to(project_dir).as_posix())
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
    """路径是否命中忽略目录：顶层忽略（.git / Debug / Release / Listings /
    Objects）+ Keil 输出目录任意层级匹配（NESTED_IGNORE_DIRS）——Keil 把
    Listings/Objects 建在 .uvprojx 所在目录，USER/ 工程时产物在 USER/ 下，
    顶层匹配会漏。"""
    parts = rel.split("/")
    if parts[0] in IGNORED_TOP_LEVEL_DIRS:
        return True
    return any(part in NESTED_IGNORE_DIRS for part in parts)


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
