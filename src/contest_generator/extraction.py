"""赛题文本抽取（薄壳的一部分）：PDF / .docx / 纯文本 → 纯文本。

纯文本输入直接直通（extract_text，不做任何文件操作）；文件输入按后缀
分发（extract_file）：.pdf 用 pypdf、.docx 用标准库解压 + XML、.txt/.md
直接读。所有失败（损坏 / 加密 / 不支持的类型 / 文件不存在）都抛
ExtractionError 带明确信息，绝不让损坏文件以静默空文或崩溃告终。
"""

from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader

# docx 正文 XML 的 WordprocessingML 主命名空间
_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

TEXT_FILE_SUFFIXES = (".txt", ".md")

FileLike = str | Path


class ExtractionError(Exception):
    """文本抽取失败，message 中说明具体问题。"""


def extract_text(text: str) -> str:
    """纯文本输入直通：原样返回，不做任何解析或文件操作。"""
    return text


def extract_file(path: FileLike) -> str:
    """按后缀解析文件为纯文本；失败抛 ExtractionError。

    支持 .pdf / .docx / .txt / .md；其余类型（如旧版二进制 .doc）
    给出明确错误，不猜内容。
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise ExtractionError(f"文件不存在：{file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(file_path)
    if suffix == ".docx":
        return _extract_docx(file_path)
    if suffix in TEXT_FILE_SUFFIXES:
        try:
            return file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ExtractionError(f"无法读取文本文件 {file_path}：{exc}") from exc
    raise ExtractionError(
        f"不支持的文件类型：{suffix or '（无扩展名）'}（支持 .pdf / .docx / .txt / .md）"
    )


def _extract_pdf(path: Path) -> str:
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise ExtractionError(f"无法读取 PDF 文件（文件可能损坏）：{exc}") from exc

    if reader.is_encrypted:
        raise ExtractionError("PDF 已加密，请先解除密码后再上传")

    parts: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            parts.append(page.extract_text() or "")
        except Exception as exc:
            raise ExtractionError(
                f"PDF 第 {page_number} 页文本抽取失败：{exc}"
            ) from exc
    return _require_text("\n".join(parts), path)


def _extract_docx(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            if "word/document.xml" not in archive.namelist():
                raise ExtractionError(
                    f"不是有效的 .docx 文件（缺少 word/document.xml）：{path}"
                )
            document = archive.read("word/document.xml")
    except zipfile.BadZipFile as exc:
        raise ExtractionError(
            f"不是有效的 .docx 文件（无法解压，文件可能损坏）：{path}"
        ) from exc
    except ExtractionError:
        raise
    except OSError as exc:
        raise ExtractionError(f"无法读取 .docx 文件：{exc}") from exc

    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        raise ExtractionError(f".docx 正文 XML 损坏：{exc}") from exc

    text = "\n".join(_paragraph_text(para) for para in root.iter(f"{_DOCX_NS}p"))
    return _require_text(text, path)


def _paragraph_text(paragraph: ET.Element) -> str:
    """段落内文本：w:t 取文字、w:tab 取制表符、w:br/w:cr 取换行。"""
    parts: list[str] = []
    for node in paragraph.iter():
        tag = node.tag
        if tag == f"{_DOCX_NS}t":
            parts.append(node.text or "")
        elif tag == f"{_DOCX_NS}tab":
            parts.append("\t")
        elif tag in (f"{_DOCX_NS}br", f"{_DOCX_NS}cr"):
            parts.append("\n")
    return "".join(parts)


def _require_text(text: str, path: Path) -> str:
    """扫描件 / 纯图片文件解不出任何文字，与损坏文件同样视为抽取失败。"""
    if not text.strip():
        raise ExtractionError(
            f"未能从 {path.name} 中抽取到任何文字（文件可能是扫描件或纯图片）"
        )
    return text
