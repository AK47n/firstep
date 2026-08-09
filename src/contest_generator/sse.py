"""SSE 线格式与流化运行器（深模块，工单 C2 架构深化 + 工单 B 终态保证归位）。

吸收 webapp 两个 SSE 端点（/api/recommend、/api/masters/distill）字节级
重复的共享块，形成唯一入口：一次调用 = 一个 run 回调（回调经 SseEmitter
决定发哪些进度事件与终端数据），返回帧流生成器。webapp 端点只保留入参
校验与核心调用。依赖方向：本模块是叶子——只依赖 events 契约与标准库；
webapp 依赖本模块，反向禁止。

**终态保证归运行器**：run 在 daemon 线程执行，运行器包一层兜底——run 抛
错（或线程以任何方式死亡）时由运行器补发 error 终态——"每条流都以
done / question / error 结束"不依赖调用方闭包写 try/except（闭包只交
"活"，不交"收尾"）。错误文案经 error_message 注入（webapp 传错误映射表
取值），不注入时默认未登记政策同款（带类型名大声失败）——sse 是叶子，
不依赖错误映射表。

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

# 终端事件词表（运行器发射收尾；越界 = 程序错误，入队即大声失败，不静默进流）
_TERMINAL_KINDS = frozenset({EVENT_DONE, EVENT_ERROR, EVENT_QUESTION})


def _sse_frame(event_type: str, data: dict[str, Any]) -> str:
    """SSE 帧：event 行 + data 行 + 空行（线格式共享契约的唯一实现点）。

    json.dumps 默认转义字符串内换行——data 恒为单行，SSE 解析不歧义。
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _unexpected_error_message(exc: BaseException) -> str:
    """兜底文案：未注入映射器 / 线程内任何死亡（含 KeyboardInterrupt 等非
    Exception）时的错误信息——与错误映射表"未登记异常大声失败"政策同款
    （带类型名方便排查），sse 是叶子模块不依赖该表。"""
    return f"服务器内部错误（{type(exc).__name__}）：{exc}"


# 事件队列条目：进度事件原样入队；终端条目 = (kind, data)，kind ∈ done/error/
# question——三者 data 统一为 dict（done = 报告 / 结果 dict，question =
# {"questions": [...]}，error = {"message": 中文 message}）
_QueueItem = ProgressEvent | tuple[str, dict[str, Any]]


class SseEmitter:
    """运行回调的发射面：进度事件旁路入队，终端事件超时保护入队。

    旁路理由（spec「发射 seam」/「断线」）：SSE 是观察通道，客户端断开后
    队列无人消费——进度事件满即丢（put_nowait）、终端事件等超时后也丢，
    提炼 / 推荐线程不因断线卡死；吞掉不诊断（本地单用户工具）。
    终端三个方法形状一致（均收 dict，error 自带 {"message": ...} 包装）；
    未知 kind 在队列边界大声失败（ValueError）。
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

    def error(self, data: dict[str, Any]) -> None:
        """error 终端事件：data = {"message": 中文错误信息}，帧后流结束。"""
        self._put_terminal(EVENT_ERROR, data)

    def _put_terminal(self, kind: str, data: dict[str, Any]) -> None:
        """终端事件入队：kind 越界大声失败；客户端已断开（队列满、无人消费）
        时等超时后丢弃。"""
        if kind not in _TERMINAL_KINDS:
            raise ValueError(f"未知终端事件类型：{kind}")
        try:
            self._events.put((kind, data), timeout=self._terminal_timeout)
        except Full:
            pass


def run_sse(
    run: Callable[[SseEmitter], None],
    *,
    error_message: Callable[[Exception], str] | None = None,
    queue_maxsize: int = _SSE_QUEUE_MAXSIZE,
    terminal_timeout: float = _SSE_TERMINAL_TIMEOUT,
) -> Iterator[str]:
    """启动一次 SSE 运行，返回帧流生成器（深模块唯一入口）。

    run 在 daemon 线程执行（阻塞的核心调用不占事件循环）；返回的生成器
    逐帧消费队列——进度事件直接成帧，终态（done / question / error）成帧
    后停流。**终态保证归运行器**：run 抛错（或线程以任何方式死亡）时运行器
    补发 error 终态；文案经 error_message 注入（默认 = 带类型名大声失败）。
    队列容量与终端超时的默认值即契约数值（不得改动）；测试注入小值覆盖
    断线两条路径（队列满丢进度 / 终端超时丢）。
    """
    events: Queue[_QueueItem] = Queue(maxsize=queue_maxsize)
    emitter = SseEmitter(events, terminal_timeout)

    def worker() -> None:
        try:
            run(emitter)
        except Exception as exc:
            message = (
                error_message(exc)
                if error_message is not None
                else _unexpected_error_message(exc)
            )
            emitter.error({"message": message})
        except BaseException as exc:  # 线程内任何死亡都不许挂起流
            emitter.error({"message": _unexpected_error_message(exc)})

    threading.Thread(target=worker, daemon=True).start()

    def stream() -> Iterator[str]:
        while True:
            item = events.get()
            if isinstance(item, ProgressEvent):
                yield _sse_frame(item.type, asdict(item))
                continue
            kind, data = item
            # 不可达（_put_terminal 已白名单校验），防御性大声失败
            if kind not in _TERMINAL_KINDS:
                raise RuntimeError(f"未知终端事件类型：{kind}")
            yield _sse_frame(kind, data)
            return

    return stream()
