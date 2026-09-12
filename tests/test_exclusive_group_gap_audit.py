"""功能组缺口排查：真库四组「同类功能件同组」的结构守卫（工单 exclusive-group-gap-audit/01）。

背景（用户报告 → 全库排查）：`exclusive_group` 是模块级 manifest 声明，
没声明的模块既不出组卡、也不吃同组互斥收敛（`selection.converge_exclusive_group_selection`）
——同一功能的两件会**同时进工程集**。`jy61p` 那一例已由
`.scratch/attitude-group-jy61p/01` 修掉；本轮按同一形状全库排查，补四组。

本测试钉住的是**声明形状与库内事实**（不是实现细节）：
  * 组存在、label 逐字一致（同 id 不一致会在 collect 时抛 ManifestError）；
  * 成员清单与库登记序；
  * 每个成员都有 role（选择卡上给用户看「选它差在哪」）；
  * 每组在**每个平台**投影后 ≥2 成员（<2 则该平台不出卡，等于该平台漏保护）；
  * 组内成员确实互相不同框——用库内事实钉：两件在该平台**默认脚完全相同**
    （或 notes 明写「互替」），这正是母版「同选概率最低者重叠」的设计前提。

证据全文与逐条判定见 `.scratch/exclusive-group-gap-audit/audit.md`。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.manifest import (
    ModuleManifest,
    build_manifest_summaries,
    collect_exclusive_groups,
)
from contest_generator.selection import (
    _exclusive_group_members,
    converge_exclusive_group_selection,
)

MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"

# 组 id → (label, 成员清单按库登记序, [(自证方, notes 里的互替关键词, 同组他件在该片段里的写法)])
GROUPS: dict[str, tuple[str, list[str], list[tuple[str, str, str]]]] = {
    "display": (
        "显示 / 屏幕",
        ["ili9341", "ili9488", "lcd", "max7219", "oled", "st7789_para"],
        [
            ("lcd", "显示族互替", "max7219"),
            ("max7219", "显示族互替", "lcd"),
            ("ili9341", "互替同脚", "lcd"),
        ],
    ),
    "distance": (
        "距离测量 / 测距传感器",
        ["ir_distance", "sr04", "us016", "vl53l0x"],
        [
            ("us016", "互替件同脚", "ir_distance"),
            ("ir_distance", "互替件同脚", "us016"),
        ],
    ),
    "barometer": (
        "气压 / 海拔传感器",
        ["bmp180", "ms5611"],
        [
            ("bmp180", "互替不可同挂", "ms5611"),
            ("ms5611", "互替不可同挂", "bmp180"),
        ],
    ),
    "sound-prompt": (
        "提示输出 / 声",
        ["beep", "jq8900"],
        [("jq8900", "提示输出互替", "蜂鸣器")],
    ),
}


def _manifests() -> list[ModuleManifest]:
    return [
        ModuleManifest.load(path) for path in sorted(MODULES.iterdir()) if path.is_dir()
    ]


@pytest.mark.parametrize("group_id", sorted(GROUPS))
def test_group_declaration_shape_on_the_real_library(group_id: str) -> None:
    """四组各自：label 逐字 + 成员清单 + role 齐备 + 每平台投影 ≥2 成员。"""
    label, members, _ = GROUPS[group_id]
    manifests = _manifests()
    groups = {g.id: g for g in collect_exclusive_groups(manifests)}
    assert group_id in groups, f"真库里没有 {group_id} 组"
    group = groups[group_id]
    assert group.label == label
    assert [m.slug for m in group.members] == members
    roles = {m.slug: m.role for m in group.members}
    for slug in members:
        assert roles[slug], f"{slug} 缺 role（选择卡上要说清「选它差在哪」）"
    # 平台投影后 ≥2 成员：<2 该平台不出卡 = 该平台漏保护（beep 的 mspm0 条目是占位
    # 实现、pins 为空，但**条目在**，故 mspm0 侧 sound-prompt 仍是 2 成员）
    for platform in ("stm32", "mspm0"):
        projected = [
            g
            for g in collect_exclusive_groups(manifests, platform=platform)
            if g.id == group_id
        ]
        assert projected, f"{group_id} 在 {platform} 侧投影后 <2 成员（不出卡）"
        assert len(projected[0].members) >= 2


@pytest.mark.parametrize("group_id", sorted(GROUPS))
def test_group_members_self_evidence_in_notes(group_id: str) -> None:
    """组成员互替的**库内文字自证**在位（组不是凭感觉分的）。

    逐条证据 = (自证方, 关键词, 同组他件在该片段里的写法)：那条 manifest 的
    description + 两个平台 notes 里必须存在**含该关键词、且同段 200 字内提到
    同组他件**的片段——即「库自己说过这两件互替」。他件写法允许用硬件别名
    （beep 的角色名「BUZZER」/中文「蜂鸣器」，两件仍是明确的一对一）。
    """
    _, _, evidence = GROUPS[group_id]
    manifests = {m.slug: m for m in _manifests()}
    missing: list[str] = []
    for slug, keyword, other in evidence:
        manifest = manifests[slug]
        text = manifest.description + "\n" + "\n".join(
            entry.notes for entry in manifest.platforms.values()
        )
        found = False
        start = text.find(keyword)
        while start >= 0:
            window = text[max(0, start - 200) : start + 200]
            if other in window:
                found = True
                break
            start = text.find(keyword, start + 1)
        if not found:
            missing.append(f"{slug}（关键词 {keyword!r} × {other!r}）")
    assert not missing, (
        f"{group_id} 组的库内自证片段缺失：{missing}——分组必须有库内证据"
    )


def test_gap_groups_converge_on_one_payload() -> None:
    """同一份模型输出同时推荐同组两件 → 顶层只剩一件，另一件进 dropped。

    这是用户报告现场（「已选姿态传感器，需求句里又出现另一个姿态件」）的**判据**，
    对四组逐组验一遍：真库 manifest → `_exclusive_group_members` → 收敛函数。
    """
    manifests = _manifests()
    summaries = build_manifest_summaries(manifests)
    known = [m.slug for m in manifests]
    group_members = _exclusive_group_members(summaries, known)
    for group_id, (_, members, _) in GROUPS.items():
        assert group_id in group_members, f"{group_id} 没进收敛判据"
        assert set(members) <= set(group_members[group_id])
        kept, dropped = converge_exclusive_group_selection(list(members), group_members)
        assert kept == [members[0]], f"{group_id} 收敛后应只剩模型清单首个"
        assert dropped == {group_id: tuple(members[1:])}
