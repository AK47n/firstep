"""key_matrix 4×4 矩阵键盘模块（B 类新 slug——仅 stm32 条目）：真实库 +
真实母版不变量与 stm32 单选生成。

B 类新模板（照 ec11 + mq2 结构测试 + B 类口径）：manifest 形状（**仅
platforms.stm32**——无 mspm0 条目，mspm0 选本件报 missing 平台警告；依赖空；
8 引脚 = ROW1-4（gpio_out PB12-15）+ COL1-4（gpio_in PA9/PA10/PB10/PB11），
逐脚端口宏 16 宏在 pin_config.h 单源）、stm32 单选生成（生成集只含
key_matrix——ml_gpio 内嵌母版、uvprojx 注册）。守卫钉死扫描原式：键值
i×4+j+1（行主序 1-16、0=无键）、逐行拉低扫列 + 恢复行高 + 命中整扫退出、
**无防抖/连按/释放代码**（防抖归调用方节拍——页面 main 500ms 演示节拍会
丢键不落）、无 while 等待（纯 GPIO 快扫）、无 printf/GPIO_Init/RCC_/delay_ms
字面量（剥离注释后）；页面 L22 bsp_mh100x 串台仅 notes 记录。全程无 LLM、
无服务。
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
    '#include "key_matrix_stm32.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    key_matrix_init();\n"
    "    (void)key_matrix_scan();\n"
    "    (void)key_matrix_scan();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

BANNED_CODE_PATTERNS = [
    (r"\bprintf\b", "printf"),
    (r"\bmain\b", "main"),
    (r"\bboard_init\b", "board_init"),
    (r"\bGPIO_Init\b", "GPIO_Init（收敛 ml_gpio）"),
    (r"\bRCC_\w+\s*\(", "RCC_ 调用（收敛 ml_gpio）"),
    (r"stm32f4xx\.h", "stm32f4xx.h"),
    (r"stm32f10x\.h", "stm32f10x.h"),
    (r"\bdelay_1ms\b", "delay_1ms（ml_delay 无此 API）"),
    (r"\bdelay_ms\b", "delay_ms（阻塞延时——防抖归调用方节拍）"),
    (r"\bIRQHandler\b", "IRQHandler（纯 GPIO 快扫无中断）"),
    (r"\bEXTI\b", "EXTI（纯 GPIO 快扫无中断）"),
]


def test_key_matrix_manifest_shape_only_stm32():
    """B 类口径：仅 platforms.stm32（无 mspm0 条目——mspm0 选本件报 missing）；
    依赖空（纯 GPIO 快扫）；8 引脚 = 4 行 gpio_out（PB12-15）+ 4 列 gpio_in
    （PA9/PA10/PB10/PB11）逐脚端口宏（16 宏）。"""
    manifest = ModuleManifest.load(MODULES / "key_matrix")
    assert manifest.slug == "key_matrix"
    assert manifest.dependencies == ()
    assert set(manifest.platforms) == {"stm32"}

    stm32 = manifest.platforms["stm32"]
    assert [Path(f).name for f in stm32.files] == [
        "key_matrix_stm32.c",
        "key_matrix_stm32.h",
    ]
    for rel in stm32.files:
        assert (MODULES / "key_matrix" / rel).is_file(), rel
    assert [(p.id, p.type, p.default, p.required, p.macros) for p in stm32.pins] == [
        ("KEY_MATRIX_ROW1", "gpio_out", "PB12", True, ("KEY_MATRIX_ROW1_GPIO", "KEY_MATRIX_ROW1_PIN")),
        ("KEY_MATRIX_ROW2", "gpio_out", "PB13", True, ("KEY_MATRIX_ROW2_GPIO", "KEY_MATRIX_ROW2_PIN")),
        ("KEY_MATRIX_ROW3", "gpio_out", "PB14", True, ("KEY_MATRIX_ROW3_GPIO", "KEY_MATRIX_ROW3_PIN")),
        ("KEY_MATRIX_ROW4", "gpio_out", "PB15", True, ("KEY_MATRIX_ROW4_GPIO", "KEY_MATRIX_ROW4_PIN")),
        ("KEY_MATRIX_COL1", "gpio_in", "PA9", True, ("KEY_MATRIX_COL1_GPIO", "KEY_MATRIX_COL1_PIN")),
        ("KEY_MATRIX_COL2", "gpio_in", "PA10", True, ("KEY_MATRIX_COL2_GPIO", "KEY_MATRIX_COL2_PIN")),
        ("KEY_MATRIX_COL3", "gpio_in", "PB10", True, ("KEY_MATRIX_COL3_GPIO", "KEY_MATRIX_COL3_PIN")),
        ("KEY_MATRIX_COL4", "gpio_in", "PB11", True, ("KEY_MATRIX_COL4_GPIO", "KEY_MATRIX_COL4_PIN")),
    ]
    assert stm32.verified is True
    assert stm32.hardware_bound is False
    assert stm32.kit and stm32.source_url == (
        "https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/"
        "module/sensor/4x4-keyboard.html"
    )
    # B 类标注（notes 注明无 mspm0 条目 + 设计依据）
    assert "B 类" in stm32.notes
    assert "无 mspm0" in stm32.notes
    for needle in (
        "lckfb-地阔星移植手册/sensor--4x4-keyboard.md",
        "互替",
        "8 脚分配",
        "防抖",
        "bsp_mh100x",
        "未上板",
    ):
        assert needle in stm32.notes


def test_key_matrix_stm32_missing_warning_on_mspm0():
    """B 类口径：mspm0 平台选 key_matrix → missing 平台警告（缺少 mspm0 版本
    条目，生成将失败——B 类仅 stm32 条目）。"""
    resolved = resolve_selection(MODULES, PLATFORM_MSPM0, ["key_matrix"])
    missing = [w for w in resolved.warnings if w.kind == WARNING_MISSING]
    assert missing and missing[0].slug == "key_matrix"
    assert "缺少平台 mspm0 的版本" in missing[0].message


def test_key_matrix_stm32_macros_defined_in_pin_config():
    """stm32 接线单源：16 宏必须在母版 pin_config.h（抽 4 断言：ROW1/PB12、
    COL1/PA9、COL4/PB11——8 脚分配是 stm32 硬约束）。"""
    text = (STM32_MASTER / "pin_config.h").read_text(encoding="utf-8")
    assert re.search(r"#define\s+KEY_MATRIX_ROW1_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+KEY_MATRIX_ROW1_PIN\s+Pin_12", text)
    assert re.search(r"#define\s+KEY_MATRIX_ROW4_PIN\s+Pin_15", text)
    assert re.search(r"#define\s+KEY_MATRIX_COL1_GPIO\s+GPIO_A", text)
    assert re.search(r"#define\s+KEY_MATRIX_COL1_PIN\s+Pin_9", text)
    assert re.search(r"#define\s+KEY_MATRIX_COL2_PIN\s+Pin_10", text)
    assert re.search(r"#define\s+KEY_MATRIX_COL3_GPIO\s+GPIO_B", text)
    assert re.search(r"#define\s+KEY_MATRIX_COL3_PIN\s+Pin_10", text)
    # 16 宏全量在场（逐脚端口宏族）
    for row in (1, 2, 3, 4):
        assert re.search(
            rf"#define\s+KEY_MATRIX_ROW{row}_GPIO\s+GPIO_[AB]", text
        )
        assert re.search(rf"#define\s+KEY_MATRIX_ROW{row}_PIN\s+Pin_\d+", text)
        assert re.search(
            rf"#define\s+KEY_MATRIX_COL{row}_GPIO\s+GPIO_[AB]", text
        )
        assert re.search(rf"#define\s+KEY_MATRIX_COL{row}_PIN\s+Pin_\d+", text)


def test_key_matrix_stm32_single_select_generation(tmp_path):
    """key_matrix stm32 单选生成：生成集只含 key_matrix（依赖空——ml_gpio 内嵌
    母版）、静态门禁通过、模块文件落盘、uvprojx 注册 key_matrix_stm32.c。"""
    resolved = resolve_selection(MODULES, PLATFORM_STM32, ["key_matrix"])
    assert {m.slug for m in resolved.manifests} == {"key_matrix"}
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
    assert (out / "modules/key_matrix/code/key_matrix_stm32.c").is_file()
    assert (out / "modules/key_matrix/code/key_matrix_stm32.h").is_file()
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("key_matrix_stm32.c" in p for p in paths)
    assert (out / "pin_config.h").is_file()


def test_key_matrix_stm32_code_guards():
    """扫描原式守卫：注释里有页面缺陷清单（bsp_mh100x 串台/500ms 演示节拍
    记录），剥离注释后零 printf/GPIO_Init/RCC_/delay_ms/while 等待残留；
    键值 = i×4+j+1（页面原式）、逐行拉低扫列 + 恢复行高 + 命中整扫退出、
    无防抖/连按/释放代码；只吃母版 ml_gpio API（gpio_init/gpio_set/gpio_get）
    与 KEY_MATRIX_* 宏。"""
    c = (MODULES / "key_matrix" / "code" / "key_matrix_stm32.c").read_text(
        encoding="utf-8"
    )
    h = (MODULES / "key_matrix" / "code" / "key_matrix_stm32.h").read_text(
        encoding="utf-8"
    )
    full = c + "\n" + h

    # 页面缺陷清单（注释记录——不落码）
    assert "bsp_mh100x" in c
    assert "500ms" in h
    assert "i×4+j+1" in h  # 键值语义注释（行主序 1-16、0=无键）
    assert "防抖/连按/释放" in h  # 防抖归调用方说明
    code_only = strip_comments(full, keep_preprocessor=True)
    for pattern, label in BANNED_CODE_PATTERNS:
        assert not re.search(pattern, code_only), f"代码残留 {label}"

    # API 原型（0-16 键值语义）
    assert re.search(r"void key_matrix_init\(void\);", h)
    assert re.search(r"uint8_t key_matrix_scan\(void\);", h)
    assert re.search(r"#define\s+KEY_MATRIX_ROWS\s+4u", h)
    assert re.search(r"#define\s+KEY_MATRIX_COLS\s+4u", h)
    # 页面原式：键值 i*4+j+1（行主序）
    assert re.search(r"i\s*\*\s*4\s*\+\s*j\s*\+\s*1", code_only)
    # 行列扫描结构：逐行拉低 → 扫列 → 恢复行高 → 命中整扫退出
    assert "key_matrix_row_set" in code_only
    assert "key_matrix_col_get" in code_only
    assert "KEY_MATRIX_ROWS" in code_only and "KEY_MATRIX_COLS" in code_only
    # 8 脚初始化（4 行 OUT_PP + 4 列 IU——逐脚宏）
    assert "gpio_init(KEY_MATRIX_ROW1_GPIO, KEY_MATRIX_ROW1_PIN, OUT_PP)" in code_only
    assert "gpio_init(KEY_MATRIX_COL4_GPIO, KEY_MATRIX_COL4_PIN, IU)" in code_only
    # 无防抖代码（无 delay 循环/两次确认——纯 GPIO 快扫）
    assert "while" not in code_only
    assert "delay" not in code_only
    # 无引脚字面量（值在 pin_config.h 单源）
    assert "GPIO_B" not in code_only
    assert "Pin_12" not in code_only
