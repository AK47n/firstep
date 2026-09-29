r"""收口对拍（工单 03）：本轮读的**上一轮那三支探针**，与上一轮的落盘基线比。

`probe-00` / `probe-01` 在上一轮**有落盘读数**（`probe-00-after-09.txt` /
`probe-01-scope-after-09.txt`），所以能比 **sha256（逐字节）**；
`probe-04` 上一轮**没有落盘**（当时是"跑一次看表"），只能比**数**——这一条如实印出来，
别把它读成"逐字节相同"（03 单双轴评审点过这条口径）。

只读，不改任何东西。
"""

from __future__ import annotations

import hashlib
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SITEWIDE = ROOT / ".scratch" / "ui-density-sitewide"

PAIRS = [
    ("after-03-probe-00-body.txt", "probe-00-after-09.txt", "探针 00（家底普查）"),
    ("after-03-probe-01-body.txt", "probe-01-scope-after-09.txt", "探针 01（字号/间距分布）"),
]


def main() -> None:
    for mine, base, label in PAIRS:
        a, b = HERE / mine, SITEWIDE / base
        if not a.exists():
            print(f"{label}：本轮读数缺 {mine}")
            continue
        if not b.exists():
            print(f"{label}：上一轮没有落盘基线（{base} 不在）——只能比数")
            continue
        ha = hashlib.sha256(a.read_bytes()).hexdigest()
        hb = hashlib.sha256(b.read_bytes()).hexdigest()
        verdict = "逐字节相同 ✅" if ha == hb else "**不同 ❌**"
        print(f"{label}：{verdict}  sha256 {ha[:12]}… / {hb[:12]}…")

    p4 = HERE / "after-03-probe-04.txt"
    if p4.exists():
        text = p4.read_text(encoding="utf-8")
        zeros = len(re.findall(r"\b0\s+0\s+(\d+)\s*$", text, re.M))
        total = re.search(r"合计\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", text)
        print("探针 04（逐作用域三口径）：上一轮**没有落盘基线**，只能比数——")
        print(f"  · 逐作用域行 {zeros} 行（v1.4.0 记的是 14 个作用域）")
        if total:
            print(f"  · 合计 = 规则 {total.group(1)} / 裸字号 {total.group(2)} / "
                  f"裸令牌间距 {total.group(3)} / 整圈完整框 {total.group(4)}"
                  f"（v1.4.0 记的是 1593 / 0 / 0 / 115）")


if __name__ == "__main__":
    main()
