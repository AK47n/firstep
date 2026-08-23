"""按需视觉问答传输层（工单 recommend-vision-qa/02）：图内问题 → 条目 PDF
渲染 → 视觉模型针对性作答。

渲染（locate_topic_pages / _render_page_png）与视觉（describe_image_cached）
均为模块级引用 = monkeypatch 接缝（照 extraction 测试先例）：假定位 / 假
渲染字节 / 假视觉回答，验证「定位 → 逐页渲染 → 提问（prompt=问题）→ 答案
返回 / 否定词判 None / 异常判 None / 多页拼接」。真实视觉网络不在此测试
（真机验收需用户配置视觉 key）。
"""

import pytest

from contest_generator.vision import VisionError
from contest_generator.vision_qa import (
    VISION_NEGATIVE_PATTERNS,
    answer_figure_question,
)

PDF_PATH = "library/topics/2021F/000_真题汇总.pdf"
PROBLEM_TEXT = "送药小车。院区如图1所示。"
QUESTION = "图1中的走廊宽度是多少？"
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-rendered-page"


def _fake_locate(page_range):
    def locate(pdf_path, topic_text):
        assert str(pdf_path) == PDF_PATH
        assert topic_text == PROBLEM_TEXT
        return page_range
    return locate


def _fake_render(fail_pages=()):
    def render(path, page_no):
        assert str(path) == PDF_PATH
        if page_no in fail_pages:
            return None
        return PNG_BYTES
    return render


def test_answer_figure_question_returns_vision_answer(monkeypatch):
    """定位 1 页 → 渲染 → 视觉回答返回（不判否定）。"""
    seen = {}

    def fake_describe(png, mime, prompt, **kwargs):
        seen["png"] = png
        seen["mime"] = mime
        seen["prompt"] = prompt
        return "走廊宽度 30cm"

    monkeypatch.setattr(
        "contest_generator.vision_qa.locate_topic_pages", _fake_locate((124, 125))
    )
    monkeypatch.setattr("contest_generator.vision_qa._render_page_png", _fake_render())
    monkeypatch.setattr(
        "contest_generator.vision_qa.describe_image_cached", fake_describe
    )

    result = answer_figure_question(
        PDF_PATH, PROBLEM_TEXT, QUESTION, vision_api_key="sk-test"
    )

    assert result == "走廊宽度 30cm"
    assert seen["png"] == PNG_BYTES and seen["mime"] == "image/png"
    assert QUESTION in seen["prompt"]  # 问题即 prompt（带引导）


def test_answer_figure_question_renders_only_located_pages(monkeypatch):
    """只渲染定位页范围（(start, end) 开区间）：共享汇总 PDF 不渲染全文档。"""
    rendered = []
    asked = []

    def fake_render(path, page_no):
        rendered.append(page_no)
        return PNG_BYTES

    def fake_describe(png, mime, prompt, **kwargs):
        asked.append(png)
        return f"第{len(asked)}页答案"

    monkeypatch.setattr(
        "contest_generator.vision_qa.locate_topic_pages", _fake_locate((5, 7))
    )
    monkeypatch.setattr("contest_generator.vision_qa._render_page_png", fake_render)
    monkeypatch.setattr(
        "contest_generator.vision_qa.describe_image_cached", fake_describe
    )

    result = answer_figure_question(
        PDF_PATH, PROBLEM_TEXT, QUESTION, vision_api_key="sk-test"
    )

    assert rendered == [5, 6]  # 只渲染定位页（开区间不含尾页）
    assert len(asked) == 2
    assert result == "第1页答案\n第2页答案"  # 多页答案换行拼接


@pytest.mark.parametrize("answer", VISION_NEGATIVE_PATTERNS + ("图中没有相关信息",))
def test_answer_figure_question_negative_answers_return_none(monkeypatch, answer):
    """视觉回答命中否定词（没有 / 未找到 / 图上无 / 图中无 / 无法 / 不确定 /
    无相关信息）→ None（转用户，宁缺毋滥——错误答案会污染澄清历史）。"""
    monkeypatch.setattr(
        "contest_generator.vision_qa.locate_topic_pages", _fake_locate((124, 126))
    )
    monkeypatch.setattr("contest_generator.vision_qa._render_page_png", _fake_render())
    monkeypatch.setattr(
        "contest_generator.vision_qa.describe_image_cached",
        lambda png, mime, prompt, **kw: f"图中{answer}标注",
    )

    assert answer_figure_question(
        PDF_PATH, PROBLEM_TEXT, QUESTION, vision_api_key="sk-test"
    ) is None


def test_answer_figure_question_locate_failure_returns_none(monkeypatch):
    """定位失败（扫描件无文本层 / 题面不匹配）→ None，不渲染任何页。"""
    monkeypatch.setattr(
        "contest_generator.vision_qa.locate_topic_pages", lambda *a: None
    )
    monkeypatch.setattr(
        "contest_generator.vision_qa._render_page_png",
        lambda *a: pytest.fail("不应渲染"),
    )

    assert answer_figure_question(
        PDF_PATH, PROBLEM_TEXT, QUESTION, vision_api_key="sk-test"
    ) is None


def test_answer_figure_question_locate_error_returns_none(monkeypatch):
    """定位抛错（坏 PDF / 无 PyMuPDF）→ None，绝不抛出、绝不阻塞推荐。"""

    def broken_locate(pdf_path, topic_text):
        raise OSError("坏 PDF")

    monkeypatch.setattr(
        "contest_generator.vision_qa.locate_topic_pages", broken_locate
    )

    assert answer_figure_question(
        PDF_PATH, PROBLEM_TEXT, QUESTION, vision_api_key="sk-test"
    ) is None


def test_answer_figure_question_render_failure_skips_page(monkeypatch):
    """渲染失败页跳过（None → continue）；其余页照常回答。"""
    monkeypatch.setattr(
        "contest_generator.vision_qa.locate_topic_pages", _fake_locate((124, 126))
    )
    monkeypatch.setattr(
        "contest_generator.vision_qa._render_page_png", _fake_render(fail_pages=(124,))
    )
    calls = []

    def fake_describe(png, mime, prompt, **kwargs):
        calls.append(1)
        return "病房尺寸 60×40cm"

    monkeypatch.setattr(
        "contest_generator.vision_qa.describe_image_cached", fake_describe
    )

    assert answer_figure_question(
        PDF_PATH, PROBLEM_TEXT, QUESTION, vision_api_key="sk-test"
    ) == "病房尺寸 60×40cm"
    assert len(calls) == 1  # 只问了成功渲染的页


def test_answer_figure_question_vision_failure_returns_none(monkeypatch):
    """视觉调用抛错（网络 / 限流 / 未配置）→ None（绝不抛出、绝不让推荐崩）。"""
    monkeypatch.setattr(
        "contest_generator.vision_qa.locate_topic_pages", _fake_locate((124, 126))
    )
    monkeypatch.setattr("contest_generator.vision_qa._render_page_png", _fake_render())

    def fake_describe(png, mime, prompt, **kwargs):
        raise VisionError("视觉服务限流")

    monkeypatch.setattr(
        "contest_generator.vision_qa.describe_image_cached", fake_describe
    )

    assert answer_figure_question(
        PDF_PATH, PROBLEM_TEXT, QUESTION, vision_api_key="sk-test"
    ) is None


def test_answer_figure_question_joins_multi_page_answers(monkeypatch):
    """多页实质答案换行拼接；否定页不掺入。"""
    monkeypatch.setattr(
        "contest_generator.vision_qa.locate_topic_pages", _fake_locate((124, 127))
    )
    page_bytes = {124: b"p124", 125: b"p125", 126: b"p126"}

    def fake_render(path, page_no):
        return page_bytes[page_no]

    monkeypatch.setattr("contest_generator.vision_qa._render_page_png", fake_render)

    def fake_describe(png, mime, prompt, **kwargs):
        answers = {
            b"p124": "走廊宽度 30cm",
            b"p125": "图中没有相关信息",
            b"p126": "门口区域 5cm",
        }
        return answers[png]

    monkeypatch.setattr(
        "contest_generator.vision_qa.describe_image_cached", fake_describe
    )

    result = answer_figure_question(
        PDF_PATH, PROBLEM_TEXT, QUESTION, vision_api_key="sk-test"
    )

    assert result == "走廊宽度 30cm\n门口区域 5cm"  # 否定页被剔除，两段拼接


def test_answer_figure_question_all_pages_negative_returns_none(monkeypatch):
    """所有页都否定 / 失败 → None。"""
    monkeypatch.setattr(
        "contest_generator.vision_qa.locate_topic_pages", _fake_locate((124, 126))
    )
    monkeypatch.setattr("contest_generator.vision_qa._render_page_png", _fake_render())
    monkeypatch.setattr(
        "contest_generator.vision_qa.describe_image_cached",
        lambda png, mime, prompt, **kw: "图中没有相关信息",
    )

    assert answer_figure_question(
        PDF_PATH, PROBLEM_TEXT, QUESTION, vision_api_key="sk-test"
    ) is None
