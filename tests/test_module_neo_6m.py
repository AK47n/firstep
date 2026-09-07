"""neo_6m GPS 定位模块（B 类新 slug——仅 stm32 条目、无 mspm0 对照）：真实库
+ 真实母版不变量与 stm32 单选生成。

与 hc05（UART 中断件）/ ec11（B 类）同款结构测试：manifest 形状（仅 stm32、
无依赖、TX/RX = UART_1 宿主）、**isr.c 聚合登记 neo_6m_rx_handler**（pinwriter
_UART_CALLS_ROLES + __weak + USART1_IRQ_CALLS）、stm32 单选生成（模块文件落盘、
uvprojx 注册）、缺陷守卫（255 越界 → 256 缓冲截断、memcpy 无长度检查 → 截断、
GPRMC 帧头全串判定、ddmm→十进制度换算）。全程无 LLM、无服务。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contest_generator.clex import strip_comments
from contest_generator.generator import generate
from contest_generator.manifest import ModuleManifest
from contest_generator.platforms import PLATFORM_STM32
from contest_generator.selection import resolve_selection

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "neo_6m_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    neo_6m_init();\n"
    "    (void)neo_6m_read_frame();\n"
    "    float lat = 0.0f;\n"
    "    float lon = 0.0f;\n"
    "    (void)neo_6m_get_position(&lat, &lon);\n"
    "    neo_6m_clear();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bUART_Init\b", "UART_Init（走 ml_uart）"),
    (r"\bUSART_Init\b", "USART_Init（走 ml_uart）"),
    (r"\bvoid\s+USART[123]_IRQHandler\b", "USARTx_IRQHandler 定义（归母版 isr.c）"),
    (r"\bGPSRX_BUFF\s*\[\s*255\s*\]", "页面 255 数组（越界）"),
    (r"\[255\]", "下标 255 越界式"),
    (r"\batoi\b|\batof\b|\bstrtod\b", "stdlib 解析（零标准库）"),
]


def test_neo_6m_manifest_shape_stm32():
    """B 类口径：仅 stm32 平台条目（无 mspm0）；无依赖；TX/RX = UART_1。"""
    manifest = ModuleManifest.load(MODULES / "neo_6m")
    assert manifest.slug == "neo_6m"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"stm32"}

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "neo_6m_stm32.c",
        "neo_6m_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "neo_6m" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        (
            "NEO_6M_TX",
            "uart_tx",
            "PA9",
            True,
            ("NEO_6M_UART", "NEO_6M_UART_INST", "NEO_6M_UART_TX_GPIO", "NEO_6M_UART_TX_Pin"),
        ),
        (
            "NEO_6M_RX",
            "uart_rx",
            "PA10",
            True,
            ("NEO_6M_UART_RX_GPIO", "NEO_6M_UART_RX_Pin"),
        ),
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/rf/neo-6m-gps-module.html"
    )
    for needle in (
        "B 类：无 mspm0 条目",
        "lckfb-地阔星移植手册/rf--neo-6m-gps-module.md",
        "UART_1",
        "9600",
        "互替",
        "neo_6m_rx_handler",
        "255",
        "未上板",
    ):
        assert needle in stm32.notes
    # 能力方向（简介判据③）：GPS 定位方向 + 无题绑定
    assert "GPS 定位" in manifest.description
    for banned in ("21F", "2024H", "2026H", "题目", "专用"):
        assert banned not in manifest.description


def test_neo_6m_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：neo_6m 六宏在母版 pin_config.h（UART_1/USART1/PA9/PA10）
    + 默认聚合 USART1_IRQ_CALLS 含 neo_6m_rx_handler。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    assert re.search(r"#define\s+NEO_6M_UART\s+UART_1", text)
    assert re.search(r"#define\s+NEO_6M_UART_INST\s+USART1", text)
    assert re.search(r"#define\s+NEO_6M_UART_TX_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+NEO_6M_UART_TX_Pin\s+Pin_9", text)
    assert re.search(r"#define\s+NEO_6M_UART_RX_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+NEO_6M_UART_RX_Pin\s+Pin_10", text)
    m = re.search(r"#define\s+USART1_IRQ_CALLS\s+(.*)", text)
    assert m is not None
    assert "neo_6m_rx_handler();" in m.group(1)


def test_neo_6m_stm32_isr_weak_stub():
    """母版 isr.c：__weak neo_6m_rx_handler 空兜底（选中模块强定义覆盖）。"""
    text = (STM32_MASTER / "isr.c").read_text(encoding="utf-8")
    assert "__weak void neo_6m_rx_handler(void) {}" in text


def test_neo_6m_stm32_pinwriter_roles_registered():
    """pinwriter：_UART_CALLS_ROLES 含 NEO_6M_UART→neo_6m_rx_handler。"""
    text = (
        Path(__file__).resolve().parents[1] / "src" / "contest_generator"
        / "pinwriter.py"
    )
    src = text.read_text(encoding="utf-8")
    assert '"NEO_6M_UART", "neo_6m_rx_handler"' in src


def test_neo_6m_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：模块文件落盘、uvprojx 注册 neo_6m_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["neo_6m"])
    assert {m.slug for m in resolved.manifests} == {"neo_6m"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/neo_6m/code/neo_6m_stm32.c").is_file()
    assert (out / "modules/neo_6m/code/neo_6m_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("neo_6m_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_neo_6m_stm32_code_guards():
    """stm32 代码层守卫：9600、GPRMC 帧头全串判定、256 缓冲截断（无 [255] 越界）、
    帧拷贝截断（memcpy 无长度检查修正）、ddmm→十进制度换算、API 4 函数、
    走 ml_uart + SR/DR 直读（零引脚字面量/零标准库）。"""
    c = (MODULES / "neo_6m" / "code" / "neo_6m_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "neo_6m" / "code" / "neo_6m_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert "#define NEO_6M_RX_BUF_SIZE      256u" in h
    assert "#define NEO_6M_FRAME_BUF_SIZE   80u" in h
    assert "#define NEO_6M_BAUDRATE         9600" in h
    # 帧头判定：$ + GP|GN + RMC（页面只验 [4]/[5] 修正——char 字面量在
    # strip_comments 会被吞，按原始源码断言）
    assert "_rx[3] == 'R' && _rx[4] == 'M' && _rx[5] == 'C'" in c
    assert "byte == '$'" in c       # 帧起点（页面原样）
    assert "byte == '\\n'" in c      # 行尾帧结束
    # 越界/截断修正：缓冲上限判断 + 帧拷贝截断
    assert "NEO_6M_RX_BUF_SIZE - 1u" in code_only
    assert "copy_len >= NEO_6M_FRAME_BUF_SIZE" in code_only
    # ddmm.mmmm → 十进制度换算（无 stdlib）
    assert "int_part / 100u" in code_only
    assert "min / 60.0f" in code_only
    # API 4 函数与 ml_uart/SR 直读换算
    for fn in ("neo_6m_init", "neo_6m_read_frame", "neo_6m_get_position", "neo_6m_clear"):
        assert f"{fn}(" in code_only, fn
    assert "uart_pin_init_ex(NEO_6M_UART, NEO_6M_UART_TX_GPIO," in code_only
    assert "uart_baud_config(NEO_6M_UART, NEO_6M_BAUDRATE)" in code_only
    assert "NEO_6M_UART_INST->SR & 0x20u" in code_only
    assert "PA9" not in code_only and "PA10" not in code_only
