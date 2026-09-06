"""open_mv4 主控侧 UART 帧解析模块：真实库 + 真实母版不变量与 mspm0 单选生成。

与 joystick / fingerprint 同款结构测试：manifest 形状（仅 mspm0、无依赖、
UART TX/RX 双角色 = PA8/PA9——默认与母版 syscfg 一致性由 test_pins.py /
test_pin_bindings.py 守）、mspm0 单选生成（syscfg 裁剪保留 OPENMV4_UART、
模块文件落盘、main.c 调 init/read_frame 过静态门禁）。**帧解析纯函数单测
（最高既有接缝——test_k230_artifact.py C 源机械比对/纯函数镜像先例）**：
伪帧序列 → 坐标结果（页面 `[cx,cy]`/`[pos]` 形态 + 前缀/`\r\n`/坏帧/越界
形态），C 侧解析器语义镜像；UART 放置决策（真实 UART 轮询、UART1/9600、
不并 coord_detect 的理由）写入 notes。
全程无 LLM、无服务。
"""

from __future__ import annotations

import re
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
    '#include "open_mv4.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    open_mv4_init();\n"
    "    int cx = 0, cy = 0;\n"
    "    float conf = 0.0f;\n"
    "    uint8_t ok = open_mv4_read_frame(&cx, &cy, &conf);\n"
    "    (void)ok;\n"
    "    (void)cx;\n"
    "    (void)cy;\n"
    "    (void)conf;\n"
    "    open_mv4_flush();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)


def _parse_int(s: str, i: int):
    """解析器镜像（C 侧 open_mv4_parse_int 语义，含 >9 位坏帧防护）：
    返回 (value, next_index) 或 None。"""
    n = len(s)
    sign = 1
    if i < n and s[i] == "-":
        sign = -1
        i += 1
    if i >= n or not s[i].isdigit():
        return None
    val = 0
    digits = 0
    while i < n and s[i].isdigit():
        val = val * 10 + int(s[i])
        i += 1
        digits += 1
        if digits > 9:
            return None  # 九位以上 = 非页面坐标（C 侧 int 溢出防护镜像）
    return val * sign, i


def openmv4_parse_frame(line: str):
    """C 侧 open_mv4_parse_frame 语义镜像：'[' 帧头 → 1-2 整数（`,` 分隔，
    单值帧 cy=0；页面格式无空格）→ ']'。返回 (ok, cx, cy)。"""
    p = line.find("[")
    if p < 0:
        return False, None, None
    i = p + 1
    r = _parse_int(line, i)
    if r is None:
        return False, None, None
    x, i = r
    y = 0
    if i < len(line) and line[i] == ",":
        r = _parse_int(line, i + 1)
        if r is None:
            return False, None, None
        y, i = r
    if i >= len(line) or line[i] != "]":
        return False, None, None
    return True, x, y


def openmv4_data_analysis(frames: list[str]):
    """C 侧 Openmv4DataAnalysis 语义镜像（按 '\n' 分帧——'\\r' 忽略、空行
    跳过、坏帧丢弃；返回最后一个有效帧）。"""
    result = None
    ready = False
    for line in frames:
        if line == "\n" or line == "\r\n":
            continue
        ok, cx, cy = openmv4_parse_frame(line)
        if ok:
            result = (cx, cy)
            ready = True
    return result if ready else None


def test_open_mv4_manifest_shape_mspm0():
    """open_mv4：仅 mspm0 平台条目；无依赖；UART TX/RX 双角色。"""
    manifest = ModuleManifest.load(MODULES / "open_mv4")
    assert manifest.slug == "open_mv4"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"mspm0"}

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["open_mv4.c", "open_mv4.h"]
    for rel in mspm0.files:
        assert (MODULES / "open_mv4" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("OPENMV4_UART_TX", "uart_tx", "PA8", True, ()),
        ("OPENMV4_UART_RX", "uart_rx", "PA9", True, ()),
    ]
    assert mspm0.kit and mspm0.source_url
    # UART 放置决策/实例上限/与 coord_detect 帧格式差异说明必须写入 notes
    assert "fingerprint" in mspm0.notes  # 决策取证引用
    assert "实例上限" in mspm0.notes
    assert "coord_detect" in mspm0.notes
    assert "9600" in mspm0.notes


def test_open_mv4_mspm0_syscfg_instances():
    """mspm0 母版：OPENMV4_UART（UART1 9600 轮询 PA8/PA9）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const OPENMV4_UART = UART.addInstance();" in syscfg
    assert 'OPENMV4_UART.peripheral.$assign = "UART1";' in syscfg
    assert 'OPENMV4_UART.targetBaudRate    = 9600;' in syscfg
    assert 'OPENMV4_UART.enabledInterrupts = [];' in syscfg
    assert 'OPENMV4_UART.peripheral.rxPin.$assign = "PA9";' in syscfg
    assert 'OPENMV4_UART.peripheral.txPin.$assign = "PA8";' in syscfg


def test_open_mv4_mspm0_single_select_generation(tmp_path):
    """open_mv4 mspm0 单选生成：syscfg 只留 OPENMV4_UART、文件落盘、门禁过。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["open_mv4"])
    assert {m.slug for m in resolved.manifests} == {"open_mv4"}
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
    assert "const OPENMV4_UART = UART.addInstance();" in syscfg
    assert 'OPENMV4_UART.peripheral.$assign = "UART1";' in syscfg
    assert 'OPENMV4_UART.peripheral.rxPin.$assign = "PA9";' in syscfg
    assert 'OPENMV4_UART.peripheral.txPin.$assign = "PA8";' in syscfg
    for drop in (
        "STEP_MOTOR", "HUIDU", "KEY", "LED_BEEP", "IR_BEAM", "WS2812",
        "HX711", "AHT10", "DHT11", "DS18B20", "BH1750", "SR04", "JOYSTICK",
        "MOTOR_PID", "NTB", "IMU601", "DIGIT_UART", "ZIGBEE_UART", "OLED",
        "I2C_0", "ADC12_0", "SHT30", "SHT20", "JY61P", "L298N_PWM", "L298N",
        "DEBUG_UART", "UWB_UART", "HC05_UART", "FINGERPRINT_UART",
    ):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/open_mv4/code/open_mv4.c").is_file()
    assert (out / "modules/open_mv4/code/open_mv4.h").is_file()


def test_open_mv4_frame_parser_pure_function():
    """帧解析纯函数单测（镜像 C 侧解析器）：页面伪帧序列 → 坐标结果。"""
    # 页面案例一：最大色块中心 [cx,cy]（实际发送带前缀 + \r\n）
    assert openmv4_parse_frame("[123,456]") == (True, 123, 456)
    assert openmv4_parse_frame(
        "Maximum color block position : [12,34]\r\n"
    ) == (True, 12, 34)
    assert openmv4_parse_frame("[-8,99]") == (True, -8, 99)
    # 页面案例二：单值循迹偏差帧 [%d] → cy 置 0 占位
    assert openmv4_parse_frame("[-12]\r\n") == (True, -12, 0)
    assert openmv4_parse_frame("[0]") == (True, 0, 0)
    # 坏帧 / 越界形态（不解析；页面格式无空格——"[5, 6]" 同拒）
    assert openmv4_parse_frame("[abc") == (False, None, None)
    assert openmv4_parse_frame("[12,34") == (False, None, None)
    assert openmv4_parse_frame("[1,2,3]") == (False, None, None)
    assert openmv4_parse_frame("[5, 6]") == (False, None, None)
    assert openmv4_parse_frame("[12345678901,0]") == (False, None, None)  # 超长
    assert openmv4_parse_frame("no frame here") == (False, None, None)
    assert openmv4_parse_frame("") == (False, None, None)
    # 按 '\n' 分帧序列（页面数据流模拟：前缀帧 → 无检测间隔 → 新帧）
    frames = [
        "Maximum color block position : [10,20]\r\n",
        "\r\n",
        "[15,25]\n",
        "[bad\n",
        "[30,40]\r\n",
    ]
    assert openmv4_data_analysis(frames) == (30, 40)
    # 全坏帧 → 无新帧（C 侧返回 1 语义）
    assert openmv4_data_analysis(["[x]\r\n", "garbage\r\n"]) is None


def test_open_mv4_source_guards():
    """源码守卫（防回潮）：轮询接收无 IRQHandler、9600/OPENMV4_UART_INST、
    置信度恒 1.0、页面调试件剔除。"""
    source = (MODULES / "open_mv4" / "code" / "open_mv4.c").read_text(
        encoding="utf-8"
    )
    header = (MODULES / "open_mv4" / "code" / "open_mv4.h").read_text(
        encoding="utf-8"
    )
    assert "DL_UART_isRXFIFOEmpty(OPENMV4_UART_INST)" in source
    assert "DL_UART_receiveData(OPENMV4_UART_INST)" in source
    assert "IRQHandler(" not in source  # 轮询无 ISR 定义（fingerprint 先例）
    assert "NVIC_" not in source  # 页面 OpenMV4_usart_config NVIC 使能裁剪
    assert "OPENMV4_CONFIDENCE" in source
    assert "OPENMV4_RX_BUF_SIZE" in header
    assert "printf(" not in source
    assert "HardFault" not in source
    # 置信度恒 1.0（页面帧无置信度字段）
    assert re.search(r"OPENMV4_CONFIDENCE\s+1\.0f", header) is not None
