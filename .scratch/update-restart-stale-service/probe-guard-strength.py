# -*- coding: utf-8 -*-
"""判据强度探针：把这条修复的守卫逐个「弄坏」，看它们是否真的会红（工单 `update-restart-stale-service/01`）。

为什么要它：「守卫全绿」本身不说明任何事——**把被测行为改坏、守卫必须转红**才算数
（照 `.scratch/resumable-download/verify-12-guard-strength.txt` 那批探针的先例）。

每一个用例：改坏一处 → 跑对应测试 → 记录「红/绿」→ **无论结果如何都复原**
（`finally` 里按原字节写回，并复核 sha256）。

判据：**每一条注入都必须转红**。有绿的 = 那条守卫是摆设 → 探针退出码非 0。

用法::

    python .scratch/update-restart-stale-service/probe-guard-strength.py
    # 证据落 verify-01-guard-strength.txt / .json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

UPDATE_PY = "src/contest_generator/update.py"          # UTF-8（LF）
START_BAT = "start-app.bat"                            # GBK + CRLF

#: (名字, 文件, 改前（必须唯一命中）, 改后, 测试文件, -k 表达式)
CASES: list[tuple[str, str, str, str, str, str]] = [
    (
        "谓词放宽成「不相等」：服务比盘上更新也会被判旧进程（误杀别人的新版）",
        UPDATE_PY,
        "    return comparison == 1",
        "    return comparison != 0",
        "tests/test_update_check.py",
        "is_stale_service",
    ),
    (
        "判不了也硬判：非 semver 不再返回 None，而是当成「不是旧进程」",
        UPDATE_PY,
        "    if comparison is None:\n        return None",
        "    if comparison is None:\n        return False",
        "tests/test_update_check.py",
        "is_stale_service",
    ),
    (
        "踢进程的作用域写成死端口 8000（不再跟着本实例的端口走）",
        START_BAT,
        'findstr ":%FIRSTEP_LAUNCHER_PORT%" ^| findstr "LISTENING"',
        'findstr ":8000" ^| findstr "LISTENING"',
        "tests/test_launcher_stale_service.py",
        "",
    ),
    (
        "判据放宽成「不是 unknown 就踢」（fresh 也会被踢掉）",
        START_BAT,
        'if /i "%FIRSTEP_STALE%"=="stale" goto :stale_service',
        'if /i not "%FIRSTEP_STALE%"=="unknown" goto :stale_service',
        "tests/test_launcher_stale_service.py",
        "",
    ),
    (
        "身份判据被写反（别的程序占着端口也算自己人）",
        START_BAT,
        'if /i not "%FIRSTEP_HEALTH_APP%"=="contest-generator" goto :port_busy',
        'if /i "%FIRSTEP_HEALTH_APP%"=="contest-generator" goto :port_busy',
        "tests/test_launcher_stale_service.py",
        "",
    ),
    (
        "反引号前少了 usebackq（cmd 把命令当文件名，循环一次都不跑、判据静默失效）",
        START_BAT,
        'for /f "usebackq tokens=1,*" %%a in (`%PYEXE% "%LAUNCHER_STALE_PY%" --port',
        'for /f "tokens=1,*" %%a in (`%PYEXE% "%LAUNCHER_STALE_PY%" --port',
        "tests/test_launcher_stale_service.py",
        "",
    ),
    (
        "干脆不问 CLI（判据退回原来的「只看身份」）",
        START_BAT,
        'for /f "usebackq tokens=1,*" %%a in (`%PYEXE% "%LAUNCHER_STALE_PY%" --port %FIRSTEP_LAUNCHER_PORT% 2^>nul`) do (',
        "rem （注入：这里不再问 CLI）",
        "tests/test_launcher_stale_service.py",
        "",
    ),
    (
        "起服务前不建数据目录（virgin profile 下重定向整行失败、服务起不来）",
        START_BAT,
        'if not exist "%USERPROFILE%\\.contest_generator" mkdir "%USERPROFILE%\\.contest_generator"',
        "rem （注入：不建目录，重定向会失败）",
        "tests/test_launcher_stale_service.py",
        "",
    ),
    (
        "旧进程被踢这件事不留痕（事后分不清「踢了」还是「碰巧没旧进程」）",
        START_BAT,
        "-Reason started tries=%tries% port=%FIRSTEP_LAUNCHER_PORT% %FIRSTEP_STALE_NOTE%",
        "-Reason started tries=%tries% port=%FIRSTEP_LAUNCHER_PORT%",
        "tests/test_launcher_stale_service.py",
        "",
    ),
]

LINES: list[str] = []
RESULTS: dict = {"cases": []}


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def read_text(relative: str) -> str:
    raw = (ROOT / relative).read_bytes()
    return raw.decode("gbk" if relative.endswith(".bat") else "utf-8")


def write_text(relative: str, text: str) -> None:
    encoding = "gbk" if relative.endswith(".bat") else "utf-8"
    (ROOT / relative).write_bytes(text.encode(encoding))


def sha256(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def run_tests(test_file: str, keyword: str) -> tuple[bool, str]:
    """跑测试，返回 (是否绿, 末行摘要)。"""
    command = [sys.executable, "-m", "pytest", test_file, "-q", "-p", "no:cacheprovider"]
    if keyword:
        command += ["-k", keyword]
    proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=900)
    tail = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    summary = tail[-1] if tail else "(无输出)"
    return proc.returncode == 0, summary


def main() -> int:
    log("# 判据强度探针：把守卫逐个弄坏，看它们会不会红")
    log(f"  仓库：{ROOT}")
    log(f"  判据：**每一条注入都必须转红**（有绿的 = 那条守卫是摆设）")
    log("")

    baseline_sha = {path: sha256(path) for path in (UPDATE_PY, START_BAT)}

    weak: list[str] = []
    for name, path, old, new, test_file, keyword in CASES:
        log("-" * 78)
        log(f"[注入] {name}")
        log(f"  文件：{path}")
        original = read_text(path)
        hits = original.count(old)
        if hits != 1:
            log(f"  **锚点命中 {hits} 次（应为 1）——探针自己失效了，本条按失败记**")
            weak.append(f"{name}（锚点失效）")
            RESULTS["cases"].append({"name": name, "file": path, "anchor_hits": hits,
                                     "turned_red": False, "weak": True})
            continue
        try:
            write_text(path, original.replace(old, new, 1))
            green, summary = run_tests(test_file, keyword)
        finally:
            write_text(path, original)  # 无论结果如何都复原
        turned_red = not green
        log(f"  测试：{test_file}{' -k ' + keyword if keyword else ''}")
        log(f"  结果：{'转红 ✓' if turned_red else '**仍然全绿 ✗**'} —— {summary}")
        RESULTS["cases"].append({"name": name, "file": path, "anchor_hits": hits,
                                 "turned_red": turned_red, "summary": summary,
                                 "weak": not turned_red})
        if not turned_red:
            weak.append(name)

    log("")
    log("-" * 78)
    log("## 复原复核")
    for path, before in baseline_sha.items():
        after = sha256(path)
        log(f"  {path} sha256 {'未变 ✓' if after == before else f'**变了 ✗（{before[:12]} → {after[:12]}）**'}")
        if after != before:
            weak.append(f"{path} 未复原")

    log("")
    log("## 总判")
    red = sum(1 for case in RESULTS["cases"] if case["turned_red"])
    log(f"  {red}/{len(CASES)} 条注入成功转红")
    for name in weak:
        log(f"  · 守卫薄弱：{name}")
    RESULTS["weak"] = weak
    RESULTS["verdict"] = "PASS" if not weak else "FAIL"
    log(f"  探针：{'PASS' if not weak else 'FAIL'}")
    return 0 if not weak else 1


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        (HERE / "verify-01-guard-strength.txt").write_text("\n".join(LINES) + "\n",
                                                           encoding="utf-8")
        (HERE / "verify-01-guard-strength.json").write_text(
            json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n证据已写：verify-01-guard-strength.txt / .json")
    raise SystemExit(code)
