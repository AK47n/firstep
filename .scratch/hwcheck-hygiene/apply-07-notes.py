"""apply-07-notes.py — 工单 hwcheck-hygiene/07 的数据面：给四个多实例格补一句
「多实例只验第一路」的如实自述（`library/hwcheck_recipes.json`）。

为什么不用 `json.dump` 整档重写：这个文件 `core.autocrlf=true`、盘上是 **LF**，
整档重写会把缩进 / 键序 / 换行全部重排（评审与回滚都会变成噪声）。本脚本按**字节**
定位（锚点 = 原句 + `",` 收尾），只替换那一句，前后字节逐字保留。

用法（幂等，重复跑 = 第二次报"已就位"）：
    python .scratch/hwcheck-hygiene/apply-07-notes.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from patch_bytes import patch  # noqa: E402  （本目录的小工具，两份脚本共用）

REPO = pathlib.Path(__file__).resolve().parents[2]
TARGET = REPO / "library/hwcheck_recipes.json"

# (格, 替换前那一句, 替换后那一句, 该锚点应命中几次) —— led × mspm0 原本已自述
# "只测通道 0"，这一轮只是把口径补全（含「第一路」，并说清多实例工程也一样）。
# ⚠ key 两格的锚点**逐字相同**（两平台那条多通道说明本来就同一句话），所以按 2 次处理：
# 它们各需要同一处插入，判据是"命中几次就替换几次"，不是"必须唯一"。
EDITS: list[tuple[str, str, str, int]] = [
    (
        "led × stm32 首条",
        "三路都要看：灯在闪 = 程序在跑，灭的那一路说明那一路没接对。",
        "三路都要看：灯在闪 = 程序在跑，灭的那一路说明那一路没接对。"
        "多实例只验**第一路**：工程里配了 4 路 LED 时（生成器覆写 led_instances.h，"
        "通道数会大于 1），检测程序这一趟只驱动第一路（LED_RED）——通道数不是「每一路都验过」"
        "的意思，另外几路这一趟一个动作都没有。",
        1,
    ),
    (
        "led × mspm0 第二条",
        "led_init() 是 void，本件不判返回值、也不判通断——只看灯闪不闪。",
        "多实例只验**第一路**：就算工程里配了多路 LED，这一趟也只测第一路（通道 0）"
        "——回显的通道数说的是本工程有几路，不是「每一路都验过」。"
        "led_init() 是 void，本件不判返回值、也不判通断——只看灯闪不闪。",
        1,
    ),
    (
        "key × 两平台的多通道那条（同一句话，各一处）",
        "所以本件只读首通道；工程里配了多路按键时",
        "所以本件只读首通道；多实例只验**第一路**"
        "（检测程序这一趟只驱动第一路，另外几路一个动作都没有）。"
        "工程里配了多路按键时",
        2,
    ),
]


def main() -> int:
    blob = TARGET.read_bytes()
    before = hashlib.sha256(blob).hexdigest()
    text = blob.decode("utf-8")
    todo = [(old, new, want) for where, old, new, want in EDITS if new not in text]
    for where, _old, new, _want in EDITS:
        if new in text:
            print(f"· {where}：已就位（跳过）")
    if not todo:
        print(f"无需改动；sha256 = {before}")
        return 0
    patch(TARGET, todo)
    after = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    raw = TARGET.read_bytes()
    print(f"\n写了 {len(todo)} 条锚点替换；换行形态："
          f"{'CRLF' if b'\\r\\n' in raw else 'LF'}（写入后实测）；"
          f"字节数 {len(blob)} → {len(raw)}")
    print(f"sha256：{before} → {after}")
    # 复核：仍是合法 JSON，且四格都带上了自述
    data = json.loads(TARGET.read_text(encoding="utf-8"))
    for slug in ("led", "key"):
        for platform, cell in data[slug].items():
            note = "\n".join(cell["note"]["lines"])
            assert "第一路" in note, f"{slug} × {platform} 没补上"
    print("复核：JSON 合法、led/key 两平台四格都含「第一路」✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
