"""工单 topic-pdf-viewer/02 真机验证：2021F 真实汇总 PDF → 完整页范围 (123,127)。"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from contest_generator.extraction import (
    FOOTER_PAGE_RE,
    _page_footer_total,
    locate_topic_pages,
    locate_topic_pages_full,
)

ROOT = Path(__file__).resolve().parents[2]
TOPICS_ROOT = ROOT / "library" / "topics"

from contest_generator.topic_library import resolve_number  # noqa: E402

entry = resolve_number(TOPICS_ROOT, "2021F")
PDF = TOPICS_ROOT / "2021F" / entry.original_pdf
topic_text = entry.problem_text
print(f"entry.original_pdf = {entry.original_pdf}")
print(f"topic_text[:40] = {topic_text[:40]!r}")

located = locate_topic_pages(PDF, topic_text)
print(f"locate_topic_pages   -> {located}   (期望 (123, 125))")

total = _page_footer_total(PDF, located[0])
print(f"_page_footer_total(123) -> {total}   (期望 4)")

full = locate_topic_pages_full(PDF, topic_text)
print(f"locate_topic_pages_full -> {full}   (期望 (123, 127))")

# 逐页 dump：122-129 页页脚形态 + 正文行首，确认 F/G 边界与误命中
from pypdf import PdfReader

reader = PdfReader(str(PDF))
print(f"\n总页数 = {len(reader.pages)}")
for page_no in range(122, 130):
    text = reader.pages[page_no - 1].extract_text() or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    hits = [ln for ln in lines if FOOTER_PAGE_RE.match(ln)]
    head = " ".join(lines[0].split())[:40] if lines else ""
    print(f"页 {page_no}: 行数={len(lines)} 页脚命中={hits} 首行={head!r}")

# 页 123-126 全部行中匹配页脚正则的行（检查正文误命中）
for page_no in range(123, 127):
    text = reader.pages[page_no - 1].extract_text() or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    hits = [ln for ln in lines if FOOTER_PAGE_RE.match(ln)]
    print(f"\n--- 页 {page_no} 页脚正则命中行（共 {len(lines)} 行）---")
    for h in hits:
        print(f"  {h!r}")
