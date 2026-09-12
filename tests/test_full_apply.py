"""完整包应用编排测试（工单 full-download/04）。

覆盖：待更新标记写出（版本 / 分卷 / 清单地址）、更新器命令行构造（独立进程，
`--full-manifest` + 逐个 `--part`）、分卷缺失与缺清单地址的拒绝（不起进程）、
spawn 失败的中文结果、以及 webapp 端点全链路（下载完成 → 拉起更新器 →
状态转 done）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contest_generator import full_task as ft
from contest_generator.full_apply import (
    PENDING_FILENAME,
    FullApplyResult,
    apply_full_package,
    build_updater_command,
)
from contest_generator.webapp import AppContext, create_app


@pytest.fixture(autouse=True)
def _reset_full_state():
    """重置模块级单例（任务 + 上次检查），防相邻测试互相污染。"""
    ft.set_last_check({})
    ft.set_full_task(None)
    yield
    ft.set_last_check({})
    ft.set_full_task(None)


def _ready_parts(tmp_path: Path, names: list[str]) -> list[dict]:
    parts = []
    for name in names:
        path = tmp_path / "updates" / "full" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"zip-bytes")
        parts.append({"name": name, "path": str(path), "sha256": "a" * 64, "size": 9})
    return parts


def _fake_tool_root(tmp_path: Path) -> Path:
    """假工具根：必须带 tools/update-app.py（拉起前预检要求它存在）。"""
    root = tmp_path / "tool"
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "tools" / "update-app.py").write_text("# 假更新器\n", encoding="utf-8")
    return root


def _spy_spawn(calls: list[tuple[list[str], Path, Path]]):
    def spawn(command, cwd, log_path):
        calls.append((list(command), Path(cwd), Path(log_path)))
        return 4242

    return spawn


# ---------------------------------------------------------------------------
# 命令行与标记
# ---------------------------------------------------------------------------


def test_build_updater_command_shape(tmp_path: Path) -> None:
    parts = [tmp_path / "a.part1.zip", tmp_path / "a.part2.zip"]
    command = build_updater_command(
        root=tmp_path / "tool",
        python="py.exe",
        manifest_location="https://example.com/firstep-full-v1.1.0.manifest.json",
        parts=parts,
        port=8123,
    )
    assert command[0] == "py.exe"
    assert command[1].endswith("update-app.py")
    assert "--full-manifest" in command
    assert "https://example.com/firstep-full-v1.1.0.manifest.json" in command
    assert command.count("--part") == 2
    assert "--port" in command and "8123" in command


def test_apply_writes_pending_marker_and_spawns(tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path, Path]] = []
    parts = _ready_parts(tmp_path, ["firstep-full-v1.1.0.zip"])
    result = apply_full_package(
        parts=parts,
        updates_dir=tmp_path / "updates",
        tool_root=_fake_tool_root(tmp_path),
        version="v1.1.0",
        manifest_url="https://example.com/manifest.json",
        spawn=_spy_spawn(calls),
    )
    assert result.ok is True
    assert result.version == "v1.1.0"
    assert "重启" in result.message
    pending = json.loads(
        (tmp_path / "updates" / PENDING_FILENAME).read_text(encoding="utf-8")
    )
    assert pending["mode"] == "full"
    assert pending["version"] == "v1.1.0"
    assert pending["parts"] == ["firstep-full-v1.1.0.zip"]
    assert pending["manifest"] == "https://example.com/manifest.json"
    assert len(calls) == 1
    command, cwd, log_path = calls[0]
    assert "--full-manifest" in command


def test_apply_rejects_missing_manifest_url(tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path, Path]] = []
    parts = _ready_parts(tmp_path, ["firstep-full-v1.1.0.zip"])
    result = apply_full_package(
        parts=parts,
        updates_dir=tmp_path / "updates",
        tool_root=_fake_tool_root(tmp_path),
        manifest_url="",
        spawn=_spy_spawn(calls),
    )
    assert result.ok is False
    assert "清单" in result.message
    assert calls == [], "缺清单不该起进程"
    assert not (tmp_path / "updates" / PENDING_FILENAME).exists()


def test_apply_rejects_missing_part_file(tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path, Path]] = []
    result = apply_full_package(
        parts=[{"name": "gone.zip", "path": str(tmp_path / "gone.zip")}],
        updates_dir=tmp_path / "updates",
        tool_root=_fake_tool_root(tmp_path),
        manifest_url="https://example.com/m.json",
        spawn=_spy_spawn(calls),
    )
    assert result.ok is False
    assert "未就绪" in result.message
    assert calls == []


def test_apply_reports_spawn_failure(tmp_path: Path) -> None:
    parts = _ready_parts(tmp_path, ["firstep-full-v1.1.0.zip"])

    def boom(command, cwd, log_path):
        raise OSError("权限不足")

    result = apply_full_package(
        parts=parts,
        updates_dir=tmp_path / "updates",
        tool_root=_fake_tool_root(tmp_path),
        version="v1.1.0",
        manifest_url="https://example.com/m.json",
        spawn=boom,
    )
    assert result.ok is False
    assert "拉起更新器失败" in result.message
    # 标记保留：前端/启动器据此提示手动处理
    assert (tmp_path / "updates" / PENDING_FILENAME).is_file()


# ---------------------------------------------------------------------------
# 端点全链路
# ---------------------------------------------------------------------------


def test_endpoint_full_flow_starts_updater(tmp_path: Path, monkeypatch) -> None:
    """check → apply（下载）→ 编排拉起更新器 → 状态 done。"""
    import hashlib

    payload = b"zip-bytes"
    sha = hashlib.sha256(payload).hexdigest()
    part_name = "firstep-full-v1.1.0.zip"
    check = {
        "current_version": "",
        "latest_version": "v1.1.0",
        "update_available": True,
        "total_bytes": len(payload),
        "parts": [
            {
                "name": part_name,
                "size": len(payload),
                "sha256": sha,
                "url": f"https://example.com/{part_name}",
            }
        ],
        "reason": "no-installed",
        "error": "",
        "message": "",
        "manifest_url": "https://example.com/firstep-full-v1.1.0.manifest.json",
    }
    ft.set_last_check(check)

    def fake_download(url: str, dest: Path, on_progress) -> str:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        on_progress(len(payload))
        return sha

    monkeypatch.setattr("contest_generator.full_task.download_part", fake_download)
    monkeypatch.setattr("contest_generator.webapp.free_bytes", lambda path: 10 * 1024**3)
    monkeypatch.setattr("contest_generator.webapp.start_full_update", lambda task: task.run())
    spawns: list[list[str]] = []

    def spy_apply_full_package(**kwargs):
        # 注入点在 webapp 的引用上（默认 spawn 在函数定义时绑定，patch 模块
        # 属性改不到它）；这里只记录「拉起的是哪条命令」，不真起进程
        spawns.append(
            build_updater_command(
                root=kwargs["tool_root"],
                python="py.exe",
                manifest_location=kwargs["manifest_url"],
                parts=[__import__("pathlib").Path(p["path"]) for p in kwargs["parts"]],
                port=8000,
            )
        )
        return FullApplyResult(ok=True, version=kwargs.get("version", ""), message="已开始应用")

    monkeypatch.setattr("contest_generator.webapp.apply_full_package", spy_apply_full_package)

    client = TestClient(create_app(AppContext(config_path=tmp_path / "config.json")))
    resp = client.post("/api/update/full/apply", json={"parts": [part_name]})
    assert resp.status_code == 200
    status = client.get("/api/update/full/status").json()
    assert status["state"] == "done", status
    assert status["parts"][0]["ok"] is True

    assert len(spawns) == 1, "应拉起一次更新器"
    command = spawns[0]
    assert "--full-manifest" in command
    assert any(arg.endswith("manifest.json") for arg in command)
    assert command.count("--part") == 1
    # 待更新标记由编排写（真实实现）；本测试只验证编排被调用，标记另测
    assert status["error"] == ""


def test_endpoint_apply_without_manifest_url_marks_failed(
    tmp_path: Path, monkeypatch
) -> None:
    """check 结果里没有清单地址（例如旧版前端）→ 任务失败并给中文原因。"""
    import hashlib

    payload = b"zip-bytes"
    sha = hashlib.sha256(payload).hexdigest()
    part_name = "firstep-full-v1.1.0.zip"
    ft.set_last_check(
        {
            "latest_version": "v1.1.0",
            "total_bytes": len(payload),
            "parts": [
                {"name": part_name, "size": len(payload), "sha256": sha,
                 "url": f"https://example.com/{part_name}"}
            ],
            "manifest_url": "",
        }
    )

    def fake_download(url: str, dest: Path, on_progress) -> str:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        on_progress(len(payload))
        return sha

    monkeypatch.setattr("contest_generator.full_task.download_part", fake_download)
    monkeypatch.setattr("contest_generator.webapp.free_bytes", lambda path: 10 * 1024**3)
    monkeypatch.setattr("contest_generator.webapp.start_full_update", lambda task: task.run())
    client = TestClient(create_app(AppContext(config_path=tmp_path / "config.json")))
    assert client.post("/api/update/full/apply", json={"parts": [part_name]}).status_code == 200
    status = client.get("/api/update/full/status").json()
    assert status["state"] == "failed"
    assert "清单" in status["error"]
