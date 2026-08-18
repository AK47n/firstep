"""赛题文本抽取（薄壳的一部分）：PDF / .docx / 纯文本 → 纯文本。

纯文本输入直接直通（extract_text，不做任何文件操作）；文件输入按后缀
分发（extract_file）：.pdf 用 pypdf、.docx 用标准库解压 + XML、.txt/.md
直接读。所有失败（损坏 / 加密 / 不支持的类型 / 文件不存在）都抛
ExtractionError 带明确信息，绝不让损坏文件以静默空文或崩溃告终。

视觉图注（工单 vision-eyes/02）：extract_pdf_with_image_notes 在文本抽取
后追加电子版 PDF 嵌入示意图的描述（[示意图N：…] 段，走 vision 通道）；
未配视觉 key / 视觉失败 = 静默降级（只用文本，与 extract_file 逐字节
一致）。扫描件 PDF（无文本层）维持现状报错，整页渲染留后续工单。
"""

from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader

from .vision import describe_image_cached

# docx 正文 XML 的 WordprocessingML 主命名空间
_DOCX_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

TEXT_FILE_SUFFIXES = (".txt", ".md")

FileLike = str | Path

# 视觉图注上限（工单 vision-eyes/02）：单文件最多 8 张、单张 ≤ 4MB——
# 防请求体爆炸与免费层限速（超限跳过并标注）
MAX_IMAGE_NOTES = 8
MAX_IMAGE_BYTES = 4 * 1024 * 1024

# 图片文件后缀（工单 vision-eyes/03：上传图片直接走视觉描述）
IMAGE_FILE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif")

# pypdf ImageFile.name 后缀 → mime（GLM-4V 接受的常见类型；未知按 png 兜底）
_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


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


def extract_pdf_with_image_notes(
    path: FileLike,
    *,
    vision_base_url: str,
    vision_api_key: str,
    vision_model: str,
) -> str:
    """PDF 文本抽取 + 嵌入示意图视觉描述（工单 vision-eyes/02）。

    文本部分与 extract_file 完全一致；图注段 `[示意图N：<描述>]` 追加在
    尾部（下游简介 / 推荐 / 骨架零改动全受益）。视觉未配置 / 任何视觉
    失败 = 静默降级（只用文本，逐字节一致）——视觉是增强不是阻塞。
    """
    text = extract_file(path)
    notes = _pdf_image_notes(
        Path(path),
        vision_base_url=vision_base_url,
        vision_api_key=vision_api_key,
        vision_model=vision_model,
    )
    if not notes:
        return text
    return text.rstrip("\n") + "\n\n" + notes


def _pdf_image_notes(
    path: Path,
    *,
    vision_base_url: str,
    vision_api_key: str,
    vision_model: str,
) -> str:
    """电子版 PDF 嵌入图 → 图注段（每张一行 `[示意图N：<描述>]`）。

    上限守卫：单文件 ≤ MAX_IMAGE_NOTES 张、单张 ≤ MAX_IMAGE_BYTES（超限
    跳过并标注）；单张描述失败 = 跳过该张（其余照常）；任何异常（未配置 /
    网络 / 解析 / PDF 结构）→ 返回空串（调用方降级，绝不让视觉拖垮抽取）。
    """
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    skipped = 0
    notes: list[str] = []
    for page in reader.pages:
        try:
            images = list(page.images)
        except Exception:
            continue  # 单页图片解析失败 = 跳过该页（防御）
        for image in images:
            if len(notes) >= MAX_IMAGE_NOTES:
                return _join_notes(notes, skipped)
            try:
                data = image.data
            except Exception:
                skipped += 1
                continue
            if len(data) > MAX_IMAGE_BYTES:
                skipped += 1
                continue
            if not data:
                skipped += 1
                continue
            try:
                description = describe_image_cached(
                    data,
                    _image_mime(image.name),
                    base_url=vision_base_url,
                    api_key=vision_api_key,
                    model=vision_model,
                )
            except Exception:
                skipped += 1
                continue  # 单张失败降级（含未配置 / 网络 / 限流）
            notes.append(description)
    return _join_notes(notes, skipped)


def _join_notes(notes: list[str], skipped: int) -> str:
    """图注段组装：`[示意图N：<描述>]` 逐行；超限/失败计数标注尾部。"""
    if not notes:
        return ""
    lines = [f"[示意图{i}：{text}]" for i, text in enumerate(notes, start=1)]
    if skipped:
        lines.append(f"（另有 {skipped} 张图跳过：超大或描述失败）")
    return "\n".join(lines)


def _image_mime(name: str) -> str:
    """ImageFile.name → mime（未知后缀按 png 兜底，GLM-4V 兼容）。"""
    suffix = Path(name or "").suffix.lower()
    return _IMAGE_MIME_BY_SUFFIX.get(suffix, "image/png")


def extract_image(
    path: FileLike,
    *,
    vision_base_url: str,
    vision_api_key: str,
    vision_model: str,
) -> str:
    """图片文件 → 视觉描述文本（工单 vision-eyes/03）。

    描述文本 = 题面上下文补充（与 PDF 图注同形态 `[示意图1：…]` 或纯描述）。
    未配视觉 key → ExtractionError（可操作提示引导设置页）；视觉失败 →
    ExtractionError（用户主动传图 = 明确意图，报错比静默空文诚实）。
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise ExtractionError(f"文件不存在：{file_path}")
    try:
        data = file_path.read_bytes()
    except OSError as exc:
        raise ExtractionError(f"无法读取图片文件 {file_path}：{exc}") from exc
    if not data:
        raise ExtractionError(f"图片文件为空：{file_path}")
    try:
        description = describe_image_cached(
            data,
            _IMAGE_MIME_BY_SUFFIX.get(file_path.suffix.lower(), "image/png"),
            base_url=vision_base_url,
            api_key=vision_api_key,
            model=vision_model,
        )
    except Exception as exc:
        if isinstance(exc, ExtractionError):
            raise
        raise ExtractionError(f"图片识别失败：{exc}") from exc
    return description


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
