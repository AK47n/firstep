"""编译错误回填自愈域模块（工单 compile-error-fix/01，决策记录 1-10）。

闭环"生成 → 编译 → 报错 → 修复"：把 Keil / CCS 编译报错文本贴回 → 解析文件
引用 → 从输出目录读真实文件内容（截断）→ LLM 逐条修复建议 → 直接写回工程
文件。域判决全部在本模块（纯函数、可单测）；llm.py 只做机械提取
（fix_compile_errors），webapp 只做薄壳装配（路由 + SSE 编排）。

可逆性（决策记录 2）：写回前把本次要改的文件原内容备份到输出目录外
（工作根/fix-backups/<timestamp>/，默认 ~/.contest_generator/fix-backups/），
UI 提供「回滚本次修复」按钮（restore_backup）。

路径安全（决策记录 3/5）：解析出的路径必须是相对形态（is_unsafe_path 原语
拒绝 `..` / 绝对路径 / 反斜杠），resolve 后仍在输出目录内，扩展名白名单
.c/.h/.s（大写 .S 一并接受）——越界即 FixError（登记 errors.py → 400 中文）。

替换协议（决策记录 4）：old_snippet 与文件现有内容逐字精确匹配（含缩进）后
替换；匹配失败 / 多处歧义一律跳过并报告「未应用」（不静默、不模糊替换）。

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
    old_snippet: str  # 必须与文件现有内容逐字一致（含缩进）
    new_snippet: str  # 替换后内容（空串 = 删除该片段）
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


def collect_candidate_paths(
    output_dir: Path, errors: Sequence[CompileError]
) -> tuple[str, ...]:
    """报错命中的可修复文件（决策记录 3/5）：路径安全（is_unsafe_path 拒绝
    `..` 穿越 / 绝对路径）+ 白名单扩展名 + resolve 后仍在输出目录内 + 文件
    真实存在。任一不满足 → 该条报错降级（整段错误文本仍在 LLM 上下文，只是
    没有文件内容）。返回去重保序的相对路径（POSIX）。
    """
    root = output_dir.resolve()
    seen: set[str] = set()
    candidates: list[str] = []
    for error in errors:
        path = error.path
        if not path or path in seen:
            continue
        if Path(path).suffix not in WRITABLE_EXTENSIONS:
            continue  # 非源码文件（.axf / .uvprojx 等）无修复价值
        if is_unsafe_path(path):
            continue
        target = (output_dir / path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            continue  # 越出输出目录 / 读取不到 → 降级
        seen.add(path)
        candidates.append(path)
    return tuple(candidates)


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


def apply_fixes(
    fixes: Sequence[FixSuggestion],
    output_dir: Path,
    backup_root: Path,
) -> ApplyReport:
    """snippet 替换协议（决策记录 4）：old_snippet 与文件现有内容逐字精确匹配
    后替换；匹配失败（0 次）/ 多处歧义（≥2 次）跳过并报告「未应用」——不
    静默、不模糊替换。

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
