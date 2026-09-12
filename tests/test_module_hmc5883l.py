"""hmc5883l 三轴磁力计模块（软 I2C 总线件）：真实库 + 真实母版不变量与双平台单选生成。

照 tests/test_module_bh1750.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = i2c_scl/i2c_sda 共总线默认 PA6/PA7）、stm32 单选
生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成（syscfg 裁剪保留 HMC5883L +
模块文件落盘）。软 I2C 守卫（自实现原语族、零 ml_i2c/标准库调用、SDA 方向切换
OD/IU）与**旧实现缺陷防回潮**（六条：读地址分列 / 数据区 X-Z-Y / 符号扩展 /
无死全局 / CRA 合法值 / init 验 ID）+ 航向角纯函数数值单测。全程无 LLM、无服务。
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contest_generator.clex import strip_comments
from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "hmc5883l.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    uint8_t ok = hmc5883l_init();\n"
    "    int16_t mx = 0, my = 0, mz = 0;\n"
    "    float heading = 0.0f;\n"
    "    ok = hmc5883l_read(&mx, &my, &mz);\n"
    "    ok = hmc5883l_read_heading(&heading, 0, 0);\n"
    "    (void)ok;\n"
    "    (void)heading;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "hmc5883l_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    int16_t mx = 0, my = 0, mz = 0;\n"
    "    float heading = 0.0f;\n"
    "    (void)hmc5883l_init();\n"
    "    (void)hmc5883l_read(&mx, &my, &mz);\n"
    "    (void)hmc5883l_read_heading(&heading, 0, 0);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 规范字面量守卫：剥离注释后不得出现（标准库/寄存器/演示残留/母版 ml_i2c 调用）
BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用"),
    (r"stm32f4xx\.h", "stm32f4xx.h"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bI2C_Init\b|\bI2C_Start\b|\bI2C_Stop\b|\bI2C_SendByte\b", "母版 ml_i2c 调用"),
    (r"\bGPIO_ReadInputDataBit\b", "GPIO_ReadInputDataBit"),
    (r"\bGPIO_WriteBit\b", "GPIO_WriteBit"),
    # 航向换算不引 math.h（免链 libm）——出现 = 回退到浮点库依赖
    (r"#include\s*<math\.h>", "math.h"),
    (r"\batan2f?\s*\(", "atan2 调用"),
]


def _code_only(path: Path) -> str:
    return strip_comments(path.read_text(encoding="utf-8"), keep_preprocessor=True)


def test_hmc5883l_manifest_shape_both_platforms():
    """hmc5883l：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda（PA6/PA7 共总线，
    macros 逐脚端口宏）；mspm0 条目 syscfg gpio_out PB6/PB7。"""
    manifest = ModuleManifest.load(MODULES / "hmc5883l")
    assert manifest.slug == "hmc5883l"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "hmc5883l_stm32.c",
        "hmc5883l_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "hmc5883l" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("HMC5883L_SCL", "i2c_scl", "PA6", True, ("HMC5883L_SCL_GPIO", "HMC5883L_SCL_PIN")),
        ("HMC5883L_SDA", "i2c_sda", "PA7", True, ("HMC5883L_SDA_GPIO", "HMC5883L_SDA_PIN")),
    ]
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    for needle in ("未上板", "旧实现缺陷清单", "math.h"):
        assert needle in stm32.notes, needle

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["hmc5883l.c", "hmc5883l.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("HMC5883L_SCL", "gpio_out", "PB6", True, ()),
        ("HMC5883L_SDA", "gpio_out", "PB7", True, ()),
    ]
    assert mspm0.hardware_bound is False
    for needle in ("未上板", "旧实现缺陷清单", "官方数据手册", "lckfb"):
        assert needle in mspm0.notes, needle


def test_hmc5883l_verified_flipped_by_compile_matrix():
    """verified 由编译矩阵翻牌（工单 magnetometer-modules/04）：四组真编译
    （mspm0 = SysConfig CLI + gmake；stm32 = UV4）0 error / 0 module warning
    通过后两平台条目均为 true，且 notes 留有编译记录可溯源。"""
    manifest = ModuleManifest.load(MODULES / "hmc5883l")
    for platform in ("mspm0", "stm32"):
        entry = manifest.platforms[platform]
        assert entry.verified is True, platform
        assert "编译矩阵" in entry.notes and "0 error" in entry.notes, platform


def test_hmc5883l_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：四宏必须在母版 pin_config.h（默认 PA6/PA7）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+HMC5883L_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+HMC5883L_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+HMC5883L_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+HMC5883L_SDA_PIN\s+Pin_7", text)


def test_hmc5883l_mspm0_syscfg_instance():
    """mspm0 母版必须有 HMC5883L 实例（SCL=PB6 / SDA=PB7）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const HMC5883L = GPIO.addInstance();" in syscfg
    assert 'HMC5883L.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'HMC5883L.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'HMC5883L.associatedPins[0].pin.$assign  = "PB6";' in syscfg
    assert 'HMC5883L.associatedPins[1].pin.$assign  = "PB7";' in syscfg


def test_hmc5883l_stm32_single_select_generation(tmp_path):
    """stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、uvprojx 注册、
    pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["hmc5883l"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/hmc5883l/code/hmc5883l_stm32.c").is_file()
    assert (out / "modules/hmc5883l/code/hmc5883l_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("hmc5883l_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_hmc5883l_mspm0_single_select_generation(tmp_path):
    """mspm0 单选生成：syscfg 只留 HMC5883L、模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["hmc5883l"])
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
    assert "const HMC5883L = GPIO.addInstance();" in syscfg
    assert 'HMC5883L.associatedPins[0].pin.$assign  = "PB6";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "SR04", "JOYSTICK", "MOTOR_PID", "NTB",
        "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0",
        "PWMAB",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/hmc5883l/code/hmc5883l.c").is_file()
    assert (out / "modules/hmc5883l/code/hmc5883l.h").is_file()


def test_hmc5883l_stm32_code_guards():
    """stm32 代码层守卫：零标准库/寄存器/演示残留、零 ml_i2c 调用、零 math.h；
    软 I2C 原语自实现（SDA 方向切换 OD/IU）；SCL 在 init 初始化（批次 3 回修）。"""
    code = _code_only(MODULES / "hmc5883l" / "code" / "hmc5883l_stm32.c")
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code), f"代码残留 {label}"

    assert re.search(r"#define\s+HMC5883L_SDA_OUT\(\)\s+gpio_init\(HMC5883L_SDA_GPIO", code)
    assert re.search(
        r"#define\s+HMC5883L_SDA_IN\(\)\s+gpio_init\(HMC5883L_SDA_GPIO, HMC5883L_SDA_PIN, IU\)",
        code,
    )
    assert "hmc5883l_iic_start" in code and "hmc5883l_iic_wait_ack" in code
    # SCL 初始化防回潮：init 必须 gpio_init(SCL, OUT_OD) + 置高
    assert re.search(r"gpio_init\(HMC5883L_SCL_GPIO, HMC5883L_SCL_PIN, OUT_OD\)", code)
    assert "HMC5883L_SCL(1)" in code


def test_hmc5883l_defect_regressions():
    """**旧实现六条缺陷防回潮**（每条都有对应断言，改回旧写法即红）。"""
    h = _code_only(MODULES / "hmc5883l" / "code" / "hmc5883l.h")
    c = _code_only(MODULES / "hmc5883l" / "code" / "hmc5883l.c")
    full = h + "\n" + c

    # ① 读地址与写地址分列，读路径不得用 `ADDR | 0x01` 当寄存器
    assert "#define HMC5883L_ADDR_WRITE 0x3C" in full
    assert "#define HMC5883L_ADDR_READ 0x3D" in full
    assert "HMC5883L_ADDR | 0x01" not in full
    assert "HMC5883L_ADDR|0x01" not in full

    # ② 数据区顺序 = X-Z-Y（宏必须按手册命名，且 read 里 Z 从 0x05 字节取）
    assert "#define HMC5883L_REG_DATA_X_MSB 0x03" in full
    assert "#define HMC5883L_REG_DATA_Z_MSB 0x05" in full
    assert "#define HMC5883L_REG_DATA_Y_MSB 0x07" in full
    assert "buf[2], buf[3]" in c and "buf[4], buf[5]" in c

    # ③ 符号扩展：两平台都必须出现「(int16_t) 作用于 (uint16_t)hi<<8 | lo」的拼接
    #    （旧实现 data_l | (data_h << 8) 是纯无符号拼接，负磁场读成 32768+）；
    #    mspm0 收在私有拼装函数里、stm32 直接写在 read 内联——字符级形态不同，
    #    故断言「该转换表达式存在」而非绑定某一种写法。
    stm_c = _code_only(MODULES / "hmc5883l" / "code" / "hmc5883l_stm32.c")
    join_expr = r"\(int16_t\)\(\(\(uint16_t\)[^;]*<<\s*8\)\s*\|\s*\(uint16_t\)"
    assert re.search(join_expr, c), "mspm0 缺 (int16_t) 符号扩展拼接"
    assert re.search(join_expr, stm_c), "stm32 缺 (int16_t) 符号扩展拼接"

    # ④ 无死全局：不得出现声明后从不赋值的 yaw_hmc 式全局
    assert "yaw_hmc" not in full
    assert re.search(r"float\s+hmc_x", full) is None

    # ⑤ CRA 取手册合法值 0x70（旧实现 0xF8 落在保留区间）
    assert "HMC5883L_CRA_8AVG_15HZ_NORMAL 0x70" in full
    assert "0xF8" not in full and "0xf8" not in full

    # ⑥ init 必须验 ID 三字节并区分返回码 1 / 2
    assert "HMC5883L_REG_ID_A" in c and "HMC5883L_ID_A_VALUE 0x48" in h
    assert "HMC5883L_ID_B_VALUE 0x34" in h and "HMC5883L_ID_C_VALUE 0x33" in h
    assert re.search(r"return 2;", c), "init 缺「型号不符」返回码"


def test_hmc5883l_heading_pure_function_numeric(tmp_path):
    """航向角纯函数**真编译真执行**验证（gcc 可用时）：把真源码 + 最小桩头文件
    编成宿主可执行文件，与 math.atan2f 逐点比对——覆盖四个正交点、四象限、
    45° 对角线、偏移输入路径与零向量边界。

    为什么不用 Python 复算公式：那只能证明「我抄了一遍」，证明不了 C 里那份
    算得对。真编译是本仓库既有接缝（编译矩阵同族），此处把它下沉成单测。
    """
    import math
    import shutil
    import subprocess

    gcc = shutil.which("gcc")
    if gcc is None:
        import pytest

        pytest.skip("宿主无 gcc，跳过 C 级数值验证（编译矩阵工单仍会真编译）")

    module_dir = MODULES / "hmc5883l" / "code"
    stub = tmp_path / "stub"
    stub.mkdir()
    # 桩头文件：只提供 .c 编译所需的最小符号面（不含任何被测逻辑）
    (stub / "delay.h").write_text("void delay_us(unsigned int us);\n", encoding="utf-8")
    (stub / "ti_msp_dl_config.h").write_text(
        "#ifndef STUB_TI_MSP_DL_CONFIG_H\n#define STUB_TI_MSP_DL_CONFIG_H\n"
        "#define HMC5883L_PORT 0u\n"
        "#define HMC5883L_SCL_PIN 1u\n"
        "#define HMC5883L_SDA_PIN 2u\n"
        "#define HMC5883L_SCL_IOMUX 3u\n"
        "#define HMC5883L_SDA_IOMUX 4u\n"
        "void DL_GPIO_initDigitalOutput(unsigned int iomux);\n"
        "void DL_GPIO_initDigitalInput(unsigned int iomux);\n"
        "void DL_GPIO_setPins(unsigned int port, unsigned int pins);\n"
        "void DL_GPIO_clearPins(unsigned int port, unsigned int pins);\n"
        "void DL_GPIO_enableOutput(unsigned int port, unsigned int pins);\n"
        "unsigned int DL_GPIO_readPins(unsigned int port, unsigned int pins);\n"
        "#endif\n",
        encoding="utf-8",
    )
    driver = tmp_path / "heading_probe.c"
    driver.write_text(
        "#include <stdio.h>\n"
        '#include "hmc5883l.h"\n'
        "/* 桩实现：只为让宿主可执行文件链接通过，不参与被测逻辑 */\n"
        "void DL_GPIO_initDigitalOutput(unsigned int iomux) { (void)iomux; }\n"
        "void DL_GPIO_initDigitalInput(unsigned int iomux) { (void)iomux; }\n"
        "void DL_GPIO_setPins(unsigned int port, unsigned int pins) { (void)port; (void)pins; }\n"
        "void DL_GPIO_clearPins(unsigned int port, unsigned int pins) { (void)port; (void)pins; }\n"
        "void DL_GPIO_enableOutput(unsigned int port, unsigned int pins) { (void)port; (void)pins; }\n"
        "unsigned int DL_GPIO_readPins(unsigned int port, unsigned int pins)\n"
        "{ (void)port; (void)pins; return 0u; }\n"
        "void delay_us(unsigned int us) { (void)us; }\n"
        "int main(void)\n"
        "{\n"
        "    const double pts[][2] = {\n"
        "        {1.0, 0.0}, {0.0, 1.0}, {-1.0, 0.0}, {0.0, -1.0},\n"
        "        {1.0, 1.0}, {-1.0, 1.0}, {-1.0, -1.0}, {1.0, -1.0},\n"
        "        {3.0, 4.0}, {-3.0, 4.0}, {7.0, -24.0}, {0.5, 88.0},\n"
        "    };\n"
        "    unsigned int i;\n"
        "    printf(\"zero %f\\n\", (double)hmc5883l_heading_from_xy(0.0f, 0.0f));\n"
        "    for (i = 0; i < sizeof(pts) / sizeof(pts[0]); i++)\n"
        "    {\n"
        "        printf(\"%f %f %f\\n\", pts[i][0], pts[i][1],\n"
        "               (double)hmc5883l_heading_from_xy((float)pts[i][0], (float)pts[i][1]));\n"
        "    }\n"
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    exe = tmp_path / "heading_probe.exe"
    build = subprocess.run(
        [
            gcc,
            "-std=c99",
            "-Wall",
            "-Werror",
            "-I",
            str(stub),
            "-I",
            str(module_dir),
            str(driver),
            str(module_dir / "hmc5883l.c"),
            "-o",
            str(exe),
        ],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, f"编译失败：\n{build.stdout}\n{build.stderr}"

    run = subprocess.run([str(exe)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    lines = run.stdout.strip().splitlines()
    assert lines[0] == "zero 0.000000", "零向量必须返回 0（不得 NaN）"

    for line in lines[1:]:
        x_str, y_str, got_str = line.split()
        x, y, got = float(x_str), float(y_str), float(got_str)
        expect = math.degrees(math.atan2(y, x)) % 360.0
        assert 0.0 <= got < 360.0, (x, y, got)
        assert abs(got - expect) < 0.05, f"({x},{y}) got={got} expect={expect}"


def test_hmc5883l_heading_source_contract():
    """源码契约（C 侧换算不引浮点库、常量在源码单一出处）。"""
    c = _code_only(MODULES / "hmc5883l" / "code" / "hmc5883l.c")
    assert "hmc5883l_heading_from_xy" in c
    assert "3.1415927f" in c and "1.5707963f" in c  # 象限归一用的 π / π÷2
    assert "HMC5883L_RAD_TO_DEG" in c
    assert "0.9998660f" in c and "0.0208351f" in c  # 逼近式首末系数在源码里

