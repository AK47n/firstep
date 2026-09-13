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

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import download_resume
from .download_resume import (
    DownloadCancelledError,
    DownloadResult,
    DownloadVerifyError,
    resumable_download,
)
from .materials_task import (
    TaskState,
    _file_sha256,
)
from .task_retry import TaskRetryMixin, TaskRetryState, part_progress_callbacks

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


class FullDownloadTask(TaskRetryMixin):
    """完整包下载任务（一任务一实例；webapp 模块级单例）。

    构造时不启动线程；`run()` 在调用方线程执行（端点用 daemon 线程包一层）。
    `download` 可注入（测试不碰网络）；快照持久化在 task_dir/full-task.json。
    """

    # 类属性是「注入点」的一部分：`monkeypatch.setattr(FullDownloadTask, "_download", fake)`
    # 靠它能落到类上（`_resolve_download` 按「实例属性 ≠ 这个缺省值」判有没有注入）。
    _download: Callable[..., Any] = staticmethod(resumable_download)

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
        # 下载器：缺省 = 可续下载；注入的（构造参数或测试直接给 `_download` 赋值）
        # 原样用——适配层只在缺省实现那条路上补 `expected_size` / `expected_sha256`。
        self._download = download or resumable_download
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
        # 重试观测（内存态，不落快照：重启后从 0 重新计更诚实）。
        # 字段与规则的单源在 `task_retry`（工单 09）；这里只持有一个值对象，
        # 六个字段名由 `TaskRetryMixin` 原样暴露，状态面契约零改动。
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

    def _resolve_download(self) -> tuple[Callable[..., Any], bool]:
        """→（这次要用的下载函数, 是不是**缺省的可续下载**）。

        解析顺序：实例属性（构造注入 / 测试直接赋值）→ 类属性（既有
        `monkeypatch.setattr(FullDownloadTask, "_download", …)` 注入点）→ 缺省的可续下载。
        实例属性仍等于缺省实现 = 没人注入过 → 让类属性优先（这就是既有 monkeypatch
        用例继续有效的原因）。

        第二个返回值交给 `as_task_downloader`：缺省实现无条件吃
        `expected_size` / `expected_sha256` / `cancel` / `before_retry`；注入的下载器
        仍按既有的三参形态调用（除非它自己声明要吃那几个关键字参数）——
        「`(url, dest, on_progress)` 签名不变」这条契约因此零改动。
        """
        instance = self.__dict__.get("_download")
        if instance is None or instance is resumable_download:
            chosen = getattr(type(self), "_download", None) or resumable_download
            return chosen, chosen is resumable_download
        return instance, False

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
        """执行下载：逐卷 → 下载 + 校验 + 完成标记；分卷边界响应取消。

        取消（含下载器在退避中的取消）→ `cancelled`（半成品与边车留着，下次接着下）。
        """
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
                self.reset_retry_state()
                self._download_one(part)
            self._retry.clear_message_and_window()
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
        except DownloadCancelledError:
            self._state = TaskState.CANCELLED
            # 取消是终态：把「进行中的摘要」与「重试观测」一并归零。
            # 特别是**退避等待中被取消**那条路——那时 retry_count / error_kind 已经被
            # 上一次失败填过了，不清就会在取消态里报出「重试 1 次 / 网络错误」，
            # 前端据此说「网络失败」= 把用户自己点的取消讲成网络故障（spec 的词表里
            # 取消态的分类是空串）。
            self._retry.reset_for_cancelled()
        except Exception as exc:
            was_applying = self._state is TaskState.APPLYING
            self._state = TaskState.FAILED
            self._retry.clear_message_and_window()
            self._error = (
                f"应用失败：{exc}" if was_applying
                else f"下载失败（卷 {self._current_part_name}）：{exc}"
            )
            # 应用阶段（解压 / 替换 / 磁盘写入）的失败不是网络问题，也不是「重下就变好」的
            # 校验问题——它是第四类，spec 的词表里没有格子，故留空：前端于是走通用话术，
            # 而不是照着 network 说「点重试会从这里接着下」。
            self.last_error_kind = (
                "" if was_applying else download_resume.error_kind(exc)
            )
        self._write_snapshot(force=True)

    def _download_one(self, part: _PartState) -> None:
        """下一卷并校验。

        - 已下字节 == 卷大小 → **不发请求**，直接进校验（spec 的断点契约）；
        - 有可续的半成品（边车对得上）→ 不重下，接着下（用户视角：上次断在这儿）；
        - 下载异常 → **半成品留着**（断点），如实往上抛；
        - 校验失败 → **清掉半成品与边车**（重下也不会有变化），如实往上抛。
        """
        dest = self.task_dir / PARTS_DIRNAME / part.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        part.dest = str(dest)
        part.downloaded_bytes = 0
        have = dest.stat().st_size if dest.is_file() else 0
        digest = ""
        if part.size > 0 and have == part.size:
            # 长度已到点：不再发请求，直接进下面那条校验。
            # 少了这条，「盘上已经是一整卷」会被当「来路不明的文件」删掉重下——
            # 白下几百 MB（快照没记 ok 的那些卷就是这个下场）。
            part.downloaded_bytes = have
        else:
            if download_resume.is_resumable_partial(dest, part.url, part.size):
                self._retry.message = download_resume.resume_message(have, part.size)
                part.downloaded_bytes = have
            else:
                download_resume.clear_partial(dest)   # 来路不明的不完整文件：不留
            download, is_default = self._resolve_download()
            on_progress, on_start = part_progress_callbacks(part, lock=self._lock)
            download = download_resume.as_task_downloader(
                download, cancel=self._cancel, on_start=on_start,
                default=is_default, **self.retry_callbacks(part),
            )
            try:
                actual = download(part.url, dest, on_progress,
                                  expected_size=part.size,
                                  expected_sha256=part.sha256)
            except Exception as exc:
                if not isinstance(exc, DownloadCancelledError):
                    # 失败：半成品是断点，留着；边车（谁留下的、期望多大）一并写出，
                    # 好让**换一次进程**也知道这份还能不能接着用。
                    download_resume.write_partial_marker(dest, part.url, part.size)
                raise
            # 缺省下载器已经把整卷算过哈希了（`DownloadResult.sha256`），不必再读一遍盘；
            # 注入的假下载器返回裸 sha 字符串，走既有行为读盘算哈希。
            digest = (actual.sha256 if isinstance(actual, DownloadResult)
                      else str(actual))
        if not digest:
            digest = download_resume.file_sha256(dest)
        if digest.lower() != part.sha256.lower():
            download_resume.clear_partial(dest)
            # 校验失败用下载域那一支（`DownloadVerifyError`）→ `error_kind` 仍是单源
            raise DownloadVerifyError(f"卷 {part.name} 校验失败（SHA256 不匹配）")
        part.ok = True
        part.downloaded_bytes = part.size
        self._retry.clear_message()
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
        "message": task.message,
        # 重试观测（工单 04 的契约面；工单 05 起前端直接消费这三个字段，不再解析文案。
        # 工单 09：取值走「重试观测」值对象的同名属性，不再是任务对象上的散字段）
        "retry_count": int(task.retry_count),
        "retrying": bool(task.retrying),
        "error_kind": str(task.last_error_kind),
        "resume_percent": int(task.resume_percent),
    }


def write_full_snapshot(task: FullDownloadTask) -> None:
    """强制落盘（测试与 shutdown 钩子用）。"""
    task._write_snapshot(force=True)


def start_full_update(task: FullDownloadTask) -> None:
    """起后台 daemon 线程执行任务（端点用；测试注入同步执行）。"""
    threading.Thread(target=task.run, daemon=True).start()
