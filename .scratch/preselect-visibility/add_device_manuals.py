"""工单 preselect-visibility/04：把器件级移植手册录入参考库（救活 6 个死映射）。

只读源素材（`sources/materials/lckfb-地猛星移植手册/*.md`）→ 走既有
`add_reference` 入库（结构校验 / 事务落盘 / 自动 git 提交）。幂等：同标题条目
已存在则跳过（重跑不重复建条目）。

条目 → 救活的映射模块：
- 0.96 寸 OLED 单色屏器件手册 → oled
- WS2812 幻彩灯带与 8 位 LED 数码管器件手册 → led / led_beep
- 按键摇杆器件手册 → key
- SG90 舵机器件手册 → servo
- 蜂鸣器驱动例程（beep 模块代码汇编）→ beep
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.reference_library import (  # noqa: E402
    ANCHOR_KIND_NONE,
    add_reference,
    list_references,
    module_kit_vocabulary,
)

MANUALS = ROOT / "sources" / "materials" / "lckfb-地猛星移植手册"
REFERENCES = ROOT / "library" / "references"
MODULES = ROOT / "library" / "modules"

# (条目标题, 类型, 简介, 平台, [(条目内文件名, 源素材路径)])
ENTRIES: tuple[tuple[str, str, str, str, tuple[tuple[str, Path], ...]], ...] = (
    (
        "0.96 寸 OLED 单色屏器件手册（oled / IIC 与 SPI）",
        "器件手册",
        "立创·地猛星移植手册的 0.96 寸单色 OLED 屏移植笔记（IIC 与 SPI 两种接线）："
        "引脚定义、初始化序列、显存式绘图与字库用法——骨架阶段选中 oled 模块时"
        "作为器件级例程参考。",
        "any",
        (
            ("0-96-iic-single-screen.md", MANUALS / "screen--0-96-iic-single-screen.md"),
            ("0-96-single-spi-screen.md", MANUALS / "screen--0-96-single-spi-screen.md"),
        ),
    ),
    (
        "WS2812 幻彩灯带与 8 位 LED 数码管器件手册（led）",
        "器件手册",
        "立创·地猛星移植手册的 LED 器件移植笔记：WS2812 幻彩 RGB 灯带（单线时序下发）"
        "与 8 位 LED 数码管（移位寄存器驱动）——骨架阶段选中 led / led_beep 模块时"
        "作为器件级例程参考。",
        "any",
        (
            ("ws2812-color-rgb-led.md", MANUALS / "control--ws2812-color-rgb-led.md"),
            ("8-bit-led-tube.md", MANUALS / "screen--8-bit-led-tube.md"),
        ),
    ),
    (
        "按键摇杆器件手册（key / button）",
        "器件手册",
        "立创·地猛星移植手册的双轴按键摇杆移植笔记：按键（含摇杆按下键）与双轴 ADC "
        "读取——骨架阶段选中 key 模块时作为器件级例程参考。",
        "any",
        (
            ("two-axis-keystroke-rocker-module.md", MANUALS / "control--two-axis-keystroke-rocker-module.md"),
            ("grayscale-sensor.md", MANUALS / "sensor--grayscale-sensor.md"),
        ),
    ),
    (
        "SG90 舵机器件手册（servo）",
        "器件手册",
        "立创·地猛星移植手册的 SG90 舵机移植笔记：PWM 周期与脉宽—角度映射、"
        "供电与共地注意点——骨架阶段选中 servo 模块时作为器件级例程参考。",
        "any",
        (
            ("sg90-steering-engine.md", MANUALS / "control--sg90-steering-engine.md"),
            ("16-ch-servo-drive-module.md", MANUALS / "control--16-ch-servo-drive-module.md"),
        ),
    ),
)


def _beep_entry_files() -> tuple[tuple[str, str], ...]:
    """蜂鸣器例程条目素材：库内 beep 模块的代码切片（双平台）+ 引脚宏来源说明。"""
    code_dir = MODULES / "beep" / "code"
    files: list[tuple[str, str]] = []
    for path in sorted(code_dir.glob("*.c")) + sorted(code_dir.glob("*.h")):
        files.append((path.name, path.read_text(encoding="utf-8", errors="replace")))
    return tuple(files)


def main() -> int:
    existing = {entry.title for entry in list_references(REFERENCES)}
    kit_vocabulary = module_kit_vocabulary(MODULES)
    created: list[str] = []
    for title, type_, description, platform, sources in ENTRIES:
        if title in existing:
            print(f"跳过（已存在）：{title}")
            continue
        files = {
            name: source.read_text(encoding="utf-8", errors="replace")
            for name, source in sources
        }
        entry = add_reference(
            REFERENCES,
            title=title,
            type=type_,
            description=description,
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            files=files,
            kit_vocabulary=kit_vocabulary,
            platform=platform,
        )
        created.append(entry.id)
        print(f"入库：{entry.id}（{len(files)} 个文件）")

    beep_title = "蜂鸣器驱动例程（beep / buzzer）"
    if beep_title not in existing:
        files = dict(_beep_entry_files())
        entry = add_reference(
            REFERENCES,
            title=beep_title,
            type="参考例程",
            description="蜂鸣器驱动例程（双平台）：beep_init / beep_on / beep_off / "
            "beep_toggle / beep_beep 响 N 声（阻塞式），引脚宏来自板级配置——"
            "骨架阶段选中 beep 模块时作为例程参考。",
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            files=files,
            kit_vocabulary=kit_vocabulary,
            platform="any",
        )
        created.append(entry.id)
        print(f"入库：{entry.id}（{len(files)} 个文件）")
    else:
        print(f"跳过（已存在）：{beep_title}")

    print(f"\n新建 {len(created)} 条：{'、'.join(created) or '（无）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
