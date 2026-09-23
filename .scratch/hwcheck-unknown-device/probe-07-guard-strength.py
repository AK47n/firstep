# -*- coding: utf-8 -*-
"""工单 hwcheck-unknown-device/07 的**判据强度探针**（反证）：把四条旧坏法注入回去，
看本单的新用例是不是真的变红，再逐字节复原并复核 sha256。

四条注入各打本单一条新守卫（草稿抽取的判据本体在 `my_device_draft`）：

* **注入 A** —— 出处比对绕过（资料原文里找不到的片段照单全收）→
  `test_a_source_quote_not_in_the_material_is_fabrication`（反编造判据）变红；
* **注入 B** —— 字段白名单放宽（模型自己发明的字段照收）→
  `test_a_field_outside_the_whitelist_is_rejected` 变红；
* **注入 C** —— 数值区间放开（7 位地址的区间守卫短路）→
  `test_an_out_of_range_or_non_numeric_address_is_rejected` 变红；
* **注入 D** —— import 面破戒（草稿链路顺手 import 生成侧模块）→
  `test_the_draft_chain_imports_nothing_that_renders_c`（本链路不产出任何 C）变红。

⚠ 纪律（本仓库先例 `module-hwcheck/09`、`probe-05/06/12-guard-strength.py`）：
**别和测试套件同时跑**——探针会真的改库内文件（改完逐字节复原）。
⚠ 先落盘再打印（本机控制台 GBK，print 抛 UnicodeEncodeError 会让证据整份丢）。
⚠ 源码读写一律走 **bytes**（文本模式会把 CRLF 归一成 LF，"复原复核"当场假红）。

用法：`python .scratch/hwcheck-unknown-device/probe-07-guard-strength.py [--out FILE]`
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SYS = REPO / "src" / "contest_generator"
DRAFT = SYS / "my_device_draft.py"
DOMAIN_TESTS = "tests/test_my_device_draft.py"

# 四条注入：文件 / 锚点（必须在原文里唯一）/ 替换文本 / 该让哪条用例变红
INJECTIONS = (
    {
        "name": "A: 出处比对绕过（资料里没有的片段照单全收 = 编造放行）",
        "path": DRAFT,
        "anchor": "    if _normalize(source) not in _normalize(material_text):\n",
        "replacement": "    if False:\n",
        "test": "test_a_source_quote_not_in_the_material_is_fabrication",
        "test_file": DOMAIN_TESTS,
    },
    {
        "name": "B: 字段白名单放宽（模型自己发明的字段照收）",
        "path": DRAFT,
        "anchor": "    unknown = sorted(set(map(str, raw)) - set(DRAFT_FIELDS))\n",
        "replacement": "    unknown: list[str] = []\n",
        "test": "test_a_field_outside_the_whitelist_is_rejected",
        "test_file": DOMAIN_TESTS,
    },
    {
        "name": "C: 数值区间放开（7 位地址的区间守卫短路）",
        "path": DRAFT,
        "anchor": (
            '    low, high = (ADDRESS7_MIN, ADDRESS7_MAX) if key == "address" '
            "else (0, limit - 1)\n"
        ),
        "replacement": "    low, high = (0, 1 << 32)\n",
        "test": "test_an_out_of_range_or_non_numeric_address_is_rejected",
        "test_file": DOMAIN_TESTS,
    },
    {
        "name": "D: import 面破戒（草稿链路顺手 import 生成侧模块）",
        "path": DRAFT,
        "anchor": "def _normalize(text: str) -> str:\n",
        "replacement": (
            "from .generator import generate_project  # 注入：生成侧模块混进草稿链路\n"
            "def _normalize(text: str) -> str:\n"
        ),
        "test": "test_the_draft_chain_imports_nothing_that_renders_c",
        "test_file": DOMAIN_TESTS,
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def match_anchor(path: Path, text: str) -> tuple[bytes, str] | tuple[None, None]:
    """锚点文本 → **文件里真实的那段字节**，连同它的行尾形态。

    ⚠ 行尾必须按文件实况取（本仓库两种形态并存：`git` 检出的文本是 CRLF
    ——`core.autocrlf=true`，而工具新写的文件是 LF）。锚点里一律写 `\\n`，
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
    files = (DRAFT,)
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
