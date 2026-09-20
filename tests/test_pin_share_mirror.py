"""跨语言镜像：同脚多角色 共享/冲突 分类的场景表**单一出处**
（工单 cross-lang-mirror-c5a/02）。

为什么需要：同一条判据有两份实现——后端 `pin_bindings._shared_groups`（守 CLI /
脚本 / 旧页面直打端点 / 生成前门禁）与前端 `fx/generate.js` 的 `pinShareClass`
（守即时反馈：角色行黄字、板图点脚菜单）。仓库先例是**跨语言镜像 + 守卫**
（`tests/test_group_choice_mirror.py`：「判据不强行单源，但两份必须给出同一结论」）
——`tests/js/pin-share.test.mjs` 此前只断言前端自己写的期望值，两份实现一起漂也
全绿；本文件把结论交给后端现算，漂移就在闸门内变红。

做法（场景表只有一份）：
  ① 本文件 = 场景表的单一出处 `CASES`（平台 / 分类 / 真实库内 slug / 绑定）；
  ② 用它跑后端判据 `_shared_groups`，把每个场景的期望（脚、角色键、kind）写进
     fixture `tests/js/pin-share-mirror.fixture.json`（由
     `tools/gen_pin_share_mirror.py` 生成，生成时同样用 Python 现算，不手抄）；
  ③ JS 侧 `tests/js/pin-share-mirror.test.mjs` 读同一份 fixture，用同一个板定义
     + 实例映射构造角色对象，复算 `pinShareClass` 的结论后逐场景比对。

**只对账 kind**（`share` / `conflict` / `none`）：原因文案前端自有、后端那几句更
贴切（「同一 ADC 实例的通道」），文案不进对拍。

场景的「涉及哪些脚」**不手写**，由 `_role_entries` 的生效落点现推（`_case_pins`）：
手写会有个隐蔽陷阱——某场景声明 `pins: []` 时，两侧的期望都被过滤成空，
`sentinel == sentinel` 恒绿，等于这个场景根本没跑（评审实测抓到的正是这一条）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from unittest import mock

from contest_generator.boards import Board, board_for_platform
from contest_generator.manifest import ModuleManifest
from contest_generator.pin_bindings import _role_entries, _shared_groups
from contest_generator.syscfg_instances import INSTANCES_BY_SLUG

REPO_ROOT = Path(__file__).resolve().parents[1]
LIBRARY_MODULES = REPO_ROOT / "library" / "modules"
FIXTURE = Path(__file__).resolve().parent / "js" / "pin-share-mirror.fixture.json"

# 场景层可用的真实模块（按需加载；库内 slug 才是判据的事实源）。
_MANIFESTS = {
    slug: ModuleManifest.load(LIBRARY_MODULES / slug)
    for slug in (
        "adc",
        "us016",
        "mq2",
        "gp2y1014au",
        "zigbee_uart",
        "zigbee_uart_key",
        "zigbee_link",
        "as32",
        "ec01g",
        "uwb_uart",
        "ttp224",
        "key",
        "aht10",
        "bh1750",
        "config",
        "pid",
        "huidu",
        "xunji",
    )
}

# ---------------------------------------------------------------------------
# 场景表（**单一出处**）
#
# `category` = 这条场景要钉的分类（`share` / `conflict` / `none`），供
# `test_scenario_categories_cover_the_ticket_floor` 从表里现推覆盖、避免另写一份。
# `bindings` 只写把角色挪到一起所需的那几条（其余角色留在自己的默认脚上，
# 它们的组不落在本场景的脚里，故不影响期望）。
# ---------------------------------------------------------------------------

CASES: list[dict[str, Any]] = [
    {
        "name": "adc 共读同槽：adc + us016 默认同落 PA24（同一 ADC 实例）→ 共享",
        "platform": "mspm0",
        "category": "share",
        "slugs": ["adc", "us016"],
        "bindings": {},
    },
    {
        "name": "adc 共读同槽三件（adc + us016 + mq2）→ 共享",
        "platform": "mspm0",
        "category": "share",
        "slugs": ["adc", "us016", "mq2"],
        "bindings": {},
    },
    {
        "name": "uart 家族同实例：zigbee_uart + zigbee_link 共 PB10 → 共享",
        "platform": "stm32",
        "category": "share",
        "slugs": ["zigbee_uart", "zigbee_link"],
        "bindings": {},
    },
    {
        "name": "同实例跨家族：zigbee_uart + zigbee_uart_key + ec01g 共 PB10 → 共享",
        "platform": "stm32",
        "category": "share",
        "slugs": ["zigbee_uart", "zigbee_uart_key", "ec01g"],
        "bindings": {},
    },
    {
        "name": "I2C 总线多挂：aht10 + bh1750 共 PA6 → 共享",
        "platform": "stm32",
        "category": "share",
        "slugs": ["aht10", "bh1750"],
        "bindings": {},
    },
    {
        "name": "gpio 位操作同器件实例：huidu + pid + xunji 共 PA24 → 共享",
        "platform": "mspm0",
        "category": "share",
        "slugs": ["huidu", "pid", "xunji"],
        "bindings": {},
    },
    {
        "name": "混合同脚冲突（默认脚撞上）：灰度 D3 与 uwb_uart RX 同落 PA24 → 冲突",
        "platform": "mspm0",
        "category": "conflict",
        "slugs": ["pid", "uwb_uart"],
        "bindings": {},
    },
    {
        "name": "不同外设同脚（绑定撞上）：ttp224 输出绑到 zigbee TX 的 PA26 → 冲突",
        "platform": "mspm0",
        "category": "conflict",
        "slugs": ["ttp224", "zigbee_uart", "zigbee_uart_key"],
        "bindings": {"ttp224.TTP224_OUT3": "PA26"},
    },
    {
        "name": "跨类型同脚（绑定撞上）：gp2y1014au 模拟量绑到 as32 TX 的 PA26 → 冲突",
        "platform": "mspm0",
        "category": "conflict",
        "slugs": ["gp2y1014au", "as32"],
        "bindings": {"gp2y1014au.GP2Y1014_AO_CH0": "PA26"},
    },
    {
        "name": "跨类型同脚（绑定撞上）：key 输入绑到 zigbee TX 的 PB10 → 冲突",
        "platform": "stm32",
        "category": "conflict",
        "slugs": ["key", "zigbee_uart"],
        "bindings": {"key.KEY_START": "PB10"},
    },
    {
        "name": "同型实例交集为空（下发映射不含 gp2y1014au）→ 冲突，不是共享",
        "platform": "mspm0",
        "category": "conflict",
        "slugs": ["adc", "gp2y1014au"],
        "bindings": {"gp2y1014au.GP2Y1014_AO_CH0": "PA24"},
        # 库内 adc 家族全挂 ADC12_0，唯一有第二实例（GP2Y1014）的就是 gp2y1014au；
        # 故「交集为空」这一支只能把它的映射构造成不含 ADC12_0 才可达。
        # 钉的是后端 _role_resource_keys 那一行判据：交集为空 → 冲突（**不是**因为
        # 类型相同就放行）。前端同路取 instanceMap[slug]，两侧结论必须一致。
        "instance_override": {"gp2y1014au": ["GP2Y1014"]},
    },
    {
        "name": "无资源键类型同脚：config 的 DIP 输入与 pid 灰度输入共 PB12 → 冲突",
        "platform": "stm32",
        "category": "conflict",
        "slugs": ["config", "pid"],
        "bindings": {},
    },
    {
        "name": "两件 I2C 器件的 SCL/SDA 同落板外脚 PD0 → 两侧都不标注（不是「合法共享」）",
        "platform": "stm32",
        "category": "none",
        # 这条专钉前端的**板内门控**：I2C 角色走的是 `pinShareClass` 的
        # 「全 i2c → 直接判 share」快路（不看资源键），若没有板内门控，板外脚上的
        # 两个 i2c 角色会被说成「I2C 总线共享（协议允许）」——而后端对板外脚
        # 一个组都不报。资源键那条路本来就有各自的门控（板外脚能力取不到），
        # 所以只有 i2c 快路能暴露这处差异；`instance_override` 置空是为免本场景
        # 顺带撞上板内同脚组（那是上面那条场景的事）。
        "slugs": ["aht10", "bh1750"],
        "bindings": {
            "aht10.AHT10_SCL": "PD0",
            "bh1750.BH1750_SCL": "PD0",
            "aht10.AHT10_SDA": "PD1",
            "bh1750.BH1750_SDA": "PD1",
        },
        "instance_override": {"aht10": [], "bh1750": []},
    },
    {
        "name": "单角色（无可比对象）→ 不标注",
        "platform": "mspm0",
        "category": "none",
        "slugs": ["adc"],
        "bindings": {},
    },
]


# ---------------------------------------------------------------------------
# 判据装配：真实库内模块 + 真实板定义
# ---------------------------------------------------------------------------


def _manifests(slugs: Sequence[str]) -> list[ModuleManifest]:
    return [_MANIFESTS[slug] for slug in slugs]


def _board(platform: str) -> Board:
    return board_for_platform(platform)


def _entries(case: Mapping[str, Any]) -> list[tuple[str, str, Any, str]]:
    """场景的生效落点（角色键 / slug / 声明 / 生效脚）。"""
    return _role_entries(
        _manifests(case["slugs"]), case["platform"], case["bindings"]
    )


def _case_pins(case: Mapping[str, Any]) -> list[str]:
    """本场景涉及的全部生效脚（现推，不手写——手写漏一处就成空转场景）。"""
    return sorted({pin for _key, _slug, _decl, pin in _entries(case)})


def actual_groups(case: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    """后端判据在该场景下的结论，规范化成 [(脚, 角色键, kind)]（按脚/角色键排序）。

    规范化的键用**角色键**（`slug.role_id`）——前端构造的角色对象本就有 key，
    两侧无需各自发明命名。`instance_override` 在两侧必须**同样生效**（前端读
    fixture 的 `instances`，后端改写 `pin_bindings.INSTANCES_BY_SLUG`），否则这一
    行就成了「两侧输入不同」的假对拍。
    """
    override = case.get("instance_override") or {}
    with mock.patch.dict(INSTANCES_BY_SLUG, override):
        groups = _shared_groups(
            _manifests(case["slugs"]), case["platform"], _board(case["platform"]),
            case["bindings"],
        )
    return sorted(
        (str(group["pin"]), role, str(group["kind"]))
        for group in groups
        for role in group["roles"]
    )


def expected_groups(case: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    """期望结论 = 后端结论里**本场景生效脚**上的那些行。

    不在其列的同脚分组（库数据顺带撞上的）不参与对账；板外脚的组后端本来就不报
    （`expected` 为空），而它在 fixture 里仍有角色、前端仍会调用判据——那正是
    「板外脚不标注」这条要两侧对齐的地方。
    """
    wanted = set(_case_pins(case))
    return [row for row in actual_groups(case) if row[0] in wanted]


# ---------------------------------------------------------------------------
# fixture 载荷：两侧共用同一份输入（板定义 + 实例映射 + 角色对象）
# ---------------------------------------------------------------------------


def _roles_payload(case: Mapping[str, Any]) -> dict[str, list[dict[str, str]]]:
    """场景角色按生效脚分组（前端直接照它构造 `{key, slug, decl}` 对象）。"""
    grouped: dict[str, list[dict[str, str]]] = {}
    for key, slug, decl, pin in _entries(case):
        grouped.setdefault(pin, []).append(
            {"key": key, "slug": slug, "type": decl.type}
        )
    return {
        pin: sorted(roles, key=lambda r: str(r["key"]))
        for pin, roles in sorted(grouped.items())
    }


def _board_pins_payload(platform: str) -> dict[str, Any]:
    """该平台场景用到的板引脚（真实板定义的子集，按板定义顺序）。

    只含本平台场景真正落到的脚：整块板（几十行）塞进 fixture 会把 diff 噪音压过
    判据。**板外脚天然不在子集里**——这正是两侧判据要回答的那件事（板外脚不标注）。
    """
    board = _board(platform)
    wanted = {
        pin
        for case in CASES
        if case["platform"] == platform
        for pin in _case_pins(case)
    }
    return {
        "platform": board.platform,
        "pins": [
            {"name": pin.name, "capabilities": list(pin.capabilities)}
            for pin in board.pins
            if pin.name in wanted
        ],
    }


def _instance_map(case: Mapping[str, Any]) -> dict[str, list[str]]:
    """gpio / adc 资源键的实例映射（= 前端 `state.module_instances` 的来源）。

    默认取库内单源 `INSTANCES_BY_SLUG`；场景可用 `instance_override` 覆盖某几个
    slug 的映射——那是**给后端不可达分支造可达形态**的唯一手段（两侧读的是同一份
    fixture 输入，故对拍仍然成立）。
    """
    override = case.get("instance_override") or {}
    return {
        slug: list(override.get(slug) or INSTANCES_BY_SLUG[slug])
        for slug in case["slugs"]
        if slug in INSTANCES_BY_SLUG
    }


def _platforms_in_use() -> list[str]:
    """场景用到的平台（板定义按平台去重，避免同一根脚的能力表在每个场景重复）。"""
    return sorted({str(case["platform"]) for case in CASES})


def mirror_payload() -> dict[str, Any]:
    """完整 fixture 载荷（由 tools/gen_pin_share_mirror.py 写盘）。

    `boards` 按平台去重放顶层（同一根脚的十来个能力 token 不必在每个场景重复
    一遍——那是 diff 噪音，无关改动也会撞上它）；每个平台只带**本平台场景真落到
    的脚**。板外脚（`PD0` / `PD1`）天然不在任何板子集里，那正是两侧判据要回答的
    那件事（板外脚不标注）。
    """
    return {
        "generated_by": (
            "python tools/gen_pin_share_mirror.py —— 场景表在 "
            "tests/test_pin_share_mirror.py 的 CASES，期望值由后端 _shared_groups 现算"
        ),
        "note": (
            "期望值 [pin, role_key, kind] 由 Python 判据 _shared_groups 现算；"
            "JS 侧 pinShareClass 必须给出同一结论（只对账 kind，原因文案不进对拍）"
        ),
        "boards": {
            platform: _board_pins_payload(platform) for platform in _platforms_in_use()
        },
        "cases": [
            {
                "name": case["name"],
                "category": case["category"],
                "platform": case["platform"],
                "instances": _instance_map(case),
                "roles_by_pin": _roles_payload(case),
                "expected": [list(row) for row in expected_groups(case)],
            }
            for case in CASES
        ],
    }


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------


def test_scenario_categories_cover_the_ticket_floor():
    """场景表必须覆盖工单点名的分类，且每条场景的 category 与后端结论相符。

    `category` 是表里唯一的「期望分类」声明（两侧共用）；本用例把后端现算结果
    按 `category` 汇总对比——**不逐条手写 kind 期望**（那是把 fixture 的活重做一遍，
    库默认脚一变就要改两处）。
    """
    by_category: dict[str, set[str]] = {}
    for case in CASES:
        kinds = {kind for _pin, _role, kind in expected_groups(case)}
        expected_kinds = (
            {"none"} if case["category"] == "none" else {case["category"]}
        )
        assert kinds <= expected_kinds or kinds == expected_kinds, (
            f"场景「{case['name']}」声明 category={case['category']}，"
            f"后端结论却是 {sorted(kinds)}"
        )
        by_category.setdefault(case["category"], set()).update(kinds or {"none"})

    # 三类结论都必须在表里出现（只测 share 的镜像守不住冲突侧，反之亦然）
    assert set(by_category) == {"share", "conflict", "none"}
    assert by_category["share"] == {"share"}
    assert by_category["conflict"] == {"conflict"}
    assert by_category["none"] == {"none"}


def test_off_board_scenario_is_not_vacuous():
    """板外脚场景必须真的让两侧判据都跑起来（评审整改：此前 `pins: []` 空转）。

    这条直接钉住「期望为空」的**原因**：本场景确实有角色、确实落在板外的脚上，
    只是后端不报、前端也不标注——而不是「没有任何角色」这种恒等式的空转。
    """
    case = next(c for c in CASES if c["category"] == "none" and "板外脚" in c["name"])
    roles = _roles_payload(case)

    assert roles, "板外脚场景必须有角色（否则前端根本没机会调用判据）"
    board_pins = {pin["name"] for pin in _board_pins_payload(case["platform"])["pins"]}
    assert set(roles).isdisjoint(board_pins), "本场景的角色应全部落在板外的脚上"
    assert len(set(roles)) >= 2, "至少要两个脚，才谈得上「两侧都不标注」"
    assert expected_groups(case) == [], "后端对板外脚不报组"


def test_mirror_fixture_matches_backend_predicate():
    """fixture 必须与后端判据现算结果逐字一致。

    它**不自动重写**：漂移时这条红，操作者必须显式跑
    `python tools/gen_pin_share_mirror.py` 并看清 diff（改一侧是有意的还是漏了）。
    """
    assert FIXTURE.is_file(), (
        f"缺少跨语言镜像 fixture {FIXTURE}；跑 `python tools/gen_pin_share_mirror.py` 生成"
    )
    on_disk = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected = mirror_payload()
    assert on_disk["cases"] == expected["cases"], (
        "pin-share 镜像 fixture 与 Python 侧判据不一致（前端判据可能已漂移）："
        "跑 `python tools/gen_pin_share_mirror.py` 前先确认这次改动是有意的"
    )
    assert on_disk["generated_by"] == expected["generated_by"]
    assert on_disk["note"] == expected["note"]
