# -*- coding: utf-8 -*-
"""判据强度自检：把 `tests/test_webapp_state_home.py` 的每条判据腿逐个 stub 掉，看守卫会不会红
（工单 webapp-state-into-ctx/03；工单 full-update-state-into-ctx/03 扩到两条腿 + src 全域腿）。

**为什么要有这支探针**：对抗性验证实测过一个反例——早期版本 stub 掉 `global_names` 或
`_test_sources` 之后守卫**仍然 7 passed 全绿**（那两条腿被别的腿兜住了 = 没有红证）。
判据的"有没有牙齿"不能靠读代码断言，只能逐个 stub 跑一遍。

做法：在**文件末尾**追加一行重定义（同模块后定义覆盖先定义），跑 `pytest -q`，再**逐字节复原**。
不碰 git、不留中间态；跑完自校验 sha256 与改前一致。

**别和测试套件同时跑**（它短时间改库内文件）。

**2026-09-22 三处维护（工单 full-update-state-into-ctx/03 随守卫扩面做的）**：① stub 签名放宽成
`(*args, **kwargs)` —— 守卫的几个判据函数加了**尾参数带缺省**（为兼容 C6 的红证探针），旧签名的
stub 会以 `TypeError` 让守卫变红，那是"因为报错所以红"，**不是**"这条腿有牙齿"的证明（假红比假绿
更阴）；② STUBS 补上完整包那半与 `src` 全域腿的名字，并把 `webapp_attribute_paths` 跟着守卫的
更名改成 `module_attribute_paths`；③「先落盘再打印」+ stdout 重设 UTF-8（本机控制台 GBK 打不出
`✅`，打印抛异常会连带丢掉整份证据文件）。**先例钉住的形状（显式钉 base + base 自校验 + 与守卫
共用聚合）一字未动**；stub 清单本来就是随守卫演化的内部件。

**归属（如实记账）**：本探针是**整个守卫文件**的强度自检（两支工单目录共用它），所以留在这里没动；
当前 17 条腿的读数落在 `.scratch/full-update-state-into-ctx/guard-strength.txt`，C6 工单记的
`13/13` 是那 13 条腿版本的历史读数（本目录 `guard-strength.txt` 保持原样，不追改历史）。

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

# 本机控制台是 GBK：报告里带 `✅` / `❌`，不重设就在 print 上抛 UnicodeEncodeError
# （2026-09-22 实测把整份证据文件丢了）。证据文件本身一律 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # 被重定向到非文本流时不管
        pass

# (腿名, 追加到文件末尾的 stub 源码, 期望守卫红的理由)
# 签名一律 `(*args, **kwargs)`：判据参数化后仍能覆盖，避免"TypeError 假红"。
STUBS: tuple[tuple[str, str, str], ...] = (
    ("global_statements", "def global_statements(*a, **k):\n    return []\n", "判据① 不再看得见 global"),
    ("global_names", "def global_names(*a, **k):\n    return set()\n", "判据③ 的 global 名单腿"),
    ("module_level_assignments", "def module_level_assignments(*a, **k):\n    return {}\n", "模块级赋值抽取"),
    ("module_level_names", "def module_level_names(*a, **k):\n    return set()\n", "模块级名字腿"),
    ("session_state_assignments", "def session_state_assignments(*a, **k):\n    return {}\n", "判据② 本体"),
    ("_is_session_shape", "def _is_session_shape(*a, **k):\n    return False\n", "判据② 的形状判据"),
    ("imported_names", "def imported_names(*a, **k):\n    return set()\n", "跨缝 import 腿"),
    ("module_object_aliases", "def module_object_aliases(*a, **k):\n    return set()\n", "模块对象别名腿"),
    ("module_object_uses", "def module_object_uses(*a, **k):\n    return set()\n", "别名直改腿"),
    ("module_attribute_paths", "def module_attribute_paths(*a, **k):\n    return set()\n", "monkeypatch 路径腿"),
    ("annotated_class_fields", "def annotated_class_fields(*a, **k):\n    return set()\n", "判据④ 正向腿"),
    ("state_violations", "def state_violations(*a, **k):\n    return []\n", "webapp 腿聚合（C6 探针跑的就是它）"),
    ("module_state_violations", "def module_state_violations(*a, **k):\n    return []\n", "两条腿共用的那条聚合"),
    ("full_chain_state_violations", "def full_chain_state_violations(*a, **k):\n    return []\n", "完整包腿聚合（本单探针跑的就是它）"),
    ("src_global_statements", "def src_global_statements(*a, **k):\n    return {}\n", "src 全域 global 腿本体"),
    ("_test_sources", "def _test_sources(*a, **k):\n    return {}\n", "真树扫描面（测试侧）"),
    ("_src_sources", "def _src_sources(*a, **k):\n    return {}\n", "真树扫描面（src 侧）"),
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
    # **先落盘再打印**（2026-09-22 修正）：本机控制台 GBK 打不出 `✅`，打印抛异常会连带
    # 丢掉证据文件——文件先写，控制台那一步失败也不影响读数落盘。
    if out_path is not None:
        out_path.write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0 if (not failures and green_before and sha_before == sha_after) else 1


if __name__ == "__main__":
    sys.exit(main())
