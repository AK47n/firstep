# -*- coding: utf-8 -*-
"""硬件检测页的板侧投影：接线行 / 同脚冲突 / 建议顺序（工单 module-hwcheck/03）。

**为什么这样测**：这一单的三块判据**一行都不新立**——接线行 = `wiring.wiring_rows`
（与工程 README「引脚接线表」同一推导 `readme._pin_row_items`）、共享/冲突 =
`pin_bindings._shared_groups`、建议顺序 = `readme.sort_verification_order`。
所以判据不是"文案像不像"，而是**同一输入下本模块的输出与那三处逐字段相等**：
两处各推一遍正是本单要防的坏法（页面上那几根线必须与工程 README 里那几根一模一样）。

**真库真板**：判据用的是 `library/modules` 与包内板定义——地猛星 MPU6050 的
I2C0 = PA0/PA1 与板载 LED 同脚这条暗雷只有在真数据上才会现形（假库造不出它）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.boards import board_for_platform
from contest_generator.hwcheck import HwCheckConfig, HwCheckError
from contest_generator.hwcheck_board import (
    HWCHECK_PIN_EXIT_MARKER,
    HwCheckBoardView,
    HwCheckView,
    hwcheck_board_view,
    hwcheck_board_view_for,
    hwcheck_pin_plan,
    hwcheck_view,
)
from contest_generator.library import list_modules
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.readme import (
    BRING_UP_SLUGS,
    PIN_TABLE_FOOTNOTE,
    VERIFICATION_GUIDE,
    parse_pin_table,
    render_readme,
    sort_verification_order,
)
from contest_generator.selection import resolve_dependencies
from contest_generator.wiring import wiring_rows

REPO = Path(__file__).resolve().parents[1]
LIBRARY = REPO / "library" / "modules"
MASTERS = REPO / "library" / "masters"


def _manifests(slugs: list[str]):
    by_slug = {m.slug: m for m in list_modules(LIBRARY)}
    return resolve_dependencies(slugs, by_slug)


def _view(platform: str, slugs: list[str], devices: list[str] | None = None):
    manifests = _manifests(slugs)
    return hwcheck_board_view(
        platform,
        manifests,
        board_for_platform(platform),
        devices=devices if devices is not None else (),
    )


# ---------------------------------------------------------------------------
# 接线行：与工程 README「引脚接线表」同一判据
# ---------------------------------------------------------------------------


def test_rows_match_the_readme_pin_table_cell_by_cell():
    """接线行与生成工程 README 的引脚接线表**逐格相等**（同一推导入参）。

    这是本单的票面硬要求（「同函数、同字段；不允许两处各推一遍」）的机器判据：
    左边 = 本模块给前端的行，右边 = README 渲染出来再解析回去的表——两条路
    若各推一遍，第一个字段就会分叉。
    """
    slugs = ["led", "delay", "debug_uart", "oled", "ml_mpu6050"]
    manifests = _manifests(slugs)
    readme = render_readme(
        PLATFORM_STM32, "STM32F103C8T6 最小系统板", manifests, module_library_dir=LIBRARY
    )
    table = parse_pin_table(readme)
    assert table, "README 里应有引脚接线表"

    view = hwcheck_board_view(
        PLATFORM_STM32, manifests, board_for_platform(PLATFORM_STM32)
    )
    core = ("slug", "role", "role_id", "role_label", "pin", "remark")
    assert [tuple(r[k] for k in core) for r in view.rows] == [
        tuple(r[k] for k in core) for r in table
    ]


def test_rows_are_the_wiring_snapshot_projection_verbatim():
    """行本体 = `wiring.wiring_rows` 的输出（接线快照同一函数），不得另写推导。"""
    manifests = _manifests(["led", "delay", "debug_uart", "ml_mpu6050"])
    view = hwcheck_board_view(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0)
    )
    expected = wiring_rows(PLATFORM_MSPM0, manifests)
    assert len(view.rows) == len(expected) > 0
    for got, want in zip(view.rows, expected):
        for key, value in want.items():
            assert got[key] == value, f"字段 {key} 与接线快照推导不一致"


def test_modules_without_declared_pins_produce_no_rows():
    """未声明引脚角色的模块不产生接线行（与 README 行为一致，不硬猜）。

    stm32 的 `led` / `delay` 就是这一形态——它们的实现内嵌母版，manifest 里
    没有 pins 声明；页面不得凭空给它们编一行出来。
    """
    view = _view(PLATFORM_STM32, ["led", "delay", "debug_uart", "ml_mpu6050"])
    assert view.rows, "串口与 MPU6050 应有接线行"
    assert all(row["slug"] not in ("led", "delay") for row in view.rows)


def test_mspm0_mpu6050_shows_the_onboard_led_share_on_pa0_pa1():
    """**地猛星 MPU6050 × 板载 LED 的默认脚重叠必须被如实呈现**（票面硬要求）。

    事实在板定义里（PA0/PA1 的 notes：板载 LED 共用，通信期间微闪）——页面
    把它挂在对应接线行上；这条暗雷不写出来，学生会以为"我什么都没接错，
    怎么灯在闪 / 怎么读到一半就断"。
    """
    view = _view(PLATFORM_MSPM0, ["led", "delay", "debug_uart", "ml_mpu6050"],
                 ["ml_mpu6050"])
    by_pin = {row["pin"]: row for row in view.rows}
    assert set(by_pin) >= {"PA0", "PA1"}
    for pin in ("PA0", "PA1"):
        assert "板载 LED 共用" in by_pin[pin]["pin_note"], by_pin[pin]


def test_pin_note_is_empty_where_the_board_says_nothing():
    """板上没注记的脚 = 空串（不许为了好看编一句）。"""
    view = _view(PLATFORM_MSPM0, ["led", "delay", "debug_uart", "ml_mpu6050"])
    led_row = [r for r in view.rows if r["slug"] == "led"]
    assert led_row and led_row[0]["pin"] == "PA15"
    assert led_row[0]["pin_note"] == ""


def test_board_shares_lift_the_onboard_led_overlap_out_of_the_rows():
    """板载共享单独成列（工单 03 评审整改）：`_shared_groups` 只看模块角色，
    看不见"板子本来就把 LED 接在 PA0/PA1 上"——只选 MPU6050 时同脚组是空的，
    冲突区若只说"没有共用同一个引脚"就是**假安心**。故板上注记归并成
    board_shares 一列：脚 + 注记 + 用到它的角色，页面据此单独列一条。
    """
    view = _view(PLATFORM_MSPM0, ["led", "delay", "debug_uart", "ml_mpu6050"],
                 ["ml_mpu6050"])
    assert view.groups == (), "模块之间确实没有同脚（板上共享不在这条判据里）"
    by_pin = {item["pin"]: item for item in view.board_shares}
    assert set(by_pin) == {"PA0", "PA1"}
    assert "板载 LED 共用" in by_pin["PA1"]["note"]
    assert by_pin["PA1"]["roles"] == ["ml_mpu6050.I2C_0_SCL"]
    assert by_pin["PA0"]["roles"] == ["ml_mpu6050.I2C_0_SDA"]


def test_board_shares_also_cover_the_stm32_onboard_leds_and_usb_pins():
    """stm32 侧同理，而且这条在真数据上更值钱：板载 LED（PC13）与 MPU6050 的
    默认脚 PA11/PA12（**USB D+/D-**）都带板上注记——学生照默认脚接线时会撞上
    "插了 USB 就没法用"这类板上事实，页面必须把它们列出来。"""
    view = _view(PLATFORM_STM32, ["led", "delay", "debug_uart", "ml_mpu6050"])
    by_pin = {item["pin"]: item for item in view.board_shares}
    assert set(by_pin) >= {"PC13", "PA11", "PA12"}
    assert "板载 LED 共用" in by_pin["PC13"]["note"]
    assert by_pin["PC13"]["roles"] == ["config.LED_RED"]
    assert "USB" in by_pin["PA11"]["note"]
    assert by_pin["PA11"]["roles"] == ["ml_mpu6050.MPU6050_SCL"]
    assert view.groups == (), "这些脚上只有一个模块角色，模块之间没有同脚"


def test_board_shares_are_empty_when_the_board_says_nothing():
    """板上没有共享注记 = 空列表（不是"没检查"）。"""
    view = _view(PLATFORM_MSPM0, ["led"], ["led"])
    assert [row["pin"] for row in view.rows] == ["PA15"]
    assert view.board_shares == ()


# ---------------------------------------------------------------------------
# 同脚冲突 / 合法共享：按既有分类规则
# ---------------------------------------------------------------------------


def test_same_i2c_bus_is_marked_as_legal_sharing():
    """同一 I2C 总线上的两件 = 合法共享（既有判据 kind=share），不误报 ⚠。"""
    view = _view(PLATFORM_STM32, ["led", "delay", "debug_uart", "hmc5883l", "qmc5883l"])
    shares = [g for g in view.groups if g["kind"] == "share"]
    assert [g["pin"] for g in shares] == ["PA6", "PA7"]
    assert "I2C" in shares[0]["reason"]


def test_same_pin_different_peripherals_is_a_conflict():
    """同脚分属不同外设 = 物理冲突（kind=conflict）——页面据此标 ⚠。

    mspm0 的默认两路输出通道就是活例子：调试串口 RX(PA22) 与 OLED 的
    SPI_RES(PA22) 在原厂默认布局里撞在一起（工单 02 的生成门禁会如实 400），
    现在这条在**生成之前**就能看见。
    """
    view = _view(PLATFORM_MSPM0, ["led", "delay", "debug_uart", "oled"])
    conflicts = [g for g in view.groups if g["kind"] == "conflict"]
    assert [g["pin"] for g in conflicts] == ["PA22"]
    group = conflicts[0]
    assert "debug_uart.DEBUG_UART_RX" in group["roles"]
    assert "oled.OLED_SPI_RES" in group["roles"]
    assert "不同外设" in group["reason"]


def test_groups_come_from_the_existing_classifier():
    """分组本体 = `pin_bindings._shared_groups` 的输出（不在此重判一遍）。"""
    from contest_generator.pin_bindings import _shared_groups

    manifests = _manifests(["led", "delay", "debug_uart", "oled"])
    board = board_for_platform(PLATFORM_MSPM0)
    view = hwcheck_board_view(PLATFORM_MSPM0, manifests, board)
    assert view.groups == _shared_groups(manifests, PLATFORM_MSPM0, board, {})


def test_no_shared_pins_means_no_groups_at_all():
    """没有同脚就没有组——空集不是"一条空警告"。"""
    view = _view(PLATFORM_MSPM0, ["led", "delay", "debug_uart", "ml_mpu6050"])
    assert view.groups == ()


# ---------------------------------------------------------------------------
# 建议顺序：复用既有 bring-up 顺序单源
# ---------------------------------------------------------------------------


def test_order_is_the_readme_verification_order():
    """顺序 = `readme.sort_verification_order` 的结果（同一排序，逐项相等）。"""
    manifests = _manifests(["led", "delay", "debug_uart", "ml_mpu6050"])
    view = hwcheck_board_view(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0)
    )
    assert [item["slug"] for item in view.order] == [
        m.slug for m in sort_verification_order(manifests)
    ]
    assert [item["description"] for item in view.order] == [
        m.description for m in sort_verification_order(manifests)
    ]


def test_order_tags_the_bring_up_modules_from_the_shared_vocabulary():
    """「先做这些」的标记来自 `readme.BRING_UP_SLUGS`（单源），不另立清单。"""
    manifests = _manifests(["led", "delay", "debug_uart", "ml_mpu6050"])
    view = hwcheck_board_view(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0)
    )
    flags = {item["slug"]: item["bring_up"] for item in view.order}
    assert flags == {m.slug: m.slug in BRING_UP_SLUGS for m in manifests}
    assert flags["delay"] and flags["debug_uart"] and flags["led"]
    assert not flags["ml_mpu6050"], "器件不是 bring-up 模块"
    # bring-up 一律排在器件前面（这就是"先确认板子活着"那句的机器判据）
    slugs = [item["slug"] for item in view.order]
    assert slugs.index("ml_mpu6050") > max(
        slugs.index(s) for s in slugs if flags[s]
    )


def test_order_carries_the_shared_guide_text_and_its_reason():
    """顺序的引导语与尾注都是既有单源原文；「为什么是这个次序」是页面自己那句。"""
    view = _view(PLATFORM_MSPM0, ["led", "delay", "debug_uart", "ml_mpu6050"])
    assert view.guide == VERIFICATION_GUIDE
    assert view.footnote == PIN_TABLE_FOOTNOTE
    assert "板子活着" in view.reason and "依赖" in view.reason


# ---------------------------------------------------------------------------
# 本平台没有条目的器件：明确提示，不静默省略
# ---------------------------------------------------------------------------


def test_device_without_a_platform_entry_is_reported_not_silently_dropped():
    """选了本平台没有条目的件 → 明确点名"无法检测"（票面硬要求）。

    `sr04` 只有 mspm0 条目：在 stm32 上选它必须被点名，而不是悄悄从接线表 /
    顺序里消失（那会让学生以为"选上了、待会儿就能测"）。
    """
    view = _view(PLATFORM_STM32, ["led", "delay", "debug_uart", "sr04"], ["sr04"])
    assert [item["slug"] for item in view.missing] == ["sr04"]
    message = view.missing[0]["message"]
    assert "sr04" in message
    assert "无本平台版本" in message
    assert "无法检测" in message


def test_missing_judgement_comes_from_the_platform_warning_table():
    """缺条目的判据走 `selection.check_platform_warnings`（与生成侧同一处）。"""
    from contest_generator.selection import WARNING_MISSING, check_platform_warnings

    manifests = _manifests(["led", "delay", "debug_uart", "sr04"])
    by_slug = {m.slug: m for m in manifests}
    expected = [
        w.slug
        for w in check_platform_warnings(
            [m.slug for m in manifests], PLATFORM_STM32, by_slug
        )
        if w.kind == WARNING_MISSING
    ]
    view = hwcheck_board_view(
        PLATFORM_STM32,
        manifests,
        board_for_platform(PLATFORM_STM32),
        devices=["sr04"],
    )
    assert [item["slug"] for item in view.missing] == expected == ["sr04"]


def test_no_missing_entry_means_empty_list():
    """两平台都有条目 = 空列表（空列表不是"没检查"）。"""
    view = _view(PLATFORM_MSPM0, ["led", "delay", "debug_uart", "sr04"], ["sr04"])
    assert view.missing == ()


# ---------------------------------------------------------------------------
# 装配入口与形状
# ---------------------------------------------------------------------------


def test_view_for_reads_the_real_library_and_board():
    """`hwcheck_board_view_for`：给库根 + 平台 + 模块集 → 同一份视图（路由用）。"""
    view = hwcheck_board_view_for(
        LIBRARY, PLATFORM_MSPM0, ["led", "delay", "debug_uart", "ml_mpu6050"],
        devices=["ml_mpu6050"],
    )
    same = hwcheck_board_view(
        PLATFORM_MSPM0,
        _manifests(["led", "delay", "debug_uart", "ml_mpu6050"]),
        board_for_platform(PLATFORM_MSPM0),
        devices=["ml_mpu6050"],
    )
    assert view.to_dict() == same.to_dict()


def test_view_for_rejects_a_slug_that_is_not_in_the_library():
    """库外 slug = 大声失败（未知模块异常已登记 400），不许静默当空。"""
    from contest_generator.selection import UnknownModuleError

    with pytest.raises(UnknownModuleError):
        hwcheck_board_view_for(LIBRARY, PLATFORM_MSPM0, ["led", "nope-不存在"])


def test_view_for_rejects_an_unknown_platform_with_the_shared_message():
    """平台词表外 = 与 HwCheckConfig 同一句 400 中文（require_known_platform 单源）。"""
    from contest_generator.hwcheck import HwCheckError

    with pytest.raises(HwCheckError) as excinfo:
        hwcheck_board_view_for(LIBRARY, "arduino", ["led"])
    assert "arduino" in str(excinfo.value)
    assert PLATFORM_MSPM0 in str(excinfo.value)


def test_payload_is_plain_json_shapes():
    """载荷是纯 JSON 形状（前端只渲染：没有 dataclass / Path / set 漏进去）。"""
    import json

    payload = _view(PLATFORM_MSPM0, ["led", "delay", "debug_uart", "ml_mpu6050"],
                    ["ml_mpu6050"]).to_dict()
    assert set(payload) == {
        "rows", "groups", "board_shares", "order", "missing", "pin_fixes",
        "guide", "reason", "footnote",
    }
    assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload
    assert all(isinstance(row, dict) for row in payload["rows"])
    assert isinstance(payload["pin_fixes"], list)


# ---------------------------------------------------------------------------
# 引脚消解（工单 hwcheck-pin-conflict-exit/01）：检测页没有引脚配置入口，
# 默认脚撞脚必须在生成前自己解开——判据与赛题页「自动配置」/ 落盘冲突门禁同源。
# ---------------------------------------------------------------------------


def _master_syscfg() -> str:
    return (MASTERS / "mspm0" / "mspm0.syscfg").read_text(
        encoding="utf-8", errors="replace"
    )


def test_pin_plan_resolves_default_channel_conflict():
    """默认双通道（oled RES × debug_uart RX 撞 PA22）→ 自动让位，页面拿得到说明行。"""
    manifests = _manifests(["led", "delay", "debug_uart", "oled"])
    plan = hwcheck_pin_plan(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0),
        _master_syscfg(),
    )
    assert plan.ok
    assert plan.bindings, "默认双通道必然要移一根（PA22）"
    assert any("PA22" in line for line in plan.fixed)
    assert {b.role_key for b in plan.resolved} == set(plan.bindings)


def test_pin_plan_view_follows_resolved_pins_not_defaults():
    """接线表 / 同脚组按**消解后**的脚渲染：学生照页面接线必须与工程 README 一致。"""
    manifests = _manifests(["led", "delay", "debug_uart", "oled"])
    board = board_for_platform(PLATFORM_MSPM0)
    plan = hwcheck_pin_plan(PLATFORM_MSPM0, manifests, board, _master_syscfg())
    view = hwcheck_board_view(
        PLATFORM_MSPM0, manifests, board,
        resolved_bindings=plan.resolved, pin_fixes=plan.fixed,
    )
    moved = {b.role_key: b.pin for b in plan.resolved}
    rows = {f"{row['slug']}.{row['role_id']}": row["pin"] for row in view.rows}
    for key, pin in moved.items():
        assert rows[key] == pin, "接线表里的脚必须是移过之后的脚"
    # 求解器说明行原样在；新脚若带板载注记，还会多一句注记（两种都给页面）
    assert list(view.pin_fixes)[: len(plan.fixed)] == list(plan.fixed)
    assert all(fix in view.pin_fixes for fix in plan.fixed)
    assert all(
        group["kind"] != "conflict" for group in view.groups
    ), "移开之后页面不该再显示这条冲突"


def test_pin_plan_stm32_untouched():
    """stm32 不自动搬（默认重叠按 ADR 0010 是提示语义）：空计划、零绑定。"""
    manifests = _manifests(["led", "delay", "debug_uart", "oled"])
    plan = hwcheck_pin_plan(
        PLATFORM_STM32, manifests, board_for_platform(PLATFORM_STM32), None
    )
    assert plan.ok
    assert plan.bindings == {} and plan.resolved == () and plan.fixed == ()


def test_pin_plan_unsolvable_gets_page_actionable_message():
    """装不下 → 文案给检测页做得到的出路（探针按 `HWCHECK_PIN_EXIT_MARKER` 认它）。"""
    slugs = [
        "led", "oled", "debug_uart", "key", "beep", "sr04", "jy61p", "xunji",
        "ml_mpu6050",
    ]
    manifests = _manifests(slugs)
    plan = hwcheck_pin_plan(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0),
        _master_syscfg(),
    )
    assert not plan.ok
    assert HWCHECK_PIN_EXIT_MARKER in plan.conflict
    assert "只勾一个输出通道" in plan.conflict, "三条出路都要在"
    assert "引脚配置里改绑上述角色" not in plan.conflict, (
        "赛题页那句出路（不可执行）不许原样带过来"
    )
    # 断言冲突清单逐脚在（页面要能点名是哪些脚）
    assert "·" in plan.conflict


def test_pin_plan_without_master_syscfg_only_resolves_bindings():
    """母版 syscfg 读不到 = 判不了就不判：只做自动解冲突，不编「装得下」的结论。"""
    manifests = _manifests(["led", "delay", "debug_uart", "oled"])
    plan = hwcheck_pin_plan(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0), None
    )
    assert plan.ok and plan.bindings


def test_view_is_deterministic_and_frozen():
    """同输入两次调用逐字段相等；视图对象不可变（投影不该被就地改）。"""
    first = hwcheck_board_view_for(
        LIBRARY, PLATFORM_STM32, ["led", "delay", "debug_uart", "oled"]
    )
    second = hwcheck_board_view_for(
        LIBRARY, PLATFORM_STM32, ["led", "delay", "debug_uart", "oled"]
    )
    assert first.to_dict() == second.to_dict()
    assert isinstance(first, HwCheckBoardView)
    with pytest.raises(Exception):
        first.rows = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 检测页一次投影归位（工单 webapp-consolidation/01）：`hwcheck_view` 原先住在
# webapp.create_app 里，只能经 TestClient 端到端测；现在吃显式路径 / 配置对象，
# 可以直接按"输入 → 载荷"断言。下面这几条就是那条新缝。
# ---------------------------------------------------------------------------


def _page_view(
    platform: str,
    *,
    devices: list[str],
    debug_uart: bool = True,
    oled: bool = True,
    recipe_path=None,
    require_pins: bool = True,
):
    """直调域层装配（不经 HTTP）：库根 / 母版根都是本仓真库。"""
    return hwcheck_view(
        HwCheckConfig(
            platform=platform,
            debug_uart=debug_uart,
            oled=oled,
            devices=tuple(devices),
        ),
        module_library_dir=LIBRARY,
        masters_dir=MASTERS,
        recipe_path=recipe_path,
        require_pins=require_pins,
    )


def test_hwcheck_view_projects_the_page_payload_without_http():
    """真库真母版：一次投影的字段与载荷键齐全（判据不再只能经端点验）。"""
    view = _page_view(PLATFORM_STM32, devices=["ml_mpu6050"])
    assert isinstance(view, HwCheckView)
    assert set(view.board) == {
        "wiring", "sections", "console", "unspecialized", "exclusive_groups",
        "custom",
    }, "载荷键是前端契约（多一个少一个都是破坏）"
    assert "pin_fixes" in view.board["wiring"], (
        "「动了哪几根线」住在 wiring 里（前端读的也是 wiring.pin_fixes）"
    )
    assert [section.slug for section in view.sections] == ["ml_mpu6050"], (
        "专精小节按配方出，且与板侧视图同一份选中集"
    )
    assert [row["slug"] for row in view.board["wiring"]["rows"]], "接线行不为空"
    # sections / generic 是域对象（生成端点拿它们去渲染 main.c，不必再解析一遍）
    assert view.sections and all(hasattr(section, "slug") for section in view.sections)
    assert all(hasattr(section, "slug") for section in view.generic)
    # 自建件小节（工单 03）：没给 data_dir = 这一趟没有自建件（旧调用方零变化）
    assert view.custom == () and view.board["custom"] == []
    # 整库 slug 词表：排障的事实约束用（不进任何载荷）
    assert "ml_mpu6050" in view.known_slugs and "led" in view.known_slugs
    assert "known_slugs" not in view.board


def test_hwcheck_view_require_pins_false_skips_the_capacity_verdict():
    """装不下（地猛星全选 9 件）→ require_pins=True 大声失败、False 照常投影。

    回读端点用 False（那次检测已经生成成功）；预览 / 生成用 True（同一判据）。
    """
    devices = ["led", "oled", "debug_uart", "key", "beep", "sr04", "jy61p",
               "xunji", "ml_mpu6050"]
    with pytest.raises(HwCheckError) as excinfo:
        _page_view(PLATFORM_MSPM0, devices=devices)
    assert HWCHECK_PIN_EXIT_MARKER in str(excinfo.value), "失败时要给页面出路"
    view = _page_view(PLATFORM_MSPM0, devices=devices, require_pins=False)
    assert view.board["wiring"]["rows"], "回读照旧给出接线表"


def test_hwcheck_view_reads_the_recipe_override_path(tmp_path):
    """`recipe_path` 是显式入参（原先走 AppContext 覆盖）：坏配方仍大声失败。"""
    broken = tmp_path / "hwcheck_recipes.json"
    broken.write_text("{ 这不是 JSON }", encoding="utf-8")
    with pytest.raises(HwCheckError) as excinfo:
        _page_view(PLATFORM_STM32, devices=[], recipe_path=broken)
    assert "不是合法 JSON" in str(excinfo.value)
    # 缺省（库内那份）= 正常装载：响应里照旧有那几个键
    assert set(_page_view(PLATFORM_STM32, devices=[]).board) == {
        "wiring", "sections", "console", "unspecialized", "exclusive_groups",
        "custom",
    }


def test_hwcheck_view_rejects_a_slug_outside_the_library():
    """库外 slug 由依赖展开大声失败（域错误 → 400）——新缝上也要有这条判据。"""
    from contest_generator.selection import UnknownModuleError

    with pytest.raises(UnknownModuleError) as excinfo:
        _page_view(PLATFORM_STM32, devices=["not_in_library"])
    assert "not_in_library" in str(excinfo.value)
