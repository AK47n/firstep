"""仓库文档语言门禁：工单 / spec / CHANGELOG / VERSIONS 条目必须中文。

背景：llm-observability-dashboard 的工单与 08-18 的 CHANGELOG 记录曾整段英文
（直接后果：更新记录展示英文）。约定：仓库面向用户/代理的文档一律中文
（技术术语可保留英文）；commit message 由 .githooks/commit-msg 拦截英文。
本测试是第二道防线（换机器忘配 hooksPath / --no-verify 时仍能抓到）。
VERSIONS.md（版本更新记录定稿区）为面向用户展示的文档，同样受此守门。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _cjk_count(text: str) -> int:
    return len(_CJK_RE.findall(text))


def _version_entry_lines(text: str) -> list[str]:
    """取 VERSIONS.md 的真实条目行（`- ` 开头），跳过 HTML 注释区间。

    注释（`<!-- … -->`）是格式示例的载体——区间内的 `- 示例` 行不是真实
    条目；条目行内允许有注释（格式契约未禁），只剥 `<!--` 起的尾部再取文本。
    """
    entries: list[str] = []
    in_comment = False
    for line in text.splitlines():
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if "<!--" in line and "-->" not in line:
            in_comment = True  # 多行注释开区间：其后行全是注释
            continue
        if line.startswith("- "):
            entries.append(line[2:].split("<!--", 1)[0].strip())
    return entries


def test_scratch_tickets_and_specs_are_chinese():
    """.scratch 下所有 spec.md 与 issues/*.md 以中文为主（≥30 个中文字符）。"""
    files = sorted(ROOT.joinpath(".scratch").rglob("*.md"))
    targets = [f for f in files if f.name == "spec.md" or f.parent.name == "issues"]
    offenders = []
    for path in targets:
        text = path.read_text(encoding="utf-8", errors="replace")
        count = _cjk_count(text)
        if count < 30:
            offenders.append(f"{path.relative_to(ROOT)}：中文字符 {count} 个")
    assert not offenders, "以下工单/spec 非中文（中文字符 < 30）：\n" + "\n".join(offenders)


def test_changelog_entries_are_chinese():
    """CHANGELOG.md 每条更新记录含中文（≥4 个中文字符）。"""
    text = ROOT.joinpath("CHANGELOG.md").read_text(encoding="utf-8")
    entries = [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]
    assert entries, "CHANGELOG.md 无条目"
    bad = [entry for entry in entries if _cjk_count(entry) < 4]
    assert not bad, "以下 CHANGELOG 条目非中文（中文字符 < 4）：\n" + "\n".join(bad)


def test_versions_entries_are_chinese():
    """VERSIONS.md 每条版本条目含中文（≥4 个中文字符）；文件缺失即红。

    未发版 = 零真实条目（空通过）；一旦发版，每条必须中文。HTML 注释区间
    与条目行内注释剥离（见 _version_entry_lines，纯函数单测见下）。
    """
    text = ROOT.joinpath("VERSIONS.md").read_text(encoding="utf-8")
    entries = _version_entry_lines(text)
    bad = [entry for entry in entries if _cjk_count(entry) < 4]
    assert not bad, "以下 VERSIONS 条目非中文（中文字符 < 4）：\n" + "\n".join(bad)


def test_version_entry_lines_skips_comment_region_and_inline_comment():
    """条目提取：多行注释区间整段跳过；条目行内注释只剥尾部不影响取文本。"""
    text = (
        "# 版本更新记录\n"
        "<!-- 格式示例：\n"
        "- 新增：短示例\n"
        "- 修复：短示例\n"
        "-->\n"
        "- 新增：正式条目 <!-- 行内注 -->\n"
        "- 主题：一句话概括\n"
    )
    assert _version_entry_lines(text) == ["新增：正式条目", "主题：一句话概括"]


def test_chinese_commit_gate_hook_exists():
    """防英文提交门禁存在：.githooks/commit-msg（含 CJK 字节模式校验）。"""
    hook = ROOT.joinpath(".githooks", "commit-msg")
    assert hook.is_file(), "缺少 .githooks/commit-msg（英文提交门禁）"
    text = hook.read_text(encoding="utf-8")
    assert r"\xe4-\xe9" in text, "commit-msg 缺少 CJK UTF-8 字节模式校验"
    assert "lib:*" in text, "commit-msg 缺少 lib: 机器提交豁免"
