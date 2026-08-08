"""entry_store 条目库原语（工单 C3）：读盘+JSON 校验 / 删除 / 键校验 / 必填
字段 / 路径安全。四库（模块库 / 赛题库 / 参考库 / 母版库）都经这些原语，
错误类型与文案在各库转写——本文件只测原语自身的契约。"""

import json
import re

import pytest

from contest_generator.entry_store import (
    StoreError,
    StoreParseError,
    StoreReadError,
    StoreShapeError,
    delete_entry,
    is_unsafe_path,
    read_json,
    require_str,
    validate_store_key,
)


def test_read_json_returns_object(tmp_path):
    entry_dir = tmp_path / "entry"
    entry_dir.mkdir()
    (entry_dir / "meta.json").write_text(
        json.dumps({"year": "2026", "key": "2026C"}), encoding="utf-8"
    )

    assert read_json(entry_dir, "meta.json") == {"year": "2026", "key": "2026C"}


def test_read_json_missing_file_raises_store_read_error_with_cause(tmp_path):
    entry_dir = tmp_path / "entry"
    entry_dir.mkdir()

    with pytest.raises(StoreReadError) as exc_info:
        read_json(entry_dir, "meta.json")

    assert isinstance(exc_info.value.error, FileNotFoundError)


def test_read_json_invalid_json_raises_store_parse_error_with_cause(tmp_path):
    entry_dir = tmp_path / "entry"
    entry_dir.mkdir()
    (entry_dir / "meta.json").write_text("{ 不是 JSON", encoding="utf-8")

    with pytest.raises(StoreParseError) as exc_info:
        read_json(entry_dir, "meta.json")

    assert exc_info.value.error is not None


def test_read_json_non_object_raises_store_shape_error(tmp_path):
    entry_dir = tmp_path / "entry"
    entry_dir.mkdir()
    (entry_dir / "meta.json").write_text("[1, 2]", encoding="utf-8")

    with pytest.raises(StoreShapeError):
        read_json(entry_dir, "meta.json")


def test_delete_entry_removes_directory(tmp_path):
    entry_dir = tmp_path / "entry"
    entry_dir.mkdir()
    (entry_dir / "file.txt").write_text("x", encoding="utf-8")

    delete_entry(tmp_path, "entry")

    assert not entry_dir.exists()


def test_delete_entry_missing_raises_store_error(tmp_path):
    with pytest.raises(StoreError, match="不存在"):
        delete_entry(tmp_path, "no-such-entry")


def test_validate_store_key_accepts_matching_name():
    validate_store_key("2026C", re.compile(r"^\d{4}[A-Z]$"), "赛题编号")


def test_validate_store_key_rejects_non_matching_name():
    with pytest.raises(StoreError, match="非法"):
        validate_store_key("2026c", re.compile(r"^\d{4}[A-Z]$"), "赛题编号")


def test_require_str_accepts_non_empty_string():
    assert require_str({"key": "value"}, "key") == "value"


@pytest.mark.parametrize("data", [{}, {"key": ""}, {"key": 123}])
def test_require_str_rejects_missing_empty_and_non_string(data):
    with pytest.raises(StoreError, match="缺少必填字段"):
        require_str(data, "key")


@pytest.mark.parametrize(
    ("path", "unsafe"),
    [
        ("src/main.c", False),
        ("stm32/src/dht11.c", False),
        ("/abs/path.c", True),
        ("../escape.c", True),
        ("a//b.c", True),
        ("a\\b.c", True),
        ("c:/windows.c", True),
    ],
)
def test_is_unsafe_path(path, unsafe):
    assert is_unsafe_path(path) is unsafe
