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

from dataclasses import dataclass
from typing import Callable

from .ccs import CcsProjectError
from .config import ConfigError
from .extraction import ExtractionError
from .fix_errors import FixError
from .generator import DuplicateFilePathError, GeneratorError
from .keil import KeilProjectError
from .library import LibraryError
from .llm import LLMError
from .master_store import MasterError
from .patchers import UnknownPlatformError
from .reference_library import ReferenceError
from .selection import ManualReferenceError, SelectionError
from .stage import StageError
from .topic_library import TopicError


@dataclass(frozen=True)
class _ErrorEntry:
    """error_to_http 表的一行：命中类型 → (HTTP 状态, 中文 message 生成)。"""

    exc_types: tuple[type[Exception], ...]
    status: int
    message: Callable[[Exception], str]


_ERROR_TABLE: tuple[_ErrorEntry, ...] = (
    # AI 服务失败：上游 LLM 不可用 / 超时 / 响应非法 → 502，message 带原因
    _ErrorEntry((LLMError,), 502, lambda exc: f"AI 服务调用失败：{exc}"),
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
            LibraryError,
            MasterError,
            SelectionError,
            ManualReferenceError,  # 手动选参考资料不存在 / 重复（工单 01）
            GeneratorError,
            DuplicateFilePathError,  # 跨模块同名文件（生成侧查重兜底，工单 gen-file-collision-gate/01）
            ConfigError,
            ReferenceError,
            TopicError,
            StageError,
        ),
        400,
        str,
    ),
    # 未知平台（用户可控输入打在生成流程，原为漏登记的 500）：400 中文，
    # message 带已注册平台清单，用户可直接修正重试
    _ErrorEntry((UnknownPlatformError,), 400, str),
)


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
    # 兜底：未登记异常 = 真 bug，500 大声失败（带类型名方便排查）
    return 500, f"服务器内部错误（{type(exc).__name__}）：{exc}"
