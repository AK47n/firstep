"""绑定判据模型（工单 gen-chain-audit/04）：`build_bindings_matrix` 的契约与语义。

背景（工单 03 真机审计）：mspm0 板图上前端 `pinCanHost` 只镜像了「类型级 /
通道 / 实例」三层，漏掉后端两条**跨角色**门禁（gpio 同端口组、成对/PWM 通道
同实例）→ 744 条（角色×脚）候选里 115 条「板图显示可绑、生成必 400」。修法 =
后端单源下发判据模型，前端只渲染（spec-matrix.md 方案 B）。

本文件钉三件事：
1. **形状**：roles 覆盖展开集全部角色、eligible 只含类型命中脚、constraint 谓词；
2. **语义**：端口组锁 = 同组**其余**角色有效脚的端口；成对实例 = 对脚有效实例集；
   两处都随观测绑定（`bindings`）变化；
3. **单源**：模型的判定与真 `resolve_bindings` 逐条一致（放行但后端拒 = 0，
   挡掉但后端收 = 0）——对拍守卫。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.boards import BOARDS_DIR, load_boards
from contest_generator.library import list_modules
from contest_generator.pin_bindings import (
    PinBindingError,
    build_bindings_matrix,
    resolve_bindings,
)
from contest_generator.selection import resolve_selection

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
LIBRARY_MODULES = LIBRARY_ROOT / "modules"

BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}
MSPM0 = "mspm0"
STM32 = "stm32"

# 工单 03 的真机审计场景（P1 节）：744 条候选 / 115 条分歧
AUDIT_SLUGS = ["step_motor", "huidu", "motor", "led_beep"]
MSPM0_BOARD = BOARDS[MSPM0]


def _matrix(slugs, platform=MSPM0, bindings=None, board=None):
    manifests = resolve_selection(LIBRARY_MODULES, platform, slugs).manifests
    return build_bindings_matrix(
        manifests, platform, board or BOARDS[platform], bindings
    )


def _rows(model):
    return {row["role"]: row for row in model["roles"]}


def _constraint(row):
    """约束谓词去掉 reason（文案不参与判定，避免测试钉死措辞）。

    `constraints` 多条并存时给**第一条**（优先级最高那条；要全量用
    `_constraints`）。
    """
    all_of = _constraints(row)
    return all_of[0] if all_of else None


def _constraints(row):
    """角色的**全部**适用谓词（后端 `constraint` / `constraints` 的读取口径，与
    前端 `pinModelConstraints` 同源）：数组优先，否则单条；逐条去 `reason`。"""
    many = row.get("constraints")
    listed = many if isinstance(many, list) and many else (
        [row["constraint"]] if row.get("constraint") else []
    )
    return [{k: v for k, v in c.items() if k != "reason"} for c in listed]


# ---------------------------------------------------------------------------
# 形状
# ---------------------------------------------------------------------------


def test_matrix_covers_every_role_of_expanded_selection():
    """roles 覆盖展开集（含依赖带入的 led/beep/delay）在该平台的全部角色声明。"""
    model = _matrix(["step_motor", "led_beep"])
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, ["step_motor", "led_beep"]).manifests
    expected = {
        f"{m.slug}.{decl.id}"
        for m in manifests
        for decl in m.platforms[MSPM0].pins
    }
    assert set(_rows(model)) == expected
    assert "led.LED" in _rows(model)  # led_beep 的依赖 led 也进来了


def test_matrix_selectable_is_capability_layer_only():
    """`selectable` = 角色**自身能力层**（类型 / 实例 / 通道前缀），不含跨角色约束。

    三条能力层判据（都与 `resolve_bindings` 的能力层同口径，漏一条就是一片假绿）：
    - 纯类型级（stm32 pwm/enc/uart、mspm0 uart/i2c）：类型 token 命中即可——
      `debug_uart` 两脚就是全部 UART 实例脚，候选集本身不收窄（跨角色那一层由
      `constraint` 的成对实例谓词管，见下面的 pair 用例）；
    - mspm0 带通道 pwm（`PWMAB_C0`）：`_mspm0_pwm_instances` 只收 `*_C0` 尾的实例
      → PA23/PA12（`TIMG8_C0`/`TIMG0_C0`）在候选里，PA0（`TIMA0_C0` + `TIMG8_C1`
      = 含 C0，**应当**在候选里）——反面判例是 PA13（`TIMG0_C1`/`TIMA0_C3`，无 C0 尾）；
    - strict-all（默认脚实例全中）：`DCC_100_PWM2_C0` 默认 PA14 只有 `pwm:TIMG12_C0`
      → 只有带该实例的脚可选（实现中途把它误判成「类型级」→ 74 条假绿被对拍抓出）。
    """
    rows = _rows(_matrix(AUDIT_SLUGS))
    io_names = {p.name for p in MSPM0_BOARD.pins if p.kind == "io"}
    for row in rows.values():
        assert row["selectable"], f"{row['role']} 的候选集为空（能力层口径坏了）"
        assert set(row["selectable"]) <= io_names

    c0 = rows["motor.PWMAB_C0"]
    for pin_name in c0["selectable"]:
        pin = next(p for p in MSPM0_BOARD.pins if p.name == pin_name)
        assert any(
            t.startswith("pwm:") and t.endswith("_C0") for t in pin.capabilities
        ), f"{pin_name} 没有 *_C0 尾的 pwm 实例，不该在 PWMAB_C0 的候选里"
    assert "PA13" not in c0["selectable"]   # TIMG0_C1 / TIMA0_C3：无 _C0 尾

    # `DCC_100_PWM2_C0` 同样是带通道角色：默认脚 PA14 带 `pwm:TIMG12_C0`，但 C0
    # 角色对**任意**带 `*_C0` 实例的脚都可绑（PA0 的 `pwm:TIMA0_C0` 也算），
    # 15 个 C0 脚 < 31 —— 全类型级，不是 strict-all（实现中途误判成 strict-all，
    # 那会让板图白挡 13 个合法脚，真机审计 P1b 的 13 条 WARN 当场抓）
    dcc = rows["step_motor.DCC_100_PWM2_C0"]
    assert "PA14" in dcc["selectable"]
    assert "PA0" in dcc["selectable"]
    assert 0 < len(dcc["selectable"]) < len(io_names)
    for p in dcc["selectable"]:
        assert any(
            t.startswith("pwm:") and t.endswith("_C0")
            for t in next(x for x in MSPM0_BOARD.pins if x.name == p).capabilities
        )

    # 纯类型级（stm32 uart）：候选集 = UART 实例脚
    tx = _rows(_matrix(["debug_uart"], platform=STM32))["debug_uart.DEBUG_UART_TX"]
    assert 0 < len(tx["selectable"]) < len(
        [p for p in BOARDS[STM32].pins if p.kind == "io"]
    )


# ---------------------------------------------------------------------------
# 端口组约束（_check_mspm0_gpio_port_groups 的同判据）
# ---------------------------------------------------------------------------


def test_port_group_constraint_from_defaults():
    """step_motor 四脚默认全 B 口 → 每个角色的约束 = 端口 B（单端口宏组）。"""
    rows = _rows(_matrix(AUDIT_SLUGS))
    for role_id in ("STEP_MOTOR_RST2", "STEP_MOTOR_SLP2", "STEP_MOTOR_DIR2", "STEP_MOTOR_DCY2"):
        assert _constraint(rows[f"step_motor.{role_id}"]) == {"kind": "port", "port": "B"}


def test_mixed_port_group_has_no_constraint():
    """huidu 八路灰度默认跨 A/B 口 → 逐脚端口宏，后端不查 = 模型不给约束。"""
    rows = _rows(_matrix(AUDIT_SLUGS))
    for role_id in ("L1", "R3", "R4"):
        assert _constraint(rows[f"huidu.{role_id}"]) is None
    # 单角色组同样不成组（motor 的 4 个 gpio_out 默认跨口 → 无约束）
    assert _constraint(rows["motor.AIN1"]) is None


def test_port_group_follows_observed_bindings():
    """约束随观测绑定走 + 一条**已知的松弛**（诚实记账，别当 bug 修）：

    - 组内某角色改绑到另一端口、其余仍在默认端口 → 该组**此刻无解**（后端会 400）：
      模型对所有角色都不给约束（`None`）——这是**故意的最松弛选择**，宁可让用户
      试到第三次才撞 400 文案，也不假红地把脚全灰掉（模型看不到用户「打算」把
      整组搬过去）；
    - 组内所有角色都被观测到同一端口（整组已搬）→ 约束跟着搬到那个端口。
    """
    # 整组搬到 A 口（观测 = 四脚全 A）：约束 = A
    rows = _rows(
        _matrix(
            AUDIT_SLUGS,
            bindings={
                "step_motor.STEP_MOTOR_RST2": "PA0",
                "step_motor.STEP_MOTOR_SLP2": "PA1",
                "step_motor.STEP_MOTOR_DIR2": "PA2",
                "step_motor.STEP_MOTOR_DCY2": "PA3",
            },
        )
    )
    for role_id in ("STEP_MOTOR_RST2", "STEP_MOTOR_SLP2", "STEP_MOTOR_DIR2", "STEP_MOTOR_DCY2"):
        assert _constraint(rows[f"step_motor.{role_id}"]) == {"kind": "port", "port": "A"}

    # 组内一半在 A、一半在 B（观测自相矛盾）：无解 → 不给约束（不假红）
    rows = _rows(_matrix(AUDIT_SLUGS, bindings={"step_motor.STEP_MOTOR_SLP2": "PA0"}))
    for role_id in ("STEP_MOTOR_RST2", "STEP_MOTOR_DIR2", "STEP_MOTOR_DCY2"):
        assert _constraint(rows[f"step_motor.{role_id}"]) is None


def test_port_group_is_mspm0_only():
    """端口组门禁是 mspm0 专属：stm32 的配置组默认同端口也**不给** port 谓词。

    stm32 `config.DIP0-3` 默认全在 PB12-15（走逐脚宏，后端不查同端口）——
    误给约束就是 4×29 条假红。这条钉住平台分支，防「顺手统一」改坏。
    """
    rows = _rows(_matrix(["config"], platform=STM32))
    dip_keys = [k for k in rows if k.rsplit(".", 1)[-1] in ("DIP0", "DIP1", "DIP2", "DIP3")]
    assert len(dip_keys) == 4
    for key in dip_keys:
        assert _constraint(rows[key]) is None


# ---------------------------------------------------------------------------
# 成对 / 通道同实例约束（_check_paired_role_instances / _pwm_channel_pairs 同判据）
# ---------------------------------------------------------------------------


def test_pwm_channel_pair_constraint_from_default_foot():
    """motor.PWMAB_C0/C1 默认 PA12/PA13（TIMG0 两通道）→ 互相给同实例约束。

    约束里的 `instances` = **对脚默认脚的完整 pwm 实例集**（不过滤通道）：
    pwm 两通道门禁按实例**基名**交集（`_check_mspm0_pwm_channel_pairs`），
    前端求值时同样按基名比——预过滤通道会让交集恒空（实现中途踩过）。
    """
    rows = _rows(_matrix(AUDIT_SLUGS))
    c0 = _constraint(rows["motor.PWMAB_C0"])
    assert c0 is not None and c0["kind"] == "instance"
    assert c0["pair"] == "motor.PWMAB_C1"
    assert c0["instances"] == ["TIMA0_C3N", "TIMG0_C1"]   # PA13 的 pwm 实例（含互补通道）
    c1 = _constraint(rows["motor.PWMAB_C1"])
    assert c1 is not None and c1["instances"] == ["TIMA0_C3", "TIMG0_C0"]  # PA12


def test_pwm_pair_constraint_follows_observed_bindings():
    """对脚绑到 PA0 后，C0 的候选实例集当场换成 PA0 的实例（TIMA0_C0/TIMG8_C1）。

    `selectable`（能力层）不随对脚变化——变的是跨角色谓词的 `instances`；
    谓词按基名比，故 TIMA0_C0 与 TIMG8_C1 两个基名都算（PA0 自身带 _C0 尾，
    在 `selectable` 里）。
    """
    rows = _rows(_matrix(AUDIT_SLUGS, bindings={"motor.PWMAB_C1": "PA0"}))
    c0 = rows["motor.PWMAB_C0"]
    assert _constraint(c0)["instances"] == ["TIMA0_C0", "TIMG8_C1"]
    # selectable（能力层）不随对脚变化——它只按**本脚**通道过滤
    assert c0["selectable"] == _rows(_matrix(AUDIT_SLUGS))["motor.PWMAB_C0"]["selectable"]
    # 能力层收窄（无 _C0 尾实例的脚根本不在候选）先于谓词：PA13 不在 selectable
    assert "PA13" not in c0["selectable"]


def test_uart_pair_instance_predicate_mirrors_gate():
    """uart TX/RX 成对同实例**也要跨角色谓词**（工单 mspm0-slot-conflict/04）。

    旧口径（工单 gen-chain-audit/04 实现期修正④「uart/i2c 成对不叠谓词」）以为
    「脚自带的实例集」就能表达成对同实例——那只在**同模块内**成立：能力层
    `selectable` 对 uart 是类型级（有 uart token 即可），说不出「必须与对脚同
    实例」。实测代价：全库累积态对拍 188 条（mspm0）+ 52 条（stm32）「板图显示
    可绑、生成必 400」。

    stm32 `debug_uart` 默认 TX=PA2 / RX=PA3（同 `UART_2`）：
    - 对脚有效实例 = `["UART_2"]`（未绑 → 默认脚实例）；
    - 本脚候选 = **必须落在 `UART_2`**；`PA9`（`UART_1`）被谓词挡住（旧口径放行）；
    - 两脚**一起**搬（TX→PA9 + RX→PA10）整份仍合法（对脚实例随观测变）。
    """
    rows = _rows(_matrix(["debug_uart"], platform=STM32))
    board = BOARDS[STM32]
    tx = rows["debug_uart.DEBUG_UART_TX"]
    rx = rows["debug_uart.DEBUG_UART_RX"]
    assert tx["default"] == "PA2" and rx["default"] == "PA3"
    assert _constraint(tx) == {
        "kind": "instance",
        "instances": ["UART_2"],
        "pair": "debug_uart.DEBUG_UART_RX",
    }
    assert _constraint(rx) == {
        "kind": "instance",
        "instances": ["UART_2"],
        "pair": "debug_uart.DEBUG_UART_TX",
    }
    # 能力层仍是类型级（三个 UART 实例的脚都在候选里），收窄的是跨角色谓词
    assert {"PA2", "PA9", "PB10"} <= set(tx["selectable"])
    assert _selectable(tx, "PA2", board)
    assert not _selectable(tx, "PA9", board)   # UART_1：与对脚 UART_2 无交集
    assert not _selectable(tx, "PB10", board)  # UART_3：同理

    # 谓词随观测走：对脚搬到 PA10（UART_1）→ 本脚候选跟着变 UART_1
    followed = _rows(
        _matrix(["debug_uart"], platform=STM32, bindings={"debug_uart.DEBUG_UART_RX": "PA10"})
    )["debug_uart.DEBUG_UART_TX"]
    assert _constraint(followed)["instances"] == ["UART_1"]
    assert _selectable(followed, "PA9", board)
    assert not _selectable(followed, "PA2", board)
    # 整对一起搬 = 合法（这就是「成对改造」该有的形状）
    assert _backend_ok_state(
        resolve_selection(LIBRARY_MODULES, STM32, ["debug_uart"]).manifests,
        STM32,
        board,
        {"debug_uart.DEBUG_UART_TX": "PA9", "debug_uart.DEBUG_UART_RX": "PA10"},
    )


def test_uart_pair_predicate_none_when_peer_has_no_instances():
    """对脚无实例 → **不给**谓词（与门禁的防御性 `continue` 同守卫）。

    stm32 i2c 是这类：脚上有 `i2c_scl` / `i2c_sda` token 但**不带实例名**，
    `_check_paired_role_instances` 两边有效实例集都空 → 直接跳过不查；模型若照发
    `instances: []` 的谓词，就是一片假红的来源（前端「空集 = 不拦」虽能兜住，
    契约上仍不该发）。mspm0 uart 相反：脚上都带实例名 → 谓词照发。
    """
    stm32_rows = _rows(_matrix(["at24c02"], platform=STM32))
    assert _constraint(stm32_rows["at24c02.AT24C02_SCL"]) is None
    assert _constraint(stm32_rows["at24c02.AT24C02_SDA"]) is None
    # 能力层照旧：SCL 角色能在 i2c_scl 脚里挑（谓词不发 = 不额外收窄）
    assert len(stm32_rows["at24c02.AT24C02_SCL"]["selectable"]) > 1

    mspm0_rows = _rows(_matrix(["debug_uart"], platform=MSPM0))
    assert _constraint(mspm0_rows["debug_uart.DEBUG_UART_TX"])["kind"] == "instance"


def test_uart_pair_predicate_blocks_single_foot_move_with_peer_bound():
    """成对实例的**累积态**回归锚（口径 = 用户点下去真实发出去的那份 bindings）。

    mspm0 `as32`（TX 默认 PA26 / RX 默认 PA25，都走 UART3）+ 混入 `debug_uart`
    （TX PA23 / RX PA22，走 UART2）——**同一份 payload 里有两个成对角色**，这正是
    工单 03 那条 188 条线索的真实形状（全库对拍时 debug_uart / as32 / hc05 /
    zigbee 族同选同绑）。种子只绑 `as32.RX → PB3`（UART3，与 TX 默认脚同实例）：
    此刻 `as32.TX → PA0`（UART0）单看是合法 uart 脚，整份提交却必 400
    （TX UART3 × RX UART3 里的另一只脚… 实际拒因 = 对脚已在该实例的另一只脚上、
    本脚实例换到 UART0 → 交集空）。旧模型放行 = 板图点得下去、最后一步被拦。
    """
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, ["as32", "debug_uart"]).manifests
    seed = {"as32.AS32_UART_RX": "PB3"}
    assert _backend_ok_state(manifests, MSPM0, MSPM0_BOARD, seed), "种子累积态被后端拒"
    rows = _rows(build_bindings_matrix(manifests, MSPM0, MSPM0_BOARD, seed))
    tx = rows["as32.AS32_UART_TX"]
    # 对脚有效实例 = UART3（种子脚 PB3）→ 谓词只放行 UART3 的脚
    assert _constraint(tx) == {
        "kind": "instance",
        "instances": ["UART3"],
        "pair": "as32.AS32_UART_RX",
    }
    assert _selectable(tx, "PB2", MSPM0_BOARD)          # UART3 的另一只 TX 脚
    assert not _selectable(tx, "PA0", MSPM0_BOARD)      # UART0：旧口径放行的那类假绿
    assert not _backend_ok_state(
        manifests, MSPM0, MSPM0_BOARD, {**seed, "as32.AS32_UART_TX": "PA0"}
    ), "后端此刻本该拒（这条缝的事实前提）"
    # 反面对照：debug_uart 的对脚**没有**被观测 → 它是否可绑不受 as32 影响
    assert _constraint(rows["debug_uart.DEBUG_UART_TX"])["instances"] == ["UART2"]


# ---------------------------------------------------------------------------
# 槽位互斥约束（_check_slot_conflicts / _mspm0_same_slot 同判据，工单 mspm0-slot-conflict/02）
# ---------------------------------------------------------------------------


def test_slot_group_pair_from_default_foot():
    """huidu.R3 与 pid.GRAY_D7 默认同为 PB6 且同属 HUIDU 实例 = 同槽位对。

    `default`（= `huidu.R3` 的有效脚）与 `peers` 都要下发，前端只比引脚名。
    """
    rows = _rows(_matrix(["huidu", "pid"]))
    assert rows["huidu.R3"]["default"] == "PB6"
    assert rows["pid.GRAY_D7"]["default"] == "PB6"


def test_slot_constraint_only_when_peer_is_observed():
    """槽位谓词只在同伴**出现在 bindings 里**时才下发（否则整组还可以一起搬）。

    - 同伴全未绑（观测空 / 同伴不在观测里）→ `None`：这一份里只有本角色自己，
      后端此刻也不拒（同伴走默认、不构成互斥），给约束会把搬家的第一步灰掉；
    - 同伴被观测到（哪怕绑的正是它自己的默认 PB6 —— 载荷里保留 no-op 条目是既有
      政策明确允许的形态）→ `{kind:"slot", pin:"PB6"}`：本角色点别的脚这一份必 400。
    """
    slugs = ["huidu", "pid"]
    assert _constraint(_rows(_matrix(slugs))["huidu.R3"]) is None
    assert (
        _constraint(_rows(_matrix(slugs, bindings={"pid.GRAY_D1": "PA22"}))["huidu.R3"])
        is None
    )
    peer_at_default = _rows(_matrix(slugs, bindings={"pid.GRAY_D7": "PB6"}))
    assert _constraint(peer_at_default["huidu.R3"]) == {
        "kind": "slot",
        "pin": "PB6",
        "peers": ["pid.GRAY_D7"],
    }
    # 反向：同伴视角同样拿到谓词（对称）
    assert _constraint(
        _rows(_matrix(slugs, bindings={"huidu.R3": "PB6"}))["pid.GRAY_D7"]
    )["pin"] == "PB6"


def test_slot_constraint_follows_observed_peer_pin():
    """同伴搬到哪，约束就跟到哪：两边都搬（同脚）→ 谓词指向新脚、该脚放行。"""
    rows = _rows(
        _matrix(["huidu", "pid"], bindings={"huidu.R3": "PA0", "pid.GRAY_D7": "PA0"})
    )
    assert _constraint(rows["huidu.R3"]) == {
        "kind": "slot",
        "pin": "PA0",
        "peers": ["pid.GRAY_D7"],
    }
    assert _selectable(rows["huidu.R3"], "PA0", MSPM0_BOARD)
    assert not _selectable(rows["huidu.R3"], "PB6", MSPM0_BOARD)


def test_slot_constraint_none_when_observed_peers_disagree():
    """同伴之间就自相矛盾（≥3 成员组里两个同伴绑在不同脚）→ 该组此刻无解 → `None`。

    与端口组 `len(ports) != 1 → None` 同一取舍：宁可让用户走到 400 文案看到后端
    逐字原因，也不把所有脚灰掉（用户可能正准备把整组继续搬过去）。

    两成员组（huidu.R3 × pid.GRAY_D7）**不存在**这一相——同伴只有一个，谈不上
    分歧；本用例用 adc 槽（PA24 上 18 个 ADC 成员）取三成员组来钉。
    """
    slugs = ["adc", "mq2", "mq3"]
    peers = _rows(_matrix(slugs))["adc.ADC_CH0"]
    assert peers["default"] == "PA24"
    agreed = _rows(_matrix(slugs, bindings={"mq2.MQ2_AO_CH0": "PA0"}))["adc.ADC_CH0"]
    assert _constraint(agreed) == {
        "kind": "slot",
        "pin": "PA0",
        "peers": ["mq2.MQ2_AO_CH0"],
    }
    disagreed = _rows(
        _matrix(
            slugs,
            bindings={"mq2.MQ2_AO_CH0": "PA0", "mq3.MQ3_AO_CH0": "PA1"},
        )
    )["adc.ADC_CH0"]
    assert _constraint(disagreed) is None
    # 两同伴被观测到同一脚 → 又变成有定解（用户把整组搬过去了）
    both = _rows(
        _matrix(slugs, bindings={"mq2.MQ2_AO_CH0": "PA0", "mq3.MQ3_AO_CH0": "PA0"})
    )["adc.ADC_CH0"]
    assert _constraint(both)["pin"] == "PA0"
    assert _constraint(both)["peers"] == ["mq2.MQ2_AO_CH0", "mq3.MQ3_AO_CH0"]


def test_slot_group_survives_when_port_group_has_no_answer():
    """huidu 八路灰度默认跨 A/B 口 → 端口组无解（不给 port 谓词），
    但同槽位对**照旧要下发 slot 谓词**。

    判据是「每一级各自判有无定解」，不是 `elif` 链：写成 `elif` 时端口组那一级的
    「无解 → None」会把第三级整个吞掉（实现中途踩过，槽位谓词一条都不出现）。
    """
    rows = _rows(_matrix(["huidu", "pid"], bindings={"pid.GRAY_D7": "PB6"}))
    r3 = rows["huidu.R3"]
    assert r3["constraint"] is not None
    assert r3["constraint"]["kind"] == "slot"


def test_slot_constraint_is_mspm0_only():
    """槽位互斥是 mspm0 专属（`resolve_bindings` 只在 mspm0 分支调
    `_check_slot_conflicts`）：stm32 各角色宏族独立，同默认脚不互斥。

    stm32 `config.DIP0-3` 默认全 PB12-15 是同一形状——给它算 slot 组就是一片假红。
    """
    rows = _rows(_matrix(["config"], platform=STM32))
    assert not [
        row for row in rows.values()
        if row["constraint"] and row["constraint"]["kind"] == "slot"
    ]


# ---------------------------------------------------------------------------
# 单源对拍：模型判定 × 真 resolve_bindings（放行但后端拒 = 0；挡掉但后端收 = 0）
# ---------------------------------------------------------------------------


def _role_channel(role_key):
    """角色 id 尾的 pwm 通道（`motor.PWMAB_C0` → `"C0"`；无则 None）。"""
    m = re.search(r"_C(\d+)$", role_key.rsplit(".", 1)[-1])
    return "C" + m.group(1) if m else None


def _selectable(row, pin_name, board):
    """前端对模型的求值口径（与 `fx/pin-model.js` 同判据，此处按板数据复核）：

    `selectable` 命中 且**全部**谓词求值通过（`constraints` 多条并存 = 并列门禁）。
    pwm 的 instance 谓词 = **两脚各自按本脚通道过滤后取实例基名比交集**——与后端
    `_check_mspm0_pwm_channel_pairs` 逐字同口径（`constraint.instances` 已是**对脚
    过滤后**的集合）；**非 pwm 的 instance 谓词**（uart TX/RX、i2c SCL/SDA）= 本脚
    该类型的实例 token 与 `instances`（对脚有效实例集）**精确**相交（前端同分支）；
    `slot` 谓词 = 引脚名与同槽位同伴的有效脚相等（后端 `_check_slot_conflicts` 同判据）。
    """
    if pin_name not in row["selectable"]:
        return False
    return all(
        _predicate_holds(c, row, pin_name, board) for c in _constraints(row)
    )

def _predicate_holds(c, row, pin_name, board):
    """单条谓词的求值（与 `fx/pin-model.js` 的 `pinConstraintHolds` 同判据）。"""
    if c["kind"] == "port":
        return pin_name[1] == c["port"]
    if c["kind"] == "slot":
        return not c.get("pin") or pin_name == c["pin"]
    tokens = {
        p.name: list(p.capabilities) for p in board.pins if p.kind == "io"
    }[pin_name]
    prefix = row["type"] + ":"
    instances = [t[len(prefix):] for t in tokens if t.startswith(prefix)]
    wanted = list(c["instances"])
    if row["type"] == "pwm":
        own = _role_channel(row["role"])
        theirs_ch = _role_channel(c.get("pair", ""))
        mine = [i for i in instances if not own or i.endswith("_" + own)]
        theirs = [i for i in wanted if not theirs_ch or i.endswith("_" + theirs_ch)]
        return bool(
            {i.split("_", 1)[0] for i in mine}
            & {i.split("_", 1)[0] for i in theirs}
        )
    return bool(set(instances) & set(wanted))


def test_frontend_evaluator_matches_model_selectable_and_constraint():
    """前端求值口径（`selectable` + 谓词）与模型逐条一致——两边都不许有额外规则。

    这条是 05 号工单（前端接线）的预演：前端只做「命中 selectable + 谓词求值」，
    没有第二条规则可漂移。
    """
    board = MSPM0_BOARD
    model = _matrix(AUDIT_SLUGS)
    io_pins = [p for p in board.pins if p.kind == "io"]
    for row in model["roles"]:
        # selectable 之外的脚一律不可选（无论谓词是否成立）
        for pin in io_pins:
            if pin.name in row["selectable"]:
                continue
            assert not _selectable(row, pin.name, board)
        # 端口约束：只有该端口的脚可选
        c = row["constraint"]
        if c is not None and c["kind"] == "port":
            for pin in row["selectable"]:
                assert _selectable(row, pin, board) == (pin[1] == c["port"])


def _backend_ok(manifests, platform, board, key, pin_name):
    try:
        resolve_bindings(manifests, platform, board, {key: pin_name})
        return True
    except PinBindingError:
        return False

@pytest.mark.parametrize("platform,slugs", [(MSPM0, AUDIT_SLUGS), (STM32, ["ir_beam", "pid", "motor", "led_beep"])])
def test_matrix_selectable_matches_backend_verdict(platform, slugs):
    """硬红线：模型放行的绑定后端必须收（假绿 = 板图上配得出、生成必 400）。"""
    board = BOARDS[platform]
    manifests = resolve_selection(LIBRARY_MODULES, platform, slugs).manifests
    model = build_bindings_matrix(manifests, platform, board, None)
    # **全脚枚举**（不只 selectable）：能力层挡掉的脚也要与后端一致，
    # 否则「selectable 收窄」会掩盖假绿（工单 06 现场：只枚举 selectable 时
    # DCC/PWMAB 的 24 条假绿全被跳过，用例一片绿）
    io_pins = [p for p in board.pins if p.kind == "io"]
    false_green, false_red, checked = [], [], 0
    for row in model["roles"]:
        for pin in io_pins:
            checked += 1
            ui_ok = _selectable(row, pin.name, board)
            be_ok = _backend_ok(manifests, platform, board, row["role"], pin.name)
            if ui_ok and not be_ok:
                false_green.append((row["role"], pin.name))
            if be_ok and not ui_ok:
                false_red.append((row["role"], pin.name))
    assert checked >= 500  # 全脚枚举规模（mspm0 = 24 角色 × 31 io 脚 / stm32 ≈ 600）
    if false_green or false_red:
        detail = {
            "假绿": [
                (r, p, _backend_reason(manifests, platform, board, r, p))
                for r, p in false_green[:6]
            ],
            "假红": false_red[:6],
        }
        pytest.fail(f"模型与后端判定不一致：{detail}")
    assert false_green == [] and false_red == []


def _backend_reason(manifests, platform, board, key, pin_name):
    try:
        resolve_bindings(manifests, platform, board, {key: pin_name})
        return "（后端收）"
    except PinBindingError as exc:
        return str(exc)[:160]


def test_matrix_blocks_every_backend_rejected_candidate():
    """后端拒的候选中，**旧口径会放行的那 115 条**必须全部被模型挡住。

    旧口径 = 只查「这脚有没有该角色类型 token」（`pinListsType`）+ mspm0 pwm 的
    通道尾过滤（`pwmRoleChannel`）；模型口径 = 自身能力层 `selectable` + 跨角色
    `constraint`。三条锚（真机审计 / 工单 03 复侦口径）：

    - 候选（菜单第一层会列的）= 744；
    - 旧口径放行但后端拒 = **115**（84 端口组 + 31 通道对），模型必须全挡住；
    - 另有 43 条后端拒是旧口径**自己就挡着的**（能力层 strict-all：如
      `DCC_100_PWM2_C0` 默认 PA14 的 `pwm:TIMG12_C0` + `pwm:TIMA0_C3N` 不是每个脚
      都有）——模型同样必须挡住（共 158 条 = 候选集里后端拒的全部）。
    """
    board = MSPM0_BOARD
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, AUDIT_SLUGS).manifests
    model = build_bindings_matrix(manifests, MSPM0, board, None)
    io_pins = [p for p in board.pins if p.kind == "io"]

    def old_can_host(row, pin_name):
        """旧前端口径（真机审计脚本 P1 的镜像，逐行对应 ui/generate-pins.js）。

        ⚠ 两个坑（本用例第一版都踩过，写下来防重犯）：
        1. **不是**「菜单第一层就列」——P1 的候选集对每个角色都用 `pinListsType`
           （类型命中）判，mspm0 pwm 的通道过滤只出现在 `pinCanHost` 里，所以
           `DCC_100_PWM2_C0` 的候选是 31 个脚（不是 2 个）→ 744 这个锚才对得上；
        2. `old_can_host` 必须严格等于审计脚本里的 `canHost`，不能「顺手修一下」：
           它比后端**窄**的地方（DCC 的通道尾过滤把 PA14 之外的合法脚挡了）正是
           旧口径的第二类漂移，模型修好它属于白捡，但不进本用例的 115 条锚。
        """
        pin = next(p for p in io_pins if p.name == pin_name)
        prefix = row["type"] + ":"
        return any(
            t == row["type"] or t.startswith(prefix) for t in pin.capabilities
        )

    blocked, still_green, candidates = [], [], 0
    rejected = 0
    for row in model["roles"]:
        for pin in io_pins:
            if not old_can_host(row, pin.name):
                continue  # 菜单第一层就不列的，不算分歧（与真机审计同口径）
            candidates += 1
            if _backend_ok(manifests, MSPM0, board, row["role"], pin.name):
                continue
            rejected += 1
            if _selectable(row, pin.name, board):
                still_green.append((row["role"], pin.name))
            else:
                blocked.append((row["role"], pin.name))
    assert still_green == [], f"仍有「可配但必 400」：{still_green[:8]}"
    assert candidates == 744, f"候选规模应与真机审计一致（744），实测 {candidates}"
    assert rejected == 158, f"候选集里后端拒的总数应为 158，实测 {rejected}"
    assert len(blocked) == rejected


def test_matrix_is_cheap_enough_for_every_render():
    """端点每次渲染算一遍：全库展开也不该慢（真机审计 P1 会连打多轮）。"""
    import time

    manifests = list_modules(LIBRARY_MODULES)
    start = time.perf_counter()
    build_bindings_matrix(manifests, MSPM0, MSPM0_BOARD, None)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"全库矩阵耗时 {elapsed:.3f}s（应 < 1s）"


def test_greedy_user_walk_never_produces_backend_rejected_state():
    """按用户真实节奏走一遍（逐角色绑脚）：凡模型放行的绑定，后端必须接受**累积态**。

    单绑定对拍（上面的用例）证明「一格一格都对」；本用例补「连起来走」——模型给
    的候选是按**当前**观测绑定算的，用户点第一脚、第二脚、第三脚时状态在变，任何
    一步放行都必须与后端对同一份累积 bindings 的判定一致（假绿在这里最容易漏）。
    算法：按角色顺序贪心取第一个「模型可选」的脚绑上，每绑一次就整份回验。
    """
    board = MSPM0_BOARD
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, AUDIT_SLUGS).manifests
    bindings: dict[str, str] = {}
    steps = 0
    for _ in range(len(manifests) * 6):  # 角色数上限（每角色最多绑一次）
        model = build_bindings_matrix(manifests, MSPM0, board, bindings or None)
        row = next(
            (r for r in model["roles"] if r["role"] not in bindings), None
        )
        if row is None:
            break
        pick = next(
            (p for p in row["selectable"] if _selectable(row, p, board)), None
        )
        assert pick is not None, f"{row['role']} 一个可绑脚都没有（模型过严）"
        bindings[row["role"]] = pick
        steps += 1
        assert _backend_ok_state(manifests, MSPM0, board, bindings), (
            f"模型放行的 {row['role']} → {pick} 让累积绑定被后端拒：{bindings}"
        )
    assert steps >= 10, f"贪心只走了 {steps} 步（模型过严，走不动）"


def _backend_ok_state(manifests, platform, board, bindings) -> bool:
    """整份累积 bindings 回验后端（`resolve_bindings` = 唯一判据）。"""
    try:
        resolve_bindings(manifests, platform, board, bindings)
        return True
    except PinBindingError:
        return False


# ---------------------------------------------------------------------------
# 累积态对拍相（工单 mspm0-slot-conflict/03）：口径 = 用户点下去真实发出去的那一份
# ---------------------------------------------------------------------------


def _stepwise_false_greens(manifests, platform, board, seed):
    """从种子累积态出发，逐步 × 全候选枚举「模型放行但整份回验后端拒」的假绿。

    口径 = 真实提交：模型对 (角色, 脚) 放行 → 把这一步并入累积 bindings
    （与 `collectBindings` 的载荷形态一致）→ **整份**回验 `resolve_bindings`。

    与上面的单绑定对拍（`_backend_ok(manifests, …, {key: pin})`）的区别正是工单 01
    那条缝：单绑定收、累积态拒。返回 (假绿清单, 假红清单, 枚举样本数)。

    `platform` / `board` 都是参数（工单 04 起用于全库两平台对拍）：计数口径不变，
    只是不再钉死 mspm0。
    """
    false_green: list[tuple[str, str, str]] = []
    false_red: list[tuple[str, str]] = []
    checked = 0
    model = build_bindings_matrix(manifests, platform, board, seed or None)
    for role, row in _rows(model).items():
        for pin_name in row["selectable"]:
            ui_ok = _selectable(row, pin_name, board)
            if seed.get(role) == pin_name:
                continue
            checked += 1
            trial = dict(seed)
            trial[role] = pin_name
            be_ok = _backend_ok_state(manifests, platform, board, trial)
            if ui_ok and not be_ok:
                false_green.append(
                    (role, pin_name, _backend_state_reason(manifests, platform, board, trial))
                )
            if be_ok and not ui_ok:
                false_red.append((role, pin_name))
    return false_green, false_red, checked


def _backend_state_reason(manifests, platform, board, bindings) -> str:
    try:
        resolve_bindings(manifests, platform, board, bindings)
        return "（后端收）"
    except PinBindingError as exc:
        return str(exc)[:140]


def _default_pin_seed(manifests, platform, board):
    """种子累积态 = 每个角色**显式绑回自己的默认脚**（两平台通用）。

    这是 `repro_slot_conflict.py` ② 的真实形态，也是既有政策明确允许的载荷形态
    （`resolve_bindings` 文档串：「绑定值 == 默认值的条目保留在清单里（写侧按 no-op
    跳过）」）：`collectBindings` 只带用户动过的角色，而「动过又动回默认」留下的就是
    这种条目。它为什么是**必要**的种子——`_check_slot_conflicts` 只在**被绑定**的角色
    之间判互斥（未绑角色走默认、不构成互斥），所以「同槽位两角色有一方在这份
    bindings 里」这一相只有这种种子能到达；缺了它，同型假绿照旧从守卫底下漏过去
    （工单 01 的成因）。
    """
    seed: dict[str, str] = {}
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for decl in entry.pins:
            if decl.default and board.pin_index.get(decl.default) is not None:
                seed[f"{manifest.slug}.{decl.id}"] = decl.default
    return seed


def test_accumulated_state_matches_backend_from_default_state():
    """累积态对拍（默认态起）：模型放行的一步改绑并入累积 bindings 后，整份必须后端收。

    这条是工单 06 单绑定对拍的**收口**：单绑定证明「一格一格都对」，本相证明
    「点下去的那一份」也对——`{huidu.R3: PA0}` 单绑定后端收，但
    `{huidu.R3: PA0, pid.GRAY_D7: PB6}` 后端拒，上一轮就是这么漏过去的。
    假红同钉（后端收而模型挡 = 模型过严，同样让用户配不出合法绑定）。
    """
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, AUDIT_SLUGS).manifests
    false_green, false_red, checked = _stepwise_false_greens(
        manifests, MSPM0, MSPM0_BOARD, {}
    )
    assert checked > 400, f"枚举样本太少（{checked}），守卫形同虚设"
    if false_green or false_red:
        pytest.fail(
            f"累积态口径分歧：假绿 {false_green[:5]} / 假红 {false_red[:5]}"
        )


def test_accumulated_state_blocks_slot_conflict_with_peer_bound():
    """槽位互斥的累积态回归锚（工单 01 那条缝的直接守卫）。

    种子 = 「显式绑回自己默认脚」（见 `_default_pin_seed`），场景 = `huidu` + `pid`
    （八路灰度族：`huidu.R3` 与 `pid.GRAY_D7` 默认同为 PB6、同属 HUIDU 实例 =
    同槽位对）。未修时：模型放行 `huidu.R3 → PA0`，而这一份整份提交后端拒
    「共用同一槽位却绑到不同引脚」——正是板图上点得下去、最后一步必 400。

    反向验证（工单 03 验收）：临时停用 `slot` 谓词 → 本用例必须当场红。
    """
    slugs = ["huidu", "pid"]
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, slugs).manifests
    seed = _default_pin_seed(manifests, MSPM0, MSPM0_BOARD)
    # 种子本身必须是后端收的合法态（否则假绿是种子带出来的，不是模型的错）
    assert _backend_ok_state(manifests, MSPM0, MSPM0_BOARD, seed), "种子累积态被后端拒"
    assert seed["huidu.R3"] == "PB6" and seed["pid.GRAY_D7"] == "PB6"

    # 该场景确实含同槽位对（防「种子/选择集变了导致本用例空转」而静默失效）
    rows = _rows(build_bindings_matrix(manifests, MSPM0, MSPM0_BOARD, seed))
    assert _constraint(rows["huidu.R3"]) == {
        "kind": "slot",
        "pin": "PB6",
        "peers": ["pid.GRAY_D7"],
    }
    assert not _selectable(rows["huidu.R3"], "PA0", MSPM0_BOARD)

    false_green, false_red, checked = _stepwise_false_greens(
        manifests, MSPM0, MSPM0_BOARD, seed
    )
    assert checked > 400, f"枚举样本太少（{checked}）"
    if false_green or false_red:
        pytest.fail(
            f"槽位互斥在累积态口径下仍有分歧：假绿 {false_green[:5]} / 假红 {false_red[:5]}"
        )


def test_accumulated_state_blocks_slot_conflict_without_seed():
    """同一槽位对的**未绑定**相：同伴也在这份 bindings 里（绑定值 = 它的默认脚）。

    与上一个用例的区别只在种子（这里只绑 `pid.GRAY_D7` 一个角色）——模拟用户先点了
    `pid.GRAY_D7 → PB6`（值 == 默认，写侧 no-op）再去动 `huidu.R3`。`huidu.R3`
    此刻**未绑定**，但整份 bindings 里同伴在，门禁就会拒，所以模型必须挡。
    """
    slugs = ["huidu", "pid"]
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, slugs).manifests
    seed = {"pid.GRAY_D7": "PB6"}
    assert _backend_ok_state(manifests, MSPM0, MSPM0_BOARD, seed)
    row = _rows(build_bindings_matrix(manifests, MSPM0, MSPM0_BOARD, seed))["huidu.R3"]
    assert not _selectable(row, "PA0", MSPM0_BOARD)
    assert not _backend_ok_state(
        manifests, MSPM0, MSPM0_BOARD, {**seed, "huidu.R3": "PA0"}
    ), "后端此刻本该拒（这条缝的事实前提）"
    assert _selectable(row, "PB6", MSPM0_BOARD)


def test_accumulated_state_allows_moving_whole_slot_group():
    """反向：整组还没动时，槽位谓词**不许**把搬家的第一步灰掉（不假红）。

    `huidu.R3` 与 `pid.GRAY_D7` 都还在默认 → 模型对 `huidu.R3 → PA0` 放行
    （门禁此刻也不拒：同伴未绑、走默认）；待同伴也搬到 PA0 后这一份才合法。
    """
    slugs = ["huidu", "pid"]
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, slugs).manifests
    seed: dict[str, str] = {}
    row = _rows(build_bindings_matrix(manifests, MSPM0, MSPM0_BOARD, seed))["huidu.R3"]
    assert row["constraint"] is None
    assert _selectable(row, "PA0", MSPM0_BOARD)
    assert _backend_ok_state(manifests, MSPM0, MSPM0_BOARD, {"huidu.R3": "PA0"})
    # 第二步：同伴跟到同脚 → 整份仍合法，且谓词此时指向 PA0
    moved = {"huidu.R3": "PA0", "pid.GRAY_D7": "PA0"}
    assert _backend_ok_state(manifests, MSPM0, MSPM0_BOARD, moved)
    assert _selectable(
        _rows(build_bindings_matrix(manifests, MSPM0, MSPM0_BOARD, {"huidu.R3": "PA0"}))[
            "pid.GRAY_D7"
        ],
        "PA0",
        MSPM0_BOARD,
    )


# ---------------------------------------------------------------------------
# 全库累积态相（工单 mspm0-slot-conflict/04）：修的就是工单 03「不做」里那条线索
# ---------------------------------------------------------------------------


def _full_library(platform):
    """全库展开（不选模块 = 全部模块在该平台的声明）——对拍的最大口径。"""
    return list_modules(LIBRARY_MODULES), BOARDS[platform]


@pytest.mark.parametrize("platform", [MSPM0, STM32])
def test_full_library_accumulated_state_has_no_divergence(platform):
    """**全库**（93 模块）累积态对拍：模型放行的一步改绑，整份回验后端必须收。

    工单 03 的「不做」条目记着这条线索：「全库（84 模块 / 176 角色）枚举已实测
    暴露 188 条 `pair` 类既有分歧——若将来要开全库相，先决定要不要给 uart 成对
    补跨角色谓词，否则那 188 条会当场变红」。用户拍板：补谓词（口径 = 严格镜像
    `_check_paired_role_instances`），本用例就是那条全库相。

    修前实测（`.scratch/mspm0-slot-conflict/probe_full_library_accumulated.py`）：

    - mspm0 空种子 4405 条样本 / **假绿 188**（全是 `pair`：as32 / debug_uart /
      hc05 / imu_uart / uwb_uart / fingerprint / zigbee 族…）；
    - stm32 空种子 5082 条样本 / **假绿 52**（同门禁，stm32 侧当年没记进工单）。

    修后两平台都归零（本用例断言）。样本下限锚（> 3000）防「选择集/库变小导致
    用例空转」——不钉死数字：库在长（真机审计时 84 模块，现在是 93）。
    """
    manifests, board = _full_library(platform)
    false_green, false_red, checked = _stepwise_false_greens(
        manifests, platform, board, {}
    )
    assert checked > 3000, f"{platform} 全库枚举样本太少（{checked}）"
    if false_green or false_red:
        pytest.fail(
            f"{platform} 全库累积态分歧：假绿 {false_green[:5]} / 假红 {false_red[:5]}"
        )


def test_full_library_default_seed_has_no_divergence():
    """默认脚种子（每角色显式绑回默认）下的全库分歧 = **已归零**，同样钉住。

    这一相与上一相的区别：种子把**每个**角色都放进 bindings，于是
    `_check_slot_conflicts` 的互斥面全开（工单 03 之前有 19 条：18 pair + 1 slot）。
    修完成对实例谓词后，mspm0 这一相也归零——**注意** `l298n.L298N_PWM_C0 → PB20`
    那条的判据是它自己的 pwm 两通道谓词而非槽位谓词（`l298n.L298N_PWM_C0` 与
    `step_motor.DCC_100_PWM2_C0` 默认同 PA14、同 C0 通道 = 同槽位，槽位谓词被
    优先级更高的成对谓词遮蔽——「一个 `constraint` 字段装不下两条并存谓词」是
    既有的结构性限制，口径 B 实测会露头 1 条）。
    """
    manifests, board = _full_library(MSPM0)
    seed = _default_pin_seed(manifests, MSPM0, board)
    assert _backend_ok_state(manifests, MSPM0, board, seed), "种子累积态被后端拒"
    false_green, false_red, checked = _stepwise_false_greens(
        manifests, MSPM0, board, seed
    )
    assert checked > 3000, f"枚举样本太少（{checked}）"
    if false_green or false_red:
        pytest.fail(
            f"默认脚种子下仍有分歧：假绿 {false_green[:5]} / 假红 {false_red[:5]}"
        )


# ---------------------------------------------------------------------------
# 成对联动搬的前端口径（工单 mspm0-slot-conflict/05）：对脚跟随的落点必须与后端同判据
# ---------------------------------------------------------------------------


def _pin_instances(board, pin_name, role_type) -> list[str]:
    """某脚某角色类型的实例名（`fx/pin-model.js` 的 `pinInstanceTokens` 同口径）。"""
    pin = board.pin_index.get(pin_name)
    if pin is None:
        return []
    prefix = role_type + ":"
    return [t[len(prefix):] for t in pin.capabilities if t.startswith(prefix)]


def _pair_relation(board, row, mate_row, candidate, pin_name) -> bool:
    """本脚候选（`pin_name`）与对脚脚（`candidate`）是否同实例。

    与后端 `_check_paired_role_instances` 同判据（两脚**有效实例集交集非空**，
    各自按本脚类型取实例）：pwm 是另一条门禁（`_check_mspm0_pwm_channel_pairs`，
    按基名比），本函数只服务 uart/i2c 那对。
    """
    mine = _pin_instances(board, pin_name, row["type"])
    theirs = _pin_instances(board, candidate, mate_row["type"])
    return bool(set(mine) & set(theirs))


def _frontend_pair_follow(model, board, role_key, pin_name, bindings):
    """`fx/pin-model.js` 的 `pinPairFollow` 判定链的 Python 镜像。

    逐条对应（改前端时必须同步改这里，否则本对拍失效）：
    ① 本角色那条成对实例谓词（唯一一条 `instance` + `pair`）；
    ② 对脚条目在场且有 `selectable`；
    ③ 对脚**原地不动**就成立（对脚当前脚与候选脚同实例）→ `same=True`；
    ④ 否则按对脚 `selectable` 顺序找「同实例 + 对脚自身其它谓词放行 + 未被占用」
       的落点，并**优先「与本脚同一份实例集」的那只**（板上成对脚彼此同实例集：
       点 PA23 时落 PA22 而不是板定义序更早的 PB18）——偏好只影响选哪只，不影响
       合法性，但「确定性落点」是本单验收的一部分（用例据此断言）。
    """
    row = next((r for r in model["roles"] if r["role"] == role_key), None)
    if row is None:
        return None
    pairs = [
        c for c in _constraints(row)
        if c.get("kind") == "instance" and c.get("pair")
    ]
    if len(pairs) != 1:
        return None
    pair = pairs[0]
    mate_key = pair["pair"]
    mate_row = next((r for r in model["roles"] if r["role"] == mate_key), None)
    if mate_row is None or not mate_row.get("selectable"):
        return None
    if row["type"] == "pwm":
        # pwm 两通道走另一条门禁（基名比 + 通道过滤），本函数不镜像它
        return None
    mate_now = bindings.get(mate_key) or mate_row["default"]
    if mate_now and _pair_relation(board, row, mate_row, mate_now, pin_name):
        return {"same": True, "mate": mate_key, "from": mate_now, "to": mate_now}
    moved = bindings.get(role_key) or row["default"]
    mine_set = sorted(_pin_instances(board, pin_name, row["type"]))
    first = None
    for candidate in mate_row["selectable"]:
        if not _pair_relation(board, row, mate_row, candidate, pin_name):
            continue
        if any(
            not _predicate_holds(c, mate_row, candidate, board)
            for c in _constraints(mate_row)
            if not (c.get("kind") == "instance" and c.get("pair"))
        ):
            continue
        holder = next((k for k, v in bindings.items() if v == candidate), None)
        if holder and holder not in (mate_key, role_key) and candidate != moved:
            continue
        landed = {
            "same": False, "mate": mate_key,
            "from": bindings.get(mate_key), "to": candidate,
        }
        if sorted(_pin_instances(board, candidate, mate_row["type"])) == mine_set:
            return landed
        if first is None:
            first = landed
    return first


def _frontend_state_after_move(model, board, role_key, pin_name, bindings):
    """前端一次点击之后的 bindings（`ui/generate-pins.js` 的 `bindRole` 镜像）：

    成对角色 = 同一次提交写两个 key（本脚 + 对脚落点），其余角色不动。
    """
    row = next((r for r in model["roles"] if r["role"] == role_key), None)
    follow = _frontend_pair_follow(model, board, role_key, pin_name, bindings)
    trial = {k: v for k, v in bindings.items() if k not in (role_key,)}
    if follow and not follow["same"]:
        trial.pop(follow["mate"], None)
    trial[role_key] = pin_name
    if follow and not follow["same"]:
        trial[follow["mate"]] = follow["to"]
    elif row is not None and not follow:
        return None       # 判据不成立：前端连点都不给点
    return trial


def _pair_move_parity(manifests, platform, board, seed=None):
    """全枚举「前端放行的成对搬」×『整份回验后端』，返回 (假绿, 假红, 样本)。

    假绿 = 前端放行（点得下去）而后端拒——工单 05 的核心不变式；假红 = 后端收而
    前端挡（模型过严，用户配不出来）。口径与既有累积态对拍一致：种子累积态出发，
    一次点击并入累积 bindings 后**整份**回验 `resolve_bindings`。
    """
    seed = dict(seed or {})
    model = build_bindings_matrix(manifests, platform, board, seed or None)
    false_green: list[tuple[str, str, str]] = []
    false_red: list[tuple[str, str]] = []
    checked = 0
    for row in model["roles"]:
        if row["type"] not in ("uart_tx", "uart_rx", "i2c_scl", "i2c_sda"):
            continue
        role = row["role"]
        for pin_name in row["selectable"]:
            if seed.get(role) == pin_name:
                continue
            trial = _frontend_state_after_move(model, board, role, pin_name, seed)
            if trial is None:
                continue
            checked += 1
            be_ok = _backend_ok_state(manifests, platform, board, trial)
            if not be_ok:
                false_green.append(
                    (role, pin_name, _backend_state_reason(manifests, platform, board, trial))
                )
            elif _frontend_pair_follow(model, board, role, pin_name, seed) is None:
                false_red.append((role, pin_name))
    return false_green, false_red, checked


def test_paired_move_frontend_matches_backend():
    """成对搬的**前端口径**（`pinPairFollow` 镜像）与后端逐条一致（0 假绿 / 0 假红）。

    这条是工单 05 的核心不变式：「点得下去 = 后端必收」。工单 04 之后模型严格镜像
    门禁，代价是成对角色在界面上**搬不动**（单角色绑一脚 → 必 400）；本单补的
    对脚跟随若算错落点（或漏判占用、漏算对脚自己的谓词），假绿会当场从这条露头。
    """
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, ["debug_uart", "as32"]).manifests
    false_green, false_red, checked = _pair_move_parity(
        manifests, MSPM0, MSPM0_BOARD
    )
    assert checked > 20, f"成对搬枚举样本太少（{checked}），守卫形同虚设"
    if false_green or false_red:
        pytest.fail(
            f"成对搬前后端与前端分歧：假绿 {false_green[:5]} / 假红 {false_red[:5]}"
        )


def test_paired_move_round_trip_from_default_seed():
    """真实用户节奏：从**全默认**出发，点一次成对搬走通、再点一次搬回来也走通。

    种子 = 两脚**显式绑回自己的默认脚**（`collectBindings` 在用户动过手脚之后的
    真实载荷形态，见 `_default_pin_seed`）——这正是工单 04 记账里「用户走不出第一步」
    的那一份：单脚搬必 400，而对脚跟随让「一搬一对」落在合法态上。
    两次点击都用**前端镜像**算出的 bindings，每一步整份回验后端。

    ⚠ 种子带**全库默认脚**时本相走不通（实测）：对脚的每个候选落点都被别角色的
    默认脚占着（如 UART2 的 RX 脚 PA24 被 `pid.GRAY_D1` 默认占、UART3 的 PB3 被
    `as32` 默认占、UART1 的 PA18 被 zigbee 默认占）→ 跟随恒 `None` → 一个可搬的脚
    都不给。这不是本单的缝（后端那一份绑定确实搬不动），是「全库默认脚铺满」的
    静态事实——真机上用户是**选了几个模块**再配脚，故本用例只用 `debug_uart`。
    """
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, ["debug_uart"]).manifests
    seed = _default_pin_seed(manifests, MSPM0, MSPM0_BOARD)
    assert _backend_ok_state(manifests, MSPM0, MSPM0_BOARD, seed), "种子累积态被后端拒"
    model = build_bindings_matrix(manifests, MSPM0, MSPM0_BOARD, seed)
    row = next(
        r for r in model["roles"] if r["role"] == "debug_uart.DEBUG_UART_TX"
    )
    # 第一次点击：选一个「对脚要跟过来」的脚（异实例）
    first = next(
        p for p in row["selectable"]
        if (follow := _frontend_pair_follow(model, MSPM0_BOARD, row["role"], p, seed))
        and not follow["same"]
    )
    first_state = _frontend_state_after_move(
        model, MSPM0_BOARD, row["role"], first, seed
    )
    assert _backend_ok_state(manifests, MSPM0, MSPM0_BOARD, first_state), (
        f"第一次点击后的整份绑定被后端拒：{first_state}"
    )
    assert first_state["debug_uart.DEBUG_UART_RX"] != "PA22", "对脚没跟过去"
    # 第二次点击：搬回默认脚——对脚此刻在别的实例上，得**跟回来**（回到 UART2 的
    # 某只 RX 脚：后端 `selectable` 序里 PA23 之后的首个合法落点，本用例不钉死是哪只）
    back = row["default"]
    model2 = build_bindings_matrix(manifests, MSPM0, MSPM0_BOARD, first_state)
    back_state = _frontend_state_after_move(
        model2, MSPM0_BOARD, row["role"], back, first_state
    )
    assert _backend_ok_state(manifests, MSPM0, MSPM0_BOARD, back_state), (
        f"搬回默认脚后的整份绑定被后端拒：{back_state}"
    )
    assert back_state[row["role"]] == back
    assert back_state["debug_uart.DEBUG_UART_RX"] in ("PA22", "PA24", "PB18"), (
        f"对脚没有跟回 UART2（默认实例）：{back_state}"
    )


def test_full_library_paired_move_has_no_divergence():
    """**全库**成对搬对拍（两平台）：mspm0 14 个 uart/i2c 对 + stm32 13 个 uart 对。

    量表（`.scratch/mspm0-slot-conflict/issues/05-paired-move-ui.md`）：mspm0 的
    对子**全部**在默认实例外还有第二个位（可搬，但必须成对搬）；stm32 的 uart 对
    每实例只有一对脚（原地即唯一解 → 跟随恒 `same`）、i2c 对不带实例 token
    （门禁跳过、模型不发谓词）——两侧都要零分歧。
    """
    for platform in (MSPM0, STM32):
        manifests, board = _full_library(platform)
        false_green, false_red, checked = _pair_move_parity(
            manifests, platform, board
        )
        # 样本下限（实测 mspm0 260 / stm32 78）：不钉死数字，只防「库/选择集一变
        # 用例空转而静默失效」——stm32 的 uart 对每实例只有一对脚，能搬的步数天然少。
        floor = 150 if platform == MSPM0 else 50
        assert checked > floor, f"{platform} 全库成对搬样本太少（{checked}）"
        if false_green or false_red:
            pytest.fail(
                f"{platform} 全库成对搬分歧："
                f"假绿 {false_green[:5]} / 假红 {false_red[:5]}"
            )


def test_paired_move_is_the_only_way_out_of_default_instance():
    """成对角色「单脚搬到别实例」仍然**必须被挡**（工单 04 的假绿不许回来）。

    三件事一起钉：
    ① `debug_uart.DEBUG_UART_TX → PA0`（UART0）：对脚走默认 PA22（UART2）跟不过
       去时是假绿——现在对脚**跟得过去**（PA1 = UART0 的 RX 脚）→ 放行，且一次
       点击写出的整份绑定后端必收（本单补的正是这条交互）；
    ② 对脚的合法落点**全被别的角色占着** → 模型当场挡住（不制造中间非法态）；
    ③ 后端对「只写本脚」的那一份仍拒——钉住「后端判据一字未动」。
    """
    manifests = resolve_selection(LIBRARY_MODULES, MSPM0, ["debug_uart"]).manifests
    model = build_bindings_matrix(manifests, MSPM0, MSPM0_BOARD, None)
    row = next(
        r for r in model["roles"] if r["role"] == "debug_uart.DEBUG_UART_TX"
    )
    assert row["default"] == "PA23"          # UART2
    # ① 一次点击 = 两脚一次写（本脚 + 对脚落点），整份后端收
    state = _frontend_state_after_move(model, MSPM0_BOARD, row["role"], "PA0", {})
    assert state == {
        "debug_uart.DEBUG_UART_TX": "PA0",
        "debug_uart.DEBUG_UART_RX": "PA1",
    }
    assert _backend_ok_state(manifests, MSPM0, MSPM0_BOARD, state)
    # ③ 旧交互唯一能走的那一步（只写本脚）后端仍然拒
    assert not _backend_ok_state(
        manifests, MSPM0, MSPM0_BOARD, {"debug_uart.DEBUG_UART_TX": "PA0"}
    )
    # ② 对脚的两只落点都被别的角色占着 → 挡（点不下去，而不是点了必 400）
    occupied = {"led.LED": "PA1", "beep.BEEP": "PA31"}
    assert _frontend_pair_follow(model, MSPM0_BOARD, row["role"], "PA0", occupied) is None
    assert _frontend_state_after_move(
        model, MSPM0_BOARD, row["role"], "PA0", occupied
    ) is None
    # 对照：对脚自己的位置（PA22 = UART2）不受影响 —— 同实例的脚照旧可点
    assert _selectable(row, "PA23", MSPM0_BOARD)
