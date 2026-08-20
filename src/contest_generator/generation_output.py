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
_TOPIC_LINE_MARKDOWN_RE = re.compile(r"^#{1,6}\s*")
_TOPIC_LINE_PREFIX_RE = re.compile(r"^[A-Za-z0-9]+\s*题\s*[:：]\s*")
_TOPIC_TRAILING_PAREN_RE = re.compile(r"（[^）]*(?:题|本科|高职|组)[^）]*）$")


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


def topic_short_title(problem_text: str) -> str:
    """赛题题面首行 → 短题名（目录名用，确定性）。

    历史赛题首行形态：`自动行驶小车（H 题）` / `C 题：无线充电电动小车（本科）`
    / `# 基于无线通信的数字钥匙实验系统（C题）`——去掉 markdown 标题符、
    行首题号前缀与行尾（题号/组别）括号，得 `自动行驶小车` 式短名。
    """
    first = next(
        (line.strip() for line in problem_text.splitlines() if line.strip()), ""
    )
    line = _TOPIC_LINE_MARKDOWN_RE.sub("", first)
    line = _TOPIC_LINE_PREFIX_RE.sub("", line).strip()
    line = _TOPIC_TRAILING_PAREN_RE.sub("", line).strip()
    return line or first


def topic_dir_title(key: str, problem_text: str) -> str:
    """历史赛题目录名：`2024H 自动行驶小车`（编号 + 首行短题名）。

    修订（2024H 复盘）：有历史赛题编号时目录名不再取 AI 简介首行——简介是
    长句（如“设计一个采用 TI MSPM0 系列 MCU 控制的自动行驶小车…”），目录名
    又长又每次生成都可能变；编号 + 短题名稳定、可预期。
    """
    return f"{key} {topic_short_title(problem_text)}".strip()


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
