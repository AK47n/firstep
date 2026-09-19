# -*- coding: utf-8 -*-
"""用**工作树的源码**跑 drill-02（沙箱真机演练）的包装器——drill 本身一个字不改。

**为什么需要它**：`drill-02-degraded.py` 起的是**沙箱 `src/`** 那份代码（它自己的 docstring
写着「产品侧一点没改：起的是沙箱 src/（v1.2.1，与真身同源）的那套代码」）。所以要让**修好的
代码**被真机跑到，必须先把工作树的 `src/contest_generator/` 放进沙箱——那一步是 harness
动作，**不写进 drill**（它是冻结的量具），放在这里并在证据里显式记账。

做四件事：

1. 记账（drill 脚本 sha256 / 沙箱源码现状 / 一次性目录）；
2. 备份沙箱源码与 drill 自己的证据文件，再用工作树的源码覆盖沙箱的
   `src/contest_generator/`（**＝用户机上跑着的那一代代码**）；
3. 逐个场景跑 `drill-02-degraded.py --only <场景>`，把它的原始证据复制成本工具的
   `verify-real-machine-<场景>.{txt,json}`（drill 每次都写同一对文件名，不复制就会互相覆盖）；
4. `finally` 里**一律还原**沙箱源码与 drill 的原始证据文件，并做收尾检查
   （8020 释放、无残留 python、真身数据目录 mtime 未变）。

判据：每个场景都以 drill 自己的 `problems` / `stuck` 为准（空 = 该格成立），
外加按场景的追加判据（见 `EXTRA_CHECKS`）——例如内容不符那一格必须真的到终态。

用法::

    python .scratch/verify-gate-drills/run-drill-02-with-workspace-src.py \
        --evidence-dir .scratch/update-verify-failure-leftovers \
        --only verify-size --only cut-retry
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
from pathlib import Path

# 控制台是 GBK：脚本里的中文与 ✓/✗ 必须能出去，否则打印时抛 UnicodeEncodeError。
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
SIM_SRC = SIM_ROOT / "src" / "contest_generator"
WORKSPACE_SRC = REPO / "src" / "contest_generator"
DRILL = HERE / "drill-02-degraded.py"
DRILL_EVIDENCE = (HERE / "verify-02-degraded.txt", HERE / "verify-02-degraded.json")

#: 按场景的**追加**判据：(说明, 从 json 里取值的函数 -> bool)
EXTRA_CHECKS: dict[str, list[tuple[str, str]]] = {
    "verify-size": [
        ("半成品被清（updates/full/ 下不再有分卷）",
         "scenarios.verify-size.checks.半成品被清（updates/full/ 下不再有分卷）"),
        ("边车被清", "scenarios.verify-size.checks.边车被清"),
    ],
    "cut-retry": [],
    "content-mismatch": [
        ("终态到达（terminal_reached）", "scenarios.content-mismatch.terminal_reached"),
        ("终态 = failed（final_state）", "scenarios.content-mismatch.final_state"),
    ],
}

LINES: list[str] = []
RESULTS: dict = {"problems": [], "scenarios": {}}


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def problem(text: str) -> None:
    RESULTS["problems"].append(text)
    log(f"  [判红] {text}")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digest(root: Path) -> tuple[int, str]:
    """目录树的（文件数，聚合 sha256）——用来证明「放进去的 == 工作树那一份」。"""
    files = sorted(p for p in root.rglob("*") if p.is_file())
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return len(files), digest.hexdigest()


def digest_of(relative: Path, root: Path) -> str:
    return sha256_of(relative) if relative.is_file() else "(缺失)"


def pick(obj: object, dotted: str) -> object:
    """按点号路径取值（判据在 json 里的位置）；取不到返回 None。"""
    current = obj
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def run_scenario(name: str, evidence_dir: Path) -> None:
    log("")
    log("-" * 78)
    log(f"## 场景：{name}（drill-02 --only {name}）")
    command = [sys.executable, str(DRILL), "--only", name]
    began = time.time()
    proc = subprocess.run(command, cwd=str(REPO), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=1800)
    elapsed = time.time() - began
    log(f"  drill 退出码 {proc.returncode}（耗时 {elapsed:.1f}s）")

    json_path, txt_path = DRILL_EVIDENCE[1], DRILL_EVIDENCE[0]
    data: dict = {}
    if json_path.is_file():
        data = json.loads(json_path.read_text(encoding="utf-8-sig", errors="replace"))
    else:
        problem(f"场景 {name}：drill 没有写出 {json_path.name}")
    for source, suffix in ((txt_path, ".txt"), (json_path, ".json")):
        if source.is_file():
            target = evidence_dir / f"verify-real-machine-{name}{suffix}"
            shutil.copy2(source, target)

    entry: dict = {"drill_exit_code": proc.returncode, "seconds": round(elapsed, 1),
                   "drill_problems": data.get("problems") or [],
                   "drill_stuck": data.get("stuck") or [],
                   "notes": data.get("notes") or [],
                   "extra": {}}
    if entry["drill_problems"]:
        problem(f"场景 {name}：drill 报红 {entry['drill_problems']}")
    if entry["drill_stuck"]:
        problem(f"场景 {name}：drill 卡住 {entry['drill_stuck']}")

    for label, dotted in EXTRA_CHECKS.get(name, []):
        value = pick(data, dotted)
        ok = bool(value) if not isinstance(value, str) else value == "failed"
        entry["extra"][label] = value
        log(f"  {'成立' if ok else '**不成立**'}：{label} → {value!r}")
        if not ok:
            problem(f"场景 {name}：追加判据不成立 —— {label}（值 {value!r}）")

    verdict = (data.get("scenarios") or {}).get(name, {})
    if name == "cut-retry":
        checks = verdict.get("checks") or {}
        for label, ok in checks.items():
            log(f"  {'成立' if ok else '**不成立**'}：{label}")
            if not ok:
                problem(f"场景 {name}：判据不成立 —— {label}")
    elif name == "content-mismatch":
        # drill 这一格把终态拆在 `final_state` / `observations`（每次状态变化一行）里，
        # **没有**单独的 final 对象——终态那句话要从最后一行观察里取。
        observations = verdict.get("observations") or []
        final = observations[-1] if observations else {}
        log(f"  观察窗内请求 {verdict.get('server_requests')} 次 / 重试 "
            f"{verdict.get('max_retry_count')} 次 / 观察 "
            f"{verdict.get('observed_seconds')}s")
        log(f"  终态：state={final.get('state')!r} error_kind={final.get('error_kind')!r} "
            f"retry_count={final.get('retry_count')!r}")
        log(f"  文案：{str(final.get('error'))[:160]!r}")
        entry["final"] = {k: final.get(k) for k in
                          ("state", "error", "error_kind", "retry_count", "message")}
        entry["server_requests"] = verdict.get("server_requests")
        entry["max_retry_count"] = verdict.get("max_retry_count")
        if final.get("state") != "failed":
            problem(f"场景 {name}：终态不是 failed（实际 {final.get('state')!r}）")
        if str(final.get("error_kind")) != "verify":
            problem(f"场景 {name}：error_kind 不是 verify（实际 {final.get('error_kind')!r}）")
        if "重下不会有变化" not in str(final.get("error") or ""):
            problem(f"场景 {name}：终态文案没接上「重下不会有变化」那句承诺")
        max_retry = int(verdict.get("max_retry_count") or 0)
        if max_retry > 5:
            problem(f"场景 {name}：重试次数越界（{max_retry} > 5）")
        if max_retry < 1:
            problem(f"场景 {name}：一次都没重试就失败了（夹具可能不对）")
    RESULTS["scenarios"][name] = entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, help="证据落盘目录")
    parser.add_argument("--only", action="append", default=[],
                        help="场景名（可重复）：verify-size / cut-retry / content-mismatch …")
    args = parser.parse_args()

    evidence_dir = Path(args.evidence_dir)
    if not evidence_dir.is_dir():
        evidence_dir.mkdir(parents=True, exist_ok=True)

    log("# drill-02 真机复跑（用工作树的源码当「用户机上那一代代码」）")
    log(f"  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"  仓库：{REPO}")
    log(f"  沙箱：{SIM_ROOT}")
    log("")

    facts = {
        "drill_sha256": sha256_of(DRILL),
        "drill_evidence_before": {
            path.name: (sha256_of(path) if path.is_file() else "(缺失)")
            for path in DRILL_EVIDENCE
        },
        "sim_src": None,
        "workspace_src": None,
        "sandbox_version_on_disk": None,
        "real_data_mtime": (REAL_DATA.stat().st_mtime if REAL_DATA.is_dir() else -1.0),
    }
    if not SIM_SRC.is_dir():
        problem(f"沙箱源码目录不存在：{SIM_SRC}")
        return 2
    if not WORKSPACE_SRC.is_dir():
        problem(f"工作树源码目录不存在：{WORKSPACE_SRC}")
        return 2
    facts["sim_src"] = tree_digest(SIM_SRC)
    facts["workspace_src"] = tree_digest(WORKSPACE_SRC)
    init_file = SIM_SRC / "__init__.py"
    if init_file.is_file():
        for line in init_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__"):
                facts["sandbox_version_on_disk"] = line.split('"')[1] if '"' in line else ""
    log(f"  drill 脚本 sha256 = {facts['drill_sha256'][:16]}…（**零改动**：下面是它的原文副本）")
    log(f"  沙箱源码：{facts['sim_src'][0]} 个文件 / 聚合 {facts['sim_src'][1][:16]}…"
        f"（盘上版本 {facts['sandbox_version_on_disk']!r}）")
    log(f"  工作树源码：{facts['workspace_src'][0]} 个文件 / 聚合 "
        f"{facts['workspace_src'][1][:16]}…")
    log("  **harness 偏离**：下面把工作树的 src/contest_generator 放进沙箱＝模拟「用户机上"
        "已经是修好的那一版」；drill 与产品代码都没有为这次演练改过任何一行。")
    RESULTS["facts"] = facts

    staging = Path(tempfile.mkdtemp(prefix="fe-drill02-src-"))
    staged_src = staging / "contest_generator"
    staged_evidence = staging / "evidence"
    staged_evidence.mkdir(parents=True, exist_ok=True)
    for path in DRILL_EVIDENCE:
        if path.is_file():
            shutil.copy2(path, staged_evidence / path.name)

    try:
        shutil.copytree(SIM_SRC, staged_src)
        shutil.rmtree(SIM_SRC)
        # **不排除任何东西**（连 `__pycache__` 一起拷）：标签判据是「逐字节相同」，
        # 少拷一层就会让上面那个记账自相矛盾（第一版就是这么误判的）。
        shutil.copytree(WORKSPACE_SRC, SIM_SRC)
        swapped = tree_digest(SIM_SRC)
        RESULTS["swapped_src"] = swapped
        log(f"  放进沙箱：{swapped[0]} 个文件 / 聚合 {swapped[1][:16]}…")
        if swapped[1] != facts["workspace_src"][1]:
            problem("放进沙箱的源码与工作树那一份不一致（复制出了问题）")

        for name in (args.only or ["verify-size"]):
            run_scenario(name, evidence_dir)
    finally:
        shutil.rmtree(SIM_SRC, ignore_errors=True)
        shutil.copytree(staged_src, SIM_SRC)
        after = tree_digest(SIM_SRC)
        log("")
        log(f"  复原沙箱源码：{after[0]} 个文件 / 聚合 {after[1][:16]}… "
            f"{'与备份一致 ✓' if after == facts['sim_src'] else '**与备份不一致 ✗**'}")
        if after != facts["sim_src"]:
            problem("沙箱源码没复原")
        for path in DRILL_EVIDENCE:
            saved = staged_evidence / path.name
            if saved.is_file():
                shutil.copy2(saved, path)
        shutil.rmtree(staging, ignore_errors=True)

    # 收尾检查（与 drill 自己的口径一致：只读地看）
    listeners = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                               errors="replace").stdout
    port_8020 = [line for line in listeners.splitlines() if ":8020" in line and "LISTENING" in line]
    RESULTS["cleanup"] = {
        "port_8020_listening": port_8020,
        "real_data_mtime_unchanged":
            (REAL_DATA.stat().st_mtime if REAL_DATA.is_dir() else -1.0) == facts["real_data_mtime"],
        "sim_data_untouched": SIM_DATA.is_dir(),
    }
    log("")
    log("## 收尾")
    log(f"  8020 监听：{port_8020 or '（无）'}")
    log(f"  真身数据目录 mtime 未变：{RESULTS['cleanup']['real_data_mtime_unchanged']}")
    if port_8020:
        problem("收尾时 8020 还有监听进程")

    log("")
    log("## 总判")
    log(f"  判红 {len(RESULTS['problems'])} 条")
    for item in RESULTS["problems"]:
        log(f"  · {item}")
    RESULTS["verdict"] = "PASS" if not RESULTS["problems"] else "FAIL"
    log(f"  复跑：{RESULTS['verdict']}")
    return 0 if not RESULTS["problems"] else 1


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except Exception as exc:  # noqa: BLE001 —— 崩溃也要留原始证据
        import traceback
        problem(f"脚本异常：{type(exc).__name__}: {exc}")
        log(traceback.format_exc())
    finally:
        evidence_dir = None
        for index, item in enumerate(sys.argv):
            if item == "--evidence-dir" and index + 1 < len(sys.argv):
                evidence_dir = Path(sys.argv[index + 1])
        target = evidence_dir or HERE
        target.mkdir(parents=True, exist_ok=True)
        (target / "verify-real-machine.txt").write_text("\n".join(LINES) + "\n",
                                                        encoding="utf-8")
        (target / "verify-real-machine.json").write_text(
            json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n证据已写：verify-real-machine.txt / .json")
    raise SystemExit(code)
