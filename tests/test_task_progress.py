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
from contest_generator.task_progress import (
    STATUS_PENDING,
    TASKS_MANIFEST_BAK_FILENAME,
    TASKS_MANIFEST_FILENAME,
    Task,
    TaskError,
    TaskPlan,
    VERIFY_COMPILE,
    VERIFY_MANUAL,
    backup_task_plan,
    build_task_plan,
    discard_task_plan,
    read_task_plan,
    run_task_planning,
    write_task_plan,
)
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
                },
                {
                    "title": "OLED 显示",
                    "description": "显示采样值",
                    "score_refs": ["s1"],
                    "depends_on": [1],
                    "verify": "manual",
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
    """备档：旧清单 → .bak（旧 .bak 先删）；作废：双文件删除。"""
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    plan = TaskPlan(tasks=(Task(id="t1", title="A", description="x"),))
    write_task_plan(output_dir, plan)
    assert backup_task_plan(output_dir) is True
    assert (output_dir / TASKS_MANIFEST_FILENAME).exists() is False
    assert (output_dir / TASKS_MANIFEST_BAK_FILENAME).exists() is True
    # 无清单 = False
    assert backup_task_plan(output_dir) is False
    # 作废：当前 + 备档双删
    write_task_plan(output_dir, plan)
    assert discard_task_plan(output_dir) is True
    assert (output_dir / TASKS_MANIFEST_FILENAME).exists() is False
    assert (output_dir / TASKS_MANIFEST_BAK_FILENAME).exists() is False
    # 空目录 = False（不误报）
    assert discard_task_plan(output_dir) is False


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
