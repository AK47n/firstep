# -*- coding: utf-8 -*-
"""素材批次质量扫描：70 篇手册 md 的可读性断言（wiki-md-repair/02）。

每篇检查：
- 无 \u200b 零宽字符；
- 无纯数字行（行号 gutter 残留）；
- 无「孤立 token 行」（#include / double / int / void / char 等独占一行）；
- 有 `## ` 章节标题（正文结构存在）；
- 围栏数 = 元数据「代码块：N 个」；
- 围栏行数 > 0 且行内含空格/n 或注释样（粗查：围栏主体平均值长度 > 12）。

退出码：0 = 全过；1 = 有失败（打印清单）；2 = 目录缺失。
运行：python .scratch/wiki-materials/scan_quality.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"

# 与旧抓取缺陷对应的「孤立 token 行」形态。
# 注意：else / #endif / #else 单行是合法 C（K&R 风格 / 预处理），return;/break; 也合法，
# 都不算；这里只保留「绝不会单独成行的残缺 token」（#include 无头文件名、
# 类型无标识符、if/for/while 无条件，且行尾无后续内容）。
_TOKEN_LINE_RE = re.compile(
    r"^\s*(?:#\s*(?:include|define|pragma|if|ifdef|ifndef)\b"
    r"|(?:double|int|void|char|unsigned|float|long|short|struct|if|for|while|switch|case)\s*\(?)\s*$",
)

_FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)

# prose 路径行号泄漏（旧抓取缺陷经新转换器复现的特征：空格连接的递增数字序列）
_NUMBER_RUN_RE = re.compile(r"^\d{1,3}(?: \d{1,3}){2,}")


def scan_one(md: str) -> list[str]:
    bad: list[str] = []
    if "\u200b" in md:
        bad.append("含零宽字符 \\u200b")
    digits = [l for l in md.splitlines() if l.strip().isdigit()]
    if digits:
        bad.append(f"行号残留纯数字行（如 {digits[0].strip()!r}）")
    num_runs = [l for l in md.splitlines() if _NUMBER_RUN_RE.match(l)]
    if num_runs:
        bad.append(f"行号序列泄漏进正文（如 {num_runs[0].strip()[:30]!r}）")
    tokens = [l for l in md.splitlines() if _TOKEN_LINE_RE.match(l) and "```" not in l]
    if tokens:
        bad.append(f"孤立 token 行（如 {tokens[0].strip()!r}）")
    if "## " not in md:
        bad.append("无 ## 章节标题")
    h1 = re.search(r"^# (.+)$", md, re.M)
    if h1 is None:
        bad.append("无 # 首页标题")
    elif not re.search(r"[\u4e00-\u9fff]", h1.group(1)):
        bad.append(f"首页标题非中文（{h1.group(1)[:30]!r}），用户难懂")
    fences = md.count("```") // 2
    m = re.search(r"- 代码块：(\d+) 个", md)
    declared = int(m.group(1)) if m else -1
    if declared < 0:
        bad.append("缺少「代码块：N 个」元数据")
    elif fences != declared:
        bad.append(f"围栏数 {fences} ≠ 元数据 {declared}")
    if fences == 0:
        bad.append("无代码围栏（可能整页无代码，需人工确认）")
    # 围栏首行抽样：代码行不应是一个词的 token（长度 1 且无空格）。
    # 排除纯括号行（{ }）与预处理 #ifdef/#endif 单行（合法短行）后求平均。
    for fm in re.finditer(r"^```[A-Za-z0-9_+\-.#]*\n([\s\S]*?)\n?^```", md, re.M):
        body = fm.group(1)
        lines = [l for l in body.splitlines()
                 if l.strip() and re.fullmatch(r"\s*[{};,]\s*", l) is None
                 and not re.match(r"^\s*#\s*(ifdef|ifndef|endif|else)\b", l)]
        if not lines:
            continue
        avg = sum(len(l) for l in lines) / len(lines)
        if avg < 10:
            bad.append(f"围栏疑似 token 逐行（平均行长 {avg:.1f}）")
    return bad


def main() -> int:
    if not BATCH.is_dir():
        print(f"批次目录缺失：{BATCH}")
        return 2
    files = sorted(BATCH.glob("*.md"))
    fails = {}
    total_bad = 0
    for f in files:
        if f.name in ("模块索引.md", "网盘索引.md"):
            continue
        text = f.read_text(encoding="utf-8")
        bad = scan_one(text)
        if bad:
            fails[f.name] = bad
            for b in bad:
                print(f"  [FAIL] {f.name}: {b}")
            total_bad += len(bad)
    num_pages = len(files) - 2
    print(f"扫描 {num_pages} 篇手册：{num_pages - len(fails)} 篇通过，{len(fails)} 篇有问题（{total_bad} 项）")
    if len(files) != 72:
        print(f"  [提示] 批次内 md 文件数 = {len(files)}（应为 72 = 70 页 + 2 索引）")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
