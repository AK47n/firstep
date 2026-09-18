# -*- coding: utf-8 -*-
"""B2 —— 三个极端场景（弱网中途取消 / 断线重试 / 校验失败）在**沙箱真机**上跑一遍。

工单 `sandbox-drill/02`：G1 后三步此前只在代码侧被自动化覆盖过——**代码侧覆盖不等于
真机覆盖**：半成品留没留、边车写没写、重试从哪接着下、报错是不是中文、旧版本还能不能用，
这些只有真跑才看得见。

## 怎么把它跑成「真机」而不是「调函数」

- **产品侧一点没改**：起的是沙箱 `src/`（v1.2.1，与真身同源）的那套代码，
  走的是产品自己的端点 `/api/update/full/{check,apply,status,cancel}`；
- **网络侧是本地可控服务器**（`drill-02-simserver.py`，与 `resumable-download/sim-server.py`
  同族）：它能发真字节、限速（弱网）、按次数切断（断线）、把字节改坏（校验失败），
  并且**载荷是一个真 zip**——这样「下载完成」之后产品自己的替换链还能一路走完
  （随机字节不是 zip，链会在预检处失败，`done` 这一格就永远看不到）；
- **唯一的一处「接线」是 harness**（`drill_app.py`，写在一次性目录里，**不进沙箱**）：
  把「线上 Release 从哪取」指到本地假 GitHub（`materials_update.RELEASES_URL` +
  `full_update._fetch_releases`），并让应用用一次性配置（沙箱库目录 + 关自动提交）。
  产品的 `.py` 文件一个字节都没动——证据里逐条写明。

## 判据（全部是产品可观察量）

| 场景 | 判据 |
|---|---|
| 弱网中途取消 | 状态 `cancelled`；`updates/full/` 下半成品 + `.partial.json` 边车**都在**；工具仍可用；再点重试**从已下字节接着下**（不是 0）；终态校验通过 |
| 断线重试 | `retry_count` 增长 + 「正在自动重试 / 从 X% 接着下」话术；网络恢复后续传完成；**终态字节数与 sha256 都对** |
| 校验失败 | 报**中文**校验失败、半成品与边车被清、`updating.lock` 与 `pending` 都没留下、**旧版本仍可用**（服务还在、版本没变）、备份目录不受影响 |

用法::

    python .scratch/verify-gate-drills/drill-02-degraded.py            # 真跑三个场景
    python .scratch/verify-gate-drills/drill-02-degraded.py --only slow-cancel
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# 控制台是 GBK（Windows 中文默认）：脚本里的中文与符号必须能出去，否则
# 打印时抛 UnicodeEncodeError 把整轮演练打断（第一版就死在 '⇒' 上）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SIM_ROOT = Path(r"C:\Users\luoji\Desktop\firstep-sim")
SIM_DATA = Path(r"C:\Users\luoji\.contest_generator_sim")
REAL_DATA = Path.home() / ".contest_generator"
REAL_UPDATES = REAL_DATA / "updates"
SIM_UPDATES = SIM_DATA / "updates"
PORT = 8020
BASE = f"http://127.0.0.1:{PORT}"
PART_NAME = "firstep-full-v1.2.1.zip"
PAYLOAD_BIG_BYTES = 4 * 1024 * 1024


def run_data_dir(work: Path) -> Path:
    """演练自己的「用户数据目录」（一次性）。

    **为什么必须钉住这件事**：产品的 `updates/` 是
    `context.config_path.parent / "updates"`——配置放哪，下载态就落哪。
    第一版把配置放在演练目录根 → 产品的半成品/边车/快照全落在**演练目录**，
    而断言却去沙箱数据目录找，于是「取消后半成品在不在」量出 0 字节、
    「断线重试」直接命中一份已下完的文件（0 次请求）——整轮证据作废。
    现在配置放进 `<work>/profile/.contest_generator/config.json`（与真机用户目录同构），
    下载态就落在它下面，沙箱自己的 `~/.contest_generator_sim` 一个字节都不碰。
    """
    return work / "profile" / ".contest_generator"


def run_updates_dir(work: Path) -> Path:
    return run_data_dir(work) / "updates"

LINES: list[str] = []
RESULTS: dict = {"problems": [], "stuck": [], "notes": [], "scenarios": {}}


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def note(text: str) -> None:
    RESULTS["notes"].append(text)
    log(f"  [记录] {text}")


def problem(text: str) -> None:
    RESULTS["problems"].append(text)
    log(f"  [判红] {text}")


def stuck(text: str) -> None:
    RESULTS["stuck"].append(text)
    log(f"  [卡住] {text}")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dir_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return -1.0


def listen_pids(port: int) -> list[str]:
    pids: list[str] = []
    try:
        output = subprocess.run(["netstat", "-ano"], capture_output=True,
                                text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001
        return pids
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[-2] == "LISTENING" and f":{port}" in parts[1]:
            if parts[-1] not in pids:
                pids.append(parts[-1])
    return pids


def kill_listener(port: int) -> list[str]:
    killed: list[str] = []
    for pid in listen_pids(port):
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True)
        killed.append(pid)
    return killed


SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv",
             "node_modules", ".claude", ".scratch"}


def tree_stamp(root: Path) -> dict[str, tuple[int, float]]:
    stamp: dict[str, tuple[int, float]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        stamp[str(rel).replace("\\", "/")] = (stat.st_size, stat.st_mtime)
    return stamp


def diff_stamp(before: dict, after: dict) -> dict:
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(k for k in set(before) & set(after) if before[k] != after[k]),
    }


# ---------------------------------------------------------------------------
# 端点客户端
# ---------------------------------------------------------------------------


def api(path: str, payload: dict | None = None, timeout: float = 120) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE + path, data=data, method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} → HTTP {exc.code}：{body[:400]}") from None


def health(timeout: float = 3) -> dict | None:
    try:
        with urllib.request.urlopen(f"{BASE}/api/health", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def wait_health(deadline_seconds: float = 60) -> dict | None:
    end = time.time() + deadline_seconds
    while time.time() < end:
        got = health()
        if got:
            return got
        time.sleep(0.4)
    return None


# ---------------------------------------------------------------------------
# 假 GitHub（本地，只服务 release 列表与清单；载荷走 sim-server）
# ---------------------------------------------------------------------------


def _send_json(handler: BaseHTTPRequestHandler, body: dict) -> None:
    """给假 GitHub 的处理器用（写在模块级：`_json` 挂错对象是演练第一版的真 bug）。"""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class FakeGitHub:
    """线程内 HTTP 服务：让产品的「检查更新」看到一份我们自己写的 Release。

    **只替换「从哪取数据」这一跳**：release 列表与清单的形状照线上真实资产
    （`browser_download_url` / `parts[].zip_name|size|sha256`），分卷地址指到
    `drill-02-simserver.py`。
    """

    def __init__(self) -> None:
        self.part_url = ""
        self.part_size = 0
        self.part_sha = ""
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a) -> None:
                pass

            def do_GET(self) -> None:  # noqa: N802
                from urllib.parse import urlparse
                path = urlparse(self.path).path
                if path == "/manifest":
                    _send_json(self, {
                        "version": "v1.2.1",
                        "published_at": "",
                        "total_bytes": outer.part_size,
                        "parts": [{"zip_name": PART_NAME, "size": outer.part_size,
                                   "sha256": outer.part_sha}],
                        "removed": [],
                        "files": [],
                    })
                    return
                if path.startswith("/repos/"):
                    _send_json(self, [{
                        "tag_name": "v1.2.1",
                        "name": "drill v1.2.1",
                        "assets": [
                            {"name": "firstep-full-v1.2.1.manifest.json",
                             "browser_download_url": f"{outer.base}/manifest",
                             "size": 200},
                            {"name": PART_NAME,
                             "browser_download_url": outer.part_url,
                             "size": outer.part_size},
                        ],
                    }])
                    return
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       kwargs={"poll_interval": 0.2}, daemon=True)

    def start(self) -> "FakeGitHub":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def releases_url(self) -> str:
        return f"{self.base}/repos/AK47n/firstep/releases?per_page=30"

    def set_part(self, url: str, size: int, sha: str) -> None:
        self.part_url, self.part_size, self.part_sha = url, size, sha


# ---------------------------------------------------------------------------
# 本地可控下载服务器（子进程：drill-02-simserver.py）
# ---------------------------------------------------------------------------


class SimServer:
    def __init__(self, payload_file: Path) -> None:
        self.payload_file = payload_file
        self.proc: subprocess.Popen | None = None
        self.port = 0
        self.size = 0
        self.sha = ""

    def __enter__(self) -> "SimServer":
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        self.proc = subprocess.Popen(
            [sys.executable, str(HERE / "drill-02-simserver.py"),
             "--port", "0", "--file", str(self.payload_file)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
            text=True, encoding="utf-8", env=env,
        )
        ready = self.proc.stdout.readline().strip()
        if not ready.startswith("READY"):
            raise RuntimeError(f"本地可控服务器未就绪：{ready!r}")
        fields = dict(kv.split("=", 1) for kv in ready.split()[1:])
        self.port = int(fields["port"])
        self.size = int(fields["size"])
        self.sha = fields["sha256"]
        return self

    def __exit__(self, *exc) -> None:
        if self.proc is None:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.write("stop\n")
                self.proc.stdin.flush()
                self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None

    def url(self, mode: str, **kw) -> str:
        query = [f"mode={mode}"] + [f"{k}={v}" for k, v in kw.items()]
        return f"http://127.0.0.1:{self.port}/p?" + "&".join(query)

    def requests(self) -> list[dict]:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/requests",
                                    timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def reset(self) -> None:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/reset",
                                    timeout=10) as resp:
            resp.read()


# ---------------------------------------------------------------------------
# 载荷：一个**真 zip**（含一个 4 MiB 的存储条目，够限速/切断用）
# ---------------------------------------------------------------------------


def build_payload_zip(dest: Path) -> dict:
    marker = ("B2 演练标记：完整包替换链真的跑到了这里（drill-02-degraded.py）\n")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED) as z:
        z.writestr("sources/materials/.b2-drill-marker.txt", marker)
        z.writestr("sources/materials/.b2-drill-payload.bin",
                   (b"firstep-drill-b2\n" * (PAYLOAD_BIG_BYTES // 18 + 1))
                   [:PAYLOAD_BIG_BYTES])
    return {"path": str(dest), "size": dest.stat().st_size,
            "sha256": sha256_of(dest), "marker": marker}


# ---------------------------------------------------------------------------
# harness：一次性入口 + 一次性配置（**不碰沙箱任何文件**）
# ---------------------------------------------------------------------------


def write_harness(work: Path, fake: FakeGitHub) -> tuple[Path, Path, dict]:
    data_dir = run_data_dir(work)
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = data_dir / "config.json"
    real_config = Path.home() / ".contest_generator" / "config.json"
    cfg = json.loads(real_config.read_text(encoding="utf-8-sig"))
    cfg["module_library_dir"] = str(SIM_ROOT / "library" / "modules")
    cfg["masters_dir"] = str(SIM_ROOT / "library" / "masters")
    cfg["autocommit_enabled"] = False
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "updates" / "full").mkdir(parents=True, exist_ok=True)

    launcher = work / "drill_app.py"
    launcher.write_text(
        "# 一次性 harness（写在演练目录，不进沙箱）：只把「Release 从哪取」这一跳\n"
        "# 指到本地假 GitHub；产品的 .py 一个字节都没动。\n"
        "import json, os, sys, urllib.request\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, r'%s')\n"
        "FAKE = os.environ['DRILL_FAKE_RELEASES_URL']\n"
        "import contest_generator.materials_update as mu\n"
        "import contest_generator.full_update as fu\n"
        "mu.RELEASES_URL = FAKE\n"
        "def _fetch():\n"
        "    req = urllib.request.Request(FAKE, headers={'User-Agent': 'firstep-drill'})\n"
        "    with urllib.request.urlopen(req, timeout=15) as resp:\n"
        "        return json.loads(resp.read().decode('utf-8'))\n"
        "mu._fetch_releases = _fetch\n"
        "fu._fetch_releases = _fetch\n"
        "import uvicorn\n"
        "from contest_generator.webapp import AppContext, create_app\n"
        "ctx = AppContext(config_path=Path(os.environ['DRILL_CONFIG']))\n"
        "uvicorn.run(create_app(ctx), host='127.0.0.1',\n"
        "            port=int(os.environ.get('FIRSTEP_LAUNCHER_PORT', '8020')))\n"
        % (SIM_ROOT / "src"),
        encoding="utf-8")

    env = dict(os.environ)
    env.update({
        "FIRSTEP_LAUNCHER_PORT": str(PORT),
        "USERPROFILE": str(work / "profile"),
        "HOME": str(work / "profile"),
        "PYTHONPATH": str(SIM_ROOT / "src"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "DRILL_FAKE_RELEASES_URL": fake.releases_url,
        "DRILL_CONFIG": str(cfg_path),
    })
    return launcher, cfg_path, env


class App:
    def __init__(self, launcher: Path, env: dict, work: Path) -> None:
        self.launcher = launcher
        self.env = env
        self.work = work
        self.proc: subprocess.Popen | None = None
        self.starts = 0

    def start(self) -> dict | None:
        kill_listener(PORT)
        time.sleep(0.6)
        self.starts += 1
        handle = open(self.work / f"harness-run-{self.starts}.log", "a",
                      encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, str(self.launcher)], cwd=str(SIM_ROOT), env=self.env,
            stdout=handle, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return wait_health(120)

    def ensure(self) -> dict | None:
        """保证跑在 8020 上的是**我们的 harness 应用**（场景之间会经历更新器重启）。

        为什么不能只看 `/api/health`：更新器替换完会拉起**产品自己的入口**
        （`start-app.vbs`，没有假 GitHub 注入）——那种情况下再点「检查更新」会去
        真的线上取，这一轮就会真下 800 MB。所以身份判据必须落在**分卷地址**
        上：`/api/update/full/check` 返回的分卷 url 指向 `127.0.0.1` 才是我们的。
        """
        got = health()
        if got is not None and self.proc is not None and self.proc.poll() is None:
            try:
                check = api("/api/update/full/check", timeout=60)
                urls = [str(p.get("url") or "") for p in check.get("parts") or []]
                if urls and all(u.startswith("http://127.0.0.1:") for u in urls):
                    return got
                log("  （8020 上的服务不是 harness 那套——分卷地址不是本地；"
                    "收掉重起 harness，避免误触真线上）")
            except Exception as exc:  # noqa: BLE001
                log(f"  （身份判据取不到 check：{type(exc).__name__}: {exc}）")
        return self.start()


# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------


def clean_task_state(work: Path, archive_root: Path) -> dict:
    """把**演练数据目录**里的 `updates/full/` 与快照挪走（不删：挪到演练目录存档），
    让每个场景从零开始。操作对象是 `run_updates_dir(work)`——不是沙箱的 updates。"""
    updates = run_updates_dir(work)
    moved: dict[str, str] = {}
    archive_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%H%M%S")
    full_dir = updates / "full"
    if full_dir.is_dir() and any(full_dir.iterdir()):
        target = archive_root / f"full-{stamp}"
        shutil.move(str(full_dir), str(target))
        full_dir.mkdir(parents=True, exist_ok=True)
        moved["updates/full"] = str(target)
    for name in ("full-task.json",):
        src = updates / name
        if src.is_file():
            target = archive_root / f"{name}-{stamp}"
            shutil.move(str(src), str(target))
            moved[f"updates/{name}"] = str(target)
    return moved


def _part_path(work: Path) -> Path:
    return run_updates_dir(work) / "full" / PART_NAME


def _sidecar(work: Path) -> Path:
    return Path(str(_part_path(work)) + ".partial.json")


def _retry_phrase_template_present() -> bool:
    """「正在自动重试（第 N 次）…从 X% 接着下」这句话是不是**前端**拼的。

    为什么要静态读模板而不是断言 `message` 里含该短语：产品把「第 N 次」放在结构化字段
    `retry_count`、把「从 X%」放在 `resume_percent`，`message` 只放原因（`fx/core.js:88-97`
    的注释明写第一版拿正则从 message 里摘百分比 = 把文案当接口，已改）。所以正确的判据是
    **结构化字段齐全 + 模板在场**，而不是在文案里找词（第一版就是这么误判了一条）。
    """
    path = REPO / "src" / "contest_generator" / "static" / "js" / "fx" / "core.js"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return "正在自动重试（第 ${attempt} 次）" in text and "接着下" in text


def scenario_slow_cancel(sim: SimServer, app: App, archive: Path,
                         payload: dict) -> dict:
    log("")
    log("## 场景一：弱网中途取消（mode=slow&kbps=64）")
    sim.reset()
    moved = clean_task_state(app.work, archive)
    log(f"  起始清理（挪走旧任务态）：{moved or '（无）'}")
    sim_url = sim.url("slow", kbps=64)
    app.ensure()
    log(f"  分卷地址（本地可控服务器）：{sim_url}")
    log(f"  载荷：{sim.size} 字节 / sha256 {sim.sha[:16]}…")
    check = api("/api/update/full/check", timeout=120)
    parts = check.get("parts") or []
    log(f"  check：latest={check.get('latest_version')} reason={check.get('reason')} "
        f"分卷={[(p['name'], p['size'], p['sha256'][:12], p['url']) for p in parts]}")
    started = api("/api/update/full/apply", {"parts": [PART_NAME]}, timeout=60)
    log(f"  apply：{started}")
    out: dict = {"sim_url": sim_url, "payload_size": sim.size, "payload_sha": sim.sha}

    # 等到确实下了点东西再取消（弱网保证有窗口）
    end = time.time() + 60
    progress = 0
    while time.time() < end:
        status = api("/api/update/full/status", timeout=30)
        progress = int(status.get("total_downloaded_bytes") or 0)
        if progress >= 262144:
            break
        time.sleep(0.5)
    log(f"  取消前已下 {progress} 字节（{progress / 1024:.0f} KB）")
    cancelled = api("/api/update/full/cancel", {}, timeout=60)
    log(f"  cancel：{cancelled}")
    end = time.time() + 90
    status = {}
    while time.time() < end:
        status = api("/api/update/full/status", timeout=30)
        if status.get("state") in ("cancelled", "failed", "done"):
            break
        time.sleep(0.5)
    part = _part_path(app.work)
    bytes_after_cancel = part.stat().st_size if part.is_file() else 0
    checks = {
        "状态 = cancelled": status.get("state") == "cancelled",
        "半成品还在（updates/full/ 下）": part.is_file() and bytes_after_cancel > 0,
        "边车 .partial.json 已写": _sidecar(app.work).is_file(),
        "工具仍可用（/api/health 正常）": health() is not None,
    }
    for label, ok in checks.items():
        log(f"  {'成立' if ok else '**不成立**'}：{label}"
            f"（半成品 {bytes_after_cancel} 字节 / "
            f"边车 {_sidecar(app.work).is_file()}）")
    out["cancel_checks"] = checks
    out["bytes_after_cancel"] = bytes_after_cancel
    out["status_after_cancel"] = {k: status.get(k) for k in
                                  ("state", "message", "error", "error_kind",
                                   "retry_count")}
    log(f"  取消态：state={status.get('state')} message={status.get('message')!r} "
        f"error={status.get('error')!r}")

    # 再点重试：必须从断点接着下
    mark = len(sim.requests())
    app.ensure()
    started2 = api("/api/update/full/apply", {"parts": [PART_NAME]}, timeout=60)
    log(f"  重试 apply：{started2}")
    first_progress = None
    first_message = None
    restarted_midway = False
    end = time.time() + 300
    final: dict = {}
    t0 = time.time()
    last_log = 0.0
    while time.time() < end:
        status = api("/api/update/full/status", timeout=30)
        if first_progress is None:
            first_progress = int(status.get("total_downloaded_bytes") or 0)
            first_message = status.get("message") or ""
            log(f"  [重试起手] 首次进度 {first_progress} 字节 / "
                f"摘要={first_message!r}")
        if time.time() - last_log > 20:
            log(f"    [{time.time() - t0:6.1f}s] state={status.get('state')} "
                f"bytes={status.get('total_downloaded_bytes')} "
                f"retry={status.get('retry_count')}")
            last_log = time.time()
        if status.get("state") in ("applying", "done", "failed", "cancelled"):
            final = status
            break
        if (status.get("state") == "idle" and app.proc is not None
                and app.proc.poll() is not None):
            # 更新器已经把替换跑完：它停掉了我们的 harness 应用、又拉起了产品自己的
            # 入口，新进程里没有这个任务（状态回到 idle）。**不是产品异常**，
            # 是「任务完成 → 应用 → 重启」这条链走到底了；终态从盘上产物与更新器
            # 留痕判。
            restarted_midway = True
            log("  （状态回到 idle 且 harness 进程已退出 = 更新器已完成替换并重启，"
                "任务终态改用盘上产物 + 更新器日志判）")
            break
        time.sleep(0.7)
    starts = [r["start"] for r in sim.requests()[mark:]] or [None]
    part = _part_path(app.work)
    digest = sha256_of(part) if part.is_file() else ""
    size_on_disk = part.stat().st_size if part.is_file() else 0
    updater_log = run_updates_dir(app.work) / "updater.log"
    updater_text = updater_log.read_text(encoding="utf-8", errors="replace") \
        if updater_log.is_file() else ""
    completed_by_updater = "更新完成" in updater_text
    log(f"  重试终局：state={final.get('state')} 盘上 {size_on_disk} 字节 / "
        f"sha256 {digest[:16]}…；更新器跑到「更新完成」= {completed_by_updater}")
    retry_checks = {
        "重试后首次进度 >= 取消时的字节（不是从 0 重下）":
            first_progress is not None and first_progress >= bytes_after_cancel,
        "摘要说明「接着下」":
            bool(first_message) and ("接着下" in first_message
                                     or "上次的进度" in first_message),
        "服务器台账：续传请求起始偏移 = 取消时的字节":
            starts[0] == bytes_after_cancel,
        "卷已下完（盘上长度 = 载荷大小）": size_on_disk == sim.size,
        "终态校验通过（盘上 sha256 = 载荷 sha256）": digest == sim.sha,
        "下载完成后替换链真的跑到了（更新器「更新完成」）": completed_by_updater,
    }
    for label, ok in retry_checks.items():
        log(f"  {'成立' if ok else '**不成立**'}：{label}")
    out["retry_checks"] = retry_checks
    out["retry_first_progress"] = first_progress
    out["retry_first_message"] = first_message
    out["retry_request_starts"] = starts
    out["restarted_midway"] = restarted_midway
    out["retry_final"] = {k: final.get(k) for k in
                          ("state", "total_downloaded_bytes", "total_bytes",
                           "message", "error", "retry_count", "error_kind")}
    out["updater_completed"] = completed_by_updater
    RESULTS["scenarios"]["slow-cancel"] = out
    for label, ok in list(checks.items()) + list(retry_checks.items()):
        if not ok:
            problem(f"[弱网取消] 判据不成立：{label}")
    return out


def scenario_cut_retry(sim: SimServer, app: App, archive: Path,
                       payload: dict) -> dict:
    log("")
    log("## 场景二：断线重试（mode=cut&fraction=0.4&cut_runs=2&kbps=512）")
    sim.reset()
    moved = clean_task_state(app.work, archive)
    log(f"  起始清理（挪走旧任务态）：{moved or '（无）'}")
    sim_url = sim.url("cut", fraction=0.4, cut_runs=2, kbps=512)
    app.ensure()
    log(f"  分卷地址：{sim_url}")
    # 夹具自检：起点必须是干净的（上一轮就是因为「上一次下载的成品还在」，
    # 任务走「长度到点 → 不发请求」，整格 0 次请求、判据全废）
    part = _part_path(app.work)
    start_clean = (not part.is_file()) and (not _sidecar(app.work).is_file())
    log(f"  夹具自检：起点分卷存在={part.is_file()} / "
        f"边车存在={_sidecar(app.work).is_file()} / 快照存在="
        f"{(run_updates_dir(app.work) / 'full-task.json').is_file()} "
        f"→ 起点{'干净' if start_clean else '**不干净**'}")
    if not start_clean:
        stuck("[断线重试] 夹具起点不干净（上一次的成品/边车还在）——本格判据会失效")
    check = api("/api/update/full/check", timeout=120)
    log(f"  check：latest={check.get('latest_version')} reason={check.get('reason')} / "
        f"分卷={[(p['name'], p['size'], p['url']) for p in check.get('parts') or []]}")
    started = api("/api/update/full/apply", {"parts": [PART_NAME]}, timeout=60)
    log(f"  apply：{started}")
    observations: list[dict] = []
    final: dict = {}
    saw_retry_window = False
    saw_retry_message = False
    saw_resume_percent = False
    end = time.time() + 300
    while time.time() < end:
        status = api("/api/update/full/status", timeout=30)
        row = {k: status.get(k) for k in
               ("state", "total_downloaded_bytes", "retry_count", "retrying",
                "error_kind", "message", "resume_percent")}
        if not observations or observations[-1] != row:
            observations.append(row)
            log(f"    state={row['state']} bytes={row['total_downloaded_bytes']} "
                f"retry={row['retry_count']} retrying={row['retrying']} "
                f"resume%={row['resume_percent']} kind={row['error_kind']!r} "
                f"msg={str(row['message'])[:56]!r}")
        if row["retrying"]:
            saw_retry_window = True
            if str(row.get("message") or "").strip():
                saw_retry_message = True
            if int(row.get("resume_percent") or -1) >= 0:
                saw_resume_percent = True
        if row["state"] in ("applying", "done", "failed", "cancelled"):
            final = status
            break
        if (row["state"] == "idle" and app.proc is not None
                and app.proc.poll() is not None):
            log("  （状态回到 idle 且 harness 进程已退出 = 更新器已完成替换并重启，"
                "改用更新器留痕判定「续传完成」）")
            break
        time.sleep(0.7)
    reqs = sim.requests()
    starts = [r["start"] for r in reqs]
    part = _part_path(app.work)
    digest = sha256_of(part) if part.is_file() else ""
    size_on_disk = part.stat().st_size if part.is_file() else 0
    updater_log = run_updates_dir(app.work) / "updater.log"
    updater_text = updater_log.read_text(encoding="utf-8", errors="replace") \
        if updater_log.is_file() else ""
    completed_by_updater = "更新完成" in updater_text
    max_retry = max([int(o.get("retry_count") or 0) for o in observations] or [0])
    checks = {
        "夹具起点干净（上一次的成品/边车都不在）": start_clean,
        "观察到 retry_count 增长（>=1）": max_retry >= 1,
        "观察到重试窗口 retrying=True": saw_retry_window,
        "重试窗口内有原因摘要（message 非空）": saw_retry_message,
        "重试窗口内给出「从 X% 接着下」的数据源（resume_percent >= 0）":
            saw_resume_percent,
        "用户可见的那句话由前端拼（模板在 fx/core.js:96-97，静态出处）":
            _retry_phrase_template_present(),
        "服务器台账：第一次从 0，其后从断点（单调不减）":
            bool(starts) and starts[0] == 0 and starts == sorted(starts),
        "至少一次带 Range 的续传请求（起始偏移 > 0）":
            any(s > 0 for s in starts[1:]),
        "卷已下完（盘上长度 = 载荷大小）": size_on_disk == sim.size,
        "终态 sha256 = 载荷 sha256": digest == sim.sha,
        "下载完成后替换链真的跑到了（更新器「更新完成」）": completed_by_updater,
        "成功后边车已清": not _sidecar(app.work).is_file(),
    }
    for label, ok in checks.items():
        log(f"  {'成立' if ok else '**不成立**'}：{label}")
    out = {"sim_url": sim_url, "request_starts": starts, "request_count": len(reqs),
           "max_retry_count": max_retry, "saw_retry_message": saw_retry_message,
           "observations": observations[-25:], "checks": checks,
           "updater_completed": completed_by_updater,
           "final": {k: final.get(k) for k in
                     ("state", "total_downloaded_bytes", "total_bytes", "error",
                      "error_kind", "retry_count")}}
    RESULTS["scenarios"]["cut-retry"] = out
    for label, ok in checks.items():
        if not ok:
            problem(f"[断线重试] 判据不成立：{label}")
    return out


def scenario_content_mismatch(sim: SimServer, app: App, archive: Path,
                              payload: dict) -> dict:
    log("")
    log("## 场景四分枝：**持久内容不符**（mode=corrupt；长度不变、字节被改坏）")
    log("  口径说明：spec `.scratch/resumable-download/spec.md` 第 122 行明文写着"
        "「下完但内容与清单 SHA256 不符 → 删半成品 + 走退避重试（从 0 整卷重来，"
        "**直到对上或用户取消**）」——所以这一格**不是**「该失败而没失败」的实现缺陷，"
        "而是**设计如此**；本格的用途是把这条设计的真机后果量出来（原先只有代码侧覆盖）。")
    sim.reset()
    moved = clean_task_state(app.work, archive)
    log(f"  起始清理（挪走旧任务态）：{moved or '（无）'}")
    sim_url = sim.url("corrupt", at=1024, count=16)
    app.ensure()
    before_health = health()
    guard = SIM_ROOT / "VERSIONS.md"
    guard_sha = sha256_of(guard) if guard.is_file() else ""
    log(f"  分卷地址：{sim_url}")
    start_clean = not _part_path(app.work).is_file()
    log(f"  夹具自检：起点分卷存在={not start_clean} → "
        f"{'干净' if start_clean else '**不干净**'}")
    if not start_clean:
        stuck("[持久内容不符] 夹具起点不干净——本格观察会失真")
    check = api("/api/update/full/check", timeout=120)
    log(f"  check：latest={check.get('latest_version')} 分卷大小="
        f"{[p.get('size') for p in check.get('parts') or []]}")
    started = api("/api/update/full/apply", {"parts": [PART_NAME]}, timeout=60)
    log(f"  apply：{started}")
    t0 = time.time()
    observations: list[dict] = []
    final: dict = {}
    end = time.time() + 150
    last_log = 0.0
    while time.time() < end:
        status = api("/api/update/full/status", timeout=30)
        row = {k: status.get(k) for k in
               ("state", "total_downloaded_bytes", "retry_count", "retrying",
                "error_kind", "message", "error")}
        if not observations or observations[-1] != row:
            observations.append(row)
            log(f"    [{time.time() - t0:6.1f}s] state={row['state']} "
                f"bytes={row['total_downloaded_bytes']} retry={row['retry_count']} "
                f"kind={row['error_kind']!r} msg={str(row['message'])[:70]!r} "
                f"err={str(row['error'])[:40]!r}")
        elif time.time() - last_log > 20:
            log(f"    [{time.time() - t0:6.1f}s] （仍在 {row['state']}："
                f"retry={row['retry_count']}）")
            last_log = time.time()
        if status.get("state") in ("failed", "done", "applying", "cancelled"):
            final = status
            break
        if (status.get("state") == "idle" and app.proc is not None
                and app.proc.poll() is not None):
            log("    （状态 idle 且 harness 退出 = 应用被更新器接走；观察到此为止）")
            break
        time.sleep(0.7)
    reqs = sim.requests()
    starts = [r["start"] for r in reqs]
    part = _part_path(app.work)
    after_health = health()
    log(f"  观察窗口 {time.time() - t0:.1f}s：{len(observations)} 个状态变化 / "
        f"重试 {max([int(o.get('retry_count') or 0) for o in observations] or [0])} 次")
    log(f"  服务器台账：{len(reqs)} 次请求，起始偏移 {starts[:20]}"
        f"（全 0 = 每轮整卷重下）")
    log(f"  半成品此刻在不在：{part.is_file()}（每轮内容不符都会就地 clear_partial）")
    out = {
        "spec_reference": "spec 第 122 行：内容不符 → 删半成品 + 退避重试，直到对上或用户取消",
        "terminal_reached": bool(final),
        "final_state": final.get("state"),
        "max_retry_count": max([int(o.get("retry_count") or 0)
                                for o in observations] or [0]),
        "observations": observations,
        "server_requests": len(reqs),
        "server_starts": starts,
        "partial_present_after": part.is_file(),
        "health_after": after_health,
        "observed_seconds": round(time.time() - t0, 1),
    }
    # 这一格**不判产品红**（行为与 spec 一致）；但要把「设计的后果」记清楚
    note("持久内容不符 = **永远 downloading + 每轮整卷重下**（spec 设计如此）："
         f"本机 {out['observed_seconds']}s 内重试 {out['max_retry_count']} 次、"
         f"台账 {len(reqs)} 次请求起始偏移全 0；退避封顶 60 秒，线上完整包 765 MB/轮 "
         f"→ 约 45 GB/小时的流量黑洞，且用户看不到任何终态或「重下不会有变化」的中文话术"
         "（那句只属于**不可重试**的 verify 分支，见下一格）。已按决策单记账。")
    if not out["terminal_reached"] and out["max_retry_count"] >= 3:
        log("  → 与 spec 设计一致：**无终态**（观察窗口内未收敛）")
    RESULTS["scenarios"]["content-mismatch"] = out
    return out


def scenario_verify_size(sim: SimServer, app: App, archive: Path,
                         payload: dict) -> dict:
    log("")
    log("## 场景三：校验失败（**不可重试**那一支：清单 size 与对端总长矛盾）")
    log("  做法：清单里把这个卷声明成 1 MiB，但服务器照真载荷（3.96 MB）发——"
        "客户端一读响应头就发现「清单说 1 MiB、对端说 3.96 MB」，"
        "按 spec 第 125 行这属于**发布物与清单不一致，不可重试**。")
    sim.reset()
    moved = clean_task_state(app.work, archive)
    log(f"  起始清理（挪走旧任务态）：{moved or '（无）'}")
    sim_url = sim.url("stable")
    app.ensure()
    before_health = health()
    guard = SIM_ROOT / "VERSIONS.md"
    guard_sha = sha256_of(guard) if guard.is_file() else ""
    log(f"  分卷地址：{sim_url}")
    log(f"  旧版本自证：跑着的服务版本 = {(before_health or {}).get('version')}")
    start_clean = not _part_path(app.work).is_file()
    log(f"  夹具自检：起点分卷存在={not start_clean} → "
        f"{'干净' if start_clean else '**不干净**'}")
    check = api("/api/update/full/check", timeout=120)
    log(f"  check：latest={check.get('latest_version')} / "
        f"分卷={[(p['name'], p['size'], p['url']) for p in check.get('parts') or []]}")
    started = api("/api/update/full/apply", {"parts": [PART_NAME]}, timeout=60)
    log(f"  apply：{started}")
    if not start_clean:
        stuck("[校验失败·不可重试] 夹具起点不干净——本格判据会失效")
    final: dict = {}
    end = time.time() + 120
    t0 = time.time()
    while time.time() < end:
        status = api("/api/update/full/status", timeout=30)
        log(f"    [{time.time() - t0:5.1f}s] state={status.get('state')} "
            f"bytes={status.get('total_downloaded_bytes')} "
            f"retry={status.get('retry_count')} kind={status.get('error_kind')!r}")
        if status.get("state") in ("failed", "done", "applying", "cancelled"):
            final = status
            break
        if (status.get("state") == "idle" and app.proc is not None
                and app.proc.poll() is not None):
            log("    （状态 idle 且 harness 退出 = 应用被更新器接走；改用更新器留痕判）")
            break
        time.sleep(0.7)
    log(f"  终态：state={final.get('state')} error_kind={final.get('error_kind')!r} "
        f"error={final.get('error')!r}")
    after_health = health()
    updates = run_updates_dir(app.work)
    part = _part_path(app.work)
    lock = updates / "updating.lock"
    pending = updates / "pending-update.json"
    error_text = str(final.get("error") or "")
    checks = {
        "夹具起点干净": start_clean,
        "终态 = failed": final.get("state") == "failed",
        "报错是中文（无英文异常名/Traceback）":
            bool(error_text) and not any(
                token in error_text for token in ("Traceback", "Error:", "Exception")),
        "报错指明清单与对端不一致": "不一致" in error_text,
        "error_kind = verify": str(final.get("error_kind")) == "verify",
        "不再重试（retry_count 未增长出多轮）":
            int(final.get("retry_count") or 0) <= 1,
        "半成品被清（updates/full/ 下不再有分卷）": not part.is_file(),
        "边车被清": not _sidecar(app.work).is_file(),
        "updating.lock 未留下": not lock.exists(),
        "pending-update.json 未留下": not pending.exists(),
        "旧版本仍可用（/api/health 正常）": after_health is not None,
        "旧版本没被换掉（服务版本仍是演练前那个）":
            (after_health or {}).get("version") == (before_health or {}).get("version"),
        "工具根没被动过（VERSIONS.md 逐字节未变）":
            (sha256_of(guard) if guard.is_file() else "") == guard_sha,
    }
    for label, ok in checks.items():
        log(f"  {'成立' if ok else '**不成立**'}：{label}")
    out = {"sim_url": sim_url, "declared_size": 1024 * 1024,
           "actual_payload_size": sim.size, "checks": checks,
           "final": {k: final.get(k) for k in
                     ("state", "error", "error_kind", "retry_count", "message")},
           "health_before": before_health, "health_after": after_health}
    RESULTS["scenarios"]["verify-size"] = out
    for label, ok in checks.items():
        if not ok:
            problem(f"[校验失败·不可重试] 判据不成立：{label}")
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="",
                        help="只跑一个场景：slow-cancel / cut-retry / bad-checksum")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    work = Path(os.environ["TEMP"]) / f"fe02-{time.strftime('%Y%m%d-%H%M%S')}"
    work.mkdir(parents=True, exist_ok=True)
    archive = work / "drill-updates-archive"
    profile = work / "profile"
    profile.mkdir(parents=True, exist_ok=True)

    log("# B2 证据：三个极端场景（沙箱真机 + 本地可控服务器）")
    log(f"  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"  一次性目录（harness 与证据都在这里）：{work}")
    log("")

    log("## 零、前置事实与隔离基线")
    real_data_mtime_before = dir_mtime(REAL_DATA)
    real_updates_before = sorted(p.name for p in REAL_UPDATES.iterdir()) \
        if REAL_UPDATES.is_dir() else []
    real_tree_before = tree_stamp(REPO)
    facts = {
        "sim_root": str(SIM_ROOT),
        "sim_version_on_disk": None,
        "sandbox_updates_entries": sorted(p.name for p in SIM_UPDATES.iterdir())
        if SIM_UPDATES.is_dir() else [],
        "port_8000_listeners": listen_pids(8000),
        "port_8020_listeners": listen_pids(PORT),
    }
    init = SIM_ROOT / "src" / "contest_generator" / "__init__.py"
    for line in init.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            facts["sim_version_on_disk"] = line.split('"')[1]
            break
    for key, value in facts.items():
        log(f"  {key} = {value!r}")
    RESULTS["facts"] = facts
    if facts["port_8020_listeners"]:
        killed = kill_listener(PORT)
        note(f"8020 上有遗留监听（PID {killed}），已先收掉再开跑")

    payload_zip = work / "payload-firstep-full-v1.2.1.zip"
    payload = build_payload_zip(payload_zip)
    log(f"  载荷 zip：{payload_zip}（{payload['size']} 字节 / "
        f"sha256 {payload['sha256'][:16]}…；含 4 MiB 存储条目，够限速与切断用）")

    fake = FakeGitHub().start()
    log(f"  本地假 GitHub：{fake.base}（release 列表 {fake.releases_url}）")
    launcher, cfg_path, env = write_harness(work, fake)
    app = App(launcher, env, work)

    scenarios = {
        "slow-cancel": scenario_slow_cancel,
        "cut-retry": scenario_cut_retry,
        "verify-size": scenario_verify_size,
        "content-mismatch": scenario_content_mismatch,
    }
    try:
        with SimServer(payload_zip) as sim:
            fake.set_part(sim.url("stable"), sim.size, sim.sha)
            log(f"  本地可控服务器：port={sim.port} size={sim.size} "
                f"sha256={sim.sha[:16]}…")
            got = app.start()
            log(f"  harness 应用：{got}")
            if got is None:
                stuck("harness 应用没起来（看 harness-run-1.log）")
                log((work / "harness-run-1.log").read_text(encoding="utf-8",
                                                           errors="replace")[-2000:])
                return 1
            order = [args.only] if args.only else list(scenarios)
            for name in order:
                if name not in scenarios:
                    problem(f"未知场景 {name!r}（可选：{list(scenarios)}）")
                    return 2
                # 每个场景换一次分卷地址（模式不同）
                if name == "slow-cancel":
                    fake.set_part(sim.url("slow", kbps=64), sim.size, sim.sha)
                elif name == "cut-retry":
                    fake.set_part(sim.url("cut", fraction=0.4, cut_runs=2, kbps=512),
                                  sim.size, sim.sha)
                elif name == "verify-size":
                    # 清单声明 1 MiB，服务器照真载荷发（3.96 MB）→ 不可重试的 verify 分支
                    fake.set_part(sim.url("stable"), 1024 * 1024, sim.sha)
                else:
                    fake.set_part(sim.url("corrupt", at=1024, count=16),
                                  sim.size, sim.sha)
                scenarios[name](sim, app, archive, payload)

        log("")
        log("## 场景之后的痕迹（如实记账）")
        for name in ("sources/materials/.b2-drill-marker.txt",
                     "sources/materials/.b2-drill-payload.bin"):
            path = SIM_ROOT / name
            log(f"  沙箱工具根 {name}: "
                f"{'在（' + str(path.stat().st_size) + ' 字节）' if path.is_file() else '不在'}")
        run_updates = run_updates_dir(work)
        markers = sorted(p.name for p in (run_updates / "backup").iterdir()) \
            if (run_updates / "backup").is_dir() else []
        log(f"  演练数据目录的备份目录：{markers}")
        log(f"  沙箱**自己**的数据目录（本格应零触碰）："
            f"{sorted(p.name for p in SIM_UPDATES.iterdir()) if SIM_UPDATES.is_dir() else '（无）'}")
        RESULTS["sandbox_traces"] = {
            "marker": (SIM_ROOT / "sources/materials/.b2-drill-marker.txt").is_file(),
            "drill_backups": markers,
            "sandbox_updates_untouched_entries": sorted(p.name for p in SIM_UPDATES.iterdir())
            if SIM_UPDATES.is_dir() else [],
        }
    finally:
        killed = kill_listener(PORT)
        fake.stop()
        time.sleep(0.5)
        leftover = listen_pids(PORT)
        log("")
        log("## 收尾")
        log(f"  收掉 8020 监听进程：{killed or '（无）'}；残余：{leftover or '（无）'}")
        RESULTS["cleanup"] = {"killed": killed, "leftover": leftover}

    log("")
    log("## 隔离边界收尾校验（真身只读）")
    real_data_mtime_after = dir_mtime(REAL_DATA)
    real_updates_after = sorted(p.name for p in REAL_UPDATES.iterdir()) \
        if REAL_UPDATES.is_dir() else []
    real_tree_after = tree_stamp(REPO)
    tree_diff = diff_stamp(real_tree_before, real_tree_after)
    isolation = {
        "real_data_mtime_untouched": real_data_mtime_after == real_data_mtime_before,
        "real_updates_untouched": real_updates_after == real_updates_before,
        "real_tree_untouched": not (tree_diff["added"] or tree_diff["removed"]
                                    or tree_diff["changed"]),
        "port_8000_listeners": listen_pids(8000),
    }
    log(f"  真身数据目录 mtime 未变：{isolation['real_data_mtime_untouched']}")
    log(f"  真身 updates/ 条目未变：{isolation['real_updates_untouched']}")
    log(f"  真身工作树未变：{isolation['real_tree_untouched']}"
        f"（{len(real_tree_before)} → {len(real_tree_after)} 个文件）")
    if not isolation["real_tree_untouched"]:
        for kind in ("added", "removed", "changed"):
            if tree_diff[kind]:
                log(f"    {kind}（前 12）：{tree_diff[kind][:12]}")
    log(f"  8000 监听：{isolation['port_8000_listeners'] or '（空）'}")
    RESULTS["isolation"] = isolation
    RESULTS["real_tree_diff"] = {k: tree_diff[k][:20] for k in
                                 ("added", "removed", "changed")}
    for label in ("real_data_mtime_untouched", "real_updates_untouched",
                  "real_tree_untouched"):
        if not isolation[label]:
            problem(f"隔离判据不成立：{label}")
    if not args.keep:
        log(f"  （证据目录保留在 {work}；脚本不自动删——里面有每个场景的原始台账）")
    return 0


def finish(code: int) -> int:
    (HERE / "verify-02-degraded.txt").write_text("\n".join(LINES) + "\n",
                                                 encoding="utf-8")
    (HERE / "verify-02-degraded.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n证据已写：verify-02-degraded.txt / .json")
    return code


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except Exception as exc:  # noqa: BLE001
        import traceback

        problem(f"脚本异常：{type(exc).__name__}: {exc}")
        log(traceback.format_exc())
    finally:
        problems = RESULTS["problems"]
        log("")
        log("## 总判")
        log(f"  判红 {len(problems)} 条 / 卡住 {len(RESULTS['stuck'])} 条")
        for item in problems:
            log(f"    · 判红：{item}")
        for item in RESULTS["stuck"]:
            log(f"    · 卡住：{item}")
        log(f"  B2「三极端场景」：{'PASS' if not problems else 'FAIL'}")
        RESULTS["verdict"] = {"problems": problems, "stuck": RESULTS["stuck"],
                              "pass": not problems}
        finish(exit_code)
    raise SystemExit(0 if not RESULTS["problems"] else 1)
