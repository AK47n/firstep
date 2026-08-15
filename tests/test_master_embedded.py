"""工单 02 真实库数据守卫：stm32 电机链路补录素材的值与结构。

测试直接读仓库内真实 library/（磁盘目录即数据库、随软件仓库走），防素材
漂移：pin_config.h 宏值 = 21F 原值、motor_stm32.c 无硬编码引脚、manifest
条目与磁盘文件一致、pid 闭环文件在位、key 维持 mspm0 only（missing 警告
保留回归）、uvprojx IncludePath 补了工程根。功能行为（生成 / 骨架）的
用例在 test_generator.py / test_skeleton.py（假库），这里只钉真实数据。
"""

from pathlib import Path

from contest_generator.manifest import ModuleManifest

LIBRARY_DIR = Path(__file__).resolve().parents[1] / "library"


def _read(rel: str) -> str:
    return (LIBRARY_DIR / rel).read_text(encoding="utf-8", errors="replace")


def test_pin_config_h_keeps_21f_pin_values():
    """引脚宏值 = 21F 原值：PWM TIM2 CH1/CH2（1000Hz）、方向 PA6/PA7/PB0/PB1、
    编码器 EXTI PA2/PA4 + 方向 PA3/PA5。"""
    text = _read("masters/stm32/pin_config.h")
    for literal in (
        "TIM2_CH1",
        "TIM2_CH2",
        "MOTOR_PWM_FREQ",
        "1000",
        "GPIO_A",
        "Pin_6",
        "Pin_7",
        "GPIO_B",
        "Pin_0",
        "Pin_1",
        "EXTI_PA2",
        "EXTI_PA4",
        "Pin_3",
        "Pin_5",
    ):
        assert literal in text, literal


def test_motor_stm32_source_has_no_hardcoded_pins():
    """motor_stm32.c 无硬编码引脚字面量（引脚只出现在 pin_config.h）；
    编码器计数中断随模块（ADR 0012 起按 MOTOR_A/B_ENC_LINE 条件编译 7 个
    handler，照 mspm0 key 的 GROUP1_IRQHandler 先例）。"""
    text = _read("modules/motor/code/motor_stm32.c")
    for literal in (
        "GPIO_A",
        "GPIO_B",
        "Pin_0",
        "Pin_1",
        "Pin_3",
        "Pin_5",
        "Pin_6",
        "Pin_7",
        "TIM2_CH1",
        "TIM2_CH2",
        "EXTI_PA2",
        "EXTI_PA4",
    ):
        assert literal not in text, literal
    assert "EXTI2_IRQHandler" in text and "EXTI4_IRQHandler" in text
    assert "MOTOR_" in text  # 只引用 pin_config.h 宏


def test_motor_manifest_stm32_entry_files_exist():
    """motor stm32 条目文件在位且 verified；依赖只声明双平台齐全者
    （delay/oled/led_beep stm32 空条目=母版内嵌，不产生文件，选 motor 无
    missing 警告的数据前提）；mspm0-only 小车栈项（huidu/imu_uart/
    ntb_time/key）不得声明——声明会拖 stm32 missing，保持手动同选。"""
    manifest = ModuleManifest.load(LIBRARY_DIR / "modules" / "motor")
    entry = manifest.platforms["stm32"]
    assert entry.verified
    for rel in entry.files:
        assert (LIBRARY_DIR / "modules" / "motor" / rel).is_file(), rel
    assert set(manifest.dependencies) == {"delay", "oled", "led_beep"}
    for mspm0_only in ("huidu", "imu_uart", "ntb_time", "key"):
        assert mspm0_only not in manifest.dependencies


def test_pid_manifest_stm32_entry_verified_and_scheduling_stripped():
    """pid stm32 条目 verified 且文件在位；pid_isr.c 已随 10ms 调度剥离
    （工单 module-universalization/03：调度归骨架，模块不再自持 ISR）。"""
    manifest = ModuleManifest.load(LIBRARY_DIR / "modules" / "pid")
    entry = manifest.platforms["stm32"]
    assert entry.verified
    assert "code/pid_isr.c" not in entry.files
    assert not (LIBRARY_DIR / "modules" / "pid" / "code" / "pid_isr.c").exists()
    for rel in entry.files:
        assert (LIBRARY_DIR / "modules" / "pid" / rel).is_file(), rel
    assert manifest.dependencies == ("motor",)  # 决策层依赖已移出


def test_pid_source_includes_stm32_motor_header():
    """pid.c 引 motor_stm32.h 而非 motor.h（模块 code/motor.h 是 mspm0 版，
    含 ti_msp_dl_config.h，stm32 上解析不到）。"""
    pid_c = _read("modules/pid/code/pid.c")
    assert '#include "motor_stm32.h"' in pid_c
    assert '#include "motor.h"' not in pid_c


def test_key_manifest_stays_mspm0_only():
    """key 不补录 stm32（21F 无独立按键素材，PB5 药物检测属工程级逻辑）：
    平台检查 missing 警告保留（回归）。"""
    manifest = ModuleManifest.load(LIBRARY_DIR / "modules" / "key")
    assert "stm32" not in manifest.platforms


def test_key_selection_on_stm32_reports_missing_warning():
    """key 在 stm32 上仍报 missing（不补录，警告保留回归，验收项）。"""
    from contest_generator.selection import WARNING_MISSING, resolve_selection

    resolved = resolve_selection(LIBRARY_DIR / "modules", "stm32", ["key"])
    assert any(w.slug == "key" and w.kind == WARNING_MISSING for w in resolved.warnings)


def test_motor_selection_on_stm32_has_no_missing_warning():
    """选 motor 不选 pid stm32：无任何平台警告（stm32 条目在 + 依赖清空）。"""
    from contest_generator.selection import resolve_selection

    resolved = resolve_selection(LIBRARY_DIR / "modules", "stm32", ["motor"])
    assert resolved.warnings == ()


def test_motor_pid_selection_on_stm32_has_no_missing_warning():
    """选 motor+pid stm32：pid 依赖展开含 motor，全链无 missing（unverified
    是工单 01 的翻 true 范围，这里只看 missing）。"""
    from contest_generator.selection import WARNING_MISSING, resolve_selection

    resolved = resolve_selection(LIBRARY_DIR / "modules", "stm32", ["pid"])
    slugs = [m.slug for m in resolved.manifests]
    assert "motor" in slugs  # 依赖方向 pid → motor
    assert all(w.kind != WARNING_MISSING for w in resolved.warnings)


def test_stm32_master_uvprojx_include_path_has_project_root():
    """uvprojx IncludePath 补工程根（pin_config.h 在工程根，模块 include 可解析）。"""
    text = _read("masters/stm32/user/Project.uvprojx")
    assert "IncludePath>..\\ml_libs;..\\sys;..<" in text
