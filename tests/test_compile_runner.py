"""自动编译执行层域模块测试（工单 autocompile-loop/01 验收项）。

覆盖：UV4/gmake 路径探测（常见路径 + config 覆盖 + PATH 兜底）、子进程
编译（正常 / 报错 / 超时 / 输出采集）、按平台定位工程文件并全量重建（stm32
UV4 `-j0 -r -b`、mspm0 gmake `-C Debug -f makefile -B`）、工具链缺失 /
工程结构异常 → CompileRunnerError（登记 errors.py → 400 中文）、退出码 →
是否通过映射。假工具链 = 本机可执行的 .bat（Windows 子进程可直接执行，
无需 shell=True——已验证），按 UV4 契约解析 `-o <log>` 参数写日志文件。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from contest_generator.compile_runner import (
    BuildLog,
    CompileRunnerError,
    compile_passed,
    collect_build_log,
    find_make,
    find_uv4,
    run_compile,
)
from contest_generator.errors import _ERROR_TABLE, error_entry
from contest_generator.fix_errors import CompileError as FixParseError
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32

_UV4_LOG_HEADER = "Build started: Project: fake\n"
_UV4_ERROR_LINE = r"..\main.c(10): error #20: identifier \"x\" is undefined"


def _write_bat(path: Path, body: str) -> Path:
    """写假工具链 .bat：Windows 下 subprocess 可直接执行（无需 shell=True）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("@echo off\r\n" + body + "\r\n", encoding="utf-8")
    return path


def _uv4_bat(dir_path: Path, exit_code: int, log_lines: tuple[str, ...]) -> Path:
    """假 UV4：解析 `-o <log>` 参数，把构建日志写进该文件，按退出码退出。

    与真实 UV4 的差异只在不真编译：日志内容由用例指定（写 -o 文件是
    collect_build_log 采集路径的契约点，必须真实演练）。
    """
    return _write_bat(
        dir_path / "fake_uv4.bat",
        "@echo off\r\n"
        "set LOG=\r\n"
        ":parse\r\n"
        'if "%~1"=="" goto run\r\n'
        'if "%~1"=="-o" set LOG=%~2\r\n'
        "shift\r\n"
        "goto parse\r\n"
        ":run\r\n"
        + "".join(f'echo {line.rstrip(chr(10))} > "%LOG%"\r\n'
                  if i == 0 else f'echo {line.rstrip(chr(10))} >> "%LOG%"\r\n'
                  for i, line in enumerate(log_lines))
        + f"exit /b {exit_code}\r\n",
    )


def _make_project(tmp_path: Path, platform: str) -> Path:
    """生成结果目录样貌：stm32 带 user/Project.uvprojx；mspm0 带 Debug/makefile。"""
    out = tmp_path / "project"
    if platform == PLATFORM_STM32:
        (out / "user").mkdir(parents=True)
        (out / "user" / "Project.uvprojx").write_text("<Project/>", encoding="utf-8")
    else:
        (out / "Debug").mkdir(parents=True)
        (out / "Debug" / "makefile").write_text("all:\n", encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# 路径探测：config 覆盖 > 常见路径 > PATH（决策记录 6）
# ---------------------------------------------------------------------------


def test_find_uv4_override_points_to_existing_file(tmp_path):
    fake = _write_bat(tmp_path / "UV4.exe", "exit /b 0")
    assert find_uv4(str(fake)) == fake


def test_find_uv4_override_missing_file_returns_none(tmp_path):
    assert find_uv4(str(tmp_path / "gone" / "UV4.exe")) is None


def test_find_uv4_empty_override_tries_common_paths(monkeypatch, tmp_path):
    from contest_generator import compile_runner

    fake = _write_bat(tmp_path / "UV4.exe", "exit /b 0")
    monkeypatch.setattr(compile_runner, "_UV4_CANDIDATES", (str(fake),))
    assert find_uv4("") == fake


def test_find_uv4_path_lookup_as_last_resort(monkeypatch, tmp_path):
    fake = tmp_path / "uv4.exe"
    monkeypatch.setattr("contest_generator.compile_runner._UV4_CANDIDATES", ())
    monkeypatch.setattr("contest_generator.compile_runner.shutil.which",
                        lambda name: str(fake) if "uv4" in name.lower() else None)
    assert find_uv4("") == fake


def test_find_uv4_nothing_found_returns_none(monkeypatch):
    monkeypatch.setattr("contest_generator.compile_runner._UV4_CANDIDATES", ())
    monkeypatch.setattr("contest_generator.compile_runner.shutil.which", lambda name: None)
    assert find_uv4("") is None


def test_find_make_override_and_path(monkeypatch, tmp_path):
    fake = _write_bat(tmp_path / "gmake.exe", "exit /b 0")
    assert find_make(str(fake)) == fake
    assert find_make(str(tmp_path / "gone")) is None
    monkeypatch.setattr("contest_generator.compile_runner.shutil.which", lambda name: str(fake))
    assert find_make("") == fake


# ---------------------------------------------------------------------------
# 子进程编译：正常 / 非零退出 / 超时（决策记录 7）
# ---------------------------------------------------------------------------


def test_run_compile_success_captures_stdout(tmp_path):
    run = run_compile([sys.executable, "-c", "print('ok')"], tmp_path)
    assert run.exit_code == 0 and not run.timed_out
    assert "ok" in run.output


def test_run_compile_nonzero_exit_does_not_raise(tmp_path):
    run = run_compile(
        [sys.executable, "-c", "import sys; print('boom', file=sys.stderr); sys.exit(2)"],
        tmp_path,
    )
    assert run.exit_code == 2 and not run.timed_out
    assert "boom" in run.output


def test_run_compile_timeout_reports_partial_output(tmp_path):
    run = run_compile(
        # flush=True：子进程 stdout 块缓冲时超时被杀前输出可能没落盘
        [sys.executable, "-c", "print('started', flush=True); import time; time.sleep(30)"],
        tmp_path,
        timeout=0.5,
    )
    assert run.timed_out and run.exit_code is None
    assert "started" in run.output  # 已采集的部分输出如实保留


def test_run_compile_missing_command_is_loud(tmp_path):
    with pytest.raises(OSError):
        run_compile([str(tmp_path / "no-such-tool.exe")], tmp_path)


# ---------------------------------------------------------------------------
# collect_build_log：按平台定位工程文件并全量重建
# ---------------------------------------------------------------------------


def test_collect_stm32_uv4_full_rebuild_command_and_log(tmp_path):
    out = _make_project(tmp_path, PLATFORM_STM32)
    fake_uv4 = _uv4_bat(tmp_path, 0, (_UV4_LOG_HEADER, "0 Error(s) 0 Warning(s)."))
    build = collect_build_log(PLATFORM_STM32, out, uv4=fake_uv4)
    assert build.platform == PLATFORM_STM32
    assert "user/Project.uvprojx" in build.project_file.replace("\\", "/")
    assert "-r" in build.command and "-j0" in build.command  # 全量重建（决策记录 4）
    assert build.run.exit_code == 0 and not build.run.timed_out
    assert "0 Error(s)" in build.run.output  # -o 日志文件原样采集
    # 日志文件不得留在工程目录内（临时文件用后即删）
    assert not list(out.rglob("*.log"))


def test_collect_stm32_uv4_errors_kept_in_output(tmp_path):
    out = _make_project(tmp_path, PLATFORM_STM32)
    fake_uv4 = _uv4_bat(tmp_path, 2, (_UV4_LOG_HEADER, _UV4_ERROR_LINE, "1 Error(s) 0 Warning(s)."))
    build = collect_build_log(PLATFORM_STM32, out, uv4=fake_uv4)
    assert build.run.exit_code == 2
    assert _UV4_ERROR_LINE in build.run.output  # warnings/errors 引用行原样保留


def test_collect_stm32_timeout_reported_not_silent(tmp_path):
    """超时如实报告（决策记录 7）：慢工具链 → timed_out=True，不挂死不静默。

    .bat 假工具链的 sleep 用 ping -n 4（≈3s）：cmd 被杀后 ping 孙进程仍继承
    stdout 管道，communicate 等管道 EOF 到 ping 自然结束——真实工具链是原生
    EXE 无此问题（TerminateProcess 直接生效），测试只验证超时路径本身。
    """
    out = _make_project(tmp_path, PLATFORM_STM32)
    fake_uv4 = _write_bat(
        tmp_path / "slow_uv4.bat",
        "@echo off\r\nset LOG=\r\n:parse\r\nif \"%~1\"==\"\" goto run\r\n"
        'if "%~1"=="-o" set LOG=%~2\r\nshift\r\ngoto parse\r\n'
        ":run\r\nping -n 4 127.0.0.1 > nul\r\nexit /b 0\r\n",
    )
    build = collect_build_log(PLATFORM_STM32, out, uv4=fake_uv4, timeout=0.5)
    assert build.run.timed_out and build.run.exit_code is None


def test_collect_stm32_missing_uvprojx_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    fake_uv4 = _uv4_bat(tmp_path, 0, ("0 Error(s)",))
    with pytest.raises(CompileRunnerError, match=".uvprojx"):
        collect_build_log(PLATFORM_STM32, empty, uv4=fake_uv4)


def test_collect_stm32_missing_toolchain_raises(tmp_path):
    out = _make_project(tmp_path, PLATFORM_STM32)
    with pytest.raises(CompileRunnerError, match="UV4"):
        collect_build_log(PLATFORM_STM32, out, uv4=None)


def test_collect_mspm0_gmake_full_rebuild(tmp_path):
    out = _make_project(tmp_path, PLATFORM_MSPM0)
    fake_make = _write_bat(
        tmp_path / "gmake.bat",
        "echo gmake: Entering directory Debug\r\n"
        "echo code/main.c:45: warning: unused variable\r\n"
        "echo Finished building target: mspm0_project.out\r\n"
        "exit /b 0\r\n",
    )
    build = collect_build_log(PLATFORM_MSPM0, out, make=fake_make)
    assert "Debug/makefile" in build.project_file.replace("\\", "/")
    # gmake -C Debug（-C 后一个参数是 Debug 目录绝对路径）
    assert build.command[build.command.index("-C") + 1].replace("\\", "/").endswith("Debug")
    assert "-B" in build.command  # 全量重建（决策记录 4）
    assert build.run.exit_code == 0
    assert "mspm0_project.out" in build.run.output  # stdout 原样采集


def test_collect_mspm0_gmake_errors_and_missing_makefile(tmp_path):
    out = _make_project(tmp_path, PLATFORM_MSPM0)
    fake_make = _write_bat(
        tmp_path / "gmake.bat",
        "echo code/main.c:45: error: use of undeclared identifier 'y'\r\nexit /b 2\r\n",
    )
    build = collect_build_log(PLATFORM_MSPM0, out, make=fake_make)
    assert build.run.exit_code == 2 and "undeclared" in build.run.output

    bare = tmp_path / "bare"
    bare.mkdir()
    with pytest.raises(CompileRunnerError, match="makefile"):
        collect_build_log(PLATFORM_MSPM0, bare, make=fake_make)


def test_collect_mspm0_missing_toolchain_raises(tmp_path):
    out = _make_project(tmp_path, PLATFORM_MSPM0)
    with pytest.raises(CompileRunnerError, match="gmake"):
        collect_build_log(PLATFORM_MSPM0, out, make=None)


def test_collect_unknown_platform_raises(tmp_path):
    with pytest.raises(CompileRunnerError, match="平台"):
        collect_build_log("esp32", tmp_path)


def test_collect_missing_output_dir_raises(tmp_path):
    with pytest.raises(CompileRunnerError, match="输出目录"):
        collect_build_log(PLATFORM_STM32, tmp_path / "gone", uv4=Path("x"))


# ---------------------------------------------------------------------------
# 退出码 → 是否通过（前端循环"无错可出活"判定单源）
# ---------------------------------------------------------------------------


def test_compile_passed_mapping():
    # UV4：0 = 无错无警、1 = 有警告无错 → 都算通过（warnings 如实展示）
    assert compile_passed(PLATFORM_STM32, 0) is True
    assert compile_passed(PLATFORM_STM32, 1) is True
    assert compile_passed(PLATFORM_STM32, 2) is False
    # gmake：warnings 不影响退出码，0 = 通过
    assert compile_passed(PLATFORM_MSPM0, 0) is True
    assert compile_passed(PLATFORM_MSPM0, 1) is False
    # 超时（None）= 终态，不算通过
    assert compile_passed(PLATFORM_STM32, None) is False


# ---------------------------------------------------------------------------
# 错误登记：400 中文 + 与 fix_errors.CompileError 的类名冲突检查
# ---------------------------------------------------------------------------


def test_compile_runner_error_registered_400_chinese():
    status, message = error_entry(CompileRunnerError("未检测到 Keil UV4 工具链"))
    assert status == 400
    assert "工具链" in message


def test_no_class_name_clash_with_fix_errors_compile_error():
    """类名冲突检查（验收项）：errors.py 登记的是 compile_runner 的
    CompileRunnerError；fix_errors.CompileError 是解析条目 dataclass（非异常
    类，不参与错误映射）——同名不同物不得混入 error_to_http 表。"""
    registered = [
        t for entry in _ERROR_TABLE for t in entry.exc_types
        if t is CompileRunnerError
    ]
    assert registered, "CompileRunnerError 未登记 errors.py"
    # fix_errors.CompileError 是 dataclass 而非异常：不可能是表内类型
    assert not issubclass(type(FixParseError(path="", line=0, message="")), Exception)
