r"""编译错误回填自愈域模块（工单 compile-error-fix/01，决策记录 1-10）。

闭环"生成 → 编译 → 报错 → 修复"：把 Keil / CCS 编译报错文本贴回 → 解析文件
引用 → 从输出目录读真实文件内容（截断）→ LLM 逐条修复建议 → 直接写回工程
文件。域判决与单轮编排（run_fix_round，对照 selection.run_recommendation
先例）全部在本模块（纯函数、可单测）；llm.py 只做机械提取
（fix_compile_errors），webapp 只做薄壳装配（取参 + 转调 + SSE 包装）。

可逆性（决策记录 2）：写回前把本次要改的文件原内容备份到输出目录外
（工作根/fix-backups/<timestamp>/，默认 ~/.contest_generator/fix-backups/），
UI 提供「回滚本次修复」按钮（restore_backup）。

路径安全（决策记录 3/5）：解析出的路径 resolve 后必须仍在输出目录内（containment
兜底，`..` 穿越 / 绝对路径 / 反斜杠起始形态天然越界被拒），扩展名白名单
.c/.h/.s（大写 .S 一并接受）——越界即 FixError（登记 errors.py → 400 中文）。

解析基准（2026-08-12 真机验收补 + 工单 gmake-fix-path-resolution/01，见
_report_benchmarks）：CCS 报错路径相对工程根（.cproject 在根），直接按
output_dir 解析；UV4 报错路径相对 .uvprojx 所在子目录（`..\main.c(158)`
形态，uvprojx 在 user/ 而源文件在工程根）；gmake（tiarmclang）报错路径相对
构建工作目录（Debug/ 含 subdir_rules.mk，`../main.c` 形态）——先按工程根
解析，解析不出再按工程文件 / 构建工作目录基准解析，两基准全 miss 再走 `..`
前缀剥除兜底（逐级剥后按工程根解析），全部过 containment。

替换协议（决策记录 4 + 工单 fix-snippet-match/01 + fix-match-seam/01）：
old_snippet 精确匹配（含缩进）优先；精确匹配失败时走行首前缀归一化兜底
（old_snippet strip 后必须是文件某行 strip 后内容的行首前缀——容忍前导
缩进差异 / 行尾注释省略 / CRLF / 行尾空白，语句本体必须逐字一致），唯一
命中才应用（reason 标注「按行首前缀归一化匹配应用」）；仍未命中 / 多处
歧义一律跳过并报告「未应用」（不静默、不模糊替换、不做语义匹配）。匹配
判决单源在 match_snippet（纯函数），理由文案单源在 _reason_for——写回循环
只消费判决，改匹配规则 / 文案只动一处；改协议须同步 llm.FIX_SYSTEM_PROMPT
约束 2（对偶测试双端断言）。

**配置级判读（工单 02「mspm0 编译判读缺口」）**：SysConfig 的工程外设配置冲突
（真机 2026H 形态 `error: DC_MOTOR(/ti/driverlib/GPIO) associatedPins[3].pin:
Resource conflict`）没有文件没有行号、也不是 LLM 能修的（没有源码可改）——解析
时归 kind="syscfg_conflict"（伪路径 + line=0 + 结构化明细），修复链对它**短路**
（不调 llm.fix_compile_errors，直接给冲突清单 + 指路），并让汇总行大小写不敏感
（gmake / SysConfig 真机汇总形态是全小写 `7 error(s), 0 warning(s)`）。判据契约
见下文「编译报错条目类别」段；载荷条目形状单源 = parsed_error_entries。

本模块依赖方向：只 import budget / entry_store / events（叶子契约）与标准库，
是叶子模块——llm.py 反向依赖本模块（FixSuggestion 模型），禁止本模块 import
llm（截断标注与 llm.TRUNCATION_NOTICE 刻意同文，改动须同步）。wire 记账
原语与预算常量单源在 budget（工单 budget-wire-unification/01）。
"""

from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .budget import FIX_CONTEXT_TOTAL_BYTES, fit_wire_budget, wire_size
from .entry_store import is_unsafe_path
from .events import (
    EVENT_APPLY_RESULT,
    EVENT_FIX_START,
    EVENT_PARSE_DONE,
    ProgressEmitter,
    ProgressEvent,
    _emit,
)

if TYPE_CHECKING:
    from .llm import LLM  # 仅类型注解用（llm 运行时依赖本模块 FixSuggestion，反向导入成环）

# 可写白名单（决策记录 3）：仅源码文件（.c/.h/.s，大写 .S 一并接受）；
# 工程配置 / 构建产物（.uvprojx / .axf / .o 等）不参与修复（读上下文同样
# 只读源码——二进制产物进 LLM 上下文会污染提示词）
WRITABLE_EXTENSIONS = frozenset({".c", ".h", ".s", ".S"})

# 单文件上下文上限（决策记录 6）：500 行 / 50KB（字符），先到先截，带标注
FILE_CONTEXT_MAX_LINES = 500
FILE_CONTEXT_MAX_CHARS = 50 * 1024

# 全部文件上下文的总预算（wire 字节，工单 fix-request-budget/01）：常量与
# 推导单源迁至 budget.FIX_CONTEXT_TOTAL_BYTES（工单 budget-wire-unification/01，
# 与推荐侧共享同款 wire 记账原语）；本模块 re-export 保既有 import 面。
# 语义不变：超预算的文件不发送、在提示词里点名（防静默丢失）。

# 截断标注（决策记录 6）：与 llm.TRUNCATION_NOTICE 同句——本模块是 llm 的
# 依赖方向下游，不能反向 import，两句刻意同文（改动须同步，契约测试双端断言）
TRUNCATION_NOTICE = "按所见内容判断，不要脑补缺失部分"

# 备份目录名（决策记录 2）：工作根（模块库 / 母版库的父目录，默认
# ~/.contest_generator）下的 fix-backups/，在输出目录之外
FIX_BACKUPS_DIRNAME = "fix-backups"

# ---------------------------------------------------------------------------
# 编译报错条目类别（工单 02「mspm0 编译判读缺口」）：源码级 vs 配置级
# ---------------------------------------------------------------------------
#
# 源码级（kind="source"，缺省）：带「文件:行号」定位，可读文件内容、可由 LLM
# 给出 snippet 修复——既有 UV4 / CCS / tiarmclang 形态全归此类。
#
# 配置级（kind="syscfg_conflict"）：SysConfig 的工程外设配置冲突（真机 2026H
# 形态「error: DC_MOTOR(/ti/driverlib/GPIO) associatedPins[3].pin: Resource
# conflict」）——没有文件没有行号（问题在 .syscfg 的外设绑定），**不是 LLM 能
# 修的**（没有源码可改）。修复链识别为此类后不进 LLM 修复、不做「未定位到可
# 修复文件」的盲轮，直接逐条列出冲突 + 给用户指路（改引脚绑定 / 去冲突模块）。
SOURCE_ERROR_KIND = "source"
SYSCFG_CONFLICT_KIND = "syscfg_conflict"

# 配置级冲突条目的伪路径（工单 02）：前端错误列表据此显示「配置冲突（来自
# mspm0.syscfg）」，且**不会被当成可打开 / 可跳转的源码文件**——line=0 让行内
# 跳转天然跳过；修复链也不会把它当源码候选（后缀不在 WRITABLE_EXTENSIONS 白
# 名单内，且工程内不存在该相对路径的文件，双重不入选）。
SYSCFG_CONFLICT_PATH = "mspm0.syscfg"

# 配置级冲突的人话指路（工单 02 修复方向③）：**载荷文案单源**——修复轮 done 的
# notice 字段与本仓 CLI 验收脚本（generate_check.py）打印的指引都用它，改文案只
# 改这里。前端不方便逐字同源（core 模块不 import 静态常量），
# ui/fix-center-core.js 的 syscfgConflictStateText 与之**刻意同文**（同一句指路 +
# 界面专属尾句「重新『一键编译修复』」），改动须两侧同步——与 TRUNCATION_NOTICE
# 同款对偶（本仓既有先例：跨语言刻意同文 + 双端断言）。
SYSCFG_CONFLICT_NOTICE = (
    "SysConfig 资源冲突：本次编译的失败原因是工程外设配置冲突（引脚被两个模块"
    "同时占用），不是源码写错——属于配置级问题，没有源码可改，因此不进行"
    "AI 修复。请按下方冲突清单处理：改引脚绑定（模块实例卡里换脚 / 自动分配），"
    "或去掉冲突模块中的一个。"
)

# SysConfig 冲突段识别（工单 02 修复方向②）。两条形态（真机逐字）：
#   行级：`error: DC_MOTOR(/ti/driverlib/GPIO) associatedPins[3].pin: Resource conflict`
#   续行：`\tPA7/49 is currently in use by SERVO_PWM(/ti/driverlib/PWM) peripheral.ccp0Pin`
# 行级锚定行首（缩进容忍）——tiarmclang / clang 的 `path:line:col: error:` 形态
# 行首是路径，不会误命中；`(/(?P<periph>...))` 要求外设名以 / 开头（SysConfig
# 的 /ti/driverlib/... 形态），排除源码级 `foo.c(12): error #20:` 的括号数字。
_SYSCFG_CONFLICT_RE = re.compile(
    r"^\s*error:\s*(?P<name>[\w.-]+)\((?P<periph>/[^)]+)\)\s*"
    r"(?P<field>[\w.\[\]]+):\s*(?P<reason>Resource conflict)\s*$",
    re.IGNORECASE,
)
# 续行（被占用方）：`PA7/49 is currently in use by SERVO_PWM(/ti/driverlib/PWM) ...`
# ——引脚名 / 占用方模块名 / 占用方字段（peripheral.ccp0Pin / associatedPins[0].pin）
_SYSCFG_OCCUPY_RE = re.compile(
    r"^\s*(?P<pin>P[A-Z]\d+)(?:/\d+)?\s+is currently in use by\s+"
    r"(?P<by>[\w.-]+)\((?P<by_periph>/[^)]+)\)\s*(?P<by_field>[\w.\[\]]+)",
    re.IGNORECASE,
)

# 冲突条目 message 用的引脚角色中文名（配置级冲突不是源码报错，人话优先；
# 未登记形态原样带出字段名，不猜语义）
_SYSCFG_FIELD_LABELS = {
    "pin": "引脚",
    "rxpin": "接收脚",
    "txpin": "发送脚",
    "ccp0pin": "PWM 通道 0 脚",
    "ccp1pin": "PWM 通道 1 脚",
}


class FixError(Exception):
    """编译错误修复的业务失败（登记 errors.py → 400 中文）。"""


@dataclass(frozen=True)
class CompileError:
    """解析出的一条编译报错。

    path 为空串 = 未解析到文件引用（降级模式）；配置级冲突（SysConfig Resource
    conflict）path = SYSCFG_CONFLICT_PATH 伪路径、line = 0（无行号，见
    SYSCFG_CONFLICT_KIND 段注释）。

    name / periph / field / pin / by / by_periph 是配置级冲突的结构化明细
    （工单 02：验收标准要求「逐条带外设名」且前端 / CLI 能列出「DC_MOTOR ×
    SERVO_PWM 抢 PA7」这类人话冲突，不必反向解析 message）；源码级条目全为
    缺省值（名称 / 外设 / 引脚 / 占用方均为空串）。
    """

    path: str  # 相对路径（POSIX，反斜杠已归一）；可能为 ""（未解析到文件引用）
    line: int  # 行号；0 = 未知
    message: str  # 报错整行文本（原文；配置级为「人话 + 原文」）
    kind: str = SOURCE_ERROR_KIND  # 条目类别（source / syscfg_conflict）
    name: str = ""  # 配置级：报错模块实例名（如 DC_MOTOR）
    periph: str = ""  # 配置级：报错模块外设（如 /ti/driverlib/GPIO）
    field: str = ""  # 配置级：冲突字段（关联引脚号 / 外设脚）
    pin: str = ""  # 配置级：被抢的引脚（如 PA7）
    by: str = ""  # 配置级：占用方模块实例名（如 SERVO_PWM）
    by_periph: str = ""  # 配置级：占用方外设（如 /ti/driverlib/PWM）


@dataclass(frozen=True)
class FixSuggestion:
    """LLM 修复建议（snippet 替换协议，决策记录 4）。

    模型只产出建议（file / line / old_snippet / new_snippet / reason），
    路径判决与精确匹配都在本模块（apply_fixes）。
    """

    file: str  # 相对路径（POSIX）
    line: int  # 报错行号（提示用，替换不依赖它）
    old_snippet: str  # 语句本体与文件逐字一致（可省前导缩进 / 行尾注释，见
    # fix-snippet-match/01 前缀归一化兜底）
    new_snippet: str  # 替换后内容（空串 = 删除该片段 / 整行）
    reason: str  # 修复理由（中文，可空）


@dataclass(frozen=True)
class FixResult:
    """单处修复的应用结果：applied / skipped + 中文说明（未应用不静默）。"""

    file: str
    line: int
    status: str  # "applied" / "skipped"
    reason: str


@dataclass(frozen=True)
class SnippetMatch:
    """片段匹配判决（工单 fix-match-seam/01 决策记录 1）：match_snippet 的产物，
    写回循环只消费它（applied / skipped 二态 + 替换区间）。

    status 四态：exact（精确子串唯一匹配）/ normalized（行首前缀归一化唯一
    匹配）/ none（未命中）/ ambiguous（多处命中歧义，不模糊替换）。start /
    end / snippet 仅 applied（exact / normalized）时有效，否则 start=end=-1、
    snippet=""。count 供文案插值（歧义 / 未命中的计数，_reason_for 用）。

    via_normalized：ambiguous 的来源判别（True = 行首前缀归一化多处命中，
    False = 精确子串多处出现）——两种歧义的 reason 文案不同（决策 3 三条
    skipped 文案逐字保持），而 status 只有一种 ambiguous（决策 1 枚举），
    判别字段为实施补录（见工单实施记录；_reason_for 之外无其他消费方）。
    """

    status: str  # "exact" / "normalized" / "none" / "ambiguous"
    start: int  # 替换区间 [start, end)（仅 applied 有效；否则 -1）
    end: int
    snippet: str  # 替换文本（仅 applied 有效；否则 ""）
    count: int  # 歧义 / 未命中的计数（文案插值用）
    via_normalized: bool = False  # ambiguous 来源：True = 归一化多处命中


@dataclass(frozen=True)
class ApplyReport:
    """apply_fixes 的产物：备份编号（回滚入口）+ 逐处应用结果。"""

    backup_id: str  # 备份目录名（timestamp）；"" = 本次无任何应用，未备份
    results: tuple[FixResult, ...]


# 两种报错形态（决策记录 5）：UV4 `..\out\code\main.c(123): error #20: ...`
# 与 CCS / armclang `code/sub/mod.c:45: error: ...`（`path:line:col:` 带列号
# 也接受）。路径要求像文件名（含 . 扩展名，1-4 位字母数字后缀）、排除空白 /
# 括号 / 冒号——绝对路径（C:\ 带驱动器冒号）因此天然不匹配，相对形态才能
# resolve 到输出目录内。UV4 行号后可带列号（path(line,col)）。
_UV4_ERROR_RE = re.compile(
    r"(?P<path>[\w./\\-]+\.\w{1,4})\((?P<line>\d+)(?:,\d+)?\)\s*:"
)
_CCS_ERROR_RE = re.compile(
    r"(?P<path>[\w./\\-]+\.\w{1,4}):(?P<line>\d+)(?::\d+)?:\s*"
    r"(?:fatal\s+)?(?:error|warning)",
    re.IGNORECASE,
)

# UV4 汇总行（工单 compile-experience-ui/01）：标准形态 "1 Error(s), 0
# Warning(s)." 与真机形态 "0 Error(s) 0 Warning(s)."（无逗号）都命中；
# Warning 段缺省（如 "5 Error(s)."）时按 0 处理。**大小写放宽**（工单 02 修复
# 方向①）：gmake / SysConfig 线的真机汇总形态是全小写 "7 error(s), 0
# warning(s)"（第十六轮 A8 现场），只认 UV4 大写形态会把「编译失败」报成
# 「0 错 0 警」——数字前缀要求（`\d+\s+`）天然不误命中行级 error: 行。
_UV4_SUMMARY_RE = re.compile(
    r"(?P<errors>\d+)\s+Error\(s\)(?:[,\s]+(?P<warnings>\d+)\s+Warning\(s\))?",
    re.IGNORECASE,
)


def parse_compile_errors(error_text: str) -> tuple[CompileError, ...]:
    """逐行解析编译报错 → CompileError 列表（路径归一为 POSIX）。

    三类形态都试（UV4 / CCS / SysConfig 配置级，混合多文件自然兼容）；解析不到
    文件引用且不是配置级冲突的行不产出条目——该行文本保留在报错全文里（随 LLM
    上下文注入，降级不丢信息）。垃圾文本（无匹配）→ 空元组，不崩。反斜杠开头
    （绝对形态）视为未解析到引用（防把绝对路径当相对路径）。

    SysConfig 配置级冲突（工单 02）：`error: NAME(外设) 字段: Resource conflict`
    行 + 紧随的「引脚 is currently in use by 占用方(外设) 字段」续行合成一条
    条目——path = SYSCFG_CONFLICT_PATH（伪路径，非源码）、line = 0、kind =
    syscfg_conflict、message = 人话（谁抢谁 + 引脚 + 指路）+ 两行原文逐字。
    解析优先级：先配置级（形态更具体），再行级两类。
    """
    parsed: list[CompileError] = []
    lines = error_text.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        conflict = _SYSCFG_CONFLICT_RE.match(lines[index])
        if conflict is not None:
            # 续行（被占用方）只在紧邻下一行时消费；否则本条只有报错侧信息
            occupied = None
            if index + 1 < len(lines):
                occupied = _SYSCFG_OCCUPY_RE.match(lines[index + 1])
            parsed.append(_syscfg_conflict_entry(conflict, occupied, lines, index))
            index += 2 if occupied is not None else 1
            continue
        match = _UV4_ERROR_RE.search(stripped) or _CCS_ERROR_RE.search(stripped)
        if match is None:
            index += 1
            continue
        path = match.group("path").replace("\\", "/")
        if path.startswith("/"):
            index += 1
            continue  # 绝对形态：解析不到相对文件引用（该行降级）
        parsed.append(
            CompileError(path=path, line=int(match.group("line")), message=stripped)
        )
        index += 1
    return tuple(parsed)


def _syscfg_conflict_entry(
    conflict: re.Match[str],
    occupied: re.Match[str] | None,
    lines: Sequence[str],
    index: int,
) -> CompileError:
    """SysConfig 冲突 → CompileError（人话 + 原文逐字，工单 02 修复方向②）。

    message 三段：① 人话冲突句（`DC_MOTOR 与 SERVO_PWM 抢 PA7（引脚）：资源
    冲突，引脚绑定需去重`——占用方缺失时只报报错侧）；② 指路一句（改引脚绑定 /
    去冲突模块）；③ 原文行逐字（可追溯，用户可拿去搜 / 贴给 AI）。
    """
    name = conflict.group("name")
    field = conflict.group("field")
    detail = occupied.group(0).strip() if occupied is not None else ""
    pin = occupied.group("pin") if occupied is not None else ""
    by = occupied.group("by") if occupied is not None else ""
    label = _SYSCFG_FIELD_LABELS.get(field.rsplit(".", 1)[-1].lower(), field)
    if occupied is not None:
        # 被占用方续行解析成功才有 of/occupied（pin=脚、by=占用方模块）
        headline = f"{name} 与 {by} 抢 {pin}（{label}）：资源冲突，引脚绑定需去重"
    else:
        # 只有报错行（无续行 / 续行形态未识别）：字段名如实带出，不猜引脚
        headline = f"{name} 的 {label} {field}：资源冲突（SysConfig 工程外设配置冲突）"
        pin = by = ""
    raw = [lines[index].strip()]
    if detail:
        raw.append(detail)
    return CompileError(
        path=SYSCFG_CONFLICT_PATH,
        line=0,
        message=headline
        + "。请改引脚绑定（模块实例卡换脚 / 自动分配）或去掉冲突模块中的一个。"
        "原文：" + " / ".join(raw),
        kind=SYSCFG_CONFLICT_KIND,
        name=name,
        periph=conflict.group("periph"),
        field=field,
        pin=pin,
        by=by,
        by_periph=occupied.group("by_periph") if occupied is not None else "",
    )


def _is_syscfg_conflict(error: CompileError) -> bool:
    """条目是否配置级冲突（判据单源）：syscfg_conflicts 两个分支共用，
    禁在别处再写一遍 `kind == SYSCFG_CONFLICT_KIND`。"""
    return error.kind == SYSCFG_CONFLICT_KIND


def syscfg_conflicts(
    error_text: str, parsed_errors: Sequence[CompileError] = ()
) -> tuple[CompileError, ...]:
    """配置级冲突清单（工单 02 修复方向③）：修复链 / 展示层的分流数据源单源。

    优先取已解析条目里的配置级条目（parsed_errors 非空即权威——调用方已解析过
    一遍，不重复解析）；parsed_errors 为空而 error_text 非空时按同一条正则现
    扫描一次（只拿到编译输出原文的调用方也能取到冲突清单）。两条路共用
    _SYSCFG_CONFLICT_RE，判据单源（禁另写正则）。
    """
    entries = parsed_errors or parse_compile_errors(error_text or "")
    return tuple(e for e in entries if _is_syscfg_conflict(e))


def should_skip_llm_fix(
    source_candidates: Sequence[str], conflicts: Sequence[CompileError]
) -> bool:
    """配置级冲突短路判据（工单 02）：**同一输入必得同一结论**，域层（run_fix_round）
    与本仓 CLI 验收脚本（generate_check.run_fix_loop）共用本函数，禁各写一份。

    判据 = 有配置级冲突（SysConfig Resource conflict）且没有源码级候选文件。
    并存「源码错 + 配置冲突」时**不短路**：LLM 修得动的是源码错（工单原文
    「这类冲突不是 LLM 能修的（没有源码可改）」，并未要求把源码错一起放弃），
    冲突条目仍随 parsed / syscfg_conflicts 如实带出给用户。两者皆空判 False
    （无候选但也无冲突 = 纯降级形态，走既有的「只按报错全文修复」路径）。
    """
    return bool(conflicts) and not source_candidates


def parsed_error_entries(
    errors: Sequence[CompileError],
) -> list[dict[str, Any]]:
    """CompileError → 载荷条目（[{path, line, message}] + 配置级带 kind）。

    载荷形状单源（工单 02）：/api/compile 的 parsed_errors、修复轮 done 的
    parsed、深化摘要的 parsed_errors 三处共用本函数，禁各写一份。源码级条目
    保持既有三字段（旧前端 / 旧契约零改动）；配置级条目追加 kind——前端据此
    区分「可跳转的源码错误」与「不可跳转的配置冲突」（kind 缺省语义 = 源码级，
    与 CompileError.kind 缺省一致）。
    """
    entries: list[dict[str, Any]] = []
    for error in errors:
        entry: dict[str, Any] = {
            "path": error.path,
            "line": error.line,
            "message": error.message,
        }
        if error.kind != SOURCE_ERROR_KIND:
            entry["kind"] = error.kind
        entries.append(entry)
    return entries


def summarize_compile_output(
    error_text: str, parsed_errors: Sequence[CompileError]
) -> dict[str, int]:
    """编译输出数字汇总（工单 compile-experience-ui/01）：{errors, warnings}。

    汇总行优先——命中即取汇总值（errors / warnings 都来自汇总行，与行级计数
    可能不一致，以汇总为准）；未命中（CCS / gmake 无汇总行）退行级：
    len(parsed_errors) 为底，warning 条数 = 消息含 "warning"（大小写不敏感）
    计数，errors = 总数 − warnings。垃圾 / 空文本 → {0, 0}，不崩。
    汇总行识别大小写放宽（工单 02 修复方向①）：UV4 的 "7 Error(s), 0
    Warning(s)" 与 gmake / SysConfig 的真机全小写 "7 error(s), 0 warning(s)"
    同判——这是「编译失败被报成 0 错 0 警」的第一处缺口。
    与 parse_compile_errors 同文件（解析域单源），展示层汇总与修复层解析
    共用同一份编译输出，禁止调用方另写正则。
    """
    match = _UV4_SUMMARY_RE.search(error_text or "")
    if match is not None:
        return {
            "errors": int(match.group("errors")),
            "warnings": int(match.group("warnings") or 0),
        }
    warnings = sum(1 for error in parsed_errors if "warning" in error.message.lower())
    return {"errors": len(parsed_errors) - warnings, "warnings": warnings}


def _report_benchmarks(output_dir: Path) -> tuple[Path, ...]:
    """报错路径的解析基准目录（2026-08-12 真机验收补）：UV4 报错路径相对
    .uvprojx 所在目录（stm32 母版产物 uvprojx 在 user/ 子目录、源文件相对它
    以 `..\\` 引用），CCS 的 .cproject 一般在工程根；gmake（tiarmclang）报错
    路径相对构建工作目录（工单 gmake-fix-path-resolution/01：mspm0 产物
    Debug/ 含 subdir_rules.mk，报错形态 `../main.c` 相对它，该目录加入基准后
    `(Debug / "../main.c").resolve()` = 工程根/main.c 直接命中）。探测
    output_dir 下所有工程文件（.uvprojx / .cproject）的父目录与
    subdir_rules.mk 所在目录（构建工作目录），去重保序；找不到 → 空（只走
    工程根相对解析，兼容无工程文件的纯源文件输出目录）。
    """
    root = output_dir.resolve()
    benchmarks: list[Path] = []
    for proj in output_dir.rglob("*"):
        if proj.is_dir():
            continue
        name = proj.name.lower()
        if name == ".cproject" or name.endswith(".uvprojx"):
            parent = proj.resolve().parent
            if parent not in benchmarks:
                benchmarks.append(parent)
    # 构建工作目录基准（工单 gmake-fix-path-resolution/01 决策记录 2）：
    # 每个 subdir_rules.mk（Debug/ 根构建规则 + 逐模块目录）的父目录都是
    # gmake 报错路径的解析基准——工程根在基准内，containment 兜底不变
    for rules in output_dir.rglob("subdir_rules.mk"):
        parent = rules.resolve().parent
        if parent not in benchmarks:
            benchmarks.append(parent)
    return tuple(benchmarks)


def collect_candidate_paths(
    output_dir: Path, errors: Sequence[CompileError]
) -> tuple[str, ...]:
    """报错命中的可修复文件（决策记录 3/5）：白名单扩展名 + resolve 后仍在
    输出目录内 + 文件真实存在。任一不满足 → 该条报错降级（整段错误文本仍在
    LLM 上下文，只是没有文件内容）。返回去重保序的相对路径（POSIX，相对
    output_dir）。

    解析基准（2026-08-12 真机验收补 + 工单 gmake-fix-path-resolution/01）：
    先按工程根直接解析（CCS 相对形态）；解析不出（UV4 `..\\` 相对形态，相对
    工程根会越过 root）再按 _report_benchmarks 的工程文件 / 构建工作目录基准
    解析（gmake `../main.c` 形态经 Debug/ 基准命中工程根）；仍不中再走
    `..` 前缀剥除兜底（逐级剥后按工程根解析）。安全由 containment 兜底：
    三种解析都 resolve 后判定是否在 root 内——`..` 逃逸 / 绝对路径 /
    反斜杠起始形态天然越界被拒（不再依赖 is_unsafe_path 的字符串判定）。
    """
    root = output_dir.resolve()
    benchmarks = _report_benchmarks(output_dir)
    seen: set[str] = set()
    candidates: list[str] = []
    for error in errors:
        path = error.path
        if not path:
            continue
        if Path(path).suffix not in WRITABLE_EXTENSIONS:
            continue  # 非源码文件（.axf / .uvprojx 等）无修复价值
        target = _resolve_in_root(output_dir, root, path, benchmarks)
        if target is None:
            continue  # 越出输出目录 / 读取不到 → 降级
        rel = target.relative_to(root).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        candidates.append(rel)
    return tuple(candidates)


def _resolve_in_root(
    output_dir: Path,
    root: Path,
    path: str,
    benchmarks: Sequence[Path],
) -> Path | None:
    """报错路径 → 输出目录内真实文件（工程根 + 工程文件 / 构建目录基准 + `..`
    前缀剥除兜底都试）；解析不到返回 None。"""
    if not is_unsafe_path(path):
        target = (output_dir / path).resolve()
        if target.is_relative_to(root) and target.is_file():
            return target
    for bench in benchmarks:
        target = (bench / path).resolve()
        if target.is_relative_to(root) and target.is_file():
            return target
    return _resolve_dotdot_stripped(root, path)


def _resolve_dotdot_stripped(root: Path, path: str) -> Path | None:
    """`..` 前缀剥除兜底（工单 gmake-fix-path-resolution/01 决策记录 2 双保险）：
    两基准都 miss 后，报错路径带 `../`（或 `..\\`，先归一为 POSIX）前缀时逐级
    剥前缀按工程根解析——每剥一级试 `(root / stripped).resolve()`，
    containment（is_relative_to(root)）+ is_file 判定与两基准一致；剥到无前缀
    仍不中 → None。覆盖更深层级 / 未知构建目录形态（基准探测不到时报错路径
    仍带 `../` 前缀）。UV4 通路不受影响：`..\\main.c(N)` 形态既有基准已命中，
    本兜底只在两基准全 miss 后才走。
    """
    norm = path.replace("\\", "/")
    while norm.startswith("../"):
        norm = norm[3:]
        if not norm:
            return None
        target = (root / norm).resolve()
        if target.is_relative_to(root) and target.is_file():
            return target
    return None


def resolve_source_path(output_dir: Path, path: str) -> Path | None:
    """展示层源码行接口的路径判决（工单 compile-experience-ui/01）：复用
    collect_candidate_paths 同款双基准解析（工程根 + 工程文件基准目录）与
    containment 校验——resolve 后必须在输出目录内，`..` 穿越 / 绝对路径
    越界拒绝。解析不到（不存在 / 越界）返回 None，调用方转 400 中文。
    与修复域共用同一套路径判决，杜绝展示 / 修复两套解析漂移。
    """
    return _resolve_in_root(
        output_dir, output_dir.resolve(), path, _report_benchmarks(output_dir)
    )


def read_file_contexts(
    output_dir: Path, paths: Sequence[str]
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """读取候选文件内容（决策记录 6 + 工单 fix-request-budget/01）：单文件
    500 行 / 50KB 双上限截断（带标注，模型明确知道读到的是截断内容），全部
    文件合计不超 FIX_CONTEXT_TOTAL_BYTES **wire 字节**（json.dumps 序列化
    口径，与 llm._chat 发送前预检一致）——超预算的当前文件按字节预算截取
    最长前缀（fit_wire_budget）+ 标注，超预算的剩余文件不读取、单独返回
    （llm 提示词点名，不静默丢失）。读取失败（磁盘错误 / 编码不可解）跳过
    （该文件降级）。返回 ((相对路径, 内容), ...) 与（未发送的相对路径列表）。
    """
    contents: list[tuple[str, str]] = []
    dropped: list[str] = []
    budget = FIX_CONTEXT_TOTAL_BYTES
    for path in paths:
        if budget <= 0:
            dropped.append(path)
            continue
        try:
            content = (output_dir / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # 读取失败 → 该文件降级（决策记录 5）
        content = _truncate_file(content)
        if wire_size(content) > budget:
            content = fit_wire_budget(content, budget)
            content += "\n……（上下文预算限制，仅截取前段）……\n"
        budget -= wire_size(content)
        contents.append((path, content))
    return tuple(contents), tuple(dropped)


def _truncate_file(content: str) -> str:
    """单文件截断（决策记录 6）：500 行 / 50KB 双上限（先到先截），带标注。
    未超限原样返回（截断只影响发送素材，不改磁盘文件）。
    """
    total_lines = content.count("\n") + 1  # 原文统计（标注用，先记再截）
    total_chars = len(content)
    cut = False
    if total_lines > FILE_CONTEXT_MAX_LINES:
        content = "\n".join(content.split("\n")[:FILE_CONTEXT_MAX_LINES])
        cut = True
    if len(content) > FILE_CONTEXT_MAX_CHARS:
        content = content[:FILE_CONTEXT_MAX_CHARS]
        cut = True
    if cut:
        return (
            content
            + f"\n……（内容过长，已截断：仅展示前 {FILE_CONTEXT_MAX_LINES} 行 / "
            f"{FILE_CONTEXT_MAX_CHARS} 字符，原文共 {total_lines} 行 {total_chars} "
            f"字符；{TRUNCATION_NOTICE}）……\n"
        )
    return content


def _snippet_normalized_lines(old_snippet: str) -> tuple[str, ...]:
    """old_snippet 归一化后的行序列（工单 fix-snippet-match/01）：整体 strip +
    逐行 strip + 去空行。与 _normalized_hits 的匹配判据共用同一函数，杜绝
    匹配与替换两端行数不一致。
    """
    return tuple(ln.strip() for ln in old_snippet.strip().splitlines() if ln.strip())


def _normalized_hits(content: str, old_snippet: str) -> tuple[int, ...]:
    """行首前缀归一化匹配（工单 fix-snippet-match/01）：返回命中的起始行号
    （0-based）元组。判据——old_snippet 归一化行序列（strip + 去空行）逐行
    必须是文件对应行 strip() 后内容的行首前缀，多行片段 = 连续行块逐行前缀。
    语句本体任何字符差异（含行内空白重组）→ 前缀比较失败，天然被拒；歧义
    （多处命中）由调用方跳过。空片段 / 无命中 → 空元组。
    """
    snippet_lines = _snippet_normalized_lines(old_snippet)
    if not snippet_lines:
        return ()
    file_lines = content.splitlines()
    hits: list[int] = []
    for i, line in enumerate(file_lines):
        if not line.strip().startswith(snippet_lines[0]):
            continue
        j = 1
        k = i + 1
        while j < len(snippet_lines) and k < len(file_lines):
            if not file_lines[k].strip().startswith(snippet_lines[j]):
                break
            j += 1
            k += 1
        if j == len(snippet_lines):
            hits.append(i)
    return tuple(hits)


def _line_span(content: str, start_line: int, n_lines: int) -> tuple[int, int]:
    """内容中第 start_line 行起连续 n_lines 行的 [start, end) 字符区间（含行尾
    换行；末行无换行则到内容末尾）。归一化替换 = 匹配行的原始全文被
    new_snippet 替换（new_snippet="" 即删整行/整块，注释随行删除）。
    """
    lines = content.splitlines(keepends=True)
    pos = 0
    offsets: list[int] = []
    for ln in lines:
        offsets.append(pos)
        pos += len(ln)
    start = offsets[start_line]
    end = start + sum(len(ln) for ln in lines[start_line : start_line + n_lines])
    return start, end


def _preserve_line_ending(new_snippet: str, span: str) -> str:
    """归一化替换的换行保护：span 以行尾换行结尾而 new_snippet 没有行尾时，
    补回原行尾——整行替换语义下 new_snippet 通常是裸语句（无 \\n），不补会把
    下一行顶上来拼成一行。new_snippet 为空串（删整行）不补（含换行整块删除）。
    """
    if not new_snippet or new_snippet.endswith("\n") or not span:
        return new_snippet
    ending = re.search(r"\r?\n\Z", span)
    if ending is None:
        return new_snippet
    return new_snippet + ending.group(0)


def match_snippet(content: str, old_snippet: str, new_snippet: str) -> SnippetMatch:
    """片段匹配判决（工单 fix-match-seam/01 决策记录 1，语义逐字迁自 apply_fixes
    写回循环）：old_snippet 精确子串唯一匹配 → exact（替换区间 = 子串区间，
    snippet = new_snippet 原样）；精确 0 次 → 行首前缀归一化兜底（old_snippet
    归一化行序列逐行必须是文件对应行 strip 后内容的行首前缀——容忍前导缩进 /
    行尾注释省略 / CRLF / 行尾空白，语句本体须逐字一致），唯一匹配 →
    normalized（替换区间 = 行区间，行尾换行保护）；仍未命中 → none；多处
    命中（精确子串多处出现 / 归一化多处命中）→ ambiguous（不模糊替换，调用
    方跳过并报告未应用——唯一匹配是应用前提）。纯函数：零文件系统，判决
    契约可单测。协议文本单源对偶于 llm.FIX_SYSTEM_PROMPT 约束 2（改一侧
    即红，见测试）。
    """
    count = content.count(old_snippet)
    if count == 1:
        index = content.find(old_snippet)
        return SnippetMatch(
            status="exact",
            start=index,
            end=index + len(old_snippet),
            snippet=new_snippet,
            count=1,
        )
    if count > 1:
        return SnippetMatch(
            status="ambiguous", start=-1, end=-1, snippet="", count=count
        )
    normalized = _normalized_hits(content, old_snippet)
    if len(normalized) == 1:
        start, end = _line_span(
            content, normalized[0], len(_snippet_normalized_lines(old_snippet))
        )
        snippet = _preserve_line_ending(new_snippet, content[start:end])
        return SnippetMatch(
            status="normalized", start=start, end=end, snippet=snippet, count=1
        )
    if len(normalized) == 0:
        return SnippetMatch(status="none", start=-1, end=-1, snippet="", count=0)
    return SnippetMatch(
        status="ambiguous",
        start=-1,
        end=-1,
        snippet="",
        count=len(normalized),
        via_normalized=True,
    )


def _reason_for(match: SnippetMatch) -> str:
    """判决 → reason 文案（工单 fix-match-seam/01 决策记录 3，单源）：exact
    无文案（""）；normalized 标注「按行首前缀归一化匹配应用」；none / 歧义
    三条 skipped 文案逐字保持（决策 2，count 插值不变）。改文案只动这里。
    """
    if match.status == "exact":
        return ""
    if match.status == "normalized":
        return "按行首前缀归一化匹配应用"
    if match.status == "none":
        return (
            "未应用：文件内未找到 old_snippet（精确匹配失败，"
            "可能缩进 / 内容不一致）"
        )
    if match.via_normalized:
        return (
            f"未应用：old_snippet 按行首前缀归一化在文件内"
            f"多处命中（{match.count} 处，歧义，要求唯一匹配）"
        )
    return (
        f"未应用：old_snippet 在文件内出现 {match.count} 次"
        "（歧义，要求唯一匹配）"
    )


def apply_fixes(
    fixes: Sequence[FixSuggestion],
    output_dir: Path,
    backup_root: Path,
) -> ApplyReport:
    """snippet 替换协议（决策记录 4 + 工单 fix-snippet-match/01 + fix-match-seam/01）：
    匹配判决单源在 match_snippet（精确优先 → 行首前缀归一化兜底 → 未命中 /
    歧义跳过，判决契约见其 docstring），本函数只消费判决并写回——改匹配规则
    或理由文案（_reason_for）不动本函数。

    路径判决（决策记录 3）：file 扩展名白名单、is_unsafe_path 防穿越、resolve
    后仍在输出目录内、目标文件存在——任一不满足 → FixError（登记 errors.py
    → 400 中文，大声失败不静默跳过：LLM 输出不可信，越界路径是协议违约）。

    写回（决策记录 2）：先在内存里完成全部替换 → 把本次实际要改的文件原内容
    备份（输出目录外）→ 全部备份成功后才写回（备份失败 = 一个文件都不写）。
    同文件多处修复按顺序作用于演化中的内容。
    """
    for fix in fixes:
        _validate_fix_file(fix.file, output_dir)

    # 按文件分组（保序），逐处匹配
    by_file: dict[str, list[FixSuggestion]] = {}
    for fix in fixes:
        by_file.setdefault(fix.file, []).append(fix)

    results: list[FixResult] = []
    new_contents: dict[str, str] = {}  # 有应用的文件的相对路径 → 新内容
    for file, file_fixes in by_file.items():
        target = (output_dir / file).resolve()
        content = target.read_text(encoding="utf-8", errors="replace")
        for fix in file_fixes:
            # 匹配判决只经 match_snippet（工单 fix-match-seam/01）：写回循环
            # 不碰匹配原语，只消费判决 + 理由文案（_reason_for 单源）
            match = match_snippet(content, fix.old_snippet, fix.new_snippet)
            if match.status in ("exact", "normalized"):
                content = (
                    content[: match.start] + match.snippet + content[match.end :]
                )
                results.append(
                    FixResult(
                        file=file,
                        line=fix.line,
                        status="applied",
                        reason=_reason_for(match),
                    )
                )
                new_contents[file] = content
            else:
                results.append(
                    FixResult(
                        file=file,
                        line=fix.line,
                        status="skipped",
                        reason=_reason_for(match),
                    )
                )

    if new_contents:
        backup_id = backup_files(
            backup_root,
            {file: (output_dir / file).resolve() for file in new_contents},
        )
        for file, content in new_contents.items():
            (output_dir / file).write_text(content, encoding="utf-8")
    else:
        backup_id = ""
    return ApplyReport(backup_id=backup_id, results=tuple(results))


def _validate_fix_file(file: str, output_dir: Path) -> None:
    """修复目标路径判决（决策记录 3）：白名单扩展名 + is_unsafe_path + resolve
    后仍在输出目录内 + 文件存在。任一不满足 → FixError（400 中文）。
    """
    if Path(file).suffix not in WRITABLE_EXTENSIONS:
        raise FixError(f"修复目标不是可写文件类型（仅 .c/.h/.s）：{file}")
    if is_unsafe_path(file):
        raise FixError(f"修复目标路径不安全：{file}")
    target = (output_dir / file).resolve()
    if not target.is_relative_to(output_dir.resolve()):
        raise FixError(f"修复目标在输出目录之外：{file}")
    if not target.is_file():
        raise FixError(f"修复目标文件不存在：{file}")


def fix_backup_root(work_root: Path) -> Path:
    """备份根（决策记录 2）：输出目录外、工具工作目录下——与赛题库 / 参考库
    同源推导（工作根 = 模块库 / 母版库的父目录，默认 ~/.contest_generator）。
    """
    return work_root / FIX_BACKUPS_DIRNAME


def backup_files(backup_root: Path, files: Mapping[str, Path]) -> str:
    """写回前备份（决策记录 2）：把本次要改的文件原内容复制到
    <backup_root>/<timestamp>/<相对路径>（输出目录外，路径镜像），返回备份 id
    （timestamp 目录名 = 回滚入口）。备份根与备份目录不存在则创建。
    """
    backup_id = _unique_backup_id(backup_root)
    target_dir = backup_root / backup_id
    for rel, source in files.items():
        destination = target_dir / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return backup_id


def _unique_backup_id(backup_root: Path) -> str:
    """时间戳备份目录名（秒粒度，冲突加序号）——回滚入口须稳定可复述。"""
    base = time.strftime("%Y%m%d-%H%M%S")
    candidate = base
    counter = 2
    while (backup_root / candidate).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def restore_backup(backup_root: Path, backup_id: str, output_dir: Path) -> tuple[str, ...]:
    """回滚（决策记录 2）：把 <backup_root>/<backup_id>/ 下镜像的备份文件复制
    回输出目录。backup_id 必须是安全目录名（is_unsafe_path 拒绝对 `..` / 绝对
    路径）；备份目录或输出目录不存在 → FixError（400 中文）。返回恢复的文件
    相对路径（POSIX）。
    """
    if is_unsafe_path(backup_id):
        raise FixError(
            f"备份编号不合法（{backup_id}）：请从任务结果里重新点击「回滚」获取"
            "有效编号，不要手改编号。"
        )
    backup_dir = backup_root / backup_id
    if not backup_dir.is_dir():
        raise FixError(
            f"备份不存在（{backup_id}）：备份可能已被清理或任务已完成——"
            "如需撤销，请重新生成后再回滚。"
        )
    if not output_dir.is_dir():
        raise FixError(f"输出目录不存在：{output_dir}")
    root = output_dir.resolve()
    restored: list[str] = []
    for source in sorted(backup_dir.rglob("*")):
        if not source.is_file():
            continue
        rel = source.relative_to(backup_dir).as_posix()
        if is_unsafe_path(rel):
            raise FixError(f"备份内包含非法路径：{rel}")
        destination = output_dir / rel
        if not destination.resolve().is_relative_to(root):
            raise FixError(f"备份文件越出输出目录：{rel}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        restored.append(rel)
    return tuple(restored)


def _validate_previous_fixes(
    previous_fixes: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """上一轮应用结果的形状校验（工单 fix-loop-progress/01 决策记录 3）：每项
    dict + file / status / reason 字符串、line 整数、status ∈ {applied,
    skipped}——非法 → FixError（登记 errors.py → 400 中文）。回喂载荷来自
    前端循环透传，形状违约大声失败不静默丢弃（协议错误，用户可修正重试）。
    返回规整后的元组（逐项只留四字段），缺省空元组 = 行为与现有一致。
    """
    if not isinstance(previous_fixes, Sequence) or isinstance(
        previous_fixes, (str, bytes)
    ):
        raise FixError("previous_fixes 必须是数组")
    validated: list[Mapping[str, Any]] = []
    for index, item in enumerate(previous_fixes):
        if not isinstance(item, Mapping):
            raise FixError(f"previous_fixes[{index}] 必须是对象")
        file = item.get("file")
        line = item.get("line")
        status = item.get("status")
        reason = item.get("reason")
        if not isinstance(file, str):
            raise FixError(f"previous_fixes[{index}] 的 file 必须是字符串")
        if not isinstance(line, int):
            raise FixError(f"previous_fixes[{index}] 的 line 必须是整数")
        if not isinstance(status, str) or status not in ("applied", "skipped"):
            raise FixError(
                f"previous_fixes[{index}] 的 status 必须是 applied 或 skipped"
            )
        if not isinstance(reason, str):
            raise FixError(f"previous_fixes[{index}] 的 reason 必须是字符串")
        validated.append(
            {"file": file, "line": line, "status": status, "reason": reason}
        )
    return tuple(validated)


def run_fix_round(
    llm: LLM,
    *,
    error_text: str,
    output_dir: Path,
    backup_root: Path,
    problem_text: str = "",
    platform: str = "",
    module_slugs: Sequence[str] = (),
    main_c: str = "",
    previous_fixes: Sequence[Mapping[str, Any]] = (),
    emit: ProgressEmitter | None = None,
) -> dict[str, Any]:
    """一轮修复的完整编排（工单 fix-session-homing/01）：/api/fix-errors 路由
    闭包内五步管线的域内归位（对照 selection.run_recommendation 先例）。

    五步：parse_compile_errors → collect_candidate_paths → read_file_contexts
    （dropped 保留）→ llm.fix_compile_errors → apply_fixes。事件序列契约：
    parse_done（error_count / file_count / conflicts：配置级冲突条目，工单 02）
    → fix_start（LLM 修复中，分钟级）→ apply_result…（逐处应用结果）——emit 走
    旁路（_emit，发射失败不影响主流程），None = 不发射（单测直调形态）。

    **配置级冲突短路（工单 02 修复方向③）**：报错里全是 SysConfig Resource
    conflict（没有源码候选）时，这条链没有可改的源码——不进 llm.fix_compile_
    errors（不白烧一轮分钟级调用，也不产出「未定位到可修复文件」的误导文案），
    直接把冲突清单 + 指路带出（syscfg_conflicts / notice）。事件序列仍是
    parse_done → fix_start（前端靠 parse_done.conflicts 就能给准话，状态机不
    引入新事件类型）。判据单源 = should_skip_llm_fix（CLI 验收脚本同用）。

    previous_fixes（工单 fix-loop-progress/01）：上一轮 done 载荷的 fixes
    数组（[{file, line, status, reason}]），形状校验（_validate_previous_fixes，
    非法 → FixError → 400 中文）后只进 LLM 素材（不发射事件、不改 done
    载荷形状）——缺省空 = 行为与现有一致（贴文本模式 / 旧调用零改动）。

    done 载荷作为返回值（形状的家在此，webapp docstring 只指向本函数）：
    output_dir（str，原样传入）/ backup_id（本次备份编号，无应用 = ""）/
    degraded（未定位到可修复文件）/ parsed（parsed_error_entries：源码级
    {path, line, message}，配置级多一个 kind）/
    fixes（[{file, line, status, reason}]，逐处应用结果）/ syscfg_conflicts
    （[{name, pin, by, message}]，配置级冲突清单，无冲突 = []）/ notice
    （配置级冲突人话指路，无冲突 = ""）。终态发射归路由（emit.done 收尾，
    run_sse 终态保证语义不变；对照 run_recommendation 的 emit.done 在域内，
    差异见工单决策记录 4）。
    """
    validated_previous = _validate_previous_fixes(previous_fixes)
    errors = parse_compile_errors(error_text)
    candidates = collect_candidate_paths(output_dir, errors)
    contexts, dropped = read_file_contexts(output_dir, candidates)
    conflicts = syscfg_conflicts(error_text, errors)
    # parse_done 带配置级冲突条目（工单 02）：前端在本阶段就能给准话（域层对纯
    # 冲突短路不调 LLM，先显示「AI 修复中」再改口是误导）
    _emit(
        emit,
        ProgressEvent(
            type=EVENT_PARSE_DONE,
            error_count=len(errors),
            file_count=len(candidates),
            conflicts=tuple(parsed_error_entries(conflicts)),
        ),
    )
    _emit(emit, ProgressEvent(type=EVENT_FIX_START))
    if should_skip_llm_fix(candidates, conflicts):
        # 配置级冲突短路（工单 02）：没有源码候选可改 → 不喂 LLM（判据单源
        # = should_skip_llm_fix，CLI 验收脚本同用；并存源码错时不短路）
        report = ApplyReport(backup_id="", results=())
    else:
        fixes = llm.fix_compile_errors(
            error_text,
            dict(contexts),
            problem_text=problem_text,
            platform=platform,
            module_slugs=module_slugs,
            main_c=main_c,
            dropped_files=dropped,
            previous_fixes=validated_previous,
        )
        report = apply_fixes(fixes, output_dir, backup_root)
    for result in report.results:
        _emit(
            emit,
            ProgressEvent(
                type=EVENT_APPLY_RESULT,
                file=result.file,
                line=result.line,
                status=result.status,
                reason=result.reason,
            ),
        )
    return {
        "output_dir": str(output_dir),
        "backup_id": report.backup_id,
        "degraded": not candidates,
        "parsed": parsed_error_entries(errors),
        "fixes": [
            {"file": r.file, "line": r.line, "status": r.status, "reason": r.reason}
            for r in report.results
        ],
        "syscfg_conflicts": [
            {
                # 载荷只带消费方真用的字段（工单 02）：name / pin / by 是前端与
                # 清单筛选的三元组（谁抢谁抢哪个脚），message 是人话全句；
                # periph / field / conflict_count 属 CompileError 的解析明细，
                # 无消费方故不下发（YAGNI——需要时再加）
                "name": e.name,
                "pin": e.pin,
                "by": e.by,
                "message": e.message,
            }
            for e in conflicts
        ],
        "notice": SYSCFG_CONFLICT_NOTICE if conflicts else "",
    }
