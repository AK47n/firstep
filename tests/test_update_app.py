"""应用内更新器集成测试（工单 auto-update/04）。

在临时目录完整演练更新流程（--no-stop / --no-restart 语义 = 选项
stop=False / restart=False）：迷你更新包（zip / removed）→ 旧树 +
模拟用户数据 → 断言落位、removed 删除、包外（.venv / 用户数据）原样、
备份生成、标记清理、zip slip 整体拒绝、pyproject 变更触发依赖安装判定。
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
import zipfile
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"

update_app = None


def _load_update_app():
    """通过 importlib 加载 tools/update-app.py（不在包内，pythonpath 不含）。

    必须注册进 sys.modules：UpdateOptions 的 dataclass 注解解析依赖
    `sys.modules[cls.__module__]`（否则 AttributeError: 'NoneType'）。
    """
    spec = importlib.util.spec_from_file_location(
        "update_app", TOOLS_DIR / "update-app.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["update_app"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def updater():
    return _load_update_app()


def _make_zip(
    tmp_path: Path, entries: dict[str, str], name: str = "firstep-update-v1.1.0.zip"
) -> Path:
    zip_path = tmp_path / name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry_name, content in entries.items():
            archive.writestr(entry_name, content)
    return zip_path


def _quiet_logger():
    logger = logging.getLogger("test-updater")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    return logger


def _old_tree(root: Path) -> None:
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("old-a", encoding="utf-8")
    (root / "sub" / "b.txt").write_text("old-b", encoding="utf-8")
    (root / "old.txt").write_text("bye", encoding="utf-8")
    (root / "pyproject.toml").write_text("project v1", encoding="utf-8")
    # 模拟工具目录外的保留物：.venv 与用户数据
    (root / ".venv" / "Scripts").mkdir(parents=True)
    (root / ".venv" / "Scripts" / "keep.py").write_text("keep", encoding="utf-8")


def test_run_update_installs_backs_up_removes_keeps_outside(
    tmp_path, updater
) -> None:
    root = tmp_path / "root"
    data_dir = tmp_path / "data"
    _old_tree(root)
    (data_dir / "updates").mkdir(parents=True)
    (data_dir / "config.json").write_text('{"key":"secret"}', encoding="utf-8")
    pending = data_dir / "updates" / "pending-update.json"
    pending.write_text('{"zip":"x"}', encoding="utf-8")

    zip_path = _make_zip(tmp_path, {
        "a.txt": "new-a",
        "sub/b.txt": "new-b",
        "new.txt": "hello",
        "pyproject.toml": "project v1",  # 与旧相同 → 不触发依赖安装
    })
    removed_path = tmp_path / "removed.txt"
    removed_path.write_text("old.txt\n", encoding="utf-8")

    opts = updater.UpdateOptions(
        zip_path=zip_path,
        removed_path=removed_path,
        root=root,
        data_dir=data_dir,
        stop=False,
        restart=False,
        check_deps=True,
        log=_quiet_logger(),
    )
    assert updater.run_update(opts) == 0

    # 落位
    assert (root / "a.txt").read_text(encoding="utf-8") == "new-a"
    assert (root / "sub" / "b.txt").read_text(encoding="utf-8") == "new-b"
    assert (root / "new.txt").read_text(encoding="utf-8") == "hello"
    # removed 删除
    assert not (root / "old.txt").exists()
    # 包外保留
    assert (root / ".venv" / "Scripts" / "keep.py").read_text(encoding="utf-8") == "keep"
    assert (data_dir / "config.json").read_text(encoding="utf-8") == '{"key":"secret"}'
    # 备份：被覆盖的旧文件（相对路径镜像）
    backup_root = data_dir / "updates" / "backup"
    backups = [p for p in backup_root.iterdir()]
    assert len(backups) == 1
    backup = backups[0]
    assert (backup / "a.txt").read_text(encoding="utf-8") == "old-a"
    assert (backup / "sub" / "b.txt").read_text(encoding="utf-8") == "old-b"
    # 标记：成功后 pending / lock 均清
    assert not pending.exists()
    assert not opts.lock_path.exists()
    # 结果记录：status ok + 版本从 zip 名解析
    result = json.loads((data_dir / "updates" / "last-update.json").read_text(encoding="utf-8"))
    assert result["status"] == "ok"
    assert result["version"] == "v1.1.0"
    assert "backup" in result["backup_dir"]


def test_zip_slip_rejected_before_any_write(tmp_path, updater) -> None:
    root = tmp_path / "root"
    data_dir = tmp_path / "data"
    _old_tree(root)
    pending = data_dir / "updates" / "pending-update.json"
    pending.parent.mkdir(parents=True)
    pending.write_text('{"zip":"x"}', encoding="utf-8")

    zip_path = _make_zip(tmp_path, {"../evil.txt": "pwn"})
    opts = updater.UpdateOptions(
        zip_path=zip_path,
        root=root,
        data_dir=data_dir,
        stop=False,
        restart=False,
        check_deps=False,
        log=_quiet_logger(),
    )
    assert updater.run_update(opts) == 1
    assert not (tmp_path / "evil.txt").exists()
    assert not (root / ".." / "evil.txt").exists()
    # 失败：pending 保留（启动器提示手动处理）、lock 已清（恢复启动器可用）
    assert pending.exists()
    assert not opts.lock_path.exists()
    # 结果记录：failed + 备份位置
    result = json.loads((data_dir / "updates" / "last-update.json").read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert "越界" in result["error"]
    # 未写盘：旧文件原样
    assert (root / "a.txt").read_text(encoding="utf-8") == "old-a"


def test_removed_outside_root_rejected(tmp_path, updater) -> None:
    root = tmp_path / "root"
    data_dir = tmp_path / "data"
    _old_tree(root)
    zip_path = _make_zip(tmp_path, {"a.txt": "new-a"})
    removed_path = tmp_path / "removed.txt"
    removed_path.write_text("../evil.txt\n", encoding="utf-8")
    opts = updater.UpdateOptions(
        zip_path=zip_path,
        removed_path=removed_path,
        root=root,
        data_dir=data_dir,
        stop=False,
        restart=False,
        check_deps=False,
        log=_quiet_logger(),
    )
    assert updater.run_update(opts) == 1
    assert not (tmp_path / "evil.txt").exists()


def test_pyproject_change_triggers_install(tmp_path, updater, monkeypatch) -> None:
    root = tmp_path / "root"
    _old_tree(root)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        updater,
        "install_dependencies",
        lambda r, py: calls.append((str(r), py)),
    )
    zip_path = _make_zip(tmp_path, {
        "a.txt": "new-a",
        "pyproject.toml": "project v2 changed",
    })
    opts = updater.UpdateOptions(
        zip_path=zip_path,
        root=root,
        data_dir=tmp_path / "data",
        stop=False,
        restart=False,
        check_deps=True,
        log=_quiet_logger(),
    )
    assert updater.run_update(opts) == 0
    assert len(calls) == 1
    assert calls[0][0] == str(root.resolve())


def test_pyproject_same_skips_install(tmp_path, updater, monkeypatch) -> None:
    root = tmp_path / "root"
    _old_tree(root)
    calls: list[str] = []
    monkeypatch.setattr(updater, "install_dependencies", lambda r, py: calls.append(str(r)))
    zip_path = _make_zip(tmp_path, {
        "a.txt": "new-a",
        "pyproject.toml": "project v1",  # 相同
    })
    opts = updater.UpdateOptions(
        zip_path=zip_path,
        root=root,
        data_dir=tmp_path / "data",
        stop=False,
        restart=False,
        check_deps=True,
        log=_quiet_logger(),
    )
    assert updater.run_update(opts) == 0
    assert calls == []


def test_validate_zip_members_rejects_absolute_and_backslash(tmp_path, updater) -> None:
    root = tmp_path / "root"
    _old_tree(root)
    for bad in ("C:/evil.txt", "/abs.txt", "a/../../evil.txt", "a\\..\\evil.txt"):
        zip_path = _make_zip(tmp_path, {bad: "pwn"})
        with pytest.raises(updater.UpdateError):
            updater.validate_zip_members(zip_path, root)


def test_safe_join_accepts_normal_nested(tmp_path, updater) -> None:
    root = tmp_path / "root"
    target = updater.safe_join(root, "sub/dir/file.c")
    assert target == (root / "sub" / "dir" / "file.c").resolve()
