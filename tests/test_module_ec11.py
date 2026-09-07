"""ec11 旋转编码器模块（B 类新 slug——仅 stm32 条目）：真实库 + 真实母版不变量
与 stm32 单选生成。

B 类新模板（照 mq2 结构测试 + B 类口径）：manifest 形状（**仅 platforms.stm32**
——无 mspm0 条目，mspm0 选本件报 missing 平台警告；依赖空；3 引脚
EC11_A/B/SW = gpio_in PA4/PB5/PB0，逐脚端口宏）、6 宏在 pin_config.h 单源、
stm32 单选生成（生成集只含 ec11——ml_gpio 内嵌母版、uvprojx 注册）。守卫钉死
轮询方案：无 EXTI/NVIC/TIM/IRQHandler/printf/GPIO_Init/RCC_/delay_ms 字面量
（剥离注释后——页面 TIM3 中断扫描 + 100ms 阻塞消抖不落码）；ec11_get_delta
增量语义（清零式）注释、「A 相跳变采样 B」判向注释（页面代码算法——页面
L60-61 真值表与正文 L44-46、代码判向矛盾按代码）、SW 低有效说明、驱动零阻塞
（无 BUSY 等待）。全程无 LLM、无服务。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from contest_generator.clex import strip_comments
from contest_generator.manifest import ModuleManifest

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"
STM32_MASTER = LIBRARY_ROOT / "masters" / "stm32"
MSPM0_MASTER = LIBRARY_ROOT / "masters" / "mspm0"

from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import (  # noqa: E402
    PLATFORM_MSPM0,
    PLATFORM_STM32,
)
from contest_generator.selection import (  # noqa: E402
    WARNING_MISSING,
    resolve_selection,
)

MAIN_C_STM32 = (
    '#include "headfile.h"\n'
    '#include "ec11_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    ec11_init();\n"
    "    (void)ec11_get_delta();\n"
    "    (void)ec11_read_sw();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf（页面 printf 在驱动文件内——必须剔除）"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init（收敛 ml_gpio）"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用（收敛 ml_gpio）"),
    (r"stm32f4xx\.h", "stm32f4xx.h"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bdelay_1ms\b", "delay_1ms（ml_delay 无此 API）"),
    (r"\bdelay_ms\b", "delay_ms（阻塞延时——防抖归调用方节拍）"),
    (r"\bIRQHandler\b", "IRQHandler（轮询方案无中断）"),
    (r"\bEXTI\b", "EXTI（轮询——不注册 EXTI 中断）"),
    (r"\bNVIC\b", "NVIC（轮询——无中断配置）"),
    (r"\bTIM3\b", "TIM3（轮询——不占 TIMER）"),
]


def test_ec11_manifest_shape_only_stm32():
    """B 类口径：仅 platforms.stm32（无 mspm0 条目——mspm0 选本件报 missing）；
    依赖空（轮询无阻塞延时）；3 引脚 gpio_in 默认 PA4/PB5/PB0 逐脚端口宏。"""
    manifest = ModuleManifest.load(MODULES / "ec11")
    assert manifest.slug == "ec11"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"stm32"}

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "ec11_stm32.c",
        "ec11_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "ec11" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("EC11_A", "gpio_in", "PA4", True, ("EC11_A_GPIO", "EC11_A_PIN")),
        ("EC11_B", "gpio_in", "PB5", True, ("EC11_B_GPIO", "EC11_B_PIN")),
        ("EC11_SW", "gpio_in", "PB0", True, ("EC11_SW_GPIO", "EC11_SW_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/ec11.html"
    )
    # B 类标注（notes 注明无 mspm0 条目 + 设计依据）
    assert "B 类" in stm32.notes
    assert "无 mspm0" in stm32.notes
    for needle in (
        "lckfb-地阔星移植手册/sensor--ec11.md",
        "轮询",
        "不注册 GPIO EXTI",
        "TIM3",
        "按代码",
        "未上板",
    ):
        assert needle in stm32.notes


def test_ec11_stm32_missing_warning_on_mspm0():
    """B 类口径：mspm0 平台选 ec11 → missing 平台警告（缺少 mspm0 版本条目，
    生成将失败——B 类仅 stm32 条目）。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["ec11"])
    missing = [w for w in resolved.warnings if w.kind == WARNING_MISSING]
    assert missing and missing[0].slug == "ec11"
    assert "缺少平台 mspm0 的版本" in missing[0].message


def test_ec11_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：6 宏必须在母版 pin_config.h（A=GPIO_A/Pin_4、B=GPIO_B/
    Pin_5、SW=GPIO_B/Pin_0——页面默认 PA6/PA4/PA7 不照抄）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+EC11_A_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+EC11_A_PIN\s+Pin_4", text)
    assert re.search(r"#define\s+EC11_B_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+EC11_B_PIN\s+Pin_5", text)
    assert re.search(r"#define\s+EC11_SW_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+EC11_SW_PIN\s+Pin_0", text)


def test_ec11_stm32_single_select_generation(tmp_path):
    """ec11 stm32 单选生成：生成集只含 ec11（依赖空——ml_gpio 内嵌母版）、
    静态门禁通过、模块文件落盘、uvprojx 注册 ec11_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["ec11"])
    assert {m.slug for m in resolved.manifests} == {"ec11"}
    assert resolved.warnings == ()
    out = tmp_path / "out"
    generate(
        platform=PLATFORM_STM32,
        manifests=resolved.manifests,
        module_library_dir=MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=out,
        main_c_content=MAIN_C_STM32,
    )
    assert (out / "modules/ec11/code/ec11_stm32.c").is_file()
    assert (out / "modules/ec11/code/ec11_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("ec11_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_ec11_stm32_code_guards():
    """轮询方案守卫：注释里有页面缺陷清单（TIM3 中断改轮询/真值表矛盾按代码/
    printf 剔除/100ms 消抖归调用方），剥离注释后零 EXTI/NVIC/TIM/printf/标准库/
    寄存器/阻塞延时残留；只吃母版 ml_gpio API（gpio_init IU + gpio_get）与
    EC11_* 宏；增量语义 + A 相跳变采样 B 判向。"""
    c = (MODULES / "ec11" / "code" / "ec11_stm32.c").read_text(encoding="utf-8")
    h = (MODULES / "ec11" / "code" / "ec11_stm32.h").read_text(encoding="utf-8")
    full = c + "\n" + h

    # 页面缺陷清单（注释记录——不落码）
    assert "TIM3" in c
    assert "按代码" in h
    assert "增量语义" in h
    assert "A 相跳变采样 B" in h  # 判向注释（页面算法）
    assert "低有效" in h and "防抖归调用方" in h
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # API 原型（增量语义 + SW 低有效）
    assert re.search(r"void ec11_init\(void\);", h)
    assert re.search(r"int16_t ec11_get_delta\(void\);", h)
    assert re.search(r"uint8_t ec11_read_sw\(void\);", h)
    # 轮询实现：A 相跳变采样 B（if (a != ec11_prev_a) + 采样 B 判向）
    assert "ec11_prev_a" in code_only
    assert "ec11_accum" in code_only
    assert "gpio_init(EC11_A_GPIO, EC11_A_PIN, IU)" in code_only
    assert "gpio_init(EC11_B_GPIO, EC11_B_PIN, IU)" in code_only
    assert "gpio_init(EC11_SW_GPIO, EC11_SW_PIN, IU)" in code_only
    assert "gpio_get(EC11_A_GPIO, EC11_A_PIN)" in code_only
    assert "gpio_get(EC11_B_GPIO, EC11_B_PIN)" in code_only
    assert "gpio_get(EC11_SW_GPIO, EC11_SW_PIN)" in code_only
    # 增量清零语义（返回累计后清零）
    assert "ec11_accum = 0" in code_only
    # 无阻塞延时/BUSY 等待（驱动零阻塞）
    assert "while" not in code_only
    # 无引脚字面量（GPIO_A/Pin_4 值在 pin_config.h 单源——代码只引用宏）
    assert "GPIO_A" not in code_only
    assert "Pin_4" not in code_only
