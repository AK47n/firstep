# -*- coding: utf-8 -*-
"""工单 06 档③：**真实完整包端到端**（工单 resumable-download/06）。

要回答的问题：「一个网络不稳的用户，从点下载到工具重启完成，这次会不会白等？」

口径（照工单原文，别即兴）：
- **真身只读**：本脚本**不碰** `Desktop\\firstep`（开发工作树）与 `%USERPROFILE%\\.contest_generator`
  （真身数据目录）。它把 `src/` 复制到 `%TEMP%` 下的一次性工具根，并把 `USERPROFILE`
  重定向到同一目录下的 `profile` —— 配置 / 日志 / updates 全被关进演练目录。
- `FIRSTEP_LAUNCHER_PORT=8020` 起服务（与真身 8000 隔离）。
- 断流用**真手段**：下载跑到一部分时把服务进程**杀掉**（模拟用户关掉工具 / 进程被杀），
  半成品与边车留在 `updates/` 下；重启服务后再点一次下载，**从断点接着下**。
- 完成判据：工具在 8020 起得来 + 版本号正确 + 真身数据目录 mtime 未变。

为什么用一次性工具根而不是 8020 沙箱：档③ 会把工具本体**替换成线上包**，
沙箱（`Desktop\\firstep-sim`）是现有的演练基线，换掉它代价太大；一次性根跑完即弃。

用法：`python .scratch/resumable-download/verify-06-tier3.py [--keep] [--fraction 0.25]`
产出：`verify-06-tier3.txt` + `.json`
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PORT = 8020
BASE = f"http://127.0.0.1:{PORT}"
LINES: list[str] = []
RESULTS: dict = {}

# 别被全局那份 editable 安装带偏：本机 site-packages 里残留的 `contest-generator`
# 元数据指向 `Desktop\firstep-sim\src`（见 docs/agents/local-environment.md 2.5），
# 它在 sys.path 的**最前面**，于是 `import contest_generator` 会拿到沙箱那份旧源码
# （实测：本脚本第一版就报 `cannot import name 'download_resume' from
# 'C:\...\firstep-sim\src\...'`）。这里显式把仓库自己的 src 插到最前，
# 并清掉任何已经加载的 contest_generator 模块，保证验的是**工作树这份**代码。
sys.path.insert(0, str(REPO / "src"))
for _name in [n for n in list(sys.modules) if n == "contest_generator"
              or n.startswith("contest_generator.")]:
    del sys.modules[_name]


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def api(path: str, payload: dict | None = None, timeout: float = 60) -> dict:
    url = BASE + path
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_retry(path: str, payload: dict | None = None, timeout: float = 120,
              attempts: int = 3) -> dict:
    """带重试的 api：GitHub 那一跳会慢会抖（实测 `full/check` 偶发超过 180 秒），
    一次超时不该把整轮演练判死——重试到成功或放弃，放弃时**大声**说清楚。
    """
    last: Exception | None = None
    for index in range(1, attempts + 1):
        try:
            return api(path, payload, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 —— 网络类异常都值得重试
            last = exc
            log(f"  （{path} 第 {index}/{attempts} 次失败：{type(exc).__name__}: {exc}）")
            time.sleep(3.0)
    raise RuntimeError(f"{path} 连续 {attempts} 次失败：{last}")


def wait_health(deadline_seconds: float = 60) -> bool:
    end = time.time() + deadline_seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001 —— 起服务期间连不上是正常的
            time.sleep(0.5)
    return False


def start_app(tool_root: Path, profile: Path, log_path: Path) -> subprocess.Popen:
    """起一次服务。

    **数据目录必须显式传进来**：`AppContext.config_path` 的默认值是在**类定义时**
    求值的（`Path.home() / CONFIG_DIRNAME / ...`），所以只重定向 `USERPROFILE`
    是**不管用**的——`Path.home()` 在导入那一刻已经解析完了。第一版脚本就踩了这个坑：
    它以为数据被关进演练目录，其实是读写真身 `~\\.contest_generator`（`app.log` 里
    能查到 `~/.contest_generator/updates`）。现在通过一段启动 shim 把 config_path
    钉死在演练目录里。
    """
    config_path = profile / ".contest_generator" / "config.json"
    shim = (
        "import uvicorn\n"
        "from contest_generator.webapp import AppContext, create_app\n"
        "from contest_generator.webapp import resolve_port\n"
        "app = create_app(AppContext(config_path=r'{config}'))\n"
        "uvicorn.run(app, host='127.0.0.1', port=resolve_port())\n"
    ).format(config=str(config_path))
    env = dict(os.environ)
    env.update({
        "FIRSTEP_LAUNCHER_PORT": str(PORT),
        "USERPROFILE": str(profile),          # 双保险（Path.home() 在 shim 里也是重定向后的）
        "HOME": str(profile),
        "PYTHONPATH": str(tool_root / "src"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
    })
    handle = open(log_path, "a", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, "-c", shim],
        cwd=str(tool_root), env=env, stdout=handle, stderr=subprocess.STDOUT,
    )


def stop_app(proc: subprocess.Popen, *, hard: bool) -> None:
    """hard=True = 直接杀（模拟进程被杀 / 用户强制关掉）；False = 正常终止。"""
    if proc.poll() is not None:
        return
    proc.kill() if hard else proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def partials(updates_dir: Path) -> list[dict]:
    """`updates/full/` 下每个卷的落盘实况 + 边车内容。"""
    out = []
    full_dir = updates_dir / "full"
    if not full_dir.is_dir():
        return out
    for path in sorted(full_dir.iterdir()):
        if path.name.endswith(".partial.json"):
            continue
        marker = Path(str(path) + ".partial.json")
        entry = {"name": path.name, "bytes": path.stat().st_size,
                 "marker": None}
        if marker.is_file():
            try:
                entry["marker"] = json.loads(marker.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                entry["marker"] = {"坏": True}
        out.append(entry)
    return out


def dir_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return -1.0


_TRACKED: dict = {"starts": []}


def fetch_parts_directly() -> list[dict]:
    """直接读线上 release 的分卷清单（不走 app 的 check 端点）。

    为什么不走端点：那条路要一次 GitHub API 往返，实测会被限流（HTTP 500 / 超时），
    而确定性复检需要的只是「真实资产 URL + size + sha256」——release 元数据里就有。
    """
    manifest_url = ""
    proc = subprocess.run(
        ["gh", "release", "view", "v1.1.1", "--repo", "AK47n/firstep",
         "--json", "assets"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh release view 失败：{proc.stderr.strip()[:200]}")
    assets = json.loads(proc.stdout)["assets"]
    for asset in assets:
        if asset["name"].endswith(".manifest.json"):
            manifest_url = asset["url"]
    if not manifest_url:
        raise RuntimeError("release 上没有 manifest.json")
    with urllib.request.urlopen(manifest_url, timeout=60) as resp:
        manifest = json.loads(resp.read().decode("utf-8"))
    # 清单里是 `zip_name` / `size` / `sha256`；资产下载地址按同名资产解析
    # （与 `full_update._parse_parts` 同口径——别自己另发明一套）
    by_name = {a["name"]: a["url"] for a in assets}
    parts: list[dict] = []
    for item in manifest.get("parts") or []:
        name = str(item.get("zip_name") or "")
        url = by_name.get(name, "")
        if not name or not url:
            raise RuntimeError(f"清单里的分卷 {name!r} 在 release 上没有对应资产")
        parts.append({"name": name, "size": int(item.get("size") or 0),
                      "sha256": str(item.get("sha256") or ""), "url": url})
    return parts


def _tracking_download():
    """包一层下载器：记录每次尝试时盘上已有多少字节（= 该次尝试的起始偏移）。"""
    from contest_generator import download_resume

    def download(url, dest, on_progress, **kwargs):   # noqa: ANN001, ANN003
        path = Path(dest)
        _TRACKED["starts"].append(path.stat().st_size if path.is_file() else 0)
        return download_resume.resumable_download(url, dest, on_progress, **kwargs)

    return download


def run_deterministic_resume_check(parts: list[dict], work: Path) -> dict:
    """**确定性**地验「半成品 + 边车 → 真任务接着下」（不依赖「下载中途正好被杀」）。

    为什么要有这一段：上面那条「下到 25% 就杀进程」的剧本受带宽影响（实测在快网上
    25% 只要十几秒，很容易杀在下载已经完成之后，结果验不到断点）。而「重启后能不能接上」
    这条判据本身不依赖杀得多准——**只要盘上有半成品 + 边车**，真任务就该从那里接着下。

    做法：把线上真资产的前 N 字节拉到本地（真 HTTP `Range`），配上边车，然后交给
    **产品自己的 `FullDownloadTask`**（真 URL、真下载器）跑完；判据 = 下载器第一次尝试
    的起始偏移 >= 铺下去的字节数（即真的发了 `Range` 接着下），且最终校验通过。
    """
    from contest_generator.full_task import FullDownloadTask
    from contest_generator import download_resume

    part = parts[0]
    url = part["url"]
    size = int(part["size"])
    seed_bytes = 32 * 1024 * 1024          # 32 MB 就够判「有没有接着下」
    task_dir = work / "resume-check"
    dest = task_dir / "full" / part["name"]

    log("")
    log("## 七、确定性复检：铺一份「半成品 + 边车」，让真任务接着下")
    log(f"  真资产：{url}")
    log(f"  先取前 {seed_bytes / 1024 / 1024:.0f} MB（真 Range 请求）")
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"Range": f"bytes=0-{seed_bytes - 1}"})
    with urllib.request.urlopen(request, timeout=180) as resp:
        seed = resp.read()
    dest.write_bytes(seed)
    marker = download_resume.write_partial_marker(dest, url, size)
    log(f"  铺好：{dest.stat().st_size / 1024 / 1024:.1f} MB + 边车 {marker.name}")

    task = FullDownloadTask(
        task_dir=task_dir,
        parts=[{"name": part["name"], "url": url, "size": size,
                "sha256": part["sha256"]}],
        snapshot_interval=2.0,
    )
    task._download = _tracking_download()
    t0 = time.time()
    task.run()
    elapsed = time.time() - t0
    observed = list(_TRACKED["starts"])
    log(f"  state={task.state.value} / 用时 {elapsed:.1f}s / "
        f"下载器每次尝试的起始偏移 {observed}")
    log(f"  卷状态：ok={task.parts[0].ok} / downloaded_bytes={task.parts[0].downloaded_bytes}")
    resumed = bool(observed and observed[0] >= seed_bytes)
    log(f"  → **从断点接着下**：{'成立' if resumed else '不成立'}（第一次尝试起始偏移 "
        f"{observed[0] if observed else '（没记录到）'}）")
    return {
        "seed_bytes": seed_bytes,
        "state": task.state.value,
        "attempt_starts": observed,
        "resumed_from_offset": resumed,
        "ok": task.parts[0].ok,
        "error": task.error[:200],
        "seconds": round(elapsed, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="跑完不删演练目录（排查用）")
    parser.add_argument("--fraction", type=float, default=0.25,
                        help="下到完整包的这个比例就杀掉进程（默认 25%%）")
    parser.add_argument("--resume-check-only", action="store_true",
                        help="只跑确定性续传复检（不起服务、不碰 GitHub check 端点）")
    args = parser.parse_args()

    real_tree = REPO
    real_data = Path.home() / ".contest_generator"
    real_data_mtime_before = dir_mtime(real_data)

    log("# 工单 06 档③ 证据：真实完整包端到端（resumable-download/06）")
    log("")
    log(f"真身工作树（**只读，绝不改**）：{real_tree}")
    log(f"真身数据目录（**只读，绝不改**）：{real_data}"
        f"（mtime={real_data_mtime_before}）")
    log("")

    work = Path(tempfile.mkdtemp(prefix="firstep-tier3-"))
    tool_root = work / "tool"
    profile = work / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    log(f"一次性演练目录：{work}")
    log("")

    if args.resume_check_only:
        # 只跑确定性那一段（不起服务、不依赖「下载中途被杀」）——GitHub 的
        # check 端点会限流/抖动，这段不碰它，能独立复现。
        # 网络不可达时**如实降级**（不把「网挂了」写成「功能坏了」）。
        try:
            try:
                parts = fetch_parts_directly()
            except Exception as exc:  # noqa: BLE001 —— 网络原因就如实说
                log(f"  **取不到线上分卷清单**（{type(exc).__name__}: {exc}）")
                log("  → 这一段要访问 GitHub；本机此刻连不上，**未验**（不是功能坏了）。")
                RESULTS["resume_check"] = {"skipped": "network-unreachable",
                                           "error": f"{type(exc).__name__}: {exc}"[:200]}
                RESULTS["verdict"] = {"resumed_from_offset": None, "verified": None}
            else:
                log(f"取到分卷：{parts[0]['name']} / "
                    f"{int(parts[0]['size']) / 1024 / 1024:.0f} MB")
                RESULTS["parts"] = [{"name": p["name"], "size": p["size"]} for p in parts]
                RESULTS["resume_check"] = run_deterministic_resume_check(parts, work)
                RESULTS["verdict"] = {
                    "resumed_from_offset": RESULTS["resume_check"]["resumed_from_offset"],
                    "verified": RESULTS["resume_check"]["ok"],
                }
        finally:
            if args.keep:
                log(f"\n（--keep：演练目录保留在 {work}）")
            else:
                shutil.rmtree(work, ignore_errors=True)
                log("\n演练目录已清理")
        (HERE / "verify-06-tier3-resume.txt").write_text(
            "\n".join(LINES) + "\n", encoding="utf-8")
        (HERE / "verify-06-tier3.json").write_text(
            json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
        print("证据已写：verify-06-tier3-resume.txt / verify-06-tier3.json")
        if RESULTS["verdict"]["resumed_from_offset"] is None:
            return 2                      # 网络不可达：既不算通过也不算失败
        return 0 if RESULTS["verdict"]["resumed_from_offset"] else 1

    try:
        # 1) 复制源码成一次性工具根（更新器替换的是它，不是真身）
        log("## 一、准备一次性工具根（src 复制，真身零触碰）")
        t0 = time.time()
        shutil.copytree(real_tree / "src", tool_root / "src",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # 更新器与前端要的东西：静态资源在 src 里；VERSIONS.md / 资料库基线按需
        for extra in ("VERSIONS.md", "README.md", "requirements.txt", "pyproject.toml"):
            source = real_tree / extra
            if source.is_file():
                shutil.copy2(source, tool_root / extra)
        log(f"复制完成：{sum(1 for _ in (tool_root / 'src').rglob('*'))} 个条目，"
            f"{time.time() - t0:.1f}s")
        log("")

        data_dir = profile / ".contest_generator"
        updates_dir = data_dir / "updates"
        log_path = work / "app.log"

        # 2) 第一次启动 + 检查更新（拿分卷清单与 URL）
        log("## 二、起服务（8020）→ 检查更新（真打 GitHub）")
        proc = start_app(tool_root, profile, log_path)
        if not wait_health():
            log("服务没起来——见 app.log")
            log(log_path.read_text(encoding="utf-8", errors="replace")[-2000:])
            return 1
        log(f"服务已就绪：{BASE}")
        check = api_retry("/api/update/full/check", timeout=180)
        parts = check.get("parts") or []
        total = sum(int(p.get("size") or 0) for p in parts)
        log(f"最新版本：{check.get('latest_version')} / 分卷 {len(parts)} 个 / 合计 "
            f"{total / 1024 / 1024:.0f} MB / error={check.get('error')!r}")
        RESULTS["check"] = {k: check.get(k) for k in
                            ("latest_version", "current_version", "update_available",
                             "error", "manifest_url")}
        RESULTS["parts"] = [{"name": p["name"], "size": p["size"]} for p in parts]
        if not parts:
            log("**没有可用分卷**（线上没有完整包资产或检查失败）——档③ 无法进行，如实记账。")
            stop_app(proc, hard=False)
            return 0

        # 3) 开始下载 → 跑到 fraction 就**杀掉进程**（模拟中途断掉）
        log("")
        log(f"## 三、开始下载 → 下到约 {int(args.fraction * 100)}% 时杀掉进程（模拟中途断掉）")
        api_retry("/api/update/full/apply", {"parts": [p["name"] for p in parts]})
        total_bytes = sum(int(p["size"]) for p in parts)
        target = int(total_bytes * args.fraction)
        deadline = time.time() + 900
        last = 0
        killed_at = None
        while time.time() < deadline:
            status = api("/api/update/full/status")
            got = status["total_downloaded_bytes"]
            if status["state"] in ("failed", "cancelled", "done", "applying"):
                log(f"  **下载提前结束了**：state={status['state']} "
                    f"error={status['error'][:120]!r}（没来得及杀）")
                break
            if got >= target:
                killed_at = got
                break
            if got - last > 16 * 1024 * 1024:
                log(f"  进度 {got / 1024 / 1024:.1f} MB / 目标 {target / 1024 / 1024:.1f} MB")
                last = got
            time.sleep(1.0)
        status = api("/api/update/full/status")
        if killed_at is None:
            log(f"杀掉前：state={status['state']} 已下 "
                f"{status['total_downloaded_bytes'] / 1024 / 1024:.1f} MB"
                f"（{status['total_downloaded_bytes'] * 100 // max(1, status['total_bytes'])}%）")
        before_kill = partials(updates_dir)
        RESULTS["phase1"] = {"status": {k: status[k] for k in
                                        ("state", "total_downloaded_bytes", "total_bytes",
                                         "parts")},
                             "files": before_kill,
                             "killed_at_bytes": killed_at}
        bytes_before_kill = before_kill[0]["bytes"] if before_kill else (killed_at or 0)
        RESULTS["phase1"]["bytes_before_kill"] = bytes_before_kill
        stop_app(proc, hard=True)
        time.sleep(2.0)
        log(f"进程已杀（模拟「用户关掉工具 / 进程被结束」）——盘上 {bytes_before_kill / 1024 / 1024:.1f} MB")

        # 4) 看盘上留下什么：半成品 + 边车
        log("")
        log("## 四、杀完之后盘上留下什么（这份就是「断点」）")
        left = partials(updates_dir)
        if not left:
            log("  **盘上没有留下任何半成品**（下载在杀之前就结束并清理了）"
                "——这一轮验不到断点，见上面的「下载提前结束」。")
        for entry in left:
            marker = entry["marker"] or {}
            log(f"  · {entry['name']}：{entry['bytes'] / 1024 / 1024:.1f} MB，"
                f"边车={'有' if entry['marker'] else '**无**'}"
                f"（url={str(marker.get('url'))[:56]}…, "
                f"expected_size={marker.get('expected_size')}）")
        RESULTS["after_kill"] = left

        # 5) 重启服务 → 再点一次下载：应当**从断点接着下**
        log("")
        log("## 五、重启服务 → 再点一次下载（应当从断点接着下）")
        proc = start_app(tool_root, profile, log_path)
        if not wait_health():
            log("重启失败——见 app.log")
            return 1
        check2 = api_retry("/api/update/full/check", timeout=180)
        log(f"重启后检查：latest={check2.get('latest_version')} "
            f"分卷 {len(check2.get('parts') or [])} 个")
        api_retry("/api/update/full/apply", {"parts": [p["name"] for p in parts]})
        resumed_seen = False
        first_poll: dict | None = None
        min_seen = None
        before_kill_bytes = RESULTS["phase1"]["bytes_before_kill"]
        deadline = time.time() + 3600          # 783 MB：给足时间
        last = 0
        while time.time() < deadline:
            status = api("/api/update/full/status")
            got = status["total_downloaded_bytes"]
            if first_poll is None:
                first_poll = {"downloaded": got, "total": status["total_bytes"],
                              "message": status.get("message", "")}
                log(f"  重启后第一次轮询：已下 {got / 1024 / 1024:.1f} MB"
                    f"（{got * 100 // max(1, status['total_bytes'])}%）"
                    f" / 摘要={status.get('message', '')[:80]!r}")
                log(f"  杀掉前盘上是 {before_kill_bytes / 1024 / 1024:.1f} MB"
                    f" → {'**从断点接着下**' if got >= before_kill_bytes else '**从 0 重下**'}")
            min_seen = got if min_seen is None else min(min_seen, got)
            if status.get("message"):
                log(f"  状态摘要：{status['message'][:100]}")
                if "接着" in status["message"]:
                    resumed_seen = True
            if status["state"] in ("applying", "done", "failed", "cancelled"):
                break
            if got - last > 32 * 1024 * 1024:
                log(f"  进度 {got / 1024 / 1024:.1f} MB "
                    f"（{got * 100 // max(1, status['total_bytes'])}%）")
                last = got
            time.sleep(2.0)
        final = api("/api/update/full/status")
        log(f"终态：state={final['state']} / 已下 "
            f"{final['total_downloaded_bytes'] / 1024 / 1024:.0f} MB"
            f"（{final['total_downloaded_bytes'] * 100 // max(1, final['total_bytes'])}%）"
            f" / error={final['error'][:200]!r}")
        RESULTS["phase2"] = {
            "state": final["state"],
            "downloaded": final["total_downloaded_bytes"],
            "total": final["total_bytes"],
            "error": final["error"],
            "message": final.get("message", ""),
            "resume_message_seen": resumed_seen,
            "first_poll": first_poll,
            "min_downloaded_seen": min_seen,
            "bytes_before_kill": before_kill_bytes,
            "files": partials(updates_dir),
        }

        # 6) 完成判据
        log("")
        log("## 六、完成判据")
        applied = final["state"] in ("applying", "done")
        phase2 = RESULTS["phase2"]
        resumed = bool(phase2["min_downloaded_seen"] is not None
                       and phase2["bytes_before_kill"] > 0
                       and phase2["min_downloaded_seen"] >= phase2["bytes_before_kill"])
        log(f"- **重启后从断点接着下**：{'成立' if resumed else '**不成立**'}"
            f"（杀掉前 {phase2['bytes_before_kill'] / 1024 / 1024:.1f} MB；"
            f"重启后最低水位 {phase2['min_downloaded_seen'] / 1024 / 1024:.1f} MB；"
            f"第一次轮询 {phase2['first_poll']['downloaded'] / 1024 / 1024:.1f} MB）")
        log(f"- 下载走完并交给替换流程：{'成立' if applied else '**不成立**'}"
            f"（state={final['state']}）")
        if applied:
            log("  更新器以独立进程跑（停服 → 备份 → 覆盖 → 重启），本脚本只等到这里；")
            log(f"  演练工具根的更新器日志落点：{updates_dir}")
        else:
            log(f"  替换流程没走完，错误：{final['error'][:200]!r}")
        time.sleep(5.0)
        version_file = tool_root / "src" / "contest_generator" / "__init__.py"
        version = ""
        if version_file.is_file():
            for line in version_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("__version__"):
                    version = line.strip()
                    break
        log(f"- 更换后的工具根版本：{version or '（还没换完 / 没读到）'}")
        real_data_mtime_after = dir_mtime(real_data)
        unchanged = real_data_mtime_after == real_data_mtime_before
        log(f"- 真身数据目录 mtime 未变：{'成立' if unchanged else '**变了**'}"
            f"（{real_data_mtime_before} → {real_data_mtime_after}）")
        RESULTS["verdict"] = {
            "resumed_from_offset": resumed,
            "applied": applied,
            "version": version,
            "real_data_untouched": unchanged,
            "resume_message_seen": phase2["resume_message_seen"],
            "bytes_before_kill": phase2["bytes_before_kill"],
            "min_downloaded_seen": phase2["min_downloaded_seen"],
        }
        stop_app(proc, hard=False)
    finally:
        if args.keep:
            log(f"\n（--keep：演练目录保留在 {work}）")
        else:
            shutil.rmtree(work, ignore_errors=True)
            log("\n演练目录已清理")

    (HERE / "verify-06-tier3.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
    (HERE / "verify-06-tier3.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print("证据已写：verify-06-tier3.txt / .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())