"""README 渲染器核心 + 生成落盘（工单 project-readme/01 + 02）。

主 seam = generate_project 流程级：stm32 与 mspm0 各生成一例到 tmp，断言
README.md 存在、含五章标题、含所选模块 slug/description、引脚表含声明角色的
默认引脚、验证顺序清单符合规则（bring-up 前置 + 组内依赖序）、不含未选模块
引脚。渲染器纯函数直测（确定性 / 板名可选 / 引脚行格式 / 依赖显示 / 快速上手
固定话术 / 排序纯函数边界 / 空集边界 / 尾部换行）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.boards import Board
from contest_generator.generator import generate_project
from contest_generator.manifest import ModuleManifest, PinDeclaration, PlatformEntry
from contest_generator.patchers import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.readme import (
    PIN_TABLE_FOOTNOTE,
    README_FILENAME,
    PLATFORM_TITLES,
    render_readme,
    sort_verification_order,
)
from tests.fakes import (
    MAIN_SKELETON,
    _add_module,
    make_fake_ccs_theia_master_project,
    make_fake_master_project,
)

# 五章标题（spec 章节顺序：概览 → 快速上手 → 引脚表 → 模块清单 → 验证清单）
CHAPTER_HEADINGS = (
    "## 工程概览",
    "## 快速上手：编译 + 烧录",
    "## 引脚接线表",
    "## 模块清单与依赖",
    "## 验证顺序清单",
)


def _add_pin_modules(library: Path) -> None:
    """给假模块库补两个带 pins 声明的模块：key（流程测试选中）/ beep（不选，
    断言「不含未选模块引脚」用）。两平台各声明一条引脚。"""
    _add_module(
        library,
        {
            "slug": "key",
            "description": "独立按键输入",
            "dependencies": ["delay"],
            "platforms": {
                PLATFORM_STM32: {
                    "files": ["code/key.c", "code/key.h"],
                    "verified": True,
                    "pins": [
                        {
                            "id": "KEY_START",
                            "type": "gpio_in",
                            "default": "PB3",
                            "label": "启动按键",
                            "required": True,
                        }
                    ],
                },
                PLATFORM_MSPM0: {
                    "files": ["code/key.c", "code/key.h"],
                    "verified": True,
                    "pins": [
                        {
                            "id": "KEY_START",
                            "type": "gpio_in",
                            "default": "PA18",
                            "label": "启动按键",
                            "required": True,
                        }
                    ],
                },
            },
        },
        {
            "code/key.c": '#include "key.h"\nvoid key_init(void);\n',
            "code/key.h": "#pragma once\nvoid key_init(void);\n",
        },
    )
    _add_module(
        library,
        {
            "slug": "beep",
            "description": "有源蜂鸣器提示",
            "dependencies": [],
            "platforms": {
                PLATFORM_STM32: {
                    "files": ["code/beep.c", "code/beep.h"],
                    "verified": True,
                    "pins": [
                        {"id": "BEEP_OUT", "type": "gpio_out", "default": "PC14"}
                    ],
                },
                PLATFORM_MSPM0: {
                    "files": ["code/beep.c", "code/beep.h"],
                    "verified": True,
                    "pins": [
                        {"id": "BEEP_OUT", "type": "gpio_out", "default": "PA14"}
                    ],
                },
            },
        },
        {
            "code/beep.c": '#include "beep.h"\nvoid beep_on(void);\n',
            "code/beep.h": "#pragma once\nvoid beep_on(void);\n",
        },
    )


def _add_bringup_modules(library: Path) -> None:
    """给假模块库补 bring-up 模块（debug_uart / led / led_beep，均依赖 delay
    ——验证顺序清单章断言 bring-up 前置 + 组内依赖序用，流程测试选中）。纯 .c
    无头文件（模块自包含门禁对无头文件模块跳过，见 generator
    _check_module_self_include）。"""
    _add_module(
        library,
        {
            "slug": "debug_uart",
            "description": "调试串口输出",
            "dependencies": ["delay"],
            "platforms": {
                PLATFORM_STM32: {"files": ["code/debug_uart.c"], "verified": True},
                PLATFORM_MSPM0: {"files": ["code/debug_uart.c"], "verified": True},
            },
        },
        {"code/debug_uart.c": "/* debug_uart */\n"},
    )
    _add_module(
        library,
        {
            "slug": "led",
            "description": "状态指示灯",
            "dependencies": ["delay"],
            "platforms": {
                PLATFORM_STM32: {"files": ["code/led.c"], "verified": True},
                PLATFORM_MSPM0: {"files": ["code/led.c"], "verified": True},
            },
        },
        {"code/led.c": "/* led */\n"},
    )
    _add_module(
        library,
        {
            "slug": "led_beep",
            "description": "LED 蜂鸣器声光提示",
            "dependencies": ["delay"],
            "platforms": {
                PLATFORM_STM32: {"files": ["code/led_beep.c"], "verified": True},
                PLATFORM_MSPM0: {"files": ["code/led_beep.c"], "verified": True},
            },
        },
        {"code/led_beep.c": "/* led_beep */\n"},
    )


# ---------------------------------------------------------------------------
# 流程级 seam：generate_project 落盘 README（stm32 / mspm0 各一例）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("platform", "master_builder", "expected_pin", "unselected_pin", "board_chip"),
    [
        (
            PLATFORM_STM32,
            make_fake_master_project,
            "PB3",
            "PC14",
            "蓝药丸",
        ),
        (
            PLATFORM_MSPM0,
            make_fake_ccs_theia_master_project,
            "PA18",
            "PA14",
            "地猛星",
        ),
    ],
)
def test_generate_project_writes_readme(
    fake_module_library,
    tmp_path,
    platform,
    master_builder,
    expected_pin,
    unselected_pin,
    board_chip,
):
    """生成工程根多出 README.md：五章标题 + 依赖展开后的模块清单 + 引脚表
    （声明角色默认脚 / label 附注 / 必接标记）+ 尾注；不含未选模块引脚。"""
    _add_pin_modules(fake_module_library)
    masters_dir = tmp_path / "masters"
    master_builder(masters_dir / platform)

    summary = generate_project(
        platform=platform,
        slugs=["key", "dht11"],  # beep 不选
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )

    assert (summary.output_dir / README_FILENAME).is_file()
    readme = (summary.output_dir / README_FILENAME).read_text(encoding="utf-8")

    # 本工单三章标题
    for heading in CHAPTER_HEADINGS:
        assert heading in readme
    # 平台/主控中文名 + 板名（board_for_platform 取到即显示）
    assert PLATFORM_TITLES[platform] in readme
    assert board_chip in readme

    # 模块清单与依赖：依赖展开后的 manifest 集，依赖先于使用者
    assert "- delay：软件延时" in readme
    assert "- key：独立按键输入（依赖：delay）" in readme
    assert "DHT11 温湿度传感器驱动" in readme

    # 引脚接线表：声明角色的默认引脚 + label 附注 + required 必接标记
    assert "KEY_START（启动按键）" in readme
    assert f"| key | KEY_START（启动按键） | {expected_pin} | gpio_in（必接） |" in readme
    # 不含未选模块（beep）的引脚
    assert "BEEP_OUT" not in readme
    assert unselected_pin not in readme
    # 表尾固定尾注（未声明 pins 模块不硬猜的兜底声明）
    assert PIN_TABLE_FOOTNOTE in readme


def test_generate_project_readme_degrades_without_board(
    fake_module_library, tmp_path, monkeypatch
):
    """板数据取不到（board_for_platform 抛 BoardError）：生成不阻断，README
    工程概览章不显示板名行（优雅降级——工单验收「取不到不阻断生成」）。"""
    from contest_generator import generator as generator_module
    from contest_generator.boards import BoardError

    def _no_board(platform: str) -> Board:
        raise BoardError(f"平台 {platform!r} 没有板定义")

    monkeypatch.setattr(generator_module, "board_for_platform", _no_board)

    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["delay"],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )

    assert (summary.output_dir / README_FILENAME).is_file()
    readme = (summary.output_dir / README_FILENAME).read_text(encoding="utf-8")
    assert "## 工程概览" in readme
    assert "- 开发板" not in readme


def test_generate_project_readme_is_byte_deterministic(fake_module_library, tmp_path):
    """同一输入两次生成 → README.md 逐字节一致（不含时间戳，可测试）。"""
    _add_pin_modules(fake_module_library)
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    def _run(out: Path) -> bytes:
        generate_project(
            platform=PLATFORM_STM32,
            slugs=["key", "dht11"],
            main_c_content=MAIN_SKELETON,
            output_dir=out,
            module_library_dir=fake_module_library,
            masters_dir=masters_dir,
        )
        return (out / README_FILENAME).read_bytes()

    assert _run(tmp_path / "out1") == _run(tmp_path / "out2")


def test_generate_project_readme_verification_order(fake_module_library, tmp_path):
    """快速上手 / 验证顺序清单两章进生成 README；验证清单 = bring-up 模块
    （delay / led_beep / debug_uart / led）前置 + 组内依赖序（delay 在
    led_beep 前），非 bring-up（dht11）殿后。"""
    _add_bringup_modules(fake_module_library)
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["led_beep", "dht11", "debug_uart", "led"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )
    readme = (summary.output_dir / README_FILENAME).read_text(encoding="utf-8")

    # 两新章标题
    assert "## 快速上手：编译 + 烧录" in readme
    assert "## 验证顺序清单" in readme
    # 快速上手固定话术（stm32 = Keil5 打开 uvprojx / 编译 / ST-Link 下载）
    assert "Keil MDK" in readme
    assert "ST-Link" in readme
    assert "uvprojx" in readme

    # 验证清单行：checkbox 格式（slug — description），顺序 = 分区排序结果
    checklist = readme.split("## 验证顺序清单")[-1]
    lines = [
        ln.removeprefix("- [ ] ")
        for ln in checklist.splitlines()
        if ln.startswith("- [ ] ")
    ]
    slugs = [ln.split(" — ", 1)[0] for ln in lines]
    assert slugs == ["delay", "led_beep", "debug_uart", "led", "dht11"]


# ---------------------------------------------------------------------------
# 渲染器纯函数直测：确定性 / 板名可选 / 引脚行格式 / 依赖 / 边界
# ---------------------------------------------------------------------------


def _m(
    slug: str,
    description: str,
    *,
    deps: tuple[str, ...] = (),
    pins: tuple[tuple[str, str, str, str, bool], ...] = (),
) -> ModuleManifest:
    """内存直构 manifest（platform = stm32；pins 形状 = (id, type, default,
    label, required)——渲染器只读该平台 pins 声明，files 空即可）。"""
    return ModuleManifest(
        slug=slug,
        description=description,
        dependencies=deps,
        platforms={
            PLATFORM_STM32: PlatformEntry(
                files=(),
                pins=tuple(
                    PinDeclaration(
                        id=pid,
                        type=ptype,
                        default=pdefault,
                        label=plabel,
                        required=preq,
                    )
                    for (pid, ptype, pdefault, plabel, preq) in pins
                ),
            )
        },
    )


def test_render_readme_same_input_same_output():
    """确定性：同一输入两次调用逐字节一致（无时间戳 / 随机源）。"""
    manifests = [
        _m("delay", "软件延时"),
        _m(
            "motor",
            "TB6612 双路直流电机驱动",
            deps=("delay",),
            pins=(("MOTOR_A_PWM", "pwm", "PA0", "A 路 PWM", True),),
        ),
    ]
    assert render_readme("stm32", "最小系统板", manifests) == render_readme(
        "stm32", "最小系统板", manifests
    )


def test_render_readme_trailing_newline():
    """尾部换行幂等：返回文本恒以单个 \\n 收尾。"""
    assert render_readme("stm32", None, []).endswith("\n")
    assert not render_readme("stm32", None, []).endswith("\n\n")


def test_render_readme_board_name_optional():
    """板名取不到（None）= 工程概览章不显示板名行，不阻断渲染。"""
    assert "- 开发板：地猛星 MSPM0G3507" in render_readme("mspm0", "地猛星 MSPM0G3507", [])
    assert "- 开发板" not in render_readme("mspm0", None, [])


def test_render_readme_pin_row_label_and_required():
    """引脚行格式：角色 id + label 附注、生效引脚 = 声明默认值、说明 = 类型 +
    必接标记；表尾尾注恒在。"""
    manifests = [
        _m(
            "motor",
            "TB6612 双路直流电机驱动",
            pins=(("MOTOR_A_PWM", "pwm", "PA0", "A 路 PWM", True),),
        )
    ]
    text = render_readme("stm32", None, manifests)
    assert "| motor | MOTOR_A_PWM（A 路 PWM） | PA0 | pwm（必接） |" in text
    assert PIN_TABLE_FOOTNOTE in text


def test_render_readme_pin_required_false_no_marker():
    """required=False 不显示必接标记；label 缺省 = 角色列只有 id。"""
    manifests = [
        _m("beep", "有源蜂鸣器", pins=(("BEEP_OUT", "gpio_out", "PC14", "", False),))
    ]
    text = render_readme("stm32", None, manifests)
    assert "| beep | BEEP_OUT | PC14 | gpio_out |" in text
    assert "（必接）" not in text


def test_render_readme_dependencies_listed_in_order():
    """模块清单章按 manifest 集顺序（依赖先于使用者）渲染 slug + description，
    有依赖才列（依赖：…）。"""
    manifests = [_m("delay", "软件延时"), _m("key", "独立按键输入", deps=("delay",))]
    text = render_readme("stm32", None, manifests)
    assert "- delay：软件延时" in text
    assert "- key：独立按键输入（依赖：delay）" in text
    assert text.index("- delay") < text.index("- key")


def test_render_readme_no_pins_falls_back_to_footnote():
    """全模块未声明 pins：不画空表头，占位句 + 固定尾注兜底。"""
    text = render_readme("stm32", None, [_m("delay", "软件延时")])
    assert "本工程所选模块未声明引脚接线。" in text
    assert "| 模块 |" not in text
    assert PIN_TABLE_FOOTNOTE in text


def test_render_readme_quick_start_stm32():
    """快速上手章（stm32）：Keil5 打开 uvprojx / 编译 / ST-Link 下载固定话术，
    不做逐模块拼装——空模块集也有完整步骤。"""
    text = render_readme("stm32", None, [])
    assert "## 快速上手：编译 + 烧录" in text
    assert "Keil MDK" in text
    assert "uvprojx" in text
    assert "ST-Link" in text
    assert "STM32F103C8T6" in text


def test_render_readme_quick_start_mspm0():
    """快速上手章（mspm0）：CCS 打开工程 / 构建 / 下载固定话术。"""
    text = render_readme("mspm0", None, [])
    assert "## 快速上手：编译 + 烧录" in text
    assert "CCS" in text
    assert "MSPM0G3507" in text
    assert "下载" in text


def test_render_readme_verification_checklist_format():
    """验证顺序清单章：固定引导语 + checkbox 行格式（slug — description），
    bring-up 模块排在非 bring-up 前。"""
    text = render_readme(
        "stm32",
        None,
        [_m("delay", "软件延时"), _m("dht11", "DHT11 温湿度传感器驱动")],
    )
    assert "按顺序逐个验证，前一个过了再接下一个" in text
    assert "- [ ] delay — 软件延时" in text
    assert "- [ ] dht11 — DHT11 温湿度传感器驱动" in text
    assert text.index("- [ ] delay") < text.index("- [ ] dht11")


# ---------------------------------------------------------------------------
# 验证顺序排序纯函数直测：bring-up 前置 / 原序保持 / 空集 / 依赖序
# ---------------------------------------------------------------------------


def test_sort_verification_order_bringup_first():
    """bring-up 模块前置，其余保持原序。"""
    manifests = [
        _m("dht11", "DHT11 温湿度传感器驱动"),
        _m("delay", "软件延时"),
        _m("led", "状态指示灯"),
    ]
    assert [m.slug for m in sort_verification_order(manifests)] == [
        "delay",
        "led",
        "dht11",
    ]


def test_sort_verification_order_no_bringup_keeps_order():
    """无 bring-up 模块：原序不变。"""
    manifests = [_m("a", "模块 A"), _m("b", "模块 B"), _m("c", "模块 C")]
    assert [m.slug for m in sort_verification_order(manifests)] == ["a", "b", "c"]


def test_sort_verification_order_empty():
    """空集不崩。"""
    assert sort_verification_order([]) == []


def test_sort_verification_order_keeps_dependency_order():
    """bring-up 组内保持相互间依赖序：delay 在 led_beep 前（输入 = DFS 后序，
    依赖先于使用者）。"""
    manifests = [_m("delay", "软件延时"), _m("led_beep", "LED 蜂鸣器声光提示")]
    assert [m.slug for m in sort_verification_order(manifests)] == [
        "delay",
        "led_beep",
    ]
