"""工单 14 的**证据落盘器**：把量具、探针、逐文件全套的输出写成 UTF-8 文件。

为什么单独一支（工单 11/12 的教训，直接照抄）：`Tee-Object` 与 PowerShell 的 `>`
在 Windows 下写的是 **UTF-16**（read 工具直接报「binary file」）；补充记录也不走
shell 追加——写在脚本里，由脚本落盘。

用法：
  python .scratch/resumable-download/run-14-evidence.py            # 量具 + 探针
  python .scratch/resumable-download/run-14-evidence.py suite      # 再加逐文件全套（约 9 分钟）
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# 探针自己栽过的地方（写在脚本里落盘，不走 shell 追加）。**这三处都是评审当场翻出来的**，
# 不是事后补的漂亮话：
# ① **阳性对照打错了靶子**：第一版把炸弹装在 `download_resume.resumable_download` 上，
#    于是 5 + 12 failed——但红的全是**身份断言**（`assert task._download is resumable_download`
#    两侧取到不同对象），没有一条是「下载路径被执行」。生产解析读的是
#    `task_download` 模块自己那份绑定（`resolve_task_download` → 实例属性 → 类属性 →
#    模块缺省），所以靶子换成 `task_download.resumable_download`，自证加一层
#    「`resolve_task_download(<真任务实例>)[0] is 炸弹`」。**那格红必须能替绿背书**。
# ② 炸弹若在插件里就地 `def`，`__code__.co_filename` 是 sitecustomize 的临时路径 →
#    「自证注入生效」那一句永远失败 → 探针会一辈子报「探针失效」。故炸弹经
#    `exec(compile(src, "<naive-boom>", "exec"))` 装上。
# ③ **活口那一节在本机 GBK 控制台下会崩**（`UnicodeEncodeError: '\ufffd'`，退出码 1、
#    整节判据丢失，看不出「没跑完」）：根因是它的子进程没设 `PYTHONIOENCODING`，
#    回程字节按 GBK 解出替换字符、再 print 回 GBK stdout。已给子进程显式 env，
#    并给探针自身 stdout 加 `reconfigure(utf-8, errors="replace")` 兜底。
PROBE_NOTE = """
== 补充：探针设计与三处已修的失真（脚本里写死，不走 shell 追加）==
1. **配对证据，且阳性对照的靶子必须找对**：只跑「炸弹没人碰」得到绿，绿也可能来自
   「注入没生效」。阳性对照要排掉这种解释，它的注入点必须覆盖**缺省下载器这条路上的
   三个绑定**——① 构造期 `__init__` 读的是**任务模块自己的**模块名；② 两个任务类的
   **类属性** `_download`（类创建时就绑死了）；③ 解析期算 `is_default` 用的是
   **`task_download`** 那份绑定。自证 = 拿真任务实例跑一遍 `resolve_task_download`，
   断言「解析结果就是炸弹」**且**「被认成缺省实现」。
   *探针第一版打的是 `download_resume.resumable_download`：它确实转红了（5 + 12 failed），
   但红的全是**身份断言**（用例里 `assert task._download is resumable_download` 两侧取到
   不同对象），没有一条是「下载路径被执行」——那格红不为绿背书。第二版只换
   `task_download` 的绑定，自证立刻如实报「探针失效」（实例属性仍是真实现 → 解析走
   `return instance, False` 那一支）。现在的判据里多了一项**「炸弹被执行 N 次」**：
   死目标那格三文件全绿且 N = 0，活目标那格 N > 0 —— 两类红分开报。*
2. **每格自证注入生效**：断言目标对象的 `__code__.co_filename` 已是 `<naive-boom>`；
   炸弹经 `exec(compile(..., "<naive-boom>", "exec"))` 装上（就地 `def` 会拿到
   sitecustomize 的临时路径 → 自证永远失败）。
3. **活口不止静态**：`.scratch` 那几处活口另做**运行时取证**——把每支工具真正用它的
   那一行执行一遍（`load_impl("plain")` / 模板里的 import / 函数体里的 import），
   全都要解析到**同一个产品函数对象**才算活口，避免「grep 命中但不是调用」的假账。
4. **落盘这一层也要设 UTF-8**：本机控制台是 GBK，不设 `PYTHONIOENCODING` 时探针会在
   「活口」那一节因回程替换字符 `UnicodeEncodeError` 崩掉（退出码 1、整节判据丢失），
   而半截输出看起来像「跑完了」。子进程 env 与探针自身 stdout 两处都钉住。
"""


def run_script(name: str, *args: str) -> str:
    # 子进程显式 UTF-8：本机控制台是 GBK，不设这一项时探针会因回程替换字符
    # `UnicodeEncodeError` 崩在一半（评审实测），而崩溃的半截输出看起来像「跑完了」。
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run(
        [sys.executable, str(HERE / name), *args], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    return (out.stdout or "") + (out.stderr or "")


def write(target: str, text: str) -> None:
    (HERE / target).write_text(text, encoding="utf-8", newline="\n")
    print(f"  写入 {target}（{len(text)} 字符，UTF-8）")


def main() -> int:
    # 量具的 stdout 在内存里取回再落盘（不让子进程自己写目标文件——会与下面的 `write` 抢同一个文件）。
    write("verify-14-callers.txt",
          run_script("measure-14-download-part.py", "4fc27282"))
    write("verify-14-guard-strength.txt",
          run_script("probe-14-guard-strength.py") + PROBE_NOTE)
    if len(sys.argv) > 1 and sys.argv[1] == "suite":
        timeout = sys.argv[2] if len(sys.argv) > 2 else "120"
        write("verify-14-suite.txt", run_script("run-11-suite.py", timeout))
    return 0


if __name__ == "__main__":
    sys.exit(main())
