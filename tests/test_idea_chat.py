"""工程级想法聊天（工单 idea-suite/01）：模型 / 落盘 / 追加 / 采纳单测。"""

import json

import pytest

from contest_generator.idea_chat import (
    IDEA_CHAT_FILENAME,
    append_chat_message,
    empty_chat,
    load_idea_chat_file,
    read_idea_chat,
    set_chat_note,
    write_idea_chat,
)
from contest_generator.task_progress import TaskError


def test_empty_chat_shape():
    """空聊天：messages 空、note 空串、generated_at 非空（供 read 兜底）。"""
    chat = empty_chat()
    assert chat.messages == ()
    assert chat.note == ""
    assert chat.generated_at
    data = chat.to_dict()
    assert set(data) == {"version", "generated_at", "messages", "note"}
    assert data["version"] == 1


def test_append_and_read_roundtrip(tmp_path):
    """追加式落盘：user + assistant 两条 → 读回逐字段一致（重开不丢）。"""
    chat = append_chat_message(read_idea_chat(tmp_path), "user", "整体架构要不要加滤波？")
    chat = append_chat_message(chat, "assistant", "可以，先加一阶低通滤波。")
    write_idea_chat(tmp_path, chat)

    assert (tmp_path / IDEA_CHAT_FILENAME).is_file()
    loaded = read_idea_chat(tmp_path)
    assert [m.role for m in loaded.messages] == ["user", "assistant"]
    assert loaded.messages[0].content == "整体架构要不要加滤波？"
    assert loaded.messages[1].content == "可以，先加一阶低通滤波。"
    assert loaded.messages[0].at and loaded.messages[1].at
    assert loaded.generated_at  # 首条消息时间戳播种


def test_read_missing_file_returns_empty(tmp_path):
    """无文件 → 空聊天（未聊过不 400）；load 原始层返回 None。"""
    assert load_idea_chat_file(tmp_path) is None
    chat = read_idea_chat(tmp_path)
    assert chat.messages == ()
    assert chat.note == ""


def test_append_rejects_unknown_role(tmp_path):
    """role 词表外 → TaskError（400 中文）。"""
    with pytest.raises(TaskError):
        append_chat_message(read_idea_chat(tmp_path), "system", "非法")


def test_set_note_overwrites_and_clears(tmp_path):
    """采纳 = 最新覆盖；空串 = 清除（未采纳）。"""
    chat = read_idea_chat(tmp_path)
    chat = set_chat_note(chat, "第一条全局结论")
    chat = append_chat_message(chat, "user", "再问一下")
    chat = set_chat_note(chat, "第二条全局结论（覆盖）")
    write_idea_chat(tmp_path, chat)
    assert read_idea_chat(tmp_path).note == "第二条全局结论（覆盖）"

    cleared = set_chat_note(read_idea_chat(tmp_path), "")
    write_idea_chat(tmp_path, cleared)
    assert read_idea_chat(tmp_path).note == ""


def test_load_bad_json_raises(tmp_path):
    """坏 JSON → TaskError（400 中文，不吞）。"""
    (tmp_path / IDEA_CHAT_FILENAME).write_text("{ 不是 JSON", encoding="utf-8")
    with pytest.raises(TaskError, match="损坏"):
        read_idea_chat(tmp_path)


def test_from_dict_tolerates_bad_message_entries(tmp_path):
    """读回侧容错：单条消息坏（role 词表外 / content 非字符串 / 非对象）→
    忽略该条；note 非字符串 → 空串；整份不拒收。"""
    raw = {
        "version": 1,
        "generated_at": "2024-01-01T00:00:00+0000",
        "messages": [
            {"role": "user", "content": "你好"},
            {"role": "system", "content": "坏角色"},
            {"role": "user", "content": 123},
            "不是对象",
            {"role": "assistant", "content": "回你"},
        ],
        "note": 999,
    }
    (tmp_path / IDEA_CHAT_FILENAME).write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8"
    )
    chat = read_idea_chat(tmp_path)
    assert [m.content for m in chat.messages] == ["你好", "回你"]
    assert chat.note == ""


def test_non_object_file_raises(tmp_path):
    """顶层非对象 → TaskError（400 中文）。"""
    (tmp_path / IDEA_CHAT_FILENAME).write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(TaskError, match="必须是 JSON 对象"):
        read_idea_chat(tmp_path)
