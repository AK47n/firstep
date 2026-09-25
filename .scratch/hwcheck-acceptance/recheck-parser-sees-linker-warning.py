# -*- coding: utf-8 -*-
"""复测插曲之二：产品侧编译面板能不能看见链接器形态的告警（`warning #10210-D:`）。

起因：`ml_mpu6050` 那格真编译带 1 条 `.sysmem` 链接器告警，而工单 09 的矩阵把它记成
warning=0。两种可能：① 告警是后来才有的；② 矩阵的计数法看不见 `warning #` 形态。
本探针只回答"产品侧的解析器认不认这条"——把真告警原文喂给 `parse_compile_errors`。
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from contest_generator.compile_runner import parse_compile_errors, parsed_error_entries  # noqa: E402

LINKER_WARNING = (
    'warning #10210-D: creating ".sysmem" section with default size of 0x800; '
    "use the -heap option to change the default size"
)
COMPILER_WARNING = "main.c:12:9: warning: unused variable 'x' [-Wunused-variable]"
COMPILER_ERROR = "main.c:20:5: error: use of undeclared identifier 'foo'"

for label, text in [
    ("链接器告警（真原文，gmake）", LINKER_WARNING),
    ("编译器告警（对照）", COMPILER_WARNING),
    ("编译器错误（对照）", COMPILER_ERROR),
]:
    log = ">> Compilation failure\n" + text + "\nFinished building target: out\n"
    parsed = parse_compile_errors(log)
    entries = parsed_error_entries(parsed)
    print(f"[{label}] 解析出 {len(entries)} 条：{entries}")
