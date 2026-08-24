"""生成输出目标解析：桌面赛题目录命名与唯一化。"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.generation_output import (
    TOPIC_EN_TITLES,
    topic_dir_title,
    topic_en_title,
    topic_short_title,
    topic_title_from_summary,
    unique_desktop_topic_dir,
    windows_safe_folder_name,
)


def test_topic_title_from_summary_uses_first_non_bullet_line():
    summary = "智能巡检小车\n- 采集温湿度\n- OLED 显示"

    assert topic_title_from_summary(summary) == "智能巡检小车"


def test_topic_title_from_summary_strips_title_prefix():
    assert topic_title_from_summary("题名：智能巡检小车\n- 要点") == "智能巡检小车"


@pytest.mark.parametrize(
    ("problem_text", "expected"),
    [
        # 历史赛题首行真实形态（2024H 复盘：目录名 = 编号 + 短题名）
        ("自动行驶小车（H 题）\n一、 任务\n", "自动行驶小车"),
        ("智能送药小车（F题）\n【本科组】\n", "智能送药小车"),
        ("小车跟随行驶系统（C 题）\n一、 任务\n", "小车跟随行驶系统"),
        ("C 题：无线充电电动小车（本科）\n1. 任务\n", "无线充电电动小车"),
        ("# 基于无线通信的数字钥匙实验系统（C题）\n", "基于无线通信的数字钥匙实验系统"),
        ("电动小车动态无线充电系统（A 题）\n", "电动小车动态无线充电系统"),
    ],
)
def test_topic_short_title_extracts_short_name_from_first_line(problem_text, expected):
    """首行短题名提取：去掉 markdown 标题符 / 行首题号前缀 / 行尾（题号/组别）括号。"""
    assert topic_short_title(problem_text) == expected


def test_topic_short_title_keeps_unparseable_first_line():
    """首行没有题号/括号形态 → 原样保留（不猜不删）。"""
    assert topic_short_title("2026C 数字钥匙题面全文（长 PDF 拆条入库）") == (
        "2026C 数字钥匙题面全文（长 PDF 拆条入库）"
    )


def test_topic_dir_title_prefixes_key_with_ascii_english():
    """历史赛题目录名 = 编号 + 英文短名（工单 ascii-project-name/01：中文路径
    在 CCS/gmake 链上乱码，目录名改纯英文）。"""
    assert topic_dir_title("2024H", "自动行驶小车（H 题）\n") == "2024H_Auto_Car"
    assert topic_dir_title("2021F", "智能送药小车（F题）\n") == "2021F_Smart_Medicine_Car"


def test_topic_en_title_dictionary_covers_all_library_topics():
    """内置字典覆盖现题库全部 8 题的短题名（topic_short_title 提取结果）。"""
    from pathlib import Path
    topics_root = (
        Path(__file__).resolve().parents[1] / "library" / "topics"
    )
    assert topics_root.is_dir(), "题库目录缺失（library/topics）"
    for entry in topics_root.iterdir():
        md = entry / "topic.md"
        if not md.is_file():
            continue
        first = md.read_text(encoding="utf-8").splitlines()[0].strip()
        short = topic_short_title(first)
        assert short in TOPIC_EN_TITLES, (
            f"题库 {entry.name} 短题名 {short!r} 未收录进 TOPIC_EN_TITLES"
        )


def test_topic_en_title_ascii_fallback_keeps_alnum_tokens():
    """字典未命中：ASCII 兜底保留字母数字 token、下划线连接。"""
    assert topic_en_title("2027年全国电子设计竞赛(F题)") == "2027_F"
    assert topic_en_title("ECCI D 2027") == "ECCI_D_2027"


def test_topic_en_title_falls_back_to_chinese_when_no_ascii():
    """纯中文兜底 → 回退原短题名（保底可生成）。"""
    assert topic_en_title("完全中文题名") == "完全中文题名"


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
