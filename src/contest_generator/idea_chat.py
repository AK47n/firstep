"""工程级想法聊天（工单 idea-suite/01）：全局商量 + 采纳为全局结论。

与任务卡商量（task-chat，会话级不落盘）不同：本模块是**工程级**多轮对话，
历史落盘工程根 `.contest_idea_chat.json`——纯新增隐藏文件（.contest_tasks.json
先例），与生成产物零交叉。采纳的全局结论（note，最新覆盖）注入后续每步
任务执行与直接修正的 prompt（【工程级全局结论】段，
llm._task_execute_user_prompt / _idea_fix_user_prompt 的 global_note 参数）。

**文件形状**（落盘与读回 = 同一模型，version 向后兼容）：

    {"version": 1, "generated_at": "…",
     "messages": [{"role": "user", "content": "…", "at": "…"},
                  {"role": "assistant", "content": "…", "at": "…"}],
     "note": "采纳的全局结论（最新覆盖，空串 = 未采纳）"}

坏 JSON / 非对象 → TaskError（400 中文，照 task_progress 清单文件先例）；
消息条逐条容错（role 词表外 / content 非字符串 → 忽略该条，坏值不误伤
全聊天——与 _parse_iterations 读回侧同哲学）。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .task_progress import TaskError

# 聊天文件名（写侧单源，webapp / 前端共用）
IDEA_CHAT_FILENAME = ".contest_idea_chat.json"

# 聊天版本：向后兼容读（未知版本容忍：只读已知字段，缺省补默认）
IDEA_CHAT_VERSION = 1

# 消息角色词表（单源：解析 / 追加共用）
IDEA_CHAT_ROLES = frozenset({"user", "assistant"})


@dataclass(frozen=True)
class IdeaMessage:
    """一条聊天消息（用户 / AI 交替，旧 → 新）。

    role = user | assistant；content = 文本；at = 时间戳。
    """

    role: str
    content: str
    at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "content": self.content, "at": self.at}


@dataclass(frozen=True)
class IdeaChat:
    """工程级聊天记录：全部消息 + 已采纳的全局结论（note）。

    messages = 旧 → 新全部消息（追加式落盘，重开不丢）；note = 采纳的
    全局结论全文（最新覆盖，空串 = 未采纳——采纳可选，与 dialog_note 同
    语义：空串即未采纳，不区分「清除」与「从未采纳」）。
    """

    version: int = IDEA_CHAT_VERSION
    generated_at: str = ""
    messages: tuple[IdeaMessage, ...] = ()
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "messages": [message.to_dict() for message in self.messages],
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> IdeaChat:
        """读回侧解释链（文件 → 模型）：字段缺失/类型错 → TaskError。

        缺省补默认（旧版本 / 手改兼容）：version 1、generated_at 空、
        messages 空、note 空串；未知字段忽略。单条消息 role 词表外 /
        content 非字符串 → 忽略该条（与 _parse_iterations 同哲学：坏值
        不误伤全聊天——展示与注入辅助，宁丢一条不拒收整份）。
        """
        version = raw.get("version", IDEA_CHAT_VERSION)
        if not isinstance(version, int) or isinstance(version, bool):
            raise TaskError(f"工程商量记录 version 非法：{version!r}")
        generated_at = raw.get("generated_at", "")
        if not isinstance(generated_at, str):
            raise TaskError("工程商量记录 generated_at 必须是字符串")
        raw_messages = raw.get("messages", [])
        if not isinstance(raw_messages, list):
            raise TaskError("工程商量记录 messages 必须是数组")
        messages: list[IdeaMessage] = []
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role not in IDEA_CHAT_ROLES or not isinstance(content, str):
                continue
            at = item.get("at", "")
            messages.append(
                IdeaMessage(role=role, content=content, at=at if isinstance(at, str) else "")
            )
        note = raw.get("note", "")
        if not isinstance(note, str):
            note = ""
        return cls(
            version=version,
            generated_at=generated_at,
            messages=tuple(messages),
            note=note,
        )


def empty_chat() -> IdeaChat:
    """空聊天（未聊过——read 的兜底形状，不 400）。"""
    return IdeaChat(generated_at=_now_stamp())


def load_idea_chat_file(output_dir: Path) -> dict[str, Any] | None:
    """读聊天原始 dict；无文件 = None；坏 JSON / 非对象 = TaskError（400）。"""
    path = output_dir / IDEA_CHAT_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskError(
            f"工程商量记录 {IDEA_CHAT_FILENAME} 损坏（不是合法 JSON）：{exc}"
        ) from exc
    if not isinstance(data, dict):
        raise TaskError(f"工程商量记录 {IDEA_CHAT_FILENAME} 必须是 JSON 对象")
    return data


def read_idea_chat(output_dir: Path) -> IdeaChat:
    """读聊天记录；无文件 = 空聊天（未聊过，不 400——与 plan-read 同先例）。"""
    raw = load_idea_chat_file(output_dir)
    if raw is None:
        return empty_chat()
    return IdeaChat.from_dict(raw)


def write_idea_chat(output_dir: Path, chat: IdeaChat) -> Path:
    """写聊天记录（原子写：先写 .tmp 再替换，坏写不落半成品）。"""
    path = output_dir / IDEA_CHAT_FILENAME
    tmp = path.with_name(IDEA_CHAT_FILENAME + ".tmp")
    tmp.write_text(
        json.dumps(chat.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(path)
    return path


def append_chat_message(chat: IdeaChat, role: str, content: str) -> IdeaChat:
    """追加一条消息（纯函数）：role 词表外 → TaskError；content 原样（不剥
    空白——消息是用户原话，注入 prompt 时由截断层处理）。"""
    if role not in IDEA_CHAT_ROLES:
        raise TaskError(f"聊天消息 role 必须是 user 或 assistant：{role!r}")
    stamp = _now_stamp()
    message = IdeaMessage(role=role, content=content, at=stamp)
    return IdeaChat(
        version=chat.version,
        generated_at=chat.generated_at or stamp,
        messages=chat.messages + (message,),
        note=chat.note,
    )


def set_chat_note(chat: IdeaChat, text: str) -> IdeaChat:
    """采纳 / 清除全局结论（纯函数）：最新覆盖；空串 = 清除（未采纳）。"""
    return IdeaChat(
        version=chat.version,
        generated_at=chat.generated_at,
        messages=chat.messages,
        note=text.strip() if isinstance(text, str) else "",
    )


def _now_stamp() -> str:
    """消息/文件时间戳（与任务迭代记录同格式）。"""
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")
