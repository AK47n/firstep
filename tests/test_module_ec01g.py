"""ec01g NB-IoT+GPS 模块（B 类新 slug——仅 stm32 条目、无 mspm0 对照）：真实库
+ 真实母版不变量与 stm32 单选生成。

与 hc05（UART 中断件）/ esp01s（AT 透传件）同款结构测试：manifest 形状
（仅 stm32、无依赖——delay_ms 走母版 ml_delay 内嵌、TX/RX = UART_3 宿主与 Zigbee/
LoRa 无线互替）、**isr.c 聚合登记 ec01g_rx_handler**（pinwriter
_UART_CALLS_ROLES + __weak + USART3_IRQ_CALLS）、stm32 单选生成、缺陷守卫
（空指针保护 NULL 检查、有界扫、%2096 回绕修正、缓冲 256 截断、HTTP/JSON
demo 不落）。全程无 LLM、无服务。
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
    '#include "ec01g_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    ec01g_init();\n"
    '    (void)ec01g_send_cmd("AT");\n'
    '    ec01g_send_string("x");\n'
    "    static uint8_t buf[128];\n"
    "    (void)ec01g_available();\n"
    "    (void)ec01g_receive(buf, sizeof(buf));\n"
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
    (r"%\s*EC01G_RX_BUF_SIZE|%2096", "% 回绕式（页面 (len+1)%2096 修正）"),
    (r"\bJSON\b|\bweather\b|\bWeather\b|Seniverse|Hex_To_Text|Search_Data",
     "HTTP 天气/JSON 解析 demo 残留"),
    (r"\bstrstr\b|\bstrlen\b", "C 库串函数（手写有界匹配）"),
]


def test_ec01g_manifest_shape_stm32():
    """B 类口径：仅 stm32 平台条目（无 mspm0）；依赖 delay；TX/RX = UART_3。"""
    manifest = ModuleManifest.load(MODULES / "ec01g")
    assert manifest.slug == "ec01g"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"stm32"}

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ec01g_stm32.c",
        "ec01g_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ec01g" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        (
            "EC01G_TX",
            "uart_tx",
            "PB10",
            True,
            ("EC01G_UART", "EC01G_UART_INST", "EC01G_UART_TX_GPIO", "EC01G_UART_TX_Pin"),
        ),
        (
            "EC01G_RX",
            "uart_rx",
            "PB11",
            True,
            ("EC01G_UART_RX_GPIO", "EC01G_UART_RX_Pin"),
        ),
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/rf/ec01g-nbiot-gps-module.html"
    )
    for needle in (
        "B 类：无 mspm0 条目",
        "lckfb-地阔星移植手册/rf--ec01g-nbiot-gps-module.md",
        "UART_3",
        "9600",
        "互替",
        "ec01g_rx_handler",
        "无 GPS 代码",
        "未上板",
    ):
        assert needle in stm32.notes
    # 能力方向（简介判据③）：NB-IoT 通信/AT 指令方向 + 无题绑定
    assert "NB-IoT" in manifest.description
    for banned in ("21F", "2024H", "2026H", "题目", "专用"):
        assert banned not in manifest.description


def test_ec01g_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：ec01g 六宏在母版 pin_config.h（UART_3/USART3/PB10/PB11）
    + 默认聚合 USART3_IRQ_CALLS 含 ec01g_rx_handler。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    assert re.search(r"#define\s+EC01G_UART\s+UART_3", text)
    assert re.search(r"#define\s+EC01G_UART_INST\s+USART3", text)
    assert re.search(r"#define\s+EC01G_UART_TX_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+EC01G_UART_TX_Pin\s+Pin_10", text)
    assert re.search(r"#define\s+EC01G_UART_RX_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+EC01G_UART_RX_Pin\s+Pin_11", text)
    m = re.search(r"#define\s+USART3_IRQ_CALLS\s+(.*)", text)
    assert m is not None
    assert "ec01g_rx_handler();" in m.group(1)


def test_ec01g_stm32_isr_weak_stub():
    """母版 isr.c：__weak ec01g_rx_handler 空兜底（选中模块强定义覆盖）。"""
    text = (STM32_MASTER / "isr.c").read_text(encoding="utf-8")
    assert "__weak void ec01g_rx_handler(void) {}" in text


def test_ec01g_stm32_pinwriter_roles_registered():
    """pinwriter：_UART_CALLS_ROLES 含 EC01G_UART→ec01g_rx_handler。"""
    text = (
        Path(__file__).resolve().parents[1] / "src" / "contest_generator"
        / "pinwriter.py"
    )
    src = text.read_text(encoding="utf-8")
    assert '"EC01G_UART", "ec01g_rx_handler"' in src


def test_ec01g_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：模块文件落盘、uvprojx 注册 ec01g_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ec01g"])
    assert {m.slug for m in resolved.manifests} == {"ec01g"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ec01g/code/ec01g_stm32.c").is_file()
    assert (out / "modules/ec01g/code/ec01g_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ec01g_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ec01g_stm32_code_guards():
    """stm32 代码层守卫：9600、线性缓冲 256 截断（无 %2096 回绕）、
    按长度 NUL 终结（IDLE 断串修正）、有界扫、空指针保护（NULL 检查）、
    API 5 函数、HTTP/JSON demo 不落、零引脚字面量。"""
    c = (MODULES / "ec01g" / "code" / "ec01g_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "ec01g" / "code" / "ec01g_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    assert "#define EC01G_RX_BUF_SIZE     256u" in h
    assert "#define EC01G_CMD_TIMEOUT_MS  1000u" in h
    assert "#define EC01G_BAUDRATE        9600" in h
    # 线性缓冲 + 截断（回绕修正）；按长度 NUL 终结（IDLE 断串修正）
    assert "EC01G_RX_BUF_SIZE - 1u" in code_only
    assert "_rx[_rx_len] = 0;" in code_only
    # 空指针保护（页面 Get_Weather_Data rev_buff=NULL 崩溃修正同源）
    assert "cmd == NULL" in code_only
    assert "buf == NULL" in code_only
    # 有界扫（_buf_contains 带上限——页面 Search_Data 无界扫修正）
    assert "i + (uint16_t)nlen <= _rx_len" in code_only
    # 应答匹配（页面 strstr 原语化——手写 _buf_contains）
    assert '_buf_contains("OK")' in c
    # API 5 函数与 ml_uart/SR 直读换算
    assert "void ec01g_init(" in code_only
    for fn in ("ec01g_send_cmd", "ec01g_send_string", "ec01g_available",
               "ec01g_receive"):
        assert f"{fn}(" in code_only, fn
    assert "uint8_t ec01g_send_cmd(" in code_only
    assert "uart_pin_init_ex(EC01G_UART, EC01G_UART_TX_GPIO," in code_only
    assert "uart_baud_config(EC01G_UART, EC01G_BAUDRATE)" in code_only
    assert "EC01G_UART_INST->SR & 0x20u" in code_only
    assert "PB10" not in code_only and "PB11" not in code_only
