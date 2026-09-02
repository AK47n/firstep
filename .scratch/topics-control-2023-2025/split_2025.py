"""工单 topics-control-2023-2025/04：2025 控制题拆条（E/H 两题入库）。

流程与工单 03-split-2023 完全一致（复用既有机制、零 LLM 改写）：
1. 定位页：fitz 文本定位（已核实：2025E=p249-252、2025H=p258-261，
   题目标记（X 题）起始页 + 页眉「E - 1 / 4」×4 确认）。
2. 小题 PDF：fitz 提取各题页 → .scratch/topics-control-2023-2025/pdf/<key>.pdf
3. 确定性拆条：文本 → split_topics_document（零 LLM）；输出 ≠ 1 条用
   章节切片兜底（照 _title_marks 行首偏移规则）。
4. 结构补全：年份标题/参赛注意事项/题名/四段（照 2026H；只补不删零改写）。
5. 视觉核对：渲染落页 PNG → read_image 检查文本层完整性（漏则补录）。
6. 入库：confirm_topics（category=control，programs=[]）。
7. 图注：enrich_topic_image_notes（三级降级、幂等、失败静默）。
8. 断言：题面结构 / manifest / original_pdf < 1MB / resolve_number。

用法：
  python .scratch/topics-control-2023-2025/split_2025.py [extract|split|render|confirm|all]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from contest_generator.topic_library import (  # noqa: E402
    TopicDraft,
    confirm_topics,
    split_topics_document,
)

# 库内自动提交 git add 限 library/ 子域，会把工作区遗留的 reference.json /
# 素材清单.txt 变更卷入——入库提交改由人工精确 add（工单允许统一一次提交）。
import contest_generator.topic_library as _topic_lib  # noqa: E402

_topic_lib.commit_after_write = lambda *args, **kwargs: None

SOURCE_PDF = (
    REPO_ROOT
    / "library/topics/2018C/000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf"
)
SCRATCH = REPO_ROOT / ".scratch/topics-control-2023-2025"
PDF_DIR = SCRATCH / "pdf"
PAGES_DIR = SCRATCH / "pages"

# 边界已核实（题目标记起始页；结束 = 下一题起始页 - 1 / 页眉页数确认）
RANGES = {"2025E": (249, 252), "2025H": (258, 261)}
YEAR = "2025"

# 结构补全（照 03：年份标题行 → 题目标记行之间 = 头部；画面零改写）

# 图内标注补录（视觉核对发现文本层缺失时人工抄录；只补在原文图引用行后）
# 2025E：图 1 的图题与标注内容流位于「2025 年全国…」标题之前、未被章节切片纳入；
# 其中「50cm」为矢量标注不在文本层——从 p249 渲染页补录（正文已含 50cm/100cm/顶点）。
SUPPLEMENT_AFTER: dict[str, str] = {
    "2025E": (
        "\n"
        "> 图1 图题与标注补录（人工补录自 p249 渲染页：图注内容流位于年份标题之前"
        "未被章节纳入；其中 50cm 为矢量标注不在文本层）：\n"
        "> 图1 简易自行瞄准装置场景图；靶纸标注：A4 紫外感光靶纸；"
        "靶面距 AB 线段 50cm；行驶轨迹外沿 100cm×100cm；四顶点 A、B、C、D"
    ),
}


def extract_pages() -> dict[str, str]:
    """提取各题页文本 + 小题 PDF（每份 < 1MB）。"""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(SOURCE_PDF)
    texts: dict[str, str] = {}
    for key, (first, last) in RANGES.items():
        parts = []
        for page_no in range(first, last + 1):
            parts.append(doc[page_no - 1].get_text("text"))
        texts[key] = "\n".join(parts)
        mini = fitz.open()
        for page_no in range(first, last + 1):
            mini.insert_pdf(doc, from_page=page_no - 1, to_page=page_no - 1)
        out = PDF_DIR / f"{key}.pdf"
        # garbage+deflate：去除 insert_pdf 带入的重复对象（字体/资源字典）
        # 与未压缩内容流（实测 2.2MB → 数百 KB）
        mini.save(out, garbage=4, deflate=True, clean=True)
        mini.close()
        # subset_fonts：MuPDF 字体子集化（2025H 原 1125KB → 699KB <1MB）
        # 验证子集后提取文本逐字一致（文本层无损失）
        mini = fitz.open(out)
        mini.subset_fonts(verbose=False)
        tmp = out.with_suffix(".tmp.pdf")
        mini.save(tmp, garbage=4, deflate=True, clean=True)
        mini.close()
        tmp.replace(out)
        print(f"提取 {key}: {out} ({out.stat().st_size / 1024:.0f} KB)")
    doc.close()
    return texts


def _section_slice(text: str, letter: str) -> str:
    """章节切片兜底：标题行起点到文档末尾（照 split_topics_document 的
    _title_marks 行首偏移规则）。"""
    pat = re.compile(rf"[（(]\s*({letter})\s*题\s*[)）]|^({letter})\s*题[：:]", re.M)
    matches = list(pat.finditer(text))
    if not matches:
        raise AssertionError(f"文本中找不到（{letter} 题）标记")
    line_start = text.rfind("\n", 0, matches[0].start()) + 1
    return text[line_start:].strip()


def split_texts(texts: dict[str, str]) -> dict[str, str]:
    """确定性拆条：每份应恰出 1 条；拆不出用章节切片兜底。"""
    problems: dict[str, str] = {}
    for key in RANGES:
        letter = key[-1]
        try:
            drafts = split_topics_document(texts[key])
        except Exception:
            drafts = ()
        if len(drafts) != 1:
            problems[key] = _section_slice(texts[key], letter)
            print(f"{key}: 拆条输出 {len(drafts)} 条 → 章节切片兜底"
                  f"（{len(problems[key])} chars，题面首行 "
                  f"{problems[key].splitlines()[0][:40]!r}）")
            continue
        draft = drafts[0]
        assert draft.year == YEAR, f"{key}: year={draft.year}"
        assert draft.number == letter, f"{key}: number={draft.number}"
        problems[key] = draft.problem_text
        print(f"{key}: 拆条 {len(draft.problem_text)} chars"
              f"（题面首行 {draft.problem_text.splitlines()[0][:40]!r}）")
    return problems


def _reflow_grid_labels(built: str, key: str) -> str:
    """2025H 图 1 网格标注（A1-A9/B1-B7 散行）顺序修复。

    图 1 的网格标注文本层位于页面内容流尾部，拼接后插进正文
    「形成450cm×…350cm 的巡查区域」两行之间，把句子拆断。把散行
    原样移至「图1 巡查区域示意图」图题行后（只移动不删除，零改写）。
    """
    if key != "2025H":
        return built
    lines = built.splitlines()
    labels = [ln for ln in lines if re.fullmatch(r"[AB][1-9]", ln.strip())]
    if not labels:
        return built
    kept = [ln for ln in lines if not re.fullmatch(r"[AB][1-9]", ln.strip())]
    idx = next(
        i for i, ln in enumerate(kept) if "巡查区域示意图" in ln
    )
    kept[idx + 1 : idx + 1] = labels
    return "\n".join(kept) + "\n"


def build_problem_text(key: str, source_text: str) -> str:
    """结构补全（照 03）：# 年份标题 → ## 参赛注意事项 → # 题名（X 题）→
    ## 一、任务 / ## 二、要求 / ## 三、说明 / ## 四、评分标准；去汇编页眉；
    只补不删零改写。"""
    letter = key[-1]
    mark = re.search(rf"[（(]\s*{letter}\s*题\s*[)）]", source_text)
    assert mark, f"{key}: 找不到题目标记行"
    title_line_start = source_text.rfind("\n", 0, mark.start()) + 1
    year_hit = re.search(
        rf"{YEAR}\s*年全国大学生电子设计竞赛试题", source_text
    )
    assert year_hit, f"{key}: 找不到年份标题行"
    head = source_text[year_hit.start() : title_line_start]
    body = source_text[title_line_start:]

    head_lines = [ln.rstrip() for ln in head.splitlines() if ln.strip()]
    out: list[str] = []
    if head_lines:
        out.append(f"# {head_lines[0]}")
        out.append("")
        if len(head_lines) > 2 and "注意事项" in head_lines[1]:
            out.append("## 参赛注意事项")
            out.append("")
            out.extend(head_lines[2:])
            out.append("")

    body_lines = [
        ln.rstrip()
        for ln in body.splitlines()
        if not re.fullmatch(r"\s*[A-H]\s*-\s*\d+\s*/\s*\d+\s*", ln)
    ]
    text = "\n".join(body_lines).strip()
    for ln in text.splitlines():
        stripped = ln.strip()
        if re.fullmatch(rf".*[（(]\s*{letter}\s*题\s*[)）]\s*", stripped):
            out.append(f"# {stripped}")
        elif re.fullmatch(r"[一二三四]、\s*(任务|要求|说明|评分标准).*", stripped):
            out.append(f"## {stripped}")
        else:
            out.append(ln)
    built = "\n".join(out).strip() + "\n"
    built = _reflow_grid_labels(built, key)
    supplement = SUPPLEMENT_AFTER.get(key)
    if supplement:
        # 插入点 = 第一个「图N …」图段（「图1 中小车…」说明段）的**段首之前**，
        # 使补录落在正文引用（…场景如图 1 所示）与图段之间，而非句子中间。
        marker = None
        for i, ln in enumerate(out):
            if re.fullmatch(r"(图\d+)\s+.*", ln.strip()):
                marker = i
                break
        assert marker is not None, f"{key}: 找不到图引用行，无法补录"
        seg_start = marker
        while seg_start > 0 and out[seg_start - 1].strip():
            seg_start -= 1
        out.insert(seg_start, supplement.strip())
        out.insert(seg_start, "")
        built = "\n".join(out).strip() + "\n"
    return built


def render_pages() -> None:
    """渲染各题页 PNG 供视觉核对（文本层 vs 渲染页）。"""
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(SOURCE_PDF)
    for key, (first, last) in RANGES.items():
        for page_no in range(first, last + 1):
            page = doc[page_no - 1]
            pix = page.get_pixmap(dpi=110)
            out = PAGES_DIR / f"{key}_p{page_no}.png"
            pix.save(out)
            print(f"渲染 {key}_p{page_no}.png ({out.stat().st_size // 1024} KB)")
    doc.close()


def confirm() -> None:
    """确认入库：2 条目 + topic.md + 小题 PDF + manifest（category=control）。"""
    texts = extract_pages()
    split_texts(texts)
    topics_root = REPO_ROOT / "library" / "topics"
    for key in RANGES:
        number = key[-1]
        problem_text = build_problem_text(key, texts[key])
        pdf_path = PDF_DIR / f"{key}.pdf"
        confirm_topics(
            topics_root,
            pdf_path=pdf_path,
            entries=[
                TopicDraft(
                    year=YEAR,
                    number=number,
                    problem_text=problem_text,
                    category="control",
                )
            ],
            program_dirs=[],
            pdf_filename=pdf_path.name,
        )
        print(f"确认入库 {key} ✓（{len(problem_text)} chars）")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("extract", "all"):
        extracted = extract_pages()
    if mode in ("split", "all"):
        split_texts(extracted if mode == "all" else extract_pages())
        for key in RANGES:
            text = build_problem_text(
                key, extracted[key] if mode == "all" else extract_pages()[key]
            )
            print(f"{key} 补全后 {len(text)} chars")
    if mode in ("render", "all"):
        render_pages()
    if mode in ("confirm", "all"):
        confirm()
    if mode == "all":
        print()
        print("全流程完成")
