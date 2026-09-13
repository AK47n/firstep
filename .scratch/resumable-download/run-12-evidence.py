"""工单 12 的**证据落盘器**：把量具、探针、单格复跑的输出写成 UTF-8 文件。

为什么单独一支（工单 11 的教训，直接照抄）：`Tee-Object` 与 PowerShell 的 `>`
在 Windows 下写的是 **UTF-16**（本单第一版 `verify-12-guard-strength.txt` 就是这么落坏的，
read 工具直接报「binary file」）；补充记录也不走 shell 追加——写在脚本里，由脚本落盘。

用法：
  python .scratch/resumable-download/run-12-evidence.py            # 量具 + 探针
  python .scratch/resumable-download/run-12-evidence.py suite 120  # 再加逐文件全套
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# 单格复跑的原始输出（诊断用）。**为什么要留这段**：探针只给「红/绿/卡住」三态，
# 看不到「为什么卡住」；本单在这上面栽过三次，**三次都是探针自己失真、不是产品行为**：
# ① 错版把「速度窗口记账」一起丢了 → 用例在注入下空转；
# ② 错版正文里的 `_time` 没进 `exec` 的名字空间 → NameError 被重试路径吞掉 → 同样空转；
# ③ `from_dict` 的自证写了 `.__func__`（从类上取 staticmethod 已解包成普通函数）→ 误报注入失败。
RERUN_NOTE = """
== 补充：单格复跑的原始输出（诊断用，脚本 rerun-12-case.py 逐文件跑）==
$ python .scratch/resumable-download/rerun-12-case.py full:no_retry_fields 180
  [红（判据有效）] tests/test_full_task.py：5 failed, 28 passed
      FAILED ...::test_status_shows_retrying_message_during_backoff
      FAILED ...::test_status_retrying_false_while_resuming_message_present
      FAILED ...::test_ignored_range_retry_message_says_from_zero
      FAILED ...::test_cancel_leaves_error_kind_empty - KeyError
      FAILED ...::test_status_idle_shape - KeyError: 'total_bytes'
  [卡住（不作判据）] tests/test_download_status_surface.py 超过 180s 没跑完
      -> faulthandler 转储（`-o faulthandler_timeout=25 -v -s`）把打转点钉在
         tests/test_download_status_surface.py:355 → test_message_cleared_when_backoff_window_closes
         → 它的 spy（第 347 行）→ download_resume.task_download → task_download.download_and_verify
      -> 重跑三次都是「稳定卡死」（>600s 也没完），不是随机抖动；
         处置 = 这一支用例在该格用 `-k 'not test_message_cleared_when_backoff_window_closes'`
         排除掉，**其余 27 支照跑**（该格结果见上方正文）。
$ python .scratch/resumable-download/rerun-12-case.py from_dict_boom 120
  （本单改动**之前**）rc=0 81 passed —— 炸弹没被碰到 = 三处 from_dict 零执行路径。
  stderr: Error in sitecustomize; AttributeError: 'function' object has no attribute '__func__'
      -> 探针自证写法错（从类上取 staticmethod 已解包成普通函数），**不是注入没生效**；
         改成查类属性表里那份原始 staticmethod 后复跑：注入生效。
  （新守卫落地**之后**）同一格转 **红**：`test_part_state_shape_has_a_single_contract`
  的 `assert not hasattr(..., "from_dict")` 抓到了炸弹 —— 「零调用点」只对**改动前的用例集**
  成立；本单落地后，这条运行时证据由**新守卫**接手（见工单「判据强度」那一节）。
"""


def run_script(name: str, *args: str) -> str:
    out = subprocess.run(
        [sys.executable, str(HERE / name), *args], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return (out.stdout or "") + (out.stderr or "")


def write(target: str, text: str) -> None:
    (HERE / target).write_text(text, encoding="utf-8", newline="\n")
    print(f"  写入 {target}（{len(text)} 字符，UTF-8）")


def main() -> int:
    # 量具 / 探针的 stdout 全部**在内存里取回再落盘**（不走 shell 重定向、也不让
    # 子进程自己写目标文件——两条都踩过：PowerShell 写 UTF-16，子进程自写会与
    # 本脚本的 `write` 抢同一个文件）。
    write("verify-12-duplication.txt",
          run_script("measure-12-twin-candidates.py", "5461f39d"))
    write("verify-12-guard-strength.txt",
          run_script("probe-12-guard-strength.py") + RERUN_NOTE)
    if len(sys.argv) > 1 and sys.argv[1] == "suite":
        timeout = sys.argv[2] if len(sys.argv) > 2 else "120"
        write("verify-12-suite.txt", run_script("run-11-suite.py", timeout))
    return 0


if __name__ == "__main__":
    sys.exit(main())
