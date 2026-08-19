"""推荐缓存模块（工单 llm-cost-control/02）：键 / 指纹 / 读写，与 CLI 格式兼容。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contest_generator.recommend_cache import (
    cache_key,
    cache_recommend,
    clarify_fingerprint,
    library_fingerprint,
    load_recommend,
    parameter_warnings,
    problem_fingerprint,
    qa_fingerprint,
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


def test_qa_fingerprint_invalidates_cache_on_change():
    """赛题答疑 Q&A 指纹（工单 qa-material/01）：Q&A 变化 → 缓存失效（阻断级，
    走真实推荐）；空文本指纹 = 空串（旧缓存无字段兼容 = 匹配）。"""
    # 写缓存带 Q&A → 同 Q&A 命中；不同 Q&A 失效
    cached = _cached_dict(qa_sha256=qa_fingerprint("问：尺寸？答：30cm。"))
    ok, _ = validate_recommend(
        cached, topic_key="2026C", problem_text=_PROBLEM, platform="stm32",
        qa_text="问：尺寸？答：30cm。",
    )
    assert ok
    ok, reason = validate_recommend(
        cached, topic_key="2026C", problem_text=_PROBLEM, platform="stm32",
        qa_text="问：尺寸？答：35cm。",
    )
    assert not ok
    assert "Q&A" in reason
    # 旧缓存无 qa_sha256 字段：请求空 Q&A = 匹配；请求带 Q&A = 失效（材料变了
    # 旧结果不含材料，必须重推）
    legacy = _cached_dict()
    assert "qa_sha256" not in legacy
    ok, _ = validate_recommend(
        legacy, topic_key="2026C", problem_text=_PROBLEM, platform="stm32"
    )
    assert ok
    ok, _ = validate_recommend(
        legacy, topic_key="2026C", problem_text=_PROBLEM, platform="stm32",
        qa_text="问：尺寸？答：30cm。",
    )
    assert not ok


# ---------------------------------------------------------------------------
# 模块库指纹（工单 recommend-cache-fingerprint/01）：库变缓存失效——
# 指纹 = ManifestSummary 摘要行（to_line）排序 hash，模型看到什么指纹什么
# ---------------------------------------------------------------------------


def _summary(slug: str, description: str, *, multi: bool = False):
    from contest_generator.manifest import ManifestSummary, MultiInstanceSpec

    return ManifestSummary(
        slug=slug,
        description=description,
        kits=(),
        dependencies=(),
        multi_instance=MultiInstanceSpec(max=8, variant="color") if multi else None,
    )


def test_library_fingerprint_sensitive_to_content_and_order_independent():
    """指纹对摘要内容敏感（description / 增删模块 / 多实例标注），顺序无关。"""
    a = _summary("led", "LED 指示灯驱动")
    b = _summary("oled", "OLED 显示驱动")
    assert library_fingerprint([a, b]) == library_fingerprint([b, a])  # 顺序无关
    assert library_fingerprint([a, b]) != library_fingerprint([a])  # 删模块 → 变
    assert library_fingerprint([a, b]) != library_fingerprint(
        [_summary("led", "LED 指示灯驱动（改版）"), b]
    )  # 改简介 → 变
    assert library_fingerprint([a, b]) != library_fingerprint(
        [_summary("led", "LED 指示灯驱动", multi=True), b]
    )  # 多实例标注 → 变
    # 空库 = 稳定指纹（不抛）
    assert library_fingerprint([]) == library_fingerprint([])


def test_validate_recommend_library_fingerprint_gates_cache():
    """库指纹校验：匹配 = 命中；不匹配 = 失效；旧缓存无字段 = 保守失效；
    传入空（兼容调用方）= 跳过。"""
    fp = library_fingerprint([_summary("led", "LED 指示灯驱动")])
    cached = _cached_dict(library_sha256=fp)

    ok, _ = validate_recommend(
        cached, topic_key="2026C", problem_text=_PROBLEM, platform="stm32",
        library_fingerprint=fp,
    )
    assert ok

    ok, reason = validate_recommend(
        cached, topic_key="2026C", problem_text=_PROBLEM, platform="stm32",
        library_fingerprint=library_fingerprint([_summary("led", "LED 改版")]),
    )
    assert not ok
    assert "模块库" in reason

    # 旧缓存无 library_sha256：无法证明匹配当前库 → 保守失效（宁可重推，
    # 用错结果成本 > 重推成本——与 Q&A 先例不同，库永远存在）
    legacy = _cached_dict()
    assert "library_sha256" not in legacy
    ok, reason = validate_recommend(
        legacy, topic_key="2026C", problem_text=_PROBLEM, platform="stm32",
        library_fingerprint=fp,
    )
    assert not ok
    assert "模块库" in reason

    # 调用方不传指纹（兼容既有调用）→ 跳过校验
    ok, _ = validate_recommend(
        legacy, topic_key="2026C", problem_text=_PROBLEM, platform="stm32"
    )
    assert ok


def test_cache_recommend_stores_library_fingerprint(tmp_path):
    """写缓存落 library_sha256 字段（读回校验用）。"""
    from contest_generator.manifest import ManifestSummary

    path = tmp_path / "recommend_2026C.json"
    fp = library_fingerprint([ManifestSummary("led", "LED 指示灯驱动")])
    cache_recommend(
        path,
        _DONE,
        topic_key="2026C",
        problem_text=_PROBLEM,
        platform="stm32",
        library_fingerprint=fp,
    )

    payload = load_recommend(path)
    assert payload["library_sha256"] == fp


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
