"""nrf24l01 2.4G 无线模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / hc05 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
六角色默认 = 母版 syscfg 由 test_pins.py / test_pin_bindings.py 守）、
mspm0 单选生成（syscfg 裁剪保留 NRF24L01 + delay 依赖文件落盘、main.c 调
init/收发过静态门禁）。软 SPI 位操作不占 SPI 外设；IRQ 轮询不注册 GROUP1
中断（motor 编码器独占）。全程无 LLM、无服务。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "nrf24l01.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    nrf24l01_init();\n"
    "    nrf24l01_set_mode(NRF24L01_MODE_TX);\n"
    "    uint8_t tx[8] = {1, 2, 3, 4, 5, 6, 7, 8};\n"
    "    uint8_t result = nrf24l01_tx_packet(tx, 8);\n"
    "    (void)result;\n"
    "    nrf24l01_set_mode(NRF24L01_MODE_RX);\n"
    "    uint8_t rx[32];\n"
    "    uint8_t got = nrf24l01_rx_packet(rx, sizeof(rx));\n"
    "    (void)got;\n"
    "    nrf24l01_flush_rx();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_nrf24l01_manifest_shape_mspm0():
    """nrf24l01：仅 mspm0 平台条目；依赖 delay；六角色默认。"""
    manifest = ModuleManifest.load(MODULES / "nrf24l01")
    assert manifest.slug == "nrf24l01"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0", "stm32"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["nrf24l01.c", "nrf24l01.h"]
    for rel in mspm0.files:
        assert (MODULES / "nrf24l01" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("NRF24L01_CLK", "gpio_out", "PA26", True, ()),
        ("NRF24L01_MOSI", "gpio_out", "PA25", True, ()),
        ("NRF24L01_MISO", "gpio_in", "PA9", True, ()),
        ("NRF24L01_CSN", "gpio_out", "PA24", True, ()),
        ("NRF24L01_CE", "gpio_out", "PA23", True, ()),
        ("NRF24L01_IRQ", "gpio_in", "PA22", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_nrf24l01_mspm0_syscfg_instance():
    """mspm0 母版必须有 NRF24L01 GPIO 实例：6 引脚（CLK/MOSI/MISO/CSN/CE/IRQ）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const NRF24L01 = GPIO.addInstance();" in syscfg
    assert "NRF24L01.associatedPins.create(6);" in syscfg
    assert 'NRF24L01.associatedPins[0].$name        = "CLK";' in syscfg
    assert 'NRF24L01.associatedPins[0].pin.$assign  = "PA26";' in syscfg
    assert 'NRF24L01.associatedPins[1].$name        = "MOSI";' in syscfg
    assert 'NRF24L01.associatedPins[1].pin.$assign  = "PA25";' in syscfg
    assert 'NRF24L01.associatedPins[2].$name        = "MISO";' in syscfg
    assert 'NRF24L01.associatedPins[2].direction    = "INPUT";' in syscfg
    assert 'NRF24L01.associatedPins[2].pin.$assign  = "PA9";' in syscfg
    assert 'NRF24L01.associatedPins[3].$name        = "CSN";' in syscfg
    assert 'NRF24L01.associatedPins[3].pin.$assign  = "PA24";' in syscfg
    assert 'NRF24L01.associatedPins[4].$name        = "CE";' in syscfg
    assert 'NRF24L01.associatedPins[4].pin.$assign  = "PA23";' in syscfg
    assert 'NRF24L01.associatedPins[5].$name        = "IRQ";' in syscfg
    assert 'NRF24L01.associatedPins[5].direction    = "INPUT";' in syscfg
    assert 'NRF24L01.associatedPins[5].pin.$assign  = "PA22";' in syscfg


def test_nrf24l01_mspm0_single_select_generation(tmp_path):
    """nrf24l01 mspm0 单选生成：syscfg 只留 NRF24L01、模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["nrf24l01"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_MSPM0,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=MSPM0_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_MSPM0,
    )
    syscfg = (out / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const NRF24L01 = GPIO.addInstance();" in syscfg
    assert 'NRF24L01.associatedPins[0].pin.$assign  = "PA26";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "JOYSTICK",
        "HC05", "IR_REMOTE", "DIGIT_UART", "DEBUG_UART", "UWB_UART",
        "ZIGBEE_UART", "IMU601", "OLED", "I2C_0", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/nrf24l01/code/nrf24l01.c").is_file()
    assert (out / "modules/nrf24l01/code/nrf24l01.h").is_file()
    # 依赖展开：delay 模块文件随选中落盘
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()


# ---------------------------------------------------------------------------
# wiki-stm32-batch8/03：stm32 平台条目（软 SPI 六脚位操作，全端口 B）
# ---------------------------------------------------------------------------

import re  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

from contest_generator.clex import strip_comments  # noqa: E402
from contest_generator.platforms import PLATFORM_STM32  # noqa: E402

STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"  # noqa: E402

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "nrf24l01_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    nrf24l01_init();\n"
    "    nrf24l01_set_channel(20);\n"
    "    nrf24l01_set_speed(NRF24L01_SPEED_1M);\n"
    "    nrf24l01_set_power(NRF24L01_POWER_0DBM);\n"
    "    static const uint8_t addr[5] = {1, 2, 3, 4, 5};\n"
    "    nrf24l01_set_address(addr, 5);\n"
    "    nrf24l01_set_mode(NRF24L01_MODE_TX);\n"
    "    static const uint8_t tx[8] = {1, 2, 3, 4, 5, 6, 7, 8};\n"
    "    (void)nrf24l01_tx_packet(tx, 8);\n"
    "    nrf24l01_set_mode(NRF24L01_MODE_RX);\n"
    "    static uint8_t rx[32];\n"
    "    (void)nrf24l01_rx_packet(rx, sizeof(rx));\n"
    "    nrf24l01_flush_rx();\n"
    "    nrf24l01_flush_tx();\n"
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
    (r"\bGPIO_WriteBit\b", "GPIO_WriteBit"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bSPI1\b", "SPI1（硬件 SPI 改软 SPI）"),
    (r"\bSPI_I2S_", "SPI_I2S_（硬件 SPI 改软 SPI）"),
    (r"\bEXTI\w*_IRQHandler\b", "EXTI IRQHandler（轮询不注册）"),
    (r"\bIRQHandler\b", "IRQHandler（轮询件）"),
]


def test_nrf24l01_manifest_shape_stm32():
    """stm32 条目：六角色（全端口 B 默认），每角色带共享 NRF24L01_PORT + PIN 宏。"""
    manifest = ModuleManifest.load(MODULES / "nrf24l01")
    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "nrf24l01_stm32.c",
        "nrf24l01_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "nrf24l01" / rel).is_file(), rel
    expect = [
        ("NRF24L01_CLK", "gpio_out", "PB10", ("NRF24L01_PORT", "NRF24L01_CLK_PIN")),
        ("NRF24L01_MOSI", "gpio_out", "PB11", ("NRF24L01_PORT", "NRF24L01_MOSI_PIN")),
        ("NRF24L01_MISO", "gpio_in", "PB4", ("NRF24L01_PORT", "NRF24L01_MISO_PIN")),
        ("NRF24L01_CSN", "gpio_out", "PB12", ("NRF24L01_PORT", "NRF24L01_CSN_PIN")),
        ("NRF24L01_CE", "gpio_out", "PB13", ("NRF24L01_PORT", "NRF24L01_CE_PIN")),
        ("NRF24L01_IRQ", "gpio_in", "PB5", ("NRF24L01_PORT", "NRF24L01_IRQ_PIN")),
    ]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        (pid, ptype, default, True, macros) for pid, ptype, default, macros in expect
    ]
    assert stm32.verified is True
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/rf/nrf24l01-2-4-g-control-module.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/rf--nrf24l01-2-4-g-control-module.md",
        "软 SPI",
        "互替件",
        "零延时",
        "未上板",
    ):
        assert needle in stm32.notes


def test_nrf24l01_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：nrf24l01 七宏在母版 pin_config.h（PORT=GPIO_B）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+NRF24L01_PORT\s+GPIO_B", text)
    assert re.search(r"#define\s+NRF24L01_CLK_PIN\s+Pin_10", text)
    assert re.search(r"#define\s+NRF24L01_MOSI_PIN\s+Pin_11", text)
    assert re.search(r"#define\s+NRF24L01_MISO_PIN\s+Pin_4", text)
    assert re.search(r"#define\s+NRF24L01_CSN_PIN\s+Pin_12", text)
    assert re.search(r"#define\s+NRF24L01_CE_PIN\s+Pin_13", text)
    assert re.search(r"#define\s+NRF24L01_IRQ_PIN\s+Pin_5", text)


def test_nrf24l01_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：依赖 delay 展开（stm32 files=[] 内嵌母版）、uvprojx 注册。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["nrf24l01"])
    assert {m.slug for m in resolved.manifests} == {"nrf24l01", "delay"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/nrf24l01/code/nrf24l01_stm32.c").is_file()
    assert (out / "modules/nrf24l01/code/nrf24l01_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("nrf24l01_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_nrf24l01_stm32_code_guards():
    """stm32 代码层守卫：软 SPI 位操作（gpio_set/get 六脚）、无硬件 SPI/EXTI/
    IRQHandler、返回码/枚举钉值、零引脚字面量、注释上游缺陷记录。"""
    c = (MODULES / "nrf24l01" / "code" / "nrf24l01_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "nrf24l01" / "code" / "nrf24l01_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    assert "#define NRF24L01_TX_OK   0x20" in h
    assert "#define NRF24L01_MAX_TX  0x10" in h
    assert "#define NRF24L01_RX_OK   0x40" in h
    assert "#define NRF24L01_PAYLOAD_MAX 32" in h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 SPI 位操作：gpio_set/gpio_get 六脚宏（零引脚字面量）
    assert "gpio_set(NRF24L01_PORT, NRF24L01_CLK_PIN" in code_only
    assert "gpio_set(NRF24L01_PORT, NRF24L01_MOSI_PIN" in code_only
    assert "gpio_get(NRF24L01_PORT, NRF24L01_MISO_PIN)" in code_only
    assert "gpio_get(NRF24L01_PORT, NRF24L01_IRQ_PIN)" in code_only
    assert "delay_ms(5)" in code_only  # TX 忙等超时（500ms）
    assert "PB10" not in code_only

