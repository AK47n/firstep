"""推荐请求契约双客户端对偶（工单 03）：CLI 与前端 /api/recommend 契约一致。

契约字段（服务端校验唯一出处 = webapp.py:575-582 的 _require_*；前端恒发 =
index.html:916；CLI 侧由本测试强制，新增契约字段时须同步三处 + 本文件常量）：
    problem_text  必填
    topic_id      可选，topic 模式才带（topic_file = no-topic 手动准入）
    reference_ids 可选 list[str]，缺省空 = 现状兼容；锚定命中 ∪ 手动选，
                  幻觉 / 重复 id 服务端 400 大声失败
    platform      恒发，空 = 不过滤
    clarifications 可选，非空才带（[{question, answer}]）

对偶性：改词表忘改 CLI → 事件词表断言红（events.py 是唯一出处）；CLI 侧加 /
删契约字段 → 字段断言红。测试从 .scratch/real-run/generate_check.py 经
importlib 加载模块（该目录在 gitignore 内但被 force-tracked，tests/ 无其他
测试 import 它）。
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
from pathlib import Path

import pytest

from contest_generator import events

# 契约五字段清单（新增字段时同步 webapp.py:575-582 + index.html:916 +
# build_recommend_payload 本文件常量三处；此处红 = 三客户端漂移）
CONTRACT_FIELDS = frozenset(
    {"problem_text", "topic_id", "reference_ids", "platform", "clarifications"}
)
# 缺省输入 = 现状两键（向后兼容语义不变）
DEFAULT_FIELDS = frozenset({"problem_text", "platform"})

REPO_ROOT = Path(__file__).resolve().parents[1]
GEN_CHECK = REPO_ROOT / ".scratch" / "real-run" / "generate_check.py"


def _load_generate_check():
    spec = importlib.util.spec_from_file_location("generate_check", GEN_CHECK)
    assert spec is not None and spec.loader is not None, f"加载失败: {GEN_CHECK}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load_generate_check()


# ---------- payload 字段对偶 ----------

def test_build_recommend_payload_full_input_has_exactly_five_fields() -> None:
    """全输入（topic_id + clarify_hist + reference_ids 都传）= 恰五字段。

    前端恒发五字段、CLI 条件发——对偶的强制点是键集合一致（新增契约字段时
    此处红，注释见文件头 / webapp.py:575-582）。
    """
    payload = gen.build_recommend_payload(
        "题面全文",
        topic_id="2026H",
        clarify_hist=[{"question": "问?", "answer": "答"}],
        reference_ids=("r1", "r2"),
    )
    assert set(payload) == CONTRACT_FIELDS
    assert payload["problem_text"] == "题面全文"
    assert payload["topic_id"] == "2026H"
    assert payload["reference_ids"] == ["r1", "r2"]
    assert payload["clarifications"] == [{"question": "问?", "answer": "答"}]
    assert payload["platform"] == gen.PLATFORM


def test_build_recommend_payload_default_keeps_two_field_legacy() -> None:
    """缺省输入 = 现状两键（problem_text + platform），向后兼容语义不变。"""
    payload = gen.build_recommend_payload("题面全文")
    assert set(payload) == DEFAULT_FIELDS


def test_build_recommend_payload_omits_empty_optionals() -> None:
    """topic_id / clarifications / reference_ids 为空时都不进 payload（现状语义）。"""
    payload = gen.build_recommend_payload("题面全文", platform="mspm0")
    assert set(payload) == DEFAULT_FIELDS
    assert payload["platform"] == "mspm0"


# ---------- check_topic 透传对偶（删 reference_ids 透传即红） ----------

@pytest.fixture
def captured_recommend_payload(monkeypatch, tmp_path) -> dict:
    """check_topic 走到推荐请求：题库 tmp 化 + recommend_stream 截获 payload。

    done 且 modules 空 → check_topic 在骨架前返回，不落盘不编译；payload 已
    截获，足以断言请求体字段。
    """
    topics = tmp_path / "topics"
    (topics / "T1").mkdir(parents=True)
    (topics / "T1" / "topic.md").write_text("题面全文", encoding="utf-8")
    monkeypatch.setattr(gen, "TOPICS", topics)
    captured: dict[str, dict] = {}

    def fake_stream(payload: dict) -> dict:
        captured["payload"] = payload
        return {"event": "done", "data": {"modules": []}, "rounds": 0}

    monkeypatch.setattr(gen, "recommend_stream", fake_stream)
    return captured


def test_check_topic_full_input_payload_has_exactly_five_fields(
    captured_recommend_payload,
) -> None:
    """topic 模式 + clarify_map + reference_ids 全给 → 请求体恰五字段。"""
    gen.check_topic(
        "T1",
        clarify_map={"问?": "答"},
        reference_ids=("r1", "r2"),
    )
    payload = captured_recommend_payload["payload"]
    assert set(payload) == CONTRACT_FIELDS
    assert payload["topic_id"] == "T1"
    assert payload["reference_ids"] == ["r1", "r2"]
    assert payload["clarifications"] == [{"question": "问?", "answer": "答"}]


def test_check_topic_default_payload_keeps_two_field_legacy(
    captured_recommend_payload, tmp_path
) -> None:
    """topic_file 模式（no-topic）无 reference_ids / clarify_map → 请求体仍是
    现状两键（兼容语义；topic 模式恒带 topic_id 是既有语义，另测）。"""
    topic_file = tmp_path / "ext_topic.md"
    topic_file.write_text("题面全文", encoding="utf-8")
    gen.check_topic("T1", topic_file=topic_file)
    assert set(captured_recommend_payload["payload"]) == DEFAULT_FIELDS


def test_cli_reference_ids_flag_reaches_check_topic(monkeypatch) -> None:
    """--reference-ids 逗号解析 → check_topic 透传（删解析即红）。"""
    captured: dict[str, object] = {}

    def fake_check_topic(
        key, clarify_map, drop, platform, topic_file, add, reference_ids
    ):
        captured["key"] = key
        captured["reference_ids"] = reference_ids
        return True

    monkeypatch.setattr(gen, "check_topic", fake_check_topic)
    monkeypatch.setattr(
        sys, "argv",
        ["generate_check.py", "2026C", "--reference-ids", "r1, r2 ,r3"],
    )
    with pytest.raises(SystemExit) as ei:
        gen.main()
    assert ei.value.code == 0
    assert captured["key"] == "2026C"
    assert captured["reference_ids"] == ("r1", "r2", "r3")


def test_cli_reference_ids_flag_absent_passes_empty(monkeypatch) -> None:
    """不带 --reference-ids → 透传空元组（缺省 = 现状兼容）。"""
    captured: dict[str, object] = {}

    def fake_check_topic(
        key, clarify_map, drop, platform, topic_file, add, reference_ids
    ):
        captured["reference_ids"] = reference_ids
        return True

    monkeypatch.setattr(gen, "check_topic", fake_check_topic)
    monkeypatch.setattr(sys, "argv", ["generate_check.py", "2026C"])
    with pytest.raises(SystemExit):
        gen.main()
    assert captured["reference_ids"] == ()


# ---------- 事件词表对偶 ----------

def _cli_handled_event_names() -> set[str]:
    """AST 抽取 recommend_stream 事件分支比较的 event 字符串字面量。

    不写死词表（写死 = 测试镜像自身）：从 CLI 源码结构抽取，与 events.py
    常量比对——改词表忘改 CLI、或改 CLI 忘改词表，任一侧都红。
    """
    tree = ast.parse(inspect.getsource(gen.recommend_stream))
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    names: set[str] = set()
    for node in ast.walk(func):
        if not (
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id == "event"
        ):
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], (ast.Eq, ast.In)):
            continue
        comparator = node.comparators[0]
        targets = comparator.elts if isinstance(comparator, ast.Tuple) else (comparator,)
        for t in targets:
            if isinstance(t, ast.Constant) and isinstance(t.value, str):
                names.add(t.value)
    return names


def test_cli_event_wordtable_matches_events_py() -> None:
    """CLI 处理的 event 名集合 == events.py 词表（唯一出处，改词表忘改 CLI 即红）。"""
    expected = {
        events.EVENT_ROUND,
        events.EVENT_CONVERGED,
        events.EVENT_DONE,
        events.EVENT_QUESTION,
        events.EVENT_ERROR,
    }
    assert _cli_handled_event_names() == expected
