"""赛题文本抽取（薄壳的一部分）：PDF / .docx / 纯文本 → 纯文本。

纯文本输入直接直通（extract_text，不做任何文件操作）；文件输入按后缀
分发（extract_file）：.pdf 用 pypdf、.docx 用标准库解压 + XML、.txt/.md
直接读。所有失败（损坏 / 加密 / 不支持的类型 / 文件不存在）都抛
ExtractionError 带明确信息，绝不让损坏文件以静默空文或崩溃告终。

视觉图注（工单 vision-eyes/02）：extract_pdf_with_image_notes 在文本抽取
后追加电子版 PDF 嵌入示意图的描述（[示意图N：…] 段，走 vision 通道）；
未配视觉 key / 视觉失败 = 静默降级（只用文本，与 extract_file 逐字节
一致）。扫描件 PDF（无文本层）维持现状报错；矢量图渲染视觉（工单
topic-vision-render/01）：pdf_page_render_notes 把页面渲染成位图后走视觉
通道（矢量图无栅格图对象，pdf_image_notes 提取不到），供赛题库存量条目
补图注使用。
"""

from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Sequence

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

# 题面页定位（工单 topic-vision-pages/01）：题面独特文本采样长度（去空白后）
# 与定位后扫描的页跨度——共享汇总 PDF 里图紧跟正文第 1~2 页
LOCATE_TOPIC_SAMPLE_CHARS = 20
LOCATE_TOPIC_SPAN_PAGES = 2

# 渲染视觉图注（工单 topic-vision-render/01）：矢量图 PDF 页渲染成位图 → 视觉
# 描述。渲染倍率（fitz Matrix 缩放，实测 2.0 → 1191×1684 PNG ~187KB < 4MB 上限，
# 质量足够识别尺寸标注）；描述下限与否定词守卫（无图页 / 正文页描述不污染题面）
PAGE_RENDER_SCALE = 2.0
RENDER_NOTE_MIN_CHARS = 8
RENDER_NO_FIGURE_PATTERN = re.compile(
    r"无(?:示意)?图|没有(?:示意)?图|仅(?:有)?文字|只有文字|无实质内容"
)
RENDER_DESCRIBE_PROMPT = (
    "这是电子设计竞赛题面 PDF 渲染出的页面图像。请只描述页面中的示意图"
    "（结构图、流程图、电路图等），忽略页面上的正文文字：提取图的布局、"
    "尺寸标注、文字标注、部件位置关系等对解题有用的信息，用中文简洁描述。"
    "如果页面中没有示意图（只有文字），只回复「无实质内容」。"
)

# 图标题行首正则（工单 topic-vision-render/01）：图内标题定位（_figure_annotation
# block 的 titles 判定）与渲染页图号提取（_page_figure_label）共享——正文引用
# 「如图1所示」不在行首，天然排除
_FIGURE_TITLE_RE = re.compile(r"^\s*图\s*(\d+)")


def _describe_kwargs(
    vision_base_url: str,
    vision_api_key: str,
    vision_model: str,
    observation_collector: object | None,
) -> dict[str, Any]:
    """describe_image_cached 参数组装（vision 三参数 + 可选观测收集器）。

    三处调用共用（pdf_image_notes / pdf_page_render_notes / 上传图片识别），
    单一出处防漂移。
    """
    kwargs: dict[str, Any] = {
        "base_url": vision_base_url,
        "api_key": vision_api_key,
        "model": vision_model,
    }
    if observation_collector is not None:
        kwargs["observation_collector"] = observation_collector
    return kwargs

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
    pages: Sequence[int] | None = None,
) -> str:
    """PDF 嵌入图 → 图注段（每张一行 `[示意图N：<描述>]`）。

    公开消费方：拆条（extract_pdf_with_image_notes 内部）与赛题库存量条目
    补图注（工单 topic-vision-notes/02）。

    pages（1-based，工单 topic-vision-pages/01）：限定扫描页——共享汇总 PDF
    只识别自己题面页的图；None = 全部（现状）。

    仅覆盖**内嵌栅格图**（page.images 对象）；矢量图（绘图命令绘制，无栅格
    对象）走 pdf_page_render_notes（工单 topic-vision-render/01，渲染页 →
    视觉描述）。

    上限守卫：单文件 ≤ MAX_IMAGE_NOTES 张、单张 ≤ MAX_IMAGE_BYTES（超限
    跳过并标注）；单张描述失败 = 跳过该张（其余照常）；任何异常（未配置 /
    网络 / 解析 / PDF 结构）→ 返回空串（调用方降级，绝不让视觉拖垮抽取）。
    """
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    selected = _selected_pages(len(reader.pages), pages)
    skipped = 0
    notes: list[str] = []
    for page_no, page in enumerate(reader.pages, start=1):
        if page_no not in selected:
            continue
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
                description = describe_image_cached(
                    data,
                    mime,
                    **_describe_kwargs(
                        vision_base_url,
                        vision_api_key,
                        vision_model,
                        observation_collector,
                    ),
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


def pdf_figure_annotations(
    path: Path, pages: Sequence[int] | None = None
) -> str:
    """矢量图标注文字布局提取（工单 topic-vision-notes/03）。

    pages（1-based，工单 topic-vision-pages/01）：限定扫描页——共享汇总 PDF
    只扫自己题面所在的页，别的题的图注天然隔离；None = 全部（现状）。

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
    selected = _selected_pages(len(reader.pages), pages)
    blocks: list[str] = []
    for page_no, page in enumerate(reader.pages, start=1):
        if page_no not in selected:
            continue
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


def _selected_pages(page_count: int, pages: Sequence[int] | None) -> frozenset[int]:
    """页范围 → 命中集合（1-based）：None = 全部页；空序列 = 空集（无页可扫）。"""
    if pages is None:
        return frozenset(range(1, page_count + 1))
    return frozenset(pages)


# ---------------------------------------------------------------------------
# 渲染视觉图注（工单 topic-vision-render/01）：矢量图 PDF 页渲染 → 视觉描述
# ---------------------------------------------------------------------------


def _render_page_png(path: Path, page_no: int) -> bytes | None:
    """第 page_no 页（1-based）渲染成 PNG 字节；无 PyMuPDF / 任何失败 → None。

    矢量图（绘图命令绘制）无栅格图对象，pdf_image_notes 提取不到——渲染成
    位图后走视觉通道（2021F 图1 实测：Matrix(2,2) → 1191×1684 PNG，DeepSeek
    vision-exp 完整还原尺寸标注与红实线走向）。模块级函数 = 测试 monkeypatch
    接缝；渲染是增强不是阻塞，失败静默降级。
    """
    try:
        import fitz  # type: ignore[import-untyped]  # PyMuPDF 无类型 stub
    except ImportError:
        return None
    try:
        with fitz.open(str(path)) as doc:
            page = doc[page_no - 1]
            pix = page.get_pixmap(
                matrix=fitz.Matrix(PAGE_RENDER_SCALE, PAGE_RENDER_SCALE)
            )
            return pix.tobytes("png")
    except Exception:
        return None


def _page_figure_label(page: Any) -> str | None:
    """页文本层行首「图N」标题 → 图号；无（正文引用 / 无文本层）→ None。

    行首正则与 _figure_annotation_block 的标题判定同源（_FIGURE_TITLE_RE，
    正文引用「如图1 所示」不在行首天然排除）；None = 扫描件无文本层 →
    顺序编号兜底。
    """
    try:
        text = page.extract_text() or ""
    except Exception:
        return None
    for line in text.splitlines():
        match = _FIGURE_TITLE_RE.match(line)
        if match:
            return match.group(1)
    return None


def pdf_page_render_notes(
    path: Path,
    *,
    vision_base_url: str,
    vision_api_key: str,
    vision_model: str,
    observation_collector: object | None = None,
    pages: Sequence[int] | None = None,
) -> str:
    """渲染页 → 视觉描述图注段（工单 topic-vision-render/01）：`[图N 标注：…]` 逐行。

    矢量图（无栅格图对象）路径：逐页渲染（_render_page_png）→ DeepSeek 视觉
    描述（RENDER_DESCRIBE_PROMPT，只描述示意图忽略正文）。无图页过滤：
    描述 < RENDER_NOTE_MIN_CHARS 或命中否定词（「无实质内容」「只有文字」等）
    → 跳过（正文页误描述不污染题面）。图号 = 页文本层行首「图N」标题优先，
    无文本层 → 顺序编号（第 k 个产出 → k）。

    pages（1-based，与 pdf_image_notes 同约定）：限定扫描页；None = 全部。
    单页渲染 / 视觉失败 = 跳过该页（其余照常）；坏 PDF / 全失败 → 空串
    （调用方降级，绝不抛——图注是增强不是阻塞）。上限 MAX_IMAGE_NOTES 封顶。
    段前缀 `[图N 标注` 命中 enrich 幂等正则（`\\[图\\s*\\d+\\s*标注`）。
    """
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    selected = _selected_pages(len(reader.pages), pages)
    notes: list[str] = []
    used_labels: set[str] = set()  # 已产出图号（真实 + 顺序兜底），防重复
    for page_no, page in enumerate(reader.pages, start=1):
        if page_no not in selected:
            continue
        if len(notes) >= MAX_IMAGE_NOTES:
            break
        try:
            png = _render_page_png(path, page_no)
            if png is None:
                continue
            description = describe_image_cached(
                png,
                "image/png",
                RENDER_DESCRIBE_PROMPT,
                **_describe_kwargs(
                    vision_base_url,
                    vision_api_key,
                    vision_model,
                    observation_collector,
                ),
            ).strip()
        except Exception:
            continue  # 渲染 / 视觉失败降级（含未配置 / 网络 / 限流）
        if len(description) < RENDER_NOTE_MIN_CHARS or RENDER_NO_FIGURE_PATTERN.search(
            description
        ):
            continue  # 无图页 / 正文页误描述：不写回
        label = _page_figure_label(page)
        if label is None:
            # 顺序编号兜底（扫描件无文本层）：从 1 找第一个未被占用的号——
            # 真实图号不连续时（如已有「图1」「图3」）直接取 len+1 会撞车
            candidate = 1
            while str(candidate) in used_labels:
                candidate += 1
            label = str(candidate)
        if label in used_labels:
            continue  # 真实图号撞车（两页同「图N」标题）：跳过，宁缺毋滥
        used_labels.add(label)
        notes.append(f"[图{label} 标注：{description}]")
    return "\n".join(notes)


def locate_topic_pages(pdf_path: Path, topic_text: str) -> tuple[int, int] | None:
    """题面页定位（工单 topic-vision-pages/01）：共享汇总 PDF 里找题面正文页。

    题面独特文本 = topic_text 去空白后前 LOCATE_TOPIC_SAMPLE_CHARS 字符；逐页
    文本层去空白后子串匹配。命中页起 LOCATE_TOPIC_SPAN_PAGES 页（图紧跟正文
    第 1~2 页）→ 返回 (start, start + span)（1-based 开区间右端，供 pages
    参数直接使用）。坏 PDF / 空白题面 / 无命中 → None（绝不抛——定位是增强
    不是阻塞；扫描件无文本层时调用方跳过补图注）。
    """
    sample = "".join(topic_text.split())[:LOCATE_TOPIC_SAMPLE_CHARS]
    if not sample:
        return None
    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return None
    for page_no, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            continue
        if sample in "".join(page_text.split()):
            return (page_no, page_no + LOCATE_TOPIC_SPAN_PAGES)
    return None


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
        for y, text, _ in rows
        if _FIGURE_TITLE_RE.match(text)
    ]
    if not titles:
        return ""
    max_chars = FIGURE_ANNOTATION_MAX_LINE_CHARS
    window = FIGURE_ANNOTATION_WINDOW
    # 短行 / 长行判定基于**行内最长单段的去空白长度**而非拼接文本（工单
    # topic-vision-pages/02）：图内尺寸链（60cm 与 60cm 之间大量空格）在
    # 文本层常是**单段**长文本——按原始长度会把真标注误判成正文长行，把
    # 整个图注区挡在窗外（2021F 图1 曾只提取出「2．发挥部分」一行）；
    # 中文正文连续无空格、英文正文空格占比低，去空白后长度仍超长。
    short_rows = [
        (y, text)
        for y, text, max_seg in rows
        if max_seg < max_chars
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
            # 与标题之间无长行（长行 = 正文 / 图边界；正文整句单段即超长）
            if any(
                max_seg >= max_chars and min(y, title_y) < ly < max(y, title_y)
                for ly, _, max_seg in rows
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


def _cluster_rows(
    segments: list[tuple[float, float, str]],
) -> list[tuple[float, str, int]]:
    """段集合 → 行（y 容差聚类，行内按 x 排序），按 y 降序（页面上→下）。

    返回 (y, 行文本, 行内最长单段的**去空白长度**)——第三元供短行/长行
    判定：图内尺寸链（60cm 与 60cm 间大量空格）单段即长，去空白后才见真
    长度（见 _figure_annotation_block）。
    """
    segs = sorted(segments, key=lambda s: (-s[1], s[0]))
    rows: list[tuple[float, list[tuple[float, str]]]] = []
    for x, y, text in segs:
        if rows and abs(rows[-1][0] - y) <= FIGURE_ANNOTATION_ROW_TOLERANCE:
            rows[-1][1].append((x, text))
        else:
            rows.append((y, [(x, text)]))
    result: list[tuple[float, str, int]] = []
    for y, items in rows:
        sorted_items = sorted(items, key=lambda item: item[0])
        result.append(
            (
                y,
                " ".join(text for _, text in sorted_items).strip(),
                max(len("".join(text.split())) for _, text in sorted_items),
            )
        )
    return result


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
        description = describe_image_cached(
            data,
            _IMAGE_MIME_BY_SUFFIX.get(file_path.suffix.lower(), "image/png"),
            **_describe_kwargs(
                vision_base_url,
                vision_api_key,
                vision_model,
                observation_collector,
            ),
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
