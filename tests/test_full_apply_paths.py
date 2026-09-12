"""工具根判定与更新器拉起预检（工单 full-download/09 回归）。

真机演练实测缺陷：源码直跑（`PYTHONPATH=src`）时 `webapp.tool_root()` 用
`parent.parent` 推根 → 得到 `<根>/src` → 更新器被拼成 `<根>/src/tools/update-app.py`
→ 子进程秒退，而编排只看「进程起没起来」就报成功（下载 783 MB 后什么都没替换）。
"""

from __future__ import annotations

import sys
from pathlib import Path

from contest_generator.full_apply import apply_full_package
from contest_generator.webapp import tool_root

REPO = Path(__file__).resolve().parent.parent


def test_tool_root_is_repo_root_in_source_mode() -> None:
    """源码直跑：工具根必须是仓库根（含 tools/ 与启动脚本的那一层）。"""
    root = tool_root()
    assert (root / "tools" / "update-app.py").is_file(), f"工具根判定错误：{root}"
    assert (root / "start-app.vbs").is_file(), f"工具根缺启动脚本：{root}"
    assert root == REPO


def test_tool_root_never_returns_src_dir() -> None:
    """绝不能返回 src/（那会让更新器路径变成 src/tools/...）。"""
    assert tool_root().name != "src"


def test_apply_rejects_missing_updater_script(tmp_path: Path) -> None:
    """工具根里没有 tools/update-app.py → 拒绝并给中文原因，且不起进程。"""
    parts_dir = tmp_path / "updates" / "full"
    parts_dir.mkdir(parents=True)
    part = parts_dir / "firstep-full-v1.1.0.zip"
    part.write_bytes(b"zip")
    empty_root = tmp_path / "tool-root"
    empty_root.mkdir()

    spawned: list[list[str]] = []

    def spy_spawn(command, cwd, log_path):
        spawned.append(list(command))
        return 1

    result = apply_full_package(
        parts=[{"name": part.name, "path": str(part)}],
        updates_dir=tmp_path / "updates",
        tool_root=empty_root,
        version="v1.1.0",
        manifest_url="https://example.com/m.json",
        spawn=spy_spawn,
    )
    assert result.ok is False
    assert "更新器脚本不存在" in result.message
    assert spawned == [], "路径不对时不该起进程"


def test_updater_stop_port_comes_from_launcher_env(monkeypatch, tmp_path: Path) -> None:
    """停服端口必须取 FIRSTEP_LAUNCHER_PORT——否则会去停 8000 上的另一个实例。

    真机演练实测：沙箱的更新器默认拿 8000，把用户在 8000 上正在用的实例停掉了。
    """
    parts_dir = tmp_path / "updates" / "full"
    parts_dir.mkdir(parents=True)
    part = parts_dir / "firstep-full-v1.1.0.zip"
    part.write_bytes(b"zip")
    captured: list[list[str]] = []

    def spy_spawn(command, cwd, log_path):
        captured.append(list(command))
        return 1

    monkeypatch.setenv("FIRSTEP_LAUNCHER_PORT", "8020")
    apply_full_package(
        parts=[{"name": part.name, "path": str(part)}],
        updates_dir=tmp_path / "updates",
        tool_root=REPO,
        version="v1.1.0",
        manifest_url="https://example.com/m.json",
        spawn=spy_spawn,
    )
    command = captured[0]
    assert command[command.index("--port") + 1] == "8020"


def test_updater_stop_port_defaults_to_8000_without_env(monkeypatch, tmp_path: Path) -> None:
    from contest_generator.full_apply import resolve_launcher_port

    monkeypatch.delenv("FIRSTEP_LAUNCHER_PORT", raising=False)
    assert resolve_launcher_port() == 8000
    monkeypatch.setenv("FIRSTEP_LAUNCHER_PORT", "abc")
    assert resolve_launcher_port() == 8000, "非法值回落默认端口"
    monkeypatch.setenv("FIRSTEP_LAUNCHER_PORT", "70000")
    assert resolve_launcher_port() == 8000, "超范围回落默认端口"
    monkeypatch.setenv("FIRSTEP_LAUNCHER_PORT", "8020")
    assert resolve_launcher_port() == 8020


def test_small_update_spawn_passes_launcher_port(monkeypatch, tmp_path: Path) -> None:
    """小发版一键更新也要显式传停服端口（同一个「误停 8000 上另一个实例」缺陷）。

    真机演练实测：沙箱的小发版更新器按默认端口 8000 停了用户正在用的实例。
    """
    import subprocess

    from contest_generator import webapp as webapp_mod

    captured: dict[str, list[str]] = {}

    class FakePopen:
        def __init__(self, command, **kwargs):
            captured["command"] = list(command)

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    monkeypatch.setenv("FIRSTEP_LAUNCHER_PORT", "8020")
    webapp_mod.spawn_updater(
        data_dir=tmp_path / "data",
        zip_path=tmp_path / "firstep-update-1.1.1.zip",
        removed_path=None,
    )
    command = captured["command"]
    assert "--port" in command, f"没传 --port：{command}"
    assert command[command.index("--port") + 1] == "8020"
    assert str(tmp_path / "data") in command


def test_apply_uses_correct_updater_path_for_real_root(tmp_path: Path) -> None:
    """真工具根（仓库根）下命令里的脚本路径必须是 <根>/tools/update-app.py。"""
    parts_dir = tmp_path / "updates" / "full"
    parts_dir.mkdir(parents=True)
    part = parts_dir / "firstep-full-v1.1.0.zip"
    part.write_bytes(b"zip")

    captured: list[list[str]] = []

    def spy_spawn(command, cwd, log_path):
        captured.append(list(command))
        return 1

    result = apply_full_package(
        parts=[{"name": part.name, "path": str(part)}],
        updates_dir=tmp_path / "updates",
        tool_root=REPO,
        version="v1.1.0",
        manifest_url="https://example.com/m.json",
        spawn=spy_spawn,
    )
    assert result.ok is True
    command = captured[0]
    assert command[1] == str(REPO / "tools" / "update-app.py")
    assert Path(command[1]).is_file()
    assert "--full-manifest" in command
