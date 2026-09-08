# -*- coding: utf-8 -*-
"""再现 v6 对 ags10 的处理，打印每个块的分类与提取结果。"""
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH = Path(__file__).resolve().parents[2] / "sources" / "materials" / "lckfb-地猛星移植手册"
FENCE_RE = re.compile(r"^```[A-Za-z0-9_+\-.#]*$", re.M)
FUNC_DEF_RE = re.compile(
    r"^\s*(?:static\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.M,
)
PY_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", re.M)
PROTO_RE = re.compile(
    r"^\s*(?:extern\s+)?(?:[A-Za-z_][\w\s\*]*\s+)?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*;\s*$",
    re.M,
)
MACRO_RE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)", re.M)


def blocks(md: str) -> list[str]:
    out, i, lines = [], 0, md.splitlines()
    while i < len(lines):
        if FENCE_RE.match(lines[i]):
            j, buf = i + 1, []
            while j < len(lines) and not FENCE_RE.match(lines[j]):
                buf.append(lines[j])
                j += 1
            out.append("\n".join(buf))
            i = j + 1
        else:
            i += 1
    return out


def strip_comments(code: str) -> str:
    code = re.sub(r"/\*[\s\S]*?\*/", "", code)
    code = re.sub(r"//[^\n]*", "", code)
    code = re.sub(r"^\s*#\s*(?!include|define|ifndef|ifdef|endif|elif|\w)", "", code)
    return code


t = (BATCH / "sensor--ags10-harmful-gas-sensor.md").read_text(encoding="utf-8")
for bi, b in enumerate(blocks(t)):
    content = strip_comments(b)
    has_py = bool(re.search(r"^\s*(def |import |from |class )", b, re.M)) or bool(
        re.search(r"^\s*[A-Za-z_]\w*\s*=\s*(?:sensor|image|pyb|clock)\.", b, re.M))
    has_c_def = bool(FUNC_DEF_RE.search(content))
    has_main = bool(re.search(r"\b(?:void|int)\s+main\s*\(", content))
    is_header = bool(re.search(r"#ifndef\s+_?[A-Za-z_\d]+", b)) and not has_c_def
    print(f"block {bi}: has_py={has_py} has_c_def={has_c_def} has_main={has_main} is_header={is_header}")
    print("   defs:", sorted({m.group(1) for m in FUNC_DEF_RE.finditer(content)}))
    print("   protos:", sorted({m.group(1) for m in PROTO_RE.finditer(content)}))
    print("   macros:", sorted({m.group(1) for m in MACRO_RE.finditer(b)}))
