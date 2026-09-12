"""功能组「未选」判据的跨语言镜像守卫（工单 group-choice-required/01 评审整改）。

为什么需要：同一条判据有两份实现——后端 `selection.missing_group_choices`（守住 CLI /
脚本 / 旧页面直打端点）与前端 `fx/module.js` 的 `pendingGroupChoices`（守住即时反馈：
点选、就绪检查单、拦截文案）。仓库既有先例是**跨语言镜像 + 守卫测试**
（`tests/test_library_invariants.py:619`：「JS 不能 import Python 枚举，故照跨语言常量镜像
先例…改任一侧此测试即红」）——判据不强行单源，但两份必须给出**同一结论**。

做法（场景表只有一份）：
  ① 本文件 = 场景表的**单一出处** `cases()`（组定义 / 平台 / group_choices / selected_slugs）；
  ② 用它断言后端判据，并把每个场景的期望结论写进 fixture
     `tests/js/group-choice-mirror.fixture.json`（由 `tools/gen_group_choice_mirror.py` 生成，
     生成时同样用 Python 现算，不手抄）；
  ③ JS 侧 `tests/js/group-choice-mirror.test.mjs` 读同一份 fixture，逐场景比对
     `pendingGroupChoices` 的结论 → **改一侧忘了另一侧，那条 JS 测试就红**。
"""

from __future__ import annotations

import json
from pathlib import Path

from contest_generator.manifest import ExclusiveGroup, ExclusiveGroupMember
from contest_generator.selection import missing_group_choices

FIXTURE = Path(__file__).resolve().parent / "js" / "group-choice-mirror.fixture.json"


def _group(
    group_id: str, label: str, members: list[tuple[str, tuple[str, ...]]]
) -> ExclusiveGroup:
    return ExclusiveGroup(
        id=group_id,
        label=label,
        members=tuple(
            ExclusiveGroupMember(slug=slug, role=f"{slug} 的差异定位", platforms=platforms)
            for slug, platforms in members
        ),
    )


def _att() -> ExclusiveGroup:
    return _group(
        "attitude-hold",
        "航向保持 / 姿态传感器",
        [
            ("imu_uart", ("mspm0",)),
            ("jy61p", ("mspm0",)),
            ("ml_mpu6050", ("mspm0", "stm32")),
        ],
    )


def _gray() -> ExclusiveGroup:
    return _group(
        "gray-track",
        "8 路灰度传感器驱动",
        [("huidu", ("mspm0",)), ("pid", ("mspm0",)), ("xunji", ("mspm0",))],
    )


def _single() -> ExclusiveGroup:
    return _group("lone", "单成员组", [("only", ("mspm0",))])


def cases() -> list[dict]:
    """跨语言共用的场景表（**单一出处**；JS 侧读由它导出的 fixture）。"""
    return [
        {"name": "未选：组在选中集里", "groups": [_att()], "platform": "mspm0",
         "choices": {}, "selected": ["imu_uart"]},
        {"name": "未选：组内非推荐成员在选中集里", "groups": [_att()], "platform": "mspm0",
         "choices": {}, "selected": ["pid", "jy61p"]},
        {"name": "已选合法成员", "groups": [_att()], "platform": "mspm0",
         "choices": {"attitude-hold": "imu_uart"}, "selected": ["imu_uart"]},
        {"name": "已选非推荐成员（换选）", "groups": [_att()], "platform": "mspm0",
         "choices": {"attitude-hold": "jy61p"}, "selected": ["imu_uart"]},
        {"name": "越界成员 = 没选", "groups": [_att()], "platform": "mspm0",
         "choices": {"attitude-hold": "motor"}, "selected": ["imu_uart"]},
        {"name": "空串值 = 没选", "groups": [_att()], "platform": "mspm0",
         "choices": {"attitude-hold": ""}, "selected": ["imu_uart"]},
        {"name": "组没进选中集（hint 卡形态）= 不拦", "groups": [_att()], "platform": "mspm0",
         "choices": {}, "selected": ["pid", "motor"]},
        {"name": "stm32 投影后单成员 = 不拦", "groups": [_att()], "platform": "stm32",
         "choices": {}, "selected": ["ml_mpu6050"]},
        {"name": "单成员组 = 不拦", "groups": [_single()], "platform": "mspm0",
         "choices": {}, "selected": ["only"]},
        {"name": "多组同时待选（库登记序）", "groups": [_gray(), _att()], "platform": "mspm0",
         "choices": {}, "selected": ["pid", "imu_uart"]},
        {"name": "多组：只选了其中一组", "groups": [_gray(), _att()], "platform": "mspm0",
         "choices": {"attitude-hold": "imu_uart"}, "selected": ["pid", "imu_uart"]},
        {"name": "无组定义（旧库 / 无组载荷）", "groups": [], "platform": "mspm0",
         "choices": {}, "selected": ["imu_uart"]},
        {"name": "用户把组内模块删掉后 = 不拦（前后端同口径）", "groups": [_att()],
         "platform": "mspm0", "choices": {}, "selected": ["pid"]},
    ]


def platform_view(group: ExclusiveGroup, platform: str) -> dict:
    """把组投影成前端载荷形态（members 只留该平台有条目的成员，与 collect 同口径）。"""
    return {
        "id": group.id,
        "label": group.label,
        "hint": False,
        "choice_required": True,
        "members": [
            {"slug": m.slug, "role": m.role}
            for m in group.members
            if platform in m.platforms
        ],
    }


def expected_pending(case: dict) -> list[str]:
    """后端判据在该场景下的结论（= fixture 里给前端比对的期望值）。"""
    return [
        g.id
        for g in missing_group_choices(
            tuple(case["groups"]), case["platform"], case["choices"], case["selected"]
        )
    ]


def mirror_payload() -> dict:
    return {
        "generated_by": "pytest/tools — 见 tests/test_group_choice_mirror.py 与 tools/gen_group_choice_mirror.py",
        "note": "期望值由 Python 判据 missing_group_choices 现算；JS 侧 pendingGroupChoices 必须一致",
        "cases": [
            {
                "name": case["name"],
                "platform": case["platform"],
                "choices": case["choices"],
                "selected": case["selected"],
                "groups": [platform_view(g, case["platform"]) for g in case["groups"]],
                "expected_pending": expected_pending(case),
            }
            for case in cases()
        ],
    }


def test_backend_predicate_on_mirror_scenarios():
    """后端判据在场景表上的结论（逐条钉住，兼作 fixture 的语义说明）。"""
    results = {case["name"]: expected_pending(case) for case in cases()}
    assert results["未选：组在选中集里"] == ["attitude-hold"]
    assert results["未选：组内非推荐成员在选中集里"] == ["attitude-hold"]
    assert results["已选合法成员"] == []
    assert results["已选非推荐成员（换选）"] == []
    assert results["越界成员 = 没选"] == ["attitude-hold"]
    assert results["空串值 = 没选"] == ["attitude-hold"]
    assert results["组没进选中集（hint 卡形态）= 不拦"] == []
    assert results["stm32 投影后单成员 = 不拦"] == []
    assert results["单成员组 = 不拦"] == []
    assert results["多组同时待选（库登记序）"] == ["gray-track", "attitude-hold"]
    assert results["多组：只选了其中一组"] == ["gray-track"]
    assert results["无组定义（旧库 / 无组载荷）"] == []
    assert results["用户把组内模块删掉后 = 不拦（前后端同口径）"] == []


def test_mirror_fixture_matches_backend_predicate():
    """fixture 必须与后端判据现算结果逐字一致。

    它**不自动重写**：漂移时这条测试红，操作者必须显式跑
    `python tools/gen_group_choice_mirror.py` 并看清 diff（改一侧是有意的还是漏了）。
    """
    assert FIXTURE.is_file(), (
        f"缺少跨语言镜像 fixture {FIXTURE}；跑 `python tools/gen_group_choice_mirror.py` 生成"
    )
    on_disk = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected = mirror_payload()
    assert on_disk["cases"] == expected["cases"], (
        "mirror fixture 与 Python 侧判据不一致（前端判据可能已漂移）："
        "跑 `python tools/gen_group_choice_mirror.py` 前先确认这次改动是有意的"
    )
