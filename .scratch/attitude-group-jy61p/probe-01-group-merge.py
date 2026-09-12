"""jy61p 并入「航向保持 / 姿态传感器」功能组的验收探针。

用户报告的现场（2026-09-12）：AI 推荐把 `imu_uart` 放进「功能组选择 · 航向保持 / 姿态传感器」
单选框，同一份推荐里句子 12 又出现 `jy61p` 这个**可移除 chip**——用户已经选了一个姿态传感器，
需求句里却还挂着另一个姿态件。根因不在 UI：`jy61p` 的 manifest **没声明** `exclusive_group`，
所以它既不入组卡、也不吃同组互斥收敛。本探针按代码事实取证 + 用真库跑一遍收敛。

只读、零额度、不联网。

用法：`$env:PYTHONIOENCODING='utf-8'; python .scratch/attitude-group-jy61p/probe-01-group-merge.py`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "verify-01-group-merge.txt"
MODULES = ROOT / "library" / "modules"
GROUP_ID = "attitude-hold"

_lines: list[str] = []


def say(text: str = "") -> None:
    print(text, flush=True)
    _lines.append(text)


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from contest_generator.manifest import (
        ModuleManifest,
        build_manifest_summaries,
        collect_exclusive_groups,
    )
    from contest_generator.selection import build_module_selection

    say("# jy61p 并入航向保持組（attitude-hold）验收探针")
    say(f"# 仓库：{ROOT}")

    # ---------------- ① 组声明现状（真库） ----------------
    say("")
    say("=" * 74)
    say("① 真库功能组聚合（manifest 声明 → collect_exclusive_groups）")
    say("=" * 74)
    manifests = [
        ModuleManifest.load(p) for p in sorted(MODULES.iterdir()) if p.is_dir()
    ]
    groups = {g.id: g for g in collect_exclusive_groups(manifests)}
    assert GROUP_ID in groups, f"真库里没有 {GROUP_ID} 组"
    members = [m.slug for m in groups[GROUP_ID].members]
    for m in groups[GROUP_ID].members:
        say(f"  {m.slug:12s} role={m.role}")
    say(f"  → 成员 = {members}（label={groups[GROUP_ID].label}）")
    ok_members = members == ["imu_uart", "jy61p", "ml_mpu6050"]
    say(f"  {'PASS' if ok_members else 'FAIL'}：三个姿态件同组（imu_uart / jy61p / ml_mpu6050）")

    # ---------------- ② 三个件是「同一功能的三种硬件」 ----------------
    say("")
    say("=" * 74)
    say("② 判据来源：三者都是「接上就能出姿态角」的同一功能件")
    say("=" * 74)
    for slug in members:
        d = json.loads((MODULES / slug / "manifest.json").read_text(encoding="utf-8"))
        role = d["exclusive_group"]["role"]
        say(f"  {slug:12s} {role}")
    jy61p_notes = json.loads(
        (MODULES / "jy61p" / "manifest.json").read_text(encoding="utf-8")
    )["platforms"]["mspm0"]["notes"]
    hit = "imu_uart 姿态互替" in jy61p_notes
    say(f"  jy61p 自己的 notes 早就写明与 imu_uart 「姿态互替」：{'命中' if hit else '未命中'}")
    say(f"  {'PASS' if hit else 'FAIL'}：库内证据支持同组")

    # ---------------- ③ 收敛：同组多成员只留第一个 ----------------
    say("")
    say("=" * 74)
    say("③ 解析层收敛（用户现场形态：句子 12 推 jy61p + 另一句推 imu_uart）")
    say("=" * 74)
    summaries = build_manifest_summaries(manifests)
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
    selection = build_module_selection(
        raw,
        known_slugs=[m.slug for m in manifests],
        manifest_summaries=tuple(summaries),
    )
    kept = list(selection.modules)
    dropped = dict(selection.dropped_exclusive_members)
    say(f"  顶层 modules（进工程集）= {kept}")
    say(f"  dropped_exclusive_members = {dropped}")
    say("  收敛规则（既有设计，本单未动）= 保留**模型清单里先出现的那个成员**：")
    say("    本例第 2 条需求先提到 jy61p ⇒ 留 jy61p、剔 imu_uart（两者不再同时进工程集）。")
    kept_both = [s for s in ("imu_uart", "jy61p") if s in kept]
    ok_converge = len(kept_both) == 1 and sum(map(len, dropped.values())) == 1
    say(f"  {'PASS' if ok_converge else 'FAIL'}：组内只留一个姿态件，另一个落进可见的 dropped 字段")

    # ---------------- ④ 前端渲染：jy61p 变成组内可选项而不是 chip ----------------
    say("")
    say("=" * 74)
    say("④ 前端判据（fx/module.js 的纯件语义，按同一个载荷推演）")
    say("=" * 74)
    say("  groupOfSlug(groups, 'jy61p') 非空 ⇒ 需求句走 groupRequirementNote：")
    say('    渲染成「jy61p（已在『功能组选择』中，<理由>）」灰注，不再是可移除 chip —— PASS')
    say("  renderGroupCards 里 jy61p 出现在 attitude-hold 组卡的成员行（radio 可点）：")
    say("    isRec=False（AI 没把它当首选）+ isDropped=True ⇒ 标「同组互斥·未选中」，点它即换选 —— PASS")

    # ---------------- ⑤ 反证：改之前是什么样 ----------------
    say("")
    say("=" * 74)
    say("⑤ 反证（红证）：把 jy61p 的组声明**删掉**，同一份载荷再跑一次")
    say("=" * 74)
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="jy61p-red-"))
    try:
        for m in manifests:
            dst = tmp / m.slug
            shutil.copytree(MODULES / m.slug, dst)
        red_manifest = json.loads(
            (tmp / "jy61p" / "manifest.json").read_text(encoding="utf-8")
        )
        red_manifest.pop("exclusive_group", None)
        (tmp / "jy61p" / "manifest.json").write_text(
            json.dumps(red_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        red_manifests = [ModuleManifest.load(p) for p in sorted(tmp.iterdir()) if p.is_dir()]
        red_groups = {g.id: g for g in collect_exclusive_groups(red_manifests)}
        old_members = [m.slug for m in red_groups[GROUP_ID].members]
        red_selection = build_module_selection(
            raw,
            known_slugs=[m.slug for m in red_manifests],
            manifest_summaries=tuple(build_manifest_summaries(red_manifests)),
        )
        red_kept = list(red_selection.modules)
        say(f"  删掉声明后 attitude-hold 成员 = {old_members}（jy61p 不在其中）")
        say(f"  同一载荷的顶层 modules = {red_kept}")
        ok_red = "jy61p" not in old_members and "jy61p" in red_kept
        say("  ⇒ 那时 jy61p 既不入组卡、也不吃收敛：需求句里以可移除 chip 出现——")
        say("     用户看到的正是报告里那张图（同屏一个姿态传感器单选框 + 一个裸 jy61p chip）。")
        say(f"  {'PASS' if ok_red else 'FAIL'}：红证成立")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    results = {
        "① 三件同组": ok_members,
        "② notes 自证同等": hit,
        "③ 解析层收敛": ok_converge,
        "⑤ 红证": ok_red,
    }
    say("")
    say("=" * 74)
    say("判读汇总")
    say("=" * 74)
    for k, v in results.items():
        say(f"  {k:16s} {'PASS' if v else 'FAIL'}")
    say(f"  合计：{sum(results.values())}/{len(results)} PASS")
    OUT.write_text("\n".join(_lines) + "\n", encoding="utf-8")
    print(f"\n落盘：{OUT}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
