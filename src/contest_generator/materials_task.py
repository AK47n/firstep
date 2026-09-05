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
    """

    def __init__(
        self,
        task_dir: Path,
        batches: list[dict[str, Any]],
        download: Callable[[str, Path, Callable[[int], None]], str] | None = None,
        snapshot_interval: float = SNAPSHOT_INTERVAL_SECONDS,
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
            download = download_part
        self._download = download
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
        """执行下载：逐批次逐卷 → 下载 + 校验 + 完成标记；分卷边界响应取消。"""
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
                    self._download_one(part, batch)
            self._state = TaskState.DONE
            self._error = ""
        except Exception as exc:
            self._state = TaskState.FAILED
            self._error = f"下载失败（卷 {self._current_part_name}）：{exc}"
        self._write_snapshot(force=True)

    def _download_one(self, part: _PartState, batch: _BatchState) -> None:
        dest = self.task_dir / "materials" / f"{batch.slug}-{part.name}.zip"
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
        "message": "",
    }


def write_task_snapshot(task: ApplyTask) -> None:
    """强制落盘（测试与 shutdown 钩子用）。"""
    task._write_snapshot(force=True)
