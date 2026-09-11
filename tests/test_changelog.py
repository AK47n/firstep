"""更新记录解析（工单 changelog-tab/01）：纯函数 parse_changelog + load_changelog。

数据源是手工维护的仓库根 CHANGELOG.md。解析规则（格式契约，见
changelog.py docstring）：`## YYYY-MM-DD` 严格日期开新组（`^...$` 锚定），
组内 `- ` 行是条目，`# ` 大标题 / 说明段落 / 空行 / 无日期组的 `- ` 行
全部跳过。纯展示数据：文件缺失 / 读取异常 → []，不阻塞工具。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.changelog import (
    _clean_subject,
    _is_displayable,
    _marker_sha,
    _merge_commits,
    _newest_datetime,
    _split_header,
    _upsert_marker,
    load_changelog,
    load_versions,
    parse_changelog,
    parse_versions,
    update_changelog,
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
# 自动补录（changelog-auto）：git log → CHANGELOG.md
# ---------------------------------------------------------------------------


def test_is_displayable_skips_merge_docs_chore_test_and_routine_lib():
    """merge / docs: / chore: / test: / 写库 CRUD 机器提交不进更新记录。"""
    assert _is_displayable("Merge pull request #56 from AK47n/ref-fulltext-truncation") is False
    assert _is_displayable("merge branch 'main'") is False
    assert _is_displayable("docs: 工单 01 开工认领") is False
    assert _is_displayable("chore: 自动更新 CHANGELOG") is False
    assert _is_displayable("test: 补结构钉") is False
    assert _is_displayable("lib: update module description filter") is False
    assert _is_displayable("lib: add reference 塔克R3两驱小车底盘资料") is False
    assert _is_displayable("lib: update topic 2023E") is False
    assert _is_displayable("lib: update reference 塔克R3两驱小车底盘资料") is False
    assert _is_displayable("lib: archive reference library/references/xxx") is False
    assert _is_displayable("lib: 赛题条目补图注") is False
    assert _is_displayable("feat: 板图加旋转按钮 (#92)") is True
    assert _is_displayable("fix: 推荐模块移除不再回加 (#91)") is True
    assert _is_displayable("软 I2C 参数化 + 共享端口宏异值门禁（工单 pin-unlock-stm32/02） (#77)") is True
    assert _is_displayable("lib: 素材录入脚本 GBK 兜底转码（工单 register-gbk-guard/01）") is True


def test_is_displayable_skips_bom_prefixed_machine_commits():
    """BOM 前缀不打穿跳过清单（工单 commit-subject-bom/01）。

    触发路径：提交信息文件由 `Out-File -Encoding utf8`（PS 5.1）写成 → 文件头
    带 BOM → `git commit -F` 把 BOM 带进主题 → `git log --format=%s` 取出的主题
    以 `\\ufeff` 开头 → startswith 判不出 `docs:` / `chore:` / `test:` / `merge`
    → 机器提交被当成用户可见条目补录进 CHANGELOG（定稿区的上游被污染）。
    修法 = 判定前先 `lstrip("\\ufeff \\t")`；只吃 BOM 与前导空白，不做别的规范化。
    """
    assert _is_displayable("\ufefftest: 补结构钉") is False
    assert _is_displayable("\ufeffdocs: 工单 01 开工认领") is False
    assert _is_displayable("\ufeffchore: 自动更新 CHANGELOG") is False
    assert _is_displayable("\ufeffmerge branch 'main'") is False
    assert _is_displayable("\ufefflib: update topic 2023E") is False
    # 只有 BOM 的真条目照常显示（别把清洗做成「见 BOM 就丢」）
    assert _is_displayable("\ufefffeat: 板图加旋转按钮 (#92)") is True
    assert _is_displayable("\ufefffix: 推荐模块移除不再回加") is True
    # 前导空白（同一类「主题前缀被噪声打穿」）一并吃掉
    assert _is_displayable("  docs: 工单 01 开工认领") is False


def test_clean_subject_strips_type_prefix_and_pr_ref():
    """条目文本 = 提交主题去类型前缀与尾部 (#NN)。"""
    assert _clean_subject("feat: 板图加「旋转 90°」按钮 (#92)") == "板图加「旋转 90°」按钮"
    assert _clean_subject("fix: 排针 30px 向上伸出板外") == "排针 30px 向上伸出板外"
    assert _clean_subject("软 I2C 参数化 + 共享端口宏异值门禁（工单 pin-unlock-stm32/02） (#77)") == "软 I2C 参数化 + 共享端口宏异值门禁（工单 pin-unlock-stm32/02）"


def test_marker_roundtrip_in_header():
    """机器标记在头部插入 / 替换 / 读取。"""
    assert _marker_sha("# 更新记录") is None
    header = _upsert_marker("# 更新记录", "abc123")
    assert _marker_sha(header) == "abc123"
    assert _upsert_marker(header, "def456") == "<!-- changelog-auto: last-commit=def456 -->\n# 更新记录"


def test_split_header_separates_before_first_date_group():
    """头部 = 首个日期组之前的一切（含标题、说明、机器标记）。"""
    text = "<!-- changelog-auto: last-commit=abc -->\n# 更新记录\n\n（说明）\n\n## 2026-08-15\n- 20:20 条目\n"
    header, body = _split_header(text)
    assert "last-commit=abc" in header
    assert body.startswith("## 2026-08-15")


def test_merge_commits_date_desc_items_time_asc_and_dedup():
    """新提交并入：日期组倒序、组内时间先后、同 (时间, 文本) 去重。"""
    groups = [
        {"date": "2026-08-15", "items": [
            {"time": "9:05", "text": "早条目"},
            {"time": "", "text": "无时间条目"},
        ]},
    ]
    commits = [
        {"sha": "a", "date": "2026-08-15", "time": "10:00", "subject": "feat: 晚条目"},
        {"sha": "b", "date": "2026-08-15", "time": "10:00", "subject": "feat: 晚条目"},
        {"sha": "c", "date": "2026-08-16", "time": "08:00", "subject": "fix: 次日条目"},
    ]
    merged = _merge_commits(groups, commits)
    assert [g["date"] for g in merged] == ["2026-08-16", "2026-08-15"]
    day15 = merged[1]["items"]
    assert [i["text"] for i in day15] == ["无时间条目", "早条目", "晚条目"]


def test_newest_datetime_uses_latest_date_and_max_minutes():
    """无标记回退：取最新日期组内最晚时间（1 位小时按分钟数比较）。"""
    groups = [
        {"date": "2026-08-15", "items": [
            {"time": "9:05", "text": "a"},
            {"time": "10:00", "text": "b"},
        ]},
        {"date": "2026-08-14", "items": [{"time": "23:59", "text": "c"}]},
    ]
    assert _newest_datetime(groups) == "2026-08-15 10:00"
    assert _newest_datetime([]) is None


def test_update_changelog_appends_entries_and_writes_marker(tmp_path, monkeypatch):
    """无标记文件 + 新提交 → 追加条目、写机器标记；再次更新无新提交不动文件。"""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# 更新记录\n\n## 2026-08-15\n- 20:20 模块平台徽标两行显示\n",
        encoding="utf-8",
    )
    repo = tmp_path  # update 只把 repo 传给 git 原语，此处已被 monkeypatch
    monkeypatch.setattr(
        "contest_generator.changelog._git_head_sha", lambda repo: "abc123"
    )
    monkeypatch.setattr(
        "contest_generator.changelog._git_log_commits",
        lambda repo, since_sha=None, since_dt=None: [
            {"sha": "abc123", "date": "2026-08-15", "time": "21:00", "subject": "feat: 新功能上线 (#94)"},
        ],
    )

    assert update_changelog(changelog, repo) is True
    text = changelog.read_text(encoding="utf-8")
    assert "last-commit=abc123" in text
    groups = parse_changelog(text)
    assert groups[0]["items"][0]["text"] == "模块平台徽标两行显示"
    assert groups[0]["items"][1] == {"time": "21:00", "text": "新功能上线"}

    # 无新提交：不写入
    monkeypatch.setattr(
        "contest_generator.changelog._git_log_commits",
        lambda repo, since_sha=None, since_dt=None: [],
    )
    assert update_changelog(changelog, repo) is False


def test_update_changelog_no_display_commits_returns_false(tmp_path, monkeypatch):
    """只有 chore/docs 噪声提交 → 不写入（也避免钩子递归提交）。"""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# 更新记录\n\n## 2026-08-15\n- 20:20 条目\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "contest_generator.changelog._git_head_sha", lambda repo: "def456"
    )
    monkeypatch.setattr(
        "contest_generator.changelog._git_log_commits",
        lambda repo, since_sha=None, since_dt=None: [
            {"sha": "def456", "date": "2026-08-15", "time": "21:00", "subject": "chore: 自动更新 CHANGELOG"},
        ],
    )
    assert update_changelog(changelog, tmp_path) is False
    assert "last-commit" not in changelog.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 版本更新记录（VERSIONS.md 定稿区，工单 version-changelog/02）：
# parse_versions + load_versions——用户视角版本要点，纯展示数据不抛
# ---------------------------------------------------------------------------


def test_parse_versions_standard_blocks():
    """标准格式：`## vX.Y.Z (YYYY-MM-DD)` 开组，主题归 summary，标签条目进 items。"""
    text = (
        "# 版本更新记录\n"
        "\n"
        "（说明段：面向用户的版本要点……）\n"
        "\n"
        "## v1.1.0 (2026-09-04)\n"
        "- 主题：一个月打磨，从能生成工程到像 IDE 一样改\n"
        "- 新增：代码栏——IDE 式编辑器（文件树 / 多标签保存）\n"
        "- 改进：生成主流程自动编译 + AI 修复\n"
        "- 修复：一批现场问题\n"
        "\n"
        "## v1.0.0 (2026-08-05)\n"
        "- 新增：首个版本\n"
    )
    assert parse_versions(text) == [
        {"version": "v1.1.0", "date": "2026-09-04",
         "summary": "一个月打磨，从能生成工程到像 IDE 一样改",
         "items": [
             {"kind": "新增", "text": "代码栏——IDE 式编辑器（文件树 / 多标签保存）"},
             {"kind": "改进", "text": "生成主流程自动编译 + AI 修复"},
             {"kind": "修复", "text": "一批现场问题"},
         ]},
        {"version": "v1.0.0", "date": "2026-08-05",
         "summary": "", "items": [{"kind": "新增", "text": "首个版本"}]},
    ]


def test_parse_versions_untagged_and_unknown_label_kept_whole():
    """无标签 / 未知标签的行不静默丢失：kind=其他，文本整行保留。"""
    text = (
        "## v1.1.0 (2026-09-04)\n"
        "- 无标签的一句话\n"
        "- 更新：未知标签也保留原文\n"
        "- 主题：  前后空白剥掉\n"
        "- 新增：\n"
    )
    assert parse_versions(text) == [
        {"version": "v1.1.0", "date": "2026-09-04", "summary": "前后空白剥掉",
         "items": [
             {"kind": "其他", "text": "无标签的一句话"},
             {"kind": "其他", "text": "更新：未知标签也保留原文"},
             {"kind": "新增", "text": ""},
         ]},
    ]


def test_parse_versions_skips_header_comments_and_foreign_sections():
    """大标题 / 多行 HTML 注释示例（内含 `## v` 与 `- ` 行）/ 非版本 `## `
    小节与组外 `- ` 行都不产生版本（注释状态跨越行界）。"""
    text = (
        "# 版本更新记录\n"
        "<!-- 格式示例（正式条目写在示例上方）：\n"
        "## v1.1.0 (2026-09-04)\n"
        "- 主题：一句话概括本期\n"
        "- 新增：示例条目不得解析出版本\n"
        "-->\n"
        "- 组外游离条目（忽略）\n"
        "## 格式约定（非版本小节）\n"
        "- 仍忽略\n"
        "## v1.1.0 (2026-09-04)\n"
        "- 新增：正式条目\n"
    )
    assert parse_versions(text) == [
        {"version": "v1.1.0", "date": "2026-09-04", "summary": "",
         "items": [{"kind": "新增", "text": "正式条目"}]},
    ]


def test_parse_versions_inline_comment_skipped():
    """同行闭合的 `<!-- … -->` 只跳过本行，不进入注释态。"""
    text = (
        "## v1.1.0 (2026-09-04)\n"
        "<!-- 单行注释：- 新增：示例 -->\n"
        "- 新增：正式条目\n"
    )
    assert parse_versions(text) == [
        {"version": "v1.1.0", "date": "2026-09-04", "summary": "",
         "items": [{"kind": "新增", "text": "正式条目"}]},
    ]


def test_parse_versions_strict_header():
    """版本头必须严格 `## vX.Y.Z (YYYY-MM-DD)`：ASCII 括号、日期补零、
    版本号主.次.补丁三段——任一残缺整块丢弃（不建组、其后条目不入任何组）。"""
    text = (
        "## v1.1.0 (2026-9-4)\n"
        "- 日期未补零，整段丢弃\n"
        "## v1.1 (2026-09-04)\n"
        "- 少一段版本号，整段丢弃\n"
        "## v1.1.0.1 (2026-09-04)\n"
        "- 多一段版本号，整段丢弃\n"
        "## v1.1.0（2026-09-04）\n"
        "- 全角括号不接受\n"
        "## v1.1.0 (2026-09-04)\n"
        "- 正式条目\n"
    )
    assert parse_versions(text) == [
        {"version": "v1.1.0", "date": "2026-09-04", "summary": "",
         "items": [{"kind": "其他", "text": "正式条目"}]},
    ]


def test_parse_versions_garbage_returns_empty():
    """乱文本（无版本头）→ []，不抛。"""
    assert parse_versions("随便什么\n# 标题\n- 游离行\n") == []


def test_load_versions_missing_file_returns_empty(tmp_path):
    """VERSIONS.md 缺失 → []（纯展示数据，损坏不阻塞工具）。"""
    assert load_versions(tmp_path / "nope" / "VERSIONS.md") == []


def test_load_versions_unreadable_path_returns_empty(tmp_path):
    """读取异常（路径是目录）→ []。"""
    assert load_versions(tmp_path) == []


def test_load_versions_real_file_reflects_released_versions():
    """真实 VERSIONS.md：已发布 v1.0.0（GitHub Release 2026-08-30 定稿）。

    契约守卫：官方格式示例注释（`<!-- … -->` 内含 `## v` / `- ` 行）不得
    击穿注释态解析出幽灵版本——真实块恰好 1 个、字段与首版定稿一致；
    下个版本发布时更新此断言（追加而非替换）。
    """
    real = Path(__file__).resolve().parents[1] / "VERSIONS.md"
    releases = load_versions(real)
    assert len(releases) == 1, "VERSIONS.md 应恰有 1 个已发布版本（示例注释不算）"
    first = releases[0]
    assert first["version"] == "v1.0.0"
    assert first["date"] == "2026-08-30"
    assert first["summary"], "首版应有主题一句话"
    assert first["items"], "首版应有要点条目"
    assert all(
        isinstance(i["kind"], str) and isinstance(i["text"], str) and i["text"]
        for i in first["items"]
    )
