"""2026C 模块补录一次性脚本（工单 module-2026c-backfill）。

读 2026C 双端工程源码，经 library.add_module（AI 一致性校验通过才入库）
录入三个模块：zigbee_uart（锁端接收版）/ zigbee_uart_key（钥匙端发送版）/
debug_uart。只写模块库目录，不改 firstep 代码库。
"""

import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\luoji\Desktop\firstep\src")

from contest_generator.config import load_config
from contest_generator.library import LibraryError, add_module
from contest_generator.llm import DeepSeekLLM

LIBRARY_ROOT = Path(r"C:\Users\luoji\.contest_generator\modules")

LOCK = r"C:\Users\luoji\Desktop\2026C\code"
KEY_FOB = r"C:\Users\luoji\Desktop\2026C\key_fob"


def read_files(*paths: str) -> dict[str, str]:
    """源文件原样读入，键按库内惯例带 code/ 前缀（LF 无 BOM，读写往返字节一致）。"""
    return {f"code/{Path(p).name}": Path(p).read_text(encoding="utf-8") for p in paths}


MODULES = [
    {
        "slug": "zigbee_uart",
        "description": "2026C 门锁端 Zigbee DL-20 接收（解析钥匙端 DIP-4 ID 帧）",
        "dependencies": ["config"],
        "notes": "",
        "files": read_files(
            rf"{LOCK}\zigbee_uart.c",
            rf"{LOCK}\zigbee_uart.h",
        ),
    },
    {
        "slug": "zigbee_uart_key",
        "description": "2026C 钥匙端 Zigbee DL-20 发送（组 4 字节帧上报 DIP-4 ID）",
        "dependencies": ["config"],
        "notes": "钥匙端过渡方案（原 STM32，芯片不足换 MSPM0；最终方案代码未定）",
        "files": read_files(
            rf"{KEY_FOB}\zigbee_uart.c",
            rf"{KEY_FOB}\zigbee_uart.h",
        ),
    },
    {
        "slug": "debug_uart",
        "description": "2026C 门锁端调试串口（UART2 调试输出 + 单字符调试命令）",
        "dependencies": ["lock_control"],
        "notes": "",
        "files": read_files(
            rf"{LOCK}\debug_uart.c",
            rf"{LOCK}\debug_uart.h",
        ),
    },
]


def main() -> None:
    config = load_config()
    llm = DeepSeekLLM(config)
    for mod in MODULES:
        if (LIBRARY_ROOT / mod["slug"]).is_dir():
            print(f"SKIP {mod['slug']}: 已存在")
            continue
        try:
            add_module(
                llm,
                LIBRARY_ROOT,
                slug=mod["slug"],
                platform="stm32",
                description=mod["description"],
                files=mod["files"],
                dependencies=mod["dependencies"],
                notes=mod["notes"],
                # 与库内 2026C 模块惯例一致：纯逻辑条目，身份字段留空由人补填
                hardware_bound=False,
            )
            print(f"OK   {mod['slug']}")
        except LibraryError as exc:
            print(f"FAIL {mod['slug']}: {exc}")


if __name__ == "__main__":
    main()
