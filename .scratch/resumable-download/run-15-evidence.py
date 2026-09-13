"""工单 15 的**证据落盘器**：把量具、探针、逐文件全套的输出写成 UTF-8 文件。

为什么单独一支（工单 11/12 的教训，直接照抄）：`Tee-Object` 与 PowerShell 的 `>`
在 Windows 下写的是 **UTF-16**；补充记录也不走 shell 追加——写在脚本里，由脚本落盘。

用法：
  python .scratch/resumable-download/run-15-evidence.py            # 量具 + 探针
  python .scratch/resumable-download/run-15-evidence.py suite      # 再加逐文件全套（约 6 分钟）
  python .scratch/resumable-download/run-15-evidence.py before     # 基线提交上的同一支探针（收之前）
  python .scratch/resumable-download/run-15-evidence.py real-tree  # 守卫的真身实测（放副本→红→删）
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# 探针自己栽过的地方（**评审与本单的真身实测各翻出一处**，写在脚本里落盘）：
# ① 第一版错版把整支投影抄成错版，非目标分支只能填桩（`return {"state": "x"}`）——
#    大量用例因为桩而红，「红在谁身上」这个问题直接被污染。改成**包装式**错版：
#    `_orig` 是真实现，只扰动要测的那一处（工单 13 第 1 条「分离变量」）。
# ② 「协调改动」那一格起初只换产品、忘了改共同常量，于是它红的理由与普通格一样，
#    答不出「第二处副本到底拦住了什么」。现在那一格配一支 pytest 插件，
#    在 collection 之后把 `STATUS_KEYS` 也补上同一个键（= 模拟文档写明的合法流程）。
# ③ 结构守卫第一版对读不了的 `.py` **静默跳过**：真身实测时 PowerShell 写的副本带 BOM，
#    `ast.parse` 抛错 → 被吞掉 → 守卫照样绿（假绿）。已改成「BOM 用 utf-8-sig 吃掉，
#    真解析不了就大声红」——**守卫静默跳过等于装饰**（工单 10/12 的坑）。
PROBE_NOTE = """
== 补充：探针与守卫的设计、以及三处已修的失真（脚本里写死，不走 shell 追加）==
1. **错版一律是「包装真实现、只扰动要测的那一处」**：`_orig(task)` 走真实现，再对返回的
   dict 做一件事（加一个键 / 少一个键 / 改名 / 改一个空态取值）。第一版把整支投影抄成
   错版，非目标分支只能填桩——那会让大量用例因为桩而红，「红在谁身上」直接失效。
2. **「协调改动」那一格**（`full:add_key_together`）= 产品两侧各多一个键 + 把共同常量
   `STATUS_KEYS` 也补上同一个键（这正是本文件 docstring 写明的加字段流程）。
   它答的是本单的核心问题：**字面副本是不是一份「独立见证」**。
   为此另配一支 pytest 插件（collection 之后改模块属性——`assert set(status) == STATUS_KEYS`
   取的是模块全局、调用时现取，故改得动）。
3. **结构守卫不许静默跳过**：守卫要扫 `tests/**/*.py` 找「又抄一遍 12 键」的集合；
   第一版 `except SyntaxError: continue`，真身实测时一个带 BOM 的副本被悄悄跳过、
   守卫报绿（**假绿**）。现在 BOM 用 `utf-8-sig` 吃掉，读不了 / 解析不了都让用例红。
   真身实测取证：造一份副本 → 守卫转红并指名 `_tmp_second_copy.py:2` → 删掉 → 复跑 32 passed。
4. **两版对照**：`verify-15-{guard-strength-before,guard-strength}.txt` 是**收之前 / 收之后**
   同一套错版注入的结果——取舍（少了哪一道拦、哪些格没变）就拿这两份对比着读。
"""


def run_script(name: str, *args: str) -> str:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run(
        [sys.executable, str(HERE / name), *args], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    return (out.stdout or "") + (out.stderr or "")


def write(target: str, text: str) -> None:
    (HERE / target).write_text(text, encoding="utf-8", newline="\n")
    print(f"  写入 {target}（{len(text)} 字符，UTF-8）")


def run_in_baseline_worktree(base: str) -> str:
    """在**基线提交**的临时 worktree 里跑同一支探针 → 「收之前」那一版网格。

    为什么费这个劲：本单的取舍（收之前多一道拦、收之后少一道）必须**两版对照**才看得见，
    而工作区只有一版。纪律是「改动前那份从 git 取」——测试文件的基线版本同理，
    故用 `git worktree`（用完即拆），而不是靠人记住旧数字。
    """
    import shutil
    import tempfile

    holder = Path(tempfile.mkdtemp(prefix="firstep-15-base-"))
    worktree = holder / "tree"
    try:
        # `git worktree add` 在 try 里：否则它失败时 `holder`（以及可能的半份检出）没人收
        # ——评审指出第一版把 `mkdtemp` 放在 try 外，失败路径会漏一份整仓拷贝。
        subprocess.run(["git", "worktree", "add", "--detach", str(worktree), base],
                       cwd=ROOT, check=True, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
        dst = worktree / ".scratch" / "resumable-download"
        dst.mkdir(parents=True, exist_ok=True)
        for name in ("probe-15-guard-strength.py",):
            shutil.copy2(HERE / name, dst / name)
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        out = subprocess.run(
            [sys.executable, str(dst / "probe-15-guard-strength.py")],
            cwd=worktree, capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=env,
        )
        header = (f"# 本文件 = 工单 15 的错版注入探针在**基线提交 {base}** 上的输出"
                  f"（`git worktree` 临时检出，可复跑：\n"
                  f"#   python .scratch/resumable-download/run-15-evidence.py before\n"
                  f"# 用途：与现状那一份对照，看「收成一份」改变了哪几格。\n\n")
        return header + (out.stdout or "") + (out.stderr or "")
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
        shutil.rmtree(holder, ignore_errors=True)      # 连空壳目录一起收干净


def guard_real_tree_check() -> str:
    """守卫的**真身实测**：往 `tests/` 真放一份第二副本 → 守卫必须指名转红 → 当场删掉。

    为什么要单独跑这一格：反向验证那两条用例喂的是 `%TEMP%` 副本，**没有一格是「真身树里
    多了一份副本」**（评审指出：探针那七格改的都是产品侧）。守卫的「会红」必须有一份
    面向**真身目录结构**的实测，否则它可能只是「对 tmp 目录有效」。
    用 `try/finally` 保证文件一定被删；跑完打印 `git status --short tests/` 供人核对。
    """
    here = HERE / "verify-15-guard-real-tree.txt"
    probe_file = ROOT / "tests" / "_tmp_second_copy.py"
    lines = ["# 工单 15：结构守卫的**真身实测**（临时往 tests/ 放一份第二副本 → 看守卫红不红）",
             "# 脚本化可复跑：python .scratch/resumable-download/run-15-evidence.py real-tree",
             ""]
    try:
        probe_file.write_text(
            "def test_tmp_second_copy():\n"
            "    assert set({\n"
            "        'state', 'parts', 'total_downloaded_bytes', 'total_bytes', 'speed_bps',\n"
            "        'current_part_name', 'error', 'message', 'retry_count', 'retrying',\n"
            "        'error_kind', 'resume_percent',\n"
            "    }) == set()\n",
            encoding="utf-8")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
             "tests/test_download_status_surface.py::test_status_contract_has_a_single_home"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=env)
        lines += ["## 放了第二副本之后（期望：**红**，并指名 _tmp_second_copy.py）",
                  (out.stdout or "") + (out.stderr or ""), ""]
    finally:
        probe_file.unlink(missing_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
         "tests/test_download_status_surface.py"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env)
    lines += ["## 删掉副本之后（期望：全绿；并核对 tests/ 干净）",
              (out.stdout or "") + (out.stderr or ""), ""]
    status = subprocess.run(["git", "status", "--short", "tests/"], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    lines += ["## git status --short tests/（应只有本单改的那两个文件）",
              (status.stdout or "(空)").strip(), ""]
    text = "\n".join(lines)
    write("verify-15-guard-real-tree.txt", text)
    return text


def together_check(base: str = "0344eb61") -> str:
    """量「按手续加一个字段」在两版下的行为：**在临时 worktree 里做真源码编辑**。

    为什么不能用运行时注入：本单新增的结构守卫把「内存里的 `STATUS_KEYS`」与「源码文本里
    那份契约」绑在一起——运行时改常量会被守卫读成自相矛盾（探针第一版就是这么红的，
    红在注入假象上）。**按手续加字段**这件事只有在源码上做才忠实：
      ① 产品两侧的空态 / 有态载荷各加一个 `extra_probe_key`（4 处真编辑）；
      ② `STATUS_KEYS` 的来源 `NEW_KEYS` 里加上同名键（1 处真编辑）；
      ③ 跑那两个测试文件，看有没有人红。
    两版对照：基线 `0344eb61`（内联字面副本还在）vs 现状（已收口）。
    """
    import shutil
    import tempfile

    def scenario(label: str, ref: str, use_worktree_tests: bool) -> list[str]:
        holder = Path(tempfile.mkdtemp(prefix="firstep-15-together-"))
        worktree = holder / "tree"
        out_lines = [f"## {label}（worktree @ {ref}{'，测试文件取工作区现状' if use_worktree_tests else ''}）"]
        try:
            subprocess.run(["git", "worktree", "add", "--detach", str(worktree), ref],
                           cwd=ROOT, check=True, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
            if use_worktree_tests:
                for name in ("test_download_status_surface.py", "test_full_task.py"):
                    shutil.copy2(ROOT / "tests" / name, worktree / "tests" / name)
            edits = [
                (worktree / "src/contest_generator/full_task.py",
                 '        "resume_percent": -1,\n',
                 '        "resume_percent": -1,\n        "extra_probe_key": 0,\n'),
                (worktree / "src/contest_generator/full_task.py",
                 '        "resume_percent": int(task.resume_percent),\n',
                 '        "resume_percent": int(task.resume_percent),\n'
                 '        "extra_probe_key": 0,\n'),
                (worktree / "src/contest_generator/materials_task.py",
                 '            "resume_percent": -1,\n',
                 '            "resume_percent": -1,\n            "extra_probe_key": 0,\n'),
                (worktree / "src/contest_generator/materials_task.py",
                 '        "resume_percent": int(task.resume_percent),\n',
                 '        "resume_percent": int(task.resume_percent),\n'
                 '        "extra_probe_key": 0,\n'),
                (worktree / "tests/test_download_status_surface.py",
                 'NEW_KEYS = {"retry_count", "retrying", "error_kind", "resume_percent"}\n',
                 'NEW_KEYS = {"retry_count", "retrying", "error_kind", "resume_percent",\n'
                 '            "extra_probe_key"}\n'),
            ]
            for path, old, new in edits:
                text = path.read_text(encoding="utf-8")
                assert old in text, f"编辑锚点没命中：{path.name} / {old.strip()!r}"
                path.write_text(text.replace(old, new, 1), encoding="utf-8")
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            out = subprocess.run(
                [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
                 "tests/test_download_status_surface.py", "tests/test_full_task.py"],
                cwd=worktree, capture_output=True, text=True, encoding="utf-8",
                errors="replace", env=env)
            out_lines += [(out.stdout or "") + (out.stderr or "")]
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
            shutil.rmtree(holder, ignore_errors=True)
        return out_lines

    lines = ["# 工单 15：按手续加一个字段（产品两侧 + 契约常量来源），两版对照",
             "# 脚本化可复跑：python .scratch/resumable-download/run-15-evidence.py together",
             "# 期望：基线版 `test_full_task.py` 红（那份内联字面副本挡了一下）；现状版全绿（手续自洽）。",
             ""]
    lines += scenario("基线（内联字面副本还在）", base, use_worktree_tests=False)
    lines += [""]
    lines += scenario("现状（已收口）", "HEAD", use_worktree_tests=True)
    lines += [""]
    text = "\n".join(lines)
    write("verify-15-together.txt", text)
    return text


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "before":
        base = sys.argv[2] if len(sys.argv) > 2 else "0344eb61"
        write("verify-15-guard-strength-before.txt", run_in_baseline_worktree(base))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "real-tree":
        guard_real_tree_check()
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "together":
        together_check(sys.argv[2] if len(sys.argv) > 2 else "0344eb61")
        return 0
    write("verify-15-duplication.txt",
          run_script("measure-15-status-key-copies.py", "0344eb61"))
    write("verify-15-guard-strength.txt",
          run_script("probe-15-guard-strength.py") + PROBE_NOTE)
    if len(sys.argv) > 1 and sys.argv[1] == "suite":
        timeout = sys.argv[2] if len(sys.argv) > 2 else "120"
        write("verify-15-suite.txt", run_script("run-11-suite.py", timeout))
    return 0


if __name__ == "__main__":
    sys.exit(main())
