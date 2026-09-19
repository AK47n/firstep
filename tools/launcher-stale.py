#!/usr/bin/env python
"""启动器问「端口上那个服务是不是旧进程」的唯一出处（工单 `update-restart-stale-service/01`）。

为什么需要它：更新换的是**盘上的文件**，跑着的进程不会跟着变。旧进程还占着端口时，启动器探测到的
`/api/health` 一切正常（`app` 也对得上），于是判「本应用已在运行」→ 只开一个浏览器标签就退出——
用户永远停在旧版本，而界面说更新成功了。

**契约（`start-app.bat` 只消费这一行）**：stdout 恰好一行，三选一——

    stale stale=1 served=<端口上> disk=<盘上>      ← 是旧进程，该踢掉重起
    fresh served=<端口上> disk=<盘上>              ← 不是（同版本，或服务比盘上还新）→ 照旧复用
    unknown                                        ← 判不了（异常 / 身份不符 / 读不到版本 / 非法 semver）

任何内部异常都走 `unknown` 并**退出码 0**：判据只有 stdout 那一行，调用方（GBK 批处理）
用 `for /f` 取词，不参与判断的退出码不必有语义；而把启动器带崩是不可接受的
（`unknown` 的后果 = 保持旧行为，是安全的一侧）。

判据本身在产品包里（`contest_generator.update.is_stale_service`）——版本语义只有一个家，
这里只做「取数 + 打印」。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

# 盘上版本与判据都在产品包里。启动器起我们时已经 `set PYTHONPATH=src`（`start-app.bat` 第 19 行），
# 这里再补一次同一个落点，好让「手工跑一下看看」也成立（装了 .venv 的机器本来就 import 得到）。
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

from contest_generator import __version__ as ON_DISK_VERSION  # noqa: E402
from contest_generator.update import is_stale_service  # noqa: E402

#: 身份判据与 webapp 的 `/api/health` 契约同源（启动器那侧还有一条同样的判据，这里是第二道确认）
APP_ID = "contest-generator"
HEALTH_PATH = "/api/health"
HTTP_TIMEOUT = 3.0


def health_version(port: int, host: str = "127.0.0.1") -> str:
    """端口上**本应用**的版本号；连不上 / 不是本应用 / 没带版本字段 → 空串（判不了）。"""
    url = f"http://{host}:{port}{HEALTH_PATH}"
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict) or data.get("app") != APP_ID:
        return ""
    return str(data.get("version") or "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="判断端口上那个服务是不是旧进程（给 start-app.bat 用）"
    )
    parser.add_argument(
        "--port", type=int, required=True,
        help="要问的端口（与启动器同一个变量 FIRSTEP_LAUNCHER_PORT）",
    )
    args = parser.parse_args(argv)

    disk = str(ON_DISK_VERSION)
    try:
        served = health_version(args.port)
        verdict = is_stale_service(served, disk)
    except Exception:  # noqa: BLE001 —— 边界处故意收口：判不了就是 unknown，绝不把启动器带崩
        print("unknown")
        return 0

    if verdict is None:
        print("unknown")
    elif verdict:
        print(f"stale stale=1 served={served} disk={disk}")
    else:
        print(f"fresh served={served} disk={disk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
