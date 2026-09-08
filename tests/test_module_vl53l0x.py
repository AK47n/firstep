"""vl53l0x ToF 激光测距模块（B 类新 slug——仅 stm32 条目、无 mspm0 对照）：
真实库 + 真实母版不变量与 stm32 单选生成。

与 neo_6m / ec11（B 类）同款结构测试：manifest 形状（仅 stm32、deps ()——delay 走母版内嵌 ml_delay（headfile.h，B 类口径）、
SCL/SDA/XSHUT 三角色 = PA6/PA7/PB0，macros 逐脚端口宏）、stm32 单选生成
（模块文件落盘、uvprojx 注册、pin_config.h 在工程根）、缺陷守卫（页面 Status
粘滞修正、char ack 死变量剔除、I2C 原语静态化、无 sys.h 位带、ST API 最小
切片 = 只含闭包函数 + 无演示件）。全程无 LLM、无服务。
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
VL53L0X = MODULES / "vl53l0x"

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "vl53l0x_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    vl53l0x_init();\n"
    "    vl53l0x_set_mode(VL53L0X_MODE_DEFAULT);\n"
    "    float d = 0.0f;\n"
    "    (void)vl53l0x_read_mm(&d);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 规范字面量守卫：剥离注释后不得出现（标准库/寄存器/演示残留/母版
# ml_i2c 调用/位带宏）。
BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bPBout\b", "PBout 位带宏"),
    (r"\bPAin\b", "PAin 位带宏"),
    (r"\bI2C_Init\b|\bI2C_Start\b|\bI2C_Stop\b|\bI2C_SendByte\b|\bI2C_WaitAck\b",
     "母版 ml_i2c 调用"),
]


def test_vl53l0x_manifest_shape():
    """B 类口径：仅 stm32 平台条目（无 mspm0）；依赖 delay；
    SCL/SDA/XSHUT 三角色 = PA6/PA7/PB0（macros 逐脚端口宏）。"""
    manifest = ModuleManifest.load(VL53L0X)
    assert manifest.slug == "vl53l0x"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"stm32"}

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "vl53l0x_core.c",
        "vl53l0x_core.h",
        "vl53l0x_stm32.c",
        "vl53l0x_stm32.h",
    ]
    for rel in stm32.files:
        assert (VL53L0X / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("VL53L0X_SCL", "i2c_scl", "PA6", True, ("VL53L0X_SCL_GPIO", "VL53L0X_SCL_PIN")),
        ("VL53L0X_SDA", "i2c_sda", "PA7", True, ("VL53L0X_SDA_GPIO", "VL53L0X_SDA_PIN")),
        ("VL53L0X_XSHUT", "gpio_out", "PB0", True, ("VL53L0X_XSHUT_GPIO", "VL53L0X_XSHUT_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/vl53l0x-laser-distance-sensor.html"
    )
    for needle in (
        "B 类：无 mspm0 条目",
        "网盘下载/vl53l0x/",
        "0x29",
        "最小切片",
        "75 函数",
        "sys.h",
        "未上板",
        "Status",
        "0x52",
        "One_measurement",
    ):
        assert needle in stm32.notes
    # 能力方向（简介判据③）：ToF 激光测距 + 无题绑定
    assert "ToF" in manifest.description
    assert "测距" in manifest.description
    for banned in ("21F", "2024H", "2026H", "题目", "专用"):
        assert banned not in manifest.description


def test_vl53l0x_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：VL53L0X 六宏在母版 pin_config.h（默认 PA6/PA7/PB0）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8", newline="")
    assert re.search(r"#define\s+VL53L0X_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+VL53L0X_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+VL53L0X_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+VL53L0X_SDA_PIN\s+Pin_7", text)
    assert re.search(r"#define\s+VL53L0X_XSHUT_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+VL53L0X_XSHUT_PIN\s+Pin_0", text)


def test_vl53l0x_stm32_single_select_generation(tmp_path):
    """vl53l0x stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 vl53l0x_core.c / vl53l0x_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["vl53l0x"])
    assert {m.slug for m in resolved.manifests} == {"vl53l0x"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    for rel in ("vl53l0x_core.c", "vl53l0x_core.h", "vl53l0x_stm32.c",
                "vl53l0x_stm32.h"):
        assert (out / "modules/vl53l0x/code" / rel).is_file(), rel
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("vl53l0x_core.c" in p for p in paths)
    assert any("vl53l0x_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_vl53l0x_stm32_code_guards():
    """stm32 代码层守卫（剥离注释后）：零标准库/寄存器/演示残留、零母版
    ml_i2c 调用、零位带宏（PBout/PAin）；软 I2C 原语自实现（静态 _iic_* 族）；
    模式四档宏；缺陷防回潮（char ack 死变量剔除、status 粘滞无 while(1)）。"""
    c = (VL53L0X / "code/vl53l0x_stm32.c").read_text(encoding="utf-8")
    h = (VL53L0X / "code/vl53l0x_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 地址/模式宏（页面 0X52 + BSP 模式枚举）
    assert "VL53L0X_ADDR 0x52u" in code_only or "0x52u" in code_only
    assert "VL53L0X_MODE_DEFAULT" in code_only
    assert "VL53L0X_MODE_HIGH_ACCURACY" in code_only
    assert "VL53L0X_MODE_LONG_RANGE" in code_only
    assert "VL53L0X_MODE_HIGH_SPEED" in code_only
    # 软 I2C 原语静态化（页面 VL_IIC_* / I2C_Start 等 → _iic_ 族）
    assert "static void vl53l0x_iic_start" in code_only
    assert "static void vl53l0x_iic_stop" in code_only
    assert "static uint8_t vl53l0x_iic_wait_ack" in code_only
    assert "static uint8_t vl53l0x_iic_write_multi" in code_only
    assert "static uint8_t vl53l0x_iic_read_multi" in code_only
    # 位带宏换算：XSHUT 走 gpio_set + 引脚宏（无 PBout）
    assert re.search(r"VL53L0X_XSHUT\(x\)\s+gpio_set\(VL53L0X_XSHUT_GPIO", code_only)
    # BSP API 三件 + 模式表
    assert re.search(r"uint8_t vl53l0x_init\(void\)", code_only)
    assert re.search(r"uint8_t vl53l0x_set_mode\(uint8_t mode\)", code_only)
    assert re.search(r"uint8_t vl53l0x_read_mm\(float \*dist_mm\)", code_only)
    assert "vl53l0x_modes[4]" in code_only
    # 缺陷防回潮：① 无 while(1)（页面 Status 粘滞 while(1) 不在模块——
    # read_mm 每次独立状态）； ② 无 char ack 死变量； ③ vl53l0x_data 显式静态
    assert "while (1)" not in code_only
    assert "char ack" not in code_only
    assert "static VL53L0X_RangingMeasurementData_t vl53l0x_data" in code_only
    # ST 平台层契约函数（官方 API 调用面——模块内实现）
    assert "VL53L0X_Error VL53L0X_WrByte(" in code_only
    assert "VL53L0X_Error VL53L0X_ReadMulti(" in code_only
    # 校准/测量原式关键字（页面 BSP 语义保留）
    assert "VL53L0X_PerformRefCalibration" in code_only
    assert "VL53L0X_PerformSingleRangingMeasurement" in code_only
    assert "VL53L0X_DEVICEMODE_SINGLE_RANGING" in code_only
    # 电平口径（缺陷⑧换算：OUT_OD/IU——共总线推挽互斥；SCL 初始化置高）
    assert "OUT_OD" in code_only and "IU" in code_only
    assert "VL53L0X_SCL(1)" in code_only
    # USE_I2C_2V8（页面 BSP 定义——DataInit 2.8V IO 模式分支按移植工程保留）
    assert "USE_I2C_2V8" in code_only


def test_vl53l0x_core_minimal_slice():
    """ST API 最小切片（核心）：闭包函数在 vl53l0x_core.c 定义；范围外演示件/
    未裁剪族不得出现（负向守卫）；头文件合并自 ST 官方（关键类型 + 平台
    契约）且无 stm32f10x.h/位带/标准外设残留。"""
    core = (VL53L0X / "code/vl53l0x_core.c").read_text(encoding="utf-8")
    coreh = (VL53L0X / "code/vl53l0x_core.h").read_text(encoding="utf-8")

    code_only = strip_comments(core, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS + [
        (r"\bPBout\b", "PBout（位带宏）"),
    ]:
        assert not re.search(pattern, code_only), f"核心残留 {label}"

    # 闭包入口 10 函数（初始化/模式/单次测量族）+ 内部闭环抽样
    for fn in (
        "VL53L0X_DataInit",
        "VL53L0X_StaticInit",
        "VL53L0X_PerformRefCalibration",
        "VL53L0X_PerformRefSpadManagement",
        "VL53L0X_SetDeviceMode",
        "VL53L0X_SetLimitCheckEnable",
        "VL53L0X_SetLimitCheckValue",
        "VL53L0X_SetMeasurementTimingBudgetMicroSeconds",
        "VL53L0X_SetVcselPulsePeriod",
        "VL53L0X_PerformSingleRangingMeasurement",
        "VL53L0X_StartMeasurement",
        "VL53L0X_GetRangingMeasurementData",
    ):
        assert re.search(r"VL53L0X_Error VL53L0X_" + fn[len("VL53L0X_"):] + r"\s*\(", code_only), fn
    # 文件级数据段（api_calibration.c 原样——is_aperture 依赖）
    assert "refArrayQuadrants" in code_only
    assert "REF_ARRAY_SPAD_0" in code_only
    # 负向守卫：范围外演示/未裁剪族不得出现
    # 负向守卫：范围外演示/未裁剪族不得出现（注意：中断**设置寄存器**辅助
    # 族（CheckAndLoadInterruptSettings/SetGpioConfig/ClearInterruptMask——
    # StartMeasurement 链自动拉入，仅写寄存器非演示）在闭包内——不在此列；
    # 中断**模式**演示（alarm/EXTI9_5/阈值触发）不在闭包内）
    for banned in (
        "vl53l0x_test",
        "print_pal_error",
        "mode_string",
        "VL53L0X_GetPalErrorString",
        "VL53L0X_GetDeviceInfo",
        "VL53L0X_SetDeviceAddress",
        "VL53L0X_PerformXTalkCalibration",
        "VL53L0X_PerformOffsetCalibration",
        "VL53L0X_PerformSingleHistogramMeasurement",
        "VL53L0X_SetInterruptThresholds",
        "VL53L0X_GetVersion",
        "VL53L0X_GetPalSpecVersion",
        # 单次测量链不含显式 StopMeasurement（ST 单次模式自停——裁剪记录：
        # PerformSingleRangingMeasurement → PerformSingleMeasurement →
        # StartMeasurement + poll_for_completion + GetRangingMeasurementData）
        "VL53L0X_StopMeasurement",
    ):
        assert not re.search(r"\b" + banned + r"\b", code_only), f"范围外泄露：{banned}"
    # 头文件：关键类型 + 平台契约 + 无标准外设/位带残留（注释剥离后）
    assert "VL53L0X_Dev_t" in coreh
    assert "VL53L0X_RangingMeasurementData_t" in coreh
    assert "VL53L0X_MAX_I2C_XFER_SIZE" in coreh
    coreh_code = strip_comments(coreh, keep_preprocessor=True)
    for forbidden in ("stm32f10x.h", "vl53l0x_i2c.h", "vl53l0x_platform_log.h",
                      "GPIO_Init", "RCC_"):
        assert forbidden not in coreh_code, forbidden
    # 无 GPIO_A/B/C 引脚字面量（ST 头 REG_SYSTEM_INTERRUPT_GPIO_* 宏名豁免）
    for m in re.finditer(r"\bGPIO_[ABC]\b", coreh_code):
        assert False, f"引脚字面量：{m.group(0)}"
