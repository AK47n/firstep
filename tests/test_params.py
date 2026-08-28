"""参数速调（工单 param-tune/01）：域判决 / 读写 / 确定性改值 / 编排 / 端点。

只测外部行为：build_params 锚硬校验（anchor 逐字节在 main.c 且 old_value
恰 1 次——不满足宁拒收不静默）、apply_param_change 确定性（单处替换、其余
文本不变）、读写 roundtrip 与损坏、run_param_scan / run_param_apply 编排
（事件 + 落盘 + 备份）、三端点（SSE 事件序列 + 400 分支 + read valid 标志）。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from contest_generator.params import (
    PARAMS_FILENAME,
    ParamItem,
    ParamList,
    apply_param_change,
    build_params,
    empty_params,
    load_params_file,
    read_params,
    run_param_apply,
    run_param_scan,
    write_params,
)
from contest_generator.platforms import PLATFORM_STM32
from contest_generator.task_progress import TaskError
from contest_generator.webapp import AppContext, AppConfig, create_app
from tests.fakes import (
    FakeLLM,
    make_fake_master_project,
    make_fake_module_library,
)
from tests.test_impact import _sse_events

MAIN_WITH_PARAM = (
    "#define THRESHOLD 800\n"
    "#define SPEED 120\n"
    "int main(void) { int x = 800; return 0; }\n"
)


def _item(
    name: str = "THRESHOLD",
    label: str = "循迹阈值",
    old_value: str = "800",
    anchor: str = "#define THRESHOLD 800",
    **extra: Any,
) -> ParamItem:
    base = dict(name=name, label=label, old_value=old_value, anchor=anchor)
    base.update(extra)
    return ParamItem(**base)


def _param_list(*items: ParamItem) -> ParamList:
    return ParamList(version=1, generated_at="2026-01-01T00:00:00+0000", params=tuple(items))


# ---------------------------------------------------------------------------
# build_params：LLM 输出的域判决（锚硬校验）
# ---------------------------------------------------------------------------


def test_build_params_valid():
    raw = {
        "params": [
            {
                "name": "THRESHOLD",
                "label": "循迹阈值",
                "old_value": "800",
                "anchor": "#define THRESHOLD 800",
                "unit": "",
                "range_hint": "500-1000",
            },
            {
                "name": "SPEED",
                "label": "速度",
                "old_value": "120",
                "anchor": "#define SPEED 120",
            },
        ]
    }
    result = build_params(raw, MAIN_WITH_PARAM)
    assert result.version == 1
    assert len(result.params) == 2
    assert result.params[0].name == "THRESHOLD"
    assert result.params[0].range_hint == "500-1000"
    assert result.params[1].unit == ""  # 宽松缺省
    assert result.params[1].range_hint == ""


def test_build_params_rejects_missing_fields():
    """name/label/old_value/anchor 任一缺失或空串 → TaskError（指明条目）。"""
    for field in ("name", "label", "old_value", "anchor"):
        raw = {
            "params": [
                {
                    "name": "THRESHOLD" if field != "name" else "",
                    "label": "循迹阈值" if field != "label" else "",
                    "old_value": "800" if field != "old_value" else "",
                    "anchor": "#define THRESHOLD 800" if field != "anchor" else "",
                }
            ]
        }
        with pytest.raises(TaskError, match=f"缺少 {field}"):
            build_params(raw, MAIN_WITH_PARAM)


def test_build_params_rejects_anchor_not_in_main_c():
    raw = {
        "params": [
            {
                "name": "THRESHOLD",
                "label": "循迹阈值",
                "old_value": "800",
                "anchor": "#define THRESHOLD 999",
            }
        ]
    }
    with pytest.raises(TaskError, match="锚不在 main.c"):
        build_params(raw, MAIN_WITH_PARAM)


def test_build_params_rejects_old_value_multiple_in_anchor():
    main_c = "#define THRESHOLD 800 + 800\nint main(void) { return 0; }\n"
    raw = {
        "params": [
            {
                "name": "THRESHOLD",
                "label": "循迹阈值",
                "old_value": "800",
                "anchor": "#define THRESHOLD 800 + 800",
            }
        ]
    }
    with pytest.raises(TaskError, match="出现 2 次"):
        build_params(raw, main_c)


def test_build_params_rejects_old_value_not_full_token():
    """子串式旧值（"80" 在 "#define THRESHOLD 800" 中恰 1 次但非完整字面量）
    → 拒收（防替换得 9000 击穿确定性改值，standards 轴整改）。"""
    raw = {
        "params": [
            {
                "name": "THRESHOLD",
                "label": "循迹阈值",
                "old_value": "80",
                "anchor": "#define THRESHOLD 800",
            }
        ]
    }
    with pytest.raises(TaskError, match="完整字面量"):
        build_params(raw, MAIN_WITH_PARAM)


def test_build_params_accepts_suffixed_literal():
    """带后缀完整值（3000UL）通过；其子串（3000 / 3000U）被拒。"""
    main_c = "#define LIMIT 3000UL\nint main(void) { return 0; }\n"
    raw = {
        "params": [
            {
                "name": "LIMIT",
                "label": "上限",
                "old_value": "3000UL",
                "anchor": "#define LIMIT 3000UL",
            }
        ]
    }
    assert build_params(raw, main_c).params[0].old_value == "3000UL"
    for bad in ("3000", "3000U"):
        with pytest.raises(TaskError, match="完整字面量"):
            build_params(
                {
                    "params": [
                        {
                            "name": "LIMIT",
                            "label": "上限",
                            "old_value": bad,
                            "anchor": "#define LIMIT 3000UL",
                        }
                    ]
                },
                main_c,
            )


def test_apply_param_change_rejects_substring_old_value():
    """读回表数据被手改成子串 → apply 拒（锚失效文案）。"""
    with pytest.raises(TaskError, match="锚已失效"):
        apply_param_change(MAIN_WITH_PARAM, _item(old_value="80"), "900")


def test_build_params_empty_params_ok():
    result = build_params({"params": []}, MAIN_WITH_PARAM)
    assert result.params == ()


def test_build_params_rejects_bad_shapes():
    with pytest.raises(TaskError, match="JSON 对象"):
        build_params([], MAIN_WITH_PARAM)
    with pytest.raises(TaskError, match="缺少 params"):
        build_params({}, MAIN_WITH_PARAM)
    with pytest.raises(TaskError, match="不是对象"):
        build_params({"params": ["x"]}, MAIN_WITH_PARAM)


# ---------------------------------------------------------------------------
# 读写：roundtrip / 无文件 / 坏 JSON / 结构非法
# ---------------------------------------------------------------------------


def test_params_write_read_roundtrip(tmp_path):
    param_list = _param_list(_item())
    path = write_params(tmp_path, param_list)
    assert path.name == PARAMS_FILENAME
    assert not (tmp_path / (PARAMS_FILENAME + ".tmp")).exists()  # 原子写不残留
    loaded = read_params(tmp_path)
    assert loaded.params[0].name == "THRESHOLD"
    assert loaded.params[0].anchor == "#define THRESHOLD 800"
    assert not loaded.params[0].unit


def test_read_params_missing_is_empty(tmp_path):
    assert read_params(tmp_path).params == ()


def test_load_params_file_corrupt(tmp_path):
    path = tmp_path / PARAMS_FILENAME
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(TaskError, match="损坏"):
        load_params_file(tmp_path)
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(TaskError, match="必须是 JSON 对象"):
        load_params_file(tmp_path)
    path.write_text('{"params": "x"}', encoding="utf-8")
    with pytest.raises(TaskError, match="必须是列表"):
        load_params_file(tmp_path)


def test_load_params_file_tolerates_bad_entries(tmp_path):
    """条目级容错：坏条目忽略（与 idea_chat/drafts 同先例），版本缺省补 1。"""
    path = tmp_path / PARAMS_FILENAME
    path.write_text(
        json.dumps(
            {
                "params": [
                    {"name": "A", "label": "好的", "old_value": "1", "anchor": "A=1"},
                    {"name": 123, "label": "坏", "old_value": "1", "anchor": "x"},
                    "不是对象",
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    loaded = load_params_file(tmp_path)
    assert loaded is not None
    assert loaded.version == 1
    assert len(loaded.params) == 1
    assert loaded.params[0].name == "A"


# ---------------------------------------------------------------------------
# apply_param_change：确定性改值（零 LLM 的落点）
# ---------------------------------------------------------------------------


def test_apply_param_change_replaces_only_anchor():
    """anchor 首现处 old_value 换新值；同值出现在别处（main 里 x=800）不动。"""
    updated = apply_param_change(MAIN_WITH_PARAM, _item(), "900")
    assert "#define THRESHOLD 900" in updated
    assert "int x = 800" in updated  # 锚外同值不受影响
    assert "#define SPEED 120" in updated


def test_apply_param_change_anchor_stale_raises():
    with pytest.raises(TaskError, match="锚已失效"):
        apply_param_change(
            "int main(void) { return 0; }\n", _item(), "900"
        )


def test_apply_param_change_old_value_missing_in_anchor():
    with pytest.raises(TaskError, match="锚已失效"):
        apply_param_change(MAIN_WITH_PARAM, _item(old_value="999"), "900")


def test_apply_param_change_value_validation():
    for bad in ("", "   ", "x" * 65):
        with pytest.raises(TaskError):
            apply_param_change(MAIN_WITH_PARAM, _item(), bad)
    # 边界：64 字符放行（格式自由，spec 用户故事 7）
    updated = apply_param_change(MAIN_WITH_PARAM, _item(), "1" * 64)
    assert "#define THRESHOLD " + "1" * 64 in updated


# ---------------------------------------------------------------------------
# 编排：run_param_scan / run_param_apply（事件 + 落盘 + 备份 + 写盘）
# ---------------------------------------------------------------------------


def test_run_param_scan_writes_and_emits(tmp_path):
    events: list[Any] = []
    emit = SimpleNamespace(progress=lambda event: events.append(event))
    llm = FakeLLM()
    result = run_param_scan(
        llm=llm,
        main_c=MAIN_WITH_PARAM,
        module_interfaces=("/* 接口 */",),
        output_dir=tmp_path,
        emit=emit,  # type: ignore[arg-type]
    )
    assert [e.type for e in events] == ["param_scanning"]
    assert result.params[0].name == "THRESHOLD"
    saved = read_params(tmp_path)
    assert saved.params[0].label == "循迹阈值"
    assert len(llm.scan_params_calls) == 1
    assert llm.scan_params_calls[0][0] == MAIN_WITH_PARAM
    assert llm.scan_params_calls[0][1] == ("/* 接口 */",)


def test_run_param_scan_empty_skips_write(tmp_path):
    """识别结果为空表 → 不落盘（spec 用户故事 6 + spec 轴评审整改）：
    无文件 = 未识别过，空表落盘会让「尚未识别」与「已识别无参数」两态无法区分。"""
    events: list[Any] = []
    emit = SimpleNamespace(progress=lambda event: events.append(event))
    llm = FakeLLM(param_list=empty_params())
    result = run_param_scan(
        llm=llm,
        main_c=MAIN_WITH_PARAM,
        module_interfaces=(),
        output_dir=tmp_path,
        emit=emit,  # type: ignore[arg-type]
    )
    assert result.params == ()
    assert [e.type for e in events] == ["param_scanning"]
    assert not (tmp_path / PARAMS_FILENAME).exists()


def test_refresh_param_after_apply():
    """apply 后的表回写单测：目标项 old_value/anchor 同步为磁盘状态，
    其余项与顺序原样；锚不在磁盘（修复轮改值）→ 保持旧值；无变化 → 原对象。"""
    from contest_generator.params import _refresh_param_after_apply

    table = _param_list(_item(), _item(name="SPEED", old_value="120", anchor="#define SPEED 120"))
    refreshed = _refresh_param_after_apply(table, "THRESHOLD", "900", MAIN_WITH_PARAM.replace("800", "900", 1))
    assert refreshed is not table
    assert refreshed.params[0].old_value == "900"
    assert refreshed.params[0].anchor == "#define THRESHOLD 900"
    assert refreshed.params[1].old_value == "120"
    assert refreshed.params[1].anchor == "#define SPEED 120"
    # 锚不在磁盘（修复轮改值）→ 该项保持旧值（前端标失效 = 诚实）
    stale = _refresh_param_after_apply(table, "THRESHOLD", "900", MAIN_WITH_PARAM)
    assert stale is table
    # 找不到 name → 原对象
    missing = _refresh_param_after_apply(table, "NO_SUCH", "900", MAIN_WITH_PARAM)
    assert missing is table


def test_run_param_apply_replaces_writes_and_verifies(tmp_path, monkeypatch):
    _green_toolchain(monkeypatch, tmp_path)
    # 模拟真实工程：盘上已有 main.c（备份树非空前提，backup_tree 拒绝空目录）
    (tmp_path / "main.c").write_text(MAIN_WITH_PARAM, encoding="utf-8")
    # 已有参数表（apply 后应回写 old_value/anchor——spec 轴评审整改）
    write_params(tmp_path, _param_list(_item()))
    events: list[Any] = []
    emit = SimpleNamespace(progress=lambda event: events.append(event))
    result = run_param_apply(
        llm=FakeLLM(),
        param=_item(),
        new_value="900",
        main_c=MAIN_WITH_PARAM,
        output_dir=tmp_path,
        work_root=tmp_path / "work",
        platform=PLATFORM_STM32,
        module_slugs=(),
        uv4_override="",
        make_override="",
        emit=emit,  # type: ignore[arg-type]
    )
    assert result["status"] == "verified"
    assert result["main_diff"]["stats"]["additions"] == 1
    assert "#define THRESHOLD 900" in (tmp_path / "main.c").read_text(encoding="utf-8")
    assert "int x = 800" in (tmp_path / "main.c").read_text(encoding="utf-8")
    assert [e.type for e in events][0] == "param_applying"
    assert "compile_start" in [e.type for e in events]
    # 备份目录有修改前快照（回滚入口存在）
    backup_root = tmp_path / "work" / "revise-backups"
    assert any(backup_root.iterdir())
    # apply 后参数表已回写：old_value/new anchor 与磁盘一致（/read 重验不误标失效）
    refreshed = read_params(tmp_path)
    assert refreshed.params[0].old_value == "900"
    assert refreshed.params[0].anchor == "#define THRESHOLD 900"


def test_run_param_apply_anchor_stale_raises_before_write(tmp_path):
    (tmp_path / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    events: list[Any] = []
    emit = SimpleNamespace(progress=lambda event: events.append(event))
    with pytest.raises(TaskError, match="锚已失效"):
        run_param_apply(
            llm=FakeLLM(),
            param=_item(),
            new_value="900",
            main_c="int main(void) { return 0; }\n",
            output_dir=tmp_path,
            work_root=tmp_path / "work",
            platform=PLATFORM_STM32,
            module_slugs=(),
            uv4_override="",
            make_override="",
            emit=emit,  # type: ignore[arg-type]
        )
    # 锚失效：不改 main.c（盘上内容仍为原样）
    assert (tmp_path / "main.c").read_text(encoding="utf-8") == "int main(void) { return 0; }\n"


# ---------------------------------------------------------------------------
# 端点：scan / apply / read（SSE 序列 + 400 分支 + valid 标志）
# ---------------------------------------------------------------------------


def _params_client(tmp_path):
    """假上下文（照 tasks_client 先例）：假模块库 + 假母版 + 假 LLM。"""
    config_path = tmp_path / "cfg" / "config.json"
    library_dir = make_fake_module_library(tmp_path / "module_library")
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    holder: dict[str, Any] = {"llm": FakeLLM()}
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
    """生成一个假工程（含 .contest_context.json + main.c）。"""
    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11"],
            "main_c": MAIN_WITH_PARAM,
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


def _green_toolchain(monkeypatch, tmp_path):
    from types import SimpleNamespace as _NS

    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _NS(
            platform=PLATFORM_STM32,
            run=_NS(exit_code=0, output="", timed_out=False, duration=0.1),
        ),
    )


def test_params_scan_sse_flow(tmp_path):
    client, holder, _ = _params_client(tmp_path)
    output_dir = _generate_project(client, tmp_path)
    resp = client.post(
        "/api/tasks/params/scan", json={"output_dir": output_dir}
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    types = [t for t, _ in events]
    assert types[-1] == "done"
    assert "param_scanning" in types
    assert "param_result" in types
    assert events[-1][1]["params"][0]["name"] == "THRESHOLD"
    # 落盘：参数表文件存在
    assert (Path(output_dir) / PARAMS_FILENAME).is_file()
    # LLM 收到 main.c + 接口
    assert holder["llm"].scan_params_calls[0][0] == MAIN_WITH_PARAM


def test_params_apply_sse_flow(tmp_path, monkeypatch):
    _green_toolchain(monkeypatch, tmp_path)
    client, _, _ = _params_client(tmp_path)
    output_dir = _generate_project(client, tmp_path)
    resp = client.post("/api/tasks/params/scan", json={"output_dir": output_dir})
    assert resp.status_code == 200, resp.text
    resp = client.post(
        "/api/tasks/params/apply",
        json={"output_dir": output_dir, "name": "THRESHOLD", "value": "900"},
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    types = [t for t, _ in events]
    assert types[-1] == "done"
    assert "param_applying" in types
    assert "compile_start" in types
    assert "verify_result" in types
    done = events[-1][1]
    assert done["status"] == "verified"
    assert done["main_diff"]["stats"]["additions"] == 1
    # 磁盘 main.c 已改值；备份回滚可用（work_root = masters_dir.parent → tmp_path）
    main_text = (Path(output_dir) / "main.c").read_text(encoding="utf-8")
    assert "#define THRESHOLD 900" in main_text
    assert "int x = 800" in main_text
    assert any((tmp_path / "revise-backups").glob("*"))
    # 参数表已回写（评审整改）：apply 后 read 的 old_value 是新值且 valid
    resp = client.post("/api/tasks/params/read", json={"output_dir": output_dir})
    assert resp.status_code == 200
    assert resp.json()["params"][0]["old_value"] == "900"
    assert resp.json()["params"][0]["valid"] is True


def test_params_read_endpoint(tmp_path):
    client, _, _ = _params_client(tmp_path)
    output_dir = _generate_project(client, tmp_path)
    # 无文件 = 空列表不 400；scanned=False（未识别过）
    resp = client.post("/api/tasks/params/read", json={"output_dir": output_dir})
    assert resp.status_code == 200
    assert resp.json()["params"] == []
    assert resp.json()["scanned"] is False
    resp = client.post("/api/tasks/params/scan", json={"output_dir": output_dir})
    assert resp.status_code == 200, resp.text
    resp = client.post("/api/tasks/params/read", json={"output_dir": output_dir})
    assert resp.status_code == 200
    assert resp.json()["params"][0]["valid"] is True
    assert resp.json()["scanned"] is True
    # main.c 被改动（锚失效）→ valid False
    (Path(output_dir) / "main.c").write_text(
        "#define THRESHOLD 777\nint main(void) { return 0; }\n", encoding="utf-8"
    )
    resp = client.post("/api/tasks/params/read", json={"output_dir": output_dir})
    assert resp.json()["params"][0]["valid"] is False


def test_params_endpoints_error_branches(tmp_path):
    client, _, _ = _params_client(tmp_path)
    output_dir = _generate_project(client, tmp_path)
    # 目录不存在 → 400
    assert client.post(
        "/api/tasks/params/scan", json={"output_dir": str(tmp_path / "nope")}
    ).status_code == 400
    assert client.post(
        "/api/tasks/params/read", json={"output_dir": str(tmp_path / "nope")}
    ).status_code == 400
    # 参数表里没有 name → 400（先走 scan 建表）
    resp = client.post("/api/tasks/params/scan", json={"output_dir": output_dir})
    assert resp.status_code == 200, resp.text
    resp = client.post(
        "/api/tasks/params/apply",
        json={"output_dir": output_dir, "name": "NO_SUCH", "value": "1"},
    )
    assert resp.status_code == 400
    assert "没有参数" in resp.json()["detail"]
    # 新值非法（空 / 超长）→ 路由体 400（spec 轴评审整改：不在流内才 error）
    resp = client.post(
        "/api/tasks/params/apply",
        json={"output_dir": output_dir, "name": "THRESHOLD", "value": "   "},
    )
    assert resp.status_code == 400
    assert "不能为空" in resp.json()["detail"]
    resp = client.post(
        "/api/tasks/params/apply",
        json={"output_dir": output_dir, "name": "THRESHOLD", "value": "x" * 65},
    )
    assert resp.status_code == 400
    assert "过长" in resp.json()["detail"]
