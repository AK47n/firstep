# -*- coding: utf-8 -*-
"""本机**离线**演练：真 v1.1.1 沙箱 + 本机打出的修好的小发版包 → 构成复算（工单 04）。

**为什么不用 drill-01**：`drill-01-upgrade.py` 从**线上 release 真下载**更新包，所以它的判据
要成立就必须先换线上资产。本轮拍板**不发版**，于是用离线口径拿同样的证据：包在本地打、
更新器是产品自带的那支、沙箱是真 v1.1.1、构成复算沿用 drill-01 的同一套口径
（顶层白名单 + 排除 `sources/materials`）。

七步（每步都记账）：

1. 前置事实：沙箱 / 三个基线产物 / 重建脚本 / 工作树是否干净；
2. **还原真 v1.1.1**：调 `.scratch/update-restart-stale-service/rebuild-sandbox-v111.py --write`；
3. **植入旧版残留**：从 v1.1.1 的发行集合里取几个「本版不再发」的真实路径，往沙箱里
   写同名文件——不植入的话，删除清单在本次演练里没有东西可删（v1.1.1 的完整包本来就
   不含 `revise-backups` / `*.exe`），那一步就等于没验；
4. **本地打包**：`tools/pack-update.ps1 -Baseline <v1.1.1 files.txt>`（含累计口径的两个输入）；
5. **真更新器应用**：`tools/update-app.py --no-stop --no-restart --skip-pip`（`--skip-pip` 是硬
   要求：沙箱没有 `.venv`，全局 `pip install -e .` 会污染全局 site-packages）；
6. **构成复算**：沙箱盘面 vs 本机 `full_pack.scan_tree` 算出的完整包文件集
   —— 判据 `not_in_official == 0`，且植入的残留**全部消失**；
7. 收尾：真身数据目录 mtime 未变、端口释放、无残留 python。

用法::

    python .scratch/update-orphan-files/drill-offline.py            # dry-run：只核对前置
    python .scratch/update-orphan-files/drill-offline.py --write    # 真跑（约 10 分钟）
    python .scratch/update-orphan-files/drill-offline.py --write --skip-pack   # 复用已有包
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
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
HOME = Path.home()
SIM_ROOT = HOME / "Desktop" / "firstep-sim"
PACK_DIR = HOME / "Desktop" / "firstep-pack"
REAL_DATA = HOME / ".contest_generator"
REBUILD = REPO / ".scratch" / "update-restart-stale-service" / "rebuild-sandbox-v111.py"
UPDATER = REPO / "tools" / "update-app.py"
PACK_PS1 = REPO / "tools" / "pack-update.ps1"
BASELINE_FILES = PACK_DIR / "firstep-update-v1.1.1.files.txt"
BASELINE_FULL = PACK_DIR / "firstep-full-v1.1.1.manifest.json"
TAG = "v1.2.1"

TOP_LEVELS = (
    "src", "library", "sources", "tests", "docs", "assets", "tools", ".githooks",
    ".gitattributes", ".gitignore", "CLAUDE.md", "README.md", "CONTEXT.md",
    "CHANGELOG.md", "VERSIONS.md", "pyproject.toml", "install.bat", "start-app.bat",
    "start-app.vbs", "stop-firstep.bat", "stop-firstep.vbs",
)
TOP_LEVELS = TOP_LEVELS + ("00-START-HERE.txt",)
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache",
             ".pytest_cache", ".scratch"}
#: 「完整包有、盘上没有」允许的例外（逐条写清，不许模糊放过）
MISSING_ALLOWED = ("src/contest_generator.egg-info/",)

LINES: list[str] = []
RESULTS: dict = {"problems": [], "notes": []}


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def problem(text: str) -> None:
    RESULTS["problems"].append(text)
    log(f"  [判红] {text}")


def note(text: str) -> None:
    RESULTS["notes"].append(text)
    log(f"  [记录] {text}")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, timeout: int = 1800, check: bool = True) -> subprocess.CompletedProcess:
    began = time.time()
    proc = subprocess.run(command, cwd=str(REPO), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    log(f"  $ {' '.join(str(c) for c in command[:4])} …（退出码 {proc.returncode}，"
        f"{time.time() - began:.1f}s）")
    if check and proc.returncode != 0:
        problem(f"命令失败（退出码 {proc.returncode}）：{' '.join(command[:4])}…")
        log((proc.stdout or "")[-1500:])
        log((proc.stderr or "")[-1500:])
    return proc


def on_disk_files(root: Path) -> dict[str, Path]:
    """沙箱盘面（顶层白名单 / 排除 `sources/materials`）——与 drill-01 同口径。"""
    found: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        parts = rel.split("/")
        if any(part in SKIP_DIRS for part in parts):
            continue
        if parts[0] not in TOP_LEVELS:
            continue
        if rel.startswith("sources/materials/"):
            continue
        found[rel] = path
    return found


def official_files() -> dict[str, dict]:
    """本机当前工作树的「完整包该有什么」（与完整包扫描同一份判据）。

    **排除 `sources/materials/`**：那一坨由资料库增量包负责，本来就不参与本次构成比对
    （与 `on_disk_files` 同口径；第一版漏了这条，把 5000+ 个资料库文件算成「盘上缺」）。
    """
    sys.path.insert(0, str(REPO / "src"))
    from contest_generator.full_pack import scan_tree  # noqa: PLC0415

    return {item.path: {"size": item.size, "sha256": item.sha256}
            for item in scan_tree(REPO)
            if not item.path.startswith("sources/materials/")}


def compare(disk: dict[str, Path], official: dict[str, dict]) -> dict:
    same = stale = 0
    stale_list: list[dict] = []
    for rel, path in sorted(disk.items()):
        want = official.get(rel)
        if want is None:
            continue
        if path.stat().st_size != want["size"] or sha256_of(path) != want["sha256"]:
            stale += 1
            stale_list.append(rel)
        else:
            same += 1
    not_in_official = sorted(rel for rel in disk if rel not in official)
    missing = sorted(rel for rel in official if rel not in disk)
    allowed = [rel for rel in missing if rel.startswith(MISSING_ALLOWED)]
    unexpected_missing = [rel for rel in missing if not rel.startswith(MISSING_ALLOWED)]
    return {
        "on_disk": len(disk),
        "official": len(official),
        "same": same,
        "stale": stale,
        "stale_list": stale_list[:20],
        "not_in_official": len(not_in_official),
        "not_in_official_list": not_in_official[:50],
        "missing": len(missing),
        "missing_allowed": allowed,
        "missing_unexpected": unexpected_missing[:50],
    }


def plant_orphans(sandbox: Path, candidates: list[str]) -> list[dict]:
    """把「v1.1.1 发过、本版不再发」的路径写进沙箱（旧版残留），返回记账。"""
    planted: list[dict] = []
    for rel in candidates:
        target = sandbox / Path(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = f"# 演练植入的旧版残留（{rel}）\n".encode("utf-8")
        target.write_bytes(payload)
        planted.append({"path": rel, "sha256": hashlib.sha256(payload).hexdigest()})
        log(f"  植入 {rel}")
    return planted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="真跑（会清空沙箱）")
    parser.add_argument("--skip-pack", action="store_true", help="复用 work/pack 里已有的包")
    parser.add_argument("--keep", action="store_true", help="保留一次性目录")
    args = parser.parse_args()

    work = Path(os.environ["TEMP"]) / f"fe-orphan-{time.strftime('%Y%m%d-%H%M%S')}"
    work.mkdir(parents=True, exist_ok=True)
    pack_out = work / "pack"
    data_dir = work / "data"
    log("# 离线演练：真 v1.1.1 沙箱 + 本机修复包 → 构成复算（工单 update-orphan-files/04）")
    log(f"  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"  一次性目录：{work}")
    log("")

    log("## 零、前置事实")
    facts = {
        "sim_root": str(SIM_ROOT),
        "rebuild_script": REBUILD.is_file(),
        "updater": UPDATER.is_file(),
        "pack_ps1": PACK_PS1.is_file(),
        "baseline_files": BASELINE_FILES.is_file(),
        "baseline_full_manifest": BASELINE_FULL.is_file(),
        "real_data": str(REAL_DATA),
        "real_data_mtime": (REAL_DATA.stat().st_mtime if REAL_DATA.is_dir() else -1.0),
        "dirty_tracked": subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=str(REPO),
            capture_output=True, text=True, encoding="utf-8").stdout.strip().splitlines(),
    }
    for key, value in facts.items():
        log(f"  {key} = {value if key != 'dirty_tracked' else len(value)}")
    RESULTS["facts"] = {k: v for k, v in facts.items() if k != "dirty_tracked"}
    RESULTS["facts"]["dirty_tracked_count"] = len(facts["dirty_tracked"])
    for key in ("rebuild_script", "updater", "pack_ps1", "baseline_files"):
        if not facts[key]:
            problem(f"前置不成立：{key}")
    if RESULTS["problems"]:
        return 2
    if not args.write:
        log("")
        log("（dry-run：加 --write 才真重建沙箱并应用包）")
        return 0

    # ---- 一、还原真 v1.1.1 ----
    log("")
    log("## 一、还原真 v1.1.1 沙箱")
    proc = run([sys.executable, str(REBUILD), "--write"], timeout=900)
    RESULTS["rebuild_ok"] = proc.returncode == 0
    if proc.returncode != 0:
        return 2

    # ---- 二、算出「v1.1.1 发过、本版不再发」的路径并植入 ----
    log("")
    log("## 二、植入旧版残留（让删除清单这一步有东西可删）")
    sys.path.insert(0, str(REPO / "src"))
    from contest_generator.full_pack import (  # noqa: PLC0415
        previous_shipped_files, scan_tree,
    )

    shipped_before = previous_shipped_files(
        update_files=BASELINE_FILES, full_manifest=BASELINE_FULL)
    current = {item.path for item in scan_tree(REPO)}
    candidates = sorted(shipped_before - current)
    log(f"  上一版发行集合 {len(shipped_before)} 条 / 本机产品文件 {len(current)} 条 "
        f"→ 候选残留 {len(candidates)} 条")
    RESULTS["candidates"] = {"shipped_before": len(shipped_before),
                             "current": len(current), "obsolete": len(candidates)}
    # 确定性取样：每个顶层目录取第一条，最多 5 条（要覆盖 revise-backups 与 *.exe 这两类）
    picks: list[str] = []
    for bucket in ("library/revise-backups", "sources"):
        hit = [name for name in candidates if name.startswith(bucket)]
        if hit:
            picks.append(hit[0])
    for name in candidates:
        if name not in picks and len(picks) < 5:
            picks.append(name)
    planted = plant_orphans(SIM_ROOT, picks)
    RESULTS["planted"] = planted

    # ---- 三、本地打包 ----
    log("")
    log("## 三、本地打小发版包（修好的打包器；输入含累计口径的两个基线）")
    zip_path = pack_out / f"firstep-update-{TAG}.zip"
    if args.skip_pack and zip_path.is_file():
        note("复用已有包（--skip-pack）")
    else:
        pack_out.mkdir(parents=True, exist_ok=True)
        # 完整包清单放同一目录：PS 会按上一版 tag 在 OutDir 里找它并传给核心
        shutil.copy2(BASELINE_FULL, pack_out / BASELINE_FULL.name)
        proc = run(["powershell", "-NoProfile", "-File", str(PACK_PS1),
                    "-Tag", TAG, "-Baseline", str(BASELINE_FILES),
                    "-OutDir", str(pack_out), "-AllowDirty"], timeout=3600)
        RESULTS["pack_ok"] = proc.returncode == 0
        if proc.returncode != 0:
            return 2
    removed_path = pack_out / f"firstep-update-{TAG}.removed.txt"
    files_path = pack_out / f"firstep-update-{TAG}.files.txt"
    removed = [line.strip() for line in removed_path.read_text(encoding="utf-8-sig").splitlines()
               if line.strip() and not line.startswith("#")]
    written = [line.strip() for line in files_path.read_text(encoding="utf-8-sig").splitlines()
               if line.strip()]
    RESULTS["pack"] = {
        "zip_bytes": zip_path.stat().st_size if zip_path.is_file() else 0,
        "files": len(written),
        "removed": len(removed),
        "removed_covers_planted": sorted(set(picks) - set(removed)),
        "files_exclude_backups": [name for name in written if "revise-backups" in name][:5],
    }
    log(f"  包内产品文件 {len(written)} 条 / 累计删除清单 {len(removed)} 条")
    if not zip_path.is_file():
        problem("本地包没生成")
        return 2
    for name in picks:
        if name not in removed:
            problem(f"植入的残留没进累计删除清单：{name}")
    for name in written:
        if "revise-backups" in name or name.lower().endswith(".exe"):
            problem(f"包内又出现了包外内容：{name}")

    # ---- 四、真更新器应用 ----
    log("")
    log("## 四、用产品自带的更新器应用（--no-stop --no-restart --skip-pip）")
    proc = run([sys.executable, str(UPDATER), "--zip", str(zip_path),
                "--removed", str(removed_path), "--root", str(SIM_ROOT),
                "--data-dir", str(data_dir), "--no-stop", "--no-restart",
                "--skip-pip"], timeout=1800)
    RESULTS["updater_exit"] = proc.returncode
    if proc.returncode != 0:
        return 2
    version_file = SIM_ROOT / "src" / "contest_generator" / "__init__.py"
    served_version = ""
    for line in version_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            served_version = line.split('"')[1] if '"' in line else ""
    log(f"  应用后盘上版本：{served_version!r}")
    RESULTS["on_disk_version"] = served_version
    if served_version != TAG.lstrip("v"):
        problem(f"应用后盘上版本不是 {TAG}（实际 {served_version!r}）")

    # ---- 五、构成复算 ----
    log("")
    log("## 五、构成复算（沙箱盘面 vs 本机完整包文件集）")
    disk = on_disk_files(SIM_ROOT)
    report = compare(disk, official_files())
    RESULTS["composition"] = report
    log(f"  盘上 {report['on_disk']} / 完整包 {report['official']}：逐字节一致 "
        f"{report['same']}、不同 {report['stale']}、盘上多出 {report['not_in_official']}、"
        f"盘上缺 {report['missing']}（其中允许例外 {len(report['missing_allowed'])}）")
    if report["not_in_official"]:
        log(f"  多出的样例：{report['not_in_official_list'][:10]}")
    if report["not_in_official"] != 0:
        problem(f"判据 not_in_official == 0 不成立（实际 {report['not_in_official']}）")
    if report["missing_unexpected"]:
        problem(f"盘上缺了不该缺的：{report['missing_unexpected'][:5]}")
    still_there = [item["path"] for item in planted
                   if (SIM_ROOT / Path(*item["path"].split("/"))).exists()]
    RESULTS["planted_survivors"] = still_there
    log(f"  植入的残留还剩：{still_there or '（全清）'}")
    if still_there:
        problem(f"植入的旧版残留没被删除清单清掉：{still_there}")

    # ---- 六、收尾 ----
    log("")
    log("## 六、收尾与隔离不变量")
    listeners = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                               errors="replace").stdout
    port_8020 = [line.strip() for line in listeners.splitlines()
                 if "LISTENING" in line and ":8020" in line]
    port_8000 = [line.strip() for line in listeners.splitlines()
                 if "LISTENING" in line and ":8000" in line]
    real_data_mtime = REAL_DATA.stat().st_mtime if REAL_DATA.is_dir() else -1.0
    RESULTS["cleanup"] = {
        "port_8020": port_8020,
        "port_8000": port_8000,
        "real_data_mtime_unchanged": real_data_mtime == facts["real_data_mtime"],
    }
    log(f"  8020 监听：{port_8020 or '（无）'}")
    log(f"  8000 监听：{port_8000 or '（无）'}（真身那个实例：本演练全程 --no-stop，不碰它）")
    log(f"  真身数据目录 mtime 未变：{RESULTS['cleanup']['real_data_mtime_unchanged']}")
    # 只判 8020：8000 上是用户自己的实例（`local-environment` 第 2 节），与本演练无关；
    # 本演练从不带 --stop，也不重启，所以它不该被我们停掉——停掉才是问题。
    if port_8020:
        problem("收尾时 8020 还有监听")
    if not RESULTS["cleanup"]["real_data_mtime_unchanged"]:
        problem("真身数据目录被动了")

    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        note(f"保留一次性目录：{work}")
    return 0


def finish(code: int) -> int:
    log("")
    log("## 总判")
    log(f"  判红 {len(RESULTS['problems'])} 条")
    for item in RESULTS["problems"]:
        log(f"  · {item}")
    RESULTS["verdict"] = "PASS" if not RESULTS["problems"] and RESULTS.get("facts") else "FAIL"
    log(f"  离线演练：{RESULTS['verdict']}")
    (HERE / "verify-offline-drill.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
    (HERE / "verify-offline-drill.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n证据已写：verify-offline-drill.txt / .json")
    return code if not RESULTS["problems"] else 1


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except Exception as exc:  # noqa: BLE001 —— 崩了也要留原始证据
        import traceback
        problem(f"脚本异常：{type(exc).__name__}: {exc}")
        log(traceback.format_exc())
    finally:
        raise SystemExit(finish(exit_code))
