# -*- coding: utf-8 -*-
r"""判据强度反证（工单 ci-gate-fixes/04）：把三处注入**真改** webapp.py，验证新加的
判据会红；跑完按原字节复原并复核 sha256。

**别和测试套件同时跑**（它会真的改库内文件——本仓老纪律，见 local-environment 第 2 节）。

注入三格：
① `modules()`（库端点）里塞回 `_require_config(context)` → 分类注册表必须红；
② `_library_dir()` 改回 `_require_config(ctx).module_library_dir` → 访问器不变量必须红；
③ `_hwcheck_library_config()` 改回只看 `_current_config` → 检测页那条引导态用例必须红
（评审补口：它曾经是第三道只看"有没有配置"的闸）。

用法（仓库根）：python .scratch\ci-gate-fixes\probe-04-guard-strength.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "src" / "contest_generator" / "webapp.py"

# (格名, 判据用例, 原文, 注入后)
CASES: tuple[tuple[str, str, bytes, bytes], ...] = (
    (
        "库端点上又挂回 AI 闸",
        "test_ai_gate_registry_matches_source",
        b"        module_root = _library_dir(context)\n",
        b"        module_root = _require_config(context).module_library_dir\n",
    ),
    (
        "库访问器里又看 api_key",
        "test_library_accessors_never_consult_the_api_key",
        b"def _library_dir(ctx: AppContext) -> Path:\n"
        b"    return _library_config(ctx).module_library_dir\n",
        b"def _library_dir(ctx: AppContext) -> Path:\n"
        b"    return _require_config(ctx).module_library_dir\n",
    ),
    (
        "检测页那道闸退回只看「有没有配置」",
        "test_bootstrap_state_serves_the_hardware_check_page",
        b"    app_config = _resolve_library_config(ctx)\n",
        b"    app_config = _current_config(ctx)\n",
    ),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(test_name: str) -> tuple[bool, str]:
    """跑一条用例，返回 (它红了吗, 摘要)。"""
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            f"tests/test_library_gate.py::{test_name}",
            "-q", "--no-header", "-p", "no:cacheprovider",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    tail = (proc.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else (proc.stderr or "")[-200:]
    return proc.returncode != 0, summary


def main() -> int:
    original = TARGET.read_bytes()
    before = sha(TARGET)
    print(f"注入前 sha256 = {before}")
    failures: list[str] = []
    try:
        for label, test_name, old, new in CASES:
            if original.count(old) != 1:
                print(f"✗ [{label}] 锚点在源码里出现 {original.count(old)} 次（应为 1）")
                failures.append(label)
                continue
            TARGET.write_bytes(original.replace(old, new, 1))
            red, summary = run_case(test_name)
            TARGET.write_bytes(original)          # 每格跑完立刻复原
            sys.stdout.write(
                f"{'✓' if red else '✗'} [{label}] 期望 {test_name} 变红 → "
                f"{'红了' if red else '没红（判据没牙）'}｜{summary}\n"
            )
            if not red:
                failures.append(label)
    finally:
        TARGET.write_bytes(original)
    after = sha(TARGET)
    print(f"\n复原后 sha256 = {after}")
    intact = after == before
    print(f"逐字节复原：{'是' if intact else '否——快去查！'}")
    if not intact:
        failures.append("复原")
    print(f"\n结论：{'PASS（三格注入都让判据变红、文件逐字节复原）' if not failures else 'FAIL：' + '；'.join(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
