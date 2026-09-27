"""工单 backlog-closeout/02 的迁移脚本：MQ 系三条 note 补齐口径（纯追加/替换，不动别的）。

做法：对 `src/contest_generator/wordlist.json` 的**原始字节**做三段精确替换
（每段都先断言唯一），写完再让 JSON 解析复核一次：

1. mq2：补「正向映射」+ 补「多路气体同选共读 MEM0 物理通道限制」那句（它正是共享 MEM0 的那件）；
2. mq135 / mq5：补「正向映射」（它们是独立 MEM4/MEM5 通道，已有对照说明，不补 MEM0 那句）；
3. 三条的预热写法从「预热（几分钟级）」统一成「预热 3-5 分钟」（与另外六件同一句）。

用法：`python .scratch/backlog-closeout/apply-02-mq-notes.py`
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORDLIST = ROOT / "src" / "contest_generator" / "wordlist.json"

PREHEAT_OLD = "模块上电必须预热（几分钟级）否则输出不准"
PREHEAT_NEW = "模块上电必须预热 3-5 分钟否则输出不准"

EDITS: tuple[tuple[str, str, str], ...] = (
    (
        "mq2 正向映射 + MEM0 共读限制",
        "mq2_read_percent 出 0-100% 相对浓度，与 adc 模块共享 ADC12_0 MEM0、默认 PA24——同选时经引脚绑定消解",
        "mq2_read_percent 出 0-100% 相对浓度——**正向映射**（浓度越高 ADC 值越高），"
        "与 adc 模块共享 ADC12_0 MEM0、默认 PA24——同选时经引脚绑定消解；"
        "**多路气体同选共读 MEM0 物理通道限制**：每路只能接一个器件到 PA24",
    ),
    (
        "mq135 正向映射",
        "mq135_read_percent 出 0-100% 相对浓度，**独立 ADC12_0 MEM4 通道、默认 PB20**",
        "mq135_read_percent 出 0-100% 相对浓度——**正向映射**（浓度越高 ADC 值越高），"
        "**独立 ADC12_0 MEM4 通道、默认 PB20**",
    ),
    (
        "mq5 正向映射",
        "mq5_read_percent 出 0-100% 相对浓度，**独立 ADC12_0 MEM5 通道、默认 PB24**",
        "mq5_read_percent 出 0-100% 相对浓度——**正向映射**（浓度越高 ADC 值越高），"
        "**独立 ADC12_0 MEM5 通道、默认 PB24**",
    ),
)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raw = WORDLIST.read_bytes()
    text = raw.decode("utf-8")
    before = len(raw)
    for name, old, new in EDITS:
        assert text.count(old) == 1, f"{name}: 锚点命中 {text.count(old)} 次（应恰好 1 次）"
        text = text.replace(old, new, 1)
    assert text.count(PREHEAT_OLD) == 3, (
        f"预热旧写法命中 {text.count(PREHEAT_OLD)} 次（应恰好 3 次：mq2/mq135/mq5）"
    )
    text = text.replace(PREHEAT_OLD, PREHEAT_NEW)
    json.loads(text)  # 解析复核：改完仍是合法 JSON
    WORDLIST.write_bytes(text.encode("utf-8"))
    after = len(text.encode("utf-8"))
    print(f"三处补齐 + 预热统一完成：{before:,} B → {after:,} B（+{after - before} B）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
