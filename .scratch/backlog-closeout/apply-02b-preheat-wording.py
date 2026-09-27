"""工单 backlog-closeout/02 的第二遍迁移：把「预热 3-5 分钟」退回**有据**的措辞。

为什么改：评审自读盘复核发现——MQ 九件的手册页里**没有**任何时长数字
（`mq-2.md:42` 只写「使用之前必须加热一段时间，否则其输出的电阻和电压不准确」；
`mq-135.md` / `mq-5.md` 连加热都没提）。全仓唯一写「3-5 分钟」的原文是 **ms1100**
（`ms1100.md:46`），而它与 mq3/4/6/7/8/9 同批入库——**疑串台**。
所以九件统一成手册支持的措辞（不再给数字）。

用法：`python .scratch/backlog-closeout/apply-02b-preheat-wording.py`
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORDLIST = ROOT / "src" / "contest_generator" / "wordlist.json"

OLD = "模块上电必须预热 3-5 分钟否则输出不准"
NEW = "模块上电必须预热（手册只说「加热一段时间」，一般几分钟）否则输出不准"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raw = WORDLIST.read_bytes()
    text = raw.decode("utf-8")
    hits = text.count(OLD)
    assert hits == 9, f"锚点命中 {hits} 次（应恰好 9 次：MQ 九件）"
    text = text.replace(OLD, NEW)
    json.loads(text)
    WORDLIST.write_bytes(text.encode("utf-8"))
    print(f"预热措辞退回有据版本：{len(raw):,} B → {len(text.encode('utf-8')):,} B（9 处）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
