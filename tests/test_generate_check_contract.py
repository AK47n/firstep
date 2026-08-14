"""推荐请求契约双客户端对偶（工单 03）：CLI 与前端 /api/recommend 契约一致。

契约字段（服务端校验唯一出处 = webapp.py:575-582 的 _require_*；前端恒发 =
index.html:916；CLI 侧由本测试强制，新增契约字段时须同步三处 + 本文件常量）：
    problem_text  必填
    topic_id      可选，topic 模式才带（topic_file = no-topic 手动准入）
    reference_ids 可选 list[str]，缺省空 = 现状兼容；锚定命中 ∪ 手动选，
                  幻觉 / 重复 id 服务端 400 大声失败
    platform      恒发，空 = 不过滤
    clarifications 可选，非空才带（[{question, answer}]）

/api/fix-errors（工单 gen-check-fix-loop/01，服务端校验唯一出处 =
webapp.py:713 fix_errors 路由；前端恒发 = index.html:1712）：
    error_text    必填（编译报错全文）
    output_dir    必填（生成结果目录）
    problem_text / platform / slugs / main_c 可选上下文，check_topic 内
                  恒有、恒发，缺省不放；previous_fixes 可选（上一轮 done
                  的 fixes 数组，非空才发——第 2 轮起回喂，对齐前端
                  index.html:1724 previousDone.fixes；服务端可选向后
                  兼容，缺省不带）

对偶性：改词表忘改 CLI → 事件词表断言红（events.py 是唯一出处）；CLI 侧加 /
删契约字段 → 字段断言红。测试从 .scratch/real-run/generate_check.py 经
importlib 加载模块（该目录在 gitignore 内但被 force-tracked，tests/ 无其他
测试 import 它）。
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import re
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

# /api/fix-errors 契约六字段清单（新增字段时同步 webapp.py:713 路由校验 +
# index.html:1712 + build_fix_payload 本文件常量三处；此处红 = 三客户端漂移）
FIX_CONTRACT_FIELDS = frozenset(
    {"output_dir", "error_text", "problem_text", "platform", "slugs", "main_c"}
)
# previous_fixes 可选第七字段（上一轮 done 的 fixes，非空才发，工单
# cli-fix-loop-parity/01）：带 = 恰七字段，不带 = 六字段语义不变
FIX_FIELDS_WITH_PREVIOUS = FIX_CONTRACT_FIELDS | {"previous_fixes"}
# 缺省输入 = 必填两键（可选上下文缺省不放）
FIX_DEFAULT_FIELDS = frozenset({"output_dir", "error_text"})

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


def test_build_fix_payload_full_input_has_exactly_six_fields() -> None:
    """全输入（problem_text + platform + slugs + main_c 都传）= 恰六字段。

    前端恒发六字段、CLI 条件发——对偶的强制点是键集合一致（新增契约字段时
    此处红，注释见文件头 / webapp.py:713）。
    """
    payload = gen.build_fix_payload(
        "out_2026C_stm32",
        "main.c(12): error #20: identifier undefined",
        problem_text="题面全文",
        platform="stm32",
        slugs=["led_beep", "gpio"],
        main_c="int main(void) { return 0; }",
    )
    assert set(payload) == FIX_CONTRACT_FIELDS
    assert payload["output_dir"] == "out_2026C_stm32"
    assert payload["error_text"] == "main.c(12): error #20: identifier undefined"
    assert payload["problem_text"] == "题面全文"
    assert payload["platform"] == "stm32"
    assert payload["slugs"] == ["led_beep", "gpio"]
    assert payload["main_c"] == "int main(void) { return 0; }"


def test_build_fix_payload_default_keeps_two_required_fields() -> None:
    """缺省输入 = 必填两键（output_dir + error_text），可选上下文缺省不放。"""
    payload = gen.build_fix_payload("out_x", "err")
    assert set(payload) == FIX_DEFAULT_FIELDS


def test_build_fix_payload_omits_empty_optionals() -> None:
    """可选上下文为空串 / 空列表时都不进 payload（缺省不放语义；
    previous_fixes 空同样不带，与前端 previousDone.fixes 真值判定一致）。"""
    payload = gen.build_fix_payload(
        "out_x", "err", problem_text="", platform="", slugs=(), main_c="",
        previous_fixes=(),
    )
    assert set(payload) == FIX_DEFAULT_FIELDS


# ---------- previous_fixes 回喂 + 超时停（工单 cli-fix-loop-parity/01） ----------
#
# previous_fixes 是 fix-loop-progress/01 协议一等元素（FIX_SYSTEM_PROMPT 约束 6
# 靠它抑制「重复输出与上一轮一模一样的建议」）：CLI 第 2 轮起把上一轮 done 的
# fixes 回喂，对齐前端 previousDone.fixes；重编译超时 = 终端状态（对齐前端
# index.html 超时停），半截输出不进下一轮 error_text——超时不停进下一轮 =
# 白烧一次 LLM 调用 + 误报轮上限文案。


def test_build_fix_payload_with_previous_fixes_has_exactly_seven_fields() -> None:
    """带 previous_fixes = 恰七字段（不带 = 六字段语义不变，另测）。"""
    payload = gen.build_fix_payload(
        "out_2026C_stm32",
        "main.c(12): error #20: identifier undefined",
        problem_text="题面全文",
        platform="stm32",
        slugs=["led_beep", "gpio"],
        main_c="int main(void) { return 0; }",
        previous_fixes=[
            {"file": "main.c", "line": 12, "status": "applied", "reason": "修"}
        ],
    )
    assert set(payload) == FIX_FIELDS_WITH_PREVIOUS
    assert payload["previous_fixes"] == [
        {"file": "main.c", "line": 12, "status": "applied", "reason": "修"}
    ]


def test_run_fix_loop_round2_payload_includes_previous_fixes(monkeypatch) -> None:
    """第 2 轮请求体带上一轮 done 的 fixes（对齐前端 previousDone.fixes 回喂）；
    第 1 轮不带（无上一轮）。"""
    calls: list[dict] = []
    fix = {"file": "main.c", "line": 12, "status": "applied", "reason": "修"}

    def fake_fix(payload: dict) -> dict:
        calls.append(payload)
        return {"event": "done", "data": {"fixes": [fix]}}

    builds = 0

    def fake_build(out_dir):
        nonlocal builds
        builds += 1
        if builds == 1:
            return False, "仍有错误", "main.c(13): error #20: undefined", False
        return True, "0 错 0 警", "", False

    monkeypatch.setattr(gen, "fix_stream", fake_fix)
    monkeypatch.setattr(gen, "uv4_build", fake_build)
    assert gen.run_fix_loop(
        Path("out_x"), "main.c(12): error #20: undefined", "题面", "stm32",
        ["led_beep"], "int main(void) { return 0; }",
    ) is True
    assert len(calls) == 2
    assert "previous_fixes" not in calls[0]
    assert calls[1]["previous_fixes"] == [fix]


def test_run_fix_loop_rebuild_timeout_stops_without_next_llm_call(
    monkeypatch, capsys
) -> None:
    """重编译超时（合成 timed_out 的 CompileRun）= 终端状态：循环即停 + 文案
    对齐前端「重编译超时，已停止循环」+ 半截输出不进下一轮 error_text（不白烧
    第 2 次 LLM 调用——旧形态会把半截输出喂下一轮）。"""
    calls: list[dict] = []

    def fake_fix(payload: dict) -> dict:
        calls.append(payload)
        return {"event": "done", "data": {"fixes": [
            {"file": "main.c", "line": 12, "status": "applied", "reason": "修"}
        ]}}

    def fake_build(out_dir):
        # exit=None + timed_out=True 的合成 CompileRun（半截输出在摘要内）
        return False, "UV4 exit=None（编译超时）", "半截输出", True

    monkeypatch.setattr(gen, "fix_stream", fake_fix)
    monkeypatch.setattr(gen, "uv4_build", fake_build)
    assert gen.run_fix_loop(
        Path("out_x"), "main.c(12): error #20: undefined", "题面", "stm32",
        ["led_beep"], "int main(void) { return 0; }",
    ) is False
    out = capsys.readouterr().out
    assert "重编译超时，已停止循环" in out
    assert len(calls) == 1


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
    # 推荐缓存目录 tmp 隔离（check_topic 真实推荐路径会写缓存，不污染真
    # 实 .scratch/real-run/cache/——工单 check-recommend-cache/01）
    monkeypatch.setenv("GENERATE_CHECK_CACHE_DIR", str(tmp_path / "cache"))
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
        key, clarify_map, drop, platform, topic_file, add, reference_ids,
        reuse_recommend,
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
        key, clarify_map, drop, platform, topic_file, add, reference_ids,
        reuse_recommend,
    ):
        captured["reference_ids"] = reference_ids
        captured["reuse_recommend"] = reuse_recommend
        return True

    monkeypatch.setattr(gen, "check_topic", fake_check_topic)
    monkeypatch.setattr(sys, "argv", ["generate_check.py", "2026C"])
    with pytest.raises(SystemExit):
        gen.main()
    assert captured["reference_ids"] == ()
    assert captured["reuse_recommend"] is False


def test_cli_reuse_recommend_flag_reaches_check_topic(monkeypatch) -> None:
    """--reuse-recommend 布尔 flag 解析 → check_topic 透传 True（删解析即红，
    工单 check-recommend-cache/01）。"""
    captured: dict[str, object] = {}

    def fake_check_topic(
        key, clarify_map, drop, platform, topic_file, add, reference_ids,
        reuse_recommend,
    ):
        captured["reuse_recommend"] = reuse_recommend
        return True

    monkeypatch.setattr(gen, "check_topic", fake_check_topic)
    monkeypatch.setattr(
        sys, "argv", ["generate_check.py", "2026C", "--reuse-recommend"]
    )
    with pytest.raises(SystemExit) as ei:
        gen.main()
    assert ei.value.code == 0
    assert captured["reuse_recommend"] is True


# ---------- 事件词表对偶 ----------

def _cli_handled_event_names(fn) -> set[str]:
    """AST 抽取 SSE 消费函数事件分支比较的 event 字符串字面量。

    不写死词表（写死 = 测试镜像自身）：从 CLI 源码结构抽取，与 events.py
    常量比对——改词表忘改 CLI、或改 CLI 忘改词表，任一侧都红。
    """
    tree = ast.parse(inspect.getsource(fn))
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
    assert _cli_handled_event_names(gen.recommend_stream) == expected


def test_cli_fix_event_wordtable_matches_events_py() -> None:
    """CLI 修复分支处理的 event 名集合 == events.py 修复词表（recommend 同款
    机制，工单 gen-check-fix-loop/01——改词表忘改 fix_stream 即红）。"""
    expected = {
        events.EVENT_PARSE_DONE,
        events.EVENT_FIX_START,
        events.EVENT_APPLY_RESULT,
        events.EVENT_DONE,
        events.EVENT_ERROR,
    }
    assert _cli_handled_event_names(gen.fix_stream) == expected


# ---------- 修复循环轮数上限钉（工单 gen-check-fix-loop/01 决策 1） ----------


def test_cli_fix_max_rounds_matches_frontend() -> None:
    """CLI FIX_MAX_ROUNDS == 前端 index.html FIX_MAX_ROUNDS（改动须两处同步）。"""
    html = _index_html()
    m = re.search(r"const FIX_MAX_ROUNDS = (\d+);", html)
    assert m is not None, "index.html 找不到 const FIX_MAX_ROUNDS"
    assert gen.FIX_MAX_ROUNDS == int(m.group(1))


# ---------- 修复循环继续按钮钉（工单 fix-loop-continue/01） ----------
#
# 轮上限终态保存续跑态（errorText / lastSummary / lastFixDone 快照）并亮
# 「继续修复」按钮——再来一批 ≤3 轮、不重跑初始编译、previous_fixes 回喂不丢。
# 结构钉防回退：按钮 id / 终态文案 / resume 快照三者缺一即红。CLI 非交互无对偶。


def _index_html() -> str:
    return (
        REPO_ROOT / "src" / "contest_generator" / "static" / "index.html"
    ).read_text(encoding="utf-8")


def test_index_html_has_fix_continue_button() -> None:
    """结构钉：index.html 有「继续修复」按钮（hidden 起，仅轮上限终态显示）——
    删按钮即红（工单 fix-loop-continue/01）。"""
    assert re.search(
        r'<button id="btn-fix-continue" class="hidden">', _index_html()
    ), "index.html 找不到 id=btn-fix-continue 的继续修复按钮"


def test_index_html_round_cap_text_mentions_fix_continue() -> None:
    """结构钉：轮上限终态文案含「继续修复」指引——改回旧文案（只能贴文本 /
    改工程）即红（工单 fix-loop-continue/01）。"""
    assert "可点「继续修复」再来" in _index_html(), (
        "index.html 轮上限终态文案未指引「继续修复」按钮"
    )


def test_index_html_has_fix_continue_resume_snapshot() -> None:
    """结构钉：轮上限终态把 errorText / lastSummary / lastFixDone 存入
    fixLoop.resume 续跑态（继续按钮消费，回喂上下文不丢）——删快照即红
    （工单 fix-loop-continue/01）。"""
    assert re.search(
        r"fixLoop\.resume\s*=\s*\{\s*errorText,\s*lastSummary,\s*lastFixDone\s*\}",
        _index_html(),
    ), "index.html 找不到 fixLoop.resume 续跑态快照"


# ---------- 修复循环告警收敛钉（工单 fix-loop-warnings/01） ----------
#
# 0 错 N 警即停违背「0 错 0 警」验收标准：停条件 passed → passed && warnings
# == 0（前端两处 + CLI 两处）、摘要行补警数、首编有警进修复循环。以下结构钉
# 防回退——警告计数判读单源 summarize_compile_output（禁止另写正则）。


def _warnings_field_refs(node: ast.AST) -> bool:
    """AST 判读：节点子树内引用 summary 的 warnings 字段（dict 下标
    ["warnings"] 形态——summary 是 summarize_compile_output 返回的 dict）。"""
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Subscript)
            and isinstance(sub.slice, ast.Constant)
            and sub.slice.value == "warnings"
        ):
            return True
    return False


def test_run_fix_loop_stop_condition_requires_zero_warnings() -> None:
    """结构钉：run_fix_loop 停条件 = passed 且 0 警（And 表达式同时引用
    passed 与 warnings 判读）——只判 passed 即返的旧形态（0 错 N 警即停）
    不合法，复活即红。"""
    tree = ast.parse(inspect.getsource(gen.run_fix_loop))
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    for node in ast.walk(func):
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            if "passed" in names and _warnings_field_refs(node):
                return
    raise AssertionError("run_fix_loop 停条件未同时引用 passed 与 warnings")


def test_check_topic_passed_branch_enters_fix_loop_on_warnings() -> None:
    """结构钉：check_topic 首编 passed 分支引用 warnings 判定并调 run_fix_loop
    （有警 → 进修复轮）——删判定即红（旧形态 0 错 N 警即收工）。"""
    tree = ast.parse(inspect.getsource(gen.check_topic))
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    for node in ast.walk(func):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "passed"
        ):
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            assert _warnings_field_refs(node), (
                "check_topic passed 分支未引用 warnings"
            )
            assert "run_fix_loop" in names, (
                "check_topic passed 分支未调用 run_fix_loop"
            )
            return
    raise AssertionError("check_topic 无 passed 分支")


def test_build_summary_lines_include_warning_count() -> None:
    """结构钉：uv4_build / gmake_build 摘要行含警数（工单 fix-loop-warnings/01
    ——0 错 N 警时 CLI 摘要警数不可见即红）。"""
    for fn in (gen.uv4_build, gen.gmake_build):
        assert "warnings" in inspect.getsource(fn), (
            f"{fn.__name__} 摘要行未引用 warnings（警数不可见）"
        )


# ---------- 门禁同源结构钉（工单 generate-check-parity/01） ----------
#
# check_artifacts 曾逐字重实现门禁（FENCE_RE / _INCLUDE_RE / EXTERNAL_HEADERS
# / _resolves / is_external_header），门禁一改脚本静默漂移、真机验收给假信心；
# 已换闸为 build_output_tree_corpus → run_generation_gates（生产同一个 runner）。
# 镜像复活即红——验收脚本与生产不再有第二套门禁实现。

MIRROR_SYMBOLS = frozenset(
    {"FENCE_RE", "_INCLUDE_RE", "EXTERNAL_HEADERS", "_resolves", "is_external_header"}
)


def test_generate_check_has_no_gate_mirror_definitions() -> None:
    """结构钉：generate_check.py 不再定义门禁镜像符号（赋值 / 函数定义级，
    AST 断言——注释里的历史提及不算；镜像复活 = 验收与门禁漂移即红）。"""
    tree = ast.parse(GEN_CHECK.read_text(encoding="utf-8"))
    defined: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defined.add(target.id)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(node.target, ast.Name):
                defined.add(node.target.id)
    assert not (defined & MIRROR_SYMBOLS), (
        f"门禁镜像复活: {sorted(defined & MIRROR_SYMBOLS)}"
    )


def test_generate_check_runs_real_generation_gates() -> None:
    """结构钉：check_artifacts 从 package 引入真门禁——contest_generator.generator
    的 build_output_tree_corpus + run_generation_gates（镜像段换闸，删调用即红）。"""
    tree = ast.parse(GEN_CHECK.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "run_generation_gates" in names
    assert "build_output_tree_corpus" in names
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "contest_generator.generator"
        ):
            imported = {alias.name for alias in node.names}
            assert {"run_generation_gates", "build_output_tree_corpus"} <= imported
            break
    else:
        raise AssertionError("generate_check.py 未从 contest_generator.generator import")


# ---------- mspm0 真机编译对偶（工单 mspm0-build-makefiles/01） ----------


def test_generate_check_gmake_build_uses_real_compile_runner() -> None:
    """结构钉：mspm0 真机编译走生产 collect_build_log + find_make（uv4_build
    对偶，Debug/makefile 集由生成器自动产出）——删调用 / 改回自带 gmake
    命令即红。"""
    tree = ast.parse(GEN_CHECK.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "contest_generator.compile_runner"
        ):
            imported = {alias.name for alias in node.names}
            assert {"collect_build_log", "find_make"} <= imported
            break
    else:
        raise AssertionError(
            "generate_check.py 未从 contest_generator.compile_runner import"
        )
    func = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "gmake_build"
    )
    body_names = {n.id for n in ast.walk(func) if isinstance(n, ast.Name)}
    assert "collect_build_log" in body_names


def test_generate_check_has_no_stale_theia_no_cli_message() -> None:
    """过时文案已删（工单 mspm0-build-makefiles/01）："Theia 无命令行构建"
    —— gmake 通路真机跑通后不再是事实。"""
    text = GEN_CHECK.read_text(encoding="utf-8")
    assert "无命令行构建" not in text


# ---------- 推荐缓存（工单 check-recommend-cache/01） ----------
#
# 缓存 json = done 载荷逐字 + 元数据（topic_key / platform / problem_sha256，
# 决策 1）；键 = topic_id 优先、无 topic_id 用题面 sha256（决策 2）。纯函数
# 经 cache_dir=tmp_path 注入；check_topic 级测试经环境变量
# GENERATE_CHECK_CACHE_DIR 隔离（真实推荐路径会写缓存，不污染真实 cache/）。

DONE_SAMPLE = {
    "modules": [
        {"slug": "led_beep", "reason": "蜂鸣器提示"},
        {"slug": "gpio", "reason": "按键扫描"},
    ],
    "requirements": [{"id": 1, "text": "上电自检"}],
    "references": [
        {"id": "r1", "title": "参考条目", "source": "manual", "platform": "stm32"}
    ],
    "topic_id": "T1",
}


def _setup_topic_env(monkeypatch, tmp_path, problem_text="题面全文") -> None:
    """check_topic 缓存级测试的题库 + 缓存目录 tmp 隔离（fixture 同款）。"""
    topics = tmp_path / "topics"
    (topics / "T1").mkdir(parents=True)
    (topics / "T1" / "topic.md").write_text(problem_text, encoding="utf-8")
    monkeypatch.setattr(gen, "TOPICS", topics)
    monkeypatch.setenv("GENERATE_CHECK_CACHE_DIR", str(tmp_path / "cache"))


def test_recommend_cache_path_override_chain(tmp_path, monkeypatch) -> None:
    """recommend_cache_path 目录覆盖：显式参数 > 环境变量 > 缺省目录
    （决策 3，测试经 cache_dir=tmp_path 注入）。"""
    assert (
        gen.recommend_cache_path("2026C", cache_dir=tmp_path)
        == tmp_path / "recommend_2026C.json"
    )
    monkeypatch.setenv("GENERATE_CHECK_CACHE_DIR", str(tmp_path / "env"))
    assert (
        gen.recommend_cache_path("2026C")
        == tmp_path / "env" / "recommend_2026C.json"
    )
    monkeypatch.delenv("GENERATE_CHECK_CACHE_DIR")
    assert gen.recommend_cache_path("2026C") == gen.CACHE_DIR / "recommend_2026C.json"


def test_cache_key_topic_id_priority_else_sha256() -> None:
    """缓存键：topic_id 优先；无 topic_id（topic_file 手动准入）用题面
    sha256（决策 2——题面变 → 键变自然失效）。"""
    assert gen.cache_key("2026C", "任意题面") == "2026C"
    assert gen.cache_key(None, "题面") == gen.problem_fingerprint("题面")


def test_cache_recommend_then_load_roundtrip(tmp_path) -> None:
    """写 → 读回形状全等：done 逐字、元数据齐全（决策 1 另存题面指纹与
    topic key；platform 元数据防跨平台复用）。"""
    path = gen.recommend_cache_path("T1", cache_dir=tmp_path)
    gen.cache_recommend(
        path, DONE_SAMPLE, topic_key="T1",
        problem_text="题面全文", platform="stm32",
    )
    cached = gen.load_recommend(path)
    assert cached["done"] == DONE_SAMPLE
    assert cached["topic_key"] == "T1"
    assert cached["platform"] == "stm32"
    assert cached["problem_sha256"] == gen.problem_fingerprint("题面全文")


@pytest.mark.parametrize(
    "raw",
    [
        "不是 json",                                    # 坏 json
        '["列表顶层"]',                                 # 顶层非对象
        {"problem_sha256": "x", "platform": "stm32"},   # 缺 done / topic_key
        {"done": DONE_SAMPLE, "platform": "stm32"},     # 缺 problem_sha256
        {"topic_key": "T1", "done": {"modules": "非列表"},
         "platform": "stm32", "problem_sha256": "x"},   # modules 非列表
    ],
)
def test_load_recommend_rejects_bad_shapes(tmp_path, raw) -> None:
    """坏 json / 缺字段 / 非对象 → ValueError（复用安全网：不带假数据进下游）。"""
    path = gen.recommend_cache_path("T1", cache_dir=tmp_path)
    if isinstance(raw, str):
        path.write_text(raw, encoding="utf-8")
    else:
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        gen.load_recommend(path)


def test_check_topic_reuse_hit_skips_recommend_stream(
    monkeypatch, tmp_path, capsys
) -> None:
    """--reuse-recommend 命中：recommend_stream 零调用，done 从缓存进下游
    （空模块 done → 骨架前收工，推荐段跳过本身可证）。"""
    _setup_topic_env(monkeypatch, tmp_path)
    gen.cache_recommend(
        gen.recommend_cache_path("T1"), {"modules": []},
        topic_key="T1", problem_text="题面全文", platform=gen.PLATFORM,
    )
    called: list[dict] = []

    def fake_stream(payload: dict) -> dict:
        called.append(payload)
        return {"event": "done", "data": {"modules": []}, "rounds": 0}

    monkeypatch.setattr(gen, "recommend_stream", fake_stream)
    assert gen.check_topic("T1", reuse_recommend=True) is False
    assert called == []
    assert "复用" in capsys.readouterr().out


def test_check_topic_reuse_miss_errors_without_real_call(
    monkeypatch, tmp_path, capsys
) -> None:
    """--reuse-recommend 缺失：报错退出（False + 可操作文案），不静默回退
    真实推荐（决策 4）。"""
    _setup_topic_env(monkeypatch, tmp_path)
    called: list[dict] = []

    def fake_stream(payload: dict) -> dict:
        called.append(payload)
        return {"event": "done", "data": {"modules": []}, "rounds": 0}

    monkeypatch.setattr(gen, "recommend_stream", fake_stream)
    assert gen.check_topic("T1", reuse_recommend=True) is False
    assert called == []
    out = capsys.readouterr().out
    assert "缓存不存在" in out
    assert "--reuse-recommend" in out


@pytest.mark.parametrize(
    "cache_problem_text, cache_platform, cache_topic_key",
    [
        ("旧题面", "stm32", "T1"),
        ("题面全文", "mspm0", "T1"),
        ("题面全文", "stm32", "T2"),
    ],
)
def test_check_topic_reuse_stale_cache_errors(
    monkeypatch, tmp_path, capsys, cache_problem_text, cache_platform,
    cache_topic_key,
) -> None:
    """题面变（指纹不符）/ 平台不符 / 键不符 → 缓存失效报错退出（决策 6：
    题面变 → 指纹变自然失效；platform 防跨平台复用；topic_key 比对 =
    grilling 裁决，键不符的缓存文件不静默进下游）。"""
    _setup_topic_env(monkeypatch, tmp_path)
    gen.cache_recommend(
        gen.recommend_cache_path("T1"), {"modules": []},
        topic_key=cache_topic_key, problem_text=cache_problem_text,
        platform=cache_platform,
    )

    def no_real(payload):
        raise AssertionError("失效缓存不得回退真实推荐")

    monkeypatch.setattr(gen, "recommend_stream", no_real)
    assert gen.check_topic("T1", reuse_recommend=True) is False
    assert "缓存失效" in capsys.readouterr().out


def test_check_topic_real_recommend_writes_cache(
    monkeypatch, tmp_path, capsys
) -> None:
    """不带 flag = 真实推荐 + 写缓存（决策 5 默认行为不变）：done 载荷逐字
    落盘（空模块 done 在骨架前收工，写缓存已发生）。"""
    _setup_topic_env(monkeypatch, tmp_path)
    done = {"modules": []}
    monkeypatch.setattr(
        gen, "recommend_stream",
        lambda p: {"event": "done", "data": done, "rounds": 0},
    )
    assert gen.check_topic("T1") is False
    cached = gen.load_recommend(gen.recommend_cache_path("T1"))
    assert cached["done"] == done
    assert cached["topic_key"] == "T1"
    assert "已写" in capsys.readouterr().out


def test_check_topic_cache_write_failure_does_not_block(
    monkeypatch, tmp_path, capsys
) -> None:
    """写缓存失败（OSError）= 打印警告不阻断主流程（决策 5）。"""
    _setup_topic_env(monkeypatch, tmp_path)

    def fail_cache(path, done, **kwargs):
        raise OSError("磁盘只读")

    monkeypatch.setattr(gen, "cache_recommend", fail_cache)
    monkeypatch.setattr(
        gen, "recommend_stream",
        lambda p: {"event": "done", "data": {"modules": []}, "rounds": 0},
    )
    assert gen.check_topic("T1") is False  # 照常走完推荐段判定（空模块收工）
    assert "写失败" in capsys.readouterr().out


def test_cache_recommend_records_param_fingerprints(tmp_path) -> None:
    """缓存元数据带参数指纹（grilling 裁决 ①）：reference_ids 列表 + clarify
    内容 sha256；clarify 指纹顺序不敏感（补问答案进 map 后重跑不误报警告）；
    旧格式缓存（无此两字段）仍可加载（load 形状校验只钉必填三元数据）。"""
    path = gen.recommend_cache_path("T1", cache_dir=tmp_path)
    hist = [
        {"question": "问1?", "answer": "答1"},
        {"question": "问2?", "answer": "答2"},
    ]
    gen.cache_recommend(
        path, DONE_SAMPLE, topic_key="T1",
        problem_text="题面全文", platform="stm32",
        reference_ids=("r1", "r2"), clarify_hist=hist,
    )
    cached = gen.load_recommend(path)
    assert cached["reference_ids"] == ["r1", "r2"]
    assert cached["clarify_sha256"] == gen.clarify_fingerprint(hist)
    assert gen.clarify_fingerprint(hist) == gen.clarify_fingerprint(
        list(reversed(hist))
    )
    old = dict(cached)
    del old["reference_ids"], old["clarify_sha256"]
    (path.parent / "old.json").write_text(
        json.dumps(old, ensure_ascii=False), encoding="utf-8"
    )
    assert gen.load_recommend(path.parent / "old.json")["done"] == DONE_SAMPLE


def test_check_topic_reuse_param_mismatch_warns_but_proceeds(
    monkeypatch, tmp_path, capsys
) -> None:
    """同题换 reference_ids / clarify 内容复用缓存 → 打警告不阻断，推荐段仍
    零调用（grilling 裁决 ①：不静默沿用旧推荐、也不废掉 flag 换参数迭代的
    用途）。"""
    _setup_topic_env(monkeypatch, tmp_path)
    gen.cache_recommend(
        gen.recommend_cache_path("T1"), {"modules": []},
        topic_key="T1", problem_text="题面全文", platform=gen.PLATFORM,
        reference_ids=("r1",), clarify_hist=[{"question": "问?", "answer": "答"}],
    )
    called: list[dict] = []

    def fake_stream(payload: dict) -> dict:
        called.append(payload)
        return {"event": "done", "data": {"modules": []}, "rounds": 0}

    monkeypatch.setattr(gen, "recommend_stream", fake_stream)
    assert gen.check_topic(
        "T1", reuse_recommend=True,
        clarify_map={"问?": "答2"}, reference_ids=("r2",),
    ) is False  # 空模块 done → 骨架前收工；警告已打、流程照走
    assert called == []
    out = capsys.readouterr().out
    assert "本次输入与生成缓存时不同" in out
    assert "reference_ids" in out
    assert "clarifications" in out


def test_check_topic_reuse_same_params_no_warning(
    monkeypatch, tmp_path, capsys
) -> None:
    """同题同参数复用 → 无警告（指纹一致静默通过，警告通道零误报）。"""
    _setup_topic_env(monkeypatch, tmp_path)
    hist = [{"question": "问?", "answer": "答"}]
    gen.cache_recommend(
        gen.recommend_cache_path("T1"), {"modules": []},
        topic_key="T1", problem_text="题面全文", platform=gen.PLATFORM,
        reference_ids=("r1",), clarify_hist=hist,
    )
    monkeypatch.setattr(
        gen, "recommend_stream",
        lambda p: {"event": "done", "data": {"modules": []}, "rounds": 0},
    )
    assert gen.check_topic(
        "T1", reuse_recommend=True,
        clarify_map={"问?": "答"}, reference_ids=("r1",),
    ) is False
    out = capsys.readouterr().out
    assert "复用" in out
    assert "本次输入与生成缓存时不同" not in out
