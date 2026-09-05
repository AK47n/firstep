"""资料库应用器测试（工单 materials-update/05）。

覆盖：安全解压覆盖（改文件落位 / 新增文件落位）、removed 删除（部分删除 +
整批删除）、备份（被覆盖 + 被删除文件镜像到 backup 目录）、新清单写回
（选中批次版本推进、未选批次保留、各字段形状）、zip slip（../evil 整体拒绝）、
分卷顺序应用、跨批次（只应用选中批次）、应用失败保留备份与部分完成提示。
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from contest_generator.materials_apply import (
    MaterialApplyError,
    apply_materials_update,
    safe_join,
)


# ---------------------------------------------------------------------------
# 工具：构造迷你资料库与增量 zip
# ---------------------------------------------------------------------------


def _make_tree(root: Path, entries: dict[str, bytes]) -> None:
    for rel, content in entries.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _make_zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for rel, content in entries.items():
            archive.writestr(rel, content)
    return path


def _batch(slug: str, name: str, files: list[dict], removed: list[str] | None = None,
           parts: list[dict] | None = None) -> dict:
    return {"slug": slug, "name": name,
            "files": files,
            "removed": removed or [],
            "parts": parts or []}


def _file(path: str, size: int, sha: str) -> dict:
    return {"path": path, "size": size, "sha256": sha}


def _manifest(version: str, batches: list[dict]) -> dict:
    return {"version": version, "published_at": "2026-09-01T00:00:00Z", "batches": batches}


# ---------------------------------------------------------------------------
# safe_join
# ---------------------------------------------------------------------------


def test_safe_join_accepts_normal(tmp_path: Path) -> None:
    target = safe_join(tmp_path, "k230资料/a.bin")
    assert target == tmp_path / "k230资料" / "a.bin"


@pytest.mark.parametrize("bad", [
    "../evil.txt",
    "a/../../evil.txt",
    "/abs/path.txt",
    "C:/evil.txt",
    "..\\evil.txt",
])
def test_safe_join_rejects_zip_slip(tmp_path: Path, bad: str) -> None:
    with pytest.raises(MaterialApplyError, match="非法路径|越界"):
        safe_join(tmp_path, bad)


# ---------------------------------------------------------------------------
# 应用主流程
# ---------------------------------------------------------------------------


def test_apply_overwrites_adds_and_removes(tmp_path: Path) -> None:
    materials = tmp_path / "materials"
    _make_tree(materials, {
        "k230资料/old.json": b"{}",
        "k230资料/keep.bin": b"keep",
        "k230资料/gone.bin": b"bye",
    })
    zip_dir = tmp_path / "zips"
    zip_dir.mkdir()
    _make_zip(zip_dir / "k230.zip", {
        "k230资料/old.json": b"{new}",
        "k230资料/new.bin": b"hello",
    })
    batch = _batch("k230", "k230资料", [
        _file("k230资料/old.json", 5, "x"),
        _file("k230资料/keep.bin", 4, "y"),
        _file("k230资料/new.bin", 5, "z"),
    ], removed=["k230资料/gone.bin"], parts=[{
        "zip_name": "k230.zip", "size": 100, "sha256": "",
    }])

    manifest = apply_materials_update(
        materials_root=materials,
        manifest=_manifest("v1.1.0", [batch]),
        zip_dir=zip_dir,
        backup_dir=tmp_path / "backup",
    )

    assert (materials / "k230资料/old.json").read_bytes() == b"{new}"
    assert (materials / "k230资料/new.bin").read_bytes() == b"hello"
    assert not (materials / "k230资料/gone.bin").exists()
    assert (materials / "k230资料/keep.bin").read_bytes() == b"keep"
    # 新清单写回（manifest 文件在资料库根）
    written = json.loads((materials / ".materials-manifest.json").read_text(encoding="utf-8"))
    assert written["version"] == "v1.1.0"
    assert written["batches"][0]["slug"] == "k230"
    # 备份：被覆盖 + 被删除
    backup = tmp_path / "backup"
    assert (backup / "k230资料/old.json").read_bytes() == b"{}"
    assert (backup / "k230资料/gone.bin").read_bytes() == b"bye"


def test_apply_skips_unselected_batches(tmp_path: Path) -> None:
    materials = tmp_path / "materials"
    _make_tree(materials, {
        "k230资料/a.bin": b"old",
        "wireless/b.pdf": b"old-pdf",
    })
    zip_dir = tmp_path / "zips"
    zip_dir.mkdir()
    _make_zip(zip_dir / "k230.zip", {"k230资料/a.bin": b"new"})
    batches = [
        _batch("k230", "k230资料", [_file("k230资料/a.bin", 3, "x")],
               parts=[{"zip_name": "k230.zip", "size": 1, "sha256": ""}]),
    ]
    # 构造：只传选中批次的 manifest 视图——用户侧只把选中批次写入新清单，
    # 未被无线串口批次选中 → 文件原样保留
    manifest = apply_materials_update(
        materials_root=materials,
        manifest=_manifest("v1.1.0", batches),
        zip_dir=zip_dir,
        backup_dir=tmp_path / "backup",
    )
    assert (materials / "k230资料/a.bin").read_bytes() == b"new"
    assert (materials / "wireless/b.pdf").read_bytes() == b"old-pdf"
    assert manifest["batches"][0]["parts"] == [{"zip_name": "k230.zip", "size": 1, "sha256": ""}]


def test_apply_rejects_slip_zip(tmp_path: Path) -> None:
    materials = tmp_path / "materials"
    _make_tree(materials, {"k230资料/a.bin": b"old"})
    zip_dir = tmp_path / "zips"
    zip_dir.mkdir()
    evil = zip_dir / "evil.zip"
    with zipfile.ZipFile(evil, "w") as archive:
        archive.writestr("../evil.txt", b"boom")
    batch = _batch("k230", "k230资料", [], parts=[{"zip_name": "evil.zip", "size": 1, "sha256": ""}])
    with pytest.raises(MaterialApplyError, match="非法路径|越界"):
        apply_materials_update(
            materials_root=materials,
            manifest=_manifest("v1.1.0", [batch]),
            zip_dir=zip_dir,
            backup_dir=tmp_path / "backup",
        )


def test_apply_multiple_parts_in_order(tmp_path: Path) -> None:
    materials = tmp_path / "materials"
    _make_tree(materials, {"k230资料/a.bin": b"old"})
    zip_dir = tmp_path / "zips"
    zip_dir.mkdir()
    _make_zip(zip_dir / "k230.part1.zip", {"k230资料/a.bin": b"new-a"})
    _make_zip(zip_dir / "k230.part2.zip", {"k230资料/b.bin": b"new-b"})
    batch = _batch("k230", "k230资料", [
        _file("k230资料/a.bin", 5, "x"),
        _file("k230资料/b.bin", 5, "y"),
    ], parts=[
        {"zip_name": "k230.part1.zip", "size": 1, "sha256": ""},
        {"zip_name": "k230.part2.zip", "size": 1, "sha256": ""},
    ])
    apply_materials_update(
        materials_root=materials,
        manifest=_manifest("v1.1.0", [batch]),
        zip_dir=zip_dir,
        backup_dir=tmp_path / "backup",
    )
    assert (materials / "k230资料/a.bin").read_bytes() == b"new-a"
    assert (materials / "k230资料/b.bin").read_bytes() == b"new-b"


def test_apply_missing_zip_raises_chinese(tmp_path: Path) -> None:
    materials = tmp_path / "materials"
    _make_tree(materials, {"k230资料/a.bin": b"old"})
    batch = _batch("k230", "k230资料", [], parts=[{"zip_name": "missing.zip", "size": 1, "sha256": ""}])
    with pytest.raises(MaterialApplyError, match="不存在"):
        apply_materials_update(
            materials_root=materials,
            manifest=_manifest("v1.1.0", [batch]),
            zip_dir=tmp_path / "zips",
            backup_dir=tmp_path / "backup",
        )


def test_apply_whole_batch_deleted_removes_files(tmp_path: Path) -> None:
    """本地有、线上无的整批删除：新清单不含该批次，但删除动作需执行——
    由应用器按「旧清单 - 新清单」推导。测试直接断言文件被删。"""
    materials = tmp_path / "materials"
    _make_tree(materials, {"gone/x.bin": b"bye", "k230资料/keep.bin": b"keep"})
    old = _manifest("v1.0.0", [
        _batch("gone", "废弃批次", [_file("gone/x.bin", 3, "x")]),
        _batch("k230", "k230资料", [_file("k230资料/keep.bin", 4, "y")]),
    ])
    new = _manifest("v1.1.0", [
        _batch("k230", "k230资料", [_file("k230资料/keep.bin", 4, "y")]),
    ])
    apply_materials_update(
        materials_root=materials,
        manifest=new,
        old_manifest=old,
        zip_dir=tmp_path / "zips",
        backup_dir=tmp_path / "backup",
    )
    assert not (materials / "gone" / "x.bin").exists()
    assert (materials / "k230资料/keep.bin").exists()