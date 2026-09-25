# -*- coding: utf-8 -*-
"""工单 `driver-defect-fixes/01`：把因头文件加行而漂移的**行号引用**改成散文。

双轴评审共同点名的一条：`joystick.h` 净增 13 行后，manifest 与测试里那些
`joystick.h L26-31` / `L24` / `L29-30` / `joystick.c L53-61` 全部指错位置。
本脚本把它们改成不依赖行号的散文（同段落 ② 早就是散文口径，这里统一）。

判据：每处替换锚点必须**恰好命中一次**（多一处少一处都说明上游又变了）。
写法：按原文件换行风格落盘（`newline=""`）。
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SUBSTITUTIONS = {
    "tests/test_module_joystick.py": [
        ("stm32：API 全套 6 函数与 mspm0 joystick.h L26-31",
         "stm32：API 全套 6 函数与 mspm0 joystick.h 的六个声明"),
        ("（页面 L149 注释串台——不落码）", "（页面注释串台——不落码）"),
        ("API 全套 6 函数与 mspm0 joystick.h L26-31 同名同型",
         "API 全套 6 函数与 mspm0 joystick.h 的六个声明同名同型"),
        ('assert "MQ2" in c  # 页面缺陷记录（注释：L149 串台）',
         'assert "MQ2" in c  # 页面缺陷记录（注释：原页注释串台）'),
        ("# API 全套 6 函数（同名同型 mspm0 joystick.h L26-31）",
         "# API 全套 6 函数（同名同型 mspm0 joystick.h 的六个声明）"),
        ("（照 mspm0 joystick.c L53-61 逐行——非 float 100.0f）",
         "（照 mspm0 joystick.c 的换算出口逐行——非 float 100.0f）"),
    ],
    "library/modules/joystick/manifest.json": [
        ("与 mspm0 joystick_read_x_percent 同名同型 joystick.h L29-30，非 float",
         "与 mspm0 joystick_read_x_percent 同名同型（mspm0 的 joystick.h 声明），非 float"),
        ("SW 低有效语义归一（0=按下页面原样 → 1=按下 API 出参——JOYSTICK_SW_PRESSED_LEVEL 0 宏照 mspm0 同名 joystick.h L24，一处反相）",
         "SW 低有效语义归一（0=按下页面原样 → 1=按下 API 出参——JOYSTICK_SW_PRESSED_LEVEL 0 宏照 mspm0 同名声明，一处反相）"),
    ],
}


def main() -> int:
    for rel, pairs in SUBSTITUTIONS.items():
        path = REPO / rel
        text = path.read_text(encoding="utf-8", newline="")
        for old, new in pairs:
            count = text.count(old)
            assert count == 1, f"{rel}：锚点命中 {count} 次（应为 1）——{old[:60]!r}"
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8", newline="")
        print(f"已改 {rel}：{len(pairs)} 处行号引用 → 散文")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
