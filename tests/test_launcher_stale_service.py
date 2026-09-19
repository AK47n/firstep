"""启动器「旧进程」判据的 CLI 契约（工单 `update-restart-stale-service/01`）。

背景：更新换的是**盘上的文件**，跑着的进程不会跟着变；旧进程还占着端口时，启动器探测到的
`/api/health` 一切正常（`app` 也对得上），于是判「本应用已在运行」→ 只开一个浏览器标签就退出，
用户永远停在旧版本。

启动器（GBK 批处理）只消费这个 CLI 的 **stdout 恰好一行**：

    stale stale=1 served=<端口上> disk=<盘上>     ← 踢掉它重起
    fresh served=<端口上> disk=<盘上>             ← 正常复用（既有行为）
    unknown                                       ← 判不了（异常 / 身份不符 / 读不到版本 / 非法 semver）

所以这里钉的是**外部契约**：真 HTTP 桩 + **真子进程**跑 CLI，断言那一行——
而不是去断言内部函数（内部判据的单测在 `tests/test_update_check.py`）。

**这里不跑 `.bat`**：启动器的失败分支会弹**模态**弹窗（`tests/test_launcher_log.py` 开头
记着那次教训），真实启动器的结论由真机演练给（`.scratch/verify-gate-drills/drill-01-upgrade.py`）。
"""

from __future__ import annotations

import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "launcher-stale.py"

from contest_generator import __version__ as ON_DISK  # noqa: E402  —— 盘上版本的真实来源


class _HealthStub:
    """只应答 `/api/health` 的桩服务器（端口由内核分配，避免撞上真在跑的服务）。"""

    def __init__(self, payload: dict | None) -> None:
        self.payload = payload
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 —— BaseHTTPRequestHandler 的接口名
                if outer.payload is None or self.path != "/api/health":
                    self.send_error(404)
                    return
                body = json.dumps(outer.payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:  # 桩的访问日志不该混进 pytest 输出
                return

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = int(self._server.server_address[1])

    def __enter__(self) -> "_HealthStub":
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> bool:
        self._server.shutdown()
        self._server.server_close()
        return False


def _run_cli(port: int) -> tuple[str, int]:
    """真起子进程跑 CLI，返回 (stdout, 退出码)。"""
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),  # 与 start-app.bat 第 19 行同一个口径
        "PYTHONIOENCODING": "utf-8",
    }
    proc = subprocess.run(
        [sys.executable, str(CLI), "--port", str(port)],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    return proc.stdout, proc.returncode


def _free_port() -> int:
    """一个当下没人听的端口（绑定后立刻放掉——判据是「连不上」）。"""
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_cli_reports_stale_for_older_service() -> None:
    """端口上跑着旧版本 → `stale` + 两个版本号都带出来（留痕字段直接可用）。"""
    with _HealthStub({"app": "contest-generator", "version": "1.1.1", "ok": True}) as stub:
        stdout, code = _run_cli(stub.port)
    assert code == 0, f"CLI 退出码 {code}（判据只在 stdout，但退出码应为 0）"
    line = stdout.strip()
    assert line == f"stale stale=1 served=1.1.1 disk={ON_DISK}", line


def test_cli_reports_fresh_for_same_version() -> None:
    """同版本 = 正常复用，不误杀。"""
    with _HealthStub({"app": "contest-generator", "version": ON_DISK, "ok": True}) as stub:
        stdout, _ = _run_cli(stub.port)
    assert stdout.strip() == f"fresh served={ON_DISK} disk={ON_DISK}", stdout


def test_cli_never_calls_a_newer_service_stale() -> None:
    """服务比盘上更新（另一个安装跑在同端口）→ `fresh`，绝不判旧。"""
    with _HealthStub({"app": "contest-generator", "version": "9.9.9"}) as stub:
        stdout, _ = _run_cli(stub.port)
    assert stdout.strip() == f"fresh served=9.9.9 disk={ON_DISK}", stdout


def test_cli_unknown_when_nothing_listens() -> None:
    """端口上没人听 → `unknown`（不是 `stale`：没有服务可踢）。"""
    stdout, code = _run_cli(_free_port())
    assert stdout.strip() == "unknown", stdout
    assert code == 0


def test_cli_unknown_when_port_answers_another_app() -> None:
    """端口上应答的不是本应用 → `unknown`（启动器自己那条身份判据走 `port_busy`）。"""
    with _HealthStub({"app": "some-other-tool", "version": "0.0.1"}) as stub:
        stdout, _ = _run_cli(stub.port)
    assert stdout.strip() == "unknown", stdout


def test_cli_unknown_when_health_has_no_version() -> None:
    """health 里没有 version 字段（更老的服务可能不返回）→ `unknown`，不当成旧进程。"""
    with _HealthStub({"app": "contest-generator", "ok": True}) as stub:
        stdout, _ = _run_cli(stub.port)
    assert stdout.strip() == "unknown", stdout


def test_cli_unknown_for_unparsable_version() -> None:
    """版本号不是合法 semver → `unknown`（判不了就不动人家的服务）。"""
    with _HealthStub({"app": "contest-generator", "version": "nightly"}) as stub:
        stdout, _ = _run_cli(stub.port)
    assert stdout.strip() == "unknown", stdout


def test_cli_prints_exactly_one_line() -> None:
    """契约是「stdout 恰好一行」——批处理用 `for /f` 取词，多一行就会取到脏值。"""
    with _HealthStub({"app": "contest-generator", "version": "1.0.0"}) as stub:
        stdout, _ = _run_cli(stub.port)
    assert len(stdout.strip().splitlines()) == 1, repr(stdout)


# ---------------------------------------------------------------------------
# 启动器静态守卫（真机结论由演练给——这里只钉「接线接对了」）
#
# 为什么不在 pytest 里真跑 `.bat`：启动器的失败分支会弹**模态**弹窗，跑进测试会在用户桌面上
# 留下一排框并把测试挂死（`tests/test_launcher_log.py` 开头有那次教训的完整记录）。
# 所以这里断言的是**结构**，而「这条分支真的能把旧进程换掉」由
# `.scratch/verify-gate-drills/drill-01-upgrade.py` 在真机上给证据。
# ---------------------------------------------------------------------------

BAT = ROOT / "start-app.bat"
#: 启动器里那条判据分支要跳去的落点
STALE_LABEL = ":stale_service"


def _bat_text() -> str:
    """`start-app.bat` 是 GBK 无 BOM（cmd 按 ANSI 解析），测试按 gbk 读。"""
    return BAT.read_bytes().decode("gbk", errors="replace")


def _bat_lines() -> list[str]:
    return _bat_text().splitlines()


def _index_of(lines: list[str], needle: str) -> int:
    for index, line in enumerate(lines):
        if needle in line:
            return index
    raise AssertionError(f"start-app.bat 里找不到：{needle}")


def _cli_call_index(lines: list[str]) -> int:
    """真正**调用**那个 CLI 的那一行。

    脚本路径在文件头上 `set LAUNCHER_STALE_PY=…` 之后以变量形式使用，所以锚点认变量名 +
    `--port`（`set LAUNCHER_STALE_PY=…` 那行没有 `--port`，自然不会误命中）。
    """
    for index, line in enumerate(lines):
        if "--port" in line and "LAUNCHER_STALE_PY" in line:
            return index
    raise AssertionError("start-app.bat 没有调用 tools/launcher-stale.py")


def _label_index(lines: list[str], label: str) -> int:
    """标签行的位置（`goto :x` 里也含 `:x`，所以必须整行相等才算）。"""
    for index, line in enumerate(lines):
        if line.strip() == label:
            return index
    raise AssertionError(f"start-app.bat 里找不到标签：{label}")


def test_bat_asks_the_cli_instead_of_comparing_versions_itself() -> None:
    """判据**不在批处理里手写**：必须有 `for /f "tokens=1,*"` 调那个 CLI 去问。

    手写比较的两种写法都错：字符串比 `1.10.0` < `1.9.0`；而批处理的 `if` 只会比整数。
    """
    lines = _bat_lines()
    index = _cli_call_index(lines)
    assert "tokens=1,*" in lines[index], f"调 CLI 的那行没有取首词：{lines[index]!r}"
    assert "2^>nul" in lines[index], "调 CLI 时要吞掉 stderr（判据只有 stdout 一行）"
    assert "usebackq" in lines[index], (
        "反引号前必须 usebackq：不加它时反引号不是「执行命令」而是**文件名**，"
        "循环一次都不跑、判据静默失效（真机演练第一次就栽在这里）")
    # 反向 ①：启动器不许自己去 health 里刨版本号
    assert "get('version'" not in _bat_text(), "从 health 里刨版本号是 CLI 的活，不该出现在启动器里"
    # 反向 ②：启动器不许对版本字段做数值比较（端口那个 gtr 65535 不在此列）
    for line in lines:
        stripped = line.strip().lower()
        if stripped.startswith(("rem ", "::")):
            continue
        if {"gtr", "lss", "geq", "leq"} & set(stripped.split()):
            marks = ("version", "disk=", "served=", "stale")
            assert not any(mark in stripped for mark in marks), (
                f"启动器里出现了手写的版本比较：{line!r}")


def test_bat_only_takes_the_kill_path_on_the_stale_token() -> None:
    """只有 CLI 说 `stale` 才去踢进程；空 / `unknown` / 其它一律走原来的复用路径。"""
    lines = _bat_lines()
    index = _cli_call_index(lines)
    tail = "\n".join(lines[index:index + 8])
    assert f'if /i "%FIRSTEP_STALE%"=="stale" goto {STALE_LABEL}' in tail, (
        f"CLI 之后没有「token == stale 才跳」的判据：\n{tail}")
    assert "goto :already_running" in tail, "非 stale 的兜底必须回到原来的 already_running 分支"
    # 取词的两个变量都要先清空：留痕字段是 key=value 形态，空值会让那一行整行写不出去
    head = "\n".join(lines[max(0, index - 6):index])
    assert "set FIRSTEP_STALE=" in head and "set FIRSTEP_STALE_NOTE=" in head, (
        f"取词变量没有先清空（上一轮的值会渗进来）：\n{head}")


def test_bat_kills_within_our_port_then_reuses_start_service() -> None:
    """踢进程的三条纪律：**只在本应用身份分支里**、作用域是本端口、踢完走原本的起服务路径。"""
    lines = _bat_lines()
    kill_index = _label_index(lines, STALE_LABEL)
    block = "\n".join(lines[kill_index:kill_index + 8])
    assert "taskkill" in block, f"落点里没有杀进程：\n{block}"
    assert "%FIRSTEP_LAUNCHER_PORT%" in block, "杀进程的作用域必须是本端口（不是写死的 8000）"
    assert _bat_text().count("taskkill") == 1, (
        "杀进程只许出现在这一处（别的地方杀服务会绕过身份判据）")
    assert "ping.exe" in block, "踢完要等一拍再起（刚被杀的进程要放开端口）"
    # 踢完直接落进原本的 :start_service（不另造一条起服务的路）
    start_index = _label_index(lines, ":start_service")
    assert kill_index < start_index, "落点必须在 :start_service 之前（否则还得 goto 回去）"
    assert start_index - kill_index <= 8, (
        f"{STALE_LABEL} 与 :start_service 隔了 {start_index - kill_index} 行——落点应紧邻")


def test_bat_still_gates_the_kill_on_identity_and_keeps_reason_codes() -> None:
    """踢进程那条路只在「端口上确实是我们自己的应用」之后才可能走到，且不新增 reason 码。"""
    lines = _bat_lines()
    identity = _index_of(lines, 'if /i not "%FIRSTEP_HEALTH_APP%"=="contest-generator"')
    cli_call = _cli_call_index(lines)
    kill_label = _label_index(lines, STALE_LABEL)
    assert identity < cli_call < kill_label, (
        "顺序必须是：先判身份（不是本应用 → port_busy）→ 再问版本 → 才可能踢")
    text = _bat_text()
    assert "-Reason stale" not in text and "-Reason launcher_stale" not in text, (
        "不许为这条分支新增 reason 码：留痕记在 started/already_running 那行的附加字段上")


def test_bat_logs_the_stale_verdict_as_extra_fields() -> None:
    """旧进程被踢这件事必须留下机器可读痕迹（否则事后分不清「踢了」还是「碰巧没旧进程」）。"""
    lines = _bat_lines()
    for needle, label in (("-Reason started", "started"),
                          ("-Reason already_running", "already_running")):
        index = _index_of(lines, needle)
        assert "%FIRSTEP_STALE_NOTE%" in lines[index], (
            f"{label} 那行没带上 CLI 给的字段：{lines[index]!r}")


# ---------------------------------------------------------------------------
# 启动器行为守卫：真跑 cmd，但**每个分支都落到 echo**
#
# 为什么非要它（用一次真机失败换来的）：静态守卫挡不住「反引号前少了 usebackq」——那一行
# 字面上完全正常（有 tokens、有 2^>nul、有 stale 判据），而 cmd 会把反引号里的东西当成
# **文件名**：循环一次都不跑、判据静默失效、启动器照旧走 already_running。第一次重发
# v1.2.1 后跑真机演练就是这么红的（沙箱盘上 1.2.1、服务仍 1.1.1）。
#
# 所以这里把 `start-app.bat` 从 `chcp` 起、到「问完 CLI 的那次分支」为止**整段原样抽出**，
# 再把每个 goto 目标换成 `echo + exit`：**弹窗 / 杀进程 / 起服务三条路都不可能执行**，
# 于是它可以安全地进 pytest——`tests/test_launcher_log.py` 开头那条「不跑会弹框的分支」的
# 硬约束仍然成立。
# ---------------------------------------------------------------------------

PROBE_LABELS = (
    "updating", "update_left", "no_python", "old_python", "no_deps",
    "already_running", "stale_service", "port_busy", "start_service", "timeout",
)


def _probe_bat_bytes(bat_bytes: bytes) -> bytes:
    """抽出「头部设置 + 端口探测 + 身份判定 + 问 CLI + 分支」这一段，接上纯 echo 的标签尾巴。"""
    lines = bat_bytes.decode("gbk").split("\r\n")

    def find(pred) -> int:
        for index, line in enumerate(lines):
            if pred(line):
                return index
        raise AssertionError("start-app.bat 的结构变了：探针锚点找不到")

    start = find(lambda s: s.startswith("chcp 936"))
    end = find(lambda s: s.strip() == "goto :already_running")
    tail: list[str] = [""]
    for label in PROBE_LABELS:
        tail.append(f":{label}")
        if label in ("already_running", "stale_service"):
            tail.append(f'echo RESULT={label} GOT=[%FIRSTEP_STALE%] '
                        f'NOTE=[%FIRSTEP_STALE_NOTE%]')
        else:
            tail.append(f"echo RESULT={label}")
        tail.append("exit /b 0")
    return "\r\n".join(lines[start:end + 1] + tail).encode("gbk")


def _stage_launcher_root(tmp_path: Path) -> tuple[Path, Path]:
    """一次性工具根：真 `start-app.bat` + 真 CLI + 真 `src`（launcher 只需要这几件）。"""
    root = tmp_path / "tool"
    (root / "tools").mkdir(parents=True)
    (root / "start-app.bat").write_bytes(BAT.read_bytes())
    shutil.copy2(ROOT / "tools" / "launcher-stale.py", root / "tools" / "launcher-stale.py")
    shutil.copytree(ROOT / "src", root / "src")
    home = tmp_path / "home"
    (home / ".contest_generator").mkdir(parents=True)
    return root, home


def _run_probe(root: Path, home: Path, port: int) -> str:
    probe = root / "_probe-launcher.bat"
    probe.write_bytes(_probe_bat_bytes((root / "start-app.bat").read_bytes()))
    env = {**os.environ, "USERPROFILE": str(home), "HOME": str(home),
           "FIRSTEP_LAUNCHER_PORT": str(port), "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(["cmd", "/c", str(probe)], cwd=str(root), env=env,
                              capture_output=True, text=True, encoding="gbk",
                              errors="replace", timeout=300)
    finally:
        probe.unlink(missing_ok=True)
    return proc.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="启动器是 Windows 批处理")
@pytest.mark.parametrize(
    ("served", "expected"),
    [("1.0.0", "stale"), (ON_DISK, "already_running"), ("9.9.9", "already_running")],
)
def test_launcher_decision_really_fires(tmp_path, served, expected, ):
    """真跑一遍启动器的判据段：旧版本 → 走 stale；同版本 / 更新版本 → 照旧复用。"""
    root, home = _stage_launcher_root(tmp_path)
    with _HealthStub({"app": "contest-generator", "version": served, "ok": True}) as stub:
        stdout = _run_probe(root, home, stub.port)
    if "RESULT=no_deps" in stdout:
        pytest.skip("本机缺启动器依赖自检要的运行依赖（fastapi/uvicorn/pypdf/PIL/fitz）")
    assert f"RESULT={expected}" in stdout, stdout[-2000:]
    if expected == "stale":
        assert f"NOTE=[stale=1 served={served} disk={ON_DISK}]" in stdout, stdout[-2000:]


@pytest.mark.skipif(sys.platform != "win32", reason="启动器是 Windows 批处理")
def test_launcher_decision_leaves_the_normal_path_alone(tmp_path) -> None:
    """端口上没人听 → 还是走原本的起服务路径（这条修复没有把正常路走歪）。"""
    root, home = _stage_launcher_root(tmp_path)
    stdout = _run_probe(root, home, _free_port())
    if "RESULT=no_deps" in stdout:
        pytest.skip("本机缺启动器依赖自检要的运行依赖（fastapi/uvicorn/pypdf/PIL/fitz）")
    assert "RESULT=start_service" in stdout, stdout[-2000:]
