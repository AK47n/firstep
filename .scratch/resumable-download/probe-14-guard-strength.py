"""工单 14 的**判据强度探针**：错版注入 → 跑既有用例 → 看红不红。

要答的问题不是「它看着像不像死代码」，而是：**测试侧的既有判据，对 `download_part`
到底有没有执行路径**？

| 想答的问题 | 对应格 |
|---|---|
| 把 `materials_task.download_part` 换成**抛异常的炸弹**，既有用例会不会红？ | `download_part_boom` |
| 同一套注入机制打在**生产路径真会解析到的**实现上，会不会红？ | `resolve_boom`（**阳性对照**） |

**为什么要那格阳性对照，以及它的靶子必须是哪个名字**（第一版就在这里栽了，见下）：
只跑「炸弹没人碰」得到的绿，也可能来自「注入根本没生效 / 那批用例本来就跑不到这条路径」。
阳性对照要排掉这种解释，它的注入点就必须是**生产路径真的会读的那个名字**——
`task_download.resolve_task_download` 的解析顺序是
「实例属性 `_download` → 类属性 `_download` → **`task_download` 模块自己那份
`resumable_download` 绑定**」。所以：
  - 打 `download_resume.resumable_download` **没用**（导入期已绑死，解析根本不读它）；
  - 打 `materials_task.resumable_download` **也没用**（实例属性已经把解析挡回缺省那一支）；
  - **只有打 `task_download.resumable_download` 才落在靶子上**，并且自证要断
    「`resolve_task_download(<真任务实例>)[0] is <炸弹>」——那才是「解析真的拿到炸弹」。
第一版正是打了 `download_resume.resumable_download`：它确实转红了（5 + 12 failed），
但**红在身份断言**（用例里 `assert task._download is resumable_download` 两侧取到不同对象），
没有一条是「下载路径被执行」。那格红**不为绿背书**——已按上面的靶子重做。

**纪律（工单 11/12 用血换的）**：
  - 每格先**自证注入生效**（断言目标对象的 `__code__.co_filename` 已是 `<naive-…>`；
    阳性对照另加一条「解析结果就是它」）；
  - 逐**文件**跑（本机会间歇性卡死，多文件一起跑会卡、单文件跑就完事）；
  - 超时如实记「卡住（不作判据）」，不折算成绿。

另附第三节：`.scratch` 活口的**运行时取证**——静态量到「谁 import / 谁调用」还不够，
这里把三支证据工具**真的用它的那一行**执行一遍，证明那不是 grep 假象。

用法：python .scratch/resumable-download/probe-14-guard-strength.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASE_TIMEOUT_SECONDS = 120

# 子进程一律按 UTF-8 收发（本机控制台是 GBK；探针第一版在「活口」那一节
# 因为回程字节里带替换字符 U+FFFD 而 `UnicodeEncodeError` 崩掉、退出码 1——
# 复跑者会误以为「跑完了」，其实第三节整节没出来）。
CHILD_ENV_EXTRA = {"PYTHONIOENCODING": "utf-8"}

# 错版正文：只用一个引号层级（外层 """，里面一律双引号），避免工单 11 踩过的
# 「三引号里嵌转义 → 插件语法错 → 注入静默失效」那条坑。
#
# 炸弹**必须经 `exec(compile(src, "<naive-boom>", "exec"))` 装上**，不能在插件里直接
# `def`：自证那一句查的是 `__code__.co_filename` 是不是 `<naive-…>`，就地 `def` 得到的是
# sitecustomize 的临时文件路径 → 自证永远失败 → 探针会一辈子报「注入失败」。
BOOM_SRC = '''
def _boom(*args, **kwargs):
    raise RuntimeError("<naive-boom> 被调用了（探针注入的炸弹）")
'''

# 数「炸弹被真调用了几次」用的记号：pytest 的失败回溯里会带上这句。
# **为什么要数它**：红的理由可以是「身份断言不相等」（用例里 `assert task._download is
# resumable_download` 两侧对象不同）也可以是「炸弹真被执行」。只有后者能替绿背书——
# 探针第一版就是被前者骗了（红得很像，其实下载路径一次也没跑）。
BOOM_MARK = "<naive-boom> 被调用了"

PLUGIN_TEMPLATE = '''# 由 probe-14-guard-strength.py 生成：内存里换掉目标实现，跑既有用例看红不红。
import json as _json  # noqa: F401
import pathlib as _pathlib
import tempfile as _tempfile


def _mk_mats_task(mt):
    return mt.ApplyTask(
        task_dir=_pathlib.Path(_tempfile.mkdtemp()) / "updates",
        batches=[{
            "slug": "s", "name": "n",
            "parts": [{"zip_url": "http://127.0.0.1:1/x.zip", "zip_name": "x.zip",
                       "size_bytes": 1, "sha256": "0" * 64}],
        }],
        snapshot_interval=0.0,
    )


def _mk_full_task(ft):
    return ft.FullDownloadTask(
        task_dir=_pathlib.Path(_tempfile.mkdtemp()) / "updates",
        parts=[{"name": "x.zip", "url": "http://127.0.0.1:1/x.zip",
                "size": 1, "sha256": "0" * 64}],
        snapshot_interval=0.0,
    )


def _install():
    from contest_generator import materials_task as mt
    from contest_generator import full_task as ft
    from contest_generator import task_download as td

    ns = {}
    exec(compile(__BOOM_SRC__, "<naive-boom>", "exec"), ns)
    boom = ns["_boom"]

    if __KIND__ == "download_part_boom":
        mt.download_part = boom
        fn = mt.download_part
        assert fn.__code__.co_filename.startswith("<naive-"), "错版注入失败：" + __KIND__
        return

    assert __KIND__ == "resolve_boom", "未知的 kind: " + __KIND__
    # **缺省下载器这条路上有三个绑定**，少换一个，解析结果就不是「炸弹 + 算缺省」：
    #   ① 构造期 `__init__` 读的是**任务模块自己的**模块名（`self._download = … or resumable_download`）；
    #   ② 类属性 `_download`（两个任务类各自 `staticmethod(resumable_download)`，类创建时就绑死了）；
    #   ③ 解析期算 `is_default` 用的是 **`task_download`** 那份绑定。
    # 只换 ③ 的话：实例属性仍是真实现 → 解析走进 `return instance, False` 那一支，
    # 炸弹根本没上（第一版就是这么失效的，探针如实报了「探针失效」）。
    mt.resumable_download = boom
    ft.resumable_download = boom
    td.resumable_download = boom
    mt.ApplyTask._download = staticmethod(boom)
    ft.FullDownloadTask._download = staticmethod(boom)

    for label, task in (("ApplyTask", _mk_mats_task(mt)),
                        ("FullDownloadTask", _mk_full_task(ft))):
        chosen, is_default = td.resolve_task_download(task)
        assert chosen is boom, label + "：注入没进到生产解析结果（打错了名字）"
        assert is_default is True, label + "：解析结果没被认成缺省实现（换漏了绑定）"


_install()
'''

# 每格 = (案件名, 注入种类, [(用例文件, `-k` 表达式或 None)])。
# `-k` 只在本机已知会打转的那支用例上用（`test_message_cleared_when_backoff_window_closes`
# 在「时序被注入改动」时会稳定打转，见 docs/agents/local-environment.md 2.5）——
# 本单的两格都不改时序（只换实现），故先不带 `-k`；真卡住就在结果里如实记。
CASES: list[tuple[str, str, list[tuple[str, str | None]]]] = [
    ("download_part_boom", "download_part_boom",
     [("tests/test_materials_task.py", None),
      ("tests/test_full_task.py", None),
      ("tests/test_download_status_surface.py", None)]),
    ("resolve_boom", "resolve_boom",
     [("tests/test_materials_task.py", None),
      ("tests/test_full_task.py", None)]),
]


def build_plugin(kind: str) -> str:
    return (PLUGIN_TEMPLATE
            .replace("__KIND__", repr(kind))
            .replace("__BOOM_SRC__", repr(BOOM_SRC)))


def run_one_file(env: dict[str, str], rel: str, drop: str | None = None) -> tuple[str, str]:
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
        return "探针失效", f"{label}：错版注入没落到位"
    lines = [ln for ln in (out.stdout or "").strip().splitlines() if ln.strip()]
    summary = next((ln for ln in reversed(lines) if "passed" in ln or "failed" in ln),
                   lines[-1] if lines else "(无输出)")
    failed = [ln for ln in lines if ln.startswith("FAILED")]
    # 炸弹真被调用了几次（失败回溯里会带这句）。这一类红才是「生产路径被执行」的红；
    # 「身份断言不相等」那种红不算——两者要分开报，别让前者替绿背书。
    bomb_hits = text.count(BOOM_MARK)
    detail = (f"{summary}；炸弹被执行 {bomb_hits} 次"
              + (f"；首个红：{failed[0].split(' - ')[0][7:]}" if failed else ""))
    if out.returncode == 0:
        return "绿（判据无效）", f"{label}：{detail}"
    return "红（判据有效）", f"{label}：{detail}"


def run_case(kind: str, files: list[tuple[str, str | None]]) -> list[tuple[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "sitecustomize.py").write_text(build_plugin(kind), encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([tmp, str(ROOT / "src")])
        env["PYTHONIOENCODING"] = "utf-8"
        return [run_one_file(env, rel, drop) for rel, drop in files]


def live_callers() -> list[tuple[str, str]]:
    """`.scratch` 活口的运行时取证：把每支工具**真正用它的那一行**执行一遍。

    静态量到「谁 import / 谁调用」可能只是 grep 假象（比如 import 了却从不调用）。
    这里按每支工具自己的用法跑一次：
      - `probe-01-resume.py`：调它的 `load_impl("plain")`，看返回的是不是产品函数；
      - `probe-01-negative.py`：把 `RUNNER_TEMPLATE` 里那句 import 原样 exec 一遍；
      - `.scratch/full-download/e2e_full_download.py`：同上（取那一行 import）。
    """
    code = r'''
import importlib.util, pathlib, sys
sys.path.insert(0, __SRC__)
from contest_generator import materials_task as _mt

out = []

# ① probe-01-resume.py：--impl plain 与 auto 兜底都从 load_impl 取
spec = importlib.util.spec_from_file_location("probe01", __PROBE1__)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fn, name = mod.load_impl("plain")
out.append(("probe-01-resume.py: load_impl('plain')",
            name + " -> " + getattr(fn, "__module__", "?") + "."
            + getattr(fn, "__qualname__", "?")
            + "；是产品那份 download_part = " + str(fn is _mt.download_part)))

# ② probe-01-negative.py：RUNNER_TEMPLATE 里那句 import（字符串模板，会被落盘执行）
neg = pathlib.Path(__PROBE2__).read_text(encoding="utf-8")
line = next(ln for ln in neg.splitlines()
            if ln.startswith("from contest_generator.materials_task import download_part"))
ns = {}
exec(compile(line, "<negative-runner-template>", "exec"), ns)
out.append(("probe-01-negative.py: 模板里的 import",
            line.strip() + " -> 解析到产品函数的同一个对象 = "
            + str(ns["_plain"] is _mt.download_part)))

# ③ full-download 的 e2e 脚本：函数体里那句 import
e2e = pathlib.Path(__E2E__).read_text(encoding="utf-8")
line3 = next(ln.strip() for ln in e2e.splitlines()
             if ln.strip().startswith(
                 "from contest_generator.materials_task import download_part"))
ns3 = {}
exec(compile(line3, "<e2e-import>", "exec"), ns3)
out.append(("full-download/e2e_full_download.py: 函数体里的 import",
            line3 + " -> 同一个对象 = " + str(ns3["download_part"] is _mt.download_part)))

for label, verdict in out:
    print(label + " || " + verdict)
'''
    script = (code
              .replace("__SRC__", repr(str(ROOT / "src")))
              .replace("__PROBE1__", repr(str(ROOT / ".scratch/resumable-download/probe-01-resume.py")))
              .replace("__PROBE2__", repr(str(ROOT / ".scratch/resumable-download/probe-01-negative.py")))
              .replace("__E2E__", repr(str(ROOT / ".scratch/full-download/e2e_full_download.py"))))
    out = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace",
                         env={**os.environ, **CHILD_ENV_EXTRA},
                         timeout=CASE_TIMEOUT_SECONDS)
    results: list[tuple[str, str]] = []
    for line in (out.stdout or "").splitlines():
        if "||" in line:
            label, verdict = line.split("||", 1)
            results.append((label.strip(), verdict.strip()))
    if not results:
        results.append(("（活口取证失败）", (out.stdout or "") + (out.stderr or "")))
    return results


def main() -> int:
    # 自身 stdout 也钉成 UTF-8 + errors="replace"：本机控制台是 GBK，
    # 若子进程回程里带了 GBK 编不出的字符（替换字符 U+FFFD 就是），
    # `print` 会 `UnicodeEncodeError` 炸掉**整节判据**并让退出码变 1——
    # 复跑者只看到前半截，最容易误判成「跑完了」（第一版实测）。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - 老解释器/被重定向
        pass
    print("工单 14 错版注入探针：内存里换成错版 → 跑既有用例 → 看红不红\n", flush=True)
    print(f"（逐文件跑、每文件 {CASE_TIMEOUT_SECONDS}s 上限；"
          "「卡住」如实记录、不作判据）\n", flush=True)
    for case, kind, files in CASES:
        print(f"== {case} ==", flush=True)
        results = run_case(kind, files)
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

    print("== .scratch 活口（运行时取证：把每支工具真正用它的那一行跑一遍） ==")
    for label, verdict in live_callers():
        print(f"      [{label}] {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
