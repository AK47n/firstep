"""软 I2C 参数化（工单 pin-unlock-stm32/02）：ml_i2c/ml_oled 宏迁 pin_config.h
+ 能力 token 去实例化 + 共享端口宏异值门禁。

契约（ADR 0011 决策 3/4）：软 I2C 参数化后 stm32 i2c_scl/i2c_sda token 无实例
（总线身份在宏里不在 token 里）——strict-all 机器自然降级类型级，i2c 角色可
绑任意 io 脚（pin_bindings.py 零改动）；渲染层同 `_GPIO/_PORT` 尾形宏的两条
改动绑定值不同 → PinBindingError 400（SCL/SDA 须同口），同值（同端口）放行。
红证 = 异口 400 / 同口放行；绿证 = 三宏值断言 + 默认逐字节契约（新母版）。
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from contest_generator.boards import (
    BOARDS_DIR,
    board_pin,
    load_boards,
    pin_capability_instances,
)
from contest_generator.library import list_modules
from contest_generator.pin_bindings import (
    PinBindingError,
    ResolvedBinding,
    resolve_bindings,
)
from contest_generator.pinwriter import PIN_CONFIG_FILENAME, render_pin_config

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
LIBRARY_MODULES = LIBRARY_ROOT / "modules"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}
ALL_MANIFESTS = list_modules(LIBRARY_MODULES)
STM32_MASTER_PIN_CONFIG = (STM32_MASTER / PIN_CONFIG_FILENAME).read_text(
    encoding="utf-8", newline=""
)


def _resolve(platform: str, bindings: dict[str, str]) -> tuple[ResolvedBinding, ...]:
    return resolve_bindings(ALL_MANIFESTS, platform, BOARDS[platform], bindings)


def _bind(role_key: str, pin: str) -> ResolvedBinding:
    """stm32 渲染器测试用：取角色在 stm32 平台的声明（同 id 在 mspm0 也有
    声明时取错平台会拿不到 macros）。实例推导与 resolve 同源。"""
    slug, role_id = role_key.split(".")
    for manifest in ALL_MANIFESTS:
        if manifest.slug != slug:
            continue
        entry = manifest.platforms.get("stm32")
        if entry is None:
            continue
        for decl in entry.pins:
            if decl.id == role_id:
                bound_pin = BOARDS["stm32"].pin_index.get(pin)
                default_pin = BOARDS["stm32"].pin_index.get(decl.default)
                instances = (
                    pin_capability_instances(bound_pin, decl.type)
                    if decl.type == "pwm" and bound_pin is not None
                    else (
                        pin_capability_instances(default_pin, decl.type)
                        if default_pin is not None
                        else ()
                    )
                )
                return ResolvedBinding(
                    slug=slug,
                    declaration=decl,
                    pin=pin,
                    instances=instances,
                )
    raise AssertionError(f"未找到 stm32 角色 {role_key}")


# ---------------------------------------------------------------------------
# 红证：共享端口宏异值 400（SCL/SDA 绑到不同端口）
# ---------------------------------------------------------------------------


def test_mpu6050_cross_port_binding_rejected():
    """SCL→PA5（GPIO_A）、SDA→PB6（GPIO_B）都写 I2C_GPIO 但值不同 → 400
    中文（一根总线不可分属两个端口）。"""
    with pytest.raises(PinBindingError, match="共享端口宏 I2C_GPIO"):
        render_pin_config(
            STM32_MASTER_PIN_CONFIG,
            _resolve(
                "stm32",
                {
                    "ml_mpu6050.MPU6050_SCL": "PA5",
                    "ml_mpu6050.MPU6050_SDA": "PB6",
                },
            ),
        )


def test_oled_cross_port_binding_rejected():
    """OLED_SCL→PA5、OLED_SDA→PB6 都写 OLED_GPIO 值不同 → 400。"""
    with pytest.raises(PinBindingError, match="共享端口宏 OLED_GPIO"):
        render_pin_config(
            STM32_MASTER_PIN_CONFIG,
            _resolve(
                "stm32",
                {"oled.OLED_SCL": "PA5", "oled.OLED_SDA": "PB6"},
            ),
        )


# ---------------------------------------------------------------------------
# 绿证：同口放行 + 三宏值断言
# ---------------------------------------------------------------------------


def test_mpu6050_same_port_binding_renders_three_macros():
    """SCL/SDA 同绑 PA5/PA6（GPIO_A）→ 放行且只变两行：I2C_SCL_GPIO_Pin
    Pin_5、I2C_SDA_GPIO_Pin Pin_6（I2C_GPIO 默认已 GPIO_A = 工单 05 新基线，
    同值不写）。"""
    out = render_pin_config(
        STM32_MASTER_PIN_CONFIG,
        _resolve(
            "stm32",
            {"ml_mpu6050.MPU6050_SCL": "PA5", "ml_mpu6050.MPU6050_SDA": "PA6"},
        ),
    )
    before = STM32_MASTER_PIN_CONFIG.splitlines(True)
    after = out.splitlines(True)
    assert len(before) == len(after)
    changed = [after[i] for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert changed == [
        "#define I2C_SCL_GPIO_Pin  Pin_5\r\n",
        "#define I2C_SDA_GPIO_Pin  Pin_6\r\n",
    ]


def test_oled_same_port_binding_renders_three_macros():
    """OLED_SCL/SDA 同绑 PB6/PB7 → OLED_GPIO GPIO_B + 两 Pin 宏。"""
    out = render_pin_config(
        STM32_MASTER_PIN_CONFIG,
        _resolve(
            "stm32",
            {"oled.OLED_SCL": "PB6", "oled.OLED_SDA": "PB7"},
        ),
    )
    assert "#define OLED_GPIO         GPIO_B\r\n" in out
    assert "#define OLED_SCL_Pin      Pin_6\r\n" in out
    assert "#define OLED_SDA_Pin      Pin_7\r\n" in out


def test_mpu6050_and_oled_same_port_render_together():
    """两族总线同绑 PA5/PA6（同脚共享合法，spec v1）：各自共享宏同值 → 不拦。"""
    out = render_pin_config(
        STM32_MASTER_PIN_CONFIG,
        _resolve(
            "stm32",
            {
                "ml_mpu6050.MPU6050_SCL": "PA5",
                "ml_mpu6050.MPU6050_SDA": "PA6",
                "oled.OLED_SCL": "PA5",
                "oled.OLED_SDA": "PA6",
            },
        ),
    )
    assert "#define I2C_GPIO          GPIO_A\r\n" in out
    assert "#define OLED_GPIO         GPIO_A\r\n" in out


# ---------------------------------------------------------------------------
# 绿证：默认逐字节契约（新母版）+ 母版六宏值钉死
# ---------------------------------------------------------------------------


def test_default_bindings_byte_identical():
    """绑定值 = 默认值（mpu6050 PA11/12、oled PB8/9）= no-op → 与母版逐字节
    一致（新母版 = 已含 6 个软 I2C 宏，工单 05 后 mpu6050 默认 PA11/12）。"""
    out = render_pin_config(
        STM32_MASTER_PIN_CONFIG,
        _resolve(
            "stm32",
            {
                "ml_mpu6050.MPU6050_SCL": "PA11",
                "ml_mpu6050.MPU6050_SDA": "PA12",
                "oled.OLED_SCL": "PB8",
                "oled.OLED_SDA": "PB9",
            },
        ),
    )
    assert out == STM32_MASTER_PIN_CONFIG


def test_master_pin_config_has_six_i2c_macros_with_original_values():
    """六宏逐字节钉死（工单 05 后 mpu6050 = GPIO_A Pin_11/12、oled = GPIO_B
    Pin_8/9）。"""
    for line in (
        "#define I2C_GPIO          GPIO_A\r\n",
        "#define I2C_SCL_GPIO_Pin  Pin_11\r\n",
        "#define I2C_SDA_GPIO_Pin  Pin_12\r\n",
        "#define OLED_GPIO         GPIO_B\r\n",
        "#define OLED_SCL_Pin      Pin_8\r\n",
        "#define OLED_SDA_Pin      Pin_9\r\n",
    ):
        assert line in STM32_MASTER_PIN_CONFIG, f"母版缺行：{line!r}"


# ---------------------------------------------------------------------------
# 板定义不变量：i2c token 去实例化
# ---------------------------------------------------------------------------


def test_stm32_board_i2c_tokens_plain_on_all_io_pins():
    """全部 32 个 io 脚有类型级 i2c_scl/i2c_sda token；无任何带实例 token
    （i2c_scl:ml_i2c 等四类已删——软 I2C 参数化后实例无意义，ADR 0011）。"""
    stm32 = BOARDS["stm32"]
    io_pins = [p for p in stm32.pins if p.kind == "io"]
    assert len(io_pins) == 32
    for pin in io_pins:
        assert "i2c_scl" in pin.capabilities, f"{pin.name} 缺 i2c_scl"
        assert "i2c_sda" in pin.capabilities, f"{pin.name} 缺 i2c_sda"
        for token in pin.capabilities:
            assert not token.startswith(("i2c_scl:", "i2c_sda:")), (
                f"{pin.name} 残留实例 token {token}"
            )


# ---------------------------------------------------------------------------
# resolve 层：strict-all 机器自然降级类型级（pin_bindings.py 零改动）
# ---------------------------------------------------------------------------


def test_resolve_i2c_type_level_any_io_pin():
    """i2c 角色绑任意 io 脚合法且实例空（旧行为：i2c_scl:ml_i2c 实例锁死
    PB10/11）。"""
    a = _resolve("stm32", {"ml_mpu6050.MPU6050_SCL": "PA5"})
    assert a[0].pin == "PA5"
    assert a[0].instances == ()
    b = _resolve("stm32", {"ml_mpu6050.MPU6050_SDA": "PC13"})
    assert b[0].pin == "PC13"
    assert b[0].instances == ()


# ---------------------------------------------------------------------------
# 旧防御保留：宏不在 pin_config.h 大声失败
# ---------------------------------------------------------------------------


def test_render_missing_macro_defense_kept():
    """宏不在母版 pin_config.h = 数据不在渲染器可控范围 → 大声失败（软 I2C
    宏迁入后此路真机不可达，用合成声明直测防御路径仍在）。"""
    decl = replace(
        _bind("ml_mpu6050.MPU6050_SCL", "PA5").declaration,
        macros=("NOT_IN_PIN_CONFIG",),
    )
    binding = ResolvedBinding(
        slug="ml_mpu6050", declaration=decl, pin="PA5", instances=()
    )
    with pytest.raises(PinBindingError, match="NOT_IN_PIN_CONFIG"):
        render_pin_config(STM32_MASTER_PIN_CONFIG, (binding,))
