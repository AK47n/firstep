# -*- coding: utf-8 -*-
"""把沙箱「模拟用户机」还原成**真 v1.1.1**（工单 `update-restart-stale-service/03`）。

为什么必须还原真旧树：本特性修的判据是「更新换完文件后，启动器把僵着的旧进程踢掉重起」，
而「僵着的旧进程」只有在**发起更新的那一代没传 `--port`** 时才会出现。今天沙箱里跑的
webapp 已经带 `--port` 修复——只把版本号改回 1.1.1 是**验不出这条修复的**（更新器会正确停掉
端口，旧进程根本不存在，采纳的判据会在「一行修复都没写」的情况下也变绿）。

来源 = 本机那份**没下过线的全量包** `firstep-pack\\firstep-full-v1.1.1.zip`（783 MB / 8777 文件 /
清单 `version=v1.1.1`），不是 `make_sim_sandbox.py`——那个脚本是从**当前工作树**拷的，
重建出来还是今天的代码。

做四件事（每一步都带前置断言，缺一即拒）：

1. 把现沙箱里两个 B2 演练标记记账（路径 / 字节 / sha256）后**随重建消失**——它们的内容是
   `drill-02-degraded.py` 里**完全确定**地造出来的（固定文本 + 固定重复字节），重跑那支演练即可复现，
   所以不入库也不丢证据；
2. 把包内**没有**的沙箱专用入口 `sim-run.py` 先暂存到 `%TEMP%`；
3. 清空工具根 → 用 **Python zipfile** 解包（走长路径 API；资源管理器那条老 API 在 259 字符就截断，
   而本包里有 223 字符的深路径，见 `local-environment` 第 6 节）；
4. 按更新器 `write_materials_baseline` 的同款口径，把清单里的资料库基线写回
   `sources/materials/.materials-manifest.json`（真实用户是完整包换装那一步写的，解包不会写）。

用法::

    python .scratch/update-restart-stale-service/rebuild-sandbox-v111.py           # dry-run，只核对
    python .scratch/update-restart-stale-service/rebuild-sandbox-v111.py --write   # 真重建（会清空沙箱）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
HOME = Path.home()
SIM_ROOT = HOME / "Desktop" / "firstep-sim"
SIM_DATA = HOME / ".contest_generator_sim"
PACK_DIR = HOME / "Desktop" / "firstep-pack"
ZIP = PACK_DIR / "firstep-full-v1.1.1.zip"
MANIFEST = PACK_DIR / "firstep-full-v1.1.1.manifest.json"
#: 包内没有、但沙箱起服务要用（生产入口的配置路径写死在真身数据目录）。
#: 这里是它的**恢复副本**：2026-09-19 一次失败的重建把沙箱里的原件连目录一起删了
#: （擦除中途撞上「目录被别的进程占着」→ 内容已清空、根没删掉），所以留一份在库里，
#: 重建脚本优先用沙箱里那份、没有就用这份。
SANDBOX_ENTRY = "sim-run.py"
SANDBOX_ENTRY_COPY = HERE / "sandbox-entry-sim-run.py"
#: 上一个演练留下的痕迹（记账后随重建消失；内容可由 drill-02 确定性复现）
B2_MARKERS = (
    "sources/materials/.b2-drill-marker.txt",
    "sources/materials/.b2-drill-payload.bin",
)
EXPECTED_START_VERSION = "1.1.1"

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


def robust_rmtree(path: Path) -> None:
    """删目录树：深路径（>260 字符）要退回 `\\\\?\\` 前缀那条 API。"""
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
        return
    except OSError as exc:
        log(f"  普通删除失败（{exc}）——改用长路径前缀重试")
    shutil.rmtree("\\\\?\\" + str(path))


def read_spawn_updater(text: str) -> str:
    """截出 `spawn_updater` 的函数体（到下一个顶层 `def` 或 `@app` 为止）。"""
    start = text.find("def spawn_updater(")
    if start < 0:
        return ""
    tail = text[start:]
    for stop in ("\ndef ", "\n@app", "\nclass "):
        index = tail.find(stop, 1)
        if index > 0:
            tail = tail[:index]
    return tail


def manifest_file_entry(manifest: dict, relative: str) -> dict | None:
    for item in manifest.get("files") or []:
        if str(item.get("path")) == relative:
            return item
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="真重建（会清空沙箱工具根）")
    args = parser.parse_args()

    log("# 沙箱还原：真 v1.1.1（工单 update-restart-stale-service/03）")
    log(f"  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("")

    # ---- 零、前置事实 ----
    log("## 零、前置事实")
    facts = {
        "zip_exists": ZIP.is_file(),
        "zip_bytes": ZIP.stat().st_size if ZIP.is_file() else 0,
        "manifest_exists": MANIFEST.is_file(),
        "sim_root_exists": SIM_ROOT.is_dir(),
        "sim_entry_exists": (SIM_ROOT / SANDBOX_ENTRY).is_file(),
        "sim_entry_copy_exists": SANDBOX_ENTRY_COPY.is_file(),
        "sim_data_exists": SIM_DATA.is_dir(),
        "sim_data_config": (SIM_DATA / "config.json").is_file(),
    }
    manifest: dict = {}
    if facts["manifest_exists"]:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        facts["manifest_version"] = str(manifest.get("version") or "")
        facts["manifest_files"] = len(manifest.get("files") or [])
        facts["manifest_materials_batches"] = len(
            (manifest.get("materials_manifest") or {}).get("batches") or [])
    for key, value in facts.items():
        log(f"  {key} = {value!r}")
    RESULTS["facts"] = facts

    for key in ("zip_exists", "manifest_exists", "sim_root_exists"):
        if not facts[key]:
            problem(f"前置不成立：{key}")
    if not (facts["sim_entry_exists"] or facts["sim_entry_copy_exists"]):
        problem(f"前置不成立：{SANDBOX_ENTRY} 既不在沙箱也不在库里（{SANDBOX_ENTRY_COPY}）")
    if RESULTS["problems"]:
        return 2
    if facts.get("manifest_version", "").lstrip("vV") != EXPECTED_START_VERSION:
        problem(f"清单版本是 {facts.get('manifest_version')!r}，不是 {EXPECTED_START_VERSION}")
        return 2

    # ---- 一、B2 标记记账（它们会被清掉）----
    log("")
    log("## 一、B2 演练标记（记账后随重建消失；内容可由 drill-02 确定性复现）")
    markers: list[dict] = []
    for relative in B2_MARKERS:
        path = SIM_ROOT / relative
        entry = {"path": relative, "exists": path.is_file()}
        if path.is_file():
            entry["bytes"] = path.stat().st_size
            entry["sha256"] = sha256_of(path)
        else:
            note(f"{relative} 不在场（可能已被清过）")
        markers.append(entry)
        log(f"  {relative}: {entry.get('bytes', '—')} 字节 / {str(entry.get('sha256', ''))[:16]}…")
    RESULTS["b2_markers"] = markers
    (HERE / "b2-markers.json").write_text(
        json.dumps(markers, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 二、暂存包内没有的沙箱入口 ----
    staging = Path(tempfile.mkdtemp(prefix="fe-sandbox-entry-"))
    staged_entry = staging / SANDBOX_ENTRY
    source = (SIM_ROOT / SANDBOX_ENTRY) if facts["sim_entry_exists"] else SANDBOX_ENTRY_COPY
    shutil.copy2(source, staged_entry)
    log("")
    log("## 二、沙箱专用入口已暂存")
    log(f"  来源：{source}")
    log(f"  → {staged_entry}（{staged_entry.stat().st_size} 字节）")

    if not args.write:
        log("")
        log("（dry-run：加 --write 才真清空并解包）")
        return 0

    # ---- 三、清空 + 解包 ----
    log("")
    log("## 三、清空工具根 → 解包 v1.1.1（Python zipfile，走长路径 API）")
    robust_rmtree(SIM_ROOT)
    if SIM_ROOT.exists():
        problem("工具根没删干净")
        return 2
    SIM_ROOT.mkdir(parents=True)
    started = time.time()
    with zipfile.ZipFile(ZIP) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        archive.extractall(SIM_ROOT)
    elapsed = time.time() - started
    extracted = sum(1 for path in SIM_ROOT.rglob("*") if path.is_file())
    log(f"  解包 {len(members)} 个条目 / 落盘 {extracted} 个文件，耗时 {elapsed:.1f}s")
    RESULTS["extract"] = {"members": len(members), "files_on_disk": extracted,
                          "seconds": round(elapsed, 1)}

    shutil.copy2(staged_entry, SIM_ROOT / SANDBOX_ENTRY)
    log(f"  补回 {SANDBOX_ENTRY}（包内没有，生产入口的配置路径写死在真身数据目录）")

    # ---- 四、资料库基线写回（更新器那一步做过的，解包不会做）----
    log("")
    log("## 四、资料库基线写回（口径 = tools/update-app.py 的 write_materials_baseline）")
    materials = manifest.get("materials_manifest")
    if isinstance(materials, dict) and materials:
        target = SIM_ROOT / "sources" / "materials" / ".materials-manifest.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(materials, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        batches = len(materials.get("batches") or [])
        log(f"  已写回：{batches} 个批次 / version={materials.get('version')!r} → {target}")
        RESULTS["baseline"] = {"batches": batches, "version": materials.get("version"),
                              "files": len(materials.get("files") or [])}
    else:
        note("清单没带资料库基线——沙箱会缺这一件（真实用户是完整包换装时写回的）")
        RESULTS["baseline"] = None

    # ---- 五、判据：这棵树真是「会触发缺陷的那一代」----
    log("")
    log("## 五、判据（真旧代码 + 真旧启动器）")
    init_text = (SIM_ROOT / "src" / "contest_generator" / "__init__.py").read_text(
        encoding="utf-8")
    on_disk_version = ""
    for line in init_text.splitlines():
        if line.startswith("__version__"):
            on_disk_version = line.split('"')[1] if '"' in line else ""
    webapp_text = (SIM_ROOT / "src" / "contest_generator" / "webapp.py").read_text(
        encoding="utf-8")
    spawn = read_spawn_updater(webapp_text)
    full_apply = (SIM_ROOT / "src" / "contest_generator" / "full_apply.py").read_text(
        encoding="utf-8")
    bat_sha = sha256_of(SIM_ROOT / "start-app.bat")
    want_bat = manifest_file_entry(manifest, "start-app.bat") or {}

    checks = {
        "盘上版本 == 1.1.1": on_disk_version == EXPECTED_START_VERSION,
        "spawn_updater 命令里没有 --port（真旧缺陷）": bool(spawn) and '"--port"' not in spawn
        and "--port" not in spawn,
        "full_apply.py 里有 --port（对照：只缺那一条路）": '"--port"' in full_apply,
        "start-app.bat sha256 == v1.1.1 清单那一份（修复还没进沙箱）":
            bat_sha == str(want_bat.get("sha256") or "").lower(),
        "沙箱入口 sim-run.py 在位": (SIM_ROOT / SANDBOX_ENTRY).is_file(),
        "数据目录 config.json 未动": (SIM_DATA / "config.json").is_file(),
    }
    for label, ok in checks.items():
        log(f"  {'成立' if ok else '**不成立**'}：{label}")
    RESULTS["checks"] = checks
    RESULTS["on_disk_version"] = on_disk_version
    RESULTS["start_app_bat_sha256"] = bat_sha
    RESULTS["expected_start_app_bat_sha256"] = str(want_bat.get("sha256") or "")
    RESULTS["spawn_updater_has_port"] = "--port" in spawn
    for label, ok in checks.items():
        if not ok:
            problem(f"判据不成立：{label}")

    shutil.rmtree(staging, ignore_errors=True)
    return 0


def finish(code: int) -> int:
    (HERE / "verify-03-sandbox-rebuild.txt").write_text("\n".join(LINES) + "\n",
                                                        encoding="utf-8")
    RESULTS["problems_count"] = len(RESULTS["problems"])
    RESULTS["pass"] = not RESULTS["problems"]
    (HERE / "verify-03-sandbox-rebuild.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    log("")
    log(f"  沙箱还原：{'PASS' if not RESULTS['problems'] else 'FAIL'}")
    (HERE / "verify-03-sandbox-rebuild.txt").write_text("\n".join(LINES) + "\n",
                                                        encoding="utf-8")
    print(f"\n证据已写：verify-03-sandbox-rebuild.txt / .json")
    return code


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except Exception as exc:  # noqa: BLE001 —— 重建脚本崩了也要留原始证据
        import traceback
        problem(f"脚本异常：{type(exc).__name__}: {exc}")
        log(traceback.format_exc())
    finally:
        raise SystemExit(finish(exit_code if not RESULTS["problems"] else 1))
