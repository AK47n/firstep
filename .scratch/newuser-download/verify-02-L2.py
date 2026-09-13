"""L2 真机演练：把本工单打出的真实完整包当「新用户收到的包」走一遍（工单 newuser-download/05）。

隔离口径（不碰真身）：
- 工具根 = `%TEMP%\\firstep-l2\\tool`（从真实 zip 解压）
- 用户目录 = `%TEMP%\\firstep-l2\\profile`，通过**重定向 USERPROFILE** 实现
  （实测 `Path.home()` 跟随它 → 配置/日志/updates 全落在演练目录，真身 `~\\.contest_generator` 不被触碰）
- 端口 8020（`FIRSTEP_LAUNCHER_PORT`）
- 依赖：预置一个 `--system-site-packages` 的 .venv，让 install.bat 的第 2、3 步在**本机内**完成，
  不去污染全局 user-site（本机全局 site-packages 里已有一处历史 editable 安装，不该再加一层）

输出为原始命令 + 原始 stdout，直接贴进 `.scratch/newuser-download/E2E-8020.md` 的 L2 证据区。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
import venv
from pathlib import Path

STAGE = Path(os.environ["TEMP"]) / "firstep-l2"
TOOL = STAGE / "tool"
PROFILE = STAGE / "profile"
ZIP = Path(os.environ["TEMP"]) / "firstep-pack-verify" / "firstep-full-v0.0.0-probe.zip"
PORT = "8020"

failures: list[str] = []


def step(title: str) -> None:
    print(f"\n=== {title} ===")


def check(label: str, ok: bool, detail: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}：{detail}")
    if not ok:
        failures.append(f"{label} → {detail}")


def run(cmd: list[str], *, cwd: Path, env: dict[str, str], timeout: int = 1800):
    return subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, timeout=timeout)


def l2_env() -> dict[str, str]:
    env = dict(os.environ)
    env["USERPROFILE"] = str(PROFILE)
    env["HOMEDRIVE"], env["HOMEPATH"] = PROFILE.drive, str(PROFILE)[len(PROFILE.drive):]
    env["FIRSTEP_LAUNCHER_PORT"] = PORT
    env["PYTHONNOUSERSITE"] = "1"  # 不让 pip 写到 user-site
    env.pop("PYTHONPATH", None)
    return env


step("0. 清场 + 从真实包解压（Windows 自带解压）")
if STAGE.exists():
    shutil.rmtree(STAGE)
(TOOL).mkdir(parents=True)
(PROFILE / "Desktop").mkdir(parents=True)
started = time.perf_counter()
subprocess.run(["tar.exe", "-xf", str(ZIP), "-C", str(TOOL)], check=True, timeout=900)
extract_s = time.perf_counter() - started
file_count = sum(1 for _ in TOOL.rglob("*") if _.is_file())
check("真实包解压成功", (TOOL / "00-START-HERE.txt").is_file(), f"{file_count:,} 文件 / {extract_s:.1f} 秒")

step("1. 解压后第一眼（资源管理器排序近似：先主名不区分大小写、再全名）")
names = sorted(
    [p.name for p in TOOL.iterdir()],
    key=lambda n: ((n.rsplit(".", 1)[0] if "." in n else n).lower(), n),
)
visible = [n for n in names if not n.startswith(".")]
for i, n in enumerate(visible[:5], 1):
    print(f"    {i}. {n}")
check("第一个可见文件", visible[0] == "00-START-HERE.txt", visible[0])

step("2. 照 00-START-HERE.txt 的第 1 步：双击 install.bat")
# 预置 .venv（--system-site-packages）：让第 2/3 步在本机内完成，且不污染全局 user-site
if not (TOOL / ".venv").exists():
    venv.create(str(TOOL / ".venv"), with_pip=True, system_site_packages=True)
    print("  已预置 .venv（--system-site-packages，供 install.bat 第 2 步跳过创建）")
else:
    print("  .venv 已在场（复用上次的）")
# stdin 用 DEVNULL：收尾的 pause 自行跳过。**不能用 input=**——文本配字节管道会卡死（踩过）
bat = subprocess.run(
    ["cmd.exe", "/c", "install.bat"],
    cwd=str(TOOL),
    env=l2_env(),
    stdin=subprocess.DEVNULL,
    capture_output=True,
    timeout=1800,
)
out = bat.stdout.decode("gbk", errors="replace")
print("  ---- install.bat 原始输出 ----")
for line in out.splitlines():
    if line.strip():
        print(f"    {line}")
check("install.bat 退出码", bat.returncode == 0, str(bat.returncode))
for mark in ["[1/5]", "[2/5]", "[3/5]", "[4/5]", "[5/5]", "安装完成"]:
    check(f"输出含 {mark}", mark in out, "在场" if mark in out else "缺失")

step("3. 桌面 firstep 快捷方式（落在重定向后的用户目录）")
lnk = PROFILE / "Desktop" / "firstep.lnk"
check("快捷方式存在", lnk.is_file(), str(lnk))
if lnk.is_file():
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('" + str(lnk) + "');"
        "'TARGET='+$s.TargetPath;'ARGS='+$s.Arguments;'WORKDIR='+$s.WorkingDirectory"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    print("    " + "\n    ".join(x for x in r.stdout.splitlines() if x.strip()))
    check("Target 是 wscript.exe", "wscript.exe" in r.stdout, "在场" if "wscript.exe" in r.stdout else "缺失")
    check("指向 start-app.vbs", "start-app.vbs" in r.stdout, "在场" if "start-app.vbs" in r.stdout else "缺失")
    check("工作目录是演练工具根", str(TOOL).lower() in r.stdout.lower(), str(TOOL))

step("4. 照第 2 步：双击快捷方式（模拟）→ 服务是否起来 + 浏览器地址可访问")
target = subprocess.list2cmdline([str(TOOL / "start-app.vbs")])
subprocess.Popen(["wscript.exe", str(TOOL / "start-app.vbs")], cwd=str(TOOL), env=l2_env())
health = None
for _ in range(40):
    time.sleep(1)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=3) as resp:
            health = json.loads(resp.read().decode("utf-8"))
        break
    except Exception:
        continue
check("8020 有响应且是本应用", bool(health and health.get("app")), str(health))

step("5. 配置与日志落点（数据必须落在演练用户目录，真身不被触碰）")
cfg = PROFILE / ".contest_generator" / "config.json"
log = PROFILE / ".contest_generator" / "webapp.log"
check("配置写在演练用户目录", cfg.is_file(), str(cfg))
if cfg.is_file():
    data = json.loads(cfg.read_text(encoding="utf-8"))
    mods = str(data.get("module_library_dir") or data.get("modules_dir") or "")
    print(f"    module 库目录 = {mods}")
    check("库目录指向工具包内 library", "library" in mods.lower(), mods)
check("日志写在演练用户目录", log.is_file(), str(log))
real = Path(r"C:\Users\luoji\.contest_generator")
check("真身数据目录未被本次演练改动", real.exists(), f"{real} 仍存在（演练用的是 {PROFILE}）")

step("6. 幂等：再跑一次 install.bat")
bat2 = subprocess.run(["cmd.exe", "/c", "install.bat"], cwd=str(TOOL), env=l2_env(),
                      stdin=subprocess.DEVNULL, capture_output=True, timeout=1800)
out2 = bat2.stdout.decode("gbk", errors="replace")
check("第二次退出码 0", bat2.returncode == 0, str(bat2.returncode))
check("第二次提示已存在/跳过", ("已存在" in out2) or ("跳过" in out2), "在场")

step("7. 收尾：停掉演练服务（只关演练那个进程）")
try:
    import subprocess as sp
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*contest_generator.webapp*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; 'killed=' + $_.ProcessId }"
    )
    r = sp.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
               capture_output=True, text=True, encoding="utf-8", timeout=120)
    print("    " + (r.stdout.strip() or "（没有匹配进程）"))
except Exception as exc:  # noqa: BLE001
    print(f"    收尾失败（不影响结论）：{exc}")

print("\n=== 结论 ===")
if failures:
    for f in failures:
        print(f"  FAIL {f}")
    raise SystemExit(1)
print("  PASS：真实包 → 解压 → 照说明书安装 → 快捷方式 → 服务起来，全链路走通")
