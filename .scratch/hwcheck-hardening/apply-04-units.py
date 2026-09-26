# -*- coding: utf-8 -*-
"""工单 hwcheck-hardening/04 的落地脚本：把 5 条超限读数行的长说明挪进该格平台说明。

板上行缓冲是 `static char hwcheck_line[128]`（可用 127 字节），溢出保护会**静默截断**——
中文一字 3 字节，截在字中间就是半个乱码。超限的 5 条全在 pilot 格（既有守卫刻意不吃 pilot）。

改法：行上只留**短量纲**，被挪走的那段说明进该格 note 的**倒数第二条**（末条必须留给
「未上板」自述——02 单的守卫钉着"这句在最后一条"）。

纪律：逐字节读写（LF 保持），不重新序列化整个 JSON。
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECIPE = ROOT / "library/hwcheck_recipes.json"
WORST_INT_DIGITS = 12
LIMIT = 128

# (slug, platform, expression) → 行上留下的短量纲
SHORT_UNITS: dict[tuple[str, str, str], str] = {
    ("debug_uart", "stm32", "gpio_get(DEBUG_UART_RX_GPIO, DEBUG_UART_RX_Pin)"):
        "RX 脚电平（1 = 空闲高，0 = 没拉高）",
    ("adc", "mspm0", "adc_get(ADC_1, ADC_Channel_0)"):
        "ADC_CH0 12 位值（0-4095；3V3≈4095）",
    ("adc", "mspm0", "adc_get(ADC_1, ADC_Channel_1)"):
        "ADC_CH1 12 位值（0-4095）",
    ("beep", "stm32", "gpio_get(BUZZER_GPIO, BUZZER_PIN)"):
        "蜂鸣器脚电平（1 = 不响，0 = 响）",
    ("adc", "stm32", "adc_get(ADC_1, ADC_0_CH)"):
        "ADC_CH0 12 位值（0-4095；3V3≈4095）",
}
NOTE_PREFIX = "读数的完整口径（板上那一行只印量纲，细节挪到这里）："


def width(expression: str, unit: str) -> int:
    return len(("x" * WORST_INT_DIGITS + (f" {unit}" if unit else "") + f" ({expression})").encode())


def quoted(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def main() -> int:
    original = RECIPE.read_bytes()
    text = original.decode("utf-8")
    data = json.loads(text)

    moved: dict[tuple[str, str], list[str]] = {}
    for (slug, platform, expression), short in SHORT_UNITS.items():
        items = (data[slug][platform].get("read") or {}).get("items") or []
        hit = [it for it in items if it["expression"] == expression]
        if len(hit) != 1:
            print(f"✗ 目标不唯一：{slug} × {platform} [{expression}] → {len(hit)} 条")
            return 2
        old_unit = str(hit[0]["unit"])
        if width(expression, short) >= LIMIT:
            print(f"✗ 新量纲还是超限：{slug} × {platform} {width(expression, short)}B")
            return 2
        if text.count(quoted(old_unit)) != 1:
            print(f"✗ 旧量纲串不唯一：{slug} × {platform} → {old_unit[:40]}…")
            return 2
        text = text.replace(quoted(old_unit), quoted(short), 1)
        moved.setdefault((slug, platform), []).append(old_unit)
        print(f"  ✓ {slug} × {platform} [{expression}]：{width(expression, old_unit)}B → {width(expression, short)}B")

    # 把挪走的那段说明插到该格 note 的倒数第二条
    for (slug, platform), olds in moved.items():
        lines = [str(n) for n in ((data[slug][platform].get("note") or {}).get("lines") or [])]
        if len(lines) < 2 or "**未上板**" not in lines[-1]:
            print(f"✗ {slug} × {platform} 的平台说明形态不符合预期（末条应当是「未上板」）")
            return 2
        new_line = NOTE_PREFIX + "；".join(olds)
        prev, last = lines[-2], lines[-1]
        anchor = quoted(prev) + ",\n"
        # 锚点要唯一：用「倒数第二条 + 换行 + 缩进 + 末条」整段来定位
        idx = text.find(quoted(prev))
        if idx < 0 or text.count(quoted(prev)) != 1:
            print(f"✗ {slug} × {platform} 的倒数第二条说明不唯一，无法安全插入")
            return 2
        # 找到该行行首缩进
        line_start = text.rfind("\n", 0, idx) + 1
        indent = text[line_start:idx]
        tail_anchor = quoted(prev) + ",\n" + indent + quoted(last)
        if tail_anchor not in text:
            print(f"✗ {slug} × {platform} 找不到「倒数第二条 + 末条」整段锚点")
            return 2
        text = text.replace(
            tail_anchor,
            quoted(prev) + ",\n" + indent + quoted(new_line) + ",\n" + indent + quoted(last),
            1,
        )
        print(f"  ✓ {slug} × {platform}：把被挪走的口径写进平台说明（末条「未上板」仍在最后）")

    RECIPE.write_bytes(text.encode("utf-8"))

    # 复核：JSON 合法 / LF / 每条读数行都在缓冲内 / 未上板末条仍在最后
    raw = RECIPE.read_bytes()
    check = json.loads(raw.decode("utf-8"))
    over = []
    hit_unboard = total = 0
    for slug, entry in check.items():
        if not isinstance(entry, dict):
            continue
        for platform, cell in entry.items():
            if not isinstance(cell, dict):
                continue
            total += 1
            lines = [str(n) for n in ((cell.get("note") or {}).get("lines") or [])]
            if lines and "**未上板**" in lines[-1]:
                hit_unboard += 1
            for it in ((cell.get("read") or {}).get("items") or []):
                if width(str(it["expression"]), str(it.get("unit") or "")) >= LIMIT:
                    over.append(f"{slug} × {platform} [{it['expression']}]")
    print(f"\n复核：JSON 合法；换行 = {'CRLF' if b'\\r\\n' in raw else 'LF'}；字节 {len(original)} → {len(raw)}")
    print(f"      超限读数行 = {len(over)} {over if over else '（全在 128 字节内）'}")
    print(f"      平台说明末条仍带「未上板」= {hit_unboard}/{total}")
    return 0 if not over and hit_unboard == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
