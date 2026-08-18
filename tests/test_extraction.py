"""文本抽取（工单 06）：纯文本直通、PDF/docx 本地解析、损坏/加密文件明确报错。

样例文件（PDF/docx）由 tests/fakes.py 的构造器在 tmp_path 现场生成，
不提交二进制 fixture。
"""

import zipfile

import pytest

from contest_generator.extraction import ExtractionError, extract_file, extract_text
from tests.fakes import (
    make_blank_pdf,
    make_encrypted_pdf,
    make_sample_docx,
    make_sample_pdf,
)


# ---------------------------------------------------------------------------
# 纯文本输入直通
# ---------------------------------------------------------------------------


def test_plain_text_passes_through_unchanged():
    problem = "设计一个温度检测系统，检测范围 -10~50℃……"

    assert extract_text(problem) == problem


def test_plain_text_is_not_reinterpreted_as_file(tmp_path):
    """直通：即使字符串恰好是某个存在的文件路径，也不去读文件。"""
    target = tmp_path / "note.txt"
    target.write_text("文件内容", encoding="utf-8")

    assert extract_text(str(target)) == str(target)


# ---------------------------------------------------------------------------
# .txt 文本文件
# ---------------------------------------------------------------------------


def test_txt_file_read_as_plain_text(tmp_path):
    path = tmp_path / "problem.txt"
    path.write_text("题面：设计一个……", encoding="utf-8")

    assert extract_file(path) == "题面：设计一个……"


# ---------------------------------------------------------------------------
# .docx
# ---------------------------------------------------------------------------


def test_docx_extracted_with_paragraph_breaks(tmp_path):
    path = make_sample_docx(
        tmp_path / "problem.docx", ["第一段：题目要求", "第二段：评分标准"]
    )

    assert extract_file(path) == "第一段：题目要求\n第二段：评分标准"


def test_corrupted_docx_reports_clear_error(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"this is not a zip archive")

    with pytest.raises(ExtractionError, match="docx"):
        extract_file(path)


def test_docx_without_document_xml_reports_clear_error(tmp_path):
    path = tmp_path / "empty.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/styles.xml", "<x/>")

    with pytest.raises(ExtractionError, match="document.xml"):
        extract_file(path)


def test_docx_field_codes_are_excluded(tmp_path):
    """TOC/PAGE 等域指令（w:instrText）是格式信息，不应混入题目文字。"""
    path = tmp_path / "field.docx"
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        "<w:r><w:t>目录内容</w:t></w:r>"
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        "</w:p>"
        "</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)

    assert extract_file(path) == "目录内容"


def test_docx_without_any_text_reports_clear_error(tmp_path):
    path = make_sample_docx(tmp_path / "empty-text.docx", [])

    with pytest.raises(ExtractionError, match="文字"):
        extract_file(path)


# ---------------------------------------------------------------------------
# .pdf
# ---------------------------------------------------------------------------


def test_pdf_extracted(tmp_path):
    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest problem 2026")

    assert "Contest problem 2026" in extract_file(path)


def test_encrypted_pdf_reports_clear_error(tmp_path):
    path = make_encrypted_pdf(tmp_path / "secret.pdf")

    with pytest.raises(ExtractionError, match="加密"):
        extract_file(path)


def test_corrupted_pdf_reports_clear_error(tmp_path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.4 this is not a real pdf")

    with pytest.raises(ExtractionError):
        extract_file(path)


def test_scanned_pdf_without_text_reports_clear_error(tmp_path):
    """扫描件 / 纯图片 PDF 抽不出任何文字，报明确错误而非给空文。"""
    path = make_blank_pdf(tmp_path / "scanned.pdf")

    with pytest.raises(ExtractionError, match="文字"):
        extract_file(path)


# ---------------------------------------------------------------------------
# 视觉图注（工单 vision-eyes/02）：电子版 PDF 嵌入图 → [示意图N：描述]
# ---------------------------------------------------------------------------


class _FakeImage:
    """pypdf ImageFile 的测试替身（data / name）。"""

    def __init__(self, data: bytes, name: str = "Image1.png"):
        self.data = data
        self.name = name


class _FakePage:
    def __init__(self, images):
        self.images = images


class _FakeReader:
    """PdfReader 测试替身（pages 带假图）。"""

    def __init__(self, pages):
        self.pages = pages


def _fake_describe(description: str):
    """describe_image_cached 假件：记录调用，返回固定描述或抛错。"""

    def fake(image_bytes, mime, *, base_url="", api_key="", model=""):
        fake.calls.append((image_bytes, mime))
        if callable(description):
            return description(image_bytes, mime)
        return description

    fake.calls = []
    return fake


def test_image_mime_mapping():
    from contest_generator.extraction import _image_mime

    assert _image_mime("Image1.png") == "image/png"
    assert _image_mime("photo.JPG") == "image/jpeg"
    assert _image_mime("a.bmp") == "image/bmp"
    assert _image_mime("weird.xyz") == "image/png"  # 未知兜底


def test_join_notes_format():
    from contest_generator.extraction import _join_notes

    assert _join_notes(["布局 A", "电路 B"], 0) == "[示意图1：布局 A]\n[示意图2：电路 B]"
    assert _join_notes(["只有一张"], 2) == (
        "[示意图1：只有一张]\n（另有 2 张图跳过：超大或描述失败）"
    )
    assert _join_notes([], 3) == ""


def test_pdf_image_notes_describes_embedded_images(monkeypatch, tmp_path):
    """电子版 PDF 嵌入图 → 逐张描述 → 图注段（[示意图N：…] 逐行）。"""
    from contest_generator import extraction

    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest 2026")
    fake_describe = _fake_describe(lambda data, mime: f"描述:{len(data)}")
    monkeypatch.setattr(extraction, "PdfReader", lambda _p: _FakeReader([
        _FakePage([_FakeImage(b"img-a", "a.png"), _FakeImage(b"img-b", "b.jpg")]),
        _FakePage([_FakeImage(b"img-c", "c.png")]),
    ]))
    monkeypatch.setattr(extraction, "describe_image_cached", fake_describe)

    notes = extraction._pdf_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model="glm-4v-flash"
    )
    assert notes == "[示意图1：描述:5]\n[示意图2：描述:5]\n[示意图3：描述:5]"
    # mime 按后缀推断（jpg → image/jpeg）
    assert fake_describe.calls[1][1] == "image/jpeg"


def test_pdf_image_notes_caps_at_eight_and_marks_skips(monkeypatch, tmp_path):
    """上限守卫：>8 张截断；超大 / 失败图跳过并标注。"""
    from contest_generator import extraction

    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest")
    images = [_FakeImage(b"small") for _ in range(9)]
    images[0] = _FakeImage(b"x" * (4 * 1024 * 1024 + 1))  # 超大
    monkeypatch.setattr(extraction, "PdfReader", lambda _p: _FakeReader([
        _FakePage(images),
    ]))
    monkeypatch.setattr(
        extraction, "describe_image_cached", _fake_describe("图")
    )

    notes = extraction._pdf_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model=""
    )
    lines = notes.splitlines()
    assert len(lines) == 9  # 8 张描述 + 1 行跳过标注
    assert lines[0] == "[示意图1：图]"
    assert "另有 1 张图跳过" in lines[-1]


def test_pdf_image_notes_degrades_to_empty_on_failure(monkeypatch, tmp_path):
    """视觉全失败（未配置 / 网络 / 解析）→ 空串（调用方降级，不拖垮抽取）。"""
    from contest_generator import extraction
    from contest_generator.vision import VisionNotConfiguredError

    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest")
    monkeypatch.setattr(extraction, "PdfReader", lambda _p: _FakeReader([
        _FakePage([_FakeImage(b"img")]),
    ]))
    # 未配置：describe 抛 VisionNotConfiguredError → 降级空串
    def not_configured(data, mime, **kwargs):
        raise VisionNotConfiguredError("视觉通道未配置")

    monkeypatch.setattr(extraction, "describe_image_cached", not_configured)
    assert (
        extraction._pdf_image_notes(
            path, vision_base_url="", vision_api_key="", vision_model=""
        )
        == ""
    )
    # 单张失败：跳过该张，其余照常
    def flaky(data, mime, **kwargs):
        raise ValueError("网络瞬断")

    monkeypatch.setattr(extraction, "describe_image_cached", flaky)
    assert (
        extraction._pdf_image_notes(
            path, vision_base_url="", vision_api_key="sk-test", vision_model=""
        )
        == ""
    )
    # PDF 结构损坏：reader 构造失败 → 空串
    monkeypatch.setattr(extraction, "PdfReader", lambda _p: (_ for _ in ()).throw(ValueError("坏 PDF")))
    assert (
        extraction._pdf_image_notes(
            path, vision_base_url="", vision_api_key="sk-test", vision_model=""
        )
        == ""
    )


def test_extract_pdf_with_image_notes_appends_notes(monkeypatch, tmp_path):
    """文本 + 图注拼接（尾部追加）；无图注 = 与 extract_file 一致。"""
    from contest_generator import extraction

    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest problem 2026")
    monkeypatch.setattr(
        extraction,
        "_pdf_image_notes",
        lambda *a, **k: "[示意图1：电路连接 A-B]",
    )
    text = extraction.extract_pdf_with_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model=""
    )
    assert text.endswith("[示意图1：电路连接 A-B]")
    assert "Contest problem 2026" in text

    # 无图注 → 纯文本（与 extract_file 逐字节一致）
    monkeypatch.setattr(extraction, "_pdf_image_notes", lambda *a, **k: "")
    assert (
        extraction.extract_pdf_with_image_notes(
            path, vision_base_url="", vision_api_key="", vision_model=""
        )
        == extract_file(path)
    )


# ---------------------------------------------------------------------------
# 不支持的格式与缺失文件
# ---------------------------------------------------------------------------


def test_unsupported_file_type_reports_clear_error(tmp_path):
    """旧版 Word 二进制 .doc 无法本地解析，给出明确错误而非崩溃。"""
    path = tmp_path / "problem.doc"
    path.write_bytes(b"old word binary")

    with pytest.raises(ExtractionError, match="不支持"):
        extract_file(path)


def test_missing_file_reports_clear_error(tmp_path):
    with pytest.raises(ExtractionError, match="不存在"):
        extract_file(tmp_path / "nope.pdf")
