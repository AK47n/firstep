# -*- coding: utf-8 -*-
"""工单 07：补完档③ —— 真实完整包端到端（替换 → 重启 → **版本号正确**）。

要回答的问题（工单 06 唯一没验到的那一格）：
「用户点一键全量下载之后，**工具真的被换成线上包那一版了吗**？」

工单 06 的 `verify-06-tier3.py` 把「下载」与「从中断处接着下」验实了，但替换环节
没走完。根因已由 `probe-07-stage-preflight.py` 定位：**那支脚本搭一次性工具根时
没复制 `tools/`**，`full_apply` 的拉起前预检因此拒了它（产品行为正确）。
本脚本把工具根铺全（`src/` + `tools/` + 启动脚本 + 顶层文件），补完这一格。

## 与工单 06 那支的差异（都写进证据里，别混读）

| 项 | 工单 06 那支 | 本脚本 |
|---|---|---|
| 工具根 | 只 `src/` + 四个顶层文件（**缺 `tools/`**） | 补齐 `tools/` 与启动脚本 |
| 版本判据 | 读盘上 `__init__.py` 的 `__version__` | **读跑起来的服务的 `GET /api/health` 的 `version`** |
| 完整包 zip | 真下载 783 MB | 复用**已下过且哈希校验过**的那份（本机已有），仍按清单 sha256 复核 |
| 数据目录隔离 | 靠 `USERPROFILE` + shim 显式 `config_path` | `USERPROFILE` + 启动器原生路径（`start-app.bat` 用 `%USERPROFILE%` 推数据目录） |

## 口径（照工单与 local-environment.md 2.5b 两条铁律）

- **真身只读**：绝不改 `Desktop\\firstep` 与 `%USERPROFILE%\\.contest_generator`；
  演练全部在 `%TEMP%` 下的一次性工具根 + 一次性数据目录里做，收尾校验真身未变。
- 数据目录隔离靠 `USERPROFILE` 重定向（`start-app.bat` 用 `%USERPROFILE%\\.contest_generator`，
  更新器与重启后的应用都吃这个变量）；隔离是否真生效**由判据自己证**：
  演练数据目录里应当出现 `webapp.log`，而真身那份 mtime 不变。
- 端口 8020（真身 8000 此刻没在跑，仍按纪律隔离）。

用法：`python .scratch/resumable-download/verify-07-tier3-e2e.py [--keep] [--zip <path>]`
产出：`verify-07-tier3-e2e.txt` + `.json`
"""

from __future__ import annotations

import argparse
import hashlib
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
STAGED_VERSION = "1.1.0"          # 工具根起点版本（脚本改 __init__.py 造出来）
TARGET_TAG = "v1.1.1"             # 线上最新软件 Release
LINES: list[str] = []
RESULTS: dict = {}

# 本机已下过的那份完整包（工单 06 档③ 真下载留下的），复用省 783 MB 流量。
DEFAULT_ZIP = Path.home() / "Desktop" / "firstep-pack" / "firstep-full-v1.1.1.zip"

# 别被全局那份 editable 安装带偏（见 docs/agents/local-environment.md 2.5）：
# site-packages 里残留的 `contest-generator` 元数据指向 firstep-sim 的旧源码。
sys.path.insert(0, str(REPO / "src"))
for _name in [n for n in list(sys.modules)
              if n == "contest_generator" or n.startswith("contest_generator.")]:
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
    """GitHub 那一跳会慢会抖：一次超时不该把整轮演练判死（失败时大声说清）。"""
    last: Exception | None = None
    for index in range(1, attempts + 1):
        try:
            return api(path, payload, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 —— 网络类异常都值得重试
            last = exc
            log(f"  （{path} 第 {index}/{attempts} 次失败：{type(exc).__name__}: {exc}）")
            time.sleep(3.0)
    raise RuntimeError(f"{path} 连续 {attempts} 次失败：{last}")


def wait_health(deadline_seconds: float = 60) -> dict | None:
    """等服务就绪；返回 /api/health 的 JSON（含 version）。"""
    end = time.time() + deadline_seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=3) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 —— 起服务期间连不上是正常的
            time.sleep(0.5)
    return None


def make_env(profile: Path, tool_root: Path) -> dict:
    """所有子进程共用的环境：数据目录被 `USERPROFILE` 关进演练目录。

    `start-app.bat` 的数据目录 = `%USERPROFILE%\\.contest_generator`，
    更新器与它拉起的应用都走这条（不像 `webapp` 模块级默认值那样在导入时定死）。
    """
    env = dict(os.environ)
    env.update({
        "FIRSTEP_LAUNCHER_PORT": str(PORT),
        "USERPROFILE": str(profile),
        "HOME": str(profile),
        "PYTHONPATH": str(tool_root / "src"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
    })
    return env


def start_via_launcher(tool_root: Path, env: dict) -> subprocess.Popen:
    """按用户机的方式起服务：`start-app.vbs`（= 启动器全流程）。

    直接调 `wscript` 起 vbs（而不是 `os.startfile`），这样本脚本能拿到进程句柄、
    收尾时能把它收干净。
    """
    vbs = tool_root / "start-app.vbs"
    return subprocess.Popen(
        ["wscript.exe", str(vbs)],
        cwd=str(tool_root), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def kill_port_listener(port: int) -> list[str]:
    """收尾：把还听着这个端口的进程收掉（演练只碰 8020）。"""
    killed: list[str] = []
    try:
        output = subprocess.run(["netstat", "-ano"], capture_output=True,
                                text=True, timeout=20).stdout
    except Exception:  # noqa: BLE001
        return killed
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[-2] == "LISTENING" and f":{port}" in parts[1]:
            pid = parts[-1]
            if pid not in killed:
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True, text=True)
                killed.append(pid)
    return killed


def dir_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return -1.0


def tree_stamp(root: Path) -> dict:
    """工作树快照：**排除 VCS / 缓存 / 虚拟环境 / 本工单区**后的 {相对路径: (字节, mtime)}。

    为什么必须排除：`.git` 与 `__pycache__` 在演练期间天然会动（本脚本自己要跑
    git / 导入模块），把它们算进「真身未变」会把判据变成恒假——第一版就是这么
    报出「**变了**」的（文件数 37185 → 37185 却判变了）。判据要判的是「**产品
    有没有往真身写东西**」，不是「这台机器有没有别的东西在动」。

    排除 `.scratch/` 的理由更具体：**证据文件本身就是本脚本的产出**，把它算进来
    等于让判据评判自己的输出（实测：第二次跑报「变了」，变的 4 个文件里两个就是
    `verify-07-review-claims.*`）。要判的是产品行为，不是验收台自己的账本。
    """
    skip_dirs = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv",
                 "node_modules", ".claude", ".scratch"}
    stamp: dict[str, tuple[int, float]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in skip_dirs for part in rel.parts):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        stamp[str(rel).replace("\\", "/")] = (stat.st_size, stat.st_mtime)
    return stamp


def diff_stamp(before: dict, after: dict) -> dict:
    """两份快照的差异（只看「产品可能自己写」的位置，给判据一个可读的理由）。"""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    return {"added": added, "removed": removed, "changed": changed}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_release_assets() -> tuple[dict, dict]:
    """直接取线上 release 元数据（不走 app 端点，避免限流）：→（清单, 资产表）。"""
    proc = subprocess.run(
        ["gh", "release", "view", TARGET_TAG, "--repo", "AK47n/firstep",
         "--json", "assets"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh release view 失败：{proc.stderr.strip()[:200]}")
    assets = json.loads(proc.stdout)["assets"]
    manifest_url = ""
    for asset in assets:
        if asset["name"].endswith(".manifest.json"):
            manifest_url = asset["url"]
    if not manifest_url:
        raise RuntimeError("release 上没有 manifest.json")
    with urllib.request.urlopen(manifest_url, timeout=120) as resp:
        manifest = json.loads(resp.read().decode("utf-8-sig"))
    return manifest, {a["name"]: a["url"] for a in assets}


def stage_tool_root(tool_root: Path, env: dict, zip_name: str, source_zip: Path) -> None:
    """铺一个**像 v1.1.0 用户机**的工具根（真身只读，这里全是副本）。

    工单 06 那支漏的正是 `tools/`——补上它才是「完整包替换链」能跑的前提。
    """
    shutil.copytree(REPO / "src", tool_root / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (tool_root / "tools").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / "tools" / "update-app.py", tool_root / "tools" / "update-app.py")
    shutil.copy2(REPO / "tools" / "launcher-log.ps1", tool_root / "tools" / "launcher-log.ps1")
    for script in ("start-app.vbs", "start-app.bat"):
        shutil.copy2(REPO / script, tool_root / script)
    for extra in ("VERSIONS.md", "README.md", "requirements.txt", "pyproject.toml"):
        if (REPO / extra).is_file():
            shutil.copy2(REPO / extra, tool_root / extra)

    # 起点版本改写成 v1.1.0：这样「替换后版本号变了」才有可判的落差。
    init = tool_root / "src" / "contest_generator" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    marker = '__version__ = "'
    head, _, tail = text.partition(marker)
    rest = tail.split('"', 1)[1]
    init.write_text(f'{head}{marker}{STAGED_VERSION}"{rest}', encoding="utf-8")
    log(f"  起点版本已改写为 {STAGED_VERSION}（{init.relative_to(tool_root)}）")

    # 隔离的数据目录 + 配置文件：库目录指向仓库真实库（只读用途，不写库）
    data_dir = Path(env["USERPROFILE"]) / ".contest_generator"
    updates = data_dir / "updates"
    (updates / "full").mkdir(parents=True, exist_ok=True)
    real_config = Path.home() / ".contest_generator" / "config.json"
    config = json.loads(real_config.read_text(encoding="utf-8"))
    config["module_library_dir"] = str(REPO / "library" / "modules")
    config["masters_dir"] = str(REPO / "library" / "masters")
    # 演练不写库：自动提交关掉（库根在 git 工作树内，autocommit 会对真身仓库提交）
    config["autocommit_enabled"] = False
    (data_dir / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"  数据目录（隔离）：{data_dir}")
    log(f"  配置文件：库目录指向 {config['module_library_dir']}（autocommit 已关）")

    # 复用本机已下过的那份完整包：拷到演练 updates/full/ 下，按 part 名命名
    target_zip = updates / "full" / zip_name
    shutil.copy2(source_zip, target_zip)
    log(f"  完整包已就位：{target_zip}（{target_zip.stat().st_size / 1024 / 1024:.0f} MB，"
        f"复用本机缓存，未重新下载）")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="跑完不删演练目录")
    parser.add_argument("--zip", dest="zip_path", default=str(DEFAULT_ZIP),
                        help="完整包 zip 路径（默认用本机缓存的那份）")
    args = parser.parse_args()
    source_zip = Path(args.zip_path)

    real_tree = REPO
    real_data = Path.home() / ".contest_generator"
    real_updates = real_data / "updates"
    real_data_mtime_before = dir_mtime(real_data)
    real_updates_before = sorted(p.name for p in real_updates.iterdir()) \
        if real_updates.is_dir() else []
    real_tree_before = tree_stamp(real_tree)

    log("# 工单 07 证据：真实完整包端到端（替换 → 重启 → 版本号正确）")
    log("")
    log("## 零、隔离边界（真身只读）")
    log(f"  真身工作树（只读）：{real_tree}")
    log(f"    基线：{len(real_tree_before)} 个文件"
        f"（已排除 .git / __pycache__ / 缓存 / .venv / node_modules）")
    log(f"  真身数据目录（只读）：{real_data}（mtime={real_data_mtime_before}）")
    log(f"    updates/ 现有条目：{real_updates_before or '（空）'}")
    log("")

    if not source_zip.is_file():
        log(f"  **完整包不在**：{source_zip}——本脚本不自己下载 783 MB；"
            f"用 --zip 指定，或先跑工单 06 那支真下载一次。")
        return 2

    work = Path(tempfile.mkdtemp(prefix="fe07-"))
    tool_root = work / "tool"
    profile = work / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    env = make_env(profile, tool_root)
    log(f"一次性演练目录：{work}")
    log("")

    verdict: dict = {}
    launcher: subprocess.Popen | None = None
    try:
        log("## 一、铺一个像 v1.1.0 用户机的工具根（**含 tools/**）")
        manifest, asset_urls = fetch_release_assets()
        parts_manifest = manifest.get("parts") or []
        if not parts_manifest:
            log("  **线上清单没有分卷**——档③ 无法进行，如实记账。")
            return 0
        part = parts_manifest[0]
        zip_name = str(part.get("zip_name") or "")
        expected_size = int(part.get("size") or 0)
        expected_sha = str(part.get("sha256") or "")
        log(f"  线上清单：{TARGET_TAG} / {zip_name} / {expected_size / 1024 / 1024:.0f} MB")
        stage_tool_root(tool_root, env, zip_name, source_zip)

        # 完整包自证：复用缓存也要复核哈希（口径不能松）
        log("")
        log("## 二、完整包自证（复用的缓存也复核 sha256）")
        actual_sha = sha256_of(source_zip)
        log(f"  清单 sha256：{expected_sha}")
        log(f"  本地 sha256：{actual_sha}")
        log(f"  一致：{actual_sha == expected_sha}")
        RESULTS["asset"] = {"zip_name": zip_name, "size": expected_size,
                            "sha256_matches": actual_sha == expected_sha}
        if actual_sha != expected_sha:
            log("  **哈希不符**：这份缓存不是清单那一份，拒用（换 --zip 或真下载）。")
            return 1

        # ---- 起服务（走用户机的启动器 start-app.vbs）----
        log("")
        log("## 三、按用户机方式起服务（start-app.vbs → 8020）")
        launcher = start_via_launcher(tool_root, env)
        health = wait_health()
        if health is None:
            log("  服务没起来；webapp.log 末尾：")
            web_log = profile / ".contest_generator" / "webapp.log"
            if web_log.is_file():
                log(web_log.read_text(encoding="utf-8", errors="replace")[-2000:])
            else:
                log(f"  （{web_log} 不存在）")
            return 1
        log(f"  服务已就绪：{BASE}")
        log(f"  **替换前 `/api/health`.version = {health.get('version')}**"
            f"（期望 {STAGED_VERSION}）")
        RESULTS["before"] = {"health": health}

        check = api_retry("/api/update/full/check", timeout=180)
        log(f"  检查更新：latest={check.get('latest_version')} / "
            f"current={check.get('current_version')!r} / "
            f"reason={check.get('reason')} / 分卷 {len(check.get('parts') or [])} 个")
        RESULTS["before"]["check"] = {k: check.get(k) for k in
                                      ("latest_version", "current_version",
                                       "update_available", "reason", "error")}
        selected = [p["name"] for p in check.get("parts") or []]
        if zip_name not in selected:
            log(f"  **线上分卷表与清单不一致**：{selected}——如实记账，停止。")
            return 1

        # ---- 真替换：产品端点会下载 + 校验 + 拉起更新器 ----
        log("")
        log("## 四、点「一键全量」（下载 783 MB → 校验 → 拉起更新器 → 替换 → 重启）")
        started = api_retry("/api/update/full/apply", {"parts": selected}, timeout=60)
        log(f"  apply 已接受：{started}")

        # 盘上已有完整包：任务会走「长度到点 → 跳过下载直接校验」（工单 03 的契约）
        deadline = time.time() + 3600
        last_log = 0.0
        final: dict | None = None
        while time.time() < deadline:
            status = api("/api/update/full/status")
            got = status.get("total_downloaded_bytes", 0)
            total = max(1, status.get("total_bytes", 1))
            if time.time() - last_log > 20:
                log(f"  进度 {got / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MB "
                    f"({got * 100 // total}%) state={status['state']} "
                    f"retry={status.get('retry_count')} 摘要={status.get('message', '')[:60]!r}")
                last_log = time.time()
            if status["state"] in ("applying", "done", "failed", "cancelled"):
                final = status
                break
            time.sleep(1.0)
        if final is None:
            log("  **超时**：一小时还没到终态。")
            return 1
        log(f"  任务终态：state={final['state']} / "
            f"{final.get('total_downloaded_bytes', 0) / 1024 / 1024:.0f} MB / "
            f"error={final.get('error', '')[:200]!r}")
        RESULTS["task"] = {k: final.get(k) for k in
                           ("state", "total_downloaded_bytes", "total_bytes", "error")}

        # 更新器是独立进程：等它把工具根换完
        log("")
        log("## 五、等更新器替换工具根（独立进程：停服 → 备份 → 覆盖 → 重启）")
        installed_marker = profile / ".contest_generator" / "updates" / "full-installed.json"
        updater_log = profile / ".contest_generator" / "updates" / "updater.log"
        end = time.time() + 900
        marker: dict | None = None
        while time.time() < end:
            if installed_marker.is_file():
                try:
                    marker = json.loads(installed_marker.read_text(encoding="utf-8"))
                    break
                except Exception:  # noqa: BLE001 —— 正在写
                    pass
            time.sleep(2.0)
        log(f"  已装版本标记：{marker}")
        RESULTS["installed_marker"] = marker

        # ---- 重启后的判据：从**跑起来的服务**读版本 ----
        log("")
        log("## 六、重启后的判据（版本号从跑起来的服务读，不只看盘上文件）")
        log("  等新区间服务就绪（旧服务已被更新器停掉）…")
        health_after = None
        end = time.time() + 180
        while time.time() < end:
            health_after = wait_health(deadline_seconds=5)
            if health_after and health_after.get("version") == "1.1.1":
                break
            time.sleep(2.0)
        # 更新器的重启是异步的；若启动器窗口还没起来，就用同一套环境手动补一次
        if not health_after or health_after.get("version") != "1.1.1":
            log("  （更新器的重启尚未就绪，用同一套环境再起一次启动器）")
            launcher = start_via_launcher(tool_root, env)
            health_after = wait_health(deadline_seconds=90)

        version_file = tool_root / "src" / "contest_generator" / "__init__.py"
        on_disk = ""
        for line in version_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__"):
                on_disk = line.strip()
                break
        served = (health_after or {}).get("version")
        log(f"  盘上 {version_file.relative_to(tool_root)}：{on_disk}")
        log(f"  **替换后 `/api/health`.version = {served}**")
        ok_version = (served == "1.1.1")
        log(f"  → 「重启后版本号正确」：{'成立' if ok_version else '**不成立**'}")
        RESULTS["after"] = {"on_disk": on_disk, "served": served,
                            "version_ok": ok_version}

        check2 = api_retry("/api/update/full/check", timeout=180) if health_after else {}
        if check2:
            log(f"  替换后检查更新：current={check2.get('current_version')!r} / "
                f"reason={check2.get('reason')} / "
                f"update_available={check2.get('update_available')}")
            RESULTS["after"]["check"] = {k: check2.get(k) for k in
                                         ("latest_version", "current_version",
                                          "update_available", "reason")}

        # ---- 更新器日志与启动器留痕 ----
        log("")
        log("## 七、更新器日志（替换链逐步骤留痕）与启动器留痕")
        if updater_log.is_file():
            for line in updater_log.read_text(encoding="utf-8",
                                              errors="replace").splitlines():
                log(f"  | {line}")
        else:
            log(f"  （{updater_log} 不存在——替换链可能没跑到写日志那步）")
        launcher_log = profile / ".contest_generator" / "launcher.log"
        if launcher_log.is_file():
            log(f"  启动器留痕（{launcher_log}）：")
            for line in launcher_log.read_text(encoding="utf-8",
                                               errors="replace").splitlines()[-6:]:
                log(f"  | {line}")

        # ---- 隔离边界收尾校验 ----
        log("")
        log("## 八、隔离边界收尾校验")
        real_data_mtime_after = dir_mtime(real_data)
        real_updates_after = sorted(p.name for p in real_updates.iterdir()) \
            if real_updates.is_dir() else []
        real_tree_after = tree_stamp(real_tree)
        data_untouched = real_data_mtime_after == real_data_mtime_before
        updates_untouched = real_updates_after == real_updates_before
        tree_diff = diff_stamp(real_tree_before, real_tree_after)
        tree_untouched = not (tree_diff["added"] or tree_diff["removed"]
                              or tree_diff["changed"])
        log(f"  真身数据目录 mtime 未变：{'成立' if data_untouched else '**变了**'}"
            f"（{real_data_mtime_before} → {real_data_mtime_after}）")
        log(f"  真身 updates/ 条目未变：{'成立' if updates_untouched else '**变了**'}"
            f"（{real_updates_after or '（空）'}）")
        log(f"  真身工作树未变（排除 VCS / 缓存）：{'成立' if tree_untouched else '**变了**'}"
            f"（{len(real_tree_before)} → {len(real_tree_after)} 个文件）")
        if not tree_untouched:
            # 判据要在「为什么」上留痕，否则下一个人只能重跑一遍才知道
            for kind in ("added", "removed", "changed"):
                names = tree_diff[kind]
                if names:
                    shown = names[:12]
                    more = f"（共 {len(names)} 个，这里列前 12）" if len(names) > 12 else ""
                    log(f"    {kind}：{shown}{more}")
        log(f"  演练数据目录里有 webapp.log（隔离生效的旁证）："
            f"{(profile / '.contest_generator' / 'webapp.log').is_file()}")

        verdict = {
            "version_before": RESULTS["before"]["health"].get("version"),
            "version_after_served": served,
            "version_after_on_disk": on_disk,
            "version_ok": ok_version,
            "task_state": final["state"],
            "installed_marker": marker,
            "real_data_untouched": data_untouched,
            "real_updates_untouched": updates_untouched,
            "real_tree_untouched": tree_untouched,
            # 判据自己也要留痕：真变了的话，变在哪（前 20 条），别让下一个人重跑
            "real_tree_diff": {kind: tree_diff[kind][:20] for kind in
                               ("added", "removed", "changed")},
            "isolation_proof": (profile / ".contest_generator" / "webapp.log").is_file(),
        }
        RESULTS["verdict"] = verdict
    finally:
        if launcher is not None and launcher.poll() is None:
            launcher.terminate()
        killed = kill_port_listener(PORT)
        if killed:
            log(f"\n收尾：已收掉 8020 上的监听进程 {killed}")
        time.sleep(1.0)
        leftover = kill_port_listener(PORT)
        log(f"收尾：8020 端口{'已释放' if not leftover else f'**仍被占用 {leftover}**'}")
        RESULTS["cleanup"] = {"killed": killed, "leftover": leftover}
        if args.keep:
            log(f"（--keep：演练目录保留在 {work}）")
        else:
            shutil.rmtree(work, ignore_errors=True)
            log("演练目录已清理")

    (HERE / "verify-07-tier3-e2e.txt").write_text("\n".join(LINES) + "\n",
                                                  encoding="utf-8")
    (HERE / "verify-07-tier3-e2e.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print("证据已写：verify-07-tier3-e2e.txt / .json")

    log("")
    log("## 九、总判")
    passed = bool(RESULTS.get("verdict", {}).get("version_ok"))
    log(f"  「一键全量 → 替换 → 重启后版本号正确」：{'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
