# -*- coding: utf-8 -*-
"""判据强度自检：把 `tests/test_webapp_state_home.py` 的每条判据腿逐个 stub 掉，看守卫会不会红
（工单 webapp-state-into-ctx/03）。

**为什么要有这支探针**：对抗性验证实测过一个反例——早期版本 stub 掉 `global_names` 或
`_test_sources` 之后守卫**仍然 7 passed 全绿**（那两条腿被别的腿兜住了 = 没有红证）。
判据的"有没有牙齿"不能靠读代码断言，只能逐个 stub 跑一遍。

做法：在**文件末尾**追加一行重定义（同模块后定义覆盖先定义），跑 `pytest -q`，再**逐字节复原**。
不碰 git、不留中间态；跑完自校验 sha256 与改前一致。

**别和测试套件同时跑**（它短时间改库内文件）。

用法：
    python .scratch/webapp-state-into-ctx/probe-02-guard-strength.py [--out guard-strength.txt]
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUARD = REPO / "tests" / "test_webapp_state_home.py"

# (腿名, 追加到文件末尾的 stub 源码, 期望守卫红的理由)
STUBS: tuple[tuple[str, str, str], ...] = (
    ("global_statements", "def global_statements(source):\n    return []\n", "判据① 不再看得见 global"),
    ("global_names", "def global_names(source):\n    return set()\n", "判据③ 的 global 名单腿"),
    ("module_level_assignments", "def module_level_assignments(source):\n    return {}\n", "模块级赋值抽取"),
    ("module_level_names", "def module_level_names(source):\n    return set()\n", "模块级名字腿"),
    ("session_state_assignments", "def session_state_assignments(source):\n    return {}\n", "判据② 本体"),
    ("_is_session_shape", "def _is_session_shape(shape):\n    return False\n", "判据② 的形状判据"),
    ("imported_names", "def imported_names(source, module_suffix):\n    return set()\n", "跨缝 import 腿"),
    ("module_object_aliases", "def module_object_aliases(source):\n    return set()\n", "模块对象别名腿"),
    ("module_object_uses", "def module_object_uses(source):\n    return set()\n", "别名直改腿"),
    ("webapp_attribute_paths", "def webapp_attribute_paths(source):\n    return set()\n", "monkeypatch 路径腿"),
    ("annotated_class_fields", "def annotated_class_fields(source, class_name):\n    return set()\n", "判据④ 正向腿"),
    ("state_violations", "def state_violations(webapp_source, test_sources):\n    return []\n", "聚合（探针跑的就是它）"),
    ("_test_sources", "def _test_sources(root=None):\n    return {}\n", "真树扫描面"),
)


def run_guard() -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_webapp_state_home.py", "-q", "-p", "no:cacheprovider"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    text = proc.stdout if proc.stdout.strip() else proc.stderr
    tail = [line for line in text.strip().splitlines() if line.strip()][-1:] or ["（无输出）"]
    return proc.returncode == 0, tail[0]


def main() -> int:
    args = sys.argv[1:]
    out_path = Path(args[args.index("--out") + 1]) if "--out" in args else None

    original = GUARD.read_bytes()
    sha_before = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")

    lines = ["== 判据强度自检：每条腿 stub 掉之后守卫必须红 ==", ""]
    green_before, summary = run_guard()
    lines.append(f"  基线（不动文件）：{'绿' if green_before else '红'} —— {summary}")
    lines.append("")

    failures: list[str] = []
    try:
        for name, stub, why in STUBS:
            GUARD.write_text(text + "\n\n# [probe] stub\n" + stub, encoding="utf-8")
            green, summary = run_guard()
            verdict = "✅ 变红" if not green else "❌ 仍绿（这条腿没有红证）"
            lines.append(f"  {verdict}  {name:<26} {why} —— {summary}")
            if green:
                failures.append(name)
    finally:
        GUARD.write_bytes(original)

    sha_after = hashlib.sha256(GUARD.read_bytes()).hexdigest()
    lines.append("")
    lines.append(f"逐字节复原：{'✅ sha256 一致' if sha_before == sha_after else '❌ 不一致！'}"
                 f"（{sha_before[:12]}…）")
    lines.append("")
    lines.append(
        f"结论：{len(STUBS) - len(failures)}/{len(STUBS)} 条腿 stub 后变红"
        + (f"；仍绿：{failures}" if failures else "；没有'没有红证'的腿")
    )
    report = "\n".join(lines)
    print(report)
    if out_path is not None:
        out_path.write_text(report + "\n", encoding="utf-8")
    return 0 if (not failures and green_before and sha_before == sha_after) else 1


if __name__ == "__main__":
    sys.exit(main())
