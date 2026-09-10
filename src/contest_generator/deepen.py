"""深化（工单 revise-deepen/04）：AI 按功能需求填 TODO + 编译验证闭环。

**深化**：输入 = 现有 main.c（含 TODO）+ 功能需求清单 + 模块接口清单 + 题面
与 Q&A；LLM 逐条填充 TODO 预留区（输出与需求清单对应，不做题外发挥）→
写盘前备份（可回滚）→ 写盘。模块没变时在现有 main.c 上进行（手工编辑保留，
修订执行已保证该语义）；模块变过则由修订执行在新骨架上进行。

**编译验证闭环**（spec 硬门槛）：工具链探测（config 覆盖 > 自动，与 /api/compile
同款）→ 无工具链 = 大声降级（结果保留、状态 = unverified，明确提示）；有
工具链 → 编译 → 失败自动进修复闭环（run_fix_round 复用）→ 重编译 → 绿 =
verified。修一轮仍红 = failed（结果保留，报错中文）。不设自动循环，用户可
重复触发。

**事件**：deepening_start（填 TODO 中，LLM 分钟级）→ compile_start（编译中，
复用 compile 词表）→ fix_start（修复中，复用 fix-errors 词表）→ verify_result
（验证结果）→ 终态 done（结果载荷）。
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .compile_runner import (
    BuildLog,
    CompileRunnerError,
    collect_build_log,
    compile_passed,
    resolve_compile_toolchain,
)
from .events import (
    EVENT_COMPILE_START,
    EVENT_DEEPENING_START,
    EVENT_FIX_START,
    EVENT_VERIFY_RESULT,
    ProgressEvent,
)
from .fix_errors import fix_backup_root, run_fix_round
from .revision import backup_tree, revise_backup_root
from .skeleton import build_skeleton_interfaces

if TYPE_CHECKING:
    from .llm import LLM  # 仅类型注解（深化的 LLM 调用在域编排层）
    from .manifest import ModuleManifest
    from .sse import SseEmitter

# 深化结果状态词表（spec「已验证 / 未验证」+ 修一轮仍红的失败态）
STATUS_VERIFIED = "verified"  # 编译绿（0 错 0 警或仅警告）
STATUS_UNVERIFIED = "unverified"  # 无工具链：结果保留、大声降级提示
STATUS_FAILED = "failed"  # 修一轮仍红：结果保留、报错中文


class DeepenError(ValueError):
    """深化失败（main.c 缺失 / 工程不可编译等），400 中文。"""


def verify_compile_tail(
    *,
    llm: LLM,
    platform: str,
    output_dir: Path,
    work_root: Path,
    problem_text: str,
    module_slugs: Sequence[str],
    main_c: str,
    uv4_override: str,
    make_override: str,
    emit: SseEmitter,
    backup_id: str,
    main_diff: dict[str, Any] | None,
    subject: str = "深化结果",
) -> dict[str, Any]:
    """编译验证闭环尾段（run_deepen 与 run_task 共用，工单 task-progress/02）。

    工具链探测（resolve_compile_toolchain 单源，config 覆盖 > 自动）→ 无 =
    大声降级（探测抛 CompileRunnerError = 无工具链，语义与 /api/compile 的
    起流前 400 同源，此处转降级不 400）；有 → 编译 → 失败修一轮（
    run_fix_round 复用）→ 重编译 → 绿 = 已验证。不设自动循环，用户可重复
    触发。

    事件：compile_start（复用 compile 词表）→ fix_start（仅首轮编译失败）→
    verify_result。返回 done 载荷：
    {"status": verified | unverified | failed, "backup_id", "compile":
    {"passed", "exit_code", "summary"}, "main_diff", "message"}——
    backup_id / main_diff 由调用方传入（写盘前已备份、diff 已算好）。
    subject = 结果主语（深化 / 任务上下文用词，message 措辞服务调用方语义
    ——共享尾段不泄漏「深化」字眼）。
    """
    try:
        uv4, make = resolve_compile_toolchain(platform, uv4_override, make_override)
    except CompileRunnerError:
        emit.progress(ProgressEvent(type=EVENT_VERIFY_RESULT))
        return {
            "status": STATUS_UNVERIFIED,
            "backup_id": backup_id,
            "compile": {
                "passed": None, "exit_code": None, "summary": "",
                "parsed_errors": [],  # 无工具链 = 无编译输出（error-jump-task 评审整改：与 _compile_summary 同型）
            },
            "main_diff": main_diff,
            "message": _status_message(STATUS_UNVERIFIED, subject),
        }

    last_build: BuildLog | None = None
    status = STATUS_FAILED
    for attempt in (1, 2):  # 至多一次修复后重编译（不设自动循环，用户可重复触发）
        emit.progress(ProgressEvent(type=EVENT_COMPILE_START))
        build = collect_build_log(platform, output_dir, uv4=uv4, make=make)
        last_build = build
        if compile_passed(platform, build.run.exit_code):
            status = STATUS_VERIFIED
            break
        if attempt == 1:
            emit.progress(ProgressEvent(type=EVENT_FIX_START))
            run_fix_round(
                llm,
                error_text=build.run.output,
                output_dir=output_dir,
                backup_root=fix_backup_root(work_root),
                problem_text=problem_text,
                platform=platform,
                module_slugs=module_slugs,
                main_c=main_c,
                previous_fixes=(),
                emit=emit.progress,
            )
    emit.progress(ProgressEvent(type=EVENT_VERIFY_RESULT))
    return {
        "status": status,
        "backup_id": backup_id,
        "compile": _compile_summary(last_build),
        "main_diff": main_diff,
        "message": _status_message(status, subject),
    }


def run_deepen(
    *,
    llm: LLM,
    problem_text: str,
    qa_text: str,
    requirements: Sequence[Mapping[str, Any]],
    manifests: Sequence[ModuleManifest],
    platform: str,
    library_dir: Path,
    master_project_dir: Path,
    main_c: str,
    output_dir: Path,
    work_root: Path,
    emit: SseEmitter,
    uv4_override: str = "",
    make_override: str = "",
    module_slugs: Sequence[str] = (),
) -> dict[str, Any]:
    """/api/revise/deepen 的域编排：LLM 填 TODO → 备份 → 写盘 → 编译验证闭环。

    模块接口清单 = build_skeleton_interfaces（与骨架 / 生成同源，喂给 LLM 的
    接口 = 工程里真实存在的函数）。main_c 必须是深化前现读的内容（修订执行
    已保证模块集不变时手工编辑保留）。

    返回 done 载荷（JSON 形状稳定）：
    {"status": verified | unverified | failed, "backup_id": ...,
    "compile": {"passed", "exit_code", "summary"},
    "main_diff": 深化效果报告（工单 deepen-report/01）——深化前 vs 深化后的
    main.c 确定性 diff（{"text", "stats": {"additions", "deletions",
    "hunks"}, "hunks": [...]}），无差异 = None，
    "message": 中文提示}。
    失败路径（main_c 缺失 / 编译异常）抛 DeepenError / 原异常（sse 运行器
    补发 error 终态，备份保留可回滚）。
    """
    if not main_c.strip():
        raise DeepenError("工程 main.c 为空，无法深化（请先生成或修订工程）")
    emit.progress(ProgressEvent(type=EVENT_DEEPENING_START))

    # 1. LLM 深化：按功能需求逐条填充 TODO（输出与需求清单对应）
    interfaces = build_skeleton_interfaces(
        manifests, platform, library_dir, master_project_dir
    )
    deepened = llm.deepen_main_c(
        main_c=main_c,
        requirements=requirements,
        module_interfaces=interfaces,
        problem_text=problem_text,
        qa_text=qa_text,
    )
    if not deepened.strip():
        raise DeepenError("深化结果为空——LLM 未产出实现后的 main.c，请重试")

    # 2. 写盘前备份（可回滚）→ 3. 写盘 → 4. 深化效果报告（真实 diff，不依赖
    #    LLM 自述——「说做了 A 实际做了 B」场景下展示的是改动的真相）
    backup_id = _backup_main_c(work_root, output_dir, main_c)
    (output_dir / "main.c").write_text(deepened, encoding="utf-8")
    diff = main_diff(main_c, deepened)  # 公共 main_diff（工单 task-progress/02）

    # 5. 编译验证闭环（公共尾段，工单 task-progress/02 抽取）：无工具链 = 大声
    #    降级（状态 = 未验证，结果保留）；有 → 编译 → 失败修一轮 → 重编译 → 绿
    return verify_compile_tail(
        llm=llm,
        platform=platform,
        output_dir=output_dir,
        work_root=work_root,
        problem_text=problem_text,
        module_slugs=module_slugs,
        main_c=deepened,
        uv4_override=uv4_override,
        make_override=make_override,
        emit=emit,
        backup_id=backup_id,
        main_diff=diff,
    )


# ---------------------------------------------------------------------------
# 深化效果报告（工单 deepen-report/01）：main.c 前后确定性 diff。
#
# 事实源 = 深化前 main_c vs 深化后 deepened（difflib.unified_diff, n=2），
# 不依赖 LLM 自述（「说做了 A 实际做了 B」场景展示的是改动真相）；标题
# 优先取被替换的 TODO 注释（需求可追踪），退化取注释行，再退化空串（前端
# 用 hunk 行号 fallback）。**公共函数**（工单 task-progress/02：run_task 的
# 单任务 diff 与深化共用同一实现，不各写一份）。
# ---------------------------------------------------------------------------

_COMMENT_BLOCK_RE = re.compile(r"/\*(.*?)\*/")
_TODO_RE = re.compile(r"TODO|FIXME|XXX", re.IGNORECASE)
_HUNK_HEADER_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def main_diff(before: str, after: str) -> dict[str, Any] | None:
    """深化前 vs 深化后的 main.c 确定性 diff；无差异 = None。

    返回：{"text": unified diff 全文, "stats": {"additions", "deletions",
    "hunks"}, "hunks": [{"header", "line"（新文件起始行号）, "title",
    "lines": [{"kind": add|del|ctx, "text": 无前缀原文}]}]}。
    """
    if before == after:
        return None
    b_lines = before.splitlines()
    a_lines = after.splitlines()
    text = list(
        difflib.unified_diff(
            b_lines,
            a_lines,
            fromfile="main.c（深化前）",
            tofile="main.c（深化后）",
            n=2,
            lineterm="",
        )
    )
    hunks: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for line in text:
        if line.startswith("@@"):
            cur = {
                "header": line,
                "line": _hunk_new_start(line),
                "title": "",
                "lines": [],
            }
            hunks.append(cur)
        elif cur is None or line.startswith(("---", "+++", "\\")):
            continue  # 文件头 / 无换行符标记不进 hunk
        elif line.startswith("+"):
            cur["lines"].append({"kind": "add", "text": line[1:]})
        elif line.startswith("-"):
            cur["lines"].append({"kind": "del", "text": line[1:]})
        else:  # 上下文行：unified diff 以单个空格开头
            cur["lines"].append({"kind": "ctx", "text": line[1:]})
    for hunk in hunks:
        hunk["title"] = _hunk_title(hunk["lines"])
    stats = {
        "additions": sum(1 for h in hunks for e in h["lines"] if e["kind"] == "add"),
        "deletions": sum(1 for h in hunks for e in h["lines"] if e["kind"] == "del"),
        "hunks": len(hunks),
    }
    return {"text": "\n".join(text), "stats": stats, "hunks": hunks}


def _hunk_new_start(header: str) -> int:
    """hunk 头 @@ -a,b +c,d @@ → 新文件起始行号 c（前端 fallback 行号用）。"""
    m = _HUNK_HEADER_RE.match(header)
    return int(m.group(1)) if m else 0


def _hunk_title(lines: Sequence[dict[str, str]]) -> str:
    """hunk 标题：① 删除行 TODO/FIXME/XXX 注释 → 「填充 TODO「…」」（剥注释
    自带的前缀，避免「填充 TODO「TODO: 初始化电机」」重复）；② 删除行注释 →
    注释文本；③ 上下文行注释 → 注释文本；④ 空串。"""
    for entry in lines:
        if entry["kind"] != "del":
            continue
        text = _comment_text(entry["text"])
        if text and _TODO_RE.search(text):
            inner = _strip_todo_prefix(text)
            return f"填充 TODO「{inner or text}」"
    for entry in lines:
        if entry["kind"] == "del":
            text = _comment_text(entry["text"])
            if text:
                return text
    for entry in lines:
        if entry["kind"] == "ctx":
            text = _comment_text(entry["text"])
            if text:
                return text
    return ""


def _strip_todo_prefix(text: str) -> str:
    """剥注释里自带的前导标记（"TODO: 循迹" → "循迹"），只剥标记 + 分隔
    （冒号 / 空白 / 横线），不剥后续中文说明（[^A-Za-z]* 会把中文一起吃
    掉——那是本函数踩过的坑）。"""
    m = re.match(r"^(TODO|FIXME|XXX)\s*([:：\-]|$)", text, re.IGNORECASE)
    return text[m.end() :].strip() if m else text


def _comment_text(line: str) -> str:
    """行内注释文本：/* … */（同行）或 // …；块注释的起始行（/* XXX 未闭合，
    跨行注释）取 /* 之后的第一行内容；剥前导 * 与空白，无注释 = 空串。"""
    m = _COMMENT_BLOCK_RE.search(line)
    if m:
        text = m.group(1)
    else:
        idx = line.find("//")
        if idx < 0:
            idx = line.find("/*")
            if idx < 0:
                return ""
            text = line[idx + 2 :]
        else:
            text = line[idx + 2 :]
    return text.strip().lstrip("*").strip()


def _backup_main_c(work_root: Path, output_dir: Path, main_c: str) -> str:
    """深化写盘前备份（可回滚）：整树备份到 revise-backups/<timestamp>/。

    只改 main.c 但整树备份——与修订执行同一回滚入口（restore_revision 恢复
    整树 = 深化前状态，含手工编辑），备份成本可接受（工程规模小）。
    """
    if not output_dir.is_dir():
        raise DeepenError(f"输出目录不存在：{output_dir}")
    return backup_tree(revise_backup_root(work_root), output_dir)


def _compile_summary(build) -> dict[str, Any]:
    """最后编译结果摘要（done 载荷展示用）。

    parsed_errors = 结构化错误列表（工单 error-jump-task/01：任务结果面板
    错误行跳转 main.c 用；parse_compile_errors 同源——compile_runner
    /api/compile done 载荷的 parsed_errors 字段同型，条目形状单源 =
    fix_errors.parsed_error_entries，工单 02：SysConfig 配置级冲突条目带
    kind）；build 为 None（无工具链降级）= 空列表。compile dict 只追加不改
    既有键（passed / exit_code / summary），旧前端忽略新字段即可。
    """
    if build is None:
        return {
            "passed": None, "exit_code": None, "summary": "",
            "parsed_errors": [],
        }
    parsed = _parse_errors(build.run.output)
    return {
        "passed": compile_passed(build.platform, build.run.exit_code),
        "exit_code": build.run.exit_code,
        "summary": _summarize(build.run.output, parsed),
        "parsed_errors": _error_entries(parsed),
    }


def _error_entries(parsed):
    """结构化错误条目（形状单源 = fix_errors.parsed_error_entries；域内延迟导入
    与 _parse_errors / _summarize 同款——本模块对 fix_errors 一律延迟导入，避免
    与 llm ← fix_errors 的依赖方向纠缠）。"""
    from .fix_errors import parsed_error_entries

    return parsed_error_entries(parsed)


def _parse_errors(output: str):
    """编译错误解析（fix-errors / compile 端点同款，域内延迟导入防环）。"""
    from .compile_runner import parse_compile_errors

    return parse_compile_errors(output)


def _summarize(output: str, parsed) -> dict[str, Any]:
    """错误/警告数字汇总（compile-experience-ui 同款）。"""
    from .compile_runner import summarize_compile_output

    return summarize_compile_output(output, parsed)


def _status_message(status: str, subject: str = "深化结果") -> str:
    """验证状态的中文提示（done 载荷 message 字段单源，三分支全活）。

    subject = 结果主语（深化 / 任务上下文用词）——共享尾段不泄漏「深化」
    字眼给任务流（工单 task-progress/02 评审发现：任务 done 载荷误写
    「深化结果已标记为已验证」）。
    """
    if status == STATUS_VERIFIED:
        return f"编译验证通过：{subject}已标记为「已验证」"
    if status == STATUS_UNVERIFIED:
        return (
            "未检测到工具链（stm32 需 Keil UV4 / mspm0 需 gmake，可在设置页填"
            f"路径覆盖）——{subject}已保留，但状态 = 未验证：请自行编译确认"
        )
    return f"编译验证未通过（修复一轮后仍红）：{subject}保留，可回滚或再次执行"
