"""想法草稿箱（工单 idea-suite/05）：模型 / 落盘 / 坏 JSON / 去重 / 删除的测试。

只测外部行为：add 去重与 id 分配、delete 幂等、read 无文件空集合、
写盘 roundtrip、坏 JSON → TaskError 400 中文（宁拒收不吞）。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from contest_generator.drafts import (
    IDEA_DRAFTS_FILENAME,
    IdeaDrafts,
    add_draft,
    delete_draft,
    empty_drafts,
    load_drafts_file,
    read_drafts,
    update_drafts,
    write_drafts,
)
from contest_generator.task_progress import TaskError
from contest_generator.webapp import AppContext, AppConfig, create_app


class _SentinelReplaceError(OSError):
    """注入用的哨兵异常：断言"抛出来的就是它"，而不是"抛了某个 OSError"。"""


def _residue(directory: Path) -> list[str]:
    """目录里除记录文件外的东西（`iterdir` 而不是 `glob("*.tmp")`——临时名带 pid + 计数后
    那个 glob 匹配不到新名字 = 断言空转；形状照 `tests/test_atomic_io.py:29`）。"""
    return [
        p.name for p in directory.iterdir() if p.name != IDEA_DRAFTS_FILENAME
    ]


def _run_in_thread(errors: list[BaseException], work) -> threading.Thread:
    """起一个守护线程跑 `work`，异常带回主线程断言（照 `tests/test_hwcheck_triage.py` 先例）。"""

    def run() -> None:
        try:
            work()
        except BaseException as exc:  # noqa: BLE001 —— 线程里的异常要带回主线程断言
            errors.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_empty_drafts_shape():
    drafts = empty_drafts()
    assert drafts.version == 1
    assert drafts.drafts == ()
    assert drafts.to_dict() == {"version": 1, "drafts": []}


def test_add_draft_roundtrip(tmp_path):
    """add 落盘 → read 全量读回（id / text / at 齐全）。"""
    drafts = add_draft(empty_drafts(), "循迹阈值太高")
    drafts = add_draft(drafts, "进弯道前先减速")
    assert len(drafts.drafts) == 2
    assert drafts.drafts[0].id and drafts.drafts[0].id != drafts.drafts[1].id
    assert drafts.drafts[0].text == "循迹阈值太高"
    assert drafts.drafts[0].at
    path = write_drafts(tmp_path, drafts)
    assert path.name == IDEA_DRAFTS_FILENAME
    # 原子写同构：落盘后目录里除记录文件外一个文件都没有（判据见下面 iterdir 那两条）
    assert _residue(tmp_path) == []
    loaded = read_drafts(tmp_path)
    assert loaded.drafts[0].text == "循迹阈值太高"
    assert loaded.drafts[1].text == "进弯道前先减速"


def test_add_draft_dedupes_same_text():
    """同文本（含首尾空白差）只存一条；不同文本追加。"""
    drafts = add_draft(empty_drafts(), "循迹阈值太高")
    again = add_draft(drafts, "  循迹阈值太高  ")
    assert again is drafts  # 去重命中：原样返回（幂等，不重复插入）
    assert len(again.drafts) == 1


def test_add_draft_rejects_blank():
    with pytest.raises(TaskError, match="必须是非空字符串"):
        add_draft(empty_drafts(), "")
    with pytest.raises(TaskError, match="必须是非空字符串"):
        add_draft(empty_drafts(), "   ")


def test_delete_draft_removes_and_ignores_unknown():
    drafts = add_draft(add_draft(empty_drafts(), "第一条"), "第二条")
    target = drafts.drafts[0]
    removed = delete_draft(drafts, target.id)
    assert len(removed.drafts) == 1
    assert removed.drafts[0].text == "第二条"
    # 未知 id 静默（幂等）：内容不变（恒返回新实例，比较内容）；非字符串 id 也无害
    assert delete_draft(drafts, "no-such-id") == drafts
    assert delete_draft(drafts, 123) == drafts


def test_read_drafts_missing_is_empty(tmp_path):
    assert read_drafts(tmp_path).drafts == ()


def test_load_drafts_file_corrupt_json(tmp_path):
    path = tmp_path / IDEA_DRAFTS_FILENAME
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(TaskError, match="损坏"):
        load_drafts_file(tmp_path)
    path.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(TaskError, match="必须是 JSON 对象"):
        load_drafts_file(tmp_path)


def test_from_dict_tolerates_bad_entries():
    """单条坏记录忽略（id 非字符串 / text 非字符串 / 非对象）；版本缺省补 1。"""
    raw = {
        "drafts": [
            {"id": "a1", "text": "好的", "at": "2026-01-01T00:00:00"},
            {"id": "a2", "text": 123},          # text 非字符串 → 忽略
            {"id": 3, "text": "坏 id"},          # id 非字符串 → 忽略
            "不是对象",                          # 非对象 → 忽略
        ]
    }
    drafts = IdeaDrafts.from_dict(raw)
    assert drafts.version == 1
    assert len(drafts.drafts) == 1
    assert drafts.drafts[0].id == "a1"
    # 结构级（drafts 非数组）→ 拒收
    with pytest.raises(TaskError, match="必须是数组"):
        IdeaDrafts.from_dict({"drafts": "x"})


# ---------------------------------------------------------------------------
# 记录写的正确性形状：唯一临时名 + 原子替换 + 短临界区（工单 record-write-hardening/02）
#
# 收走前的形状（本单要挡的）：固定临时名 `…json.tmp` + 无锁的"读-改-写"。
# 后果两条：① 写失败 / 两个写者并发时互抢同一个 `.tmp`（一个刚写完、另一个把同一文件
# 截断，`replace` 落盘的可能就是半成品，或后一个的 `replace` 直接失败）；
# ② 两个入口（两个标签页）各自读一份旧记录再整份写回 → 后写的那笔把先写的那笔盖掉。
# ---------------------------------------------------------------------------


def test_drafts_write_leaves_no_tmp_behind(tmp_path):
    """原子写：落盘后除记录文件外**一个文件都没有**（成功路径也不许留残渣）。

    判据用 `iterdir` 逐条看（工单 hwcheck-hygiene/03 起临时名带 pid + 计数，
    `assert not (tmp_path / (IDEA_DRAFTS_FILENAME + ".tmp")).exists()` 那种写法
    匹配不到新名字 = 断言空转）。
    """
    write_drafts(tmp_path, add_draft(empty_drafts(), "循迹阈值太高"))
    leftovers = _residue(tmp_path)
    assert leftovers == [], f"落盘后留下了临时文件：{leftovers}"


def test_drafts_write_failure_leaves_no_residue_and_keeps_the_original_error(
    tmp_path, monkeypatch
):
    """坏写：临时文件必须被清掉，且**原异常照抛**（不许被清理动作掩盖成另一个异常）。

    注入点打在共享原语看到的 `os` 上（写实现已归 `atomic_io`）：`replace` 抛哨兵异常，
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
        write_drafts(tmp_path, add_draft(empty_drafts(), "循迹阈值太高"))
    assert caught.value is boom, "抛出来的不是原异常（被清理动作掩盖了）"
    assert _residue(tmp_path) == [], "写失败后留下了临时文件"


def test_concurrent_drafts_writes_share_no_tmp_file(tmp_path, monkeypatch):
    """两个写者并发：**不许抢同一个临时名**——收走前抢了，先来的那个 `replace` 会落空。

    确定性做法（照 `tests/test_hwcheck_triage.py`）：把**第一个** `replace` 卡住
    （此刻它的临时文件还在盘上），让第二个写者从头走完一遍，再放行第一个。
    · 收走前（固定名 `.contest_ideas.json.tmp`）：第二个写者把**同一个**临时文件截断重写成
      自己的内容并替换掉；第一个放行后 `replace` 的源文件已经不在 → 报错
      （学生看到的就是"草稿存不上"）；
    · 收走后（pid + 计数）：各写各的临时文件，两个都落盘成功，目录里零残留。

    两次**真实** `replace` 刻意不重叠（第二个先落盘再放行第一个）：Windows 上并发替换
    同一目标会以 `WinError 5` 失败，那是"谁先落盘"的另一回事，混进来判据就测不准。
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

    first = _run_in_thread(
        errors, lambda: write_drafts(tmp_path, add_draft(empty_drafts(), "先到的"))
    )
    assert first_inside.wait(timeout=30), "第一个写者没走到替换那一步"
    second = _run_in_thread(
        errors, lambda: write_drafts(tmp_path, add_draft(empty_drafts(), "后到的"))
    )
    second.join(timeout=30)
    release.set()
    first.join(timeout=30)

    assert errors == [], f"并发写报错（临时名互抢）：{errors!r}"
    leftovers = _residue(tmp_path)
    assert leftovers == [], f"并发写留下了残留：{leftovers}"
    assert {draft.text for draft in read_drafts(tmp_path).drafts} in (
        {"先到的"},
        {"后到的"},
    )


def test_update_drafts_does_not_lose_a_concurrent_add(tmp_path):
    """读-改-写整段在临界区里：A 卡在自己的合并里、B 增一条 → **两条都在**。

    确定性做法（照 `tests/test_hwcheck_triage.py` 的并发先例）：把 A 卡在它自己的合并里
    （此刻它已进临界区），B 这时候进来。
    · 收走前（无锁、各自读一份再整份写回）：B 读到的是**空集合**（A 还没写），
      于是 B 落盘的只有自己那条；A 随后落盘只有它那条 → B 那笔丢了；
    · 收走后：B 在锁上等，A 写完它才**重读**——两条草稿都在。
    """
    entered = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []

    def slow_add(latest):
        entered.set()
        assert release.wait(timeout=30), "等不到放行——判据自己失败，别挂住整场"
        return add_draft(latest, "循迹阈值太高")

    first = _run_in_thread(errors, lambda: update_drafts(tmp_path, slow_add))
    assert entered.wait(timeout=30), "第一个写者没进临界区"

    second = _run_in_thread(
        errors,
        lambda: update_drafts(tmp_path, lambda d: add_draft(d, "进弯道前先减速")),
    )
    release.set()
    first.join(timeout=30)
    second.join(timeout=30)

    assert errors == [], f"并发写报错：{errors!r}"
    texts = {draft.text for draft in read_drafts(tmp_path).drafts}
    assert texts == {"循迹阈值太高", "进弯道前先减速"}, f"丢了一笔：{texts}"


def test_update_drafts_does_not_lose_a_concurrent_delete(tmp_path):
    """一页加、一页删（spec 故事 1）：A 卡在自己的合并里、B 删掉一条既有草稿 → **两笔都在**。

    · 收走前（无锁、各自读一份再整份写回）：B 读到的是旧集合（只有既有那条），删完写空；
      A 放行后拿它手上的旧快照整份盖回去 —— 被删的那条**又回来了**（学生的"删了"白删）；
    · 收走后：B 在锁上等，A 写完它才**重读** → A 新增的那条在、被删的那条不在。
    """
    seeded = add_draft(empty_drafts(), "进弯道前先减速")
    write_drafts(tmp_path, seeded)
    target_id = seeded.drafts[0].id

    entered = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []

    def slow_add(latest):
        entered.set()
        assert release.wait(timeout=30), "等不到放行——判据自己失败，别挂住整场"
        return add_draft(latest, "循迹阈值太高")

    first = _run_in_thread(errors, lambda: update_drafts(tmp_path, slow_add))
    assert entered.wait(timeout=30), "第一个写者没进临界区"

    second = _run_in_thread(
        errors,
        lambda: update_drafts(tmp_path, lambda d: delete_draft(d, target_id)),
    )
    release.set()
    first.join(timeout=30)
    second.join(timeout=30)

    assert errors == [], f"并发写报错：{errors!r}"
    texts = {draft.text for draft in read_drafts(tmp_path).drafts}
    assert texts == {"循迹阈值太高"}, f"删掉的那条又回来了，或新加的那条丢了：{texts}"


def test_drafts_endpoints_flow(tmp_path):
    """三端点全流程（工单 idea-suite/05）：read 无文件 [] → add 落盘（去重）→
    delete 删除；输出目录不存在 → 400；text / id 非法 → 400。"""
    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(api_key="sk-test"),
        llm_factory=lambda config: object(),
        desktop_dir=lambda: tmp_path / "Desktop",
    )
    client = TestClient(create_app(ctx))
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    resp = client.post("/api/tasks/idea/drafts/read", json={"output_dir": str(output_dir)})
    assert resp.status_code == 200
    assert resp.json()["drafts"] == []

    resp = client.post(
        "/api/tasks/idea/drafts/add",
        json={"output_dir": str(output_dir), "text": "循迹阈值太高"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["drafts"]) == 1
    # 去重：同文本再 add → 仍 1 条
    resp = client.post(
        "/api/tasks/idea/drafts/add",
        json={"output_dir": str(output_dir), "text": "循迹阈值太高"},
    )
    assert len(resp.json()["drafts"]) == 1
    assert (output_dir / IDEA_DRAFTS_FILENAME).is_file()

    draft_id = resp.json()["drafts"][0]["id"]
    resp = client.post(
        "/api/tasks/idea/drafts/delete",
        json={"output_dir": str(output_dir), "id": draft_id},
    )
    assert resp.status_code == 200
    assert resp.json()["drafts"] == []

    # 400 分支：目录不存在 / 空 text / id 非字符串
    assert client.post(
        "/api/tasks/idea/drafts/read", json={"output_dir": str(tmp_path / "nope")}
    ).status_code == 400
    assert client.post(
        "/api/tasks/idea/drafts/add",
        json={"output_dir": str(output_dir), "text": "   "},
    ).status_code == 400
    assert client.post(
        "/api/tasks/idea/drafts/delete",
        json={"output_dir": str(output_dir), "id": 123},
    ).status_code == 400


def test_two_drafts_endpoints_do_not_clobber_each_other(tmp_path, monkeypatch):
    """两个标签页同时增草稿：判据取**最终落盘**（不取响应体）——两笔都在。

    确定性做法（照 `tests/test_hwcheck.py` 的端点级先例）：把第一个请求卡在它自己的合并里
    （此刻它已进临界区），第二个请求同时发出去。
    · 有锁：第二个请求在锁上等，第一个写完它才进来（重读到第一条）→ 落盘两条都在；
    · 无锁：第二个请求当场读完（空集合）就整份写，第一个放行后拿旧快照盖掉它 → 落盘只剩一条。
    `second_done.wait(timeout=1.0)` 只为在**无锁**那一格把顺序钉死（有锁那一格它必然等不到，
    判据不依赖这一跳）。

    落点说明：票里写的家是 `tests/test_webapp.py`，但**既有草稿端点用例**在 `tests/test_drafts.py`
    （`test_drafts_endpoints_flow`）——照 spec「家 = 既有端点测试文件」放在这里。
    """
    from contest_generator import drafts as drafts_module

    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(api_key="sk-test"),
        llm_factory=lambda config: object(),
        desktop_dir=lambda: tmp_path / "Desktop",
    )
    client = TestClient(create_app(ctx))
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    real_add = drafts_module.add_draft
    entered = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    def blocking_add(latest, text):
        calls["n"] += 1
        if calls["n"] == 1:
            entered.set()
            assert release.wait(timeout=30), "等不到放行——判据自己失败，别挂住整场"
        return real_add(latest, text)

    monkeypatch.setattr(drafts_module, "add_draft", blocking_add)

    results: dict[str, object] = {}

    def add(text: str, done: threading.Event | None = None) -> None:
        results[text] = client.post(
            "/api/tasks/idea/drafts/add",
            json={"output_dir": str(output_dir), "text": text},
        )
        if done is not None:
            done.set()

    first = threading.Thread(target=add, args=("循迹阈值太高",), daemon=True)
    first.start()
    assert entered.wait(timeout=30), "第一个请求没进合并（临界区）"

    second_done = threading.Event()
    second = threading.Thread(
        target=add, args=("进弯道前先减速", second_done), daemon=True
    )
    second.start()
    second_done.wait(timeout=1.0)
    release.set()
    first.join(timeout=30)
    second.join(timeout=30)

    assert results["循迹阈值太高"].status_code == 200, results["循迹阈值太高"].text
    assert results["进弯道前先减速"].status_code == 200, results["进弯道前先减速"].text
    on_disk = json.loads(
        (output_dir / IDEA_DRAFTS_FILENAME).read_text(encoding="utf-8")
    )
    texts = {item["text"] for item in on_disk["drafts"]}
    assert texts == {"循迹阈值太高", "进弯道前先减速"}, f"丢了一笔：{texts}"
    assert _residue(output_dir) == [], "留下了残渣"
