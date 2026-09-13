# -*- coding: utf-8 -*-
"""反证：证明「探针确实会红」——不是跑绿了就完事（工单 resumable-download/01）。

要证明的命题有两条，各自需要一个**故意做错**的对照：

- 命题 A：**「从断点接着下」这件事被判得到。**
  对照：一个「每次尝试前先把落盘文件删掉」的下载函数——它从不续传。
  期望：cut / stall 的请求起始偏移序列**全是 0**，判据转红。
- 命题 B：**「被截断却自称成功」这件事被判得到。**
  对照：`download_part`（当前唯一实现）在断流下既不报错、也不校验长度。
  期望：cut / stall 判红，且红的理由写的是「被截断却自称成功」。

对照用**包装函数**实现（包在 `download_part` 外面），使它与被测对象只差一件事：
「试之前有没有保留半成品」。差一件事，才说明红的成因就是这一件事。

用法：在仓库根跑 ``python .scratch/resumable-download/probe-01-negative.py``；
输出 `verify-01-negative.txt`（与正证分开存）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROBE = HERE / "probe-01-resume.py"
OUT = HERE / "verify-01-negative.txt"

# 临时启动脚本：复用 probe 的全部判据，只把「实现解析」这一处换成对照函数。
RUNNER_TEMPLATE = '''\
import importlib.util, pathlib, sys
sys.path.insert(0, str(pathlib.Path(r"{src}")))
from contest_generator.materials_task import download_part as _plain


def never_resumes(url, dest, on_progress):
    """对照：每次尝试前丢弃半成品 —— 于情于理都不该续传。"""
    pathlib.Path(dest).unlink(missing_ok=True)
    return _plain(url, dest, on_progress)


spec = importlib.util.spec_from_file_location("probe01", r"{probe}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.load_impl = lambda name: (never_resumes, "对照：每次尝试前丢弃半成品")
sys.argv = ["probe-01-resume.py"]
raise SystemExit(mod.main())
'''


def main() -> int:
    runner = HERE / "_negative_runner.py"
    runner.write_text(
        RUNNER_TEMPLATE.format(src=REPO / "src", probe=PROBE), encoding="utf-8"
    )
    try:
        proc = subprocess.run([sys.executable, str(runner)], capture_output=True,
                              text=True, encoding="utf-8", cwd=str(REPO))
    finally:
        runner.unlink(missing_ok=True)

    lines = [
        "# 工单 01 反证证据（证明判据会红，而不是只会绿）",
        "# 对照 = 「每次尝试前丢弃半成品」的下载函数；与被测对象只差这一件事",
        "",
        "## 对照运行输出（probe 的判据原样复用，一行未改）",
        proc.stdout or "",
    ]
    if proc.stderr:
        lines += ["### stderr", proc.stderr]
    lines += [
        f"### 退出码：{proc.returncode}（非 0 = 判据如期转红）",
        "",
        "## 读法",
        "- 请求起始偏移序列若全是 0 → 「续传」这条判据确实在工作（命题 A 成立）。",
        "- cut/stall 若判红且理由含「被截断却自称成功」→ 命题 B 成立。",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
