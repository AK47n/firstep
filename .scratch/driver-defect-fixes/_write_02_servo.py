# -*- coding: utf-8 -*-
"""工单 `driver-defect-fixes/02`：把 servo 两格配方按**修后**的驱动口径改一遍。

改什么：

  1. `servo × mspm0` 的 `prereq`：动作序列从 **0° → 90° → 0°（三段）** 补成
     **0° → 90° → 180° → 0°（四段）**——修好周期量程之后，180° 已经能正常输出，
     当年那句「先别扫到 180°」的限制随修复撤掉（工单 02 的验收项之一）。
  2. `servo × mspm0` 的 note：删掉「**故意不扫 180°**」那句（并改掉「本格只扫三段」的说明）。
  3. 两格 note 里那条「正常范围参考」：段数说明从「stm32 四段 / mspm0 三段」改成
     **两平台都是四段**（这条事实是跨平台共用的，两格一起改）。
  4. `servo × mspm0` 的 note：把「本单不修的驱动缺陷（D1：周期超 16 位量程…）」那条
     改成「**已修**」，写清修法（母版 `clockPrescale = 16` ⇒ 计数时钟 2MHz ⇒ 20ms = 40000
     计数；驱动侧编译期 `#error` 守量程；LOAD 写 period - 1 与 stm32 的 ARR 对偶）。
  5. stm32 那一格的 `include` / `init` / `probe` / `read` / `console` **一字不动**
     （那一侧驱动没动）。

判据面：`tests/test_hwcheck_recipe.py` 的扩张地板 / 读数行宽 / locals 守卫照跑；
本脚本只改文本值，不动段结构与格数。

写法照 `.scratch/hwcheck-specialize/_write_batch_f.py`：json 往返（`ensure_ascii=False,
indent=2`）与原文件逐字节相同，并按原文件的换行风格写回。
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NEW_MSPM0_PREREQ = [
    "servo_init(0, 0)", "delay_ms(600)",
    "servo_set_angle(0, 90)", "delay_ms(600)",
    "servo_set_angle(0, 180)", "delay_ms(600)",
    "servo_set_angle(0, 0)",
]

NEW_MSPM0_PRACTICE = (
    "判「有没有坏」的实操：复测一遍，**盯舵机臂**——① 完全不动：先查**信号线接在 PA7 上**、"
    "再查**舵机的独立供电**（**别从板子 3V3 供**）；② 抖动 / 只往一个方向跑：多半是供电不足；"
    "③ 转到某个角度就卡住：机械限位或舵机本身坏了。⚠ 本格扫的是 **0° → 90° → 180° → 0° 四段**"
    "（驱动修好后大角度也能正常输出，见下面的「已修的驱动缺陷」），别把「某个角度不动」"
    "读成舵机坏之前先确认那不是机械限位。"
)

NEW_RANGE = (
    "正常范围参考：**0° / 90° / 180° 对应脉宽 0.5ms / 1.5ms / 2.5ms**（50Hz、20ms 周期）。"
    "想确认「它真的在动」：复测时**盯舵机臂**——按本格的扫描顺序，应看到舵机臂**一段一段地"
    "转到指定角度**（stm32 与 mspm0 都是 **0°→90°→180°→…** 四段），而不是纹丝不动或只抖一下。"
)

NEW_FIXED_D1 = (
    "**已修的驱动缺陷（driver-defect-fixes/02，本格扫到 180° 就是它的验收）**：本平台此前"
    "`servo_period()` 算出的周期（`SERVO_PWM_INST_CLK_FREQ / 50` = **640000**）**超过 16 位"
    "定时器量程**（SERVO_PWM = TIMG8；SysConfig 元数据原文「TIMG = 16-bit counter + 8-bit "
    "prescaler」，只有 TIMG12 是 32 位），而 `DL_Timer_setLoadValue` **不钳位** ⇒ LOAD 被截成 "
    "50176、周期 ≈1.57ms（≈638Hz）、≈96° 以上比较值超过周期、输出恒高。现在把母版 "
    "`SERVO_PWM.clockPrescale` 配成 **16**（计数时钟 2MHz）⇒ 20ms = **40000 计数 < 65535**，"
    "运行时写 `LOAD = period - 1`（EDGE_ALIGN 语义，与 stm32 的 `ARR = 1000000/fre - 1` 对偶）；"
    "驱动侧另有**编译期 `#error`** 把量程钉住（分频被改小就编不过，不允许静默钳位——钳位会把 "
    "50Hz 变成别的频率）。"
)


def main() -> int:
    text = RECIPES.read_text(encoding="utf-8", newline="")
    document = json.loads(text)

    mspm0 = document["servo"]["mspm0"]
    stm32 = document["servo"]["stm32"]

    assert mspm0["prereq"]["calls"] == [
        "servo_init(0, 0)", "delay_ms(600)", "servo_set_angle(0, 90)",
        "delay_ms(600)", "servo_set_angle(0, 0)",
    ], mspm0["prereq"]
    assert stm32["probe"]["calls"][4] == "servo_set_angle(0, 180)", stm32["probe"]

    mspm0["prereq"]["calls"] = NEW_MSPM0_PREREQ
    for cell in (mspm0, stm32):
        lines = cell["note"]["lines"]
        for index, line in enumerate(lines):
            if "只扫 0° → 90° → 0°" in line:
                lines[index] = NEW_MSPM0_PRACTICE
            elif line.startswith("正常范围参考："):
                assert "mspm0 是 0°→90°→0° 三段" in line, line[:60]
                lines[index] = NEW_RANGE
            elif "本单不修的驱动缺陷" in line and "SERVO_PWM_INST_CLK_FREQ / 50" in line:
                lines[index] = NEW_FIXED_D1

    # 修后核对：mspm0 那一格不该再出现「不扫 180°」的口径
    joined = "\n".join(mspm0["note"]["lines"]) + "\n" + "\n".join(mspm0["prereq"]["calls"])
    assert "不扫 180" not in joined, joined
    assert "servo_set_angle(0, 180)" in joined

    newline = "\r\n" if "\r\n" in text else "\n"
    body = json.dumps(document, ensure_ascii=False, indent=2).replace("\n", newline) + newline
    RECIPES.write_text(body, encoding="utf-8", newline="")
    print("已更新 servo 两格配方（mspm0 prereq 四段 + 两格 note 三处）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
