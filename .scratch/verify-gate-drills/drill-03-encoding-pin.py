# -*- coding: utf-8 -*-
"""B3 —— 编码钉落点实证：沙箱里生成一个 mspm0 工程，看 `.settings/` 有没有落进去。

要回答的问题：v1.2.1 修「CCS 中文注释乱码」这件事，**从「包里有这两个文件」升级到
「生成出来的工程里有这两个文件」**。

判据（spec 测试决策，全部落在产物上）：

- 在**沙箱**（升到 v1.2.1 之后）真调生成端点 `POST /api/generate`（平台 mspm0 +
  一个最小模块集 `servo`），payload 照真实历史产物 `.scratch/real-run/out_16_mspm0_min/.contest_context.json`；
- 断言产物里有 `.settings/org.eclipse.core.resources.prefs` 与
  `.settings/org.eclipse.cdt.codan.core.prefs`，且正文含 `encoding/<project>=UTF-8`；
- 与**母版源文件**逐个 sha256 对照（生成产物 = 母版文件，未被改写），
  并与**官方 v1.2.1 完整包清单**里的 sha256 三方对照；
- **诚实边界写进证据**：这证明的是「落点正确」，**不是**「CCS 实际读取行为」——
  本机没有可交互的 CCS 工作区实测条件，不外推。

为什么用 `servo` 这个组合：它是仓库里真实生成过的 mspm0 最小工程
（`.scratch/real-run/out_16_mspm0_min/`，含 `.settings/`），main.c 与模块集都能照抄，
**不烧 LLM 额度**（无 `problem_text` → 报告草稿那一次调用不发生；显式编号路径也不需要 AI）。

用法::

    python .scratch/verify-gate-drills/drill-03-encoding-pin.py [--keep]
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
MASTER_SETTINGS = SIM_ROOT / "library" / "masters" / "mspm0" / ".settings"
PACK_MANIFEST = Path.home() / "Desktop" / "firstep-pack" / "firstep-full-v1.2.1.manifest.json"
SAMPLE_CONTEXT = REPO / ".scratch" / "real-run" / "out_16_mspm0_min" / ".contest_context.json"
ARTIFACTS = HERE / "artifacts-b3"
PORT = 8020
BASE = f"http://127.0.0.1:{PORT}"

LINES: list[str] = []
RESULTS: dict = {"problems": [], "stuck": [], "notes": []}


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


def api(path: str, payload: dict | None = None, timeout: float = 600) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE + path, data=data, method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # 400 的中文正文就是产品给的判决理由——必须进证据（不然只剩一个空白的 400）
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} → HTTP {exc.code}：{body[:500]}") from None


def wait_health(deadline_seconds: float = 90) -> dict | None:
    end = time.time() + deadline_seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=3) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return None


def read_version_file(root: Path) -> str:
    init = root / "src" / "contest_generator" / "__init__.py"
    for line in init.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split('"')[1] if '"' in line else line.strip()
    return ""


def official_settings_sha() -> dict[str, str]:
    if not PACK_MANIFEST.is_file():
        return {}
    data = json.loads(PACK_MANIFEST.read_text(encoding="utf-8-sig"))
    out: dict[str, str] = {}
    for item in data.get("files") or []:
        path = str(item.get("path") or "")
        if path.startswith("library/masters/mspm0/.settings/"):
            out[Path(path).name] = str(item.get("sha256") or "")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    work = Path(os.environ["TEMP"]) / f"fe03-{time.strftime('%Y%m%d-%H%M%S')}"
    profile = work / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    output_dir = work / "out_mspm0"

    log("# B3 证据：编码钉落点实证（沙箱里真生成一个 mspm0 工程）")
    log(f"  时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"  一次性目录：{work}")
    log("")

    log("## 零、前置事实")
    facts = {
        "sim_version_on_disk": read_version_file(SIM_ROOT),
        "master_settings_dir": str(MASTER_SETTINGS),
        "master_settings_files": sorted(p.name for p in MASTER_SETTINGS.glob("*"))
        if MASTER_SETTINGS.is_dir() else [],
        "sample_context": str(SAMPLE_CONTEXT),
        "sample_context_exists": SAMPLE_CONTEXT.is_file(),
        "port_8020_listeners": listen_pids(PORT),
    }
    for key, value in facts.items():
        log(f"  {key} = {value!r}")
    RESULTS["facts"] = facts
    if not MASTER_SETTINGS.is_dir():
        problem("沙箱母版里没有 `library/masters/mspm0/.settings/`——编码钉根本没进母版")
        return 1
    if not SAMPLE_CONTEXT.is_file():
        problem(f"找不到真实历史产物样例 {SAMPLE_CONTEXT}（payload 来源）")
        return 1
    if facts["port_8020_listeners"]:
        killed = kill_listener(PORT)
        note(f"8020 上有遗留监听（PID {killed}），已先收掉再开跑")

    master_sha = {name: sha256_of(MASTER_SETTINGS / name)
                  for name in facts["master_settings_files"]}
    official_sha = official_settings_sha()
    log("  母版 `.settings` 逐个 sha256：")
    for name, digest in master_sha.items():
        log(f"    {name}: {digest}")
    if official_sha:
        log("  官方 v1.2.1 完整包清单里的同名文件 sha256：")
        for name, digest in official_sha.items():
            log(f"    {name}: {digest}")
        mismatch = [n for n in master_sha if official_sha.get(n)
                    and official_sha[n] != master_sha[n]]
        if mismatch:
            problem(f"沙箱母版与官方包清单不一致：{mismatch}")
        else:
            log("  → 沙箱母版 = 官方 v1.2.1 包内那份（逐字节）")
    RESULTS["master"] = {"sha256": master_sha, "official_sha256": official_sha}

    env = dict(os.environ)
    env.update({
        "FIRSTEP_LAUNCHER_PORT": str(PORT),
        "USERPROFILE": str(profile),
        "HOME": str(profile),
        "PYTHONPATH": str(SIM_ROOT / "src"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
    })

    # 生成端点需要一份**可用配置**（`_require_config`：缺 api_key 直接 400）。
    # 沙箱自己那份 config.json 是手搓的旧键（`deepseek_api_key` / `modules_dir`），
    # 一调就 400——**不去改沙箱的配置**（它是沙箱的既有事实），改用一次性副本：
    # 拷真身配置（含真 key，**正文不进证据**），库目录改指**沙箱**的库与母版
    # （B3 要证的正是沙箱这套 v1.2.1 母版），自动提交关。
    drill_config = work / "config.json"
    real_config = Path.home() / ".contest_generator" / "config.json"
    cfg = json.loads(real_config.read_text(encoding="utf-8-sig"))
    cfg["module_library_dir"] = str(SIM_ROOT / "library" / "modules")
    cfg["masters_dir"] = str(SIM_ROOT / "library" / "masters")
    cfg["autocommit_enabled"] = False
    drill_config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    launcher_py = work / "drill_app.py"
    launcher_py.write_text(
        "# 一次性入口（照沙箱 sim-run.py 的姿势，只把配置路径换成演练副本）\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, r'%s')\n"
        "import uvicorn\n"
        "from contest_generator.webapp import AppContext, create_app\n"
        "# 配置路径必须是 Path：传字符串时端点内部 `load_config(path).read_text()`\n"
        "# 会抛 AttributeError('str' object has no attribute 'read_text')，\n"
        "# 而 HTTP 侧只看得到一句通用 500（演练第一版就是这么白排查一轮的）。\n"
        "ctx = AppContext(config_path=Path(r'%s'))\n"
        "uvicorn.run(create_app(ctx), host='127.0.0.1', port=int(os.environ.get("
        "'FIRSTEP_LAUNCHER_PORT', '8020')))\n" % (SIM_ROOT / "src", drill_config),
        encoding="utf-8")
    log(f"  一次性配置：{drill_config}（库目录指沙箱 library，autocommit 关；"
        f"**配置正文不进证据**）")

    launcher: subprocess.Popen | None = None
    try:
        log("")
        log(f"## 一、起服务（一次性入口 → {PORT}，代码仍是沙箱 v1.2.1 那套）")
        handle = open(work / "sandbox-run.log", "a", encoding="utf-8")
        launcher = subprocess.Popen(
            [sys.executable, str(launcher_py)], cwd=str(SIM_ROOT), env=env,
            stdout=handle, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        health = wait_health(deadline_seconds=120)
        if health is None:
            stuck("沙箱服务 120 秒没起来")
            log((work / "sandbox-run.log").read_text(encoding="utf-8",
                                                     errors="replace")[-2000:])
            return 1
        log(f"  服务已就绪：{health}（生成器版本 = {health.get('version')}）")
        RESULTS["health"] = health

        log("")
        log("## 二、真调生成链路（POST /api/generate，平台 mspm0 + servo）")
        sample = json.loads(SAMPLE_CONTEXT.read_text(encoding="utf-8"))
        payload = {
            "platform": sample["platform"],
            "slugs": sample["slugs"],
            "main_c": sample["main_c"],
            "references": [],
            "output_dir": str(output_dir),
        }
        log(f"  payload：platform={payload['platform']} slugs={payload['slugs']} "
            f"output_dir={payload['output_dir']}")
        log(f"  main_c（{len(sample['main_c'])} 字符）照抄真实历史产物样例")
        result = api("/api/generate", payload, timeout=900)
        log(f"  响应：{json.dumps(result, ensure_ascii=False)[:600]}")
        RESULTS["generate"] = result

        log("")
        log("## 三、产物断言（落点 + 内容 + 与母版逐字节）")
        if not output_dir.is_dir():
            problem(f"生成产物目录不存在：{output_dir}")
            return 1
        produced = sorted(str(p.relative_to(output_dir)).replace("\\", "/")
                          for p in output_dir.rglob("*") if p.is_file())
        log(f"  产物文件数：{len(produced)}")
        log(f"  产物清单（前 40）：{produced[:40]}")
        RESULTS["produced"] = produced

        settings_dir = output_dir / ".settings"
        checks: dict[str, bool] = {}
        sha_out: dict[str, str] = {}
        for name in facts["master_settings_files"]:
            target = settings_dir / name
            exists = target.is_file()
            checks[f"{name} 在产物里"] = exists
            if exists:
                sha_out[name] = sha256_of(target)
                checks[f"{name} = 母版（逐字节）"] = sha_out[name] == master_sha.get(name)
                if official_sha.get(name):
                    checks[f"{name} = 官方包清单"] = sha_out[name] == official_sha[name]
        resources = settings_dir / "org.eclipse.core.resources.prefs"
        content = resources.read_text(encoding="utf-8") if resources.is_file() else ""
        log(f"  `org.eclipse.core.resources.prefs` 正文：{content!r}")
        checks["正文含 encoding/<project>=UTF-8"] = "encoding/<project>=UTF-8" in content
        for label, ok in checks.items():
            log(f"  {'成立' if ok else '**不成立**'}：{label}")
        RESULTS["checks"] = checks
        RESULTS["produced_settings_sha256"] = sha_out
        for label, ok in checks.items():
            if not ok:
                problem(f"编码钉落点判据不成立：{label}")

        log("")
        log("## 四、证据落盘与诚实边界")
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        for name in facts["master_settings_files"]:
            target = settings_dir / name
            if target.is_file():
                shutil.copy2(target, ARTIFACTS / f"produced-{name}")
        for extra in (".contest_context.json", ".ccsproject", ".project", "main.c"):
            src = output_dir / extra
            if src.is_file():
                shutil.copy2(src, ARTIFACTS / f"produced-{Path(extra).name}")
        (ARTIFACTS / "produced-files.txt").write_text(
            "\n".join(produced) + "\n", encoding="utf-8")
        log(f"  产物副本（编码钉 + 上下文 + 工程文件）落：{ARTIFACTS}")
        note("**诚实边界**：以上证明的是「编码钉随生成工程落盘、内容与母版逐字节相同」；"
             "**不证明** CCS 打开工程后中文注释不乱码——本机没有可交互的 CCS 工作区实测条件，"
             "不外推。")
        log("  [记录] 诚实边界：本格只证「落点与内容」，不证「CCS 实际读取行为」（已在 "
            "notes 与本节写明）")
        return 0
    finally:
        if launcher is not None and launcher.poll() is None:
            launcher.terminate()
        killed = kill_listener(PORT)
        time.sleep(1.0)
        leftover = listen_pids(PORT)
        log("")
        log("## 收尾")
        log(f"  收掉 8020 监听进程：{killed or '（无）'}；残余：{leftover or '（无）'}")
        RESULTS["cleanup"] = {"killed": killed, "leftover": leftover}
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
            log("  一次性目录已清理（产物副本已留在 artifacts-b3/）")
        else:
            log(f"  （--keep：一次性目录保留在 {work}）")


def finish(code: int) -> int:
    (HERE / "verify-03-encoding-pin.txt").write_text("\n".join(LINES) + "\n",
                                                     encoding="utf-8")
    (HERE / "verify-03-encoding-pin.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n证据已写：verify-03-encoding-pin.txt / .json")
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
        log(f"  B3「编码钉落点实证」：{'PASS' if not problems else 'FAIL'}")
        RESULTS["verdict"] = {"problems": problems, "stuck": RESULTS["stuck"],
                              "pass": not problems}
        finish(exit_code)
    raise SystemExit(0 if not RESULTS["problems"] else 1)
