"""事件契约（唯一出处，契约测试断言；spec「事件契约」+ ADR 0004）。

SSE 推送事件的类型词表（进度事件 + 终态事件）与字段子集、发射 seam 的
唯一出处。进度事件由 llm 层（批次循环层）发射，终态事件（done / error /
question）由 sse 运行器发射收尾；线格式在 sse.py，webapp 层只装配调用。
前端按这些键消费——改动须同步测试契约。本模块不依赖任何其他模块，
事件契约不属于 LLM 客户端。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# 阶段名与事件类型（sse 运行器 / 前端按这些键消费，改动须同步测试契约）
PHASE_SUMMARY = "summary"  # 阶段 1：逐文件读全文出摘要
PHASE_DECIDE = "decide"  # 阶段 2：基于摘要判定

EVENT_START = "start"
EVENT_BATCH_START = "batch_start"
EVENT_BATCH_DONE = "batch_done"
EVENT_RETRY = "retry"
EVENT_PHASE_DONE = "phase_done"

# 模块推荐收敛循环（工单 10）的事件类型：round = 一轮收敛自检开始（round =
# 轮次、round_total = 上限）；converged = 功能需求层两轮一致（round = 收敛
# 轮次）。补问（questions）是终端事件，由 sse 运行器发射（与 done / error 同款）。
EVENT_ROUND = "round"
EVENT_CONVERGED = "converged"

# 编译错误修复（工单 compile-error-fix/01）的事件类型：parse_done = 报错解析
# 完成（error_count = 解析出的报错条数、file_count = 定位到的可修复文件数，
# file_count 为 0 = 降级模式）；fix_start = LLM 修复开始（分钟级阻塞调用）；
# apply_result = 单处修复应用结果（file / line / status / reason，status ∈
# applied / skipped，未应用带中文 reason）。
EVENT_PARSE_DONE = "parse_done"
EVENT_FIX_START = "fix_start"
EVENT_APPLY_RESULT = "apply_result"

# LLM 观测旁路事件（llm-observability-dashboard/02）：只携带 content-safe
# 聚合字段，不含 prompt / response / API key / 源码 / 编译输出。字段前缀 llm_
# 避免与既有 ProgressEvent 字段碰撞；前端显示紧凑状态行，终态行为不变。
EVENT_LLM_TELEMETRY = "llm_telemetry"

# 自动编译（工单 autocompile-loop/01）的事件类型：compile_start = 编译子进程
# 启动（前端显示"编译中"，分钟级以内）；done 的 data = {platform, output_dir,
# exit_code, error_text, passed, timed_out, project_file, command}——error_text
# 原样采集自编译器输出（与 fix-errors 解析契约对齐），passed 由域模块
# compile_runner.compile_passed 判定（前端循环不自己判退出码）。展示层字段
# （工单 compile-experience-ui/01，只增不改旧字段）：duration（秒，float，
# 子进程实际耗时）/ parsed_errors（[{path, line, message}]，parse_compile_errors
# 解析——与 fix-errors 的 parsed 同源同构）/ summary（{errors, warnings}，
# summarize_compile_output）。done 契约与 webapp.py /api/compile 路由 docstring
# 同源（词表唯一出处，改动须两处同步）
EVENT_COMPILE_START = "compile_start"

# 终端事件（收尾事件，sse 运行器发射；done / question / error 后流结束）：
# done 的 data = 完整报告（提炼 = report.to_dict()，推荐 = 推荐结果 dict）；
# question 的 data = {"questions": [...]}（推荐端点：模型拿不准向用户补问）；
# error 的 data = {"message": 中文错误信息}。词表唯一出处 = 本模块。
EVENT_DONE = "done"
EVENT_ERROR = "error"
EVENT_QUESTION = "question"


@dataclass(frozen=True)
class ProgressEvent:
    """提炼进度事件（事件契约的代码形态，唯一出处）。

    每个事件类型只用字段子集：start 用 judgment_count / summary_batch_count /
    decide_batch_count（均由入口先算定）；batch_start 用 phase / batch_index
    （批号，1 起）/ batch_count / paths（阶段 1 = 待判文件路径、阶段 2 = 摘要
    路径）；batch_done 用 phase / batch_index / processed_count（本阶段累计已
    处理文件数——前端直接显示"已读 X/115"，无需累加状态）；retry 用 phase /
    batch_index / retry_round（补问轮次，1 起——首次补问 = 1）/ missing_count
    （该轮要补问的缺失文件数）；phase_done 用 phase / file_count（本阶段文件数）；
    推荐收敛循环（工单 10）的 round 用 round / round_total、converged 用 round；
    编译错误修复（工单 compile-error-fix/01）的 parse_done 用 error_count /
    file_count、apply_result 用 file / line / status / reason；LLM telemetry 用
    llm_* 聚合字段与 llm_calls 明细（均为脱敏数值 / 枚举 / id，不含内容）。
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
    round: int = 0  # 模块推荐收敛轮次（round / converged 事件用，1 起）
    round_total: int = 0  # 收敛轮次上限（round 事件携带，前端显示"N/上限"）
    error_count: int = 0  # 编译错误修复：parse_done 解析出的报错条数
    file: str = ""  # 编译错误修复：apply_result 修复的文件相对路径
    line: int = 0  # 编译错误修复：apply_result 报错行号
    status: str = ""  # 编译错误修复：apply_result "applied" / "skipped"
    reason: str = ""  # 编译错误修复：apply_result 中文说明（未应用原因）
    llm_workflow_id: str = ""  # LLM telemetry：工作流 id（类型 + 随机 id，无内容）
    llm_total_calls: int = 0
    llm_local_calls: int = 0
    llm_deepseek_calls: int = 0
    llm_latest_operation: str = ""
    llm_error_kind: str = ""
    llm_parse_status: str = ""
    llm_latest_http_status: int = 0
    llm_attempts: int = 0
    llm_retry_calls: int = 0
    llm_error_calls: int = 0
    llm_parse_error_calls: int = 0
    llm_rate_limit_calls: int = 0
    llm_network_error_calls: int = 0
    llm_5xx_calls: int = 0
    llm_budget_blocked_calls: int = 0
    llm_request_bytes: int = 0
    llm_duration_ms: int = 0
    llm_usage: dict[str, Any] | None = None
    llm_calls: tuple[dict[str, Any], ...] = ()


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
