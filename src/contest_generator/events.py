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

# 500 兜底反馈引导（工单 beginner-gap-closure/06，单一出处）：errors.py 与
# sse.py 两处「未登记异常大声失败」兜底文案共享——放在事件契约叶子模块
#（两端都依赖、无环——sse 是叶子不能再 import errors，本模块不依赖任何
# 其它模块）。把「内部错误 = 工具 bug」的定性告诉新手（不是操作错误），
# 并给可反馈出口；具体错误与类型名仍保留在消息头，复制即可反馈。
INTERNAL_ERROR_HINT = (
    "（这是工具的内部问题，不是你的操作错误——请把这段错误信息复制反馈给我们，"
    "我们会尽快修复）"
)

# 阶段名与事件类型（sse 运行器 / 前端按这些键消费，改动须同步测试契约）
PHASE_SUMMARY = "summary"  # 阶段 1：逐文件读全文出摘要
PHASE_DECIDE = "decide"  # 阶段 2：基于摘要判定

# 提炼与推荐端点共用 start 事件（字段子集按端点取：提炼 = judgment_count /
# summary_batch_count / decide_batch_count；推荐（工单 ux-walkthrough-02/13）=
# stage 中文阶段标签——首个分钟级 LLM 调用前先送一条，前端等待期即有内容）。
EVENT_START = "start"
EVENT_BATCH_START = "batch_start"
EVENT_BATCH_DONE = "batch_done"
EVENT_RETRY = "retry"
EVENT_PHASE_DONE = "phase_done"

# 模块推荐收敛循环（工单 10）的事件类型：round = 一轮收敛自检开始（round =
# 轮次、round_total = 上限）；converged = 功能需求层两轮一致（round = 收敛
# 轮次）。补问（questions）是终端事件，由 sse 运行器发射（与 done / error 同款）。
# 推荐端点的首个进度事件复用 EVENT_START（见上；stage 字段 = 中文阶段标签）。
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
# 子进程实际耗时）/ parsed_errors（[{path, line, message, kind?}]，解析与条目
# 形状单源 = fix_errors.parse_compile_errors / parsed_error_entries——与 fix-errors
# 的 parsed 同源同构；配置级冲突（工单 02：SysConfig Resource conflict）条目带
# kind="syscfg_conflict"、path 为伪路径、line=0，前端据此渲染不可跳转的说明行）/
# summary（{errors, warnings}，
# summarize_compile_output）。done 契约与 webapp.py /api/compile 路由 docstring
# 同源（词表唯一出处，改动须两处同步）
EVENT_COMPILE_START = "compile_start"

# 推荐缓存命中（工单 llm-cost-control/02）：进度事件，缓存直出 done 载荷前
# 发射——warns = 参数指纹警告列表（reference_ids / clarifications 与缓存时
# 不同，结果沿用旧推荐）；前端显示「复用本地缓存」，带警告时提示差异。
EVENT_CACHE_HIT = "cache_hit"

# 修订影响分析（工单 revise-deepen/02）的事件类型：impact_analyzing = LLM
# 影响分析开始（分钟级阻塞调用）；diff_ready = 确定性 diff 与平台警告重算
# 完成（done 载荷前）。done 的 data = 影响产物（impacts + suggested_slugs +
# diff + warnings）。
EVENT_IMPACT_ANALYZING = "impact_analyzing"
EVENT_DIFF_READY = "diff_ready"

# 修订执行（工单 revise-deepen/03）的事件类型：revision_backup = 整树备份
# 中；revision_generating = 覆盖式重生成中（骨架 LLM + 生成管线，仅模块集
# 变化时发射）。done 的 data = diff 记录（backup_id / regenerated / diff /
# qa_text / output_dir / generated_at）。
EVENT_REVISION_BACKUP = "revision_backup"
EVENT_REVISION_GENERATING = "revision_generating"

# 深化（工单 revise-deepen/04）的事件类型：deepening_start = LLM 按功能需求
# 填 TODO 预留区（分钟级）；verify_result = 编译验证结果就绪（done 载荷前）。
# 编译 / 修复环节复用 compile_start / fix_start 既有词表。
EVENT_DEEPENING_START = "deepening_start"
EVENT_VERIFY_RESULT = "verify_result"

# 任务推进（工单 task-progress/01）的事件类型：task_planning = 任务拆解
# LLM 调用开始（分钟级）；执行侧 task_executing（工单 02）+ 复用
# compile_start / fix_start / verify_result 既有词表。
EVENT_TASK_PLANNING = "task_planning"
EVENT_TASK_EXECUTING = "task_executing"

# 步骤报告（工单 stepwise-deepen/01）：task_reporting = LLM 正在总结本步
# 「做了什么 + 接下来你要做什么」（编译验证之后、轮次落盘之前，秒级阻塞
# 调用）；任务执行事件序列：task_executing → compile_start → fix_start →
# verify_result → task_reporting → done。
EVENT_TASK_REPORTING = "task_reporting"

# 参数速调（工单 param-tune/01）的事件类型：param_scanning = LLM 正在识别
# main.c 可调数值参数（分钟级阻塞调用）；param_result = 识别结果就绪（done
# 载荷前发射，载荷由 done 携带）；param_applying = 确定性改值 + 编译验证开始
# （零 LLM，改值本身瞬时——事件供前端切换「改值并编译中」状态）。端点事件
# 序列：scan = param_scanning → param_result → done；apply = param_applying →
# compile_start → fix_start → verify_result → done。
EVENT_PARAM_SCANNING = "param_scanning"
EVENT_PARAM_RESULT = "param_result"
EVENT_PARAM_APPLYING = "param_applying"

# 灵活修正（工单 idea-fix/01）：idea_analyzing = LLM 正在分析用户的新想法 /
# 问题（分钟级阻塞调用）；idea_result = 分析结果就绪（done 载荷前发射，
# 载荷由 done 携带）。分析端点事件序列：idea_analyzing → idea_result → done；
# 直接修正端点复用 compile_start / fix_start / verify_result / task_reporting
# 既有词表（不新增）。
EVENT_IDEA_ANALYZING = "idea_analyzing"
EVENT_IDEA_RESULT = "idea_result"

# 买件方案商量（工单 buy-discuss/01）：discuss_start = 一轮讨论的 LLM 调用
# 开始（分钟级阻塞）；端点同步返回（非 SSE），事件供观察面板消费。
EVENT_BUY_DISCUSS = "buy_discuss"

# 任务商量（工单 task-chat/02）：每卡「和 AI 商量」的一轮讨论 LLM 调用
# 开始（分钟级阻塞）；端点同步返回（非 SSE），事件供观察面板消费。
EVENT_TASK_DISCUSS = "task_discuss"

# 全局工程级商量（工单 idea-suite/01）：一轮全局讨论的 LLM 调用开始
# （分钟级阻塞）；端点同步返回（非 SSE），事件供观察面板消费。
EVENT_IDEA_CHAT = "idea_chat"

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

    每个事件类型只用字段子集：start（提炼端点）用 judgment_count /
    summary_batch_count / decide_batch_count（均由入口先算定）；start（推荐
    端点）用 stage（工单 ux-walkthrough-02/13：首个进度事件的中文阶段标签）；
    batch_start 用 phase / batch_index
    （批号，1 起）/ batch_count / paths（阶段 1 = 待判文件路径、阶段 2 = 摘要
    路径）；batch_done 用 phase / batch_index / processed_count（本阶段累计已
    处理文件数——前端直接显示"已读 X/115"，无需累加状态）；retry 用 phase /
    batch_index / retry_round（补问轮次，1 起——首次补问 = 1）/ missing_count
    （该轮要补问的缺失文件数）；phase_done 用 phase / file_count（本阶段文件数）；
    推荐收敛循环（工单 10）的 round 用 round / round_total、converged 用 round；
    编译错误修复（工单 compile-error-fix/01）的 parse_done 用 error_count /
    file_count / conflicts（该轮解析出的配置级冲突条目，工单 02：SysConfig
    Resource conflict——前端 parse_done 阶段就能给准话，不必先显示「AI 修复中」
    再改口；域层对纯冲突短路不调 LLM）、apply_result 用 file / line / status /
    reason；LLM telemetry 用
    llm_* 聚合字段与 llm_calls 明细（均为脱敏数值 / 枚举 / id，不含内容）。
    """

    type: str
    stage: str = ""  # start 事件的中文阶段标签（工单 ux-walkthrough-02/13，词表单源）
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
    conflicts: tuple[dict[str, Any], ...] = ()  # 编译错误修复 parse_done：配置级冲突条目
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
    warns: tuple[str, ...] = ()  # 推荐缓存命中（cache_hit）：参数指纹警告列表


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
