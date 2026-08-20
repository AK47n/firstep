"""修订影响分析与确定性 diff（工单 revise-deepen/02）的测试。

只测外部行为：diff 纯函数（集合差）、模型输出解析校验（域判决）、编排
（LLM 调用 → diff → 平台警告 → done 载荷）、webapp 分析端点（SSE 事件序列
与错误路径）。素材 = 假模块库 + 假母版 + 假 LLM（fakes.py 先例）。
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from contest_generator.impact import (
    ImpactAnalysis,
    ImpactError,
    QaImpact,
    build_impact_analysis,
    compute_module_diff,
    run_impact_analysis,
)
from contest_generator.platforms import PLATFORM_STM32
from contest_generator.webapp import AppContext, AppConfig, create_app
from tests.fakes import (
    MAIN_SKELETON,
    FakeLLM,
    make_fake_master_project,
    make_fake_module_library,
)
from tests.test_context_manifest import _DummyLLM  # 复用：加载 API 不触 LLM 的桩


# ---------------------------------------------------------------------------
# 确定性 diff（纯函数）
# ---------------------------------------------------------------------------


def test_compute_module_diff_add_remove_unchanged():
    """新旧 slugs 集合差 → 增 / 删 / 不变清单（保持输入顺序）。"""
    diff = compute_module_diff(
        ["delay", "dht11", "oled"], ["delay", "dht11", "oled", "motor", "pid"]
    )
    assert diff.added == ("motor", "pid")  # 新集顺序
    assert diff.removed == ()
    assert diff.unchanged == ("delay", "dht11", "oled")  # 旧集顺序


def test_compute_module_diff_removes_in_old_order():
    diff = compute_module_diff(["a", "b", "c", "d"], ["b", "d"])
    assert diff.added == ()
    assert diff.removed == ("a", "c")  # 旧集顺序
    assert diff.unchanged == ("b", "d")


def test_compute_module_diff_identical_and_empty():
    assert compute_module_diff(["a", "b"], ["a", "b"]).added == ()
    assert compute_module_diff(["a", "b"], ["a", "b"]).removed == ()
    assert compute_module_diff([], []).unchanged == ()
    diff = compute_module_diff([], ["x"])
    assert diff.added == ("x",)
    assert diff.removed == ()


# ---------------------------------------------------------------------------
# 模型输出解析（域判决）
# ---------------------------------------------------------------------------


def test_build_impact_analysis_parses_valid_output():
    """合法输出 → ImpactAnalysis（逐条影响 + 建议模块集）。"""
    analysis = build_impact_analysis(
        {
            "impacts": [
                {
                    "qa_index": 1,
                    "requirement_refs": ["循迹"],
                    "add": ["motor"],
                    "remove": [],
                    "reason": "Q&A 明确要求电机驱动",
                }
            ],
            "suggested_slugs": ["delay", "motor"],
        },
        known_slugs=["delay", "motor", "dht11"],
    )
    assert len(analysis.impacts) == 1
    impact = analysis.impacts[0]
    assert impact.qa_index == 1
    assert impact.add == ("motor",)
    assert impact.reason == "Q&A 明确要求电机驱动"
    assert analysis.suggested_slugs == ("delay", "motor")


def test_build_impact_analysis_tolerates_missing_optional_fields():
    """缺 add / remove / requirement_refs = 补空（旧版本模型输出容忍）。"""
    analysis = build_impact_analysis(
        {"impacts": [{"qa_index": 1, "reason": "确认原方案"}], "suggested_slugs": []},
        known_slugs=["delay"],
    )
    assert analysis.impacts[0].add == ()
    assert analysis.impacts[0].remove == ()
    assert analysis.impacts[0].requirement_refs == ()


def test_build_impact_analysis_rejects_missing_suggested_slugs():
    """缺 suggested_slugs（diff 与修订执行必需）→ 大声失败。"""
    with pytest.raises(ImpactError, match="suggested_slugs"):
        build_impact_analysis({"impacts": []}, known_slugs=["delay"])


def test_build_impact_analysis_rejects_unknown_slugs():
    """建议模块集含库外模块（幻觉）→ 大声失败（宁严勿假绿）。"""
    with pytest.raises(ImpactError, match="库外模块"):
        build_impact_analysis(
            {"impacts": [], "suggested_slugs": ["nope"]}, known_slugs=["delay"]
        )


def test_build_impact_analysis_rejects_bad_qa_index_and_reason():
    """qa_index 非正整数 / reason 缺失 → 大声失败。"""
    with pytest.raises(ImpactError, match="qa_index"):
        build_impact_analysis(
            {"impacts": [{"qa_index": 0, "reason": "x"}], "suggested_slugs": []},
            known_slugs=[],
        )
    with pytest.raises(ImpactError, match="理由"):
        build_impact_analysis(
            {"impacts": [{"qa_index": 1}], "suggested_slugs": []}, known_slugs=[]
        )


def test_build_impact_analysis_rejects_non_list_impacts():
    with pytest.raises(ImpactError, match="impacts"):
        build_impact_analysis({"impacts": {}}, known_slugs=[])


# ---------------------------------------------------------------------------
# 编排：LLM → diff → 平台警告 → done 载荷
# ---------------------------------------------------------------------------


class _RecordEmitter:
    """记录进度事件的发射器桩（对照 SseEmitter.progress 形状）。"""

    def __init__(self) -> None:
        self.events: list[str] = []

    def progress(self, event) -> None:
        self.events.append(event.type)


def test_run_impact_analysis_full_pipeline(fake_module_library, tmp_path):
    """编排：假 LLM 建议去掉 oled（diff 移除 1 模块）+ 平台警告重算。"""
    llm = FakeLLM(
        impact_analysis=ImpactAnalysis(
            impacts=(
                QaImpact(qa_index=1, requirement_refs=("循迹",), remove=("oled",), reason="Q&A 不要显示屏"),
            ),
            suggested_slugs=["delay", "dht11"],
        )
    )
    emitter = _RecordEmitter()
    result = run_impact_analysis(
        llm=llm,
        problem_text="巡线小车",
        requirements=[{"requirement": "循迹", "sentence": 1}],
        current_slugs=["delay", "dht11", "oled"],
        manifest_summaries=(),
        new_qa_text="不需要显示屏",
        platform=PLATFORM_STM32,
        library_dir=fake_module_library,
        emit=emitter,  # type: ignore[arg-type]
    )
    assert emitter.events == ["impact_analyzing", "diff_ready"]
    assert result["impacts"][0]["qa_index"] == 1
    assert result["diff"] == {
        "added": [],
        "removed": ["oled"],
        "unchanged": ["delay", "dht11"],
    }
    # dht11/oled/delay 都有 stm32 版本 → 无平台警告
    assert result["warnings"] == []
    assert result["platform"] == PLATFORM_STM32


def test_run_impact_analysis_warnings_recomputed(fake_module_library, tmp_path):
    """平台警告按建议模块集重算：建议集含无 stm32 版本的模块 → missing 警告。"""
    llm = FakeLLM(
        impact_analysis=ImpactAnalysis(
            suggested_slugs=["delay", "dht11", "broken"],  # broken 无 stm32 版本
        )
    )
    emitter = _RecordEmitter()
    result = run_impact_analysis(
        llm=llm,
        problem_text="题面",
        requirements=(),
        current_slugs=["delay", "dht11"],
        manifest_summaries=(),
        new_qa_text="Q&A",
        platform=PLATFORM_STM32,
        library_dir=fake_module_library,
        emit=emitter,  # type: ignore[arg-type]
    )
    kinds = {warning["kind"] for warning in result["warnings"]}
    assert "unverified" in kinds  # broken 有 stm32 条目但未验证
    assert result["diff"]["added"] == ["broken"]


# ---------------------------------------------------------------------------
# webapp /api/revise/analyze：SSE 事件序列与错误路径
# ---------------------------------------------------------------------------


@pytest.fixture
def analyze_client(tmp_path):
    """已配置的假上下文（test_webapp 同款）：假模块库 + 假母版 + 假 LLM。"""
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


def _generate_out(client, tmp_path) -> str:
    """经 /api/generate 生成一个工程（带题面与需求，供分析）。"""
    resp = client.post(
        "/api/generate",
        json={
            "platform": PLATFORM_STM32,
            "slugs": ["dht11", "oled"],
            "main_c": MAIN_SKELETON,
            "problem_text": "2024 巡线小车赛题",
            "output_dir": str(tmp_path / "out"),
            "requirements": [{"requirement": "循迹", "sentence": 1, "modules": ["dht11"]}],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["output_dir"]


def _sse_events(resp) -> list[tuple[str, dict]]:
    """解析 SSE 响应为 [(type, data)]。"""
    events: list[tuple[str, dict]] = []
    current_type = None
    current_data: list[str] = []
    for line in resp.text.splitlines():
        if line.startswith("event: "):
            current_type = line[len("event: "):]
        elif line.startswith("data: "):
            current_data.append(line[len("data: "):])
        elif line == "" and current_type:
            events.append((current_type, json.loads("\n".join(current_data))))
            current_type = None
            current_data = []
    return events


def test_revise_analyze_sse_flow(analyze_client):
    """分析端点：impact_analyzing → diff_ready → done（影响产物 + diff）。"""
    client, holder, tmp_path = analyze_client
    output_dir = _generate_out(client, tmp_path)
    holder["llm"] = FakeLLM(
        impact_analysis=ImpactAnalysis(
            impacts=(
                QaImpact(qa_index=1, reason="确认原方案", remove=()),
            ),
            suggested_slugs=["delay", "dht11", "oled"],
        )
    )
    resp = client.post(
        "/api/revise/analyze",
        json={"output_dir": output_dir, "new_qa_text": "可以用现有方案"},
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    types = [event_type for event_type, _ in events]
    assert types[-1] == "done"
    done = events[-1][1]
    assert done["diff"]["added"] == []
    assert done["diff"]["removed"] == []
    assert done["suggested_slugs"] == ["delay", "dht11", "oled"]
    assert done["impacts"][0]["qa_index"] == 1
    assert done["platform"] == PLATFORM_STM32
    # 中间进度事件
    assert "impact_analyzing" in types
    assert "diff_ready" in types


def test_revise_analyze_diff_detects_changes(analyze_client):
    """建议模块集变化 → diff 反映增删（motor/pid 有 stm32 版本，可增）。"""
    client, holder, tmp_path = analyze_client
    output_dir = _generate_out(client, tmp_path)
    # 假库 motor/pid 由 make_fake_motor_pid_library 提供——这里用库内已有模块
    # 构造变化：建议集去掉 oled（保留 dht11 系）
    holder["llm"] = FakeLLM(
        impact_analysis=ImpactAnalysis(
            impacts=(QaImpact(qa_index=1, reason="不要显示屏"),),
            suggested_slugs=["delay", "dht11"],
        )
    )
    resp = client.post(
        "/api/revise/analyze",
        json={"output_dir": output_dir, "new_qa_text": "不要 OLED"},
    )
    assert resp.status_code == 200, resp.text
    events = _sse_events(resp)
    done = events[-1][1]
    assert done["diff"]["added"] == []
    assert done["diff"]["removed"] == ["oled"]
    assert done["diff"]["unchanged"] == ["delay", "dht11"]


def test_revise_analyze_missing_output_dir_400(analyze_client):
    client, _, tmp_path = analyze_client
    resp = client.post(
        "/api/revise/analyze",
        json={"output_dir": str(tmp_path / "nope"), "new_qa_text": "Q&A"},
    )
    assert resp.status_code == 400
    assert "输出目录不存在" in resp.json()["detail"]


def test_revise_analyze_missing_problem_text_errors(analyze_client):
    """无清单反推路径缺题面（历史工程）→ 同步 400（中文提示补题面）。"""
    client, holder, tmp_path = analyze_client
    # 构造一个无清单、无题面的历史工程目录
    out = tmp_path / "hist"
    out.mkdir()
    (out / "project.uvprojx").write_text("<Project/>", encoding="utf-8")
    (out / "main.c").write_text("int main(void) {}\n", encoding="utf-8")
    holder["llm"] = FakeLLM()
    resp = client.post(
        "/api/revise/analyze",
        json={"output_dir": str(out), "new_qa_text": "新答疑"},
    )
    assert resp.status_code == 400
    assert "题面" in resp.json()["detail"]
