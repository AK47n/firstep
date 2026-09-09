r"""列出 tracker 里状态仍为未完成的工单（标题 + 要做什么 + 阻塞），供人工盘点。

与 `.scratch/tracker-audit/census.py` 的分工（两者不重叠，故并存）：
- census.py = **数量视角**：扫全库所有工单（含无状态行与 resolved），按 feature 打印
  各状态计数——回答「还剩多少、分布如何」，不读标题与正文。
- 本脚本 = **清单视角**：只挑未完成状态（ready-for-agent / claimed / ready-for-human /
  needs-*），逐张打印状态 + feature/文件名 + 标题 + 要做什么 + 被谁阻塞——回答
  「剩下的这些是什么、卡在谁身上」。标题与阻塞字段是 census.py 不产出的内容。

位置：2026-09-09 从 `.scratch/library-audit/` 挪入本目录——它读的是 tracker 工单，
与 library-audit 域无关。

状态行形态单源 = `.scratch/tracker-audit/ticket_status.py`（2026-09-09 在途盘点修复）：
旧版正则只认「粗体 + 全角冒号」，**漏报过两张真正开放的工单**（`code-editor-refine/08`
claimed、`code-page-vscode-overhaul/07` ready-for-agent）；现在三种形态都认。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch\tracker-audit\list_open_tickets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ticket_status import extract_status, is_open  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    for path in sorted(ROOT.glob(".scratch/*/issues/*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        state = extract_status(text)
        if not is_open(state):
            continue
        title = next(
            (line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")),
            path.name,
        )
        what = _field(text, (r"\*\*要做什么：\*\*", r"\*\*What to build:\*\*"), multiline=True)
        blocked = _field(text, (r"\*\*被谁阻塞：\*\*", r"\*\*Blocked by:\*\*"), multiline=False)
        feature = path.parent.parent.name
        print(f"--- {state:16s} {feature}/{path.name}")
        print(f"    标题：{title[:110]}")
        if what:
            print(f"    要做什么：{what[:130]}")
        if blocked:
            print(f"    阻塞：{blocked[:110]}")
    return 0


def _field(text: str, patterns: tuple[str, ...], *, multiline: bool) -> str:
    """取字段值（中文模板与英文模板两种写法都认），压平空白。

    multiline=True 取到空行（整段），False 只取该行。
    """
    import re

    tail = r"\s*(.*?)\n\n" if multiline else r"\s*(.*?)\n"
    for pattern in patterns:
        match = re.search(pattern + tail, text, re.S)
        if match:
            return " ".join(match.group(1).split())
    return ""


if __name__ == "__main__":
    sys.exit(main())
