"""烧录执行层（工单 flash-deploy/01）：定位 / 探测 / 命令构建 / 执行 / 端点。

纯确定性单元：固件与 ccxml 定位（最新 / 备份目录跳过 / 缺失）、工具探测
（覆盖优先 / 自动扫描 / 缺失 None）、三 builder 精确参数、子进程执行
（成功 / 失败 / 超时）；webapp 集成：/api/flash 平台反推（.uvprojx /
.cproject）、产物缺失 400、工具缺失 400、成功回路（config 覆盖注入假工具）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contest_generator.config import AppConfig
from contest_generator.flash import (
    FlashError,
    FlashTool,
    build_flash_command,
    find_ccxml,
    find_firmware,
    flash_project,
    resolve_flash_tool,
    run_flash,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32
from contest_generator.webapp import AppContext, create_app


# ---------------------------------------------------------------------------
# 测试素材构造
# ---------------------------------------------------------------------------


def _stm32_project(tmp_path: Path) -> Path:
    out = tmp_path / "stm32"
    (out / "user" / "Objects").mkdir(parents=True)
    (out / "user" / "Project.uvprojx").write_text("<Project/>", encoding="utf-8")
    return out


def _mspm0_project(tmp_path: Path) -> Path:
    out = tmp_path / "mspm0"
    (out / "Debug").mkdir(parents=True)
    (out / "targetConfigs").mkdir(parents=True)
    (out / ".cproject").write_text("<cproject/>", encoding="utf-8")
    (out / "targetConfigs" / "MSPM0G3507.ccxml").write_text(
        "<ccxml/>", encoding="utf-8"
    )
    return out


def _fake_tool_bat(tmp_path: Path, exit_code: int = 0, lines=("flash ok",)) -> Path:
    """假烧录器 .bat：忽略参数、打印指定行、按指定退出码退出（Windows 下
    subprocess 可直接执行，与假 UV4 同构）。"""
    bat = tmp_path / "fake_flash.bat"
    bat.write_text(
        "@echo off\r\n"
        + "".join(f"echo {line}\r\n" for line in lines)
        + f"exit /b {exit_code}\r\n",
        encoding="utf-8",
    )
    return bat


def _touch(path: Path, mtime: float) -> None:
    path.write_bytes(b"bin")
    os.utime(path, (mtime, mtime))


# ---------------------------------------------------------------------------
# find_firmware / find_ccxml：定位
# ---------------------------------------------------------------------------


def test_find_firmware_stm32_hex_latest_wins(tmp_path):
    out = _stm32_project(tmp_path)
    _touch(out / "user" / "Objects" / "old.hex", 1000.0)
    _touch(out / "user" / "Objects" / "new.hex", 2000.0)
    assert find_firmware(out, PLATFORM_STM32) == out / "user" / "Objects" / "new.hex"


def test_find_firmware_mspm0_out_in_debug(tmp_path):
    out = _mspm0_project(tmp_path)
    _touch(out / "Debug" / "mspm0_project.out", 1000.0)
    assert find_firmware(out, PLATFORM_MSPM0) == out / "Debug" / "mspm0_project.out"


def test_find_firmware_skips_backup_dirs(tmp_path):
    out = _stm32_project(tmp_path)
    (out / "user" / "Objects" / "revise-backups").mkdir(parents=True)
    _touch(out / "user" / "Objects" / "revise-backups" / "old.hex", 9999.0)
    _touch(out / "user" / "Objects" / "current.hex", 1000.0)
    assert find_firmware(out, PLATFORM_STM32) == out / "user" / "Objects" / "current.hex"


def test_find_firmware_missing_returns_none(tmp_path):
    assert find_firmware(_stm32_project(tmp_path), PLATFORM_STM32) is None


def test_find_firmware_unknown_platform_raises(tmp_path):
    out = _stm32_project(tmp_path)
    with pytest.raises(FlashError, match="未知平台"):
        find_firmware(out, "avr")


def test_find_ccxml_latest_and_missing(tmp_path):
    out = _mspm0_project(tmp_path)
    os.utime(out / "targetConfigs" / "MSPM0G3507.ccxml", (500.0, 500.0))
    _touch(out / "targetConfigs" / "old.ccxml", 1000.0)
    _touch(out / "targetConfigs" / "new.ccxml", 2000.0)
    assert find_ccxml(out) == out / "targetConfigs" / "new.ccxml"
    assert find_ccxml(_stm32_project(tmp_path)) is None


# ---------------------------------------------------------------------------
# resolve_flash_tool：探测
# ---------------------------------------------------------------------------


def test_resolve_mspm0_dslite_override_wins(monkeypatch, tmp_path):
    fake = tmp_path / "DSLite.exe"
    fake.write_bytes(b"")
    tool = resolve_flash_tool(PLATFORM_MSPM0, dslite_path=str(fake))
    assert tool is not None and tool.kind == "dslite" and tool.exe == fake


def test_resolve_mspm0_dslite_scan_finds_newest(monkeypatch, tmp_path):
    for name, mtime in (("ccs2050", 1000.0), ("ccs2051", 2000.0)):
        dslite = (
            tmp_path / name / "ccs" / "ccs_base" / "DebugServer" / "bin" / "DSLite.exe"
        )
        dslite.parent.mkdir(parents=True)
        _touch(dslite, mtime)
    monkeypatch.setattr("contest_generator.flash._CCS_SCAN_ROOT", str(tmp_path))
    tool = resolve_flash_tool(PLATFORM_MSPM0)
    assert tool is not None and tool.kind == "dslite"
    assert "ccs2051" in str(tool.exe)  # 目录名排序最大 = 新版本


def test_resolve_mspm0_invalid_override_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr("contest_generator.flash._CCS_SCAN_ROOT", str(tmp_path))
    assert resolve_flash_tool(PLATFORM_MSPM0, dslite_path=str(tmp_path / "nope.exe")) is None


def test_resolve_stm32_openocd_preferred_over_stflash(monkeypatch, tmp_path):
    openocd = tmp_path / "openocd.exe"
    openocd.write_bytes(b"")
    monkeypatch.setattr(
        "contest_generator.flash.shutil.which",
        lambda name: str(openocd) if name == "openocd" else None,
    )
    tool = resolve_flash_tool(PLATFORM_STM32)
    assert tool is not None and tool.kind == "openocd"


def test_resolve_stm32_stflash_fallback(monkeypatch, tmp_path):
    stflash = tmp_path / "st-flash.exe"
    stflash.write_bytes(b"")
    monkeypatch.setattr(
        "contest_generator.flash.shutil.which",
        lambda name: str(stflash) if name == "st-flash" else None,
    )
    tool = resolve_flash_tool(PLATFORM_STM32)
    assert tool is not None and tool.kind == "stflash"


def test_resolve_stm32_both_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr("contest_generator.flash.shutil.which", lambda name: None)
    assert resolve_flash_tool(PLATFORM_STM32) is None


def test_resolve_unknown_platform_raises(monkeypatch):
    with pytest.raises(FlashError, match="未知平台"):
        resolve_flash_tool("avr")


# ---------------------------------------------------------------------------
# build_flash_command：三 builder 精确参数
# ---------------------------------------------------------------------------


def test_build_dslite_command_exact(tmp_path):
    out = _mspm0_project(tmp_path)
    ccxml = find_ccxml(out)
    firmware = out / "Debug" / "mspm0_project.out"
    tool = FlashTool(kind="dslite", exe=Path("DSLite.exe"), display="x")
    assert build_flash_command(tool, firmware, out) == [
        "DSLite.exe",
        "flash",
        f"--config={ccxml}",
        str(firmware),
        "-u",
    ]


def test_build_dslite_without_ccxml_raises(tmp_path):
    out = _stm32_project(tmp_path)  # 无 ccxml
    tool = FlashTool(kind="dslite", exe=Path("DSLite.exe"), display="x")
    with pytest.raises(FlashError, match="ccxml"):
        build_flash_command(tool, out / "a.out", out)


def test_build_openocd_command_exact(tmp_path):
    firmware = Path("C:/proj/user/Objects/proj.hex")
    tool = FlashTool(kind="openocd", exe=Path("openocd.exe"), display="x")
    assert build_flash_command(tool, firmware, tmp_path) == [
        "openocd.exe",
        "-f",
        "interface/stlink.cfg",
        "-f",
        "target/stm32f1x.cfg",
        "-c",
        f"program {firmware} verify reset exit",
    ]


def test_build_stflash_command_exact(tmp_path):
    firmware = Path("C:/proj/user/Objects/proj.hex")
    tool = FlashTool(kind="stflash", exe=Path("st-flash.exe"), display="x")
    assert build_flash_command(tool, firmware, tmp_path) == [
        "st-flash.exe",
        "write",
        str(firmware),
        "0x08000000",
    ]


def test_build_unknown_kind_raises(tmp_path):
    tool = FlashTool(kind="jlink", exe=Path("x.exe"), display="x")
    with pytest.raises(FlashError, match="未知烧录工具类型"):
        build_flash_command(tool, tmp_path / "a.hex", tmp_path)


# ---------------------------------------------------------------------------
# run_flash：子进程执行（成功 / 非零 / 超时 / 缺命令大声）
# ---------------------------------------------------------------------------


def test_run_flash_success(tmp_path):
    run = run_flash([sys.executable, "-c", "print('flashed ok')"], cwd=tmp_path)
    assert run.exit_code == 0 and not run.timed_out
    assert "flashed ok" in run.output


def test_run_flash_nonzero_does_not_raise(tmp_path):
    run = run_flash(
        [sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(3)"],
        cwd=tmp_path,
    )
    assert run.exit_code == 3 and not run.timed_out
    assert "boom" in run.output


def test_run_flash_timeout_reports_partial_output(tmp_path):
    run = run_flash(
        [
            sys.executable,
            "-c",
            "print('started', flush=True); import time; time.sleep(30)",
        ],
        cwd=tmp_path,
        timeout=0.5,
    )
    assert run.timed_out and run.exit_code is None
    assert "started" in run.output


def test_run_flash_missing_command_is_loud(tmp_path):
    with pytest.raises(OSError):
        run_flash([str(tmp_path / "no-such-tool.exe")], cwd=tmp_path)


# ---------------------------------------------------------------------------
# flash_project：编排（成功 / 失败 / 缺失 / 超时路径）
# ---------------------------------------------------------------------------


def test_flash_project_stm32_success(tmp_path):
    out = _stm32_project(tmp_path)
    _touch(out / "user" / "Objects" / "proj.hex", 1000.0)
    tool = _fake_tool_bat(tmp_path, 0, ("flashed ok",))
    result = flash_project(PLATFORM_STM32, out, openocd_path=str(tool))
    assert result["ok"] is True
    assert result["tool"]["kind"] == "openocd"
    assert result["firmware"].endswith("proj.hex")
    assert "stlink.cfg" in " ".join(result["command"])
    assert "program" in " ".join(result["command"])
    assert "烧录成功" in result["message"]
    assert "flashed ok" in result["output"]
    assert result["timed_out"] is False


def test_flash_project_mspm0_dslite_success(tmp_path):
    out = _mspm0_project(tmp_path)
    _touch(out / "Debug" / "mspm0_project.out", 1000.0)
    tool = _fake_tool_bat(tmp_path, 0, ("flashed ok",))
    result = flash_project(PLATFORM_MSPM0, out, dslite_path=str(tool))
    assert result["ok"] is True
    assert result["tool"]["kind"] == "dslite"
    assert "--config=" in " ".join(result["command"])


def test_flash_project_failure_returns_ok_false_with_tail(tmp_path):
    out = _stm32_project(tmp_path)
    _touch(out / "user" / "Objects" / "proj.hex", 1000.0)
    tool = _fake_tool_bat(tmp_path, 2, ("error: probe not found",))
    result = flash_project(PLATFORM_STM32, out, openocd_path=str(tool))
    assert result["ok"] is False
    assert result["exit_code"] == 2
    assert "失败" in result["message"]
    assert "error: probe not found" in result["output"]
    assert result["output_tail_lines"] == 40


def test_flash_project_missing_firmware_raises(tmp_path):
    out = _stm32_project(tmp_path)
    tool = _fake_tool_bat(tmp_path)
    with pytest.raises(FlashError, match="未找到固件产物"):
        flash_project(PLATFORM_STM32, out, openocd_path=str(tool))


def test_flash_project_missing_tool_raises_with_guide(tmp_path, monkeypatch):
    out = _stm32_project(tmp_path)
    _touch(out / "user" / "Objects" / "proj.hex", 1000.0)
    monkeypatch.setattr("contest_generator.flash.shutil.which", lambda name: None)
    with pytest.raises(FlashError, match="STM32 烧录工具"):
        flash_project(PLATFORM_STM32, out)


def test_flash_project_unknown_platform_raises(tmp_path):
    with pytest.raises(FlashError, match="未知平台"):
        flash_project("avr", tmp_path)


# ---------------------------------------------------------------------------
# webapp：POST /api/flash（平台反推 + 400 分级 + 成功回路）
# ---------------------------------------------------------------------------


def _flash_client(tmp_path, **config_kwargs):
    ctx = AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(api_key="sk-test", **config_kwargs),
    )
    return TestClient(create_app(ctx))


def test_flash_endpoint_infers_platform_stm32_and_succeeds(tmp_path):
    out = _stm32_project(tmp_path)
    _touch(out / "user" / "Objects" / "proj.hex", 1000.0)
    tool = _fake_tool_bat(tmp_path, 0, ("flashed ok",))
    client = _flash_client(tmp_path, openocd_path=str(tool))
    resp = client.post("/api/flash", json={"output_dir": str(out)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True and data["tool"]["kind"] == "openocd"


def test_flash_endpoint_infers_platform_mspm0_and_succeeds(tmp_path):
    out = _mspm0_project(tmp_path)
    _touch(out / "Debug" / "mspm0_project.out", 1000.0)
    tool = _fake_tool_bat(tmp_path, 0, ("flashed ok",))
    client = _flash_client(tmp_path, dslite_path=str(tool))
    resp = client.post("/api/flash", json={"output_dir": str(out)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True and data["tool"]["kind"] == "dslite"


def test_flash_endpoint_missing_firmware_400_chinese(tmp_path):
    out = _stm32_project(tmp_path)
    tool = _fake_tool_bat(tmp_path)
    client = _flash_client(tmp_path, openocd_path=str(tool))
    resp = client.post("/api/flash", json={"output_dir": str(out)})
    assert resp.status_code == 400
    assert "未找到固件产物" in resp.json()["detail"]


def test_flash_endpoint_missing_tool_400_chinese(tmp_path, monkeypatch):
    out = _stm32_project(tmp_path)
    _touch(out / "user" / "Objects" / "proj.hex", 1000.0)
    monkeypatch.setattr("contest_generator.flash.shutil.which", lambda name: None)
    client = _flash_client(tmp_path)
    resp = client.post("/api/flash", json={"output_dir": str(out)})
    assert resp.status_code == 400
    assert "未找到 STM32 烧录工具" in resp.json()["detail"]


def test_flash_endpoint_missing_output_dir_400_chinese(tmp_path):
    client = _flash_client(tmp_path)
    resp = client.post("/api/flash", json={"output_dir": str(tmp_path / "gone")})
    assert resp.status_code == 400
    assert "输出目录不存在" in resp.json()["detail"]


def test_flash_endpoint_ambiguous_platform_400_chinese(tmp_path):
    out = tmp_path / "both"
    (out / "user").mkdir(parents=True)
    (out / "user" / "Project.uvprojx").write_text("<Project/>", encoding="utf-8")
    (out / ".cproject").write_text("<cproject/>", encoding="utf-8")
    client = _flash_client(tmp_path)
    resp = client.post("/api/flash", json={"output_dir": str(out)})
    assert resp.status_code == 400
    assert "无法判定平台" in resp.json()["detail"]


def test_flash_settings_roundtrip(tmp_path):
    client = _flash_client(tmp_path)
    resp = client.put(
        "/api/settings",
        json={
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-v4-flash",
            "module_library_dir": str(tmp_path / "lib"),
            "masters_dir": str(tmp_path / "masters"),
            "openocd_path": "C:/tools/openocd.exe",
            "stflash_path": "",
            "dslite_path": "C:/ti/ccs2050/ccs/ccs_base/DebugServer/bin/DSLite.exe",
        },
    )
    assert resp.status_code == 200
    saved = client.get("/api/settings").json()
    assert saved["openocd_path"] == "C:/tools/openocd.exe"
    assert saved["dslite_path"] == "C:/ti/ccs2050/ccs/ccs_base/DebugServer/bin/DSLite.exe"
    assert saved["stflash_path"] == ""
