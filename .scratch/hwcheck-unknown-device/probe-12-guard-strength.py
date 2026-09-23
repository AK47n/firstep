# -*- coding: utf-8 -*-
"""工单 hwcheck-unknown-device/12 的**判据强度探针**（反证）：把三条旧坏法注入回去，
看本单的新用例是不是真的变红，再逐字节复原并复核 sha256。

三条注入各打本单一条新守卫（工单 12 取的是出路①：id 文法收紧到 C 标识符可用
字符，判据单源 `my_devices.DEVICE_ID_PATTERN`）：

* **注入 A** —— `DEVICE_ID_PATTERN` 本身放宽回允许连字符的旧文法 →
  `test_the_device_id_grammar_only_admits_c_identifier_characters`（文法面逐字钉）
  变红；
* **注入 B** —— 保存路径不再查文法（`_require_device_id` 的字符集判据短路成
  `False`）→ `test_create_rejects_a_hyphen_id_and_says_why`（建件端点 400 并说清
  为什么）变红——判据本体在、执行点被绕过时它也得响；
* **注入 C** —— 列表装载吞掉坏条目（`list_devices` 静默跳过读不出来的条目）→
  `test_a_stale_hyphen_entry_on_disk_is_named_loudly`（盘上旧坏条目大声点名 + 指路）
  变红。

⚠ 纪律（本仓库先例 `module-hwcheck/09`、`probe-05/06-guard-strength.py`）：
**别和测试套件同时跑**——探针会真的改库内文件（改完逐字节复原）。
⚠ 先落盘再打印（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。
⚠ 源码读写一律走 **bytes**（文本模式会把 CRLF 归一成 LF，"复原复核"当场假红）。

用法：`python .scratch/hwcheck-unknown-device/probe-12-guard-strength.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SYS = REPO / "src" / "contest_generator"
MY_DEVICES = SYS / "my_devices.py"
DOMAIN_TESTS = "tests/test_my_devices.py"
ENDPOINT_TESTS = "tests/test_my_devices_endpoint.py"

# 三条注入：文件 / 锚点（必须在原文里唯一）/ 替换文本 / 该让哪条用例变红
INJECTIONS = (
    {
        "name": "A: DEVICE_ID_PATTERN 放宽回允许连字符的旧文法",
        "path": MY_DEVICES,
        "anchor": 'DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")',
        "replacement": 'DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")',
        "test": "test_the_device_id_grammar_only_admits_c_identifier_characters",
        "test_file": DOMAIN_TESTS,
    },
    {
        "name": "B: 保存路径不再查字符集（判据本体在、执行点被绕过）",
        "path": MY_DEVICES,
        "anchor": "        or DEVICE_ID_PATTERN.fullmatch(text) is None\n",
        "replacement": "        or False\n",
        "test": "test_create_rejects_a_hyphen_id_and_says_why",
        "test_file": ENDPOINT_TESTS,
    },
    {
        "name": "C: 列表装载吞掉坏条目（静默跳过，不再大声点名）",
        "path": MY_DEVICES,
        "anchor": (
            "    devices = [\n"
            "        _load_entry(entry)\n"
            "        for entry in directory.iterdir()\n"
            "        if entry.is_dir() and not entry.name.startswith(\".\")\n"
            "    ]\n"
        ),
        "replacement": (
            "    devices = []\n"
            "    for entry in directory.iterdir():\n"
            "        if entry.is_dir() and not entry.name.startswith(\".\"):\n"
            "            try:\n"
            "                devices.append(_load_entry(entry))\n"
            "            except MyDeviceError:\n"
            "                continue\n"
        ),
        "test": "test_a_stale_hyphen_entry_on_disk_is_named_loudly",
        "test_file": DOMAIN_TESTS,
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def match_anchor(path: Path, text: str) -> tuple[bytes, str] | tuple[None, None]:
    """锚点文本 → **文件里真实的那段字节**，连同它的行尾形态。

    ⚠ 行尾必须按文件实况取（本仓库两种形态并存：`git` 检出的文本是 CRLF
    ——`core.autocrlf=true`，而工具新写的文件是 LF）。锚点里一律写 `\\n`，
    这里先试 LF 再试 CRLF，恰好命中一处才算数；替换文本跟着用同一种行尾，
    免得把注入进去的那几行写成另一种换行。
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
    files = (MY_DEVICES,)
    before = {path: sha256(path) for path in files}

    # 前置：源文件此刻是干净的（上一轮被强杀会留在注入态——先自检，别把"已经在
    # 注入态"读成"守卫没抓住"）
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
