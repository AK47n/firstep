"""最近生成记录模块（工单 recent-jobs/01）：recent.json 落盘纯函数测试。

覆盖：record 字段与排序 / 同目录更新 / 状态白名单 / delete /
损坏文件容错 / cap 截断 / load 非列表容错。
"""

from __future__ import annotations

import json

import pytest

from contest_generator.recent_jobs import (
    MAX_RECENT,
    STATUS_FAILED,
    STATUS_GENERATED,
    STATUS_OK,
    RecentStatusError,
    delete_recent,
    load_recent,
    record_recent,
    recent_file,
    update_recent_status,
)


def test_recent_file_sits_next_to_config(tmp_path):
    assert recent_file(tmp_path / "cfg" / "config.json") == tmp_path / "cfg" / "recent.json"


def test_record_recent_creates_entry(tmp_path):
    fp = recent_file(tmp_path / "config.json")
    entry = record_recent(
        fp, output_dir="D:/contest/demo", platform="stm32", slugs=["dht11", "oled"]
    )

    assert fp.exists()
    assert entry["status"] == STATUS_GENERATED
    assert entry["output_dir"] == "D:/contest/demo"
    assert entry["platform"] == "stm32"
    assert entry["slugs"] == ["dht11", "oled"]
    assert entry["id"]
    assert float(entry["ts"]) > 0
    loaded = load_recent(fp)
    assert len(loaded) == 1
    assert loaded[0]["id"] == entry["id"]


def test_record_recent_same_dir_updates_not_duplicates(tmp_path):
    fp = recent_file(tmp_path / "config.json")
    first = record_recent(fp, output_dir="D:/contest/demo", platform="stm32", slugs=["dht11"])
    second = record_recent(fp, output_dir="D:/contest/demo", platform="stm32", slugs=["led"])

    loaded = load_recent(fp)
    assert len(loaded) == 1
    assert loaded[0]["id"] != first["id"]  # 新记录替换旧记录（id 更新）
    assert loaded[0]["id"] == second["id"]
    assert loaded[0]["slugs"] == ["led"]


def test_record_recent_newest_first_and_capped(tmp_path):
    fp = recent_file(tmp_path / "config.json")
    for i in range(MAX_RECENT + 3):
        record_recent(fp, output_dir=f"D:/contest/job{i}", platform="stm32", slugs=["dht11"])

    loaded = load_recent(fp)
    assert len(loaded) == MAX_RECENT
    assert loaded[0]["output_dir"] == f"D:/contest/job{MAX_RECENT + 2}"  # 最新在前
    assert loaded[-1]["output_dir"] == "D:/contest/job3"  # 最旧 3 条被挤掉


def test_update_recent_status_known_and_unknown(tmp_path):
    fp = recent_file(tmp_path / "config.json")
    entry = record_recent(fp, output_dir="D:/contest/demo", platform="stm32", slugs=["dht11"])

    updated = update_recent_status(fp, "D:/contest/demo", STATUS_OK)
    assert updated is not None
    assert updated["status"] == STATUS_OK
    assert load_recent(fp)[0]["status"] == STATUS_OK
    assert updated["id"] == entry["id"]  # 更新不换 id

    assert update_recent_status(fp, "D:/contest/nope", STATUS_OK) is None


def test_update_recent_status_rejects_unknown_status(tmp_path):
    fp = recent_file(tmp_path / "config.json")
    record_recent(fp, output_dir="D:/contest/demo", platform="stm32", slugs=["dht11"])
    with pytest.raises(RecentStatusError):
        update_recent_status(fp, "D:/contest/demo", "compiled_maybe")
    # 非法状态不落盘
    assert load_recent(fp)[0]["status"] == STATUS_GENERATED


def test_delete_recent(tmp_path):
    fp = recent_file(tmp_path / "config.json")
    entry = record_recent(fp, output_dir="D:/contest/demo", platform="stm32", slugs=["dht11"])

    assert delete_recent(fp, "no-such-id") is False
    assert delete_recent(fp, entry["id"]) is True
    assert load_recent(fp) == []
    # 删除后再删同样 id → False（已不存在）
    assert delete_recent(fp, entry["id"]) is False


def test_load_recent_tolerates_missing_and_corrupt(tmp_path):
    fp = recent_file(tmp_path / "config.json")
    assert load_recent(fp) == []  # 不存在

    fp.write_text("{ not json", encoding="utf-8")
    assert load_recent(fp) == []  # 损坏 → 空列表不炸

    fp.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert load_recent(fp) == []  # 非列表 → 空列表

    fp.write_text(json.dumps([{"ok": 1}, "junk", 42, {"ok": 2}]), encoding="utf-8")
    loaded = load_recent(fp)
    assert loaded == [{"ok": 1}, {"ok": 2}]  # 非 dict 条目被过滤


def test_load_recent_tolerates_utf8_bom(tmp_path):
    """Windows 记事本 / PowerShell 写出的 recent.json 常带 BOM（本地工具
    用户可能手改）；BOM 会让 json.loads 抛 ValueError → 静默丢条，必须容忍。"""
    fp = recent_file(tmp_path / "config.json")
    fp.write_bytes(b"\xef\xbb\xbf" + json.dumps(
        [{"id": "a", "output_dir": "D:/x", "status": STATUS_GENERATED}]
    ).encode("utf-8"))
    loaded = load_recent(fp)
    assert len(loaded) == 1
    assert loaded[0]["id"] == "a"


def test_load_recent_caps_at_max_even_if_file_overflows(tmp_path):
    """cap 20 双保险：写入端截断 + 读取端再截（用户手改超 20 条不炸显示）。"""
    fp = recent_file(tmp_path / "config.json")
    entries = [
        {"id": f"e{i}", "output_dir": f"D:/x/{i}", "status": STATUS_GENERATED}
        for i in range(MAX_RECENT + 5)
    ]
    fp.write_text(json.dumps(entries), encoding="utf-8")
    loaded = load_recent(fp)
    assert len(loaded) == MAX_RECENT
    assert loaded[0]["id"] == "e0"  # 新 → 旧序保留，只裁尾部


def test_record_recent_status_default_generated_but_failed_status_allowed(tmp_path):
    fp = recent_file(tmp_path / "config.json")
    entry = record_recent(fp, output_dir="D:/contest/demo", platform="stm32", slugs=["dht11"])
    assert entry["status"] == STATUS_GENERATED
    update_recent_status(fp, "D:/contest/demo", STATUS_FAILED)
    assert load_recent(fp)[0]["status"] == STATUS_FAILED
