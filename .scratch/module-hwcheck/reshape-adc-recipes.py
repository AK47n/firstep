# -*- coding: utf-8 -*-
"""把 adc 两格改成"直接写枚举常量"的形态（工单 09 的一次性整形脚本）。

背景：配方校验的接口清单原来不收枚举常量，adc 的读数只能绕道"整型变量 + 强转"，
代价是 stm32 侧 4 个 `#188-D`（验收线是 0 warning）。`hwcheck_recipe` 补上枚举
常量 / typedef 名之后，`adc_get(ADC_1, ADC_Channel_0)` 这种自然写法能过校验，
本脚本把已经合并进库的那两格改回自然形态（locals / probe 的强转往返一并删掉）。

⚠ **一次性脚本**：跑过一次之后再跑会因为这些字段已经不在了而报错，属预期——
它不是守卫，别挂进任何自动流程。
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"


def main() -> None:
    data = json.loads(RECIPES.read_text(encoding="utf-8"))
    cell = data["adc"]

    for removed in ("locals", "probe"):
        cell["stm32"].pop(removed, None)
        cell["mspm0"].pop(removed, None)

    cell["stm32"]["read"] = {
        "items": [
            {
                "expression": "adc_get(ADC_1, ADC_0_CH)",
                "unit": "ADC_CH0（PA0 = ADC_Channel_0）12 位电压值，LSB：0-4095，"
                        "接 3V3 应接近 4095、接 GND 应接近 0",
            },
            {
                "expression": "adc_get(ADC_1, ADC_1_CH)",
                "unit": "ADC_CH1（PA1 = ADC_Channel_1）12 位电压值，LSB：0-4095，同上的判据",
            },
        ]
    }
    cell["mspm0"]["read"] = {
        "items": [
            {
                "expression": "adc_get(ADC_1, ADC_Channel_0)",
                "unit": "ADC_CH0（PA24 / A0_3 = ADC_Channel_0）12 位电压值，LSB：0-4095，"
                        "接 3V3 应接近 4095、接 GND 应接近 0",
            },
            {
                "expression": "adc_get(ADC_1, ADC_Channel_1)",
                "unit": "ADC_CH1（PA26 / A0_1 = ADC_Channel_1，与 joystick 摇杆 X 同通道）"
                        "12 位电压值，LSB：0-4095",
            },
        ]
    }
    order = ["include", "init", "read", "console", "note"]
    for platform in ("stm32", "mspm0"):
        cell[platform] = {key: cell[platform][key] for key in order if key in cell[platform]}

    RECIPES.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("adc cells rewritten")


if __name__ == "__main__":
    main()
