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
                "verify": "compile", "status": "pending", "note": "",
                "dialog_note": ""}]}

note = 补充框内容（执行时透传 LLM，未执行 = 空串）；dialog_note = 对话
采纳结论（每卡「和 AI 商量」里用户采纳的 AI 回复全文，工单 task-chat/01；
执行时作为独立段注入 prompt，采纳可选、空串 = 未采纳）。status 只在本域
状态机内变化，前置任务不强制阻断（展示与排序用途）。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .events import EVENT_TASK_EXECUTING, EVENT_TASK_PLANNING, ProgressEvent

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

# 迭代记录种类（工单 task-feedback/01）：execute = 初始执行 / feedback = 上板反馈轮
ITERATION_KIND_EXECUTE = "execute"
ITERATION_KIND_FEEDBACK = "feedback"

VALID_ITERATION_KINDS = frozenset({ITERATION_KIND_EXECUTE, ITERATION_KIND_FEEDBACK})

# 状态转移表（单源：人工改标端点 / 前端显隐 / 测试共用）——from → 允许的 to。
# 语义：pending → skipped（跳过不打算做的）；skipped → pending（恢复）；
# verified / unverified / failed → pending（重做）；unverified / failed →
# verified（人工上板确认改标）。doing（执行中）不可人工操作（LLM 调用 /
# 编译验证进行中，退出终态由 run_task 回填）；doing → 终态由域编排
# （run_task）不可经此表。
ALLOWED_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_PENDING: frozenset({STATUS_SKIPPED}),
    STATUS_SKIPPED: frozenset({STATUS_PENDING}),
    STATUS_VERIFIED: frozenset({STATUS_PENDING}),
    STATUS_UNVERIFIED: frozenset({STATUS_VERIFIED, STATUS_PENDING}),
    STATUS_FAILED: frozenset({STATUS_VERIFIED, STATUS_PENDING}),
    STATUS_DOING: frozenset(),
}


class TaskError(ValueError):
    """任务推进失败（清单损坏 / 缺上下文 / LLM 输出畸形），400 中文。"""


# ---------------------------------------------------------------------------
# 任务域模型：Task / TaskPlan（序列化与校验唯一所有者）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskIteration:
    """一轮执行记录（初始执行 / 上板反馈轮共同形状，工单 task-feedback/01）。

    seq = 任务内轮次序号（1 起）；kind = execute（初始实现）| feedback（上板
    反馈修复）；feedback = 用户反馈文本（execute 轮 = 空串）；status = 该轮
    结束后的任务终态（回滚到该轮时恢复用）；backup_id = 该轮整树备份 id
    （可回滚——用户拍板全部保留，一轮几十 KB~几 MB）；compile_summary =
    编译摘要（供卡上展示）；at = 轮次时间戳。
    """

    seq: int
    kind: str = ITERATION_KIND_EXECUTE
    feedback: str = ""
    status: str = ""
    backup_id: str = ""
    compile_summary: str = ""
    at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "feedback": self.feedback,
            "status": self.status,
            "backup_id": self.backup_id,
            "compile_summary": self.compile_summary,
            "at": self.at,
        }


@dataclass(frozen=True)
class Task:
    """一个实现任务（可独立执行、可独立编译验证的 main.c 增量）。

    id = 清单内序号（t1..tn，解析层分配）；score_refs = 关联评分点 id
    （来自题面评分点清单，无评分点 = 空）；depends_on = 前置任务 id
    （展示与排序用途，不强制阻断）；verify = 验收方式；status = 状态机
    当前态；note = 补充框内容（用户向 AI 补的一句说明，执行时透传）；
    dialog_note = 对话采纳结论（每卡「和 AI 商量」中用户采纳的 AI 回复
    全文，执行时作为独立段注入 prompt——比 note 话语新、优先级高）；
    iterations = 执行轮次历史（上板反馈闭环，向后兼容读回）。
    """

    id: str
    title: str
    description: str
    score_refs: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    verify: str = VERIFY_COMPILE
    status: str = STATUS_PENDING
    note: str = ""
    dialog_note: str = ""
    iterations: tuple[TaskIteration, ...] = ()

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
            "dialog_note": self.dialog_note,
            "iterations": [iteration.to_dict() for iteration in self.iterations],
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
                    dialog_note=(
                        item.get("dialog_note", "")
                        if isinstance(item.get("dialog_note", ""), str)
                        else ""
                    ),
                    iterations=_parse_iterations(item.get("iterations", [])),
                )
            )
        return cls(version=version, generated_at=generated_at, tasks=tuple(tasks))


def _parse_iterations(raw: Any) -> tuple[TaskIteration, ...]:
    """迭代历史读回（清单文件 → 模型）：整段损坏容错。

    旧清单无该字段 / 非数组 → 空元组（向后兼容）；单条非 dict / 缺 seq /
    kind 词表外 → 忽略该条（历史记录是展示与回滚辅助，坏值不应让整份
    清单不可用——与 status 词表外修正为默认同哲学，宁丢一条不误伤全清单）。
    其余字段非字符串 → 空串（to_dict 形状契约由本函数单源）。
    """
    if not isinstance(raw, list):
        return ()
    iterations: list[TaskIteration] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        seq = item.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int):
            continue
        kind = item.get("kind", ITERATION_KIND_EXECUTE)
        if kind not in VALID_ITERATION_KINDS:
            continue
        iterations.append(
            TaskIteration(
                seq=seq,
                kind=kind,
                feedback=_iter_opt_str(item, "feedback"),
                status=_iter_opt_str(item, "status"),
                backup_id=_iter_opt_str(item, "backup_id"),
                compile_summary=_iter_opt_str(item, "compile_summary"),
                at=_iter_opt_str(item, "at"),
            )
        )
    return tuple(iterations)


def _iter_opt_str(item: dict[str, Any], key: str) -> str:
    """迭代记录的可空字符串字段：非 str（含缺失/None/错型）一律落空串。"""
    value = item.get(key)
    return value if isinstance(value, str) else ""


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


# ---------------------------------------------------------------------------
# 域编排：单任务执行（工单 02）。共用深化尾段 verify_compile_tail（deepen.py）
# 与 main_diff（改名自 _main_diff，工单 02 起公共）。
# ---------------------------------------------------------------------------


def find_task(plan: TaskPlan, task_id: str) -> Task:
    """按 id 查任务；清单未拆解 / 任务不存在 → TaskError（400 中文）。"""
    if plan is None:
        raise TaskError("该目录尚未拆解任务——请先点「拆解任务」生成任务清单")
    for task in plan.tasks:
        if task.id == task_id:
            return task
    raise TaskError(f"任务清单里没有任务 {task_id}——清单可能已过期，请重新拆解")


def run_task(
    *,
    llm: LLM,
    task_id: str,
    note: str,
    problem_text: str,
    qa_text: str,
    manifests: Sequence[Any],
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
    feedback: str = "",
) -> dict[str, Any]:
    """/api/tasks/execute 的域编排：单任务 LLM 实现 → 备份 → 写盘 → 编译
    验证闭环（与深化共用 verify_compile_tail 尾段）→ 状态回填清单。

    任务 = 清单里的一个任务（find_task 查）。LLM 输入 = 当前 main.c + 任务
    描述 + 补充框（note，用户对本次执行的附加说明）+ 上板反馈（feedback，
    可选——用户烧录实测现象，工单 task-feedback/02）+ 模块接口 + 题面/Q&A；
    输出 = 实现后的 main.c 全文（与深化同形状，prompt 约束只实现本任务）。

    feedback 非空 = 上板反馈轮：任务当前为终态（verified / unverified /
    failed）时先自动重开（转移表 verified / unverified / failed → pending
    均合法），保证反馈修复的执行语义从 pending 起步（执行中 doing 不可人工
    操作的不变量不被破坏）；该轮迭代记录 kind = feedback。

    返回 done 载荷：{"task": 执行后任务 to_dict（状态 doing 已回填 -> 终态
    verified/unverified/failed）, "status", "backup_id", "compile",
    "main_diff", "message"}——status / compile / main_diff / message 与深化
    尾段同形状；task 为清单回填后的最新形状（前端据此重渲染该卡）。
    """
    from .deepen import main_diff, verify_compile_tail
    from .revision import backup_tree, revise_backup_root
    from .skeleton import build_skeleton_interfaces

    if not main_c.strip():
        raise TaskError("工程 main.c 为空，无法执行任务（请先生成或修订工程）")

    plan = read_task_plan(output_dir)
    if plan is None:
        raise TaskError("该目录尚未拆解任务——请先点「拆解任务」生成任务清单")
    task = find_task(plan, task_id)
    # 失败路径恢复用（不把任务钉死在 doing）——必须在自动重开**之前**捕获：
    # 反馈轮的终态任务先重开为 pending，若在重开后取 previous_status 会拿到
    # pending，LLM 失败时任务被错位恢复为 pending（而非反馈前终态，状态与
    # main.c 旧实现不一致）。先捕获原终态，重开只在成功后生效。
    previous_status = task.status
    # 上板反馈轮：终态任务先自动重开（verified/unverified/failed → pending
    # 均已在转移表；用户主动反馈 = 撤销终态改判，重新进入执行语义）
    if feedback and task.status in (
        STATUS_VERIFIED,
        STATUS_UNVERIFIED,
        STATUS_FAILED,
    ):
        plan, task = update_task_status(plan, task_id, STATUS_PENDING)
        write_task_plan(output_dir, plan)
    emit.progress(ProgressEvent(type=EVENT_TASK_EXECUTING))

    # 执行起始：状态 → doing 并落盘（前端实时可见；失败路径恢复 previous_status
    # ——异常 → 恢复后 re-raise，不静默回滚也不钉死）
    plan = _with_task_status(plan, task_id, STATUS_DOING)
    write_task_plan(output_dir, plan)

    try:
        interfaces = build_skeleton_interfaces(
            manifests, platform, library_dir, master_project_dir
        )
        executed = llm.execute_task(
            main_c=main_c,
            task=task.to_dict(),
            note=note,
            module_interfaces=interfaces,
            problem_text=problem_text,
            qa_text=qa_text,
            feedback=feedback,
        )
        if not executed.strip():
            raise TaskError("任务执行结果为空——LLM 未产出实现后的 main.c，请重试")
    except Exception:
        # 失败恢复：任务状态回 previous_status（LLM 空结果 / 接口装配失败等
        # 早于写盘的路径不留下 doing 钉子；已落盘的事故由用户重做 / 改标）
        try:
            write_task_plan(output_dir, _with_task_status(plan, task_id, previous_status))
        except TaskError:
            pass  # 恢复失败（清单并发损坏）不掩盖原始异常
        raise

    # 备份（与深化同一回滚入口：revise-backups）→ 写盘 → 单任务 diff
    backup_id = backup_tree(revise_backup_root(work_root), output_dir)
    (output_dir / "main.c").write_text(executed, encoding="utf-8")
    diff = main_diff(main_c, executed)  # deepen.main_diff（公共，工单 02）

    # 编译验证闭环（与深化共用尾段；main_diff 已算好；subject = 任务上下文）
    result = verify_compile_tail(
        llm=llm,
        platform=platform,
        output_dir=output_dir,
        work_root=work_root,
        problem_text=problem_text,
        module_slugs=module_slugs,
        main_c=executed,
        uv4_override=uv4_override,
        make_override=make_override,
        emit=emit,
        backup_id=backup_id,
        main_diff=diff,
        subject="任务结果",
    )

    # verify=manual 的任务：即使编译通过初始也为 unverified（spec 用户拍板
    # ——编译绿只证明语法/链接正确，该任务的验收方式是上板观察现象，由学生
    # 上板后人工改标 verified；message + verify_cause 覆盖提示语义——前端
    # 徽章按 cause 区分「无工具链降级」与「手动验收待确认」，不能只按 status）
    if task.verify == VERIFY_MANUAL and result["status"] == STATUS_VERIFIED:
        result = {
            **result,
            "status": STATUS_UNVERIFIED,
            "verify_cause": "manual",
            "message": (
                "编译验证通过，但本任务验收方式为「上板人工确认」——状态为"
                "未验证：请烧录观察现象后标记为「已验证」"
            ),
        }

    # 状态回填（终态写盘；note 持久化——补充框内容刷新不丢，spec 用户故事 10；
    # 迭代历史追加——每轮执行记录（备份点 / 终态），回滚到任意轮靠它）
    iteration = TaskIteration(
        seq=len(task.iterations) + 1,
        kind=ITERATION_KIND_FEEDBACK if feedback else ITERATION_KIND_EXECUTE,
        feedback=feedback,
        status=result["status"],
        backup_id=backup_id,
        compile_summary=str(result.get("compile", {}).get("summary", "") or ""),
        at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )
    updated_plan = _with_task_status(
        plan,
        task_id,
        result["status"],
        note=note,
        iterations=task.iterations + (iteration,),
    )
    write_task_plan(output_dir, updated_plan)
    updated = find_task(updated_plan, task_id)
    return {"task": updated.to_dict(), **result}


def _with_task_status(
    plan: TaskPlan,
    task_id: str,
    status: str,
    note: str | None = None,
    dialog_note: str | None = None,
    iterations: tuple[TaskIteration, ...] | None = None,
) -> TaskPlan:
    """任务状态替换（纯函数）：任务不存在 → TaskError；状态词表外 → TaskError。

    note 非 None 时一并替换（执行后持久化补充框内容——spec 用户故事 10
    「任务清单与进度（id / 描述 / 状态 / 备注）」；None = 只改状态）。
    dialog_note 非 None 时一并替换（采纳对话结论——工单 task-chat/01；
    None = 保留原值）。
    iterations 非 None 时一并替换（执行后追加轮次历史——工单 task-feedback/01；
    None = 保留原值）。
    """
    if status not in ALL_STATUSES:
        raise TaskError(f"非法任务状态：{status}")
    tasks = []
    found = False
    for task in plan.tasks:
        if task.id == task_id:
            found = True
            tasks.append(
                Task(
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    score_refs=task.score_refs,
                    depends_on=task.depends_on,
                    verify=task.verify,
                    status=status,
                    note=task.note if note is None else note,
                    dialog_note=task.dialog_note if dialog_note is None else dialog_note,
                    iterations=task.iterations if iterations is None else iterations,
                )
            )
        else:
            tasks.append(task)
    if not found:
        raise TaskError(f"任务清单里没有任务 {task_id}——清单可能已过期，请重新拆解")
    return TaskPlan(
        version=plan.version,
        generated_at=plan.generated_at,
        tasks=tuple(tasks),
    )


def update_task_status(
    plan: TaskPlan, task_id: str, status: str
) -> tuple[TaskPlan, Task]:
    """人工改标（纯函数，工单 03）：按转移表校验 → 替换状态 → (新清单, 任务)。

    校验失败 → TaskError（400 中文，消息带允许的目标状态清单）；doing
    （执行中）不可人工操作。只改状态不动 note。
    """
    if status not in ALL_STATUSES:
        raise TaskError(f"非法任务状态：{status}")
    task = find_task(plan, task_id)
    allowed = ALLOWED_STATUS_TRANSITIONS.get(task.status, frozenset())
    if status not in allowed:
        targets = "、".join(sorted(allowed)) if allowed else "无（执行中不可操作）"
        raise TaskError(
            f"任务 {task_id} 当前状态 {task.status} 不能改为 {status}"
            f"（允许：{targets}）"
        )
    updated_plan = _with_task_status(plan, task_id, status)
    return updated_plan, find_task(updated_plan, task_id)


def apply_task_status(output_dir: Path, task_id: str, status: str) -> dict[str, Any]:
    """人工改标域编排（工单 03）：读清单 → 转移校验 → 落盘 → (任务, 清单)。

    路由薄壳（对照 /api/revise/apply → run_revision 先例）：读-验-写单址，
    不变量「校验失败都在落盘前」由纯函数 update_task_status 保证（先校验
    后写盘，无部分写入窗口）。返回 {"task", "plan"}。
    """
    plan = read_task_plan(output_dir)
    if plan is None:
        raise TaskError("该目录尚未拆解任务——请先点「拆解任务」生成任务清单")
    updated_plan, task = update_task_status(plan, task_id, status)
    write_task_plan(output_dir, updated_plan)
    return {"task": task.to_dict(), "plan": updated_plan.to_dict()}


def set_task_dialog_note(
    output_dir: Path, task_id: str, text: str
) -> dict[str, Any]:
    """采纳 / 清除对话结论（工单 task-chat/01）：读清单 → 替换 dialog_note →
    落盘 → (任务, 清单)。

    text 为空串 = 清除采纳（用户取消 / 采纳错了）。text 非字符串由路由层
    校验（照 note/feedback 的 _optional_str 先例）；本函数只做域判决：
    清单未拆解 / 任务不存在 → TaskError 400。返回 {"task", "plan"}。
    """
    plan = read_task_plan(output_dir)
    if plan is None:
        raise TaskError("该目录尚未拆解任务——请先点「拆解任务」生成任务清单")
    task = find_task(plan, task_id)
    updated_plan = _with_task_status(plan, task_id, task.status, dialog_note=text)
    write_task_plan(output_dir, updated_plan)
    updated = find_task(updated_plan, task_id)
    return {"task": updated.to_dict(), "plan": updated_plan.to_dict()}


def rollback_task_iteration(
    output_dir: Path, task_id: str, seq: int, backup_root: Path
) -> dict[str, Any]:
    """回滚到指定轮次（工单 task-feedback/03）：撤销语义。

    备份时机 = 该轮写盘**前**（run_task：backup_tree → write），故该轮迭代
    记录的 backup_id = 「该轮执行前」的整树快照——回滚 = 恢复该快照 + 状态
    恢复为「该轮之前的终态」（向前找最近历史轮次的 status；无前轮 →
    pending），代码与状态同源一致（回到做这一轮之前的样子）。迭代历史
    本身保留（撤销不改历史，留痕可追溯，用户可再执行/再反馈造新轮）。

    校验：清单存在 / 任务存在 / 轮次存在且有备份 id → 否则 TaskError 400；
    备份恢复走 revision.restore_revision（路径安全校验 + 清空恢复内建，
    与修订回滚同入口）。轮次状态恢复绕过转移表（回滚 = 恢复历史事实，
    非人工改标）。

    返回 {"task": 回滚后任务 to_dict, "plan": 全量清单 to_dict,
    "restored": 恢复文件相对路径列表}。
    """
    from .revision import restore_revision

    plan = read_task_plan(output_dir)
    if plan is None:
        raise TaskError("该目录尚未拆解任务——请先点「拆解任务」生成任务清单")
    task = find_task(plan, task_id)
    iteration = next((it for it in task.iterations if it.seq == seq), None)
    if iteration is None:
        raise TaskError(f"任务 {task_id} 没有第 {seq} 轮记录——无法回滚")
    if not iteration.backup_id:
        raise TaskError(f"任务 {task_id} 第 {seq} 轮没有备份——无法回滚")
    restored = restore_revision(backup_root, iteration.backup_id, output_dir)
    # 该轮之前的终态：向前找最近历史轮次（iterations 按 seq 递增追加）；
    # 无前轮（seq=1）→ pending；前轮终态词表外 → 兜底 pending
    prev_status = STATUS_PENDING
    for it in task.iterations:
        if it.seq < seq and it.status in ALL_STATUSES:
            prev_status = it.status
    updated_plan = _with_task_status(plan, task_id, prev_status)
    write_task_plan(output_dir, updated_plan)
    updated = find_task(updated_plan, task_id)
    return {
        "task": updated.to_dict(),
        "plan": updated_plan.to_dict(),
        "restored": list(restored),
    }
