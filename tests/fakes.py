"""测试假件与构造器：假模块库、假母版、假 LLM、记录桩。

只放纯数据/构造逻辑，不放 pytest fixture（fixture 见 conftest.py）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from contest_generator.llm import ModuleSelection

# ---------------------------------------------------------------------------
# 假模块文件内容（断言输出目录里文件内容用）
# ---------------------------------------------------------------------------

DHT11_STM32_C = "/* DHT11 driver for STM32 */\nfloat dht11_read(void);\n"
DHT11_MSPM0_C = "/* DHT11 driver for MSPM0 */\nfloat dht11_read(void);\n"
DHT11_H = "#pragma once\nfloat dht11_read(void);\n"
OLED_STM32_C = "/* OLED driver for STM32 */\nvoid oled_init(void);\n"
OLED_H = "#pragma once\nvoid oled_init(void);\n"

# 假 LLM 生成的 main.c 骨架（工单 05 前由测试直接传入生成器）
MAIN_SKELETON = "int main(void) { dht11_init(); oled_init(); while(1); }\n"


def make_fake_module_library(library_dir: Path) -> Path:
    """假模块库：dht11（双平台验证过，依赖 delay）、oled（仅 stm32）、
    delay（双平台，平铺文件）、broken（manifest 指向不存在的文件）。"""
    _add_module(
        library_dir,
        {
            "slug": "dht11",
            "description": "DHT11 温湿度传感器驱动",
            "dependencies": ["delay"],
            "platforms": {
                "stm32": {
                    "files": ["stm32/src/dht11.c", "inc/dht11.h"],
                    "verified": True,
                    "hardware_bound": False,
                    "notes": "PA0",
                },
                "mspm0": {
                    "files": ["mspm0/src/dht11.c", "inc/dht11.h"],
                    "verified": True,
                },
            },
        },
        {
            "stm32/src/dht11.c": DHT11_STM32_C,
            "mspm0/src/dht11.c": DHT11_MSPM0_C,
            "inc/dht11.h": DHT11_H,
        },
    )
    _add_module(
        library_dir,
        {
            "slug": "oled",
            "description": "OLED 屏显驱动",
            "platforms": {
                "stm32": {"files": ["stm32/src/oled.c", "inc/oled.h"], "verified": True}
            },
        },
        {"stm32/src/oled.c": OLED_STM32_C, "inc/oled.h": OLED_H},
    )
    _add_module(
        library_dir,
        {
            "slug": "delay",
            "description": "软件延时",
            "platforms": {
                "stm32": {"files": ["delay.c", "delay.h"], "verified": True},
                "mspm0": {"files": ["delay.c", "delay.h"], "verified": True},
            },
        },
        {"delay.c": "/* delay */\nvoid delay_ms(int ms);\n", "delay.h": "#pragma once\n"},
    )
    _add_module(
        library_dir,
        {
            "slug": "broken",
            "description": "manifest 指向的文件不存在",
            "platforms": {"stm32": {"files": ["stm32/src/broken.c"]}},
        },
        {},
    )
    return library_dir


def make_fake_master_project(master_dir: Path) -> Path:
    """最小化的 Keil 风格母版工程（真实母版由工单 08 提炼，这里只求结构真实）。"""
    (master_dir / "inc").mkdir(parents=True)
    (master_dir / "src").mkdir()
    (master_dir / ".git").mkdir()
    (master_dir / "project.uvprojx").write_text(
        "<!-- fake keil project -->", encoding="utf-8"
    )
    (master_dir / "main.c").write_text("/* master's old main */", encoding="utf-8")
    (master_dir / "inc/stm32f10x_conf.h").write_text("#pragma once\n", encoding="utf-8")
    (master_dir / "src/system_stm32f10x.c").write_text(
        "/* startup/system */", encoding="utf-8"
    )
    (master_dir / ".git/HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
    return master_dir


class FakeLLM:
    """假 LLM：固定返回，供后续工单（04/05）注入。"""

    def __init__(
        self,
        selection: ModuleSelection | None = None,
        main_skeleton: str = "/* skeleton placeholder */\n",
    ) -> None:
        self._selection = selection or ModuleSelection(modules=(), reasons={})
        self._main_skeleton = main_skeleton

    def select_modules(
        self, problem_text: str, manifest_summaries: Sequence[str]
    ) -> ModuleSelection:
        return self._selection

    def generate_main_skeleton(
        self, problem_text: str, module_summaries: Sequence[str]
    ) -> str:
        return self._main_skeleton

    def summarize_module(self, code: str) -> str:
        return "AI 生成的模块简介"


class RecordingPatcher:
    """记录调用参数的桩修改器，用于断言核心通过注册表委托。"""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, tuple[Path, ...], tuple[Path, ...]]] = []

    def patch(
        self,
        project_dir: Path,
        module_files: Sequence[Path],
        include_dirs: Sequence[Path],
    ) -> None:
        self.calls.append((project_dir, tuple(module_files), tuple(include_dirs)))


def _add_module(library_dir: Path, manifest: dict, files: dict[str, str]) -> None:
    module_dir = library_dir / manifest["slug"]
    module_dir.mkdir(parents=True)
    (module_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    for relpath, content in files.items():
        path = module_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
