"""想法草稿箱（工单 idea-suite/05）：工程目录落盘 .contest_ideas.json。

现场连冒多个念头时先「存入草稿」，逐条或批量分析（前端工单 06 消费）。
模型 / 落盘 / 校验照 idea_chat.py 先例：坏 JSON → TaskError 400 中文
（「宁拒收不吞」——损坏即显式报错，不静默丢数据）；单条坏记录忽略
（条目级容错，同 IdeaChat.from_dict 哲学）；未知 id 删除静默（幂等）。
from task_progress import TaskError（防环：task_progress 不 import drafts）。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .task_progress import TaskError

IDEA_DRAFTS_FILENAME = ".contest_ideas.json"
IDEA_DRAFTS_VERSION = 1


@dataclass(frozen=True)
class IdeaDraft:
    """一条想法草稿：id（uuid4 hex 前 12 位）、text（用户原文，strip 后落盘）、
    at（创建时间戳，%Y-%m-%dT%H:%M:%S%z）。"""

    id: str
    text: str
    at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "at": self.at}


@dataclass(frozen=True)
class IdeaDrafts:
    """草稿集合（落盘与读回 = 同一模型）。"""

    version: int = IDEA_DRAFTS_VERSION
    drafts: tuple[IdeaDraft, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "drafts": [draft.to_dict() for draft in self.drafts],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> IdeaDrafts:
        """读回侧解释链：字段缺失 / 类型错 → TaskError；单条坏记录忽略。

        缺省补默认（旧版本 / 手改兼容）：version 默认 1、drafts 空；
        未知字段忽略；drafts 非数组 → TaskError（结构级拒收——顶层形状错
        说明文件被外部破坏，乱猜会吞数据）；条目非对象 / text 非字符串 /
        id 非字符串 → 忽略该条（宁丢一条不拒收整份，同 IdeaChat.from_dict）。
        """
        version = raw.get("version", IDEA_DRAFTS_VERSION)
        if not isinstance(version, int) or isinstance(version, bool):
            raise TaskError(f"想法草稿 version 非法：{version!r}")
        raw_drafts = raw.get("drafts", [])
        if not isinstance(raw_drafts, list):
            raise TaskError("想法草稿 drafts 必须是数组")
        drafts: list[IdeaDraft] = []
        for item in raw_drafts:
            if not isinstance(item, Mapping):
                continue
            draft_id = item.get("id")
            text = item.get("text")
            if not isinstance(draft_id, str) or not isinstance(text, str):
                continue
            at = item.get("at", "")
            drafts.append(
                IdeaDraft(
                    id=draft_id,
                    text=text,
                    at=at if isinstance(at, str) else "",
                )
            )
        return cls(version=version, drafts=tuple(drafts))


def empty_drafts() -> IdeaDrafts:
    return IdeaDrafts()


def load_drafts_file(output_dir: Path) -> dict[str, Any] | None:
    """读侧（照 load_idea_chat_file）：无文件 = None；坏 JSON / 非对象 →
    TaskError 400 中文（损坏即报错，留给用户处理而非静默清空）。"""
    path = output_dir / IDEA_DRAFTS_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TaskError(
            f"想法草稿记录 {path.name} 损坏（不是合法 JSON）：{exc}"
        ) from exc
    if not isinstance(data, dict):
        raise TaskError(f"想法草稿记录 {path.name} 必须是 JSON 对象")
    return data


def read_drafts(output_dir: Path) -> IdeaDrafts:
    """读侧（无文件 = 空集合，不 400——照 read_idea_chat 先例）。"""
    data = load_drafts_file(output_dir)
    if data is None:
        return empty_drafts()
    return IdeaDrafts.from_dict(data)


def write_drafts(output_dir: Path, drafts: IdeaDrafts) -> Path:
    """草稿落盘（原子写 .tmp → replace，照 idea_chat.py；目录损坏风险与
    文件级坏 JSON 不同——写碎文件比写坏文件更不易自愈）。"""
    path = output_dir / IDEA_DRAFTS_FILENAME
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(drafts.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def _now_stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def add_draft(drafts: IdeaDrafts, text: object) -> IdeaDrafts:
    """新增一条草稿（纯函数）：text 空 / 纯空白 → TaskError；strip 后与
    既有草稿同文本 → 原样返回（去重——同文本只存一条，spec 故事 8）；
    id = uuid4 hex 前 12 位（全局唯一，删除按 id 定位）。

    入参标 object（mypy 基线遗留）：函数本身做 isinstance 收窄，端点把
    payload 原值直接传进来；标 str 会让调用点被判类型不兼容。
    """
    if not isinstance(text, str) or not text.strip():
        raise TaskError("草稿 text 必须是非空字符串")
    cleaned = text.strip()
    if any(draft.text == cleaned for draft in drafts.drafts):
        return drafts
    draft = IdeaDraft(id=uuid.uuid4().hex[:12], text=cleaned, at=_now_stamp())
    return IdeaDrafts(
        version=drafts.version,
        drafts=drafts.drafts + (draft,),
    )


def delete_draft(drafts: IdeaDrafts, draft_id: str) -> IdeaDrafts:
    """删除一条草稿（纯函数）：未知 id 静默原样返回（幂等——删除不存在
    的草稿不是错误；前端可能双击删除按钮）。"""
    if not isinstance(draft_id, str):
        return drafts
    return IdeaDrafts(
        version=drafts.version,
        drafts=tuple(d for d in drafts.drafts if d.id != draft_id),
    )
