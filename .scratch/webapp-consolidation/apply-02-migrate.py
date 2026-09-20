# -*- coding: utf-8 -*-
"""工单 webapp-consolidation/02 的机械改写：20 处三件套改用 `_llm_run` 缝。

只吃**逐字形态**（缩进 8 空格的块 + 固定的调用串），不猜不模糊匹配；每改一处都
打印出来供人工复核。视觉那 5 处（`vision-describe` ×4 + `vision-qa`）已在跑本脚本
之前手工改完（它们的局部变量也叫 `collector`，先改免得被这里的规则误伤）。

用法：`python .scratch/webapp-consolidation/apply-02-migrate.py [--write]`
（缺省 dry-run，只打印计划与命中数）
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "src" / "contest_generator" / "webapp.py"


def _string_spans(source: str) -> list[tuple[int, int]]:
    """源码里所有字符串 / 注释 token 的 (start, end) 字符区间。

    为什么需要：规则也会命中**文档字符串里**的示例代码（本单的 `LLMRun` docstring
    就写着 `_llm(context, budget, collector)`）——那些是散文，不是调用点，不能改。
    """
    spans: list[tuple[int, int]] = []
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in (tokenize.STRING, tokenize.COMMENT):
            start = offsets[token.start[0] - 1] + token.start[1]
            end = offsets[token.end[0] - 1] + token.end[1]
            spans.append((start, end))
    return spans


def _inside(offset: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in spans)

# (说明, 正则, 替换) —— 逐条都是"逐字形态"，不含模糊匹配
RULES: tuple[tuple[str, str, str], ...] = (
    (
        "三件套块 → 缝",
        r'        budget = RetryBudget\(\)\n'
        r'        collector = create_llm_observation_collector\("([^"]+)"\)\n',
        '        llm_run = _llm_run(context, "\\1")\n',
    ),
    (
        "取客户端（局部变量形态）",
        r"llm = _llm\(context, budget, collector\)",
        "llm = llm_run.llm()",
    ),
    (
        "取客户端（内联预算形态）",
        r"_llm\(context, RetryBudget\(\), collector\)",
        "llm_run.llm()",
    ),
    (
        "取客户端（其余调用点）",
        r"_llm\(context, budget, collector\)",
        "llm_run.llm()",
    ),
    (
        "遥测挂钩",
        r"with bind_llm_telemetry\(collector, emit\.progress\):",
        "with bind_llm_telemetry(llm_run.collector, emit.progress):",
    ),
    (
        "观测结算",
        r"context\.recent_llm_workflows\.add_completed\(collector\)",
        "llm_run.settle()",
    ),
    (
        "同步端点：裸收集器 → 缝",
        r'        collector = create_llm_observation_collector\("([^"]+)"\)\n',
        '        llm_run = _llm_run(context, "\\1")\n',
    ),
)


def main() -> int:
    write = "--write" in sys.argv
    source = WEBAPP.read_text(encoding="utf-8")
    total = 0
    for label, pattern, replacement in RULES:
        spans = _string_spans(source)
        hits = [
            match for match in re.finditer(pattern, source)
            if not _inside(match.start(), spans)
        ]
        skipped = len(re.findall(pattern, source)) - len(hits)
        print(f"{label}: {len(hits)} 处" + (f"（跳过 {skipped} 处：在字符串/注释里）" if skipped else ""))
        for match in hits:
            line = source[: match.start()].count("\n") + 1
            before = match.group(0).replace("\n", " ⏎ ")
            after = (
                replacement.replace("\\1", match.group(1))
                if match.groups() else replacement
            )
            print(f"  L{line}: {before}  →  {after}")
        total += len(hits)
        # 逐处替换（保序：字符串里的那些原样留着）
        out: list[str] = []
        cursor = 0
        for match in hits:
            out.append(source[cursor:match.start()])
            out.append(
                replacement.replace("\\1", match.group(1))
                if match.groups() else replacement
            )
            cursor = match.end()
        out.append(source[cursor:])
        source = "".join(out)
    print(f"合计改写 {total} 处")
    leftover = {
        "create_llm_observation_collector": len(
            re.findall(r"create_llm_observation_collector\(", source)
        ),
        "RetryBudget": len(re.findall(r"RetryBudget\(", source)),
        "add_completed": len(re.findall(r"add_completed\(", source)),
        "裸 collector 变量": len(re.findall(r"(?<![\w.])collector(?![\w.])", source)),
    }
    print(f"改写后残留：{leftover}")
    for name in ("collector", "RetryBudget", "create_llm_observation_collector"):
        for match in re.finditer(rf"(?<![\w.]){name}(?![\w.])", source):
            line = source[: match.start()].count("\n") + 1
            print(f"  残留 L{line}: {source.splitlines()[line - 1].strip()[:90]}")
    if write:
        WEBAPP.write_text(source, encoding="utf-8")
        print("已写入", WEBAPP)
    else:
        print("dry-run（加 --write 落盘）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
