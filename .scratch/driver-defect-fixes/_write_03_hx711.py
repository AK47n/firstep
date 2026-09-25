# -*- coding: utf-8 -*-
"""工单 `driver-defect-fixes/03`：把 hx711 两格配方按**修后**的驱动口径改一遍。

改什么：

  * **两格**的 `probe` 判据：从「读到一个非 0 的数」改成「读到的值**不是哨兵值**」
    （`HX711_TIMEOUT_SENTINEL`）——0 现在是合法读数（空秤零点），不能再当失败标记；
  * **stm32 格**的 `probe` 去掉 `delay_ms(500)` 那个拐杖（驱动自己会等满一个转换周期），
    `include.headers` 里的 `ml_delay.h` 随之摘掉（本格不再有 `delay_ms` 调用）；
  * **mspm0 格**的 `prereq` 去掉 `delay_ms(500)`，只留 `hx711_init()`；
  * **两格** note 的四处按修后口径重写：探头含义 / 就绪窗口（已修）/ FAIL 排查 /
    「0 是歧义词」（已修）；
  * **mspm0 格**那条「接线坑：默认 SCK = PB5 / DT = PB0」是**从 stm32 格抄错的**（本平台是
    PA28/PA31，上一条已经写对）——同批删掉，避免学生在同一格读到两套引脚。

判据面：`tests/test_hwcheck_recipe.py` 的扩张地板 / 读数行宽 / locals 守卫照跑；
本脚本只改文本值与两处调用清单，不动段结构、不动格数、不动 `console`。

写法照 `.scratch/hwcheck-specialize/_write_batch_f.py`：json 往返（`ensure_ascii=False,
indent=2`）与原文件逐字节相同，并按原文件的换行风格写回。
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROBE_STM32 = ["(raw = hx711_read_raw(), (raw != HX711_TIMEOUT_SENTINEL) ? 1 : 0)"]
PROBE_MSPM0 = ["(raw = hx711_read_raw(), (raw != HX711_TIMEOUT_SENTINEL) ? 1 : 0)"]

READ_RAW_UNIT = "24bit 偏移值（≈8388608 = 零点；**不是克数**；**4294967295 = 没读到**）"
READ_SIGNED_UNIT = "有符号计数（加砝码应单调变化；与上面那行是同一个采样）"

NOTE_MEANING = (
    "**探头到底证明了什么**：探头 = **`hx711_read_raw()` 读回一个不是哨兵值的数**，含义是"
    "「**DT 数据就绪通路是活的 + 一次采样真的出来了**」。它**不证明重量准**——克换算要先"
    "**去皮**再按每只秤的传感器曲线标定（`HX711_GAP_VALUE`，默认 207.00 只是立创的示例值），"
    "所以本页**故意不显示克数**。"
)
NOTE_TIMING = (
    "⚠ **本件最要紧的一条（driver-defect-fixes/03 已修）**：驱动等 DT 就绪的窗口是 "
    "**2 个转换周期 = 200ms**（模块默认 **10SPS ⇒ 100ms/次**）。此前那个窗口写死成 **20ms**"
    "（2000×10us），而 `hx711_init()` **内部就先读一次**（空秤去皮）消费掉一个采样 ⇒ "
    "**init 之后紧接着读必然超时**。现在驱动自己会等满一个完整转换周期，**读数段可以直接再读**、"
    "不必调用方掐时间；本格仍然把那次采样存进 `raw` 给读数两行复用（一次检测里两行同源，也少等一次）。"
)
NOTE_FAIL_CHECK = (
    "判 FAIL 时按返回码排查：**`raw == HX711_TIMEOUT_SENTINEL`（页面印 4294967295）** = 两个转换周期"
    "（200ms）内 DT 一直没拉低，按嫌疑从大到小——① 没接 / 线断 / SCK·DT 插反；② **刚上电 400ms 内**"
    "（模块自己也要启动）；③ 模块没供电，或 RATE 脚接错（拉高走 80SPS 是另一个档）。"
    "⚠ 探头判 FAIL 会 **return**，后面的读数就不打印了。"
)
NOTE_AMBIGUITY = (
    "**「0」不再是失败标记了**（driver-defect-fixes/03）：`count ^ 0x800000` 在空秤零点"
    "（count == 0x800000）时**也返 0**——所以 **0 是合法读数**（秤正好在零点），失败改由 "
    "**`HX711_TIMEOUT_SENTINEL` = 4294967295** 表示（它落在 24 位合法域之外）。"
    "换句话说：**读到 0 = 秤在零点；读到 4294967295 = 没读到**，两者从此分得开。"
)
NOTE_FIXED = (
    "**已修的驱动缺陷（driver-defect-fixes/03）**：① 就绪窗口从写死的 20ms 改成**按转换周期算**"
    "（`1000 / 10SPS = 100ms`，取 2 倍 = 200ms）；② 「init / tare 是消费一次采样的读却没有节流」"
    "这条由**驱动自己承担**（等满一个周期，不再靠调用方补延时）；③ 「0 是歧义词」有了出口——"
    "超时返回哨兵值。"
)
NOTE_MSPM0_SHAPE = (
    "**平台差异 / 接线**：引脚 = SysConfig 实例 HX711：**SCK = PA28 / DT = PA31**（DT 内部上拉；"
    "SCK 空闲低、DT 空闲高）。⚠ **PA28 / PA31 与 `jy61p` / IMU601 / `sht30` / FINGERPRINT 的默认脚"
    "重叠**（低频采集池共用这两根线）——同一个物理脚只能接一件器件，同选经引脚绑定消解。"
    "⚠ 模块头注释 `hx711.h` 里出现过 PB24/PB8，那是**历史默认**，以 syscfg / manifest 的 "
    "**PA28/PA31** 为准。⚠ 本平台（mspm0）**母版没有 .h**：`delay_ms` 出现在 `init` / `probe` / "
    "`read` 的**任何一处都是构建期红**，唯一放行它的是 **`prereq`**——本格因此把 `hx711_init()` "
    "放在 `prereq`（它一次就等满一个转换周期，**不再需要 `delay_ms(500)` 那个拐杖**）。"
)


def rewrite_note(lines: list[str], *, mspm0: bool) -> list[str]:
    """按「这一行在讲什么」逐条替换（判据是内容，不是下标）。"""
    out: list[str] = []
    for line in lines:
        if line.startswith("**探头到底证明了什么**"):
            out.append(NOTE_MEANING)
        elif line.startswith("⚠ **本件最硬的一条"):
            out.append(NOTE_TIMING)
        elif line.startswith("判 FAIL 时按返回码排查"):
            out.append(NOTE_FAIL_CHECK)
        elif line.startswith("**0 是个歧义词**"):
            out.append(NOTE_AMBIGUITY)
        elif line.startswith("**平台差异 / 接线（本格的形状"):
            out.append(NOTE_MSPM0_SHAPE)
        elif line.startswith("接线坑：默认 **SCK = PB5"):
            if mspm0:
                continue  # mspm0 格这条是从 stm32 抄错的（本平台是 PA28/PA31），删掉
            out.append(line)  # stm32 格这条是本平台事实，原样保留
        elif line.startswith("**本单不修的驱动缺陷") and "20ms 超时" in line:
            out.append(NOTE_FIXED)
        else:
            out.append(line)
    return out


def main() -> int:
    text = RECIPES.read_text(encoding="utf-8", newline="")
    document = json.loads(text)

    stm32 = document["hx711"]["stm32"]
    mspm0 = document["hx711"]["mspm0"]

    assert stm32["probe"]["calls"] == [
        "(delay_ms(500), raw = hx711_read_raw(), (raw != 0) ? 1 : 0)"
    ], stm32["probe"]
    assert mspm0["prereq"]["calls"] == ["hx711_init()", "delay_ms(500)"], mspm0["prereq"]
    assert mspm0["probe"]["calls"] == ["(raw = hx711_read_raw(), (raw != 0) ? 1 : 0)"], mspm0["probe"]
    assert "接线坑：默认 **SCK = PB5" in "\n".join(mspm0["note"]["lines"])

    stm32["probe"]["calls"] = PROBE_STM32
    stm32["include"]["headers"] = [h for h in stm32["include"]["headers"] if h != "ml_delay.h"]
    mspm0["probe"]["calls"] = PROBE_MSPM0
    mspm0["prereq"]["calls"] = ["hx711_init()"]

    for cell, is_mspm0 in ((stm32, False), (mspm0, True)):
        items = cell["read"]["items"]
        assert [i["expression"] for i in items] == ["raw", "(int)raw - 8388608"]
        items[0]["unit"] = READ_RAW_UNIT
        items[1]["unit"] = READ_SIGNED_UNIT
        cell["note"]["lines"] = rewrite_note(cell["note"]["lines"], mspm0=is_mspm0)

    # 修后核对：两格都不该再有「非 0 判据」与「不修的缺陷」口径；
    # **调用清单里**（init / prereq / probe）也不该再出现 delay_ms（note 的散文里提到
    # 「不再需要那个拐杖」是如实的，不算）
    for name, cell in (("stm32", stm32), ("mspm0", mspm0)):
        blob = json.dumps(cell, ensure_ascii=False)
        assert "(raw != 0)" not in blob, name
        assert "本单不修的驱动缺陷" not in blob, name
        assert "HX711_TIMEOUT_SENTINEL" in blob, name
        calls = json.dumps(
            {key: cell.get(key) for key in ("init", "prereq", "probe")}, ensure_ascii=False
        )
        assert "delay_ms" not in calls, f"{name} 的调用清单里还有 delay_ms：{calls}"

    newline = "\r\n" if "\r\n" in text else "\n"
    body = json.dumps(document, ensure_ascii=False, indent=2).replace("\n", newline) + newline
    RECIPES.write_text(body, encoding="utf-8", newline="")
    print("已更新 hx711 两格配方（probe / prereq / include + 两格 note 四处 + 删一条抄错的接线坑）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
