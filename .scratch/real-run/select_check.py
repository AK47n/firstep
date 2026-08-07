"""选模块真机验收（工单 05 checklist 4）：真实 DeepSeek 跑选模块，看推荐能否分辨套件与专用性。

用法：python select_check.py <赛题文本文件>
例：python select_check.py C:/Users/luoji/Desktop/2026C/赛题原文.md
"""
import sys
from pathlib import Path

from contest_generator.config import load_config
from contest_generator.library import list_modules
from contest_generator.llm import DeepSeekLLM, build_manifest_summaries


def main() -> None:
    problem_text = Path(sys.argv[1]).read_text(encoding="utf-8")
    config = load_config()
    root = Path(config.module_library_dir)
    summaries = build_manifest_summaries(list_modules(root))
    print("=== 喂给 AI 的模块清单 ===")
    for line in summaries:
        print(line)
    print("\n=== AI 推荐 ===")
    selection = DeepSeekLLM(config).select_modules(problem_text, summaries)
    for slug in selection.modules:
        print(f"- {slug}: {selection.reasons.get(slug, '')}")


if __name__ == "__main__":
    main()
