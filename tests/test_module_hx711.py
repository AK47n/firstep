"""hx711 称重模块（GPIO 双线时序件——非 I2C）：真实库 + 真实母版不变量与
双平台单选生成。

照 test_module_aht10.py 模板：manifest 形状（双平台文件齐、stm32 引脚宏
在母版 pin_config.h、pins 类型 = gpio_out（SCK）/gpio_in（DT）默认
PB5/PB0）、stm32 单选生成（uvprojx 注册 + 静态门禁过）、mspm0 单选生成
（syscfg 裁剪保留 HX711 + 模块文件落盘）。**页面缺陷防回潮守卫**（① 就绪
窗口 ≥ 一个转换周期（driver-defect-fixes/03：默认 10SPS ⇒ 100ms，窗口取 2 倍）
且无 `while (DT_GET` 无界式；② 无 GapValue 硬编码 207 演示常数
（HX711_GAP_VALUE 宏）；③ 补码 `^ 0x800000u`；④ 模块内 static 收敛无全局
泄漏；⑤ 无 printf/GPIO_Init/RCC_ 残留；⑥ SCK OUT_PP + DT IU 初始化）。
全程无 LLM、无服务。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contest_generator.clex import strip_comments
from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"


from tests._c_macros import c_defines, c_functions, c_int

def _read(rel: str) -> str:
    """读库内相对路径的文本（照 test_module_servo.py 同款小助手）。"""
    return (LIBRARY_ROOT / rel).read_text(encoding="utf-8", errors="replace")


from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

MAIN_C_MSPM0 = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "hx711.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    /* SYSCFG_DL_init(); */\n"
    "    hx711_init();\n"
    "    hx711_tare();\n"
    "    float w = hx711_get_gram();\n"
    "    (void)w;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)
MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "hx711_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    uint32_t raw = 0;\n"
    "    float gram = 0.0f;\n"
    "    hx711_init();\n"
    "    hx711_tare();\n"
    "    raw = hx711_read_raw();\n"
    "    (void)raw;\n"
    "    gram = hx711_get_gram();\n"
    "    (void)gram;\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

# 换算/规范字面量守卫：剥离注释后不得出现（标准库/寄存器/演示残留/
# 母版 ml_i2c 调用）。
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


def test_hx711_manifest_shape_both_platforms():
    """hx711：双平台文件齐；stm32 双角色 = gpio_out（SCK=PB5）/gpio_in
    （DT=PB0）逐脚端口宏；mspm0 条目原样（syscfg gpio_out PA28/gpio_in PA31）。"""
    manifest = ModuleManifest.load(MODULES / "hx711")
    assert manifest.slug == "hx711"
    assert manifest.dependencies == ("delay",)

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "hx711_stm32.c",
        "hx711_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "hx711" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("HX711_SCK", "gpio_out", "PB5", True, ("HX711_SCK_GPIO", "HX711_SCK_PIN")),
        ("HX711_DT", "gpio_in", "PB0", True, ("HX711_DT_GPIO", "HX711_DT_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit != ""
    assert stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/hx711-weighing-sensor.html"
    )
    for needle in (
        "lckfb-地阔星移植手册/sensor--hx711-weighing-sensor.md",
        "无界轮询",
        "未上板",
    ):
        assert needle in stm32.notes

    mspm0 = manifest.platforms["mspm0"]
    assert [Path(f).name for f in mspm0.files] == ["hx711.c", "hx711.h"]
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in mspm0.pins] == [
        ("HX711_SCK", "gpio_out", "PA28", True, ()),
        ("HX711_DT", "gpio_in", "PA31", True, ()),
    ]
    assert mspm0.verified is True


def test_hx711_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：HX711_SCK_GPIO/_SCK_PIN/_DT_GPIO/_DT_PIN 必须在
    母版 pin_config.h（默认 SCK=PB5 / DT=PB0——独立 GPIO 双线，非 I2C 总线）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+HX711_SCK_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+HX711_SCK_PIN\s+Pin_5", text)
    assert re.search(r"#define\s+HX711_DT_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+HX711_DT_PIN\s+Pin_0", text)


def test_hx711_mspm0_syscfg_instance():
    """mspm0 母版必须有 HX711 实例（SCK=PA28 输出 / DT=PA31 输入带上拉）。"""
    syscfg = (MSPM0_MASTER / "mspm0.syscfg").read_text(encoding="utf-8", newline="")
    assert "const HX711 = GPIO.addInstance();" in syscfg
    assert 'HX711.associatedPins[0].$name        = "HX711_SCK";' in syscfg
    assert 'HX711.associatedPins[0].pin.$assign  = "PA28";' in syscfg
    assert 'HX711.associatedPins[1].$name        = "DT";' in syscfg
    assert 'HX711.associatedPins[1].pin.$assign  = "PA31";' in syscfg


def test_hx711_stm32_single_select_generation(tmp_path):
    """hx711 stm32 单选生成：静态门禁通过、模块文件按 manifest 落盘、
    uvprojx 注册 hx711_stm32.c、pin_config.h 在工程根。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["hx711"])
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/hx711/code/hx711_stm32.c").is_file()
    assert (out / "modules/hx711/code/hx711_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("hx711_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_hx711_mspm0_single_select_generation(tmp_path):
    """hx711 mspm0 单选生成：syscfg 只留 HX711、模块文件落盘。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["hx711"])
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
    assert "const HX711 = GPIO.addInstance();" in syscfg
    assert 'HX711.associatedPins[1].pin.$assign  = "PA31";' in syscfg
    for drop in ("KEY", "HUIDU", "DIGIT_UART", "LED_BEEP", "IR_BEAM", "WS2812", "IMU601"):
        assert f"const {drop}" not in syscfg
    assert (out / "modules/hx711/code/hx711.c").is_file()
    assert (out / "modules/hx711/code/hx711.h").is_file()


def test_hx711_stm32_code_guards():
    """stm32 代码层守卫：剥离注释后零标准库/寄存器/演示残留、零 ml_i2c
    调用；引脚初始化（SCK OUT_PP + DT IU）；**页面缺陷防回潮**（① 就绪窗口
    按时间立（`HX711_READY_TIMEOUT_LOOPS`，专测见文件末）且无 `while (DT_GET`
    无界式、超时**不再返回 0**；② 补码 `^ 0x800000u`；③ HX711_GAP_VALUE 宏
    （无演示常数 207 硬编码于换算）；④ 模块内 static 收敛（无全局泄漏）；
    ⑤ 无 printf/GPIO_Init/RCC_）。"""
    c = (MODULES / "hx711" / "code" / "hx711_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "hx711" / "code" / "hx711_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # 引脚初始化：SCK 输出 PP、DT 上拉输入 IU（页面先 PP 输出再重配 IPU
    # 的动作按 mspm0 先例收敛为 init 直配 IU）
    assert re.search(
        r"gpio_init\(HX711_SCK_GPIO, HX711_SCK_PIN, OUT_PP\)", code_only
    )
    assert re.search(
        r"gpio_init\(HX711_DT_GPIO, HX711_DT_PIN, IU\)", code_only
    )

    # 页面缺陷防回潮：① 就绪窗口按时间立（≥ 一个转换周期，专测见文件末）——
    # 无 while 无界式、超时返回哨兵值而**不是 0**
    assert "if (++timeout > HX711_READY_TIMEOUT_LOOPS)" in code_only
    assert "return HX711_TIMEOUT_SENTINEL;" in code_only
    assert "return 0;" not in code_only
    assert "while (DT_GET" not in code_only
    assert "while (gpio_get(HX711_DT_GPIO" in code_only
    # ② 补码 ^0x800000；③ HX711_GAP_VALUE 宏（无 207.00 硬编码进换算——
    # 宏已参数化）
    assert "^ 0x800000u" in code_only
    assert "HX711_GAP_VALUE" in code_only
    assert "207.00f" in h  # 宏默认值保留在头（参数化）
    assert "GapValue 207" not in code_only
    # ④ 模块内 static 收敛（无全局泄漏）
    assert "static uint32_t s_tare" in code_only
    assert "HX711_Buffer" not in code_only
    assert "Weight_Maopi" not in code_only
    assert "Flag_Error" not in code_only

    # 时序/换算原式：24 位读 + 第 25 个脉冲、克 = (raw - tare)/GAP 差 ≤0 钳 0
    assert "for (i = 0; i < 24; i++)" in code_only
    assert "(int32_t)raw - (int32_t)s_tare" in code_only
    assert "delta <= 0" in code_only


# ---------------------------------------------------------------------------
# driver-defect-fixes/03：就绪窗口 ≥ 一个转换周期 + 「0 是合法读数」的歧义出口
# ---------------------------------------------------------------------------

# 模块默认输出速率：RATE 脚接低 = 10SPS（数据手册）⇒ 一个转换周期 100ms。
# 判据面用这个数**独立复算**窗口，不照抄实现里的表达式。
HX711_DEFAULT_SPS = 10

DRIVER_FILES = ("modules/hx711/code/hx711.c", "modules/hx711/code/hx711_stm32.c")


@pytest.mark.parametrize("rel", DRIVER_FILES)
def test_hx711_ready_window_covers_a_conversion_period(rel):
    """driver-defect-fixes/03 判据①：等 DT 就绪的窗口 ≥ **一个转换周期**。

    旧实现写死 `2000 × delay_us(10)` = 20ms（注释自称"近似手册转换周期"），
    而模块默认 10SPS 是 **100ms** ⇒ `hx711_init()` 内部那次去皮消费掉一个采样
    之后，紧接着的任何读都在等下一个样本、**必然超时**。窗口现在按常量算出来：
    转换周期 = 1000 / SPS，窗口 = 2 × 转换周期。
    """
    defines = c_defines(_read(rel))
    conv_ms = 1000 // HX711_DEFAULT_SPS  # = 100
    assert c_int(defines, "HX711_CONV_PERIOD_MS") == conv_ms
    window_ms = c_int(defines, "HX711_READY_TIMEOUT_MS")
    assert window_ms >= conv_ms, f"{rel} 的窗口 {window_ms}ms 短于一个转换周期 {conv_ms}ms"
    # 轮询圈数必须由「窗口 ÷ 步长」推出来（不许再出现写死的 2000）
    assert c_int(defines, "HX711_READY_TIMEOUT_LOOPS") == (
        window_ms * 1000 // c_int(defines, "HX711_POLL_US")
    )
    assert "2000" not in strip_comments(_read(rel), keep_preprocessor=True)
    # **循环的退出界与步长也要绑住**：常量算对了、循环里却写死别的数等于没修
    reader = c_functions(strip_comments(_read(rel), keep_preprocessor=True))["hx711_read_raw"]
    assert re.search(
        r"if\s*\(\s*\+\+timeout\s*>\s*HX711_READY_TIMEOUT_LOOPS\s*\)", reader
    ), "等 DT 就绪的循环没有拿 HX711_READY_TIMEOUT_LOOPS 当退出界"
    assert re.search(r"delay_us\(HX711_POLL_US\)", reader), "轮询步长不是那个 10µs 常量"


@pytest.mark.parametrize("rel", DRIVER_FILES)
def test_hx711_tare_never_stores_a_timeout_as_the_zero_point(rel):
    """driver-defect-fixes/03 判据②尾巴：**去皮也不能把哨兵存成零点**。

    这是评审抓出来的一处真缺陷：`s_tare = hx711_read_raw();` 在超时时会让
    `s_tare = 0xFFFFFFFF`，于是 `克 = (raw - s_tare)` 变成 `raw + 1` 的**天文数字**
    （旧代码存 0 反而没这么坏）。「失败不能靠调用方自觉」这条对驱动自己也成立。
    """
    code_only = strip_comments(_read(rel), keep_preprocessor=True)
    tare = c_functions(code_only)["hx711_tare"]
    assert "s_tare = hx711_read_raw();" not in tare, "把可能超时的读直接存成了零点"
    assert re.search(
        r"if\s*\(\s*raw\s*!=\s*HX711_TIMEOUT_SENTINEL\s*\)\s*\{[^}]*s_tare\s*=\s*raw\s*;",
        tare,
        re.S,
    ), "去皮的赋值没有过哨兵判断"


@pytest.mark.parametrize("rel", DRIVER_FILES)
def test_hx711_timeout_is_never_disguised_as_a_zero_reading(rel):
    """driver-defect-fixes/03 判据②：读失败时**能明确区分「超时」与「零值」**。

    合法读数是 `count ^ 0x800000`（24 位，0 ~ 0xFFFFFF）：`count == 0x800000`
    （空秤零点）也返 0，所以 0 不能同时充当失败标记。超时改返回哨兵值
    `HX711_TIMEOUT_SENTINEL`——它在 24 位合法域之外；克数接口同样把「没读到」
    （负值）与「空秤」（0.0f）分开。
    """
    source = _read(rel)
    header = _read(
        "modules/hx711/code/hx711.h"
        if rel.endswith("hx711.c")
        else "modules/hx711/code/hx711_stm32.h"
    )
    code_only = strip_comments(source, keep_preprocessor=True)
    defines = c_defines(source, header)

    sentinel = c_int(defines, "HX711_TIMEOUT_SENTINEL")
    assert sentinel > 0xFFFFFF, "哨兵值落在 24 位合法读数域内，分不开"
    assert "return HX711_TIMEOUT_SENTINEL;" in code_only
    assert "return 0;" not in code_only, "超时分支仍在用 0 冒充读数"
    assert "return -1.0f;" in code_only, "克数接口没把「没读到」与「空秤 0」分开"


def test_hx711_window_and_sentinel_are_identical_on_both_platforms():
    """driver-defect-fixes/03 判据③：双平台行为一致（同窗口、同哨兵、同语义）。

    两平台各写一份常量是既有体例（各自 .c 自持），所以这里做**跨文件对拍**：
    任一平台单独改了窗口 / 哨兵值，本用例当场红。
    """
    mspm0 = c_defines(_read(DRIVER_FILES[0]), _read("modules/hx711/code/hx711.h"))
    stm32 = c_defines(_read(DRIVER_FILES[1]), _read("modules/hx711/code/hx711_stm32.h"))
    for name in (
        "HX711_SPS_DEFAULT",
        "HX711_CONV_PERIOD_MS",
        "HX711_READY_TIMEOUT_MS",
        "HX711_POLL_US",
        "HX711_READY_TIMEOUT_LOOPS",
        "HX711_TIMEOUT_SENTINEL",
    ):
        assert c_int(mspm0, name) == c_int(stm32, name), f"两平台的 {name} 不一致"
    # 公共 API 签名与语义（对偶）一字不动
    for header in ("modules/hx711/code/hx711.h", "modules/hx711/code/hx711_stm32.h"):
        text = _read(header)
        assert re.search(r"void hx711_init\(void\);", text)
        assert re.search(r"void hx711_tare\(void\);", text)
        assert re.search(r"uint32_t hx711_read_raw\(void\);", text)
        assert re.search(r"float hx711_get_gram\(void\);", text)
