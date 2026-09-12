"""生成「功能组卡」前端验收用的真实载荷 fixture（工单 group-choice-required/01）。

为什么要它：`/api/recommend` 要真 LLM（烧额度），而本次改动要验的是**前端渲染与拦截**
——用真库 + 用户现场那道题的需求结构，跑一遍真实解析层（`build_module_selection`）与出卡层
（`build_exclusive_groups`），把得到的 done 载荷形状落盘，浏览器冒烟脚本再把它喂给真页面。

判据全部来自库与生产代码；本脚本不改任何状态、零额度。

用法：`$env:PYTHONPATH='src'; python .scratch/group-choice-required/make-payload.py`
产物：`.scratch/group-choice-required/payload.json`（含 `exclusive_groups` / `modules` /
`requirements` 三段 + 一句自证：`choice_required` 命中卡为真）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "payload.json"
AMB = Path(__file__).resolve().parent / "payload-ambiguous.json"
MODULES = ROOT / "library" / "modules"
PLATFORM = "mspm0"


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from contest_generator.manifest import (
        ModuleManifest,
        build_manifest_summaries,
        collect_exclusive_groups,
    )
    from contest_generator.selection import build_exclusive_groups, build_module_selection

    manifests = [ModuleManifest.load(p) for p in sorted(MODULES.iterdir()) if p.is_dir()]
    # 用户现场的需求结构（截图里的句子 4 / 12 与功能组卡）：功能组两个成员都被 AI 推荐过
    raw = {
        "requirements": [
            {
                "sentence": 4,
                "requirement": "沿直线与半圆弧路径自动行驶",
                "modules": [{"slug": "pid", "reason": "灰度循迹 + PID"}],
            },
            {
                "sentence": 12,
                "requirement": "无引导标记直线段航向保持",
                "modules": [{"slug": "jy61p", "reason": "陀螺仪输出角度，直线段保持航向"}],
            },
            {
                "sentence": 1,
                "requirement": "航向保持 / 姿态传感器",
                "modules": [{"slug": "imu_uart", "reason": "UART 串口陀螺仪"}],
            },
        ],
        "references": [],
        "questions": [],
    }
    summaries = build_manifest_summaries(manifests)
    selection = build_module_selection(
        raw,
        known_slugs=[m.slug for m in manifests],
        manifest_summaries=tuple(summaries),
    )
    groups = collect_exclusive_groups(manifests)
    cards = build_exclusive_groups(
        list(selection.modules),
        groups,
        PLATFORM,
        dropped=selection.dropped_exclusive_members,
    )
    payload = {
        "modules": [
            {"slug": slug, "reason": selection.reasons.get(slug, "")}
            for slug in selection.modules
        ],
        "requirements": [
            {
                "sentence": r.sentence_index,
                "requirement": r.requirement,
                "modules": list(r.modules),
            }
            for r in selection.requirements
        ],
        "exclusive_groups": cards,
        "score_points": [],
        "references": [],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hard = [c for c in cards if c.get("choice_required")]
    print(f"落盘：{OUT}")
    print(f"  组卡：{[(c['id'], c['recommended'], c['dropped']) for c in cards]}")
    print(f"  硬选择卡（choice_required=true）：{[c['id'] for c in hard]}")
    print(f"  modules：{list(selection.modules)}")
    print(f"  requirements：{[r.sentence_index for r in selection.requirements]}")
    assert hard, "fixture 里必须至少有一张硬选择卡（否则冒烟验不到本次改动）"

    # 第二份 fixture = **歧义态**（用户现场那张图的形态）：同一功能的两件同时在集合里。
    # 生产路径上它出现在两种场合——① 收敛前的旧缓存载荷（`--reuse-recommend` 补刀之前）；
    # ② 同组互斥没生效的库/载荷（本次 jy61p 那一半就是这种：它当时不在组里）。
    # 「必须由用户选择」真正要拦的正是这一态：组内 ≥2 件 = 需要人拍板。
    ambiguous_modules = list(selection.modules) + list(
        selection.dropped_exclusive_members.get("attitude-hold", ())
    )
    ambiguous = {
        "modules": [
            {"slug": s, "reason": selection.reasons.get(s, "")} for s in ambiguous_modules
        ],
        "requirements": payload["requirements"],
        "exclusive_groups": build_exclusive_groups(ambiguous_modules, groups, PLATFORM),
        "score_points": [],
        "references": [],
    }
    AMB.write_text(json.dumps(ambiguous, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"落盘（歧义态）：{AMB}")
    print(f"  modules：{ambiguous_modules}")
    print(f"  组卡：{[(c['id'], c['recommended']) for c in ambiguous['exclusive_groups']]}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
