"""工单 11 的**判据强度探针**：既有用例能不能抓到这两个函数里的错？

本仓库的纪律是「先证明判据会红，再用它判绿」。要判断这两处同形重复值不值得收，
先得知道**既有判据对它们的覆盖强度**——若有一侧的函数改坏了都没人红，那这一侧的重复
就是「没有任何判据在看的行为」，收它等于给无人区加结构约束（还得为此立守卫）。

做法：在被测进程启动时把函数换成**错版**（内存里换，磁盘一个字节不碰），再跑既有用例，
看红不红：

| 错版 | 含义 |
|---|---|
| `_restore_snapshot` 去掉哈希校验 | 快照记 ok 就认，不看盘上内容对不对 |
| `_resolve_download` 只认实例属性 | 丢掉类属性注入那一支 |
| `_resolve_download` 永远返回缺省 | 丢掉实例注入那一支 |

**第一版探针自己栽过一次**：错版是塞进 `'''...'''` 里的代码，里面的 `\"\"\"` 落成
了字面反斜杠 → 插件语法错 → 注入根本没生效 → 四格全绿（看着像「判据都不灵」，
实为探针失真）。故现在：① 错版代码只用一个引号层级；② 每格先**自证注入生效**
（断言被测类的方法已换成错版），注入失败直接判探针失效，不给出「绿」的结论。

用法：python .scratch/resumable-download/probe-11-guard-strength.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 单格上限。**别把 timeout 当「慢」处理**：本机会间歇性卡住（上次整支探针就是这样
# 十分钟没输出、被我按中断杀掉）——超时就如实报「探针失效」，不拿它当判据。
# 60s 的依据：本机这些文件单独跑都在 4～18s；卡住的那格是**真下载器**发不出去、
# 在重试退避里打转（实测 `always_default` 错版会让 materials 那批卡满 90s+），
# 那种格本来也不该给出判据。
CASE_TIMEOUT_SECONDS = 60

NAIVE_RESTORE_FULL = '''
def _restore_snapshot(self):
    snapshot = self.task_dir / SNAPSHOT_FILENAME
    if not snapshot.is_file():
        return
    try:
        data = json.loads(snapshot.read_text(encoding="utf-8"))
    except Exception:
        return
    saved = {p["name"]: p for p in data.get("parts") or []}
    for part in self.parts:
        saved_part = saved.get(part.name)
        if not saved_part or not saved_part.get("ok"):
            continue
        part.ok = True
        part.dest = str(saved_part.get("dest") or "")
        part.downloaded_bytes = part.size
'''

NAIVE_RESTORE_MATERIALS = '''
def _restore_snapshot(self):
    snapshot = self.task_dir / SNAPSHOT_FILENAME
    if not snapshot.is_file():
        return
    try:
        data = json.loads(snapshot.read_text(encoding="utf-8"))
    except Exception:
        return
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
            part.ok = True
            part.dest = str(saved_part.get("dest") or "")
            part.downloaded_bytes = part.size
'''

NAIVE_RESOLVE_ONLY_INSTANCE = '''
def _resolve_download(self):
    instance = self.__dict__.get("_download")
    if instance is None:
        return resumable_download, True
    return instance, False
'''

NAIVE_RESOLVE_ALWAYS_DEFAULT = '''
def _resolve_download(self):
    return resumable_download, True
'''

PLUGIN_TEMPLATE = """# 由 probe-11-guard-strength.py 生成：内存里换掉目标函数，跑既有用例看红不红。
import json as _json  # noqa: F401

TARGET = __TARGET__
WHICH = __WHICH__

_NAIVE_RESTORE = '''__NAIVE_RESTORE__'''
_NAIVE_RESOLVE = '''__NAIVE_RESOLVE__'''


def _install():
    from contest_generator import full_task as ft
    from contest_generator import materials_task as mt

    if TARGET == "_restore_snapshot":
        src = _NAIVE_RESTORE.strip()
        ns = {"json": _json, "SNAPSHOT_FILENAME":
              ft.SNAPSHOT_FILENAME if WHICH == "full" else mt.SNAPSHOT_FILENAME}
        exec(compile(src, "<naive-restore>", "exec"), ns)
        cls = ft.FullDownloadTask if WHICH == "full" else mt.ApplyTask
        cls._restore_snapshot = ns["_restore_snapshot"]
    else:
        from contest_generator.download_resume import resumable_download
        ns = {"resumable_download": resumable_download}
        exec(compile(_NAIVE_RESOLVE.strip(), "<naive-resolve>", "exec"), ns)
        ft.FullDownloadTask._resolve_download = ns["_resolve_download"]
        mt.ApplyTask._resolve_download = ns["_resolve_download"]

    # 自证注入生效（探针的第一版就是在这里失真的）：**本格那个类**的方法必须真的换成错版。
    # （只查本格的类：`sitecustomize` 里断言另一个类会被真实 pytest 当作
    #  `Error in sitecustomize` 报出来，虽不致命但会污染判读。）
    from contest_generator import full_task as _ft
    from contest_generator import materials_task as _mt
    checked = ((_ft, _ft.FullDownloadTask),) if (TARGET == "_restore_snapshot" and WHICH == "full") \
        else ((_mt, _mt.ApplyTask),) if TARGET == "_restore_snapshot" \
        else ((_ft, _ft.FullDownloadTask), (_mt, _mt.ApplyTask))
    for mod, cls in checked:
        fn = getattr(cls, TARGET)
        assert fn.__code__.co_filename.startswith("<naive-"), (
            f"错版注入失败：{cls.__name__}.{TARGET} 仍来自 {fn.__code__.co_filename}"
        )


_install()
"""

CASES = [
    ("_restore_snapshot", "full", ["tests/test_full_task.py", "tests/test_full_apply.py",
                                   "tests/test_download_status_surface.py"]),
    ("_restore_snapshot", "materials", ["tests/test_materials_task.py",
                                        "tests/test_download_status_surface.py"]),
    ("_resolve_download", "only_instance", ["tests/test_full_task.py",
                                            "tests/test_full_apply.py",
                                            "tests/test_materials_task.py",
                                            "tests/test_download_status_surface.py"]),
    ("_resolve_download", "always_default", ["tests/test_full_task.py",
                                             "tests/test_full_apply.py",
                                             "tests/test_materials_task.py",
                                             "tests/test_download_status_surface.py"]),
]


def build_plugin(target: str, which: str) -> str:
    naive = {
        "full": NAIVE_RESTORE_FULL,
        "materials": NAIVE_RESTORE_MATERIALS,
    }.get(which, "")
    resolve = ""
    if which == "only_instance":
        resolve = NAIVE_RESOLVE_ONLY_INSTANCE
    elif which == "always_default":
        resolve = NAIVE_RESOLVE_ALWAYS_DEFAULT
    return (PLUGIN_TEMPLATE
            .replace("__TARGET__", repr(target))
            .replace("__WHICH__", repr(which))
            .replace("__NAIVE_RESTORE__", naive.strip())
            .replace("__NAIVE_RESOLVE__", resolve.strip()))


def run(target: str, which: str, files: list[str]) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "sitecustomize.py").write_text(
            build_plugin(target, which), encoding="utf-8"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([tmp, str(ROOT / "src")])
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            out = subprocess.run(
                [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", *files],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                errors="replace", env=env, timeout=CASE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return "探针失效", (f"超过 {CASE_TIMEOUT_SECONDS}s 没跑完"
                              "（按中断处理，不当作「绿」也不当作「红」）")
        text = (out.stdout or "") + (out.stderr or "")
        if "错版注入失败" in text:
            return "探针失效", "错版注入没落到类上（见下方输出）"
        lines = [ln for ln in (out.stdout or "").strip().splitlines() if ln.strip()]
        summary = lines[-1] if lines else "(无输出)"
        failed = [ln for ln in lines if ln.startswith("FAILED")]
        detail = (f"{summary}；首个红：{failed[0].split(' - ')[0][7:]}"
                  if failed else summary)
        return ("红（判据有效）" if out.returncode != 0 else "绿（判据无效）"), detail


def main() -> int:
    print("错版注入探针：内存里换成错版 → 跑既有用例 → 看红不红\n", flush=True)
    for target, which, files in CASES:
        print(f"  ... 跑 {target} / {which}", flush=True)
        verdict, detail = run(target, which, files)
        print(f"  [{verdict}] {target} / {which}")
        print(f"      用例：{' '.join(Path(f).name for f in files)}")
        print(f"      结果：{detail}\n", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
