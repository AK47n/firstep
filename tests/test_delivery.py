"""交付域（工单 delivery-suite/01）：打开工程 / 交付检查 / 一键打包 + 三端点。

纯确定性单元：open_project_dir 平台分流（stm32 UV4 优先 → 关联打开 →
explorer 兜底 / mspm0 folder / 平台未知 400——subprocess 与 os.startfile
均 monkeypatch 不真启动）；delivery_check 状态统计 + 未完成清单 + 未拆解
提示；package_project 排除规则 + 时间戳命名 + 缺失目录 400；webapp 集成：
三端点 200 / 400 分级。
"""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contest_generator.context_manifest import ContextError
from contest_generator.delivery import (
    DeliveryError,
    delivery_check,
    open_project_dir,
    package_project,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.task_progress import Task, TaskPlan
from contest_generator.webapp import AppContext, create_app


# ---------------------------------------------------------------------------
# 素材构造
# ---------------------------------------------------------------------------


def _stm32_project(tmp_path: Path) -> Path:
    out = tmp_path / "stm32"
    (out / "user").mkdir(parents=True)
    (out / "user" / "Project.uvprojx").write_text("<Project/>", encoding="utf-8")
    return out


def _mspm0_project(tmp_path: Path) -> Path:
    out = tmp_path / "mspm0"
    out.mkdir(parents=True)
    (out / ".cproject").write_text("<cproject/>", encoding="utf-8")
    return out


def _plan_with_statuses(*statuses: str) -> TaskPlan:
    """按状态序列造任务清单（build_task_plan 不保留 status——直接构造 Task）。"""
    return TaskPlan(tasks=tuple(
        Task(id=f"t{i}", title=f"任务{i}", description="描述", status=status)
        for i, status in enumerate(statuses, 1)
    ))


# ---------------------------------------------------------------------------
# open_project_dir：平台分流
# ---------------------------------------------------------------------------


def test_open_stm32_uses_uv4_when_found(tmp_path, monkeypatch):
    """stm32 + UV4 命中（config 覆盖）→ Popen([uv4, uvprojx])，mode=ide。"""
    out = _stm32_project(tmp_path)
    uv4 = tmp_path / "UV4.exe"
    uv4.write_bytes(b"MZ")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "contest_generator.delivery.subprocess.Popen",
        lambda cmd, **kw: calls.append(list(cmd)),
    )
    result = open_project_dir(out, uv4_path=str(uv4))
    assert result["mode"] == "ide"
    assert result["target"].endswith("Project.uvprojx")
    assert calls == [[str(uv4), str(out / "user" / "Project.uvprojx")]]
    assert "Keil" in result["message"]


def test_open_stm32_falls_back_to_startfile(tmp_path, monkeypatch):
    """stm32 无 UV4 → os.startfile 关联打开（mode 仍 ide）。"""
    out = _stm32_project(tmp_path)
    monkeypatch.setattr(
        "contest_generator.delivery._find_uv4", lambda uv4_path: None
    )
    opened: list[str] = []
    monkeypatch.setattr(os, "startfile", lambda p: opened.append(p))
    result = open_project_dir(out)
    assert result["mode"] == "ide"
    assert opened and opened[0].endswith("Project.uvprojx")


def test_open_stm32_startfile_fails_then_explorer(tmp_path, monkeypatch):
    """stm32 无 UV4 且 startfile 抛 OSError → explorer 兜底 mode=folder。"""
    out = _stm32_project(tmp_path)
    monkeypatch.setattr(
        "contest_generator.delivery._find_uv4", lambda uv4_path: None
    )
    monkeypatch.setattr(
        os, "startfile", lambda p: (_ for _ in ()).throw(OSError("no assoc"))
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "contest_generator.delivery.subprocess.Popen",
        lambda cmd, **kw: calls.append(list(cmd)),
    )
    result = open_project_dir(out)
    assert result["mode"] == "folder"
    assert calls[0][0] == "explorer"
    assert "Keil" in result["message"]


def test_open_mspm0_opens_folder(tmp_path, monkeypatch):
    """mspm0 → explorer 打开目录 + CCS 导入提示。"""
    out = _mspm0_project(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "contest_generator.delivery.subprocess.Popen",
        lambda cmd, **kw: calls.append(list(cmd)),
    )
    result = open_project_dir(out)
    assert result["mode"] == "folder"
    assert calls == [["explorer", str(out)]]
    assert "CCS" in result["message"]


def test_open_unknown_platform_400(tmp_path, monkeypatch):
    """平台未知（_infer_platform 抛 ContextError）→ DeliveryError。"""
    out = tmp_path / "empty"
    out.mkdir()

    def _raise(directory):
        raise ContextError("无法判定平台")

    monkeypatch.setattr(
        "contest_generator.context_manifest._infer_platform", _raise
    )
    with pytest.raises(DeliveryError, match="无法判定平台"):
        open_project_dir(out)


def test_open_explorer_missing_degrades_message(tmp_path, monkeypatch):
    """explorer 启动失败（非 Windows）→ 仍 folder 模式 + 手动打开提示。"""
    out = _mspm0_project(tmp_path)
    monkeypatch.setattr(
        "contest_generator.delivery.subprocess.Popen",
        lambda cmd, **kw: (_ for _ in ()).throw(OSError("no explorer")),
    )
    result = open_project_dir(out)
    assert result["mode"] == "folder"
    assert "手动打开" in result["message"]


# ---------------------------------------------------------------------------
# delivery_check：状态统计 / 未完成清单
# ---------------------------------------------------------------------------


def test_check_no_plan_tells_user(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "main.c").write_text("int main(void){}", encoding="utf-8")
    result = delivery_check(out)
    assert result["ok"] is False
    assert result["plan_present"] is False
    assert result["stats"] is None
    assert result["incomplete"] == []
    assert "尚未拆解" in result["message"]


def test_check_all_done_ok(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "main.c").write_text("int main(void){}", encoding="utf-8")
    from contest_generator.task_progress import write_task_plan

    write_task_plan(out, _plan_with_statuses("verified", "skipped", "verified"))
    result = delivery_check(out)
    assert result["ok"] is True
    assert result["plan_present"] is True
    assert result["stats"]["verified"] == 2
    assert result["stats"]["skipped"] == 1
    assert result["incomplete"] == []
    assert "全部步骤完成" in result["message"]


def test_check_incomplete_lists_and_failed_counts(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "main.c").write_text("int main(void){}", encoding="utf-8")
    from contest_generator.task_progress import write_task_plan

    write_task_plan(
        out,
        _plan_with_statuses("verified", "pending", "failed", "unverified"),
    )
    result = delivery_check(out)
    assert result["ok"] is False
    assert [item["id"] for item in result["incomplete"]] == ["t2", "t3", "t4"]
    statuses = {item["id"]: item["status"] for item in result["incomplete"]}
    assert statuses["t3"] == "failed"
    assert result["stats"]["verified"] == 1
    assert "还有 3 步未完成" in result["message"]


def test_check_warns_missing_main_c(tmp_path):
    """main.c 缺失 → message 追加提示（ok 仍以清单状态为准）。"""
    out = tmp_path / "out"
    out.mkdir()
    from contest_generator.task_progress import write_task_plan

    write_task_plan(out, _plan_with_statuses("verified"))
    result = delivery_check(out)
    assert result["ok"] is True
    assert "main.c 不存在" in result["message"]


# ---------------------------------------------------------------------------
# package_project：排除规则 / 时间戳 / 错误
# ---------------------------------------------------------------------------


def test_package_excludes_internal_and_temp(tmp_path):
    out = tmp_path / "工程"
    (out / "sub").mkdir(parents=True)
    (out / "main.c").write_text("int main(void){}", encoding="utf-8")
    (out / ".contest_tasks.json").write_text("{}", encoding="utf-8")
    (out / ".contest_context.json").write_text("{}", encoding="utf-8")
    (out / "x.tmp").write_text("tmp", encoding="utf-8")
    (out / "y.bak").write_text("bak", encoding="utf-8")
    (out / "sub" / "module.c").write_text("void m(void){}", encoding="utf-8")

    result = package_project(out)
    assert result["files"] == 2
    assert result["zip_path"].endswith(
        f"{out.name}-交付-" + result["zip_path"].split("-交付-")[1]
    )
    with zipfile.ZipFile(result["zip_path"]) as zf:
        names = set(zf.namelist())
    assert names == {"main.c", "sub/module.c"}
    assert Path(result["zip_path"]).stat().st_size == result["size"]


def test_package_timestamp_does_not_overwrite(tmp_path):
    """连续两次打包 = 两个 zip（时间戳秒级，不同名不覆盖）。"""
    out = tmp_path / "out"
    out.mkdir()
    (out / "main.c").write_text("int main(void){}", encoding="utf-8")
    first = package_project(out)
    second = package_project(out)
    assert first["zip_path"] != second["zip_path"]
    assert Path(first["zip_path"]).is_file()
    assert Path(second["zip_path"]).is_file()


def test_package_missing_dir_400(tmp_path):
    with pytest.raises(DeliveryError, match="输出目录不存在"):
        package_project(tmp_path / "nope")


# ---------------------------------------------------------------------------
# webapp 端点：200 / 400 分级
# ---------------------------------------------------------------------------


def _client(tmp_path: Path) -> TestClient:
    from contest_generator.config import AppConfig

    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(api_key="sk-test"),
    )
    return TestClient(create_app(ctx))


def test_delivery_check_endpoint_200(tmp_path):
    out = _stm32_project(tmp_path)
    (out / "main.c").write_text("int main(void){}", encoding="utf-8")
    data = _client(tmp_path).post(
        "/api/delivery/check", json={"output_dir": str(out)}
    )
    assert data.status_code == 200
    body = data.json()
    assert body["plan_present"] is False
    assert body["ok"] is False


def test_delivery_package_endpoint_200(tmp_path):
    out = _stm32_project(tmp_path)
    (out / "main.c").write_text("int main(void){}", encoding="utf-8")
    data = _client(tmp_path).post(
        "/api/delivery/package", json={"output_dir": str(out)}
    )
    assert data.status_code == 200
    body = data.json()
    assert Path(body["zip_path"]).is_file()
    assert body["files"] == 2  # main.c + user/Project.uvprojx


def test_delivery_open_ide_endpoint_400_missing_dir(tmp_path):
    data = _client(tmp_path).post(
        "/api/delivery/open-ide", json={"output_dir": str(tmp_path / "nope")}
    )
    assert data.status_code == 400
    assert "输出目录不存在" in data.json()["detail"]
