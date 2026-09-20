# -*- coding: utf-8 -*-
"""配方 note 的三处质量修（工单 09 评审整改，一次性脚本）。

1. **硬编码行号**（`（ml_adc.h 第 33 行）`）：头文件一改行号就失效，且读者会被
   引到错的物理行——改成"文件 + 名字"（`（ml_adc.h 的 adc_get）`）。
2. **xunji 的「（真机极性）」是overclaim**：该模块 mspm0 条目自己的状态是
   **编译验证未上板**（manifest notes 原话），"真机"说的是**移植源**那份代码。
   改成如实口径。
3. **`**` 强调未闭合**（xunji 第 1 行有 3 个 `**`）：渲染出来强调会串位。

跑完把每件 note 里 `**` 计数为奇数（疑似未闭合）的行打出来复核。

⚠ **一次性脚本**：三处修都只对"改动前"的原文生效，跑过一次之后再跑等于空转
（`**` 复核那段仍可读）——它不是守卫，别挂进任何自动流程。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"

_LINE_REF_RE = re.compile(r"（([A-Za-z_][\w.]*\.h) 第 \d+ 行([^）]*)）")

_XUNJI_OLD_HEAD = (
    "**这一件会驱动执行机构：库里的 `xunji_set_speed(left, right)` 会直接写电机方向与 "
    "PWM 占空比（正=前进、负=后退，百分比 → motor 原始占空比 0~1300）——只要调到它车就会跑。"
    "所以本配方**一个输出动作都不放**："
)
_XUNJI_NEW_HEAD = (
    "**这一件会驱动执行机构**：库里的 `xunji_set_speed(left, right)` 会直接写电机方向与 "
    "PWM 占空比（正=前进、负=后退，百分比 → motor 原始占空比 0~1300）——只要调到它车就会跑。"
    "**所以本配方一个输出动作都不放**："
)
_XUNJI_POLARITY_OLD = "**极性：1 = 白区、0 = 压黑线**（真机极性）"
_XUNJI_POLARITY_NEW = (
    "**极性：1 = 白区、0 = 压黑线**（按驱动实现与移植源那份真机代码；本模块 mspm0 条目"
    "自己的状态是**编译验证未上板**——manifest 原话）"
)


def main() -> None:
    data = json.loads(RECIPES.read_text(encoding="utf-8"))
    changed = {"line_refs": 0, "xunji": 0}
    for slug, platforms in data.items():
        if slug == "_comment" or not isinstance(platforms, dict):
            continue
        for platform, cell in platforms.items():
            note = cell.get("note") or {}
            lines = note.get("lines") or []
            out: list[str] = []
            for line in lines:
                new_line, hits = _LINE_REF_RE.subn(
                    lambda m: f"（{m.group(1)}{m.group(2)}）", line
                )
                changed["line_refs"] += hits
                if _XUNJI_OLD_HEAD in new_line:
                    new_line = new_line.replace(_XUNJI_OLD_HEAD, _XUNJI_NEW_HEAD)
                    changed["xunji"] += 1
                if _XUNJI_POLARITY_OLD in new_line:
                    new_line = new_line.replace(_XUNJI_POLARITY_OLD, _XUNJI_POLARITY_NEW)
                    changed["xunji"] += 1
                out.append(new_line)
            note["lines"] = out
            cell["note"] = note
    RECIPES.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 复核：还有没有 `**` 未闭合的行（奇数个 = 疑似串位）
    odd: list[str] = []
    for slug, platforms in data.items():
        if slug == "_comment" or not isinstance(platforms, dict):
            continue
        for platform, cell in platforms.items():
            for line in (cell.get("note") or {}).get("lines") or []:
                if line.count("**") % 2:
                    odd.append(f"{slug}:{platform} :: {line[:80]}")
    print(f"改动：行号 {changed['line_refs']} 处 / xunji {changed['xunji']} 处")
    print("`**` 计数为奇数（疑似未闭合）的行：" + (str(len(odd)) + " 条"))
    for item in odd:
        print("  -", item)


if __name__ == "__main__":
    main()
