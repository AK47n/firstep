"""工单 pin-unlock-stm32/04：stm32 母版启动文件弱 handler 默认体 `B .`
（原地死循环）→ `BX LR`（安全返回）。

背景（spec）：生成工程无 isr.c、ml_nvic 无条件使能 RXNE 中断——任何模块
`uart_init(...,0x01)` 开中断后收到第一个字节即进弱 handler 死循环（编译全
绿、运行即挂）。修复 = 所有弱 handler 默认体改 BX LR；向量表 / Reset_Handler
/ 其余汇编不动。RX 数据仍无人消费（ISR 名联动 = 全解候选 ②，本单不做）。

契约：startup_stm32f10x_md.s 全文无 `B .`；10 个弱 dummy handler PROC 块
（9 个异常 handler + Default_Handler 共享体）默认体 `BX LR`；弱导出数与向
量表 DCD 数不变（handler 不丢、向量表不动）；生成产物 copytree 出来的
startup 逐字节同母版且同断言（真机产物同源）。

红证 = 断言修复后的状态：未修复时全文 10 处 `B .` → 红，修复后转绿。
"""

from __future__ import annotations

import re
from pathlib import Path

from contest_generator.generator import generate
from contest_generator.library import list_modules

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
LIBRARY_MODULES = LIBRARY_ROOT / "modules"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"
STARTUP_PATH = STM32_MASTER / "key" / "startup_stm32f10x_md.s"

STARTUP_TEXT = STARTUP_PATH.read_text(encoding="utf-8", newline="")

# `B .`（B 后空白再点）——弱 handler 死循环唯一形态；向量表 DCD 行与注释
# 均不含此词形。`BX LR`（含 __user_initial_stackheap 既有一处）。
B_DOT = re.compile(r"\bB\s+\.")
BX_LR = re.compile(r"\bBX\s+LR")
PROC_BLOCK = re.compile(r"PROC\b[\s\S]*?ENDP")
DCD_ENTRY = re.compile(r"^\s+DCD\s+", re.M)

# 结构不变量（防误删 handler / 误动向量表；计数来自 STM32F10x MD 标准模板）：
# [WEAK] = 9 异常 handler + Reset_Handler + 43 外设别名；DCD = 15 内核 + 43
# 外设；弱 dummy PROC 块 = 9 异常 handler + Default_Handler 共享体。
WEAK_EXPORT_COUNT = 53
DCD_COUNT = 58
DUMMY_HANDLER_BLOCKS = 10


def _weak_dummy_blocks(text: str) -> tuple[str, ...]:
    """每个含 [WEAK] 的 PROC 块（Reset_Handler 除外）的块文本。

    Reset_Handler 也是弱导出但其体是真实实现（BX R0 进 __main），不属于
    dummy 默认体；其余 10 块（9 异常 + Default_Handler 共享体）修复后
    默认体必须是 BX LR。
    """
    return tuple(
        block
        for block in PROC_BLOCK.findall(text)
        if "[WEAK]" in block and "Reset_Handler" not in block
    )


def test_startup_has_no_b_dot_deadloop():
    """全文零 `B .`——弱 handler 死循环清零（修复前 10 处 → 红证）。"""
    assert B_DOT.findall(STARTUP_TEXT) == []


def test_weak_dummy_handlers_return_via_bx_lr():
    """每个弱 dummy handler 默认体 BX LR 且无 B .；块数与 BX LR 总数钉死。"""
    blocks = _weak_dummy_blocks(STARTUP_TEXT)
    assert len(blocks) == DUMMY_HANDLER_BLOCKS
    for block in blocks:
        assert not B_DOT.search(block)
        assert BX_LR.search(block)
    # BX LR 总数 = 10 dummy 默认体 + __user_initial_stackheap 既有 1 处
    assert len(BX_LR.findall(STARTUP_TEXT)) == DUMMY_HANDLER_BLOCKS + 1


def test_weak_export_and_vector_table_counts_unchanged():
    """弱导出 53 处 / 向量表 DCD 58 条不变——修复不丢 handler、不动向量表。"""
    assert STARTUP_TEXT.count("[WEAK]") == WEAK_EXPORT_COUNT
    assert len(DCD_ENTRY.findall(STARTUP_TEXT)) == DCD_COUNT


def test_generated_product_startup_is_deadloop_free(tmp_path: Path):
    """生成产物 copytree 回归：产物 startup 逐字节同母版（修复随产物走）。"""
    motor = next(m for m in list_modules(LIBRARY_MODULES) if m.slug == "motor")
    out_dir = tmp_path / "out"
    generate(
        platform="stm32",
        manifests=[motor],
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out_dir,
        main_c_content="int main(void) { while (1); }\n",
    )
    product = out_dir / "key" / "startup_stm32f10x_md.s"
    text = product.read_text(encoding="utf-8", newline="")
    assert text == STARTUP_TEXT  # copytree 逐字节，弱 handler 修复随产物走
    assert B_DOT.findall(text) == []
    assert len(_weak_dummy_blocks(text)) == DUMMY_HANDLER_BLOCKS
