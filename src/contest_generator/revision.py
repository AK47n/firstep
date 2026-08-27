"""修订执行（工单 revise-deepen/03）：备份 + 覆盖式重生成 + 回滚。

**两段式 API 第二段**（对照推荐「分析 → 执行」先例）：用户确认影响分析与
diff 后执行——目标输出目录整树备份到输出目录外（fix-backups 先例，带编号），
然后覆盖式重生成进同一目录（复用既有生成全链路：门禁 / 绑定写侧 / 多实例 /
副产物 / README / 构建脚本），并同步落新上下文清单。

**main.c 保全策略**（spec 关键决策）：模块集变化 → 重生成时骨架重生成
（新 main.c 替换，旧版在备份里）；模块集不变 → 不重生成、main.c 原样保留
（不丢手工编辑），深化直接在现有 main.c 上填 TODO。

**失败路径**：备份成功但重生成失败 → 目录保持可回滚状态（备份不删），
报错中文（RevisionError 登记 errors.py → 400；SSE 流内 error 由运行器收尾）。

**回滚**：`restore_revision` 清空输出目录 → 恢复备份内容（回滚 = 目录内容
恢复为备份内容，逐文件比对一致）。
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .context_manifest import (
    build_context_fields,
    read_context_fields,
    read_project_main_c,
    write_context_manifest,
)
from .events import (
    EVENT_REVISION_BACKUP,
    EVENT_REVISION_GENERATING,
    ProgressEvent,
)
from .fix_errors import is_unsafe_path
from .generator import generate_project
from .master_store import master_project_dir
from .selection import resolve_selection
from .skeleton import generate_skeleton

if TYPE_CHECKING:
    from .compile_runner import CcsTools
    from .llm import LLM  # 仅类型注解（生成流程不运行时拉 LLM 栈，先例同款）
    from .selection import ModuleInstance
    from .sse import SseEmitter

# 修订备份目录名（输出目录外，与 fix-backups 平级——同一工作根下的独立
# 备份族，互不干扰）
REVISE_BACKUPS_DIRNAME = "revise-backups"


class RevisionError(ValueError):
    """修订执行失败（备份缺失 / 回滚目标非法等），400 中文。"""


def revise_backup_root(work_root: Path) -> Path:
    """修订备份根（对照 fix_backup_root）：输出目录外、工具工作目录下。"""
    return work_root / REVISE_BACKUPS_DIRNAME


def backup_tree(backup_root: Path, output_dir: Path) -> str:
    """整树备份（修订执行第一步）：<backup_root>/<timestamp>/<相对路径>。

    输出目录外镜像（带编号 = 回滚入口）；输出目录不存在 / 为空 → RevisionError
    （修订目标必须是已生成的工程）。备份根不存在则创建。生成产物无 .git
    （copytree 先例），备份排除 .git 是防御。
    """
    if not output_dir.is_dir():
        raise RevisionError(f"输出目录不存在：{output_dir}")
    if not any(output_dir.iterdir()):
        raise RevisionError(f"输出目录为空，没有可修订的工程：{output_dir}")
    backup_id = _unique_backup_id(backup_root)
    target_dir = backup_root / backup_id
    shutil.copytree(
        output_dir,
        target_dir,
        ignore=shutil.ignore_patterns(".git"),
    )
    return backup_id


def restore_revision(
    backup_root: Path, backup_id: str, output_dir: Path
) -> tuple[str, ...]:
    """修订回滚：清空输出目录 → 恢复备份内容（回滚 = 目录内容恢复为备份
    内容，spec「回滚 = 目录内容恢复为备份内容」）。

    backup_id 必须是安全目录名（防 `..` / 绝对路径）；备份或输出目录不存在 →
    RevisionError（400 中文）。恢复前校验备份树内全部路径安全（is_unsafe_path
    ——与 fix_errors.restore_backup 同规，防恶意备份内容越出目录）；恢复的
    文件相对路径（POSIX）排序返回。
    """
    if is_unsafe_path(backup_id):
        raise RevisionError(f"非法的备份编号：{backup_id}")
    backup_dir = backup_root / backup_id
    if not backup_dir.is_dir():
        raise RevisionError(f"备份不存在：{backup_id}")
    if not output_dir.is_dir():
        raise RevisionError(f"输出目录不存在：{output_dir}")
    # 恢复前整树路径安全校验（备份内容不可信）：任一相对路径不安全 →
    # 大声失败，不清空不恢复
    unsafe = [
        p.relative_to(backup_dir).as_posix()
        for p in backup_dir.rglob("*")
        if p.is_file() and is_unsafe_path(p.relative_to(backup_dir).as_posix())
    ]
    if unsafe:
        raise RevisionError(f"备份内包含非法路径：{unsafe[0]}")
    # 回滚 = 目录内容恢复为备份内容：先清空现有内容（修订后的产物全删），
    # 再整体恢复备份（不留修订残留）
    for child in output_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    shutil.copytree(backup_dir, output_dir, dirs_exist_ok=True)
    return tuple(
        p.relative_to(output_dir).as_posix()
        for p in sorted(output_dir.rglob("*"))
        if p.is_file()
    )


def _unique_backup_id(backup_root: Path) -> str:
    """时间戳备份目录名（秒粒度，冲突加序号）——回滚入口须稳定可复述。"""
    base = time.strftime("%Y%m%d-%H%M%S")
    candidate = base
    counter = 2
    while (backup_root / candidate).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def run_revision(
    *,
    llm: LLM,
    problem_text: str,
    qa_text: str,
    requirements: Sequence[Mapping[str, Any]],
    references: Sequence[str],
    current_slugs: Sequence[str],
    confirmed_slugs: Sequence[str],
    new_qa_text: str,
    platform: str,
    library_dir: Path,
    masters_dir: Path,
    output_dir: Path,
    backup_root: Path,
    bindings: Mapping[str, str] | None = None,
    instances: Mapping[str, Sequence[ModuleInstance]] | None = None,
    python_templates: Mapping[str, str] | None = None,
    emit: SseEmitter,
    tool_version: str = "",
    impacts: Sequence[Mapping[str, Any]] = (),
    topic_id: str = "",
    ccs_tools: CcsTools | None = None,
) -> dict[str, Any]:
    """/api/revise/apply 的域编排（工单 03）：备份 → （模块集变化时）骨架
    重生成 → 覆盖式重生成 → 上下文清单更新 → diff 记录。

    进度事件：revision_backup（整树备份中）→ revision_generating（重生成中，
    仅模块集变化时发射）→ 终态 done（diff 记录，由路由 emit.done 收尾）。

    **模块集判定用依赖展开后的集合**（resolve_selection 展开，与生成产物
    同源）：确认集缺依赖时展开补回 = 模块集实际没变 → 不重生成、main.c 保留
    （不丢手工编辑）；diff 的增删同样按展开集算（与产物一致，不误报）。

    impacts（可选）= 影响结论记录（分析阶段产物，随 diff 记录留痕）。

    返回 done 载荷（JSON 形状稳定）：
    {"backup_id": ..., "regenerated": bool, "diff": {"added": [...],
    "removed": [...]}, "impacts": [...], "qa_text": 并入后的 Q&A 原文,
    "output_dir": ..., "generated_at": ...}。失败路径：备份成功但重生成失败
    → 抛 RevisionError / 原异常（sse 运行器补发 error 终态，备份保留 =
    目录保持可回滚）。
    """
    emit.progress(ProgressEvent(type=EVENT_REVISION_BACKUP))
    backup_id = backup_tree(backup_root, output_dir)

    # 依赖展开后的模块集（与生成产物同源）：判定变化与算 diff 都用它
    expanded_current = tuple(
        m.slug for m in resolve_selection(library_dir, platform, current_slugs).manifests
    )
    expanded_confirmed = tuple(
        m.slug for m in resolve_selection(library_dir, platform, confirmed_slugs).manifests
    )
    old_set = set(expanded_current)
    new_set = set(expanded_confirmed)
    regenerated = new_set != old_set
    merged_qa = _merge_qa(qa_text, new_qa_text)

    if regenerated:
        emit.progress(ProgressEvent(type=EVENT_REVISION_GENERATING))
        # 新骨架（LLM 出稿 + 静态自检，generate_skeleton 先例）→ 覆盖式重生成
        resolved = resolve_selection(library_dir, platform, confirmed_slugs)
        main_c, _intercepted = generate_skeleton(
            llm,
            problem_text,
            resolved.manifests,
            platform,
            library_dir,
            master_project_dir=master_project_dir(masters_dir, platform),
            instances=instances,
        )
        # 任务清单作废（工单 task-progress/03）：重生成替换了 main.c 与模块集，
        # 旧任务清单（含进度/备注）已与新工程无关——**重生成前**记录存在性
        # （rmtree 会清掉文件，事后判存在 = 常 False；存在性 = 是否曾拆解过）
        from .task_progress import TASKS_MANIFEST_FILENAME  # 函数级延迟导入（防环）

        tasks_invalidated = (output_dir / TASKS_MANIFEST_FILENAME).is_file()
        # 覆盖式重生成进同一输出目录（生成前清空——备份已完成，可回滚；
        # 任务清单文件随 rmtree 一并清除，无需再删）
        shutil.rmtree(output_dir, ignore_errors=True)
        generate_project(
            platform=platform,
            slugs=confirmed_slugs,
            main_c_content=main_c,
            output_dir=output_dir,
            module_library_dir=library_dir,
            masters_dir=masters_dir,
            ccs_tools=ccs_tools,  # mspm0 构建脚本（makefile 集）随全链路复用
            bindings=bindings,
            instances=instances,
            python_templates=python_templates,
            problem_text=problem_text,
            topic_id=topic_id,
            qa_text=merged_qa,
            requirements=requirements,
            references=references,
            tool_version=tool_version,
        )
    else:
        tasks_invalidated = False
        # 模块集不变：不重生成、main.c 原样保留（不丢手工编辑）——只把
        # 新 Q&A 并入上下文清单（修订的输入记录保持最新）；main_c 现读磁盘
        # （手工编辑过的内容进清单，与读侧语义一致）
        fields = read_context_fields(output_dir) or {}
        write_context_manifest(
            output_dir,
            build_context_fields(
                platform=platform,
                slugs=list(expanded_confirmed),
                main_c=read_project_main_c(output_dir),
                problem_text=problem_text,
                topic_id=topic_id or fields.get("topic_id", ""),
                qa_text=merged_qa,
                requirements=requirements,
                references=references,
                bindings=bindings or {},
                instances={
                    slug: [item.to_dict() for item in items]
                    for slug, items in (instances or {}).items()
                },
                python_templates=python_templates or {},
                tool_version=fields.get("tool_version", ""),
            ),
        )

    return {
        "backup_id": backup_id,
        "regenerated": regenerated,
        "tasks_invalidated": tasks_invalidated,  # 工单 task-progress/03：清单作废标记（前端提示重新拆解）
        "diff": {
            "added": [slug for slug in expanded_confirmed if slug not in old_set],
            "removed": [slug for slug in expanded_current if slug not in new_set],
        },
        "impacts": list(impacts),
        "qa_text": merged_qa,
        "output_dir": str(output_dir),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def _merge_qa(old_qa: str, new_qa: str) -> str:
    """新旧 Q&A 合并（上下文清单 qa_text 字段）：旧文 + 新 Q&A 独立段。

    旧文为空 / 新 Q&A 为空 = 对方原样；两者都有 = 空行分隔拼接（原文直引，
    不加工不改写——Q&A 是权威材料，逐字保留）。
    """
    if not old_qa:
        return new_qa
    if not new_qa:
        return old_qa
    return f"{old_qa}\n\n{new_qa}"
