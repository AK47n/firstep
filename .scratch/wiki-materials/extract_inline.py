# -*- coding: utf-8 -*-
"""从 wiki 手册提取正文围栏代码 + 机械修复抓取破坏（工单 wiki-materials 用）。

抓取脚本把正文代码保留了行结构，但把 token 间空格规范化并拆开了
`0xNN`（成为 `0x` + 空格 + `NN`，还可能在运算符后）。本脚本从正文
` c /* ... */ ` 围栏提取代码块，并做最小机械修复：

1. `0x` 后跟空格再跟十六进制数字 -> 合并为 `0xNN`（如 `0x ff` -> `0xff`、
   `&0x ff` -> `&0xff`、`( 0x 80 >> i)` -> `(0x80 >> i)`）
2. 行首行尾空白裁剪（围栏行原始带前后空格）

用法：python .scratch/wiki-materials/extract_inline.py <手册md> <输出目录>
"""
import re
import sys
from pathlib import Path

# 正文围栏：以 " c " 开头的一行（围栏标记），内容到第二个 " */ " 或 " c " 结束。
# 观察：正文里每条代码 = 一行 " c " + 若干代码行（每行原文前后有空格）+
# 一行（可能是下一个 " c " 或文章段落）。我们按 " c " 行分段。
CODE_START_RE = re.compile(r"^ {0,6}c (/\*.*)$", re.M | re.S)
BLOCK_RE = re.compile(r"(?ms)^ {0,6}c (.+?)(?=^ {0,6}c |^[^ ]|\Z)")

# 围栏尾随的说明句（抓取把「在文件…编写如下代码。」之类句子并进了围栏）
TRAIL_SENTENCE_RE = re.compile(r"^(在文件|接下来|移植完成|选择好引脚|到这里|上电效果|运行效果|直接替换|注意：)")

def repair(code: str) -> str:
    lines = []
    for line in code.splitlines():
        line = line.rstrip()
        # 丢弃行号栏（抓取产物：每个围栏后的纯数字行 1..N 是代码行号 gutter）
        if line.strip().isdigit():
            continue
        # 修复 token 破坏：0x 空格 hex -> 0xhex
        line = re.sub(r"\b0x\s+([0-9a-fA-F]+)\b", r"0x\1", line)
        lines.append(line)
    return "\n".join(lines).strip("\n")

def extract(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    blocks = []
    for m in BLOCK_RE.finditer(text):
        code = m.group(1)
        # 截断尾随说明句：从第一个「在文件…」行起丢弃（该行及其后）
        cut = len(code.splitlines())
        for i, line in enumerate(code.splitlines()):
            if TRAIL_SENTENCE_RE.search(line.strip()):
                cut = i
                break
        blocks.append(repair("\n".join(code.splitlines()[:cut])))
    return blocks

def main() -> None:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    blocks = extract(src)
    total = 0
    for i, code in enumerate(blocks, 1):
        fn = out / f"{src.stem.replace('--', '-')}-inline{i}.c"
        fn.write_text(code, encoding="utf-8")
        total += len(code.splitlines())
        print(f"inline{i}: {len(code.splitlines())} 行 {len(code)} 字符 -> {fn.name}")
    print(f"共 {len(blocks)} 个围栏代码块，合计 {total} 行")

if __name__ == "__main__":
    main()
