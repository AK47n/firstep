# -*- coding: utf-8 -*-
"""工单 hwcheck-unknown-device/12 的量具：**带连字符的自建件 id** 会渲染出非法 C。

发现的现场是工单 06（把自建件接进命令台）：ids 的文法（`entry_store.SLUG_PATTERN`
允许 `-`）与"id 直接拼进 C 函数名"（`CustomSection.func_name`）这两件事对不上。
本探针走**产品真路径**（TestClient + 真库真母版），量三件事：

1. `POST /api/my-devices` 收下 `mine_gyro-2`（id 文法真的允许连字符）；
2. `POST /api/hwcheck/preview` / `generate` 都**200**——页面与端点都不拦；
3. 产物 `main.c` 里那三行是 `hwcheck_custom_mine_gyro-2`（**不是合法 C 标识符**）
   ——学生的工程会在编译期炸，报的还是看不懂的语法错。

先落盘再打印（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。

用法：`python .scratch/hwcheck-unknown-device/probe-12-hyphen-id.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from fastapi.testclient import TestClient  # noqa: E402

from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402
from tests.fakes import FakeLLM  # noqa: E402

DEVICE_ID = "mine_gyro-2"
C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(Path(__file__).with_suffix(".txt")),
        help="证据文件（UTF-8，先落盘再打印）",
    )
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="hyphen-id-probe-"))
    data_dir = tmp / "data"
    data_dir.mkdir()
    ctx = AppContext(
        config_path=data_dir / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=REPO / "library" / "modules",
            masters_dir=REPO / "library" / "masters",
        ),
        llm_factory=lambda config: FakeLLM(),
    )
    client = TestClient(create_app(ctx))

    lines: list[str] = [f"自建件 id = {DEVICE_ID!r}", ""]
    created = client.post("/api/my-devices", json={"device": {
        "id": DEVICE_ID, "name": "连字符 id 的库外件", "bus": "i2c",
        "address": 0x68, "register": 0x75, "expect": 0x68,
    }})
    lines.append(f"[1] 建件端点：{created.status_code}"
                 f"（200 = id 文法收下了连字符）")

    request = {
        "platform": "stm32", "debug_uart": True, "oled": False,
        "devices": [DEVICE_ID],
    }
    preview = client.post("/api/hwcheck/preview", json=request)
    lines.append(f"[2] 预览端点：{preview.status_code}")
    culprit_lines: list[str] = []
    if preview.status_code == 200:
        main_c = preview.json().get("main_c", "")
        culprit_lines = [
            line.strip() for line in main_c.splitlines()
            if "hwcheck_custom_mine_gyro-2" in line
        ]
        lines.append("    产物里的那几行（**都不是合法 C**）：")
        lines.extend(f"      {line}" for line in culprit_lines)
        commands = preview.json().get("console", {}).get("commands", [])
        lines.append(f"    命令表：{commands}")

    out_parent = tmp / "out"
    out_parent.mkdir()
    generated = client.post(
        "/api/hwcheck/generate", json={**request, "parent_dir": str(out_parent)}
    )
    lines.append(f"[3] 生成端点：{generated.status_code}"
                 "（200 = 界面会说「生成成功」，坏工程已经落盘）")
    lines.append("")

    func_name = f"hwcheck_custom_{DEVICE_ID}"
    legal = C_IDENTIFIER.fullmatch(func_name) is not None
    verdict = (
        "缺陷成立：id 直接拼进 C 函数名，产物编不过（页面与端点都不拦）"
        if culprit_lines and not legal else
        "缺陷不成立（今天已经拦住 / 拼出来是合法标识符）——请复核判据"
    )
    lines.append(f"[4] {func_name!r} 是合法 C 标识符吗：{legal}")
    lines.append(f"=== 结论：{verdict} ===")

    report = "\n".join(lines) + "\n"
    Path(args.out).write_text(report, encoding="utf-8")          # 先落盘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 再打印
    print(report)
    return 0 if (culprit_lines and not legal) else 1


if __name__ == "__main__":
    raise SystemExit(main())
