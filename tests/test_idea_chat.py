"""工程级想法聊天（工单 idea-suite/01）：模型 / 落盘 / 追加 / 采纳单测。

`record-write-hardening/03` 起补「记录写的正确性形状」一节：唯一临时名 + 原子替换 +
**按记录路径的短临界区**（两份历史各一把锁）、跨慢窗口的追加重放。
"""

import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from contest_generator.idea_chat import (
    IDEA_CHAT_FILENAME,
    PARAMS_CHAT_FILENAME,
    append_chat_message,
    empty_chat,
    load_idea_chat_file,
    read_idea_chat,
    set_chat_note,
    update_idea_chat,
    write_idea_chat,
)
from contest_generator.task_progress import TaskError
from tests.concurrency import run_in_thread


class _SentinelReplaceError(OSError):
    """注入用的哨兵异常：断言"抛出来的就是它"，而不是"抛了某个 OSError"。"""


def _residue(directory: Path) -> list[str]:
    """除两份聊天记录外的东西（`iterdir` 而不是 `glob("*.tmp")`——临时名带 pid + 计数后
    那个 glob 匹配不到新名字 = 断言空转；形状照 `tests/test_atomic_io.py:29`）。"""
    keep = {IDEA_CHAT_FILENAME, PARAMS_CHAT_FILENAME}
    return [p.name for p in directory.iterdir() if p.name not in keep]


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


def test_filename_param_isolates_chats(tmp_path):
    """filename 参数化（工单 params-chat-ai/01）：同一读写 API 对不同文件名
    互不干扰——写参数速调咨询文件读工程级聊天 = 空；默认参数仍写原文件。"""
    from contest_generator.idea_chat import PARAMS_CHAT_FILENAME

    chat = read_idea_chat(tmp_path, PARAMS_CHAT_FILENAME)
    chat = append_chat_message(chat, "user", "跑偏了调哪个？")
    chat = append_chat_message(chat, "assistant", "先调 THRESHOLD。")
    write_idea_chat(tmp_path, chat, PARAMS_CHAT_FILENAME)

    assert (tmp_path / PARAMS_CHAT_FILENAME).is_file()
    assert not (tmp_path / IDEA_CHAT_FILENAME).exists()
    loaded = read_idea_chat(tmp_path, PARAMS_CHAT_FILENAME)
    assert [m.content for m in loaded.messages] == ["跑偏了调哪个？", "先调 THRESHOLD。"]
    # 默认文件名仍读原工程级聊天（无文件 = 空）；显式同名 = 一致
    assert read_idea_chat(tmp_path).messages == ()
    assert read_idea_chat(tmp_path, IDEA_CHAT_FILENAME).messages == ()


def test_bad_params_chat_file_message_names_file(tmp_path):
    """坏参数速调咨询文件 → TaskError 消息带该文件名（不误导为工程级文件）。"""
    from contest_generator.idea_chat import PARAMS_CHAT_FILENAME

    (tmp_path / PARAMS_CHAT_FILENAME).write_text("{ 坏", encoding="utf-8")
    with pytest.raises(TaskError, match=PARAMS_CHAT_FILENAME):
        read_idea_chat(tmp_path, PARAMS_CHAT_FILENAME)


# ---------------------------------------------------------------------------
# 记录写的正确性形状：唯一临时名 + 原子替换 + 按记录路径的短临界区（工单 03）
#
# 收走前的形状（本单要挡的）：固定临时名 `…json.tmp` + 无锁的"读-改-写"。
# 最疼的一条横跨模型调用：一轮全局商量要**秒级**，这期间学生若在另一处采纳结论，
# 商量结束时的整份写回会把他刚采纳的结论抹掉——而他看到的是"采纳成功了"。
# ---------------------------------------------------------------------------



def test_idea_chat_write_leaves_no_tmp_behind(tmp_path):
    """原子写：落盘后除记录文件外**一个文件都没有**（成功路径也不许留残渣）。"""
    write_idea_chat(tmp_path, append_chat_message(empty_chat(), "user", "你好"))
    assert _residue(tmp_path) == [], f"落盘后留下了临时文件：{_residue(tmp_path)}"


def test_idea_chat_write_failure_leaves_no_residue_and_keeps_the_original_error(
    tmp_path, monkeypatch
):
    """坏写：临时文件必须被清掉，且**原异常照抛**（不许被清理动作掩盖成另一个异常）。

    注入点打在共享原语看到的 `os` 上（写实现归 `atomic_io`）：`replace` 抛哨兵异常，
    此刻临时文件**真的在盘上**（上一步刚写完）——不这样造，`finally` 里没东西可清 = 判据空转。
    """
    import contest_generator.atomic_io as atomic_io

    boom = _SentinelReplaceError("替换失败")

    def failing_replace(src, dst):
        raise boom

    monkeypatch.setattr(
        atomic_io,
        "os",
        SimpleNamespace(path=os.path, getpid=os.getpid, replace=failing_replace),
    )
    with pytest.raises(_SentinelReplaceError) as caught:
        write_idea_chat(tmp_path, append_chat_message(empty_chat(), "user", "你好"))
    assert caught.value is boom, "抛出来的不是原异常（被清理动作掩盖了）"
    assert _residue(tmp_path) == [], "写失败后留下了临时文件"


def test_concurrent_idea_chat_writes_share_no_tmp_file(tmp_path, monkeypatch):
    """两个写者并发：**不许抢同一个临时名**——收走前抢了，先来的那个 `replace` 会落空。

    确定性做法（照 `tests/test_hwcheck_triage.py`）：把**第一个** `replace` 卡住
    （此刻它的临时文件还在盘上），让第二个写者从头走完一遍，再放行第一个。
    两次**真实** `replace` 刻意不重叠（第二个先落盘再放行第一个）：Windows 上并发替换
    同一目标会以 `WinError 5` 失败，那是"谁先落盘"的另一回事。
    """
    import contest_generator.atomic_io as atomic_io

    first_inside = threading.Event()
    release = threading.Event()
    calls = {"n": 0}
    real_replace = os.replace

    def slow_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:
            first_inside.set()
            assert release.wait(timeout=30), "等不到放行——判据自己失败，别挂住整场"
        return real_replace(src, dst)

    monkeypatch.setattr(
        atomic_io,
        "os",
        SimpleNamespace(path=os.path, getpid=os.getpid, replace=slow_replace),
    )
    errors: list[BaseException] = []

    def write(text: str) -> None:
        try:
            write_idea_chat(tmp_path, append_chat_message(empty_chat(), "user", text))
        except BaseException as exc:  # noqa: BLE001 —— 线程里的异常要带回主线程断言
            errors.append(exc)

    def run(work):
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        return thread

    first = run(lambda: write("先到的"))
    assert first_inside.wait(timeout=30), "第一个写者没走到替换那一步"
    second = run(lambda: write("后到的"))
    second.join(timeout=30)
    release.set()
    first.join(timeout=30)

    assert errors == [], f"并发写报错（临时名互抢）：{errors!r}"
    assert _residue(tmp_path) == [], f"并发写留下了残留：{_residue(tmp_path)}"
    contents = [m.content for m in read_idea_chat(tmp_path).messages]
    assert contents in (["先到的"], ["后到的"])


def test_two_chat_files_do_not_share_a_lock(tmp_path):
    """两份历史各拿一把锁：全局商量那一路卡在自己合并里时，参数商量照样写完。

    判据取"参数商量在全局商量还卡着的时候就已经落盘"——`path_lock` 的键**含文件名**
    （工单 01 立的地基）；若两份文件共用一把锁，这里会等不到（判据红）。
    """
    entered = threading.Event()
    release = threading.Event()
    params_done = threading.Event()
    errors: list[BaseException] = []

    def slow_merge(latest):
        entered.set()
        assert release.wait(timeout=30), "等不到放行——判据自己失败，别挂住整场"
        return append_chat_message(latest, "user", "整体架构要不要加滤波？")

    def params_round() -> None:
        update_idea_chat(
            tmp_path,
            lambda latest: set_chat_note(latest, "先调 THRESHOLD"),
            PARAMS_CHAT_FILENAME,
        )
        params_done.set()

    first = run_in_thread(errors, lambda: update_idea_chat(tmp_path, slow_merge))
    assert entered.wait(timeout=30), "全局商量那一路没进临界区"

    second = run_in_thread(errors, params_round)
    assert params_done.wait(timeout=5), "两份历史共锁了：参数商量被全局商量挡在门外"
    release.set()
    first.join(timeout=30)
    second.join(timeout=30)

    assert errors == [], f"并发写报错：{errors!r}"
    assert [m.content for m in read_idea_chat(tmp_path).messages] == [
        "整体架构要不要加滤波？"
    ]
    assert read_idea_chat(tmp_path, PARAMS_CHAT_FILENAME).note == "先调 THRESHOLD"
    assert _residue(tmp_path) == [], "两份历史都写完之后留下了残渣"


def test_update_idea_chat_keeps_an_adopt_that_landed_in_the_slow_window(tmp_path):
    """跨慢窗口的追加重放：模型调用那几秒里别人采纳了结论 → **两笔都在**。

    形状 = 两个 send 端点那一路：进模型调用**之前**先读一份（喂 history / note 用）；
    窗口里另一处采纳结论；模型答完之后才拿"追加本轮两条"的 merge 进来。这里把窗口的
    尾巴钉死在**合并那一刻**（A 卡在自己的合并里，采纳那一路同时来）——合并里拿到的是
    **重读**的那份，所以两条消息追加在它上面。
    · 撤掉临界区 / 把重读挪到锁外：采纳那笔会被 A 手上的旧快照盖掉（note 丢，或
      消息丢——两条断言分别盖住两种）；
    · 收走后：新 note 与本轮两条消息都在。
    """
    base = read_idea_chat(tmp_path)  # 模型调用之前读的那份（note 空）
    assert base.note == ""
    entered = threading.Event()
    release = threading.Event()
    adopt_done = threading.Event()
    errors: list[BaseException] = []

    def slow_merge(latest):
        """临界区里拿到的是**重读**的那份——本轮两条追加在它上面。"""
        entered.set()
        assert release.wait(timeout=30), "等不到放行——判据自己失败，别挂住整场"
        latest = append_chat_message(latest, "user", "整体架构要不要加滤波？")
        return append_chat_message(latest, "assistant", "先加一阶低通，再接 PID。")

    def adopt() -> None:
        update_idea_chat(
            tmp_path,
            lambda latest: set_chat_note(latest, "全局结论：先保证循迹稳定"),
        )
        adopt_done.set()

    first = run_in_thread(errors, lambda: update_idea_chat(tmp_path, slow_merge))
    assert entered.wait(timeout=30), "商量那一路没进临界区"

    second = run_in_thread(errors, adopt)
    adopt_done.wait(timeout=1.0)  # 无锁那一格：这里会先写完；有锁那一格：等不到
    release.set()
    first.join(timeout=30)
    second.join(timeout=30)

    assert errors == [], f"并发写报错：{errors!r}"
    on_disk = read_idea_chat(tmp_path)
    assert on_disk.note == "全局结论：先保证循迹稳定", "窗口里采纳的结论被旧快照盖掉了"
    assert [m.content for m in on_disk.messages] == [
        "整体架构要不要加滤波？",
        "先加一阶低通，再接 PID。",
    ], "本轮两条消息没落上（采纳那一路读的是锁外的旧快照）"
