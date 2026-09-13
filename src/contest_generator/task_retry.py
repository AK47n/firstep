"""任务层共享的「重试观测」（工单 resumable-download/09）。

**为什么有这个模块**：完整包（`full_task`）与资料库（`materials_task`）两条链路
各自维护同一套重试观测字段与同一套回调——**重复的不是几行字，是规则**：

| 规则 | 漂过的证据 |
|---|---|
| 退避开窗：`retrying=True` + 摘要只说原因 | 工单 04 修「0 宽窗口」时两边都要改 |
| 退避关窗：`retrying=False` **且**摘要清空 | 工单 04 评审：只清一个会留下自相矛盾的状态组合 |
| 取消时把重试观测归零 | 工单 04 评审：**两边都漏了**，各补一次 |
| 换卷复位 | `test_retry_state_resets_per_part` 两边各一条 |

「两边各改一次、漏一边就出 bug」正是这个形状最贵的地方。本模块把它压成一处。

**为什么不塞进 `download_resume`**：下载域**不许知道状态面字段名**——
`tests/test_download_status_surface.py::test_download_resume_module_has_no_status_knowledge`
是这个方向的守卫（工单 04 立的）。本模块是**桥**：字段与回执归这里，
「退避几秒」「怎么措辞」「怎么分类」仍归下载域（`retry_delay` / `retry_message` /
`retry_resume_percent` / `error_kind`）。

**状态面契约一字不改**：`TaskRetryMixin` 把六个字段名原样暴露成属性，所以
`full_task_status` / `task_status` 的投影、以及既有测试里
`task.retry_count = 5` 这类直接注入，行为都不变——外部看不出这次重排。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from . import download_resume

T = TypeVar("T")


@dataclass
class TaskRetryState:
    """一卷的自动重试观测（内存态，**不落快照**：重启后从 0 重新计更诚实）。

    字段名 = 状态面字段名的单一出处（`retry_count` / `last_retry_at` /
    `last_error_kind` / `retrying` / `resume_percent` / `message`）。同名属性由
    `TaskRetryMixin` 暴露给任务对象，故调用方看不出这次重排。
    """

    # 「本卷」累计自动重试次数（spec 原话：换卷即清零）
    retry_count: int = 0
    # 最近一次进入退避的时刻（unix 秒；0 = 从没重试过）
    last_retry_at: float = 0.0
    # 分类词表单源在下载域（`download_resume.error_kind`），这里只存结果
    last_error_kind: str = ""
    # 退避等待中（窗口 = `before_retry` 开 → 退避结束 `before_attempt` 关）
    retrying: bool = False
    # 本轮从多少百分比接着下（-1 = 不知道 / 不适用）
    resume_percent: int = -1
    # 进行中的摘要（只说原因）；终态清空（终态原因只走 `error`）
    message: str = ""

    # -- 复位 ---------------------------------------------------------------

    def reset(self) -> None:
        """换卷复位：六个字段一起回到初值。

        为什么要一条方法而不是六个赋值：`test_retry_state_resets_per_part` 钉的
        语义是「上一卷的重试观测不许漏到下一卷」——漏掉任何一个字段都是同一个 bug，
        而散着写就必然有人漏（工单 04 评审已经在「取消」那条路上抓到过一次）。
        """
        self.retry_count = 0
        self.last_retry_at = 0.0
        self.last_error_kind = ""
        self.retrying = False
        self.resume_percent = -1
        self.message = ""

    def reset_for_cancelled(self) -> None:
        """取消是终态：重试观测一并归零。

        **退避等待中被取消**那条路尤其要清——那时 `retry_count` / `last_error_kind`
        已被上一次失败填过，不清就会在取消态里报出「重试 1 次 / 网络错误」，
        前端据此把用户自己点的取消讲成网络故障（spec 的词表里取消态的分类是空串）。

        **为什么不清 `resume_percent` 与 `last_retry_at`**（与 `reset()` 不对称，是有意的）：
        取消态的状态面里 `retrying` 为假，前端只在「正在重试」那一支读 `resume_percent`
        （`fx/core.js`），所以它对用户不可见；`last_retry_at` 则压根不进状态投影
        （它是给排障用的观测值，「上次重试发生在几点」在取消后仍然是真的）。
        **这一条是对既有行为的如实记录，不是本单改出来的**：工单 04 定的取消路径本来
        就只清这四个字段。哪天要让取消态也把这两个清干净，那是行为变更，得配判据、另行开单。
        """
        self.message = ""
        self.retrying = False
        self.retry_count = 0
        self.last_error_kind = ""

    def clear_message(self) -> None:
        """清掉进行中的摘要（成功收尾、卷下载完都走这条）。"""
        self.message = ""

    def clear_message_and_window(self) -> None:
        """清摘要 + 关「正在重试」窗口（失败收尾走这条）。"""
        self.message = ""
        self.retrying = False

    # -- 窗口 ---------------------------------------------------------------

    def close_window(self) -> None:
        """退避等待结束、马上要真的重连：关窗。

        只清 `retrying` 不清 `message` 会留下「正在重试第 2 次」挂满剩下整段下载
        （自相矛盾的状态组合，前端只剩解析文案一条路——而 spec 明禁解析文案）。
        """
        self.retrying = False
        self.message = ""

    def note_retry(
        self,
        attempt: int,
        exc: BaseException,
        on_disk: int,
        restarted: bool,
        part_size: int,
        *,
        now: float | None = None,
    ) -> None:
        """`before_retry` 回调：如实计数 + 把「正在重试」拆成三个字段。

        `message`（原因）/ `retry_count`（第几次）/ `resume_percent`（从多少接着下）
        ——**分开就是给前端拼的**：前端不再需要从任何文案里抠信息。

        `restarted=True`（服务器没让我们接上）→ 半成品已被丢弃，本轮起点**就是 0%**
        （说 0 才是如实；说 -1「不知道」会让界面拿不到「从 0 重新下」这个事实）。
        """
        self.retry_count = int(attempt)
        self.last_retry_at = time.time() if now is None else float(now)
        self.last_error_kind = download_resume.error_kind(exc)
        self.resume_percent = (
            0 if restarted
            else download_resume.retry_resume_percent(on_disk, part_size)
        )
        self.retrying = True      # 退避等待中（退避结束时由 close_window 清）
        self.message = download_resume.retry_message(
            download_resume.retry_reason(exc)
        )

    # -- 回调工厂 -----------------------------------------------------------

    def on_retry(self, part: T) -> Callable[..., None]:
        """`before_retry` 的绑定回调（`part` 提供总长，用于算百分比）。"""

        def cb(attempt: int, exc: BaseException, on_disk: int, restarted: bool) -> None:
            self.note_retry(attempt, exc, on_disk, restarted,
                            part.size)  # type: ignore[attr-defined]

        return cb


def part_progress_callbacks(
    part: T, *, lock: threading.Lock
) -> tuple[Callable[[int], None], Callable[[int], None]]:
    """→（`on_progress`, `on_start`）两个进度回调（两条链路共用，工单 09）。

    **累计量 = 本轮尝试的落盘起点 + 本次连接读到的字节**，起点由下载器每轮开始时报一次。
    不能拿「调用前盘上有多少」当基准：服务器忽略 Range 时会**丢弃半成品从 0 重下**，
    那时起点是 0 而不是盘上原有字节，拿旧基准会把已经扔掉的字节继续算进进度
    （实测能算出超过卷大小的进度——工单 03 双轴评审修过这个坑）。

    锁由调用方传（任务对象自己的那把）：`part.downloaded_bytes` 也由 `status` 侧读，
    两条链路的并发纪律一致。
    """

    def on_progress(nbytes: int) -> None:
        with lock:
            part.downloaded_bytes += nbytes   # type: ignore[attr-defined]

    def on_start(offset: int) -> None:
        with lock:
            part.downloaded_bytes = max(0, int(offset))   # type: ignore[attr-defined]

    return on_progress, on_start


class TaskRetryMixin:
    """把 `TaskRetryState` 的字段名原样暴露给任务对象（状态面契约零改动）。

    继承它就得到：`retry_count` / `last_retry_at` / `last_error_kind` / `retrying` /
    `resume_percent` / `message` 六个可读可写属性（既有测试直接给它们赋值做脏状态注入，
    故写访问也必须保留），外加共享的回调与复位方法。

    子类必须实现 `_retry_state()`（返回自己那个 `TaskRetryState`）。
    为什么用「返回值」而不是存成实例属性：两条链路的 `__init__` 各自建状态，
    mixin 不该假设它们怎么建（也避免与子类已有的 `__init__` 抢初始化顺序）。
    """

    def _retry_state(self) -> TaskRetryState:
        raise NotImplementedError("子类必须返回自己的 TaskRetryState")

    # -- 字段投影（读写都透传；名字 = 状态面契约）----------------------------

    @property
    def retry_count(self) -> int:
        return self._retry_state().retry_count

    @retry_count.setter
    def retry_count(self, value: int) -> None:
        self._retry_state().retry_count = value

    @property
    def last_retry_at(self) -> float:
        return self._retry_state().last_retry_at

    @last_retry_at.setter
    def last_retry_at(self, value: float) -> None:
        self._retry_state().last_retry_at = value

    @property
    def last_error_kind(self) -> str:
        return self._retry_state().last_error_kind

    @last_error_kind.setter
    def last_error_kind(self, value: str) -> None:
        self._retry_state().last_error_kind = value

    @property
    def retrying(self) -> bool:
        return self._retry_state().retrying

    @retrying.setter
    def retrying(self, value: bool) -> None:
        self._retry_state().retrying = bool(value)

    @property
    def resume_percent(self) -> int:
        return self._retry_state().resume_percent

    @resume_percent.setter
    def resume_percent(self, value: int) -> None:
        self._retry_state().resume_percent = value

    @property
    def message(self) -> str:
        return self._retry_state().message

    @message.setter
    def message(self, value: str) -> None:
        self._retry_state().message = value

    # -- 共享行为（两条链路同一份实现）--------------------------------------

    def reset_retry_state(self) -> None:
        """换卷复位（`run()` 的卷循环开头调）。"""
        self._retry_state().reset()

    def close_retry_window(self) -> None:
        """`before_attempt` 回调：退避结束、马上要重连时关窗。"""
        self._retry_state().close_window()

    def retry_callbacks(self, part: T) -> dict[str, Any]:
        """交给 `as_task_downloader` 的两个重试观测回调（一次装配好）。

        → `{"before_retry": …, "before_attempt": …}`
        （`on_start` 是进度基准回调，归 `part_progress_callbacks`，不在这里。）
        """
        return {
            "before_retry": self._retry_state().on_retry(part),
            "before_attempt": self.close_retry_window,
        }

    # -- 兼容别名（**只给既有测试的私有注入点**，新代码用上面的公开名）--------
    #
    # 为什么留着：工单 09 的验收线是「零行为变化、既有判据一个断言都不改」。而既有测试
    # （工单 03/04 立的）有几处直接调私有回调、读写私有字段——它们是**判据**，不是产品
    # 接口。为了让重排不动判据，这里把四个私有名原样接出来。
    #
    # 取舍如实记：这与「值对象是唯一载体」的意图有张力（对外多了一层间接）。
    # 接受它的理由 = 判据的价值高于内部形状的纯度；**新代码不许用这四个名字**。
    # 要清理的话是独立一步（连测试一起改），不该混在纯重排里做。

    @property
    def _message(self) -> str:
        return self._retry_state().message

    @_message.setter
    def _message(self, value: str) -> None:
        self._retry_state().message = value

    @property
    def _retrying(self) -> bool:
        return self._retry_state().retrying

    @_retrying.setter
    def _retrying(self, value: bool) -> None:
        self._retry_state().retrying = bool(value)

    @property
    def _resume_percent(self) -> int:
        return self._retry_state().resume_percent

    @_resume_percent.setter
    def _resume_percent(self, value: int) -> None:
        self._retry_state().resume_percent = value

    def _on_retry(self, part: T) -> Callable[..., None]:
        """兼容别名 → `TaskRetryState.on_retry`。"""
        return self._retry_state().on_retry(part)

    def _on_retry_window_closed(self) -> None:
        """兼容别名 → `close_retry_window`（既有测试直接调它来合成「关窗」那一刻）。"""
        self.close_retry_window()

    def _on_progress(self, part: T) -> Callable[[int], None]:
        """兼容别名 → `part_progress_callbacks` 的第一个（锁用子类那把）。"""
        return part_progress_callbacks(part, lock=self._lock)[0]  # type: ignore[attr-defined]

    def _on_attempt_start(self, part: T) -> Callable[[int], None]:
        """兼容别名 → `part_progress_callbacks` 的第二个。"""
        return part_progress_callbacks(part, lock=self._lock)[1]  # type: ignore[attr-defined]
