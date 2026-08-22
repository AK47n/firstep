"""桌面测试产物清理函数单测（conftest 收尾钩子的核心逻辑）。

cleanup_desktop_test_artifacts 只删「AI 生成的赛题简介」前缀目录（FakeLLM
fallback 命名 = 测试产物特征）；真实命名（赛题名目录）与文件一律保留。
"""

from pathlib import Path

from tests._desktop_cleanup import cleanup_desktop_test_artifacts

cleanup = cleanup_desktop_test_artifacts


def test_removes_only_fallback_named_dirs(tmp_path):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "AI 生成的赛题简介_20260822-230724").mkdir()
    (desktop / "AI 生成的赛题简介_20260822-230724_2").mkdir()
    (desktop / "AI 生成的赛题简介").mkdir()
    (desktop / "2026H 自动行驶小车").mkdir()          # 真实命名（LLM 成功）→ 保留
    (desktop / "AI 生成的赛题简介.txt").write_text("x", encoding="utf-8")  # 文件 → 保留

    removed = cleanup(desktop)

    assert sorted(removed) == [
        "AI 生成的赛题简介",
        "AI 生成的赛题简介_20260822-230724",
        "AI 生成的赛题简介_20260822-230724_2",
    ]
    assert (desktop / "2026H 自动行驶小车").is_dir()
    assert (desktop / "AI 生成的赛题简介.txt").is_file()


def test_nested_content_removed_fully(tmp_path):
    desktop = tmp_path / "Desktop"
    (desktop / "AI 生成的赛题简介_20260822-013505" / "sub").mkdir(parents=True)
    (desktop / "AI 生成的赛题简介_20260822-013505" / "main.c").write_text("x", encoding="utf-8")

    removed = cleanup(desktop)

    assert removed == ["AI 生成的赛题简介_20260822-013505"]
    assert not (desktop / "AI 生成的赛题简介_20260822-013505").exists()


def test_missing_desktop_no_error(tmp_path):
    assert cleanup(tmp_path / "no_such_desktop") == []


def test_clean_desktop_noop(tmp_path):
    desktop = tmp_path / "Desktop"
    (desktop / "2026H 自动行驶小车").mkdir(parents=True)
    assert cleanup(desktop) == []
    assert (desktop / "2026H 自动行驶小车").is_dir()
