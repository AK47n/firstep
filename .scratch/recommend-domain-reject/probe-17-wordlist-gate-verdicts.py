"""第十七轮评估探针：词表闸对第十六轮现场五个被拒名的确定性判定（只读，不调 LLM）。

工单 real-acceptance/03 修复方向 ③「降级而非拒收」的评估前置：先把五个被拒名
逐条过一遍现行判据（`selection._solution_group` 单源），再看它们与词表里
**已经存在的东西**是什么关系——这决定「降级」能不能落成确定性规则。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/recommend-domain-reject/probe-17-wordlist-gate-verdicts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.llm import DEFAULT_WORDLIST  # noqa: E402
from contest_generator.selection import _solution_group  # noqa: E402

# 第十六 / 十七轮真机现场被拒的库外建议名（工单 03 表格逐字 + 第十七轮探针新增）
REJECTED = (
    "红外对管循迹数组",
    "红外测距传感器",
    "TI MSPM0 主控板",
    "称重传感器",
    "直流减速电机 + TB6612 双路驱动板",
    # 第十七轮 2026H/mspm0 现场新增（verify-17-recommend-2026H-mspm0.txt）
    "串口摄像头（JPEG 输出 UART 转接）",
)

# 词表内两类合法 name（类别 / 型号）与第三类可展示名（选购方案名）——判据
# 只看前两类，方案名不在合法 name 取值域内（这就是闸能拒的理由）。
CATEGORIES = {g.category for g in DEFAULT_WORDLIST}
MODELS = {m for g in DEFAULT_WORDLIST for m in g.models}
SOLUTIONS = {
    (g.category, s.name) for g in DEFAULT_WORDLIST for s in g.solutions
}


def main() -> int:
    print(f"词表：{len(DEFAULT_WORDLIST)} 行 / {len(CATEGORIES)} 类别 / "
          f"{len(MODELS)} 型号 / {len(SOLUTIONS)} 选购方案")
    print()
    for name in REJECTED:
        hit = _solution_group(name, DEFAULT_WORDLIST)
        as_category = name in CATEGORIES
        as_model = name in MODELS
        as_solution = [cat for cat, sol in SOLUTIONS if sol == name]
        # 方案名的「去括号裸名」是否与 name 相同（如「红外测距传感器
        # （GP2Y0A02YK0F）」的裸名就是「红外测距传感器」——模型多半见过它）
        bare_hits = [
            (cat, sol)
            for cat, sol in SOLUTIONS
            if sol.split("（")[0].strip() == name
        ]
        print(f"被拒名：{name}")
        print(f"  现行判据 _solution_group → "
              f"{'命中类别行 ' + hit.category if hit else 'None（拒收）'}")
        print(f"  是类别名={as_category} 是型号名={as_model} "
              f"是选购方案名={as_solution or False} "
              f"是某方案名的裸名={bare_hits or False}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
