"""launcher 分支矩阵真机探针（工单 launcher-failure-reason/01 + /02）。

真跑 `cmd /c start-app.bat`（不模拟、不桩掉 launcher 本身），逐态取证：

1. `updating`：更新中锁在场 → 退出码 1 + 日志 reason 一致；
2. `no_python`：PATH 里没有 python → 退出码 1 + reason 一致；
3. `started`：8000 空着 → 真起服务、就绪后 `reason=started`、exit 0；
4. `already_running`：服务已在跑 → `reason=already_running`、exit 0（**不是**失败态）；
5. `port_busy`：同一端口上放一个「身份不符」的占位服务（`/api/health` 返回别的 app 名）
   → `reason=port_busy`、exit 1；
6. `timeout`（**E2 第三态**）：PATH 前置门控垫片，把**服务启动那条命令行**延迟到 20s 轮询
   窗口之外 → `reason=timeout`、exit 1。

端口隔离：3~6 全部跑在 `FIRSTEP_LAUNCHER_PORT=8899` 上（launcher 支持该覆盖，默认 8000），
所以**不碰用户正在用的 8000 会话**、也不需要在跑完复原任何东西。
另外单跑一次真实 8000：只读观察（`already_running`），证明默认端口上的行为与覆盖端口一致。

launcher 侧隔离：把 `start-app.bat` + `tools/launcher-log.ps1` + 一个 `start.cmd` 桩
（拦掉 `start "" "http://…"`，不弹浏览器）拷进临时沙箱目录里跑，`USERPROFILE` 也重定向到临时目录
⇒ 不污染仓库与用户配置目录。

零 LLM 调用、零额度。

用法：`$env:PYTHONIOENCODING='utf-8'; python .scratch/launcher-failure-reason/probe-01-branch-matrix.py`
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / "verify-01-branch-matrix.txt"
LAUNCHER = ROOT / "start-app.bat"
LOG_PS1 = ROOT / "tools" / "launcher-log.ps1"
PORT = 8899          # 探针专用端口（不碰用户的 8000）
REAL_PORT = 8000     # 只读观察用
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SYSTEM_ROOT = os.environ.get("SystemRoot", r"C:\Windows")
SYSTEM_PATH = f"{SYSTEM_ROOT}\\System32;{SYSTEM_ROOT}"
POWERSHELL = Path(SYSTEM_ROOT) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"

# 浏览器抑制单源（成功分支会 `start "" url`——验收期间不许真开浏览器，见该模块头注释）
sys.path.insert(0, str(HERE))
import browser_stub  # noqa: E402

_lines: list[str] = []


def say(text: str = "") -> None:
    print(text, flush=True)
    _lines.append(text)


def frame(expect: str, note: str = "") -> None:
    say("")
    say("-" * 78)
    say(f"判读标记：本段要证明的形态 = {expect}" + (f"（{note}）" if note else ""))
    say("-" * 78)


# ---------------------------------------------------------------- 弹窗清扫（验收纪律）

# start-app.bat 的失败分支会弹**模态**框（WScript.Shell.Popup，不点不返回）。探针跑的是真 launcher，
# 所以框会真的出现——**不能让框留在用户桌面上**：后台线程每 0.4s 扫一遍「标题含 firstep 的窗口」，
# 逮到就只杀那个 pid（绝不用 `taskkill /IM powershell.exe` 这类误伤写法）。
# 判读口径因此是 launcher.log 里的 reason 行（launcher 在弹框之前就写好了），
# 而不是退出码——被强杀的进程退不出码，这一点在落盘里如实记账。
POPUP_TITLES_PS = (
    "Get-Process -ErrorAction SilentlyContinue | "
    "Where-Object { $_.MainWindowTitle -like '*firstep*' } | "
    "ForEach-Object { $_.Id }"
)
_stop_reaper = threading.Event()
_reaped: list[int] = []


def _reaper() -> None:
    while not _stop_reaper.is_set():
        try:
            out = subprocess.run(
                [str(POWERSHELL), "-NoProfile", "-Command", POPUP_TITLES_PS],
                capture_output=True, text=True, errors="replace", timeout=20)
            for line in (out.stdout or "").splitlines():
                pid_text = line.strip()
                if pid_text.isdigit() and int(pid_text) != os.getpid():
                    subprocess.run(["taskkill", "/PID", pid_text, "/F"],
                                   capture_output=True, text=True)
                    _reaped.append(int(pid_text))
        except Exception:
            pass
        _stop_reaper.wait(0.4)


# ---------------------------------------------------------------- 基础工具

def health(port: int = PORT, timeout: float = 3.0) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as resp:
            return json.load(resp)
    except Exception:
        return None


def port_listening(port: int = PORT) -> bool:
    with socket.socket() as s:
        s.settimeout(0.6)
        return s.connect_ex(("127.0.0.1", port)) == 0


def listener_pid(port: int = PORT) -> int | None:
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                         errors="replace").stdout
    for line in out.splitlines():
        if "LISTENING" in line and re.search(rf":{port}\s", line):
            tail = [c for c in line.split() if c]
            if tail and tail[-1].isdigit():
                return int(tail[-1])
    return None


def wait_port_free(port: int = PORT, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not port_listening(port):
            return True
        time.sleep(0.4)
    return not port_listening(port)


def clear_port(port: int = PORT, note: str = "") -> bool:
    """把探针端口上的监听者清干净（含子进程树），返回最终是否空闲。

    为什么必须有：探针自己起的服务、或**上一次手工复现留下的**进程都会占着这个端口；不清干净，
    下一个状态就会拿到 `:already_running`/`:port_busy` 而不是它该有的形态
    （2026-09-12 实测踩到：一次手工复现的残留服务让 `:started` 判成 `port_busy`）。
    """
    for _ in range(5):
        pid = listener_pid(port)
        if not pid:
            break
        say(f"[清理{note}] 端口 {port} 上有监听者 pid={pid} → taskkill /T /F")
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True)
        time.sleep(0.6)
    return wait_port_free(port, timeout=5.0)


def stop(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def temp_dir(tag: str) -> Path:
    p = Path(os.environ.get("TEMP", ".")) / f"lfr-{tag}-{random.randint(100000, 999999)}"
    p.mkdir(parents=True, exist_ok=True)
    return p


START_STUB = "@echo off\r\nexit /b 0\r\n"


def make_sandbox() -> tuple[Path, str]:
    """拷一份 launcher 到临时目录（含 start 桩），返回 (launcher 路径, 盒子 PATH)。"""
    box = temp_dir("sandbox")
    shutil.copy2(LAUNCHER, box / "start-app.bat")
    (box / "tools").mkdir(exist_ok=True)
    shutil.copy2(LOG_PS1, box / "tools" / "launcher-log.ps1")
    (box / "start.cmd").write_text(START_STUB, encoding="ascii")
    return box / "start-app.bat", f"{box};{SYSTEM_PATH}"


def run_launcher(launcher: Path, profile: Path, box_path: str,
                 extra_env: dict[str, str] | None = None, timeout: float = 180.0,
                 note: str = "") -> dict:
    """真跑 `cmd /c <launcher>`（USERPROFILE 重定向到临时目录）。

    stdout/stderr **落文件而不是管道**：launcher 会 spawn 后台服务（`start "" /b`），子进程继承
    管道句柄 ⇒ `communicate()` 要等管道关闭才返回，服务活着时永久阻塞（第一版探针就挂在
    `no_python` 那一步：根因在探针读法，不在 launcher）。超时用 `taskkill /T` 杀整棵进程树。
    `note` 会写进落盘（例如「进程被强杀、判读看 reason 行」）。
    """
    env = {**os.environ, "USERPROFILE": str(profile), "PATH": box_path}
    if extra_env:
        env.update(extra_env)
    # launcher 会把服务 stdout 重定向到 %USERPROFILE%\.contest_generator\webapp.log：
    # 这个目录不存在时 **cmd 的 `>>` 直接失败**（「系统找不到指定的路径」），服务根本不会启动。
    # 真实机器上该目录由应用/安装流程建好，所以验收侧必须自己先建（第一版探针就栽在这里）。
    (profile / ".contest_generator").mkdir(parents=True, exist_ok=True)
    out_file = profile / "launcher-stdout.txt"
    err_file = profile / "launcher-stderr.txt"
    started = time.time()
    with open(out_file, "w", encoding="utf-8", errors="replace") as fo, \
            open(err_file, "w", encoding="utf-8", errors="replace") as fe:
        proc = subprocess.Popen(["cmd", "/c", str(launcher)], cwd=str(launcher.parent), env=env,
                                stdin=subprocess.DEVNULL, stdout=fo, stderr=fe,
                                creationflags=NO_WINDOW)
        try:
            exit_code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, text=True)
            proc.wait(timeout=30)
            exit_code = "timeout-killed"
    elapsed = time.time() - started
    log = profile / ".contest_generator" / "launcher.log"
    log_text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    lines = [ln for ln in log_text.splitlines() if ln.strip()]
    reasons = [m.group(1) for ln in lines for m in [re.search(r"reason=([a-z_]+)", ln)] if m]
    return {
        "exit_code": exit_code,
        "elapsed_s": round(elapsed, 1),
        "reasons": reasons,
        "log_lines": lines,
        "stdout": out_file.read_text(encoding="utf-8", errors="replace").strip(),
        "stderr": err_file.read_text(encoding="utf-8", errors="replace").strip(),
        "note": note,
    }


def report(name: str, expect: str, result: dict, ok: bool) -> bool:
    say(f"[{name}] 期望 {expect}")
    say(f"    退出码={result['exit_code']} 耗时={result['elapsed_s']}s reasons={result['reasons']}"
        + (f"（{result['note']}）" if result.get("note") else ""))
    for ln in result["log_lines"]:
        say(f"    launcher.log: {ln}")
    if result["stdout"]:
        say(f"    stdout: {result['stdout'][:400]}")
    if result["stderr"]:
        say(f"    stderr: {result['stderr'][:400]}")
    say(f"    → {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------- 占位服务与垫片

PLACEHOLDER = r'''
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

APP = sys.argv[1]

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"app": APP, "ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass

HTTPServer(("127.0.0.1", int(sys.argv[2])), H).serve_forever()
'''

# PATH 垫片与「慢 python」替身：**都已不用**（下面两条是走过的死路，留文字记账防重走）
#   * PATH 前置 `python.cmd`：launcher 的批处理在解析到 `.cmd` 形式的 python 时会异常退出；
#   * 只拷 python.exe 单体：本机是可搬运安装，缺 DLL 起不来（STATUS_DLL_NOT_FOUND）。
# 现行做法见本段 `timeout` 状态：真 python 目录整拷 + `sitecustomize.py` 钩子（python_fake.py）。


def start_placeholder(app_name: str, port: int = PORT) -> subprocess.Popen:
    proc = subprocess.Popen([sys.executable, "-c", PLACEHOLDER, app_name, str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=NO_WINDOW)
    deadline = time.time() + 15
    while time.time() < deadline:
        if port_listening(port):
            return proc
        time.sleep(0.3)
    proc.kill()
    raise RuntimeError(f"占位服务未在 {port} 起来")


# ---------------------------------------------------------------- 主流程

def main() -> int:
    say("# launcher 分支矩阵真机探针（工单 launcher-failure-reason/01 + /02）")
    say(f"# 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    say(f"# 仓库：{ROOT}")
    say(f"# launcher：{LAUNCHER}（探针用沙箱副本 + 覆盖端口 {PORT}，默认端口 {REAL_PORT}）")
    say(f"# python：{sys.executable} ({sys.version.split()[0]})")
    say(f"# 起始现场：{PORT} 监听={port_listening()} ｜ {REAL_PORT} 健康={health(REAL_PORT)}")

    launcher, box_path = make_sandbox()
    sandbox_profile = launcher.parent
    say(f"# 沙箱：{sandbox_profile}（含 start.cmd 桩拦浏览器）")

    reaper = threading.Thread(target=_reaper, name="popup-reaper", daemon=True)
    reaper.start()
    say("# 弹窗清扫线程已启动（标题含 firstep 的窗口一出现就按 pid 杀掉，框不留桌面）")

    # 浏览器抑制**先自证再开跑**：成功分支会 `start "" url`，抑制没生效就会在用户桌面上反复开标签
    # （2026-09-12 用户当场叫停的那件事）。自证不过就立刻停手，不拿用户桌面做实验。
    probe_prof = temp_dir("browserselftest")
    selftest = browser_stub.probe_browser_suppression(probe_prof)
    say(f"# 浏览器抑制自证：ProgId={selftest['progid']} 写入替身={selftest.get('wrote_stub')} "
        f"新增浏览器进程={selftest['new_browser_procs']} 已复原={selftest['restored']}")
    if not selftest.get("browser_open_suppressed") or not selftest.get("restored"):
        say("# 自证未通过 → 立即停止（不做会弹浏览器的验收）")
        OUT.write_text("\n".join(_lines) + "\n", encoding="utf-8")
        return 2

    results: dict[str, bool] = {}
    placeholder: subprocess.Popen | None = None
    started_here = False

    try:
        # ---------------- 1. updating ----------------
        frame("updating", "更新中锁在场")
        prof = temp_dir("updating")
        upd = prof / ".contest_generator" / "updates"
        upd.mkdir(parents=True, exist_ok=True)
        (upd / "updating.lock").write_text("probe", encoding="utf-8")
        res = run_launcher(launcher, prof, box_path)
        results["updating"] = report(
            "updating", "reason=updating / exit 1", res,
            res["exit_code"] == 1 and res["reasons"] == ["updating"],
        )

        # ---------------- 2. no_python ----------------
        frame("no_python", "PATH 里没有 python（沙箱里也没有 .venv）")
        prof = temp_dir("nopython")
        res = run_launcher(launcher, prof, box_path)
        results["no_python"] = report(
            "no_python", "reason=no_python / exit 1", res,
            res["exit_code"] == 1 and res["reasons"] == ["no_python"],
        )

        # ---------------- 3. started（真起服务，探针端口）----------------
        frame("started", f"{PORT} 空闲 → 真起服务并等就绪（期间抑制浏览器打开）")
        say(f"[started] 前置：清干净 {PORT}（含上次残留）→ 空闲={clear_port(PORT, 'started')}")
        prof = temp_dir("started")
        with browser_stub.suppress_browser(prof) as brep:
            res = run_launcher(launcher, prof, f"{box_path};{os.environ.get('PATH', '')}", {
                "FIRSTEP_LAUNCHER_PORT": str(PORT),
                "PYTHONPATH": "src",
            }, timeout=180)
        say(f"[started] 浏览器抑制：新增浏览器进程={brep['new_browser_procs']} "
            f"已复原={brep['restored']}（原 ProgId={brep['progid']}）")
        results["started"] = report(
            "started", "reason=started / exit 0（服务在 20s 内就绪）", res,
            res["exit_code"] == 0 and res["reasons"] == ["started"],
        )
        started_here = True
        say(f"[started] 健康核对（{PORT}）：{health()}  pid={listener_pid()}")

        # ---------------- 4. already_running ----------------
        frame("already_running", f"{PORT} 上的就是本应用（也会走一次浏览器打开 → 同样抑制）")
        prof = temp_dir("running")
        with browser_stub.suppress_browser(prof) as brep2:
            res = run_launcher(launcher, prof, f"{box_path};{os.environ.get('PATH', '')}", {
                "FIRSTEP_LAUNCHER_PORT": str(PORT),
            })
        say(f"[already_running] 浏览器抑制：新增浏览器进程={brep2['new_browser_procs']} "
            f"已复原={brep2['restored']}")
        results["already_running"] = report(
            "already_running", "reason=already_running / exit 0", res,
            res["exit_code"] == 0 and res["reasons"] == ["already_running"],
        )

        # 停掉探针自己起的服务（连子进程树），把端口让给 port_busy
        clear_port(PORT, "already_running")
        started_here = False

        # ---------------- 5. port_busy ----------------
        frame("port_busy", f"{PORT} 上有监听但身份不符")
        say(f"[port_busy] 前置：清干净 {PORT} → 空闲={clear_port(PORT, 'port_busy')}")
        placeholder = start_placeholder("someone-else")
        say(f"[port_busy] 占位服务就绪（{PORT}）：{health()}")
        prof = temp_dir("portbusy")
        res = run_launcher(launcher, prof, f"{box_path};{os.environ.get('PATH', '')}", {
            "FIRSTEP_LAUNCHER_PORT": str(PORT),
        })
        results["port_busy"] = report(
            "port_busy", "reason=port_busy / exit 1（身份不符 ≠ 本应用）", res,
            res["exit_code"] == 1 and res["reasons"] == ["port_busy"],
        )
        stop(placeholder)
        placeholder = None
        wait_port_free(PORT)

        # ---------------- 6. timeout（E2 第三态）----------------
        frame("timeout", "服务起得来但 20s 内不就绪（python 替身：服务启动被挂住）")
        say(f"[timeout] 前置：清干净 {PORT} → 空闲={clear_port(PORT, 'timeout')}")
        prof = temp_dir("timeout")
        # 替身必须是**可运行的 python.exe**：本机 python 是「嵌入式/可搬运」安装
        # （`sys.executable` 那份 python.exe 旁边带着 DLL），只拷 exe 本体跑不起来
        # （实测 STATUS_DLL_NOT_FOUND），所以整目录拷一份再替换。
        real_home = Path(sys.executable).parent
        stage = prof / "realpy"
        shutil.copytree(real_home, stage)
        fake_src = (HERE / "python_fake.py").read_text(encoding="utf-8")
        (stage / "python_fake.py").write_text(fake_src, encoding="utf-8")
        # `import site`（见下 `._pth`）会自动 import `sitecustomize` —— 官方钩子，
        # 于是「服务启动」在解释器启动阶段就被截住，不需要改任何产品码。
        (stage / "sitecustomize.py").write_text(fake_src, encoding="utf-8")
        # `._pth` 会**接管** sys.path（隔离模式）：标准库 `Lib`、扩展 `DLLs`、本目录都得写进去，
        # 否则连 `encodings` 都 import 不了（第一版报了 Fatal Python error: Failed to import
        # encodings module）；`import site` 才会去读 launcher 设的 PYTHONPATH=src。
        (stage / "python._pth").write_text(
            "Lib\nDLLs\n.\nimport site\n", encoding="ascii")
        chatter = subprocess.run([str(stage / "python.exe"), "-c", "print('shim ok')"],
                                 capture_output=True, text=True, errors="replace", timeout=90)
        say(f"[timeout] 替身自证（转发自检，应含 shim ok、不挂）："
            f"{chatter.stdout.strip()!r} rc={chatter.returncode}")
        hold = subprocess.Popen([str(stage / "python.exe"), "-m", "contest_generator.webapp"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=NO_WINDOW)
        time.sleep(2.0)
        held = hold.poll() is None
        say(f"[timeout] 替身对服务启动的反应（应挂住）：{'挂住 ✓' if held else '没挂住 ✗'}")
        subprocess.run(["taskkill", "/PID", str(hold.pid), "/T", "/F"],
                       capture_output=True, text=True)
        res = run_launcher(launcher, prof, f"{stage};{box_path}", {
            "FIRSTEP_LAUNCHER_PORT": str(PORT),
        }, timeout=180, note="服务被替身挂住，launcher 走完 20 次轮询后自行退出")
        results["timeout"] = report(
            "timeout", "reason=timeout / exit 1（服务 20s 内未就绪）", res,
            res["exit_code"] == 1 and res["reasons"] == ["timeout"],
        )
        webapp_log = prof / ".contest_generator" / "webapp.log"
        if webapp_log.is_file():
            tail = webapp_log.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            say(f"[timeout] 服务侧 webapp.log 尾 3 行：{tail[-3:]}")
        else:
            say("[timeout] 服务侧 webapp.log 尚不存在")

        # 收尾：替身还挂着，按端口找监听者杀干净（否则下一次测量会被它污染）
        for _ in range(20):
            pid = listener_pid(PORT)
            if not pid:
                break
            say(f"[timeout] 收尾：杀掉替身挂住的服务 pid={pid}")
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, text=True)
            time.sleep(0.5)
        say(f"[timeout] 收尾后 {PORT} 监听={port_listening()}")

        # ---------------- 7. 默认端口的只读观察 ----------------
        frame("already_running@8000", "默认端口上与用户真实会话共存（只读观察，不起服务）")
        real_health = health(REAL_PORT)
        say(f"[already_running@8000] 现场健康={real_health} 监听={port_listening(REAL_PORT)}")
        if real_health:
            prof = temp_dir("real8000")
            with browser_stub.suppress_browser(prof) as brep3:
                res = run_launcher(launcher, prof, f"{box_path};{os.environ.get('PATH', '')}")
            say(f"[already_running@8000] 浏览器抑制：新增浏览器进程={brep3['new_browser_procs']} "
                f"已复原={brep3['restored']}")
            results["already_running@8000"] = report(
                "already_running@8000", "reason=already_running / exit 0（默认端口不变）", res,
                res["exit_code"] == 0 and res["reasons"] == ["already_running"],
            )
        else:
            say("[already_running@8000] 8000 上此刻没有本应用 → 跳过（不冒充）")
            results["already_running@8000"] = False

    finally:
        stop(placeholder)
        if started_here:
            pid = listener_pid()
            if pid:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True)
                say(f"[收尾] 停掉探针起的服务 pid={pid}")
        # launcher 是用 `start "" /b python -m …` 把服务**脱离**进程树起的：`taskkill /T` 打不到它，
        # 所以最后必须按端口再收一次（实测漏掉一次就会留一个 8899 监听者，让下一次测量读到
        # `:already_running`/`:port_busy` 而不是它该有的形态）。
        cleared = clear_port(PORT, "收尾")
        say(f"[收尾] 探针端口 {PORT} 已清空={cleared}")
        _stop_reaper.set()
        say("")
        say(f"[收尾] 弹窗清扫共杀掉 {len(_reaped)} 个宿主进程 {_reaped[:8]}")
        say(f"[收尾] 用户会话核对：{REAL_PORT} 健康={health(REAL_PORT)}")

    say("")
    say("=" * 78)
    say("判读汇总（全部真跑，非推断）")
    say("=" * 78)
    for name, ok in results.items():
        say(f"  {name:20s} {'PASS' if ok else 'FAIL'}")
    say(f"  合计：{sum(results.values())}/{len(results)} PASS")
    OUT.write_text("\n".join(_lines) + "\n", encoding="utf-8")
    print(f"\n落盘：{OUT}", flush=True)
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
