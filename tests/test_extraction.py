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
