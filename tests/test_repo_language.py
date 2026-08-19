"""仓库文档语言门禁：工单 / spec / CHANGELOG 条目必须中文。

背景：llm-observability-dashboard 的工单与 08-18 的 CHANGELOG 记录曾整段英文
（直接后果：更新记录展示英文）。约定：仓库面向用户/代理的文档一律中文
（技术术语可保留英文）；commit message 由 .githooks/commit-msg 拦截英文。
本测试是第二道防线（换机器忘配 hooksPath / --no-verify 时仍能抓到）。
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _cjk_count(text: str) -> int:
    return len(_CJK_RE.findall(text))


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


def test_chinese_commit_gate_hook_exists():
    """防英文提交门禁存在：.githooks/commit-msg（含 CJK 字节模式校验）。"""
    hook = ROOT.joinpath(".githooks", "commit-msg")
    assert hook.is_file(), "缺少 .githooks/commit-msg（英文提交门禁）"
    text = hook.read_text(encoding="utf-8")
    assert r"\xe4-\xe9" in text, "commit-msg 缺少 CJK UTF-8 字节模式校验"
    assert "lib:*" in text, "commit-msg 缺少 lib: 机器提交豁免"
