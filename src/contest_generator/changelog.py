"""更新记录：手工维护 CHANGELOG.md 的解析（webapp 薄路由的数据源）。

数据源是仓库根 CHANGELOG.md（GitHub 惯例位置）——用户定案：不自动生成
（git log 措辞不可控）、不前端写死（更新要动内联 HTML），想要什么写什么。
本模块只有解析与读取：`## YYYY-MM-DD` 严格日期开新组，组内 `- ` 行是条目
（可带 `HH:MM` 时间前缀），`# ` 大标题 / 说明段落 / 空行 / 无日期组的
`- ` 行全部跳过。

格式契约（新记录插最前，日期组倒序；组内条目带 `HH:MM` 时间前缀，
按时间先后写，可省略）：

    # 更新记录

    （格式说明：`## YYYY-MM-DD` + `- [HH:MM] 描述`，新记录插最前面。以下为示例）

    ## 2026-08-12
    - 17:48 新增更新记录栏目（第 8 个 tab）
    - 16:00 编译错误列表支持点击展开源码行

    ## 2026-08-11
    - ...

解析返回 `[{date, items: [{time, text}]}]` 按文件顺序。纯展示数据：文件
缺失 / 读取异常 → []（前端显示「暂无更新记录」），损坏不阻塞工具——
展示数据不走"大声失败"。
"""

from __future__ import annotations

import re
from pathlib import Path

# 严格日期：行首行尾锚定，防说明文字里的 `## ` 小节（或残缺日期）误判
_GROUP_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})$")
# 条目：可选 `HH:MM ` 时间前缀（`- ` 后必须是时间 + 空格，否则整段当文本）
_ITEM_RE = re.compile(r"^- (?:(\d{1,2}:\d{2}) )?(.+)$")


def parse_changelog(text: str) -> list[dict]:
    """按格式契约解析 CHANGELOG.md 文本 → [{date, items}]（文件顺序）。

    `## YYYY-MM-DD`（严格 `\d{4}-\d{2}-\d{2}`，行首行尾锚定）开新日期组；
    组内 `- ` 行是条目，行首 `HH:MM ` 时间前缀剥离进 {time, text}（无前缀
    time=""）；`# ` 大标题 / 说明段落 / 空行 / 无日期组时的 `- ` 行一律
    跳过。非日期 `## ` 小节不建组，其后条目仍归当前日期组。
    """
    groups: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        m = _GROUP_RE.match(line)
        if m:
            current = {"date": m.group(1), "items": []}
            groups.append(current)
            continue
        m = _ITEM_RE.match(line)
        if m and current is not None:
            current["items"].append(
                {"time": m.group(1) or "", "text": m.group(2).strip()}
            )
    return groups


def load_changelog(path: Path) -> list[dict]:
    """读取 CHANGELOG.md → 解析结果；文件缺失 / 读取 / 解析异常 → []。

    纯展示数据：损坏不阻塞工具（前端显示「暂无更新记录」），docstring
    即契约——解析异常不抛，调用方无需兜底。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        return parse_changelog(text)
    except Exception:
        return []
