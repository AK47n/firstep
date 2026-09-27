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

import json
import re
from pathlib import Path

import pytest

from contest_generator.boards import board_for_platform
from contest_generator.hwcheck import (
    HWCHECK_CHANNEL_LABELS,
    HWCHECK_CHANNEL_SECTION,
    HWCHECK_DEVICE_SECTION,
    HwCheckConfig,
    HwCheckError,
)
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


def test_board_payload_carries_the_console_capacity_note_key():
    """载荷里必须有 `console_note`，且平时是**空串**（工单 hwcheck-hardening/05）。

    为什么单独立一条：前端靠这个键渲染"复测字符快用完了"那句，**缺键时前端会静默退化成
    永远不提示**——那正是这一单要消灭的"只有按了生成才吃 400"。键名是跨语言契约。

    两条腿：① 键在（契约）；② 常见小组合下是空串（平时不许常驻一句警告）。
    """
    view = _page_view(PLATFORM_STM32, devices=["ml_mpu6050"])
    assert "console_note" in view.board, "board 载荷缺 console_note（前端会永远不提示）"
    assert isinstance(view.board["console_note"], str)
    assert view.board["console_note"] == "", "只勾一件时不该挂一句「字符快用完了」"


def _config(
    platform: str = PLATFORM_MSPM0,
    *,
    devices: tuple[str, ...] = (),
    debug_uart: bool = True,
    oled: bool = True,
) -> HwCheckConfig:
    """页面上那一趟选择（通道勾选框 + 器件清单）——出口文案点名哪个控件由它判。

    出口文案说的是"这一页上做得到的动作"，所以判据必须吃**与页面同一份配置**：
    只给 manifests 是造不出"这个实例属于哪个勾选框"的（同一个 oled 模块，勾着
    通道时它是通道，只从器件列表里选时它是器件）。
    """
    return HwCheckConfig(
        platform=platform, debug_uart=debug_uart, oled=oled, devices=devices
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
        "capacity_note", "guide", "reason", "footnote",
    }
    assert json.loads(json.dumps(payload, ensure_ascii=False)) == payload
    assert all(isinstance(row, dict) for row in payload["rows"])
    assert isinstance(payload["pin_fixes"], list)
    assert isinstance(payload["capacity_note"], str)


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
        _master_syscfg(), _config(),
    )
    assert plan.ok
    assert plan.bindings, "默认双通道必然要移一根（PA22）"
    assert any("PA22" in line for line in plan.fixed)
    assert {b.role_key for b in plan.resolved} == set(plan.bindings)


def test_pin_plan_view_follows_resolved_pins_not_defaults():
    """接线表 / 同脚组按**消解后**的脚渲染：学生照页面接线必须与工程 README 一致。"""
    manifests = _manifests(["led", "delay", "debug_uart", "oled"])
    board = board_for_platform(PLATFORM_MSPM0)
    plan = hwcheck_pin_plan(
        PLATFORM_MSPM0, manifests, board, _master_syscfg(), _config()
    )
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
        PLATFORM_STM32, manifests, board_for_platform(PLATFORM_STM32), None,
        _config(PLATFORM_STM32),
    )
    assert plan.ok
    assert plan.bindings == {} and plan.resolved == () and plan.fixed == ()


# ---------------------------------------------------------------------------
# 「判不了」不许伪装成「判过了」（工单 hwcheck-hygiene/04）
#
# 两种语义完全不同的情况在旧实现里被抹平成同一个 None：**母版没导入**（平台本来就
# 不可用，页面有状态可依）与**母版在、读不出来**（占用 / 权限 / IO = 失败）。
# 后者静默降级 ⇒ 容量判定整段跳过 ⇒ 预览放行、点「生成」才 400，学生看不到任何理由。
# ---------------------------------------------------------------------------


def test_master_syscfg_missing_is_none_but_unreadable_is_loud(tmp_path, monkeypatch):
    """没导入 = None（判不了就不判）；**存在但读不出来 = 大声 400 中文**。"""
    from contest_generator.hwcheck_board import read_master_syscfg

    masters = tmp_path / "masters"
    (masters / "mspm0").mkdir(parents=True)
    syscfg = masters / "mspm0" / "mspm0.syscfg"

    # ① 没导入：文件不在 → None（平台不可用是页面已有的状态，不是失败）
    assert read_master_syscfg(masters, PLATFORM_MSPM0) is None

    # ② 文件在、读不出来：占用 / 权限 / IO → 中文 400，不许返回 None
    syscfg.write_text("// 母版\n", encoding="utf-8")
    real_read_text = Path.read_text

    def boom(self, *args, **kwargs):
        if self.name == syscfg.name:
            raise PermissionError(13, "另一个程序正在使用此文件，进程无法访问。")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom)
    with pytest.raises(HwCheckError) as excinfo:
        read_master_syscfg(masters, PLATFORM_MSPM0)
    message = str(excinfo.value)
    assert "读不出来" in message, f"没说是「读不出来」：{message}"
    assert "占用" in message or "权限" in message, f"没给下一步（占用 / 权限）：{message}"
    assert syscfg.name in message, "没点名是哪个文件"


def test_missing_master_syscfg_skips_capacity_but_says_so():
    """母版没导入 → 容量判定跳过，但**不无声**：计划里带一句人话。"""
    manifests = _manifests(["led", "delay", "debug_uart", "oled"])
    plan = hwcheck_pin_plan(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0), None, _config()
    )
    assert plan.ok
    assert plan.capacity_note, "跳过容量判定却不吭声 = 把「判不了」伪装成「判过了」"
    assert "没判" in plan.capacity_note or "判不了" in plan.capacity_note


def test_capacity_note_is_empty_when_the_check_really_ran():
    """真判过（母版在）就不能挂那句"没判"——否则页面会为一趟正常的检查报警。"""
    manifests = _manifests(["led", "delay", "debug_uart", "oled"])
    plan = hwcheck_pin_plan(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0),
        _master_syscfg(), _config(),
    )
    assert plan.ok and plan.capacity_note == ""
    # stm32 压根不做这一步（不是"跳过了"）——同样不挂
    stm32 = hwcheck_pin_plan(
        PLATFORM_STM32, manifests, board_for_platform(PLATFORM_STM32), None,
        _config(PLATFORM_STM32),
    )
    assert stm32.capacity_note == ""


def test_view_payload_discloses_the_skipped_capacity_check(tmp_path):
    """页面上看得见：跳过容量判定那句话进 `wiring` 载荷（前端只渲染不判）。"""
    from contest_generator.hwcheck_board import hwcheck_view

    view = hwcheck_view(
        _config(),
        module_library_dir=LIBRARY,
        masters_dir=tmp_path / "还没导入母版",
    )
    wiring = view.board["wiring"]
    assert wiring["capacity_note"], "载荷里没有这句话 —— 页面上就看不出来"
    assert "没判" in wiring["capacity_note"]


def test_page_facing_copy_carries_no_markdown_markers(tmp_path, monkeypatch):
    """**页面上要显示的**域层文案不许带 markdown 标记（工单 hwcheck-hygiene/02 的口径）。

    为什么单独一条：那条守卫（`tests/js/bold-marker-guard.test.mjs` 判据 ⑨）的面只切
    `static/js/{fx,ui}/**`——**管不到域层的 Python 文案**，而这些文案经前端 `esc()`
    直接进 innerHTML（本单新增的 `capacity_note` 就是这一路；评审当场抓到过一笔）。
    所以这里把本单碰过的四处页面文案一起钉住。
    """
    from contest_generator.hwcheck_board import (
        PIN_CAPACITY_SKIPPED_NOTE,
        PIN_CAPACITY_UNREADABLE_NOTE,
    )
    from contest_generator.hwcheck_triage import HWCHECK_RECORD_FILENAME, read_hwcheck_record

    page_copy = {
        "PIN_CAPACITY_SKIPPED_NOTE": PIN_CAPACITY_SKIPPED_NOTE,
        "PIN_CAPACITY_UNREADABLE_NOTE": PIN_CAPACITY_UNREADABLE_NOTE,
    }
    # 「装不下」那份 400 文案的两支（工单 08 复量时抓到：重名那一支的两处标记还留着
    # ——这条注释当时写着"全靠注释与评审盯住"，评审确实盯住了，但注释不是判据）
    from contest_generator.hwcheck_board import hwcheck_pin_message
    from contest_generator.syscfg_prune import SyscfgPinConflictReport

    same_pin = SyscfgPinConflictReport(
        lines=("  · PA7：oled(SPI_CLK) 与 jy61p(JY61P) 都要用",),
        capacity="", name_lines=(),
        pin_instances=("OLED_SPI", "JY61P"),
    )
    same_name = SyscfgPinConflictReport(
        lines=(), capacity="",
        name_lines=("  · SCL：oled(SCL) 与 aht10(SCL)",),
        name_instances=("OLED_SPI", "AHT10"),
    )
    page_copy["引脚撞脚（同脚那支）"] = hwcheck_pin_message(same_pin, "地猛星 MSPM0G3507", _config())
    page_copy["引脚撞脚（重名那支）"] = hwcheck_pin_message(
        same_name, "地猛星 MSPM0G3507", _config())
    # 「这一趟不能交互式复测」那句（命令表提示，页面上原样显示）
    from contest_generator.hwcheck_console import CONSOLE_HINT_NONE

    page_copy["CONSOLE_HINT_NONE"] = CONSOLE_HINT_NONE
    # 母版配置读不出来那句（页面上原样显示）
    masters = tmp_path / "masters"
    (masters / "mspm0").mkdir(parents=True)
    (masters / "mspm0" / "mspm0.syscfg").write_text("// 母版\n", encoding="utf-8")
    real_read_text = Path.read_text

    def boom_syscfg(self, *args, **kwargs):
        if self.name == "mspm0.syscfg":
            raise PermissionError(13, "另一个程序正在使用此文件，进程无法访问。")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom_syscfg)
    with pytest.raises(HwCheckError) as syscfg_error:
        hwcheck_view(_config(), module_library_dir=LIBRARY, masters_dir=masters)
    page_copy["母版配置读不出来"] = str(syscfg_error.value)

    # 记录读不出来那句
    (tmp_path / HWCHECK_RECORD_FILENAME).write_text("{}", encoding="utf-8")

    def boom_record(self, *args, **kwargs):
        if self.name == HWCHECK_RECORD_FILENAME:
            raise PermissionError(13, "另一个程序正在使用此文件，进程无法访问。")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom_record)
    with pytest.raises(HwCheckError) as record_error:
        read_hwcheck_record(tmp_path)
    page_copy["记录读不出来"] = str(record_error.value)

    bad = {name: text for name, text in page_copy.items() if "**" in text}
    assert bad == {}, (
        "这些页面文案里带着 markdown 粗体标记 —— 到了页面上就是两个字面星号"
        f"（判据 ⑨ 的面只切 static/js，管不到这里）：{bad}"
    )


def test_readback_still_opens_when_the_master_syscfg_is_locked(tmp_path, monkeypatch):
    """回读 / 排障（`require_pins=False`）不因为母版被占用就打不开工程（工单 04）。

    这两条路回放的是**已经生成成功的那一次**，容量早就判过了：读不出来按"判不了就不判"
    走，但**照样把那句原因带给页面**（跳过不无声）。预览 / 生成（`require_pins=True`）
    才是"当场 400"的那条路。
    """
    from contest_generator.hwcheck_board import hwcheck_view

    masters = tmp_path / "masters"
    (masters / "mspm0").mkdir(parents=True)
    (masters / "mspm0" / "mspm0.syscfg").write_text("// 母版\n", encoding="utf-8")
    real_read_text = Path.read_text

    def boom(self, *args, **kwargs):
        if self.name == "mspm0.syscfg":
            raise PermissionError(13, "另一个程序正在使用此文件，进程无法访问。")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom)
    view = hwcheck_view(
        _config(), module_library_dir=LIBRARY, masters_dir=masters, require_pins=False
    )
    note = view.board["wiring"]["capacity_note"]
    assert "读不出来" in note, f"回读路径跳过了容量判定却不说原因：{note!r}"
    # 同一条路在"要判容量"的那一侧（预览 / 生成）必须 400
    with pytest.raises(HwCheckError) as excinfo:
        hwcheck_view(_config(), module_library_dir=LIBRARY, masters_dir=masters)
    assert "读不出来" in str(excinfo.value)


def test_pin_plan_unsolvable_gets_page_actionable_message():
    """装不下 → 文案给检测页做得到的出路（探针按 `HWCHECK_PIN_EXIT_MARKER` 认它）。

    这一组（地猛星 + 默认双通道 + 6 件器件）撞脚的两侧既有通道模块（oled /
    debug_uart）也有器件，所以出路里两个控件都要点名——且都必须带**这一页的
    栏位名**（`HWCHECK_CHANNEL_SECTION` / `HWCHECK_DEVICE_SECTION`，与
    index.html 的 <h3> 对过账）。
    """
    slugs = [
        "led", "oled", "debug_uart", "key", "beep", "sr04", "jy61p", "xunji",
        "ml_mpu6050",
    ]
    devices = ("key", "beep", "sr04", "jy61p", "xunji", "ml_mpu6050")
    manifests = _manifests(slugs)
    plan = hwcheck_pin_plan(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0),
        _master_syscfg(), _config(devices=devices),
    )
    assert not plan.ok
    assert HWCHECK_PIN_EXIT_MARKER in plan.conflict
    exit_block = plan.conflict.split(HWCHECK_PIN_EXIT_MARKER, 1)[1]
    assert f"取消勾选「{HWCHECK_CHANNEL_SECTION}」里的" in exit_block, exit_block
    oled_label = HWCHECK_CHANNEL_LABELS["oled"]
    assert f"「{oled_label}」" in exit_block, exit_block
    assert f"去掉「{HWCHECK_DEVICE_SECTION}」里勾上的" in exit_block, exit_block
    assert "回到上面的器件选择" not in plan.conflict, (
        "旧文案把人支去器件列表——通道模块（oled / debug_uart）不在那儿"
    )
    assert "引脚配置里改绑上述角色" not in plan.conflict, (
        "赛题页那句出路（不可执行）不许原样带过来"
    )
    # 断言冲突清单逐脚在（页面要能点名是哪些脚）
    assert "·" in plan.conflict


def test_pin_plan_without_master_syscfg_only_resolves_bindings():
    """母版 syscfg 读不到 = 判不了就不判：只做自动解冲突，不编「装得下」的结论。"""
    manifests = _manifests(["led", "delay", "debug_uart", "oled"])
    plan = hwcheck_pin_plan(
        PLATFORM_MSPM0, manifests, board_for_platform(PLATFORM_MSPM0), None,
        _config(),
    )
    assert plan.ok and plan.bindings


# ---------------------------------------------------------------------------
# 工单 hwcheck-acceptance/03：被拦下时的**出路**必须点名这一页上真有的控件
#
# 反例（工单立项时的实测原文，见 `.scratch/hwcheck-acceptance/exit-aht10.txt`）：
# 出路第 1、2 条把人支去"回到上面的器件选择去掉一件"——可 oled **根本不在器件
# 列表里**（它是「2. 输出通道」里的勾选框），屏幕上没有那个动作可做。
#
# 判据 = 「哪个实例属于哪个控件」现算（通道开关 → 通道模块 → `INSTANCE_CONSUMERS`
# 反查实例），不手抄一份实例名清单；实例名只作括号里的补充信息。
# ---------------------------------------------------------------------------


def _plan_with_config(
    slugs: list[str], config: HwCheckConfig, master_syscfg: str
):
    return hwcheck_pin_plan(
        config.platform, _manifests(slugs), board_for_platform(config.platform),
        master_syscfg, config,
    )


def test_exit_copy_splits_channel_and_device_branches(collision_reverted_syscfg):
    """重名那一支：撞名的一方来自**输出通道**、另一方来自**器件清单**——各点名各的。

    现场（注入）：真母版 + 撤回一处改名（`collision_reverted_syscfg`）＝"将来又有
    模块把引脚起成同名"；地猛星 + 默认双通道 + 只选一件 jy61p。撞名的是
    oled(OLED_SPI)（**通道**带进来的）与 jy61p(JY61P)（**器件**带进来的）。
    """
    config = _config(devices=("jy61p",))
    plan = _plan_with_config(
        ["led", "delay", "debug_uart", "oled", "jy61p"], config,
        collision_reverted_syscfg,
    )
    assert not plan.ok
    message = plan.conflict
    exit_block = message.split(HWCHECK_PIN_EXIT_MARKER, 1)[1]
    oled_label = HWCHECK_CHANNEL_LABELS["oled"]
    assert f"取消勾选「{HWCHECK_CHANNEL_SECTION}」里的「{oled_label}」" in exit_block, (
        "通道带进来的那一方要点名那个勾选框：\n" + exit_block
    )
    assert f"去掉「{HWCHECK_DEVICE_SECTION}」里勾上的 jy61p" in exit_block, (
        "器件带进来的那一方要点名器件清单里那一件：\n" + exit_block
    )
    # SysConfig 实例名只作括号里的补充信息（不是唯一线索）
    for instance in ("OLED_SPI", "JY61P"):
        assert re.search("（[^）]*" + instance + "[^）]*）", exit_block), (
            f"实例名 {instance} 只该出现在括号里：\n" + exit_block
        )
    # 工单 11 的约定不许退化：重名那一支不说"能靠改绑"
    assert "改绑引脚解不开" in message, message
    assert "去掉其中一件" not in exit_block, (
        "不许再把重名的出路压成一句「去掉一件」（那一件可能是通道）：\n" + exit_block
    )


def test_exit_copy_never_invents_a_cause_for_unregistered_instances():
    """**未登记的实例不许被说成"心跳模块"**（01/03 评审抓到的说错成因）。

    `INSTANCE_CONSUMERS` 里没有这只实例 = 判据不认识的实例（母版新加、表还没跟上）。
    旧写法把"consumers 为空"和"consumers 只含框架模块"合并成同一个 `framework_only`
    标志，于是对未登记实例说出"它是检测程序自带的心跳模块（led / delay）"——一句
    **不成立**的成因，学生会照着一条做不到的动作去点。这里直接打文案函数：三条成因
    各说各的，且都不指错控件。
    """
    from contest_generator.hwcheck_board import _page_action_lines
    from contest_generator.syscfg_prune import SyscfgPinConflictReport

    config = _config(devices=("aht10",))
    report = SyscfgPinConflictReport(
        lines=("  · PA7：…",), capacity="", name_lines=(),
        pin_instances=("PROBE_UNKNOWN",),
    )
    text = "\n".join(_page_action_lines(report, config))
    assert "心跳模块" not in text, (
        "未登记实例（INSTANCE_CONSUMERS 里没有）不是框架心跳模块：\n" + text
    )
    assert "母版新加的实例" in text and "没有对应的勾选控件" in text, text
    # 兜底也不许写回工单 03 点名删掉的那句"回到上面的器件选择"
    assert "回到上面的器件选择" not in text, text


def test_exit_copy_uses_the_device_list_when_no_channel_is_involved(
    collision_reverted_syscfg,
):
    """同一个 oled 模块，**只从器件列表里选**时出路就只说器件清单，一个字不提通道。

    这是判据是"现算"而不是"抄一份实例名清单"的证明：模块集与上一条**逐字相同**
    （oled 照样进工程、照样撞名），只是通道勾选框关着、改从器件列表里选——所以
    屏幕上唯一做得到的动作是"去掉这一件"，不能再教人"取消勾选"。
    """
    config = _config(devices=("oled", "jy61p"), oled=False)
    plan = _plan_with_config(
        ["led", "delay", "debug_uart", "oled", "jy61p"], config,
        collision_reverted_syscfg,
    )
    assert not plan.ok
    exit_block = plan.conflict.split(HWCHECK_PIN_EXIT_MARKER, 1)[1]
    assert "取消勾选" not in exit_block, (
        "这一趟根本没有「OLED 屏」这个勾选框可取消（通道关着）：\n" + exit_block
    )
    assert f"去掉「{HWCHECK_DEVICE_SECTION}」里勾上的 oled、jy61p" in exit_block, (
        "两件都在器件清单里，就按页面上 chip 的顺序一起点名：\n" + exit_block
    )


def test_exit_copy_for_a_same_pin_conflict_names_controls_not_roles():
    """同脚那一支（真库真母版）：同样按控件分派，且照旧保留"可去引脚配置改绑"这句。

    现场 = 地猛星 + 默认双通道 + xunji + rc522（**浏览器验收用的同一组**，
    见 `tests/browser/hwcheck.spec.mjs`）：撞脚的一方是 OLED 通道带进来的 oled，
    另一方是器件 rc522，另有被 xunji 带进来的依赖 motor（它不是这一趟选的器件）。
    """
    config = _config(devices=("xunji", "rc522"))
    plan = _plan_with_config(
        ["led", "delay", "debug_uart", "oled", "xunji", "rc522"], config,
        _master_syscfg(),
    )
    assert not plan.ok
    exit_block = plan.conflict.split(HWCHECK_PIN_EXIT_MARKER, 1)[1]
    assert f"取消勾选「{HWCHECK_CHANNEL_SECTION}」里的" in exit_block, exit_block
    assert f"去掉「{HWCHECK_DEVICE_SECTION}」里勾上的 rc522" in exit_block, (
        "撞脚的器件要点名：\n" + exit_block
    )
    assert "motor" in exit_block, (
        "依赖件（motor 由 xunji 带进来）也要如实说它不在器件清单里：\n" + exit_block
    )
    assert "引脚配置" in exit_block and "改绑" in exit_block, (
        "同脚那一支照旧可以去赛题页改绑（工单 11：与重名分开写）：\n" + exit_block
    )
    assert "先只勾一个输出通道" not in exit_block, (
        "通道要不要去掉由上面那条点名控件的出路说，不再当万能出路：\n" + exit_block
    )


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
    masters_dir=None,
):
    """直调域层装配（不经 HTTP）：库根 / 母版根都是本仓真库
    （`masters_dir` 只在"造重名现场"的用例里换成临时副本）。"""
    return hwcheck_view(
        HwCheckConfig(
            platform=platform,
            debug_uart=debug_uart,
            oled=oled,
            devices=tuple(devices),
        ),
        module_library_dir=LIBRARY,
        masters_dir=MASTERS if masters_dir is None else masters_dir,
        recipe_path=recipe_path,
        require_pins=require_pins,
    )


def test_page_payload_shows_the_assigned_console_character(tmp_path):
    """页面那一格显示的是**分配后**的字符（工单 hwcheck-specialize/01）。

    前端「串口命令 <字符>」读的就是 `board["sections"][].console.command`
    （`fx/hwcheck-plan.js`），所以首选被别的器件占用、命令表按候选让位之后，这一格必须
    跟着表走——否则页面写着一个板上不认的键。判据用一份**临时配方文件**造出撞车
    现场（真库这一刻还没有两件抢同一字符的配方），库与母版仍是本仓真库。
    """
    recipes = tmp_path / "hwcheck_recipes.json"
    recipes.write_text(json.dumps({
        "led": {"stm32": {
            "init": {"calls": ["led_init(LED_RED)"]},
            "console": {"command": "l", "description": "占住 l"},
        }},
        "oled": {"stm32": {
            "init": {"calls": ["OLED_Init()"]},
            "console": {"command": "l", "candidates": ["w", "z"],
                        "description": "让位到候选"},
        }},
    }, ensure_ascii=False), encoding="utf-8")
    view = _page_view(
        PLATFORM_STM32, devices=["led", "oled"], recipe_path=recipes,
        require_pins=False,
    )
    table = {item["slug"]: item["command"] for item in view.board["console"]["commands"]}
    sections = {
        item["slug"]: item["console"]["command"] for item in view.board["sections"]
    }
    assert table == {"led": "l", "oled": "w"}, table
    assert sections == table, "页面那一格与命令表必须是同一个字符（单源不破）"


def test_hwcheck_view_projects_the_page_payload_without_http():
    """真库真母版：一次投影的字段与载荷键齐全（判据不再只能经端点验）。"""
    view = _page_view(PLATFORM_STM32, devices=["ml_mpu6050"])
    assert isinstance(view, HwCheckView)
    assert set(view.board) == {
        "wiring", "sections", "console", "console_note", "unspecialized",
        "exclusive_groups", "custom",
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


def test_hwcheck_view_surfaces_the_pin_name_collision(
    collision_reverted_masters_dir,
):
    """**同名引脚符号**在检测页也要拦下（工单 11 的第二条路；工单 02 之后现场
    改为"撤回改名一处"）。

    现场：工单 `hwcheck-acceptance/02` 已把母版 14 组同名符号全部改名，真母版今天
    一组重名都没有——判据不会自己红。`collision_reverted_masters_dir` = 母版库的
    临时副本 + 把 OLED_SPI / JY61P 的 SCL/SDA 撤回成裸名，等价于"将来又有模块把
    引脚起成同名"。

    形态是最日常的一组：地猛星 + 默认双通道 + OLED + JY61P。检测页在生成前跑
    与赛题页「自动配置」同一个求解器，PA22 那条同脚冲突解得开，**重名那一轴解不开**
    ——判据缺席时它就一路生成出去，学生在 CCS 里看到 4 个 `Duplicate name`
    （工单 11 实测）。

    判据：`require_pins=True`（预览 / 生成）大声失败 + 给检测页三条出路；文案说的是
    重名（不是"装不下"），并点名撞车的两件。`require_pins=False`（回读那次已生成的
    检测）照常投影——与既有「装不下」同一条口径。
    """
    devices = ["oled", "jy61p"]
    with pytest.raises(HwCheckError) as excinfo:
        _page_view(
            PLATFORM_MSPM0, devices=devices,
            masters_dir=collision_reverted_masters_dir,
        )
    message = str(excinfo.value)
    assert HWCHECK_PIN_EXIT_MARKER in message, "失败时要给页面出路"
    assert "符号" in message and "Duplicate name" in message, message
    assert "SCL" in message and "SDA" in message, message
    for slug in ("oled", "jy61p"):
        assert slug in message, f"要点名撞车的模块 {slug}：{message}"
    assert "改绑引脚解不开" in message, "别把重名的出路说成改绑：" + message
    view = _page_view(
        PLATFORM_MSPM0, devices=devices, require_pins=False,
        masters_dir=collision_reverted_masters_dir,
    )
    assert view.board["wiring"]["rows"], "回读照旧给出接线表"


def test_hwcheck_view_opens_oled_plus_i2c_sensor():
    """工单 `hwcheck-acceptance/02` 打开的那一格：**真母版上「OLED 屏 + 一件
    I2C 器件」检测页不再拦**（判据 = 投影照常产出接线表；02 之前这四件全 400）。

    「勾着屏幕看结果 + 我新买的那件传感器」是学生最自然的一次上板组合，
    02 之前它是死的（实测读数 `.scratch/hwcheck-acceptance/probe-02-combos.txt`）。
    """
    for slug in ("jy61p", "aht10", "bh1750", "sht30"):
        view = _page_view(PLATFORM_MSPM0, devices=["oled", slug])
        assert view.board["wiring"]["rows"], f"oled + {slug} 应能生成接线表"


def test_hwcheck_view_reads_the_recipe_override_path(tmp_path):
    """`recipe_path` 是显式入参（原先走 AppContext 覆盖）：坏配方仍大声失败。"""
    broken = tmp_path / "hwcheck_recipes.json"
    broken.write_text("{ 这不是 JSON }", encoding="utf-8")
    with pytest.raises(HwCheckError) as excinfo:
        _page_view(PLATFORM_STM32, devices=[], recipe_path=broken)
    assert "不是合法 JSON" in str(excinfo.value)
    # 缺省（库内那份）= 正常装载：响应里照旧有那几个键
    assert set(_page_view(PLATFORM_STM32, devices=[]).board) == {
        "wiring", "sections", "console", "console_note", "unspecialized",
        "exclusive_groups", "custom",
    }


def test_hwcheck_view_rejects_a_slug_outside_the_library():
    """库外 slug 由依赖展开大声失败（域错误 → 400）——新缝上也要有这条判据。"""
    from contest_generator.selection import UnknownModuleError

    with pytest.raises(UnknownModuleError) as excinfo:
        _page_view(PLATFORM_STM32, devices=["not_in_library"])
    assert "not_in_library" in str(excinfo.value)
