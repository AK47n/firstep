"""条目库原语：模块库 / 赛题库 / 参考文件库共用的"目录即数据库"骨架。

三库各自完整实现过一遍"条目目录 + JSON 元数据 + 浏览 / 事务入库"——同一事务
模式（建目录 → 写 payload → 失败清理不留半成品）在库与 master 归档流里出现
5 次；删除 ×4、JSON 读+校验 ×4、目录名 = 键的校验 ×4 也各实现一遍。本模块
把这些共用形状收敛一处：事务落盘、浏览目录迭代、JSON 元数据读写与校验、
已建目录清理、删除条目目录、键合法性校验、必填字符串字段校验。各库保留
独有的领域校验（slug 词表 / 赛题编号 / kit 与锚定词表）、模型与错误类型——
原语不持任何业务形状；存储与浏览入口分设的决策（ADR 0006）不动，共享的
只是内部原语。
"""

from __future__ import annotations

import json
import re
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Pattern, Sequence


class StoreError(ValueError):
    """条目库原语失败（读盘 / 键非法 / 查无此条 / 字段缺失）。

    错误类型与文案归各库（错误映射按域错误登记），本类只承载原语统一措辞，
    调用方捕获后转写自己的域错误（webapp 从不直接见到本类，errors.py 结构
    测试白名单登记）。.error 持原始异常（读盘 / 解析失败时非 None），域侧
    用它原样转写域文案。
    """

    def __init__(self, message: str, *, error: Exception | None = None) -> None:
        super().__init__(message)
        self.error = error


class StoreReadError(StoreError):
    """读盘失败（OSError）：.error 持原始异常。"""


class StoreParseError(StoreError):
    """JSON 解析失败（JSONDecodeError）：.error 持原始异常。"""


class StoreShapeError(StoreError):
    """JSON 形状非法（非 JSON 对象）。"""


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


def read_json(entry_dir: Path, filename: str) -> dict[str, Any]:
    """条目目录内读 JSON 元数据：读盘 / 解析 / 必须是 JSON 对象三层校验统一
    由本原语完成，失败抛 StoreReadError / StoreParseError / StoreShapeError
    （.error 持原始异常）；字段形状校验仍归各库（域错误类型与文案不变）。"""
    path = entry_dir / filename
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StoreReadError(f"无法读取 {path}: {exc}", error=exc) from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StoreParseError(f"无法解析 {path}: {exc}", error=exc) from exc
    if not isinstance(data, dict):
        raise StoreShapeError(f"{path} 必须是 JSON 对象")
    return data


def delete_entry(root: Path, name: str) -> None:
    """删除条目目录（rmtree）；查无此条大声失败（统一措辞）。键合法性由
    各库先校验（validate_store_key / 各自文法），本原语不做键校验。"""
    entry_dir = root / name
    if not entry_dir.is_dir():
        raise StoreError(f"条目 {name!r} 不存在")
    shutil.rmtree(entry_dir)


def validate_store_key(name: str, pattern: Pattern[str], what: str) -> None:
    """目录名 = 键的校验原语：非法键大声失败（统一措辞）。各库传自己的
    文法正则与域名（如 "slug" / "平台名"）——正则内容与错误类型仍归各库，
    这里只统一执行与措辞。"""
    if not pattern.fullmatch(name):
        raise StoreError(f"非法{what}：{name!r}")


def require_str(data: Mapping[str, Any], key: str) -> str:
    """元数据必填字符串字段校验：缺省 / 非字符串 / 空串大声失败（统一措辞，
    错误类型归各库——调用方捕获后转写域错误）。"""
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise StoreError(f"缺少必填字段：{key}")
    return value


def is_unsafe_path(path: str) -> bool:
    """路径必须是相对路径，不含 .. 、空段、绝对路径（跨目录逃逸风险）。"""
    return (
        path.startswith("/")
        or ":" in path
        or "\\" in path
        or any(part in ("", "..") for part in path.split("/"))
    )
