#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工单 hwcheck-hygiene/12 的删除表：把**已被真浏览器用例替代**的源码串断言从
`tests/js/hwcheck.test.mjs` 里摘掉。

用法：

    python .scratch/hwcheck-hygiene/apply-12-migrate.py            # 干跑
    python .scratch/hwcheck-hygiene/apply-12-migrate.py --write    # 落盘

每条都点名"替它的是哪一条浏览器用例"（票尾有整张对照表）。**只删这些**：
其余源码串断言要么判的是"结构单源"（`ui` 不得手拼壳 / 不得双源定义 / 静态 import——
真浏览器看不出来，只能靠源码判据），要么只**部分**可观测（例如"生成时现象与建议都归零"，
建议那一半要 LLM 才造得出来）——那两类留在前端门禁，票尾逐条记账。

判据（脚本自己算）：每条必须命中**恰好一次**；删完总数 = 原数 − 10。
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEST = REPO / "tests" / "js" / "hwcheck.test.mjs"

# (用例标题, 替它的浏览器用例)
REMOVALS = [
    ("ui 的 id 建议不覆盖用户手填的 id（只在空 / 还是建议值时补）",
     "「我的器件」：手填过 id 就不被「名称 → id 建议」覆盖"),
    ("ui 的 id 建议也只改那一个输入框（不许整块重绘把在填的字段清掉）",
     "「我的器件」：逐字打字不被整块重绘吞掉，补 id 建议也不清空别的字段"),
    ("ui 打字期间**不整块重绘表单**（重绘 = 正在打字的输入框被换掉，字全丢）",
     "同上（同一条用例的 ① 与 ②）"),
    ("「我的器件」的行随选择集重绘（从 chip 侧取消加选后，行上按钮不许还说「已在」）",
     "「我的器件」：能选（加进这次检测…取消加选 → 行上按钮文案回退）——**既有**用例"),
    ("「我的器件」不随平台清空（件与平台无关：切平台不该把用户填的件弄丢）",
     "「我的器件」：切平台不丢正在填的表单（件与平台无关）"),
    ("结构钉：总口径那句真的被渲染出来（容器在卡片正文里 + ui 调了 fx）",
     "顶部总口径真的在页面上（未上板那句）"),
    ("ui 的空态文案把自建件也算进「哪些能复测」（否则页面在说谎）",
     "空态：串口复测那句把自建件也算进去"),
    ("ui 的说明弹窗走既有委托（捕获阶段拦，否则点说明会把器件去掉）",
     "器件卡「说明」：开弹窗，且**不**把这一件加进 / 移出这次检测"),
    ("单平台件不误导：器件挑选面按**本栏目当前平台**标记「需切换平台」",
     "单平台件在错平台上标「需切换平台」"),
    ("ui 删掉一件时把它从**这次检测的选择**里去掉（否则下次预览 400 未知模块）",
     "「我的器件」删掉一件时，它同时从这次检测的选择里去掉"),
]


def _blocks_module():
    """借 11 号单迁移脚本的掩码括号切块（**单源**：别在第三个脚本里再写一遍）。"""
    spec = importlib.util.spec_from_file_location(
        "apply_11_tests", Path(__file__).resolve().parent / "apply-11-tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BLOCKS = _blocks_module().blocks


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    text = TEST.read_bytes().decode("utf-8")
    blocks = {t: (s, e) for t, s, e in BLOCKS(text)}
    before = len(re.findall(r'(?m)^test\("', text))
    spans = []
    for title, replaced_by in REMOVALS:
        assert title in blocks, f"用例标题不在表里（改了标题？）：{title}"
        start, end = blocks[title]
        # `blocks()` 的 end 停在**回调的收尾 `}`**上（它切的是 `test("…", () => { … })` 的
        # 函数体）——整块删除还要吃掉括号与分号 `);`，不然每删一条都留一行 `);`（第一版实测：
        # 9 处残片，整份文件当场 SyntaxError）。
        tail = re.compile(r"[ \t]*\)[ \t]*;").match(text, end)
        assert tail, f"用例收尾不是 `);`（{title}）：{text[end:end + 20]!r}"
        end = tail.end()
        while text[end:end + 1] == "\n":      # 连它后面的空行一起吃掉（不留双空行）
            end += 1
        spans.append((start, end))
        print(f"  删掉：{title}\n        替它的是：{replaced_by}")
    out = text
    for start, end in sorted(spans, reverse=True):
        out = out[:start] + out[end:]
    after = len(re.findall(r'(?m)^test\("', out))
    assert after == before - len(REMOVALS), f"删完剩 {after} 条（应 {before - len(REMOVALS)}）"
    print(f"用例数：{before} → {after}（删 {len(REMOVALS)} 条）")
    if not args.write:
        print("（干跑，未落盘）")
        return 0
    TEST.write_bytes(out.encode("utf-8"))
    print(f"已写：{TEST.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
