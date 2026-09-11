"""红证（工单 real-acceptance/11 方向 ②）：拿**现场原始模型输出**直测判决层。

为什么要有它：方向 ② 的前提是「模型到底输出了什么形态」。`[PROBE16][域拒绝]`
只印异常文本，所以 probe-22 把每条违规现场的**原始模型输出**（dict）落盘在
`instances-shape-22.txt`；本脚本把那份现场逐条**重放**进
`build_module_selection`（多实例能力清单取真实库的 manifest.multi_instance，
与生产同源），打印每条的判决：

- 修前（HEAD）：单元素现场也应抛 `SelectionError`「模块 X 不支持多实例」
  → 这就是红证（工单验收第 1 条）；
- 修后：同一条现场应降级为「无实例 + instances_degraded 标注」，
  而 ≥2 元素现场**仍拒收**（对照用例）。

用法（GBK 控制台先设编码）：
    $env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
    python .scratch/recommend-domain-reject/probe-22-red-first.py \
        [--shape .scratch/recommend-domain-reject/instances-shape-22.txt]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.library import list_modules  # noqa: E402
from contest_generator.selection import (  # noqa: E402
    SelectionError,
    build_module_selection,
)


def multi_instance_slugs() -> list[str]:
    """真实库的多实例能力清单（与生产 llm.select_modules 同源口径）。"""
    modules = list_modules(REPO / "library" / "modules")
    return [m.slug for m in modules if m.multi_instance is not None]


def replay(raw_form: dict) -> dict:
    """一条现场形态 → 最小模型输出 dict（形状照现场那条所在的位置）。"""
    slug = raw_form["slug"]
    value = raw_form["value"]
    module = {"slug": slug, "reason": "现场复现", "instances": value}
    if raw_form["path"].startswith("requirements"):
        return {
            "requirements": [
                {"requirement": "现场复现", "sentence": 1, "modules": [module]}
            ]
        }
    return {"modules": [module]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shape", default=str(HERE / "instances-shape-22.txt"))
    args = parser.parse_args()

    shape_path = Path(args.shape)
    if not shape_path.exists():
        print(f"[红证] 缺现场落盘 {shape_path}（先跑 probe-22-instances-shape.py）")
        return 2
    multi = multi_instance_slugs()
    print(f"[红证] 库内多实例能力清单（{len(multi)} 条）：{', '.join(multi) or '（空）'}",
          flush=True)

    records = [
        json.loads(line)
        for line in shape_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    forms = [
        (record, form)
        for record in records
        for form in record.get("forms") or []
    ]
    if not forms:
        print("[红证] 现场无 instances 形态可重放")
        return 2

    print(f"[红证] 现场 {len(records)} 条违规 / {len(forms)} 个 instances 形态：",
          flush=True)
    for record, form in forms:
        raw = replay(form)
        print(f"\n  · 现场异常：{record['error']}", flush=True)
        print(f"    形态：{form['path']} slug={form['slug']} "
              f"type={form['type']} len={form['len']} "
              f"value={json.dumps(form['value'], ensure_ascii=False)[:160]}",
              flush=True)
        try:
            result = build_module_selection(
                raw,
                known_slugs=[form["slug"]],
                multi_instance_slugs=multi,
            )
        except SelectionError as exc:
            print(f"    判决：拒收 → {exc}", flush=True)
        else:
            # 修前（HEAD）的 ModuleSelection 没有 instances_degraded 字段——
            # getattr 兜底，同一脚本能跑修前/修后两侧（红证 ↔ 绿证对照）
            print(f"    判决：通过 → instances={result.instances} "
                  f"instances_degraded="
                  f"{getattr(result, 'instances_degraded', {})}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
