"""生成输出目标解析：桌面赛题目录命名与唯一化。

webapp 只负责收请求与调用 LLM；题名裁剪、Windows 文件名清洗和重名策略在
这里集中，避免把生成输出域逻辑塞进路由薄壳。
"""

from __future__ import annotations

import re
import time
from pathlib import Path

WINDOWS_RESERVED_FILENAMES = frozenset(
    {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)
_INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*]+')
_FILENAME_WHITESPACE_RE = re.compile(r"\s+")
_TOPIC_TITLE_PREFIX_RE = re.compile(r"^(?:题名|标题|赛题名称|赛题名)[:：]\s*")


def topic_title_from_summary(summary: str) -> str:
    """赛题简介文本 → 适合目录名的题名候选。

    现有 LLM 协议的 `summarize_topic` 首行是“这个赛题要做什么样的装置 / 系统”
    的一句话总览；目录名只取首个非列表行，避免把后续功能要点整段塞进路径。
    """
    for raw_line in summary.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("- "):
            continue
        return _TOPIC_TITLE_PREFIX_RE.sub("", line).strip()
    return summary.strip()


def windows_safe_folder_name(title: str) -> str:
    """AI 题名 → Windows 目录名：清非法字符、空白和保留设备名。"""
    name = _INVALID_FILENAME_CHARS_RE.sub("_", title)
    name = _FILENAME_WHITESPACE_RE.sub(" ", name).strip(" ._")
    if not name:
        name = "赛题工程"
    name = name[:80].rstrip(" .") or "赛题工程"
    if _is_windows_reserved_filename(name):
        name = f"{name}_"
    return name


def unique_desktop_topic_dir(desktop_dir: Path, title: str) -> Path:
    """桌面根 + 题名 → 唯一输出目录；重名追加时间，再冲突追加序号。"""
    base = windows_safe_folder_name(title)
    candidate = desktop_dir / base
    if not candidate.exists():
        return candidate

    stamp_base = base.rstrip("_") or base
    stamped = f"{stamp_base}_{time.strftime('%Y%m%d-%H%M%S')}"
    candidate = desktop_dir / stamped
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = desktop_dir / f"{stamped}_{index}"
        if not candidate.exists():
            return candidate
        index += 1


def _is_windows_reserved_filename(name: str) -> bool:
    """Windows 保留设备名含扩展名形态同样非法：CON 与 CON.txt 都要避开。"""
    stem = name.rstrip(" .").split(".", 1)[0].upper()
    return stem in WINDOWS_RESERVED_FILENAMES
