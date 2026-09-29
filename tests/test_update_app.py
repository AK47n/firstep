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


# ---------------------------------------------------------------------------
# 解压的临时名（工单 backlog-agent-sweep/02）
#
# 收走前的形状：固定临时名 `<目标>.update-tmp` + **没有 `finally`** —— 解压中途异常/被杀
# 就在工具根里留下 `*.update-tmp`（会被"产品文件与全新安装是否一致"那类判据读成"多出来的
# 文件"），同进程内两个解压者也会互抢同一个临时名。
# 收走后：`<目标>.<pid>-<计数>.update-tmp` + 失败清残渣（照 `atomic_io` 的纪律）。
# ---------------------------------------------------------------------------


def _tmp_leftovers(root: Path) -> list[str]:
    return [p.name for p in root.rglob("*.update-tmp")]


def test_extract_zip_writes_content_and_leaves_no_tmp(tmp_path, updater) -> None:
    """正常路径：内容落对、目录里零 `*.update-tmp`。"""
    root = tmp_path / "root"
    root.mkdir()
    zip_path = _make_zip(tmp_path, {"a.txt": "new-a", "sub/b.txt": "new-b"})
    members = updater.validate_zip_members(zip_path, root)
    assert updater.extract_zip(zip_path, root, members) == 2
    assert (root / "a.txt").read_text(encoding="utf-8") == "new-a"
    assert (root / "sub" / "b.txt").read_text(encoding="utf-8") == "new-b"
    assert _tmp_leftovers(root) == []


def test_extract_zip_failure_leaves_no_tmp_and_keeps_old_content(tmp_path, updater) -> None:
    """坏路径：替换失败时临时文件必须被清掉，且**没被写坏的那条**保持原样。

    造法照 `tests/test_hwcheck_triage.py` 的同族先例：把第二个目标做成**目录** →
    `os.replace(文件, 目录)` 必然失败（不管实现用哪个 API）。
    """
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("old-a", encoding="utf-8")
    (root / "b.txt").mkdir()  # 目标是个目录 → 换入必然失败
    zip_path = _make_zip(tmp_path, {"a.txt": "new-a", "b.txt": "new-b"})
    members = updater.validate_zip_members(zip_path, root)

    with pytest.raises(OSError):
        updater.extract_zip(zip_path, root, members)

    assert _tmp_leftovers(root) == [], "解压失败后留下了临时文件"
    assert (root / "a.txt").read_text(encoding="utf-8") == "new-a", "失败前已换入的那条应已生效"
    assert (root / "b.txt").is_dir(), "失败的那条不许被动过"


def test_extract_zip_temp_names_do_not_collide_within_one_process(tmp_path, updater, monkeypatch) -> None:
    """同一进程里两次解压**不许**用同一个临时名（固定名形态在这里就会撞）。

    判据直接盯"两次替换的源文件名"——比"跑完看结果"更早、更准。
    """
    root = tmp_path / "root"
    root.mkdir()
    seen: list[str] = []
    real_replace = updater.os.replace

    def recording_replace(src, dst):
        seen.append(Path(src).name)
        return real_replace(src, dst)

    monkeypatch.setattr(updater.os, "replace", recording_replace)
    for content in ("v1", "v2"):
        zip_path = _make_zip(tmp_path, {"a.txt": content}, name=f"z-{content}.zip")
        members = updater.validate_zip_members(zip_path, root)
        updater.extract_zip(zip_path, root, members)

    assert len(seen) == 2, f"应记录两次替换：{seen}"
    assert seen[0] != seen[1], f"两次解压用了同一个临时名：{seen}"
    assert all(name.endswith(".update-tmp") for name in seen), seen
