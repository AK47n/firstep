"""编译错误回填自愈域模块（工单 compile-error-fix/01，决策记录 1-10）。

闭环"生成 → 编译 → 报错 → 修复"：把 Keil / CCS 编译报错文本贴回 → 解析文件
引用 → 从输出目录读真实文件内容（截断）→ LLM 逐条修复建议 → 直接写回工程
文件。域判决全部在本模块（纯函数、可单测）；llm.py 只做机械提取
（fix_compile_errors），webapp 只做薄壳装配（路由 + SSE 编排）。

可逆性（决策记录 2）：写回前把本次要改的文件原内容备份到输出目录外
（工作根/fix-backups/<timestamp>/，默认 ~/.contest_generator/fix-backups/），
UI 提供「回滚本次修复」按钮（restore_backup）。

路径安全（决策记录 3/5）：解析出的路径 resolve 后必须仍在输出目录内（containment
兜底，`..` 穿越 / 绝对路径 / 反斜杠起始形态天然越界被拒），扩展名白名单
.c/.h/.s（大写 .S 一并接受）——越界即 FixError（登记 errors.py → 400 中文）。

解析基准（2026-08-12 真机验收补，见 _report_benchmarks）：CCS 报错路径相对
工程根（.cproject 在根），直接按 output_dir 解析；UV4 报错路径相对 .uvprojx
所在子目录（`..\main.c(158)` 形态，uvprojx 在 user/ 而源文件在工程根）——
先按工程根解析，解析不出再按工程文件基准目录解析，两种都过 containment。

替换协议（决策记录 4 + 工单 fix-snippet-match/01）：old_snippet 精确匹配
（含缩进）优先；精确匹配失败时走行首前缀归一化兜底（old_snippet strip 后
必须是文件某行 strip 后内容的行首前缀——容忍前导缩进差异 / 行尾注释省略 /
CRLF / 行尾空白，语句本体必须逐字一致），唯一命中才应用（reason 标注
「按行首前缀归一化匹配应用」）；仍未命中 / 多处歧义一律跳过并报告
「未应用」（不静默、不模糊替换、不做语义匹配）。

本模块依赖方向：只 import entry_store（原语）与标准库，是叶子模块——llm.py
反向依赖本模块（FixSuggestion 模型），禁止本模块 import llm（截断标注与
llm.TRUNCATION_NOTICE 刻意同文，改动须同步）。
"""

from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .entry_store import is_unsafe_path

# 可写白名单（决策记录 3）：仅源码文件（.c/.h/.s，大写 .S 一并接受）；
# 工程配置 / 构建产物（.uvprojx / .axf / .o 等）不参与修复（读上下文同样
# 只读源码——二进制产物进 LLM 上下文会污染提示词）
WRITABLE_EXTENSIONS = frozenset({".c", ".h", ".s", ".S"})

# 单文件上下文上限（决策记录 6）：500 行 / 50KB，先到先截，带标注
FILE_CONTEXT_MAX_LINES = 500
FILE_CONTEXT_MAX_CHARS = 50 * 1024

# 全部文件上下文的总预算：LLM 请求体有硬性大小限制（llm.py MAX_REQUEST_BYTES
# 128KB），超预算的文件不发送、在提示词里点名（防静默丢失）
FIX_CONTEXT_TOTAL_CHARS = 48 * 1024

# 截断标注（决策记录 6）：与 llm.TRUNCATION_NOTICE 同句——本模块是 llm 的
# 依赖方向下游，不能反向 import，两句刻意同文（改动须同步，契约测试双端断言）
TRUNCATION_NOTICE = "按所见内容判断，不要脑补缺失部分"

# 备份目录名（决策记录 2）：工作根（模块库 / 母版库的父目录，默认
# ~/.contest_generator）下的 fix-backups/，在输出目录之外
FIX_BACKUPS_DIRNAME = "fix-backups"


class FixError(Exception):
    """编译错误修复的业务失败（登记 errors.py → 400 中文）。"""


@dataclass(frozen=True)
class CompileError:
    """解析出的一条编译报错：path 为空串 = 未解析到文件引用（降级模式）。"""

    path: str  # 相对路径（POSIX，反斜杠已归一）；可能为 ""（未解析到文件引用）
    line: int  # 行号；0 = 未知
    message: str  # 报错整行文本（原文）


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
# Warning 段缺省（如 "5 Error(s)."）时按 0 处理
_UV4_SUMMARY_RE = re.compile(
    r"(?P<errors>\d+)\s+Error\(s\)(?:[,\s]+(?P<warnings>\d+)\s+Warning\(s\))?"
)


def parse_compile_errors(error_text: str) -> tuple[CompileError, ...]:
    """逐行解析编译报错 → CompileError 列表（路径归一为 POSIX）。

    两种形态都试（UV4 / CCS，混合多文件自然兼容）；解析不到文件引用的行不
    产出条目——该行文本保留在报错全文里（随 LLM 上下文注入，降级不丢信息）。
    垃圾文本（无匹配）→ 空元组，不崩。反斜杠开头（\proj\... 绝对形态）视为
    未解析到引用（防把绝对路径当相对路径）。
    """
    parsed: list[CompileError] = []
    for line in error_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _UV4_ERROR_RE.search(stripped) or _CCS_ERROR_RE.search(stripped)
        if match is None:
            continue
        path = match.group("path").replace("\\", "/")
        if path.startswith("/"):
            continue  # 绝对形态：解析不到相对文件引用（该行降级）
        parsed.append(
            CompileError(path=path, line=int(match.group("line")), message=stripped)
        )
    return tuple(parsed)


def summarize_compile_output(
    error_text: str, parsed_errors: Sequence[CompileError]
) -> dict[str, int]:
    """编译输出数字汇总（工单 compile-experience-ui/01）：{errors, warnings}。

    UV4 汇总行优先——命中即取汇总值（errors / warnings 都来自汇总行，与行级
    计数可能不一致，以汇总为准）；未命中（CCS / gmake 无汇总行）退行级：
    len(parsed_errors) 为底，warning 条数 = 消息含 "warning"（大小写不敏感）
    计数，errors = 总数 − warnings。垃圾 / 空文本 → {0, 0}，不崩。
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
    以 `..\\` 引用），CCS 的 .cproject 一般在工程根。探测 output_dir 下所有
    工程文件（.uvprojx / .cproject）的父目录，去重保序；找不到 → 空（只走
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
    return tuple(benchmarks)


def collect_candidate_paths(
    output_dir: Path, errors: Sequence[CompileError]
) -> tuple[str, ...]:
    """报错命中的可修复文件（决策记录 3/5）：白名单扩展名 + resolve 后仍在
    输出目录内 + 文件真实存在。任一不满足 → 该条报错降级（整段错误文本仍在
    LLM 上下文，只是没有文件内容）。返回去重保序的相对路径（POSIX，相对
    output_dir）。

    两种解析基准（2026-08-12 真机验收补）：先按工程根直接解析（CCS 相对
    形态）；解析不出（UV4 `..\\` 相对形态，相对工程根会越过 root）再按
    _report_benchmarks 的工程文件基准目录解析。安全由 containment 兜底：
    两种解析都 resolve 后判定是否在 root 内——`..` 逃逸 / 绝对路径 /
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
    """报错路径 → 输出目录内真实文件（两种基准都试）；解析不到返回 None。"""
    if not is_unsafe_path(path):
        target = (output_dir / path).resolve()
        if target.is_relative_to(root) and target.is_file():
            return target
    for bench in benchmarks:
        target = (bench / path).resolve()
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
    """读取候选文件内容（决策记录 6）：单文件 500 行 / 50KB 双上限截断（带
    标注，模型明确知道读到的是截断内容），全部文件合计不超
    FIX_CONTEXT_TOTAL_CHARS——超预算的剩余文件不读取、单独返回（llm 提示词
    点名，不静默丢失）。读取失败（磁盘错误 / 编码不可解）跳过（该文件降级）。
    返回 ((相对路径, 内容), ...) 与（未发送的相对路径列表）。
    """
    contents: list[tuple[str, str]] = []
    dropped: list[str] = []
    budget = FIX_CONTEXT_TOTAL_CHARS
    for path in paths:
        if budget <= 0:
            dropped.append(path)
            continue
        try:
            content = (output_dir / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # 读取失败 → 该文件降级（决策记录 5）
        content = _truncate_file(content)
        if len(content) > budget:
            content = content[:budget] + "\n……（上下文预算限制，仅截取前段）……\n"
        budget -= len(content)
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


def apply_fixes(
    fixes: Sequence[FixSuggestion],
    output_dir: Path,
    backup_root: Path,
) -> ApplyReport:
    """snippet 替换协议（决策记录 4 + 工单 fix-snippet-match/01）：old_snippet
    精确匹配优先；精确匹配失败（0 次）时走行首前缀归一化兜底（容忍缩进 /
    行尾注释省略 / CRLF / 行尾空白，语句本体须逐字一致），唯一命中才 applied
    （reason 标注归一化）；仍未命中 / 多处歧义跳过并报告「未应用」——不
    静默、不模糊替换、不做语义匹配。

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
            count = content.count(fix.old_snippet)
            if count == 1:
                index = content.find(fix.old_snippet)
                content = (
                    content[:index] + fix.new_snippet + content[index + len(fix.old_snippet):]
                )
                results.append(
                    FixResult(file=file, line=fix.line, status="applied", reason="")
                )
                new_contents[file] = content
            elif count == 0:
                # 精确匹配失败 → 行首前缀归一化兜底（fix-snippet-match/01）
                normalized = _normalized_hits(content, fix.old_snippet)
                if len(normalized) == 1:
                    start, end = _line_span(
                        content, normalized[0], len(_snippet_normalized_lines(fix.old_snippet))
                    )
                    snippet = _preserve_line_ending(fix.new_snippet, content[start:end])
                    content = content[:start] + snippet + content[end:]
                    results.append(
                        FixResult(
                            file=file,
                            line=fix.line,
                            status="applied",
                            reason="按行首前缀归一化匹配应用",
                        )
                    )
                    new_contents[file] = content
                elif len(normalized) == 0:
                    results.append(
                        FixResult(
                            file=file,
                            line=fix.line,
                            status="skipped",
                            reason="未应用：文件内未找到 old_snippet（精确匹配失败，"
                            "可能缩进 / 内容不一致）",
                        )
                    )
                else:
                    results.append(
                        FixResult(
                            file=file,
                            line=fix.line,
                            status="skipped",
                            reason=f"未应用：old_snippet 按行首前缀归一化在文件内"
                            f"多处命中（{len(normalized)} 处，歧义，要求唯一匹配）",
                        )
                    )
            else:
                results.append(
                    FixResult(
                        file=file,
                        line=fix.line,
                        status="skipped",
                        reason=f"未应用：old_snippet 在文件内出现 {count} 次"
                        "（歧义，要求唯一匹配）",
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
        raise FixError(f"非法的备份编号：{backup_id}")
    backup_dir = backup_root / backup_id
    if not backup_dir.is_dir():
        raise FixError(f"备份不存在：{backup_id}")
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
