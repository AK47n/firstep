"""工单 15 的**判据强度探针**：错版注入 → 跑既有用例 → 看红不红。

要答的问题不是「这几处看着重不重复」，而是：**每一份 12 键契约副本各自坏了会不会红、
覆盖到哪一格**——以及**收成一份之后覆盖面会不会缩水**。

| 想答的问题 | 对应格 |
|---|---|
| 产品侧 `full_task_status` **多一个键**，谁会红？ | `full:add_key` |
| 只在 `full_task_status(None)`（空态）多一个键呢？ | `full:idle_add_key` |
| 产品侧 `full_task_status` **少一个键**，谁会红？ | `full:drop_key` |
| 产品侧 `task_status`（另一侧）少一个键呢？ | `materials:drop_key` |
| **键名改错**（`current_part_name` → 别的名字）谁会红？ | `full:rename_key` |
| `test_status_idle_shape` 的**取值**那一半坏了谁会红？ | `full:idle_total_bytes` |

**「按手续加字段」那一格不在这里**（第一版有，已撤）：它的做法是「产品两侧各加一个键 +
把共同常量也补上同一个键」，而那件事**没法用运行时改常量来模拟**——本单新增的结构守卫
把「内存里的 `STATUS_KEYS`」与「源码文本里的那份契约」绑在一起，运行时改常量会被守卫
读成自相矛盾（第一版实测：守卫那两条用例转红，红在**注入假象**上，不是产品行为）。
现在它由 `run-15-evidence.py together` 在**临时 worktree 里做真源码编辑**来量
（`verify-15-together.txt`，基线 / 现状两版对照）。

**错版一律写成「包装真实现、只扰动要测的那一处」**（工单 13 第 1 条的教训：分离变量）。
第一版把整支投影抄成错版，非目标分支只能填桩（`return {"state": "x"}`）——
那会让大量用例因为桩而红，「红在谁身上」这个问题直接被污染。包装式错版不会：
其余行为逐字走真实现。

**纪律（工单 11/12 用血换的）**：
  - 每格先**自证注入生效**（断言目标实现已来自 `<naive-…>`）；注入失败直接判「探针失效」，
    **不给绿的结论**；
  - 逐**文件**跑；超时如实记「卡住（不作判据）」，不折算成绿；
  - 红要**报在谁身上**：每格把失败的用例名印出来，一眼看出红在哪一条断言上。

用法：python .scratch/resumable-download/probe-15-guard-strength.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE_TIMEOUT_SECONDS = 120
CHILD_ENV_EXTRA = {"PYTHONIOENCODING": "utf-8"}

# ---- 错版：包装式（`_orig` 是真实现，只改要测的那一处） ----------------------
ADD_KEY_BOTH = '''
def full_task_status(task):
    status = _orig(task)
    status["extra_probe_key"] = 0
    return status
'''

ADD_KEY_IDLE_ONLY = '''
def full_task_status(task):
    status = _orig(task)
    if task is None:
        status["extra_probe_key"] = 0
    return status
'''

DROP_KEY_BOTH = '''
def full_task_status(task):
    status = _orig(task)
    status.pop("resume_percent", None)
    return status
'''

DROP_KEY_MATERIALS = '''
def task_status(task):
    status = _orig(task)
    status.pop("resume_percent", None)
    return status
'''

ADD_KEY_MATERIALS = '''
def task_status(task):
    status = _orig(task)
    status["extra_probe_key"] = 0
    return status
'''

RENAME_KEY_BOTH = '''
def full_task_status(task):
    status = _orig(task)
    status["current_part_name_renamed"] = status.pop("current_part_name", "")
    return status
'''

IDLE_TOTAL_BYTES = '''
def full_task_status(task):
    status = _orig(task)
    if task is None:
        status["total_bytes"] = 7
    return status
'''

# pytest 插件：把共同常量也改掉（只用在「协调改动」那一格）。
# **要改的不止「家」那一处**：别的测试模块是 `from … import STATUS_KEYS` 按值绑定的，
# 真身改常量时它们是**新进程重新 import**（自然拿到新值）；而这里的注入发生在 import 之后，
# 只改 home 那一份的话，import 方仍握着旧集合 → 那一格会红在一个**注入假象**上
# （本单第一版就是这样：收之后 `full:add_key_together` 仍红，看着像「第二道拦还在」——
#  那是我注入方式的问题，不是产品/判据的行为）。故这里把所有持有该名字的模块一起改，
# 忠实模拟「常量被改了」这件事。
CONST_PLUGIN = '''# 由 probe-15-guard-strength.py 生成：把契约常量也补上同一个键（模拟「按文档流程改契约」）。
def pytest_collection_modifyitems(config, items):
    import sys
    updated = None
    for name in ("tests.test_download_status_surface", "tests.test_full_task"):
        module = sys.modules.get(name)
        if module is None or not hasattr(module, "STATUS_KEYS"):
            continue
        if updated is None:
            updated = set(module.STATUS_KEYS) | {"extra_probe_key"}
        module.STATUS_KEYS = set(updated)
'''

# 每格 = (案件名, [(模块, 函数名, 错版源码)], 是否连常量一起改, [(用例文件, -k 或 None)])
# `together` 那一维现在的格子里恒为 False——「按手续加字段」改用 worktree 里的真源码编辑量，
# 见模块 docstring 与 `run-15-evidence.py together`（保留这个维度是为了不重排结构）。
CASES: list[tuple[str, list[tuple[str, str, str]], bool,
                  list[tuple[str, str | None]]]] = [
    ("full:add_key", [("full_task", "full_task_status", ADD_KEY_BOTH)], False,
     [("tests/test_download_status_surface.py", None), ("tests/test_full_task.py", None)]),
    ("full:idle_add_key", [("full_task", "full_task_status", ADD_KEY_IDLE_ONLY)], False,
     [("tests/test_download_status_surface.py", None), ("tests/test_full_task.py", None)]),
    ("full:drop_key", [("full_task", "full_task_status", DROP_KEY_BOTH)], False,
     [("tests/test_download_status_surface.py", None), ("tests/test_full_task.py", None)]),
    ("materials:drop_key", [("materials_task", "task_status", DROP_KEY_MATERIALS)], False,
     [("tests/test_download_status_surface.py", None), ("tests/test_materials_task.py", None)]),
    ("full:rename_key", [("full_task", "full_task_status", RENAME_KEY_BOTH)], False,
     [("tests/test_download_status_surface.py", None), ("tests/test_full_task.py", None)]),
    ("full:idle_total_bytes", [("full_task", "full_task_status", IDLE_TOTAL_BYTES)], False,
     [("tests/test_download_status_surface.py", None), ("tests/test_full_task.py", None)]),
]

SITECUSTOMIZE = '''# 由 probe-15-guard-strength.py 生成：内存里换掉目标实现，跑既有用例看红不红。
import time as _time  # noqa: F401


def _install():
    from contest_generator import full_task as _ft
    from contest_generator import materials_task as _mt

    mods = {"full_task": _ft, "materials_task": _mt}
    for mod_name, fn_name, naive_src in __TARGETS__:
        module = mods[mod_name]
        original = getattr(module, fn_name)
        ns = {"_orig": original, "_time": _time}
        exec(compile(naive_src, "<naive-status>", "exec"), ns)
        setattr(module, fn_name, ns[fn_name])
        installed = getattr(module, fn_name)
        assert installed.__code__.co_filename.startswith("<naive-"), \\
            "错版注入失败：" + mod_name + "." + fn_name


_install()
'''

def build_sitecustomize(targets: list[tuple[str, str, str]]) -> str:
    return SITECUSTOMIZE.replace("__TARGETS__", repr(targets))


def run_one_file(env: dict[str, str], rel: str, drop: str | None = None,
                 plugin: bool = False) -> tuple[str, str]:
    args = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q"]
    if plugin:
        args += ["-p", "probe15_const"]
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
        return "探针失效", f"{label}：错版注入没落到位"
    lines = [ln for ln in (out.stdout or "").strip().splitlines() if ln.strip()]
    summary = next((ln for ln in reversed(lines) if "passed" in ln or "failed" in ln),
                   lines[-1] if lines else "(无输出)")
    failed = [ln.split(" - ")[0][7:] for ln in lines if ln.startswith("FAILED")]
    detail = summary + ("；红在：" + "、".join(failed[:3]) if failed else "")
    if out.returncode == 0:
        return "绿（判据无效）", f"{label}：{detail}"
    return "红（判据有效）", f"{label}：{detail}"


def run(targets: list[tuple[str, str, str]], together: bool,
        files: list[tuple[str, str | None]]) -> list[tuple[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "sitecustomize.py").write_text(
            build_sitecustomize(targets), encoding="utf-8")
        if together:
            (Path(tmp) / "probe15_const.py").write_text(CONST_PLUGIN, encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([tmp, str(ROOT / "src")])
        env["PYTHONIOENCODING"] = "utf-8"
        return [run_one_file(env, rel, drop, plugin=together) for rel, drop in files]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):   # pragma: no cover
        pass
    print("工单 15 错版注入探针：内存里换成错版 → 跑既有用例 → 看红不红\n", flush=True)
    print(f"（逐文件跑、每文件 {CASE_TIMEOUT_SECONDS}s 上限；"
          "「卡住」如实记录、不作判据）\n", flush=True)
    for case, targets, together, files in CASES:
        print(f"== {case} ==", flush=True)
        results = run(targets, together, files)
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
