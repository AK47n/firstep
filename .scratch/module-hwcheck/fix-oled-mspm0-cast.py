# -*- coding: utf-8 -*-
"""给 mspm0 的 oled 探头加显式强转（工单 09 编译矩阵抓到的真 warning）。

`void OLED_ShowString(u8 x, u8 y, u8 *chr, u8 size1);`——第三个形参是 `u8 *`
（= `unsigned char *`），直接传 `"OLED OK"` 会被 tiarmclang 判
`warning: passing 'char[8]' to parameter of type 'u8 *'`（实测 2 条）。
检测程序的验收线是 0 error / **0 warning**，所以配方里要显式强转。

强转写 `(unsigned char *)` 而不是 `(u8 *)`：前者只用 C 关键字（校验器本来就认），
不依赖"哪个头 typedef 了 u8"。

⚠ **一次性脚本**：跑过一次之后前置断言（原文已改）会报错，属预期——它不是守卫，
别挂进任何自动流程。
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"

_OLD = 'OLED_ShowString(0, 0, "OLED OK", 16)'
_NEW = 'OLED_ShowString(0, 0, (unsigned char *)"OLED OK", 16)'
_NOTE = (
    "探头那句里的 `(unsigned char *)` 强转是**必须**的：本平台 "
    "`OLED_ShowString(u8 x, u8 y, u8 *chr, u8 size1)` 第三个形参是 `u8 *`"
    "（= `unsigned char *`），直接传字符串常量会被 tiarmclang 判 "
    "`warning: passing 'char[8]' to parameter of type 'u8 *'`——检测程序的验收线"
    "是 0 error / **0 warning**（工单 09 编译矩阵实测 2 条）。强转写 "
    "`unsigned char *` 而不是 `u8 *`：前者只用 C 关键字，不依赖哪个头 typedef 了 `u8`。"
)


def main() -> None:
    data = json.loads(RECIPES.read_text(encoding="utf-8"))
    cell = data["oled"]["mspm0"]
    calls = cell["probe"]["calls"]
    assert calls == [_OLD], f"mspm0 oled 探头不是预期形态：{calls}"
    cell["probe"]["calls"] = [_NEW]
    if _NOTE not in cell["note"]["lines"]:
        cell["note"]["lines"].append(_NOTE)
    RECIPES.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("mspm0 oled 探头已加显式强转")


if __name__ == "__main__":
    main()
