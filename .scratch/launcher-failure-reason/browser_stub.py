"""验收期间的「浏览器打开」抑制单源（工单 launcher-failure-reason/01 + /02）。

问题：`start-app.bat` 的成功分支最后会 `start "" "http://127.0.0.1:<port>"` 打开浏览器——
**这是产品行为**（正常双击就该开浏览器），但验收里每跑一次都真开一个标签，用户看到的就是
「firstep 一直打开又关掉」（2026-09-12 实测被用户当场叫停）。

试过但**不行**的三条路（记下来免得重走）：

| 做法 | 结果 |
|---|---|
| PATH 前置 `start.cmd` | ❌ `start` 是 cmd **内建命令**，不查 PATH |
| 用分派 shell 内建替换 `start`（`set /p =<nul & "url" >log`） | ❌ 实测没拦住（框照开），且日志也没落下来 |
| 包装层里改 `start-app.bat` 的那一行 | ❌ 改的就不是被测对象了 |

**可行做法（用户 2026-09-12 拍板）**：验收期间把当前用户默认浏览器的 URL 关联**临时**指到
无害命令（写 `HKCU\\Software\\Classes\\<ProgId>\\shell\\open\\command` = `cmd.exe /c exit`，
`<ProgId>` 取自 `…\\UrlAssociations\\http\\UserChoice`），跑完**立刻**复原（含异常路径）。
实测：URL 打开不再产生任何浏览器进程；复原后类键恢复原样（原本不存在就删掉）。

边界与纪律：
- 只碰**当前用户**的 HKCU，且只碰「默认浏览器的 ProgId 类」这一个键；全程在 `finally` 里复原；
- `suppress_browser()` 是上下文管理器，落盘一份 `browser-suppressed.json` 记账（原值 / 新值 / 时间），
  验收结束由测试断言「已复原」；
- 只影响**被包装的那一次启动**（launcher 的 `start` 解析走的就是这套关联）。
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

USER_CHOICE = r"HKCU\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
CLASSES = r"HKCU\Software\Classes"
STUB_COMMAND = "cmd.exe /c exit"
MARKER_NAME = "browser-suppressed.json"


def _query_value(key: str, name: str = "") -> str | None:
    """读注册表值（`reg query`，避免依赖 PowerShell 的注册表 provider 措辞）。"""
    args = ["reg", "query", key]
    if name:
        args.append("/v")
        args.append(name)
    out = subprocess.run(args, capture_output=True, text=True, errors="replace")
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        parts = line.split()
        if name and len(parts) >= 3 and parts[0] == name:
            return " ".join(parts[2:])
        if not name and line.strip().startswith("(Default)"):
            return " ".join(line.split()[2:])
    return None


def current_progid() -> str | None:
    """默认浏览器的 URL 关联 ProgId（如 ChromeHTML）；取不到返回 None。"""
    out = subprocess.run(["reg", "query", USER_CHOICE, "/v", "ProgId"],
                         capture_output=True, text=True, errors="replace")
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "ProgId":
            return parts[2]
    return None


def class_key(progid: str) -> str:
    return f"{CLASSES}\\{progid}\\shell\\open\\command"


def _write_command(key: str, command: str) -> bool:
    out = subprocess.run(["reg", "add", key, "/ve", "/d", command, "/f"],
                         capture_output=True, text=True, errors="replace")
    return out.returncode == 0


def _delete_class(progid: str) -> None:
    subprocess.run(["reg", "delete", f"{CLASSES}\\{progid}", "/f"],
                   capture_output=True, text=True, errors="replace")


def _browser_procs() -> set[int]:
    names = ("chrome.exe", "msedge.exe", "firefox.exe", "iexplore.exe", "brave.exe")
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True,
                         text=True, errors="replace")
    found: set[int] = set()
    for line in out.stdout.splitlines():
        cols = [c.strip('"') for c in line.split('","')]
        if len(cols) >= 2 and cols[0].lower() in names:
            pid = cols[1].strip('"')
            if pid.isdigit():
                found.add(int(pid))
    return found


@contextlib.contextmanager
def suppress_browser(profile: Path, expect_open: bool = True):
    """上下文管理器：期间 URL 关联指向无害命令，退出时复原（含异常）。

    产出 `report` dict（原 ProgId / 类键 / 是否原本存在 / 期间新增的浏览器进程数），
    并落盘 `profile/.contest_generator/browser-suppressed.json` 供验收引用。
    """
    progid = current_progid()
    before = _browser_procs()
    report: dict = {"progid": progid, "stub": STUB_COMMAND, "restored": None,
                    "class_existed_before": None, "new_browser_procs": None}
    key = class_key(progid) if progid else None
    if key:
        old = _query_value(key)
        report["class_existed_before"] = old is not None
        report["old_command"] = old
        report["wrote_stub"] = _write_command(key, STUB_COMMAND)
    try:
        yield report
    finally:
        if key:
            if report.get("class_existed_before") and report.get("old_command"):
                report["restored"] = _write_command(key, str(report["old_command"]))
            else:
                _delete_class(progid)
                report["restored"] = _query_value(key) is None
        time.sleep(0.5)
        after = _browser_procs()
        report["new_browser_procs"] = len(after - before)
        if expect_open:
            report["browser_open_suppressed"] = report["new_browser_procs"] == 0
        marker = profile / ".contest_generator" / MARKER_NAME
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass


def browser_available() -> bool:
    """当前环境能不能定位浏览器（决定抑制手段是否有意义）。"""
    return bool(current_progid()) and shutil.which("reg") is not None


def env_without_launcher_port(env: dict[str, str]) -> dict[str, str]:
    """拷贝一份环境并清掉端口覆盖（避免把上一次的 8899 带进按默认端口跑的用例）。"""
    out = dict(env)
    out.pop("FIRSTEP_LAUNCHER_PORT", None)
    return out


def probe_browser_suppression(profile: Path) -> dict:
    """自证：抑制期间打开一个 URL，必须**不新增浏览器进程**（验收的第一步就是这个）。"""
    with suppress_browser(profile, expect_open=True) as report:
        subprocess.run(["cmd", "/c", "start", "", "http://127.0.0.1:65535/suppression-probe"],
                       capture_output=True, text=True)
        time.sleep(1.5)
    return report
