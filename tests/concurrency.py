"""测试侧并发小工具（工单 record-write-hardening/06 收口）。

本批四单各自抄了一份"起守护线程跑 work、异常带回主线程断言"的脚手架
（`test_drafts.py` / `test_idea_chat.py` / `test_params.py` / `test_master_store.py`），
评审点名后收成这一处——形状照 `tests/test_hwcheck_triage.py:625-645` 那段并发先例。

为什么不放 `tests/fakes.py`：那里放的是"假件"（假 LLM / 假工程），不是线程脚手架；
`tests/test_impact.py::_sse_events` 被别的用例文件 import 也是本仓已有的先例。
"""

from __future__ import annotations

import threading


def run_in_thread(errors: list[BaseException], work) -> threading.Thread:
    """起一个守护线程跑 `work`，线程里的异常追加到 `errors`（主线程随后断言 `errors == []`）。"""

    def body() -> None:
        try:
            work()
        except BaseException as exc:  # noqa: BLE001 —— 线程里的异常要带回主线程断言
            errors.append(exc)

    thread = threading.Thread(target=body, daemon=True)
    thread.start()
    return thread
