# -*- coding: utf-8 -*-
"""检测页「学生实际看到什么」的取证探针（只读，不写盘、不起服务）。

用途：把 hwcheck_view 一次投影的载荷按键打印出来——回答「这个栏目现在是否
真的能帮学生判断手上这件通不通 / 会不会用」时，看的是页面实际内容，
不是 spec 的承诺。

跑法（仓库根）：
  $env:PYTHONIOENCODING='utf-8'
  .venv\\Scripts\\python.exe .scratch\\hwcheck-acceptance\\probe-page.py
输出同时落 .scratch\\hwcheck-acceptance\\probe-page.txt（UTF-8，绕开控制台 GBK）。
"""
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.hwcheck import HwCheckConfig, render_checklist  # noqa: E402
from contest_generator.hwcheck_board import hwcheck_view  # noqa: E402

LIBRARY = ROOT / "library" / "modules"
MASTERS = ROOT / "library" / "masters"

OUT = io.StringIO()


def w(line=""):
    OUT.write(str(line) + "\n")


def dump(title, platform, devices, debug_uart=True, oled=True):
    w("=" * 78)
    w(f"# {title}")
    w(f"# 平台={platform}  器件={list(devices) or '（一件都不选）'}  串口={debug_uart} OLED={oled}")
    w("=" * 78)
    cfg = HwCheckConfig(
        platform=platform, debug_uart=debug_uart, oled=oled, devices=tuple(devices)
    )
    from contest_generator.hwcheck import HwCheckError

    try:
        view = hwcheck_view(
            cfg, module_library_dir=LIBRARY, masters_dir=MASTERS, require_pins=True
        )
    except HwCheckError as exc:
        w("\n!! 生成前被拦下（HwCheckError → 400），页面文案如下：\n")
        w(str(exc))
        w()
        return
    board = view.board
    wiring = board["wiring"]

    w("\n-- 接线表 rows --")
    for row in wiring["rows"]:
        w("    " + str(row))
    w(f"    pin_fixes: {wiring.get('pin_fixes')}")
    w(f"    footnote: {wiring.get('footnote')}")

    w("\n-- 默认脚冲突组 groups --")
    for g in wiring.get("groups") or []:
        w("    " + str(g))
    w(f"    board_shares: {wiring.get('board_shares')}")

    w("\n-- 建议检测顺序 order --")
    for item in wiring.get("order") or []:
        w("    " + str(item))
    w(f"    guide: {wiring.get('guide')}")
    w(f"    reason: {wiring.get('reason')}")
    w(f"    missing: {wiring.get('missing')}")

    w("\n-- 专精小节 sections --")
    for s in view.sections:
        w(f"    [{s.slug}] 计划: {getattr(s, 'plan', '')}")
        note = getattr(s, "note", "")
        if note:
            w(f"      平台差异: {note}")
    w(f"    unspecialized: {board['unspecialized']}")
    w(f"    custom: {board['custom']}")
    w(f"    exclusive_groups: {board['exclusive_groups']}")

    w("\n-- 串口命令台 console --")
    console = board["console"]
    if isinstance(console, dict):
        w(f"    available: {console.get('available')}")
        w(f"    hint: {console.get('hint')}")
        for c in console.get("commands") or []:
            w(f"    命令 {c.get('command')!r} → {c.get('slug')}: {c.get('description')}")
    else:
        w("    " + str(console))

    w("\n-- 上板确认清单 --")
    items = render_checklist(cfg, view.custom)
    for it in items:
        w(f"    [{it.id}] 应看到: {it.expect}")
        w(f"           不对先查: {it.check}")
    w()


if __name__ == "__main__":
    dump("场景 A：只验板子活着（一件器件都不选）", "mspm0", [])
    dump("场景 B：地猛星 + MPU6050（平台不对称那一格）", "mspm0", ["ml_mpu6050"])
    dump("场景 C：stm32 + MPU6050（原文说只有原始六轴）", "stm32", ["ml_mpu6050"])
    dump("场景 D：地猛星 + LED + OLED + 按键", "mspm0", ["led", "oled", "key"])
    dump("场景 E：未专精件（看通用降级怎么说话）", "mspm0", ["aht10"])
    text = OUT.getvalue()
    (Path(__file__).parent / "probe-page.txt").write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(text)
