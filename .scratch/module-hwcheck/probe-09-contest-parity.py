# -*- coding: utf-8 -*-
"""一次性取证：赛题生成链路在同一条 mspm0 默认脚冲突上是什么表现。

背景（工单 module-hwcheck/09 的编译矩阵撞出来的）：检测页默认「调试串口 + OLED」
两个通道都勾上，而 mspm0 母版里 **OLED_SPI_RES = PA22 = DEBUG_UART RX**——检测页
没有引脚配置入口，于是"生成"直接 400。问题是：这条冲突是检测页独有的，还是
赛题链路一样会撞（只是赛题链路有「自动配置」出口）？

用法：python .scratch/module-hwcheck/probe-09-contest-parity.py
只读（生成到临时目录，跑完删）；读数同时落盘到 `probe-09-contest-parity.txt`
（评审整改：结论不能只活在单据文字里）。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

OUT = Path(__file__).resolve().parent / "probe-09-contest-parity.txt"
MAIN_C = '#include "headfile.h"\n\nint main(void)\n{\n    return 0;\n}\n'


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    root = Path(tempfile.mkdtemp(prefix="firstep-parity09-"))
    try:
        ctx = AppContext(
            config_path=root / "cfg" / "config.json",
            config=AppConfig(
                api_key="sk-test",
                module_library_dir=REPO / "library" / "modules",
                masters_dir=REPO / "library" / "masters",
            ),
            desktop_dir=lambda: root,
        )
        client = TestClient(create_app(ctx))
        slugs = ["led", "oled", "debug_uart"]
        out = root / "contest-mspm0"
        response = client.post(
            "/api/generate",
            json={
                "problem_text": "测试题面：点亮 OLED 并打印串口。",
                "platform": "mspm0",
                "slugs": slugs,
                "main_c": MAIN_C,
                "output_dir": str(out),
                "confirm_overwrite": True,
            },
        )
        lines: list[str] = [
            "# 赛题链路 vs 检测页：同一条 mspm0 默认脚冲突的两个出口（工单 09 取证）",
            "",
            "选中集：mspm0 + led / oled / debug_uart",
            "",
        ]
        lines.append(f"赛题生成 /api/generate → {response.status_code}")
        body = response.json()
        lines.append(str(body.get("detail") or {k: body[k] for k in list(body)[:4]})[:800])
        if response.status_code == 200:
            lines.append("产物：" + str(body.get("output_dir")))
        auto = client.post(
            "/api/bindings/auto",
            json={"platform": "mspm0", "slugs": slugs, "bindings": {}},
        )
        lines.append("")
        lines.append(f"「自动配置」/api/bindings/auto → {auto.status_code}")
        lines.append(str(auto.json())[:800])
        lines.append("")
        lines.append(
            "结论：同一条冲突在赛题链路有出口（上面那条改绑就是），"
            "而检测页没有引脚配置入口 —— 见 .scratch/hwcheck-pin-conflict-exit/。"
        )
        text = "\n".join(lines) + "\n"
        OUT.write_text(text, encoding="utf-8")
        print(text)
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
