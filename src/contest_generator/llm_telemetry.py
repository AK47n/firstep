"""LLM collector snapshots → content-safe SSE telemetry events.

This adapter keeps live-progress mechanics out of llm.py and web routes: llm.py owns
sanitized observations, events.py owns the SSE event shape, and this module translates
one collector snapshot into the live telemetry event used by SSE flows.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator, Mapping

from .events import EVENT_LLM_TELEMETRY, ProgressEvent
from .llm import LLMObservationCollector, sanitize_llm_usage


_LLM_CALL_FIELDS = (
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


@contextmanager
def bind_llm_telemetry(
    collector: LLMObservationCollector,
    emit: Callable[[ProgressEvent], None],
) -> Iterator[None]:
    """Emit telemetry whenever the collector records a new observation."""
    previous = collector.on_record
    collector.on_record = lambda: emit_llm_telemetry(emit, collector)
    try:
        yield
    finally:
        collector.on_record = previous


def llm_telemetry_event(collector: LLMObservationCollector) -> ProgressEvent | None:
    """Build one content-safe telemetry ProgressEvent from the collector snapshot."""
    observations = collector.observations
    if not observations:
        return None
    latest = observations[-1]
    sent_observations = tuple(
        item for item in observations if item.get("parse_status") != "not_sent"
    )
    calls = tuple(_safe_call(item) for item in observations)
    return ProgressEvent(
        type=EVENT_LLM_TELEMETRY,
        llm_workflow_id=collector.workflow_id,
        llm_total_calls=len(sent_observations),
        llm_local_calls=sum(1 for item in sent_observations if item.get("provider") == "local"),
        llm_deepseek_calls=sum(
            1 for item in sent_observations if item.get("provider") == "deepseek"
        ),
        llm_latest_operation=str(latest.get("operation") or ""),
        llm_error_kind=str(latest.get("error_kind") or ""),
        llm_parse_status=str(latest.get("parse_status") or ""),
        llm_latest_http_status=_nonnegative_int(latest.get("http_status")),
        llm_attempts=len(observations),
        llm_retry_calls=sum(
            1 for item in observations if _nonnegative_int(item.get("attempts")) > 1
        ),
        llm_error_calls=sum(1 for item in observations if item.get("status") == "error"),
        llm_parse_error_calls=sum(
            1 for item in observations if item.get("parse_status") == "parse_error"
        ),
        llm_rate_limit_calls=sum(
            1 for item in observations if item.get("error_kind") == "rate_limit"
        ),
        llm_network_error_calls=sum(
            1 for item in observations if item.get("error_kind") == "network"
        ),
        llm_5xx_calls=sum(1 for item in observations if _is_5xx(item.get("http_status"))),
        llm_budget_blocked_calls=sum(
            1 for item in observations if item.get("error_kind") == "budget"
        ),
        llm_request_bytes=sum(
            _nonnegative_int(item.get("request_bytes")) for item in observations
        ),
        llm_duration_ms=collector.elapsed_ms,
        llm_usage=_aggregate_usage(observations),
        llm_calls=calls,
    )


def emit_llm_telemetry(
    emit: Callable[[ProgressEvent], None], collector: LLMObservationCollector
) -> None:
    """Best-effort telemetry emit; failures never affect the owning workflow."""
    try:
        event = llm_telemetry_event(collector)
        if event is not None:
            emit(event)
    except Exception:
        pass


def _safe_call(observation: Mapping[str, Any]) -> dict[str, Any]:
    call = {field: observation.get(field) for field in _LLM_CALL_FIELDS}
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


def _is_5xx(value: object) -> bool:
    return isinstance(value, int) and value >= 500


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and value > 0 else 0
