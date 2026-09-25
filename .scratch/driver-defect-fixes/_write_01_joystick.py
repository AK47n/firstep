# -*- coding: utf-8 -*-
"""工单 `driver-defect-fixes/01`：把 joystick × mspm0 配方按**修后**的驱动口径改一遍。

改什么（三处，全部只动 mspm0 那一格；stm32 侧驱动未动、配方也不动）：

  1. `read` 的两行 0-100% 读数补上「65535 = 本次没读到」——这是修后新出现的值
     （`JOYSTICK_ADC_INVALID`，工单 01 加的「本次无效」出口）；
  2. `note` 的「失败模式」那条：此前写的是「本平台有一个已知缺陷会让 X/Y 读数很可能
     恒 0」——**缺陷已修**，改成按修后口径读（0 是合法读数、65535 才是没读到）；
  3. `note` 的「本单不修的驱动缺陷」那条：改成「已修」并写清修法（判据从「50 圈自旋」
     改成时间：8 槽 × 125µs ≈ 1000µs、上限 4 倍；一圈都没采到返回哨兵值）。

判据面：`tests/test_hwcheck_recipe.py` 的扩张地板 / 读数行宽 / locals 守卫全部照跑；
本脚本只改**文本值**，不动段结构、不动 `console`、不动格数。

写法照 `.scratch/hwcheck-specialize/_write_batch_f.py`：json 往返（`ensure_ascii=False,
indent=2`）与原文件**逐字节相同**（已实测），并按原文件的换行风格写回。
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NEW_READ_X = "X 轴 0-100%（不推杆应≈50；两端接近 0 / 100；65535=没读到）"
NEW_READ_Y = "Y 轴 0-100%（不推杆应≈50；两端接近 0 / 100；65535=没读到）"

NEW_FAIL_MODE = (
    "失败模式：**读数印 65535** —— 这一路**没读到**（`JOYSTICK_ADC_INVALID`，"
    "ADC 没使能 / 转换一直不完成）；⚠ **读到 0 不是故障**——0 与 0% 都是**合法读数**"
    "（杆真的推到端点），这正是本工单修掉的那条歧义；**恒定值** —— 推杆时数字一动不动 "
    "= X/Y 那两路没接对或接到了别的脚；**上电第一遍** —— 读数抖动属正常。"
)

NEW_FIXED_DEFECT = (
    "**已修的驱动缺陷（driver-defect-fixes/01，本格读数按修后口径读）**：此前本平台的 ADC 忙等"
    "超时判据用的是**「自旋圈数」而不是时间**（50 圈寄存器轮询 ≈ 几微秒，而一次完整转换要 "
    "≈1ms）⇒ **按代码常量核算**每一轮都会在第一轮就提前返回（板上到底是不是「恒 0」"
    "**仍未上板复核**，见 recon-03 §4-D2）。现在按时间等："
    "**8 槽 × 125µs ≈ 1000µs，上限取 4 倍 = 4000µs**（槽数 / 每槽时间都取自母版 `mspm0.syscfg`），"
    "轮询步长由 `CPUCLK_FREQ` 折成 1µs；一圈都没采到时返回 **`JOYSTICK_ADC_INVALID`(65535) "
    "=「本次无效」**——**不再用 0 冒充读数**。同实例的 `adc` 模块是无超时忙等，两处口径差写在"
    "驱动注释里。顺带把三处文档对 sequence 槽数的口径统一成 syscfg 的事实（**8 槽 / endAdd=7**）。"
)


def main() -> int:
    text = RECIPES.read_text(encoding="utf-8", newline="")
    document = json.loads(text)

    cell = document["joystick"]["mspm0"]
    note = cell["note"]["lines"]

    # 断言改前形态与预期一致（防止在错的基础上改；两条 note 判据容忍"已改过一遍"）
    assert "不推杆应≈50" in cell["read"]["items"][0]["unit"], cell["read"]["items"][0]
    assert any("65535" in line or "恒 0" in line for line in note), note

    cell["read"]["items"][0]["unit"] = NEW_READ_X
    cell["read"]["items"][1]["unit"] = NEW_READ_Y
    for index, line in enumerate(note):
        if "已知缺陷会让 X/Y 读数很可能恒 0" in line or "读数印 65535" in line:
            note[index] = NEW_FAIL_MODE
        elif ("本单不修的驱动缺陷" in line and "自旋圈数" in line) or "已修的驱动缺陷" in line:
            note[index] = NEW_FIXED_DEFECT

    # stm32 那一格只做一致性核对：驱动没动，配方就不该动
    stm32_read = document["joystick"]["stm32"]["read"]["items"]
    assert "65535" not in stm32_read[0]["unit"], "stm32 侧没有哨兵值，别把 mspm0 的口径抄过去"

    newline = "\r\n" if "\r\n" in text else "\n"
    body = json.dumps(document, ensure_ascii=False, indent=2).replace("\n", newline) + newline
    RECIPES.write_text(body, encoding="utf-8", newline="")
    print("已更新 joystick × mspm0 配方（read ×2 + note ×2）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
