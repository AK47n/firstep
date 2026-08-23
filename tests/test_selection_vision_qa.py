"""推荐阶段按需视觉问答（工单 recommend-vision-qa/01）：图内问题机械判定 +
澄清 / 收敛补问被视觉消化（答案并入澄清历史）。注入假视觉回调，不碰网络。

判定是纯函数；编排走 run_recommendation（真实 SseEmitter + Queue 断言事件
逐字形状，照 test_selection.py 先例）。
"""

from queue import Queue

from contest_generator.events import (
    EVENT_CONVERGED,
    EVENT_DONE,
    EVENT_QUESTION,
    EVENT_ROUND,
)
from contest_generator.generator import TopicContext
from contest_generator.selection import (
    FunctionRequirement,
    ModuleSelection,
    OutOfLibrarySuggestion,
    run_recommendation,
    vision_answerable,
)
from contest_generator.sse import SseEmitter
from tests.fakes import FakeLLM

# ---------------------------------------------------------------------------
# 假件：记录型 LLM（clarify 可配置返回；select 按队列返回）+ 最小 TopicContext
# ---------------------------------------------------------------------------


class _FakeLLM(FakeLLM):
    """记录型假 LLM：select 按队列返回选择，记录每次调用的澄清历史。"""

    def __init__(
        self,
        clarify_questions: tuple[str, ...] = (),
        selections: tuple[ModuleSelection, ...] = (),
    ) -> None:
        super().__init__(clarify_questions=clarify_questions)
        self._queue = list(selections)
        self.select_calls: list[str] = []
        self.clarifications_seen: list[tuple[tuple[str, str], ...]] = []

    def select_modules(
        self,
        problem_text: str,
        manifest_summaries,
        references=(),
        reference_fulltexts=None,
        manual_fulltexts=None,
        clarifications=(),
        qa_material="",
    ) -> ModuleSelection:
        self.select_calls.append(problem_text)
        self.clarifications_seen.append(tuple(clarifications))
        return self._queue.pop(0)


def _selection_with(
    requirement: str,
    *,
    questions: tuple[str, ...] = (),
) -> ModuleSelection:
    return ModuleSelection(
        modules=(),
        reasons={},
        requirements=(
            FunctionRequirement(
                requirement=requirement,
                sentence_index=1,
                modules=(),
                suggestions=(),
            ),
        ),
        questions=questions,
    )


def _topic(problem_text: str = "送药小车。院区如图1所示。") -> TopicContext:
    return TopicContext(
        key="2021F",
        problem_text=problem_text,
        references=(),
        manifest_summaries=(),
        suggestions=(),
        read_fulltext=lambda entry_id: "",
    )


def _run_recommendation(
    llm: _FakeLLM,
    *,
    vision_qa=None,
    topic: TopicContext | None = None,
    clarifications=(),
) -> tuple[Queue, dict]:
    """直调 run_recommendation，返回 (事件队列, 视觉调用记录)。"""
    events: Queue = Queue()
    emit = SseEmitter(events, terminal_timeout=1.0)
    vision_calls: list[tuple[str, str | None]] = []

    def recording_vision_qa(question: str) -> str | None:
        answer = vision_qa(question) if vision_qa else None
        vision_calls.append((question, answer))
        return answer

    run_recommendation(
        topic or _topic(),
        llm,
        clarifications,
        emit=emit,
        vision_qa=recording_vision_qa if vision_qa is not None else None,
    )
    return events, {"vision_calls": vision_calls}


def _drain(events: Queue) -> list:
    items = []
    while not events.empty():
        items.append(events.get_nowait())
    return items


def _kinds(items: list) -> list[str]:
    return [item.type if not isinstance(item, tuple) else item[0] for item in items]


# ---------------------------------------------------------------------------
# vision_answerable：机械判定（宁漏判不误判）
# ---------------------------------------------------------------------------


def test_vision_answerable_hits_figure_dimension_question():
    """问题点名题面引用过的图号 + 尺寸/位置类关键词 → 命中。"""
    problem = "院区尺寸如图1所示。"
    assert vision_answerable("图1中的走廊宽度是多少？", problem)
    assert vision_answerable("图1 标注的门口区域尺寸是？", problem)
    assert vision_answerable("图1中病房的位置在哪？", problem)
    assert vision_answerable("图1的走向如何？", problem)
    assert vision_answerable("图1标注的走廊有多宽？", problem)


def test_vision_answerable_multi_figure_problem():
    """题面引用多图：问题点名任一被引用图号即命中。"""
    problem = "院区如图1所示，病房如图2所示。"
    assert vision_answerable("图2中的入口位置在哪？", problem)
    assert vision_answerable("图1中的走廊宽度？", problem)


def test_vision_answerable_figure_number_intersection_not_substring():
    """图号按编号求交而非子串匹配：题面只引图1，问题写「图10」不命中。"""
    problem = "院区尺寸如图1所示。"
    assert not vision_answerable("图10中的走廊宽度是多少？", problem)


def test_vision_answerable_misses_without_figure_number_in_question():
    """问题没点名图号（如「走廊宽度是多少？」）→ 漏判（保守：照旧问用户）。"""
    problem = "院区尺寸如图1所示。"
    assert not vision_answerable("走廊宽度是多少？", problem)
    assert not vision_answerable("门口区域的精确尺寸是多少？", problem)


def test_vision_answerable_misses_when_problem_has_no_figure_reference():
    """题面没引用任何图号（no-topic 粘贴题面）→ 永不命中。"""
    problem = "送药小车。识别数字。"
    assert not vision_answerable("图1中的走廊宽度是多少？", problem)
    assert not vision_answerable("图中走廊宽度？", problem)


def test_vision_answerable_misses_interaction_question():
    """图号命中但问题非图上事实（交互/实现细节）→ 漏判。"""
    problem = "院区尺寸如图1所示。"
    assert not vision_answerable("图1里小车用什么方式识别数字？", problem)
    assert not vision_answerable("图1区域需要几块电池？", problem)


def test_vision_answerable_empty_inputs():
    assert not vision_answerable("", "院区如图1所示。")
    assert not vision_answerable("图1中的走廊宽度？", "")


# ---------------------------------------------------------------------------
# run_recommendation 编排：澄清门视觉消化四路径
# ---------------------------------------------------------------------------


def test_clarify_questions_fully_consumed_by_vision_then_converge():
    """澄清问题被视觉全部消化 → 无 question 事件，答案进澄清历史随收敛喂给
    模型，最终 done。"""
    llm = _FakeLLM(
        clarify_questions=("图1中的走廊宽度是多少？",),
        selections=(_selection_with("循迹送药"), _selection_with("循迹送药")),
    )

    events, record = _run_recommendation(
        llm, vision_qa=lambda question: "走廊宽 30cm"
    )

    assert record["vision_calls"] == [("图1中的走廊宽度是多少？", "走廊宽 30cm")]
    assert _kinds(_drain(events)) == [EVENT_ROUND, EVENT_ROUND, EVENT_CONVERGED, EVENT_DONE]
    # 视觉答案作为澄清问答并入历史，收敛每轮透传
    expected_history = (("图1中的走廊宽度是多少？", "走廊宽 30cm"),)
    assert llm.clarifications_seen == [expected_history, expected_history]


def test_clarify_partial_vision_consumption_keeps_remaining_for_user():
    """部分消化：命中的图内问题被视觉答掉，其余照旧问用户（question 事件只
    含剩余）。"""
    llm = _FakeLLM(
        clarify_questions=(
            "图1中的走廊宽度是多少？",
            "小车最大尺寸限制是多少？",  # 无图号 → 漏判，保留
        ),
    )

    events, record = _run_recommendation(
        llm, vision_qa=lambda question: "走廊宽 30cm"
    )

    assert record["vision_calls"] == [("图1中的走廊宽度是多少？", "走廊宽 30cm")]
    assert _drain(events) == [
        ("question", {"questions": ["小车最大尺寸限制是多少？"]})
    ]
    assert llm.select_calls == []  # 有剩余待问：不进收敛


def test_clarify_vision_qa_failure_falls_back_to_user():
    """视觉答不上（回调返回 None）→ 问题原样问用户，流程不阻塞。"""
    llm = _FakeLLM(clarify_questions=("图1中的走廊宽度是多少？",))

    events, record = _run_recommendation(llm, vision_qa=lambda question: None)

    assert record["vision_calls"] == [("图1中的走廊宽度是多少？", None)]
    assert _drain(events) == [("question", {"questions": ["图1中的走廊宽度是多少？"]})]


def test_clarify_vision_qa_empty_answer_treated_as_failure():
    """视觉返回空串 / 纯空白 → 视为答不上，照旧问用户。"""
    llm = _FakeLLM(clarify_questions=("图1中的走廊宽度是多少？",))

    events, record = _run_recommendation(
        llm, vision_qa=lambda question: "   "
    )

    assert _drain(events) == [("question", {"questions": ["图1中的走廊宽度是多少？"]})]


def test_clarify_without_vision_qa_unchanged():
    """未注入视觉回调 → 行为与改动前一致（问题原样问用户）。"""
    llm = _FakeLLM(clarify_questions=("具体要识别什么数字？",))

    events, _ = _run_recommendation(llm, vision_qa=None)

    assert _drain(events) == [("question", {"questions": ["具体要识别什么数字？"]})]
    assert llm.select_calls == []


# ---------------------------------------------------------------------------
# run_recommendation 编排：收敛补问视觉消化
# ---------------------------------------------------------------------------


def test_convergence_questions_consumed_by_vision_then_rerun():
    """收敛循环补问被视觉全部消化 → 答案并入历史重跑收敛（回答并入历史重发
    的既有语义），最终 done；重跑轮次正常推进。"""
    llm = _FakeLLM(
        selections=(
            _selection_with("需求一", questions=("图1中的走廊宽度是多少？",)),
            _selection_with("识别数字"),
            _selection_with("识别数字"),
        )
    )

    events, record = _run_recommendation(
        llm, vision_qa=lambda question: "走廊宽 30cm"
    )

    assert record["vision_calls"] == [("图1中的走廊宽度是多少？", "走廊宽 30cm")]
    kinds = _kinds(_drain(events))
    assert kinds == [EVENT_ROUND, EVENT_ROUND, EVENT_ROUND, EVENT_CONVERGED, EVENT_DONE]
    expected_history = (("图1中的走廊宽度是多少？", "走廊宽 30cm"),)
    # 首轮无历史，重跑两轮带视觉答案
    assert llm.clarifications_seen == [(), expected_history, expected_history]


def test_convergence_questions_partially_remaining_ask_user():
    """收敛补问部分被视觉消化 → 剩余照旧问用户，不重跑收敛。"""
    llm = _FakeLLM(
        selections=(
            _selection_with(
                "需求一",
                questions=("图1中的走廊宽度是多少？", "题面没有说明识别方式，用摄像头还是传感器？"),
            ),
        )
    )

    events, record = _run_recommendation(
        llm, vision_qa=lambda question: "走廊宽 30cm"
    )

    assert record["vision_calls"] == [("图1中的走廊宽度是多少？", "走廊宽 30cm")]
    items = _drain(events)
    assert _kinds(items) == [EVENT_ROUND, EVENT_QUESTION]
    assert items[-1] == (
        "question",
        {"questions": ["题面没有说明识别方式，用摄像头还是传感器？"]},
    )


def test_convergence_questions_remaining_after_rerun_ask_user():
    """重跑收敛后模型仍有疑问 → 直接问用户（视觉已尽力，防问问题链死循环）。"""
    llm = _FakeLLM(
        selections=(
            _selection_with("需求一", questions=("图1中的走廊宽度是多少？",)),
            _selection_with("识别数字", questions=("识别用摄像头还是传感器？",)),
        )
    )

    events, record = _run_recommendation(
        llm, vision_qa=lambda question: "走廊宽 30cm"
    )

    assert record["vision_calls"] == [("图1中的走廊宽度是多少？", "走廊宽 30cm")]
    items = _drain(events)
    assert _kinds(items) == [EVENT_ROUND, EVENT_ROUND, EVENT_QUESTION]
    assert items[-1] == ("question", {"questions": ["识别用摄像头还是传感器？"]})


def test_convergence_without_vision_qa_unchanged():
    """未注入视觉回调：收敛补问原样问用户（既有行为）。"""
    llm = _FakeLLM(
        selections=(
            _selection_with(
                "需求一", questions=("题面没有说明识别方式，用摄像头还是传感器？",)
            ),
        )
    )

    events, _ = _run_recommendation(llm, vision_qa=None)

    items = _drain(events)
    assert _kinds(items) == [EVENT_ROUND, EVENT_QUESTION]
    assert items[-1] == (
        "question",
        {"questions": ["题面没有说明识别方式，用摄像头还是传感器？"]},
    )
