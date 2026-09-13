"""「一次分卷下载」原语自己的契约（工单 resumable-download/10）。

`tests/test_download_sequence_home.py` 管的是**结构**（这段序列只许有一个家）；
这一份管的是**行为**：`download_and_verify` 自己的四条规则。

为什么要单独钉一遍（任务层那两份测试不是已经覆盖了吗）：这份判据的意义是
**把原语当被测对象**——两条链路的行为测试挂在任务对象上，一旦哪天有人把规则从
原语里搬回某个任务模块，那两份测试可能照样绿（只要两边都改），而这一份会红。
它同时是「判据在这里、实现必须也在这里」的锚。
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import pytest

from contest_generator import download_resume
from contest_generator.download_resume import (
    DownloadCancelledError,
    DownloadVerifyError,
    resumable_download,
)
from contest_generator.task_download import (
    download_and_verify,
    resolve_task_download,
    restore_snapshot_parts,
)
from contest_generator.task_retry import TaskRetryState
from tests._byte_server import ByteServer

PAYLOAD = bytes((i * 13 + 7) % 251 for i in range(120 * 1024))


class _Part:
    """最小分卷状态（形状与两条链路的 `_PartState` 相同——原语吃的就是这个形状）。"""

    def __init__(self, name: str, url: str, size: int, sha256: str) -> None:
        self.name = name
        self.url = url
        self.size = size
        self.sha256 = sha256
        self.dest = ""
        self.ok = False
        self.downloaded_bytes = 0


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _call(part: _Part, dest: Path, download, *, is_default: bool = False,
          cancel: threading.Event | None = None,
          retry: TaskRetryState | None = None) -> None:
    download_and_verify(
        part, dest,
        retry=retry or TaskRetryState(),
        lock=threading.Lock(),
        cancel=cancel or threading.Event(),
        # 注入缝的解析器：这里直接给一个「就选这个下载函数」的实现
        resolve=lambda: (download, is_default),
    )


def test_length_already_complete_skips_the_request(tmp_path: Path) -> None:
    """盘上已经是一整卷 → **不发请求**，直接进校验（spec 的断点契约）。

    少了这条，「完整卷」会被当「来路不明的文件」删掉重下——白下几百 MB。
    """
    dest = tmp_path / "updates" / "materials" / "k230.zip"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(PAYLOAD)
    part = _Part("k230.zip", "http://127.0.0.1:1/k230.zip", len(PAYLOAD), _sha(PAYLOAD))
    called: list[str] = []

    def never(url, target, on_progress):  # noqa: ANN001
        called.append(url)
        raise AssertionError("长度到点还发了请求")

    _call(part, dest, never)

    assert called == [], "不该发请求"
    assert part.ok is True
    assert part.downloaded_bytes == len(PAYLOAD)
    assert part.dest == str(dest)


def test_resumable_partial_is_resumed_and_message_says_so(tmp_path: Path) -> None:
    """有可续的半成品（边车对得上）→ 不重下、接着下，摘要如实写「从多少接着下」。

    摘要在**下载器被调用的那一刻**抓（成功收尾会清掉它——那是既定语义，不是漏写）。
    """
    dest = tmp_path / "full" / "part.zip"
    dest.parent.mkdir(parents=True)
    half = PAYLOAD[: len(PAYLOAD) // 2]
    dest.write_bytes(half)
    download_resume.write_partial_marker(dest, "http://x/part.zip", len(PAYLOAD))
    part = _Part("part.zip", "http://x/part.zip", len(PAYLOAD), _sha(PAYLOAD))
    retry = TaskRetryState()
    seen_here: list[int] = []
    message_at_call: list[str] = []

    def download(url, target, on_progress, **kwargs):  # noqa: ANN001, ANN003
        seen_here.append(target.stat().st_size)      # 从哪儿接着下
        message_at_call.append(retry.message)
        target.write_bytes(PAYLOAD)
        on_progress(len(PAYLOAD) - len(half))
        return _sha(PAYLOAD)

    _call(part, dest, download, retry=retry)

    assert seen_here == [len(half)], "半成品应当留在盘上被接着下"
    assert part.ok is True
    assert message_at_call == ["接着上次的进度从 50% 继续下载"], message_at_call
    assert retry.message == "", "成功收尾要清掉进行中的摘要"


def test_unresumable_partial_is_cleared_before_download(tmp_path: Path) -> None:
    """来路不明的不完整文件 → 先清掉（半成品 + 边车），再从头下。"""
    dest = tmp_path / "full" / "part.zip"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"junk" * 100)          # 没有边车 = 来路不明
    part = _Part("part.zip", "http://x/part.zip", len(PAYLOAD), _sha(PAYLOAD))

    def download(url, target, on_progress, **kwargs):  # noqa: ANN001, ANN003
        seen_here.append(target.stat().st_size if target.is_file() else 0)
        target.write_bytes(PAYLOAD)
        on_progress(len(PAYLOAD))
        return _sha(PAYLOAD)

    seen_here: list[int] = []
    _call(part, dest, download)

    assert seen_here == [0], "来路不明的半成品应当先被清掉"
    assert part.ok is True


def test_failure_keeps_the_partial_and_writes_the_sidecar(tmp_path: Path) -> None:
    """下载异常 → **半成品留着**（它就是断点），边车写出（换进程也能接着下）；异常照抛。"""
    dest = tmp_path / "full" / "part.zip"
    dest.parent.mkdir(parents=True)
    part = _Part("part.zip", "http://x/part.zip", len(PAYLOAD), _sha(PAYLOAD))

    def boom(url, target, on_progress, **kwargs):  # noqa: ANN001, ANN003
        target.write_bytes(PAYLOAD[: 64 * 1024])     # 落了半成品再断
        on_progress(64 * 1024)
        raise OSError("连接中断")

    with pytest.raises(OSError):
        _call(part, dest, boom)

    assert dest.is_file() and dest.stat().st_size == 64 * 1024, "半成品必须留着"
    assert part.ok is False, "失败不算 ok"
    assert download_resume.read_partial_marker(dest), (
        "边车必须写出（下一个进程靠它判定能不能续）"
    )


def test_cancelled_failure_writes_no_sidecar(tmp_path: Path) -> None:
    """取消不算失败：半成品留着、但**不写边车**（与重排前的分支逐字一致）。"""
    dest = tmp_path / "full" / "part.zip"
    dest.parent.mkdir(parents=True)
    part = _Part("part.zip", "http://x/part.zip", len(PAYLOAD), _sha(PAYLOAD))

    def cancelled(url, target, on_progress, **kwargs):  # noqa: ANN001, ANN003
        target.write_bytes(PAYLOAD[: 32 * 1024])
        raise DownloadCancelledError("用户取消")

    with pytest.raises(DownloadCancelledError):
        _call(part, dest, cancelled)

    assert dest.is_file(), "取消也留着半成品"
    assert not download_resume.read_partial_marker(dest), "取消不写边车"


def test_verify_failure_clears_everything_and_raises_domain_error(tmp_path: Path) -> None:
    """校验失败 → 清掉半成品与边车（重下也是坏的），抛下载域的 `DownloadVerifyError`。"""
    dest = tmp_path / "materials" / "k230.zip"
    dest.parent.mkdir(parents=True)
    part = _Part("k230.zip", "http://x/k230.zip", len(PAYLOAD), _sha(PAYLOAD))

    def wrong(url, target, on_progress, **kwargs):  # noqa: ANN001, ANN003
        target.write_bytes(b"x" * len(PAYLOAD))      # 长度对、内容不对
        on_progress(len(PAYLOAD))
        return "0" * 64

    with pytest.raises(DownloadVerifyError) as caught:
        _call(part, dest, wrong)

    assert "校验失败" in str(caught.value)
    assert not dest.exists(), "校验失败要连半成品一起清"
    assert not download_resume.read_partial_marker(dest), "边车也要清"
    assert part.ok is False


def test_downloader_returning_nothing_falls_back_to_reading_the_disk(tmp_path: Path) -> None:
    """注入的下载器**什么都不返回**（`None`）→ 读盘自算哈希，而不是判校验失败。

    这一格是双轴评审翻出来的：重排时我用了「没下载」记号，于是非 `DownloadResult`
    的返回值一律 `str(...)` → `"None"` → 与真 sha 不等 → **把好端端下完的一卷清掉并报
    校验失败**。旧码的 `if not digest` 不会这样（空 / `None` 都走读盘）。
    极端，但真注入器写出这种形状并不稀奇，而且后果是删文件。
    """
    dest = tmp_path / "full" / "part.zip"
    part = _Part("part.zip", "http://x/part.zip", len(PAYLOAD), _sha(PAYLOAD))

    def silent(url, target, on_progress, **kwargs):  # noqa: ANN001, ANN003
        target.write_bytes(PAYLOAD)
        on_progress(len(PAYLOAD))
        return None                                   # 不返回哈希

    _call(part, dest, silent)

    assert part.ok is True, "返回 None 不该被当成校验失败"
    assert dest.read_bytes() == PAYLOAD, "更不该把下好的整卷清掉"


def test_real_downloader_through_the_primitive(tmp_path: Path) -> None:
    """真 socket 一遍：缺省下载器（`is_default=True`）走原语仍能下完并落对哈希。

    前几条都用注入式假件（快、确定），这一条负责证明**缺省路径**没有被缝接坏。
    """
    from contest_generator.download_resume import resumable_download

    dest = tmp_path / "full" / "part.zip"
    part = _Part("part.zip", "http://127.0.0.1:1/part.zip", len(PAYLOAD), _sha(PAYLOAD))
    with ByteServer(PAYLOAD) as server:
        part.url = server.url
        _call(part, dest, resumable_download, is_default=True)

    assert part.ok is True
    assert dest.read_bytes() == PAYLOAD


# ---------------------------------------------------------------------------
# 任务层的另外两件共享事（工单 resumable-download/11）：
# 注入缝的解析、卷级断点的恢复
# ---------------------------------------------------------------------------


class _FakeTask:
    """最小任务对象：只持 `_download` 一个类属性 + 一个可设的实例属性。

    为什么要自造一个：`resolve_task_download` 只碰这两处（
    `task.__dict__["_download"]` 与 `type(task)._download`），拿真任务类测会让
    「解析顺序」这件事被任务类的其它构造逻辑盖住。
    """

    _download = staticmethod(resumable_download)

    def __init__(self, instance_value=None, set_instance: bool = True) -> None:
        if set_instance:
            self._download = instance_value if instance_value is not None else resumable_download


def test_resolve_download_prefers_instance_attribute(tmp_path: Path) -> None:
    """实例属性（构造注入 / 判据直接赋值）优先，且 `is_default=False`。

    `is_default=False` 是有代价的语义：适配层据此**不**给注入的下载器补
    `expected_size` / `expected_sha256`（保住既有的三参注入缝）。
    """
    def injected(url, dest, on_progress):  # noqa: ANN001
        return ""

    task = _FakeTask(instance_value=injected)
    assert resolve_task_download(task) == (injected, False)


def test_resolve_download_falls_back_to_class_attribute(tmp_path: Path) -> None:
    """**类属性注入缝**：`monkeypatch.setattr(<Task>, "_download", fake)` 必须仍然生效。

    这是工单 10 第七节点名要先回答的那个判据问题。构造后实例属性若等于缺省实现
    （`__init__` 的 `download or resumable_download` 就会这样），解析必须让**类属性**赢——
    否则 monkeypatch 出来的假下载器会被实例上那份缺省实现挡掉。
    """
    def patched(url, dest, on_progress):  # noqa: ANN001
        return ""

    task = _FakeTask()                       # 实例属性 = 缺省实现（没人真注入过）
    original = _FakeTask._download
    _FakeTask._download = staticmethod(patched)
    try:
        assert resolve_task_download(task) == (patched, False)
    finally:
        _FakeTask._download = original


def test_resolve_download_defaults_to_resumable() -> None:
    """两处都没有 → 缺省的可续下载，且 `is_default=True`（适配层据此补清单参数）。"""
    task = _FakeTask(instance_value=None, set_instance=False)
    assert resolve_task_download(task) == (resumable_download, True)

    # 实例属性**显式**等于缺省实现（构造参数默认路径）→ 也算「没人注入过」
    assert resolve_task_download(_FakeTask()) == (resumable_download, True)


def test_resolve_download_without_class_attribute_falls_back() -> None:
    """类属性被整体删掉（注释掉 / 换实现）→ 仍要退回缺省，不能返回 None。"""
    class Bare:
        pass

    task = Bare()
    assert resolve_task_download(task) == (resumable_download, True)


def test_restore_snapshot_parts_skips_when_no_snapshot(tmp_path: Path) -> None:
    """没有快照文件 → 什么都不做（也不是异常）。"""
    part = _Part("a.zip", "http://x/a.zip", 3, _sha(b"abc"))
    restore_snapshot_parts(tmp_path / "nope.json", lambda data: [(part, None)])
    assert part.ok is False


def test_restore_snapshot_parts_tolerates_broken_json(tmp_path: Path) -> None:
    """坏快照（不是合法 JSON）→ 当作没有断点，静默返回（不许把启动流程炸掉）。

    这条**不是**洁癖：快照是节流写盘的，断电 / 硬杀进程留下的半截文件很常见，
    任务对象在 `__init__` 里就要能带着它起来（大不了重下一卷）。
    """
    snapshot = tmp_path / "full-task.json"
    snapshot.write_text("{不是 JSON", encoding="utf-8")
    part = _Part("a.zip", "http://x/a.zip", 3, _sha(b"abc"))
    restore_snapshot_parts(snapshot, lambda data: [(part, None)])
    assert part.ok is False


def test_restore_snapshot_parts_restores_all_three_fields(tmp_path: Path) -> None:
    """认下来的卷：`ok` / `dest` / `downloaded_bytes` **三个字段一起**恢复。

    少恢复 `downloaded_bytes` 会让进度条从 0 开始（用户以为白下了）；
    少恢复 `dest` 会让 `part_paths()` 交不出应用器的输入。
    """
    data = b"abcdefgh"
    target = tmp_path / "full" / "a.zip"
    target.parent.mkdir(parents=True)
    target.write_bytes(data)
    snapshot = tmp_path / "full-task.json"
    snapshot.write_text(
        json.dumps({"parts": [{"name": "a.zip", "ok": True, "dest": str(target)}]}),
        encoding="utf-8",
    )
    part = _Part("a.zip", "http://x/a.zip", len(data), _sha(data))
    restore_snapshot_parts(
        snapshot, lambda saved: [(part, next(iter(saved.get("parts") or []), None))]
    )
    assert (part.ok, part.dest, part.downloaded_bytes) == (True, str(target), len(data))


def test_restore_snapshot_parts_rejects_tampered_content(tmp_path: Path) -> None:
    """快照记 ok、文件也在，但**内容哈希与清单 sha 不符** → 不认（这就是卷级断点的安全线）。

    没有这一条，一个被改坏 / 被别的程序覆盖的同名文件会被当「已下好」，
    应用器拿它去解压 —— 终态是「校验失败」甚至更糟。
    """
    target = tmp_path / "full" / "a.zip"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"tampered")
    snapshot = tmp_path / "full-task.json"
    snapshot.write_text(
        json.dumps({"parts": [{"name": "a.zip", "ok": True, "dest": str(target)}]}),
        encoding="utf-8",
    )
    part = _Part("a.zip", "http://x/a.zip", 8, _sha(b"abcdefgh"))
    restore_snapshot_parts(
        snapshot, lambda saved: [(part, next(iter(saved.get("parts") or []), None))]
    )
    assert part.ok is False, "内容哈希不符的卷不许被当成已下好"


def test_restore_snapshot_parts_ignores_entries_that_are_not_ok_or_gone(
    tmp_path: Path,
) -> None:
    """四种「不该认」的存档形状：未标 ok / 文件不在 / dest 空 / 存档项根本不是字典。

    最后一格（存档项是字符串而不是对象）是**形状防御**：快照文件是外部输入
    （磁盘上可能被别人改过），旧实现靠 `TypeError` 撞进 `except Exception` 兜住，
    现在按形状判掉，行为同样是「跳过这一卷」。
    """
    target = tmp_path / "full" / "a.zip"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"abcdefgh")
    snapshot = tmp_path / "full-task.json"
    snapshot.write_text(json.dumps({"parts": []}), encoding="utf-8")
    saved_entries = [
        {"name": "a.zip", "ok": False, "dest": str(target)},          # 没标 ok
        {"name": "a.zip", "ok": True, "dest": str(tmp_path / "x.zip")},  # 文件不在
        {"name": "a.zip", "ok": True, "dest": ""},                     # dest 空
        "a.zip",                                                       # 形状就不对
    ]
    for saved in saved_entries:
        part = _Part("a.zip", "http://x/a.zip", 8, _sha(b"abcdefgh"))
        restore_snapshot_parts(snapshot, lambda _saved, s=saved: [(part, s)])
        assert part.ok is False, f"不该认的存档形状被认了：{saved!r}"


def test_restore_snapshot_parts_compares_sha_case_insensitively(tmp_path: Path) -> None:
    """清单里的 sha 大小写不统一（大写）也要认——旧实现就是这么比的（`str(...).lower()`）。"""
    data = b"abcdefgh"
    target = tmp_path / "full" / "a.zip"
    target.parent.mkdir(parents=True)
    target.write_bytes(data)
    snapshot = tmp_path / "full-task.json"
    snapshot.write_text(json.dumps({"parts": []}), encoding="utf-8")
    part = _Part("a.zip", "http://x/a.zip", len(data), _sha(data).upper())
    restore_snapshot_parts(
        snapshot,
        lambda _saved: [(part, {"name": "a.zip", "ok": True, "dest": str(target)})],
    )
    assert part.ok is True
