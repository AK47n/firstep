# -*- coding: utf-8 -*-
"""工单 `driver-defect-fixes/03`：按**双轴评审**改 hx711 两格的文案（第二轮）。

三处（都是评审抓出来的、有证据的）：

  1. **印出来的不是 4294967295 而是 -1**：渲染出口是
     `hwcheck.py` 的 `static void hwcheck_report_int(int value)`，而两格 `locals` 是
     `uint32_t raw` ⇒ 哨兵 0xFFFFFFFF 过 int 形参会印成 **-1**
     （量具：`.scratch/driver-defect-fixes/probe-03-printed-values.py` 打印了真产物里的
     调用点与函数签名）。文案是上板判读的唯一指引，必须按**实际印出来的**写。
  2. **冷启动那条如实提示被删过头**：窗口现在 200ms，而 HX711 上电后第一个样本要 ~400ms
     ⇒ 冷启动那一次 `hx711_init()` **仍可能超时**（那时零点不存，`s_tare` 保持原值）。
     这条要写回去（旧版写的是"第一遍可能读到 0"，理由不对但现象是真的）。
  3. **命令台说明残留旧口径**：「每次读相隔≥100ms」是修复前"让调用方自己节流"的说法，
     现在驱动自己会等 ⇒ 改写成"读到 -1 = 本次没读到"。

写法照 `.scratch/hwcheck-specialize/_write_batch_f.py`：json 往返与原文件逐字节同形。
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

READ_RAW_UNIT = (
    "24bit 偏移值（≈8388608 = 零点；**不是克数**；**-1 = 没读到**）"
)
CONSOLE_DESC = "HX711 称重：重读原始计数（空秤≈8388608；读到 -1 = 本次没读到）"

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
    "⚠ **冷启动那一次仍可能超时**：HX711 上电后第一个样本要 ~400ms（比窗口长），所以刚上电就调 "
    "`hx711_init()` 时它可能没读到（那时**零点不存**，克换算暂不可用——驱动不会把哨兵当零点）。"
    "**敲一次复测字符再看**：第二遍读就在窗口内了。（这就是旧版那句「第一遍可能失败」的真相，"
    "只是当年的理由写错了。）"
)
NOTE_FAIL_CHECK = (
    "判 FAIL 时按返回码排查：**`raw` 印成 `-1`** = 两个转换周期（200ms）内 DT 一直没拉低"
    "（哨兵值 0xFFFFFFFF 按有符号整型印出来就是 -1）。按嫌疑从大到小——① 没接 / 线断 / "
    "SCK·DT 插反；② **刚上电 400ms 内**（模块自己也要启动，见上面那条）；③ 模块没供电，"
    "或 RATE 脚接错（拉高走 80SPS 是另一个档）。⚠ 探头判 FAIL 会 **return**，后面的读数就不打印了。"
)
NOTE_AMBIGUITY = (
    "**「0」不再是失败标记了**（driver-defect-fixes/03）：`count ^ 0x800000` 在空秤零点"
    "（count == 0x800000）时**也返 0**——所以 **0 是合法读数**（秤正好在零点），失败改由哨兵值 "
    "**0xFFFFFFFF** 表示（它落在 24 位合法域之外；页面按有符号整型印成 **-1**）。"
    "换句话说：**读到 0 = 秤在零点；读到 -1 = 没读到**，两者从此分得开。"
)
NOTE_FIXED = (
    "**已修的驱动缺陷（driver-defect-fixes/03）**：① 就绪窗口从写死的 20ms 改成**按转换周期算**"
    "（`1000 / 10SPS = 100ms`，取 2 倍 = 200ms）；② 「init / tare 是消费一次采样的读却没有节流」"
    "这条由**驱动自己承担**（等满一个周期，不再靠调用方补延时），并且**去皮读失败时零点原样不动**"
    "（绝不把哨兵当零点存进去——那会让克数变成 raw + 1 的天文数字）；③ 「0 是歧义词」有了出口"
    "——超时返回哨兵值。"
)
NOTE_MSPM0_SHAPE = (
    "**平台差异 / 接线**：引脚 = SysConfig 实例 HX711：**SCK = PA28 / DT = PA31**（DT 内部上拉；"
    "SCK 空闲低、DT 空闲高）。⚠ **PA28 / PA31 与 `jy61p` / IMU601 / `sht30` / FINGERPRINT 的默认脚"
    "重叠**（低频采集池共用这两根线）——同一个物理脚只能接一件器件，同选经引脚绑定消解。"
    "⚠ 模块头注释 `hx711.h` 里出现过 PB24/PB8，那是**历史默认**，以 syscfg / manifest 的 "
    "**PA28/PA31** 为准。⚠ 本平台（mspm0）**母版没有 .h**：`delay_ms` 出现在 `init` / `probe` / "
    "`read` 的**任何一处都是构建期红**，唯一放行它的是 **`prereq`**——本格因此把 `hx711_init()` "
    "放在 `prereq`（它一次就等满一个转换周期，**不再需要 `delay_ms(500)` 那个拐杖**；"
    "冷启动那一次仍可能没读到，见上面那条）。"
)


def rewrite(lines: list[str], *, mspm0: bool) -> list[str]:
    out: list[str] = []
    for line in lines:
        if line.startswith("**探头到底证明了什么**"):
            out.append(NOTE_MEANING)
        elif line.startswith("⚠ **本件最要紧的一条"):
            out.append(NOTE_TIMING)
        elif line.startswith("判 FAIL 时按返回码排查"):
            out.append(NOTE_FAIL_CHECK)
        elif line.startswith("**「0」不再是失败标记了**"):
            out.append(NOTE_AMBIGUITY)
        elif line.startswith("**平台差异 / 接线**：引脚 = SysConfig"):
            out.append(NOTE_MSPM0_SHAPE)
        elif line.startswith("**已修的驱动缺陷"):
            out.append(NOTE_FIXED)
        else:
            out.append(line)
    return out


def main() -> int:
    text = RECIPES.read_text(encoding="utf-8", newline="")
    document = json.loads(text)
    for name in ("stm32", "mspm0"):
        cell = document["hx711"][name]
        assert cell["read"]["items"][0]["expression"] == "raw"
        cell["read"]["items"][0]["unit"] = READ_RAW_UNIT
        cell["console"]["description"] = CONSOLE_DESC
        cell["note"]["lines"] = rewrite(cell["note"]["lines"], mspm0=(name == "mspm0"))
        blob = json.dumps(cell, ensure_ascii=False)
        assert "4294967295" not in blob, name
        assert "-1 = 没读到" in blob or "印成 `-1`" in blob, name
        assert "冷启动" in blob, name
    newline = "\r\n" if "\r\n" in text else "\n"
    body = json.dumps(document, ensure_ascii=False, indent=2).replace("\n", newline) + newline
    RECIPES.write_text(body, encoding="utf-8", newline="")
    print("已按评审修 hx711 两格文案（印出 -1 / 冷启动如实提示 / 命令台说明）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
