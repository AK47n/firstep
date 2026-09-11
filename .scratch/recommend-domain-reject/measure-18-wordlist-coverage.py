# -*- coding: utf-8 -*-
"""词表覆盖率只读测量（工单 real-acceptance/08 取证工具，零写入零网络）。

算什么：

1. 「方案名 → 合法 name 域」（合法域 = 类别名 ∪ 该行 models，判据单源
   selection._solution_group）——多少方案名其实是模型抄不出合法名的（缺口规模）；
2. B1（把方案名去括号裸名补进同类别 models）后的**词表提示词字节增量**——
   这是 B1 唯一的非零风险（词表段喂模型，撑预算）；
3. 现场被拒名逐条现算 `build_module_selection`——红证（实施前应全部拒收，
   实施后四条应合法、`TI MSPM0 主控板` 仍拒收）。

跑法（仓库根）：

    $env:PYTHONPATH='src'; python .scratch/recommend-domain-reject/measure-18-wordlist-coverage.py

产物：stdout 即证据，落到 verify-18-wordlist-coverage.txt（工单 08 的验收基线）。
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from contest_generator import wordlist as W  # noqa: E402
from contest_generator.llm import DEFAULT_WORDLIST  # noqa: E402
from contest_generator.selection import SelectionError, build_module_selection  # noqa: E402

# 现场被拒名（第十六 / 十七轮真机，见工单 03 真机现场表与工单 08「实测数据」）
ONSITE_REJECTED = (
    "红外对管循迹数组",
    "红外测距传感器",
    "直流减速电机 + TB6612 双路驱动板",
    "串口摄像头（JPEG 输出 UART 转接）",
    "称重传感器",
    "TI MSPM0 主控板",
)
# 对照：应保持拒收（平台本身，闸不得被放宽成万金油）
MUST_STAY_REJECTED = ("TI MSPM0 主控板",)


def bare(name: str) -> str:
    """方案名的去括号裸名（提示词里方案名整句可见，模型常抄前半句）。"""
    return re.sub(r"（[^）]*）", "", name).strip()


def legal_names(groups) -> set[str]:
    legal: set[str] = set()
    for group in groups:
        legal.add(group.category)
        legal.update(group.models)
    return legal


def probe_selection(name: str) -> str:
    """现算一条库外建议名的判决（真跑 build_module_selection，不模拟判据）。"""
    raw = {
        "requirements": [
            {
                "requirement": "循迹",
                "sentence": 1,
                "modules": [],
                "suggestions": [{"name": name}],
            }
        ]
    }
    try:
        build_module_selection(raw, known_slugs=(), hardware_words=DEFAULT_WORDLIST)
    except SelectionError as exc:
        return f"拒收：{exc}"
    return "合法"


def main() -> int:
    groups = W.load_wordlist()
    legal = legal_names(groups)
    total = sum(len(g.solutions) for g in groups)

    print("== ① 覆盖率（方案名 → 合法 name 域）==")
    outside = [
        (g.category, s.name, bare(s.name))
        for g in groups
        for s in g.solutions
        if s.name not in legal
    ]
    bare_only = [x for x in outside if x[2] != x[1]]
    print(f"词表行 {len(groups)} / 方案 {total} 条")
    print(f"方案名不在合法 name 域：{len(outside)} / {total}")
    print(f"其中裸名 ≠ 全名（模型可能抄前半句）：{len(bare_only)} 条")

    print("\n== ② B1 词表提示词字节增量 ==")
    before = W.format_wordlist_prompt(groups)
    added = 0
    simulated = []
    for group in groups:
        models = list(group.models)
        have = set(models)
        for option in group.solutions:
            name = bare(option.name)
            if name and name not in have:
                models.append(name)
                have.add(name)
                added += 1
        simulated.append(dataclasses.replace(group, models=tuple(models)))
    after = W.format_wordlist_prompt(simulated)
    b_before, b_after = len(before.encode("utf-8")), len(after.encode("utf-8"))
    print(f"补裸名 {added} 条（去重后）")
    print(f"提示词 {b_before} → {b_after} 字节（增量 {b_after - b_before}）")

    print("\n== ③ 现场被拒名现算（红证 / 回归锚）==")
    for name in ONSITE_REJECTED:
        print(f"  {name!r:42} → {probe_selection(name)}")

    print("\n== ④ 对照：新增项应合法、平台名应仍拒收 ==")
    for name in ("红外传感器", "步进电机", "指纹模块"):
        print(f"  {name!r:42} → {probe_selection(name)}")

    print("\n== ⑤ 词表别名检查（models 内重复）==")
    dup = {
        g.category: [m for m in g.models if g.models.count(m) > 1]
        for g in groups
        if len(set(g.models)) != len(g.models)
    }
    print(f"含重复 models 的行：{dup or '无'}")

    print("\n== ⑥ 原始数据（供工单逐条裁定用）==")
    print(json.dumps(
        [{"category": g.category, "solutions": [s.name for s in g.solutions],
          "bare_not_in_models": [bare(s.name) for s in g.solutions
                                 if bare(s.name) and bare(s.name) not in g.models]}
         for g in groups],
        ensure_ascii=False, indent=1,
    ))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
