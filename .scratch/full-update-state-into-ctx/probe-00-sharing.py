# -*- coding: utf-8 -*-
"""两个 app 实例共不共享完整包链路的会话态：收走前 / 收走后同一支探针
（工单 full-update-state-into-ctx/01）。

只读探针：不碰仓库文件，只在本进程里起**两个** TestClient（两个各自的 `AppContext`），看
「A 实例的完整包会话态」会不会被 **B 实例**的端点看见。会话态的注入缝随版本自动识别——新
代码在 `ctx.full_last_check` / `ctx.full_task`，旧代码在 `contest_generator.full_task` 的模块级
`_LAST_CHECK` / `_FULL_TASK`（经 `set_last_check` / `set_full_task`）。同一支探针因此在改动
前后各跑一次，读数可直接对读：**这是本条「每个 app 实例一份状态」那张卖点的证据**。

读数含义：
- 分卷白名单：把一份 check 结果放进 A（其注入缝）→ 看 B 的 apply 认不认那几个分卷。
  旧形状 B 认（直接过白名单，200）；新形状 B 不认（走兜底自查，桩回来的清单里没有 → 400）。
- 任务槽：把 A 的槽位占成「正在下载」→ 看 B 的 apply 会不会跟着被拒。
  旧形状 B 跟着拒（400「已有完整包下载任务在进行中」）；新形状 B 照常起任务（200）。

不打网络、不起服务器、不起下载线程：check 结果直接注入状态缝（不走 check 端点），兜底自查的
`check_for_full_update`、磁盘探测 `free_bytes`、任务类 `FullDownloadTask` 与线程启动
`start_full_update` 一律用桩替掉。

用法（**让探针自己落盘**，别用 PowerShell 的 `>`——那是 UTF-16LE，读工具会拒读）：
    python .scratch/full-update-state-into-ctx/probe-00-sharing.py --out <证据文件>
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from fastapi.testclient import TestClient  # noqa: E402

import contest_generator.webapp as webapp_mod  # noqa: E402
from contest_generator import full_task as ft  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

PART_NAME = "firstep-full-v1.1.0.zip"
PART = {
    "name": PART_NAME,
    "size": 9,
    "sha256": "a" * 64,
    "url": "https://example.invalid/firstep-full-v1.1.0.zip",
}
# 兜底自查的桩答复：**没有**可用分卷（于是 B 新形状下走 400「暂无可用」，不是真打 GitHub）
REFRESH_REPLY = {
    "latest_version": "",
    "total_bytes": 0,
    "parts": [],
    "error": "",
    "message": "（探针桩）暂无可用完整包",
    "manifest_url": "",
}


class _StubFullTask:
    """下载任务的桩（探针不允许真起线程 / 真打网络）。"""

    def __init__(self, task_dir=None, parts=None, on_complete=None, **_kw) -> None:
        self.task_dir = task_dir
        self.parts = parts or []
        self._on_complete = on_complete
        self.state = type("S", (), {"value": "downloading"})()

    def run(self) -> None:  # 端点用 daemon 线程包一层，这里什么都不做
        return None

    def cancel(self) -> None:
        return None


def _two_instances(root: Path) -> tuple[AppContext, TestClient, AppContext, TestClient]:
    """两个 app 实例（两个各自的 AppContext），照 tests/test_full_task.py 的构造形状。"""
    made = []
    for name in ("a", "b"):
        ctx = AppContext(config_path=root / name / "config.json")
        made.append((ctx, TestClient(create_app(ctx))))
    (ctx_a, client_a), (ctx_b, client_b) = made
    return ctx_a, client_a, ctx_b, client_b


# --- 注入缝随版本自动识别 -------------------------------------------------


def _seed_check(ctx: AppContext, check: dict) -> str:
    if hasattr(ctx, "full_last_check"):
        ctx.full_last_check.clear()
        ctx.full_last_check.update(check)
        return "ctx.full_last_check"
    ft.set_last_check(check)
    return "full_task._LAST_CHECK（模块级）"


def _clear_check(ctx: AppContext) -> None:
    if hasattr(ctx, "full_last_check"):
        ctx.full_last_check.clear()
    else:
        ft.set_last_check({})


def _seed_task(ctx: AppContext, task) -> str:
    if hasattr(ctx, "full_task"):
        ctx.full_task = task
        return "ctx.full_task"
    ft.set_full_task(task)
    return "full_task._FULL_TASK（模块级）"


def _clear_task(ctx: AppContext) -> None:
    if hasattr(ctx, "full_task"):
        ctx.full_task = None
    else:
        ft.set_full_task(None)


def _check_result() -> dict:
    return {
        "latest_version": "v1.1.0",
        "total_bytes": PART["size"],
        "parts": [PART],
        "manifest_url": "https://example.invalid/firstep-full-v1.1.0.manifest.json",
    }


def _stub_running_task() -> _StubFullTask:
    task = _StubFullTask()
    task.state = type("S", (), {"value": "downloading"})()
    return task


def _verdict(resp, shared_code: int, shared_text: str, own_text: str) -> str:
    if resp.status_code == shared_code:
        return f"  ← {shared_text}"
    return f"  ← {own_text}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="证据文件（UTF-8；不给就只打印）")
    args = parser.parse_args()

    # 桩：不真下载、不真起线程、不打网络、磁盘永远够
    webapp_mod.FullDownloadTask = _StubFullTask  # type: ignore[assignment]
    webapp_mod.start_full_update = lambda task: None  # type: ignore[assignment]
    webapp_mod.check_for_full_update = lambda installed: dict(REFRESH_REPLY)  # type: ignore[assignment]
    webapp_mod.free_bytes = lambda path: 10 * 1024**3  # type: ignore[assignment]

    rows: list[str] = []
    with tempfile.TemporaryDirectory(prefix="firstep-full-sharing-") as tmp:
        root = Path(tmp)
        ctx_a, client_a, ctx_b, client_b = _two_instances(root)

        # ① 分卷白名单 ---------------------------------------------------
        rows.append("① 分卷白名单（把 check 结果只放进 A 的会话态）")
        seam = _seed_check(ctx_a, _check_result())
        rows.append(f"  注入缝 = {seam}")
        resp_a = client_a.post("/api/update/full/apply", json={"parts": [PART_NAME]})
        rows.append(f"  A（持有白名单的实例）apply → {resp_a.status_code}")
        # A 的这次 apply 会占上任务槽；旧形状下那是**共享**的，会顶掉 B 的判据
        # （B 会被「已有任务在跑」拒掉，读数是 400 却不是白名单的功劳）。
        # 故先清槽，让这一格的判据只落在「B 认不认 A 的白名单」上。
        _clear_task(ctx_a)
        _clear_task(ctx_b)
        rows.append("  （清掉任务槽，让这一格只判白名单）")
        resp_b = client_b.post("/api/update/full/apply", json={"parts": [PART_NAME]})
        rows.append(
            f"  B（另一个实例）apply     → {resp_b.status_code}"
            + _verdict(resp_b, 200, "认了 = 两边共用白名单", "不认 = 各实例一份")
        )
        if resp_b.status_code == 400:
            rows.append(f"    B 的答复：{resp_b.json().get('detail', '')}")

        # ② 任务槽 -------------------------------------------------------
        rows.append("")
        rows.append("② 任务槽（把「正在下载」只占进 A 的会话态）")
        _clear_task(ctx_a)
        _clear_task(ctx_b)
        _clear_check(ctx_a)
        _clear_check(ctx_b)
        _seed_check(ctx_a, _check_result())
        _seed_check(ctx_b, _check_result())  # 两边都有白名单，判据只落在「任务在跑」这一跳
        seam2 = _seed_task(ctx_a, _stub_running_task())
        rows.append(f"  注入缝 = {seam2}")
        resp_a2 = client_a.post("/api/update/full/apply", json={"parts": [PART_NAME]})
        rows.append(
            f"  A（占着任务槽的实例）apply → {resp_a2.status_code}"
            + _verdict(resp_a2, 400, "自己的任务在跑，拒得对", "**A 自己也不拒 = 判据坏了**")
        )
        resp_b2 = client_b.post("/api/update/full/apply", json={"parts": [PART_NAME]})
        rows.append(
            f"  B（另一个实例）apply       → {resp_b2.status_code}"
            + _verdict(resp_b2, 400, "跟着拒了 = 两边共用同一个任务槽", "看不见 = 各实例一份")
        )

    text = "== 两个 app 实例共不共享完整包链路的会话态 ==\n" + "\n".join(rows) + "\n"
    print(text, end="")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
