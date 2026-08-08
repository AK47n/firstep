"""条目库原语：模块库 / 赛题库 / 参考文件库共用的"目录即数据库"骨架。

三库各自完整实现过一遍"条目目录 + JSON 元数据 + 浏览 / 事务入库"——同一事务
模式（建目录 → 写 payload → 失败清理不留半成品）在库与 master 归档流里出现
5 次。本模块把这些共用形状收敛一处：事务落盘、浏览目录迭代、JSON 元数据
写入、已建目录清理。各库保留独有的领域校验（slug 词表 / 赛题编号 / kit 与
锚定词表）、模型与错误类型——原语不持任何业务形状；存储与浏览入口分设的
决策（ADR 0006）不动，共享的只是内部原语。
"""

from __future__ import annotations

import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


def iter_entry_dirs(root: Path) -> list[Path]:
    """库根下条目目录（按名排序）：跳过散文件与点开头目录（临时目录不影响
    浏览）；库根不存在 = 空库。损坏条目由调用方加载时大声失败（浏览不静默
    缺条目）。"""
    if not root.is_dir():
        return []
    return sorted(
        (
            entry
            for entry in root.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        ),
        key=lambda entry: entry.name,
    )


def discard_entry_dirs(paths: Sequence[Path]) -> None:
    """清理已建条目目录（ignore_errors：清理失败不掩盖原始错误，不留半成品）。"""
    for entry_dir in paths:
        shutil.rmtree(entry_dir, ignore_errors=True)


@contextmanager
def entry_transaction(root: Path, names: Sequence[str]) -> Iterator[list[Path]]:
    """建条目目录并兜底清理的事务：全部校验必须在事务外先完成（任何校验
    失败都在落盘前，目录都没建），本原语只兜底落盘中途失败——已建目录全部
    清理，不留半成品。返回已建目录列表供写入 payload。"""
    root.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for name in names:
            entry_dir = root / name
            entry_dir.mkdir()
            created.append(entry_dir)
        yield created
    except Exception:
        discard_entry_dirs(created)
        raise


def write_json(entry_dir: Path, filename: str, data: Mapping[str, Any]) -> None:
    """条目目录内写 JSON 元数据（ensure_ascii=False + indent=2，三库同款）。"""
    (entry_dir / filename).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
