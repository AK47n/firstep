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

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

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

# 矢量图标注布局（工单 topic-vision-notes/03）：图N 标题上下窗口 / 图内短行
# 上限（滤正文长行）/ 行聚类 y 容差（页面坐标单位）
FIGURE_ANNOTATION_WINDOW = 350.0
FIGURE_ANNOTATION_MAX_LINE_CHARS = 20
FIGURE_ANNOTATION_ROW_TOLERANCE = 6.0

# pypdf ImageFile.name 后缀 → mime（通用映射；.bmp 条目保留作映射完整性
# 与 PDF 结构兼容——PDF 内嵌图发送前由 _VISION_PASSTHROUGH_SUFFIXES 判定
# 直发/转码，非直发格式（.bmp / JPEG2000 / 未知）走 _transcode_to_png）
_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

# DeepSeek 视觉支持直发的后缀集（工单 vision-format-transcode/01）：其余
# （BMP / JPEG2000 / 未知）发送前用 Pillow 转 PNG——DeepSeek 不收 BMP 与
# JPEG2000，且未知后缀兜底 image/png 直发原字节必然解码失败
_VISION_PASSTHROUGH_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp"})


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
    observation_collector: object | None = None,
) -> str:
    """PDF 文本抽取 + 嵌入示意图视觉描述（工单 vision-eyes/02）。

    文本部分与 extract_file 完全一致；图注段 `[示意图N：<描述>]` 追加在
    尾部（下游简介 / 推荐 / 骨架零改动全受益）。视觉未配置 / 任何视觉
    失败 = 静默降级（只用文本，逐字节一致）——视觉是增强不是阻塞。
    """
    text = extract_file(path)
    notes = pdf_image_notes(
        Path(path),
        vision_base_url=vision_base_url,
        vision_api_key=vision_api_key,
        vision_model=vision_model,
        observation_collector=observation_collector,
    )
    if not notes:
        return text
    return text.rstrip("\n") + "\n\n" + notes


def pdf_image_notes(
    path: Path,
    *,
    vision_base_url: str,
    vision_api_key: str,
    vision_model: str,
    observation_collector: object | None = None,
) -> str:
    """PDF 嵌入图 → 图注段（每张一行 `[示意图N：<描述>]`）。

    公开消费方：拆条（extract_pdf_with_image_notes 内部）与赛题库存量条目
    补图注（工单 topic-vision-notes/02）。

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
            # DeepSeek 不收 BMP / JPEG2000 等：发送前转 PNG（工单
            # vision-format-transcode/01，替换「BMP 发送前跳过」）；Pillow
            # 未装 / 解码失败 → 降级跳过（不浪费注定失败的视觉调用）
            if _needs_transcode(image.name):
                png = _transcode_to_png(data)
                if png is None:
                    skipped += 1
                    continue
                data, mime = png, "image/png"
            else:
                mime = _image_mime(image.name)
            try:
                describe_kwargs: dict[str, Any] = {
                    "base_url": vision_base_url,
                    "api_key": vision_api_key,
                    "model": vision_model,
                }
                if observation_collector is not None:
                    describe_kwargs["observation_collector"] = observation_collector
                description = describe_image_cached(
                    data,
                    mime,
                    **describe_kwargs,
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


def pdf_figure_annotations(path: Path) -> str:
    """矢量图标注文字布局提取（工单 topic-vision-notes/03）。

    电赛题面矢量图（绘图命令绘制）无栅格图对象，视觉提取不到；但图内标注
    文字（尺寸 / 角度 / 区域标签）留在 PDF 文本层。本函数用 visitor_text
    回调取每个文字段的变换矩阵，**复合 cm×tm 还原页面坐标**（图内文字经
    缩放矩阵，tm 平移是原始值），按 y 聚类成行、行内按 x 排序，定位「图N」
    标题行后取其上下窗口内的短文本行（正文长行滤除），产出布局文本：

        [图N 标注]
        <行1：同 y 的标注按 x 从左到右>
        ...

    标注与线段的位置关系（左角度 / 右角度 / 尺寸链）由行序与行内序保留，
    LLM 可据此还原图的结构。坏 PDF / 无图 / 无标注 → 空串（调用方降级，
    绝不抛——文字标注是增强不是阻塞）。
    """
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    blocks: list[str] = []
    for page in reader.pages:
        segments: list[tuple[float, float, str]] = []

        def visitor(text, cm, tm, font_dict, font_size) -> None:
            if not (text and text.strip()):
                return
            x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
            y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
            segments.append((x, y, text))

        try:
            page.extract_text(visitor_text=visitor)
        except Exception:
            continue
        block = _figure_annotation_block(segments)
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


def _figure_annotation_block(segments: list[tuple[float, float, str]]) -> str:
    """单页段集合 → 标注区布局块（纯函数，可测）。

    标题行 = 「图N」在**行首**的短行（正文引用"如图1所示"、序号行"8．可
    使用图2…"、表格行"…电路图 6"的"图"都不在行首，天然排除）。图内
    标注短行排除页码行（"C - 1 / 4" / "H 题 - 1 / 4"，坐标经变换异常）。

    归属规则（每条短行 ∈ 图 N 标注区，须同时满足）：
    1. 距「图N」标题行 ≤ 窗口（FIGURE_ANNOTATION_WINDOW）；
    2. 与标题行之间（y 区间内）无正文长行（长行 = 图 / 正文的边界）；
    3. 该标题是它的**最近**图标题（相邻两图之间无长行分隔时，短行归属
       最近标题，杜绝 A 图标注混入 B 图）。

    行序 = 页面上→下，行内按 x 排序（标注与线段的位置关系由此保留）。
    无标题 / 无标注 → 空串。
    """
    if not segments:
        return ""
    rows = _cluster_rows(segments)
    titles = [
        (y, text)
        for y, text in rows
        if re.match(r"^\s*图\s*\d", text)
    ]
    if not titles:
        return ""
    max_chars = FIGURE_ANNOTATION_MAX_LINE_CHARS
    window = FIGURE_ANNOTATION_WINDOW
    short_rows = [
        (y, text)
        for y, text in rows
        if len(text) < max_chars
        and not re.match(r"^\s*图\s*\d", text)
        and not re.match(r"^[^-–]*[-–]\s*\d+\s*/\s*\d+", text)  # 页码行
    ]
    blocks: list[str] = []
    for title_y, title_text in titles:
        match = re.search(r"图\s*(\d+)", title_text)
        label = match.group(1) if match else "?"
        own: list[tuple[float, str]] = []
        for y, text in short_rows:
            if abs(y - title_y) > window:
                continue
            # 与标题之间无长行（长行 = 正文 / 图边界）
            if any(
                len(t) >= max_chars and min(y, title_y) < ly < max(y, title_y)
                for ly, t in rows
            ):
                continue
            # 最近图标题归属
            if any(
                abs(y - other_y) < abs(y - title_y) for other_y, _ in titles
            ):
                continue
            own.append((y, text))
        own.sort(key=lambda item: -item[0])
        if not own:
            continue
        blocks.append(
            "[图" + label + " 标注]\n" + "\n".join(text for _, text in own)
        )
    return "\n\n".join(blocks)


def _cluster_rows(segments: list[tuple[float, float, str]]) -> list[tuple[float, str]]:
    """段集合 → 行（y 容差聚类，行内按 x 排序），按 y 降序（页面上→下）。"""
    segs = sorted(segments, key=lambda s: (-s[1], s[0]))
    rows: list[tuple[float, list[tuple[float, str]]]] = []
    for x, y, text in segs:
        if rows and abs(rows[-1][0] - y) <= FIGURE_ANNOTATION_ROW_TOLERANCE:
            rows[-1][1].append((x, text))
        else:
            rows.append((y, [(x, text)]))
    return [
        (y, " ".join(text for _, text in sorted(items, key=lambda item: item[0])).strip())
        for y, items in rows
    ]


def _image_suffix(name: str) -> str:
    """ImageFile.name / 文件路径 → 小写后缀（空名兜底 ""）。"""
    return Path(name or "").suffix.lower()


def _image_mime(name: str) -> str:
    """ImageFile.name → mime（未知后缀按 png 兜底，DeepSeek 视觉兼容）。"""
    return _IMAGE_MIME_BY_SUFFIX.get(_image_suffix(name), "image/png")


def _needs_transcode(name: str) -> bool:
    """后缀 ∉ DeepSeek 直发集 → 需转码（BMP / JPEG2000 / 未知）。"""
    return _image_suffix(name) not in _VISION_PASSTHROUGH_SUFFIXES


def _transcode_to_png(data: bytes) -> bytes | None:
    """非 DeepSeek 支持格式（BMP / JPEG2000 等）→ PNG 字节（工单
    vision-format-transcode/01）。

    Pillow lazy import：未安装（老环境未升级依赖）或无法解码 → None，
    调用方降级跳过——绝不崩启动，也不让格式问题拖垮图注。
    """
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        return None


def extract_image(
    path: FileLike,
    *,
    vision_base_url: str,
    vision_api_key: str,
    vision_model: str,
    observation_collector: object | None = None,
) -> str:
    """图片文件 → 视觉描述文本（工单 vision-eyes/03）。

    描述文本 = 题面上下文补充（与 PDF 图注同形态 `[示意图1：…]` 或纯描述）。
    未配视觉 key → ExtractionError（可操作提示引导设置页）；视觉失败 →
    ExtractionError（用户主动传图 = 明确意图，报错比静默空文诚实）。
    .bmp 入口拦截（工单 vision-deepseek-native/01）：DeepSeek 视觉不支持
    BMP，直接友好报错引导转存，不浪费一次注定失败的视觉调用。
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise ExtractionError(f"文件不存在：{file_path}")
    if file_path.suffix.lower() == ".bmp":
        raise ExtractionError(
            "暂不支持 BMP 格式的图片：DeepSeek 视觉仅支持 PNG / JPEG / GIF / WebP，"
            "请用画图等工具将图片转存为 PNG 或 JPEG 后重新上传"
        )
    try:
        data = file_path.read_bytes()
    except OSError as exc:
        raise ExtractionError(f"无法读取图片文件 {file_path}：{exc}") from exc
    if not data:
        raise ExtractionError(f"图片文件为空：{file_path}")
    try:
        describe_kwargs: dict[str, Any] = {
            "base_url": vision_base_url,
            "api_key": vision_api_key,
            "model": vision_model,
        }
        if observation_collector is not None:
            describe_kwargs["observation_collector"] = observation_collector
        description = describe_image_cached(
            data,
            _IMAGE_MIME_BY_SUFFIX.get(file_path.suffix.lower(), "image/png"),
            **describe_kwargs,
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
