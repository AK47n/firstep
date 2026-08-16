"""stm32 UART 换实例（工单 pin-full-unlock/02，ADR 0012）：uart 类型级 +
TX/RX 对同实例校验 + 实例冲突门禁 + USARTx_IRQ_CALLS 重分组渲染 + 母版
isr.c 聚合 + fputc 跟随 DEBUG_UART + ml_uart 参数化（uart_pin_init_ex）。

红证（先写、未实施前红）：uart 类型级缺位时绑 PB10/PB11 被实例锁拦 / TX/RX
交集空 400 缺位 / 绑 DEBUG→UART_3 撞 ZIGBEE 默认 400 缺位 / CALLS 宏缺失。
绿证：三组绑定全换位（DEBUG→UART_3、ZIGBEE→UART_2、UWB→UART_2 成对绑）
放行 + pin_config.h 宏值 + USARTx_IRQ_CALLS 重分组断言 + isr.c 聚合结构 +
fputc 宏断言 + 默认不配输出 == 新母版逐字节。运行级（串口观察位置随
DEBUG_UART 挪位）用户上板自验（验收口径 ADR 0012）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.boards import (
    BOARDS_DIR,
    Board,
    BoardPin,
    load_boards,
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

# 三组绑定全换位（真机场景 ② 同款）：DEBUG UART_2→UART_3、ZIGBEE UART_3→
# UART_2、UWB UART_1→UART_2 成对绑 TX/RX（UWB×ZIGBEE 同实例 UART_2 共享
# = 绑定×绑定放行，换位合法）。
SWAP_BINDINGS = {
    "debug_uart.DEBUG_UART_TX": "PB10",
    "debug_uart.DEBUG_UART_RX": "PB11",
    "zigbee_uart.ZIGBEE_UART_TX": "PA2",
    "zigbee_uart.ZIGBEE_UART_RX": "PA3",
    "uwb_uart.UWB_UART_TX": "PA2",
    "uwb_uart.UWB_UART_RX": "PA3",
}


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


def _uart_manifests():
    # 五 uart 模块 + config/filter（uwb/zigbee 的 config.h、filter.h 依赖；
    # generate 直传 manifests 不做依赖展开，手动并上）
    return [
        m
        for m in ALL_MANIFESTS
        if m.slug
        in (
            "digit_uart",
            "coord_detect",
            "debug_uart",
            "uwb_uart",
            "zigbee_uart",
            "config",
            "filter",
        )
    ]


# ---------------------------------------------------------------------------
# 红证 1：uart 类型级（缺位时绑 PB10/PB11 被"实例锁"拦下）
# ---------------------------------------------------------------------------


def test_resolve_uart_type_level_pair_to_uart_3():
    """uart 类型级（ADR 0012）：有 uart_tx/uart_rx token 的脚可绑，实例随
    **绑定引脚**推导喂渲染器——DIGIT 成对绑 PB10/PB11 → 两脚实例均
    ("UART_3",)（旧实例锁：DIGIT_UART TX 默认 PA9 只认 uart_tx:UART_1，
    PB10 必拒）。"""
    resolved = _resolve(
        {
            "digit_uart.DIGIT_UART_TX": "PB10",
            "digit_uart.DIGIT_UART_RX": "PB11",
        }
    )
    assert {b.role_key: b.instances for b in resolved} == {
        "digit_uart.DIGIT_UART_TX": ("UART_3",),
        "digit_uart.DIGIT_UART_RX": ("UART_3",),
    }


def _fake_stm32_board(*caps: tuple[str, tuple[str, ...]]) -> Board:
    """假板（uart 类型级下限红证用）：无 uart token 的脚仍拒 = 类型级下限。"""
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


def test_resolve_uart_rejects_pin_without_uart_token():
    """类型级下限：无 uart_tx token 的脚仍拒——报错文案 = 类型级（不支持角色
    类型 uart_tx），非实例锁文案。"""
    fake = _fake_stm32_board(
        ("PA9", ("uart_tx:UART_1", "gpio_out")),
        ("PA10", ("uart_rx:UART_1", "gpio_out")),
        ("PB1", ("gpio_out",)),
    )
    with pytest.raises(PinBindingError, match="不支持角色类型 uart_tx"):
        resolve_bindings(ALL_MANIFESTS, "stm32", fake, {"debug_uart.DEBUG_UART_TX": "PB1"})


# ---------------------------------------------------------------------------
# 红证 2：TX/RX 对同实例约束（交集空 400 缺位）
# ---------------------------------------------------------------------------


def test_resolve_uart_pair_intersection_empty_400():
    """TX/RX 对同实例约束：DIGIT TX→PB10（UART_3）× RX→PA3（UART_2）交集
    空 → 400 中文"必须同实例，请成对绑定"（缺位时 TX→PB10 先被实例锁拦，
    报不出成对绑定文案）。"""
    with pytest.raises(PinBindingError, match="必须同实例，请成对绑定") as excinfo:
        _resolve({"digit_uart.DIGIT_UART_TX": "PB10", "digit_uart.DIGIT_UART_RX": "PA3"})
    assert "DIGIT_UART_TX" in str(excinfo.value)
    assert "DIGIT_UART_RX" in str(excinfo.value)


def test_resolve_uart_pair_single_foot_move_400():
    """单脚换实例必撞另一脚默认实例：只绑 DIGIT TX→PB10（RX 留默认 PA10 =
    UART_1）交集空 → 400 成对绑定。"""
    with pytest.raises(PinBindingError, match="必须同实例，请成对绑定"):
        _resolve({"digit_uart.DIGIT_UART_TX": "PB10"})


def test_resolve_uart_pair_same_instance_pass():
    """成对同实例放行：DIGIT→UART_3（PB10/PB11）、DEBUG→UART_3（PB10/PB11）
    同脚共享合法（提示语义）。"""
    resolved = _resolve(
        {
            "digit_uart.DIGIT_UART_TX": "PB10",
            "digit_uart.DIGIT_UART_RX": "PB11",
            "debug_uart.DEBUG_UART_TX": "PB10",
            "debug_uart.DEBUG_UART_RX": "PB11",
        }
    )
    assert len(resolved) == 4


# ---------------------------------------------------------------------------
# 红证 3：实例冲突门禁（绑 DEBUG→UART_3 撞 ZIGBEE 默认 400 缺位）
# ---------------------------------------------------------------------------


def _uart_conflict_check(bindings: dict[str, str], manifests=None):
    from contest_generator.generator import _check_uart_instance_conflicts

    _check_uart_instance_conflicts(
        _corpus(), manifests or _uart_manifests(), "stm32",
        GateContext(bindings=bindings, board=BOARDS["stm32"]),
    )


def test_uart_instance_conflict_gate_rejects_single_role_move():
    """单角色换实例必撞同实例默认角色：DEBUG 成对绑 UART_3（PB10/PB11）×
    未绑 ZIGBEE 默认 UART_3 → 400 中文（生成前拦，编译绿运行坏）。"""
    from contest_generator.generator import UartInstanceConflictError

    with pytest.raises(UartInstanceConflictError, match="默认实例 UART_3") as excinfo:
        _uart_conflict_check(
            {"debug_uart.DEBUG_UART_TX": "PB10", "debug_uart.DEBUG_UART_RX": "PB11"}
        )
    assert "DEBUG_UART_TX" in str(excinfo.value)
    assert "ZIGBEE" in str(excinfo.value)


def test_uart_instance_conflict_gate_rejects_when_key_module_holds_default():
    """共享宏同族模块也算默认占位：zigbee_uart_key 选中未绑（默认 UART_3）
    时，DEBUG 绑 UART_3 仍撞它（共享 ZIGBEE_UART 宏会漂移撞车）。"""
    from contest_generator.generator import UartInstanceConflictError

    with pytest.raises(UartInstanceConflictError, match="zigbee_uart_key"):
        _uart_conflict_check(
            {"debug_uart.DEBUG_UART_TX": "PB10", "debug_uart.DEBUG_UART_RX": "PB11"},
            manifests=[
                m
                for m in ALL_MANIFESTS
                if m.slug in ("debug_uart", "zigbee_uart_key")
            ],
        )


def test_uart_instance_conflict_gate_passes_swap_and_defaults():
    """换位放行（绑定×绑定同实例 = 共享提示语义）：三组全换位直过；空载荷
    直过；no-op 绑定（= 默认值）不触发（默认×默认不查——UWB/DIGIT/COORD 共
    UART_1 现状合法）。"""
    _uart_conflict_check(SWAP_BINDINGS)  # 五模块选中：换位合法
    _uart_conflict_check({})
    _uart_conflict_check(
        {"debug_uart.DEBUG_UART_TX": "PA2", "debug_uart.DEBUG_UART_RX": "PA3"}
    )
    # mspm0 无 USART 聚合语义不适用
    from contest_generator.generator import _check_uart_instance_conflicts

    _check_uart_instance_conflicts(
        _corpus(), ALL_MANIFESTS, "mspm0",
        GateContext(bindings={"motor.AA": "PA8"}, board=BOARDS["mspm0"]),
    )


def test_error_entry_maps_uart_instance_conflict_to_400():
    """UartInstanceConflictError 显式登记 error_to_http 表 → 400 中文。"""
    from contest_generator.generator import UartInstanceConflictError

    status, message = error_entry(
        UartInstanceConflictError(
            "绑定冲突：debug_uart.DEBUG_UART_TX（绑 PB10，推导实例 UART_3）"
            "与未绑定的 zigbee_uart.ZIGBEE_UART_TX 默认实例 UART_3 冲突"
        )
    )
    assert status == 400
    assert "默认实例 UART_3" in message


# ---------------------------------------------------------------------------
# 绿证：渲染器宏值 + USARTx_IRQ_CALLS 重分组
# ---------------------------------------------------------------------------


def test_render_pin_config_uart_swap_macro_values():
    """三组换位 → 每角色 _UART/_INST/_TX_GPIO/_TX_Pin/_RX_GPIO/_RX_Pin 六宏
    换值；注释旧引脚字样同步替换。"""
    out = render_pin_config(STM32_MASTER_PIN_CONFIG, _resolve(SWAP_BINDINGS))
    # DEBUG UART_2 → UART_3（PB10 TX / PB11 RX）
    assert "#define DEBUG_UART             UART_3\r\n" in out
    assert "#define DEBUG_UART_INST        USART3\r\n" in out
    assert "#define DEBUG_UART_TX_GPIO GPIO_B" in out
    assert "#define DEBUG_UART_TX_Pin Pin_10" in out
    assert "#define DEBUG_UART_RX_GPIO GPIO_B" in out
    assert "#define DEBUG_UART_RX_Pin Pin_11" in out
    # ZIGBEE UART_3 → UART_2（PA2 TX / PA3 RX）
    assert "#define ZIGBEE_UART       UART_2\r\n" in out
    assert "#define ZIGBEE_UART_INST  USART2\r\n" in out
    assert "#define ZIGBEE_UART_TX_GPIO GPIO_A" in out
    assert "#define ZIGBEE_UART_TX_Pin Pin_2" in out
    assert "#define ZIGBEE_UART_RX_GPIO GPIO_A" in out
    assert "#define ZIGBEE_UART_RX_Pin Pin_3" in out
    # UWB UART_1 → UART_2（PA2 TX / PA3 RX）
    assert "#define UWB_UART          UART_2\r\n" in out
    assert "#define UWB_UART_INST     USART2\r\n" in out
    assert "#define UWB_UART_TX_GPIO GPIO_A" in out
    assert "#define UWB_UART_TX_Pin Pin_2" in out
    assert "#define UWB_UART_RX_GPIO GPIO_A" in out
    assert "#define UWB_UART_RX_Pin Pin_3" in out
    # 未绑角色不动（DIGIT/COORD 仍 UART_1）
    assert "#define DIGIT_UART             UART_1\r\n" in out
    assert "#define COORD_DETECT_UART       UART_1\r\n" in out


def test_render_pin_config_uart_swap_irq_calls_regrouped():
    """USARTx_IRQ_CALLS 重分组：默认分组按绑定实例重排——USART1 只剩
    digit+coord（uwb 移出）、USART2 = uwb+zigbee（debug 移出、按默认序
    追加）、USART3 = debug。"""
    out = render_pin_config(STM32_MASTER_PIN_CONFIG, _resolve(SWAP_BINDINGS))
    assert (
        "#define USART1_IRQ_CALLS digit_uart_rx_handler(); coord_detect_rx_handler();\r\n"
        in out
    )
    assert (
        "#define USART2_IRQ_CALLS uwb_rx_handler(); zigbee_rx_handler();\r\n" in out
    )
    assert "#define USART3_IRQ_CALLS debug_uart_rx_handler();\r\n" in out


def test_render_pin_config_default_irq_calls_byte_identical():
    """非 uart 绑定不碰 CALLS 行：motor pwm 换脚 → CALLS 三行逐字节保持默认
    分组（缺位时 CALLS 宏不存在，渲染器对 pwm 绑定照旧逐字节 = 结构红）。"""
    from contest_generator.pin_bindings import ResolvedBinding

    motor_decl = next(
        m for m in ALL_MANIFESTS if m.slug == "motor"
    ).platforms["stm32"].pins[0]
    out = render_pin_config(
        STM32_MASTER_PIN_CONFIG,
        (
            ResolvedBinding(
                slug="motor",
                declaration=motor_decl,
                pin="PA6",
                instances=("TIM3_CH1",),
            ),
        ),
    )
    assert "#define USART1_IRQ_CALLS digit_uart_rx_handler(); coord_detect_rx_handler(); uwb_rx_handler();\r\n" in out
    assert "#define USART2_IRQ_CALLS debug_uart_rx_handler();\r\n" in out
    assert "#define USART3_IRQ_CALLS zigbee_rx_handler();\r\n" in out


def test_generate_stm32_uart_swap_and_default_byte_identical(tmp_path):
    """generate 集成：三组换位 → pin_config.h 宏值变（fputc 流随 DEBUG_UART
    挪位）；缺省路径 → pin_config.h/isr.c 与母版逐字节。"""
    manifests = _uart_manifests()
    out_dir = tmp_path / "out_bound"
    generate(
        platform="stm32",
        manifests=manifests,
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out_dir,
        main_c_content="int main(void) { while (1); }\n",
        bindings=SWAP_BINDINGS,
    )
    written = (out_dir / PIN_CONFIG_FILENAME).read_text(encoding="utf-8", newline="")
    assert "#define DEBUG_UART_INST        USART3" in written
    assert "#define ZIGBEE_UART_INST  USART2" in written
    assert "#define USART2_IRQ_CALLS uwb_rx_handler(); zigbee_rx_handler();" in written
    assert written != STM32_MASTER_PIN_CONFIG

    out_dir2 = tmp_path / "out_default"
    generate(
        platform="stm32",
        manifests=manifests,
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out_dir2,
        main_c_content="int main(void) { while (1); }\n",
    )
    assert (
        out_dir2 / PIN_CONFIG_FILENAME
    ).read_text(encoding="utf-8", newline="") == STM32_MASTER_PIN_CONFIG
    assert (
        out_dir2 / "isr.c"
    ).read_text(encoding="utf-8", newline="") == (STM32_MASTER / "isr.c").read_text(
        encoding="utf-8", newline=""
    )


# ---------------------------------------------------------------------------
# 绿证：母版 C 侧结构钉（ml_uart.c / isr.c / 五模块 init / uvprojx）
# ---------------------------------------------------------------------------

ML_UART_C = STM32_MASTER / "ml_libs" / "ml_uart.c"
ML_UART_H = STM32_MASTER / "ml_libs" / "ml_uart.h"
ISR_C = STM32_MASTER / "isr.c"


def test_ml_uart_fputc_follows_debug_uart_inst():
    """fputc 改 DEBUG_UART_INST->SR/DR（printf 流随 DEBUG_UART 宏挪位）——
    写死 USART1->SR/DR 即红；ml_uart.c include pin_config.h。"""
    text = ML_UART_C.read_text(encoding="utf-8", errors="replace")
    assert '#include "pin_config.h"' in text
    assert "DEBUG_UART_INST->SR" in text
    assert "DEBUG_UART_INST->DR" in text
    assert "USART1->SR" not in text
    assert "USART1->DR" not in text


def test_ml_uart_pin_init_ex_parameterized():
    """uart_pin_init_ex 引脚参数化：函数声明（ml_uart.h）+ 定义（ml_uart.c，
    RCC/NVIC 公式沿用 uart_init）+ 旧 uart_pin_init switch 表保留（供旧
    调用方 zigbee_uart_key）。形参用 uint8_t（ml_gpio.h 枚举经
    ml_gpio.h→headfile.h→ml_uart.h 循环 include 时在 ml_uart.h 处尚未定义
    ——真机 UV4 4 错判例，定义体内显式转换回枚举）。"""
    source = ML_UART_C.read_text(encoding="utf-8", errors="replace")
    header = ML_UART_H.read_text(encoding="utf-8", errors="replace")
    assert (
        "void uart_pin_init_ex(UARTn_enum uartn, uint8_t tx_gpio, uint8_t"
        " tx_pin, uint8_t rx_gpio, uint8_t rx_pin)" in header
    )
    assert "void uart_pin_init_ex(UARTn_enum uartn" in source
    assert "gpio_init((GPIOn_enum)tx_gpio, (Pinx_enum)tx_pin, AF_PP);" in source
    assert "gpio_init((GPIOn_enum)rx_gpio, (Pinx_enum)rx_pin, ID);" in source
    assert "RCC->APB2ENR |= 1<<14;" in source  # UART_1 在 APB2 的 RCC 公式
    assert "RCC->APB1ENR |= 1<<(uartn+16);" in source
    assert "NVIC_init(0x01,uartn+37);" in source or "NVIC_init(0x01, uartn+37);" in source
    assert "void uart_pin_init(UARTn_enum uartn)" in source  # 旧函数保留
    assert "case UART_1:" in source  # switch 表仍在


def test_master_isr_c_aggregates_usart_handlers():
    """母版 isr.c：include pin_config.h + 5 个 __weak *_rx_handler 空兜底
    （未选模块链接不炸）+ 3 个 USARTx_IRQHandler 调 USARTx_IRQ_CALLS 聚合
    宏（按绑定实例分组）。"""
    text = ISR_C.read_text(encoding="utf-8")
    assert '#include "pin_config.h"' in text
    for handler in (
        "digit_uart_rx_handler",
        "coord_detect_rx_handler",
        "debug_uart_rx_handler",
        "uwb_rx_handler",
        "zigbee_rx_handler",
    ):
        assert f"__weak void {handler}(void)" in text, handler
    for instance in ("USART1_IRQHandler", "USART2_IRQHandler", "USART3_IRQHandler"):
        assert f"void {instance}(void)" in text, instance
        assert f"{instance[:-7]}_CALLS" in text, instance  # USARTx_IRQ_CALLS 调用


def test_module_uarts_init_via_pin_init_ex_with_macros():
    """五模块 stm32 init 改调 uart_pin_init_ex 传各自 TX/RX 宏（引脚由
    pin_config.h 单源，switch 表第二层锁拆除）；rx_handler 非 static（isr.c
    weak 兜底依赖链接覆盖）。"""
    cases = {
        "debug_uart/code/debug_uart.c": (
            "DEBUG_UART", "DEBUG_UART_TX_GPIO", "DEBUG_UART_RX_Pin"
        ),
        "uwb_uart/code/uwb_uart.c": ("UWB_UART", "UWB_UART_TX_GPIO", "UWB_UART_RX_Pin"),
        "zigbee_uart/code/zigbee_uart.c": (
            "ZIGBEE_UART", "ZIGBEE_UART_TX_GPIO", "ZIGBEE_UART_RX_Pin"
        ),
        "digit_uart/code/digit_uart.c": (
            "DIGIT_UART", "DIGIT_UART_TX_GPIO", "DIGIT_UART_RX_Pin"
        ),
        "coord_detect/code/coord_detect_stm32.c": (
            "COORD_DETECT_UART", "COORD_DETECT_UART_TX_GPIO", "COORD_DETECT_UART_RX_Pin"
        ),
    }
    for rel, (instance, tx_gpio, rx_pin) in cases.items():
        text = (LIBRARY_MODULES / rel).read_text(encoding="utf-8")
        assert f"uart_pin_init_ex({instance}," in text, rel
        assert tx_gpio in text and rx_pin in text, rel
        assert re.search(r"\buart_init\(", text) is None, rel
    # rx_handler 均非 static（链接覆盖依赖）
    handlers = {
        "digit_uart/code/digit_uart.c": "digit_uart_rx_handler",
        "coord_detect/code/coord_detect_stm32.c": "coord_detect_rx_handler",
        "debug_uart/code/debug_uart.c": "debug_uart_rx_handler",
        "uwb_uart/code/uwb_uart.c": "uwb_rx_handler",
        "zigbee_uart/code/zigbee_uart.c": "zigbee_rx_handler",
    }
    for rel, handler in handlers.items():
        text = (LIBRARY_MODULES / rel).read_text(encoding="utf-8")
        assert f"void {handler}(void)" in text, rel
        assert f"static void {handler}" not in text, rel


def test_no_usart_handlers_in_main_gate():
    """main.c 不得定义 USART1/2/3_IRQHandler（真机 UV4 L6200E multiply
    defined 判例：骨架 LLM 按旧模块头注释"USART1 中断调用"在 main.c 写
    handler，撞母版 isr.c 强符号）→ 400 中文；注释里提到 handler 名不误伤
    （clex 注释剥离后判定）；mspm0 不适用。"""
    from contest_generator.generator import UsartHandlerInMainError

    from contest_generator.generator import _check_no_usart_handlers_in_main

    with pytest.raises(UsartHandlerInMainError, match="USART1_IRQHandler"):
        _check_no_usart_handlers_in_main(
            _corpus("void USART1_IRQHandler(void) { uwb_rx_handler(); }\n"),
            ALL_MANIFESTS,
            "stm32",
            GateContext(),
        )
    # 注释/其它形态直过
    _check_no_usart_handlers_in_main(
        _corpus("int main(void) { /* USART1_IRQHandler 归 isr.c */ while (1); }\n"),
        ALL_MANIFESTS,
        "stm32",
        GateContext(),
    )
    # mspm0 不适用（UART 中断挂载形态在 SysConfig 生成侧）：同名定义不拦
    _check_no_usart_handlers_in_main(
        _corpus("void USART1_IRQHandler(void) { digit_uart_rx_handler(); }\n"),
        ALL_MANIFESTS,
        "mspm0",
        GateContext(),
    )


def test_error_entry_maps_usart_handler_in_main_to_400():
    """UsartHandlerInMainError 显式登记 error_to_http 表 → 400 中文。"""
    from contest_generator.generator import UsartHandlerInMainError

    status, message = error_entry(
        UsartHandlerInMainError(
            "main.c 不得定义 USARTx_IRQHandler（USART1_IRQHandler）"
        )
    )
    assert status == 400
    assert "USART1_IRQHandler" in message


def test_master_uvprojx_includes_isr_c():
    """母版 uvprojx 文件树含 isr.c 条目（uvprojx 确定性渲染器按顶层目录分组
    全 .c 引用 → 根级 isr.c 进 user 组；母版静态 uvprojx 同步手改）。"""
    text = (STM32_MASTER / "user" / "Project.uvprojx").read_text(encoding="utf-8")
    assert "<FileName>isr.c</FileName>" in text
    assert "<FilePath>..\\isr.c</FilePath>" in text
