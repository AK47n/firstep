"""工单 12 的**判据强度探针**：错版注入 → 跑既有用例 → 看红不红。

要答的问题不是「这两处重复看着像不像」，而是**既有判据对这两处各自覆盖到什么程度**：

| 想答的问题 | 对应格 |
|---|---|
| 状态视图的**契约字段**（`resume_percent` / `retry_count` / `retrying` / `error_kind`）漏一边，会不会红？ | `full:no_retry_fields` / `materials:no_retry_fields` |
| 状态视图的**载荷键名**（`parts`）漏一边，会不会红？ | `full:part_key` / `materials:part_key` |
| 两条链路的**速度估算**（公式相同）改坏了谁会红？ | `full:speed_zero` / `materials:speed_zero` |
| `run()` 成功收尾把当前卷名清掉——这件事有没有判据？ | `full:keep_current_name` |
| `run()` 失败分类（`last_error_kind`）有没有判据？ | `full:no_error_kind` |
| `_PartState` 的**快照形状**字段（`dest`）漏一个，会不会红？ | `full:drop_field` |
| `_PartState.from_dict` 是不是**零调用点**（工单 12 的静态发现）？ | `from_dict_boom` |

**纪律（工单 11 用血换的）**：错版代码只用一个引号层级；每格先**自证注入生效**
（断言目标对象的实现已来自 `<naive-*>`）——注入失败直接判「探针失效」，
**不给出绿的结论**。超时同理：本机会间歇性卡死，超时如实记「探针失效」，
不拿它当判据。

用法：python .scratch/resumable-download/probe-12-guard-strength.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE_TIMEOUT_SECONDS = 120

# 错版正文。**每个只用一个引号层级**（外层 """，里面一律双引号），避免工单 11 踩过的
# 「三引号里嵌转义 → 插件语法错 → 注入静默失效」那条坑。
NO_RETRY_TEMPLATE = '''
def {NAME}(task):
    if task is None:
        return {{"state": "idle", "parts": []}}
    parts = []
    for part in {PARTS}:
        parts.append({{
            "name": part.name,
            "downloaded_bytes": part.downloaded_bytes,
            "total_bytes": part.size,
            "ok": part.ok,
        }})
    now = _time.time()
    current = task.downloaded_bytes
    task._last_ts, task._last_bytes = now, current
    return {{
        "state": task.state.value,
        "parts": parts,
        "total_downloaded_bytes": current,
        "total_bytes": task.total_bytes,
        "speed_bps": 0,
        "current_part_name": task._current_part_name,
        "error": task.error,
        "message": task.message,
    }}
'''

# 每格都保留**窗口记账**那一句（`task._last_ts` / `task._last_bytes` 就地更新）：
# 第一版错版把它一起丢了，于是 `test_message_cleared_when_backoff_window_closes`
# 在注入下**打转不返回**（那支用例的 spy 每次进度回调都调 status；窗口不动 → 退避空转），
# 探针只能报「失效」。那是我自己造的失效，不是产品行为——**分离变量**：
# 错版只丢要测的那部分，其余逐字保留（工单 11 那条「不许把探针的假形状当产品行为」）。
# 下面 `PART_KEY_TEMPLATE` 与 `SPEED_ZERO_TEMPLATE` 同理，各自保留该句。
PART_KEY_TEMPLATE = '''
def {NAME}(task):
    if task is None:
        return {{"state": "idle", "parts": []}}
    now = _time.time()
    current = task.downloaded_bytes
    task._last_ts, task._last_bytes = now, current
    return {{
        "state": task.state.value,
        "卷表": [],
        "total_downloaded_bytes": current,
        "total_bytes": task.total_bytes,
        "speed_bps": 0,
        "current_part_name": task._current_part_name,
        "error": task.error,
        "message": task.message,
        "retry_count": int(task.retry_count),
        "retrying": bool(task.retrying),
        "error_kind": str(task.last_error_kind),
        "resume_percent": int(task.resume_percent),
    }}
'''

SPEED_ZERO_TEMPLATE = '''
def {NAME}(task):
    if task is None:
        return {{
            "state": "idle", "parts": [], "total_downloaded_bytes": 0,
            "total_bytes": 0, "speed_bps": 0, "current_part_name": "",
            "error": "", "message": "", "retry_count": 0, "retrying": False,
            "error_kind": "", "resume_percent": -1,
        }}
    parts = []
    for part in {PARTS}:
        parts.append({{
            "name": part.name,
            "downloaded_bytes": part.downloaded_bytes,
            "total_bytes": part.size,
            "ok": part.ok,
        }})
    now = _time.time()
    current = task.downloaded_bytes
    task._last_ts, task._last_bytes = now, current
    return {{
        "state": task.state.value,
        "parts": parts,
        "total_downloaded_bytes": current,
        "total_bytes": task.total_bytes,
        "speed_bps": 0,
        "current_part_name": task._current_part_name,
        "error": task.error,
        "message": task.message,
        "retry_count": int(task.retry_count),
        "retrying": bool(task.retrying),
        "error_kind": str(task.last_error_kind),
        "resume_percent": int(task.resume_percent),
    }}
'''

RUN_KEEP_CURRENT_NAME = '''
def run(self):
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
            self._on_complete(
                [{"name": p.name, "path": p.dest, "sha256": p.sha256, "size": p.size}
                 for p in self.parts]
            )
        self._state = TaskState.DONE
        self._error = ""
    except DownloadCancelledError:
        self._state = TaskState.CANCELLED
        self._retry.reset_for_cancelled()
    except Exception as exc:
        was_applying = self._state is TaskState.APPLYING
        self._state = TaskState.FAILED
        self._retry.clear_message_and_window()
        self._error = (
            f"应用失败：{exc}" if was_applying
            else f"下载失败（卷 {self._current_part_name}）：{exc}"
        )
        self.last_error_kind = (
            "" if was_applying else download_resume.error_kind(exc)
        )
    self._write_snapshot(force=True)
'''

RUN_NO_ERROR_KIND = '''
def run(self):
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
        self._retry.reset_for_cancelled()
    except Exception as exc:
        was_applying = self._state is TaskState.APPLYING
        self._state = TaskState.FAILED
        self._retry.clear_message_and_window()
        self._error = (
            f"应用失败：{exc}" if was_applying
            else f"下载失败（卷 {self._current_part_name}）：{exc}"
        )
    self._write_snapshot(force=True)
'''

# `__init__` 的 parts 解析：把卷名吞掉（`size=0` 那版会让用例在真下载里打转——
# 那是「自己造的卡住」，不是判据，故改用**确定性失败**的错版：卷名不解析）。
INIT_DROPS_NAME = '''
def __init__(
    self,
    task_dir,
    parts,
    download=None,
    snapshot_interval=SNAPSHOT_INTERVAL_SECONDS,
    on_complete=None,
):
    self.task_dir = Path(task_dir)
    self.parts = [
        _PartState(
            name="",
            url=str(p.get("url") or ""),
            size=int(p.get("size") or 0),
            sha256=str(p.get("sha256") or ""),
        )
        for p in parts
    ]
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
    self._last_ts = time.time()
    self._last_bytes = 0
    self._retry = TaskRetryState()
    self._restore_snapshot()
'''

# 单行取值器改成常量：`state` 永远报 idle、`error` 永远报空串
GETTER_STATE_CONST = '''
@property
def state(self):
    return TaskState.IDLE
'''

GETTER_ERROR_CONST = '''
@property
def error(self):
    return ""
'''

# `to_dict` 漏一个字段（只漏 `dest`：快照恢复的三条规则之一正好读它）
DROP_FIELD = '''
def to_dict(self):
    return {
        "name": self.name,
        "url": self.url,
        "size": self.size,
        "sha256": self.sha256,
        "downloaded_bytes": self.downloaded_bytes,
        "ok": self.ok,
    }
'''

# `from_dict` 换成炸弹：谁碰它谁炸（用来判它到底有没有调用点）
FROM_DICT_BOOM = '''
def from_dict(data):
    raise RuntimeError("from_dict 被调用了（工单 12 的静态发现说它零调用点）")
'''

# 案件名 → 该塞进 sitecustomize 的错版源码（键就是 CASE 的第一段，判据口径单源）
FULL_PARTS = "task.parts"
MATS_PARTS = "[p for b in task.batches for p in b.parts]"
STATUS_NAIVE = {
    "full:no_retry_fields": NO_RETRY_TEMPLATE.format(
        NAME="full_task_status", PARTS=FULL_PARTS),
    "materials:no_retry_fields": NO_RETRY_TEMPLATE.format(
        NAME="task_status", PARTS=MATS_PARTS),
    "full:part_key": PART_KEY_TEMPLATE.format(NAME="full_task_status"),
    "materials:part_key": PART_KEY_TEMPLATE.format(NAME="task_status"),
    "full:speed_zero": SPEED_ZERO_TEMPLATE.format(NAME="full_task_status", PARTS=FULL_PARTS),
    "materials:speed_zero": SPEED_ZERO_TEMPLATE.format(NAME="task_status", PARTS=MATS_PARTS),
    "full:keep_current_name": RUN_KEEP_CURRENT_NAME,
    "full:no_error_kind": RUN_NO_ERROR_KIND,
    "full:drop_field": DROP_FIELD,
    "from_dict_boom": FROM_DICT_BOOM,
    "full:init_drops_name": INIT_DROPS_NAME,
    "full:getter_state_const": GETTER_STATE_CONST,
    "full:getter_error_const": GETTER_ERROR_CONST,
}

PLUGIN_TEMPLATE = '''# 由 probe-12-guard-strength.py 生成：内存里换掉目标实现，跑既有用例看红不红。
import json as _json  # noqa: F401
import time as _time  # noqa: F401


def _install():
    from contest_generator import full_task as ft
    from contest_generator import materials_task as mt

    MODS = {"full": ft, "materials": mt}
    STATUS = {"full": "full_task_status", "materials": "task_status"}

    def _status_ns(flavor):
        # **`_time` 必须进 exec 的名字空间**：错版正文里那句窗口记账用的就是它。
        # 第一版只建了空 ns，于是错版一调用就 NameError → 被下载重试路径吞掉 →
        # 用例空转不返回（探针报「卡住」）。是探针自己失真，不是用例的问题。
        ns = {"_time": _time}
        exec(compile(__STATUS_SRC__, "<naive-status>", "exec"), ns)
        target = MODS[flavor]
        name = STATUS[flavor]
        setattr(target, name, ns[name])
        fn = getattr(target, name)
        assert fn.__code__.co_filename.startswith("<naive-"), "错版注入失败：" + name

    if __KIND__ == "status":
        _status_ns(__FLAVOR__)
    elif __KIND__ == "run":
        from contest_generator.full_task import TaskState
        from contest_generator.download_resume import DownloadCancelledError
        from contest_generator import download_resume
        ns = {"TaskState": TaskState, "DownloadCancelledError": DownloadCancelledError,
              "download_resume": download_resume}
        exec(compile(__RUN_SRC__, "<naive-run>", "exec"), ns)
        ft.FullDownloadTask.run = ns["run"]
        fn = ft.FullDownloadTask.run
        assert fn.__code__.co_filename.startswith("<naive-"), "错版注入失败：run"
    elif __KIND__ == "drop_field":
        ns = {}
        exec(compile(__DROP_SRC__, "<naive-drop>", "exec"), ns)
        ft._PartState.to_dict = ns["to_dict"]
        fn = ft._PartState.to_dict
        assert fn.__code__.co_filename.startswith("<naive-"), "错版注入失败：to_dict"
    elif __KIND__ == "from_dict_boom":
        ns = {}
        exec(compile(__BOOM_SRC__, "<naive-boom>", "exec"), ns)
        ft._PartState.from_dict = staticmethod(ns["from_dict"])
        mt._PartState.from_dict = staticmethod(ns["from_dict"])
        mt._BatchState.from_dict = staticmethod(ns["from_dict"])
        # 自证注入生效：类属性表里那份**原始** staticmethod 指向错版文件
        # （第一版写 `__func__` 是错的——从类上取已解包成普通函数，探针因此报「注入失败」）
        installed = ft._PartState.__dict__["from_dict"]
        assert installed.__func__.__code__.co_filename.startswith("<naive-"), \\
            "错版注入失败：from_dict"
    elif __KIND__ in ("init", "getter"):
        from contest_generator.full_task import (
            FullDownloadTask, TaskState, SNAPSHOT_INTERVAL_SECONDS,
            SNAPSHOT_FILENAME)
        from contest_generator.download_resume import resumable_download
        from contest_generator.task_retry import TaskRetryState
        import pathlib as _pathlib
        import threading as _threading
        ns = {"_PartState": ft._PartState, "Path": _pathlib.Path,
              "resumable_download": resumable_download, "threading": _threading,
              "TaskState": TaskState, "time": _time,
              "TaskRetryState": TaskRetryState,
              "SNAPSHOT_INTERVAL_SECONDS": SNAPSHOT_INTERVAL_SECONDS,
              "SNAPSHOT_FILENAME": SNAPSHOT_FILENAME}
        exec(compile(__INIT_SRC__, "<naive-init>", "exec"), ns)
        if __KIND__ == "init":
            FullDownloadTask.__init__ = ns["__init__"]
            fn = FullDownloadTask.__init__
        else:
            prop = ns["state"] if __FLAVOR__ == "state" else ns["error"]
            setattr(FullDownloadTask, __FLAVOR__, prop)
            fn = getattr(FullDownloadTask, __FLAVOR__).fget
        assert fn.__code__.co_filename.startswith("<naive-"), \\
            "错版注入失败：" + __KIND__ + "/" + __FLAVOR__
    else:
        raise AssertionError("未知的 kind: " + __KIND__)


_install()
'''

# 每格 = (案件名, 注入种类, 哪一侧, [(用例文件, `-k` 表达式或 None)])。
# `-k` **只在本格会打转时**才用（`no_retry_fields` 那两格在
# `test_message_cleared_when_backoff_window_closes` 上不返回——那是本机已知的
# 间歇性卡死被注入改了时序后**稳定复现**，不是判据本身；用 `-k` 把它排除掉，
# 让这一格照样能给出「两侧各自红了没有」的答案）。
CASES: list[tuple[str, str, str, list[tuple[str, str | None]]]] = [
    ("full:no_retry_fields", "status", "full",
     [("tests/test_full_task.py", None),
      ("tests/test_download_status_surface.py",
       "not test_message_cleared_when_backoff_window_closes")]),
    ("materials:no_retry_fields", "status", "materials",
     [("tests/test_materials_task.py", None),
      ("tests/test_download_status_surface.py",
       "not test_message_cleared_when_backoff_window_closes")]),
    ("full:part_key", "status", "full",
     [("tests/test_full_task.py", None),
      ("tests/test_download_status_surface.py", None)]),
    ("materials:part_key", "status", "materials",
     [("tests/test_materials_task.py", None),
      ("tests/test_download_status_surface.py", None)]),
    ("full:speed_zero", "status", "full", [("tests/test_full_task.py", None)]),
    ("materials:speed_zero", "status", "materials",
     [("tests/test_materials_task.py", None)]),
    ("full:keep_current_name", "run", "full", [("tests/test_full_task.py", None)]),
    ("full:no_error_kind", "run", "full",
     [("tests/test_full_task.py", None),
      ("tests/test_download_status_surface.py", None)]),
    ("full:drop_field", "drop_field", "full",
     [("tests/test_full_task.py", None),
      ("tests/test_download_status_surface.py", None),
      ("tests/test_task_download.py", None)]),
    ("from_dict_boom", "from_dict_boom", "full",
     [("tests/test_full_task.py", None),
      ("tests/test_materials_task.py", None),
      ("tests/test_download_status_surface.py", None)]),
    ("full:init_drops_name", "init", "full",
     [("tests/test_full_task.py", None),
      ("tests/test_download_status_surface.py", None)]),
    ("full:getter_state_const", "getter", "state",
     [("tests/test_full_task.py", None),
      ("tests/test_download_status_surface.py", None)]),
    ("full:getter_error_const", "getter", "error",
     [("tests/test_full_task.py", None),
      ("tests/test_download_status_surface.py", None)]),
]


def build_plugin(kind: str, flavor: str, status_src: str) -> str:
    text = PLUGIN_TEMPLATE
    text = text.replace("__KIND__", repr(kind)).replace("__FLAVOR__", repr(flavor))
    if kind == "status":
        text = text.replace("__STATUS_SRC__", repr(status_src))
    elif kind == "run":
        text = text.replace("__RUN_SRC__", repr(status_src))
    elif kind == "drop_field":
        text = text.replace("__DROP_SRC__", repr(DROP_FIELD))
    elif kind in ("init", "getter"):     # 这两格共用同一个 `exec` 槽 `__INIT_SRC__`
        text = text.replace("__INIT_SRC__", repr(status_src))
    else:
        text = text.replace("__BOOM_SRC__", repr(FROM_DICT_BOOM))
    return text


def run_one_file(env: dict[str, str], rel: str, drop: str | None = None) -> tuple[str, str]:
    """跑**一个**用例文件 →（判定, 说明）。

    为什么逐文件而不是一次多文件：本机会间歇性卡住（工单 11 记过；工单 12 实测
    「多文件一起跑」会卡、「单文件跑」14 秒完事，同一个错版两种结果）。
    逐文件跑能把**红**（判据有效）与**卡住**（不是判据）分开——卡住如实记，
    绝不折算成绿。`drop` = `-k` 表达式，只用来排除已知会打转的那支用例。
    """
    args = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q"]
    if drop:
        args += ["-k", drop]
    args.append(rel)
    label = f"{rel}（-k '{drop}'）" if drop else rel
    try:
        out = subprocess.run(
            args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=env, timeout=CASE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return "卡住（不作判据）", f"{label} 超过 {CASE_TIMEOUT_SECONDS}s 没跑完"
    text = (out.stdout or "") + (out.stderr or "")
    if "注入失败" in text or "Error in sitecustomize" in text:
        return "探针失效", f"{label}：错版注入没落到位（见复跑诊断）"
    lines = [ln for ln in (out.stdout or "").strip().splitlines() if ln.strip()]
    # 汇总行取「含 passed/failed 的那一行」，**不是最后一行**——最后一行可能是 warning 汇总
    summary = next((ln for ln in reversed(lines) if "passed" in ln or "failed" in ln),
                   lines[-1] if lines else "(无输出)")
    failed = [ln for ln in lines if ln.startswith("FAILED")]
    detail = (f"{summary}；首个红：{failed[0].split(' - ')[0][7:]}"
              if failed else summary)
    if out.returncode == 0:
        return "绿（判据无效）", f"{label}：{detail}"
    return "红（判据有效）", f"{label}：{detail}"


def run(case: str, kind: str, flavor: str, status_src: str,
        files: list[tuple[str, str | None]]) -> list[tuple[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "sitecustomize.py").write_text(
            build_plugin(kind, flavor, status_src), encoding="utf-8"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([tmp, str(ROOT / "src")])
        env["PYTHONIOENCODING"] = "utf-8"
        return [run_one_file(env, rel, drop) for rel, drop in files]


def main() -> int:
    print("工单 12 错版注入探针：内存里换成错版 → 跑既有用例 → 看红不红\n", flush=True)
    print(f"（逐文件跑、每文件 {CASE_TIMEOUT_SECONDS}s 上限；"
          "「卡住」如实记录、不作判据）\n", flush=True)
    for case, kind, flavor, files in CASES:
        print(f"== {case} ==", flush=True)
        src = STATUS_NAIVE[case]
        results = run(case, kind, flavor, src, files)
        verdicts = {v for v, _ in results}
        if "红（判据有效）" in verdicts:
            headline = "红（判据有效）"
        elif verdicts == {"绿（判据无效）"}:
            headline = "绿（判据无效）"
        else:
            headline = "未定（有文件卡住/注入失败）"
        print(f"  [{headline}]")
        for verdict, detail in results:
            print(f"      [{verdict}] {detail}")
        print(flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
