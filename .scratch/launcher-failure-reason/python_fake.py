"""探针用的「慢 Python」替身（工单 launcher-failure-reason/02）。

为什么需要它：`start-app.bat` 的 `:timeout` 分支要的形态是「**服务起得来但 20 秒内不就绪**」，
本机依赖齐全、真服务 ~2s 就绪，造不出来。踩过并放弃的两条路：

| 做法 | 结果 |
|---|---|
| PATH 前置 `python.cmd` 垫片 | ❌ cmd 在 PATH 上解析到 `.cmd` 形式的 `python` 时，launcher 的批处理会异常退出（stdout 只剩一行、连 launcher.log 都没写） |
| 只拷 `python.exe` 单体 + `python._pth` 直接跑脚本 | ❌ 本机是「可搬运」安装（DLL 在安装目录里）：单拷 exe 跑不起来（STATUS_DLL_NOT_FOUND）；`._pth` 里直接列脚本也不是「跑脚本」的语义 |

**现在的做法**（真 exe + 官方 `sitecustomize` 钩子）：

    prof\\realpy\\      ← 真 python 安装目录的整目录拷贝
      python.exe        （launcher 的 `python` 解析到这里）
      python._pth       （`Lib` / `DLLs` / `.` / `import site`：`._pth` 会接管 sys.path）
      sitecustomize.py  ← 本文件（`import site` 时会自动 import 它）
      python_fake.py    ← 同上的拷贝，供 sitecustomize 导入

判据一条：`sys.argv` 里出现 `-m contest_generator.webapp`（= 服务启动）→ **挂住不返回**（远大于
launcher 的 20 秒轮询预算）；其余调用（launcher 的 4 次快速自检）**原样放行**。于是自检全过、
服务 20 秒内给不出健康响应 → 走 `:timeout`。

`sitecustomize.py` 由本文件在探针里拷成，导入即执行 `main()`（见 `if __name__ == "__main__"` 之外的
`guard()`：sitecustomize 是被 import 的，所以这里用导入即调用的写法）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

SERVICE_MODULE = "contest_generator.webapp"


def _full_command_line() -> list[str]:
    """解释器启动阶段只看得到 `sys.argv[1:] == ['-m']`（模块名还没被解析进去）——
    真正的整条命令行在 `sys.orig_argv` 里（Python 3.10+）。import 之后 `sys.argv` 才补全。
    """
    orig = getattr(sys, "orig_argv", None)
    if orig:
        return list(orig)
    return list(sys.argv)


def is_service_start(argv: list[str]) -> bool:
    if "-m" not in argv:
        return False
    idx = argv.index("-m")
    return idx + 1 < len(argv) and argv[idx + 1] == SERVICE_MODULE


def hold_service_start() -> int:
    """服务启动：挂住（launcher 的轮询预算 20 秒，这里远大于它）。"""
    print("[slow-python] holding service start", flush=True)
    subprocess.call(["ping", "-n", "120", "127.0.0.1"], stdout=subprocess.DEVNULL)
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if is_service_start(argv):
        return hold_service_start()
    real = HERE / "python-real.exe"
    if not real.is_file():
        real = Path(sys.executable)
    return subprocess.call([str(real), *argv])


# sitecustomize 是被 import 的：导入即判据（自检放行 / 服务启动挂住）。
if is_service_start(_full_command_line()):
    hold_service_start()

