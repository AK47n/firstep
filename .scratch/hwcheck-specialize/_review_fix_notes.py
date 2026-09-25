# -*- coding: utf-8 -*-
"""评审整改：修掉本批 note 里**平台串台**与**学生看不到的失败签名**（工单 07 双轴评审 (c) 5/6）。

逐条回源码核过：

1. `ads1115 × mspm0` 的「判 FAIL 排查」行是从 stm32 那份复制的（"本平台默认 PA6/PA7"），
   而 mspm0 的引脚是 **PA16/PA17**（`ads1115.h` 头注释 + manifest）。这一行**两平台共用**，
   所以改法不是改数字，而是把"引脚"整块交给各平台自己的「平台差异」那条：
   跨平台共用的那句只说总线层面的排查。
2. `ds18b20 × mspm0` 的「接线坑」行整行抄自 stm32（PB1 与 MOTOR_B_DIR2）——同一格上面
   三行本来就写着 **PA7**，自相矛盾，会把 mspm0 学生指向错脚。按 mspm0 的事实重写。
3. `ds18b20` 的失败签名原写「悬空 → 读回 -0.0625℃」，但读数两行都是 `(int)t` **向零截断**
   ⇒ 学生实际看到 **0.0℃**，与同段「恒 0.0℃ = 读位全 0」撞在一起。改成如实说明截断。

用法：`py -3 .scratch/hwcheck-specialize/_review_fix_notes.py`
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OLD_FAIL = (
    "**2** → 查 SCL/SDA 有没有被别的模块拉住（本平台默认 PA6/PA7，与库内另外十来件"
    "共挂同一软 I2C 总线，地址互异是合法的，但**同一根线上有件把 SDA 一直拉低**就全挂）。"
)
NEW_FAIL = (
    "**2** → 查 SCL/SDA 有没有被别的模块拉住（**这两根脚在本平台是哪一个见本格"
    "「平台差异」那条**；本件与库内另外十来件共挂同一软 I2C 总线，地址互异是合法的，"
    "但**同一根线上有件把 SDA 一直拉低**就全挂）。"
)

OLD_PIN_MSPM0 = "接线坑：默认 DATA = **PB1**，与 `motor` 的 MOTOR_B_DIR2 默认脚重叠"
NEW_PIN_MSPM0 = (
    "接线坑：默认 DATA = **PA7**（**不是 stm32 那根 PB1**），与 `servo` 的 SERVO_PWM / "
    "`motor` 的 BIN2 / `rc522` 的 CS 默认脚重叠"
)

OLD_SIGN = (
    "失败签名特别具体（照这个对号入座）：**悬空 / 器件缺席** → 读回寄存器 `0xFFFF` → "
    "换算成 **-0.0625℃**；"
)
NEW_SIGN = (
    "失败签名特别具体（照这个对号入座）：**悬空 / 器件缺席** → 读回寄存器 `0xFFFF` → "
    "换算成 **-0.0625℃**，而下面那两行读数都是 `(int)` **向零截断**的 ⇒ **屏幕上是 0**"
    "（所以「读到 0」**不能**当成「器件在、只是冷」，它更像**器件不在**）；"
)

old_text = RECIPES.read_text(encoding="utf-8")
new_text = old_text

# 1) ads1115：**两份都换**（这是跨平台共用句，两边写的是同一个错事实）
assert new_text.count(OLD_FAIL) == 2, f"ads1115 的排查句应有两处，实测 {new_text.count(OLD_FAIL)}"
new_text = new_text.replace(OLD_FAIL, NEW_FAIL)

# 2) ds18b20 × mspm0：只换第二处（第一处是 stm32 的，事实正确）
assert new_text.count(OLD_PIN_MSPM0) == 2, (
    f"ds18b20 的接线坑行应有两处，实测 {new_text.count(OLD_PIN_MSPM0)}")
first = new_text.index(OLD_PIN_MSPM0)
head, tail = new_text[:first + len(OLD_PIN_MSPM0)], new_text[first + len(OLD_PIN_MSPM0):]
tail = tail.replace(OLD_PIN_MSPM0, NEW_PIN_MSPM0, 1)
new_text = head + tail

# 3) ds18b20：两平台共用那段失败签名
assert new_text.count(OLD_SIGN) == 2, f"失败签名段应有两处，实测 {new_text.count(OLD_SIGN)}"
new_text = new_text.replace(OLD_SIGN, NEW_SIGN)

RECIPES.write_text(new_text, encoding="utf-8", newline="")
print("✓ 三处整改已写入；"
      f"行数 {len(old_text.splitlines())} → {len(new_text.splitlines())}")
