"""manifest pins 声明（工单 pin-board-config/01 B/C）：模型校验 + 真库不变量。

词表单源 = manifest.PIN_ROLE_TYPES（boards 能力 token 与 pins 声明共用）。
真库不变量（防回退）：默认值 = 现值——stm32 默认 = pin_config.h 宏值、
mspm0 默认 = 母版 mspm0.syscfg 的 $assign；stm32 声明的 macros 都必须在
母版 pin_config.h 中定义；默认引脚必须在对应板定义上且能力集含该角色类型；
板外默认（HUIDU R3/R4 = PB4/PB5 不在排针）合法保留；模块 code 注释剥离后
零引脚字面量（C 迁移验收 grep 的 pytest 化）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.boards import (
    BOARDS_DIR,
    board_pin,
    load_boards,
    pin_capability_instances,
    pin_supports,
)
from contest_generator.clex import strip_comments
from contest_generator.manifest import (
    PIN_ROLE_TYPES,
    ManifestError,
    ModuleManifest,
    PinDeclaration,
)

LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"
STM32_MASTER = Path(__file__).resolve().parents[1] / "library" / "masters" / "stm32"
MSPM0_MASTER = Path(__file__).resolve().parents[1] / "library" / "masters" / "mspm0"

# 平台 → 板定义（板 JSON 是板图/能力集单源）
BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}


def _all_declarations() -> list[tuple[str, str, PinDeclaration]]:
    """(模块 slug, 平台, 声明) 全库遍历——任一条损坏即本文件多数用例红。"""
    result: list[tuple[str, str, PinDeclaration]] = []
    for module_dir in sorted(LIBRARY_MODULES.iterdir()):
        if not module_dir.is_dir():
            continue
        manifest = ModuleManifest.load(module_dir)
        for platform, entry in manifest.platforms.items():
            for pin in entry.pins:
                result.append((manifest.slug, platform, pin))
    return result


ALL_DECLARATIONS = _all_declarations()


# ---------------------------------------------------------------------------
# 模型校验
# ---------------------------------------------------------------------------


def test_pin_declaration_roundtrip():
    raw = {
        "id": "MOTOR_A_PWM",
        "type": "pwm",
        "default": "PA0",
        "required": True,
        "macros": ["MOTOR_A_PWM_TIM", "MOTOR_A_PWM_CH"],
    }
    manifest = ModuleManifest.from_dict(
        {
            "slug": "motor",
            "description": "d",
            "platforms": {"stm32": {"files": [], "pins": [raw]}},
        }
    )
    pin = manifest.platforms["stm32"].pins[0]
    assert pin.id == "MOTOR_A_PWM"
    assert pin.type == "pwm"
    assert pin.default == "PA0"
    assert pin.label == ""  # 缺省 = id（to_dict 时落 id）
    assert pin.required is True
    assert pin.macros == ("MOTOR_A_PWM_TIM", "MOTOR_A_PWM_CH")
    # 序列化 → 反序列化保持
    again = ModuleManifest.from_dict(manifest.to_dict())
    assert again.platforms["stm32"].pins == manifest.platforms["stm32"].pins
    assert again.to_dict()["platforms"]["stm32"]["pins"][0]["label"] == "MOTOR_A_PWM"


@pytest.mark.parametrize(
    "bad_pin",
    [
        {"id": "", "type": "pwm", "default": "PA0"},  # id 空
        {"id": "P", "type": "can_tx", "default": "PA0"},  # type 不在词表
        {"id": "P", "type": "pwm", "default": ""},  # default 空
        {"id": "P", "type": "pwm", "default": "PA0", "required": "yes"},  # required 非布尔
        {"id": "P", "type": "pwm", "default": "PA0", "macros": "X"},  # macros 非数组
        {"id": "P", "type": "pwm", "default": "PA0", "macros": [""]},  # 宏名空
    ],
)
def test_pin_declaration_rejects_bad_fields(bad_pin):
    with pytest.raises(ManifestError):
        ModuleManifest.from_dict(
            {
                "slug": "m",
                "description": "d",
                "platforms": {"stm32": {"files": [], "pins": [bad_pin]}},
            }
        )


def test_pin_declaration_rejects_duplicate_id():
    with pytest.raises(ManifestError):
        ModuleManifest.from_dict(
            {
                "slug": "m",
                "description": "d",
                "platforms": {
                    "stm32": {
                        "files": [],
                        "pins": [
                            {"id": "P", "type": "pwm", "default": "PA0"},
                            {"id": "P", "type": "gpio_out", "default": "PA1"},
                        ],
                    }
                },
            }
        )


def test_pins_optional_for_legacy_entries():
    manifest = ModuleManifest.from_dict(
        {"slug": "m", "description": "d", "platforms": {"stm32": {"files": []}}}
    )
    assert manifest.platforms["stm32"].pins == ()


def test_role_type_vocabulary_is_source_of_both_layers():
    """词表单源：boards 能力 token 类型与 manifest pins 类型同吃一张表。"""
    assert isinstance(PIN_ROLE_TYPES, tuple) and PIN_ROLE_TYPES
    for board in BOARDS.values():
        for pin in board.pins:
            for token in pin.capabilities:
                assert token.split(":")[0] in PIN_ROLE_TYPES
    for _, _, pin in ALL_DECLARATIONS:
        assert pin.type in PIN_ROLE_TYPES


# ---------------------------------------------------------------------------
# 真库不变量：默认值 = 现值
# ---------------------------------------------------------------------------


def _pin_config_defines() -> dict[str, str]:
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    defines: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"\s*#define\s+([A-Za-z_]\w*)\s+(.*?)(?:\s+/\*|$)", line)
        if m:
            defines[m.group(1)] = m.group(2).strip()
    return defines


# 迁移后 pin_config.h 宏值钉死（默认值零变化 = 迁移前硬编码原值）
STM32_MACRO_VALUES = {
    # motor（既有，21F 原值）
    "MOTOR_A_PWM_TIM": "TIM_2",
    "MOTOR_A_PWM_CH": "TIM2_CH1",
    "MOTOR_A_DIR_PORT": "GPIO_A",
    "MOTOR_A_DIR_PIN": "Pin_6",
    "MOTOR_A_ENC_EXTI": "EXTI_PB5",
    "MOTOR_A_ENC_LINE": "5",
    "MOTOR_A_ENC_DIR_PORT": "GPIO_B",
    "MOTOR_A_ENC_DIR_PIN": "Pin_4",
    "MOTOR_B_ENC_EXTI": "EXTI_PA4",
    "MOTOR_B_ENC_LINE": "4",
    # gray_track（工单 pin-full-unlock/05 后：D1-4 PB12-15、D5 PA8、D6-8 PB3/PB6/PB7）
    "GRAY_D1_PORT": "GPIO_B",
    "GRAY_D1_PIN": "Pin_12",
    "GRAY_D5_PORT": "GPIO_A",
    "GRAY_D5_PIN": "Pin_8",
    "GRAY_D6_PORT": "GPIO_B",
    "GRAY_D6_PIN": "Pin_3",
    "GRAY_D7_PORT": "GPIO_B",
    "GRAY_D7_PIN": "Pin_6",
    "GRAY_D8_PORT": "GPIO_B",
    "GRAY_D8_PIN": "Pin_7",
    # uart 实例宏（迁移前硬编码 UART_1/UART_2 + USART1/2 寄存器）
    "DIGIT_UART": "UART_1",
    "DIGIT_UART_INST": "USART1",
    "BALL_DETECT_UART": "UART_1",
    "BALL_DETECT_UART_INST": "USART1",
    "DEBUG_UART": "UART_2",
    "DEBUG_UART_INST": "USART2",
    # uart 引脚宏（工单 pin-full-unlock/02：值 = ml_uart switch 表原值不变）
    "DIGIT_UART_TX_GPIO": "GPIO_A",
    "DIGIT_UART_TX_Pin": "Pin_9",
    "DIGIT_UART_RX_GPIO": "GPIO_A",
    "DIGIT_UART_RX_Pin": "Pin_10",
    "BALL_DETECT_UART_TX_GPIO": "GPIO_A",
    "BALL_DETECT_UART_TX_Pin": "Pin_9",
    "BALL_DETECT_UART_RX_GPIO": "GPIO_A",
    "BALL_DETECT_UART_RX_Pin": "Pin_10",
    "DEBUG_UART_TX_GPIO": "GPIO_A",
    "DEBUG_UART_TX_Pin": "Pin_2",
    "DEBUG_UART_RX_GPIO": "GPIO_A",
    "DEBUG_UART_RX_Pin": "Pin_3",
    # config.h 并入（LED/BUZZER/DIP/UWB/ZIGBEE 原值）
    "LED_PORT": "GPIO_C",
    "LED_RED_PIN": "Pin_13",
    "LED_YELLOW_PIN": "Pin_14",
    "LED_GREEN_PIN": "Pin_15",
    "BUZZER_GPIO": "GPIO_A",
    "BUZZER_PIN": "Pin_15",
    "DIP_GPIO": "GPIO_B",
    "DIP_PIN0": "Pin_12",
    "DIP_PIN3": "Pin_15",
    "UWB_UART": "UART_1",
    "UWB_UART_INST": "USART1",
    "ZIGBEE_UART": "UART_3",
    "ZIGBEE_UART_INST": "USART3",
    "UWB_UART_TX_GPIO": "GPIO_A",
    "UWB_UART_TX_Pin": "Pin_9",
    "UWB_UART_RX_GPIO": "GPIO_A",
    "UWB_UART_RX_Pin": "Pin_10",
    "ZIGBEE_UART_TX_GPIO": "GPIO_B",
    "ZIGBEE_UART_TX_Pin": "Pin_10",
    "ZIGBEE_UART_RX_GPIO": "GPIO_B",
    "ZIGBEE_UART_RX_Pin": "Pin_11",
    # UART 接收中断聚合（isr.c USARTx_IRQHandler 调用；默认分组）
    "USART1_IRQ_CALLS": (
        "digit_uart_rx_handler(); ball_detect_rx_handler(); uwb_rx_handler();"
    ),
    "USART2_IRQ_CALLS": "debug_uart_rx_handler();",
    "USART3_IRQ_CALLS": "zigbee_rx_handler();",
    # 软 I2C（工单 pin-full-unlock/05：mpu6050 离 PB10/11 让位 Zigbee → PA11/PA12）
    "I2C_GPIO": "GPIO_A",
    "I2C_SCL_GPIO_Pin": "Pin_11",
    "I2C_SDA_GPIO_Pin": "Pin_12",
    "OLED_GPIO": "GPIO_B",
    "OLED_SCL_Pin": "Pin_8",
    "OLED_SDA_Pin": "Pin_9",
}


def test_pin_config_macro_values_preserve_pre_migration_defaults():
    defines = _pin_config_defines()
    for name, expected in STM32_MACRO_VALUES.items():
        assert defines.get(name) == expected, f"{name} = {defines.get(name)!r} ≠ {expected}"


def _master_header_defines() -> dict[str, str]:
    """母版全部头（pin_config.h + ml_libs/*.h）的顶层宏——写侧渲染要改的宏
    必须在母版可见（软 I2C 宏已随工单 pin-unlock-stm32/02 迁入 pin_config.h；
    ml_libs 头以 GBK 编码按 errors="replace" 读入，ASCII 宏名不受影响）。"""
    defines = dict(_pin_config_defines())
    for header in (STM32_MASTER / "ml_libs").glob("*.h"):
        for line in header.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*#define\s+([A-Za-z_]\w*)", line)
            if m:
                defines[m.group(1)] = "defined"
    return defines


def test_stm32_declaration_macros_exist_in_master_headers():
    defines = _master_header_defines()
    for slug, platform, pin in ALL_DECLARATIONS:
        if platform != "stm32":
            continue
        for macro in pin.macros:
            assert macro in defines, f"{slug}.{pin.id} 引用未定义宏 {macro}"


# mspm0 默认值 = 母版 mspm0.syscfg 的 $assign（地猛星化后现值）——解析 syscfg
# 逐项核对，改 syscfg 不改声明（或反之）即红。
def _syscfg_peripheral_assignments() -> dict[tuple[str, str], str]:
    """外设类实例的引脚键 → 引脚名（ccp0Pin/ccp1Pin/txPin/rxPin/sclPin/sdaPin）。"""
    text = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8")
    result: dict[tuple[str, str], str] = {}
    pattern = re.compile(
        r"(\w+)\.peripheral\.(ccp\dPin|txPin|rxPin|sclPin|sdaPin)\.\$assign\s*=\s*\"(\w+)\""
    )
    for line in text.splitlines():
        m = pattern.match(line)
        if m:
            result[(m.group(1), m.group(2))] = m.group(3)
    return result


def _extract_group_pins(group: str) -> list[tuple[str, str]]:
    """GPIO 组实例 associatedPins 的 ($name, 引脚) 列表（顺序 = syscfg 行序）。"""
    text = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8")
    result: list[tuple[str, str]] = []
    cur_name: str | None = None
    for line in text.splitlines():
        m = re.match(rf"{group}\.associatedPins\[\d+\]\.\$name\s*=\s*\"(\w+)\"", line)
        if m:
            cur_name = m.group(1)
            continue
        m = re.match(rf"{group}\.associatedPins\[\d+\]\.pin\.\$assign\s*=\s*\"(\w+)\"", line)
        if m and cur_name:
            result.append((cur_name, m.group(1)))
            cur_name = None
    return result


MSPM0_DEFAULT_MAP = {
    # (模块 slug, 角色 id) → syscfg 定位（instance 名/引脚键 或 组名 + $name）
    ("motor", "PWMAB_C0"): ("PWMAB", "ccp0Pin"),
    ("motor", "PWMAB_C1"): ("PWMAB", "ccp1Pin"),
    ("motor", "AIN1"): ("DC_MOTOR", "AIN1"),
    ("motor", "AIN2"): ("DC_MOTOR", "AIN2"),
    ("motor", "BIN1"): ("DC_MOTOR", "BIN1"),
    ("motor", "BIN2"): ("DC_MOTOR", "BIN2"),
    ("motor", "AA"): ("DC_MOTOR", "AA"),
    ("motor", "AB"): ("DC_MOTOR", "AB"),
    ("motor", "BA"): ("DC_MOTOR", "BA"),
    ("motor", "BB"): ("DC_MOTOR", "BB"),
    ("huidu", "L1"): ("HUIDU", "L1"),
    ("huidu", "L2"): ("HUIDU", "L2"),
    ("huidu", "L3"): ("HUIDU", "L3"),
    ("huidu", "L4"): ("HUIDU", "L4"),
    ("huidu", "R1"): ("HUIDU", "R1"),
    ("huidu", "R2"): ("HUIDU", "R2"),
    ("huidu", "R3"): ("HUIDU", "R3"),
    ("huidu", "R4"): ("HUIDU", "R4"),
    ("pid", "GRAY_D1"): ("HUIDU", "L1"),
    ("pid", "GRAY_D2"): ("HUIDU", "L2"),
    ("pid", "GRAY_D3"): ("HUIDU", "L3"),
    ("pid", "GRAY_D4"): ("HUIDU", "L4"),
    ("pid", "GRAY_D5"): ("HUIDU", "R1"),
    ("pid", "GRAY_D6"): ("HUIDU", "R2"),
    ("pid", "GRAY_D7"): ("HUIDU", "R3"),
    ("pid", "GRAY_D8"): ("HUIDU", "R4"),
    # xunji P1..P8 = huidu 模块索引序 L3/L2/L1/R1/R2/L4/R3/R4
    ("xunji", "P1"): ("HUIDU", "L3"),
    ("xunji", "P2"): ("HUIDU", "L2"),
    ("xunji", "P3"): ("HUIDU", "L1"),
    ("xunji", "P4"): ("HUIDU", "R1"),
    ("xunji", "P5"): ("HUIDU", "R2"),
    ("xunji", "P6"): ("HUIDU", "L4"),
    ("xunji", "P7"): ("HUIDU", "R3"),
    ("xunji", "P8"): ("HUIDU", "R4"),
    ("key", "KEY_START"): ("KEY", "START"),
    ("key", "DC_MOTOR_AA"): ("DC_MOTOR", "AA"),
    ("key", "DC_MOTOR_AB"): ("DC_MOTOR", "AB"),
    ("key", "DC_MOTOR_BA"): ("DC_MOTOR", "BA"),
    ("key", "DC_MOTOR_BB"): ("DC_MOTOR", "BB"),
    ("digit_uart", "DIGIT_UART_TX"): ("DIGIT_UART", "txPin"),
    ("digit_uart", "DIGIT_UART_RX"): ("DIGIT_UART", "rxPin"),
    ("imu_uart", "IMU601_TX"): ("IMU601", "txPin"),
    ("imu_uart", "IMU601_RX"): ("IMU601", "rxPin"),
    ("led_beep", "LED_BEEP_LED"): ("LED_BEEP", "LED"),
    ("oled", "OLED_SCL"): ("OLED", "sclPin"),
    ("oled", "OLED_SDA"): ("OLED", "sdaPin"),
    ("step_motor", "STEP_MOTOR_RST2"): ("STEP_MOTOR", "RST2"),
    ("step_motor", "STEP_MOTOR_SLP2"): ("STEP_MOTOR", "SLP2"),
    ("step_motor", "STEP_MOTOR_DIR2"): ("STEP_MOTOR", "DIR2"),
    ("step_motor", "STEP_MOTOR_DCY2"): ("STEP_MOTOR", "DCY2"),
    ("step_motor", "DCC_100_PWM2_C0"): ("DCC_100_PWM2", "ccp0Pin"),
    ("ml_mpu6050", "I2C_0_SCL"): ("I2C_0", "sclPin"),
    ("ml_mpu6050", "I2C_0_SDA"): ("I2C_0", "sdaPin"),
}


def test_mspm0_declaration_defaults_match_master_syscfg():
    peripheral = _syscfg_peripheral_assignments()
    group_pins: dict[str, dict[str, str]] = {}
    for (slug, role_id), (instance, key) in MSPM0_DEFAULT_MAP.items():
        if key in ("txPin", "rxPin", "sclPin", "sdaPin", "ccp0Pin", "ccp1Pin"):
            expected = peripheral[(instance, key)]
        else:  # GPIO 组 associatedPins（$name = 键）
            if instance not in group_pins:
                group_pins[instance] = dict(_extract_group_pins(instance))
            expected = group_pins[instance][key]
        declaration = next(
            p
            for s, plat, p in ALL_DECLARATIONS
            if s == slug and plat == "mspm0" and p.id == role_id
        )
        assert declaration.default == expected, (
            f"{slug}.{role_id} 默认 {declaration.default!r} ≠ syscfg {expected!r}"
        )


# ---------------------------------------------------------------------------
# 真库不变量：默认引脚在板上且能力合法（板外默认规则）
# ---------------------------------------------------------------------------


def test_every_declaration_default_on_board_and_capable():
    """默认引脚必须在对应板定义上、能力集含该角色类型；板外默认（PB4/PB5）
    例外——排针未引出但仍合法（清单保留默认，绑定校验由工单 02 拒绝）。"""
    for slug, platform, pin in ALL_DECLARATIONS:
        board = BOARDS[platform]
        board_pin_ = board_pin(board, pin.default)
        if board_pin_ is None:
            # 板外默认仅限 dimx 的 PB4/PB5（HUIDU R3/R4 + 共享方）
            assert platform == "mspm0" and pin.default in ("PB4", "PB5"), (
                f"{slug}.{pin.id} 默认 {pin.default} 不在 {board.board_id} 板上"
            )
            continue
        if pin.type in ("gpio_out", "gpio_in") or (
            platform == "mspm0" and pin.type == "enc"
        ):
            assert pin_supports(board_pin_, pin.type), (
                f"{slug}.{pin.id} 默认 {pin.default} 不支持 {pin.type}"
            )
        elif platform == "stm32" and pin.type in ("i2c_scl", "i2c_sda"):
            # 软 I2C 去实例化（ADR 0011 工单 02）：stm32 i2c token 无实例，
            # 默认引脚只须类型级支持（总线身份在宏里不在 token 里）
            assert pin_supports(board_pin_, pin.type), (
                f"{slug}.{pin.id} 默认 {pin.default} 不支持 {pin.type}"
            )
        else:
            assert pin_capability_instances(board_pin_, pin.type), (
                f"{slug}.{pin.id} 默认 {pin.default} 无 {pin.type} 能力实例"
            )


def test_offboard_defaults_are_exactly_pb4_pb5():
    offboard = {
        (slug, pin.id)
        for slug, platform, pin in ALL_DECLARATIONS
        if platform == "mspm0" and board_pin(BOARDS[platform], pin.default) is None
    }
    assert offboard == {
        ("huidu", "R3"),
        ("huidu", "R4"),
        ("pid", "GRAY_D7"),
        ("pid", "GRAY_D8"),
        ("xunji", "P7"),
        ("xunji", "P8"),
    }


def test_shared_pin_roles_allowed():
    """同引脚多角色合法（xunji/huidu/pid 共享灰度传感器先例）——不拦重复。"""
    for slug in ("huidu", "xunji", "pid"):
        manifest = ModuleManifest.load(LIBRARY_MODULES / slug)
        defaults = [p.default for p in manifest.platforms["mspm0"].pins]
        assert len(set(defaults)) == len(defaults), f"{slug} 自身声明重复引脚"
    defaults = [
        pin.default
        for slug, platform, pin in ALL_DECLARATIONS
        if platform == "mspm0"
    ]
    assert len(defaults) != len(set(defaults))  # 跨模块共享确实存在


# ---------------------------------------------------------------------------
# C 迁移验收：模块 code 零引脚字面量（宏名与注释除外）
# ---------------------------------------------------------------------------

PIN_LITERAL_PATTERNS = [
    (r"\bGPIO_[ABC]\b", "GPIO_A/B/C 字面量"),
    (r"\bPin_\d+\b", "Pin_N 字面量"),
    (r"\bUART_[123]\b", "UART_N 字面量"),
    (r"\bUSART[123]\b", "USARTN 寄存器字面量"),
    (r"\bEXTI_P[ABC]\d\b", "EXTI 枚举字面量"),
    (r"\bTIM[234]_CH[1-4]\b", "TIMx_CHy 字面量"),
    (r"\bADC_Channel_\d+\b", "ADC 通道字面量"),
]


def test_module_code_has_no_pin_literals():
    """验收 grep：注释剥离后模块 .c/.h 无引脚字面量（宏名如
    DC_MOTOR_AA_PORT / HUIDU_L1_PIN 整体豁免——GPIOA/GPIOB 组宏名是
    syscfg 生成宏的一部分）。"""
    hits: list[str] = []
    for path in sorted(LIBRARY_MODULES.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".c", ".h"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        stripped = strip_comments(text, keep_preprocessor=True)
        for pattern, label in PIN_LITERAL_PATTERNS:
            for m in re.finditer(pattern, stripped):
                hits.append(f"{path.relative_to(LIBRARY_MODULES)}:{label}: {m.group(0)}")
    assert not hits, "模块 code 引脚字面量残留：\n" + "\n".join(hits)
