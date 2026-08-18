"""Recent LLM workflow dashboard：内存 ring buffer 与 content-safe 快照。"""

from __future__ import annotations

import json

from contest_generator.llm import create_llm_observation_collector
from contest_generator.llm_pricing import LLMPriceTable
from contest_generator.llm_recent_workflows import (
    LLMRecentWorkflowStore,
    attach_cost_estimates,
    estimate_workflow_cost,
)


def _collector(workflow_name: str, *, workflow_id: str | None = None):
    collector = create_llm_observation_collector(workflow_name)
    if workflow_id is not None:
        collector.workflow_id = workflow_id
    return collector


def _record(
    collector,
    *,
    operation: str = "select_modules",
    provider: str = "deepseek",
    route: str = "remote",
    status: str = "success",
    error_kind: str | None = None,
    parse_status: str = "success",
    request_bytes: int = 100,
    usage: dict | None = None,
):
    collector.collect(
        operation=operation,
        provider=provider,
        route=route,
        model="secret-model-name",
        duration_ms=12,
        attempts=1,
        status=status,
        final=True,
        call_id=1,
        budget_attempt=1,
        http_status=200,
        error_kind=error_kind,
        parse_status=parse_status,
        request_bytes=request_bytes,
        usage=usage,
    )


def test_recent_workflow_store_truncates_to_bounded_ring_buffer():
    store = LLMRecentWorkflowStore(max_workflows=2)

    for index in range(3):
        collector = _collector("recommend", workflow_id=f"recommend:{index}")
        _record(collector, request_bytes=100 + index)
        store.add_completed(collector)

    recent = store.to_dict()["workflows"]
    assert [item["workflow_id"] for item in recent] == ["recommend:2", "recommend:1"]
    assert [item["request_bytes"] for item in recent] == [102, 101]


def test_recent_workflow_store_returns_content_safe_summary_and_call_details():
    store = LLMRecentWorkflowStore(max_workflows=10)
    collector = _collector("fix-errors", workflow_id="fix-errors:abc")
    _record(
        collector,
        operation="fix_compile_errors",
        provider="deepseek",
        route="remote",
        usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "unsafe": "secret-usage"},
    )
    _record(
        collector,
        operation="summarize_topic",
        provider="local",
        route="local",
        status="error",
        error_kind="network",
        parse_status="parse_error",
        request_bytes=25,
    )

    store.add_completed(collector)

    payload = store.to_dict()
    workflow = payload["workflows"][0]
    assert workflow == {
        "workflow_id": "fix-errors:abc",
        "workflow_name": "fix-errors",
        "call_count": 2,
        "local_calls": 1,
        "deepseek_calls": 1,
        "duration_ms": workflow["duration_ms"],
        "request_bytes": 125,
        "status": "error",
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        "calls": workflow["calls"],
    }
    assert workflow["duration_ms"] >= 0
    assert workflow["calls"] == [
        {
            "workflow_id": "fix-errors:abc",
            "sequence": 1,
            "operation": "fix_compile_errors",
            "provider": "deepseek",
            "route": "remote",
            "model": "secret-model-name",
            "duration_ms": 12,
            "attempts": 1,
            "status": "success",
            "final": True,
            "call_id": 1,
            "budget_attempt": 1,
            "http_status": 200,
            "error_kind": None,
            "parse_status": "success",
            "request_bytes": 100,
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        },
        {
            "workflow_id": "fix-errors:abc",
            "sequence": 2,
            "operation": "summarize_topic",
            "provider": "local",
            "route": "local",
            "model": "secret-model-name",
            "duration_ms": 12,
            "attempts": 1,
            "status": "error",
            "final": True,
            "call_id": 1,
            "budget_attempt": 1,
            "http_status": 200,
            "error_kind": "network",
            "parse_status": "parse_error",
            "request_bytes": 25,
        },
    ]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "secret-usage" not in serialized
    assert "secret-prompt-content" not in serialized
    assert "secret-response-content" not in serialized
    assert "api_key" not in serialized.lower()


_TABLES = {
    "deepseek": LLMPriceTable("deepseek", 2.0, 8.0),
    "local": LLMPriceTable("local", 0.0, 0.0),
}


def _workflow_with_calls(calls):
    return {"workflow_id": "fix-errors:abc", "calls": tuple(calls)}


def test_estimate_workflow_cost_splits_by_provider():
    """实际花费按 provider 单价、对照全按 DeepSeek、节省 = 差值。"""
    workflow = _workflow_with_calls(
        (
            {"provider": "deepseek", "usage": {"prompt_tokens": 500_000, "completion_tokens": 100_000}},
            {"provider": "local", "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 200_000}},
        )
    )
    est = estimate_workflow_cost(workflow, _TABLES)
    # 实际 = deepseek 1.8 + local 0 = 1.8；对照 = 1.8 + (2 + 1.6) = 5.4；节省 = 3.6
    assert est["est_cost_actual"] == 1.8
    assert est["est_cost_deepseek"] == 5.4
    assert est["est_savings"] == 3.6


def test_estimate_workflow_cost_handles_missing_usage_and_unknown_provider():
    """无 usage 的调用贡献 0；provider 不在表内实际按 0 计，对照仍按 DeepSeek 价。"""
    workflow = _workflow_with_calls(
        (
            {"provider": "deepseek"},
            {"provider": "mystery", "usage": {"prompt_tokens": 1000}},
            {"usage": {"completion_tokens": 1000}},
        )
    )
    est = estimate_workflow_cost(workflow, _TABLES)
    assert est["est_cost_actual"] == 0.0
    # 对照按 DeepSeek 价：mystery 1000 prompt(0.002) + 无 provider 1000 completion(0.008)
    assert est["est_cost_deepseek"] == 0.01
    assert est["est_savings"] == 0.01


def test_attach_cost_estimates_injects_est_field():
    """recent 载荷逐工作流注入 est 字段，原字段保留。"""
    payload = {
        "workflows": [
            {"workflow_id": "a:1", "calls": [{"provider": "local", "usage": {"prompt_tokens": 10}}]},
            {"workflow_id": "b:2", "calls": []},
        ]
    }
    enriched = attach_cost_estimates(payload, _TABLES)
    assert len(enriched["workflows"]) == 2
    assert enriched["workflows"][0]["workflow_id"] == "a:1"
    assert "est" in enriched["workflows"][0]
    assert enriched["workflows"][0]["est"]["est_savings"] == 0.0
    assert "est" in enriched["workflows"][1]
    assert enriched["workflows"][1]["est"]["est_cost_actual"] == 0.0
    # 原载荷不被污染
    assert "est" not in payload["workflows"][0]
