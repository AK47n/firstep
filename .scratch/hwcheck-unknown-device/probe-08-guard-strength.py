# -*- coding: utf-8 -*-
"""工单 hwcheck-unknown-device/08 的**判据强度探针**（反证）：把四条旧坏法注入回去，
看本单的新用例是不是真的变红，再逐字节复原并复核 sha256。

四条注入各打本单一条新守卫（工程内快照 + 回读以快照为准）：

* **注入 A** —— 回读不再吃工程内快照（照旧读数据目录）→
  `test_readback_prefers_the_project_snapshot_after_the_device_is_deleted`
  （删掉「我的器件」后回读仍完整）变红；
* **注入 B** —— 归档时定义不见了就静默跳过（不再大声报错）→
  `test_archive_is_loud_when_the_definition_has_vanished` 变红；
* **注入 C** —— 幂等保存不再带走上一次的资料与草稿 →
  `test_save_carries_over_provenance_when_not_given_again` 变红；
* **注入 D** —— 生成后不再调用归档 → `test_generate_archives_the_custom_device_
  into_the_project` 变红。

⚠ 纪律（本仓库先例 `module-hwcheck/09`、`probe-05/06/07/12-guard-strength.py`）：
**别和测试套件同时跑**——探针会真的改库内文件（改完逐字节复原）。
⚠ 先落盘再打印（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。
⚠ 源码读写一律走 **bytes**（文本模式会把 CRLF 归一成 LF，"复原复核"当场假红）。

用法：`python .scratch/hwcheck-unknown-device/probe-08-guard-strength.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SYS = REPO / "src" / "contest_generator"
BOARD = SYS / "hwcheck_board.py"
STORE = SYS / "hwcheck_store.py"
MY_DEVICES = SYS / "my_devices.py"
WEBAPP = SYS / "webapp.py"
ENDPOINT_TESTS = "tests/test_my_devices_endpoint.py"
STORE_TESTS = "tests/test_hwcheck_store.py"
MY_DEVICES_TESTS = "tests/test_my_devices.py"

# 四条注入：文件 / 锚点（必须在原文里唯一）/ 替换文本 / 该让哪条用例变红
INJECTIONS = (
    {
        "name": "A: 回读不再吃工程内快照（照旧读数据目录）",
        "path": BOARD,
        "anchor": "    if snapshot_dir is not None:\n",
        "replacement": "    if False:\n",
        "test": "test_readback_prefers_the_project_snapshot_after_the_device_is_deleted",
        "test_file": ENDPOINT_TESTS,
    },
    {
        "name": "B: 归档时定义不见了就静默跳过（不再大声报错）",
        "path": STORE,
        "anchor": (
            "        if not source.is_dir():\n"
            "            raise HwCheckError(\n"
        ),
        "replacement": (
            "        if not source.is_dir():\n"
            "            continue\n"
            "        if False:\n"
        ),
        "test": "test_archive_is_loud_when_the_definition_has_vanished",
        "test_file": STORE_TESTS,
    },
    {
        "name": "C: 幂等保存不再带走上一次的资料与草稿",
        "path": MY_DEVICES,
        "anchor": "            _carry_over_provenance(entry_dir, staging, material_text, draft)\n",
        "replacement": "            pass\n",
        "test": "test_save_carries_over_provenance_when_not_given_again",
        "test_file": MY_DEVICES_TESTS,
    },
    {
        "name": "D: 生成后不再调用归档",
        "path": WEBAPP,
        "anchor": "        archive_custom_devices(\n            summary.output_dir,\n",
        "replacement": "        (lambda *a, **k: ())(\n            summary.output_dir,\n",
        "test": "test_generate_archives_the_custom_device_into_the_project",
        "test_file": ENDPOINT_TESTS,
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def match_anchor(path: Path, text: str) -> tuple[bytes, str] | tuple[None, None]:
    """锚点文本 → **文件里真实的那段字节**，连同它的行尾形态。

    ⚠ 行尾必须按文件实况取（本仓库两种形态并存）。锚点里一律写 `\\n`，
    这里先试 LF 再试 CRLF，恰好命中一处才算数；替换文本跟着用同一种行尾。
    """
    data = path.read_bytes()
    for newline in ("\n", "\r\n"):
        candidate = text.replace("\n", newline).encode("utf-8")
        if data.count(candidate) == 1:
            return candidate, newline
    return None, None


def run_test(name: str, test_file: str) -> tuple[bool, str]:
    """跑一条用例；返回（是否通过, 摘要行）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-q", "-p", "no:cacheprovider",
         "-k", name],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=900,
    )
    tail = [
        line.strip() for line in (proc.stdout or "").splitlines()
        if "passed" in line or "failed" in line or "error" in line
    ]
    return proc.returncode == 0, (tail[-1] if tail else f"exit={proc.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(Path(__file__).with_suffix(".txt")),
        help="证据文件（UTF-8，先落盘再打印；缺省 = 与本探针同名的 .txt）",
    )
    args = parser.parse_args()

    lines: list[str] = []
    ok_all = True
    files = (BOARD, STORE, MY_DEVICES, WEBAPP)
    before = {path: sha256(path) for path in files}

    lines.append("[1] 前置检查（源文件指纹与锚点唯一性）")
    for injection in INJECTIONS:
        path: Path = injection["path"]
        anchor, newline = match_anchor(path, injection["anchor"])
        assert anchor is not None, (
            f"{path.name} 里锚点不唯一或找不到（注入目标必须恰好一处）："
            f"{injection['name']}"
        )
        injection["_anchor_bytes"] = anchor
        injection["_newline"] = newline
    for path in files:
        lines.append(f"    {path.name}: {sha256(path)[:16]}…（锚点各一处 ✓）")

    cases = [(item["test"], item["test_file"]) for item in INJECTIONS]
    base = [run_test(name, test_file) for name, test_file in cases]
    base_ok = all(good for good, _ in base)
    lines.append(
        f"[2] 注入前（守卫在）："
        f"{'PASS（' + str(len(cases)) + ' 条全绿）' if base_ok else 'RED ✗'}"
        f"  ｜ {' / '.join(tail for _g, tail in base)}"
    )
    ok_all = ok_all and base_ok

    for injection in INJECTIONS:
        path: Path = injection["path"]
        original_bytes = path.read_bytes()
        anchor: bytes = injection["_anchor_bytes"]
        replacement = injection["replacement"].replace(
            "\n", injection["_newline"]
        ).encode("utf-8")
        try:
            path.write_bytes(original_bytes.replace(anchor, replacement))
            good, tail = run_test(injection["test"], injection["test_file"])
            lines.append(
                f"[3] 注入 {injection['name']} → "
                f"{'RED（守卫变红）' if not good else '仍绿（守卫没抓住！）'} ｜ {tail}"
            )
            ok_all = ok_all and not good
        finally:
            path.write_bytes(original_bytes)
            restored = sha256(path) == before[path]
            lines.append(
                f"[4] 复原复核：{path.name} sha256 "
                f"{'相等 ✓' if restored else '不相等 ✗'}（{sha256(path)[:16]}…）"
            )
            ok_all = ok_all and restored

    for name, test_file in cases:
        good, tail = run_test(name, test_file)
        lines.append(f"[5] 复原后复跑：{name} {'PASS（回绿）' if good else 'RED ✗'} ｜ {tail}")
        ok_all = ok_all and good

    final = {path: sha256(path) for path in files}
    same = final == before
    lines.append(
        f"[6] 收尾指纹：{f'{len(files)} 个文件逐字节未变 ✓' if same else '有文件被改动 ✗'}"
    )
    ok_all = ok_all and same
    lines.append("")
    lines.append(
        "=== 结论：" + (f"反证成立（{len(INJECTIONS)} 条注入都让对应用例变红，"
                       "且逐字节复原）"
                       if ok_all else "反证不成立（见上面读数）") + " ==="
    )
    report = "\n".join(lines) + "\n"
    Path(args.out).write_text(report, encoding="utf-8")          # 先落盘
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 再打印
    print(report)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
