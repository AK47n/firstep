# -*- coding: utf-8 -*-
"""批次 11 同构对仗核对：代码与测试按 slug 归一化后与 mq8 基准逐行 diff。"""
import re
import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "library" / "modules"
TESTS = ROOT / "tests"
REF = "mq8"


def normalize(text: str, slug: str) -> str:
    t = text
    t = t.replace(slug, "###")            # mq3 -> ### (lowercase slug tokens)
    t = t.replace(slug.upper(), "###")    # MQ3 -> ###
    t = re.sub(r"MQ-?[0-9]+", "MQ-###", t)  # MQ-3 / MQ9 注释写法
    t = re.sub(r"MS1100", "MS100", t)
    return t


def show_diff(name: str, a: str, b: str, limit: int = 60) -> int:
    d = list(difflib.unified_diff(
        a.splitlines(), b.splitlines(), lineterm="", n=1))
    if not d:
        return 0
    print(f"--- {name} 与 {REF} 归一化差异（前 {limit} 行）---")
    for line in d[:limit]:
        print("   " + line)
    print(f"    （共 {len(d)} 行差异）")
    return len(d)


refc = (MOD / REF / "code" / f"{REF}.c").read_text(encoding="utf-8")
refh = (MOD / REF / "code" / f"{REF}.h").read_text(encoding="utf-8")
reft = (TESTS / f"test_module_{REF}.py").read_text(encoding="utf-8")
total = 0
for slug in ["mq3", "mq4", "mq6", "mq7", "mq9"]:
    c = (MOD / slug / "code" / f"{slug}.c").read_text(encoding="utf-8")
    h = (MOD / slug / "code" / f"{slug}.h").read_text(encoding="utf-8")
    t = (TESTS / f"test_module_{slug}.py").read_text(encoding="utf-8")
    total += show_diff(f"{slug}.c", normalize(c, slug), normalize(refc, REF))
    total += show_diff(f"{slug}.h", normalize(h, slug), normalize(refh, REF))
    total += show_diff(f"test_module_{slug}.py", normalize(t, slug),
                       normalize(reft, REF))
print(f"\n总差异块数: {total}")
