"""Recent LLM workflow dashboard：内存 ring buffer 与 content-safe 快照。"""

from __future__ import annotations

import json

from contest_generator.llm import create_llm_observation_collector
from contest_generator.llm_recent_workflows import LLMRecentWorkflowStore


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
