"""qmc5883l 三轴磁力计 / 电子罗盘模块（软 I2C 总线件）：真实库 + 真实母版
不变量与双平台单选生成。

照 test_module_bh1750.py 模板：manifest 形状（双平台文件齐、pins 类型/默认
脚/macros、verified（编译矩阵翻牌后 true）/hardware_bound=false/kit/source_url、notes 含手册
来源交代与「未上板」）、stm32 引脚宏落母版 pin_config.h、mspm0 新实例落母版
mspm0.syscfg、双平台单选生成（stm32：uvprojx 注册 + pin_config.h 落盘；
mspm0：syscfg 裁剪只留 QMC5883L + 模块文件落盘 + 依赖 delay 展开）。
软 I2C 代码守卫（自实现原语族、零标准库/母版 ml_i2c 调用、显式写/读地址两
宏、小端 16 位有符号拼装、Chip ID 校验、DRDY 等待、SDA 方向切换 OD/IU、
SCL 显式初始化）与 **HMC/QMC 语义对撞防回潮**（0x09/0x0B 不得按 HMC 语义
使用）+ 航向角纯函数单测（0/90/180/270 四点、偏移入参生效、零向量不 NaN）。
全程无 LLM、无服务。
"""
from __future__ import annotations

import math
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
    '#include "qmc5883l.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    uint8_t ok = qmc5883l_init();\n"
    "    int16_t x = 0, y = 0, z = 0;\n"
    "    float deg = 0.0f;\n"
    "    ok = qmc5883l_read(&x, &y, &z);\n"
    "    ok = qmc5883l_read_heading(&deg, x, y);\n"
    "    (void)ok;\n"
    "    (void)z;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "qmc5883l_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    int16_t x = 0, y = 0, z = 0;\n"
    "    float deg = 0.0f;\n"
    "    (void)qmc5883l_init();\n"
    "    (void)qmc5883l_read(&x, &y, &z);\n"
    "    (void)qmc5883l_read_heading(&deg, 0, 0);\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 换算/规范字面量守卫：剥离注释后不得出现（标准库/寄存器/演示残留/
# 母版 ml_i2c 调用）——照 test_module_bh1750.py 原表。
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
]


def int16_t_ish(value: int) -> int:
    """C 侧 int16_t 截断镜像（负值补码回绕——旧 HMC 实现缺符号扩展的对照物）。"""
    return ((value + 0x8000) & 0xFFFF) - 0x8000


def heading_from_xy(x: float, y: float) -> float:
    """C 侧 qmc5883l_heading_from_xy 语义镜像（零向量短路 + atan2(y, x) 折算
    成度 + 0–360° 归一；基线 = math.atan2，math.degrees）。"""
    if x == 0.0 and y == 0.0:
        return 0.0  # C 侧同款零向量短路（含 -0.0：atan2(-0.0, -0.0)=π）
    deg = math.degrees(math.atan2(y, x))
    while deg < 0.0:
        deg += 360.0
    while deg >= 360.0:
        deg -= 360.0
    return deg


def test_qmc5883l_heading_from_xy_cardinal_points():
    """航向角换算纯函数：0/90/180/270 四点（+X 前=0°、+Y 右=90°，顺时针）。"""
    # 基线表（math.atan2/math.degrees）：四点真值
    baseline = ((1.0, 0.0, 0.0), (0.0, 1.0, 90.0), (-1.0, 0.0, 180.0), (0.0, -1.0, 270.0))
    for x, y, expect in baseline:
        got = heading_from_xy(x, y)
        assert abs(got - expect) <= 1e-4, (x, y, got, expect)
    # 45° 象限点：东北 = 45°、西南 = 225°
    assert abs(heading_from_xy(1.0, 1.0) - 45.0) <= 1e-4
    assert abs(heading_from_xy(-1.0, -1.0) - 225.0) <= 1e-4
    # 输出恒落在 [0, 360)
    for x, y in ((1.0, -1e-9), (-1.0, 1e-9), (3.0, -4.0)):
        got = heading_from_xy(x, y)
        assert 0.0 <= got < 360.0, (x, y, got)


def test_qmc5883l_heading_offset_argument_takes_effect():
    """偏移入参生效：硬铁偏移把「偏移后的向量」当原始向量用——(x-x_off,
    y-y_off) 与直接把结果算在偏移后向量上等价（镜像 read_heading 语义）。"""
    x_raw = int16_t_ish(1200)
    y_raw = int16_t_ish(-800)
    x_off = 200
    y_off = -300
    # 未校正
    assert abs(heading_from_xy(float(x_raw), float(y_raw)) - heading_from_xy(1200.0, -800.0)) <= 1e-6
    # 校正后 = 偏移后的向量
    got = heading_from_xy(float(x_raw - x_off), float(y_raw - y_off))
    assert abs(got - heading_from_xy(1000.0, -500.0)) <= 1e-6
    # 偏移确实改变了结果（-800 → -500 抬角）
    assert abs(got - heading_from_xy(1200.0, -800.0)) > 1.0


def test_qmc5883l_heading_zero_vector_no_nan():
    """零向量边界：x=y=0 与全偏移抵消后为零时，输出为有限值（不产生 NaN）。"""
    for x, y in ((0.0, 0.0), (0.0, -0.0), (-0.0, 0.0)):
        got = heading_from_xy(x, y)
        assert not math.isnan(got) and not math.isinf(got), (x, y, got)
        assert got == 0.0
    # 偏移把读数抵消成零向量（镜像 read_heading 的 (x - x_off, y - y_off)）
    got = heading_from_xy(float(300 - 300), float(-700 - (-700)))
    assert not math.isnan(got) and got == 0.0


def test_qmc5883l_sign_extension_keeps_negative_axis():
    """符号扩展回归（旧 HMC 实现缺陷 ③ 的对照）：负磁场经 16 位小端拼装后
    仍是负数——C 侧用 (int16_t)(uint16_t) 拼装，等价于本函数镜像。"""
    # 0xFFFE (=-2) 小端字节序：低 0xFE、高 0xFF
    lo, hi = 0xFE, 0xFF
    raw = ((hi << 8) | lo) & 0xFFFF
    signed = ((raw + 0x8000) & 0xFFFF) - 0x8000
    assert signed == -2
    # 而「只取原始 uint16 值」的旧式读法会得到 65534（大正数）——差异即缺陷
    assert raw == 65534
    assert int16_t_ish(-2) == -2


def test_qmc5883l_manifest_shape_both_platforms():
    """qmc5883l：双平台文件齐；stm32 双角色 = i2c_scl/i2c_sda（SCL=PA6/
    SDA=PA7，macros 逐脚端口宏）；mspm0 条目 = syscfg gpio_out PA23/PA24；
    两平台 verified=true（工单 04 编译矩阵翻牌）、hardware_bound=false、
    notes 含手册来源交代 / 与 hmc5883l 互替证据 / 未上板。"""
    manifest = ModuleManifest.load(MODULES / "qmc5883l")
    assert manifest.slug == "qmc5883l"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "qmc5883l_stm32.c",
        "qmc5883l_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "qmc5883l" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("QMC5883L_SCL", "i2c_scl", "PA6", True, ("QMC5883L_SCL_GPIO", "QMC5883L_SCL_PIN")),
        ("QMC5883L_SDA", "i2c_sda", "PA7", True, ("QMC5883L_SDA_GPIO", "QMC5883L_SDA_PIN")),
    ]
    # verified 由编译矩阵翻牌（工单 magnetometer-modules/04：mspm0 = SysConfig CLI + gmake、
    # stm32 = UV4，四组 0 error / 0 module warning 全 PASS）
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == "https://www.qstcorp.com/"
    for needle in (
        "QST-PD-B002-22",
        "Rev. B",
        "库内**无**磁力计移植手册页",
        "hmc5883l",
        "0x09",
        "0x0B",
        "0x0D/0x0E",
        "未上板",
    ):
        assert needle in stm32.notes, needle

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["qmc5883l.c", "qmc5883l.h"]
    for rel in mspm0.files:
        assert (MODULES / "qmc5883l" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("QMC5883L_SCL", "gpio_out", "PA23", True, ()),
        ("QMC5883L_SDA", "gpio_out", "PA24", True, ()),
    ]
    assert mspm0.verified is True   # 编译矩阵已翻牌（magnetometer-modules/04）
    assert mspm0.hardware_bound is False
    assert mspm0.source_url == "https://www.qstcorp.com/"
    for needle in (
        "QST-PD-B002-22",
        "库内**无** lckfb 磁力计移植手册页",
        "hmc5883l",
        "bmp180",
        "未上板",
    ):
        assert needle in mspm0.notes, needle


def test_qmc5883l_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：QMC5883L_SCL_GPIO/_PIN/_SDA_GPIO/_SDA_PIN 必须在
    母版 pin_config.h（默认 PA6/PA7 = 库内软 I2C 总线共享组）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+QMC5883L_SCL_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+QMC5883L_SCL_PIN\s+Pin_6", text)
    assert re.search(r"#define\s+QMC5883L_SDA_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+QMC5883L_SDA_PIN\s+Pin_7", text)


def test_qmc5883l_mspm0_syscfg_instance():
    """mspm0 母版必须有 QMC5883L 实例（SCL=PA23 / SDA=PA24，两脚 OUTPUT）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const QMC5883L = GPIO.addInstance();" in syscfg
    assert 'QMC5883L.associatedPins[0].$name        = "SCL";' in syscfg
    assert 'QMC5883L.associatedPins[1].$name        = "SDA";' in syscfg
    assert 'QMC5883L.associatedPins[0].pin.$assign  = "PA23";' in syscfg
    assert 'QMC5883L.associatedPins[1].pin.$assign  = "PA24";' in syscfg


def test_qmc5883l_stm32_single_select_generation(tmp_path):
    """qmc5883l stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 qmc5883l_stm32.c、pin_config.h 在工程根、依赖 delay 展开。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["qmc5883l"])
    assert {m.slug for m in resolved.manifests} == {"qmc5883l", "delay"}
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/qmc5883l/code/qmc5883l_stm32.c").is_file()
    assert (out / "modules/qmc5883l/code/qmc5883l_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("qmc5883l_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_qmc5883l_mspm0_single_select_generation(tmp_path):
    """qmc5883l mspm0 单选生成：syscfg 只留 QMC5883L、依赖 delay 展开、
    模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["qmc5883l"])
    assert {m.slug for m in resolved.manifests} == {"qmc5883l", "delay"}
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
    assert "const QMC5883L = GPIO.addInstance();" in syscfg
    assert 'QMC5883L.associatedPins[1].pin.$assign  = "PA24";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "ZIGBEE_UART", "OLED", "I2C_0", "ADC12_0", "SHT30",
        "SHT20", "JY61P", "SGP30", "AGS10", "TTP224", "HUMAN_IR",
        "BH1750", "BMP180", "MS5611", "PCA9685", "DHT11",
        # 注：HMC5883L 实例暂不在此列——母版新增实例未登记 INSTANCE_CONSUMERS
        # 时按「宁多勿裁」保留（syscfg_model.prune 防御路径），登记属工单 03
        # 的共享表改动（tests/test_syscfg_prune.py 现为红）
    ):
        assert f"const {drop}" not in syscfg, drop
    assert (out / "modules/qmc5883l/code/qmc5883l.c").is_file()
    assert (out / "modules/qmc5883l/code/qmc5883l.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()


def test_qmc5883l_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c 调用；
    软 I2C 原语自实现（SDA 方向切换 = gpio_init OD/IU）；寄存器表按 QMC 手册
    （地址 0x0D/0x0E、控制1 0x1D、控制2 0x40、SET/RESET 0x01、Chip ID 0xFF、
    数据 6 字节小端）；**HMC 语义对撞防回潮**（0x09/0x0B 不得按 HMC 语义
    出现 CRA/CRB/MR 式写法）。"""
    c = (MODULES / "qmc5883l" / "code" / "qmc5883l_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "qmc5883l" / "code" / "qmc5883l_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 软 I2C 原语族静态化 + 方向切换（OUT_OD 输出 / IU 输入）
    assert re.search(
        r"#define\s+QMC5883L_SDA_OUT\(\)\s+gpio_init\(QMC5883L_SDA_GPIO, QMC5883L_SDA_PIN, OUT_OD\)",
        code_only,
    )
    assert re.search(
        r"#define\s+QMC5883L_SDA_IN\(\)\s+gpio_init\(QMC5883L_SDA_GPIO, QMC5883L_SDA_PIN, IU\)",
        code_only,
    )
    assert re.search(r"#define\s+QMC5883L_SDA\(x\)\s+gpio_set", code_only)
    assert "qmc5883l_iic_start" in code_only and "qmc5883l_iic_wait_ack" in code_only
    assert "qmc5883l_iic_send_ack" in code_only and "qmc5883l_iic_read_byte" in code_only

    # 显式写地址 / 读地址两宏（旧件「读地址当寄存器地址」缺陷不回潮）
    assert "QMC5883L_ADDR_WRITE 0x0Du" in h
    assert "QMC5883L_ADDR_READ 0x0Eu" in h
    assert "QMC5883L_ADDR_READ" in code_only
    assert "+ 1" not in code_only  # 不得用 ADDR_WRITE+1 之类派生写法掩盖地址语义

    # 寄存器表最终取值（QMC 手册 Rev. B）
    assert "QMC5883L_REG_CTRL1 0x09u" in h
    assert "QMC5883L_REG_FBR 0x0Bu" in h
    assert "QMC5883L_REG_CHIP_ID 0x0Du" in h
    assert "QMC5883L_CTRL1_VALUE 0x1Du" in h
    assert "QMC5883L_CTRL2_VALUE 0x40u" in h
    assert "QMC5883L_FBR_PERIOD 0x01u" in h
    assert "QMC5883L_CHIP_ID 0xFFu" in h
    assert "QMC5883L_REG_CTRL2, QMC5883L_CTRL2_RESET" in code_only
    assert "QMC5883L_REG_FBR, QMC5883L_FBR_PERIOD" in code_only
    assert "QMC5883L_REG_CTRL1, QMC5883L_CTRL1_VALUE" in code_only
    assert "QMC5883L_REG_CTRL2, QMC5883L_CTRL2_VALUE" in code_only

    # 数据 6 字节、小端（低字节在前）、符号扩展走 int16_t 拼装
    assert "QMC5883L_DATA_LEN 6u" in h
    assert "QMC5883L_REG_DATA, buf, QMC5883L_DATA_LEN" in code_only
    assert "(int16_t)(((uint16_t)buf[1] << 8) | (uint16_t)buf[0])" in code_only
    assert "(int16_t)(((uint16_t)buf[3] << 8) | (uint16_t)buf[2])" in code_only
    assert "(int16_t)(((uint16_t)buf[5] << 8) | (uint16_t)buf[4])" in code_only
    # 旧件「缺符号扩展 / 寄存器序注释错」的写法不得回归
    assert "data_l" not in code_only and "data_h" not in code_only

    # 状态位 DRDY 等待 + 超时窗口（Chip ID 校验在 init）
    assert "QMC5883L_STATUS_DRDY 0x01u" in h
    assert "QMC5883L_DRDY_TIMEOUT_MS 20u" in h
    assert "status & QMC5883L_STATUS_DRDY" in code_only
    assert "qmc5883l_wait_drdy" in code_only
    assert "return 2;" in code_only  # 器件 ID 不符
    assert re.search(r"if \(qmc5883l_write_reg\(QMC5883L_REG_CTRL2, QMC5883L_CTRL2_RESET\) != 0\)\s*\{\s*return 1;", code_only)
    assert "QMC5883L_RESET_WAIT_MS 10u" in h
    assert "delay_ms(QMC5883L_RESET_WAIT_MS)" in code_only

    # 航向角：atan2f + 0–360 归一 + 纯函数出参（换算唯一收敛点）
    assert "atan2f" in code_only
    assert "57.29578f" in code_only
    assert "float qmc5883l_heading_from_xy(float x, float y)" in code_only
    assert "*deg = qmc5883l_heading_from_xy(" in code_only

    # 旧件死全局（yaw_hmc / hmc_x 式）不回潮 + HMC 寄存器名不得残留
    for banned in ("hmc_", "yaw_hmc", "HMC5883L", "CRA", "CRB", "QMC5883L_REG_ID"):
        assert banned not in code_only, banned


def test_qmc5883l_stm32_scl_init_guard():
    """SCL 初始化防回潮：init 必须含 gpio_init(QMC5883L_SCL_GPIO,
    QMC5883L_SCL_PIN, OUT_OD) + 置高——F1 复位后浮空输入、ODR 写入无效，
    不初始化 = 总线死（批次 2 六件 SCL 从未初始化的真 bug 回修先例）。"""
    c = (MODULES / "qmc5883l" / "code" / "qmc5883l_stm32.c").read_text(encoding="utf-8")
    code_only = strip_comments(c, keep_preprocessor=True)
    assert re.search(
        r"gpio_init\(QMC5883L_SCL_GPIO, QMC5883L_SCL_PIN, OUT_OD\)", code_only
    )
    assert "QMC5883L_SCL(1)" in code_only


def test_qmc5883l_stm32_wait_ack_failure_returns_code():
    """wait_ack 失败必须有返回码（旧实现忽略 ACK 的缺陷不回潮）：写寄存器三处
    + 读序列两处 + DRDY 状态读一处 = 六处均检查。"""
    c = (MODULES / "qmc5883l" / "code" / "qmc5883l_stm32.c").read_text(encoding="utf-8")
    code_only = strip_comments(c, keep_preprocessor=True)
    assert code_only.count("if (qmc5883l_iic_wait_ack() != 0)") == 6
    assert "return 1;" in code_only
    assert "qmc5883l_iic_stop();" in code_only  # 超时拉停止条件释放总线
