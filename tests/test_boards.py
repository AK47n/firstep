"""板定义数据层（工单 pin-board-config/01 A）：模型 / 真实板数据不变量 / API。

boards/*.json 是板图坐标与能力集的唯一数据源（前端板图与生成门禁同吃）——
本文件对仓库内真实板定义断言不变量（防回退）：排针唯一、坐标在 2×20 界内、
能力 token 词表合法、io 脚必有 gpio 角色、stm32 能力集与 ml_libs 映射表一致、
mspm0 排针清单与地猛星引脚图 PDF 一致、/api/boards 路由形状。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contest_generator.boards import (
    BOARDS_DIR,
    BoardError,
    board_pin,
    load_board,
    load_boards,
    pin_capability_instances,
    pin_supports,
)
from contest_generator.manifest import PIN_ROLE_TYPES
from contest_generator.webapp import create_app


@pytest.fixture(scope="module")
def boards() -> dict[str, object]:
    return {b.board_id: b for b in load_boards(BOARDS_DIR)}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def test_load_real_boards_two_boards(boards):
    assert list(boards) == ["mspm0-dimx", "stm32-min-system"]
    assert boards["stm32-min-system"].platform == "stm32"
    assert boards["mspm0-dimx"].platform == "mspm0"
    # 各 40 个排针位（2×20）
    for board in boards.values():
        assert len(board.pins) == 40


def test_pin_coords_in_board_bounds_and_unique(boards):
    for board in boards.values():
        positions: set[tuple[int, int]] = set()
        for pin in board.pins:
            assert pin.kind in ("io", "power", "gnd", "reset", "fixed")
            assert pin.x in (0, 1) and 0 <= pin.y <= 19
            assert pin.side in ("left", "right")
            assert (pin.x, pin.y) not in positions, f"{board.board_id} 坐标重复"
            positions.add((pin.x, pin.y))


def test_io_pins_have_gpio_roles(boards):
    for board in boards.values():
        for pin in board.pins:
            if pin.kind == "io":
                assert pin_supports(pin, "gpio_out"), f"{pin.name} 缺 gpio_out"
                assert pin_supports(pin, "gpio_in"), f"{pin.name} 缺 gpio_in"


def test_capability_tokens_valid_and_unique(boards):
    for board in boards.values():
        for pin in board.pins:
            tokens: set[str] = set()
            for token in pin.capabilities:
                assert token not in tokens, f"{pin.name} 能力 token 重复 {token}"
                tokens.add(token)
                parts = token.split(":")
                assert parts[0] in PIN_ROLE_TYPES, f"{pin.name} 非法 token {token}"


# stm32 能力集口径 = ml_libs 支持表（ml_uart/ml_pwm/ml_exti/ml_adc/
# ml_i2c/ml_oled 的实例→引脚映射逐条编码）——映射表硬编码于此防回退。
STM32_ML_LIBS_EXPECTED = {
    "PA0": ["pwm:TIM2_CH1", "adc:ADC_Channel_0", "exti:PA0", "enc:0"],
    "PA1": ["pwm:TIM2_CH2", "adc:ADC_Channel_1", "exti:PA1", "enc:1"],
    "PA2": ["pwm:TIM2_CH3", "adc:ADC_Channel_2", "exti:PA2", "enc:2", "uart_tx:UART_2"],
    "PA3": ["pwm:TIM2_CH4", "adc:ADC_Channel_3", "exti:PA3", "enc:3", "uart_rx:UART_2"],
    "PA4": ["adc:ADC_Channel_4", "exti:PA4", "enc:4"],
    "PA5": ["adc:ADC_Channel_5", "exti:PA5", "enc:5"],
    "PA6": ["pwm:TIM3_CH1", "adc:ADC_Channel_6", "exti:PA6", "enc:6"],
    "PA7": ["pwm:TIM3_CH2", "adc:ADC_Channel_7", "exti:PA7", "enc:7"],
    "PA9": ["uart_tx:UART_1"],
    "PA10": ["uart_rx:UART_1"],
    "PB0": ["pwm:TIM3_CH3", "adc:ADC_Channel_8", "exti:PB0", "enc:0"],
    "PB1": ["pwm:TIM3_CH4", "adc:ADC_Channel_9", "exti:PB1", "enc:1"],
    "PB3": ["exti:PB3", "enc:3"],
    "PB4": ["exti:PB4", "enc:4"],
    "PB5": ["exti:PB5", "enc:5"],
    "PB6": ["pwm:TIM4_CH1", "exti:PB6", "enc:6"],
    "PB7": ["pwm:TIM4_CH2", "exti:PB7", "enc:7"],
    "PB8": ["pwm:TIM4_CH3", "i2c_scl:ml_oled"],
    "PB9": ["pwm:TIM4_CH4", "i2c_sda:ml_oled"],
    "PB10": ["uart_tx:UART_3", "i2c_scl:ml_i2c"],
    "PB11": ["uart_rx:UART_3", "i2c_sda:ml_i2c"],
}


def test_stm32_capabilities_match_ml_libs(boards):
    stm32 = boards["stm32-min-system"]
    for name, expected in STM32_ML_LIBS_EXPECTED.items():
        pin = board_pin(stm32, name)
        assert pin is not None, name
        for token in expected:
            assert token in pin.capabilities, f"{name} 缺能力 {token}（ml_libs 表）"


def test_stm32_enc_limited_to_same_exti_line(boards):
    """enc 实例 = EXTI 线号：v1 限同线号引脚（handler 名绑定线号）。"""
    stm32 = boards["stm32-min-system"]
    line2 = [p.name for p in stm32.pins if pin_supports(p, "enc", "2")]
    line4 = [p.name for p in stm32.pins if pin_supports(p, "enc", "4")]
    assert line2 == ["PA2"]  # PB2(BOOT1)/PC2 不在排针
    assert line4 == ["PA4", "PB4"]


def test_dimx_header_layout_matches_pin_diagram(boards):
    """排针清单与地猛星引脚图 PDF 一致（左排/右排自上而下，各 20 位）。"""
    dimx = boards["mspm0-dimx"]
    left = [
        "PA0", "PA1", "PA28", "PA31", "NRST", "PA2", "PB24", "PB20", "PB19",
        "PB18", "PA7", "PB2", "PB3", "PA8", "PA9", "PB6", "PB7", "+5V", "3V3", "GND",
    ]
    right = [
        "GND", "PA27", "PA26", "PA25", "PA24", "PA23", "PA22", "PA21", "PB9",
        "PB8", "PA18", "PA17", "PA16", "PA15", "PA14", "PA13", "PA12",
        "+5V", "3V3", "GND",
    ]
    for x, expected in ((0, left), (1, right)):
        got = [
            p.name
            for p in sorted(
                (p for p in dimx.pins if p.x == x),
                key=lambda p: p.y,
            )
        ]
        assert got == expected


def test_dimx_pb4_pb5_not_on_headers(boards):
    dimx = boards["mspm0-dimx"]
    assert board_pin(dimx, "PB4") is None
    assert board_pin(dimx, "PB5") is None


def test_stm32_header_layout_matches_blue_pill(boards):
    """蓝药丸双排 20×2 布局（2026-08-14 按用户手上真板校正：左下角
    R→3V3→GND→GND；右排从上到下与左排相反——真板丝印为镜像印刷）。"""
    stm32 = boards["stm32-min-system"]
    left = [
        "VBAT", "PC13", "PC14", "PC15", "PA0", "PA1", "PA2", "PA3", "PA4",
        "PA5", "PA6", "PA7", "PB0", "PB1", "PB10", "PB11", "R", "3V3", "GND", "GND",
    ]
    right = [
        "3V3", "GND", "5V", "PB9", "PB8", "PB7", "PB6", "PB5", "PB4", "PB3",
        "PA15", "PA12", "PA11", "PA10", "PA9", "PA8", "PB15", "PB14", "PB13", "PB12",
    ]
    for x, expected in ((0, left), (1, right)):
        got = [
            p.name
            for p in sorted(
                (p for p in stm32.pins if p.x == x),
                key=lambda p: p.y,
            )
        ]
        assert got == expected


def test_stm32_landmarks_mark_orientation(boards):
    """板缘地标（真板校正 2026-08-14）：4P 弯针上缘 + Type-C 下缘区分板图上下。"""
    stm32 = boards["stm32-min-system"]
    by_edge = {lm.edge: lm for lm in stm32.landmarks}
    assert by_edge["top"].kind == "header_4p"
    assert by_edge["bottom"].kind == "usb_typec"
    assert stm32.pcb_color == "#1e4f9e"  # 蓝药丸俯视底色


def test_stm32_fixed_resources(boards):
    stm32 = boards["stm32-min-system"]
    occupies = {f.name: f.occupies for f in stm32.fixed}
    assert occupies["SWD 调试"] == ("PA13", "PA14")
    assert occupies["晶振"] == ("PD0", "PD1")
    assert occupies["BOOT1"] == ("PB2",)
    assert occupies["板载 LED"] == ("PC13",)
    # PA13/PA14 不在排针；PC13 在排针（板载 LED 共用）
    assert board_pin(stm32, "PA13") is None
    assert board_pin(stm32, "PA14") is None
    assert board_pin(stm32, "PC13") is not None


def test_dimx_fixed_resources(boards):
    dimx = boards["mspm0-dimx"]
    occupies = {f.name: f.occupies for f in dimx.fixed}
    assert occupies["CH340E USB串口"] == ("PA10", "PA11")
    assert occupies["Flash 存储"] == ("PB14", "PB15", "PB16", "PB17")
    assert occupies["晶振"] == ("PA3", "PA4", "PA5", "PA6")
    assert occupies["SWD 调试"] == ("PA19", "PA20")


def test_pin_supports_with_and_without_instance(boards):
    dimx = boards["mspm0-dimx"]
    pa12 = board_pin(dimx, "PA12")
    assert pa12 is not None
    assert pin_supports(pa12, "pwm", "TIMG0_C0")
    assert not pin_supports(pa12, "pwm", "TIMG12_C0")
    assert pin_supports(pa12, "gpio_out")
    assert not pin_supports(pa12, "uart_tx", "UART0")


def test_pin_capability_instances(boards):
    stm32 = boards["stm32-min-system"]
    pa2 = board_pin(stm32, "PA2")
    assert pa2 is not None
    assert pin_capability_instances(pa2, "enc") == ("2",)
    assert "UART_2" in pin_capability_instances(pa2, "uart_tx")
    assert pin_capability_instances(pa2, "i2c_scl") == ()


def test_load_board_rejects_bad_data(tmp_path):
    cases = [
        # 缺必填字段
        '{"board_id": "x", "name": "x", "platform": "stm32", "pins": []}',
        # 平台非法
        '{"board_id": "x", "name": "x", "platform": "avr", "pins": [], "fixed": []}',
        # 引脚 kind 非法
        '{"board_id": "x", "name": "x", "platform": "stm32", "pins": ['
        '{"name": "PA0", "kind": "weird", "x": 0, "y": 0, "side": "left"}], "fixed": []}',
        # 能力 token 类型不在词表
        '{"board_id": "x", "name": "x", "platform": "stm32", "pins": ['
        '{"name": "PA0", "kind": "io", "x": 0, "y": 0, "side": "left",'
        '"capabilities": ["can_tx:CAN1"]}], "fixed": []}',
        # 引脚重名
        '{"board_id": "x", "name": "x", "platform": "stm32", "pins": ['
        '{"name": "PA0", "kind": "io", "x": 0, "y": 0, "side": "left"},'
        '{"name": "PA0", "kind": "io", "x": 1, "y": 0, "side": "right"}], "fixed": []}',
    ]
    for i, text in enumerate(cases):
        path = tmp_path / f"bad{i}.json"
        path.write_text(text, encoding="utf-8")
        with pytest.raises(BoardError):
            load_board(path)


def test_load_board_rejects_id_mismatch(tmp_path):
    path = tmp_path / "board-x.json"
    path.write_text(
        '{"board_id": "other", "name": "x", "platform": "stm32", "pins": [], "fixed": []}',
        encoding="utf-8",
    )
    with pytest.raises(BoardError):
        load_board(path)


def test_api_boards_returns_both_boards(client):
    resp = client.get("/api/boards")
    assert resp.status_code == 200
    boards = resp.json()["boards"]
    assert {b["board_id"] for b in boards} == {"stm32-min-system", "mspm0-dimx"}
    for board in boards:
        assert {"board_id", "name", "platform", "pins", "fixed"} <= board.keys()
        for pin in board["pins"]:
            assert {"name", "kind", "x", "y", "side", "capabilities", "notes"} <= pin.keys()


def test_api_boards_platform_filter(client):
    resp = client.get("/api/boards", params={"platform": "stm32"})
    assert resp.status_code == 200
    boards = resp.json()["boards"]
    assert [b["board_id"] for b in boards] == ["stm32-min-system"]
    resp = client.get("/api/boards", params={"platform": "avr"})
    assert resp.json() == {"boards": []}
