"""motor 两平台 API 对偶（module-functionalize/02）：stm32 补统一 API。

motor_set_duty / motor_set_direction / motor_encoder_read 与 mspm0 同名同义；
旧 API（motorA_duty/motorB_duty/encoder_init/extern 变量）保留兼容。
"""

from pathlib import Path

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MOTOR_DIR = LIBRARY_ROOT / "modules" / "motor"


def _read(rel: str) -> str:
    return (MOTOR_DIR / rel).read_text(encoding="utf-8", errors="replace")


def test_motor_stm32_header_declares_uniform_api():
    h = _read("code/motor_stm32.h")
    for fn in ("motor_set_duty", "motor_set_direction", "motor_encoder_read"):
        assert fn in h


def test_motor_stm32_source_implements_uniform_api_and_keeps_old_api():
    c = _read("code/motor_stm32.c")
    for fn in (
        "void motor_set_duty(",
        "void motor_set_direction(",
        "void motor_encoder_read(",
        "void motorA_duty(",  # 旧 API 保留
        "void motorB_duty(",
        "void encoder_init(",
    ):
        assert fn in c
    # 方向映射：stm32 旧语义 0=正转/1=反转 → 统一 1=正转/2=反转
    assert "direction == 1) ? 0 : 1" in c
    assert "motorA_dir = dir" in c and "motorB_dir = dir" in c


def test_motor_stm32_encoder_read_clears_counts():
    c = _read("code/motor_stm32.c")
    assert "Encoder_count1" in c and "Encoder_count2" in c
    assert "Encoder_count1 = 0" in c and "Encoder_count2 = 0" in c
