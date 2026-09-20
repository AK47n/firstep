# -*- coding: utf-8 -*-
"""把 adc 配方 note 里"绕道强转"那段说明改成现状（工单 09 的一次性整形脚本之二）。

`hwcheck_recipe` 补上枚举常量 / typedef 名之后，读数可以直接写
`adc_get(ADC_1, ADC_0_CH)`：① 那段"为什么绕这一下"的说明不再成立；
② 由此产生的 `#188-D` 遗留也随之消失——两处都得跟着改，否则配方文档说谎。

做法：正则把「两路读数写成 …（绕道理由结尾）」整段换成新措辞 + 删掉 `#188-D`
那条遗留说明（两平台的原措辞不同，用正则锚两端，不照抄整句）。末尾断言旧措辞
一处不剩、新措辞在场，并把 note 逐行打出来给人复核。

⚠ **一次性脚本**：跑过一次之后旧措辞已经不在了，再跑会断言报错——属预期，
它不是守卫，别挂进任何自动流程。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"

# 旧段：从「两路读数写成」到绕道理由的句末（stm32 收在「写法。」、mspm0 收在「判红。」）
_OLD_BLOCK_RE = re.compile(r"两路读数写成.*?(?:真编得过的写法。|当场判红。)", re.DOTALL)

_NEW_TEXT = {
    "stm32": (
        "两路读数直接写 `adc_get(ADC_1, ADC_0_CH)` / `adc_get(ADC_1, ADC_1_CH)`："
        "通道用绑定宏（换引脚只改这两个宏），ADC 用枚举常量 `ADC_1`。"
        "这些名字都在头文件里真实存在，配方校验认（枚举常量与 typedef 名已进接口清单，工单 09）。"
    ),
    "mspm0": (
        "两路读数直接写 `adc_get(ADC_1, ADC_Channel_0)` / `adc_get(ADC_1, ADC_Channel_1)`："
        "`ADC_Channel_0` / `ADC_Channel_1` = MEM0 / MEM1，adc_get 内部拿它当 MEM 索引取结果，"
        "返回值同样是 12 位（0-4095）。这些名字都在 adc_mspm0.h 里真实存在，配方校验认"
        "（枚举常量与 typedef 名已进接口清单，工单 09）。"
    ),
}

_LEGACY_MARK = "**已知遗留（如实记）**：本节在 stm32 上编出来有 4 个 `#188-D"


def main() -> None:
    data = json.loads(RECIPES.read_text(encoding="utf-8"))
    for platform, new_text in _NEW_TEXT.items():
        lines = data["adc"][platform]["note"]["lines"]
        rewritten: list[str] = []
        for line in lines:
            if line.startswith(_LEGACY_MARK):
                continue
            replaced, hits = _OLD_BLOCK_RE.subn(new_text, line)
            assert hits <= 1, f"{platform} 的绕道说明出现 {hits} 次（预期 ≤1）"
            rewritten.append(replaced)
        data["adc"][platform]["note"]["lines"] = rewritten

    for platform in ("stm32", "mspm0"):
        joined = "\n".join(data["adc"][platform]["note"]["lines"])
        for stale in ("为什么绕这一下", "#188-D", "`adc_i`", "`ch0`", "强转赋值"):
            assert stale not in joined, f"{platform} 仍残留旧措辞：{stale}"
        # ⚠ 别用裸 "adc_i" 判：`adc_init()` 里也含这三个字符（本脚本第一版就栽在这）
        assert not re.search(r"\badc_i\b(?!nit)", joined), f"{platform} 仍残留 adc_i 变量"
        assert "adc_get(ADC_1," in joined, f"{platform} 的读数说明没更新"
        print(f"==== {platform} note（复核用）")
        for line in data["adc"][platform]["note"]["lines"]:
            print("  -", line[:100] + ("…" if len(line) > 100 else ""))
    RECIPES.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("adc note 整形完成")


if __name__ == "__main__":
    main()
