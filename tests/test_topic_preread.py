"""赛题预读域机械校验单测（工单 topic-preread/01）。

normalize_preread 纯函数：steps 洗白、引用命中题面（空白归一）、长度 /
条数上限、顶层形状错误。与其它「AI 输出不可信」契约同哲学——条目级宽松
过滤，顶层形状错误大声失败。
"""

from __future__ import annotations

import pytest

from contest_generator.topic_preread import (
    MAX_OVERVIEW_LEN,
    MAX_QUOTE_LEN,
    MAX_REMINDER_TEXT_LEN,
    MAX_REMINDERS,
    PREREAD_STEPS,
    normalize_preread,
    quote_in_problem,
)

PROBLEM = "采用 TI 公司 MSPM0 系列处理器\n车体尺寸\n不超过 30cm\n上位机串口通信"


def test_normalize_accepts_empty_reminders_and_missing_key():
    """无提醒合法（题面没有限定信息很常见）：缺 reminders = 空列表。"""
    result = normalize_preread({"overview": "做一个温湿度采集系统"}, PROBLEM)

    assert result.overview == "做一个温湿度采集系统"
    assert result.reminders == ()


def test_normalize_requires_top_level_shape():
    """顶层形状错误大声失败：非对象 / 缺 overview / reminders 非数组。"""
    for bad in ("文本", None, 42, ["x"]):
        with pytest.raises(ValueError):
            normalize_preread(bad, PROBLEM)
    with pytest.raises(ValueError):
        normalize_preread({"reminders": []}, PROBLEM)
    with pytest.raises(ValueError):
        normalize_preread({"overview": "总览", "reminders": "不是数组"}, PROBLEM)


def test_normalize_cleans_steps_enum_only():
    """steps 洗白：只认 PREREAD_STEPS 枚举；bool 不算 int；重复合并保序。"""
    result = normalize_preread(
        {
            "overview": "总览",
            "reminders": [
                {"steps": [3, 7, 3, 99, True, "5"], "text": "A"},
                {"steps": [], "text": "B"},
            ],
        },
        PROBLEM,
    )

    assert result.reminders[0].steps == (3, 7)
    assert result.reminders[1].steps == ()


def test_normalize_quote_must_hit_problem_after_whitespace_normalization():
    """引用命中判断：空白归一后子串匹配（折行 / 多余空格 / 全角空格都算命中）；
    不命中丢弃引用（保留提醒）。"""
    assert quote_in_problem(PROBLEM, "采用 TI 公司 MSPM0 系列处理器")
    assert quote_in_problem(PROBLEM, "采用 TI 公司\nMSPM0 系列处理器")
    assert quote_in_problem(PROBLEM, "车体尺寸  不超过\n30cm")
    assert not quote_in_problem(PROBLEM, "题面根本没有这句话")
    assert not quote_in_problem(PROBLEM, "  ")

    result = normalize_preread(
        {
            "overview": "总览",
            "reminders": [
                {"steps": [3], "text": "限定 MSPM0", "quote": "MSPM0（题面没有）"},
                {"steps": [3], "text": "限定 MSPM0", "quote": "采用 TI 公司 MSPM0"},
            ],
        },
        PROBLEM,
    )

    assert result.reminders[0].quote == ""
    assert result.reminders[1].quote == "采用 TI 公司 MSPM0"


def test_normalize_drops_reminder_with_empty_text_and_limits_count_and_length():
    """空 text 丢弃整条；超条数截尾（保留前 N 条）；text/quote/overview 超长截断。"""
    long_text = "长" * (MAX_REMINDER_TEXT_LEN + 50)
    long_quote = "采用 TI 公司 MSPM0 系列处理器" + "延长" * MAX_QUOTE_LEN
    raw = {
        "overview": "总览" * (MAX_OVERVIEW_LEN + 10),
        "reminders": [
            {"steps": [3], "text": "", "quote": ""},
            {"steps": [3], "text": "无引用", "quote": ""},
            *(
                {"steps": [3], "text": f"提醒{i}", "quote": ""}
                for i in range(MAX_REMINDERS + 5)
            ),
        ],
    }
    result = normalize_preread(raw, PROBLEM)

    assert len(result.reminders) == MAX_REMINDERS
    assert result.reminders[0].text == "无引用"  # 空 text 被丢，后一条前移
    assert len(result.overview) == MAX_OVERVIEW_LEN

    result = normalize_preread(
        {
            "overview": "总览",
            "reminders": [{"steps": [3], "text": long_text, "quote": long_quote}],
        },
        PROBLEM,
    )
    assert len(result.reminders[0].text) == MAX_REMINDER_TEXT_LEN
    assert len(result.reminders[0].quote) <= MAX_QUOTE_LEN


def test_normalize_to_dict_roundtrip():
    """to_dict 形状（webapp 返回契约）：steps 数组 + text + quote。"""
    result = normalize_preread(
        {
            "overview": "总览",
            "reminders": [{"steps": [3, 7], "text": "提醒", "quote": "采用 TI 公司 MSPM0"}],
        },
        PROBLEM,
    )

    assert result.to_dict() == {
        "overview": "总览",
        "reminders": [{"steps": [3, 7], "text": "提醒", "quote": "采用 TI 公司 MSPM0"}],
    }


def test_normalize_step_names_cover_preread_steps():
    """步骤语义表与合法集单源一致：键集 = PREREAD_STEPS（提示词数字同源）。"""
    from contest_generator.topic_preread import PREREAD_STEP_NAMES

    assert set(PREREAD_STEP_NAMES) == set(PREREAD_STEPS)
