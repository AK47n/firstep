"""从已生成的 matrix/*.log 重算结果（修复 stm32 把 “0 Warning(s)” 当警告的误判）。"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).parent
MATRIX = HERE / "matrix"
RESULTS = HERE / "matrix_results.md"

BASELINE_WARNING_MARKERS = ("ovsRate", "higher oversampling rate")


def warning_lines(platform: str, output: str) -> list[str]:
    lines = []
    for line in output.splitlines():
        if "warning" not in line.lower():
            continue
        if re.search(r"0 warning", line, re.I):
            continue
        if re.search(r"\b1 warning", line, re.I) or re.search(r"\b\d warning", line, re.I):
            # 摘要行（0 error(s), N warning(s)）不当作源码警告
            if re.search(r"error\(s\)", line, re.I):
                continue
        lines.append(line)
    return [
        line for line in lines
        if not any(marker.lower() in line.lower() for marker in BASELINE_WARNING_MARKERS)
    ]


def main() -> None:
    rows = []
    for platform in ("mspm0", "stm32"):
        base = MATRIX / platform
        if not base.is_dir():
            continue
        for slug_dir in sorted(base.iterdir()):
            if not slug_dir.is_dir():
                continue
            log = slug_dir / "build.log"
            if not log.is_file():
                rows.append((slug_dir.name, platform, "NO_LOG", "-", "GEN_FAIL", "无日志"))
                continue
            output = log.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"(\d+)\s+errors?", output, re.I)
            errors = m.group(1) if m else "0"
            warnings = warning_lines(platform, output)
            verdict = "PASS" if errors == "0" and not warnings else ("WARN_FAIL" if errors == "0" else "ERROR")
            note = ("非基线 warning: " + "; ".join(warnings[:3])) if warnings else "-"
            rows.append((slug_dir.name, platform, "0", errors, verdict, note))
    lines = [
        "# module-polish 编译矩阵结果\n",
        "| slug | platform | exit | errors | 判定 | 备注 |",
        "|---|---|---|---|---|---|",
    ]
    for slug, platform, exit_code, errors, verdict, note in rows:
        lines.append(f"| {slug} | {platform} | {exit_code} | {errors} | {verdict} | {note} |")
    RESULTS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
