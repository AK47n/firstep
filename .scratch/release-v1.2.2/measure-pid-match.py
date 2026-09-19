# -*- coding: utf-8 -*-
"""把 `tools/update-app.py` 的 `find_listening_pids` 拿到**当前真机 netstat** 上跑一遍。

要回答的问题（2026-09-19 真机演练踩到）：为什么沙箱那轮更新（端口 8020）停掉了
**真身 43960**（端口 8000）？两种可能，必须当场分开：

- **A. 判据把 8000 认成 8020**：`f":{port}" in parts[1]` 是子串匹配——`":8020" in
  "127.0.0.1:8000"` 是 **False**，所以只有当 netstat 行里出现**别的含 `:8020` 的列**
  才会误命中。本量具直接跑真 netstat，把每个端口的命中行原样打出来。
- **B. 端口压根没传对**：判据没错，是上游把 `--port 8000`（缺省）传下去了。那要看
  调用侧，不归本量具。

本量具只回答 A。用**磁盘上那份真实现**（importlib 直接加载 `tools/update-app.py`），
不重写一份，避免"量具对了、产品错了"。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[2]
UPDATE_APP = REPO / "tools" / "update-app.py"


def load_module():
    spec = importlib.util.spec_from_file_location("update_app_under_test", UPDATE_APP)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # 必须先登记进 sys.modules：`update-app.py` 里有 @dataclass，dataclasses 会去
    # `sys.modules[cls.__module__]` 取命名空间，没登记就 AttributeError（'NoneType'）。
    sys.modules["update_app_under_test"] = module
    spec.loader.exec_module(module)
    return module


def raw_netstat_lines(port: int) -> list[str]:
    """按**实现自己的判据**筛出命中行（原样返回，供人眼复核）。"""
    output = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                            timeout=30).stdout
    hits: list[str] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[-2] == "LISTENING" and f":{port}" in parts[1]:
            hits.append(line.strip())
    return hits


def main() -> int:
    module = load_module()
    print(f"# find_listening_pids 真机复核（实现来自 {UPDATE_APP.name}）")

    print("\n## 当前监听端口的行（前 15 条，看看都有谁）")
    output = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                            timeout=30).stdout
    shown = 0
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[-2] == "LISTENING" and "127.0.0.1:" in parts[1]:
            print(f"  {line.strip()}")
            shown += 1
            if shown >= 15:
                break
    if not shown:
        print("  （本机当前没有 127.0.0.1 上的监听——真身与沙箱都没在跑）")

    print("\n## 逐端口对照（实现判据 vs 原样命中行）")
    verdict = True
    for port in (8000, 8020, 8021):
        pids = module.find_listening_pids(port)
        hits = raw_netstat_lines(port)
        print(f"  find_listening_pids({port}) = {pids}")
        for line in hits:
            print(f"      命中行：{line}")
        # 自证：命中行里**每一条**的本地地址列必须真以 `:<port>` 结尾
        for line in hits:
            local = line.split()[1]
            if not local.endswith(f":{port}"):
                print(f"      **误命中**：本地地址 {local} 并非 :{port}")
                verdict = False

    print(f"\n判据 A（子串误命中）：{'未复现' if verdict else '**复现**'}")
    print("  说明：未复现 = 端口选错的原因不在这条判据上，去调用侧找（--port 传了什么）")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
