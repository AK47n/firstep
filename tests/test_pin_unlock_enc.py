"""stm32 enc 换线（工单 pin-full-unlock/01，ADR 0012）：类型级绑定 + EXTI
线冲突门禁 + motor 条件 handler + ml_exti 48 项枚举 + 板定义数据扩线。

红证（先写、未实施前红）：类型级分支缺位时绑 PA5 被拦 / 异口同线 400 缺位 /
枚举缺线 8-15 时 switch 缺项（exti_pin_init 静默跳过 = 配不动作）。绿证：
绑 PA5/PA6 → pin_config.h 宏值断言 + 默认不配输出与母版逐字节 + motor
7 个条件 handler 结构 + ml_exti NVIC 通道公式 + 板定义扩线数据。运行级
（编码器真转）用户上板自验（验收口径 ADR 0012）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.boards import (
    BOARDS_DIR,
    Board,
    BoardPin,
    board_pin,
    load_boards,
    pin_supports,
)
from contest_generator.errors import error_entry
from contest_generator.generator import GateContext, ModuleCorpus, generate
from contest_generator.library import list_modules
from contest_generator.pin_bindings import PinBindingError, resolve_bindings
from contest_generator.pinwriter import PIN_CONFIG_FILENAME, render_pin_config

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
LIBRARY_MODULES = LIBRARY_ROOT / "modules"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}
ALL_MANIFESTS = list_modules(LIBRARY_MODULES)
STM32_MASTER_PIN_CONFIG = (STM32_MASTER / PIN_CONFIG_FILENAME).read_text(
    encoding="utf-8", newline=""
)


def _resolve(bindings: dict[str, str]):
    return resolve_bindings(ALL_MANIFESTS, "stm32", BOARDS["stm32"], bindings)


def _corpus(main_c: str = "") -> ModuleCorpus:
    return ModuleCorpus(
        platform="stm32",
        modules=(),
        missing_platforms=(),
        missing_files=(),
        master_headers=(),
        master_search_dirs=(),
        search_dir_headers=(),
        master_project_dir=Path("."),
        main_c=main_c,
    )


# ---------------------------------------------------------------------------
# 红证 1：enc 类型级分支（缺位时绑 PA5 被"实例锁"拦下）
# ---------------------------------------------------------------------------


def test_resolve_enc_type_level_any_enc_pin():
    """enc 类型级（ADR 0012）：任意 enc:* 脚可绑，实例（= 线号）随**绑定
    引脚**推导喂渲染器（PA5 → 5、PB8 → 8、PC13 → 13）。"""
    for pin, line in (("PA5", "5"), ("PB8", "8"), ("PC13", "13")):
        resolved = _resolve({"motor.MOTOR_A_ENC": pin})
        assert len(resolved) == 1
        assert resolved[0].pin == pin
        assert resolved[0].instances == (line,)


def _fake_stm32_board(*caps: tuple[str, tuple[str, ...]]) -> Board:
    """假板（enc 类型级下限红证用）：真板扩线后全 io 脚都有 enc token，
    "无 enc token 的脚拒绝"分支只能靠假板直测。"""
    pins = tuple(
        BoardPin(name=name, kind="io", x=0, y=i, side="left", capabilities=cap)
        for i, (name, cap) in enumerate(caps)
    )
    return Board(
        board_id="fake-stm32",
        name="fake",
        platform="stm32",
        pins=pins,
        pin_index={p.name: p for p in pins},
    )


def test_resolve_enc_rejects_pin_without_enc_token():
    """类型级下限：无 enc token 的脚仍拒——报错文案 = 类型级（不支持角色
    类型 enc），非实例锁文案。"""
    fake = _fake_stm32_board(
        ("PA0", ("enc:0", "gpio_out")),
        ("PB1", ("gpio_out",)),
    )
    with pytest.raises(PinBindingError, match="不支持角色类型 enc"):
        resolve_bindings(ALL_MANIFESTS, "stm32", fake, {"motor.MOTOR_A_ENC": "PB1"})


# ---------------------------------------------------------------------------
# 红证 2：EXTI 线冲突门禁（异口同线 400 缺位）
# ---------------------------------------------------------------------------


def _exti_line_check(platform: str, bindings: dict[str, str]):
    from contest_generator.generator import _check_exti_line_conflicts

    _check_exti_line_conflicts(
        _corpus(), ALL_MANIFESTS, platform,
        GateContext(bindings=bindings, board=BOARDS[platform]),
    )


def test_exti_line_conflict_gate_rejects_same_line_different_pins():
    """异口同线互斥：MOTOR_A_ENC→PA5、MOTOR_B_ENC→PB5 同 EXTI 线 5 ∧ 引脚
    不同 → 400 中文（同线 handler 互相清 PR 位 = 编译绿运行坏，生成前拦）。"""
    from contest_generator.generator import ExtiLineConflictError

    with pytest.raises(ExtiLineConflictError, match="同 EXTI 线 5") as excinfo:
        _exti_line_check(
            "stm32",
            {"motor.MOTOR_A_ENC": "PA5", "motor.MOTOR_B_ENC": "PB5"},
        )
    assert "MOTOR_A_ENC" in str(excinfo.value)
    assert "MOTOR_B_ENC" in str(excinfo.value)


def test_exti_line_conflict_gate_passes_shared_pin_and_distinct_lines():
    """同脚共享不查（提示语义）；异线直过；空载荷直过；mspm0 无 EXTI 线
    语义不适用（enc 走 GPIO 组中断）。"""
    # 同脚共享（同线同脚 = 合法）
    _exti_line_check("stm32", {"motor.MOTOR_A_ENC": "PA5", "motor.MOTOR_B_ENC": "PA5"})
    # 异线（默认组合 PA2 线 2 / PA4 线 4）
    _exti_line_check("stm32", {"motor.MOTOR_A_ENC": "PA2", "motor.MOTOR_B_ENC": "PA4"})
    # 线 13 / 线 15 不冲突
    _exti_line_check("stm32", {"motor.MOTOR_A_ENC": "PC13", "motor.MOTOR_B_ENC": "PA15"})
    # 空载荷直过（generate_check 产物复核 / 存量测试形态）
    _exti_line_check("stm32", {})
    # mspm0：PA8/PB8 尾号同为 8 也不拦（无线号概念）
    _exti_line_check("mspm0", {"motor.AA": "PA8", "motor.AB": "PB8"})


def test_error_entry_maps_exti_line_conflict_to_400():
    """ExtiLineConflictError 显式登记 error_to_http 表 → 400 中文。"""
    from contest_generator.generator import ExtiLineConflictError

    status, message = error_entry(
        ExtiLineConflictError(
            "绑定冲突：motor.MOTOR_A_ENC（PA5）与 motor.MOTOR_B_ENC（PB5）"
            "同 EXTI 线 5，异口同线互斥"
        )
    )
    assert status == 400
    assert "同 EXTI 线 5" in message


# ---------------------------------------------------------------------------
# 绿证：渲染器宏值（渲染器零改动——尾形已有，类型级喂实例）
# ---------------------------------------------------------------------------


def test_render_pin_config_enc_reline_pa5_pa6():
    """工单 05 后 A_ENC 默认 PB5（线 5）、B_ENC 默认 PA4（线 4）——绑
    A→PA6（线 6）/ B→PA5（线 5）两线都变；注释旧引脚字样同步替换。"""
    out = render_pin_config(
        STM32_MASTER_PIN_CONFIG,
        _resolve({"motor.MOTOR_A_ENC": "PA6", "motor.MOTOR_B_ENC": "PA5"}),
    )
    assert "#define MOTOR_A_ENC_EXTI      EXTI_PA6   /* PA6，下降沿触发 */\r\n" in out
    assert "#define MOTOR_A_ENC_LINE      6          /* EXTI 线号（handler 按此条件编译） */\r\n" in out
    assert "#define MOTOR_B_ENC_EXTI      EXTI_PA5   /* PA5，下降沿触发 */\r\n" in out
    assert "#define MOTOR_B_ENC_LINE      5          /* EXTI 线号（handler 按此条件编译） */\r\n" in out
    assert "EXTI_PB5" not in out
    assert "EXTI_PA4" not in out


def test_render_enc_reline_changes_only_enc_lines():
    """换线只动 4 行 ENC 宏（EXTI/LINE × A/B），其余行逐字节不动。"""
    out = render_pin_config(
        STM32_MASTER_PIN_CONFIG,
        _resolve({"motor.MOTOR_A_ENC": "PA6", "motor.MOTOR_B_ENC": "PA5"}),
    )
    before = STM32_MASTER_PIN_CONFIG.splitlines(True)
    after = out.splitlines(True)
    assert len(before) == len(after)
    changed = [after[i] for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert changed == [
        "#define MOTOR_A_ENC_EXTI      EXTI_PA6   /* PA6，下降沿触发 */\r\n",
        "#define MOTOR_A_ENC_LINE      6          /* EXTI 线号（handler 按此条件编译） */\r\n",
        "#define MOTOR_B_ENC_EXTI      EXTI_PA5   /* PA5，下降沿触发 */\r\n",
        "#define MOTOR_B_ENC_LINE      5          /* EXTI 线号（handler 按此条件编译） */\r\n",
    ]


def test_generate_stm32_enc_reline_and_default_byte_identical(tmp_path):
    """generate 集成：带绑定 → pin_config.h 宏值变；缺省路径 → 与母版逐字节。"""
    motor = next(m for m in ALL_MANIFESTS if m.slug == "motor")
    out_dir = tmp_path / "out_bound"
    generate(
        platform="stm32",
        manifests=[motor],
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out_dir,
        main_c_content="int main(void) { while (1); }\n",
        bindings={"motor.MOTOR_A_ENC": "PA6", "motor.MOTOR_B_ENC": "PA5"},
    )
    written = (out_dir / PIN_CONFIG_FILENAME).read_text(encoding="utf-8", newline="")
    assert "#define MOTOR_A_ENC_EXTI      EXTI_PA6" in written
    assert "#define MOTOR_A_ENC_LINE      6" in written
    assert "#define MOTOR_B_ENC_LINE      5" in written
    assert written != STM32_MASTER_PIN_CONFIG

    out_dir2 = tmp_path / "out_default"
    generate(
        platform="stm32",
        manifests=[motor],
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out_dir2,
        main_c_content="int main(void) { while (1); }\n",
    )
    assert (
        out_dir2 / PIN_CONFIG_FILENAME
    ).read_text(encoding="utf-8", newline="") == STM32_MASTER_PIN_CONFIG


# ---------------------------------------------------------------------------
# 红证 3 / 绿证：ml_exti 枚举 48 项 + NVIC 通道公式（结构钉）
# ---------------------------------------------------------------------------


def test_ml_exti_enum_and_switch_cover_all_48_pins():
    """枚举（ml_exti.h）与 exti_pin_init switch（ml_exti.c）覆盖 PA/PB/PC ×
    线 0-15 全 48 项——switch 缺项 = gpio_init 静默跳过（配不动作），枚举缺
    项 = EXTI_PAx 符号不存在（编译炸）。"""
    header = (STM32_MASTER / "ml_libs" / "ml_exti.h").read_text(
        encoding="utf-8", errors="replace"
    )
    source = (STM32_MASTER / "ml_libs" / "ml_exti.c").read_text(
        encoding="utf-8", errors="replace"
    )
    for port in "ABC":
        for line in range(16):
            name = f"EXTI_P{port}{line}"
            assert name in header, f"ml_exti.h 枚举缺 {name}"
            assert f"case {name}:" in source, f"ml_exti.c switch 缺 {name}"


def test_ml_exti_nvic_channel_formula():
    """NVIC 通道公式：线 ≤4 → EXTI0-4_IRQn（pin/3+6）、5-9 → EXTI9_5_IRQn、
    10-15 → EXTI15_10_IRQn。"""
    text = (STM32_MASTER / "ml_libs" / "ml_exti.c").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "if(pin/3<=4)" in text
    assert "NVIC_init(priority,pin/3+6)" in text
    assert "else if(pin/3<=9)" in text
    assert "NVIC_init(priority,EXTI9_5_IRQn)" in text
    assert "NVIC_init(priority,EXTI15_10_IRQn)" in text


# ---------------------------------------------------------------------------
# 绿证：motor_stm32.c 7 条件 handler 结构（默认 PA2/PA4 行为等价）
# ---------------------------------------------------------------------------

MOTOR_STM32_C = LIBRARY_MODULES / "motor" / "code" / "motor_stm32.c"

_HANDLER_GUARDS = {
    "EXTI0_IRQHandler": "#if MOTOR_A_ENC_LINE == 0 || MOTOR_B_ENC_LINE == 0",
    "EXTI1_IRQHandler": "#if MOTOR_A_ENC_LINE == 1 || MOTOR_B_ENC_LINE == 1",
    "EXTI2_IRQHandler": "#if MOTOR_A_ENC_LINE == 2 || MOTOR_B_ENC_LINE == 2",
    "EXTI3_IRQHandler": "#if MOTOR_A_ENC_LINE == 3 || MOTOR_B_ENC_LINE == 3",
    "EXTI4_IRQHandler": "#if MOTOR_A_ENC_LINE == 4 || MOTOR_B_ENC_LINE == 4",
    "EXTI9_5_IRQHandler": "#if (MOTOR_A_ENC_LINE >= 5 && MOTOR_A_ENC_LINE <= 9)"
    " || (MOTOR_B_ENC_LINE >= 5 && MOTOR_B_ENC_LINE <= 9)",
    "EXTI15_10_IRQHandler": "#if (MOTOR_A_ENC_LINE >= 10 && MOTOR_A_ENC_LINE <= 15)"
    " || (MOTOR_B_ENC_LINE >= 10 && MOTOR_B_ENC_LINE <= 15)",
}


def _motor_stm32_text() -> str:
    return MOTOR_STM32_C.read_text(encoding="utf-8")


def test_motor_stm32_handlers_conditional_on_line_macros():
    """7 个 handler 全部条件编译：每个 `void EXTIx_IRQHandler(void)` 定义前
    最近的非空行必须是对应的 `#if` 线号守卫——写死 handler（旧 EXTI2/EXTI4
    无条件定义）即红。"""
    text = _motor_stm32_text()
    for handler, guard in _HANDLER_GUARDS.items():
        assert guard in text, f"缺守卫 {guard}"
        m = re.search(rf"void {handler}\(void\)", text)
        assert m is not None, f"缺 handler {handler}"
        previous = text[: m.start()].rstrip().rsplit("\n", 1)[-1]
        assert previous.startswith("#if"), (
            f"{handler} 定义前最近非空行不是 #if 守卫：{previous!r}"
        )


def test_motor_stm32_counters_dispatch_on_line_bits():
    """共线组内 PR 位分派：A/B 块各自按 MOTOR_A/B_ENC_LINE 查 PR 位与清位，
    组 handler（5-9/10-15）按区间条件编译 A/B 块。"""
    text = _motor_stm32_text()
    assert "EXTI->PR & (1 << MOTOR_A_ENC_LINE)" in text
    assert "EXTI->PR & (1 << MOTOR_B_ENC_LINE)" in text
    assert "EXTI->PR = 1 << MOTOR_A_ENC_LINE" in text
    assert "EXTI->PR = 1 << MOTOR_B_ENC_LINE" in text
    assert "#if MOTOR_A_ENC_LINE >= 5 && MOTOR_A_ENC_LINE <= 9" in text
    assert "#if MOTOR_A_ENC_LINE >= 10 && MOTOR_A_ENC_LINE <= 15" in text
    assert "Encoder_count1" in text and "Encoder_count2" in text


# ---------------------------------------------------------------------------
# 绿证：板定义数据扩线（PA8-15 / PB8-15 / PC13-15 加 exti + enc 线号 token）
# ---------------------------------------------------------------------------


def test_board_def_exti_enc_tokens_extended_to_lines_8_15():
    """扩线数据：既有 exti/enc 脚不动；PA8-15/PB8-15/PC13-15 补齐
    exti:PAx/PBx/PCx + enc:<尾号 mod 16>。PA13/PA14（SWD）不在排针不涉及。"""
    stm32 = BOARDS["stm32"]
    for pin in (
        "PA8", "PA9", "PA10", "PA11", "PA12", "PA15",
        "PB8", "PB9", "PB10", "PB11", "PB12", "PB13", "PB14", "PB15",
        "PC13", "PC14", "PC15",
    ):
        board_pin_ = board_pin(stm32, pin)
        assert board_pin_ is not None, pin
        assert pin_supports(board_pin_, "exti", pin), f"{pin} 缺 exti:{pin}"
        line = int(pin[2:]) % 16
        assert pin_supports(board_pin_, "enc", str(line)), f"{pin} 缺 enc:{line}"
