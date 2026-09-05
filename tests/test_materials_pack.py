"""资料库增量打包核心测试（工单 materials-update/01）。

覆盖：资料库扫描（排除自身清单 / 相对路径 / size / sha256）、目录名 → slug
映射（已知中文目录 / ASCII 透传 / 未登记报错）、前后清单 diff（新增 / 修改
/ 删除三态 + 未变更批次不出现）、分卷切分（超限自动拆 part / 单文件超限单
独一卷）、批次 zip 生成（条目路径 = 相对资料库根 / PartInfo 的 size 与
sha256 与实际文件一致）、清单 JSON 往返、`-Init`（只清单不打包，removed
为空 / parts 为空）、`-Full` / `-Diff` 差异产物。
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from contest_generator.materials_pack import (
    MANIFEST_FILENAME,
    PART_LIMIT_BYTES,
    BatchChange,
    PartFile,
    build_manifest,
    build_zip_parts,
    diff_manifest,
    main,
    prepare_package,
    scan_materials,
    slug_for_dir,
)


# ---------------------------------------------------------------------------
# 工具：造迷你资料库
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(256 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _make_tree(root: Path, entries: dict[str, bytes]) -> Path:
    """{相对路径: 内容} → 建树到 root，返回 root。"""
    for rel, content in entries.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return root


# ---------------------------------------------------------------------------
# 扫描
# ---------------------------------------------------------------------------


def test_scan_excludes_self_and_reports_meta(tmp_path: Path) -> None:
    _make_tree(tmp_path, {
        "k230资料/a.bin": b"hello",
        "k230资料/sub/b.txt": b"world",
        "无线串口模块资料/x.pdf": b"pdf-bytes",
    })
    (tmp_path / MANIFEST_FILENAME).write_text("{}", encoding="utf-8")
    entries = scan_materials(tmp_path)
    paths = {e.path for e in entries}
    assert paths == {"k230资料/a.bin", "k230资料/sub/b.txt", "无线串口模块资料/x.pdf"}
    by_path = {e.path: e for e in entries}
    assert by_path["k230资料/a.bin"].size == 5
    assert by_path["k230资料/a.bin"].sha256 == _sha256(tmp_path / "k230资料/a.bin")


def test_scan_skips_noise_dirs(tmp_path: Path) -> None:
    _make_tree(tmp_path, {
        "k230资料/ok.bin": b"ok",
        "k230资料/.git/config": b"git",
        "k230资料/__pycache__/x.pyc": b"pyc",
    })
    paths = {e.path for e in scan_materials(tmp_path)}
    assert paths == {"k230资料/ok.bin"}


# ---------------------------------------------------------------------------
# slug 映射
# ---------------------------------------------------------------------------


def test_slug_known_chinese_dirs() -> None:
    assert slug_for_dir("k230资料") == "k230"
    assert slug_for_dir("2026_06_电赛视觉资料") == "2026-06-vision"
    assert slug_for_dir("2026_04_地猛星电赛控制题配套资料") == "2026-04-dimx-kit"
    assert slug_for_dir("2026_08_MSPM0G3507与常用芯片手册") == "2026-08-mspm0-manuals"
    assert slug_for_dir("无线串口模块资料") == "wireless-uart"
    assert slug_for_dir("塔克R3两驱小车底盘资料") == "tark-r3-chassis"
    assert slug_for_dir("C7-3-4L ESP32-CAM开发板资料") == "c7-3-4l-esp32cam"


def test_slug_ascii_passthrough() -> None:
    assert slug_for_dir("K230_SDK") == "k230_sdk"
    assert slug_for_dir("car-1.1") == "car-1.1"


def test_slug_unknown_chinese_dir_raises() -> None:
    with pytest.raises(ValueError, match="未登记"):
        slug_for_dir("全新中文目录")


# ---------------------------------------------------------------------------
# diff 三态
# ---------------------------------------------------------------------------


def _file(path: str, size: int, sha: str) -> dict:
    return {"path": path, "size": size, "sha256": sha}


def _manifest(version: str, batches: list[dict]) -> dict:
    return {"version": version, "published_at": "2026-09-01T00:00:00Z", "batches": batches}


def _batch(slug: str, name: str, files: list[dict], removed: list[str] | None = None,
           parts: list[dict] | None = None) -> dict:
    return {"slug": slug, "name": name, "files": files,
            "removed": removed or [], "parts": parts or []}


def test_diff_detects_add_modify_remove() -> None:
    prev = _manifest("v1.0.0", [
        _batch("k230", "k230资料", [
            _file("k230资料/keep.bin", 10, "a" * 64),
            _file("k230资料/change.bin", 10, "b" * 64),
            _file("k230资料/gone.bin", 10, "c" * 64),
        ]),
        _batch("wireless-uart", "无线串口模块资料", [
            _file("无线串口模块资料/stable.pdf", 5, "d" * 64),
        ]),
    ])
    curr = _manifest("v1.1.0", [
        _batch("k230", "k230资料", [
            _file("k230资料/keep.bin", 10, "a" * 64),
            _file("k230资料/change.bin", 10, "e" * 64),  # 修改
            _file("k230资料/new.bin", 20, "f" * 64),     # 新增
        ]),
        _batch("wireless-uart", "无线串口模块资料", [
            _file("无线串口模块资料/stable.pdf", 5, "d" * 64),  # 未变
        ]),
    ])
    changes = diff_manifest(prev, curr)
    assert [c.slug for c in changes] == ["k230"]  # 未变更批次不出现
    change = changes[0]
    assert {f.path for f in change.parts_files} == {
        "k230资料/change.bin", "k230资料/new.bin",
    }
    assert list(change.removed) == ["k230资料/gone.bin"]
    assert change.add_count == 1
    assert change.modify_count == 1
    assert change.del_count == 1


def test_diff_whole_batch_removed_reported_as_removed() -> None:
    prev = _manifest("v1.0.0", [
        _batch("k230", "k230资料", [_file("k230资料/x.bin", 1, "a" * 64)]),
    ])
    curr = _manifest("v1.1.0", [])
    changes = diff_manifest(prev, curr)
    assert len(changes) == 1
    assert changes[0].slug == "k230"
    assert list(changes[0].removed) == ["k230资料/x.bin"]
    assert changes[0].parts_files == ()


def test_diff_from_none_means_all_added() -> None:
    curr = _manifest("v1.0.0", [
        _batch("k230", "k230资料", [_file("k230资料/x.bin", 1, "a" * 64)]),
    ])
    changes = diff_manifest(None, curr)
    assert len(changes) == 1
    assert changes[0].add_count == 1
    assert changes[0].removed == ()
    assert changes[0].parts_files[0].path == "k230资料/x.bin"


# ---------------------------------------------------------------------------
# 分卷切分
# ---------------------------------------------------------------------------


def test_split_parts_respects_limit() -> None:
    files = [PartFile(f"f{i}.bin", 40, "x" * 64) for i in range(6)]
    parts = BatchChange.split_parts(files, limit=120)
    assert [len(p) for p in parts] == [3, 3]  # 40*3 = 120 恰好触顶切


def test_split_single_file_over_limit_gets_own_part() -> None:
    files = [PartFile("big.bin", 5000, "x" * 64),
             PartFile("small.bin", 10, "y" * 64)]
    parts = BatchChange.split_parts(files, limit=100)
    assert [len(p) for p in parts] == [1, 1]
    assert parts[0][0].path == "big.bin"


# ---------------------------------------------------------------------------
# 批次 zip 生成
# ---------------------------------------------------------------------------


def test_build_zip_parts_writes_entries_and_meta(tmp_path: Path) -> None:
    tree = tmp_path / "materials"
    _make_tree(tree, {
        "k230资料/a.bin": b"aaa",
        "k230资料/sub/b.txt": b"bbb",
    })
    files = [
        PartFile("k230资料/a.bin", 3, hashlib.sha256(b"aaa").hexdigest()),
        PartFile("k230资料/sub/b.txt", 3, hashlib.sha256(b"bbb").hexdigest()),
    ]
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    parts, written = build_zip_parts(
        tree, "firstep-materials-v1.1.0-k230", files, out_dir, limit=100
    )
    assert len(parts) == 1
    assert written[0].exists() and written[0].stat().st_size > 0
    meta = parts[0]
    assert meta["zip_name"].startswith("firstep-materials-v1.1.0-k230")
    assert meta["size"] == written[0].stat().st_size
    assert meta["sha256"] == _sha256(written[0])
    with zipfile.ZipFile(written[0]) as archive:
        assert set(archive.namelist()) == {"k230资料/a.bin", "k230资料/sub/b.txt"}


def test_build_zip_parts_splits_over_limit(tmp_path: Path) -> None:
    tree = tmp_path / "materials"
    _make_tree(tree, {"k230资料/a.bin": b"a" * 60, "k230资料/b.bin": b"b" * 60})
    files = [
        PartFile("k230资料/a.bin", 60, "x" * 64),
        PartFile("k230资料/b.bin", 60, "y" * 64),
    ]
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    parts, written = build_zip_parts(
        tree, "firstep-materials-v1.1.0-k230", files, out_dir, limit=100
    )
    assert len(parts) == 2
    assert written[0].name.endswith(".part1.zip")
    assert written[1].name.endswith(".part2.zip")


# ---------------------------------------------------------------------------
# 清单构建与 JSON 往返
# ---------------------------------------------------------------------------


def test_build_manifest_full_snapshot_shape() -> None:
    manifest = build_manifest(
        version="v1.1.0",
        published_at="2026-09-01T00:00:00Z",
        full_batches=[
            {
                "slug": "k230",
                "name": "k230资料",
                "files": [{"path": "k230资料/x.bin", "size": 3, "sha256": "a" * 64}],
                "removed": ["k230资料/gone.bin"],
                "parts": [{"zip_name": "firstep-materials-v1.1.0-k230.zip",
                           "size": 100, "sha256": "b" * 64}],
            }
        ],
    )
    assert manifest["version"] == "v1.1.0"
    assert manifest["published_at"] == "2026-09-01T00:00:00Z"
    batch = manifest["batches"][0]
    assert batch["slug"] == "k230"
    assert batch["files"] == [{"path": "k230资料/x.bin", "size": 3, "sha256": "a" * 64}]
    assert batch["removed"] == ["k230资料/gone.bin"]
    assert batch["parts"][0]["zip_name"] == "firstep-materials-v1.1.0-k230.zip"
    # JSON 往返无损
    assert json.loads(json.dumps(manifest, ensure_ascii=False)) == manifest


def test_build_manifest_unchanged_batch_keeps_files_no_parts() -> None:
    manifest = build_manifest(
        "v1.1.0", "2026-09-01T00:00:00Z",
        full_batches=[
            {
                "slug": "wireless-uart", "name": "无线串口模块资料",
                "files": [{"path": "无线串口模块资料/ok.pdf", "size": 4, "sha256": "c" * 64}],
                "removed": [], "parts": [],
            }
        ],
    )
    batch = manifest["batches"][0]
    assert batch["files"] == [{"path": "无线串口模块资料/ok.pdf", "size": 4, "sha256": "c" * 64}]
    assert batch["parts"] == []
    assert batch["removed"] == []


# ---------------------------------------------------------------------------
# prepare_package 编排（Init / Full / Diff）
# ---------------------------------------------------------------------------


def test_prepare_package_init_writes_manifest_only(tmp_path: Path) -> None:
    tree = tmp_path / "materials"
    _make_tree(tree, {"k230资料/a.bin": b"aaa"})
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    manifest, written = prepare_package(
        tree, prev=None, version="v1.1.0", out_dir=out_dir, write_zips=False,
    )
    assert manifest["version"] == "v1.1.0"
    assert manifest["batches"][0]["files"][0]["path"] == "k230资料/a.bin"
    assert manifest["batches"][0]["parts"] == []
    assert written == []
    # manifest 落盘由调用方（ps1 / 用户侧）决定；此处纯数据


def test_prepare_package_diff_writes_only_changes(tmp_path: Path) -> None:
    tree = tmp_path / "materials"
    _make_tree(tree, {
        "k230资料/keep.bin": b"keep",
        "k230资料/change.bin": b"NEW",   # 由 old 改
        "k230资料/new.bin": b"new-file",
    })
    prev = _manifest("v1.0.0", [
        _batch("k230", "k230资料", [
            _file("k230资料/keep.bin", 4, hashlib.sha256(b"keep").hexdigest()),
            _file("k230资料/change.bin", 3, hashlib.sha256(b"OLD").hexdigest()),
            _file("k230资料/gone.bin", 3, hashlib.sha256(b"gone").hexdigest()),
        ]),
    ])
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    manifest, written = prepare_package(
        tree, prev=prev, version="v1.1.0", out_dir=out_dir, write_zips=True,
    )
    assert len(written) == 1
    with zipfile.ZipFile(written[0]) as archive:
        assert set(archive.namelist()) == {"k230资料/change.bin", "k230资料/new.bin"}
    batch = manifest["batches"][0]
    assert batch["removed"] == ["k230资料/gone.bin"]
    assert len(batch["parts"]) == 1


# ---------------------------------------------------------------------------
# CLI（main(argv)，不 spawn 子进程）
# ---------------------------------------------------------------------------


def test_cli_init_writes_manifest(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    tree = tmp_path / "materials"
    _make_tree(tree, {"k230资料/a.bin": b"aaa"})
    out_dir = tmp_path / "out"
    code = main([
        "--tree", str(tree), "--version", "v1.1.0", "--out", str(out_dir),
        "--mode", "init",
    ])
    assert code == 0
    manifest_path = out_dir / "firstep-materials-v1.1.0.manifest.json"
    assert manifest_path.is_file()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["version"] == "v1.1.0"
    assert data["batches"][0]["slug"] == "k230"
    assert data["batches"][0]["parts"] == []
    out = capsys.readouterr().out
    assert "清单" in out


def test_cli_diff_requires_baseline(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    tree = tmp_path / "materials"
    _make_tree(tree, {"k230资料/a.bin": b"aaa"})
    code = main([
        "--tree", str(tree), "--version", "v1.1.0", "--out", str(tmp_path / "out"),
        "--mode", "diff",
    ])
    assert code == 2
    assert "diff 模式需要" in capsys.readouterr().err


def test_cli_diff_local_baseline(tmp_path: Path) -> None:
    tree = tmp_path / "materials"
    _make_tree(tree, {"k230资料/a.bin": b"aaa"})
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(_manifest("v1.0.0", [
            _batch("k230", "k230资料", [_file("k230资料/a.bin", 3, "x" * 64)]),
        ]), ensure_ascii=False),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    code = main([
        "--tree", str(tree), "--version", "v1.1.0", "--out", str(out_dir),
        "--mode", "diff", "--baseline", str(baseline),
    ])
    assert code == 0
    assert (out_dir / "firstep-materials-v1.1.0-k230.zip").is_file()
    data = json.loads(
        (out_dir / "firstep-materials-v1.1.0.manifest.json").read_text(encoding="utf-8")
    )
    assert data["batches"][0]["parts"][0]["zip_name"] == "firstep-materials-v1.1.0-k230.zip"


def test_cli_bad_version_rejected(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    tree = tmp_path / "materials"
    _make_tree(tree, {"k230资料/a.bin": b"aaa"})
    code = main([
        "--tree", str(tree), "--version", "v1.1.0/../evil", "--out", str(tmp_path / "out"),
        "--mode", "init",
    ])
    assert code == 2
    assert "非法字符" in capsys.readouterr().err
