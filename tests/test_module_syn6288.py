"""syn6288 语音合成模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 jq8900 同款结构测试（软 UART 单发 TX 新先例）：manifest 形状（仅 mspm0、
依赖 delay、单角色 TX = 母版 syscfg 由 test_pins.py / test_pin_bindings.py
守）、mspm0 单选生成（syscfg 裁剪保留 SYN6288 + delay 展开、模块文件落盘、
main.c 调 init/speak 过静态门禁）。软 UART 9600 8N1 位序列时序用 Python
纯函数镜像（电平时间轴）钉死 + SYN6288 帧格式纯函数测试（0xFD+长度+命令+
参数+文本+异或，页面帧结构镜像）+ 源码文本守卫（ir_remote_tx 先例）。
全程无 LLM、无服务。
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
    '#include "syn6288.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    syn6288_init();\n"
    '    syn6288_speak("lckfb");\n'
    "    syn6288_stop();\n"
    "    syn6288_pause();\n"
    "    syn6288_resume();\n"
    "    syn6288_send_cmd(SYN6288_CMD_SPEECH, 0x00, \"ok\");\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# ---------------------------------------------------------------------------
# 软 UART 时序 + 帧格式纯函数镜像（编译矩阵只验编译不验时序/帧结构）
# ---------------------------------------------------------------------------

SYN6288_BIT_US = 104  # 9600 8N1 单位时间 ≈104.17us（取整 104，模块头宏同值）


def soft_uart_timeline(byte: int, bit_us: int = SYN6288_BIT_US) -> list[tuple[int, int]]:
    """9600 8N1 位序列 → [(电平, 时长us), ...]，共 10 段（起始+8 数据+停止）。

    电平：1 = 高（空闲），0 = 低；数据位 LSB 先。与 syn6288.c 的 _tx_byte
    实现同构（起始位低 → for i in 0..7 取 (byte>>i)&1 → 停止位高，每段
    delay_us(SYN6288_UART_BIT_US)）。
    """
    levels = [0] + [(byte >> i) & 1 for i in range(8)] + [1]
    return [(level, bit_us) for level in levels]


def syn6288_frame(text: str, cmd: int = 0x01, cmd_par: int = 0x00) -> list[int]:
    """SYN6288 指令帧镜像（页面 SYN6288_Send_Cmd 结构逐字节一致）：

    0xFD + Data_Len(高/低)（= 文本长度 + 3）+ CmdType + CmdPar + 文本字节 +
    异或校验（帧头到文本逐字节 ^，最后发送）。文本按 ASCII 等字节处理
    （GB2312 编码字节序与 ASCII 一致，页面要求 GB2312）。
    """
    data = [b & 0xFF for b in text.encode("gb2312")]
    data_len = len(data) + 3
    frame = [0xFD, (data_len >> 8) & 0xFF, data_len & 0xFF, cmd, cmd_par] + data
    xor = 0
    for b in frame:
        xor ^= b
    return frame + [xor]


def test_syn6288_soft_uart_timeline_shape_and_order():
    """9600 8N1：10 段、起始位低、停止位高、数据位 LSB 先、每段 104us。"""
    byte = 0x0F  # 00001111，LSB 先 = 1,1,1,1,0,0,0,0
    timeline = soft_uart_timeline(byte)
    assert len(timeline) == 10
    levels = [level for level, _ in timeline]
    assert levels[0] == 0
    assert levels[-1] == 1
    assert levels[1:9] == [(byte >> i) & 1 for i in range(8)]
    assert all(dur == SYN6288_BIT_US for _, dur in timeline)
    assert sum(dur for _, dur in timeline) == 10 * SYN6288_BIT_US


def test_syn6288_frame_matches_page_protocol():
    """帧结构镜像：0xFD + len(文本+3) 高低位在前 + 命令/参数 + 文本 + 异或。"""
    frame = syn6288_frame("abc")
    assert frame == [0xFD, 0x00, 0x06, 0x01, 0x00, 0x61, 0x62, 0x63, 0x9A]
    # 无文本命令（stop/pause/resume）：Data_Len = 3，异或 = FD^00^03^02^00
    empty = syn6288_frame("", cmd=0x02)
    assert empty == [0xFD, 0x00, 0x03, 0x02, 0x00, 0xFC]


def test_syn6288_soft_uart_source_guards():
    """源码文本守卫：位时序公式/帧结构走样即红（编译矩阵不验时序）。"""
    source = (MODULES / "syn6288" / "code" / "syn6288.c").read_text(encoding="utf-8")
    assert "SYN6288_UART_BIT_US" in source
    assert "_tx_bit(0u);" in source
    assert "(ch >> i) & 0x01u" in source
    assert "_tx_bit(1u);" in source
    assert "0xFDu" in source                 # 帧头
    assert "text_len + 3u" in source         # Data_Len = 文本长度 + 3
    assert "xor_check ^" in source           # 异或校验
    assert "SYN6288_TEXT_MAX" in source      # 防越界上限


# ---------------------------------------------------------------------------
# 结构 + 生成（既有接缝）
# ---------------------------------------------------------------------------


def test_syn6288_manifest_shape_mspm0():
    """syn6288：仅 mspm0 平台条目；依赖 delay；单角色 TX = gpio_out PB20。"""
    manifest = ModuleManifest.load(MODULES / "syn6288")
    assert manifest.slug == "syn6288"
    assert manifest.dependencies == ("delay",)
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["syn6288.c", "syn6288.h"]
    for rel in mspm0.files:
        assert (MODULES / "syn6288" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("SYN6288_TX", "gpio_out", "PB20", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url


def test_syn6288_mspm0_syscfg_instances():
    """mspm0 母版：SYN6288 GPIO 实例（TX 输出，初始 SET = 空闲高）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const SYN6288 = GPIO.addInstance();" in syscfg
    assert 'SYN6288.associatedPins[0].$name        = "TX";' in syscfg
    assert 'SYN6288.associatedPins[0].direction    = "OUTPUT";' in syscfg
    assert 'SYN6288.associatedPins[0].initialValue = "SET";' in syscfg
    assert 'SYN6288.associatedPins[0].pin.$assign  = "PB20";' in syscfg


def test_syn6288_mspm0_single_select_generation(tmp_path):
    """syn6288 mspm0 单选生成：syscfg 只留 SYN6288、依赖 delay 展开、文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["syn6288"])
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
    assert "const SYN6288 = GPIO.addInstance();" in syscfg
    assert 'SYN6288.associatedPins[0].pin.$assign  = "PB20";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "SR04", "JOYSTICK", "MOTOR_PID", "NTB", "IMU601",
        "DIGIT_UART", "DEBUG_UART", "UWB_UART", "ZIGBEE_UART", "OLED", "I2C_0",
        "ADC12_0", "DC_MOTOR", "PWMAB", "SERVO_PWM", "IR_REMOTE", "MAX7219",
        "PCA9685", "IR_TX", "NRF24L01", "HC05_UART", "HC05", "JQ8900",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/syn6288/code/syn6288.c").is_file()
    assert (out / "modules/syn6288/code/syn6288.h").is_file()
    assert (out / "modules/delay/code/delay.c").is_file()
    assert (out / "modules/delay/code/delay.h").is_file()
