r"""工单状态行提取（唯一出处）——census.py 与 list_open_tickets.py 共用。

**为什么需要它**：历史工单的状态行有三种形态共存，早期脚本只认「粗体 + 全角冒号」
（`**Status：**`），把 301 个用半角冒号 / 标题式写法的文件误算成「无状态行」，
并**漏报过两张真正开放的工单**（`code-editor-refine/08` claimed、
`code-page-vscode-overhaul/07` ready-for-agent，2026-09-09 在途盘点发现）。
形态单源收敛在此，两个脚本不再各写一份正则。

形态优先级（取首个命中）：
1. 粗体行：`**Status:** resolved` / `**状态：** resolved`（半角/全角冒号都认）
2. 普通行 / 引用行 / 列表行：`Status: resolved`、`> 状态：resolved`、`- Status: resolved`
3. 标题式：`## 状态` 空行后跟 `resolved`

值本身不做合法性判决——`STANDARD_STATES` 只用于让 census 把非标准值单独成桶
（`已实施` / `resolved：2026-08-23` 这类历史遗留不与标准五值混为一谈）。

用法：$env:PYTHONIOENCODING='utf-8'; python .scratch\tracker-audit\census.py
"""

from __future__ import annotations

import re

# 标准状态值（含 tracker 五值与流程内两态）——之外的值为历史遗留形态。
STANDARD_STATES = frozenset(
    {
        "needs-triage",
        "needs-info",
        "ready-for-agent",
        "ready-for-human",
        "wontfix",
        "claimed",
        "resolved",
    }
)

# 未完成状态前缀（list_open_tickets.py 用）：命中即视为「未翻牌」。
OPEN_PREFIXES = ("ready-for-agent", "claimed", "ready-for-human", "needs-")

# 状态行形态单源。顺序 = 优先级；值取到第一个非空白、非括号字符序列。
_PATTERNS = (
    re.compile(r"\*\*(?:Status|状态)\s*[:：]\*\*\s*([^\s（(]+)"),
    re.compile(r"^\s*[-*>]?\s*(?:Status|状态)\s*[:：]\s*([^\s（(]+)", re.M),
    re.compile(r"^#+\s*(?:Status|状态)\s*$\s*\n+\s*([^\s（(]+)", re.M),
)

# 先在前 N 行找（状态行按约定在文件顶部），找不到再退到全文——避免正文引用误配。
_HEAD_LINES = 40


def extract_status(text: str) -> str | None:
    """返回状态行里的第一个值；三种形态都认，找不到返回 None。"""
    head = "\n".join(text.splitlines()[:_HEAD_LINES])
    for pattern in _PATTERNS:
        match = pattern.search(head)
        if match:
            return match.group(1)
    for pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def is_open(state: str | None) -> bool:
    """未完成状态（供 list_open_tickets.py 用）。"""
    return bool(state) and state.startswith(OPEN_PREFIXES)
