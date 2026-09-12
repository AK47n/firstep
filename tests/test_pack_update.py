"""小发版更新包打包核心测试（工单 full-download/08）。

覆盖：**跨包不变量**（两个包对同一文件逐字节一致，且与 `git archive` 不变量相同）、
`core.autocrlf` 不影响结果、批处理保持 CRLF、文件清单与 zip 条目一一对应、
非 git 目录回退工作树。
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from contest_generator.full_pack import prepare_full_package
from contest_generator.pack_update import pack_update, read_files_manifest, sha256_of

# 发布侧自检脚本（`.scratch/full-download/`）里的跨包判据，测试直接调它——
# 免得「自检脚本自己写一份比对逻辑」与产品侧判据漂移。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".scratch" / "full-download"))
from verify_release_assets import cross_pack_byte_diff  # noqa: E402


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def make_mini_repo(root: Path, *, autocrlf: str = "true") -> Path:
    """最小仓库树：既有普通文本，也有必须保持 CRLF 的批处理。

    `.gitattributes` 与仓库同款（`*.bat text eol=crlf`）——批处理行长尾变 LF
    会让 cmd 的 `if ()` 块解析错乱，这条口径不能被本工单的改动碰坏。
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@test.invalid")
    _git(root, "config", "user.name", "test")
    _git(root, "config", "core.autocrlf", autocrlf)

    (root / ".gitattributes").write_bytes(b"*.bat text eol=crlf\n.githooks/* text eol=lf\n")
    (root / "README.md").write_bytes("# firstep\n正文\n".encode("utf-8"))
    (root / "src").mkdir()
    (root / "src" / "app.py").write_bytes(b"print(1)\n")
    (root / "library").mkdir()
    (root / "library" / "manifest.json").write_bytes('{"slug": "oled"}\n'.encode("utf-8"))
    (root / "start-app.bat").write_bytes(b"@echo off\r\necho hi\r\n")
    (root / ".githooks").mkdir()
    (root / ".githooks" / "pre-commit").write_bytes(b"#!/bin/sh\necho hi\n")
    (root / "sources" / "materials" / "batch").mkdir(parents=True)

    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


def zip_bytes(zip_path: Path) -> dict[str, bytes]:
    """zip → {条目路径: 原始字节}（跨包比对只认内容，不比 zip 容器元数据）。"""
    content: dict[str, bytes] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            content[name] = archive.read(name)
    return content


def tracked_files(tree: Path) -> list[str]:
    """`git ls-files` 全量（顶层白名单由 PS 侧做；迷你仓库里全部都在白名单内）。"""
    return sorted(line for line in _git(tree, "-c", "core.quotepath=false", "ls-files").splitlines() if line)


def build_both(
    tree: Path, out_dir: Path, *, version: str = "v9.9.9", limit: int = 1_000_000
) -> tuple[dict[str, bytes], dict[str, bytes]]:
    """同一 commit 分别跑两个打包路径，返回 (完整包内容, 更新包内容)。"""
    full_out = out_dir / "full"
    update_out = out_dir / "update"
    prepare_full_package(tree, version=version, out_dir=full_out, published_at="", limit=limit)

    manifest = out_dir / "files.txt"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("".join(f"{p}\n" for p in tracked_files(tree)), encoding="utf-8")
    pack_update(tree, version=version, out_dir=update_out, files_manifest=manifest)

    full_content: dict[str, bytes] = {}
    for zip_path in sorted(full_out.glob("firstep-full-*.zip")):
        full_content.update(zip_bytes(zip_path))
    return full_content, zip_bytes(update_out / f"firstep-update-{version}.zip")


def archive_bytes(tree: Path, paths: list[str], *, config: tuple[str, ...] = ("core.autocrlf=false",)) -> dict[str, bytes]:
    """跑 `git archive`（第二意见）：默认走**钉住的确定性配置**，与实现同口径。

    传 `config=()` 可拿本机配置下的结果——用来证明「不钉会有差异」。
    """
    archive = tree.parent / "git-archive.zip"
    options: list[str] = []
    for item in config:
        options += ["-c", item]
    _git(
        tree,
        "-c",
        "core.quotepath=false",
        *options,
        "archive",
        "--format=zip",
        f"--output={archive}",
        "HEAD",
        "--",
        *paths,
    )
    return zip_bytes(archive)


# ---------------------------------------------------------------------------
# 跨包不变量（工单的核心验收）
# ---------------------------------------------------------------------------


def test_shared_files_have_identical_bytes(tmp_path: Path) -> None:
    """两个包对同一源文件必须产出同一份字节（本工单要修的就是这条）。"""
    tree = make_mini_repo(tmp_path / "repo")
    full, update = build_both(tree, tmp_path / "out")

    shared = sorted(set(full) & set(update))
    assert set(shared) >= {
        "README.md",
        "src/app.py",
        "library/manifest.json",
        "start-app.bat",
        ".githooks/pre-commit",
    }
    assert cross_pack_byte_diff(full, update) == []


def test_update_pack_matches_git_archive(tmp_path: Path) -> None:
    """更新包字节 = 钉住配置的 `git archive` 不变量。"""
    tree = make_mini_repo(tmp_path / "repo")
    paths = tracked_files(tree)

    manifest = tmp_path / "files.txt"
    manifest.write_text("".join(f"{p}\n" for p in paths), encoding="utf-8")
    pack_update(tree, version="v9.9.9", out_dir=tmp_path / "update", files_manifest=manifest)

    update = zip_bytes(tmp_path / "update" / "firstep-update-v9.9.9.zip")
    assert update == archive_bytes(tree, paths)


def test_pinning_autocrlf_is_what_makes_it_match(tmp_path: Path) -> None:
    """红证：不钉配置（= 改动前的 `git archive`）时，本机 autocrlf=true 会转出 CRLF。"""
    tree = make_mini_repo(tmp_path / "repo", autocrlf="true")
    paths = tracked_files(tree)
    unpinned = archive_bytes(tree, paths, config=())
    pinned = archive_bytes(tree, paths)

    assert unpinned["README.md"] == b"# firstep\r\n\xe6\xad\xa3\xe6\x96\x87\r\n"
    assert pinned["README.md"] == b"# firstep\n\xe6\xad\xa3\xe6\x96\x87\n"
    assert unpinned != pinned


def test_autocrlf_true_and_false_agree(tmp_path: Path) -> None:
    """换一台没设 autocrlf 的机器，两个包的字节仍必须一致（不依赖本机配置）。"""
    results = []
    for setting in ("true", "false"):
        tree = make_mini_repo(tmp_path / f"repo-{setting}", autocrlf=setting)
        full, update = build_both(tree, tmp_path / f"out-{setting}")
        shared = sorted(set(full) & set(update))
        assert cross_pack_byte_diff(full, update) == []
        results.append({name: full[name] for name in shared})
    assert results[0] == results[1]


def test_bat_stays_crlf_and_hook_stays_lf(tmp_path: Path) -> None:
    """`.gitattributes` 的物化口径不能被本工单碰坏：批处理 CRLF、钩子 LF。"""
    tree = make_mini_repo(tmp_path / "repo")
    full, update = build_both(tree, tmp_path / "out")
    for content in (full, update):
        assert content["start-app.bat"] == b"@echo off\r\necho hi\r\n"
        assert content[".githooks/pre-commit"] == b"#!/bin/sh\necho hi\n"


def test_full_pack_manifest_hashes_match_zip_bytes(tmp_path: Path) -> None:
    """完整包清单里的 SHA256 = 实际写进 zip 的字节（清单不能自说自话）。"""
    import hashlib
    import json

    tree = make_mini_repo(tmp_path / "repo")
    out = tmp_path / "full"
    prepare_full_package(tree, version="v9.9.9", out_dir=out, published_at="")
    manifest = json.loads((out / "firstep-full-v9.9.9.manifest.json").read_text("utf-8"))
    content = zip_bytes(out / "firstep-full-v9.9.9.zip")

    assert content
    for item in manifest["files"]:
        assert hashlib.sha256(content[item["path"]]).hexdigest() == item["sha256"]
        assert len(content[item["path"]]) == item["size"]


# ---------------------------------------------------------------------------
# 小发版四件套自身
# ---------------------------------------------------------------------------


def test_update_pack_files_txt_matches_zip_entries(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path / "repo")
    out = tmp_path / "update"
    manifest = tmp_path / "files.txt"
    manifest.write_text("README.md\nsrc/app.py\n", encoding="utf-8")
    written = pack_update(tree, version="v9.9.9", out_dir=out, files_manifest=manifest)

    assert written == out / "firstep-update-v9.9.9.zip"
    assert read_files_manifest(out / "firstep-update-v9.9.9.files.txt") == ["README.md", "src/app.py"]
    assert sorted(zip_bytes(written)) == ["README.md", "src/app.py"]


def test_update_pack_writes_sha256_sidecar_consistently(tmp_path: Path) -> None:
    """`sha256_of` 与标准库复算一致（打包脚本据此写 .sha256.txt）。"""
    import hashlib

    tree = make_mini_repo(tmp_path / "repo")
    manifest = tmp_path / "files.txt"
    manifest.write_text("README.md\n", encoding="utf-8")
    written = pack_update(tree, version="v9.9.9", out_dir=tmp_path / "out", files_manifest=manifest)
    expected = hashlib.sha256(written.read_bytes()).hexdigest()
    assert sha256_of(written) == expected


def test_update_pack_rejects_empty_missing_and_unreadable(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path / "repo")
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        pack_update(tree, version="v9.9.9", out_dir=tmp_path / "o1", files_manifest=empty)
    with pytest.raises(ValueError):
        pack_update(tree, version="v9.9.9", out_dir=tmp_path / "o2", files_manifest=tmp_path / "无.txt")
    missing = tmp_path / "missing.txt"
    missing.write_text("nope/absent.md\n", encoding="utf-8")
    with pytest.raises(ValueError):
        pack_update(tree, version="v9.9.9", out_dir=tmp_path / "o3", files_manifest=missing)


def test_update_pack_rejects_bad_version(tmp_path: Path) -> None:
    tree = make_mini_repo(tmp_path / "repo")
    manifest = tmp_path / "files.txt"
    manifest.write_text("README.md\n", encoding="utf-8")
    with pytest.raises(ValueError):
        pack_update(tree, version="../evil", out_dir=tmp_path / "out", files_manifest=manifest)


def test_update_pack_works_without_git(tmp_path: Path) -> None:
    """非 git 目录（手工打包 / 测试夹具）回退工作树，不因缺 git 而炸。"""
    tree = tmp_path / "plain"
    (tree / "src").mkdir(parents=True)
    (tree / "src" / "app.py").write_bytes(b"print(3)\n")
    manifest = tmp_path / "files.txt"
    manifest.write_text("src/app.py\n", encoding="utf-8")
    out = tmp_path / "out"
    pack_update(tree, version="v9.9.9", out_dir=out, files_manifest=manifest)
    assert zip_bytes(out / "firstep-update-v9.9.9.zip") == {"src/app.py": b"print(3)\n"}


# ---------------------------------------------------------------------------
# 发布侧自检的跨包断言
# ---------------------------------------------------------------------------


def test_release_check_reports_cross_pack_diff(tmp_path: Path) -> None:
    """自检脚本的跨包判据：抄件一致时差异为空，抄件不同必须点名该文件。"""
    tree = make_mini_repo(tmp_path / "repo")
    full, update = build_both(tree, tmp_path / "out")

    assert cross_pack_byte_diff(full, update) == []

    tampered = dict(update)
    tampered["README.md"] = full["README.md"].replace(b"\n", b"\r\n")
    assert cross_pack_byte_diff(full, tampered) == ["README.md"]
