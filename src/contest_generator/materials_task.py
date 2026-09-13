"""资料库下载任务：后台线程 + 卷级断点 + 状态持久化（工单 materials-update/04）。

契约（spec `.scratch/materials-update/spec.md`）：
- `POST /api/update/materials/apply`：所选批次 slug 白名单（仅限 check 返回）→
  磁盘空间校验 → 启动后台线程 → 返回 `{started}`；
- `GET /api/update/materials/status`：
  `{state, parts: [{name, downloaded_bytes, total_bytes, ok}],
    total_downloaded_bytes, total_bytes, speed_bps, current_part_name,
    error, message}`；state ∈ idle|downloading|applying|done|failed|cancelled|
  partial（本次实现 applying/partial 由 apply 阶段（工单 05）切换，本模块
  先落地 idle/downloading/done/failed/cancelled + 预留字段）；
- `POST /api/update/materials/cancel`：置取消标记，任务在分卷边界停止；
  已完成卷标记保留（断点续传）。

卷级断点：每卷下载完成且 SHA256 校验通过 → 快照（materials-task.json）记
ok=True；任务重建（重启 / 失败重试）时读快照，ok 且本地文件存在且 sha 复
验一致 → 跳过下载。快照落盘节流（默认 2 秒），异常退出 / 进程重启后可恢复。

下载抗断（工单 resumable-download/03）：
- 缺省下载器 = `download_resume.resumable_download`（卷内断点 + 自动重试 + 退避可取消），
  经 `download_resume.as_task_downloader` 适配成既有的 `(url, dest, on_progress)` 注入缝；
- **下载异常保留半成品**（它就是断点），**校验失败才删**（重下也是坏的）；
- 半成品旁落 `.partial.json` 边车（**开跑就写**，取消 / 失败时兜底重写，成功时清），
  `run()` 启动时对得上就接着下，对不上就清掉从头下；
- 重试计数与「正在重试」摘要进内存态（`retry_count` / `last_retry_at` /
  `last_error_kind` 不落快照；`message` 走进行中的摘要）。
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator

from . import download_resume
from .download_resume import (
    DownloadCancelledError,
    resumable_download,
)
from .task_download import (
    download_and_verify,
    resolve_task_download,
    restore_snapshot_parts,
)
from .task_retry import TaskRetryMixin, TaskRetryState

SNAPSHOT_FILENAME = "materials-task.json"
SNAPSHOT_INTERVAL_SECONDS = 2.0


class TaskState(str, Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    APPLYING = "applying"  # 工单 05 使用；预留
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # 工单 05 使用：部分批次成功；预留


def _part_name(part: dict[str, Any], slug: str) -> str:
    """卷名：优先 zip_name，其次 URL 文件名，兜底 `<slug>.zip`。"""
    zip_name = str(part.get("zip_name") or "")
    if zip_name:
        return zip_name
    url = str(part.get("zip_url") or "")
    if url:
        return url.rsplit("/", 1)[-1] or f"{slug}.zip"
    return f"{slug}.zip"


def normalize_part(part: dict[str, Any]) -> dict[str, Any]:
    """check 响应 part → 任务内部 part（zip_name 可缺省；补默认字段）。"""
    return {
        "zip_name": str(part.get("zip_name") or ""),
        "zip_url": str(part.get("zip_url") or ""),
        "size_bytes": int(part.get("size_bytes") or 0),
        "sha256": str(part.get("sha256") or ""),
    }


def download_part(
    url: str, dest: Path, on_progress: Callable[[int], None]
) -> str:
    """流式下载单卷到 dest（256 KB 分块），返回 SHA256 hex。

    失败抛 urllib.error / OSError（调用方转失败态并清理半成品）。

    **它已经不在生产链路上**（工单 14 量清后按 `wontfix` 留下，别照着用它）：
    两条任务链路的缺省下载器自工单 03 起是 `download_resume.resumable_download`
    （卷内断点 + 截断判定 + 退避重试），而全仓对它的活口只剩**证据工具**——
    本特性探针的红基线复现与反证对照、以及完整包那次端到端演练脚本里的一处真调用。
    留它的理由正是那批工具要一份**冻结的「改之前」实现**当对照，按定义不该随产品演进。

    **别拿它当下载器**：它不校验 `Content-Length`，被截断也会自称成功
    （工单 01 探针实测到的原缺陷，正是它被换掉的原因）。
    """
    digest = hashlib.sha256()
    request = urllib.request.Request(url, headers={"User-Agent": "firstep-materials"})
    with urllib.request.urlopen(request, timeout=300) as response:
        with open(dest, "wb") as handle:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                on_progress(len(chunk))
    return digest.hexdigest()


@dataclass
class _PartState:
    """单卷下载态（内存 + 快照共用形状）。

    **没有 `from_dict`**（工单 12，与 `full_task._PartState` 完全同形）：快照读侧
    从来不重建这个对象——`_snapshot_pairs` 把 JSON 存档项当 dict 交给
    `task_download.restore_snapshot_parts`。原来那个 `from_dict` **全仓零调用点**
    （工单 12 用静态 grep 与「换成抛异常的炸弹」两手证明），故删。
    """

    name: str
    url: str = ""
    size: int = 0
    sha256: str = ""
    downloaded_bytes: int = 0
    ok: bool = False
    dest: str = ""  # 本地保存路径（快照恢复时校验存在与 sha）

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "size": self.size,
            "sha256": self.sha256,
            "downloaded_bytes": self.downloaded_bytes,
            "ok": self.ok,
            "dest": self.dest,
        }


@dataclass
class _BatchState:
    """一个批次的下载态（资料库这条链路独有：卷是**两层**组织的）。

    与 `_PartState` 同理没有 `from_dict`（工单 12：零调用点，快照读侧走 dict）。
    """

    slug: str
    name: str
    parts: list[_PartState] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"slug": self.slug, "name": self.name,
                "parts": [p.to_dict() for p in self.parts]}


class ApplyTask(TaskRetryMixin):
    """资料库增量下载任务（一任务一实例；webapp 模块级单例）。

    构造时不启动线程；run() 在调用方线程执行（端点用 daemon 线程包一层）。
    download 可注入（测试不碰网络）；快照持久化在 task_dir/materials-task.json。

    下载器解析顺序 = 实例属性 → 类属性（`monkeypatch.setattr(ApplyTask, "_download", …)`
    这个既有注入点）→ 缺省的可续下载，见 `_resolve_download`。
    """

    # 类属性 = 注入点的一部分（解析规则见 `task_download.resolve_task_download`）：
    # 缺省值本身就是可续下载。
    _download: Callable[..., Any] = staticmethod(resumable_download)

    def __init__(
        self,
        task_dir: Path,
        batches: list[dict[str, Any]],
        download: Callable[[str, Path, Callable[[int], None]], str] | None = None,
        snapshot_interval: float = SNAPSHOT_INTERVAL_SECONDS,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        self.task_dir = task_dir
        # 批次形状：check 响应的批次（slug/name/size_bytes/parts）→ 任务内部
        # _BatchState（parts 逐个 normalize：zip_name 可缺省）
        self.batches = [
            _BatchState(
                slug=str(b["slug"]),
                name=str(b.get("name") or b["slug"]),
                parts=[
                    _PartState(
                        name=_part_name(p, slug=str(b["slug"])),
                        url=str(p.get("zip_url") or ""),
                        size=int(p.get("size_bytes") or 0),
                        sha256=str(p.get("sha256") or ""),
                    )
                    for p in b.get("parts") or []
                ],
            )
            for b in batches
        ]
        if download is None:
            download = resumable_download
        self._download = download
        self._on_complete = on_complete
        self._snapshot_interval = snapshot_interval
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._last_snapshot = 0.0
        self._state = TaskState.IDLE
        self._error = ""
        self._current_part_name = ""
        self._started_at = time.time()
        self._last_ts = time.time()
        self._last_bytes = 0
        # 重试观测（内存态，不落快照）；字段与规则的单源在 `task_retry`（工单 09）
        self._retry = TaskRetryState()
        self._restore_snapshot()

    # -- 状态 --------------------------------------------------------------

    @property
    def state(self) -> TaskState:
        return self._state

    @property
    def error(self) -> str:
        return self._error

    @property
    def total_bytes(self) -> int:
        return sum(p.size for b in self.batches for p in b.parts)

    @property
    def downloaded_bytes(self) -> int:
        return sum(p.downloaded_bytes for b in self.batches for p in b.parts)

    def cancel(self) -> None:
        self._cancel.set()

    # -- 主流程 -------------------------------------------------------------

    def _resolve_download(self) -> tuple[Callable[..., Any], bool]:
        """→（这次要用的下载函数, 是不是缺省的可续下载）。

        解析顺序住在 `task_download.resolve_task_download`——与
        `full_task.FullDownloadTask._resolve_download` **同一份**（工单 11：
        两处原本是 7 行逐字相同的代码，账在 `measure-11-duplication.py`）。
        **壳为什么要留**：调用点（`download_and_verify(resolve=…)`）与判据
        `task._resolve_download()` 都按方法取用；壳只剩一句转发，规则不在这里。
        """
        return resolve_task_download(self)

    def _snapshot_pairs(self, data: dict[str, Any]) -> Iterator[tuple[_PartState, Any]]:
        """按 **slug + 卷名**把本次批次与上次快照对齐——本链路是**「批次 → 卷」两层**。

        这一层形状差异就是工单 11 划的缝：共享件（`restore_snapshot_parts`）只收
        「逐卷怎么恢复」，「卷怎么遍历」留在各链路。快照形状 =
        `{"batches": [{slug, parts: [{name, ok, dest, …}]}]}`：先按 slug 找批次
        （找不到就整批跳过），再在该批次内按卷名找存档项。
        """
        saved = {b["slug"]: b for b in data.get("batches") or []}
        for batch in self.batches:
            saved_batch = saved.get(batch.slug)
            if not saved_batch:
                continue
            saved_parts = {p["name"]: p for p in saved_batch.get("parts") or []}
            for part in batch.parts:
                yield part, saved_parts.get(part.name)

    def _restore_snapshot(self) -> None:
        """读上次快照：ok 卷校验本地文件 sha 一致 → 标记跳过（断点续传）。

        「逐卷恢复」那三条规则住在 `task_download.restore_snapshot_parts`（工单 11）；
        本方法只交代**本链路的卷怎么遍历**：资料库是「批次 → 卷」两层。
        """
        restore_snapshot_parts(
            self.task_dir / SNAPSHOT_FILENAME, self._snapshot_pairs
        )

    def run(self) -> None:
        """执行下载：逐批次逐卷 → 下载 + 校验 + 完成标记；分卷边界响应取消。

        全部卷就绪后调 `on_complete`（应用器挂钩：解压 / 备份 / 删除 / 写
        基线——应用器失败也记为该任务 failed，保留备份与中文错误）。
        取消（含下载器在退避中的取消）→ `cancelled`，半成品与边车留着。
        """
        if self._cancel.is_set():
            self._state = TaskState.CANCELLED
            self._write_snapshot(force=True)
            return
        self._state = TaskState.DOWNLOADING
        self._write_snapshot(force=True)
        try:
            for batch in self.batches:
                for part in batch.parts:
                    if self._cancel.is_set():
                        self._state = TaskState.CANCELLED
                        self._write_snapshot(force=True)
                        return
                    if part.ok:
                        continue
                    self._current_part_name = part.name
                    self.reset_retry_state()
                    self._download_one(part)
            self._retry.clear_message_and_window()
            # 下载全部完成 → 应用（挂钩抛错 = 失败态）
            if self._on_complete is not None:
                self._state = TaskState.APPLYING
                self._write_snapshot(force=True)
                self._current_part_name = ""
                self._on_complete()
            self._state = TaskState.DONE
            self._error = ""
        except DownloadCancelledError:
            self._state = TaskState.CANCELLED
            # 取消是终态：重试观测归零（**退避等待中被取消**那条路尤其要清——
            # 那时 retry_count / error_kind 已被上一次失败填过，不清就会把用户自己
            # 点的取消报成「网络失败」）
            self._retry.reset_for_cancelled()
        except Exception as exc:
            was_applying = self._state is TaskState.APPLYING
            self._retry.clear_message_and_window()
            if was_applying:
                self._state = TaskState.FAILED
                self._error = f"应用失败：{exc}"
            else:
                self._state = TaskState.FAILED
                self._error = f"下载失败（卷 {self._current_part_name}）：{exc}"
            # 应用阶段的失败（解压 / 备份 / 磁盘写入）既不是 network 也不是 verify，
            # spec 的词表里没有格子 → 留空，前端走通用话术（别讲成「点重试会接着下」）
            self.last_error_kind = (
                "" if was_applying else download_resume.error_kind(exc)
            )
        self._write_snapshot(force=True)

    def _download_one(self, part: _PartState) -> None:
        """下一卷并校验。

        「一次分卷下载」的**动作序列**住在 `task_download.download_and_verify`——
        两条链路同一份（工单 10）。本方法只剩**本链路自己的两件事**：
        这卷落在哪（`materials/` 目录，文件名口径见下），以及成功之后的卷级记账与快照。

        文件名 = part.name（即 zip_name / URL 尾段），与应用器按
        manifest parts[].zip_name 找文件的口径一致（勿加 slug 前缀，
        否则双缀导致应用器找不到）。
        """
        dest = self.task_dir / "materials" / part.name
        download_and_verify(
            part, dest,
            retry=self._retry, lock=self._lock, cancel=self._cancel,
            resolve=self._resolve_download,
        )
        self._write_snapshot(force=False)

    def _retry_state(self) -> TaskRetryState:
        """`TaskRetryMixin` 要的取值入口（字段与规则都住在 `task_retry`）。"""
        return self._retry

    def _write_snapshot(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_snapshot < self._snapshot_interval:
            return
        self._last_snapshot = now
        self.task_dir.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "state": self._state.value,
            "started_at": self._started_at,
            "batches": [b.to_dict() for b in self.batches],
        }
        (self.task_dir / SNAPSHOT_FILENAME).write_text(
            json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _snapshot_path() -> str:
        return SNAPSHOT_FILENAME


# ---------------------------------------------------------------------------
# 状态视图（status 端点数据）
# ---------------------------------------------------------------------------


def task_status(task: ApplyTask | None) -> dict[str, Any]:
    """任务 → status 响应（任务 None = idle 空态）。

    speed_bps 为瞬时估算：最近一窗的字节增速（窗口 = 上次 status 调用至今；
    首调返回 0，前端显示「—」）。
    """
    if task is None:
        return {
            "state": TaskState.IDLE.value,
            "parts": [],
            "total_downloaded_bytes": 0,
            "total_bytes": 0,
            "speed_bps": 0,
            "current_part_name": "",
            "error": "",
            "message": "",
            # 空态也要在场（前端零分支）
            "retry_count": 0,
            "retrying": False,
            "error_kind": "",
            "resume_percent": -1,
        }
    parts = [
        {
            "name": p.name,
            "downloaded_bytes": p.downloaded_bytes,
            "total_bytes": p.size,
            "ok": p.ok,
        }
        for b in task.batches for p in b.parts
    ]
    current = task.downloaded_bytes
    now = time.time()
    delta_t = now - task._last_ts
    delta_b = current - task._last_bytes
    task._last_ts, task._last_bytes = now, current
    speed = int(delta_b / delta_t) if delta_t > 0 else 0
    return {
        "state": task.state.value,
        "parts": parts,
        "total_downloaded_bytes": current,
        "total_bytes": task.total_bytes,
        "speed_bps": speed,
        "current_part_name": task._current_part_name,
        "error": task.error,
        "message": task.message,
        # 重试观测（工单 04 的契约面；工单 05 起前端直接消费，不再解析文案）
        "retry_count": int(task.retry_count),
        "retrying": bool(task.retrying),
        "error_kind": str(task.last_error_kind),
        "resume_percent": int(task.resume_percent),
    }


def write_task_snapshot(task: ApplyTask) -> None:
    """强制落盘（测试与 shutdown 钩子用）。"""
    task._write_snapshot(force=True)
