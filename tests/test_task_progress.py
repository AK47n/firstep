"""任务推进（工单 task-progress/01）：任务拆解 + 清单落盘的测试。

只测外部行为：LLM 拆解调用（输入装配断言）、域判决（build_task_plan 的
id 分配 / depends_on 序号转 id / score_refs 校验 / verify 词表修正 / 畸形
拒收）、清单文件读写 roundtrip + 坏 JSON、force 备档、重复拆解拦截、
webapp /api/tasks/plan 端点（SSE 事件序列 + 错误路径）。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from contest_generator.platforms import PLATFORM_STM32
from contest_generator.llm import IdeaAnalysis, StepReport
from contest_generator.revision import revise_backup_root
from contest_generator.task_progress import (
    ALLOWED_STATUS_TRANSITIONS,
    STATUS_DOING,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    STATUS_UNVERIFIED,
    STATUS_VERIFIED,
    TASKS_MANIFEST_BAK_FILENAME,
    TASKS_MANIFEST_FILENAME,
    Task,
    TaskError,
    TaskIteration,
    TaskPlan,
    VERIFY_COMPILE,
    VERIFY_MANUAL,
    backup_task_plan,
    build_task_plan,
    find_task,
    insert_task_from_idea,
    move_task,
    read_task_plan,
    rollback_task_iteration,
    run_direct_fix,
    run_task,
    run_task_planning,
    set_task_dialog_note,
    set_tasks_needs_redo,
    update_task_fields,
    update_task_status,
    write_task_plan,
)
from contest_generator.task_progress import _with_task_status
from contest_generator.webapp import AppContext, AppConfig, create_app
from tests.fakes import FakeLLM, make_fake_master_project, make_fake_module_library
from tests.test_impact import _sse_events


def _raw_tasks(tasks):
    """LLM 输出形状（无 id——id 由域层分配）。"""
    return {"tasks": tasks}


def test_build_task_plan_assigns_ids_and_converts_depends():
    """合法输出：id 按顺序分配（t1..tn）；depends_on 序号转 id；verify 保留。"""
    plan = build_task_plan(
        _raw_tasks(
            [
                {
                    "title": "ADC 采样",
                    "description": "初始化 ADC",
                    "score_refs": [],
                    "depends_on": [],
                    "verify": "compile",
                    "resources": ["PA0", "TIM1"],
                },
                {
                    "title": "OLED 显示",
                    "description": "显示采样值",
                    "score_refs": ["s1"],
                    "depends_on": [1],
                    "verify": "manual",
                    "resources": ["UART0"],
                },
            ]
        ),
        known_score_ids=["s1"],
    )
    assert [task.id for task in plan.tasks] == ["t1", "t2"]
    assert plan.tasks[0].depends_on == ()
    assert plan.tasks[1].depends_on == ("t1",)
    assert plan.tasks[1].score_refs == ("s1",)
    assert plan.tasks[1].verify == VERIFY_MANUAL
    assert all(task.status == STATUS_PENDING for task in plan.tasks)
    # 互斥资源标注（工单 task-insight/01）：正常列表保留
    assert plan.tasks[0].resources == ("PA0", "TIM1")
    assert plan.tasks[1].resources == ("UART0",)


def test_build_task_plan_resources_lenient():
    """resources 宽松解析（spec：辅助信息宁空勿拒）：非数组 → ()；
    数组内非 str / 空串项过滤（strip 后保留非空）。"""
    plan = build_task_plan(
        _raw_tasks(
            [
                {
                    "title": "任务",
                    "description": "描述",
                    "resources": ["PA0", 123, "", "  TIM1  ", None],
                }
            ]
        )
    )
    assert plan.tasks[0].resources == ("PA0", "TIM1")
    plan_missing = build_task_plan(
        _raw_tasks([{"title": "任务", "description": "描述"}])
    )
    assert plan_missing.tasks[0].resources == ()
    plan_bad = build_task_plan(
        _raw_tasks([{"title": "任务", "description": "描述", "resources": "PA0"}])
    )
    assert plan_bad.tasks[0].resources == ()


def test_build_task_plan_verify_word_outside_list_corrected():
    """verify 词表外 → 修正为 compile（值修正而非拒收）。"""
    plan = build_task_plan(
        _raw_tasks(
            [
                {
                    "title": "任务",
                    "description": "描述",
                    "verify": "onboard",
                }
            ]
        )
    )
    assert plan.tasks[0].verify == VERIFY_COMPILE


def test_build_task_plan_missing_tasks_rejected():
    """缺 tasks / 空数组 / 非对象 → TaskError（大声失败，不静默拆空单）。"""
    with pytest.raises(TaskError):
        build_task_plan({})
    with pytest.raises(TaskError):
        build_task_plan(_raw_tasks([]))
    with pytest.raises(TaskError):
        build_task_plan({"tasks": "not-a-list"})


def test_build_task_plan_missing_title_rejected():
    """缺标题 / 空标题 → TaskError。"""
    with pytest.raises(TaskError):
        build_task_plan(_raw_tasks([{"description": "无标题"}]))
    with pytest.raises(TaskError):
        build_task_plan(_raw_tasks([{"title": "  ", "description": "空标题"}]))


def test_build_task_plan_depends_out_of_range_rejected():
    """depends_on 越界 / 引用自身 / 非正整数 → TaskError。"""
    with pytest.raises(TaskError):
        build_task_plan(
            _raw_tasks(
                [{"title": "A", "description": "x", "depends_on": [3]},
                 {"title": "B", "description": "y"}],
            )
        )
    with pytest.raises(TaskError):
        build_task_plan(
            _raw_tasks(
                [{"title": "A", "description": "x", "depends_on": [1]}],
            )
        )
    with pytest.raises(TaskError):
        build_task_plan(
            _raw_tasks(
                [{"title": "A", "description": "x", "depends_on": ["1"]}],
            )
        )


def test_build_task_plan_score_refs_unknown_rejected():
    """已知评分点集非空时引用集外 id → TaskError（宁重试不猜）。"""
    with pytest.raises(TaskError):
        build_task_plan(
            _raw_tasks(
                [{"title": "A", "description": "x", "score_refs": ["s9"]}],
            ),
            known_score_ids=["s1"],
        )
    # 无已知集（历史目录无评分点清单）→ 置空（spec「无评分表时为空」）
    plan = build_task_plan(
        _raw_tasks([{"title": "A", "description": "x", "score_refs": ["编的"]}])
    )
    assert plan.tasks[0].score_refs == ()


def test_task_plan_file_roundtrip_and_bad_json(tmp_path):
    """落盘写读 roundtrip；坏 JSON / 非对象 → TaskError；缺文件 = None。"""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    plan = TaskPlan(
        generated_at="2026-08-18T10:00:00+0800",
        tasks=(Task(id="t1", title="循迹", description="循迹决策"),),
    )
    write_task_plan(output_dir, plan)
    loaded = read_task_plan(output_dir)
    assert loaded == plan
    # 缺文件 = None（未拆解）
    assert read_task_plan(tmp_path / "none") is None
    # 坏 JSON → TaskError（400 中文）
    (output_dir / TASKS_MANIFEST_FILENAME).write_text("{broken", encoding="utf-8")
    with pytest.raises(TaskError):
        read_task_plan(output_dir)
    # 非对象 → TaskError
    (output_dir / TASKS_MANIFEST_FILENAME).write_text("[1,2]", encoding="utf-8")
    with pytest.raises(TaskError):
        read_task_plan(output_dir)


def test_task_plan_from_dict_tolerates_unknown_status_and_missing_fields():
    """读回侧：status 词表外修正为 pending；缺字段补默认；未知字段忽略。"""
    raw = {
        "version": 1,
        "generated_at": "",
        "tasks": [
            {
                "id": "t1",
                "title": "任务",
                "description": "描述",
                "status": "not-a-status",
                "score_refs": "not-a-list",
                "depends_on": ["t2"],
                "verify": "weird",
                "note": 123,
                "future_field": "忽略",
            }
        ],
    }
    plan = TaskPlan.from_dict(raw)
    assert plan.tasks[0].status == STATUS_PENDING
    assert plan.tasks[0].score_refs == ()
    assert plan.tasks[0].verify == VERIFY_COMPILE
    assert plan.tasks[0].note == ""


def test_backup_and_discard(tmp_path):
    """备档：旧清单 → .bak（旧 .bak 先删）；修订作废路径由 revision 的 rmtree
    覆盖（清单文件随整树删除，见 test_revision_regeneration_invalidates_tasks）。"""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    plan = TaskPlan(tasks=(Task(id="t1", title="A", description="x"),))
    write_task_plan(output_dir, plan)
    assert backup_task_plan(output_dir) is True
    assert (output_dir / TASKS_MANIFEST_FILENAME).exists() is False
    assert (output_dir / TASKS_MANIFEST_BAK_FILENAME).exists() is True
    # 无清单 = False
    assert backup_task_plan(output_dir) is False


def test_run_task_planning_writes_plan_and_emits_event(tmp_path):
    """域编排：LLM 拆解 → 落盘 → 返回清单任务（全部 pending）；发射
    task_planning 进度事件。"""
    from contest_generator.generator import generate_project

    library = make_fake_module_library(tmp_path / "modules")
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    output_dir = tmp_path / "out"
    generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
        problem_text="题面",
    )
    llm = FakeLLM(
        task_plan=TaskPlan(
            tasks=(Task(id="t1", title="循迹", description="循迹决策"),)
        )
    )
    events: list[str] = []

    def emit_progress(event) -> None:
        events.append(event.type)

    result = run_task_planning(
        llm=llm,
        problem_text="题面",
        qa_text="",
        requirements=[{"requirement": "循迹", "sentence": 1}],
        score_points=[],
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        emit=SimpleNamespace(progress=emit_progress),  # type: ignore[arg-type]
    )
    assert events == ["task_planning"]
    assert result["tasks"][0]["title"] == "循迹"
    assert result["tasks"][0]["status"] == STATUS_PENDING
    # generated_at 由域层落定（done 载荷与落盘同源，非空）
    assert result["generated_at"]
    saved = read_task_plan(output_dir)
    assert saved is not None
    assert saved.tasks[0].id == "t1"
    assert saved.generated_at == result["generated_at"]
    # LLM 收到装配好的输入（题面 / 需求 / main.c）
    assert llm.plan_tasks_calls[0][0] == "题面"
    assert llm.plan_tasks_calls[0][2] == ({"requirement": "循迹", "sentence": 1},)
    assert llm.plan_tasks_calls[0][5] == "int main(void) { /* TODO */ while (1); }\n"


def test_run_task_planning_existing_without_force_rejected(tmp_path):
    """清单已存在且未 force → TaskError（防误覆盖进度）。"""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    write_task_plan(
        output_dir, TaskPlan(tasks=(Task(id="t1", title="旧", description="旧"),))
    )
    llm = FakeLLM()
    with pytest.raises(TaskError):
        run_task_planning(
            llm=llm,
            problem_text="题面",
            qa_text="",
            requirements=(),
            score_points=[],
            manifests=[],
            platform=PLATFORM_STM32,
            library_dir=tmp_path,
            master_project_dir=tmp_path,
            main_c="main",
            output_dir=output_dir,
            emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
        )


def test_run_task_planning_force_backs_up_old_plan(tmp_path):
    """force 重新拆解：旧清单 → .bak，新清单覆盖。"""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    write_task_plan(
        output_dir, TaskPlan(tasks=(Task(id="t1", title="旧", description="旧"),))
    )
    llm = FakeLLM(
        task_plan=TaskPlan(
            tasks=(Task(id="t1", title="新", description="新"),)
        )
    )
    result = run_task_planning(
        llm=llm,
        problem_text="题面",
        qa_text="",
        requirements=(),
        score_points=[],
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=tmp_path,
        master_project_dir=tmp_path,
        main_c="main",
        output_dir=output_dir,
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
        force=True,
    )
    assert result["tasks"][0]["title"] == "新"
    assert (output_dir / TASKS_MANIFEST_BAK_FILENAME).exists() is True
    archived = json.loads(
        (output_dir / TASKS_MANIFEST_BAK_FILENAME).read_text(encoding="utf-8")
    )
    assert archived["tasks"][0]["title"] == "旧"


# ---------------------------------------------------------------------------
# webapp /api/tasks/plan：SSE 事件序列与错误路径
# ---------------------------------------------------------------------------


@pytest.fixture
def tasks_client(tmp_path):
    """已配置的假上下文：假模块库 + 假母版 + 假 LLM（照 deepen_client 先例）。"""
    config_path = tmp_path / "cfg" / "config.json"
    library_dir = make_fake_module_library(tmp_path / "module_library")
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    holder: dict = {"llm": FakeLLM()}
    ctx = AppContext(
        config_path=config_path,
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=library_dir,
            masters_dir=tmp_path / "masters",
        ),
        llm_factory=lambda config: holder["llm"],
        desktop_dir=lambda: tmp_path / "Desktop",
    )
    return TestClient(create_app(ctx)), holder, tmp_path


def _generate_project(client, tmp_path) -> str:
    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "main_c": "int main(void) { /* TODO */ while (1); }\n",
            "problem_text": "2024 巡线小车",
            "output_dir": str(tmp_path / "out"),
            "requirements": [{"requirement": "循迹", "sentence": 1, "modules": ["dht11"]}],
            "score_points": [
                {"id": "s1", "part": "basic", "description": "循迹", "score": 20}
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["output_dir"]


def test_tasks_plan_sse_flow(tasks_client):
    """拆解端点：task_planning → done（任务清单全部 pending）；清单落盘。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(
            tasks=(
                Task(id="t1", title="循迹", description="循迹决策", score_refs=("s1",)),
                Task(id="t2", title="OLED 显示", description="显示分值", depends_on=("t1",)),
            )
        )
    )
    resp = client.post(
        "/api/tasks/plan",
        json={
            "output_dir": output_dir,
            "score_points": [
                {"id": "s1", "part": "basic", "description": "循迹", "score": 20}
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    types = [event_type for event_type, _ in events]
    assert types[-1] == "done"
    assert "task_planning" in types
    done = events[-1][1]
    assert [task["title"] for task in done["tasks"]] == ["循迹", "OLED 显示"]
    assert all(task["status"] == STATUS_PENDING for task in done["tasks"])
    assert done["tasks"][1]["depends_on"] == ["t1"]
    # 清单落盘
    saved = json.loads(
        (Path(output_dir) / TASKS_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert [task["title"] for task in saved["tasks"]] == ["循迹", "OLED 显示"]
    # LLM 收到评分点（当前会话推荐结果）
    assert holder["llm"].plan_tasks_calls[0][3][0]["id"] == "s1"


def test_tasks_plan_replan_with_force_backs_up(tasks_client):
    """force 重新拆解：旧清单 → .bak；新清单覆盖。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="旧任务", description="旧"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="新任务", description="新"),))
    )
    resp = client.post(
        "/api/tasks/plan", json={"output_dir": output_dir, "force": True}
    )
    assert resp.status_code == 200, resp.text
    assert _sse_events(resp)[-1][1]["tasks"][0]["title"] == "新任务"
    assert (Path(output_dir) / TASKS_MANIFEST_BAK_FILENAME).exists() is True


def test_tasks_plan_existing_without_force_400(tasks_client):
    """清单已存在且未 force → 400 中文（引导用重新拆解）。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    resp = client.post("/api/tasks/plan", json={"output_dir": output_dir})
    assert resp.status_code == 400
    assert "重新拆解" in resp.json()["detail"]


def test_tasks_plan_missing_problem_text_400(tasks_client):
    """缺题面（历史目录无上下文清单且未补题面）→ 400 中文提示。"""
    client, _, tmp_path = tasks_client
    out = tmp_path / "manual"
    out.mkdir()
    (out / "project.uvprojx").write_text("<Project/>", encoding="utf-8")
    (out / "main.c").write_text("int main(void) {}\n", encoding="utf-8")
    resp = client.post("/api/tasks/plan", json={"output_dir": str(out)})
    assert resp.status_code == 400
    assert "题面" in resp.json()["detail"]


def test_tasks_plan_output_dir_missing_400(tasks_client):
    """输出目录不存在 → 400 中文。"""
    client, _, tmp_path = tasks_client
    resp = client.post(
        "/api/tasks/plan", json={"output_dir": str(tmp_path / "none")}
    )
    assert resp.status_code == 400
    assert "不存在" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# run_task：单任务执行（工单 02）——备份 / 写盘 / 编译三态 / 状态回填
# ---------------------------------------------------------------------------


def _task_env(tmp_path):
    """假模块库 + 假母版 + 生成工程 + 拆好任务清单（t1 循迹）。"""
    from contest_generator.generator import generate_project

    library = make_fake_module_library(tmp_path / "modules")
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    output_dir = tmp_path / "out"
    generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
        problem_text="题面",
    )
    write_task_plan(
        output_dir,
        TaskPlan(
            tasks=(
                Task(id="t1", title="循迹", description="循迹决策"),
                Task(id="t2", title="OLED 显示", description="显示", depends_on=("t1",)),
            )
        ),
    )
    return library, output_dir


def _build(exit_code: int, output: str = ""):
    """假编译结果（compile_runner.BuildLog 同构形状，照 test_deepen 先例）。"""
    from types import SimpleNamespace

    return SimpleNamespace(
        platform=PLATFORM_STM32,
        run=SimpleNamespace(
            exit_code=exit_code, output=output, timed_out=False, duration=0.1
        ),
    )


def _no_toolchain(monkeypatch):
    """无工具链：resolve_compile_toolchain 抛 CompileRunnerError（转降级）。"""
    from contest_generator.compile_runner import CompileRunnerError

    def _raise(platform, uv4_override="", make_override=""):
        raise CompileRunnerError("未检测到工具链")

    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain", _raise
    )


def test_run_task_without_toolchain_degrades_loudly(tmp_path, monkeypatch):
    """无工具链 → 降级：结果保留、状态 = unverified、备份存在、清单回填未验证。"""
    library, output_dir = _task_env(tmp_path)
    _no_toolchain(monkeypatch)
    llm = FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n")
    events: list[str] = []

    def emit_progress(event) -> None:
        events.append(event.type)

    result = run_task(
        llm=llm,
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=emit_progress),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_UNVERIFIED
    assert "未验证" in result["message"]
    assert result["backup_id"]
    assert "循迹已实现" in (output_dir / "main.c").read_text(encoding="utf-8")
    assert events[0] == "task_executing"
    assert "verify_result" in events
    # 清单回填：任务状态 = unverified
    saved = read_task_plan(output_dir)
    assert saved is not None
    assert saved.tasks[0].status == STATUS_UNVERIFIED
    assert saved.tasks[1].status == STATUS_PENDING  # 未执行任务不受影响


def test_run_task_verified_when_compile_passes(tmp_path, monkeypatch):
    """有工具链 + 编译绿 → 状态 = verified；note 进 LLM 调用。"""
    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    llm = FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n")
    result = run_task(
        llm=llm,
        task_id="t1",
        note="循迹用 10ms 定时器",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_VERIFIED
    assert result["compile"]["passed"] is True
    assert result["task"]["status"] == STATUS_VERIFIED
    assert "main_diff" in result
    # note 透传 LLM
    assert llm.execute_task_calls[0][2] == "循迹用 10ms 定时器"
    assert llm.execute_task_calls[0][1]["id"] == "t1"


def test_run_task_failed_after_one_fix_round(tmp_path, monkeypatch):
    """修一轮仍红 → 状态 = failed（结果保留，中文提示）。"""
    from types import SimpleNamespace

    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(2, "error: x"),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.run_fix_round",
        lambda llm, **kwargs: SimpleNamespace(backup_id="fix-1", results=()),
    )
    llm = FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n")
    result = run_task(
        llm=llm,
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_FAILED
    assert "仍红" in result["message"]
    saved = read_task_plan(output_dir)
    assert saved is not None
    assert saved.tasks[0].status == STATUS_FAILED


def test_run_task_unknown_task_id_raises(tmp_path):
    """任务 id 不存在 / 清单未拆解 → TaskError（400 中文）。"""
    library, output_dir = _task_env(tmp_path)
    llm = FakeLLM()
    with pytest.raises(TaskError):
        run_task(
            llm=llm,
            task_id="t99",
            note="",
            problem_text="题面",
            qa_text="",
            manifests=[],
            platform=PLATFORM_STM32,
            library_dir=library,
            master_project_dir=tmp_path,
            main_c="main",
            output_dir=output_dir,
            work_root=tmp_path / "work",
            emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
        )
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(TaskError):
        run_task(
            llm=llm,
            task_id="t1",
            note="",
            problem_text="题面",
            qa_text="",
            manifests=[],
            platform=PLATFORM_STM32,
            library_dir=library,
            master_project_dir=tmp_path,
            main_c="main",
            output_dir=empty_dir,
            work_root=tmp_path / "work",
            emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
        )


def test_run_task_note_persisted_and_message_task_flavored(tmp_path, monkeypatch):
    """note 落盘（刷新不丢，spec 用户故事 10）；message 用「任务」措辞（不泄
    漏「深化」字眼——共享尾段 subject 参数，评审发现）。"""
    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    llm = FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n")
    result = run_task(
        llm=llm,
        task_id="t1",
        note="循迹用 10ms 定时器",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_VERIFIED
    assert "任务结果" in result["message"]  # 任务语境措辞
    assert "深化" not in result["message"]  # 不泄漏深化字眼
    saved = read_task_plan(output_dir)
    assert saved is not None
    assert saved.tasks[0].note == "循迹用 10ms 定时器"  # note 落盘


def test_run_task_empty_llm_result_reverts_doing(tmp_path):
    """LLM 空结果 → TaskError；任务状态恢复 previous（不钉死在 doing）。"""
    library, output_dir = _task_env(tmp_path)
    llm = FakeLLM(executed_main_c="   ")
    with pytest.raises(TaskError):
        run_task(
            llm=llm,
            task_id="t1",
            note="",
            problem_text="题面",
            qa_text="",
            manifests=[],
            platform=PLATFORM_STM32,
            library_dir=library,
            master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
            main_c="int main(void) { /* TODO */ while (1); }\n",
            output_dir=output_dir,
            work_root=tmp_path / "work",
            emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
        )
    saved = read_task_plan(output_dir)
    assert saved is not None
    assert saved.tasks[0].status == STATUS_PENDING  # 恢复 previous，不钉 doing


def test_run_task_feedback_empty_result_reverts_terminal(tmp_path, monkeypatch):
    """反馈轮 LLM 空结果 → 恢复**反馈前终态**而非 pending（评审 (c) 修复回归：
    previous_status 必须在自动重开前捕获——若在重开后捕获会拿到 pending，
    任务错位恢复为「pending + 旧 verified 实现」）。"""
    library, output_dir = _task_env(tmp_path)
    _green_toolchain(monkeypatch, tmp_path)
    plan = TaskPlan(
        tasks=(Task(id="t1", title="循迹", description="循迹决策"),)
    )
    # 首轮：verified
    run_task(
        llm=FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n"),
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert read_task_plan(output_dir).tasks[0].status == STATUS_VERIFIED
    # 反馈轮：LLM 空结果 → TaskError；状态必须回 verified（反馈前终态）
    with pytest.raises(TaskError):
        run_task(
            llm=FakeLLM(executed_main_c="   "),
            task_id="t1",
            note="",
            problem_text="题面",
            qa_text="",
            manifests=[],
            platform=PLATFORM_STM32,
            library_dir=library,
            master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
            main_c="int main(void) { /* 循迹已实现 */ while (1); }\n",
            output_dir=output_dir,
            work_root=tmp_path / "work",
            emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
            feedback="上板发现左轮不转",
        )
    saved = read_task_plan(output_dir)
    assert saved is not None
    assert saved.tasks[0].status == STATUS_VERIFIED  # 反馈前终态，非 pending
    assert len(saved.tasks[0].iterations) == 1  # 失败轮不落迭代记录


def test_find_task_missing_plan():
    """清单未拆解（None）→ TaskError；找不到任务 → TaskError。"""
    with pytest.raises(TaskError):
        find_task(None, "t1")
    plan = TaskPlan(tasks=(Task(id="t1", title="A", description="x"),))
    assert find_task(plan, "t1").title == "A"
    with pytest.raises(TaskError):
        find_task(plan, "t2")


def test_tasks_plan_read_endpoint(tasks_client):
    """清单读取端点：未拆解 = plan None；拆解后 = 清单全量（回滚后刷新用）。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    resp = client.post("/api/tasks/plan-read", json={"output_dir": output_dir})
    assert resp.status_code == 200
    assert resp.json()["plan"] is None
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    resp = client.post("/api/tasks/plan-read", json={"output_dir": output_dir})
    assert resp.status_code == 200
    assert resp.json()["plan"]["tasks"][0]["title"] == "循迹"


def test_tasks_execute_sse_flow(tasks_client, monkeypatch):
    """执行端点：task_executing → done（verified）；清单状态已回填。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(
            tasks=(Task(id="t1", title="循迹", description="循迹决策"),)
        )
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    holder["llm"] = FakeLLM(
        executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n"
    )
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    resp = client.post(
        "/api/tasks/execute", json={"output_dir": output_dir, "task_id": "t1"}
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    types = [event_type for event_type, _ in events]
    assert types[-1] == "done"
    assert "task_executing" in types
    assert "task_reporting" in types  # 步骤报告事件（工单 stepwise-deepen/01）
    done = events[-1][1]
    assert done["status"] == STATUS_VERIFIED
    assert done["task"]["status"] == STATUS_VERIFIED
    # 清单落盘回填
    saved = json.loads(
        (Path(output_dir) / TASKS_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert saved["tasks"][0]["status"] == STATUS_VERIFIED
    # 写盘生效
    assert "循迹已实现" in (Path(output_dir) / "main.c").read_text(encoding="utf-8")


def test_tasks_execute_feedback_not_string_400(tasks_client):
    """feedback 非字符串 → 400 中文（表单契约校验，_optional_str 单源）。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    resp = client.post(
        "/api/tasks/execute",
        json={
            "output_dir": output_dir,
            "task_id": "t1",
            "feedback": ["左轮不转"],
        },
    )
    assert resp.status_code == 400, resp.text
    assert "必须是字符串" in resp.json()["detail"]


def test_tasks_execute_unknown_task_error_event(tasks_client):
    """任务不存在 → SSE 流内 error 事件（find_task TaskError 走错误映射，
    不裸 500）；事件含任务 id 便于前端定位。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    resp = client.post(
        "/api/tasks/execute",
        json={"output_dir": output_dir, "task_id": "t99"},
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    assert events[-1][0] == "error"
    assert "t99" in events[-1][1]["message"]


def test_tasks_execute_feedback_flow(tasks_client, monkeypatch):
    """反馈轮 SSE：已验证任务 + feedback → 自动重开 → done（task 带 2 条迭代，
    第 2 条 kind=feedback）；清单落盘含迭代记录。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(
            tasks=(Task(id="t1", title="循迹", description="循迹决策"),)
        )
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    holder["llm"] = FakeLLM(
        executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n"
    )
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    # 首轮执行 → verified
    resp = client.post(
        "/api/tasks/execute", json={"output_dir": output_dir, "task_id": "t1"}
    )
    assert resp.status_code == 200, resp.text
    # 反馈轮 → 自动重开 + 迭代追加
    resp = client.post(
        "/api/tasks/execute",
        json={
            "output_dir": output_dir,
            "task_id": "t1",
            "feedback": "上板发现左轮不转",
        },
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    done = events[-1][1]
    assert done["status"] == STATUS_VERIFIED
    iterations = done["task"]["iterations"]
    assert len(iterations) == 2
    assert iterations[1]["kind"] == "feedback"
    assert iterations[1]["feedback"] == "上板发现左轮不转"
    # 落盘一致
    saved = json.loads(
        (Path(output_dir) / TASKS_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert len(saved["tasks"][0]["iterations"]) == 2


def test_tasks_idea_analyze_sse_flow(tasks_client):
    """想法分析端点：idea_analyzing → idea_result → done（analysis 载荷）；
    LLM 收到想法 + 清单状态。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        idea_analysis=IdeaAnalysis(
            kind="direct_fix",
            reply="阈值太高，直接改。",
            fix_summary="把阈值从 500 降到 350",
            affected_task_ids=("t1",),
        )
    )
    resp = client.post(
        "/api/tasks/idea/analyze", json={"output_dir": output_dir, "idea": "阈值太高"}
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    types = [event_type for event_type, _ in events]
    assert types[-1] == "done"
    assert "idea_analyzing" in types
    assert "idea_result" in types
    analysis = events[-1][1]["analysis"]
    assert analysis["kind"] == "direct_fix"
    assert analysis["fix_summary"] == "把阈值从 500 降到 350"
    assert analysis["affected_task_ids"] == ["t1"]
    idea_call = holder["llm"].idea_analyze_calls[0]
    assert idea_call[0] == "阈值太高"
    assert idea_call[7] is None  # 未拆解清单 → None（AI 仍可分类讨论 / 新功能）


def test_tasks_idea_analyze_missing_idea_400(tasks_client):
    """缺 idea / 缺题面 → 400 中文。"""
    client, _, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    resp = client.post("/api/tasks/idea/analyze", json={"output_dir": output_dir})
    assert resp.status_code == 400, resp.text
    assert "idea" in resp.json()["detail"]
    # 有工程但缺题面（历史目录无上下文清单且未补题面）→ 400
    out = tmp_path / "manual"
    out.mkdir()
    (out / "project.uvprojx").write_text("<Project/>", encoding="utf-8")
    (out / "main.c").write_text("int main(void) {}\n", encoding="utf-8")
    resp = client.post(
        "/api/tasks/idea/analyze", json={"output_dir": str(out), "idea": "改阈值"}
    )
    assert resp.status_code == 400, resp.text
    assert "题面" in resp.json()["detail"]


def test_tasks_idea_insert_appends_and_backs_up(tasks_client):
    """插入端点：新任务落盘 t2（依赖序号转 id）；旧清单 → .bak；无清单也允许。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    resp = client.post(
        "/api/tasks/idea/insert",
        json={
            "output_dir": output_dir,
            "new_task": {
                "title": "弯道减速",
                "description": "弯道降低目标速度",
                "depends_on": [1],
            },
        },
    )
    assert resp.status_code == 200, resp.text
    plan = resp.json()["plan"]
    assert [task["id"] for task in plan["tasks"]] == ["t1", "t2"]
    assert plan["tasks"][1]["depends_on"] == ["t1"]
    assert (Path(output_dir) / TASKS_MANIFEST_BAK_FILENAME).exists()
    # 无清单目录也允许（建新清单只含该任务）
    out2 = tmp_path / "fresh"
    out2.mkdir()
    resp = client.post(
        "/api/tasks/idea/insert",
        json={
            "output_dir": str(out2),
            "new_task": {"title": "弯道减速", "description": "弯道降低目标速度"},
        },
    )
    assert resp.status_code == 200, resp.text
    assert [task["id"] for task in resp.json()["plan"]["tasks"]] == ["t1"]


def test_tasks_idea_insert_invalid_keeps_manifest(tasks_client):
    """插入校验失败 → 400 且现有清单**仍在原位**（.bak 备份须在校验通过后——
    评审发现 backup 是 move 语义，先备后验会吞掉现有清单）。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    manifest = Path(output_dir) / TASKS_MANIFEST_FILENAME
    before = manifest.read_text(encoding="utf-8")
    resp = client.post(
        "/api/tasks/idea/insert",
        json={
            "output_dir": output_dir,
            "new_task": {"title": "", "description": "空标题非法"},
        },
    )
    assert resp.status_code == 400, resp.text
    assert manifest.is_file()
    assert manifest.read_text(encoding="utf-8") == before
    assert not (Path(output_dir) / TASKS_MANIFEST_BAK_FILENAME).exists()


def _edited_plan() -> TaskPlan:
    """编辑 / 调序共用的两任务清单（t1 带轮次与 needs_redo，t2 依赖 t1）。"""
    return TaskPlan(
        generated_at="2026-01-01T00:00:00+0800",
        tasks=(
            Task(
                id="t1",
                title="循迹",
                description="循迹决策",
                score_refs=("s1",),
                depends_on=(),
                verify="manual",
                status="verified",
                note="补充说明",
                dialog_note="对话结论",
                needs_redo=True,
                iterations=(
                    TaskIteration(
                        seq=1, kind="execute", status="verified",
                        what_changed="实现了循迹",
                    ),
                ),
            ),
            Task(id="t2", title="OLED 显示", description="显示分值",
                 depends_on=("t1",), verify="compile", status="pending"),
        ),
    )


def test_update_task_fields_valid_and_preserves_progress():
    """微编辑合法：字段改、依赖序号转 id；status/note/dialog_note/needs_redo/
    轮次历史一律保留（spec 故事 5）。"""
    plan = _edited_plan()
    updated = update_task_fields(
        plan, "t1",
        title="循迹（改）",
        description="循迹决策 v2",
        depends_on=[2],
        verify="compile",
        score_refs=["s1", "s2"],
    )
    task = find_task(updated, "t1")
    assert task.title == "循迹（改）"
    assert task.description == "循迹决策 v2"
    assert task.depends_on == ("t2",)
    assert task.verify == "compile"
    assert task.score_refs == ("s1", "s2")
    # 进度与轮次历史原样保留
    assert task.status == "verified"
    assert task.note == "补充说明"
    assert task.dialog_note == "对话结论"
    assert task.needs_redo is True
    assert task.iterations[0].what_changed == "实现了循迹"
    # 未编辑的任务原样
    assert find_task(updated, "t2").title == "OLED 显示"
    # 未提供字段 = 保留原值
    partial = update_task_fields(plan, "t1", title="只改标题")
    assert find_task(partial, "t1").verify == "manual"
    assert find_task(partial, "t1").depends_on == ()


def test_update_task_fields_invalid_rejects():
    """非法输入各分支 → TaskError（空标题 / 未知依赖 / verify 词表外 /
    非字符串数组 / 依赖自己 / 未拆解）。"""
    plan = _edited_plan()
    with pytest.raises(TaskError, match="title 必须是非空字符串"):
        update_task_fields(plan, "t1", title="  ")
    with pytest.raises(TaskError, match="description 必须是非空字符串"):
        update_task_fields(plan, "t1", description="")
    with pytest.raises(TaskError, match="前置任务序号越界"):
        update_task_fields(plan, "t1", depends_on=[3])
    with pytest.raises(TaskError, match="必须是正整数"):
        update_task_fields(plan, "t1", depends_on=[0])
    with pytest.raises(TaskError, match="verify 必须是"):
        update_task_fields(plan, "t1", verify="flash")
    with pytest.raises(TaskError, match="score_refs 必须是字符串数组"):
        update_task_fields(plan, "t1", score_refs=[1])
    with pytest.raises(TaskError, match="不能依赖自己"):
        update_task_fields(plan, "t1", depends_on=[1])
    with pytest.raises(TaskError, match="尚未拆解"):
        update_task_fields(None, "t1", title="x")


def test_update_task_fields_depends_on_uses_position_not_id_suffix():
    """调序后依赖序号按**数组位置**解析（评审发现的错位缺陷回归）：plan 已
    被 move 成 [t2, t1]——编辑 t2（位置 1）设 depends_on=[2] = 依赖位置 2 的
    t1（不是 id 后缀 t2）；depends_on=[1] = 依赖自己 → 拒收。"""
    moved = move_task(_edited_plan(), "t1", "down")
    assert [t.id for t in moved.tasks] == ["t2", "t1"]
    updated = update_task_fields(moved, "t2", depends_on=[2])
    assert find_task(updated, "t2").depends_on == ("t1",)
    with pytest.raises(TaskError, match="不能依赖自己"):
        update_task_fields(moved, "t2", depends_on=[1])
    # insert 同款修复：新任务依赖「位置 2」= t1（而非 id 后缀 t2）
    inserted = insert_task_from_idea(
        moved, {"title": "新任务", "description": "描述", "depends_on": [2]}
    )
    assert inserted.tasks[-1].depends_on == ("t1",)


def test_move_task_swaps_adjacent_and_keeps_ids():
    """上移 / 下移相邻换位；id 不变；边界与词表外 → TaskError。"""
    plan = _edited_plan()
    moved = move_task(plan, "t1", "down")
    assert [t.id for t in moved.tasks] == ["t2", "t1"]
    assert [t.id for t in plan.tasks] == ["t1", "t2"]  # 纯函数不改原清单
    back = move_task(moved, "t1", "up")
    assert [t.id for t in back.tasks] == ["t1", "t2"]
    assert find_task(back, "t1").depends_on == ()  # id 稳定，依赖原样
    with pytest.raises(TaskError, match="已是第一个任务"):
        move_task(plan, "t1", "up")
    with pytest.raises(TaskError, match="已是最后一个任务"):
        move_task(plan, "t2", "down")
    with pytest.raises(TaskError, match="direction 必须是"):
        move_task(plan, "t1", "left")
    with pytest.raises(TaskError, match="尚未拆解"):
        move_task(None, "t1", "up")


def test_tasks_idea_edit_flow(tasks_client):
    """edit 端点 200：改 title/verify 落盘 + .bak 备份 + 返回 {task, plan}。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    resp = client.post(
        "/api/tasks/idea/edit",
        json={
            "output_dir": output_dir,
            "task_id": "t1",
            "fields": {"title": "循迹（改）", "verify": "manual"},
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["task"]["title"] == "循迹（改）"
    assert resp.json()["task"]["verify"] == "manual"
    assert resp.json()["plan"]["tasks"][0]["title"] == "循迹（改）"
    assert (Path(output_dir) / TASKS_MANIFEST_BAK_FILENAME).exists()
    disk = read_task_plan(Path(output_dir))
    assert disk is not None and disk.tasks[0].title == "循迹（改）"


def test_tasks_idea_edit_invalid_keeps_manifest(tasks_client):
    """edit 校验失败 → 400 中文且清单不动（先纯函数后备份再写）。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    manifest = Path(output_dir) / TASKS_MANIFEST_FILENAME
    before = manifest.read_text(encoding="utf-8")
    resp = client.post(
        "/api/tasks/idea/edit",
        json={"output_dir": output_dir, "task_id": "t1", "fields": {"title": ""}},
    )
    assert resp.status_code == 400
    assert "非空字符串" in resp.json()["detail"]
    assert manifest.read_text(encoding="utf-8") == before
    assert not (Path(output_dir) / TASKS_MANIFEST_BAK_FILENAME).exists()
    # 未拆解 / 任务不存在 / fields 非对象
    assert client.post(
        "/api/tasks/idea/edit",
        json={"output_dir": str(tmp_path / "nope"), "task_id": "t1", "fields": {}},
    ).status_code == 400


def test_tasks_idea_move_flow(tasks_client):
    """move 端点 200：down 换位落盘；边界 → 400；direction 词表外 → 400。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(
            Task(id="t1", title="循迹", description="循迹决策"),
            Task(id="t2", title="OLED 显示", description="显示分值"),
        ))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    resp = client.post(
        "/api/tasks/idea/move",
        json={"output_dir": output_dir, "task_id": "t1", "direction": "down"},
    )
    assert resp.status_code == 200, resp.text
    assert [t["id"] for t in resp.json()["plan"]["tasks"]] == ["t2", "t1"]
    disk = read_task_plan(Path(output_dir))
    assert disk is not None and [t.id for t in disk.tasks] == ["t2", "t1"]
    resp = client.post(
        "/api/tasks/idea/move",
        json={"output_dir": output_dir, "task_id": "t1", "direction": "up"},
    )
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()["plan"]["tasks"]] == ["t1", "t2"]
    assert client.post(
        "/api/tasks/idea/move",
        json={"output_dir": output_dir, "task_id": "t1", "direction": "up"},
    ).status_code == 400
    assert client.post(
        "/api/tasks/idea/move",
        json={"output_dir": output_dir, "task_id": "t1", "direction": "left"},
    ).status_code == 400


def test_tasks_idea_fix_sse_flow(tasks_client, monkeypatch):
    """直接修正端点：复用 compile_start / verify_result / task_reporting 词表
    → done（status/backup_id/main_diff/step_report/affected）；受影响任务
    needs_redo=true 落盘。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    holder["llm"] = FakeLLM(
        fixed_main_c="int main(void) { /* 阈值已调 */ while (1); }\n",
        idea_analysis=IdeaAnalysis(
            kind="direct_fix",
            reply="阈值太高，直接改。",
            fix_summary="把阈值从 500 降到 350",
            affected_task_ids=("t1",),
        ),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    resp = client.post(
        "/api/tasks/idea/fix",
        json={
            "output_dir": output_dir,
            "idea": "阈值太高",
            "fix_summary": "把阈值从 500 降到 350",
            "affected_task_ids": ["t1"],
        },
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    types = [event_type for event_type, _ in events]
    assert types[-1] == "done"
    assert "compile_start" in types
    assert "task_reporting" in types
    done = events[-1][1]
    assert done["status"] == STATUS_VERIFIED
    assert done["affected"] == ["t1"]
    assert done["step_report"]["what_changed"]
    # 写盘 + 受影响任务标记落盘
    assert "阈值已调" in (Path(output_dir) / "main.c").read_text(encoding="utf-8")
    saved = json.loads(
        (Path(output_dir) / TASKS_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert saved["tasks"][0]["needs_redo"] is True


def test_tasks_idea_fix_with_affected_but_no_plan_400(tasks_client):
    """有受影响任务但清单未拆解 → 400（不落失败半成品）。"""
    client, _, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    resp = client.post(
        "/api/tasks/idea/fix",
        json={"output_dir": output_dir, "idea": "改阈值", "affected_task_ids": ["t1"]},
    )
    assert resp.status_code == 400, resp.text
    assert "拆解" in resp.json()["detail"]


def test_tasks_idea_mark_redo_endpoint(tasks_client):
    """标记端点：needs_redo true/false 往返；未知 id 忽略；清单未拆解 → 400。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    resp = client.post(
        "/api/tasks/idea/mark-redo",
        json={"output_dir": output_dir, "task_ids": ["t1"], "needs_redo": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan"]["tasks"][0]["needs_redo"] is True
    resp = client.post(
        "/api/tasks/idea/mark-redo",
        json={"output_dir": output_dir, "task_ids": ["t1"], "needs_redo": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan"]["tasks"][0]["needs_redo"] is False
    resp = client.post(
        "/api/tasks/idea/mark-redo",
        json={"output_dir": output_dir, "task_ids": ["t99"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["plan"]["tasks"][0]["needs_redo"] is False
    out = tmp_path / "none"
    out.mkdir()
    resp = client.post(
        "/api/tasks/idea/mark-redo", json={"output_dir": str(out), "task_ids": ["t1"]}
    )
    assert resp.status_code == 400, resp.text
    assert "拆解" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 轮次回滚（工单 task-feedback/03）：撤销语义（恢复该轮执行前快照 + 前轮终态）
# ---------------------------------------------------------------------------


def test_rollback_task_iteration_restores_previous_state(tmp_path, monkeypatch):
    """回滚第 2 轮：main.c 恢复为第 2 轮执行前内容（= 第 1 轮成果），
    状态恢复为该轮前终态（verified）；迭代历史保留。"""
    library, output_dir = _task_env(tmp_path)
    _green_toolchain(monkeypatch, tmp_path)
    kwargs = dict(
        llm=FakeLLM(executed_main_c="// v1\nint main(void) { return 0; }\n"),
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    run_task(**kwargs)
    run_task(
        **{
            **kwargs,
            "llm": FakeLLM(executed_main_c="// v2\nint main(void) { return 0; }\n"),
            "feedback": "左轮不转，改慢一点",
        }
    )
    assert "// v2" in (output_dir / "main.c").read_text(encoding="utf-8")
    result = rollback_task_iteration(
        output_dir, "t1", 2, revise_backup_root(tmp_path / "work")
    )
    main_c = (output_dir / "main.c").read_text(encoding="utf-8")
    assert "// v1" in main_c
    assert "// v2" not in main_c
    assert result["task"]["status"] == STATUS_VERIFIED  # 第 2 轮前终态 = 轮 1 verified
    assert result["restored"]  # 恢复文件列表非空
    # 迭代历史保留（撤销不改历史）
    saved = read_task_plan(output_dir)
    assert saved is not None
    assert len(saved.tasks[0].iterations) == 2


def test_rollback_task_iteration_seq1_returns_to_pending(tmp_path, monkeypatch):
    """回滚第 1 轮（无前轮）：main.c 回到执行前 TODO 内容，状态回 pending。"""
    library, output_dir = _task_env(tmp_path)
    _green_toolchain(monkeypatch, tmp_path)
    result = run_task(
        llm=FakeLLM(
            executed_main_c="// v1\nint main(void) { /* 循迹已实现 */ while (1); }\n"
        ),
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_VERIFIED
    out = rollback_task_iteration(
        output_dir, "t1", 1, revise_backup_root(tmp_path / "work")
    )
    main_c = (output_dir / "main.c").read_text(encoding="utf-8")
    assert "/* TODO */" in main_c  # 回到执行前骨架
    assert "循迹已实现" not in main_c
    assert out["task"]["status"] == STATUS_PENDING


def test_rollback_task_iteration_missing_seq_raises(tmp_path, monkeypatch):
    """轮次不存在：TaskError，不写盘。"""
    library, output_dir = _task_env(tmp_path)
    _green_toolchain(monkeypatch, tmp_path)
    run_task(
        llm=FakeLLM(
            executed_main_c="// v1\nint main(void) { /* 循迹已实现 */ while (1); }\n"
        ),
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    with pytest.raises(TaskError, match="没有第 99 轮记录"):
        rollback_task_iteration(
            output_dir, "t1", 99, revise_backup_root(tmp_path / "work")
        )


def test_tasks_rollback_iteration_endpoint(tasks_client, monkeypatch):
    """回滚端点：执行 → 回滚 seq=1 → 200（status=pending + restored 非空）。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(
            tasks=(Task(id="t1", title="循迹", description="循迹决策"),)
        )
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    holder["llm"] = FakeLLM(
        executed_main_c="// v1\nint main(void) { /* 循迹已实现 */ while (1); }\n"
    )
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    client.post("/api/tasks/execute", json={"output_dir": output_dir, "task_id": "t1"})
    resp = client.post(
        "/api/tasks/rollback-iteration",
        json={"output_dir": output_dir, "task_id": "t1", "seq": 1},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["task"]["status"] == STATUS_PENDING
    assert body["restored"]
    assert "/* TODO */" in (Path(output_dir) / "main.c").read_text(encoding="utf-8")


def test_tasks_rollback_iteration_seq_bad_400(tasks_client):
    """seq 非正整数 → TaskError 400 中文。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    resp = client.post(
        "/api/tasks/rollback-iteration",
        json={"output_dir": output_dir, "task_id": "t1", "seq": "x"},
    )
    assert resp.status_code == 400, resp.text
    assert "正整数" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 工单 03：状态机转移表 / 人工改标端点 / manual 验收降级 / 修订联动作废
# ---------------------------------------------------------------------------


def test_update_task_status_transitions():
    """转移表：pending→skipped / skipped→pending / verified→pending /
    unverified→verified / unverified→pending / failed→verified / failed→pending；
    非法转移（pending→verified 直达等）→ TaskError。"""
    plan = TaskPlan(
        tasks=(
            Task(id="t1", title="A", description="x", status=STATUS_PENDING),
            Task(id="t2", title="B", description="x", status=STATUS_SKIPPED),
            Task(id="t3", title="C", description="x", status=STATUS_VERIFIED),
            Task(id="t4", title="D", description="x", status=STATUS_UNVERIFIED),
            Task(id="t5", title="E", description="x", status=STATUS_FAILED),
            Task(id="t6", title="F", description="x", status=STATUS_DOING),
        )
    )
    # 合法
    plan, t1 = update_task_status(plan, "t1", STATUS_SKIPPED)
    assert t1.status == STATUS_SKIPPED
    plan, t1b = update_task_status(plan, "t1", STATUS_PENDING)
    assert t1b.status == STATUS_PENDING
    _, t3 = update_task_status(plan, "t3", STATUS_PENDING)
    assert t3.status == STATUS_PENDING
    _, t4 = update_task_status(plan, "t4", STATUS_VERIFIED)
    assert t4.status == STATUS_VERIFIED
    _, t5 = update_task_status(plan, "t5", STATUS_VERIFIED)
    assert t5.status == STATUS_VERIFIED
    # 非法：pending 未执行直接 verified（绕过 AI 执行）；doing 任何改标；
    # 未知状态词
    with pytest.raises(TaskError):
        update_task_status(plan, "t1", STATUS_VERIFIED)
    with pytest.raises(TaskError):
        update_task_status(plan, "t6", STATUS_VERIFIED)
    with pytest.raises(TaskError):
        update_task_status(plan, "t1", "bogus")
    # 错误消息带允许目标
    with pytest.raises(TaskError) as exc_info:
        update_task_status(plan, "t6", STATUS_SKIPPED)
    assert "无（执行中不可操作）" in str(exc_info.value)


def test_transition_table_consistency():
    """转移表自洽：每个状态条目的目标都在词表内；doing 无出口（终态由
    run_task 回填，不经人工转移表）。"""
    assert set(ALLOWED_STATUS_TRANSITIONS) == {
        STATUS_PENDING, STATUS_SKIPPED, STATUS_VERIFIED,
        STATUS_UNVERIFIED, STATUS_FAILED, STATUS_DOING,
    }
    for targets in ALLOWED_STATUS_TRANSITIONS.values():
        for target in targets:
            assert target in ALLOWED_STATUS_TRANSITIONS
    assert ALLOWED_STATUS_TRANSITIONS[STATUS_DOING] == frozenset()


def test_run_task_manual_verify_stays_unverified(tmp_path, monkeypatch):
    """verify=manual 的任务：编译绿 → 仍 unverified（上板人工改标，spec 拍板）。"""
    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    # 换成 manual 任务
    write_task_plan(
        output_dir,
        TaskPlan(
            tasks=(Task(id="t1", title="循迹", description="循迹决策", verify=VERIFY_MANUAL),)
        ),
    )
    llm = FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n")
    result = run_task(
        llm=llm,
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_UNVERIFIED  # 编译绿但 manual → 未验证
    assert result["verify_cause"] == "manual"  # 徽章按 cause 区分（非无工具链降级）
    assert "上板人工确认" in result["message"]
    saved = read_task_plan(output_dir)
    assert saved is not None
    assert saved.tasks[0].status == STATUS_UNVERIFIED


# ---------------------------------------------------------------------------
# 迭代历史（工单 task-feedback/01）：每轮执行记录 + 旧清单兼容
# ---------------------------------------------------------------------------


def test_run_task_records_first_iteration(tmp_path, monkeypatch):
    """初始执行后：任务带 1 条迭代记录（seq=1/kind=execute/status 终态/backup_id）。"""
    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    llm = FakeLLM(
        executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n",
        step_report=StepReport(
            what_changed="在 main.c 实现循迹状态机（调用 xunji_read），编译通过。",
            user_action="把 PA0 接到灰度模块 DIO，烧录后观察小车沿黑线行驶。",
            checklist=(
                "烧录后应看到小车沿黑线行驶（约 0.5m/s）。",
                "若不沿线检查 PA0 与灰度模块 DIO 接线；若抖动检查阈值。",
            ),
        ),
    )
    run_task(
        llm=llm,
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    saved = read_task_plan(output_dir)
    assert saved is not None
    task = saved.tasks[0]
    assert len(task.iterations) == 1
    iteration = task.iterations[0]
    assert iteration.seq == 1
    assert iteration.kind == "execute"
    assert iteration.feedback == ""
    assert iteration.status == STATUS_VERIFIED  # 该轮终态（回滚恢复用）
    assert iteration.backup_id
    assert iteration.at  # 时间戳非空
    # 编译摘要已落（形状如 {'errors': 0, 'warnings': 0}，存在即可）
    assert iteration.compile_summary
    # 步骤报告（工单 stepwise-deepen/01）：what_changed / user_action 随轮次落盘
    assert "循迹状态机" in iteration.what_changed
    assert "PA0" in iteration.user_action
    # 上板自检清单（工单 task-insight/01）：checklist 随轮次落盘
    assert iteration.checklist == (
        "烧录后应看到小车沿黑线行驶（约 0.5m/s）。",
        "若不沿线检查 PA0 与灰度模块 DIO 接线；若抖动检查阈值。",
    )
    # 报告调用输入：任务 dict + 验证结果 + diff + 模块接口
    assert len(llm.step_report_calls) == 1
    report_task, verify_result, diff_text, interfaces = llm.step_report_calls[0]
    assert report_task["id"] == "t1"
    assert verify_result["status"] == STATUS_VERIFIED
    assert "循迹已实现" in diff_text
    assert interfaces == ()
    # 未执行任务不受影响
    assert saved.tasks[1].iterations == ()


def test_run_task_appends_iteration_on_reexecute(tmp_path, monkeypatch):
    """再次执行（反馈/重做）→ 追加而非覆盖，seq 递增。"""
    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    kwargs = dict(
        llm=FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n"),
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    run_task(**kwargs)
    run_task(**kwargs)
    saved = read_task_plan(output_dir)
    assert saved is not None
    iterations = saved.tasks[0].iterations
    assert len(iterations) == 2
    assert [it.seq for it in iterations] == [1, 2]


def test_task_plan_from_dict_legacy_without_iterations():
    """旧 shape 清单（无 iterations 字段）读回 → iterations = ()。"""
    plan = TaskPlan.from_dict(
        {
            "version": 1,
            "generated_at": "",
            "tasks": [{"id": "t1", "title": "循迹", "description": "循迹决策"}],
        }
    )
    assert plan.tasks[0].iterations == ()


def test_task_plan_from_dict_bad_iteration_ignored():
    """单条 iteration 形状非法（非 dict / 缺 seq）→ 忽略该条，不报错。"""
    plan = TaskPlan.from_dict(
        {
            "version": 1,
            "generated_at": "",
            "tasks": [
                {
                    "id": "t1",
                    "title": "循迹",
                    "description": "循迹决策",
                    "iterations": [
                        "not-a-dict",
                        {"kind": "execute"},  # 缺 seq
                        {"seq": 2, "kind": "bad-kind"},  # kind 词表外
                        None,
                    ],
                }
            ],
        }
    )
    assert plan.tasks[0].iterations == ()


def test_task_iteration_roundtrip():
    """迭代记录 to_dict/from_dict roundtrip（seq/kind/feedback/status/backup_id/at）。"""
    plan = TaskPlan.from_dict(
        {
            "version": 1,
            "generated_at": "",
            "tasks": [
                {
                    "id": "t1",
                    "title": "循迹",
                    "description": "循迹决策",
                    "iterations": [
                        {
                            "seq": 1,
                            "kind": "execute",
                            "feedback": "",
                            "status": "verified",
                            "backup_id": "b1",
                            "compile_summary": "编译通过",
                            "at": "2026-08-27T10:00:00+0800",
                        }
                    ],
                }
            ],
        }
    )
    iteration = plan.tasks[0].iterations[0]
    assert iteration.seq == 1
    assert iteration.kind == "execute"
    assert iteration.status == STATUS_VERIFIED
    assert iteration.backup_id == "b1"
    assert iteration.compile_summary == "编译通过"
    assert iteration.at == "2026-08-27T10:00:00+0800"
    # 落盘 → 读回同一形状
    dumped = TaskPlan(tasks=plan.tasks).to_dict()
    assert dumped["tasks"][0]["iterations"][0]["seq"] == 1
    assert dumped["tasks"][0]["iterations"][0]["backup_id"] == "b1"


def test_task_iteration_roundtrip_with_step_report():
    """迭代记录带步骤报告字段（what_changed / user_action / checklist）roundtrip；
    旧记录缺字段 → 读回空串 / 空元组（向后兼容）。"""
    plan = TaskPlan.from_dict(
        {
            "version": 1,
            "generated_at": "",
            "tasks": [
                {
                    "id": "t1",
                    "title": "循迹",
                    "description": "循迹决策",
                    "iterations": [
                        {
                            "seq": 1,
                            "kind": "execute",
                            "status": "verified",
                            "backup_id": "b1",
                            "what_changed": "在 main.c 实现循迹状态机",
                            "user_action": "把 PA0 接到灰度模块 DIO",
                            "checklist": ["烧录后应看到 LED 闪烁。", "若不闪检查接线。"],
                        }
                    ],
                }
            ],
        }
    )
    iteration = plan.tasks[0].iterations[0]
    assert iteration.what_changed == "在 main.c 实现循迹状态机"
    assert iteration.user_action == "把 PA0 接到灰度模块 DIO"
    assert iteration.checklist == ("烧录后应看到 LED 闪烁。", "若不闪检查接线。")
    dumped = TaskPlan(tasks=plan.tasks).to_dict()
    assert dumped["tasks"][0]["iterations"][0]["what_changed"] == "在 main.c 实现循迹状态机"
    assert dumped["tasks"][0]["iterations"][0]["user_action"] == "把 PA0 接到灰度模块 DIO"
    assert dumped["tasks"][0]["iterations"][0]["checklist"] == [
        "烧录后应看到 LED 闪烁。", "若不闪检查接线。",
    ]
    # 旧记录（无步骤报告字段）→ 空串 / 空元组，不拒收
    legacy = TaskPlan.from_dict(
        {
            "version": 1,
            "generated_at": "",
            "tasks": [
                {
                    "id": "t1",
                    "title": "循迹",
                    "description": "循迹决策",
                    "iterations": [{"seq": 1, "kind": "execute", "status": "verified"}],
                }
            ],
        }
    )
    legacy_iteration = legacy.tasks[0].iterations[0]
    assert legacy_iteration.what_changed == ""
    assert legacy_iteration.user_action == ""
    assert legacy_iteration.checklist == ()
    # 坏项过滤：非 str / 空串项忽略，正常项保留
    messy = TaskPlan.from_dict(
        {
            "version": 1,
            "generated_at": "",
            "tasks": [
                {
                    "id": "t1",
                    "title": "循迹",
                    "description": "循迹决策",
                    "iterations": [{
                        "seq": 1,
                        "kind": "execute",
                        "status": "verified",
                        "checklist": ["正常项", 123, "", None, "  另一项  "],
                    }],
                }
            ],
        }
    )
    assert messy.tasks[0].iterations[0].checklist == ("正常项", "另一项")


class _ReportBrokenLLM(FakeLLM):
    """步骤报告调用失败的假 LLM：report_task_step 抛异常（降级测试用）。"""

    def report_task_step(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("步骤报告服务崩溃")


def test_run_task_step_report_failure_degrades(tmp_path, monkeypatch):
    """步骤报告失败不阻断：任务仍落盘终态，轮次记录两个字段为空串。"""
    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    llm = _ReportBrokenLLM(
        executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n"
    )
    events: list[str] = []
    result = run_task(
        llm=llm,
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: events.append(event.type)),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_VERIFIED
    assert "task_reporting" in events  # 报告调用前已发射进度事件
    saved = read_task_plan(output_dir)
    assert saved is not None
    iteration = saved.tasks[0].iterations[0]
    assert iteration.status == STATUS_VERIFIED
    assert iteration.what_changed == ""
    assert iteration.user_action == ""
    assert iteration.checklist == ()


# ---------------------------------------------------------------------------
# 灵活修正（工单 idea-fix/01）：needs_redo 标记 / 想法转任务卡 / 直接修正管线
# ---------------------------------------------------------------------------


def test_legacy_task_without_needs_redo_defaults_false():
    """旧清单（无 needs_redo 字段）读回 → False（向后兼容）。"""
    plan = TaskPlan.from_dict(
        {
            "version": 1,
            "generated_at": "",
            "tasks": [{"id": "t1", "title": "循迹", "description": "循迹决策"}],
        }
    )
    assert plan.tasks[0].needs_redo is False


def test_task_needs_redo_roundtrip():
    """needs_redo 标记往返：to_dict / from_dict 全字段；非布尔 → False。"""
    plan = TaskPlan.from_dict(
        {
            "version": 1,
            "generated_at": "",
            "tasks": [
                {
                    "id": "t1",
                    "title": "循迹",
                    "description": "循迹决策",
                    "needs_redo": True,
                }
            ],
        }
    )
    assert plan.tasks[0].needs_redo is True
    dumped = TaskPlan(tasks=plan.tasks).to_dict()
    assert dumped["tasks"][0]["needs_redo"] is True
    # 非布尔值 → False（读回侧不拒收，与 status 词表外同哲学）
    plan = TaskPlan.from_dict(
        {
            "version": 1,
            "generated_at": "",
            "tasks": [
                {
                    "id": "t1",
                    "title": "循迹",
                    "description": "循迹决策",
                    "needs_redo": "yes",
                }
            ],
        }
    )
    assert plan.tasks[0].needs_redo is False


def test_insert_task_from_idea_appends_with_id_and_deps():
    """想法转任务卡：追加 t3、depends_on 序号转 id、score_refs 原样、
    status=pending / needs_redo=False；旧任务原样保留。"""
    plan = TaskPlan(
        tasks=(
            Task(id="t1", title="循迹", description="循迹决策"),
            Task(id="t2", title="OLED", description="显示", depends_on=("t1",)),
        )
    )
    updated = insert_task_from_idea(
        plan,
        {
            "title": "弯道减速",
            "description": "弯道降低目标速度",
            "score_refs": ["s1"],
            "depends_on": [1, 2],
            "verify": VERIFY_COMPILE,
        },
    )
    assert len(updated.tasks) == 3
    new_task = updated.tasks[2]
    assert new_task.id == "t3"
    assert new_task.title == "弯道减速"
    assert new_task.depends_on == ("t1", "t2")
    assert new_task.score_refs == ("s1",)
    assert new_task.status == STATUS_PENDING
    assert new_task.needs_redo is False
    assert new_task.iterations == ()
    assert updated.tasks[0].id == "t1"
    assert updated.tasks[1].depends_on == ("t1",)
    assert updated.generated_at  # 空 → 落时间戳


def test_insert_task_from_idea_validation():
    """想法转任务卡校验：缺标题/描述、depends_on 越界/非正整数 → TaskError；
    verify 词表外 → 修正 compile。"""
    plan = TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    with pytest.raises(TaskError):
        insert_task_from_idea(plan, {"description": "缺标题"})
    with pytest.raises(TaskError):
        insert_task_from_idea(plan, {"title": "有标题", "description": ""})
    with pytest.raises(TaskError):
        insert_task_from_idea(
            plan, {"title": "越界", "description": "依赖不存在", "depends_on": [9]}
        )
    with pytest.raises(TaskError):
        insert_task_from_idea(
            plan, {"title": "非法", "description": "序号非正整数", "depends_on": [0]}
        )
    updated = insert_task_from_idea(
        plan,
        {"title": "新任务", "description": "描述", "verify": "bad-verify"},
    )
    assert updated.tasks[1].verify == VERIFY_COMPILE


def test_set_tasks_needs_redo_marks_and_ignores_unknown():
    """标记重做：已知 id 置 true；未知 id 静默忽略；False 清除；空集 = 原样。"""
    plan = TaskPlan(
        tasks=(
            Task(id="t1", title="循迹", description="循迹决策"),
            Task(id="t2", title="OLED", description="显示"),
        )
    )
    marked = set_tasks_needs_redo(plan, ["t1", "t99"])
    assert marked.tasks[0].needs_redo is True
    assert marked.tasks[1].needs_redo is False
    cleared = set_tasks_needs_redo(marked, ["t1"], False)
    assert cleared.tasks[0].needs_redo is False
    assert set_tasks_needs_redo(plan, []) is plan


def test_run_task_clears_needs_redo(tmp_path, monkeypatch):
    """执行过的任务清除「建议重做」标记（重做消化了标记来源）。"""
    library, output_dir = _task_env(tmp_path)
    plan = read_task_plan(output_dir)
    assert plan is not None
    write_task_plan(output_dir, set_tasks_needs_redo(plan, ["t1"], True))
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    llm = FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n")
    run_task(
        llm=llm,
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    saved = read_task_plan(output_dir)
    assert saved is not None
    assert saved.tasks[0].needs_redo is False


def test_run_direct_fix_verified_when_compile_passes(tmp_path, monkeypatch):
    """直接修正管线：备份 → 写盘 → 编译绿 → verified + diff + 步骤报告。"""
    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    llm = FakeLLM(
        fixed_main_c="int main(void) { /* 阈值已调 */ while (1); }\n",
        idea_analysis=IdeaAnalysis(
            kind="direct_fix",
            reply="阈值太高，直接改。",
            fix_summary="把阈值从 500 降到 350",
            affected_task_ids=("t1",),
        ),
    )
    events: list[str] = []
    result = run_direct_fix(
        llm=llm,
        idea="阈值太高",
        fix_summary="把阈值从 500 降到 350",
        affected=["t1"],
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: events.append(event.type)),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_VERIFIED
    assert result["backup_id"]
    assert "阈值已调" in (output_dir / "main.c").read_text(encoding="utf-8")
    assert result["main_diff"]["stats"]["additions"] >= 1
    assert result["step_report"]["what_changed"]
    assert result["step_report"]["user_action"]
    # 上板自检清单（工单 task-insight/01）：直接修正的步骤报告也带 checklist
    assert result["step_report"]["checklist"]
    assert len(result["step_report"]["checklist"]) == 2
    idea, fix_summary, affected, interfaces, ptext, qa, main, global_note = llm.idea_fix_calls[0]
    assert idea == "阈值太高"
    assert fix_summary == "把阈值从 500 降到 350"
    assert affected == ("t1",)
    assert global_note == ""  # 未采纳全局结论 = 空串（工单 idea-suite/01）
    assert "task_reporting" in events
    assert "verify_result" in events
    # 不造任务轮次（run_direct_fix 不 touch plan）
    saved = read_task_plan(output_dir)
    assert saved is not None
    assert all(task.iterations == () for task in saved.tasks)


def test_run_direct_fix_without_toolchain_degrades(tmp_path, monkeypatch):
    """无工具链 → unverified 降级（结果保留，中文说明）。"""
    library, output_dir = _task_env(tmp_path)
    _no_toolchain(monkeypatch)
    llm = FakeLLM(fixed_main_c="int main(void) { /* 阈值已调 */ while (1); }\n")
    result = run_direct_fix(
        llm=llm,
        idea="阈值太高",
        fix_summary="",
        affected=[],
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_UNVERIFIED
    assert "未验证" in result["message"]
    assert "阈值已调" in (output_dir / "main.c").read_text(encoding="utf-8")


def test_run_direct_fix_passes_global_note(tmp_path, monkeypatch):
    """工程级全局结论透传（工单 idea-suite/01）：run_direct_fix 的 global_note
    原样交给 llm.apply_idea_fix（修正亦与之保持一致）。"""
    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    llm = FakeLLM(fixed_main_c="int main(void) { /* 阈值已调 */ while (1); }\n")
    run_direct_fix(
        llm=llm,
        idea="阈值太高",
        fix_summary="",
        affected=[],
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
        global_note="全局结论：阈值先按 350 起步",
    )
    assert llm.idea_fix_calls[0][-1] == "全局结论：阈值先按 350 起步"


def test_run_task_passes_global_note(tmp_path, monkeypatch):
    """工程级全局结论透传（工单 idea-suite/01）：run_task 的 global_note 原样
    交给 llm.execute_task（任何一步执行都与之保持一致）。"""
    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    llm = FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n")
    run_task(
        llm=llm,
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
        global_note="全局结论：循迹阈值先按 500 起步",
    )
    assert llm.execute_task_calls[0][-1] == "全局结论：循迹阈值先按 500 起步"


def test_run_direct_fix_empty_result_raises(tmp_path, monkeypatch):
    """LLM 输出空 → TaskError（不做任何写盘）。"""
    library, output_dir = _task_env(tmp_path)
    llm = FakeLLM(fixed_main_c="")
    before = (output_dir / "main.c").read_text(encoding="utf-8")
    with pytest.raises(TaskError):
        run_direct_fix(
            llm=llm,
            idea="阈值太高",
            fix_summary="",
            affected=[],
            problem_text="题面",
            qa_text="",
            manifests=[],
            platform=PLATFORM_STM32,
            library_dir=library,
            master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
            main_c="int main(void) { /* TODO */ while (1); }\n",
            output_dir=output_dir,
            work_root=tmp_path / "work",
            emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
        )
    assert (output_dir / "main.c").read_text(encoding="utf-8") == before


class _IdeaFixBrokenLLM(FakeLLM):
    """想法修正调用失败的假 LLM：apply_idea_fix 抛异常（防写盘测试用）。"""

    def apply_idea_fix(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("想法修正调用崩溃")


def test_run_direct_fix_llm_failure_propagates(tmp_path, monkeypatch):
    """LLM 修正调用抛异常 → 原样传播（不写盘、不产生备份）。"""
    library, output_dir = _task_env(tmp_path)
    llm = _IdeaFixBrokenLLM()
    before = (output_dir / "main.c").read_text(encoding="utf-8")
    with pytest.raises(RuntimeError):
        run_direct_fix(
            llm=llm,
            idea="阈值太高",
            fix_summary="",
            affected=[],
            problem_text="题面",
            qa_text="",
            manifests=[],
            platform=PLATFORM_STM32,
            library_dir=library,
            master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
            main_c="int main(void) { /* TODO */ while (1); }\n",
            output_dir=output_dir,
            work_root=tmp_path / "work",
            emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
        )
    assert (output_dir / "main.c").read_text(encoding="utf-8") == before


def test_run_direct_fix_failed_after_one_fix_round(tmp_path, monkeypatch):
    """修正修一轮仍红 → status = failed（结果保留，中文提示；共享
    verify_compile_tail 的 failed 路径在直接修正管线同样生效）。"""
    library, output_dir = _task_env(tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(2, "error: x"),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.run_fix_round",
        lambda llm, **kwargs: SimpleNamespace(backup_id="fix-1", results=()),
    )
    llm = FakeLLM(fixed_main_c="int main(void) { /* 阈值已调 */ while (1); }\n")
    result = run_direct_fix(
        llm=llm,
        idea="阈值太高",
        fix_summary="把阈值从 500 降到 350",
        affected=[],
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_FAILED
    assert "仍红" in result["message"]
    assert "阈值已调" in (output_dir / "main.c").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 上板反馈（工单 task-feedback/02）：反馈执行 = 自动重开 + 第 2 轮 kind=feedback
# ---------------------------------------------------------------------------


def _green_toolchain(monkeypatch, tmp_path):
    """有工具链 + 编译绿（反馈轮共用）。"""
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )


def test_run_task_feedback_reexecutes_verified_task(tmp_path, monkeypatch):
    """已验证任务 + 上板反馈 → 自动重开（先回 pending 再执行），第 2 轮 kind=feedback。"""
    library, output_dir = _task_env(tmp_path)
    _green_toolchain(monkeypatch, tmp_path)
    kwargs = dict(
        llm=FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n"),
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    run_task(**kwargs)
    result = run_task(**{**kwargs, "feedback": "上板发现左轮不转"})
    assert result["status"] == STATUS_VERIFIED  # compile 类反馈绿 → 已验证
    saved = read_task_plan(output_dir)
    assert saved is not None
    iterations = saved.tasks[0].iterations
    assert len(iterations) == 2
    assert iterations[1].seq == 2
    assert iterations[1].kind == "feedback"
    assert iterations[1].feedback == "上板发现左轮不转"
    assert iterations[1].backup_id


def test_run_task_feedback_manual_keeps_unverified(tmp_path, monkeypatch):
    """manual 任务 + 反馈轮编译绿 → 仍 unverified（上板人工确认，spec 拍板）。"""
    library, output_dir = _task_env(tmp_path)
    _green_toolchain(monkeypatch, tmp_path)
    write_task_plan(
        output_dir,
        TaskPlan(
            tasks=(Task(id="t1", title="循迹", description="循迹决策", verify=VERIFY_MANUAL),)
        ),
    )
    result = run_task(
        llm=FakeLLM(executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n"),
        task_id="t1",
        note="",
        problem_text="题面",
        qa_text="",
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
        feedback="上板发现不沿线，向右偏",
    )
    assert result["status"] == STATUS_UNVERIFIED
    saved = read_task_plan(output_dir)
    assert saved is not None
    iterations = saved.tasks[0].iterations
    assert len(iterations) == 1
    assert iterations[0].kind == "feedback"
    assert iterations[0].feedback == "上板发现不沿线，向右偏"


def test_tasks_status_endpoint(tasks_client):
    """改标端点：pending→skipped 落盘；非法转移 400 中文。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    resp = client.post(
        "/api/tasks/status",
        json={"output_dir": output_dir, "task_id": "t1", "status": "skipped"},
    )
    assert resp.status_code == 200
    assert resp.json()["task"]["status"] == STATUS_SKIPPED
    # 落盘
    saved = json.loads(
        (Path(output_dir) / TASKS_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    assert saved["tasks"][0]["status"] == STATUS_SKIPPED
    # 非法：skipped → verified 直达
    resp = client.post(
        "/api/tasks/status",
        json={"output_dir": output_dir, "task_id": "t1", "status": "verified"},
    )
    assert resp.status_code == 400
    assert "不能改为" in resp.json()["detail"]
    # 未拆解目录
    empty = tmp_path / "empty"
    empty.mkdir()
    resp = client.post(
        "/api/tasks/status",
        json={"output_dir": str(empty), "task_id": "t1", "status": "skipped"},
    )
    assert resp.status_code == 400
    assert "尚未拆解" in resp.json()["detail"]


def test_revision_regeneration_invalidates_tasks(tmp_path, monkeypatch):
    """修订重生成后任务清单删除（含 .bak）；模块集不变路径不删。"""
    from contest_generator.revision import run_revision

    library = make_fake_module_library(tmp_path / "modules")
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    write_task_plan(
        output_dir,
        TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),)),
    )
    (output_dir / TASKS_MANIFEST_BAK_FILENAME).write_text("{}", encoding="utf-8")
    # 假生成器：不真生成（run_revision 的生成链不在此测）
    monkeypatch.setattr(
        "contest_generator.revision.generate_skeleton",
        lambda llm, problem, manifests, platform, library_dir=None, master_project_dir=None, instances=None: (
            "int main(void) { while (1); }\n", [],
        ),
    )
    monkeypatch.setattr(
        "contest_generator.revision.generate_project",
        lambda **kwargs: None,
    )
    llm = FakeLLM()
    result = run_revision(
        llm=llm,
        problem_text="题面",
        qa_text="",
        requirements=(),
        references=(),
        current_slugs=["dht11"],
        confirmed_slugs=["dht11", "oled"],  # 模块集变化 → 重生成
        new_qa_text="新 Q&A",
        platform=PLATFORM_STM32,
        library_dir=library,
        masters_dir=tmp_path / "masters",
        output_dir=output_dir,
        backup_root=tmp_path / "revise-backups",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result["tasks_invalidated"] is True
    assert (output_dir / TASKS_MANIFEST_FILENAME).exists() is False
    assert (output_dir / TASKS_MANIFEST_BAK_FILENAME).exists() is False


def test_revision_unchanged_keeps_tasks(tmp_path):
    """模块集不变路径：不删任务清单（tasks_invalidated = False）。"""
    from contest_generator.revision import run_revision

    library = make_fake_module_library(tmp_path / "modules")
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    write_task_plan(
        output_dir,
        TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),)),
    )
    # 模块集相同（dht11 + 依赖 delay 不变）：不重生成
    result = run_revision(
        llm=FakeLLM(),
        problem_text="题面",
        qa_text="",
        requirements=(),
        references=(),
        current_slugs=["dht11"],
        confirmed_slugs=["dht11"],
        new_qa_text="新 Q&A",
        platform=PLATFORM_STM32,
        library_dir=library,
        masters_dir=tmp_path / "masters",
        output_dir=output_dir,
        backup_root=tmp_path / "revise-backups",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result["tasks_invalidated"] is False
    assert (output_dir / TASKS_MANIFEST_FILENAME).exists() is True


# ---------------------------------------------------------------------------
# 任务对话结论（工单 task-chat/01：dialog_note 字段落盘 + 采纳/清除域编排）
# ---------------------------------------------------------------------------


def test_task_dialog_note_roundtrip(tmp_path):
    """dialog_note 往返：Task → to_dict → from_dict 保留；旧清单无字段 → 空串。"""
    task = Task(
        id="t1",
        title="循迹",
        description="循迹决策",
        dialog_note="左轮不转，改成脉冲式控制",
        note="pre note",
    )
    plan = TaskPlan(tasks=(task,))
    with open(tmp_path / TASKS_MANIFEST_FILENAME, "w", encoding="utf-8") as fh:
        json.dump(plan.to_dict(), fh)
    loaded = read_task_plan(tmp_path)
    assert loaded is not None
    assert loaded.tasks[0].dialog_note == "左轮不转，改成脉冲式控制"
    assert loaded.tasks[0].note == "pre note"
    # 旧清单（无 dialog_note 字段）→ 空串，不报错
    legacy = {
        "version": 1,
        "generated_at": "2026-01-01T00:00:00+0800",
        "tasks": [{"id": "t1", "title": "循迹", "description": "循迹决策"}],
    }
    with open(tmp_path / TASKS_MANIFEST_FILENAME, "w", encoding="utf-8") as fh:
        json.dump(legacy, fh)
    loaded = read_task_plan(tmp_path)
    assert loaded is not None
    assert loaded.tasks[0].dialog_note == ""
    assert loaded.tasks[0].status == STATUS_PENDING


def test_with_task_status_preserves_and_replaces_dialog_note():
    """_with_task_status：dialog_note None = 保留原值；传值 = 替换；清除 = 空串。"""
    plan = TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策", dialog_note="结论A"),))
    kept = _with_task_status(plan, "t1", STATUS_SKIPPED)
    assert kept.tasks[0].dialog_note == "结论A"
    assert kept.tasks[0].status == STATUS_SKIPPED
    replaced = _with_task_status(plan, "t1", STATUS_PENDING, dialog_note="结论B")
    assert replaced.tasks[0].dialog_note == "结论B"
    cleared = _with_task_status(plan, "t1", STATUS_PENDING, dialog_note="")
    assert cleared.tasks[0].dialog_note == ""


def test_set_task_dialog_note_writes_and_clears(tmp_path):
    """采纳域编排：写盘 / 清除（空串）/ 未知任务 / 未拆解 → TaskError。"""
    plan = TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    write_task_plan(tmp_path, plan)
    result = set_task_dialog_note(tmp_path, "t1", "按反馈改为 PID 循迹")
    assert result["task"]["dialog_note"] == "按反馈改为 PID 循迹"
    assert result["plan"]["tasks"][0]["dialog_note"] == "按反馈改为 PID 循迹"
    loaded = read_task_plan(tmp_path)
    assert loaded is not None and loaded.tasks[0].dialog_note == "按反馈改为 PID 循迹"
    # 清除
    cleared = set_task_dialog_note(tmp_path, "t1", "")
    assert cleared["task"]["dialog_note"] == ""
    # 未知任务
    with pytest.raises(TaskError):
        set_task_dialog_note(tmp_path, "t9", "谁也不")
    # 未拆解
    with pytest.raises(TaskError):
        set_task_dialog_note(tmp_path / "nope", "t1", "谁也不")


def test_tasks_dialog_adopt_endpoint(tasks_client):
    """采纳端点：200 写盘 → 清除；text 非字符串 → 400。"""
    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    resp = client.post(
        "/api/tasks/plan",
        json={"output_dir": output_dir, "score_points": []},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(
        "/api/tasks/dialog-adopt",
        json={"output_dir": output_dir, "task_id": "t1", "text": "左轮不转：改为脉冲式控制"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["task"]["dialog_note"] == "左轮不转：改为脉冲式控制"
    assert body["plan"]["tasks"][0]["dialog_note"] == "左轮不转：改为脉冲式控制"
    # 清除
    resp = client.post(
        "/api/tasks/dialog-adopt",
        json={"output_dir": output_dir, "task_id": "t1", "text": ""},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["task"]["dialog_note"] == ""
    # text 非字符串 → 400
    resp = client.post(
        "/api/tasks/dialog-adopt",
        json={"output_dir": output_dir, "task_id": "t1", "text": 123},
    )
    assert resp.status_code == 400
    # 输出目录不存在 → 400
    resp = client.post(
        "/api/tasks/dialog-adopt",
        json={"output_dir": str(tmp_path / "nope"), "task_id": "t1", "text": "x"},
    )
    assert resp.status_code == 400


def test_tasks_discuss_endpoint(tasks_client):
    """任务商量端点（工单 task-chat/02）：正常流 → {reply}（历史/任务透传 LLM）；
    校验 400（缺 message / history 非法 / 任务不存在）；LLM 失败 → 502。"""
    from contest_generator.llm import LLMError, TaskDiscussion

    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),)),
        task_discussion=TaskDiscussion(reply="可行，建议 10ms 采样"),
    )
    resp = client.post(
        "/api/tasks/plan",
        json={"output_dir": output_dir, "score_points": []},
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        "/api/tasks/discuss",
        json={
            "output_dir": output_dir,
            "task_id": "t1",
            "history": [{"role": "user", "content": "左轮不转怎么办"}],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["reply"] == "可行，建议 10ms 采样"
    (task, problem, qa, reqs, interfaces, main_c, history) = holder["llm"].task_discuss_calls[0]
    assert task["id"] == "t1" and task["title"] == "循迹"
    assert "循迹" in problem or "巡线" in problem
    assert history == (("user", "左轮不转怎么办"),)
    assert main_c.strip()

    # 空 history → 400（单通道：最后一条 user = 本轮消息，无独立 message 参数）
    resp = client.post(
        "/api/tasks/discuss",
        json={"output_dir": output_dir, "task_id": "t1", "history": []},
    )
    assert resp.status_code == 400
    assert "history" in resp.json()["detail"]
    # history 非数组 → 400
    resp = client.post(
        "/api/tasks/discuss",
        json={"output_dir": output_dir, "task_id": "t1", "history": "不是数组"},
    )
    assert resp.status_code == 400
    assert "history" in resp.json()["detail"]
    # 任务不存在 → 400
    resp = client.post(
        "/api/tasks/discuss",
        json={"output_dir": output_dir, "task_id": "t9", "history": [{"role": "user", "content": "你好"}]},
    )
    assert resp.status_code == 400
    # LLM 失败 → 502
    class _BoomTask:
        def discuss_task(self, **kwargs):
            raise LLMError("上游超时")

    holder["llm"] = _BoomTask()
    resp = client.post(
        "/api/tasks/discuss",
        json={"output_dir": output_dir, "task_id": "t1", "history": [{"role": "user", "content": "你好"}]},
    )
    assert resp.status_code == 502
    assert "上游超时" in resp.json()["detail"]


def test_tasks_idea_chat_send_read_adopt_flow(tasks_client):
    """全局商量三端点（工单 idea-suite/01）：send 落盘 user+assistant 两条 →
    read 全量读回 → adopt 覆盖 note / 空串清除；LLM 失败不落半轮。"""
    from contest_generator.idea_chat import IDEA_CHAT_FILENAME, read_idea_chat
    from contest_generator.llm import LLMError, TaskDiscussion

    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        global_discussion=TaskDiscussion(reply="可行——先加一阶低通，再接 PID。"),
    )

    # 无文件 read → 空聊天（不 400）
    resp = client.post("/api/tasks/idea/chat/read", json={"output_dir": output_dir})
    assert resp.status_code == 200, resp.text
    assert resp.json()["chat"]["messages"] == []
    assert resp.json()["chat"]["note"] == ""

    # send 一轮：历史单通道（最后一条 user = 本轮消息）
    resp = client.post(
        "/api/tasks/idea/chat/send",
        json={
            "output_dir": output_dir,
            "history": [{"role": "user", "content": "整体架构要不要加滤波？"}],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["reply"] == "可行——先加一阶低通，再接 PID。"
    chat = read_idea_chat(Path(output_dir))
    assert [m.role for m in chat.messages] == ["user", "assistant"]
    assert chat.messages[0].content == "整体架构要不要加滤波？"
    assert (Path(output_dir) / IDEA_CHAT_FILENAME).is_file()
    # LLM 输入：题面/接口/main.c/清单(未拆解 None)/全局结论空/历史含本轮
    (problem, qa, reqs, points, interfaces, main_c, plan, note, history) = (
        holder["llm"].global_discuss_calls[0]
    )
    assert history == (("user", "整体架构要不要加滤波？"),)
    assert note == ""
    assert plan is None  # 未拆解允许全局商量
    assert main_c.strip()

    # read：全量读回
    resp = client.post("/api/tasks/idea/chat/read", json={"output_dir": output_dir})
    assert resp.status_code == 200
    data = resp.json()["chat"]
    assert len(data["messages"]) == 2
    assert data["messages"][1]["content"] == "可行——先加一阶低通，再接 PID。"

    # adopt：覆盖 note；再发一轮后 note 仍在（后缀消息不清除）
    resp = client.post(
        "/api/tasks/idea/chat/adopt",
        json={"output_dir": output_dir, "text": "全局结论：先保证循迹稳定再上 PID"},
    )
    assert resp.status_code == 200
    assert resp.json()["chat"]["note"] == "全局结论：先保证循迹稳定再上 PID"
    assert read_idea_chat(Path(output_dir)).note == "全局结论：先保证循迹稳定再上 PID"

    # adopt 空串 = 清除
    resp = client.post(
        "/api/tasks/idea/chat/adopt", json={"output_dir": output_dir, "text": ""}
    )
    assert resp.status_code == 200
    assert resp.json()["chat"]["note"] == ""
    assert read_idea_chat(Path(output_dir)).note == ""

    # 校验 400：history 空 / role 非法 / text 非字符串
    resp = client.post(
        "/api/tasks/idea/chat/send",
        json={"output_dir": output_dir, "history": []},
    )
    assert resp.status_code == 400
    resp = client.post(
        "/api/tasks/idea/chat/send",
        json={
            "output_dir": output_dir,
            "history": [{"role": "system", "content": "坏"}],
        },
    )
    assert resp.status_code == 400
    # 末条强制 user（评审整改）：assistant 结尾会被错标为 user 落盘——拒收
    resp = client.post(
        "/api/tasks/idea/chat/send",
        json={
            "output_dir": output_dir,
            "history": [{"role": "assistant", "content": "AI 结尾"}],
        },
    )
    assert resp.status_code == 400
    assert "最后一条必须是 user" in resp.json()["detail"]
    resp = client.post(
        "/api/tasks/idea/chat/adopt",
        json={"output_dir": output_dir, "text": 123},
    )
    assert resp.status_code == 400
    assert "必须是字符串" in resp.json()["detail"]

    # LLM 失败 → 502 且不落半轮（user 消息也不追加；历史仍是上一轮 2 条）
    class _BoomGlobal:
        def discuss_global_idea(self, **kwargs):
            raise LLMError("上游超时")

    holder["llm"] = _BoomGlobal()
    before = len(read_idea_chat(Path(output_dir)).messages)
    resp = client.post(
        "/api/tasks/idea/chat/send",
        json={
            "output_dir": output_dir,
            "history": [{"role": "user", "content": "又想到一个问题"}],
        },
    )
    assert resp.status_code == 502
    assert len(read_idea_chat(Path(output_dir)).messages) == before


def test_tasks_execute_injects_global_note(tasks_client, monkeypatch):
    """执行端点注入全局结论（工单 idea-suite/01）：.contest_idea_chat.json
    的 note → run_task 的 global_note 透传 LLM；无文件 → 空串。"""
    from contest_generator.idea_chat import read_idea_chat, set_chat_note, write_idea_chat

    client, holder, tmp_path = tasks_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(
        task_plan=TaskPlan(tasks=(Task(id="t1", title="循迹", description="循迹决策"),))
    )
    client.post("/api/tasks/plan", json={"output_dir": output_dir})
    write_idea_chat(
        Path(output_dir),
        set_chat_note(read_idea_chat(Path(output_dir)), "全局结论：循迹阈值 500 起步"),
    )
    holder["llm"] = FakeLLM(
        executed_main_c="int main(void) { /* 循迹已实现 */ while (1); }\n"
    )
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    resp = client.post(
        "/api/tasks/execute", json={"output_dir": output_dir, "task_id": "t1"}
    )
    assert resp.status_code == 200, resp.text
    assert holder["llm"].execute_task_calls[0][-1] == "全局结论：循迹阈值 500 起步"

    # 清除聊天文件 → 空串（既有形状）
    (Path(output_dir) / ".contest_idea_chat.json").unlink()
    holder["llm"] = FakeLLM(
        executed_main_c="int main(void) { /* 循迹再实现 */ while (1); }\n"
    )
    resp = client.post(
        "/api/tasks/execute", json={"output_dir": output_dir, "task_id": "t1"}
    )
    assert resp.status_code == 200, resp.text
    assert holder["llm"].execute_task_calls[-1][-1] == ""
