"""推荐缓存模块（工单 llm-cost-control/02）：键 / 指纹 / 读写，与 CLI 格式兼容。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contest_generator.recommend_cache import (
    cache_key,
    cache_recommend,
    clarify_fingerprint,
    load_recommend,
    parameter_warnings,
    problem_fingerprint,
    recommend_cache_path,
    validate_recommend,
)

_PROBLEM = "赛题：做个智能小车，能巡线、能避障。"
_DONE = {"modules": [{"slug": "xunji", "reason": "巡线"}], "requirements": [], "topic_id": None}


def _cached_dict(**overrides):
    payload = {
        "topic_key": "2026C",
        "platform": "stm32",
        "problem_sha256": problem_fingerprint(_PROBLEM),
        "reference_ids": ["ref-1"],
        "clarify_sha256": clarify_fingerprint([{"question": "q?", "answer": "a"}]),
        "done": _DONE,
    }
    payload.update(overrides)
    return payload


def test_cache_key_prefers_topic_id_and_falls_back_to_problem_hash():
    """键：topic_id 优先；无 topic_id 用题面 sha256；题面变 → 键变。"""
    assert cache_key("2026C", _PROBLEM) == "2026C"
    key = cache_key(None, _PROBLEM)
    assert key == problem_fingerprint(_PROBLEM)
    assert cache_key(None, _PROBLEM + "改") != key


def test_cache_path_under_given_dir():
    path = recommend_cache_path("2026C", cache_dir=Path("/tmp/cache"))
    assert path == Path("/tmp/cache") / "recommend_2026C.json"


def test_cache_roundtrip_preserves_done_verbatim(tmp_path):
    """写 → 读：done 载荷逐字一致（下游消费零改动语义）。"""
    path = recommend_cache_path("2026C", cache_dir=tmp_path)
    cache_recommend(
        path,
        _DONE,
        topic_key="2026C",
        problem_text=_PROBLEM,
        platform="stm32",
        reference_ids=["ref-1"],
        clarify_hist=[{"question": "q?", "answer": "a"}],
    )
    loaded = load_recommend(path)
    assert loaded["done"] == _DONE
    assert loaded["topic_key"] == "2026C"
    assert loaded["platform"] == "stm32"
    assert loaded["problem_sha256"] == problem_fingerprint(_PROBLEM)
    assert loaded["reference_ids"] == ["ref-1"]


def test_load_recommend_rejects_corrupt_files(tmp_path):
    """损坏 json / 缺字段 → ValueError（不静默带假数据进下游）。"""
    path = recommend_cache_path("2026C", cache_dir=tmp_path)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        load_recommend(path)
    path.write_text(json.dumps({"topic_key": "2026C"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_recommend(path)


def test_load_recommend_accepts_cli_shape(tmp_path):
    """CLI（generate_check.py）写出的缓存形状 → 后端能读（双客户端格式兼容）。"""
    path = tmp_path / "recommend_2026C.json"
    path.write_text(json.dumps(_cached_dict()), encoding="utf-8")
    loaded = load_recommend(path)
    assert loaded["done"]["modules"][0]["slug"] == "xunji"


def test_validate_recommend_invalidates_on_problem_platform_key_change(tmp_path):
    """题面指纹 / 平台 / topic_key 任一不符 → 失效（返回原因），一致 → 通过。"""
    path = recommend_cache_path("2026C", cache_dir=tmp_path)
    path.write_text(json.dumps(_cached_dict()), encoding="utf-8")
    cached = load_recommend(path)

    ok, reason = validate_recommend(
        cached, topic_key="2026C", problem_text=_PROBLEM, platform="stm32"
    )
    assert ok and reason == ""

    _, reason = validate_recommend(
        cached, topic_key="2026C", problem_text=_PROBLEM + "变", platform="stm32"
    )
    assert "题面" in reason

    _, reason = validate_recommend(
        cached, topic_key="2026C", problem_text=_PROBLEM, platform="mspm0"
    )
    assert "平台" in reason

    _, reason = validate_recommend(
        cached, topic_key="2024H", problem_text=_PROBLEM, platform="stm32"
    )
    assert "键" in reason


def test_parameter_warnings_on_reference_and_clarify_drift():
    """reference_ids / clarify 指纹与缓存时不同 → 警告列表；一致 → 空。"""
    cached = _cached_dict()
    assert (
        parameter_warnings(
            cached,
            reference_ids=["ref-1"],
            clarify_hist=[{"question": "q?", "answer": "a"}],
        )
        == []
    )
    warns = parameter_warnings(
        cached,
        reference_ids=["ref-2"],
        clarify_hist=[{"question": "q?", "answer": "a"}],
    )
    assert any("reference_ids" in w for w in warns)

    warns = parameter_warnings(
        cached,
        reference_ids=["ref-1"],
        clarify_hist=[],
    )
    assert any("clarifications" in w for w in warns)

    # 旧格式缓存无元数据 → 跳过比对（不警告）
    legacy = _cached_dict()
    del legacy["reference_ids"]
    del legacy["clarify_sha256"]
    assert parameter_warnings(legacy, reference_ids=["ref-9"], clarify_hist=[]) == []
