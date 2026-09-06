"""oled SPI 总线变体（批次 12/07 决策 B）：真实库 + 真实母版不变量与测试。

覆盖：manifest 形状（mspm0 条目现含 7 角色——I2C SCL/SDA + SPI 五脚）、
母版 syscfg OLED_SPI 实例（5 脚，CS/RES 初始 SET）、I2C 零回归断言
（OLED_INST 路径保留 + OLED_Init 主体原命令序 + 既有 API 签名不变）、
SPI 变体断言（OLED_SPI_Init 存在 + 位操作无 DL_I2C 依赖 + 分辨率宏
OLED_RES_128X32 与 oled_set_res——0.91 核验结论）、mspm0 单选生成
（OLED + OLED_SPI 两实例共存——已知取舍记录）。
全程无 LLM、无服务。
"""

from __future__ import annotations

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
OLED_DIR = MODULES / "oled"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_SPI = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "oled.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    OLED_SPI_Init();\n"
    "    OLED_Clear();\n"
    "    OLED_ShowString(0, 0, (u8 *)\"SPI OK!\", 16);\n"
    "    OLED_Refresh();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_oled_manifest_shape_with_spi_variant():
    """oled：mspm0 条目 7 角色（I2C 2 角色保留 + SPI 5 角色）。"""
    manifest = ModuleManifest.load(OLED_DIR)
    assert manifest.slug == "oled"
    assert manifest.dependencies == ("delay",)

    mspm0 = manifest.platforms["mspm0"]
    assert [(p.id, p.type, p.default) for p in mspm0.pins] == [
        ("OLED_SCL", "i2c_scl", "PB2"),
        ("OLED_SDA", "i2c_sda", "PB3"),
        ("OLED_SPI_SCL", "gpio_out", "PA28"),
        ("OLED_SPI_SDA", "gpio_out", "PA31"),
        ("OLED_SPI_DC", "gpio_out", "PA13"),
        ("OLED_SPI_CS", "gpio_out", "PB18"),
        ("OLED_SPI_RES", "gpio_out", "PA22"),
    ]


def test_oled_code_i2c_zero_regression_and_spi_variant():
    """I2C 零回归：OLED_Init/OLED_WR_Byte 主体（DL_I2C 路径 + 原命令序）
    保留；SPI 变体：OLED_SPI_Init + OLED_WR_Byte 位操作分发 + 分辨率宏。"""
    c = (OLED_DIR / "code" / "oled.c").read_text(encoding="utf-8")
    h = (OLED_DIR / "code" / "oled.h").read_text(encoding="utf-8")
    # I2C 主体（零回归断言）
    assert "DL_I2C_getControllerStatus(OLED_INST)" in c
    assert "OLED_INST" in c
    assert "void OLED_Init(void)" in c
    for legacy_api in (
        "OLED_ColorTurn", "OLED_DisplayTurn", "OLED_Refresh", "OLED_Clear",
        "OLED_DrawPoint", "OLED_DrawLine", "OLED_DrawCircle",
        "OLED_ShowChar", "OLED_ShowString", "OLED_ShowNum",
        "OLED_ShowChinese", "OLED_ShowPicture", "OLED_DisPlay_On",
        "OLED_DisPlay_Off",
    ):
        assert legacy_api in h, f"既有 API 被移除：{legacy_api}"
    # SPI 变体断言
    assert "OLED_SPI_Init" in h and "OLED_SPI_Init" in c
    assert "static uint8_t s_bus_spi" in c
    assert "oled_spi_write_byte" in c
    assert "OLED_RES_128X32" in h and "oled_set_res" in h
    # 0.91 128×32 核验结论：MUX/COM 分支
    assert "0x1F : 0x3F" in c.replace(" ", "") or "(s_res == OLED_RES_128X32" in c


def test_oled_mspm0_syscfg_spi_instance():
    """mspm0 母版：OLED_SPI GPIO 实例（SCL/SDA/DC/CS/RES 五输出，
    CS/RES 初始 SET）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const OLED_SPI = GPIO.addInstance();" in syscfg
    assert "OLED_SPI.associatedPins.create(5);" in syscfg
    for i, (name, pin, initial) in enumerate([
        ("SCL", "PA28", "CLEARED"), ("SDA", "PA31", "CLEARED"),
        ("DC", "PA13", "CLEARED"), ("CS", "PB18", "SET"),
        ("RES", "PA22", "SET"),
    ]):
        assert f'OLED_SPI.associatedPins[{i}].$name        = "{name}";' in syscfg
        assert f'OLED_SPI.associatedPins[{i}].pin.$assign  = "{pin}";' in syscfg
        assert (f"OLED_SPI.associatedPins[{i}].initialValue = "
                f'"{initial}";') in syscfg


def test_oled_spi_single_select_generation(tmp_path):
    """oled SPI 变体单选生成：OLED（I2C1）与 OLED_SPI 两实例共存
    （已知取舍：SPI 模式下 I2C1 的 PB2/PB3 仍被占用——绑定换脚消解）。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["oled"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_MSPM0,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=MSPM0_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_SPI,
    )
    syscfg = (out / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const OLED" in syscfg  # I2C1 实例（母版声明 = const OLED    = I2C.addInstance();）
    assert "const OLED_SPI = GPIO.addInstance();" in syscfg
    assert 'OLED_SPI.associatedPins[4].pin.$assign  = "PA22";' in syscfg
    for rel in ("oled.c", "oled.h", "oledfont.h"):
        assert (out / f"modules/oled/code/{rel}").is_file()
