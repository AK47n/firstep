"""更新器全量模式测试（工单 full-download/04）。

覆盖：多分卷整体预检后按清单序解压、zip slip 整体拒绝（目标目录零改动）、
被覆盖文件备份、按删除清单清理废弃文件、包外文件与「不进包的第三方安装包」
原样保留、资料库基线清单写回、更新结果记录（成功 / 失败）、updating.lock
生命周期、以及单包（小发版）模式行为不变。
"""

from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path

import pytest

from tests.test_update_app import _load_update_app

updater = _load_update_app()


def _write_zip(path: Path, entries: dict[str, str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def _make_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    """(工具根, 用户数据目录, 下载目录) —— 工具根里预置旧版本文件。"""
    root = tmp_path / "tool"
    data = tmp_path / "data"
    downloads = data / "updates"
    (root / "src" / "contest_generator").mkdir(parents=True)
    (root / "src" / "contest_generator" / "__init__.py").write_text(
        '__version__ = "1.0.0"\n', encoding="utf-8"
    )
    (root / "README.md").write_text("# 旧说明\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "sources" / "materials" / "手册").mkdir(parents=True)
    (root / "sources" / "materials" / "手册" / "a.md").write_text("旧手册\n", encoding="utf-8")
    # 不进包的第三方安装包（必须原地不动）
    (root / "sources" / "materials" / "2026_04_配套资料").mkdir(parents=True)
    (root / "sources" / "materials" / "2026_04_配套资料" / "00_CH341SER.EXE").write_text(
        "MZ", encoding="utf-8"
    )
    # 用户数据（工具根之外，天然保留）
    downloads.mkdir(parents=True)
    (data / "config.json").write_text("{}", encoding="utf-8")
    return root, data, downloads


def _manifest(parts: list[Path], removed: list[str] | None = None) -> Path:
    path = parts[0].parent / "firstep-full-v1.1.0.manifest.json"
    path.write_text(
        json.dumps(
            {
                "version": "v1.1.0",
                "parts": [{"zip_name": p.name, "size": p.stat().st_size, "sha256": ""} for p in parts],
                "removed": removed or [],
                "materials_manifest": {
                    "version": "v1.1.0",
                    "published_at": "",
                    "batches": [
                        {
                            "slug": "2026-08-mspm0-manuals",
                            "name": "2026_08_MSPM0G3507与常用芯片手册",
                            "files": [
                                {
                                    "path": "2026_08_MSPM0G3507与常用芯片手册/手册.md",
                                    "size": 3,
                                    "sha256": "a" * 64,
                                }
                            ],
                            "removed": [],
                            "parts": [],
                        }
                    ],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _options(root: Path, data: Path, parts: list[Path], manifest: Path):
    return updater.UpdateOptions(
        zip_path=parts[0],
        root=root,
        data_dir=data,
        stop=False,
        restart=False,
        check_deps=False,
        full_parts=[str(p) for p in parts],
        full_manifest_location=str(manifest),
        log=updater.logging.getLogger("test-full"),
    )


# ---------------------------------------------------------------------------
# 全量模式：解压落位
# ---------------------------------------------------------------------------


def test_full_mode_extracts_all_parts(tmp_path: Path) -> None:
    root, data, downloads = _make_workspace(tmp_path)
    part1 = _write_zip(
        downloads / "firstep-full-v1.1.0.part1.zip",
        {
            "src/contest_generator/__init__.py": '__version__ = "1.1.0"\n',
            "README.md": "# 新说明\n",
        },
    )
    part2 = _write_zip(
        downloads / "firstep-full-v1.1.0.part2.zip",
        {"docs/guide.md": "# 指南\n", "library/modules/oled/manifest.json": "{}"},
    )
    manifest = _manifest([part1, part2])

    code = updater.run_update(_options(root, data, [part1, part2], manifest))
    assert code == 0
    assert (root / "src" / "contest_generator" / "__init__.py").read_text(
        encoding="utf-8"
    ) == '__version__ = "1.1.0"\n'
    assert (root / "docs" / "guide.md").read_text(encoding="utf-8") == "# 指南\n"
    assert (root / "library" / "modules" / "oled" / "manifest.json").is_file()


def test_full_mode_backs_up_overwritten_files(tmp_path: Path) -> None:
    root, data, downloads = _make_workspace(tmp_path)
    part = _write_zip(
        downloads / "firstep-full-v1.1.0.zip",
        {"README.md": "# 新说明\n", "src/contest_generator/__init__.py": "v2\n"},
    )
    manifest = _manifest([part])
    code = updater.run_update(_options(root, data, [part], manifest))
    assert code == 0
    backups = sorted((data / "updates" / "backup").iterdir())
    assert len(backups) == 1
    backup = backups[0]
    assert (backup / "README.md").read_text(encoding="utf-8") == "# 旧说明\n"


def test_full_mode_writes_materials_baseline(tmp_path: Path) -> None:
    root, data, downloads = _make_workspace(tmp_path)
    part = _write_zip(downloads / "firstep-full-v1.1.0.zip", {"README.md": "# 新\n"})
    manifest = _manifest([part])
    assert not (root / "sources" / "materials" / ".materials-manifest.json").exists()

    code = updater.run_update(_options(root, data, [part], manifest))
    assert code == 0
    baseline = json.loads(
        (root / "sources" / "materials" / ".materials-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert baseline["version"] == "v1.1.0"
    assert baseline["batches"][0]["slug"] == "2026-08-mspm0-manuals"


def test_full_mode_skips_parts_not_present_in_package_content(tmp_path: Path) -> None:
    """不进包的第三方安装包必须原地不动（删除清单只以完整包清单为基线）。"""
    root, data, downloads = _make_workspace(tmp_path)
    part = _write_zip(downloads / "firstep-full-v1.1.0.zip", {"README.md": "# 新\n"})
    manifest = _manifest([part], removed=["sources/materials/手册/a.md"])
    installer = root / "sources" / "materials" / "2026_04_配套资料" / "00_CH341SER.EXE"

    code = updater.run_update(_options(root, data, [part], manifest))
    assert code == 0
    assert installer.is_file(), "第三方安装包不该被删"
    assert not (root / "sources" / "materials" / "手册" / "a.md").exists()
    assert (data / "config.json").is_file()
    assert (root / "pyproject.toml").is_file()


def test_full_mode_applies_removed_list_from_manifest(tmp_path: Path) -> None:
    """删除清单来自**清单 JSON 的 removed**（发布侧真实产物形态）。

    回归：发布侧曾只写 removed.txt、不写清单 removed，导致线上清理静默不执行。
    """
    root, data, downloads = _make_workspace(tmp_path)
    part = _write_zip(downloads / "firstep-full-v1.1.0.zip", {"README.md": "# 新\n"})
    manifest = _manifest([part], removed=["sources/materials/手册/a.md"])
    assert json.loads(manifest.read_text(encoding="utf-8"))["removed"] == [
        "sources/materials/手册/a.md"
    ]
    assert updater.run_update(_options(root, data, [part], manifest)) == 0
    assert not (root / "sources" / "materials" / "手册" / "a.md").exists()


def test_full_mode_without_removed_key_is_noop(tmp_path: Path) -> None:
    """清单没有 removed 键（老资产）→ 跳过删除，不报错。"""
    root, data, downloads = _make_workspace(tmp_path)
    part = _write_zip(downloads / "firstep-full-v1.1.0.zip", {"README.md": "# 新\n"})
    manifest = _manifest([part])
    data_json = json.loads(manifest.read_text(encoding="utf-8"))
    data_json.pop("removed", None)
    manifest.write_text(json.dumps(data_json, ensure_ascii=False), encoding="utf-8")
    assert updater.run_update(_options(root, data, [part], manifest)) == 0
    assert (root / "sources" / "materials" / "手册" / "a.md").is_file()


def test_full_mode_cleans_upstate_and_lock(tmp_path: Path) -> None:
    root, data, downloads = _make_workspace(tmp_path)
    part = _write_zip(downloads / "firstep-full-v1.1.0.zip", {"README.md": "# 新\n"})
    manifest = _manifest([part])
    code = updater.run_update(_options(root, data, [part], manifest))
    assert code == 0
    lock = data / "updates" / "updating.lock"
    assert not lock.exists(), "更新器退出后不该留下更新中锁"
    result = json.loads((data / "updates" / "last-update.json").read_text(encoding="utf-8"))
    assert result["status"] == "ok"
    assert result["mode"] == "full"
    assert result["version"] == "v1.1.0"


# ---------------------------------------------------------------------------
# 安全：zip slip 整体拒绝
# ---------------------------------------------------------------------------


def test_full_mode_rejects_zip_slip_without_touching_target(tmp_path: Path) -> None:
    root, data, downloads = _make_workspace(tmp_path)
    good = _write_zip(downloads / "firstep-full-v1.1.0.part1.zip", {"README.md": "# 新\n"})
    evil = _write_zip(
        downloads / "firstep-full-v1.1.0.part2.zip",
        {"../evil.txt": "pwned", "src/ok.py": "ok"},
    )
    manifest = _manifest([good, evil])

    code = updater.run_update(_options(root, data, [good, evil], manifest))
    assert code == 1
    assert not (tmp_path / "evil.txt").exists()
    # 整体拒绝：合法卷也不该落位（预检在写盘之前）
    assert (root / "README.md").read_text(encoding="utf-8") == "# 旧说明\n"
    assert not (root / "src" / "ok.py").exists()
    result = json.loads((data / "updates" / "last-update.json").read_text(encoding="utf-8"))
    assert result["status"] == "failed"


def test_full_mode_rejects_absolute_path_entries(tmp_path: Path) -> None:
    root, data, downloads = _make_workspace(tmp_path)
    bad = _write_zip(downloads / "firstep-full-v1.1.0.zip", {"C:/Windows/evil.dll": "x"})
    manifest = _manifest([bad])
    assert updater.run_update(_options(root, data, [bad], manifest)) == 1


def test_full_mode_removed_list_path_escape_rejected(tmp_path: Path) -> None:
    root, data, downloads = _make_workspace(tmp_path)
    part = _write_zip(downloads / "firstep-full-v1.1.0.zip", {"README.md": "# 新\n"})
    manifest = _manifest([part], removed=["../outside.txt"])
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")

    assert updater.run_update(_options(root, data, [part], manifest)) == 1
    assert outside.is_file()


# ---------------------------------------------------------------------------
# 兼容：小发版单包模式原行为不变
# ---------------------------------------------------------------------------


def test_single_zip_mode_still_works(tmp_path: Path) -> None:
    root, data, downloads = _make_workspace(tmp_path)
    part = _write_zip(downloads / "firstep-update-v1.1.0.zip", {"README.md": "# 新说明\n"})
    opts = updater.UpdateOptions(
        zip_path=part,
        root=root,
        data_dir=data,
        stop=False,
        restart=False,
        check_deps=False,
        log=updater.logging.getLogger("test-single"),
    )
    assert updater.run_update(opts) == 0
    assert (root / "README.md").read_text(encoding="utf-8") == "# 新说明\n"
    result = json.loads((data / "updates" / "last-update.json").read_text(encoding="utf-8"))
    assert result["mode"] == "single"


def test_parts_from_manifest_used_when_not_given(tmp_path: Path) -> None:
    """未显式给分卷时：按清单 parts 顺序在下载目录里找（分卷乱序也无妨）。"""
    root, data, downloads = _make_workspace(tmp_path)
    p2 = _write_zip(downloads / "firstep-full-v1.1.0.part2.zip", {"b.txt": "B"})
    p1 = _write_zip(downloads / "firstep-full-v1.1.0.part1.zip", {"a.txt": "A"})
    manifest = _manifest([p1, p2])
    opts = updater.UpdateOptions(
        zip_path=p1,
        root=root,
        data_dir=data,
        stop=False,
        restart=False,
        check_deps=False,
        full_manifest_location=str(manifest),
        log=updater.logging.getLogger("test-order"),
    )
    assert updater.run_update(opts) == 0
    assert (root / "a.txt").read_text(encoding="utf-8") == "A"
    assert (root / "b.txt").read_text(encoding="utf-8") == "B"


def test_cli_accepts_full_options(tmp_path: Path, monkeypatch) -> None:
    root, data, downloads = _make_workspace(tmp_path)
    part = _write_zip(downloads / "firstep-full-v1.1.0.zip", {"README.md": "# 新\n"})
    manifest = _manifest([part])
    captured: dict[str, object] = {}

    def fake_run(opts):
        captured["opts"] = opts
        return 0

    monkeypatch.setattr(updater, "run_update", fake_run)
    code = updater.main(
        [
            "--zip",
            str(part),
            "--root",
            str(root),
            "--data-dir",
            str(data),
            "--full-manifest",
            str(manifest),
            "--no-stop",
            "--no-restart",
            "--skip-pip",
        ]
    )
    assert code == 0
    opts = captured["opts"]
    assert opts.full_manifest_location == str(manifest)
    assert opts.full_parts == []


def test_full_manifest_url_is_not_mangled(tmp_path: Path, monkeypatch) -> None:
    """URL 形式的清单地址必须原样送达更新器（回归：[Errno 22] 正斜杠变反斜杠）。

    Python 3.14 + Windows 上 `Path("https://a/b")` 会把 `//` 折叠成 `\\`，
    更新器于是认不出 URL、按本地路径打开而报 `[Errno 22] Invalid argument`。
    """
    url = (
        "https://github.com/AK47n/firstep/releases/download/v1.1.0/"
        "firstep-full-v1.1.0.manifest.json"
    )
    captured: dict[str, object] = {}

    def fake_run(opts):
        captured["opts"] = opts
        return 0

    monkeypatch.setattr(updater, "run_update", fake_run)
    code = updater.main(
        ["--zip", "x.zip", "--full-manifest", url, "--no-stop", "--no-restart", "--skip-pip"]
    )
    assert code == 0
    opts = captured["opts"]
    assert opts.full_manifest_location == url
    assert "https://" in opts.full_manifest_location
    assert "\\" not in opts.full_manifest_location


def test_load_full_manifest_detects_url_before_path(tmp_path: Path, monkeypatch) -> None:
    """load_full_manifest 收到 URL 时走网络分支（不落本地路径分支）。"""
    url = "https://example.com/firstep-full-v1.1.0.manifest.json"
    seen: list[str] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"version": "v1.1.0", "parts": [], "files": []}'

    def fake_urlopen(request, timeout=0):
        seen.append(request.full_url if hasattr(request, "full_url") else str(request))
        return FakeResponse()

    monkeypatch.setattr(updater.urllib.request, "urlopen", fake_urlopen)
    data = updater.load_full_manifest(url)
    assert data["version"] == "v1.1.0"
    assert seen == [url], f"传给 urlopen 的地址被改坏：{seen}"


def test_load_full_manifest_rejects_broken_url(tmp_path: Path) -> None:
    """反斜杠形态的 URL（被 Path 折叠过的样子）→ 大声报错，不静默读本地。"""
    broken = "https:\\\\github.com\\AK47n\\x.json"
    with pytest.raises(updater.UpdateError):
        updater.load_full_manifest(broken)
