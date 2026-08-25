"""文本抽取（工单 06）：纯文本直通、PDF/docx 本地解析、损坏/加密文件明确报错。

样例文件（PDF/docx）由 tests/fakes.py 的构造器在 tmp_path 现场生成，
不提交二进制 fixture。
"""

import io
import zipfile
from pathlib import Path

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


def testpdf_image_notes_describes_embedded_images(monkeypatch, tmp_path):
    """电子版 PDF 嵌入图 → 逐张描述 → 图注段（[示意图N：…] 逐行）。"""
    from contest_generator import extraction

    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest 2026")
    fake_describe = _fake_describe(lambda data, mime: f"描述:{len(data)}")
    monkeypatch.setattr(extraction, "PdfReader", lambda _p: _FakeReader([
        _FakePage([_FakeImage(b"img-a", "a.png"), _FakeImage(b"img-b", "b.jpg")]),
        _FakePage([_FakeImage(b"img-c", "c.png")]),
    ]))
    monkeypatch.setattr(extraction, "describe_image_cached", fake_describe)

    notes = extraction.pdf_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model="glm-4.6v-flash"
    )
    assert notes == "[示意图1：描述:5]\n[示意图2：描述:5]\n[示意图3：描述:5]"
    # mime 按后缀推断（jpg → image/jpeg）
    assert fake_describe.calls[1][1] == "image/jpeg"


def testpdf_image_notes_caps_at_eight_and_marks_skips(monkeypatch, tmp_path):
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

    notes = extraction.pdf_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model=""
    )
    lines = notes.splitlines()
    assert len(lines) == 9  # 8 张描述 + 1 行跳过标注
    assert lines[0] == "[示意图1：图]"
    assert "另有 1 张图跳过" in lines[-1]


def _pil_image_bytes(fmt: str) -> bytes:
    """PIL 现场生成指定格式小图字节（BMP / JPEG2000 等，测试用）。"""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 30, 30)).save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize(
    "fmt,name",
    [("BMP", "a.bmp"), ("JPEG2000", "a.jp2")],
    ids=["bmp", "jpeg2000"],
)
def testpdf_image_notes_transcodes_non_supported_embedded_images(
    fmt, name, monkeypatch, tmp_path
):
    """PDF 内嵌 DeepSeek 不支持格式（BMP / JPEG2000）：转 PNG 后发送
    （工单 vision-format-transcode/01）；旧实现 BMP 跳过 / JPEG2000 兜底
    直发原字节 → 红证。Pillow 无 JPEG2000 支持时精确 skip 防脆。"""
    from contest_generator import extraction

    if fmt == "JPEG2000":
        from PIL import Image

        if "JPEG2000" not in Image.registered_extensions().values():
            pytest.skip("Pillow 无 JPEG2000 支持（缺 OpenJPEG）")
    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest")
    fake_describe = _fake_describe("图")
    src_bytes = _pil_image_bytes(fmt)
    monkeypatch.setattr(extraction, "PdfReader", lambda _p: _FakeReader([
        _FakePage([_FakeImage(src_bytes, name), _FakeImage(b"img-png", "b.png")]),
    ]))
    monkeypatch.setattr(extraction, "describe_image_cached", fake_describe)

    notes = extraction.pdf_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model=""
    )
    assert notes == "[示意图1：图]\n[示意图2：图]"  # 非直发格式不再跳过
    from PIL import Image

    sent, mime = fake_describe.calls[0]
    assert mime == "image/png"
    with Image.open(io.BytesIO(sent)) as im:
        assert im.format == "PNG"  # 旧实现跳过/兜底直发 → 红
    assert fake_describe.calls[1] == (b"img-png", "image/png")


def testpdf_image_notes_skips_undecodable_non_supported_image(monkeypatch, tmp_path):
    """非支持格式且 PIL 无法解码（垃圾字节 + .bmp 后缀）→ 跳过计尾部标注。"""
    from contest_generator import extraction

    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest")
    fake_describe = _fake_describe("图")
    monkeypatch.setattr(extraction, "PdfReader", lambda _p: _FakeReader([
        _FakePage([_FakeImage(b"not-an-image", "a.bmp"), _FakeImage(b"img-png", "b.png")]),
    ]))
    monkeypatch.setattr(extraction, "describe_image_cached", fake_describe)

    notes = extraction.pdf_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model=""
    )
    assert notes == "[示意图1：图]\n（另有 1 张图跳过：超大或描述失败）"
    assert fake_describe.calls == [(b"img-png", "image/png")]


def testpdf_image_notes_all_images_undecodable_returns_empty(monkeypatch, tmp_path):
    """全部嵌入图无法解码 → 空串（_join_notes 空 notes 语义：跳过计数不
    呈现——既有行为边界，记录于工单 vision-format-transcode/01）。"""
    from contest_generator import extraction

    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest")
    fake_describe = _fake_describe("图")
    monkeypatch.setattr(extraction, "PdfReader", lambda _p: _FakeReader([
        _FakePage([_FakeImage(b"not-an-image", "a.bmp")]),
    ]))
    monkeypatch.setattr(extraction, "describe_image_cached", fake_describe)

    assert (
        extraction.pdf_image_notes(
            path, vision_base_url="", vision_api_key="sk-test", vision_model=""
        )
        == ""
    )
    assert fake_describe.calls == []


def testpdf_image_notes_degrades_to_empty_on_failure(monkeypatch, tmp_path):
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
        extraction.pdf_image_notes(
            path, vision_base_url="", vision_api_key="", vision_model=""
        )
        == ""
    )
    # 单张失败：跳过该张，其余照常
    def flaky(data, mime, **kwargs):
        raise ValueError("网络瞬断")

    monkeypatch.setattr(extraction, "describe_image_cached", flaky)
    assert (
        extraction.pdf_image_notes(
            path, vision_base_url="", vision_api_key="sk-test", vision_model=""
        )
        == ""
    )
    # PDF 结构损坏：reader 构造失败 → 空串
    monkeypatch.setattr(extraction, "PdfReader", lambda _p: (_ for _ in ()).throw(ValueError("坏 PDF")))
    assert (
        extraction.pdf_image_notes(
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
        "pdf_image_notes",
        lambda *a, **k: "[示意图1：电路连接 A-B]",
    )
    text = extraction.extract_pdf_with_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model=""
    )
    assert text.endswith("[示意图1：电路连接 A-B]")
    assert "Contest problem 2026" in text

    # 无图注 → 纯文本（与 extract_file 逐字节一致）
    monkeypatch.setattr(extraction, "pdf_image_notes", lambda *a, **k: "")
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


def test_extract_image_rejects_bmp_with_actionable_message(tmp_path, monkeypatch):
    """.bmp 直接上传 → 入口拦截，友好中文报错引导转存 PNG/JPEG
    （工单 vision-deepseek-native/01：DeepSeek 视觉不支持 BMP，不浪费
    一次注定失败的视觉调用）。"""
    from contest_generator import extraction

    path = tmp_path / "图.bmp"
    path.write_bytes(b"BMfake-bmp")
    monkeypatch.setattr(
        extraction, "describe_image_cached", lambda *a, **k: "不该走到这里"
    )

    with pytest.raises(ExtractionError) as excinfo:
        extraction.extract_image(
            path, vision_base_url="", vision_api_key="sk-test", vision_model=""
        )
    message = str(excinfo.value)
    assert "BMP" in message
    assert "PNG" in message or "JPEG" in message  # 引导转存方向



# ---------------------------------------------------------------------------
# 矢量图标注文字布局（工单 topic-vision-notes/03）：visitor_text 带坐标 →
# 复合矩阵还原页面坐标 → 行聚类 → 「图N」标题窗口内短行 → [图N 标注] 段
# ---------------------------------------------------------------------------


def _fake_visitor_page(segments):
    """假页：extract_text(visitor_text=fn) 直接喂带坐标段（坐标已含复合变换）。"""

    class _FakePage:
        def extract_text(self, visitor_text=None):
            cm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
            for x, y, text in segments:
                tm = (1.0, 0.0, 0.0, 1.0, x, y)
                visitor_text(text, cm, tm, None, 10.0)

    return _FakePage()


def _figure_segments():
    """2026C 图1 形态的段集合：正文长行 + 图内短标注 + 标题行（图在页底）。"""
    return [
        (120.0, 460.0, "一、"),                      # 正文标题（窗口外）
        (160.0, 440.0, "任务"),                      # 正文标题（窗口外）
        (120.0, 400.0, "设计制作一套基于无线通信的数字钥匙实验系统……"),  # 正文长行
        (150.0, 350.0, "感应区 迎宾区 开锁区"),        # 图内标签行
        (160.0, 335.0, "-45°"),                      # 左角度
        (230.0, 335.0, "门锁"),                      # 图中央标签
        (290.0, 335.0, "60cm"),                      # 尺寸
        (200.0, 300.0, "37"),                        # 高度
        (160.0, 270.0, "α"),                        # 变量
        (150.0, 245.0, "15°"),                       # 右角度（下方）
        (120.0, 100.0, "图"),                        # 标题行（拆段）
        (135.0, 100.0, "1"),
        (145.0, 100.0, "数字钥匙实验系统功能示意图"),
    ]


def test_figure_annotation_block_rebuilds_layout():
    """段集合 → [图1 标注] 布局块：窗口内短行、按 y 降序、行内按 x 排序。"""
    from contest_generator.extraction import _figure_annotation_block

    block = _figure_annotation_block(_figure_segments())

    assert block.startswith("[图1 标注]\n")
    lines = block.split("\n")[1:]
    assert "感应区 迎宾区 开锁区" in lines[0]          # 最上方标签行
    assert "-45° 门锁 60cm" in lines[1]                # 行内按 x 排序（-45° < 门锁 < 60cm）
    assert "37" in lines[2]
    assert "α" in lines[3]
    assert "15°" in lines[4]
    assert len(lines) == 5
    # 正文（长行 / 窗口外标题）不进标注区
    assert "一、" not in block
    assert "任务" not in block
    assert "设计制作" not in block
    assert "功能示意图" not in block  # 标题行自身排除


def test_figure_annotation_block_no_title_returns_empty():
    """无「图N」标题行 → 空串。"""
    from contest_generator.extraction import _figure_annotation_block

    assert _figure_annotation_block([(100.0, 300.0, "只有正文")]) == ""


def test_figure_annotation_block_multiple_figures():
    """一页多图 → 每图独立段。"""
    from contest_generator.extraction import _figure_annotation_block

    segs = [
        (100.0, 600.0, "图"), (110.0, 600.0, "1"), (120.0, 600.0, "示意图一"),
        (150.0, 570.0, "A点"), (150.0, 550.0, "B点"),
        (100.0, 400.0, "图"), (110.0, 400.0, "2"), (120.0, 400.0, "示意图二"),
        (150.0, 370.0, "10cm"), (150.0, 350.0, "20cm"),
    ]
    block = _figure_annotation_block(segs)

    assert "[图1 标注]" in block
    assert "[图2 标注]" in block
    assert "A点" in block and "B点" in block
    assert "10cm" in block and "20cm" in block


def test_figure_annotation_block_excludes_fake_titles_and_page_numbers():
    """伪标题（正文引用 / 序号行 / 表格行的"图N"不在行首）与页码行不产出块。"""
    from contest_generator.extraction import _figure_annotation_block

    segs = [
        (120.0, 700.0, "数字钥匙实验系统的功能示意图如图"),  # 正文引用（图不在行首）
        (300.0, 700.0, "1"), (320.0, 700.0, "所示，开锁区为1m以内"),
        (120.0, 650.0, "8．可使用图"), (200.0, 650.0, "2"), (220.0, 650.0, "喷绘铺设测试场地"),
        (120.0, 600.0, "设计报告"), (220.0, 600.0, "电路与程序设计"), (350.0, 600.0, "电路图"), (420.0, 600.0, "6"),
        (120.0, 300.0, "C"), (140.0, 300.0, "-"), (155.0, 300.0, "1"), (170.0, 300.0, "/"), (185.0, 300.0, "4"),  # 页码行
        (100.0, 100.0, "图"), (110.0, 100.0, "1"), (125.0, 100.0, "功能示意图"),  # 真标题
        (150.0, 80.0, "60cm"),  # 图内标注
    ]
    block = _figure_annotation_block(segs)

    assert block == "[图1 标注]\n60cm"  # 只有真标题 + 图内标注；伪标题行与页码行全排除


def test_pdf_figure_annotations_extracts_via_visitor(monkeypatch, tmp_path):
    """整链：假 PdfReader（visitor 喂段）→ 标注布局文本；坏 PDF → 空串。"""
    from contest_generator import extraction

    class _FakeReader:
        def __init__(self, pages):
            self.pages = pages

    path = tmp_path / "fig.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader([_fake_visitor_page(_figure_segments())]),
    )

    text = extraction.pdf_figure_annotations(path)

    assert text.startswith("[图1 标注]\n")
    assert "-45° 门锁 60cm" in text

    # 坏 PDF：reader 构造失败 → 空串（调用方降级）
    monkeypatch.setattr(
        extraction, "PdfReader", lambda _p: (_ for _ in ()).throw(ValueError("坏 PDF"))
    )
    assert extraction.pdf_figure_annotations(path) == ""


def test_pdf_figure_annotations_deals_scaled_coordinates(tmp_path):
    """坐标经缩放矩阵（矢量图文本）→ 复合 cm×tm 还原为页面坐标后可聚类。"""
    from contest_generator import extraction

    class _FakeReader:
        def __init__(self, pages):
            self.pages = pages

    class _ScaledPage:
        """visitor 喂原始 tm（图内文字经缩放），cm 带缩放——需复合还原。"""

        def extract_text(self, visitor_text=None):
            cm = (10.0, 0.0, 0.0, 10.0, 0.0, 0.0)      # 缩放 10x
            tm = (1.0, 0.0, 0.0, 1.0, 10.0, 20.0)      # 平移 (10, 20) → 还原 (100, 200)
            visitor_text("60cm", cm, tm, None, 10.0)
            tm = (1.0, 0.0, 0.0, 1.0, 10.0, 30.0)      # 平移 (10, 30) → 还原 (100, 300)
            visitor_text("图", cm, tm, None, 10.0)
            visitor_text("1", cm, tm, None, 10.0)
            visitor_text("标题", cm, tm, None, 10.0)   # 同行 → 标题行
            cm2 = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
            tm2 = (1.0, 0.0, 0.0, 1.0, 100.0, 600.0)   # 正文远在标题上方
            visitor_text("这是很长的正文段落……" * 3, cm2, tm2, None, 10.0)

    path = tmp_path / "scaled.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    original = extraction.PdfReader
    extraction.PdfReader = lambda _p: _FakeReader([_ScaledPage()])
    try:
        text = extraction.pdf_figure_annotations(path)
    finally:
        extraction.PdfReader = original

    assert "60cm" in text
    assert text.startswith("[图1 标注]\n")
    assert "标题" not in text   # 标题行自身排除
    assert "正文" not in text


# ---------------------------------------------------------------------------
# 页范围定位与提取（工单 topic-vision-pages/01）：题面页定位 + 限定页提取——
# 共享汇总 PDF 赛题补图注的基础能力（2021F 图1 缺失根因修复）
# ---------------------------------------------------------------------------


class _TextPage:
    """假页：extract_text() 返回纯文本（locate_topic_pages 的搜索目标）。"""

    def __init__(self, text):
        self._text = text

    def extract_text(self, visitor_text=None):
        if visitor_text is not None:
            visitor_text(
                self._text, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
                None, 10.0,
            )
            return None
        return self._text


def test_locate_topic_pages_finds_topic_page(monkeypatch, tmp_path):
    """题面独特文本（去空白后前 20 字符）命中页 → 该页起 2 页范围（1-based）。"""
    from contest_generator import extraction

    path = tmp_path / "joint.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader(
            [
                _TextPage("2019A 题面正文……另一个赛题"),
                _TextPage("智能送药小车（F题）【本科组】一 任务 设计并制作智能送药小车……"),
                _TextPage("图1 院区结构示意图 60cm 40cm 30cm"),
            ]
        ),
    )

    assert extraction.locate_topic_pages(
        path, "智能送药小车（F题）【本科组】一 任务"
    ) == (2, 4)


def test_locate_topic_pages_miss_returns_none(monkeypatch, tmp_path):
    """题面文本不在 PDF（扫描件无文本层 / 不匹配）→ None（调用方跳过）。"""
    from contest_generator import extraction

    path = tmp_path / "joint.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(
        extraction, "PdfReader", lambda _p: _FakeReader([_TextPage("别的赛题内容")])
    )

    assert extraction.locate_topic_pages(path, "不存在的题面文本") is None


def test_locate_topic_pages_blank_or_bad_pdf(monkeypatch, tmp_path):
    """空白题面不搜；坏 PDF → None 不抛（防御）。"""
    from contest_generator import extraction

    path = tmp_path / "bad.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    assert extraction.locate_topic_pages(path, "   \n ") is None
    monkeypatch.setattr(
        extraction, "PdfReader", lambda _p: (_ for _ in ()).throw(ValueError("坏 PDF"))
    )
    assert extraction.locate_topic_pages(path, "智能送药小车") is None


def test_pdf_figure_annotations_pages_filter(monkeypatch, tmp_path):
    """pages 限定扫描页：第 1 页图1 出、第 2 页图2 不出；None = 全部（现状）。"""
    from contest_generator import extraction

    path = tmp_path / "fig.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    page1 = _fake_visitor_page(
        [(100.0, 100.0, "图"), (110.0, 100.0, "1"), (120.0, 100.0, "第一页图"),
         (150.0, 80.0, "60cm")]
    )
    page2 = _fake_visitor_page(
        [(100.0, 100.0, "图"), (110.0, 100.0, "2"), (120.0, 100.0, "第二页图"),
         (150.0, 80.0, "40cm")]
    )
    monkeypatch.setattr(extraction, "PdfReader", lambda _p: _FakeReader([page1, page2]))

    filtered = extraction.pdf_figure_annotations(path, pages=[1])
    assert filtered.startswith("[图1 标注]") and "60cm" in filtered
    assert "40cm" not in filtered  # 第 2 页不扫

    both = extraction.pdf_figure_annotations(path, pages=None)
    assert "[图1 标注]" in both and "[图2 标注]" in both


def test_pdf_image_notes_pages_filter(monkeypatch, tmp_path):
    """pages 限定页：只描述限定页的嵌入图；None = 全部（现状）。"""
    from contest_generator import extraction

    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest")
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader(
            [
                _FakePage([_FakeImage(b"img-a", "a.png")]),
                _FakePage([_FakeImage(b"img-b", "b.png")]),
            ]
        ),
    )
    fake_describe = _fake_describe(lambda data, mime: f"描述:{data.decode()}")
    monkeypatch.setattr(extraction, "describe_image_cached", fake_describe)

    notes = extraction.pdf_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model="m", pages=[2]
    )
    assert notes == "[示意图1：描述:img-b]"
    assert [call[0] for call in fake_describe.calls] == [b"img-b"]  # 只调第 2 页图


# ---------------------------------------------------------------------------
# 渲染视觉图注（工单 topic-vision-render/01）：矢量图 PDF 页渲染 → 视觉描述
# ---------------------------------------------------------------------------


def _render_fake(description):
    """describe_image_cached 假件（渲染场景专用）：记录全 kwargs，返回固定描述或抛错。"""

    def fake(image_bytes, mime, prompt, **kwargs):
        fake.calls.append((image_bytes, mime, prompt, kwargs))
        if callable(description):
            return description(image_bytes, mime)
        return description

    fake.calls = []
    return fake


class _FakePixmap:
    def tobytes(self, fmt):
        return b"PNG-DATA"


class _FakeFitzPage:
    def get_pixmap(self, matrix):
        self.matrix = matrix
        return _FakePixmap()


class _FakeFitzDoc:
    def __init__(self):
        self._pages = {}
        self.index = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __getitem__(self, index):
        self.index = index
        if index not in self._pages:
            self._pages[index] = _FakeFitzPage()
        return self._pages[index]


class _FakeFitz:
    """fitz 测试替身：open → doc[page_no-1] → get_pixmap(Matrix(2,2)) → PNG。"""

    last_open = None
    last_doc = None

    @classmethod
    def open(cls, path):
        cls.last_open = str(path)
        cls.last_doc = _FakeFitzDoc()
        return cls.last_doc

    @staticmethod
    def Matrix(a, b):
        return (a, b)


def test_render_page_png_without_fitz_returns_none(monkeypatch):
    """无 PyMuPDF（import 失败）→ None（渲染路径静默降级）。"""
    import sys

    from contest_generator import extraction

    monkeypatch.setitem(sys.modules, "fitz", None)
    assert extraction._render_page_png(Path("vec.pdf"), 1) is None


def test_render_page_png_renders_via_fitz(monkeypatch):
    """fitz 可用：第 page_no 页（1-based）渲染成 PNG 字节。"""
    import sys

    from contest_generator import extraction

    monkeypatch.setitem(sys.modules, "fitz", _FakeFitz)
    png = extraction._render_page_png(Path("vec.pdf"), 2)
    assert png == b"PNG-DATA"
    assert _FakeFitz.last_open == str(Path("vec.pdf"))
    assert _FakeFitz.last_doc.index == 1  # 1-based → fitz 0-based 索引
    assert _FakeFitz.last_doc[1].matrix == (2.0, 2.0)  # PAGE_RENDER_SCALE


def test_render_page_png_bad_pdf_returns_none(monkeypatch):
    """fitz.open 失败（坏 PDF）→ None 不抛。"""
    import sys

    from contest_generator import extraction

    class _BadFitz:
        @staticmethod
        def open(path):
            raise RuntimeError("坏 PDF")

        @staticmethod
        def Matrix(a, b):
            return (a, b)

    monkeypatch.setitem(sys.modules, "fitz", _BadFitz)
    assert extraction._render_page_png(Path("bad.pdf"), 1) is None


def test_page_figure_label_extracts_title_number():
    """页文本层行首「图N」标题 → 图号；正文引用 / 无文本层 → None。"""
    from contest_generator.extraction import _page_figure_label

    assert _page_figure_label(_TextPage("图1 院区结构示意图\n正文行")) == "1"
    assert _page_figure_label(_TextPage("  图 2 系统框图")) == "2"
    assert _page_figure_label(_TextPage("如图1所示，小车沿走廊行驶")) is None  # 行内引用
    assert _page_figure_label(_TextPage("")) is None  # 无文本层


def test_pdf_page_render_notes_formats_figure_notes(monkeypatch, tmp_path):
    """渲染页 → 视觉描述 → [图N 标注：…] 逐行；真实图号优先 + 顺序编号兜底。"""
    from contest_generator import extraction

    path = tmp_path / "vec.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(
        extraction, "_render_page_png", lambda p, n: b"PNG-%d" % n
    )
    fake = _render_fake(lambda data, mime: "走廊 60cm 红实线走向")
    monkeypatch.setattr(extraction, "describe_image_cached", fake)
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader(
            [_TextPage("图1 院区结构示意图"), _TextPage("正文文字无图")]
        ),
    )

    notes = extraction.pdf_page_render_notes(
        path, vision_base_url="https://api.deepseek.com", vision_api_key="sk", vision_model="m",
        detail_qa=False,
    )
    # 页1 真实图号 1；页2 无图标题 → 顺序编号（第 2 个产出 → 2）
    assert notes == (
        "[图1 标注：走廊 60cm 红实线走向]\n"
        "[图2 标注：走廊 60cm 红实线走向]"
    )
    assert fake.calls[0][1] == "image/png"  # mime
    assert fake.calls[0][2] == extraction.RENDER_DESCRIBE_PROMPT  # 渲染场景提示词
    assert fake.calls[0][3] == {
        "base_url": "https://api.deepseek.com",
        "api_key": "sk",
        "model": "m",
    }  # 视觉参数透传


def test_pdf_page_render_notes_detail_qa_merges(monkeypatch, tmp_path):
    """渲染图注默认开启精注记（工单 vision-detail-qa/01）：二轮细节合并进
    [图N 标注：…]，每页两次视觉调用。"""
    from contest_generator import extraction

    path = tmp_path / "vec.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(extraction, "_render_page_png", lambda p, n: b"pg1")
    fake = _render_fake(
        lambda data, mime: "布局完整描述：走廊布局" if len(fake.calls) == 1 else "尺寸 60cm；红色实线"
    )
    monkeypatch.setattr(extraction, "describe_image_cached", fake)
    monkeypatch.setattr(
        extraction, "PdfReader", lambda _p: _FakeReader([_TextPage("")])
    )

    notes = extraction.pdf_page_render_notes(
        path, vision_base_url="", vision_api_key="sk", vision_model="m"
    )
    assert notes == "[图1 标注：布局完整描述：走廊布局；细节补充：尺寸 60cm；红色实线]"
    assert len(fake.calls) == 2


def test_pdf_page_render_notes_filters_no_figure_pages(monkeypatch, tmp_path):
    """无实质内容 / 否定词描述（无图页、正文页）→ 丢弃不写回。"""
    from contest_generator import extraction

    path = tmp_path / "vec.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(extraction, "_render_page_png", lambda p, n: b"pg%d" % n)
    fake = _render_fake(
        lambda data, mime: {
            b"pg1": "无实质内容",
            b"pg2": "页面只有文字，没有示意图",
            b"pg3": "布局完整描述：走廊与病房",
        }[data]
    )
    monkeypatch.setattr(extraction, "describe_image_cached", fake)
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader([_TextPage(""), _TextPage(""), _TextPage("")]),
    )

    notes = extraction.pdf_page_render_notes(
        path, vision_base_url="", vision_api_key="sk", vision_model="m",
        detail_qa=False,
    )
    assert notes == "[图1 标注：布局完整描述：走廊与病房]"  # 第 1 个产出 → 顺序号 1


def test_pdf_page_render_notes_skips_failed_pages(monkeypatch, tmp_path):
    """渲染失败 / 视觉失败 → 跳过该页；全部失败 → 空串（绝不抛）。"""
    from contest_generator import extraction

    path = tmp_path / "vec.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(extraction, "_render_page_png", lambda p, n: b"x" if n == 2 else None)
    fake = _render_fake(lambda data, mime: "这是一段完整的布局描述")
    monkeypatch.setattr(extraction, "describe_image_cached", fake)
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader([_TextPage(""), _TextPage(""), _TextPage("")]),
    )
    notes = extraction.pdf_page_render_notes(
        path, vision_base_url="", vision_api_key="sk", vision_model="m",
        detail_qa=False,
    )
    assert notes == "[图1 标注：这是一段完整的布局描述]"  # 只页2 产出（第 1 个）

    # 视觉全失败 → 空串
    def failing(data, mime):
        from contest_generator.vision import VisionError

        raise VisionError("视觉失败")

    monkeypatch.setattr(extraction, "describe_image_cached", _render_fake(failing))
    assert (
        extraction.pdf_page_render_notes(
            path, vision_base_url="", vision_api_key="sk", vision_model="m"
        )
        == ""
    )


def test_pdf_page_render_notes_rendering_exception_skips_page(monkeypatch, tmp_path):
    """渲染函数抛异常（防御外异常）→ 跳过该页，绝不外泄。"""
    from contest_generator import extraction

    path = tmp_path / "vec.pdf"
    path.write_bytes(b"%PDF-1.4 fake")

    def exploding_render(p, n):
        if n == 1:
            raise RuntimeError("渲染器爆炸")
        return b"x"

    monkeypatch.setattr(extraction, "_render_page_png", exploding_render)
    monkeypatch.setattr(
        extraction, "describe_image_cached", _render_fake("这是一段完整的布局描述")
    )
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader([_TextPage(""), _TextPage("")]),
    )
    notes = extraction.pdf_page_render_notes(
        path, vision_base_url="", vision_api_key="sk", vision_model="m",
        detail_qa=False,
    )
    assert notes == "[图1 标注：这是一段完整的布局描述]"  # 页1 跳过，页2 照常


def test_pdf_page_render_notes_avoids_label_collisions(monkeypatch, tmp_path):
    """图号防撞：真实图号不连续时顺序兜底跳过已占用号。"""
    from contest_generator import extraction

    path = tmp_path / "vec.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(extraction, "_render_page_png", lambda p, n: b"x")
    monkeypatch.setattr(
        extraction, "describe_image_cached", _render_fake("这是一段完整的布局描述")
    )
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader(
            [
                _TextPage("图1 结构示意"),  # 真实图号 1
                _TextPage("图3 布局示意"),  # 真实图号 3（不连续）
                _TextPage(""),  # 无文本层 → 顺序兜底
            ]
        ),
    )
    notes = extraction.pdf_page_render_notes(
        path, vision_base_url="", vision_api_key="sk", vision_model="m",
        detail_qa=False,
    )
    lines = notes.splitlines()
    assert lines[0].startswith("[图1 标注：")
    assert lines[1].startswith("[图3 标注：")
    # 顺序兜底：已用 {1,3}，len+1=3 被占用 → 取 2
    assert lines[2].startswith("[图2 标注：")
    assert len(lines) == 3


def test_pdf_page_render_notes_skips_duplicate_real_label(monkeypatch, tmp_path):
    """两页同真实图号（如都是「图1」）→ 后者跳过，宁缺毋滥。"""
    from contest_generator import extraction

    path = tmp_path / "vec.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(extraction, "_render_page_png", lambda p, n: b"x")
    monkeypatch.setattr(
        extraction, "describe_image_cached", _render_fake("这是一段完整的布局描述")
    )
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader([_TextPage("图1 结构示意"), _TextPage("图1 重复标题")]),
    )
    notes = extraction.pdf_page_render_notes(
        path, vision_base_url="", vision_api_key="sk", vision_model="m",
        detail_qa=False,
    )
    assert notes.count("[图") == 1  # 第二个「图1」被跳过


def test_pdf_page_render_notes_pages_filter(monkeypatch, tmp_path):
    """pages 限定（1-based）：只渲染限定页。"""
    from contest_generator import extraction

    path = tmp_path / "vec.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    rendered = []

    def fake_render(p, n):
        rendered.append(n)
        return b"x"

    monkeypatch.setattr(extraction, "_render_page_png", fake_render)
    monkeypatch.setattr(extraction, "describe_image_cached", _render_fake("这是一段完整的布局描述"))
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader([_TextPage(""), _TextPage(""), _TextPage("")]),
    )
    notes = extraction.pdf_page_render_notes(
        path, vision_base_url="", vision_api_key="sk", vision_model="m", pages=[2],
        detail_qa=False,
    )
    assert rendered == [2]
    assert notes == "[图1 标注：这是一段完整的布局描述]"


def test_pdf_page_render_notes_caps_at_eight(monkeypatch, tmp_path):
    """产出上限 MAX_IMAGE_NOTES=8：第 9 页不再渲染。"""
    from contest_generator import extraction

    path = tmp_path / "vec.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    rendered = []
    monkeypatch.setattr(
        extraction, "_render_page_png", lambda p, n: rendered.append(n) or b"x"
    )
    monkeypatch.setattr(extraction, "describe_image_cached", _render_fake("这是一段完整的布局描述"))
    monkeypatch.setattr(
        extraction,
        "PdfReader",
        lambda _p: _FakeReader([_TextPage("") for _ in range(9)]),
    )
    notes = extraction.pdf_page_render_notes(
        path, vision_base_url="", vision_api_key="sk", vision_model="m",
        detail_qa=False,
    )
    assert notes.count("[图") == 8
    assert len(rendered) == 8  # 第 9 页未渲染


def test_pdf_page_render_notes_bad_pdf_returns_empty(monkeypatch, tmp_path):
    """坏 PDF → 空串不抛。"""
    from contest_generator import extraction

    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a pdf")
    monkeypatch.setattr(extraction, "_render_page_png", lambda p, n: b"x")
    monkeypatch.setattr(extraction, "describe_image_cached", _render_fake("这是一段完整的布局描述"))
    monkeypatch.setattr(
        extraction, "PdfReader", lambda _p: (_ for _ in ()).throw(ValueError("坏 PDF"))
    )
    assert (
        extraction.pdf_page_render_notes(
            path, vision_base_url="", vision_api_key="sk", vision_model="m"
        )
        == ""
    )


# ---------------------------------------------------------------------------
# 问答式精注记（工单 vision-detail-qa/01）：第一轮描述基础上追问细节，
# 补偿图→文字转译的信息损耗（数字标注 / 型号 / 颜色线型 / 引脚号）
# ---------------------------------------------------------------------------


def _qa_fake(responses):
    """精注记假件：按调用顺序返回 responses（可 callable），记录 prompt。

    与 _fake_describe 不同：接受位置 prompt（refine 第二轮调用把
    DETAIL_QA_PROMPT 当位置参数传）。单响应 = 恒返。
    """

    def fake(image_bytes, mime, prompt="", **kwargs):
        fake.calls.append((image_bytes, mime, prompt))
        idx = len(fake.calls) - 1
        result = responses[idx] if idx < len(responses) else responses[-1]
        if callable(result):
            return result(image_bytes, mime)
        return result

    fake.calls = []
    return fake


def test_refine_image_description_merges_details(monkeypatch):
    """二轮有细节 → 合并成「描述；细节补充：细节」，prompt 含第一轮描述。"""
    from contest_generator import extraction

    fake = _qa_fake(["R1 10kΩ；红色实线；PA1"])
    monkeypatch.setattr(extraction, "describe_image_cached", fake)

    out = extraction.refine_image_description(
        b"img", "image/png", "R1 10kΩ",
        vision_base_url="", vision_api_key="sk-test", vision_model="m",
    )
    assert out == "R1 10kΩ；细节补充：R1 10kΩ；红色实线；PA1"
    assert len(fake.calls) == 1
    assert "R1 10kΩ" in fake.calls[0][2]  # 追问 prompt 带上第一轮描述


def test_refine_image_description_keeps_original_on_error(monkeypatch):
    """二轮异常 → 返回原描述（精注记是增强，不抛）。"""
    from contest_generator import extraction

    def boom(*a, **k):
        raise RuntimeError("视觉挂了")

    monkeypatch.setattr(extraction, "describe_image_cached", boom)
    assert extraction.refine_image_description(
        b"img", "image/png", "原描述",
        vision_base_url="", vision_api_key="sk-test", vision_model="m",
    ) == "原描述"


def test_refine_image_description_keeps_original_on_no_supplement(monkeypatch):
    """二轮回复「无补充」/ 空 → 不合并，返回原描述。"""
    from contest_generator import extraction

    monkeypatch.setattr(extraction, "describe_image_cached", _qa_fake(["无补充"]))
    assert extraction.refine_image_description(
        b"img", "image/png", "原描述",
        vision_base_url="", vision_api_key="sk-test", vision_model="m",
    ) == "原描述"

    monkeypatch.setattr(extraction, "describe_image_cached", _qa_fake([""]))
    assert extraction.refine_image_description(
        b"img", "image/png", "原描述",
        vision_base_url="", vision_api_key="sk-test", vision_model="m",
    ) == "原描述"


def test_pdf_image_notes_detail_qa_true_merges(monkeypatch, tmp_path):
    """默认 detail_qa=True：pdf_image_notes 每张图二轮追问并合并。"""
    from contest_generator import extraction

    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest")
    monkeypatch.setattr(
        extraction, "PdfReader",
        lambda _p: _FakeReader([_FakePage([_FakeImage(b"img-a", "a.png")])]),
    )
    fake = _qa_fake(["布局描述", "尺寸 10cm；引脚 PA1"])
    monkeypatch.setattr(extraction, "describe_image_cached", fake)

    notes = extraction.pdf_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model="m"
    )
    assert notes == "[示意图1：布局描述；细节补充：尺寸 10cm；引脚 PA1]"
    assert len(fake.calls) == 2


def test_pdf_image_notes_detail_qa_false_single_call(monkeypatch, tmp_path):
    """detail_qa=False：完全不发起二轮调用（行为与现状一致）。"""
    from contest_generator import extraction

    path = make_sample_pdf(tmp_path / "problem.pdf", "Contest")
    monkeypatch.setattr(
        extraction, "PdfReader",
        lambda _p: _FakeReader([_FakePage([_FakeImage(b"img-a", "a.png")])]),
    )
    fake = _qa_fake(["布局描述"])
    monkeypatch.setattr(extraction, "describe_image_cached", fake)

    notes = extraction.pdf_image_notes(
        path, vision_base_url="", vision_api_key="sk-test", vision_model="m",
        detail_qa=False,
    )
    assert notes == "[示意图1：布局描述]"
    assert len(fake.calls) == 1


def test_extract_image_detail_qa_false_single_call(monkeypatch, tmp_path):
    """extract_image detail_qa=False：一轮描述即返回，无二轮调用。"""
    from contest_generator import extraction

    p = tmp_path / "img.png"
    p.write_bytes(b"fakeimg")
    fake = _qa_fake(["图A"])
    monkeypatch.setattr(extraction, "describe_image_cached", fake)

    out = extraction.extract_image(
        p, vision_base_url="", vision_api_key="sk-test", vision_model="m",
        detail_qa=False,
    )
    assert out == "图A"
    assert len(fake.calls) == 1
