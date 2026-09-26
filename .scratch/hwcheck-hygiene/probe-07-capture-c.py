"""probe-07-capture-c.py — 临时量具：把反证 C 那一跑的**原始输出**抓下来看格式。

为什么需要它：`probe-07-red.py` 的 C 段（真浏览器）在注入态确实红了（`ℹ fail 1`、退出码 1），
但 `failed_tests()` 一行都没抓到——说明我对 node 报告的失败行格式猜错了，**不是判据没强度**。
先把原文落盘看清格式，再把解析改对（证据优先于猜测）。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from patch_bytes import encode_anchor  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
RECIPES = REPO / "library/hwcheck_recipes.json"
OUT = pathlib.Path(__file__).resolve().parent / "probe-07-capture-c.txt"
SPEC = "tests/browser/hwcheck.spec.mjs"

A_NEW = ("多实例只验第一路：工程里配了 4 路 LED 时（生成器覆写 led_instances.h，"
         "通道数会大于 1），检测程序这一趟只驱动第一路（LED_RED）——通道数不是"
         "「每一路都验过」的意思，另外几路这一趟一个动作都没有。")


def main() -> int:
    original = RECIPES.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    try:
        RECIPES.write_bytes(original.replace(
            encode_anchor(A_NEW, original), b"", 1))
        proc = subprocess.run(
            ["node", "--test", "--test-concurrency=1", SPEC],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=900)
    finally:
        RECIPES.write_bytes(original)
    body = (proc.stdout or "") + "\n---- STDERR ----\n" + (proc.stderr or "")
    OUT.write_text(
        f"# 注入式：撤掉 led × stm32 的多实例自述\n"
        f"# 命令：node --test --test-concurrency=1 {SPEC}\n"
        f"# 退出码：{proc.returncode}  前置 sha256：{digest}\n"
        f"# 复原 sha256：{hashlib.sha256(RECIPES.read_bytes()).hexdigest()}\n\n" + body,
        encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"退出码 {proc.returncode}；原文已落盘：{OUT.name}")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
