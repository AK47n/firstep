"""ags10 有害气体传感器模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 sht30/sgp30 同款结构测试：manifest 形状（仅 mspm0、依赖 delay、双角色
AGS10_SCL/AGS10_SDA = gpio_out PB18/PA14——软 I2C 2 脚不占硬件 I2C 外设）、
mspm0 单选生成（syscfg 裁剪保留 AGS10 实例 + 模块文件落盘 + main.c 调
init/read 过静态门禁）。CRC8 原式 / 重试条件修正（页面 `timeout >= 50`
写反——超时分支永不触发）/ 出参+状态收敛（页面返回值与错误码混用）源码
守卫钉死。全程无 LLM、无服务。
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
    '#include "ags10.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    ags10_init();\n"
    "    uint32_t voc = 0;\n"
    "    uint8_t ret = ags10_read(&voc);\n"
    "    (void)ret;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def test_ags10_manifest_shape_mspm0():
    """ags10：仅 mspm0 平台条目；依赖 delay；双角色 = gpio_out PB18/PA14
    （软 I2C 2 脚）。"""
    manifest = ModuleManifest.load(MODULES / "ags10")
    assert manifest.slug == "ags10"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["ags10.c", "ags10.h"]
    for rel in mspm0.files:
        assert (MODULES / "ags10" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("AGS10_SCL", "gpio_out", "PB18", True, ()),
        ("AGS10_SDA", "gpio_out", "PA14", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # 上游缺陷修正记录必须写入 notes（重试条件写反 + 返回值混用收敛）
    assert "写反" in mspm0.notes
    assert "出参" in mspm0.notes


def test_ags10_mspm0_master_syscfg_instances():
    """mspm0 母版：AGS10 GPIO 实例（SCL=PB18 输出 / SDA=PA14 输出）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const AGS10 = GPIO.addInstance();" in syscfg
    assert 'AGS10.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'AGS10.associatedPins[0].pin.$assign  = "PB18";' in syscfg
    assert 'AGS10.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'AGS10.associatedPins[1].pin.$assign  = "PA14";' in syscfg


def test_ags10_mspm0_single_select_generation(tmp_path):
    """ags10 mspm0 单选生成：syscfg 保留 AGS10 + 依赖 delay 模块文件落盘、
    静态门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ags10"])
    assert {m.slug for m in resolved.manifests} == {"ags10", "delay"}
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
    assert "const AGS10 = GPIO.addInstance();" in syscfg
    assert 'AGS10.associatedPins[0].pin.$assign  = "PB18";' in syscfg
    assert 'AGS10.associatedPins[1].pin.$assign  = "PA14";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "SHT30", "SGP30", "SR04",
        "JOYSTICK", "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART",
        "OLED", "I2C_0", "TTP224", "ADC12_0",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/ags10/code/ags10.c").is_file()
    assert (out / "modules/ags10/code/ags10.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()


def test_ags10_protocol_and_fix_guards():
    """CRC8 原式 / 重试条件修正 / 出参+状态收敛守卫（防回潮）：
    - CRC8 初值 0xFF、多项式 0x31（页面 Calc_CRC8 原式）；
    - 页面读地址重试条件写反（比较方向 `>=` 错误）→ 修正为
      `timeout < AGS10_RETRY_MAX` 且超时判定 `timeout >= AGS10_RETRY_MAX`
      （防回潮：while 条件不得写成 `>=`）；
    - 页面返回值（TVOC 值/1-4 错误码混用）→ 出参 voc_ppb + 状态码；
    - IIC 原语族静态化（无 AGS10_IIC_ 页面命名残留）。"""
    source = (MODULES / "ags10" / "code" / "ags10.c").read_text(encoding="utf-8")
    header = (MODULES / "ags10" / "code" / "ags10.h").read_text(encoding="utf-8")
    assert "0x31u" in source
    assert "0xFFu" in source
    assert "ags10_crc8(data, 4) != data[4]" in source  # 页面校验原式
    assert "while ((ags10_iic_wait_ack() == 1) && (timeout < AGS10_RETRY_MAX))" in source
    assert "if (timeout >= AGS10_RETRY_MAX) {" in source  # 超时判定（页面永不触发）
    assert "voc_ppb" in header  # 出参（页面返回值收敛）
    assert "AGS10_IIC_" not in source  # 原语族静态化（页面宏命名收敛）
