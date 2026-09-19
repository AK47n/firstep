# -*- coding: utf-8 -*-
"""判据强度探针：把「egg-info 不进包」这条守卫弄坏，看它会不会红（工单 `release-v1.2.2/01`）。

为什么要它：「守卫全绿」本身不说明任何事——**把被测行为改坏、守卫必须转红**才算数
（照 `.scratch/update-orphan-files/probe-guard-strength.py` 的先例）。

两处注入各代表一种退化方式：

- ① **目录名通配被清空**（`SKIP_DIR_GLOBS = ()`）：`*.egg-info` 又变成产品文件，
  完整包会把它发给每个用户——真值表与扫描面两条守卫都必须抓住；
- ② **判据被抄回扫描函数**：谓词不问了，改成内联的「目录名精确匹配」——
  行为几乎等价，但 `.egg-info` 这种带前缀的目录名精确匹配装不下，
  单源也被破坏（这正是静态守卫存在的意义）。

每一个用例：改坏一处 → 跑对应测试 → 记「红/绿」→ **无论结果如何都复原**
（`finally` 里按原字节写回，并复核 sha256）。

判据：**每一条注入都必须转红**。有绿的 = 那条守卫是摆设 → 探针退出码非 0。

用法::

    python .scratch/release-v1.2.2/probe-guard-strength.py
    # 证据落 verify-01-guard-strength.txt / .json
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

# 控制台是 GBK（Windows 中文默认）：脚本里的 ✓ / ✗ / 中文必须能出去，
# 否则打印时抛 UnicodeEncodeError 把整轮探针打断（照 drill-02 的先例）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

FULL_PACK = "src/contest_generator/full_pack.py"

#: (名字, 文件, 改前（必须唯一命中）, 改后, -k 表达式)
CASES: list[tuple[str, str, str, str, str]] = [
    (
        "① 目录名通配被清空：*.egg-info 又成产品文件",
        FULL_PACK,
        'SKIP_DIR_GLOBS: tuple[str, ...] = ("*.egg-info",)',
        'SKIP_DIR_GLOBS: tuple[str, ...] = ()  # 注入：不排除 egg-info',
        "product_file_predicate or scan_tree_excludes_caches",
    ),
    (
        "② 谓词被抄回扫描函数：目录名只做精确匹配（装不下 <包名>.egg-info）",
        FULL_PACK,
        "        if product_file_reason(relative, skip_dir_names=dir_skips) is not None:",
        "        if not parts or parts[0] not in TOP_LEVEL_ENTRIES:  # 注入：内联规则\n"
        "            continue\n"
        "        if any(part in dir_skips for part in parts[:-1]):\n"
        "            continue\n"
        "        if product_file_reason(relative, skip_dir_names=dir_skips) is not None:",
        "scan_tree_asks_the_single_predicate",
    ),
]

LINES: list[str] = []
RESULTS: dict = {"cases": []}


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def read_text(relative: str) -> str:
    """按**字节**读再解码（不用 `Path.read_text`），保证「复原复核」是逐字节判定。

    文本模式读会把 CRLF 归一成 LF、写回时再按平台换回 CRLF——文件里只要有一处混行，
    一次往返就把整份文件的换行统一了，于是复核报假红（上一轮实测踩到过）。
    """
    return (ROOT / relative).read_bytes().decode("utf-8")


def write_text(relative: str, text: str) -> None:
    (ROOT / relative).write_bytes(text.encode("utf-8"))


def newline_of(text: str) -> str:
    """目标文件的换行风格（探针里的锚点一律以 LF 书写，注入前要适配）。"""
    return "\r\n" if "\r\n" in text else "\n"


def adapt(text: str, newline: str) -> str:
    """把 LF 书写的锚点 / 注入文本适配到目标文件的换行风格。"""
    return text.replace("\n", newline) if newline != "\n" else text


def sha256(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def run_tests(keyword: str) -> tuple[bool, str]:
    """跑既有测试（本轮不新开文件：egg-info 判据加在 `test_full_pack.py` 同族里）。"""
    command = [sys.executable, "-m", "pytest",
               "tests/test_full_pack.py", "tests/test_pack_update.py",
               "-q", "-p", "no:cacheprovider"]
    if keyword:
        command += ["-k", keyword]
    try:
        proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
    except subprocess.TimeoutExpired:
        return False, "卡住（300 秒未返回）"
    tail = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    return proc.returncode == 0, (tail[-1] if tail else "(无输出)")


def main() -> int:
    log("# 判据强度探针：「egg-info 不进包」（工单 release-v1.2.2/01）")
    log(f"  仓库：{ROOT}")
    log("  判据：**每一条注入都必须转红**（有绿的 = 那条守卫是摆设）")
    log("")

    # 前置：目标文件必须是干净状态（探针被强杀时 finally 跑不到，文件会停在注入态——
    # 那时后面每条都报「锚点失效」，看起来像探针写错了）。
    missing: list[str] = []
    for name, path, old, _new, _kw in CASES:
        text = read_text(path)
        if text.count(adapt(old, newline_of(text))) != 1:
            missing.append(f"{name}（{path}）")
    if missing:
        log("**拒绝开跑**：目标文件不是干净状态（可能上一轮探针被强杀、没来得及复原）。")
        for item in missing:
            log(f"  · 锚点不在：{item}")
        log(f"  修法：`git checkout -- {FULL_PACK}` 之后重跑本探针。")
        RESULTS["preflight_missing"] = missing
        RESULTS["verdict"] = "FAIL"
        return 2

    targets = sorted({case[1] for case in CASES})
    baseline_sha = {path: sha256(path) for path in targets}
    weak: list[str] = []
    for name, path, old, new, keyword in CASES:
        log("-" * 78)
        log(f"[注入] {name}")
        log(f"  文件：{path}")
        original = read_text(path)
        sha_before_case = sha256(path)
        newline = newline_of(original)
        try:
            write_text(path, original.replace(adapt(old, newline), adapt(new, newline), 1))
            green, summary = run_tests(keyword)
        finally:
            write_text(path, original)               # 无论结果如何都复原
        sha_after_case = sha256(path)
        turned_red = not green
        log(f"  测试：-k {keyword!r}")
        log(f"  结果：{'转红 ✓' if turned_red else '**仍然全绿 ✗**'} —— {summary}")
        log(f"  复原：{'逐字节相同 ✓' if sha_after_case == sha_before_case else '**不同 ✗**'}"
            f"（{sha_before_case[:12]} → {sha_after_case[:12]}）")
        RESULTS["cases"].append({"name": name, "file": path, "turned_red": turned_red,
                                 "summary": summary, "weak": not turned_red,
                                 "restored": sha_after_case == sha_before_case})
        if not turned_red:
            weak.append(name)

    log("")
    log("-" * 78)
    log("## 复原复核")
    for path, before in baseline_sha.items():
        after = sha256(path)
        log(f"  {path} sha256 "
            f"{'未变 ✓' if after == before else f'**变了 ✗（{before[:12]} → {after[:12]}）**'}")
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
        print("\n证据已写：verify-01-guard-strength.txt / .json")
    raise SystemExit(code)
