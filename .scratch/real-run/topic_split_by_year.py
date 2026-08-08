"""长真题 PDF 真机拆条（确定性版）：LLM 一次拆 8 题会被 flash 模型输出预算截断
（实测 max_tokens=8192 也断），改为纯文本规则切分——按年份章节 + 标题标记
（"（X 题）" 或行首 "X 题："）把每道题切成一段，题面全文 = 原文段落，不做 AI
改写（比 LLM 抽取更忠实）。

用法：python topic_split_by_year.py <pdf_path>
产出（本目录）：topic_drafts.json（草稿，供用户校对后 confirm）+ topic_drafts_summary.txt
"""
import json
import re
import sys
from pathlib import Path

from contest_generator.extraction import extract_file

YEAR_RE = re.compile(r"20(1[7-9]|2[0-5])[ ]*年")
TITLE_RE = re.compile(r"[（(]\s*([A-H])\s*题\s*[)）]|^([A-H])\s*题[：:]", re.M)


def _year_of(marker: str) -> str:
    return re.search(r"20\d\d", marker).group()


def split_years(text: str) -> list[tuple[str, int, int]]:
    """年份章节边界：同一年变体（'2017年'/'2017 年'）按数字归组，
    取'到下一年距离最大'的出现作为章节起点（封面/页眉只有几百字符）。
    """
    occ = [(m.group(0).strip(), m.start()) for m in YEAR_RE.finditer(text)]
    best: dict[str, tuple[str, int, int]] = {}
    for i, (mk, pos) in enumerate(occ):
        nxt = len(text)
        for mk2, pos2 in occ[i + 1 :]:
            if _year_of(mk2) != _year_of(mk):
                nxt = pos2
                break
        year = _year_of(mk)
        if year not in best or nxt - pos > best[year][2] - best[year][1]:
            best[year] = (year, pos, nxt)
    return sorted(best.values(), key=lambda t: t[1])


def main() -> None:
    pdf = Path(sys.argv[1])
    print(f"extract {pdf.name} ...", flush=True)
    text = extract_file(pdf)
    print(f"text {len(text)} chars", flush=True)

    drafts: list[dict] = []
    for year, start, end in split_years(text):
        seg = text[start:end]
        marks: list[tuple[str, int]] = []
        for m in TITLE_RE.finditer(seg):
            letter = m.group(1) or m.group(2)
            # 行首偏移：题面从标题行起点开始（含标题文字）
            line_start = seg.rfind("\n", 0, m.start()) + 1
            if not marks or marks[-1][0] != letter:
                marks.append((letter, line_start))
        for i, (letter, pos) in enumerate(marks):
            nxt = marks[i + 1][1] if i + 1 < len(marks) else len(seg)
            problem_text = seg[pos:nxt].strip()
            drafts.append(
                {"year": year, "number": letter, "key": f"{year}{letter}",
                 "problem_text": problem_text}
            )
        print(f"{year}: {len(marks)} topics", flush=True)

    drafts.sort(key=lambda d: d["key"])
    out_dir = Path(__file__).parent
    (out_dir / "topic_drafts.json").write_text(
        json.dumps(drafts, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    summary = "\n".join(
        f"{d['key']}  ({len(d['problem_text'])} chars)  "
        f"{d['problem_text'][:50].strip().splitlines()[0]}"
        for d in drafts
    )
    (out_dir / "topic_drafts_summary.txt").write_text(summary, encoding="utf-8")
    print(f"TOTAL {len(drafts)} drafts -> topic_drafts.json", flush=True)


if __name__ == "__main__":
    main()
