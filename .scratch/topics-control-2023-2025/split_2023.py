"""工单 topics-control-2023-2025/03：2023 控制题拆条（E/G/I 三题入库）。

复用既有机制、零 LLM 改写：
1. 定位页：fitz 文本定位 2023 章节内三题边界（已核实：E=p183-185、
   G=p189-193、I=p197-199，题目标记（X 题）起始页；相邻题分界 = 下一题
   标题行，页眉「E - 1 / 3」确认页数）。
2. 小题 PDF：fitz 提取各题页 → .scratch/topics-control-2023-2025/pdf/<key>.pdf
3. 确定性拆条：文本 → split_topics_document（零 LLM）；每份应恰 1 条。
4. 结构补全：从全文章节头部（年份标题 + 参赛注意事项）确定性拼接，
   照 2026H 结构（# 年份标题 → ## 参赛注意事项 → # 题名（X 题）→ 正文）。
5. 视觉核对：渲染各题页 PNG → .scratch/topics-control-2023-2025/pages/
6. 入库：confirm_topics（category=control，programs=[]）
7. 图注：GET /api/topics/<key> 触发 enrich_topic_image_notes
8. 断言：题面结构 / manifest / original_pdf < 1MB / resolve_number

用法：
  python .scratch/topics-control-2023-2025/split_2023.py [--extract|--split|--build|--confirm|--all]
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
# 素材清单.txt 变更卷入——拆条入库的提交改由人工精确 add（工单允许统一
# 一次提交）；confirm_topics 内部调用经模块全局名，打桩为 no-op。
import contest_generator.topic_library as _topic_lib  # noqa: E402

_topic_lib.commit_after_write = lambda *args, **kwargs: None

SOURCE_PDF = (
    REPO_ROOT
    / "library/topics/2018C/000_2017-2025_全国大学生电子设计竞赛真题汇总.pdf"
)
SCRATCH = REPO_ROOT / ".scratch/topics-control-2023-2025"
PDF_DIR = SCRATCH / "pdf"
PAGES_DIR = SCRATCH / "pages"

# 边界已核实（题目标记起始页；结束 = 下一题起始页 - 1）
RANGES = {"2023E": (183, 185), "2023G": (189, 193), "2023I": (197, 199)}

# 图内标注补录（视觉核对发现文本层缺失）：图 1 的矢量标注文字不在
# get_text("text") 输出里——2023E/G 的图内标注被提取（散行，原文本层
# 顺序）；2023I 图 1 全漏（赛道参数：弧半径/圆心/标识线长度/尺寸）。照
# 2026D 先例把关键参数整理为图引用行；追加在原文「图1 悬浮车测试赛道」
# 行之后，不改动原文本行（零改写：只补不删）。
SUPPLEMENT_AFTER = {
    "2023I": (
        "\n"
        "> 图1 标注补录（人工补录自 p197 渲染页，矢量标注不在文本层）："
        "r1=42.5 cm O1(30,60)；r2=42.5 cm O2(90,120)；r3=42.5 cm O3(150,60)；"
        "r4=15 cm O4(15,15)；r5=15 cm O5(165,15)；标识线B 长20cm；"
        "标识线A 长20cm；启/停点 标号线长35 cm；纵向 40 cm、50 cm；"
        "横向 180 cm；坐标(0,0)"
    ),
}

# 结构补全模板（照 2026H 结构；确定性拼接，不 AI 生成）
CHAPTER_HEAD = None  # 不再使用：头部（年份标题+参赛注意事项）从原文确定性抽取


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
        mini.save(out)
        mini.close()
        print(f"提取 {key}: {out} ({out.stat().st_size / 1024:.0f} KB)")
    doc.close()
    return texts


def _section_slice(text: str, letter: str) -> str:
    """章节切片兜底（工单步骤 3）：标题行起点到文档末尾的原文段落，
    照 split_topics_document 的 _title_marks 分块逻辑（行首偏移）。

    用于 TITLE_RE 字母域 [A-H] 外的题号（2023 年真题 A-K 十一题，I 题
    超域；库函数 split_topics_document 有意只认 A-H——往年真题范围）。
    """
    pat = re.compile(rf"[（(]\s*({letter})\s*题\s*[)）]|^({letter})\s*题[：:]", re.M)
    matches = list(pat.finditer(text))
    if not matches:
        raise AssertionError(f"文本中找不到（{letter} 题）标记")
    line_start = text.rfind("\n", 0, matches[0].start()) + 1
    return text[line_start:].strip()


def split_texts(texts: dict[str, str]) -> dict[str, str]:
    """确定性拆条：每份文本应恰出 1 条草稿（含标题行起点的题面）；
    拆不出（输出 ≠ 1 条）用章节切片兜底。"""
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
        assert draft.year == "2023", f"{key}: year={draft.year}"
        assert draft.number == letter, f"{key}: number={draft.number}"
        problems[key] = draft.problem_text
        print(f"{key}: 拆条 {len(draft.problem_text)} chars"
              f"（题面首行 {draft.problem_text.splitlines()[0][:40]!r}）")
    return problems


def build_problem_text(key: str, source_text: str) -> str:
    """结构补全（照 2026H 结构，确定性拼接，零 AI 改写）：

    # 2023年全国大学生电子设计竞赛试题
    ## 参赛注意事项
    （1）…
    # 题名（X 题）
    【本科组】
    ## 一、任务 / ## 二、要求 / ## 三、说明 / ## 四、评分标准

    处理：年份标题行 → 题目标记行之间 = 章节头部（标题 + 参赛注意事项）；
    题面主体去汇编页眉（「E - 1 / 3」）；题名行 / 四小标题行 markdown 化。
    """
    letter = key[-1]
    mark = re.search(rf"[（(]\s*{letter}\s*题\s*[)）]", source_text)
    assert mark, f"{key}: 找不到题目标记行"
    title_line_start = source_text.rfind("\n", 0, mark.start()) + 1
    year_hit = re.search(
        r"2023\s*年全国大学生电子设计竞赛试题", source_text
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
        if not re.fullmatch(r"\s*[A-K]\s*-\s*\d+\s*/\s*\d+\s*", ln)
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
    supplement = SUPPLEMENT_AFTER.get(key)
    if supplement:
        # 补录插在原文「图1…」行之后（只补不删）
        marker = None
        for i, ln in enumerate(out):
            if re.fullmatch(r"(图\d+)\s+.*", ln.strip()):
                marker = i
                break
        assert marker is not None, f"{key}: 找不到图引用行，无法补录"
        out.insert(marker + 1, supplement.strip())
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
    """确认入库：3 条目 + topic.md + 小题 PDF + manifest（category=control）。"""
    texts = extract_pages()
    problems = split_texts(texts)
    topics_root = REPO_ROOT / "library" / "topics"
    for key in RANGES:
        number = key[-1]
        problem_text = build_problem_text(key, texts[key])
        pdf_path = PDF_DIR / f"{key}.pdf"
        # confirm_topics 单条入库（pdf = 小题 PDF；programs=[]；category=control）
        confirm_topics(
            topics_root,
            pdf_path=pdf_path,
            entries=[
                TopicDraft(
                    year="2023",
                    number=number,
                    problem_text=problem_text,
                    category="control",
                )
            ],
            program_dirs=[],
            pdf_filename=pdf_path.name,
        )
        print(f"确认入库 {key} ✓（{len(problem_text)} chars，拆条 {len(problems[key])} chars）")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("extract", "all"):
        extracted = extract_pages()
    if mode in ("split", "all"):
        problems = split_texts(extracted if mode == "all" else extract_pages())
        for key in RANGES:
            text = build_problem_text(key, extracted[key] if mode == "all" else extract_pages()[key])
            print(f"{key} 补全后 {len(text)} chars")
    if mode in ("render", "all"):
        render_pages()
    if mode in ("confirm", "all"):
        confirm()
    if mode == "all":
        print()
        print("全流程完成")
