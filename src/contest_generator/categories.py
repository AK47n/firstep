"""文件类别生命周期唯一出处：识别规则（残留 / 旧 main.c / 基础设施 / 二进制 /
工程配置文件）+ 类别表（RULE_CATEGORIES）+ 分类（classify）+ 启动文件跨工程
去重生命周期（_pick_startup / _validate_startup_disposition）。

架构深化 v5 三轴拆块（工单 01）：master.py 的类别概念全部收进本模块，master
只消费不定义（结构测试防回退）。识别规则即确定性处置：命中类别的文件不进
扫描清单、不进 AI 判定素材，但进报告并带规则化原因（ADR 0001：不做黑盒
消失）；启动文件候选是表内钩子（决策 2：跨工程去重），由扫描钩子单独记录、
各流水线表外处理。启动谓词（is_startup_candidate / is_md_startup）经蒸馏
适配器按平台取（工单 04：mspm0 显式 False），本模块不直连 keil。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Sequence

from .distill_adapters import get_distill_adapter
from .master_store import MasterError
from .report import ACTION_EXCLUDE, DistillationReport

# 扫描时忽略的目录：版本库与构建产物不是母版内容。Debug/Release（CCS 构建
# 输出）只在工程顶层出现，顶层匹配即可；Listings/Objects（Keil 默认输出目录）
# 建在 .uvprojx 所在目录——正点原子风格工程 .uvprojx 在 USER/ 下时，产物在
# USER/Listings、USER/Objects，必须按任意层级组件匹配（见 treewalk 模块）。
# Keil 的 .d 依赖文件落在这些输出目录里，整目录忽略已覆盖，名单里不需要裸
# ".d" 规则（见 RESIDUE_RULES 注释）。常量与跳过规则的唯一出处 = treewalk.py。

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
# 现写（格式知识在 keil.py，结构一致性由构造保证），.cproject/.project
# （mspm0，CCS 按目录编译、无文件引用问题，母版库尚无 mspm0 良好格式种子）
# 确定性保留首份原样、不现写不重写（决策 6）。与基础设施同模式：不进扫描
# 清单、不进 AI 判定素材、不读全文，但进报告 keep 清单并带规则化原因
# （ADR 0001：不做黑盒消失）；条目不可改动作（决策 7）。
UVPROJX_CONFIG_REASON = "工程配置文件：由确定性模板现写，保留文件全量入树"
CCS_CONFIG_REASON = "工程配置文件：由确定性规则保留首份原样（CCS 按目录编译）"


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


def classify(rel: str, path: Path, platform: str) -> tuple[str | None, bool]:
    """文件类别判定：表内第一命中返回 (类别 key, 是否启动候选)，None = 不命中。

    表内钩子（决策 2）：基础设施命中且是启动文件候选（startup_stm32f10x_*.s）
    时返回 is_startup=True——扫描单列到 startup_files（跨工程去重），不进
    基础设施组。启动候选谓词按平台取（工单 04，蒸馏适配器）：mspm0 显式
    False（TI/CCS 启动为 .c，不在基础设施词表）。表遍历知识收在本模块，
    扫描不再自写类别循环（Q7 裁决）。
    """
    for cat in RULE_CATEGORIES:
        if cat.reason_of(rel, path) is not None:
            if (
                cat.key == "infrastructure"
                and get_distill_adapter(platform).is_startup_candidate(rel)
            ):
                return cat.key, True
            return cat.key, False
    return None, False


def _pick_startup(startup_files: Sequence[str], platform: str) -> str | None:
    """跨工程启动文件去重（决策 2）：返回保留的那份，落选候选进 exclude。

    优先 startup_stm32f10x_md.s（与目标板 C8T6 中密度匹配）；没有 _md 则按
    路径排序取第一份（密度守卫在渲染器：保留份非 _md 时入库前大声失败）。
    _md 谓词按平台取适配器（工单 04）：mspm0 显式 False——启动去重对 mspm0
    不生效（无 .s 启动文件）。确定性：同一输入必然同一结果。
    """
    if not startup_files:
        return None
    md = sorted(
        c for c in startup_files if get_distill_adapter(platform).is_md_startup(c)
    )
    if md:
        return md[0]
    return sorted(startup_files)[0]


def _validate_startup_disposition(
    report: DistillationReport, startup_files: Sequence[str]
) -> None:
    """启动文件去重结果不可改动作（决策 2）：保留份必须恰好保留一次，落选
    候选必须恰好剔除一次——同一器件只需一份启动文件（两份并存 = Reset_Handler
    重复定义），用户确认也不能改回或删掉（删掉 = 黑盒消失，ADR 0001）。两种
    问题一次报全，各自带原因。类别表的确定性剔除由 master 的
    _validate_category_disposition 泛化覆盖；本函数只处理启动文件落选候选。
    """
    picked = _pick_startup(startup_files, report.platform)
    if picked is None:
        return
    if picked not in {d.path for d in report.keep}:
        raise MasterError(f"启动文件必须保留：{picked}")
    eliminated = sorted(set(startup_files) - {picked})
    moved = sorted(
        set(eliminated)
        & {
            d.path
            for d in (*report.keep, *report.merge, *report.exclude)
            if d.action != ACTION_EXCLUDE
        }
    )
    missing = sorted(set(eliminated) - {d.path for d in report.exclude})
    if moved or missing:
        problems = [f"{path}（被改为保留/整合）" for path in moved]
        problems += [f"{path}（报告中缺失）" for path in missing]
        raise MasterError(f"落选启动文件必须剔除：" + "、".join(problems))
