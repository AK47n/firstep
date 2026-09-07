"""esp01s WiFi 模块（B 类新 slug——仅 stm32 条目、无 mspm0 对照）：真实库 +
真实母版不变量与 stm32 单选生成。

与 hc05（UART 中断件）/ ec11（B 类）同款结构测试：manifest 形状（仅 stm32、
无依赖——delay_ms 走母版 ml_delay 内嵌、TX/RX = UART_1 宿主）、**isr.c 聚合登记
esp01s_rx_handler**（pinwriter _UART_CALLS_ROLES + __weak + USART1_IRQ_CALLS）、
stm32 单选生成、缺陷守卫（无 % 200 回绕式、IDLE 断串修正、有界扫、缓冲 200
截断、+IPD 解析）。全程无 LLM、无服务。
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
    '#include "esp01s_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    esp01s_init();\n"
    '    (void)esp01s_send_cmd("AT");\n'
    '    esp01s_send_string("hi");\n'
    "    static uint8_t buf[128];\n"
    "    (void)esp01s_available();\n"
    "    (void)esp01s_receive(buf, sizeof(buf));\n"
    "    static uint8_t ipd[64];\n"
    "    uint8_t id = 0;\n"
    "    uint16_t n = 0;\n"
    "    (void)esp01s_parse_ipd(&id, &n, ipd, sizeof(ipd));\n"
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
    (r"%\s*ESP01S_RX_BUF_SIZE", "% MAX 回绕式（页面 (len+1)%200 修正）"),
    (r"\bMQTT\b|\bAliyun\b|\baliyun\b|hmacsha1", "MQTT/阿里云 demo 残留"),
    (r"\bstrstr\b|\bstrlen\b", "C 库串函数（手写有界匹配）"),
]


def test_esp01s_manifest_shape_stm32():
    """B 类口径：仅 stm32 平台条目（无 mspm0）；依赖 delay；TX/RX = UART_1。"""
    manifest = ModuleManifest.load(MODULES / "esp01s")
    assert manifest.slug == "esp01s"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"stm32"}

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "esp01s_stm32.c",
        "esp01s_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "esp01s" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        (
            "ESP01S_TX",
            "uart_tx",
            "PA9",
            True,
            ("ESP01S_UART", "ESP01S_UART_INST", "ESP01S_UART_TX_GPIO", "ESP01S_UART_TX_Pin"),
        ),
        (
            "ESP01S_RX",
            "uart_rx",
            "PA10",
            True,
            ("ESP01S_UART_RX_GPIO", "ESP01S_UART_RX_Pin"),
        ),
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/rf/esp01s-wifi-module.html"
    )
    for needle in (
        "B 类：无 mspm0 条目",
        "lckfb-地阔星移植手册/rf--esp01s-wifi-module.md",
        "UART_1",
        "115200",
        "互替",
        "esp01s_rx_handler",
        "回绕",
        "未上板",
    ):
        assert needle in stm32.notes
    # 能力方向（简介判据③）：WiFi 连接/AT 透传方向 + 无题绑定
    assert "WiFi" in manifest.description
    for banned in ("21F", "2024H", "2026H", "题目", "专用"):
        assert banned not in manifest.description


def test_esp01s_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：esp01s 六宏在母版 pin_config.h（UART_1/USART1/PA9/PA10）
    + 默认聚合 USART1_IRQ_CALLS 含 esp01s_rx_handler。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    assert re.search(r"#define\s+ESP01S_UART\s+UART_1", text)
    assert re.search(r"#define\s+ESP01S_UART_INST\s+USART1", text)
    assert re.search(r"#define\s+ESP01S_UART_TX_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+ESP01S_UART_TX_Pin\s+Pin_9", text)
    assert re.search(r"#define\s+ESP01S_UART_RX_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+ESP01S_UART_RX_Pin\s+Pin_10", text)
    m = re.search(r"#define\s+USART1_IRQ_CALLS\s+(.*)", text)
    assert m is not None
    assert "esp01s_rx_handler();" in m.group(1)


def test_esp01s_stm32_isr_weak_stub():
    """母版 isr.c：__weak esp01s_rx_handler 空兜底（选中模块强定义覆盖）。"""
    text = (STM32_MASTER / "isr.c").read_text(encoding="utf-8")
    assert "__weak void esp01s_rx_handler(void) {}" in text


def test_esp01s_stm32_pinwriter_roles_registered():
    """pinwriter：_UART_CALLS_ROLES 含 ESP01S_UART→esp01s_rx_handler。"""
    text = (
        Path(__file__).resolve().parents[1] / "src" / "contest_generator"
        / "pinwriter.py"
    )
    src = text.read_text(encoding="utf-8")
    assert '"ESP01S_UART", "esp01s_rx_handler"' in src


def test_esp01s_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：模块文件落盘、uvprojx 注册 esp01s_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["esp01s"])
    assert {m.slug for m in resolved.manifests} == {"esp01s"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/esp01s/code/esp01s_stm32.c").is_file()
    assert (out / "modules/esp01s/code/esp01s_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("esp01s_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_esp01s_stm32_code_guards():
    """stm32 代码层守卫：115200、线性缓冲 200 截断（无 %200 回绕）、
    按长度 NUL 终结（IDLE 断串修正）、有界扫描（while 含上限条件）、
    strstr 命中匹配、+IPD 解析、API 6 函数、零引脚字面量。"""
    c = (MODULES / "esp01s" / "code" / "esp01s_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "esp01s" / "code" / "esp01s_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert "#define ESP01S_RX_BUF_SIZE     200u" in h
    assert "#define ESP01S_CMD_TIMEOUT_MS  1000u" in h
    assert "#define ESP01S_BAUDRATE        115200" in h
    # 线性缓冲 + 截断（回绕修正）；按长度 NUL 终结（IDLE 断串修正）
    assert "ESP01S_RX_BUF_SIZE - 1u" in code_only
    assert "_rx[_rx_len] = 0;" in code_only
    # 有界扫描（+IPD 定位/id/len 都带 i < _rx_len 上限）
    assert "i + 5u <= _rx_len" in code_only
    assert re.search(r"while \(i < _rx_len", code_only)
    # 应答匹配（页面 strstr 原语化——手写 _buf_contains；双引号串在
    # strip_comments 会被吞，按原始源码断言）
    assert '_buf_contains("OK")' in c
    # +IPD 载荷拷贝（缓冲上限修正）
    assert "olen < max - 1u" in code_only
    # API 6 函数与 ml_uart/SR 直读换算
    for fn in ("esp01s_send_cmd", "esp01s_send_string", "esp01s_available",
               "esp01s_receive", "esp01s_parse_ipd"):
        assert f"{fn}(" in code_only, fn
    assert "uart_pin_init_ex(ESP01S_UART, ESP01S_UART_TX_GPIO," in code_only
    assert "uart_baud_config(ESP01S_UART, ESP01S_BAUDRATE)" in code_only
    assert "ESP01S_UART_INST->SR & 0x20u" in code_only
    assert "PA9" not in code_only and "PA10" not in code_only
