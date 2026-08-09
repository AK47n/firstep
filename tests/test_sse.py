"""SSE 流化运行器单测（工单 C2）：帧格式契约 + 终态停流 + 断线旁路。

运行器是纯函数式生成器（不涉及 HTTP），直接驱动 run_sse 的帧流断言；
端点装配契约（HTTP 200 起流 / 事件序列 / 载荷形态）由 tests/test_webapp.py
原样覆盖，本文件只测 sse.py 本身。
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from queue import Queue

import pytest

from contest_generator.events import (
    EVENT_BATCH_START,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_PHASE_DONE,
    EVENT_QUESTION,
    PHASE_SUMMARY,
    ProgressEvent,
)
from contest_generator.sse import SseEmitter, run_sse


def _frame(event_type: str, data: dict) -> str:
    """期望帧（与线格式契约同构，逐字节比对）：event 行 + data 行 + 空行。"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def test_streams_progress_frames_then_done() -> None:
    """进度事件逐帧原样成帧（帧格式逐字节），done 收尾停流。"""
    progress = [
        ProgressEvent(
            type=EVENT_BATCH_START,
            phase=PHASE_SUMMARY,
            batch_index=1,
            batch_count=2,
        ),
        ProgressEvent(
            type=EVENT_PHASE_DONE,
            phase=PHASE_SUMMARY,
            file_count=5,
        ),
    ]

    def run(emit: SseEmitter) -> None:
        for event in progress:
            emit.progress(event)
        emit.done({"report": {"summary": "ok"}})

    assert list(run_sse(run)) == [
        _frame(event.type, asdict(event)) for event in progress
    ] + [_frame(EVENT_DONE, {"report": {"summary": "ok"}})]


def test_done_frame_carries_result_and_stops() -> None:
    """done：data 原样带出（结果 dict），帧后流结束。"""
    result = {"modules": [{"slug": "led", "reason": "题面要求"}]}

    def run(emit: SseEmitter) -> None:
        emit.done(result)

    frames = list(run_sse(run))
    assert frames == [_frame(EVENT_DONE, result)]


def test_question_frame_carries_questions_and_stops() -> None:
    """question：data 原样带出（{"questions": [...]}），帧后流结束。"""
    questions = {"questions": ["需要用到什么传感器？"]}

    def run(emit: SseEmitter) -> None:
        emit.question(questions)

    frames = list(run_sse(run))
    assert frames == [_frame(EVENT_QUESTION, questions)]


def test_error_frame_wraps_message_and_stops() -> None:
    """error：data = {"message": 中文信息}（错误映射语义不变），帧后流结束。"""
    def run(emit: SseEmitter) -> None:
        emit.error({"message": "AI 服务超时"})

    frames = list(run_sse(run))
    assert frames == [_frame(EVENT_ERROR, {"message": "AI 服务超时"})]


def test_progress_dropped_when_queue_full() -> None:
    """断线旁路 1：队列满（客户端断开、无人消费）→ 进度事件满即丢，不堵线程。

    队列容量 2：前两个进度事件入队，第三个 put_nowait 丢；done 等队列腾出
    空间后照常入队收尾——流仍以 done 结束，只缺被丢的进度。
    """
    sent = 0

    def run(emit: SseEmitter) -> None:
        nonlocal sent
        for index in range(3):
            emit.progress(
                ProgressEvent(
                    type=EVENT_BATCH_START,
                    phase=PHASE_SUMMARY,
                    batch_index=index + 1,
                    batch_count=3,
                )
            )
            sent += 1
        emit.done({"ok": True})

    frames = list(run_sse(run, queue_maxsize=2))
    assert sent == 3  # 业务线程全部发完，未被阻塞
    assert frames == [
        _frame(
            EVENT_BATCH_START,
            asdict(
                ProgressEvent(
                    type=EVENT_BATCH_START,
                    phase=PHASE_SUMMARY,
                    batch_index=1,
                    batch_count=3,
                )
            ),
        ),
        _frame(
            EVENT_BATCH_START,
            asdict(
                ProgressEvent(
                    type=EVENT_BATCH_START,
                    phase=PHASE_SUMMARY,
                    batch_index=2,
                    batch_count=3,
                )
            ),
        ),
        _frame(EVENT_DONE, {"ok": True}),
    ]


def test_terminal_dropped_on_timeout_when_disconnected() -> None:
    """断线旁路 2：队列满且无人消费（客户端断开）→ 终端事件等超时后丢弃，
    提炼 / 推荐线程不因断线卡死（spec「断线」）。

    不消费返回的帧流即模拟断开：进度事件填满队列后，done 的 put 只等
    terminal_timeout 秒（此处注入 0.1）即放弃——run 回调应照常完成返回。
    """
    done = threading.Event()
    start = time.monotonic()

    def run(emit: SseEmitter) -> None:
        emit.progress(
            ProgressEvent(
                type=EVENT_BATCH_START,
                phase=PHASE_SUMMARY,
                batch_index=1,
                batch_count=1,
            )
        )
        emit.done({"ok": True})
        done.set()

    stream = run_sse(run, queue_maxsize=1, terminal_timeout=0.1)
    # 注意：不迭代 stream——客户端断开后无人消费队列
    assert done.wait(2.0), "终端事件超时旁路未生效：业务线程卡在 put"
    assert time.monotonic() - start < 1.0, "超时旁路耗时远超 0.1s，疑似阻塞"


# ---------------------------------------------------------------------------
# 终态保证归运行器（工单 B）：run 抛错 / 线程死亡 → 运行器补发 error 终态，
# "每条流都以 done / question / error 结束"不依赖闭包写 try/except
# ---------------------------------------------------------------------------


def test_runner_emits_error_when_run_raises() -> None:
    """run 抛错（如忘记 catch 的 LLMError）→ 运行器补发 error 终态，流结束。"""
    def run(emit: SseEmitter) -> None:
        emit.progress(
            ProgressEvent(type=EVENT_BATCH_START, phase=PHASE_SUMMARY, batch_index=1)
        )
        raise ValueError("boom")

    frames = list(run_sse(run, error_message=lambda exc: f"映射：{exc}"))
    assert frames == [
        _frame(
            EVENT_BATCH_START,
            asdict(
                ProgressEvent(
                    type=EVENT_BATCH_START, phase=PHASE_SUMMARY, batch_index=1
                )
            ),
        ),
        _frame(EVENT_ERROR, {"message": "映射：boom"}),
    ]


def test_runner_uses_injected_mapper_and_defaults_loud() -> None:
    """错误文案：注入的映射器生效；不注入时默认带类型名大声失败（与错误
    映射表"未登记异常大声失败"政策同款，sse 是叶子不依赖该表）。"""
    def run(emit: SseEmitter) -> None:
        raise ValueError("boom")

    assert list(run_sse(run, error_message=lambda exc: "中文信息")) == [
        _frame(EVENT_ERROR, {"message": "中文信息"})
    ]
    assert list(run_sse(run)) == [
        _frame(EVENT_ERROR, {"message": "服务器内部错误（ValueError）：boom"})
    ]


def test_runner_emits_error_on_non_exception_death() -> None:
    """run 以 Exception 之外的 BaseException 死亡（如 KeyboardInterrupt）——
    旧实现线程静默死亡、流永久悬挂；运行器兜底补发 error 终态，流结束。"""
    def run(emit: SseEmitter) -> None:
        raise KeyboardInterrupt

    frames = list(run_sse(run))
    assert frames == [_frame(EVENT_ERROR, {"message": "服务器内部错误（KeyboardInterrupt）："})]


def test_unknown_terminal_kind_fails_loud_at_queue_boundary() -> None:
    """未知终端 kind：队列边界大声失败（ValueError），不静默进流当 error 帧——
    stream 的 dispatch 分支由此不可达，防御性 RuntimeError 只是双保险。"""
    emitter = SseEmitter(Queue(), 0.1)
    with pytest.raises(ValueError):
        emitter._put_terminal("bogus", {})  # 本文件是 sse.py 专属测试，私有面可测
