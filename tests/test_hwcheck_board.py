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
from contest_generator.hwcheck_board import (
    HwCheckBoardView,
    hwcheck_board_view,
    hwcheck_board_view_for,
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
        "rows", "groups", "board_shares", "order", "missing", "guide", "reason",
        "footnote",
    }
    assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload
    assert all(isinstance(row, dict) for row in payload["rows"])


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
