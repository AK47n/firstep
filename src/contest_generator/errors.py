"""错误映射：核心异常 → HTTP 状态与中文 message（全路由唯一出口，工单 C6）。

error_to_http 表唯一出处 = 本模块。webapp 不定义任何映射，只做取值
（_error_message → SSE 流内 error 事件）与包装（_error_response → 同步端点
HTTPException）——同一张表两端共用，未登记政策一致。

**未登记的异常 = 真 bug，兜底 500 大声失败（类型名只进日志，用户只见
人话 + 反馈引导，工单 ux-walkthrough-02/10）**——旧实现兜底 400
会把真 bug 吞成业务失败（测试 raise_server_exceptions=False 时静默通过）。
新异常类型必须在此登记；登记遗漏由结构测试（tests/test_errors.py）反射枚举
包内全部异常类兜住——漏登从此是测试红，不是线上 500。刻意按 500 暴露的
白名单类也在结构测试里逐条注释理由。
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Callable

from .ccs import CcsProjectError
from .codeview import CodeViewConflictError, CodeViewError
from .compile_runner import CompileRunnerError
from .config import ConfigError
from .context_manifest import ContextError
from .deepen import DeepenError
from .delivery import DeliveryError
from .events import INTERNAL_ERROR_HINT
from .extraction import ExtractionError
from .fix_errors import FixError
from .flash import FlashError
from .generation_output import BackupRestoreError, GenerationBusyError, GenerationConflictError
from .generator import (
    DuplicateFilePathError,
    ExclusivePairConflictError,
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
    ERROR_KIND_CLIENT,
    ERROR_KIND_DOMAIN,
    ERROR_KIND_NETWORK,
    ERROR_KIND_PARSE,
    ERROR_KIND_RATE_LIMIT,
    LLMError,
    LOCAL_LLM_LOAD_FAILED_MESSAGE,
    LOCAL_LLM_UNAVAILABLE_MESSAGE,
)
from .materials_apply import MaterialApplyError
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
    # 入参标 Any（mypy 基线遗留）：各行的生成函数按自己的异常类型收窄
    # （os_error_message 收 OSError 再 getattr winerror/errno），表里存成
    # 统一的 Exception 签名会让它们被判为不兼容；调用点只会传该行匹配到的
    # 异常实例，收窄由各生成函数自己负责。
    message: Callable[[Any], str]


_LOG = logging.getLogger(__name__)

# 文件系统错误人话化（工单 ux-walkthrough-02/10）：OSError 按 winerror / errno
# 分派中文文案与修复步骤——不再把裸系统串（WinError 32 等）透给用户。
OS_ERROR_LOCKED_MESSAGE = (
    "文件操作失败：文件正被其它程序占用（常见：Keil / CCS 正打开着工程文件）。"
    "请关闭占用程序后重试；如仍失败，请重启电脑后再操作。"
)
OS_ERROR_DISK_FULL_MESSAGE = (
    "文件操作失败：磁盘空间不足。请清理磁盘空间（或换到更大分区）后重试。"
)
OS_ERROR_PERMISSION_MESSAGE = (
    "文件操作失败：没有写入权限（文件可能只读，或所在目录受保护）。"
    "请检查文件 / 目录权限后重试。"
)
OS_ERROR_GENERIC_MESSAGE = (
    "文件操作失败：系统返回了未识别的文件系统错误。"
    "请检查磁盘与文件状态（占用 / 权限 / 空间）后重试；问题持续请反馈。"
)


def os_error_message(exc: OSError) -> str:
    """OSError → 中文人话（工单 ux-walkthrough-02/10）：winerror 32（共用冲突 /
    文件被占用）、errno 28（磁盘满）、PermissionError / winerror 5（无权限）
    各有专属文案；未映射的给一般性说明（不再裸 str(exc)）。"""
    win = getattr(exc, "winerror", None)
    errno_ = getattr(exc, "errno", None)
    if win == 32:
        return OS_ERROR_LOCKED_MESSAGE
    if isinstance(exc, PermissionError) or win == 5:
        return OS_ERROR_PERMISSION_MESSAGE
    if errno_ == 28:
        return OS_ERROR_DISK_FULL_MESSAGE
    return OS_ERROR_GENERIC_MESSAGE


# LLM 失败人话化（工单 beginner-gap-closure/05）：error_to_http 表 502 行不再把
# 原始异常串（urlopen / URL / 响应体原文）透给用户——按错误类别重写为中文人话
# + 建议动作；原始消息保留在异常链（服务端日志 / 回滚排查可溯源），用户界面
# 只见人话。类别来源 = llm.LLMError.kind（network / rate_limit / client /
# domain / parse，缺省 parse=业务解析失败）；**分支按 kind 常量分派**
# （ERROR_KIND_DOMAIN 等），与 llm 侧单源——不靠字符串猜语义。
LLM_NETWORK_MESSAGE = (
    "AI 服务连接失败（网络不通 / 连接超时 / 服务暂时不可用）。"
    "请检查网络连接后重试；若多次失败，请稍后再试。"
)
LLM_NETWORK_TIMEOUT_MESSAGE = (
    "AI 服务连接超时（网络延迟高或服务响应慢）——请检查网络后重试；"
    "若网络正常，可能是服务繁忙，请稍后再试。"
)
LLM_NETWORK_DNS_MESSAGE = (
    "AI 服务地址无法解析（DNS 失败）——请检查网络连接与 DNS 配置后重试。"
)
LLM_NETWORK_TLS_MESSAGE = (
    "AI 服务证书校验失败——请检查系统时间是否准确、网络环境（代理/安全软件）"
    "是否拦截后重试。"
)
LLM_RATE_LIMIT_MESSAGE = "AI 服务请求过于频繁——请等待片刻后重试"
LLM_CLIENT_MESSAGE = (
    "AI 服务拒绝了本次请求（可能是 API key 无效、账户余额不足或请求内容不被接受）。"
    "请在设置页核对 API key 与账户余额后重试。"
)
# 本地域判决（kind=domain，工单 real-acceptance/03）：不是上游拒绝，而是产品
# 自己判的（selection.build_module_selection 的域拒绝——模型输出与库内事实
# 冲突：给非多实例模块带 instances、推荐库中不存在的模块、库外建议的硬件名
# 不在硬件词表…）。这类失败**必须保留真实理由**：用「API key / 余额」话术
# 描述它是指错方向的误导（第十六轮真机 14 轮推荐里 9 轮栽在这，用户被指去
# 查 key，而真因是模型手滑）。前半句说明真实冲突，括号里明说"不是凭据 /
# 账户问题" + 可操作引导。
#
# 只说「已自动重试」不说次数（评审整改）：次数与 DOMAIN_RETRY_LIMIT 保持
# 一致靠格式化容易写错（原实现用 DOMAIN_RETRY_LIMIT + 1 说成"重试 2 次"，
# 而用户感知的"重试"是额外那一次 = 1 次），且将来若有调用方不开 domain_retry
# 就会被谎报。硬编码只会更糟——文案不承载可变量。
LLM_DOMAIN_MESSAGE_SUFFIX = (
    "（这是 AI 输出与库内容对不上，不是登录凭据或账户问题——"
    "系统已自动重试仍不通过。请再点一次推荐；若反复失败，"
    "可调整题面措辞或在赛题答疑里补充说明。）"
)


def _scrub_urls(text: str) -> str:
    """URL 去技术化（映射层兜底）：用户可见消息不再原样出现服务地址。"""
    return re.sub(r"https?://\S+", "<服务地址>", text)


def _llm_network_message(exc: Exception) -> str:
    """网络类信号细分（spec 实现决策「区分连接 / 超时 / DNS / 证书」）：按
    原始消息特征选对应人话——技术串（urlopen / gaierror / CERTIFICATE_…
    等）只作判别依据，绝不透出；识别不出 → 通用连接失败文案。"""
    raw = str(exc)
    if re.search(r"timed?\s*out|timeout|超时", raw, re.IGNORECASE):
        return LLM_NETWORK_TIMEOUT_MESSAGE
    if re.search(r"gaierror|getaddrinfo|unknown host|dns|无法解析", raw, re.IGNORECASE):
        return LLM_NETWORK_DNS_MESSAGE
    if re.search(r"certificate|certif|ssl|tls", raw, re.IGNORECASE):
        return LLM_NETWORK_TLS_MESSAGE
    return LLM_NETWORK_MESSAGE


def llm_error_message(exc: Exception) -> str:
    """LLM 失败 → 中文人话（按类别重写 + 建议动作）。

    network（连接失败 / 超时 / DNS / 网关 5xx）→ 检查网络建议；若为本地模型
    失联（RoutingLLM 包装附 LOCAL_LLM_* 提示），本地专属建议一并给出（别被
    通用网络建议覆盖——用户需知道「启动 Ollama / 清空本地模型配置」）。
    rate_limit（429）→ 等待建议（附 retry_after 秒数）；
    domain（本地域判决，工单 real-acceptance/03）→ **message 原文保留**
    （真实理由，如「模块 oled 不支持多实例，不能带 instances」）+ 一句
    「不是 key / 余额问题」的引导——本产品自己判的失败与上游拒绝是两回事，
    通用话术只适用于后者；
    client（上游 HTTP 4xx）→ 核对 key 与余额建议；413（请求体过大）保留专属
    提示（检查赛题文本 / 文件数量——通用 key 建议对它是误导）；
    parse 及其它（含缺省 kind，AI 输出非法 / 业务失败）→ message 原样带出
    （保留「AI 服务调用失败：」前缀——存量文案契约不变，测试
    test_error_entry_contract_unchanged 钉住）。
    """
    message = str(exc)
    kind = exc.kind if isinstance(exc, LLMError) else ERROR_KIND_PARSE
    if kind == ERROR_KIND_NETWORK:
        hint = next(
            (
                h for h in
                (LOCAL_LLM_UNAVAILABLE_MESSAGE, LOCAL_LLM_LOAD_FAILED_MESSAGE)
                if h in message
            ),
            None,
        )
        return _llm_network_message(exc) + ("另：" + hint if hint else "")
    if kind == ERROR_KIND_RATE_LIMIT:
        retry = exc.retry_after if isinstance(exc, LLMError) else None
        suffix = f"（约 {math.ceil(retry)} 秒后）" if retry else ""
        return LLM_RATE_LIMIT_MESSAGE + suffix
    if kind == ERROR_KIND_DOMAIN:
        # 域拒绝保留理由原文（判据：errors.py 能区分「上游 HTTP 4xx」与
        # 「本地域判决」，不靠字符串猜——两条分支吃的是不同 kind 常量）
        return (
            "AI 生成的推荐内容与库内事实冲突："
            + _scrub_urls(message)
            + LLM_DOMAIN_MESSAGE_SUFFIX
        )
    if kind == ERROR_KIND_CLIENT:
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
    # 文件系统失败（文件占用 / 权限 / 磁盘满）：本地工具场景用户可处理，
    # 按 errno/winerror 分派中文人话（工单 ux-walkthrough-02/10），不裸透系统串
    _ErrorEntry((OSError,), 400, os_error_message),
    # 代码编辑器保存冲突（工单 code-viewer-editor/01）：磁盘文件被外部修改
    # （任务 / 深化写盘 / 外部 IDE），base_mtime_ns 与磁盘不一致——不静默
    # 覆盖别人的写入，前端弹「覆盖 / 重载 / 取消」模态。**必须排在 400 大
    # 元组之前**：CodeViewConflictError 继承 CodeViewError，error_entry 按序
    # isinstance 匹配，排后会被 CodeViewError 的 400 表项先吞成 400。
    _ErrorEntry((CodeViewConflictError,), 409, str),
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
            ExclusivePairConflictError,  # 硬互斥对同选（同一外设单消费者，工单 zigbee-link/02）
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
            BackupRestoreError,  # 覆盖备份恢复失败（工单 ux-walkthrough-02/03）：目标名不合法 / 备份缺失 / 目标已存在
            RecentStatusError,  # 最近生成状态非法（工单 recent-jobs/01）：前端上报未知状态值
            CodeViewError,  # 代码查看器失败（工单 code-viewer/01-02）：目录不存在 / 路径穿越 / 二进制 / 超限
            MaterialApplyError,  # 资料库应用失败（工单 materials-update/05）：zip slip / 备份失败 / 增量包缺失
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
    文件系统失败 → 400；**未登记的异常 = 真 bug，兜底 500 去类型名（类型名
    只进日志，用户只见人话 + 反馈引导）**——
    同步端点取状态码转 HTTPException、SSE 端点只取 message（HTTP 保持 200
    起流）——同一张表两端共用，未登记政策一致，改动只在此一处。
    """
    for entry in _ERROR_TABLE:
        if isinstance(exc, entry.exc_types):
            return entry.status, entry.message(exc)
    # 兜底：未登记异常 = 真 bug，500 大声失败——类型名只进日志（排查可溯源），
    # 用户界面只见「服务器内部错误」+ 反馈引导（工单 ux-walkthrough-02/10：
    # 类型名是工程黑话，对用户无用）
    _LOG.error("未登记异常（用户可见 500 兜底）：%r", exc)
    return 500, "服务器内部错误：" + INTERNAL_ERROR_HINT
