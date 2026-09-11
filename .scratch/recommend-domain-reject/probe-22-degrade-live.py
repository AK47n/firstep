"""第二十二轮探针之二：**降级路径的现场正证**（工单 real-acceptance/11 方向 ②）。

为什么要它：修好之后 `[PROBE16][域拒绝]` 行消失只能证「没被拒」，证不了「模型真
又犯了 instances 形态、是我们把它降级接住了」——那条形态若压根没出现，跑绿也说明
不了修复在起作用。本探针直接把 `llm.build_module_selection` 包一层：只要判决层
产出 `instances_degraded`（= 现场真出现非多实例模块带 `[]` / 单元素的形态），就
把它打出来并落盘。

**零源码注入**（不需要 exec llm.py）：`select_modules.parse` 找的是 llm 模块全局
命名空间里的 `build_module_selection`，探针侧换掉那个绑定即可（磁盘代码零改动）。

产物：`.scratch/recommend-domain-reject/degraded-22-live.txt`（每行一条 JSON：
{"notes": {slug: 标注}, "modules": [顶层模块清单]}）。

用法（GBK 控制台先设编码）：
    $env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
    python .scratch/recommend-domain-reject/probe-22-degrade-live.py \
        --topic 2026H --platform mspm0 --attempts 2 \
        --clarify-answers .scratch/recommend-domain-reject/clarify-answers-18-2026H.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

OUT = HERE / "degraded-22-live.txt"


def load_probe16():
    spec = importlib.util.spec_from_file_location(
        "probe16", HERE / "probe-16-recommend-live.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="2026H")
    parser.add_argument("--platform", default="mspm0")
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--clarify-answers", default="")
    args = parser.parse_args()

    clarify_answers: dict[str, str] = {}
    if args.clarify_answers:
        clarify_answers = json.loads(
            Path(args.clarify_answers).read_text(encoding="utf-8")
        )

    p16 = load_probe16()
    original = p16.llm_mod.build_module_selection
    caught: list[dict] = []

    def watching(raw, **kwargs):  # noqa: ANN001, ANN003
        result = original(raw, **kwargs)
        notes = getattr(result, "instances_degraded", None)
        if notes:
            caught.append({"notes": dict(notes), "modules": list(result.modules)})
            print("[PROBE22][降级接住]", json.dumps(notes, ensure_ascii=False),
                  flush=True)
        return result

    p16.llm_mod.build_module_selection = watching
    OUT.unlink(missing_ok=True)
    print(f"[探针] 降级路径监听已挂（磁盘代码零改动）；"
          f"topic={args.topic} platform={args.platform} attempts={args.attempts}",
          flush=True)

    for attempt in range(1, args.attempts + 1):
        print(f"\n===== 第 {attempt}/{args.attempts} 次真实推荐 =====", flush=True)
        kind, _data, rounds, questions, _vision = p16.run_once(
            args.topic, args.platform, clarify_answers
        )
        print(f"[结果] 终态 {kind}；收敛轮次 {rounds}；补问 {len(questions)} 条",
              flush=True)

    if not caught:
        print("[降级] 本轮现场未出现非多实例模块带 instances 的形态（无正证）",
              flush=True)
        return 1
    with OUT.open("w", encoding="utf-8") as fh:
        for record in caught:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"\n[降级] 现场接住 {len(caught)} 次降级 → {OUT}", flush=True)
    for record in caught:
        print(f"  · {json.dumps(record['notes'], ensure_ascii=False)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
