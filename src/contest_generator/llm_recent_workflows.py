"""Recent completed LLM workflow snapshots for the settings dashboard.

The store is intentionally process-local and memory-only: it is a presentation layer
over the sanitized LLM observation collector, not telemetry persistence.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Mapping

from .llm import LLMObservationCollector, sanitize_llm_usage


_CALL_FIELDS = (
    "workflow_id",
    "sequence",
    "operation",
    "provider",
    "route",
    "model",
    "duration_ms",
    "attempts",
    "status",
    "final",
    "call_id",
    "budget_attempt",
    "http_status",
    "error_kind",
    "parse_status",
    "request_bytes",
)


@dataclass(frozen=True)
class LLMWorkflowSnapshot:
    """Content-safe summary plus sanitized per-call details for one completed workflow."""

    workflow_id: str
    workflow_name: str
    call_count: int
    local_calls: int
    deepseek_calls: int
    duration_ms: int
    request_bytes: int
    status: str
    usage: dict[str, int | float] | None
    calls: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "call_count": self.call_count,
            "local_calls": self.local_calls,
            "deepseek_calls": self.deepseek_calls,
            "duration_ms": self.duration_ms,
            "request_bytes": self.request_bytes,
            "status": self.status,
            "usage": self.usage,
            "calls": [dict(call) for call in self.calls],
        }


class LLMRecentWorkflowStore:
    """Bounded, thread-safe, memory-only ring buffer of completed LLM workflows."""

    def __init__(self, max_workflows: int = 20) -> None:
        if max_workflows <= 0:
            raise ValueError("max_workflows 必须 > 0")
        self._workflows: deque[LLMWorkflowSnapshot] = deque(maxlen=max_workflows)
        self._lock = threading.Lock()

    def add_completed(self, collector: LLMObservationCollector) -> None:
        snapshot = snapshot_collector(collector)
        if snapshot.call_count == 0:
            return
        with self._lock:
            self._workflows.append(snapshot)

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            workflows = list(reversed(self._workflows))
        return {"workflows": [workflow.to_dict() for workflow in workflows]}


def snapshot_collector(collector: LLMObservationCollector) -> LLMWorkflowSnapshot:
    observations = collector.observations
    calls = tuple(_safe_call(observation) for observation in observations)
    return LLMWorkflowSnapshot(
        workflow_id=collector.workflow_id,
        workflow_name=_workflow_name(collector.workflow_id),
        call_count=len(calls),
        local_calls=sum(1 for call in calls if call.get("provider") == "local"),
        deepseek_calls=sum(1 for call in calls if call.get("provider") == "deepseek"),
        duration_ms=collector.elapsed_ms,
        request_bytes=sum(_nonnegative_int(call.get("request_bytes")) for call in calls),
        status="error" if any(call.get("status") == "error" for call in calls) else "success",
        usage=_aggregate_usage(observations),
        calls=calls,
    )


def _safe_call(observation: Mapping[str, Any]) -> dict[str, Any]:
    call = {field: observation.get(field) for field in _CALL_FIELDS}
    usage = sanitize_llm_usage(_usage_mapping(observation.get("usage")))
    if usage:
        call["usage"] = usage
    return call


def _aggregate_usage(observations: tuple[dict[str, Any], ...]) -> dict[str, int | float] | None:
    totals: dict[str, int | float] = {}
    for observation in observations:
        usage = sanitize_llm_usage(_usage_mapping(observation.get("usage"))) or {}
        for key, value in usage.items():
            totals[key] = totals.get(key, 0) + value
    return totals or None


def _usage_mapping(usage: object) -> Mapping[str, Any] | None:
    return usage if isinstance(usage, Mapping) else None


def _workflow_name(workflow_id: str) -> str:
    return workflow_id.split(":", 1)[0]


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and value > 0 else 0
