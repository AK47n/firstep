"""进度事件契约（唯一出处，契约测试断言；spec「事件契约」+ ADR 0004）。

提炼期间后端经 SSE 推送的实时进展事件：类型 / 阶段名 / 字段子集与发射
seam 的唯一出处。llm 层（批次循环层）发射，webapp 层组装 SSE 线格式，
前端按这些键消费——改动须同步测试契约。本模块不依赖任何其他模块，
事件契约不属于 LLM 客户端。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# 阶段名与事件类型（webapp 层 / 前端按这些键消费，改动须同步测试契约）
PHASE_SUMMARY = "summary"  # 阶段 1：逐文件读全文出摘要
PHASE_DECIDE = "decide"  # 阶段 2：基于摘要判定

EVENT_START = "start"
EVENT_BATCH_START = "batch_start"
EVENT_BATCH_DONE = "batch_done"
EVENT_RETRY = "retry"
EVENT_PHASE_DONE = "phase_done"


@dataclass(frozen=True)
class ProgressEvent:
    """提炼进度事件（事件契约的代码形态，唯一出处）。

    每个事件类型只用字段子集：start 用 judgment_count / summary_batch_count /
    decide_batch_count（均由入口先算定）；batch_start 用 phase / batch_index
    （批号，1 起）/ batch_count / paths（阶段 1 = 待判文件路径、阶段 2 = 摘要
    路径）；batch_done 用 phase / batch_index / processed_count（本阶段累计已
    处理文件数——前端直接显示"已读 X/115"，无需累加状态）；retry 用 phase /
    batch_index / retry_round（补问轮次，1 起——首次补问 = 1）/ missing_count
    （该轮要补问的缺失文件数）；phase_done 用 phase / file_count（本阶段文件数）。
    """

    type: str
    judgment_count: int = 0
    summary_batch_count: int = 0
    decide_batch_count: int = 0
    phase: str = ""
    batch_index: int = 0
    batch_count: int = 0
    paths: tuple[str, ...] = ()
    processed_count: int = 0
    retry_round: int = 0
    missing_count: int = 0
    file_count: int = 0


ProgressEmitter = Callable[[ProgressEvent], None]


def _emit(emitter: ProgressEmitter | None, event: ProgressEvent) -> None:
    """旁路发射进度事件：发射器调用失败不影响提炼主流程（spec「发射 seam」）。

    选旁路而非透传的理由：提炼的主产物是完整报告（10-15 分钟 API 调用），进度
    只是观察通道——UI 消费失败（如前端断开）最多丢进度，不该让整个提炼陪葬。
    吞掉的异常不外抛也不记录（本地单用户工具，进度通道无诊断需求）。
    """
    if emitter is None:
        return
    try:
        emitter(event)
    except Exception:
        pass
