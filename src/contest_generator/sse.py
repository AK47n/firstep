"""SSE 线格式与流化运行器（深模块，工单 C2 架构深化）。

吸收 webapp 两个 SSE 端点（/api/recommend、/api/masters/distill）字节级
重复的共享块，形成唯一入口：一次调用 = 一个 run 回调（回调经 SseEmitter
决定发哪些进度事件与终端数据），返回帧流生成器。webapp 端点只保留入参
校验与核心调用。依赖方向：本模块是叶子——只依赖 events 契约与标准库；
webapp 依赖本模块，反向禁止。

线格式契约（工单 02 起，与工单 03 并行开发，精确一致不得单方面改动）：
HTTP 200，Content-Type: text/event-stream，无自动重连（断线 = 放弃本次）。
每个事件 = "event: <type>\\n" + "data: <JSON>\\n" + "\\n"（空行分隔）。
提炼端点 type ∈ start / batch_start / batch_done / retry / phase_done /
done / error（前五者由 llm 层发射器产生，done / error 由运行器发射收尾）；
推荐端点（工单 10）type ∈ round / converged / question / done / error
（round / converged 由收敛循环发射器产生，question / done / error 由运行
器发射收尾）。进度事件 data = ProgressEvent 字段 JSON；done 的 data =
完整报告（提炼 = report.to_dict()，推荐 = 推荐结果 dict）；question 的
data = {"questions": [...]}（模型拿不准向用户补问）；error 的 data =
{"message": 中文错误信息}；done / question / error 后流结束。
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict
from queue import Full, Queue
from typing import Any, Callable, Iterator

from .events import (
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_QUESTION,
    ProgressEmitter,
    ProgressEvent,
)

# 事件缓冲上限与终端事件等待超时：进度事件只在批次边界产生（分钟级），
# 100 个缓冲对在线消费方绰绰有余；客户端断开后队列无人消费——进度事件满即丢
# （put_nowait，旁路），终端事件等超时后也丢——提炼线程（daemon）不因断线卡死。
_SSE_QUEUE_MAXSIZE = 100
_SSE_TERMINAL_TIMEOUT = 10  # 秒


def _sse_frame(event_type: str, data: dict[str, Any]) -> str:
    """SSE 帧：event 行 + data 行 + 空行（线格式共享契约的唯一实现点）。

    json.dumps 默认转义字符串内换行——data 恒为单行，SSE 解析不歧义。
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# 事件队列条目：进度事件原样入队；终端条目 = (kind, data)，kind ∈ done/error/
# question（done 的 data = 报告 / 结果 dict，question 的 data = {"questions":
# [...]}，error 的 data = 中文 message——错误信息语义与错误映射表一致）
_QueueItem = ProgressEvent | tuple[str, Any]


class SseEmitter:
    """运行回调的发射面：进度事件旁路入队，终端事件超时保护入队。

    旁路理由（spec「发射 seam」/「断线」）：SSE 是观察通道，客户端断开后
    队列无人消费——进度事件满即丢（put_nowait）、终端事件等超时后也丢，
    提炼 / 推荐线程不因断线卡死；吞掉不诊断（本地单用户工具）。
    """

    def __init__(self, events: Queue[_QueueItem], terminal_timeout: float) -> None:
        self._events = events
        self._terminal_timeout = terminal_timeout

    def progress(self, event: ProgressEvent) -> None:
        """进度事件入队：队列满（客户端断开）即丢，不堵业务线程。"""
        try:
            self._events.put_nowait(event)
        except Full:
            pass

    def done(self, data: dict[str, Any]) -> None:
        """done 终端事件：data = 完整报告 / 推荐结果 dict，帧后流结束。"""
        self._put_terminal(EVENT_DONE, data)

    def question(self, data: dict[str, Any]) -> None:
        """question 终端事件：data = {"questions": [...]}（推荐端点补问）。"""
        self._put_terminal(EVENT_QUESTION, data)

    def error(self, message: str) -> None:
        """error 终端事件：data = 中文错误信息（帧内包成 {"message": ...}）。"""
        self._put_terminal(EVENT_ERROR, message)

    def _put_terminal(self, kind: str, data: Any) -> None:
        """终端事件入队：客户端已断开（队列满、无人消费）时等超时后丢弃。"""
        try:
            self._events.put((kind, data), timeout=self._terminal_timeout)
        except Full:
            pass


def run_sse(
    run: Callable[[SseEmitter], None],
    *,
    queue_maxsize: int = _SSE_QUEUE_MAXSIZE,
    terminal_timeout: float = _SSE_TERMINAL_TIMEOUT,
) -> Iterator[str]:
    """启动一次 SSE 运行，返回帧流生成器（深模块唯一入口）。

    run 在 daemon 线程执行（阻塞的核心调用不占事件循环）；返回的生成器
    逐帧消费队列——进度事件直接成帧，终态（done / question / error）成帧
    后停流。队列容量与终端超时的默认值即契约数值（不得改动）；测试注入
    小值覆盖断线两条路径（队列满丢进度 / 终端超时丢）。
    """
    events: Queue[_QueueItem] = Queue(maxsize=queue_maxsize)
    emitter = SseEmitter(events, terminal_timeout)

    def worker() -> None:
        run(emitter)

    threading.Thread(target=worker, daemon=True).start()

    def stream() -> Iterator[str]:
        while True:
            item = events.get()
            if isinstance(item, ProgressEvent):
                yield _sse_frame(item.type, asdict(item))
                continue
            kind, data = item
            if kind in (EVENT_DONE, EVENT_QUESTION):
                yield _sse_frame(kind, data)
            else:
                yield _sse_frame(EVENT_ERROR, {"message": data})
            return

    return stream()
