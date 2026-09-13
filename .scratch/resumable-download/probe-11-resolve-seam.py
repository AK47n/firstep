"""工单 11 的**判据探针**（只读 + 临时目录，不碰真身数据）。

要回答四个问题，每个都用**真跑**而不是读代码来回答：

1. **类属性注入缝在两处都真的生效吗**？——`monkeypatch.setattr(<Task>, "_download", fake)`
   之后不赋值实例属性，`run()` 是否真的走 fake（工单 10 第七节把这条列为「要动
   `_resolve_download` 之前得先回答的判据问题」）。
   *这条是「既有判据是不是依赖它」的关键：若某条链路的类属性注入其实**没人用**，
   那「收成一处」就要多担一份风险；若两处都在用，收的时候必须把契约显式钉住。*
2. **实例属性注入**（`task._download = fake`）同样两处都查。
3. **`_restore_snapshot`（卷级断点恢复）在既有判据里被钉到什么程度**：
   全 side 有「本地文件被改坏 → 不认」；materials side 有没有对应用例？
   没有哈希校验时会不会有人红？（改坏盘上文件再重建任务，看它是否重下）
4. **既有用例是否依赖 `_resolve_download` / `_restore_snapshot` 的「住处」**
   （全仓引用点盘点）。

用法：python .scratch/resumable-download/probe-11-resolve-seam.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator import full_task as ft  # noqa: E402
from contest_generator import materials_task as mt  # noqa: E402

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def _payload(size: int, fill: bytes) -> bytes:
    return fill * size


def _sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# 1 / 2 注入缝
# ---------------------------------------------------------------------------


def probe_class_attribute_injection() -> None:
    """类属性注入：不设实例属性，看 run() 走的是不是 fake。"""
    print("\n== 1. 类属性注入缝（monkeypatch.setattr(<Task>, '_download', fake)）==")
    for name, cls in (("full_task.FullDownloadTask", ft.FullDownloadTask),
                      ("materials_task.ApplyTask", mt.ApplyTask)):
        called: list[str] = []

        def fake(url: str, dest: Path, on_progress, _called=called) -> str:
            data = _payload(8, b"x")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            on_progress(len(data))
            _called.append(url)
            return _sha(data)

        original = cls._download
        cls._download = staticmethod(fake)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                if cls is ft.FullDownloadTask:
                    task = cls(Path(tmp), [{"name": "a.zip", "url": "u://a",
                                            "size": 8, "sha256": _sha(_payload(8, b"x"))}])
                else:
                    task = cls(Path(tmp), [{"slug": "s", "name": "n", "parts": [
                        {"zip_url": "u://a", "size_bytes": 8,
                         "sha256": _sha(_payload(8, b"x")), "zip_name": "a.zip"}]}])
                task.run()
                used = bool(called)
                check(f"{name}：类属性注入被采纳（fake 真被调用）", used,
                      f"calls={called} state={task.state.value} err={task.error}")
                check(f"{name}：解析结果 is fake",
                      task._resolve_download()[0] is fake)
        finally:
            cls._download = original


def probe_instance_injection() -> None:
    """实例属性注入：构造后直接赋值（既有判据大量使用）。"""
    print("\n== 2. 实例属性注入缝（task._download = fake）==")
    for name, cls in (("full_task.FullDownloadTask", ft.FullDownloadTask),
                      ("materials_task.ApplyTask", mt.ApplyTask)):
        called: list[str] = []

        def fake(url: str, dest: Path, on_progress, _called=called) -> str:
            data = _payload(8, b"x")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            on_progress(len(data))
            _called.append(url)
            return _sha(data)

        with tempfile.TemporaryDirectory() as tmp:
            if cls is ft.FullDownloadTask:
                task = cls(Path(tmp), [{"name": "a.zip", "url": "u://a",
                                        "size": 8, "sha256": _sha(_payload(8, b"x"))}])
            else:
                task = cls(Path(tmp), [{"slug": "s", "name": "n", "parts": [
                    {"zip_url": "u://a", "size_bytes": 8,
                     "sha256": _sha(_payload(8, b"x")), "zip_name": "a.zip"}]}])
            task._download = fake
            task.run()
            check(f"{name}：实例属性注入被采纳", bool(called), f"calls={called}")
            check(f"{name}：解析结果 is fake（且 is_default=False）",
                  task._resolve_download() == (fake, False))


# ---------------------------------------------------------------------------
# 3 卷级断点恢复（_restore_snapshot）在既有判据里的覆盖
# ---------------------------------------------------------------------------


def _run_and_corrupt_full(tmp: Path, damage: str) -> tuple[list[str], str]:
    """跑一卷 → 落快照 → 按 `damage` 破坏现场 → 重建任务，返回（下载调用, 状态）。

    **第一版探针在这里栽过**：假下载器只在「第一次」写文件，于是重建后
    `have == part.size` 走了「长度到点 → 不发请求」，看起来像「恢复逻辑没校验哈希」。
    实为夹具失真——故这里 fake **每次都写**（真下载器本来就有没有网络请求两种走法，
    而这一格要测的是 `_restore_snapshot` 认不认盘上那份，故必须让请求该发就发）。
    """
    calls: list[str] = []
    data = _payload(8, b"x")
    parts = [{"name": "a.zip", "url": "u://a", "size": 8, "sha256": _sha(data)}]

    def fake(url: str, dest: Path, on_progress) -> str:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        on_progress(len(data))
        calls.append(url)
        return _sha(data)

    first = ft.FullDownloadTask(Path(tmp), parts, download=fake)
    first.run()
    ft.write_full_snapshot(first)
    target = Path(tmp) / ft.PARTS_DIRNAME / "a.zip"
    if damage == "tamper_same_size":       # 大小对得上、内容不对 ← 只有哈希校验拦得住
        target.write_bytes(b"y" * 8)
    elif damage == "truncate":             # 短了
        target.write_bytes(b"x" * 4)
    elif damage == "grow":                 # 长了（比清单大）
        target.write_bytes(b"x" * 16)
    elif damage == "remove":               # 没了
        target.unlink()
    calls.clear()
    again = ft.FullDownloadTask(Path(tmp), parts, download=fake)
    restored_ok = again.parts[0].ok
    again.run()
    return calls, f"{again.state.value}（恢复时 ok={restored_ok}）"


def _run_and_corrupt_materials(tmp: Path, damage: str) -> tuple[list[str], str]:
    """同上，资料库链路（两层 batches 的那个版本）。"""
    calls: list[str] = []
    data = _payload(8, b"x")
    batches = [{"slug": "s", "name": "n", "parts": [
        {"zip_url": "u://a", "size_bytes": 8, "sha256": _sha(data), "zip_name": "a.zip"}]}]

    def fake(url: str, dest: Path, on_progress) -> str:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        on_progress(len(data))
        calls.append(url)
        return _sha(data)

    first = mt.ApplyTask(Path(tmp), batches, download=fake)
    first.run()
    mt.write_task_snapshot(first)
    target = Path(tmp) / "materials" / "a.zip"
    if damage == "tamper_same_size":
        target.write_bytes(b"y" * 8)
    elif damage == "truncate":
        target.write_bytes(b"x" * 4)
    elif damage == "grow":
        target.write_bytes(b"x" * 16)
    elif damage == "remove":
        target.unlink()
    calls.clear()
    again = mt.ApplyTask(Path(tmp), batches, download=fake)
    restored_ok = again.parts_flat_ok() if hasattr(again, "parts_flat_ok") else again.batches[0].parts[0].ok
    again.run()
    return calls, f"{again.state.value}（恢复时 ok={restored_ok}）"


def probe_restore_coverage() -> None:
    """卷级断点恢复：完好则跳过；被破坏则**必须在请求该发时就发**。

    这一格问的是「既有判据钉住了多少」——`_restore_snapshot` 是**两条链路各一份**，
    若只有一侧有判据，那就是「同形重复 + 判据不对称」这条账的硬证据。
    """
    print("\n== 3. _restore_snapshot（卷级断点）行为五格 ==")
    expected_calls = {
        "intact": [],                      # 完好 → 跳过（不发请求）
        "tamper_same_size": [],            # 快照被否掉，但请求也不发（见下）
        "truncate": ["u://a"],
        "grow": ["u://a"],
        "remove": ["u://a"],
    }
    # `tamper_same_size` 的**真口径**（第一版探针在这一格写过错期望）：
    # 「大小对得上、内容不对」时 `_restore_snapshot` 的哈希校验**确实把它否掉了**
    # （恢复时 ok=False），但**不会重下**——`download_and_verify` 的「长度到点 →
    # 不发请求直接校验」先命中（规则来自工单 03：同一路径下 `part.size > 0 and
    # have == part.size` 就跳过请求）。于是终态是 `failed` + 校验失败（不是 done）。
    # 这**不是本单要动的规则**：它就是 spec 的断点契约里「尺寸到点但内容坏」那一行，
    # 用户看到的处置是**报校验失败**（而不是静默当成功）。判据写成这样才不假。
    expected_state = {
        "intact": "done",
        "tamper_same_size": "failed",
        "truncate": "done",
        "grow": "done",
        "remove": "done",
    }
    for label, runner in (("full_task", _run_and_corrupt_full),
                          ("materials_task", _run_and_corrupt_materials)):
        for damage, want in expected_calls.items():
            with tempfile.TemporaryDirectory() as tmp:
                calls, state = runner(Path(tmp), damage)
            check(f"{label}：{damage} calls={calls or '[]（跳过）'} 状态={state.split('（')[0]}",
                  calls == want and state.startswith(expected_state[damage]),
                  f"期望 calls={want} 状态={expected_state[damage]}")


# ---------------------------------------------------------------------------
# 4 引用点盘点
# ---------------------------------------------------------------------------


def probe_reference_surface() -> None:
    """引用点盘点（谁依赖这两个私有方法的『住处』）。

    **扫描面只算代码**：`src` / `tests` / `tools`。第一版把 `.scratch` 也算进来，
    于是**本探针自己的输出文件**（`verify-11-resolve-seam.txt`，里面逐条列了引用点）
    被下一次运行当成新的引用点读进去——输出一次比一次长（18KB → 43KB），
    且结论被自己的回声污染。判据探针的输出不许进判据的输入。
    """
    print("\n== 4. 引用点盘点（谁依赖这两个私有方法的『住处』）==")
    for token in ("_resolve_download", "_restore_snapshot"):
        out = subprocess.run(
            ["git", "grep", "-n", token, "--", "src", "tests", "tools"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip().splitlines()
        print(f"\n  [{token}] {len(out)} 处引用：")
        for line in out:
            print(f"    {line[:150]}")
        check(f"{token}：引用面已盘点", True)


def main() -> int:
    probe_class_attribute_injection()
    probe_instance_injection()
    probe_restore_coverage()
    probe_reference_surface()
    print(f"\n总判：{'PASS' if not FAILURES else 'FAIL'}（{len(FAILURES)} 项不达预期）")
    for item in FAILURES:
        print(f"  - {item}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
