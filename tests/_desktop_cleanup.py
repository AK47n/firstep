"""桌面测试产物清理（conftest 收尾钩子的核心逻辑，独立模块便于单测）。

生成类测试经 /api/generate 桌面模式（payload 带 problem_text 且未显式关
桌面输出）落盘到真实桌面，FakeLLM 的 summarize_topic 返回 fallback 默认值
→ 目录名固定为「AI 生成的赛题简介_时间戳」。只清该前缀目录（LLM 成功时
是赛题名目录、用户真实产物，绝不误删）。
"""

from __future__ import annotations

import shutil
from pathlib import Path

#: 测试产物目录名前缀（FakeLLM fallback 默认值，见 tests/fakes.py）
FALLBACK_DIR_PREFIX = "AI 生成的赛题简介"


def cleanup_desktop_test_artifacts(desktop: Path) -> list[str]:
    """删除桌面下以 FALLBACK_DIR_PREFIX 开头的目录；返回删除清单。"""
    if not desktop.is_dir():
        return []
    removed: list[str] = []
    for p in desktop.iterdir():
        if p.is_dir() and p.name.startswith(FALLBACK_DIR_PREFIX):
            shutil.rmtree(p, ignore_errors=True)
            removed.append(p.name)
    return removed
