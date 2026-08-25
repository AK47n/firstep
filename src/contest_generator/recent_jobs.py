"""最近生成记录（工单 recent-jobs/01）：recent.json 落盘，cap 20 条。

用户场景 = 一题做几天：生成工程后关页面，第二天打开要能一眼看到上次
生成到哪（输出目录）、编译过没有（状态）。记录由 /api/generate 成功时
自动写入（status=generated），编译完成由前端上报状态（ok / warn / failed）。

设计：纯函数 + 显式文件路径（测试注入 tmp）；原子写（同目录 tmp +
os.replace，绝不写半个文件）；损坏 / 缺失 / 非列表 → 空列表不炸（本地
工具，记录文件坏了不该挡生成主流程）；同 output_dir 重复记录 = 更新
移到头部（防手动模式重生成同目录时列表膨胀）。
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

MAX_RECENT = 20

STATUS_GENERATED = "generated"
STATUS_OK = "compiled_ok"
STATUS_WARN = "compiled_warn"
STATUS_FAILED = "compile_failed"
# 状态白名单（模块层拒绝未知值；路由经 errors.py 映射为 400 中文）
RECENT_STATUSES = (STATUS_GENERATED, STATUS_OK, STATUS_WARN, STATUS_FAILED)


class RecentStatusError(ValueError):
    """最近生成状态非法（工单 recent-jobs/01）：未知状态上报值，注册于
    errors.py（与 LibraryError/StageError 同款业务失败 → 400 中文）。"""


def recent_file(config_path: Path) -> Path:
    """记录文件路径 = 配置文件同目录（~/.contest_generator/recent.json）。"""
    return Path(config_path).parent / "recent.json"


def _read(fp: Path) -> list[dict[str, Any]]:
    # utf-8-sig：容忍 Windows 记事本 / PowerShell 写出的 BOM（本地工具，
    # 用户可能手改 recent.json；BOM 会让 json.loads 抛 ValueError 静默丢条）
    try:
        data = json.loads(Path(fp).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict)]


def _write(fp: Path, entries: list[dict[str, Any]]) -> None:
    fp.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(fp.parent), prefix="recent-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
        os.replace(tmp, fp)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_recent(fp: Path) -> list[dict[str, Any]]:
    """读取列表（新 → 旧，cap MAX_RECENT）；不存在 / 损坏 → 空列表。"""
    return _read(fp)[:MAX_RECENT]


def record_recent(
    fp: Path,
    *,
    output_dir: str,
    platform: str,
    slugs: list[str],
    topic_id: str | None = None,
) -> dict[str, Any]:
    """生成成功记录：插头部，cap 20；同 output_dir 已存在 → 更新移到头部。

    返回新记录（id / ts / status=generated 一并回显，供测试与前端核对）。
    """
    entries = _read(fp)
    entry: dict[str, Any] = {
        "id": uuid.uuid4().hex,
        "ts": f"{time.time():.3f}",
        "output_dir": str(output_dir),
        "platform": platform,
        "slugs": list(slugs),
        "status": STATUS_GENERATED,
    }
    if topic_id:
        entry["topic_id"] = topic_id
    entries = [e for e in entries if e.get("output_dir") != entry["output_dir"]]
    entries.insert(0, entry)
    _write(fp, entries[:MAX_RECENT])
    return entry


def update_recent_status(fp: Path, output_dir: str, status: str) -> dict[str, Any] | None:
    """按输出目录更新状态（前端编译完成后上报）；未知 status 抛 ValueError。

    返回更新后的记录；目录无记录 → None（调用方忽略，不建假记录）。
    """
    if status not in RECENT_STATUSES:
        raise RecentStatusError(f"未知状态：{status}")
    entries = _read(fp)
    for entry in entries:
        if entry.get("output_dir") == str(output_dir):
            entry["status"] = status
            _write(fp, entries)
            return dict(entry)
    return None


def delete_recent(fp: Path, entry_id: str) -> bool:
    """按 id 删除（清错记 / 不想要的）；存在删除返回 True，不存在 False。"""
    entries = _read(fp)
    kept = [e for e in entries if e.get("id") != entry_id]
    if len(kept) == len(entries):
        return False
    _write(fp, kept)
    return True
