"""深化（工单 revise-deepen/04）：填 TODO + 编译验证闭环的测试。

只测外部行为：LLM 深化调用（需求逐条注入）、写盘前备份可回滚、无工具链大声
降级（结果保留、状态 = 未验证）、编译绿 = 已验证、失败修复后重编译绿、修一
轮仍红 = failed、webapp 深化端点（SSE 事件序列 + 错误路径）。编译通过
monkeypatch collect_build_log 注入（不真起编译器）。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from contest_generator.deepen import (
    STATUS_FAILED,
    STATUS_UNVERIFIED,
    STATUS_VERIFIED,
    _main_diff,
    run_deepen,
)
from contest_generator.platforms import PLATFORM_STM32
from contest_generator.webapp import AppContext, AppConfig, create_app
from tests.fakes import (
    FakeLLM,
    make_fake_master_project,
    make_fake_module_library,
)
from tests.test_impact import _sse_events


def _build(exit_code: int, output: str = ""):
    """假编译结果（compile_runner.BuildLog 同构形状）。"""
    return SimpleNamespace(
        platform=PLATFORM_STM32,
        run=SimpleNamespace(
            exit_code=exit_code, output=output, timed_out=False, duration=0.1
        ),
    )


def _deepen_env(tmp_path):
    """假模块库 + 假母版。"""
    library = make_fake_module_library(tmp_path / "modules")
    make_fake_master_project(tmp_path / "masters" / PLATFORM_STM32)
    return library


def _no_toolchain(monkeypatch):
    """无工具链：resolve_compile_toolchain 抛 CompileRunnerError（与 /api/compile
    起流前 400 同源，deepen 转降级）。"""
    from contest_generator.compile_runner import CompileRunnerError

    def _raise(platform, uv4_override="", make_override=""):
        raise CompileRunnerError("未检测到工具链")

    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain", _raise
    )


def _uv4_toolchain(monkeypatch, tmp_path):
    """有工具链：resolve_compile_toolchain 返回 (UV4, None)。"""
    monkeypatch.setattr(
        "contest_generator.deepen.resolve_compile_toolchain",
        lambda platform, uv4_override="", make_override="": (tmp_path / "UV4.exe", None),
    )


def test_run_deepen_without_toolchain_degrades_loudly(tmp_path, monkeypatch):
    """无工具链 → 大声降级：结果保留、状态 = 未验证、备份可回滚、中文提示。"""
    from contest_generator.generator import generate_project

    library = _deepen_env(tmp_path)
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
    _no_toolchain(monkeypatch)
    llm = FakeLLM(deepened_main_c="int main(void) { /* 已实现 */ while (1); }\n")
    events: list[str] = []

    def emit_progress(event) -> None:
        events.append(event.type)

    result = run_deepen(
        llm=llm,
        problem_text="题面",
        qa_text="",
        requirements=[{"requirement": "循迹", "sentence": 1}],
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
    # 结果保留（深化写盘）
    assert "已实现" in (output_dir / "main.c").read_text(encoding="utf-8")
    # 未触发编译事件
    assert "compile_start" not in events
    assert events[0] == "deepening_start"


def test_run_deepen_verified_when_compile_passes(tmp_path, monkeypatch):
    """有工具链 + 编译绿 → 状态 = 已验证。"""
    from contest_generator.generator import generate_project

    library = _deepen_env(tmp_path)
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
    _uv4_toolchain(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    llm = FakeLLM(deepened_main_c="int main(void) { /* 已实现 */ while (1); }\n")
    events: list[str] = []

    def emit_progress(event) -> None:
        events.append(event.type)

    result = run_deepen(
        llm=llm,
        problem_text="题面",
        qa_text="",
        requirements=(),
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=emit_progress),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_VERIFIED
    assert result["compile"]["passed"] is True
    assert "deepening_start" in events
    assert "compile_start" in events
    assert "verify_result" in events


def test_run_deepen_fixes_once_then_verifies(tmp_path, monkeypatch):
    """首轮编译失败 → 修复一轮 → 重编译绿 = 已验证。"""
    from contest_generator.generator import generate_project

    library = _deepen_env(tmp_path)
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
    _uv4_toolchain(monkeypatch, tmp_path)
    calls = {"n": 0}

    def fake_collect(platform, out_dir, uv4=None, make=None):
        calls["n"] += 1
        return _build(2, "error: something") if calls["n"] == 1 else _build(0)

    monkeypatch.setattr("contest_generator.deepen.collect_build_log", fake_collect)
    fixed = {"n": 0}

    def fake_fix_round(llm, **kwargs):
        fixed["n"] += 1
        return SimpleNamespace(backup_id="fix-1", results=())

    monkeypatch.setattr("contest_generator.deepen.run_fix_round", fake_fix_round)
    llm = FakeLLM(deepened_main_c="int main(void) { /* 已实现 */ while (1); }\n")
    events: list[str] = []

    def emit_progress(event) -> None:
        events.append(event.type)

    result = run_deepen(
        llm=llm,
        problem_text="题面",
        qa_text="",
        requirements=(),
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c="int main(void) { /* TODO */ while (1); }\n",
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=emit_progress),  # type: ignore[arg-type]
    )
    assert result["status"] == STATUS_VERIFIED
    assert fixed["n"] == 1  # 修复恰好一轮
    assert calls["n"] == 2  # 编译 + 重编译
    assert "fix_start" in events


def test_run_deepen_failed_after_one_fix_round(tmp_path, monkeypatch):
    """修一轮仍红 → 状态 = failed（结果保留，中文提示）。"""
    from contest_generator.generator import generate_project

    library = _deepen_env(tmp_path)
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
    _uv4_toolchain(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(2, "error: x"),
    )
    monkeypatch.setattr(
        "contest_generator.deepen.run_fix_round",
        lambda llm, **kwargs: SimpleNamespace(backup_id="fix-1", results=()),
    )
    llm = FakeLLM(deepened_main_c="int main(void) { /* 已实现 */ while (1); }\n")
    result = run_deepen(
        llm=llm,
        problem_text="题面",
        qa_text="",
        requirements=(),
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


# ---------------------------------------------------------------------------
# 深化效果报告（工单 deepen-report/01）：main.c 前后确定性 diff 纯函数
# ---------------------------------------------------------------------------


def test_main_diff_none_when_unchanged():
    """深化前后相同 → main_diff = None（无差异，前端展示占位）。"""
    assert _main_diff("int main(void) { }\n", "int main(void) { }\n") is None


def test_main_diff_single_hunk_stats_and_todo_title():
    """单 hunk：统计正确；hunk 标题取被替换的 TODO 注释（可追踪）。"""
    before = "int main(void) {\n    // TODO: 循迹\n    while (1);\n}\n"
    after = "int main(void) {\n    line_follow();\n    while (1);\n}\n"
    diff = _main_diff(before, after)
    assert diff is not None
    assert diff["stats"] == {"additions": 1, "deletions": 1, "hunks": 1}
    hunk = diff["hunks"][0]
    assert hunk["header"].startswith("@@ -")
    assert hunk["line"] == 1
    assert "TODO" in hunk["title"]
    kinds = [entry["kind"] for entry in hunk["lines"]]
    assert kinds[0] == "ctx" and kinds[1] == "del" and kinds[2] == "add"
    assert hunk["lines"][1]["text"] == "    // TODO: 循迹"
    assert hunk["lines"][2]["text"] == "    line_follow();"
    assert diff["text"].startswith("---")


def test_main_diff_multi_hunk_stats():
    """相距 >2n 行的两处改动 → 两个独立 hunk，统计逐项正确。"""
    before = "l1\nl2\nl3\nl4\nl5\nl6\nl7\nl8\nl9\nl10\nl11\n"
    after = "l1\nX2\nl3\nl4\nl5\nl6\nl7\nl8\nX9\nl10\nl11\n"
    diff = _main_diff(before, after)
    assert diff is not None
    assert diff["stats"] == {"additions": 2, "deletions": 2, "hunks": 2}
    assert [h["line"] for h in diff["hunks"]] == [1, 7]


def test_main_diff_title_falls_back_to_plain_comment():
    """无 TODO 注释时：标题退化为删除行注释文本，再退化空串（前端用行号）。"""
    before = "int main(void) {\n    dummy();\n}\n"
    after = "int main(void) {\n    real();\n}\n"
    diff = _main_diff(before, after)
    assert diff is not None
    assert diff["hunks"][0]["title"] == ""  # 无注释无 TODO → 空标题


# ---------------------------------------------------------------------------
# run_deepen：done 载荷含 main_diff（深化效果报告）
# ---------------------------------------------------------------------------


def test_run_deepen_main_diff_in_payload(tmp_path, monkeypatch):
    """rune_deepen 返回载荷含 main_diff；LLM 原样返回 → None（无差异）。"""
    from contest_generator.generator import generate_project

    library = _deepen_env(tmp_path)
    output_dir = tmp_path / "out"
    main_c = "int main(void) { /* TODO */ while (1); }\n"
    generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content=main_c,
        output_dir=output_dir,
        module_library_dir=library,
        masters_dir=tmp_path / "masters",
        problem_text="题面",
    )
    _uv4_toolchain(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )

    # 有差异：深化改动了 main.c
    llm = FakeLLM(deepened_main_c="int main(void) { /* 已实现 */ while (1); }\n")
    result = run_deepen(
        llm=llm,
        problem_text="题面",
        qa_text="",
        requirements=(),
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c=main_c,
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result["main_diff"] is not None
    assert result["main_diff"]["stats"] == {"additions": 1, "deletions": 1, "hunks": 1}
    assert "已实现" in result["main_diff"]["text"]

    # 无差异：LLM 原样返回 → main_diff = None（前端显示占位，不冒充改动）
    llm2 = FakeLLM(deepened_main_c=main_c)
    result2 = run_deepen(
        llm=llm2,
        problem_text="题面",
        qa_text="",
        requirements=(),
        manifests=[],
        platform=PLATFORM_STM32,
        library_dir=library,
        master_project_dir=tmp_path / "masters" / PLATFORM_STM32,
        main_c=main_c,
        output_dir=output_dir,
        work_root=tmp_path / "work",
        emit=SimpleNamespace(progress=lambda event: None),  # type: ignore[arg-type]
    )
    assert result2["main_diff"] is None


# ---------------------------------------------------------------------------
# webapp /api/revise/deepen：SSE 事件序列与错误路径
# ---------------------------------------------------------------------------


@pytest.fixture
def deepen_client(tmp_path):
    """已配置的假上下文：假模块库 + 假母版 + 假 LLM。"""
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
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["output_dir"]


def test_revise_deepen_sse_flow_unverified(deepen_client, monkeypatch):
    """深化端点：deepening_start → verify_result → done（无工具链降级）。"""
    client, holder, tmp_path = deepen_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(deepened_main_c="int main(void) { /* 已实现 */ }\n")
    _no_toolchain(monkeypatch)
    resp = client.post("/api/revise/deepen", json={"output_dir": output_dir})
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    types = [event_type for event_type, _ in events]
    assert types[-1] == "done"
    done = events[-1][1]
    assert done["status"] == STATUS_UNVERIFIED
    assert "deepening_start" in types
    assert "verify_result" in types
    # 深化效果报告：done 载荷含 main_diff（深化前 vs 深化后真实 diff）
    assert done["main_diff"] is not None
    assert done["main_diff"]["stats"]["additions"] == 1
    assert "已实现" in done["main_diff"]["text"]
    # 深化写盘生效
    assert "已实现" in (Path(output_dir) / "main.c").read_text(encoding="utf-8")


def test_revise_deepen_verified(deepen_client, monkeypatch):
    """编译绿（monkeypatch collect_build_log）→ 状态 = 已验证。"""
    client, holder, tmp_path = deepen_client
    output_dir = _generate_project(client, tmp_path)
    holder["llm"] = FakeLLM(deepened_main_c="int main(void) { /* 已实现 */ }\n")
    _uv4_toolchain(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "contest_generator.deepen.collect_build_log",
        lambda platform, out_dir, uv4=None, make=None: _build(0),
    )
    resp = client.post("/api/revise/deepen", json={"output_dir": output_dir})
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    assert events[-1][0] == "done"
    assert events[-1][1]["status"] == STATUS_VERIFIED
    assert events[-1][1]["main_diff"] is not None


def test_revise_deepen_missing_main_c_400(deepen_client):
    """main.c 为空 → 同步 400（中文提示）。"""
    client, _, tmp_path = deepen_client
    out = tmp_path / "empty"
    out.mkdir()
    (out / "project.uvprojx").write_text("<Project/>", encoding="utf-8")
    resp = client.post("/api/revise/deepen", json={"output_dir": str(out)})
    assert resp.status_code == 400
    assert "main.c" in resp.json()["detail"]
