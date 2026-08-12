"""真机验收（工单 fix-snippet-match/01）：2026C 注入带行尾注释错误行 →
真实 DeepSeek fix-errors 第 1 轮应 applied（对比 compile-error-fix/01 历史
第 1 轮 skipped）。

复刻 webapp /api/fix-errors 的装配：parse → collect → read_contexts → 真实
LLM → apply_fixes。输出逐处结果 + 备份编号 + 重编译指引。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from contest_generator.config import load_config
from contest_generator.fix_errors import (
    apply_fixes,
    collect_candidate_paths,
    fix_backup_root,
    parse_compile_errors,
    read_file_contexts,
)
from contest_generator.llm import DeepSeekLLM

OUT = ROOT / ".scratch/fix-snippet-match/out_2026C_stm32"
WORK_ROOT = Path.home() / ".contest_generator"

# 1) 从 Keil build_log 提取真实报错文本（编译是真实 UV4 -r -b 跑出来的）
log = (OUT / "user/Objects/Project.build_log.htm").read_text(
    encoding="utf-8", errors="replace"
)
error_text = re.sub(r"<[^>]+>", "", log)
error_text = (
    error_text.replace("&nbsp;", " ").replace("&quot;", '"').replace("&amp;", "&")
)
print("=== 报错全文（去 HTML 标签） ===")
for line in error_text.splitlines():
    if "error" in line.lower() or "Error(s)" in line:
        print(line)

# 2) 上下文（与 webapp 装配同款：题面 / 平台 / 模块 / main.c）
problem_text = (WORK_ROOT / "topics/2026C/topic.md").read_text(
    encoding="utf-8", errors="replace"
)
slugs = tuple(
    p.name for p in sorted((OUT / "modules").iterdir()) if p.is_dir()
)
main_c = (OUT / "main.c").read_text(encoding="utf-8", errors="replace")

# 3) 真实 DeepSeek 修复（单轮，不重试——验证第 1 轮即收敛）
errors = parse_compile_errors(error_text)
candidates = collect_candidate_paths(OUT, errors)
contexts, dropped = read_file_contexts(OUT, candidates)
print("\n=== 解析 ===")
print("parsed:", [(e.path, e.line) for e in errors])
print("candidates:", candidates, "dropped:", dropped)

llm = DeepSeekLLM(load_config())
print("\n=== 真实 DeepSeek 修复中（分钟级） ===")
fixes = llm.fix_compile_errors(
    error_text,
    dict(contexts),
    problem_text=problem_text,
    platform="stm32",
    module_slugs=slugs,
    main_c=main_c,
    dropped_files=dropped,
)
print("LLM fixes:", len(fixes))

report = apply_fixes(fixes, OUT, fix_backup_root(WORK_ROOT))
print("\n=== 应用结果（第 1 轮） ===")
for r in report.results:
    print(f"[{r.status}] {r.file}:{r.line} — {r.reason}")
print("backup_id:", report.backup_id)
