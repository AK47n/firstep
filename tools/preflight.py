#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""发版前自检：一条命令回答「这一版能不能发」（工单 commit-gate/03）。

**为什么需要它**：2026-09-14 发 v1.2.0 时，`VERSIONS.md` 的版本头写坏（日期段混进中文），
解析器静默跳过整块 → 「版本更新记录」页最新只到上一版，**两个线上包都带着这份坏文件**，
只能重打重传。当时的收尾写着：改完版本号**必须**跑一遍守卫——可那要靠人记得。
这个脚本把「记得跑」变成「跑一条命令」。

四项判据**全部复用既有实现的同一套事实**，不新造第二份：

1. **三处版本号一致**：`src/contest_generator/__init__.py` 的 `__version__`（唯一可信来源）
   / `pyproject.toml` 的 `project.version` / `VERSIONS.md` 首个版本块（用
   `contest_generator.changelog.load_versions` —— 与页面同一解析器，格式写坏就会在这里红）；
2. **母版 `.settings/` 在盘且在库**：mspm0 母版的 CCS 编码钉（2026-09-15 误删事故的守卫，
   判据与 `tests/test_master_template_config.py` 同源）；
3. **下载文档一致性**：`tools/check-download-docs.py --offline`（README 入口与包内文件）；
4. **README 当前版本行**与 `__version__` 一致。

用法（仓库根）：

    python tools/preflight.py            # 逐项检查，全绿退 0，任一红退 1
    tools/preflight.ps1                  # 同一件事的 PowerShell 入口（发版清单里写这条）

退出码：0 = 可以发；1 = 有红项（逐条给原因与修法）；2 = 用法/环境错误。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# 母版编码钉：2026-09-15「编译产物不入库」清理误删的那两件（见 local-environment.md 7.1）
MASTER_SETTINGS_DIR = "library/masters/mspm0/.settings"
MASTER_SETTINGS_FILES = (
    "org.eclipse.cdt.codan.core.prefs",
    "org.eclipse.core.resources.prefs",
)
ENCODING_PIN = "encoding/"


class Report:
    """逐项记账：红项带「怎么修」，全绿也给一行结论。"""

    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append((name, ok, detail))

    @property
    def failed(self) -> list[tuple[str, str]]:
        return [(name, detail) for name, ok, detail in self.checks if not ok]

    def render(self) -> str:
        lines = []
        for name, ok, detail in self.checks:
            lines.append(f"  [{'OK' if ok else '红'}] {name}")
            for chunk in detail.splitlines():
                if chunk.strip():
                    lines.append(f"        {chunk}")
        return "\n".join(lines)


def tool_version() -> str:
    from contest_generator import __version__  # noqa: PLC0415 —— 延迟到 sys.path 就位后

    return __version__


def pyproject_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else ""


def versions_head() -> tuple[str, str]:
    """VERSIONS.md 首个版本块 → (版本号, 日期)；解析器与页面同一份。"""
    from contest_generator.changelog import load_versions  # noqa: PLC0415

    releases = load_versions(REPO_ROOT / "VERSIONS.md")
    if not releases:
        return "", ""
    return str(releases[0].get("version", "")), str(releases[0].get("date", ""))


def readme_current_version() -> str:
    """README「版本与发布」里的当前版本（没有这一行 = 空串，判据自己会红）。"""
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"-\s*当前版本：\*\*v([0-9][0-9A-Za-z.\-]*)\*\*", text)
    return match.group(1) if match else ""


def check_versions(report: Report) -> None:
    version = tool_version()
    py_version = pyproject_version()
    head_version, head_date = versions_head()
    readme_version = readme_current_version()

    problems: list[str] = []
    if py_version != version:
        problems.append(
            f"pyproject.toml = {py_version!r}，而 src/contest_generator/__init__.py = {version!r}"
            "  → 改 pyproject.toml 的 project.version 与之一致"
        )
    expected_head = f"v{version}"
    if head_version != expected_head:
        problems.append(
            f"VERSIONS.md 首个版本块 = {head_version!r}，应为 {expected_head!r}"
            "  → 在文件最顶部加 `## v<版本> (YYYY-MM-DD)` 区块（**ASCII 括号 + 严格日期**，"
            "日期后别写中文备注，会让整块被静默跳过）"
        )
    if readme_version != version:
        problems.append(
            f"README.md 当前版本行 = {readme_version!r}，应为 {version!r}"
            "  → 改「## 版本与发布」下的「- 当前版本：**v…**」那一行"
        )
    report.add(
        f"三处版本号一致（{version}）",
        not problems,
        "\n".join(problems) if problems
        else f"__init__.py / pyproject.toml / VERSIONS.md（{head_date}）/ README 全部 = {version}",
    )


def check_master_settings(report: Report) -> None:
    """母版编码钉既要在盘上、也要被 git 跟踪（只看盘上会漏掉「盘上有但不进包」）。"""
    directory = REPO_ROOT / MASTER_SETTINGS_DIR
    problems: list[str] = []
    missing_disk: list[str] = []
    for name in MASTER_SETTINGS_FILES:
        path = directory / name
        if not path.is_file():
            missing_disk.append(name)
    if missing_disk:
        problems.append(
            f"盘上缺：{', '.join(missing_disk)}"
            "  → 从线上完整包或沙箱 firstep-sim 里取回同两份文件（内容逐字节一致）"
        )

    try:
        tracked = subprocess.run(
            ["git", "ls-files", MASTER_SETTINGS_DIR], cwd=str(REPO_ROOT),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        ).stdout.split()
    except OSError as exc:  # pragma: no cover —— git 不在时下面的分支会红
        tracked = []
        problems.append(f"git 不可用：{exc}")
    tracked_names = {Path(item).name for item in tracked}
    untracked = [name for name in MASTER_SETTINGS_FILES if name not in tracked_names]
    if untracked:
        problems.append(
            f"未被 git 跟踪：{', '.join(untracked)}"
            "  → 检查 .gitignore 是否有母版例外（不修这条 = 文件在盘上但发布包也不会带）"
        )

    pin_ok = False
    pin_file = directory / "org.eclipse.core.resources.prefs"
    if pin_file.is_file():
        pin_ok = ENCODING_PIN in pin_file.read_text(encoding="utf-8", errors="replace")
    if not pin_ok:
        problems.append(
            f"编码钉不在：{MASTER_SETTINGS_DIR}/org.eclipse.core.resources.prefs 里没有 "
            f"`{ENCODING_PIN}…=UTF-8`"
            "  → 这份文件就是给生成工程钉 CCS 编码的（丢了中文注释有乱码风险）"
        )
    report.add("母版 .settings/ 编码钉在盘 + 在库", not problems,
               "\n".join(problems) if problems
               else f"{MASTER_SETTINGS_DIR}/ 两件都在盘且被跟踪，编码钉内容在场（{ENCODING_PIN}…=UTF-8）")


def check_download_docs(report: Report) -> None:
    script = REPO_ROOT / "tools" / "check-download-docs.py"
    if not script.is_file():
        report.add("下载文档一致性（offline）", False,
                   f"{script.relative_to(REPO_ROOT)} 不存在 → 发版自检脚本被删了？")
        return
    try:
        env = dict(os.environ)
        # Windows 上 Python 默认按控制台代码页输出（CI 上实测 cp1252）——子脚本打印中文
        # 会直接 `UnicodeEncodeError: 'charmap' codec ...`，看起来像"文档不一致"，
        # 实际是编码没钉（2026-09-16 Windows CI 抓到的真缺陷，用户机同理）。
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        result = subprocess.run(
            [sys.executable, str(script), "--offline"], cwd=str(REPO_ROOT),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        report.add("下载文档一致性（offline）", False, f"跑不起来：{exc}")
        return
    ok = result.returncode == 0
    # 失败时把子进程的**完整输出**带出来：截断的尾巴在 CI 上等于没有诊断信息
    # （2026-09-16 实测：Windows CI 报「下载文档一致性红」而看不到原因，只能重跑排查）
    body = (result.stdout or "") + (("\n[stderr]\n" + result.stderr) if result.stderr else "")
    if ok:
        detail = "\n".join([line for line in body.splitlines() if line.strip()][-4:])
    else:
        detail = body.strip() or "（脚本无输出）"
        detail += "\n→ 修 README「获取方式」/ 包内文件，或看上面脚本输出的逐条原因"
    report.add("下载文档一致性（offline）", ok, detail)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发版前自检")
    parser.parse_args(argv)

    report = Report()
    try:
        check_versions(report)
    except Exception as exc:  # noqa: BLE001 —— 自检脚本自己不许炸
        report.add("三处版本号一致", False, f"检查本身失败：{type(exc).__name__}: {exc}")
    try:
        check_master_settings(report)
    except Exception as exc:  # noqa: BLE001
        report.add("母版 .settings/ 编码钉在盘 + 在库", False,
                   f"检查本身失败：{type(exc).__name__}: {exc}")
    try:
        check_download_docs(report)
    except Exception as exc:  # noqa: BLE001
        report.add("下载文档一致性（offline）", False,
                   f"检查本身失败：{type(exc).__name__}: {exc}")

    print("=== 发版前自检 ===")
    print(report.render())
    print()
    if report.failed:
        print(f"结论：{len(report.failed)} 项红——**先修再打包/打 tag**：")
        for name, _detail in report.failed:
            print(f"  · {name}")
        return 1
    print(f"结论：全绿，可以发版（当前版本 v{tool_version()}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
