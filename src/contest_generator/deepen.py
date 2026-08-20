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
    "compile": {"passed", "exit_code", "summary"}, "message": 中文提示}。
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

    # 2. 写盘前备份（可回滚）→ 3. 写盘
    backup_id = _backup_main_c(work_root, output_dir, main_c)
    (output_dir / "main.c").write_text(deepened, encoding="utf-8")

    # 4. 编译验证闭环：工具链探测（resolve_compile_toolchain 单源，config 覆盖
    #    > 自动）→ 无 = 大声降级（探测抛 CompileRunnerError = 无工具链，语义
    #    与 /api/compile 的起流前 400 同源，此处转降级不 400）；有 → 编译 →
    #    失败修一轮 → 重编译 → 绿 = 已验证
    try:
        uv4, make = resolve_compile_toolchain(platform, uv4_override, make_override)
    except CompileRunnerError:
        emit.progress(ProgressEvent(type=EVENT_VERIFY_RESULT))
        return {
            "status": STATUS_UNVERIFIED,
            "backup_id": backup_id,
            "compile": {"passed": None, "exit_code": None, "summary": ""},
            "message": _status_message(STATUS_UNVERIFIED),
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
                main_c=deepened,
                previous_fixes=(),
                emit=emit.progress,
            )
    emit.progress(ProgressEvent(type=EVENT_VERIFY_RESULT))
    compile_summary = _compile_summary(last_build)
    return {
        "status": status,
        "backup_id": backup_id,
        "compile": compile_summary,
        "message": _status_message(status),
    }


def _backup_main_c(work_root: Path, output_dir: Path, main_c: str) -> str:
    """深化写盘前备份（可回滚）：整树备份到 revise-backups/<timestamp>/。

    只改 main.c 但整树备份——与修订执行同一回滚入口（restore_revision 恢复
    整树 = 深化前状态，含手工编辑），备份成本可接受（工程规模小）。
    """
    if not output_dir.is_dir():
        raise DeepenError(f"输出目录不存在：{output_dir}")
    return backup_tree(revise_backup_root(work_root), output_dir)


def _compile_summary(build) -> dict[str, Any]:
    """最后编译结果摘要（done 载荷展示用）。"""
    if build is None:
        return {"passed": None, "exit_code": None, "summary": ""}
    parsed = _parse_errors(build.run.output)
    return {
        "passed": compile_passed(build.platform, build.run.exit_code),
        "exit_code": build.run.exit_code,
        "summary": _summarize(build.run.output, parsed),
    }


def _parse_errors(output: str):
    """编译错误解析（fix-errors / compile 端点同款，域内延迟导入防环）。"""
    from .compile_runner import parse_compile_errors

    return parse_compile_errors(output)


def _summarize(output: str, parsed) -> dict[str, Any]:
    """错误/警告数字汇总（compile-experience-ui 同款）。"""
    from .compile_runner import summarize_compile_output

    return summarize_compile_output(output, parsed)


def _status_message(status: str) -> str:
    """验证状态的中文提示（done 载荷 message 字段单源，三分支全活）。"""
    if status == STATUS_VERIFIED:
        return "编译验证通过：深化结果已标记为「已验证」"
    if status == STATUS_UNVERIFIED:
        return (
            "未检测到工具链（stm32 需 Keil UV4 / mspm0 需 gmake，可在设置页填"
            "路径覆盖）——深化结果已保留，但状态 = 未验证：请自行编译确认"
        )
    return "编译验证未通过（修复一轮后仍红）：深化结果保留，可回滚或再次触发深化"
