"""README 渲染器核心 + 生成落盘（工单 project-readme/01 + 02 + 03）。

主 seam = generate_project 流程级：stm32 与 mspm0 各生成一例到 tmp，断言
README.md 存在、含五章标题、含所选模块 slug/description、引脚表含声明角色的
默认引脚、验证顺序清单符合规则（bring-up 前置 + 组内依赖序）、不含未选模块
引脚。渲染器纯函数直测（确定性 / 板名可选 / 引脚行格式 / 依赖显示 / 快速上手
固定话术 / 排序纯函数边界 / 空集边界 / 尾部换行）。

工单 03：生效引脚 = 绑定载荷覆盖值否则声明默认值（两平台统一）+ 多实例计划
每实例追加一行（角色 = 通道宏名、引脚 = 实例 pin）。流程级：同一选择无绑定
vs 带绑定各生成一例断言默认脚 / 绑定脚、带 led 多实例断言每实例一行；渲染器
级：双平台绑定覆盖 / 多实例行 / 缺省参数与现状逐字节不变（回归护栏）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pytest

from contest_generator.boards import Board
from contest_generator.generator import generate_project
from contest_generator.manifest import ModuleManifest, PinDeclaration, PlatformEntry
from contest_generator.patchers import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.pin_bindings import ResolvedBinding
from contest_generator.readme import (
    PIN_TABLE_FOOTNOTE,
    README_FILENAME,
    PLATFORM_TITLES,
    render_readme,
    sort_verification_order,
)
from contest_generator.selection import ExpandedInstance, ModuleInstance, ScorePoint
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


def _add_led_multi_module(library: Path) -> None:
    """给假模块库补带 multi_instance 的 led 模块（与真实 led manifest 同构：
    stm32 实现内嵌母版、无 pins 声明（多实例通道级接线落 led_instances.h）；
    mspm0 声明 LED 角色默认 PA15）。README 只消费实例计划，写侧（led_instances.h
    / syscfg）行为由 test_module_multi_instance 另行锁定。"""
    _add_module(
        library,
        {
            "slug": "led",
            "description": "状态指示灯",
            "dependencies": [],
            "multi_instance": {"max": 8, "variant": "color"},
            "platforms": {
                PLATFORM_STM32: {
                    "files": ["code/led.c", "code/led.h"],
                    "verified": True,
                },
                PLATFORM_MSPM0: {
                    "files": ["code/led.c", "code/led.h"],
                    "verified": True,
                    "pins": [
                        {
                            "id": "LED",
                            "type": "gpio_out",
                            "default": "PA15",
                            "required": True,
                        }
                    ],
                },
            },
        },
        {
            "code/led.c": '#include "led.h"\nvoid led_init(unsigned char channel);\n',
            "code/led.h": "#pragma once\nvoid led_init(unsigned char channel);\n",
        },
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


def test_generate_project_readme_binding_overrides_default_pin(
    fake_module_library, tmp_path
):
    """同一选择生成两例（不带绑定 vs 带绑定覆盖 key.KEY_START）：README 引脚表
    分别显示声明默认脚 PB3 与绑定脚 PA4（工单 03 生效引脚口径进生成 README）。"""
    _add_pin_modules(fake_module_library)
    masters_dir = tmp_path / "masters"
    master = make_fake_master_project(masters_dir / PLATFORM_STM32)
    # 写侧 apply_pin_bindings 对 stm32 无条件读 pin_config.h；key 无 macros =
    # 绑定写侧零改动（逐字节不落盘）——本测试只测 README 引脚表，写侧行为由
    # test_pin_unlock_* 另行锁定。
    (master / "pin_config.h").write_text(
        "#ifndef __PIN_CONFIG_H\n#define __PIN_CONFIG_H\n#endif\n", encoding="utf-8"
    )

    def _readme(out: Path, bindings: Mapping[str, str] | None) -> str:
        generate_project(
            platform=PLATFORM_STM32,
            slugs=["key", "dht11"],
            main_c_content=MAIN_SKELETON,
            output_dir=out,
            module_library_dir=fake_module_library,
            masters_dir=masters_dir,
            bindings=bindings,
        )
        return (out / README_FILENAME).read_text(encoding="utf-8")

    default_readme = _readme(tmp_path / "out_default", None)
    bound_readme = _readme(tmp_path / "out_bound", {"key.KEY_START": "PA4"})
    assert "| key | KEY_START（启动按键） | PB3 | gpio_in（必接） |" in default_readme
    assert "| key | KEY_START（启动按键） | PA4 | gpio_in（必接） |" in bound_readme
    assert "| key | KEY_START（启动按键） | PB3 | gpio_in（必接） |" not in bound_readme


def test_generate_project_readme_led_multi_instance(fake_module_library, tmp_path):
    """带 led 多实例选择的生成：引脚表每实例一行，角色 = 通道宏名、引脚 = 实例
    脚（stm32 内置色指定脚 red→PC13 / yellow→PC14）——追加在模块声明行之后。"""
    _add_led_multi_module(fake_module_library)
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["led", "dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
        instances={
            "led": (
                ModuleInstance(name="红灯", variant="red"),
                ModuleInstance(name="黄灯", variant="yellow"),
            )
        },
    )
    readme = (summary.output_dir / README_FILENAME).read_text(encoding="utf-8")
    # 每实例一行 + 引脚正确；stm32 led 无 pins 声明 = 实例行说明空串（尾注兜底）
    assert "| led | LED_RED | PC13 |  |" in readme
    assert "| led | LED_YELLOW | PC14 |  |" in readme


def test_generate_project_readme_defaults_byte_identical(fake_module_library, tmp_path):
    """流程级回归护栏：generate_project 缺省（None）与显式空载荷（bindings={}
    / instances={}）产出 README 逐字节一致——工单 03 参数透传不扰动 01/02 基线
    （基线内容由既有流程测试逐行锁定，渲染器级等价另由
    test_render_readme_defaults_byte_identical 覆盖）。"""
    _add_pin_modules(fake_module_library)
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    def _readme(
        out: Path,
        bindings: Mapping[str, str] | None,
        instances: Mapping[str, object] | None,
    ) -> bytes:
        generate_project(
            platform=PLATFORM_STM32,
            slugs=["key", "dht11"],
            main_c_content=MAIN_SKELETON,
            output_dir=out,
            module_library_dir=fake_module_library,
            masters_dir=masters_dir,
            bindings=bindings,
            instances=instances,
        )
        return (out / README_FILENAME).read_bytes()

    assert _readme(tmp_path / "out_default", None, None) == _readme(
        tmp_path / "out_empty", {}, {}
    )


def test_generate_project_readme_score_points_and_summary(fake_module_library, tmp_path):
    """评分点随生成流程进入 README 与只读摘要；同一份结构化数据用于两处输出。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    score_points = (
        ScorePoint("B1", "basic", "完成测距", 10.0, (2, 3)),
        ScorePoint("D1", "development", "提高精度", None, ()),
    )

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out_score",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
        score_points=score_points,
    )
    readme = (summary.output_dir / README_FILENAME).read_text(encoding="utf-8")

    assert summary.score_points == score_points
    assert "## 评分点验收清单" in readme
    assert "| B1 | 基础 | 10 分 | 句子 2、3 | 完成测距 |" in readme
    assert "| D1 | 发挥 | 未标分 | 未关联原文 | 提高精度 |" in readme


def test_generate_project_readme_omits_score_section_when_absent(
    fake_module_library, tmp_path
):
    """缺省评分点不新增空章节，保持既有 README 结构。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out_no_score",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )
    readme = (summary.output_dir / README_FILENAME).read_text(encoding="utf-8")

    assert summary.score_points == ()
    assert "## 评分点验收清单" not in readme


# ---------------------------------------------------------------------------
# 渲染器纯函数直测：确定性 / 板名可选 / 引脚行格式 / 依赖 / 边界
# ---------------------------------------------------------------------------


def _pin_data_rows(text: str) -> list[str]:
    """引脚表数据行（剔除表头 `| 模块 |` 与分隔行 `|---|`）。"""
    return [
        ln
        for ln in text.splitlines()
        if ln.startswith("| ") and not ln.startswith("| 模块") and not ln.startswith("|---")
    ]


def _entry(pins: tuple[tuple[str, str, str, str, bool], ...]) -> PlatformEntry:
    """(id, type, default, label, required) 序列 → PlatformEntry（files 空，
    渲染器只读 pins 声明）。双平台直构 manifest 用。"""
    return PlatformEntry(
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
        platforms={PLATFORM_STM32: _entry(pins)},
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


def test_render_readme_binding_overrides_default_pin():
    """生效引脚 = 绑定载荷覆盖值，否则声明默认值（两平台同一渲染路径；绑定
    只改 pin 值，角色 / 说明列不动）。"""
    key = ModuleManifest(
        slug="key",
        description="独立按键输入",
        platforms={
            PLATFORM_STM32: _entry((("KEY_START", "gpio_in", "PB3", "启动按键", True),)),
            PLATFORM_MSPM0: _entry((("KEY_START", "gpio_in", "PA18", "启动按键", True),)),
        },
    )

    decl_s = key.platforms[PLATFORM_STM32].pins[0]
    bound = render_readme(
        PLATFORM_STM32,
        None,
        [key],
        (ResolvedBinding(slug="key", declaration=decl_s, pin="PA4"),),
    )
    assert "| key | KEY_START（启动按键） | PA4 | gpio_in（必接） |" in bound
    assert "| key | KEY_START（启动按键） | PB3 | gpio_in（必接） |" not in bound

    decl_m = key.platforms[PLATFORM_MSPM0].pins[0]
    bound_m = render_readme(
        PLATFORM_MSPM0,
        None,
        [key],
        (ResolvedBinding(slug="key", declaration=decl_m, pin="PA28"),),
    )
    assert "| key | KEY_START（启动按键） | PA28 | gpio_in（必接） |" in bound_m
    assert "| key | KEY_START（启动按键） | PA18 | gpio_in（必接） |" not in bound_m


def test_render_readme_multi_instance_appends_rows():
    """多实例计划每实例追加一行：角色 = 通道宏名、引脚 = 实例 pin；追加在对应
    模块声明行之后（无声明行的模块 = 实例行紧贴其 manifest 位置）；说明 = 模块
    首个声明类型（未声明 pins = 空串）。"""
    key = ModuleManifest(
        slug="key",
        description="独立按键输入",
        platforms={PLATFORM_STM32: _entry((("KEY_START", "gpio_in", "PB3", "", False),))},
    )
    led = ModuleManifest(
        slug="led",
        description="状态指示灯",
        platforms={
            PLATFORM_STM32: _entry(()),  # stm32 led 无 pins 声明（内嵌母版）
            PLATFORM_MSPM0: _entry((("LED", "gpio_out", "PA15", "", True),)),
        },
    )
    plans_s = {
        "led": (
            ExpandedInstance(slug="led", index=1, macro="LED_RED", pin="PC13"),
            ExpandedInstance(slug="led", index=2, macro="LED_YELLOW", pin="PC14"),
        )
    }
    text = render_readme(PLATFORM_STM32, None, [key, led], instance_plans=plans_s)
    lines = _pin_data_rows(text)
    # 行序：key 声明行 → led 实例行（led 无声明行，实例行紧跟其 manifest 位置）
    assert lines == [
        "| key | KEY_START | PB3 | gpio_in |",
        "| led | LED_RED | PC13 |  |",
        "| led | LED_YELLOW | PC14 |  |",
    ]

    # mspm0：实例行说明 = 模块首个声明类型（仅类型，必接标记不随实例通道继承）
    # ——声明行（LED 默认脚）仍在实例行前
    plans_m = {
        "led": (
            ExpandedInstance(slug="led", index=1, macro="LED_RED", pin="PA15"),
            ExpandedInstance(slug="led", index=2, macro="LED_YELLOW", pin="PA16"),
        )
    }
    text_m = render_readme(PLATFORM_MSPM0, None, [led], instance_plans=plans_m)
    lines_m = _pin_data_rows(text_m)
    assert lines_m == [
        "| led | LED | PA15 | gpio_out（必接） |",
        "| led | LED_RED | PA15 | gpio_out |",
        "| led | LED_YELLOW | PA16 | gpio_out |",
    ]


def test_render_readme_defaults_byte_identical():
    """缺省参数（绑定 / 实例缺省或空）= 现状逐字节不变：显式 None / 空序列与
    完全缺省同输出（工单 03 回归护栏）。"""
    manifests = [
        _m(
            "motor",
            "TB6612 双路直流电机驱动",
            pins=(("MOTOR_A_PWM", "pwm", "PA0", "A 路 PWM", True),),
        )
    ]
    baseline = render_readme("stm32", "最小系统板", manifests)
    assert render_readme("stm32", "最小系统板", manifests, None, None) == baseline
    assert render_readme("stm32", "最小系统板", manifests, (), {}) == baseline


def test_render_readme_score_points_section():
    """评分点验收清单章：按题面顺序展示分区、分值、句号引用与描述。"""
    text = render_readme(
        "stm32",
        None,
        [_m("delay", "软件延时")],
        score_points=(
            ScorePoint("B1", "basic", "完成测距", 10.0, (2, 3)),
            ScorePoint("D1", "development", "提高精度", None, ()),
            ScorePoint("U1", "unknown", "展示结果", 2.5, ()),
        ),
    )

    assert "## 评分点验收清单" in text
    assert "| B1 | 基础 | 10 分 | 句子 2、3 | 完成测距 |" in text
    assert "| D1 | 发挥 | 未标分 | 未关联原文 | 提高精度 |" in text
    assert "| U1 | 未分区 | 2.5 分 | 未关联原文 | 展示结果 |" in text


def test_render_readme_score_points_absent_keeps_baseline():
    """评分点缺省 / 空清单不新增空章节，README 文本保持逐字节兼容。"""
    manifests = [_m("delay", "软件延时")]
    baseline = render_readme("stm32", None, manifests)

    assert render_readme("stm32", None, manifests, score_points=None) == baseline
    assert render_readme("stm32", None, manifests, score_points=()) == baseline
    assert "## 评分点验收清单" not in baseline


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
