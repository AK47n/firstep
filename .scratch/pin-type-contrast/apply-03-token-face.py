# -*- coding: utf-8 -*-
"""引脚配色 03 单 · 施工脚本：令牌面那 8 行从 `var(--pin-X)` 换成 `var(--pin-X-text)`。

两侧一起改（JS 守卫 + Python 口径），并把理由文字点明"03 单已换文字档"。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUARD = REPO / "tests" / "js" / "css-tokens.test.mjs"
PROBE_LIB = REPO / ".scratch" / "light-contrast" / "probe_lib.py"
FAMS = ["gpio", "pwm", "enc", "uart", "i2c", "spi", "adc", "exti"]

OLD_WHY = {
    "gpio": "引脚类型色当文字用（状态文字 / 板上引脚名 / 类型标）——色值与文字档见工单 pin-type-contrast/03",
    "pwm": "同上（PWM 族）", "enc": "同上（编码器族）", "uart": "同上（UART 族）",
    "i2c": "同上（I2C 族）",
    "spi": "同上（SPI 族；库内暂无该类型的角色，令牌仍在）",
    "adc": "同上（ADC 族）",
    "exti": "同上（EXTI 族；库内暂无该类型的角色，令牌仍在）",
}
NEW_WHY = {
    "gpio": "引脚类型**文字档**（状态文字 / 板上引脚名 / 类型标）——03 单把文字从主色拆出来，见 `--pin-gpio-text`",
    "pwm": "同上（PWM 族）", "enc": "同上（编码器族）", "uart": "同上（UART 族）",
    "i2c": "同上（I2C 族）",
    "spi": "同上（SPI 族；库内暂无该类型的角色，令牌仍在）",
    "adc": "同上（ADC 族）",
    "exti": "同上（EXTI 族；库内暂无该类型的角色，令牌仍在）",
}


def patch(path: Path, quote: str) -> int:
    s = path.read_text(encoding="utf-8")
    n = 0
    for f in FAMS:
        old_lit = f"{quote}var(--pin-{f}){quote}"
        new_lit = f"{quote}var(--pin-{f}-text){quote}"
        # 只替换"令牌面那一行"：JS 侧是 `[…, […], "text",`（方括号），Python 侧是 `(…, […], "text",`（圆括号）
        old = next((f"{br}{old_lit}, [" for br in ("[", "(") if f"{br}{old_lit}, [" in s), None)
        if old is None:
            print(f"  （{path.name}：{old_lit} 已经是文字档，跳过）")
            continue
        new = f"{old[0]}{new_lit}, ["
        s = s.replace(old, new, 1)
        n += 1
        old_why, new_why = OLD_WHY[f], NEW_WHY[f]
        if old_why not in s:
            raise SystemExit(f"{path.name}：找不到理由串 {old_why}")
        s = s.replace(old_why, new_why, 1)
    path.write_text(s, encoding="utf-8", newline="")
    return n


def main() -> int:
    a = patch(GUARD, '"')
    b = patch(PROBE_LIB, '"')
    print(f"已改：JS 守卫 {a} 行；Python 口径 {b} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
