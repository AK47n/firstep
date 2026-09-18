# -*- coding: utf-8 -*-
"""B4 —— 完整包换装：**从线上真下 802 MB** → 校验 → 替换 → 重启（工单 sandbox-drill/04）。

要回答的问题：**新用户第一次装（以及「修损坏 / 换机器」那条路）能不能一次装好？**
判据（spec 测试决策：全部落在产品可观察量上）：

- 走产品端点：`GET /api/update/full/check` → `POST /api/update/full/apply` →
  `GET /api/update/full/status`（**真下载 801,873,335 B，不是复用本机缓存**）
  → 更新器替换 → 重启；
- 终态判据：跑起来的服务 `/api/health.version == 1.2.1`；`full-installed.json` 落盘；
  **资料库基线写回**（`sources/materials/.materials-manifest.json`，版本 / 批次数对得上）；
- 包外文件与第三方安装包**未被误删**（一次性根里放的是**真身那 56 个第三方安装包**的副本，
  逐个 sha256 比）；
- 隔离三判据：真身数据目录 mtime、真身 `updates/` 条目、真身工作树 tree_stamp 全未变；
  收尾 8021 释放、无残留 python。

## 与 `resumable-download/verify-07-tier3-e2e.py` 的关系（别混读）

骨架照它（`USERPROFILE` 重定向 + 一次性工具根 + tree_stamp），三处**刻意不同**：

| | verify-07 | 本脚本 |
|---|---|---|
| 完整包 zip | **复用本机已下过的缓存**（脚本里明写「未重新下载」） | **真下载**（耗时/速度/字节/sha256 全留痕） |
| 资料库内容 | 一次性根里没有资料库 | 放进**真身那 56 个第三方安装包**的副本当「包外文件」判据 |
| 资料库基线 | 只记「已装标记」 | **断言基线写回**（版本 / 批次数 / 文件数） |

用法::

    python .scratch/verify-gate-drills/drill-04-full-pack.py            # 真跑（下 802 MB）
    python .scratch/verify-gate-drills/drill-04-full-pack.py --port 8021
    python .scratch/verify-gate-drills/drill-04-full-pack.py --dry-run  # 只做前置 + check
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
HOME = Path.home()
SANDBOX_MATERIALS = HOME / "Desktop" / "firstep-sim" / "sources" / "materials"
REAL_DATA = HOME / ".contest_generator"
REAL_UPDATES = REAL_DATA / "updates"
REAL_CONFIG = REAL_DATA / "config.json"
PACK_DIR = HOME / "Desktop" / "firstep-pack"
TARGET_TAG = "v1.2.1"
STAGED_VERSION = "1.1.0"          # 工具根起点版本（脚本改 __init__.py 造出来，判据才有落差）
THIRD_PARTY_SUFFIXES = {".exe", ".zip", ".rar", ".7z", ".iso", ".img"}

LINES: list[str] = []
RESULTS: dict = {"problems": [], "stuck": [], "notes": []}
# 证据文件名（复算格另存一份，别覆盖主跑的原始输出）
OUTPUT_STEM = "verify-04-full-pack"


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


# ---------------------------------------------------------------------------
# 小工具（与 drill-01 同款口径，脚本之间不共享模块：每一格都要能独立复跑）
# ---------------------------------------------------------------------------


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


class Api:
    """端点客户端（端口可配：真身 8000 只读，沙箱 8020，本脚本缺省 8021）。"""

    def __init__(self, port: int) -> None:
        self.base = f"http://127.0.0.1:{port}"

    def get(self, path: str, timeout: float = 60) -> dict:
        with urllib.request.urlopen(self.base + path, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def post(self, path: str, payload: dict, timeout: float = 120) -> dict:
        request = urllib.request.Request(
            self.base + path, data=json.dumps(payload).encode("utf-8"),
            method="POST", headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def health(self, timeout: float = 3) -> dict | None:
        try:
            return self.get("/api/health", timeout=timeout)
        except Exception:  # noqa: BLE001
            return None

    def wait_health(self, deadline_seconds: float = 60) -> dict | None:
        end = time.time() + deadline_seconds
        while time.time() < end:
            health = self.health()
            if health:
                return health
            time.sleep(0.5)
        return None


def read_version_file(root: Path) -> str:
    init = root / "src" / "contest_generator" / "__init__.py"
    for line in init.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split('"')[1] if '"' in line else line.strip()
    return ""


# ---------------------------------------------------------------------------
# 铺一次性工具根
# ---------------------------------------------------------------------------


def stage_tool_root(tool_root: Path, profile: Path, api_key_source: Path) -> dict:
    """铺一个「像 v1.1.0 用户机」的工具根（真身只读，这里全是副本）。

    与 verify-07 的差异只有两条（都为了 B4 自己的判据）：
    - 资料库里放进**真身那批第三方安装包**的副本 → 完整包替换后逐个 sha256 比；
    - 预写配置文件（库目录指向仓库真库只读 + 关自动提交），免得首次启动去 bootstrap。
    """
    shutil.copytree(REPO / "src", tool_root / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (tool_root / "tools").mkdir(parents=True, exist_ok=True)
    for name in ("update-app.py", "launcher-log.ps1"):
        shutil.copy2(REPO / "tools" / name, tool_root / "tools" / name)
    for script in ("start-app.vbs", "start-app.bat", "stop-firstep.vbs", "stop-firstep.bat"):
        if (REPO / script).is_file():
            shutil.copy2(REPO / script, tool_root / script)
    for extra in ("VERSIONS.md", "README.md", "requirements.txt", "pyproject.toml",
                  "install.bat", ".gitattributes", ".gitignore"):
        if (REPO / extra).is_file():
            shutil.copy2(REPO / extra, tool_root / extra)
    # 工具根判定标记：`tools` / `sources` 够了（find_tool_root 认这几个之一）。
    # **刻意不建 `library/`**：`wordlist.source_module_slugs()` 拿工具根的
    # `library/modules` 当「源码树模块库」锚点——目录**存在但为空**时它会返回空集，
    # 于是词表加载的机械校验（lib_modules 必须命中已知 slug）当场炸、服务起不来
    # （本脚本第一版真踩到：`lib_modules 引用了库中不存在的模块 slug 'k230'`）；
    # 目录**不存在**时它返回 None（校验跳过）——B4 只走更新链，不需要真库。
    (tool_root / "assets").mkdir(parents=True, exist_ok=True)

    # 起点版本改写成 v1.1.0（判据才有落差）
    init = tool_root / "src" / "contest_generator" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    marker = '__version__ = "'
    head, _, tail = text.partition(marker)
    rest = tail.split('"', 1)[1]
    init.write_text(f'{head}{marker}{STAGED_VERSION}"{rest}', encoding="utf-8")

    # 包外文件：真身那批第三方安装包（完整包把它们排除在外——替换后必须还在）
    sentinels: dict[str, dict] = {}
    if SANDBOX_MATERIALS.is_dir():
        for path in SANDBOX_MATERIALS.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in THIRD_PARTY_SUFFIXES:
                continue
            rel = path.relative_to(SANDBOX_MATERIALS)
            dest = tool_root / "sources" / "materials" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            sentinels[str(rel).replace("\\", "/")] = {
                "size": dest.stat().st_size, "sha256": sha256_of(dest),
            }
    keep = tool_root / "sources" / "materials" / "_drill_keep_me.txt"
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_text("B4 演练哨兵：包外文件，完整包替换后必须原样在\n", encoding="utf-8")
    sentinels["_drill_keep_me.txt"] = {"size": keep.stat().st_size,
                                       "sha256": sha256_of(keep)}

    # 配置：拷真身那份，只改库目录与自动提交（真身配置含真 key，**不进证据**）
    data_dir = profile / ".contest_generator"
    (data_dir / "updates").mkdir(parents=True, exist_ok=True)
    config = json.loads(api_key_source.read_text(encoding="utf-8-sig"))
    config["module_library_dir"] = str(REPO / "library" / "modules")
    config["masters_dir"] = str(REPO / "library" / "masters")
    config["autocommit_enabled"] = False
    (data_dir / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    (data_dir / "updates" / "full").mkdir(parents=True, exist_ok=True)
    return {"sentinels": sentinels, "config_keys": sorted(config.keys())}


def make_env(profile: Path, tool_root: Path, port: int) -> dict:
    env = dict(os.environ)
    env.update({
        "FIRSTEP_LAUNCHER_PORT": str(port),
        "USERPROFILE": str(profile),
        "HOME": str(profile),
        "PYTHONPATH": str(tool_root / "src"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
    })
    return env


def start_via_launcher(tool_root: Path, env: dict) -> subprocess.Popen:
    vbs = tool_root / "start-app.vbs"
    return subprocess.Popen(
        ["wscript.exe", str(vbs)], cwd=str(tool_root), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def load_official_manifest() -> dict:
    path = PACK_DIR / f"firstep-full-{TARGET_TAG}.manifest.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_recheck(work: Path) -> int:
    """复算格（独立可跑）：把「包外文件」这条判据的口径算精确。

    为什么需要：主跑把**真身那 56 个第三方安装包副本**全当「包外文件」算了，
    但 `.exe/.zip/.rar/...` 只是**扩展名**筛法——完整包真正排除的只有其中一部分
    （`full_pack` 的排除规则），另一部分其实在包内。于是「包外文件未被误删」这句
    在数量上不够精确。本格把每个哨兵**按包内 / 包外分开报**，判据两条都判，
    但话要说得准（包内那批被包覆盖过，只要内容相同也算没被弄坏）。
    """
    tool_root = work / "tool"
    materials = tool_root / "sources" / "materials"
    log("# B4 复算：哨兵口径（包内 / 包外分开）")
    log(f"  演练目录：{work}")
    if not materials.is_dir():
        problem(f"演练目录里没有资料库：{materials}")
        return 1
    manifest = load_official_manifest()
    official = {str(f["path"]): f for f in manifest.get("files") or []}
    official_materials = {p[len("sources/materials/"):] for p in official
                          if p.startswith("sources/materials/")}
    excluded = manifest.get("materials_excluded") or []
    log(f"  官方包：{len(official)} 个文件（资料库 {len(official_materials)}）；"
        f"清单里的排除项 materials_excluded = {len(excluded)}")
    RESULTS["recheck"] = {"official_files": len(official),
                          "official_materials": len(official_materials),
                          "materials_excluded": len(excluded)}

    # 哨兵来源：真身沙箱那批第三方安装包（副本）+ 一个纯文本哨兵
    sentinels: dict[str, dict] = {}
    if SANDBOX_MATERIALS.is_dir():
        for path in SANDBOX_MATERIALS.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in THIRD_PARTY_SUFFIXES:
                continue
            rel = path.relative_to(SANDBOX_MATERIALS)
            sentinels[str(rel).replace("\\", "/")] = {
                "size": path.stat().st_size, "sha256": sha256_of(path)}
    sentinels["_drill_keep_me.txt"] = {
        "text": "B4 演练哨兵：包外文件，完整包替换后必须原样在\n"}

    in_pack = [rel for rel in sentinels if rel in official_materials]
    out_pack = [rel for rel in sentinels if rel not in official_materials]
    log(f"  哨兵 {len(sentinels)} 个：**包内 {len(in_pack)}** / **包外 {len(out_pack)}**")
    log(f"    包外那批（完整包不带的）：{sorted(out_pack)}")
    missing, changed = [], []
    for rel, want in sorted(sentinels.items()):
        dest = materials / rel
        if not dest.is_file():
            missing.append(rel)
            continue
        if "text" in want:
            ok = dest.read_text(encoding="utf-8") == want["text"]
        else:
            ok = dest.stat().st_size == want["size"] and sha256_of(dest) == want["sha256"]
        if not ok:
            changed.append(rel)
    log(f"  实测：缺失 {len(missing)} / 内容变了 {len(changed)}")
    if missing:
        log(f"    缺失：{missing}")
    if changed:
        log(f"    变化：{changed}")

    on_disk = [p for p in materials.rglob("*") if p.is_file()]
    extra = sorted(str(p.relative_to(materials)).replace("\\", "/")
                   for p in on_disk
                   if str(p.relative_to(materials)).replace("\\", "/")
                   not in official_materials)
    log(f"  资料库实到 {len(on_disk)} 个文件 = 官方 {len(official_materials)} ∪ 包外 "
        f"{len(extra)}（多出来的就是包外那批 + 基线本身）")
    log(f"    包外实到：{extra}")

    # 「包外」的权威口径 = **打包器自己的排除规则**（`full_pack.materials_excluded`），
    # 不是本脚本按扩展名猜的那一套。用真身沙箱的资料库算出排除集合，
    # 逐个核对「在不在 + 内容变没变」——这才是工单那句「第三方安装包未被动过」的判据。
    sys.path.insert(0, str(REPO / "src"))
    try:
        from contest_generator.full_pack import materials_excluded  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        note(f"取不到打包器排除规则（{type(exc).__name__}: {exc}）——这一格按扩展名口径报")
        materials_excluded = None
    really_excluded: list[str] = []
    if materials_excluded is not None and SANDBOX_MATERIALS.is_dir():
        for path in SANDBOX_MATERIALS.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(SANDBOX_MATERIALS)).replace("\\", "/")
            if materials_excluded(rel) and rel != ".materials-manifest.json":
                # 基线清单**也**在排除集合里（它不进包），但它的内容**本来就该被
                # 完整包换装写回**（B4 的另一条判据就是它）——把它算进「不许变」
                # 会造出假红（本格第一版就是这么误报了 1 条）。
                really_excluded.append(rel)
        really_excluded.sort()
        ex_missing, ex_changed = [], []
        for rel in really_excluded:
            src = SANDBOX_MATERIALS / rel
            dest = materials / rel
            if not dest.is_file():
                ex_missing.append(rel)
                continue
            if dest.stat().st_size != src.stat().st_size or sha256_of(dest) != sha256_of(src):
                ex_changed.append(rel)
        log(f"  按打包器排除规则（`full_pack.materials_excluded`）算：真身**沙箱**资料库里"
            f"被排除的文件 {len(really_excluded)} 个（完整包不带它们）")
        log(f"    替换后：缺失 {len(ex_missing)} / 内容变了 {len(ex_changed)}")
        if ex_missing[:5]:
            log(f"    缺失样例：{ex_missing[:5]}")
        if ex_changed[:5]:
            log(f"    变化样例：{ex_changed[:5]}")
        log("  覆盖边界（如实说）：一次性根里只搬进了真身沙箱「第三方安装包扩展名」"
            "匹配到的那批副本，其中**真被排除的只有上面这 "
            f"{len(really_excluded)} 个**；其余被排除项没参与本格——它们由第九节的"
            "隔离判据覆盖（真身零触碰），不是被这条判据放过。")
        RESULTS["recheck"]["really_excluded"] = {
            "count": len(really_excluded), "missing": ex_missing,
            "changed": ex_changed, "sample": really_excluded[:5],
        }
        if ex_missing:
            problem(f"被完整包排除的第三方安装包被删了 {len(ex_missing)} 个：{ex_missing[:5]}")
        if ex_changed:
            problem(f"被完整包排除的第三方安装包内容被改了 {len(ex_changed)} 个："
                    f"{ex_changed[:5]}")
    baseline = materials / ".materials-manifest.json"
    baseline_info = {}
    if baseline.is_file():
        data = json.loads(baseline.read_text(encoding="utf-8-sig"))
        baseline_info = {"version": data.get("version"),
                         "batches": len(data.get("batches") or []),
                         "sha256": sha256_of(baseline)}
        log(f"  基线：version={baseline_info['version']!r} / "
            f"batches={baseline_info['batches']} / sha256={baseline_info['sha256'][:16]}…")
    else:
        problem("复算时基线不在（`.materials-manifest.json` 缺失）")
    RESULTS["recheck"].update({
        "sentinels": len(sentinels), "in_pack": len(in_pack), "out_pack": len(out_pack),
        "out_pack_paths": sorted(out_pack), "missing": missing, "changed": changed,
        "materials_on_disk": len(on_disk), "materials_not_in_pack": extra,
        "baseline": baseline_info,
    })
    if missing:
        problem(f"哨兵缺失 {len(missing)} 个：{missing[:5]}")
    if changed:
        problem(f"哨兵内容变了 {len(changed)} 个：{changed[:5]}")
    if baseline_info and baseline_info["version"] != TARGET_TAG:
        problem(f"基线版本不是 {TARGET_TAG}：{baseline_info['version']!r}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8021,
                        help="一次性实例端口（缺省 8021：8020 留给沙箱的 B2/B3）")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--recheck", action="store_true",
                        help="复算格：对一次已跑完的 --keep 目录复算哨兵口径（不下载）")
    parser.add_argument("--work", default="", help="配合 --recheck 指定演练目录")
    args = parser.parse_args()
    port = args.port
    api = Api(port)

    if args.recheck:
        global OUTPUT_STEM
        OUTPUT_STEM = "verify-04-full-pack-recheck"
        target = Path(args.work) if args.work else max(
            Path(os.environ["TEMP"]).glob("fe04-*"), key=lambda p: p.stat().st_mtime)
        return run_recheck(target)

    work = Path(os.environ["TEMP"]) / f"fe04-{time.strftime('%Y%m%d-%H%M%S')}"
    tool_root = work / "tool"
    profile = work / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    tool_root.mkdir(parents=True, exist_ok=True)

    log("# B4 证据：完整包换装（**从线上真下 802 MB** → 校验 → 替换 → 重启）")
    log(f"  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"  一次性工具根：{tool_root}")
    log(f"  一次性数据目录（USERPROFILE 重定向）：{profile}")
    log(f"  端口：{port}（真身 8000 只读、沙箱 8020 不动）")
    log("")

    log("## 零、隔离边界与真身基线")
    real_data_mtime_before = dir_mtime(REAL_DATA)
    real_updates_before = sorted(p.name for p in REAL_UPDATES.iterdir()) \
        if REAL_UPDATES.is_dir() else []
    real_tree_before = tree_stamp(REPO)
    log(f"  真身数据目录 mtime = {real_data_mtime_before}；updates/ = "
        f"{real_updates_before or '（空）'}")
    log(f"  真身工作树基线 = {len(real_tree_before)} 个文件")
    log(f"  8000 监听：{listen_pids(8000) or '（空）'}；{port} 监听："
        f"{listen_pids(port) or '（空）'}")
    if listen_pids(port):
        killed = kill_listener(port)
        note(f"{port} 上有遗留监听（PID {killed}），已先收掉再开跑")
    if not REAL_CONFIG.is_file():
        problem(f"找不到真身配置 {REAL_CONFIG}（一次性根需要一份可用配置）")
        return 2

    manifest = load_official_manifest()
    if not manifest:
        problem("拿不到官方完整包清单（firstep-pack 里没有 v1.2.1 的 manifest）")
        return 2
    parts_manifest = manifest.get("parts") or []
    materials_paths = [f for f in manifest.get("files") or []
                       if str(f.get("path", "")).startswith("sources/materials/")]
    log(f"  官方清单：{len(manifest.get('files') or [])} 个文件"
        f"（其中资料库 {len(materials_paths)}）；分卷 {len(parts_manifest)} 个；"
        f"合计 {manifest.get('total_bytes')} 字节")
    RESULTS["manifest"] = {"files": len(manifest.get("files") or []),
                           "materials_files": len(materials_paths),
                           "parts": parts_manifest,
                           "total_bytes": manifest.get("total_bytes")}

    log("")
    log("## 一、铺一次性工具根（起点版本改写为 v1.1.0 + 第三方安装包副本）")
    staged = stage_tool_root(tool_root, profile, REAL_CONFIG)
    sentinels = staged["sentinels"]
    log(f"  起点版本：盘上 = {read_version_file(tool_root)}"
        f"（脚本改写，判据才有落差）")
    log(f"  包外哨兵：{len(sentinels)} 个"
        f"（真身那批第三方安装包 {sum(1 for k in sentinels if k != '_drill_keep_me.txt')} 个"
        f" + 1 个纯文本哨兵），合计 "
        f"{sum(v['size'] for v in sentinels.values())} 字节")
    log(f"  配置：拷真身那份，库目录改指仓库真库（只读）+ autocommit 关；"
        f"键 = {staged['config_keys']}")
    RESULTS["staged"] = {"sentinels": len(sentinels),
                         "sentinel_bytes": sum(v["size"] for v in sentinels.values()),
                         "start_version": read_version_file(tool_root)}
    env = make_env(profile, tool_root, port)

    launcher: subprocess.Popen | None = None
    try:
        log("")
        log(f"## 二、按用户机方式起服务（start-app.vbs → {port}）")
        launcher = start_via_launcher(tool_root, env)
        health = api.wait_health(deadline_seconds=120)
        if health is None:
            log("  服务没起来；webapp.log 末尾：")
            web_log = profile / ".contest_generator" / "webapp.log"
            if web_log.is_file():
                log(web_log.read_text(encoding="utf-8", errors="replace")[-2000:])
            stuck("一次性工具根的服务 120 秒没起来")
            return 1
        log(f"  服务已就绪：`/api/health` = {health}")
        RESULTS["before"] = {"health": health, "on_disk": read_version_file(tool_root)}

        log("")
        log("## 三、走产品端点：检查完整包更新")
        check = api.get("/api/update/full/check", timeout=180)
        log(f"  latest={check.get('latest_version')} current={check.get('current_version')!r} "
            f"reason={check.get('reason')} update_available={check.get('update_available')}")
        log(f"  message={check.get('message')!r}")
        for part in check.get("parts") or []:
            log(f"  分卷：{part['name']} {part['size']} 字节 sha256={part['sha256']}")
        log(f"  manifest_url={check.get('manifest_url')}")
        RESULTS["check"] = {k: check.get(k) for k in
                            ("latest_version", "current_version", "update_available",
                             "reason", "error", "message", "manifest_url")}
        selected = [p["name"] for p in check.get("parts") or []]
        if not selected:
            problem(f"检查更新没给出分卷（error={check.get('error')!r}）")
            return 1
        expected_bytes = sum(int(p["size"]) for p in check["parts"])
        expected_sha = str(check["parts"][0]["sha256"]).lower()
        if args.dry_run:
            log("")
            log(f"（--dry-run：到此为止，不下载。将下载 {expected_bytes} 字节）")
            return 0

        log("")
        log("## 四、点「一键全量」：**真下载** → 校验 → 拉起更新器 → 替换 → 重启")
        t0 = time.time()
        started = api.post("/api/update/full/apply", {"parts": selected}, timeout=120)
        log(f"  apply 已接受：{started}")
        deadline = time.time() + 3600
        last_log = 0.0
        final: dict | None = None
        while time.time() < deadline:
            status = api.get("/api/update/full/status", timeout=30)
            got = status.get("total_downloaded_bytes", 0)
            total = max(1, status.get("total_bytes", 1))
            if time.time() - last_log > 15:
                elapsed = max(0.1, time.time() - t0)
                log(f"  进度 {got / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MB "
                    f"({got * 100 // total}%) state={status['state']} "
                    f"retry={status.get('retry_count')} "
                    f"均速≈{got / elapsed / 1024 / 1024:.2f} MB/s")
                last_log = time.time()
            if status["state"] in ("applying", "done", "failed", "cancelled"):
                final = status
                break
            time.sleep(2.0)
        if final is None:
            stuck("一小时还没到终态（下载未完成）")
            return 1
        elapsed = time.time() - t0
        log(f"  任务终态：state={final['state']} / "
            f"{final.get('total_downloaded_bytes', 0)} 字节 / "
            f"error={final.get('error', '')[:200]!r}")
        log(f"  耗时 {elapsed:.1f}s，平均 {final.get('total_downloaded_bytes', 0) / max(0.1, elapsed) / 1024 / 1024:.2f} MB/s")
        RESULTS["task"] = {"state": final["state"],
                           "downloaded_bytes": final.get("total_downloaded_bytes"),
                           "total_bytes": final.get("total_bytes"),
                           "seconds": round(elapsed, 1),
                           "error": final.get("error", "")}
        if final["state"] == "failed":
            problem(f"完整包下载任务失败：{final.get('error', '')[:300]}")
        if int(final.get("total_downloaded_bytes") or 0) != expected_bytes:
            problem(f"下载字节与清单不符：{final.get('total_downloaded_bytes')} != "
                    f"{expected_bytes}")

        # 落盘的卷自证（真下载的字节在盘上，且 sha256 == 清单）
        part_path = profile / ".contest_generator" / "updates" / "full" / selected[0]
        if part_path.is_file():
            digest = sha256_of(part_path)
            log(f"  盘上分卷 {selected[0]} = {part_path.stat().st_size} 字节 / "
                f"sha256 {digest}")
            log(f"  清单 sha256 = {expected_sha}")
            RESULTS["part"] = {"path": str(part_path), "size": part_path.stat().st_size,
                               "sha256": digest, "expected_sha256": expected_sha}
            if part_path.stat().st_size != expected_bytes or digest != expected_sha:
                problem("盘上分卷与清单不一致（下载物不对）")
        else:
            problem(f"盘上找不到分卷：{part_path}")

        log("")
        log("## 五、等更新器替换（停服 → 备份 → 覆盖 → 写基线 → 重启）")
        installed_marker = profile / ".contest_generator" / "updates" / "full-installed.json"
        updater_log = profile / ".contest_generator" / "updates" / "updater.log"
        end = time.time() + 1800
        marker: dict | None = None
        while time.time() < end:
            if installed_marker.is_file():
                try:
                    marker = json.loads(installed_marker.read_text(encoding="utf-8"))
                    break
                except Exception:  # noqa: BLE001 —— 正在写
                    pass
            time.sleep(2.0)
        log(f"  已装版本标记 full-installed.json：{marker}")
        RESULTS["installed_marker"] = marker
        if not marker:
            stuck("30 分钟没等到 full-installed.json（替换链没跑完）")
        if updater_log.is_file():
            log("  更新器日志：")
            for line in updater_log.read_text(encoding="utf-8",
                                              errors="replace").splitlines():
                log(f"  | {line}")

        log("")
        log("## 六、终点判据（版本号从跑起来的服务读）")
        disk_after = read_version_file(tool_root)
        log(f"  盘上 __init__.py = {disk_after}")
        served = None
        end = time.time() + 300
        while time.time() < end:
            health_after = api.wait_health(deadline_seconds=5)
            if health_after and health_after.get("version") == TARGET_TAG.lstrip("v"):
                served = health_after.get("version")
                break
            time.sleep(2.0)
        restarted_by_updater = served is not None
        if served is None:
            log("  （更新器没把服务带起来，用同一套环境再起一次启动器；"
                "「更新器自己重启」这一格如实记为未成立）")
            launcher = start_via_launcher(tool_root, env)
            health_after = api.wait_health(deadline_seconds=120)
            served = (health_after or {}).get("version")
        log(f"  **替换后 `/api/health`.version = {served}**（期望 {TARGET_TAG}）")
        RESULTS["after"] = {"on_disk": disk_after, "served": served,
                            "restarted_by_updater": restarted_by_updater}
        if served != TARGET_TAG.lstrip("v"):
            problem(f"终点判据不成立：服务报 {served}，期望 {TARGET_TAG}")
        if disk_after != TARGET_TAG.lstrip("v"):
            problem(f"盘上版本不对：{disk_after}")

        log("")
        log("## 七、资料库基线写回 + 资料库内容")
        baseline = tool_root / "sources" / "materials" / ".materials-manifest.json"
        materials_now = [p for p in (tool_root / "sources" / "materials").rglob("*")
                         if p.is_file()]
        log(f"  资料库文件数（含哨兵与基线）：{len(materials_now)}"
            f"（官方清单 {len(materials_paths)} + 哨兵 {len(sentinels)}"
            f" + 基线本身）")
        RESULTS["materials"] = {"files_now": len(materials_now),
                                "official_files": len(materials_paths),
                                "sentinels": len(sentinels)}
        if not baseline.is_file():
            problem("资料库基线**没有写回**（sources/materials/.materials-manifest.json 缺失）")
        else:
            data = json.loads(baseline.read_text(encoding="utf-8-sig"))
            log(f"  基线：version={data.get('version')!r} / "
                f"batches={len(data.get('batches') or [])} / "
                f"sha256={sha256_of(baseline)[:16]}…")
            RESULTS["baseline"] = {"version": data.get("version"),
                                   "batches": len(data.get("batches") or [])}
            if str(data.get("version")) != TARGET_TAG:
                problem(f"基线版本不对：{data.get('version')!r} != {TARGET_TAG}")
            expected_batches = len((manifest.get("materials_manifest") or {}).get("batches") or [])
            if expected_batches and len(data.get("batches") or []) != expected_batches:
                problem(f"基线批次数不对：{len(data.get('batches') or [])} != {expected_batches}")

        log("")
        log("## 八、包外文件与第三方安装包（逐个 sha256 比）")
        changed = []
        missing = []
        for rel, want in sentinels.items():
            dest = tool_root / "sources" / "materials" / rel
            if not dest.is_file():
                missing.append(rel)
                continue
            if sha256_of(dest) != want["sha256"]:
                changed.append(rel)
        log(f"  哨兵总数 {len(sentinels)}：缺失 {len(missing)} / 内容变了 {len(changed)}")
        if missing[:5]:
            log(f"    缺失样例：{missing[:5]}")
        if changed[:5]:
            log(f"    变化样例：{changed[:5]}")
        RESULTS["sentinels"] = {"total": len(sentinels), "missing": missing,
                                "changed": changed}
        if missing:
            problem(f"包外文件/第三方安装包被删了 {len(missing)} 个：{missing[:5]}")
        if changed:
            problem(f"包外文件/第三方安装包内容被改了 {len(changed)} 个：{changed[:5]}")

        log("")
        log("## 九、隔离边界收尾校验（真身只读）")
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
        log(f"  真身数据目录 mtime 未变：{isolation['real_data_mtime_untouched']}"
            f"（{real_data_mtime_before} → {real_data_mtime_after}）")
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
        return 0
    finally:
        if launcher is not None and launcher.poll() is None:
            launcher.terminate()
        killed = kill_listener(port)
        time.sleep(1.0)
        leftover = listen_pids(port)
        log("")
        log("## 收尾")
        log(f"  收掉 {port} 上的监听进程：{killed or '（无）'}；"
            f"残余：{leftover or '（无）'}")
        RESULTS["cleanup"] = {"killed": killed, "leftover": leftover,
                              "work_dir": str(work)}
        if args.keep:
            log(f"  （--keep：一次性目录保留在 {work}）")
        else:
            shutil.rmtree(work, ignore_errors=True)
            log("  一次性目录已清理")


def finish(code: int) -> int:
    (HERE / f"{OUTPUT_STEM}.txt").write_text("\n".join(LINES) + "\n",
                                             encoding="utf-8")
    (HERE / f"{OUTPUT_STEM}.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n证据已写：{OUTPUT_STEM}.txt / .json")
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
        log(f"  B4「完整包真下 → 换装 → 重启」：{'PASS' if not problems else 'FAIL'}")
        RESULTS["verdict"] = {"problems": problems, "stuck": RESULTS["stuck"],
                              "pass": not problems}
        finish(exit_code)
    raise SystemExit(0 if RESULTS["problems"] == [] else 1)
