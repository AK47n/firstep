"""生成输出目标解析：桌面赛题目录命名与唯一化。"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.generation_output import (
    topic_title_from_summary,
    unique_desktop_topic_dir,
    windows_safe_folder_name,
)


def test_topic_title_from_summary_uses_first_non_bullet_line():
    summary = "智能巡检小车\n- 采集温湿度\n- OLED 显示"

    assert topic_title_from_summary(summary) == "智能巡检小车"


def test_topic_title_from_summary_strips_title_prefix():
    assert topic_title_from_summary("题名：智能巡检小车\n- 要点") == "智能巡检小车"


def test_windows_safe_folder_name_cleans_invalid_chars_and_empty_title():
    assert windows_safe_folder_name('  A<>:"/\\|?*  B  ') == "A_ B"
    assert windows_safe_folder_name(" / ") == "赛题工程"


@pytest.mark.parametrize("name", ["CON", "CON.txt", "prn.md", "COM1.log", "LPT9.tmp"])
def test_windows_safe_folder_name_avoids_reserved_device_names(name):
    assert windows_safe_folder_name(name).endswith("_")


def test_unique_desktop_topic_dir_adds_timestamp_then_counter(tmp_path, monkeypatch):
    desktop = tmp_path / "Desktop"
    (desktop / "CON_").mkdir(parents=True)
    (desktop / "CON_20260819-153000").mkdir()
    monkeypatch.setattr("contest_generator.generation_output.time.strftime", lambda fmt: "20260819-153000")

    assert unique_desktop_topic_dir(desktop, "CON") == desktop / "CON_20260819-153000_2"
