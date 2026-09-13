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
from typing import Any, Callable

from . import download_resume
from .download_resume import (
    DownloadCancelledError,
    DownloadResult,
    DownloadVerifyError,
    resumable_download,
)

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
    """单卷下载态（内存 + 快照共用形状）。"""

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

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "_PartState":
        return _PartState(
            name=str(data.get("name") or ""),
            url=str(data.get("url") or ""),
            size=int(data.get("size") or 0),
            sha256=str(data.get("sha256") or ""),
            downloaded_bytes=int(data.get("downloaded_bytes") or 0),
            ok=bool(data.get("ok")),
            dest=str(data.get("dest") or ""),
        )


@dataclass
class _BatchState:
    slug: str
    name: str
    parts: list[_PartState] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"slug": self.slug, "name": self.name,
                "parts": [p.to_dict() for p in self.parts]}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "_BatchState":
        return _BatchState(
            slug=str(data.get("slug") or ""),
            name=str(data.get("name") or ""),
            parts=[_PartState.from_dict(p) for p in data.get("parts") or []],
        )


class ApplyTask:
    """资料库增量下载任务（一任务一实例；webapp 模块级单例）。

    构造时不启动线程；run() 在调用方线程执行（端点用 daemon 线程包一层）。
    download 可注入（测试不碰网络）；快照持久化在 task_dir/materials-task.json。

    下载器解析顺序 = 实例属性 → 类属性（`monkeypatch.setattr(ApplyTask, "_download", …)`
    这个既有注入点）→ 缺省的可续下载，见 `_resolve_download`。
    """

    # 类属性 = 注入点的一部分（见 `_resolve_download`）：缺省值本身就是可续下载。
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
        # 重试观测（内存态，不落快照）
        self.retry_count = 0
        self.last_retry_at = 0.0
        self.last_error_kind = ""
        self._retrying = False
        self._resume_percent = -1
        self._message = ""
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

        与 `full_task.FullDownloadTask._resolve_download` 同形（两文件故意对称，
        对照阅读）。第二个返回值交给 `as_task_downloader`：缺省实现无条件吃
        `expected_size` / `expected_sha256` / `cancel` / `before_retry`，注入的下载器
        仍按既有的三参形态调用。
        """
        instance = self.__dict__.get("_download")
        if instance is None or instance is resumable_download:
            chosen = getattr(type(self), "_download", None) or resumable_download
            return chosen, chosen is resumable_download
        return instance, False

    def _restore_snapshot(self) -> None:
        """读上次快照：ok 卷校验本地文件 sha 一致 → 标记跳过（断点续传）。"""
        snapshot = self.task_dir / SNAPSHOT_FILENAME
        if not snapshot.is_file():
            return
        try:
            data = json.loads(snapshot.read_text(encoding="utf-8"))
        except Exception:
            return
        # 仅按 slug + part name 对齐恢复（快照与本次任务形状一致）
        saved = {b["slug"]: b for b in data.get("batches") or []}
        for batch in self.batches:
            saved_batch = saved.get(batch.slug)
            if not saved_batch:
                continue
            saved_parts = {p["name"]: p for p in saved_batch.get("parts") or []}
            for part in batch.parts:
                saved_part = saved_parts.get(part.name)
                if not saved_part or not saved_part.get("ok"):
                    continue
                dest = Path(str(saved_part.get("dest") or ""))
                if not dest.is_file():
                    continue
                # 恢复校验：本地已下载文件的内容哈希 == 清单期望 SHA256
                if _file_sha256(dest) == str(part.sha256 or "").lower():
                    part.ok = True
                    part.dest = str(dest)
                    part.downloaded_bytes = part.size

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
                    self.retry_count = 0
                    self.last_retry_at = 0.0
                    self.last_error_kind = ""
                    self._retrying = False
                    self._resume_percent = -1
                    self._message = ""
                    self._download_one(part, batch)
            self._message = ""
            self._retrying = False
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
            self._message = ""
            self._retrying = False
            # 取消是终态：重试观测归零（**退避等待中被取消**那条路尤其要清——
            # 那时 retry_count / error_kind 已被上一次失败填过，不清就会把用户自己
            # 点的取消报成「网络失败」）
            self.retry_count = 0
            self.last_error_kind = ""
        except Exception as exc:
            self._message = ""
            self._retrying = False
            was_applying = self._state is TaskState.APPLYING
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

    def _download_one(self, part: _PartState, batch: _BatchState) -> None:
        # 文件名 = part.name（即 zip_name / URL 尾段），与应用器按
        # manifest parts[].zip_name 找文件的口径一致（勿加 slug 前缀，
        # 否则双缀导致应用器找不到）。
        dest = self.task_dir / "materials" / part.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        part.dest = str(dest)
        part.downloaded_bytes = 0
        have = dest.stat().st_size if dest.is_file() else 0
        digest = ""
        if part.size > 0 and have == part.size:
            # 长度已到点：不再发请求，直接进校验（spec 的断点契约）
            part.downloaded_bytes = have
        else:
            if download_resume.is_resumable_partial(dest, part.url, part.size):
                self._message = download_resume.resume_message(have, part.size)
                part.downloaded_bytes = have
            else:
                download_resume.clear_partial(dest)   # 来路不明的不完整文件：不留
            download, is_default = self._resolve_download()
            download = download_resume.as_task_downloader(
                download, cancel=self._cancel, before_retry=self._on_retry(part),
                on_start=self._on_attempt_start(part),
                before_attempt=self._on_retry_window_closed, default=is_default,
            )
            try:
                actual = download(part.url, dest, self._on_progress(part),
                                  expected_size=part.size,
                                  expected_sha256=part.sha256)
            except Exception as exc:
                if not isinstance(exc, DownloadCancelledError):
                    download_resume.write_partial_marker(dest, part.url, part.size)
                raise
            # 缺省下载器已算过整卷哈希；注入的假下载器返回裸 sha 字符串则读盘算
            digest = (actual.sha256 if isinstance(actual, DownloadResult)
                      else str(actual))
        if not digest:
            digest = _file_sha256(dest)
        if digest.lower() != part.sha256.lower():
            # 校验失败 = 重下也是坏的：整份清掉（半成品 + 边车），不留孤儿。
            # 异常用下载域那一支（`DownloadVerifyError`），好让 `error_kind` 仍是单源。
            download_resume.clear_partial(dest)
            raise DownloadVerifyError(f"卷 {part.name} 校验失败（SHA256 不匹配）")
        part.ok = True
        part.downloaded_bytes = part.size
        self._message = ""
        self._write_snapshot(force=False)

    def _on_progress(self, part: _PartState) -> Callable[[int], None]:
        """进度回调：累计量 = **本轮尝试的落盘起点**（`on_start` 报来）+ 本次读到的字节。

        不能拿「调用前盘上有多少」当基准：服务器忽略 Range 时会丢弃半成品从 0 重下，
        那时起点是 0，拿旧基准会把已扔掉的字节继续算进进度。
        """

        def cb(nbytes: int) -> None:
            with self._lock:
                part.downloaded_bytes += nbytes
        return cb

    def _on_attempt_start(self, part: _PartState) -> Callable[[int], None]:
        """每轮尝试开始：进度基准对齐到这一轮真实起点。

        **不在这里关「重试窗口」**：`on_start` 紧跟着 `before_retry` 发生，
        在这关窗口会被压成 0 宽（状态面永远看不到「正在重试」）。窗口由
        `resumable_download` 在**退避等待结束后**回调 `before_attempt` 关闭。
        """

        def cb(offset: int) -> None:
            with self._lock:
                part.downloaded_bytes = max(0, int(offset))

        return cb

    def _on_retry_window_closed(self) -> None:
        """退避等待结束、马上要真的重连：关掉「正在重试」窗口（摘要一并清）。"""
        self._retrying = False
        self._message = ""

    def _on_retry(self, part: _PartState) -> Callable[..., None]:
        """`before_retry` 回调：如实计数 + 「正在重试」的三件事分别落成三个字段。

        `message`（原因）/ `retry_count`（第几次）/ `resume_percent`（从多少接着下）分开放，
        前端直接拼——**不用从任何文案里抠信息**（与 full_task 同形）。
        """

        def cb(attempt: int, exc: BaseException, on_disk: int, restarted: bool) -> None:
            self.retry_count = int(attempt)
            self.last_retry_at = time.time()
            self.last_error_kind = download_resume.error_kind(exc)
            # 「服务器没让我们接上」→ 半成品已被丢弃，本轮起点就是 0%（说 -1「不知道」
            # 会让界面拿不到「从 0 重新下」这个事实）
            self._resume_percent = (
                0 if restarted
                else download_resume.retry_resume_percent(on_disk, part.size)
            )
            self._retrying = True     # 退避等待中（退避结束时清）
            self._message = download_resume.retry_message(
                download_resume.retry_reason(exc)
            )

        return cb

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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(256 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        "message": task._message,
        # 重试观测（工单 04 的契约面；工单 05 起前端直接消费，不再解析文案）
        "retry_count": int(task.retry_count),
        "retrying": bool(task._retrying),
        "error_kind": str(task.last_error_kind),
        "resume_percent": int(task._resume_percent),
    }


def write_task_snapshot(task: ApplyTask) -> None:
    """强制落盘（测试与 shutdown 钩子用）。"""
    task._write_snapshot(force=True)
