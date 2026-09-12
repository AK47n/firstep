"""完整包下载任务：扁平分卷 + 卷级断点 + 状态持久化（工单 full-download/03）。

契约（spec `.scratch/full-download/spec.md`）：
- `POST /api/update/full/apply`：所选分卷白名单（仅限 check 返回的分卷，防注入）
  → 磁盘空间校验（下载总量 × 1.5 + 16 MB 余量，不足 400 中文）→ 起后台线程 →
  返回 `{started}`，不阻塞请求；
- `GET /api/update/full/status`：
  `{state, parts: [{name, downloaded_bytes, total_bytes, ok}],
    total_downloaded_bytes, total_bytes, speed_bps, current_part_name,
    error, message}`；state ∈ idle|downloading|applying|done|failed|cancelled；
- `POST /api/update/full/cancel`：置取消标记 → 任务在**分卷边界**停止，已完成
  卷标记保留（下次重试不重下）。

卷级断点：每卷下载完且 SHA256 校验通过 → 落盘快照（`full-task.json`，节流
~2 s）记 ok=True；任务重建（失败重试 / 进程重启）时读快照，ok 且本地文件存在
且内容哈希与清单一致 → 跳过下载。

与 `materials_task.ApplyTask` 的差异：完整包是**扁平分卷表**（没有批次分组，
也没有 partial 态），落盘目录是 `updates/full/`，卷名 = 清单 `zip_name` 逐字节
一致（应用器按它找文件）。流式下载与状态机形态与资料库任务同构，故意保持结构
一致以便对照阅读。
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .materials_task import (
    TaskState,
    _file_sha256,
    download_part,
)

SNAPSHOT_FILENAME = "full-task.json"
SNAPSHOT_INTERVAL_SECONDS = 2.0
PARTS_DIRNAME = "full"
# 磁盘余量：下载总量 × 1.5（备份被覆盖文件）+ 16 MB
DISK_HEADROOM_FACTOR = 1.5
DISK_HEADROOM_BYTES = 16 * 1024 * 1024

# check 端点最近一次结果（apply 的分卷白名单来源；webapp 模块级单例语义）
_LAST_CHECK: dict[str, Any] = {}
_FULL_TASK: "FullDownloadTask | None" = None


def get_full_task() -> "FullDownloadTask | None":
    return _FULL_TASK


def set_full_task(task: "FullDownloadTask | None") -> None:
    """登记当前任务（webapp 端点与测试都用它，状态单源在本模块）。"""
    global _FULL_TASK
    _FULL_TASK = task


def last_check() -> dict[str, Any]:
    """最近一次 check 结果（apply 白名单来源）。"""
    return _LAST_CHECK


def set_last_check(result: dict[str, Any]) -> None:
    _LAST_CHECK.clear()
    _LAST_CHECK.update(result)


@dataclass
class _PartState:
    """单卷下载态（内存 + 快照共用形状）。"""

    name: str
    url: str = ""
    size: int = 0
    sha256: str = ""
    downloaded_bytes: int = 0
    ok: bool = False
    dest: str = ""

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


def _safe_part_name(name: str) -> bool:
    """卷名必须是纯文件名（应用器按名找文件，带路径 = 注入面）。"""
    if not name or not name.strip():
        return False
    if "/" in name or "\\" in name or ".." in name:
        return False
    return Path(name).name == name


def _free_bytes(path: Path) -> int:
    """目标盘剩余空间（盘符不可解析 = 0 → 调用方按不足处理）。"""
    import shutil

    try:
        return shutil.disk_usage(str(path.anchor or path)).free
    except Exception:
        return 0


# 公开别名（webapp 端点与测试都按 `free_bytes` 引用；实现单源在上面）
free_bytes = _free_bytes


class FullDownloadTask:
    """完整包下载任务（一任务一实例；webapp 模块级单例）。

    构造时不启动线程；`run()` 在调用方线程执行（端点用 daemon 线程包一层）。
    `download` 可注入（测试不碰网络）；快照持久化在 task_dir/full-task.json。
    """

    def __init__(
        self,
        task_dir: Path,
        parts: list[dict[str, Any]],
        download: Callable[[str, Path, Callable[[int], None]], str] | None = None,
        snapshot_interval: float = SNAPSHOT_INTERVAL_SECONDS,
        on_complete: Callable[[list[dict[str, Any]]], None] | None = None,
    ) -> None:
        self.task_dir = Path(task_dir)
        self.parts = [
            _PartState(
                name=str(p.get("name") or ""),
                url=str(p.get("url") or ""),
                size=int(p.get("size") or 0),
                sha256=str(p.get("sha256") or ""),
            )
            for p in parts
        ]
        self._download = download or download_part
        self._on_complete = on_complete
        self._snapshot_interval = snapshot_interval
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._last_snapshot = 0.0
        self._state = TaskState.IDLE
        self._error = ""
        self._current_part_name = ""
        self._started_at = time.time()
        # 速度估算窗口（status 轮询时更新）
        self._last_ts = time.time()
        self._last_bytes = 0
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
        return sum(p.size for p in self.parts)

    @property
    def downloaded_bytes(self) -> int:
        return sum(p.downloaded_bytes for p in self.parts)

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> None:
        self._cancel.set()

    def part_paths(self) -> list[Path]:
        """已就绪（校验通过）的分卷本地路径，按清单顺序。"""
        return [Path(p.dest) for p in self.parts if p.ok and p.dest]

    # -- 主流程 -------------------------------------------------------------

    def _restore_snapshot(self) -> None:
        """读上次快照：ok 卷且本地文件内容哈希与清单一致 → 标记跳过（断点续传）。"""
        snapshot = self.task_dir / SNAPSHOT_FILENAME
        if not snapshot.is_file():
            return
        try:
            data = json.loads(snapshot.read_text(encoding="utf-8"))
        except Exception:
            return
        saved_parts = {p["name"]: p for p in data.get("parts") or []}
        for part in self.parts:
            saved = saved_parts.get(part.name)
            if not saved or not saved.get("ok"):
                continue
            dest = Path(str(saved.get("dest") or ""))
            if not dest.is_file():
                continue
            if _file_sha256(dest) == str(part.sha256 or "").lower():
                part.ok = True
                part.dest = str(dest)
                part.downloaded_bytes = part.size

    def run(self) -> None:
        """执行下载：逐卷 → 下载 + 校验 + 完成标记；分卷边界响应取消。"""
        if self._cancel.is_set():
            self._state = TaskState.CANCELLED
            self._write_snapshot(force=True)
            return
        self._state = TaskState.DOWNLOADING
        self._write_snapshot(force=True)
        try:
            for part in self.parts:
                if self._cancel.is_set():
                    self._state = TaskState.CANCELLED
                    self._write_snapshot(force=True)
                    return
                if part.ok:
                    continue
                self._current_part_name = part.name
                self._download_one(part)
            if self._on_complete is not None:
                self._state = TaskState.APPLYING
                self._write_snapshot(force=True)
                self._current_part_name = ""
                self._on_complete(
                    [{"name": p.name, "path": p.dest, "sha256": p.sha256, "size": p.size}
                     for p in self.parts]
                )
            self._state = TaskState.DONE
            self._error = ""
            self._current_part_name = ""
        except Exception as exc:
            was_applying = self._state is TaskState.APPLYING
            self._state = TaskState.FAILED
            self._error = (
                f"应用失败：{exc}" if was_applying
                else f"下载失败（卷 {self._current_part_name}）：{exc}"
            )
        self._write_snapshot(force=True)

    def _download_one(self, part: _PartState) -> None:
        dest = self.task_dir / PARTS_DIRNAME / part.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        part.dest = str(dest)
        part.downloaded_bytes = 0
        try:
            actual = self._download(part.url, dest, self._on_progress(part))
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        if actual.lower() != part.sha256.lower():
            dest.unlink(missing_ok=True)
            raise OSError(f"卷 {part.name} 校验失败（SHA256 不匹配）")
        part.ok = True
        part.downloaded_bytes = part.size
        self._write_snapshot(force=False)

    def _on_progress(self, part: _PartState) -> Callable[[int], None]:
        def cb(nbytes: int) -> None:
            with self._lock:
                part.downloaded_bytes += nbytes

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
            "parts": [p.to_dict() for p in self.parts],
        }
        (self.task_dir / SNAPSHOT_FILENAME).write_text(
            json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# 状态视图（status 端点数据）
# ---------------------------------------------------------------------------


def full_task_status(task: "FullDownloadTask | None") -> dict[str, Any]:
    """任务 → status 响应（任务 None = idle 空态）；speed_bps 为瞬时估算。"""
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
        }
    parts = [
        {
            "name": p.name,
            "downloaded_bytes": p.downloaded_bytes,
            "total_bytes": p.size,
            "ok": p.ok,
        }
        for p in task.parts
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
        "message": "",
    }


def write_full_snapshot(task: FullDownloadTask) -> None:
    """强制落盘（测试与 shutdown 钩子用）。"""
    task._write_snapshot(force=True)


def start_full_update(task: FullDownloadTask) -> None:
    """起后台 daemon 线程执行任务（端点用；测试注入同步执行）。"""
    threading.Thread(target=task.run, daemon=True).start()
