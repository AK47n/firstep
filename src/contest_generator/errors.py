"""错误映射：核心异常 → HTTP 状态与中文 message（全路由唯一出口，工单 C6）。

error_to_http 表唯一出处 = 本模块。webapp 不定义任何映射，只做取值
（_error_message → SSE 流内 error 事件）与包装（_error_response → 同步端点
HTTPException）——同一张表两端共用，未登记政策一致。

**未登记的异常 = 真 bug，兜底 500 大声失败（带类型名）**——旧实现兜底 400
会把真 bug 吞成业务失败（测试 raise_server_exceptions=False 时静默通过）。
新异常类型必须在此登记；登记遗漏由结构测试（tests/test_errors.py）反射枚举
包内全部异常类兜住——漏登从此是测试红，不是线上 500。刻意按 500 暴露的
白名单类也在结构测试里逐条注释理由。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable

from .ccs import CcsProjectError
from .compile_runner import CompileRunnerError
from .config import ConfigError
from .context_manifest import ContextError
from .deepen import DeepenError
from .delivery import DeliveryError
from .events import INTERNAL_ERROR_HINT
from .extraction import ExtractionError
from .fix_errors import FixError
from .flash import FlashError
from .generation_output import GenerationBusyError, GenerationConflictError
from .generator import (
    DuplicateFilePathError,
    ExtiLineConflictError,
    GeneratorError,
    PythonArtifactError,
    TimerConflictError,
    UartInstanceConflictError,
    UsartHandlerInMainError,
)
from .impact import ImpactError
from .keil import KeilProjectError
from .library import LibraryError
from .llm import (
    LLMError,
    LOCAL_LLM_LOAD_FAILED_MESSAGE,
    LOCAL_LLM_UNAVAILABLE_MESSAGE,
)
from .master_store import MasterError
from .patchers import UnknownPlatformError
from .pin_bindings import PinBindingError
from .recent_jobs import RecentStatusError
from .reference_library import ReferenceError
from .revision import RevisionError
from .selection import BuyError, ManualReferenceError, SelectionError
from .skeleton import SkeletonError
from .stage import StageError
from .task_progress import TaskError
from .topic_library import TopicError
from .vision import VisionError


@dataclass(frozen=True)
class _ErrorEntry:
    """error_to_http 表的一行：命中类型 → (HTTP 状态, 中文 message 生成)。"""

    exc_types: tuple[type[Exception], ...]
    status: int
    message: Callable[[Exception], str]


# LLM 失败人话化（工单 beginner-gap-closure/05）：error_to_http 表 502 行不再把
# 原始异常串（urlopen / URL / 响应体原文）透给用户——按错误类别重写为中文人话
# + 建议动作；原始消息保留在异常链（服务端日志 / 回滚排查可溯源），用户界面
# 只见人话。类别来源 = llm.LLMError.kind（network / rate_limit / client /
# parse，缺省 parse=业务解析失败）。
LLM_NETWORK_MESSAGE = (
    "AI 服务连接失败（网络不通 / 连接超时 / 服务暂时不可用）。"
    "请检查网络连接后重试；若多次失败，请稍后再试。"
)
LLM_RATE_LIMIT_MESSAGE = "AI 服务请求过于频繁——请等待片刻后重试"
LLM_CLIENT_MESSAGE = (
    "AI 服务拒绝了本次请求（可能是 API key 无效、账户余额不足或请求内容不被接受）。"
    "请在设置页核对 API key 与账户余额后重试。"
)


def _scrub_urls(text: str) -> str:
    """URL 去技术化（映射层兜底）：用户可见消息不再原样出现服务地址。"""
    return re.sub(r"https?://\S+", "<服务地址>", text)


def llm_error_message(exc: Exception) -> str:
    """LLM 失败 → 中文人话（按类别重写 + 建议动作）。

    network（连接失败 / 超时 / DNS / 网关 5xx）→ 检查网络建议；若为本地模型
    失联（RoutingLLM 包装附 LOCAL_LLM_* 提示），本地专属建议一并给出（别被
    通用网络建议覆盖——用户需知道「启动 Ollama / 清空本地模型配置」）。
    rate_limit（429）→ 等待建议（附 retry_after 秒数）；
    client（4xx）→ 核对 key 与余额建议；413（请求体过大）保留专属提示
    （检查赛题文本 / 文件数量——通用 key 建议对它是误导）；
    parse 及其它（含缺省 kind，AI 输出非法 / 业务失败）→ message 原样带出
    （保留「AI 服务调用失败：」前缀——存量文案契约不变，测试
    test_error_entry_contract_unchanged 钉住）。
    """
    message = str(exc)
    kind = exc.kind if isinstance(exc, LLMError) else "parse"
    if kind == "network":
        hint = next(
            (
                h for h in
                (LOCAL_LLM_UNAVAILABLE_MESSAGE, LOCAL_LLM_LOAD_FAILED_MESSAGE)
                if h in message
            ),
            None,
        )
        return LLM_NETWORK_MESSAGE + ("另：" + hint if hint else "")
    if kind == "rate_limit":
        retry = exc.retry_after if isinstance(exc, LLMError) else None
        suffix = f"（约 {math.ceil(retry)} 秒后）" if retry else ""
        return LLM_RATE_LIMIT_MESSAGE + suffix
    if kind == "client":
        if "413" in message:
            return (
                "AI 服务拒绝了本次请求：请求体过大——请检查赛题文本是否异常巨大，"
                "或减少导入工程的文件数量与单文件大小。"
            )
        return LLM_CLIENT_MESSAGE
    return "AI 服务调用失败：" + _scrub_urls(message)


_ERROR_TABLE: tuple[_ErrorEntry, ...] = (
    # AI 服务失败：上游 LLM 不可用 / 超时 / 响应非法 → 502。message 按错误
    # 类别人话化（工单 beginner-gap-closure/05）：网络 / 限流 / 客户端类重写为
    # 中文人话 + 建议动作，原始技术串（urlopen、URL、响应体）不再上界面；
    # 解析类（AI 输出非法）保留中文业务说明（「AI 服务调用失败：」前缀契约）。
    _ErrorEntry((LLMError,), 502, llm_error_message),
    # 工程文件（.uvprojx / .cproject）缺失、重复或不是合法 XML：业务失败
    # （旧工程 / AI 整合产物有问题），带中文 message，不裸 500
    _ErrorEntry((KeilProjectError, CcsProjectError), 400, str),
    # 文件系统失败（文件占用 / 权限 / 磁盘满）：本地工具场景用户可处理，带说明
    _ErrorEntry((OSError,), 400, lambda exc: f"文件操作失败：{exc}"),
    # 业务失败：message 原样带出（用户可按提示修正重试）
    _ErrorEntry(
        (
            ExtractionError,
            FixError,  # 编译错误修复（工单 compile-error-fix/01）：路径越界 / 白名单外扩展名拒绝
            CompileRunnerError,  # 自动编译（工单 autocompile-loop/01）：工具链缺失 / 工程结构异常
            LibraryError,
            MasterError,
            SelectionError,
            ManualReferenceError,  # 手动选参考资料不存在 / 重复（工单 01）
            GeneratorError,
            DuplicateFilePathError,  # 跨模块同名文件（生成侧查重兜底，工单 gen-file-collision-gate/01）
            PinBindingError,  # 引脚绑定载荷非法（工单 pin-board-config/02：键/角色/引脚/能力/槽位）
            SkeletonError,  # 骨架/自检冒烟（工单 route-orchestration-homing/01：main_mode 非法 / 冒烟守卫）
            TimerConflictError,  # 绑定 pwm TIM 实例撞骨架调度定时器（工单 pin-unlock-stm32/01）
            ExtiLineConflictError,  # 绑定 enc/exti 角色异口同线互斥（工单 pin-full-unlock/01）
            UartInstanceConflictError,  # 绑定 UART 实例撞未绑角色默认实例（工单 pin-full-unlock/02）
            UsartHandlerInMainError,  # main.c 定义 USARTx_IRQHandler 撞 isr.c 聚合（工单 pin-full-unlock/02）
            PythonArtifactError,  # Python 副产物写盘失败：模板缺失 / 跨模块 output 同名（工单 k230-vision-copilot/02）
            ConfigError,
            ReferenceError,
            TopicError,
            StageError,
            VisionError,  # 视觉通道失败（工单 vision-eyes/01）：未配置 / 网络 / 上游非法——调用方按降级政策决定阻断与否
            ContextError,  # 上下文清单损坏 / 形状非法 / 平台无法识别（工单 revise-deepen/01）
            ImpactError,  # 影响分析输出非法（工单 revise-deepen/02）：缺数组 / 未知 slug / 字段类型错
            RevisionError,  # 修订执行失败（工单 revise-deepen/03）：备份缺失 / 回滚目标非法
            DeepenError,  # 深化失败（工单 revise-deepen/04）：main.c 缺失 / 深化结果为空
            TaskError,  # 任务推进失败（工单 task-progress/01）：清单损坏 / 缺上下文 / 拆解输出畸形
            FlashError,  # 烧录失败（工单 flash-deploy/01）：平台未知 / 产物缺失 / 烧录工具缺失（带指引）
            DeliveryError,  # 交付失败（工单 delivery-suite/01）：输出目录缺失 / 平台未知
            BuyError,  # 买件方案商量请求非法（工单 buy-discuss/03）：缺题面 / 历史形状 / 角色词表外
            GenerationConflictError,  # 桌面同名工程已存在（工单 generate-conflict-guard/01）：不静默换名/覆盖
            RecentStatusError,  # 最近生成状态非法（工单 recent-jobs/01）：前端上报未知状态值
        ),
        400,
        str,
    ),
    # 同名工程生成进行中（工单 generate-conflict-guard/01）：HTTP 语义冲突，
    # 多标签页 / 并发请求同题只放一个进闸，其余等前一个完成再试
    _ErrorEntry((GenerationBusyError,), 409, str),
    # 未知平台（用户可控输入打在生成流程，原为漏登记的 500）：400 中文，
    # message 带已注册平台清单，用户可直接修正重试
    _ErrorEntry((UnknownPlatformError,), 400, str),
)


# 500 兜底反馈引导（工单 beginner-gap-closure/06）：常量单一出处 = events.py
# （叶子契约模块，errors 与 sse 双向可依赖防漂移），本模块顶部已导入。


def error_entry(exc: Exception) -> tuple[int, str]:
    """error_to_http 表（唯一实现）：核心异常 → (HTTP 状态, 中文 message)。

    已知异常：业务失败 → 400（message 原样带出）、LLM 服务失败 → 502、
    文件系统失败 → 400；**未登记的异常 = 真 bug，兜底 500 带类型名**——
    同步端点取状态码转 HTTPException、SSE 端点只取 message（HTTP 保持 200
    起流）——同一张表两端共用，未登记政策一致，改动只在此一处。
    """
    for entry in _ERROR_TABLE:
        if isinstance(exc, entry.exc_types):
            return entry.status, entry.message(exc)
    # 兜底：未登记异常 = 真 bug，500 大声失败（带类型名方便排查）+ 反馈引导
    # （工单 beginner-gap-closure/06：新手知道这是工具问题、能把信息反馈回来）
    return 500, f"服务器内部错误（{type(exc).__name__}）：{exc}" + INTERNAL_ERROR_HINT
