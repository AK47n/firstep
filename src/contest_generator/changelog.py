"""更新记录：手工维护 CHANGELOG.md + git log 自动补记（webapp 薄路由的数据源）。

数据源 = 仓库根 CHANGELOG.md（GitHub 惯例位置）为主、git log 自动补记手工
文件没有的日期（2026-08-15 用户定案：更新记录要自动更新，不再等人手追加；
`docs:` 内部工单提交过滤）。手工文件仍是主数据源：`## YYYY-MM-DD` 严格日期
开新组，组内 `- ` 行是条目（可带 `HH:MM` 时间前缀），`# ` 大标题 / 说明
段落 / 空行 / 无日期组的 `- ` 行全部跳过。

格式契约（新记录插最前，日期组倒序；组内条目带 `HH:MM` 时间前缀，
按时间先后写，可省略）：

    # 更新记录

    （格式说明：`## YYYY-MM-DD` + `- HH:MM 描述`，新记录插最前面。以下为示例）

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

    `## YYYY-MM-DD`（严格 `\\d{4}-\\d{2}-\\d{2}`，行首行尾锚定）开新日期组；
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


# git log 自动补记的提交日期行：`YYYY-MM-DD HH:MM <subject>`（subprocess
# `--date=format:%Y-%m-%d %H:%M` 的确定性输出）。只在手工文件缺该日期时
# 补一组，措辞 = commit subject（用户 2026-08-15 定案：更新记录要自动更新，
# 不再等人手追加 CHANGELOG.md；`docs:` 内部工单提交过滤掉）。
_GIT_LOG_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{1,2}:\d{2}) (.+)$")


def git_changelog_groups(repo_dir: Path, branch: str = "main") -> list[dict]:
    """git log → [{date, items}]（日期倒序、组内时间正序）。

    只取 first-parent 历史（squash 合 main 后每个 PR 一个提交），过滤
    `docs:` 内部工单提交与空 subject；`git` 不可用 / 不在 git 工作树 /
    超时 → []（纯展示数据，不阻塞工具）。措辞用 commit subject——自动更新
    的代价是措辞不可控，手工 CHANGELOG.md 仍可覆盖同日期（见 merge_changelog）。
    """
    try:
        import subprocess

        completed = subprocess.run(
            [
                "git", "-C", str(repo_dir), "log", "--first-parent", branch,
                "--date=format:%Y-%m-%d %H:%M", "--pretty=format:%ad %s",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except Exception:
        return []
    if completed.returncode != 0:
        return []

    by_date: dict[str, list[dict]] = {}
    for line in completed.stdout.splitlines():
        m = _GIT_LOG_LINE_RE.match(line)
        if m is None:
            continue
        date, time, subject = m.group(1), m.group(2), m.group(3).strip()
        if not subject or subject.startswith("docs:") or subject.startswith("Merge"):
            continue
        by_date.setdefault(date, []).append({"time": time, "text": subject})

    groups: list[dict] = []
    for date in sorted(by_date, reverse=True):
        # git log 同一日期内新提交在前；更新记录按时间先后展示 → 组内反转
        groups.append({"date": date, "items": list(reversed(by_date[date]))})
    return groups


def merge_changelog(manual: list[dict], auto: list[dict]) -> list[dict]:
    """合并手工文件与 git 自动补记：手工日期组优先，git 只补手工没有的日期；
    结果按日期倒序（同日期不合并，手工组原样保留）。"""
    manual_dates = {group["date"] for group in manual}
    merged = [group for group in manual]
    for group in auto:
        if group["date"] not in manual_dates:
            merged.append(group)
    merged.sort(key=lambda group: group["date"], reverse=True)
    return merged


def load_changelog_auto(path: Path, repo_dir: Path | None = None) -> list[dict]:
    """读取 CHANGELOG.md + git log 自动补记（手工文件缺的日期才补）。

    repo_dir 为 None 或 git 不可用 → 只回手工文件（旧行为）。纯展示数据：
    任何异常都不抛，调用方无需兜底。
    """
    manual = load_changelog(path)
    if repo_dir is None:
        return manual
    try:
        auto = git_changelog_groups(repo_dir)
    except Exception:
        auto = []
    return merge_changelog(manual, auto)
