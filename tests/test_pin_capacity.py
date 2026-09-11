"""引脚容量诊断的域模块接缝（工单 pin-capacity/01）。

为什么需要这个第二缝：门禁缝（`tests/test_generator.py`）只能覆盖**真实板**上出现过的
形态——真机样本里「引脚落点 ≤ 板上可用 IO 却仍无解」这一支从未出现（14 个样本里落点超
可用脚的才无解），但 spec 明确要求它有一句**不赖容量**的措辞。要直测那一支，只能用
假板再造一次「脚够、但合法共享仍解不开」的形态。

接缝 = `pin_capacity` 的两个公开纯函数（`diagnose_pin_capacity` /
`render_pin_capacity_diagnosis`）；判据本身仍是现成两件（`_role_entries` +
`auto_assign_bindings(resolve_default_conflicts=True)`），本文件不复制判定。
"""

from pathlib import Path

import pytest

from contest_generator.boards import Board, BoardPin
from contest_generator.library import list_modules
from contest_generator.pin_capacity import (
    diagnose_pin_capacity,
    render_pin_capacity_diagnosis,
)
from contest_generator.patchers import PLATFORM_MSPM0

ROOT = Path(__file__).resolve().parents[1]

# motor 的真实 mspm0 角色数（PA12/PA13 PB9/PA18 PB18/PA7 PA16/PA17 PB19/PB20）
MOTOR_ROLES = 10


def _manifests(*slugs: str):
    by_slug = {
        m.slug: m for m in list_modules(ROOT / "library" / "modules")
    }
    return [by_slug[slug] for slug in slugs]


def _board_with_io(count: int) -> Board:
    """假板：`count` 个统一能力的 io 脚（够落的脚数即 `count`，无板外默认脚）。

    能力集给全类型（gpio_out / gpio_in / enc / pwm 通道 / uart / i2c / adc）——本文件
    要测的是**容量分支**而不是能力校验，能力面的红证在 `tests/test_pin_bindings.py`。
    """
    caps = (
        "gpio_out",
        "gpio_in",
        "enc",
        "pwm:TIMA0_C0",
        "pwm:TIMA0_C1",
        "uart_tx:UART1",
        "uart_rx:UART1",
        "i2c_scl:I2C0",
        "i2c_sda:I2C0",
        "adc",
    )
    pins = tuple(
        BoardPin(name=f"P{i}", kind="io", x=0, y=i, side="left", capabilities=caps)
        for i in range(count)
    )
    return Board(
        board_id="fake-mspm0",
        name="假板",
        platform=PLATFORM_MSPM0,
        pins=pins,
        pin_index={pin.name: pin for pin in pins},
    )


def _bind_all_motor_pins(board: Board, *, servo_pin: str = "P10") -> dict[str, str]:
    """把 motor 的 10 个角色显式绑到假板前 10 脚、servo 绑到指定脚。

    为什么要显式绑：motor/servo 的**声明默认脚**（PA12… / PA7）都不在假板上，不显式绑
    就没有「落点」可言（`_role_entries` 只收有生效脚的角色）——假板形态必须自己给出布线。
    """
    slugs = ("PWMAB_C0", "PWMAB_C1", "AIN1", "AIN2", "BIN1", "BIN2", "AA", "AB", "BA", "BB")
    bindings = {f"motor.{role}": f"P{index}" for index, role in enumerate(slugs)}
    bindings["servo.SERVO_PWM_C0"] = servo_pin
    return bindings


def test_diagnose_reports_groups_not_roles_and_pin_based_free_counts():
    """判定量的口径（工单 pin-capacity/01）：

    `moved_groups` 是**组**数、`occupied` / `free` / `free_after_moves` 一律按**脚**算、
    `slots` 按**角色落点**算——motor（10 角色）+ servo（1 角色）在 12 脚假板上把
    servo 摆到 motor.BIN2 同脚：1 组冲突、11 个落点占 10 脚（其中 2 角色共脚）。
    显式绑定 = 用户明确选择，求解器只标注不搬 → 该组留在 `unresolved_roles` 里。
    """
    board = _board_with_io(MOTOR_ROLES + 2)  # 12 脚
    report = diagnose_pin_capacity(
        _manifests("motor", "servo"),
        PLATFORM_MSPM0,
        board,
        _bind_all_motor_pins(board, servo_pin="P5"),  # 与 motor.BIN2 同脚
    )

    assert report.modules == 2
    assert report.slots == MOTOR_ROLES + 1  # 角色落点数（上界口径）
    assert report.board_io == MOTOR_ROLES + 2
    assert report.occupied == MOTOR_ROLES  # 脚口径：11 个落点占 10 脚
    assert report.free == 2
    assert report.conflict_groups == 1
    assert report.moved_groups == 0  # 组数语义：显式绑定不被搬 → 0 组被解开
    assert report.unresolved_groups == 1
    assert report.unresolved_roles == (("motor.BIN2", "servo.SERVO_PWM_C0"),)
    assert report.unresolved_modules == ("motor", "servo")
    assert report.free_after_moves == 2  # 脚口径：搬动前后都按脚算
    assert report.solvable is False


def test_diagnose_unresolved_with_enough_pins_avoids_capacity_story():
    """防御支（spec 第 3 条口径）：引脚落点**不超**板上可用 IO、却仍有解不开的组时，
    文案必须说「与引脚数量无关，卡在能力/实例分配」，**不得**声称「物理不可实现」。

    真机 14 个样本里没有这一支（落点超容量的才无解），只能靠假板读它——而它与
    「物理不可实现」支的分野正是 `free_after_moves > 0`：还有空闲脚能搬家当，就不该
    把账算到板容量上。
    """
    board = _board_with_io(MOTOR_ROLES + 2)  # 12 脚
    report = diagnose_pin_capacity(
        _manifests("motor", "servo"),
        PLATFORM_MSPM0,
        board,
        _bind_all_motor_pins(board, servo_pin="P5"),
    )

    assert report.slots == MOTOR_ROLES + 1 <= report.board_io
    assert report.unresolved_groups == 1
    assert report.free_after_moves > 0

    text = render_pin_capacity_diagnosis(report, board.name)
    assert "与引脚数量无关" in text
    assert "卡在引脚能力 / 外设实例分配上" in text
    assert "物理不可实现" not in text
    assert "至少要去掉" not in text
