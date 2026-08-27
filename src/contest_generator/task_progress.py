"""任务推进（工单 task-progress/01-03）：拆解任务清单 + 落盘 + 逐任务执行。

**任务推进**：生成后 AI 把题面拆成有序任务（每任务 = 一段可独立实现并编译
验证的 main.c 增量），学生逐卡点「做这一步」，每步备份 + 写盘 + 编译验证
闭环（与深化同款管线尾段）。任务清单落盘工程根 `.contest_tasks.json`——
纯新增隐藏文件（.contest_context.json 先例），与生成产物零交叉。

本模块 = 任务域模型 / LLM 输出解释链 / 清单文件读写 / 域编排。事件词表在
events.py，错误映射在 errors.py（TaskError → 400 中文），路由在 webapp.py
（薄壳，对照 revise/deepen 先例）。

**状态机**（工单 03 完整转移表，此处常量为单源）：pending（待做）→
doing（执行中）→ verified / unverified / failed / skipped；verified →
pending（重做）；unverified / failed → verified（人工改标，上板确认）；
skipped → pending（恢复）。

**任务模型**（LLM 输出 → 域判决解释链，照 ScorePoint / ImpactAnalysis 先例）：
LLM 产出 {tasks: [{title, description, score_refs, depends_on, verify}]}——
id（t1..tn）由解析层按顺序分配，depends_on 用 1 起序号引用清单内任务
（解析后转 id）；score_refs 引用传入评分点 id 清单（无评分点清单 =
忽略该字段，置空）；verify = compile（编译绿即验证）/ manual（需上板
人工确认，如循迹效果）。

**文件形状**（落盘与读回 = 同一模型，version 向后兼容）：

    {"version": 1, "generated_at": "…",
     "tasks": [{"id": "t1", "title": "…", "description": "…",
                "score_refs": ["s1"], "depends_on": ["t2"],
                "verify": "compile", "status": "pending", "note": ""}]}

note = 补充框内容（执行时透传 LLM，未执行 = 空串）。status 只在本域
状态机内变化，前置任务不强制阻断（展示与排序用途）。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .events import EVENT_TASK_PLANNING, ProgressEvent

if TYPE_CHECKING:
    from .llm import LLM  # 仅类型注解（llm 运行时依赖本层，反向禁止）
    from .sse import SseEmitter

# 清单文件名（写侧单源，webapp / 前端共用）
TASKS_MANIFEST_FILENAME = ".contest_tasks.json"
TASKS_MANIFEST_BAK_FILENAME = ".contest_tasks.json.bak"

# 清单版本：向后兼容读（未知版本容忍：只读已知字段，缺省补默认）
TASKS_MANIFEST_VERSION = 1

# 任务状态词表（单源：解析 / 文件读回 / 状态机 / 前端共用）
STATUS_PENDING = "pending"  # 待做
STATUS_DOING = "doing"  # 执行中（一次 LLM 调用 + 编译验证闭环节点）
STATUS_VERIFIED = "verified"  # 已验证（编译绿 / 人工上板改标）
STATUS_UNVERIFIED = "unverified"  # 未验证（无工具链降级，结果保留）
STATUS_FAILED = "failed"  # 失败（修一轮仍红，结果保留可回滚）
STATUS_SKIPPED = "skipped"  # 已跳过（用户主动放弃该任务）

ALL_STATUSES = frozenset(
    {
        STATUS_PENDING,
        STATUS_DOING,
        STATUS_VERIFIED,
        STATUS_UNVERIFIED,
        STATUS_FAILED,
        STATUS_SKIPPED,
    }
)

# 验收方式词表
VERIFY_COMPILE = "compile"  # 编译绿即验证
VERIFY_MANUAL = "manual"  # 上板人工确认（如循迹效果观察）

VALID_VERIFY = frozenset({VERIFY_COMPILE, VERIFY_MANUAL})


class TaskError(ValueError):
    """任务推进失败（清单损坏 / 缺上下文 / LLM 输出畸形），400 中文。"""


# ---------------------------------------------------------------------------
# 任务域模型：Task / TaskPlan（序列化与校验唯一所有者）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Task:
    """一个实现任务（可独立执行、可独立编译验证的 main.c 增量）。

    id = 清单内序号（t1..tn，解析层分配）；score_refs = 关联评分点 id
    （来自题面评分点清单，无评分点 = 空）；depends_on = 前置任务 id
    （展示与排序用途，不强制阻断）；verify = 验收方式；status = 状态机
    当前态；note = 补充框内容（用户向 AI 补的一句说明，执行时透传）。
    """

    id: str
    title: str
    description: str
    score_refs: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    verify: str = VERIFY_COMPILE
    status: str = STATUS_PENDING
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "score_refs": list(self.score_refs),
            "depends_on": list(self.depends_on),
            "verify": self.verify,
            "status": self.status,
            "note": self.note,
        }


@dataclass(frozen=True)
class TaskPlan:
    """任务清单（落盘与读回 = 同一模型）。"""

    version: int = TASKS_MANIFEST_VERSION
    generated_at: str = ""
    tasks: tuple[Task, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> TaskPlan:
        """读回侧解释链（清单文件 → 模型）：字段缺失/类型错 → TaskError。

        缺省补默认（旧版本 / 手改兼容）：generated_at 空、tasks 空；
        未知任务字段忽略；status 词表外 → 修正为 pending（不拒收——
        读回侧宁可用默认态也把清单交还用户，避免一次坏值永久不可用）。
        """
        version = raw.get("version", TASKS_MANIFEST_VERSION)
        if not isinstance(version, int) or isinstance(version, bool):
            raise TaskError(f"任务清单 version 非法：{version!r}")
        generated_at = raw.get("generated_at", "")
        if not isinstance(generated_at, str):
            raise TaskError("任务清单 generated_at 必须是字符串")
        raw_tasks = raw.get("tasks", [])
        if not isinstance(raw_tasks, list):
            raise TaskError("任务清单 tasks 必须是数组")
        tasks: list[Task] = []
        for index, item in enumerate(raw_tasks, 1):
            if not isinstance(item, dict):
                raise TaskError(f"任务清单第 {index} 项必须是对象")
            task_id = item.get("id", f"t{index}")
            if not isinstance(task_id, str) or not task_id.strip():
                raise TaskError(f"任务清单第 {index} 项缺少 id")
            title = item.get("title", "")
            if not isinstance(title, str) or not title.strip():
                raise TaskError(f"任务清单第 {index} 项缺少标题")
            description = item.get("description", "")
            if not isinstance(description, str):
                raise TaskError(f"任务清单第 {index} 项 description 必须是字符串")
            verify = item.get("verify", VERIFY_COMPILE)
            if verify not in VALID_VERIFY:
                verify = VERIFY_COMPILE  # 词表外修正（读回侧不拒收）
            status = item.get("status", STATUS_PENDING)
            if status not in ALL_STATUSES:
                status = STATUS_PENDING
            raw_refs = item.get("score_refs", [])
            raw_deps = item.get("depends_on", [])
            tasks.append(
                Task(
                    id=task_id.strip(),
                    title=title.strip(),
                    description=description.strip(),
                    score_refs=tuple(
                        s
                        for s in (raw_refs if isinstance(raw_refs, list) else ())
                        if isinstance(s, str) and s.strip()
                    ),
                    depends_on=tuple(
                        d
                        for d in (raw_deps if isinstance(raw_deps, list) else ())
                        if isinstance(d, str) and d.strip()
                    ),
                    verify=verify,
                    status=status,
                    note=item.get("note", "") if isinstance(item.get("note", ""), str) else "",
                )
            )
        return cls(version=version, generated_at=generated_at, tasks=tuple(tasks))


# ---------------------------------------------------------------------------
# LLM 输出 → TaskPlan 解释链（域判决单址，照 ScorePoint / ImpactAnalysis 先例）
# ---------------------------------------------------------------------------


def build_task_plan(
    raw: Any, *, known_score_ids: Sequence[str] = ()
) -> TaskPlan:
    """把 LLM 输出的原始 dict 解析校验为 TaskPlan。

    LLM 契约形状：{"tasks": [{"title", "description", "score_refs", "depends_on",
    "verify"}]}——id 由解析层按顺序分配（t1..tn）；depends_on 用 1 起序号
    引用清单内任务（越界 = 拒收，结构问题宁重试不猜）；score_refs 引用传入
    评分点 id 清单（已知集非空时逐项校验，集外 = 拒收；无已知集 = 忽略该
    字段置空——历史目录无评分点，AI 编造 id 无意义）；verify 词表外 → 修正
    为 compile（值修正而非拒收）。任何结构问题（非 dict / 缺 tasks / 缺标题 /
    类型错）→ TaskError——LLM 输出不可信，宁可大声失败带病不拆。
    """
    if not isinstance(raw, dict):
        raise TaskError("任务拆解输出必须是 JSON 对象")
    raw_tasks = raw.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise TaskError("任务拆解输出的 tasks 必须是非空数组")
    known = set(known_score_ids)
    tasks: list[Task] = []
    for index, item in enumerate(raw_tasks, 1):
        if not isinstance(item, dict):
            raise TaskError(f"任务拆解输出第 {index} 项必须是对象")
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise TaskError(f"任务拆解输出第 {index} 项缺少标题")
        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            raise TaskError(f"任务拆解输出第 {index} 项缺少描述")
        score_refs = _score_refs(item.get("score_refs", []), index, known)
        depends_on = _depends_ids(item.get("depends_on", []), index, len(raw_tasks))
        verify = item.get("verify", VERIFY_COMPILE)
        if verify not in VALID_VERIFY:
            verify = VERIFY_COMPILE
        tasks.append(
            Task(
                id=f"t{index}",
                title=title.strip(),
                description=description.strip(),
                score_refs=score_refs,
                depends_on=depends_on,
                verify=verify,
            )
        )
    return TaskPlan(tasks=tuple(tasks))


def _score_refs(
    raw: Any, task_index: int, known: set[str]
) -> tuple[str, ...]:
    """score_refs 解析：非字符串数组 → 拒收；已知集非空时集外 id → 拒收；
    无已知集（历史目录无评分点清单）→ 置空（spec「无评分表时为空」）。"""
    if raw in (None, [], ()):
        return ()
    if not isinstance(raw, list) or any(
        not isinstance(ref, str) or not ref.strip() for ref in raw
    ):
        raise TaskError(f"任务拆解输出第 {task_index} 项的 score_refs 必须是字符串数组")
    refs = tuple(ref.strip() for ref in raw)
    if not known:
        return ()  # 无评分点清单：AI 编造 id 无意义，置空（宁缺勿假）
    unknown = [ref for ref in refs if ref not in known]
    if unknown:
        raise TaskError(
            f"任务拆解输出第 {task_index} 项引用未知评分点："
            + "、".join(unknown)
            + " —— 请只引用给出的评分点 id"
        )
    return refs


def _depends_ids(raw: Any, task_index: int, task_count: int) -> tuple[str, ...]:
    """depends_on 解析：1 起序号（LLM 契约）→ t{序号} id；越界 → 拒收。"""
    if raw in (None, [], ()):
        return ()
    if not isinstance(raw, list) or any(
        isinstance(i, bool) or not isinstance(i, int) or i < 1
        for i in raw
    ):
        raise TaskError(
            f"任务拆解输出第 {task_index} 项的 depends_on 必须是正整数序号数组"
        )
    invalid = [i for i in raw if i > task_count or i == task_index]
    if invalid:
        raise TaskError(
            f"任务拆解输出第 {task_index} 项的前置任务序号越界或引用自身："
            + "、".join(str(i) for i in invalid)
        )
    return tuple(f"t{i}" for i in raw)


# ---------------------------------------------------------------------------
# 清单文件读写（工程根 .contest_tasks.json 单源）
# ---------------------------------------------------------------------------


def load_task_plan_file(output_dir: Path) -> dict[str, Any] | None:
    """读清单原始 dict；无清单 = None；坏 JSON / 非对象 = TaskError（400）。"""
    path = output_dir / TASKS_MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskError(
            f"任务清单 {TASKS_MANIFEST_FILENAME} 损坏（不是合法 JSON）：{exc}"
        ) from exc
    if not isinstance(data, dict):
        raise TaskError(f"任务清单 {TASKS_MANIFEST_FILENAME} 必须是 JSON 对象")
    return data


def read_task_plan(output_dir: Path) -> TaskPlan | None:
    """读侧（缺字段/旧版本向后兼容）：清单文件 → 模型；无清单 = None。"""
    data = load_task_plan_file(output_dir)
    if data is None:
        return None
    return TaskPlan.from_dict(data)


def write_task_plan(output_dir: Path, plan: TaskPlan) -> Path:
    """清单落盘（工程根，纯新增文件；force 备档由调用方先行）。"""
    path = output_dir / TASKS_MANIFEST_FILENAME
    path.write_text(
        json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def backup_task_plan(output_dir: Path) -> bool:
    """旧清单备档（重新拆解前）：.contest_tasks.json → .contest_tasks.json.bak。

    旧 .bak 先删（单份备档策略，防残渣堆积）；无旧清单 = False（无备档）。
    """
    src = output_dir / TASKS_MANIFEST_FILENAME
    if not src.is_file():
        return False
    bak = output_dir / TASKS_MANIFEST_BAK_FILENAME
    if bak.is_file():
        bak.unlink()
    src.replace(bak)
    return True


def discard_task_plan(output_dir: Path) -> bool:
    """清单作废（修订重生成后）：删 .contest_tasks.json 与 .bak。

    返回是否有清单被删除（修订联动的 tasks_invalidated 标记依据）。
    """
    removed = False
    for name in (TASKS_MANIFEST_FILENAME, TASKS_MANIFEST_BAK_FILENAME):
        path = output_dir / name
        if path.is_file():
            path.unlink()
            removed = True
    return removed


# ---------------------------------------------------------------------------
# 域编排：拆解（工单 01）。执行编排（run_task）归工单 02。
# ---------------------------------------------------------------------------


def check_plan_replaceable(output_dir: Path, force: bool = False) -> None:
    """拆解前置守卫：清单已存在且未 force → TaskError（防误覆盖进度）。

    单实现（消息单源）：域编排与 webapp 路由共用——路由在起流前调用得到
    400 中文（历史目录 / 误点场景同步失败明确），域编排内再次调用作背兜
    （任何调用方都不得覆盖已有清单）。
    """
    if load_task_plan_file(output_dir) is not None and not force:
        raise TaskError(
            "该目录已有任务清单——如需重新拆解请使用「重新拆解」"
            "（旧清单会备档为 .contest_tasks.json.bak）"
        )


def run_task_planning(
    *,
    llm: LLM,
    problem_text: str,
    qa_text: str,
    requirements: Sequence[Mapping[str, Any]],
    score_points: Sequence[Mapping[str, Any]],
    manifests: Sequence[Any],
    platform: str,
    library_dir: Path,
    master_project_dir: Path,
    main_c: str,
    output_dir: Path,
    emit: SseEmitter,
    force: bool = False,
) -> dict[str, Any]:
    """/api/tasks/plan 的域编排：LLM 拆解 → 清单落盘（force = 旧清单备档）。

    模块接口清单 = build_skeleton_interfaces（与骨架 / 生成 / 深化同源）。
    score_points 为已解析的评分点 to_dict 列表（当前会话推荐结果；历史
    目录 = 空，任务不带分值标注）。main_c = 拆解前现读（手工编辑保留）。

    返回 done 载荷：{"version", "generated_at", "tasks": [...]}（任务状态
    全部 pending）。缺清单文件先备档（force）再覆盖；清单已存在且未 force
    → TaskError（前端引导用「重新拆解」，防误覆盖进度）。
    """
    from .skeleton import build_skeleton_interfaces

    emit.progress(ProgressEvent(type=EVENT_TASK_PLANNING))

    # 防误覆盖守卫（背兜；路由已在起流前调用同步 400，这里拦截任何其他调用方）
    check_plan_replaceable(output_dir, force)

    interfaces = build_skeleton_interfaces(
        manifests, platform, library_dir, master_project_dir
    )
    plan = llm.plan_tasks(
        problem_text=problem_text,
        qa_text=qa_text,
        requirements=requirements,
        score_points=score_points,
        module_interfaces=interfaces,
        main_c=main_c,
    )
    if not plan.tasks:
        raise TaskError("任务拆解结果为空——LLM 未产出任务清单，请重试")
    if force:
        backup_task_plan(output_dir)
    # 生成时间由域层落定（LLM 输出不含时间字段；done 载荷与落盘同源）
    stamped = TaskPlan(
        version=plan.version,
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        tasks=plan.tasks,
    )
    write_task_plan(output_dir, stamped)
    return stamped.to_dict()
