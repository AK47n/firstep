"""更新记录解析（工单 changelog-tab/01）：纯函数 parse_changelog + load_changelog
+ git log 自动补记（git_changelog_groups / merge_changelog / load_changelog_auto）。

数据源 = 手工维护的仓库根 CHANGELOG.md 为主、git log 自动补记手工文件没有的
日期。解析规则（格式契约，见 changelog.py docstring）：`## YYYY-MM-DD` 严格
日期开新组（`^...$` 锚定），组内 `- ` 行是条目，`# ` 大标题 / 说明段落 /
空行 / 无日期组的 `- ` 行全部跳过。纯展示数据：文件缺失 / 读取异常 → []，
不阻塞工具。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.changelog import (
    git_changelog_groups,
    load_changelog,
    load_changelog_auto,
    merge_changelog,
    parse_changelog,
)


def test_parse_standard_multiple_groups_and_items():
    """标准格式：多组多条目按文件顺序，日期 / 条目内容原样保留（无时间前缀）。"""
    text = (
        "# 更新记录\n"
        "\n"
        "（格式说明：`## YYYY-MM-DD` + `- 描述`，新记录插最前面。以下为示例）\n"
        "\n"
        "## 2026-08-12\n"
        "- 新增更新记录栏目（第 8 个 tab）\n"
        "- 编译错误列表支持点击展开源码行\n"
        "\n"
        "## 2026-08-11\n"
        "- 推荐请求契约对偶\n"
        "- 2021F Keil 真机验收\n"
    )
    assert parse_changelog(text) == [
        {"date": "2026-08-12", "items": [
            {"time": "", "text": "新增更新记录栏目（第 8 个 tab）"},
            {"time": "", "text": "编译错误列表支持点击展开源码行"},
        ]},
        {"date": "2026-08-11", "items": [
            {"time": "", "text": "推荐请求契约对偶"},
            {"time": "", "text": "2021F Keil 真机验收"},
        ]},
    ]


def test_parse_standard_with_time_prefixes():
    """带 `HH:MM ` 时间前缀的条目：前缀剥离进 {time, text}，文本保持原样。"""
    text = (
        "## 2026-08-12\n"
        "- 17:48 编译体验展示层（结果横幅四态 + 错误列表）\n"
        "- 16:38 自动编译修复闭环\n"
        "- 9:05 单小时位时间也接受\n"
        "- 无时间前缀条目\n"
    )
    assert parse_changelog(text) == [
        {"date": "2026-08-12", "items": [
            {"time": "17:48", "text": "编译体验展示层（结果横幅四态 + 错误列表）"},
            {"time": "16:38", "text": "自动编译修复闭环"},
            {"time": "9:05", "text": "单小时位时间也接受"},
            {"time": "", "text": "无时间前缀条目"},
        ]},
    ]


def test_parse_skips_heading_and_description():
    """`# ` 大标题与说明段落跳过，不影响后续日期组解析。"""
    text = (
        "# 更新记录\n"
        "（这是一段说明文字，介绍文件维护方式；开头 `## ` 的表述只是举例）\n"
        "## 2026-08-09\n"
        "- 架构深化 v5 闭环\n"
    )
    assert parse_changelog(text) == [{"date": "2026-08-09", "items": [{"time": "", "text": "架构深化 v5 闭环"}]}]


def test_parse_skips_blank_lines():
    """空行（含纯空白行）跳过，不产生空组 / 空条目。"""
    text = "## 2026-08-12\n\n\n- 条目\n   \n## 2026-08-11\n\n- 另一条\n"
    assert parse_changelog(text) == [
        {"date": "2026-08-12", "items": [{"time": "", "text": "条目"}]},
        {"date": "2026-08-11", "items": [{"time": "", "text": "另一条"}]},
    ]


def test_parse_non_date_section_header_not_misparsed():
    """说明里的 `## 非日期` 小节不误判为日期组，条目仍归当前日期组。"""
    text = (
        "## 2026-08-12\n"
        "- 组内条目\n"
        "## 补充说明（不是日期）\n"
        "- 仍归 08-12 组\n"
    )
    assert parse_changelog(text) == [{"date": "2026-08-12", "items": [
        {"time": "", "text": "组内条目"},
        {"time": "", "text": "仍归 08-12 组"},
    ]}]


def test_parse_ignores_dash_lines_without_date_group():
    """无当前日期组时的 `- ` 行忽略（格式说明示例等位置）。"""
    text = (
        "# 更新记录\n"
        "- 游离条目（无日期组，应忽略）\n"
        "\n"
        "## 2026-08-11\n"
        "- 正式条目\n"
    )
    assert parse_changelog(text) == [{"date": "2026-08-11", "items": [{"time": "", "text": "正式条目"}]}]


def test_parse_strips_item_whitespace():
    """条目只取 `- ` 后内容并去首尾空白；空条目行（`- ` 后无内容）跳过。"""
    text = "## 2026-08-12\n-   左侧有缩进  \n- \n- 正常条目\n"
    assert parse_changelog(text) == [{"date": "2026-08-12", "items": [
        {"time": "", "text": "左侧有缩进"},
        {"time": "", "text": "正常条目"},
    ]}]


def test_parse_strict_date_format():
    """日期必须严格 `YYYY-MM-DD` 两位（行首行尾锚定），残缺 / 尾部追加不建组。"""
    text = (
        "## 2026-8-12\n"
        "- 月份未补零，整段丢弃\n"
        "## 2026-08-12 补记\n"
        "- 行尾有多余文字，整段丢弃\n"
        "## 2026-08-12\n"
        "- 严格格式正常\n"
    )
    assert parse_changelog(text) == [{"date": "2026-08-12", "items": [{"time": "", "text": "严格格式正常"}]}]


def test_load_missing_file_returns_empty(tmp_path):
    """文件缺失 → []（纯展示数据，损坏不阻塞工具）。"""
    assert load_changelog(tmp_path / "nope" / "CHANGELOG.md") == []


def test_load_unreadable_path_returns_empty(tmp_path):
    """读取异常（如路径是目录）→ []。"""
    assert load_changelog(tmp_path) == []


# ---------------------------------------------------------------------------
# git log 自动补记（2026-08-15 用户定案：更新记录自动更新）
# ---------------------------------------------------------------------------


def test_merge_changelog_manual_wins_and_auto_fills_missing_dates():
    """手工日期组优先；git 组只补手工没有的日期；结果按日期倒序。"""
    manual = [
        {"date": "2026-08-13", "items": [{"time": "13:45", "text": "手工条目"}]},
        {"date": "2026-08-12", "items": [{"time": "17:48", "text": "旧条目"}]},
    ]
    auto = [
        {"date": "2026-08-15", "items": [{"time": "19:49", "text": "自动条目"}]},
        {"date": "2026-08-13", "items": [{"time": "00:00", "text": "不应出现"}]},
        {"date": "2026-08-14", "items": [{"time": "10:00", "text": "补 08-14"}]},
    ]
    assert merge_changelog(manual, auto) == [
        {"date": "2026-08-15", "items": [{"time": "19:49", "text": "自动条目"}]},
        {"date": "2026-08-14", "items": [{"time": "10:00", "text": "补 08-14"}]},
        {"date": "2026-08-13", "items": [{"time": "13:45", "text": "手工条目"}]},
        {"date": "2026-08-12", "items": [{"time": "17:48", "text": "旧条目"}]},
    ]


def test_merge_changelog_empty_auto_returns_manual():
    """git 不可用（自动组为空）→ 手工组原样返回（旧行为）。"""
    manual = [{"date": "2026-08-13", "items": [{"time": "", "text": "手工"}]}]
    assert merge_changelog(manual, []) == manual


def test_git_changelog_groups_non_repo_returns_empty(tmp_path):
    """不在 git 工作树（如临时空目录）→ []，不阻塞工具。"""
    assert git_changelog_groups(tmp_path) == []


def test_load_changelog_auto_without_repo_dir_falls_back_to_manual(tmp_path):
    """repo_dir 为 None → 只回手工文件（旧行为）。"""
    path = tmp_path / "CHANGELOG.md"
    path.write_text("## 2026-08-13\n- 手工条目\n", encoding="utf-8")
    assert load_changelog_auto(path, None) == [
        {"date": "2026-08-13", "items": [{"time": "", "text": "手工条目"}]}
    ]
