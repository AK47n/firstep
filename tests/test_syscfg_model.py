"""mspm0.syscfg 文件模型（架构评审 ② 工单 01）：解析层 + 槽位原语 + 逐字节契约。

契约（spec syscfg 文件模型）：
- 新模块独占 syscfg 文法（实例声明 addInstance / 模块声明 addModule /
  `$assign` 赋值）、一次解析为结构化模型、一个槽位身份原语。
- 槽位身份原语对 GPIO 组（associatedPins[n].pin）、外设（txPin/sclPin/
  ccp0Pin 等）两类路径返回正确判定（唯一实现，工单 03 起 pinwriter 已删旧副本）。
- 关键断言：新模块 parse+prune+rewrite 输出与旧 prune→rewrite 顺序逐字节一致。
- MSPM0_SYSCFG_FILENAME 单源在新模块（pinwriter 旧定义已迁走，工单 04）。
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

from contest_generator.boards import BOARDS_DIR, load_boards
from contest_generator.library import list_modules
from contest_generator.pin_bindings import resolve_bindings
from contest_generator.pinwriter import rewrite_syscfg
from contest_generator.syscfg_instances import INSTANCE_CONSUMERS
from contest_generator.syscfg_model import (
    MSPM0_SYSCFG_FILENAME,
    parse_syscfg,
    syscfg_path_matches,
)
from contest_generator.syscfg_prune import prune_syscfg

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
LIBRARY_MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"

BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}
ALL_MANIFESTS = list_modules(LIBRARY_MODULES)
MSPM0_MASTER_SYSCFG = (MSPM0_MASTER / MSPM0_SYSCFG_FILENAME).read_text(
    encoding="utf-8", newline=""
)

ALL_SLUGS = sorted(
    {s for consumers in INSTANCE_CONSUMERS.values() for s in consumers}
)

# UART 换位（真机场景 ② 同款，test_pin_unlock_mspm0_same 复用口径）。
UART_SWAP_BINDINGS = {
    "imu_uart.IMU601_TX": "PA8",
    "imu_uart.IMU601_RX": "PA9",
    "digit_uart.DIGIT_UART_TX": "PA28",
    "digit_uart.DIGIT_UART_RX": "PA31",
    "coord_detect.COORD_DETECT_UART_TX": "PA28",
    "coord_detect.COORD_DETECT_UART_RX": "PA31",
}


def _resolve(bindings: dict[str, str]):
    return resolve_bindings(ALL_MANIFESTS, "mspm0", BOARDS["mspm0"], bindings)


# ---------------------------------------------------------------------------
# 解析层：实例集 + $assign 落点集与旧推导一致
# ---------------------------------------------------------------------------


def test_parse_produces_instance_set_consistent_with_prune():
    """模型实例集 == prune 消费的 INSTANCE_CONSUMERS 键；实例→模块映射与母版
    addInstance 声明逐条一致（独立正则直扫对照）。"""
    model = parse_syscfg(MSPM0_MASTER_SYSCFG)
    assert set(model.instances) == set(INSTANCE_CONSUMERS)
    expected = {}
    for line in MSPM0_MASTER_SYSCFG.splitlines(True):
        m = re.match(
            r"^\s*const\s+([A-Za-z_]\w*)\s*=\s*([A-Za-z_]\w*)\.addInstance\(\);?",
            line,
        )
        if m:
            expected[m.group(1)] = m.group(2)
    assert {name: inst.module for name, inst in model.instances.items()} == expected


def test_parse_produces_assign_sites_consistent_with_rewrite():
    """模型 $assign 落点集（路径+引脚值）与 rewrite 的正则直扫一致；行号指向
    对应行。"""
    model = parse_syscfg(MSPM0_MASTER_SYSCFG)
    expected = {
        (m.group(1), m.group(2))
        for line in MSPM0_MASTER_SYSCFG.splitlines(True)
        if (m := re.match(r'^\s*(.+?)\.\$assign\s*=\s*"([A-Za-z0-9]+)"', line))
    }
    assert {(a.path, a.pin) for a in model.assigns} == expected
    assert expected, "母版应含 $assign 行（测试前置失效）"
    for assign in model.assigns:
        line = model.lines[assign.line]
        assert assign.path in line and f'"{assign.pin}"' in line


def test_serialize_roundtrip_identity():
    """parse→serialize 是恒等变换（文本进 / 文本出无损）。"""
    assert parse_syscfg(MSPM0_MASTER_SYSCFG).to_text() == MSPM0_MASTER_SYSCFG


# ---------------------------------------------------------------------------
# 槽位身份原语：显式判例（唯一的槽位匹配实现已在文件模型）
# ---------------------------------------------------------------------------


def test_slot_path_matches_spot_cases():
    """显式判例（可读性 + 数据漂移哨兵）：gpio 组认 slug 消费实例、外设认
    尾字段、pwm 分 C0/C1 通道。"""
    cases = [
        ("gpio_out", "MOTOR_A_DIR", "motor", "DC_MOTOR.associatedPins[0].pin", True),
        ("gpio_in", "R3", "huidu", "HUIDU.associatedPins[6].pin", True),
        ("gpio_out", "MOTOR_A_DIR", "motor", "HUIDU.associatedPins[0].pin", False),
        ("enc", "MOTOR_A_ENC", "motor", "DC_MOTOR.associatedPins[4].pin", True),
        ("uart_tx", "IMU601_TX", "imu_uart", "IMU601.peripheral.txPin", True),
        ("uart_tx", "IMU601_TX", "imu_uart", "DIGIT_UART.peripheral.txPin", False),
        ("i2c_scl", "OLED_SCL", "oled", "OLED.peripheral.sclPin", True),
        ("i2c_sda", "OLED_SDA", "oled", "OLED.peripheral.sdaPin", True),
        ("pwm", "PWMAB_C0", "motor", "PWMAB.peripheral.ccp0Pin", True),
        ("pwm", "PWMAB_C0", "motor", "PWMAB.peripheral.ccp1Pin", False),
        ("pwm", "PWMAB_C1", "motor", "PWMAB.peripheral.ccp1Pin", True),
        ("pwm", "DCC_100_PWM2_C0", "step_motor", "DCC_100_PWM2.peripheral.ccp0Pin", True),
    ]
    for decl_type, role_id, slug, path, expected in cases:
        assert syscfg_path_matches(decl_type, role_id, slug, path) is expected, (
            f"{slug}.{role_id} vs {path}"
        )


# ---------------------------------------------------------------------------
# 逐字节契约：新模块 parse+prune+rewrite == 旧 prune→rewrite
# ---------------------------------------------------------------------------


def _model_pipeline(selected: list[str], resolved) -> str:
    return (
        parse_syscfg(MSPM0_MASTER_SYSCFG)
        .prune(selected)
        .rewrite(resolved)
        .to_text()
    )


def _old_pipeline(selected: list[str], resolved) -> str:
    return rewrite_syscfg(prune_syscfg(MSPM0_MASTER_SYSCFG, selected), resolved)


def test_pipeline_byte_identical_prune_only():
    """无绑定：parse+prune 与旧 prune 逐字节一致（空选/全选/单模块/共享实例）。"""
    for selected in (
        [],
        ALL_SLUGS,
        ["motor"],
        ["led"],
        ["huidu", "pid"],
        ["imu_uart", "digit_uart", "coord_detect", "uwb_uart", "debug_uart",
         "zigbee_uart", "zigbee_uart_key"],
    ):
        assert _model_pipeline(selected, ()) == _old_pipeline(selected, ())


def test_pipeline_byte_identical_with_bindings():
    """带绑定：parse+prune+rewrite 与旧 prune→rewrite 逐字节一致——gpio 组 /
    默认重叠定位 / uart 换位 / i2c 换实例 / pwm 同族与跨族联动全覆盖。"""
    for selected, bindings in (
        (["led"], {"led.LED": "PA12"}),  # 裁剪 + 保留模块绑定交互
        (ALL_SLUGS, {"huidu.R3": "PA27"}),
        (ALL_SLUGS, {"step_motor.STEP_MOTOR_SLP2": "PB2"}),
        (ALL_SLUGS, UART_SWAP_BINDINGS),
        (ALL_SLUGS, {"oled.OLED_SCL": "PA17"}),
        (ALL_SLUGS, {"oled.OLED_SCL": "PA1", "oled.OLED_SDA": "PA0"}),
        (ALL_SLUGS, {"motor.PWMAB_C0": "PA23"}),
        (ALL_SLUGS, {"motor.PWMAB_C0": "PA14", "motor.PWMAB_C1": "PA25"}),
        (ALL_SLUGS, {"motor.PWMAB_C0": "PA8", "motor.PWMAB_C1": "PA9"}),
    ):
        resolved = _resolve(bindings)
        assert _model_pipeline(selected, resolved) == _old_pipeline(
            selected, resolved
        ), f"selected={selected} bindings={bindings}"


# ---------------------------------------------------------------------------
# 文件名常量：单源在新模块（兼容期结束）
# ---------------------------------------------------------------------------


def test_mspm0_syscfg_filename_single_source_in_model():
    """文件名常量单源：值对 + pinwriter 旧定义已删（工单 04 迁走兼容期副本）。"""
    assert MSPM0_SYSCFG_FILENAME == "mspm0.syscfg"
    pinwriter_source = Path(
        importlib.import_module("contest_generator.pinwriter").__file__
    ).read_text(encoding="utf-8")
    assert "MSPM0_SYSCFG_FILENAME =" not in pinwriter_source
