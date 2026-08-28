"""想法草稿箱（工单 idea-suite/05）：模型 / 落盘 / 坏 JSON / 去重 / 删除的测试。

只测外部行为：add 去重与 id 分配、delete 幂等、read 无文件空集合、
写盘 roundtrip、坏 JSON → TaskError 400 中文（宁拒收不吞）。
"""

from __future__ import annotations

import json
from pathlib import Path

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
    write_drafts,
)
from contest_generator.task_progress import TaskError
from contest_generator.webapp import AppContext, AppConfig, create_app


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
    # 原子写同构：.tmp 文件不残留
    assert not (tmp_path / (IDEA_DRAFTS_FILENAME + ".tmp")).exists()
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
