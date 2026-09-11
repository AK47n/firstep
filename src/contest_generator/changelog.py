"""更新记录：CHANGELOG.md 的解析 + git log 自动补录（webapp 薄路由的数据源）。

数据源是仓库根 CHANGELOG.md（GitHub 惯例位置）。最初定案手工维护（git log
措辞不可控），后改为自动：post-commit 钩子调用 update_changelog()，把上次
已录入提交之后的新提交自动整理成条目追加进 CHANGELOG.md 并提交。

CHANGELOG.md 是「自动草稿区」（开发视角、全量提交史）；用户前台展示的是
「定稿区」VERSIONS.md——每个版本一条 `## vX.Y.Z (YYYY-MM-DD)` 区块，组内
3~6 条用户视角要点（解析见 parse_versions / load_versions）。发版时把草稿
归纳成要点写进 VERSIONS.md 顶部（详见仓库根 VERSIONS.md 说明段）。

文件头部有一行机器标记（HTML 注释，渲染不可见）：
    <!-- changelog-auto: last-commit=<sha> -->
记录上次已录入的提交 SHA。没有标记时按文件内最新日期时间回退。

解析规则（展示契约）：
`## YYYY-MM-DD` 严格日期开新组，组内 `- ` 行是条目（可带 `HH:MM` 时间
前缀），`# ` 大标题 / 说明段落 / 空行 / 无日期组的 `- ` 行全部跳过。
解析返回 `[{date, items: [{time, text}]}]` 按文件顺序。

自动补录规则（尽力而为，绝不抛）：
- 只补非合并提交，跳过 docs: / chore: / test: 与 Merge 提交；
- 跳过写库 CRUD 机器提交（lib: add/update/delete ... 的固定模板）；
- 条目文本 = 提交主题去常规类型前缀与尾部 (#NN)；
- 日期组倒序、组内按时间先后；同 (时间, 文本) 去重。

纯展示数据：文件缺失 / 读取异常 → []（前端显示「暂无更新记录」），损坏
不阻塞工具——展示数据不走"大声失败"；自动补录同样不阻塞提交。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# 严格日期：行首行尾锚定，防说明文字里的 `## ` 小节（或残缺日期）误判
_GROUP_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})$")
# 条目：可选 `HH:MM ` 时间前缀（`- ` 后必须是时间 + 空格，否则整段当文本）
_ITEM_RE = re.compile(r"^- (?:(\d{1,2}:\d{2}) )?(.+)$")
# 机器标记：记录上次已录入提交 SHA（HTML 注释，渲染不可见）
_MARKER_RE = re.compile(r"^<!-- changelog-auto: last-commit=([0-9a-fA-F]+) -->$")
# 常规类型前缀（条目展示时剥掉，与手工条目风格一致）
_TYPE_PREFIX_RE = re.compile(r"^[a-z]+: ", re.ASCII)
# 尾部 PR 引用（#93 等）
_PR_REF_RE = re.compile(r"\s*\(#\d+\)$")
# 版本头：`## vX.Y.Z (YYYY-MM-DD)`（ASCII 括号、日期补零；版本号严格
# 主.次.补丁 三段，组 1 = 带 v 前缀的版本串，直接作展示徽章文本）
_VERSION_HEADER_RE = re.compile(
    r"^## (v[0-9]+\.[0-9]+\.[0-9]+) \(([0-9]{4}-[0-9]{2}-[0-9]{2})\)$"
)
# 任意二级标题：非版本的 `## ` 行是分区边界（重置当前块——残缺版本头不会把
# 后续条目误挂到上一版本）
_SECTION_RE = re.compile(r"^## ")
# 版本条目：`- 标签：文本`（标签 ∈ 主题 / 新增 / 改进 / 修复 / 性能）
_VERSION_ITEM_RE = re.compile(r"^- ([^：:]+)[：:]\s*(.*)$")
_VERSION_SUMMARY = "主题"
_VERSION_KINDS = ("新增", "改进", "修复", "性能")
_VERSION_KIND_OTHER = "其他"  # 无标签 / 未知标签行的兜底标签（整行保留，不静默丢）
# HTML 注释状态（VERSIONS.md 用 `<!-- … -->` 包格式示例——注释内的
# `## vX.Y.Z` / `- ` 行不得误入解析结果）
_COMMENT_START = "<!--"
_COMMENT_END = "-->"
# 自动补录跳过的提交前缀（工单管理 / 机器自提交噪声）
_SKIP_PREFIXES = ("docs:", "chore:", "test:")
# 写库 CRUD 机器提交固定模板（库管理动作不是工具改进，不进更新记录）
_ROUTINE_LIB_RE = re.compile(
    r"^lib: (?:"
    r"add module |update module description |delete module |"
    r"update platform identity |add platform files |remove platform files |"
    r"add reference |delete reference |update reference |archive reference |"
    r"import master |delete master |"
    r"confirm topics|delete topic |update topic |"
    r"赛题条目补图注"
    r")"
)

_GIT_TIMEOUT_SECONDS = 60


# ---------------------------------------------------------------------------
# 展示侧：解析（与手工时代契约完全一致）
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 版本更新记录（定稿区 VERSIONS.md）：用户视角版本要点（工单 version-changelog/02）
# ---------------------------------------------------------------------------


def parse_versions(text: str) -> list[dict]:
    """按格式契约解析 VERSIONS.md 文本 → [{version, date, summary, items}]。

    `## vX.Y.Z (YYYY-MM-DD)`（ASCII 括号、严格补零日期、主.次.补丁三段）开
    新版块；组内 `- 标签：文本`（标签 ∈ 新增/改进/修复/性能）进 items，
    `- 主题：文本` 进 summary（不占条目）；无标签 / 未知标签的行 kind=「其他」
    且整行文本保留（不静默丢内容）。`# ` 大标题 / HTML 注释（含多行注释内的
    `## v` / `- ` 示例行）/ 说明段跳过；任何非版本的 `## ` 行是分区边界
    （重置当前块——残缺版本头不会把后续条目误挂到上一版本）。
    """
    versions: list[dict] = []
    current: dict | None = None
    in_comment = False
    for line in text.splitlines():
        if in_comment:
            if _COMMENT_END in line:
                in_comment = False
            continue
        if _COMMENT_START in line:
            # 整行 + 后续区间都是注释；`<!-- … -->` 同行闭合只跳本行
            if _COMMENT_END not in line:
                in_comment = True
            continue
        m = _VERSION_HEADER_RE.match(line)
        if m:
            current = {
                "version": m.group(1),
                "date": m.group(2),
                "summary": "",
                "items": [],
            }
            versions.append(current)
            continue
        if _SECTION_RE.match(line):
            current = None
            continue
        if current is None or not line.startswith("- "):
            continue
        m = _VERSION_ITEM_RE.match(line)
        if m:
            label, rest = m.group(1).strip(), m.group(2).strip()
            if label == _VERSION_SUMMARY:
                current["summary"] = rest
            elif label in _VERSION_KINDS:
                current["items"].append({"kind": label, "text": rest})
            else:
                # 未知标签整行保留（kind=其他），防「更新：xxx」这类漏网被静默丢掉
                current["items"].append(
                    {"kind": _VERSION_KIND_OTHER, "text": line[2:].strip()}
                )
        else:
            rest = line[2:].strip()
            if rest:
                current["items"].append({"kind": _VERSION_KIND_OTHER, "text": rest})
    return versions


def load_versions(path: Path) -> list[dict]:
    """读取 VERSIONS.md → 解析结果；文件缺失 / 读取 / 解析异常 → []。

    与 load_changelog 同风格：纯展示数据，损坏不阻塞工具（前端显示空态），
    解析异常不抛，调用方无需兜底。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        return parse_versions(text)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 自动补录侧：git log → CHANGELOG.md
# ---------------------------------------------------------------------------


def update_changelog(path: Path, repo: Path) -> bool:
    """把 git log 里的新提交自动补进 CHANGELOG.md；返回是否写入。

    path 是 CHANGELOG.md 路径，repo 是 git 工作树根。调用时机：post-commit
    钩子（提交后自动补录并提交），也可手动 `python -m contest_generator.
    changelog`。尽力而为：git 不可用 / 文件缺失 / 解析失败都静默跳过，
    绝不抛——更新记录是展示数据，不阻塞提交。
    """
    text = _read_text(path)
    groups = parse_changelog(text)
    marker_sha = _marker_sha(text)
    head_sha = _git_head_sha(repo)

    if marker_sha:
        commits = _git_log_commits(repo, since_sha=marker_sha)
    else:
        since_dt = _newest_datetime(groups)
        commits = _git_log_commits(repo, since_dt=since_dt) if since_dt else []

    display = [c for c in commits if _is_displayable(c["subject"])]
    if not display:
        return False

    groups = _merge_commits(groups, display)
    header = _split_header(text)[0]
    newest_sha = head_sha or commits[0]["sha"]
    header = _upsert_marker(header, newest_sha)
    new_text = _compose(header, groups)
    if new_text == text:
        return False
    try:
        path.write_text(new_text, encoding="utf-8")
    except OSError:
        return False
    return True


def _is_displayable(subject: str) -> bool:
    """提交主题是否进更新记录：跳过 merge / 工单噪声 / 写库 CRUD 机器提交。

    先清洗前导空白与 UTF-8 BOM（工单 commit-subject-bom/01）：PS 5.1 的
    `Out-File -Encoding utf8` 写的提交信息文件带 BOM，`git commit -F` 会把它
    带进主题，而 `git log --format=%s` 取出的主题以 `\\ufeff` 开头——不洗的话
    `startswith` 判不出 `docs:` / `chore:` / `test:` / `merge`，机器提交就被当成
    用户可见条目补录进 CHANGELOG（定稿区 `VERSIONS.md` 的上游被污染）。
    只吃前导噪声，不做别的规范化。
    """
    subject = subject.lstrip("\ufeff \t")
    if subject.lower().startswith(("merge", *_SKIP_PREFIXES)):
        return False
    if _ROUTINE_LIB_RE.match(subject):
        return False
    return True


def _clean_subject(subject: str) -> str:
    """提交主题 → 条目文本：去类型前缀与尾部 (#NN)，去首尾空白。"""
    subject = subject.strip()
    subject = _PR_REF_RE.sub("", subject)
    subject = _TYPE_PREFIX_RE.sub("", subject, count=1)
    return subject.strip()


def _merge_commits(groups: list[dict], commits: list[dict]) -> list[dict]:
    """新提交并入现有分组：日期组倒序、组内按时间先后、同 (时间, 文本) 去重。"""
    by_date = {g["date"]: g for g in groups}
    for c in commits:
        text = _clean_subject(c["subject"])
        if not text:
            continue
        group = by_date.setdefault(c["date"], {"date": c["date"], "items": []})
        item = {"time": c["time"], "text": text}
        if item not in group["items"]:
            group["items"].append(item)
    merged = sorted(by_date.values(), key=lambda g: g["date"], reverse=True)
    for group in merged:
        group["items"].sort(key=lambda item: _minutes(item["time"]) if item["time"] else -1)
    return merged


# ---------------------------------------------------------------------------
# 文本 / 标记 / 渲染
# ---------------------------------------------------------------------------


def _read_text(path: Path) -> str:
    """读取 CHANGELOG.md；缺失 / 解码失败 → ''（补录从头开始）。"""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _marker_sha(text: str) -> str | None:
    """取文件头部机器标记记录的 SHA；无标记返回 None。"""
    for line in text.splitlines():
        m = _MARKER_RE.match(line)
        if m:
            return m.group(1)
    return None


def _split_header(text: str) -> tuple[str, str]:
    """拆成（首个日期组之前的一切, 首个日期组及其后）。无日期组 → (text, '')。"""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if _GROUP_RE.match(line):
            return "\n".join(lines[:i]), "\n".join(lines[i:])
    return text.rstrip(), ""


def _upsert_marker(header: str, sha: str | None) -> str:
    """头部插入 / 替换机器标记；sha 为 None 时原样返回。"""
    if sha is None:
        return header
    marker = f"<!-- changelog-auto: last-commit={sha} -->"
    lines = header.splitlines()
    for i, line in enumerate(lines):
        if _MARKER_RE.match(line):
            lines[i] = marker
            return "\n".join(lines)
    return marker + "\n" + header if header else marker


def _render_groups(groups: list[dict]) -> str:
    """分组渲染为 markdown（与解析契约对偶：日期组倒序、组内时间先后）。"""
    blocks: list[str] = []
    for group in groups:
        lines = [f"## {group['date']}"]
        for item in group["items"]:
            if item["time"]:
                lines.append(f"- {item['time']} {item['text']}")
            else:
                lines.append(f"- {item['text']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _compose(header: str, groups: list[dict]) -> str:
    """头部 + 分组拼回完整文件文本（末尾带换行）。"""
    body = _render_groups(groups)
    if header:
        return header.rstrip() + "\n\n" + body + "\n"
    return body + "\n"


def _newest_datetime(groups: list[dict]) -> str | None:
    """文件内最新日期时间（YYYY-MM-DD HH:MM），供无标记时 --since 回退；无分组 → None。"""
    if not groups:
        return None
    latest = max(g["date"] for g in groups)
    times = [item["time"] for g in groups if g["date"] == latest for item in g["items"]]
    best = "00:00"
    for time in times:
        if time and _minutes(time) > _minutes(best):
            best = time
    return f"{latest} {best}"


def _minutes(time: str) -> int:
    """HH:MM → 分钟数（排序用；格式已由解析 / git 保证）。"""
    h, m = time.split(":")
    return int(h) * 60 + int(m)


# ---------------------------------------------------------------------------
# git 原语
# ---------------------------------------------------------------------------


def _git_log_commits(
    repo: Path,
    since_sha: str | None = None,
    since_dt: str | None = None,
) -> list[dict]:
    """git log → [{sha, date, time, subject}]（新在前，文件顺序）。

    since_sha 优先：`<sha>..HEAD`；无 sha 用 `--since=<YYYY-MM-DD HH:MM>`；
    两者都无拉全量。git 不可用 / 非零退出 → []（补录尽力而为）。
    """
    cmd = [
        "git",
        "log",
        "--no-merges",
        "--pretty=format:%H%x09%ad%x09%s",
        "--date=format:%Y-%m-%d %H:%M",
    ]
    if since_sha:
        cmd.append(f"{since_sha}..HEAD")
    elif since_dt:
        cmd.append(f"--since={since_dt}")
    result = _run_git(cmd, repo)
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return []
    commits: list[dict] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        sha, dt, subject = parts
        date_str, _, time_str = dt.strip().partition(" ")
        if not sha or not date_str or not time_str:
            continue
        commits.append(
            {
                "sha": sha.strip(),
                "date": date_str,
                "time": time_str,
                "subject": subject.strip(),
            }
        )
    return commits


def _git_head_sha(repo: Path) -> str | None:
    """当前 HEAD SHA；git 不可用返回 None。"""
    result = _run_git(["git", "rev-parse", "HEAD"], repo)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _run_git(
    args: list[str], cwd: Path
) -> subprocess.CompletedProcess[str] | None:
    """运行 git 命令；执行失败（git 不可用 / 超时）返回 None。"""
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


if __name__ == "__main__":
    _root = Path(__file__).resolve().parents[2]
    _changed = update_changelog(_root / "CHANGELOG.md", _root)
    print("CHANGELOG updated" if _changed else "CHANGELOG up-to-date")
