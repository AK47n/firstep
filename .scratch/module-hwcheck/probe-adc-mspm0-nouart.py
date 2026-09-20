# -*- coding: utf-8 -*-
"""探针：mspm0 上**唯一能生成出来的 adc 形态**（既不开串口也不开 OLED）真编译。

背景（probe-adc-mspm0-pinconflict.py 实测）：`adc` 在 mspm0 上只要带 debug_uart
或 oled 就是 400——PA22 被 DEBUG_UART RX / OLED_SPI_RES 与 `ADC12_0.adcPin7`
（母版 syscfg，角色未登记）同时占用。那是平台级既有事实，与配方无关。

所以真正该问的是：**把两个输出通道都关掉**，adc 那一格还剩什么？本探针编它
（只有 LED 心跳输出）。若这一格能过，说明配方的 mspm0 侧至少是编得过的。

用法：python .scratch/module-hwcheck/probe-adc-mspm0-nouart.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from contest_generator.compile_runner import find_make, run_compile  # noqa: E402
from contest_generator.config import AppConfig  # noqa: E402
from contest_generator.sse import SseEmitter  # noqa: E402
from contest_generator.webapp import AppContext, create_app  # noqa: E402

HERE = Path(__file__).resolve().parent


class _Collector(SseEmitter):
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def progress(self, event) -> None:
        self.events.append(("progress", event))

    def done(self, data: dict) -> None:
        self.events.append(("done", data))

    def error(self, data: dict) -> None:
        self.events.append(("error", data))

    def question(self, data: dict) -> None:
        self.events.append(("question", data))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    import json

    make = find_make()
    recipe_file = REPO / "library" / "hwcheck_recipes.json"
    staged_root = Path(tempfile.mkdtemp(prefix="firstep-probe-adcnouart-"))
    staged = staged_root / "hwcheck_recipes.json"
    data = json.loads(recipe_file.read_text(encoding="utf-8"))
    data.update(json.loads((HERE / "drafts" / "adc.json").read_text(encoding="utf-8")))
    staged.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    root = Path(tempfile.mkdtemp(prefix="firstep-probe-adcnouart-out-"))
    try:
        ctx = AppContext(
            config_path=root / "cfg" / "config.json",
            config=AppConfig(
                api_key="sk-test",
                module_library_dir=REPO / "library" / "modules",
                masters_dir=REPO / "library" / "masters",
            ),
            desktop_dir=lambda: root,
            hwcheck_recipe_path=staged,
        )
        client = TestClient(create_app(ctx))
        response = client.post(
            "/api/hwcheck/generate",
            json={"platform": "mspm0", "debug_uart": False, "oled": False,
                  "devices": ["adc"], "parent_dir": str(root)},
        )
        print(f"生成：{response.status_code}")
        if response.status_code != 200:
            print(str(response.json().get("detail", ""))[:400])
            return 1
        project = Path(response.json()["output_dir"])
        main_c = (project / "main.c").read_text(encoding="utf-8", errors="replace")
        print(f"main.c 里有 adc 小节：{'hwcheck_check_adc(' in main_c}")
        print(f"main.c 里有输出通道调用："
              f"debug_uart_init={'debug_uart_init();' in main_c} "
              f"OLED_Init={'OLED_Init();' in main_c}")
        lines = main_c.splitlines()
        start = next((i for i, ln in enumerate(lines) if "hwcheck_check_adc(" in ln), None)
        if start is None:
            print("→ 这一形态**根本不渲染逐件小节**（没有输出通道就没有检测小节），"
                  "所以它证明不了 adc 的 mspm0 侧能不能编——如实记账，不假装测过。")
            return 0
        end = next((i for i in range(start + 1, len(lines))
                    if lines[i].startswith("static void")), len(lines))
        print("--- adc 小节 ---")
        print("\n".join(lines[start:end]).rstrip())
        print("--- 编译 ---")
        collector = _Collector()
        run_compile("mspm0", project, uv4=None, make=make, emit=collector)
        done = next((p for e, p in collector.events if e == "done"), {})
        rows = done.get("parsed_errors") or []
        print(f"passed={done.get('passed')} exit={done.get('exit_code')} "
              f"summary={done.get('summary')}")
        for row in rows[:8]:
            print(f"  - {row.get('path','')}:{row.get('line','')} "
                  f"{str(row.get('message',''))[:150]}")
        return 0 if done.get("passed") else 1
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(staged_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
