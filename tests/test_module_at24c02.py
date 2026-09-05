"""at24c02 EEPROM 存储器模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 aht10 / bh1750 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、
SCL/SDA 双 gpio_out 角色 = PB24/PB8——默认与母版 syscfg 一致性由
test_pins.py / test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留
AT24C02、模块文件落盘、main.c 调 init/write_byte/read_byte/write_page/
read_block/wait_write_done 过静态门禁）。软 I2C 位操作走 delay 模块；
0xA0/0xA1 地址宏命名纠正（页面 READ/WRITE 颠倒——上游缺陷记录见 manifest
notes）与 5ms 写周期常量源码守卫钉死。
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
    '#include "at24c02.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    at24c02_init();\n"
    "    at24c02_write_byte(0, 48);\n"
    "    at24c02_wait_write_done();\n"
    "    uint8_t dat1 = at24c02_read_byte(0);\n"
    "    (void)dat1;\n"
    "    uint8_t page[AT24C02_PAGE_SIZE] = {0};\n"
    "    if (at24c02_write_page(16, page, AT24C02_PAGE_SIZE) == 0) {\n"
    "        at24c02_wait_write_done();\n"
    "    }\n"
    "    uint8_t buf[4] = {0};\n"
    "    (void)at24c02_read_block(16, buf, 4);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_at24c02_manifest_shape_mspm0():
    """at24c02：仅 mspm0 平台条目；依赖 delay；SCL+SDA 双角色 gpio_out。"""
    manifest = ModuleManifest.load(MODULES / "at24c02")
    assert manifest.slug == "at24c02"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["at24c02.c", "at24c02.h"]
    for rel in mspm0.files:
        assert (MODULES / "at24c02" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("AT24C02_SCL", "gpio_out", "PB24", True, ()),
        ("AT24C02_SDA", "gpio_out", "PB8", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 页面地址宏颠倒缺陷必须记录在 notes
    assert "颠倒" in mspm0.notes


def test_at24c02_mspm0_syscfg_instances():
    """mspm0 母版：AT24C02 GPIO 实例（SCL/SDA 输出，运行时 SDA 切输入）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const AT24C02 = GPIO.addInstance();" in syscfg
    assert 'AT24C02.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'AT24C02.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'AT24C02.associatedPins[0].pin.$assign  = "PB24";' in syscfg
    assert 'AT24C02.associatedPins[1].pin.$assign  = "PB8";' in syscfg


def test_at24c02_mspm0_single_select_generation(tmp_path):
    """at24c02 mspm0 单选生成：syscfg 只留 AT24C02、模块文件落盘、门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["at24c02"])
    assert {m.slug for m in resolved.manifests} == {"at24c02", "delay"}
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
    assert "const AT24C02 = GPIO.addInstance();" in syscfg
    assert 'AT24C02.associatedPins[0].pin.$assign  = "PB24";' in syscfg
    assert 'AT24C02.associatedPins[1].pin.$assign  = "PB8";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "BH1750", "ADS1115", "TCS34725",
        "MLX90614", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "PWMAB",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/at24c02/code/at24c02.c").is_file()
    assert (out / "modules/at24c02/code/at24c02.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()


def test_at24c02_address_and_write_cycle_guards():
    """源码守卫：地址宏语义（0xA0=写、0xA1=读——页面宏名颠倒已纠正）与
    5ms 写周期常量不得回潮。"""
    header = (MODULES / "at24c02" / "code" / "at24c02.h").read_text(
        encoding="utf-8"
    )
    assert "AT24C02_ADDR_WRITE (AT24C02_ADDR << 1)" in header
    assert "AT24C02_ADDR_READ  ((AT24C02_ADDR << 1) | 1u)" in header
    assert "AT24C02_ADDR       (0x50u)" in header  # 页面 7 位地址（0x50<<1=0xA0）
    assert "AT24C02_WRITE_CYCLE_MS 5u" in header
    assert "AT24C02_PAGE_SIZE 16u" in header
    source = (MODULES / "at24c02" / "code" / "at24c02.c").read_text(
        encoding="utf-8"
    )
    # 页面颠倒宏名 `AT24C02_ADDRESS_READ/WRITE` 不得回潮
    assert "AT24C02_ADDRESS_READ" not in source
    assert "AT24C02_ADDRESS_WRITE" not in source
    assert "delay_ms(AT24C02_WRITE_CYCLE_MS)" in source  # 写完成等待封装
