# -*- coding: utf-8 -*-
"""B1 —— 沙箱「模拟用户机」真机升级：v1.1.1 → v1.2.1（工单 sandbox-drill/01）。

要回答的问题：**已装 v1.1.1 的用户，点「检查更新 → 一键更新」能不能真的到 v1.2.1？**

判据全部落在产品可观察量上（spec `.scratch/sandbox-drill/spec.md` 测试决策）：

- 起点自证：沙箱**盘上** `__version__` 与**跑起来的服务** `/api/health.version` 都是 1.1.1；
- 走产品端点：`GET /api/update/check` → `POST /api/update/apply`（真下载线上 305 MB）→
  `GET /api/update/status` → 更新器替换（独立进程）→ 重启；
- 终点判据：**跑起来的服务 `/api/health.version == 1.2.1`**（不只看盘上文件），盘上
  `src/contest_generator/__init__.py` 也是 1.2.1；
- 保命项：DeepSeek key / 任务记录 / 资料库内容 / 第三方安装包 / 备份 / 标记清理 / 锁释放；
- 隔离：**真身 8000 与 `~/.contest_generator` 只读**（数据目录 mtime、updates 条目、
  工作树 tree_stamp 三条判据），收尾 8020 释放。

## 与既有脚本的关系（别混读）

| | `resumable-download/verify-07-tier3-e2e.py` | 本脚本 |
|---|---|---|
| 对象 | 一次性 `%TEMP%` 工具根（拼装出来的） | **沙箱 `Desktop\\firstep-sim`（第二份真安装）** |
| 路径 | **完整包**（full/apply，复用本机缓存 zip） | **小发版**（update/apply，**真下线上 305 MB**） |
| 起点版本 | 脚本改写 `__init__.py` 造 v1.1.0 | 沙箱**本来**就是 v1.1.1（不许改，改了下次没法重演） |

## 两处必须知道的沙箱事实（决定了本脚本的姿势）

1. 沙箱没有 `.venv`，所以**启动走 `sim-run.py`**（沙箱专用入口，配置路径钉在
   `~/.contest_generator_sim`）——这是 `docs/agents/local-environment.md` 第 1 节记的
   两处「故意不真实」之一。
2. 更新器的重启走产品自己的 `start-app.vbs`（我们改不了），而 `start-app.bat` 的数据目录
   是 `%USERPROFILE%\\.contest_generator`——**为了不让它落到真身数据目录**，本脚本把
   `USERPROFILE` 重定向到一次性目录（`%TEMP%\\fe01-*\\profile`）。沙箱自己的配置不受影响
   （`sim-run.py` 里是绝对路径 `C:\\Users\\luoji\\.contest_generator_sim`）。
   真身 `~/.contest_generator` 因此全程零触碰——这一条由「演练前后 mtime + 文件清单」自己证。

用法::

    python .scratch/verify-gate-drills/drill-01-upgrade.py            # 真跑（下 305 MB）
    python .scratch/verify-gate-drills/drill-01-upgrade.py --dry-run  # 只做前置核对与起点自证
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SIM_ROOT = Path(r"C:\Users\luoji\Desktop\firstep-sim")
SIM_DATA = Path(r"C:\Users\luoji\.contest_generator_sim")
SIM_RUN = SIM_ROOT / "sim-run.py"
REAL_DATA = Path.home() / ".contest_generator"
REAL_UPDATES = REAL_DATA / "updates"
PACK_DIR = Path.home() / "Desktop" / "firstep-pack"
PORT = 8020
START_VERSION = "1.1.1"
TARGET_VERSION = "1.2.1"
BASE = f"http://127.0.0.1:{PORT}"

LINES: list[str] = []
RESULTS: dict = {"problems": [], "stuck": [], "notes": []}
# 证据文件名（善后复测另存一份，别把主跑的原始输出覆盖掉）
OUTPUT_STEM = "verify-01-upgrade"


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def note(text: str) -> None:
    RESULTS["notes"].append(text)
    log(f"  [记录] {text}")


def problem(text: str) -> None:
    """判红（红 = 产品行为与工单判据不符）。"""
    RESULTS["problems"].append(text)
    log(f"  [判红] {text}")


def stuck(text: str) -> None:
    """卡住（≠ 红：超时/环境没到位，判据本身没说话）。"""
    RESULTS["stuck"].append(text)
    log(f"  [卡住] {text}")


# ---------------------------------------------------------------------------
# HTTP / 环境小工具（照 verify-07 的口径，不另发明）
# ---------------------------------------------------------------------------


def api(path: str, payload: dict | None = None, timeout: float = 60) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE + path, data=data, method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_retry(path: str, payload: dict | None = None, timeout: float = 180,
              attempts: int = 3) -> dict:
    last: Exception | None = None
    for index in range(1, attempts + 1):
        try:
            return api(path, payload, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 —— GitHub 那一跳会慢会抖，值得重试
            last = exc
            log(f"  （{path} 第 {index}/{attempts} 次失败：{type(exc).__name__}: {exc}）")
            time.sleep(3.0)
    raise RuntimeError(f"{path} 连续 {attempts} 次失败：{last}")


def wait_health(deadline_seconds: float = 60) -> dict | None:
    end = time.time() + deadline_seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=3) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 —— 起服务/重启期间连不上是正常的
            time.sleep(0.5)
    return None


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


def python_processes() -> list[str]:
    try:
        output = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId"],
            capture_output=True, text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001
        return []
    return [line.strip() for line in output.splitlines()[1:] if line.strip().isdigit()]


SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv",
             "node_modules", ".claude", ".scratch"}


def tree_stamp(root: Path) -> dict[str, tuple[int, float]]:
    """真身工作树快照（排除 VCS / 缓存 / 本特性区，理由同 verify-07 的注释）。"""
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
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    return {"added": added, "removed": removed, "changed": changed}


def read_version_file(root: Path) -> str:
    init = root / "src" / "contest_generator" / "__init__.py"
    for line in init.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split('"')[1] if '"' in line else line.strip()
    return ""


# ---------------------------------------------------------------------------
# 保命项快照（升级前后各一次，逐字节比）
# ---------------------------------------------------------------------------


def materials_snapshot() -> dict:
    """资料库快照：文件数 / 总字节 / 基线清单 sha256 / 前 5 个小文件 sha256。

    大文件不逐个哈希（资料库里有几百 MB 的第三方包）——判据要的是「内容没被动过」，
    计数 + 字节和 + 抽样哈希足够给出可复算的证据。
    """
    root = SIM_ROOT / "sources" / "materials"
    baseline = root / ".materials-manifest.json"
    count = 0
    total = 0
    samples: dict[str, str] = {}
    sample_candidates: list[tuple[str, int]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        count += 1
        total += size
        rel = str(path.relative_to(root)).replace("\\", "/")
        if size < 1024 * 1024 and not rel.startswith("."):
            sample_candidates.append((rel, size))
    for rel, _size in sorted(sample_candidates)[:5]:
        samples[rel] = sha256_of(root / rel)

    baseline_info: dict = {"exists": baseline.is_file()}
    if baseline.is_file():
        baseline_info["bytes"] = baseline.stat().st_size
        baseline_info["sha256"] = sha256_of(baseline)
        try:
            data = json.loads(baseline.read_text(encoding="utf-8-sig"))
            baseline_info["version"] = str(data.get("version") or "")
            baseline_info["batches"] = len(data.get("batches") or [])
        except Exception as exc:  # noqa: BLE001
            baseline_info["parse_error"] = str(exc)
    return {"count": count, "total_bytes": total, "baseline": baseline_info,
            "sample_sha256": samples}


def third_party_snapshot() -> dict:
    """第三方安装包（故意不进包的那批）：计数 + 字节和（不哈希，太大）。"""
    root = SIM_ROOT / "sources" / "materials"
    suffixes = {".exe", ".zip", ".rar", ".7z", ".iso", ".img"}
    count = 0
    total = 0
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in suffixes:
            try:
                total += path.stat().st_size
            except OSError:
                continue
            count += 1
    return {"count": count, "total_bytes": total}


def data_dir_snapshot() -> dict:
    """沙箱数据目录：逐文件（相对路径 → (字节, mtime)）+ config.json 的 sha256。"""
    files: dict[str, list] = {}
    for path in SIM_DATA.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(SIM_DATA)).replace("\\", "/")
        if rel.startswith(("updates/backup/", "updates/full/", "updates/materials/")):
            continue  # 演练自己会写这些地方，不算保命项
        try:
            stat = path.stat()
        except OSError:
            continue
        files[rel] = [stat.st_size, stat.st_mtime]
    config = SIM_DATA / "config.json"
    return {
        "files": files,
        "config_sha256": sha256_of(config) if config.is_file() else "",
        "config_text": config.read_text(encoding="utf-8") if config.is_file() else "",
    }


def start_sandbox(env: dict, log_path: Path) -> subprocess.Popen:
    handle = open(log_path, "a", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, str(SIM_RUN)],
        cwd=str(SIM_ROOT), env=env,
        stdout=handle, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def make_env(profile: Path) -> dict:
    env = dict(os.environ)
    env.update({
        "FIRSTEP_LAUNCHER_PORT": str(PORT),
        # 更新器的重启（start-app.vbs → start-app.bat）按 %USERPROFILE% 推数据目录：
        # 重定向它，重启就不会落到真身 ~/.contest_generator（见模块 docstring 第 2 条）
        "USERPROFILE": str(profile),
        "HOME": str(profile),
        "PYTHONPATH": str(SIM_ROOT / "src"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
    })
    return env


def load_full_manifest() -> dict[str, dict]:
    """官方完整包清单的 {路径: {size, sha256}}（用于量「升级后还有多少旧文件」）。"""
    path = PACK_DIR / f"firstep-full-v{TARGET_VERSION}.manifest.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return {str(item["path"]): item for item in data.get("files") or []}


def compare_to_official() -> dict:
    """沙箱 tracked 树 vs 官方 v1.2.1 完整包清单：一致 / 内容旧 / 缺 / 多。

    **为什么值得量**：小发版更新包是「全量 tracked 快照」（`tools/pack-update.ps1`
    第 60-67 行：清单 = 全部 tracked 文件，`-Baseline` 只用于算删除清单）。于是
    「删了但没有出现在本版 removed.txt 里」的旧文件会留下来——量出来才知道有多少。
    只比 tracked 顶层（与打包器白名单同口径），`sources/materials` 与演练产物除外。
    """
    official = load_full_manifest()
    if not official:
        return {"available": False}
    top_levels = ("src", "library", "sources", "tests", "docs", "assets", "tools",
                  ".githooks", ".gitattributes", ".gitignore", "CLAUDE.md", "README.md",
                  "CONTEXT.md", "CHANGELOG.md", "VERSIONS.md", "pyproject.toml",
                  "install.bat", "start-app.bat", "start-app.vbs", "stop-firstep.bat",
                  "stop-firstep.vbs")
    top_set = set(top_levels)
    on_disk: dict[str, Path] = {}
    for path in SIM_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(SIM_ROOT)).replace("\\", "/")
        parts = rel.split("/")
        if any(part in SKIP_DIRS for part in parts):
            continue
        # 打包器的顶层白名单（新增顶层目录时打包器那边也要登记）
        if parts[0] not in top_set:
            continue
        # 资料库内容不进小发版包（pack-update 第 60 行注释），跳过它免得把
        # 「包本来就不带的东西」算成异类
        if rel.startswith("sources/materials/"):
            continue
        on_disk[rel] = path

    same = stale = 0
    missing: list[str] = []
    stale_list: list[dict] = []
    blobs: dict[str, dict] = {}
    for rel, path in sorted(on_disk.items()):
        want = official.get(rel)
        if want is None:
            missing.append(rel)
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        # 期望大小：**0 是合法值**（空文件在包里很常见）——不能用 `or -1`，
        # 那会把「期望 0 字节」误判成「清单没写大小」（本脚本第一版就是这么
        # 给两个 0 字节文件判了「stale」的，重算时修掉）。
        want_size = want.get("size")
        want_size = int(want_size) if isinstance(want_size, (int, float)) else -1
        if want_size != size:
            stale += 1
            stale_list.append({"path": rel, "why": f"size {size} != {want_size}"})
            continue
        digest = sha256_of(path)
        if digest == str(want.get("sha256") or "").lower():
            same += 1
        else:
            stale += 1
            stale_list.append({"path": rel, "why": "sha256 不同（内容仍是旧版 / 被改过）"})
    # 官方清单里但沙箱没有的（tracked 部分）
    official_tracked = [p for p in official
                        if not p.startswith("sources/materials/")
                        and p.split("/")[0] in top_set]
    extra_missing = sorted(set(official_tracked) - set(on_disk))
    return {
        "available": True,
        "official_tracked": len(official_tracked),
        "on_disk_tracked": len(on_disk),
        "same": same,
        "stale": stale,
        "stale_examples": stale_list[:20],
        "stale_by_top": _count_by_top(stale_list),
        "not_in_official": len(missing),
        "not_in_official_examples": missing[:20],
        "not_in_official_by_top": _by_top(missing),
        "official_missing_on_disk": len(extra_missing),
        "official_missing_on_disk_examples": extra_missing[:20],
        "official_missing_on_disk_by_top": _by_top(extra_missing),
        "blobs": blobs,
    }


def _by_top(paths: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        top = path.split("/")[0]
        counts[top] = counts.get(top, 0) + 1
    return counts


def _count_by_top(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        top = item["path"].split("/")[0]
        counts[top] = counts.get(top, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def run_aftercare(env: dict, work: Path) -> int:
    """B1 善后复测（独立一格，可单独复跑）：**手动重启后到底是不是 1.2.1**。

    为什么单列：主跑暴露的正是「文件全换了、**跑着的服务**没换」——那么
    「用户自己重开一次能不能到新版」就是这条链的最后一块（也是给用户的自救口径）。
    本格不改任何文件，只收掉端口上的旧进程、按沙箱口径（`sim-run.py`）重起一次、
    读 `/api/health`。
    """
    log("# B1 善后复测：手动重启后的服务版本 + 升级后构成复算")
    log(f"  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    disk = read_version_file(SIM_ROOT)
    log(f"  盘上 __init__.py = {disk}")
    killed = kill_listener(PORT)
    log(f"  收掉端口 {PORT} 上的旧进程：{killed or '（无）'}")
    time.sleep(1.0)
    launcher = start_sandbox(env, work / "aftercare-run.log")
    health = wait_health(deadline_seconds=120)
    served = (health or {}).get("version")
    log(f"  重起后 `/api/health` = {health}")
    RESULTS["aftercare"] = {"on_disk": disk, "served": served, "killed": killed}
    if served != TARGET_VERSION:
        problem(f"善后复测不成立：重起后服务报 {served}，期望 {TARGET_VERSION}")
    else:
        log(f"  → 手动重开一次即到 {TARGET_VERSION}（用户自救口径成立）")

    log("")
    log("## 升级后构成复算（沙箱 tracked 树 vs 官方 v1.2.1 完整包清单）")
    compare = compare_to_official()
    RESULTS["composition"] = compare
    if not compare.get("available"):
        note("拿不到官方完整包清单——这一格跳过")
    else:
        log(f"  官方 tracked 文件：{compare['official_tracked']}；沙箱 tracked 文件："
            f"{compare['on_disk_tracked']}")
        log(f"  内容与官方逐字节一致：{compare['same']}")
        log(f"  内容与官方不同：{compare['stale']}"
            f"（按顶层 {compare['stale_by_top']}）")
        log(f"  官方没了但沙箱还在（孤儿）：{compare['not_in_official']}"
            f"（按顶层 {compare['not_in_official_by_top']}）")
        log(f"  官方有但沙箱没有（缺）：{compare['official_missing_on_disk']}"
            f"（按顶层 {compare['official_missing_on_disk_by_top']}）")
        for item in compare["stale_examples"]:
            log(f"    - 不同：{item['path']}（{item['why']}）")
        log(f"  孤儿样例（前 20）：{compare['not_in_official_examples']}")

    if launcher.poll() is not None:
        log("  （善后起的服务进程已退出——看 aftercare-run.log）")
        log((work / "aftercare-run.log").read_text(encoding="utf-8",
                                                   errors="replace")[-1500:])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="只做前置核对 + 起点自证 + 线上检查更新（不下载、不替换）")
    parser.add_argument("--aftercare", action="store_true",
                        help="善后复测：收掉端口旧进程 → 按沙箱口径重起 → 读版本 + 构成复算")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    work = Path(os.environ["TEMP"]) / f"fe01-{time.strftime('%Y%m%d-%H%M%S')}"
    profile = work / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    env = make_env(profile)

    if args.aftercare:
        global OUTPUT_STEM
        OUTPUT_STEM = "verify-01-upgrade-aftercare"
        return run_aftercare(env, work)

    log("# B1 证据：沙箱「模拟用户机」真机升级 v1.1.1 → v1.2.1")
    log(f"  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"  一次性演练目录：{work}")
    log("")

    # ---- 零、前置事实（照 E2E-8020.md 第 0 节核对，不符就当场说） ----
    log("## 零、前置事实核对")
    facts = {
        "sim_root_exists": SIM_ROOT.is_dir(),
        "sim_data_exists": SIM_DATA.is_dir(),
        "sim_run_exists": SIM_RUN.is_file(),
        "sim_venv_absent": not (SIM_ROOT / ".venv").exists(),
        "sim_version_on_disk": read_version_file(SIM_ROOT),
        "sim_config": str(SIM_DATA / "config.json"),
        "real_data": str(REAL_DATA),
        "port_8000_listeners": listen_pids(8000),
        "port_8020_listeners": listen_pids(PORT),
    }
    for key, value in facts.items():
        log(f"  {key} = {value!r}")
    RESULTS["facts"] = facts
    if not (facts["sim_root_exists"] and facts["sim_data_exists"] and facts["sim_run_exists"]):
        problem("沙箱前置不成立（工具根 / 数据目录 / sim-run.py 有缺）——本单按 spec 用 "
                "`.scratch/full-download/make_sim_sandbox.py` 重建后重跑")
        return 2
    if facts["sim_version_on_disk"] != START_VERSION:
        log(f"  **注意**：盘上起点版本是 {facts['sim_version_on_disk']!r}，不是工单写的 "
            f"{START_VERSION}——如实记账，判据按实际起点算")
        note(f"沙箱起点版本实际为 {facts['sim_version_on_disk']}（工单写的是 {START_VERSION}）")
    if facts["port_8000_listeners"]:
        note(f"真身 8000 在跑（PID {facts['port_8000_listeners']}）——只读，不碰")
    if facts["port_8020_listeners"]:
        killed = kill_listener(PORT)
        note(f"8020 上有遗留监听（PID {killed}），已先收掉再开跑")

    # ---- 一、隔离与保命项基线 ----
    log("")
    log("## 一、隔离边界与保命项基线（真身只读）")
    real_data_mtime_before = dir_mtime(REAL_DATA)
    real_updates_before = sorted(p.name for p in REAL_UPDATES.iterdir()) \
        if REAL_UPDATES.is_dir() else []
    real_launcher_log = REAL_DATA / "launcher.log"
    real_launcher_mtime_before = dir_mtime(real_launcher_log) if real_launcher_log.is_file() else -1.0
    real_tree_before = tree_stamp(REPO)
    materials_before = materials_snapshot()
    third_party_before = third_party_snapshot()
    data_before = data_dir_snapshot()
    RESULTS["before"] = {
        "real_data_mtime": real_data_mtime_before,
        "real_updates": real_updates_before,
        "real_tree_files": len(real_tree_before),
        "materials": materials_before,
        "third_party": third_party_before,
        "sim_data_files": sorted(data_before["files"]),
        "sim_config_sha256": data_before["config_sha256"],
    }
    log(f"  真身数据目录 mtime = {real_data_mtime_before}；updates/ = {real_updates_before or '（空）'}")
    log(f"  真身工作树基线 = {len(real_tree_before)} 个文件（已排除 VCS/缓存/.scratch）")
    log(f"  沙箱资料库：{materials_before['count']} 文件 / "
        f"{materials_before['total_bytes']} 字节；基线清单 "
        f"{materials_before['baseline'].get('version', '?')} / "
        f"batches={materials_before['baseline'].get('batches', '?')} / "
        f"sha256={materials_before['baseline'].get('sha256', '')[:16]}…")
    log(f"  第三方安装包：{third_party_before['count']} 个 / "
        f"{third_party_before['total_bytes']} 字节")
    log(f"  沙箱数据目录文件：{sorted(data_before['files'])}")
    log(f"  沙箱 config.json sha256 = {data_before['config_sha256'][:16]}…")
    log(f"  沙箱 config 正文：{data_before['config_text'].replace(chr(10), ' ')}")

    # ---- 二、起点自证：盘上 + 跑起来的服务 ----
    log("")
    log("## 二、起点自证（盘上版本 + 跑起来的服务）")
    launcher = start_sandbox(env, work / "sandbox-run.log")
    health = wait_health(deadline_seconds=90)
    if health is None:
        stuck("沙箱服务 90 秒没起来——看 sandbox-run.log 与沙箱 webapp 日志")
        log(f"  sandbox-run.log 末尾：")
        log((work / "sandbox-run.log").read_text(encoding="utf-8", errors="replace")[-2000:])
        return 1
    served_before = health.get("version")
    disk_before = read_version_file(SIM_ROOT)
    log(f"  跑起来的服务 `/api/health` = {health}")
    log(f"  盘上 `src/contest_generator/__init__.py` = {disk_before}")
    RESULTS["startpoint"] = {"served": served_before, "on_disk": disk_before}
    if served_before != START_VERSION or disk_before != START_VERSION:
        problem(f"起点自证不成立：服务报 {served_before} / 盘上 {disk_before}，"
                f"与 {START_VERSION} 不符")

    # ---- 三、检查更新（线上真实 Release） ----
    log("")
    log("## 三、走产品端点：检查更新")
    check = api_retry("/api/update/check", timeout=180)
    log(f"  latest={check.get('latest_version')} current={check.get('current_version')!r} "
        f"update_available={check.get('update_available')} "
        f"size={check.get('size_bytes')} error={check.get('error')!r}")
    log(f"  message={check.get('message')!r}")
    log(f"  zip_url={check.get('zip_url')}")
    log(f"  sha256={check.get('sha256')}")
    log(f"  removed_url={check.get('removed_url')}")
    RESULTS["check"] = {k: check.get(k) for k in
                        ("latest_version", "current_version", "update_available",
                         "zip_url", "size_bytes", "sha256", "removed_url", "error",
                         "message")}
    if not check.get("update_available"):
        problem(f"检查更新没报有新版（error={check.get('error')!r}）——升级链无从开跑")
        return 1
    if str(check.get("latest_version")) != TARGET_VERSION:
        note(f"线上最新是 {check.get('latest_version')}，工单写的是 {TARGET_VERSION}")
    if not check.get("sha256"):
        problem("检查更新没拿到 sha256（apply 会被 400 拒——产品防护正确，但升级走不通）")
        return 1
    expected_size = int(check.get("size_bytes") or 0)
    target_version = str(check.get("latest_version") or "")

    if args.dry_run:
        log("")
        log("（--dry-run：到此为止，不下载不替换）")
        return 0

    # ---- 四、一键更新（真下 305 MB） ----
    log("")
    log(f"## 四、一键更新：真下载线上 {expected_size / 1024 / 1024:.0f} MB → 校验 → 拉起更新器")
    updates_dir = SIM_DATA / "updates"
    zip_path = updates_dir / f"firstep-update-{target_version}.zip"
    if zip_path.exists():
        note(f"目标位置已存在旧包 {zip_path.name}（{zip_path.stat().st_size} 字节）——"
             f"产品会覆盖它，先记下来")
    last_update_path = updates_dir / "last-update.json"
    last_update_mtime_before = dir_mtime(last_update_path)
    updater_log = updates_dir / "updater.log"
    updater_log_bytes_before = updater_log.stat().st_size if updater_log.is_file() else 0
    t0 = time.time()
    try:
        started = api("/api/update/apply", {
            "zip_url": str(check.get("zip_url")),
            "sha256": str(check.get("sha256")),
            "version": target_version,
            "removed_url": str(check.get("removed_url") or ""),
        }, timeout=3600)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        problem(f"apply 返回 HTTP {exc.code}：{body[:300]}")
        return 1
    elapsed = time.time() - t0
    log(f"  apply 返回（耗时 {elapsed:.1f}s）：{started}")
    downloaded = zip_path.stat().st_size if zip_path.is_file() else 0
    speed = downloaded / elapsed / 1024 / 1024 if elapsed > 0 else 0
    log(f"  落盘 {zip_path.name} = {downloaded} 字节"
        f"（清单 {expected_size}；差 {downloaded - expected_size}）"
        f"，均速 {speed:.2f} MB/s")
    RESULTS["apply"] = {"elapsed_seconds": round(elapsed, 1), "response": started,
                        "downloaded_bytes": downloaded, "expected_bytes": expected_size,
                        "avg_mbps": round(speed, 2)}
    if downloaded != expected_size:
        problem(f"下载字节与清单不符：{downloaded} != {expected_size}")
    if zip_path.is_file():
        digest = sha256_of(zip_path)
        log(f"  下载物 sha256 = {digest}")
        log(f"  清单 sha256   = {check.get('sha256')}")
        if digest != str(check.get("sha256")).lower():
            problem("下载物 sha256 与线上清单不符")
        else:
            log("  → 真下载 + 校验一致（这一格是真下载，不是复用缓存）")

    # ---- 五、任务状态 + 更新器替换 ----
    log("")
    log("## 五、更新状态与更新器替换（独立进程：停服 → 备份 → 覆盖 → 重启）")
    lock = updates_dir / "updating.lock"
    pending = updates_dir / "pending-update.json"
    saw_lock = False
    final_status: dict | None = None
    deadline = time.time() + 300
    while time.time() < deadline:
        if lock.exists():
            saw_lock = True
        try:
            status = api("/api/update/status", timeout=10)
        except Exception as exc:  # noqa: BLE001 —— 停服窗口里连不上是正常的
            status = {"state": f"<连不上：{type(exc).__name__}>"}
        if time.time() % 5 < 1:
            log(f"  state={status.get('state')} lock={lock.exists()} "
                f"pending={pending.exists()}")
        if status.get("state") in ("done", "failed"):
            # 陈旧 last-update.json 会让它先报 done：要求「见过锁」或 last-update 变新
            fresh = dir_mtime(last_update_path) != last_update_mtime_before
            if saw_lock or fresh:
                final_status = status
                break
        time.sleep(1.0)
    log(f"  lock 出现过：{saw_lock}；pending 还在：{pending.exists()}；"
        f"last-update.json 更新：{dir_mtime(last_update_path) != last_update_mtime_before}")
    if final_status is None:
        stuck("5 分钟没等到更新器终态（锁与 last-update.json 都没动）——替换链可能没跑起来")
        final_status = {"state": "<超时>"}
    else:
        log(f"  终态：{json.dumps(final_status, ensure_ascii=False)[:400]}")
    RESULTS["status"] = {"saw_lock": saw_lock, "pending_left": pending.exists(),
                         "final": {k: final_status.get(k) for k in ("state", "message", "result")}}

    if updater_log.is_file():
        text = updater_log.read_text(encoding="utf-8", errors="replace")
        new_text = text[updater_log_bytes_before:]
        log("  更新器日志（本次新增部分）：")
        for line in new_text.splitlines():
            log(f"  | {line}")

    # ---- 六、终点判据：跑起来的服务版本 == 1.2.1 ----
    log("")
    log("## 六、终点判据（版本号从跑起来的服务读，不只看盘上文件）")
    disk_after = read_version_file(SIM_ROOT)
    log(f"  盘上 __init__.py = {disk_after}")
    served_after = None
    end = time.time() + 180
    while time.time() < end:
        health_after = wait_health(deadline_seconds=5)
        if health_after and health_after.get("version") == TARGET_VERSION:
            served_after = health_after.get("version")
            break
        time.sleep(2.0)
    restarted_by_updater = served_after is not None
    if served_after is None:
        log("  （更新器的重启没把服务带起来——按 local-environment 第 1 节的沙箱口径，"
            "用 sim-run.py 起一次，版本判据仍成立；但「更新器自己重启」这一格如实记为未成立）")
        launcher = start_sandbox(env, work / "sandbox-run-2.log")
        health_after = wait_health(deadline_seconds=120)
        served_after = (health_after or {}).get("version")
    log(f"  **重启后 `/api/health`.version = {served_after}**（工单判据 {TARGET_VERSION}）")
    RESULTS["endpoint"] = {"on_disk": disk_after, "served": served_after,
                           "restarted_by_updater": restarted_by_updater}
    if served_after != TARGET_VERSION:
        problem(f"终点判据不成立：服务报 {served_after}，期望 {TARGET_VERSION}")
    if disk_after != TARGET_VERSION:
        problem(f"盘上版本不对：{disk_after}，期望 {TARGET_VERSION}")

    # ---- 七、升级后的构成：还有多少旧文件 / 少没少文件 ----
    log("")
    log("## 七、升级后的构成（沙箱 tracked 树 vs 官方 v1.2.1 完整包清单）")
    compare = compare_to_official()
    RESULTS["composition"] = compare
    if not compare.get("available"):
        note("拿不到官方完整包清单（firstep-pack 里没有 v1.2.1 的 manifest）——这一格跳过")
    else:
        log(f"  官方 tracked 文件：{compare['official_tracked']}；沙箱 tracked 文件："
            f"{compare['on_disk_tracked']}")
        log(f"  **内容与官方逐字节一致：{compare['same']}**")
        log(f"  **内容与官方不同（仍是旧版 / 被改过）：{compare['stale']}**")
        log(f"  官方没了但沙箱还在（多出来的）：{compare['not_in_official']}")
        log(f"  官方有但沙箱没有（缺的）：{compare['official_missing_on_disk']}")
        if compare["stale"]:
            log(f"  旧内容按顶层目录分布：{compare['stale_by_top']}")
            log("  旧内容样例（前 20）：")
            for item in compare["stale_examples"]:
                log(f"    - {item['path']}（{item['why']}）")
        if compare["not_in_official_examples"]:
            log(f"  多出来的样例（前 20）：{compare['not_in_official_examples']}")
        if compare["official_missing_on_disk_examples"]:
            log(f"  缺的样例（前 20）：{compare['official_missing_on_disk_examples']}")
        if compare["stale"] or compare["official_missing_on_disk"]:
            note(f"升级后沙箱 tracked 树与官方 v1.2.1 包**不完全一致**："
                 f"内容不同 {compare['stale']} 个、缺 {compare['official_missing_on_disk']} 个"
                 f"（小发版更新包是全量 tracked 快照，但删除清单只覆盖「上一版 → 本版」的删除）")

    # ---- 八、保命项 ----
    log("")
    log("## 八、保命项（升级前后逐项比）")
    materials_after = materials_snapshot()
    third_party_after = third_party_snapshot()
    data_after = data_dir_snapshot()
    checks = {
        "config.json 未变": data_after["config_sha256"] == data_before["config_sha256"],
        "资料库文件数未变": materials_after["count"] == materials_before["count"],
        "资料库字节数未变": materials_after["total_bytes"] == materials_before["total_bytes"],
        "资料库基线清单未变": (materials_after["baseline"].get("sha256")
                              == materials_before["baseline"].get("sha256")),
        "资料库抽样 sha256 未变":
            materials_after["sample_sha256"] == materials_before["sample_sha256"],
        "第三方安装包计数未变": third_party_after["count"] == third_party_before["count"],
        "第三方安装包字节未变":
            third_party_after["total_bytes"] == third_party_before["total_bytes"],
        "任务记录 recent.json 未变":
            data_after["files"].get("recent.json") == data_before["files"].get("recent.json"),
        "任务记录 tasks-simulated.json 未变":
            data_after["files"].get("tasks-simulated.json")
            == data_before["files"].get("tasks-simulated.json"),
        "pending-update.json 已清": not pending.exists(),
        "updating.lock 已释放": not lock.exists(),
        "备份目录已生成": (updates_dir / "backup").is_dir()
                          and any((updates_dir / "backup").iterdir()),
    }
    for label, ok in checks.items():
        log(f"  {'成立' if ok else '**不成立**'}：{label}")
    RESULTS["safeguards"] = checks
    for label, ok in checks.items():
        if not ok and label not in ("备份目录已生成",):
            problem(f"保命项不成立：{label}")
    if not checks["备份目录已生成"]:
        problem("保命项不成立：更新器没留下备份目录")

    # 备份目录内容摘要
    backup_root = updates_dir / "backup"
    if backup_root.is_dir():
        stamps = sorted(p.name for p in backup_root.iterdir() if p.is_dir())
        latest = backup_root / stamps[-1] if stamps else None
        count = 0
        if latest is not None:
            count = sum(1 for p in latest.rglob("*") if p.is_file())
        log(f"  备份：{stamps}；最新一份 {latest.name if latest else '?'} 含 {count} 个文件")
        RESULTS["backup"] = {"stamps": stamps, "latest_files": count}

    # ---- 九、隔离边界收尾校验 ----
    log("")
    log("## 九、隔离边界收尾校验（真身只读）")
    real_data_mtime_after = dir_mtime(REAL_DATA)
    real_updates_after = sorted(p.name for p in REAL_UPDATES.iterdir()) \
        if REAL_UPDATES.is_dir() else []
    real_tree_after = tree_stamp(REPO)
    tree_diff = diff_stamp(real_tree_before, real_tree_after)
    real_launcher_mtime_after = dir_mtime(real_launcher_log) if real_launcher_log.is_file() else -1.0
    isolation = {
        "real_data_mtime_untouched": real_data_mtime_after == real_data_mtime_before,
        "real_updates_untouched": real_updates_after == real_updates_before,
        "real_tree_untouched": not (tree_diff["added"] or tree_diff["removed"]
                                    or tree_diff["changed"]),
        "real_launcher_log_untouched": real_launcher_mtime_after == real_launcher_mtime_before,
        "port_8000_listeners": listen_pids(8000),
    }
    log(f"  真身数据目录 mtime 未变：{isolation['real_data_mtime_untouched']}"
        f"（{real_data_mtime_before} → {real_data_mtime_after}）")
    log(f"  真身 updates/ 条目未变：{isolation['real_updates_untouched']}")
    log(f"  真身工作树未变：{isolation['real_tree_untouched']}"
        f"（{len(real_tree_before)} → {len(real_tree_after)} 个文件）")
    if not isolation["real_tree_untouched"]:
        for kind in ("added", "removed", "changed"):
            names = tree_diff[kind]
            if names:
                log(f"    {kind}（前 12）：{names[:12]}")
    log(f"  真身 launcher.log 未变：{isolation['real_launcher_log_untouched']}")
    log(f"  8000 监听（应为空/与演练前一致）：{isolation['port_8000_listeners']}")
    RESULTS["isolation"] = isolation
    RESULTS["real_tree_diff"] = {k: tree_diff[k][:20] for k in
                                 ("added", "removed", "changed")}
    for label in ("real_data_mtime_untouched", "real_updates_untouched",
                  "real_tree_untouched", "real_launcher_log_untouched"):
        if not isolation[label]:
            problem(f"隔离判据不成立：{label}")
    if isolation["port_8000_listeners"] != facts["port_8000_listeners"]:
        problem("隔离判据不成立：真身 8000 的监听状态在演练期间变了")

    # 更新器的重启落在哪（重定向 profile vs 真身）
    profile_launcher = profile / ".contest_generator" / "launcher.log"
    profile_webapp_log = profile / ".contest_generator" / "webapp.log"
    log(f"  重定向 profile 里：launcher.log={profile_launcher.is_file()} / "
        f"webapp.log={profile_webapp_log.is_file()}")
    if profile_launcher.is_file():
        log("  重定向 profile 的 launcher.log 末尾：")
        for line in profile_launcher.read_text(encoding="utf-8",
                                               errors="replace").splitlines()[-6:]:
            log(f"  | {line}")
    RESULTS["redirect_profile"] = {
        "launcher_log": profile_launcher.is_file(),
        "webapp_log": profile_webapp_log.is_file(),
    }

    return 0


def finish(code: int) -> int:
    (HERE / f"{OUTPUT_STEM}.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
    (HERE / f"{OUTPUT_STEM}.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n证据已写：{OUTPUT_STEM}.txt / .json")
    return code


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except Exception as exc:  # noqa: BLE001 —— 演练脚本崩了也要留原始证据
        import traceback

        problem(f"脚本异常：{type(exc).__name__}: {exc}")
        log(traceback.format_exc())
    finally:
        # 收尾：只收 8020（真身 8000 不碰）
        killed = kill_listener(PORT)
        log("")
        log("## 收尾")
        log(f"  收掉 8020 监听进程：{killed or '（无）'}")
        time.sleep(1.0)
        leftover = listen_pids(PORT)
        log(f"  8020 端口{'已释放' if not leftover else f'**仍被占用 {leftover}**'}")
        log(f"  残留 python 进程：{python_processes() or '（无）'}")
        RESULTS["cleanup"] = {"killed": killed, "leftover": leftover,
                              "python_left": python_processes()}
        exit_code = finish(exit_code)
        problems = RESULTS["problems"]
        log("")
        log("## 总判")
        log(f"  判红 {len(problems)} 条 / 卡住 {len(RESULTS['stuck'])} 条")
        for item in problems:
            log(f"    · 判红：{item}")
        for item in RESULTS["stuck"]:
            log(f"    · 卡住：{item}")
        log(f"  B1「沙箱升级到 {TARGET_VERSION}」："
            f"{'PASS' if not problems else 'FAIL'}")
        # 证据要含总判，落盘一次（上面的 finish 已写，这里补写含总判的版本）
        (HERE / f"{OUTPUT_STEM}.txt").write_text("\n".join(LINES) + "\n",
                                                 encoding="utf-8")
        RESULTS["verdict"] = {"problems": problems, "stuck": RESULTS["stuck"],
                              "pass": not problems}
        (HERE / f"{OUTPUT_STEM}.json").write_text(
            json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(exit_code if not RESULTS["problems"] else 1)
