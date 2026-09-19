# -*- coding: utf-8 -*-
"""判据强度探针：把「产品文件判据单源」这条守卫弄坏，看它会不会红（工单 `update-orphan-files/01`）。

为什么要它：「守卫全绿」本身不说明任何事——**把被测行为改坏、守卫必须转红**才算数
（照 `.scratch/update-restart-stale-service/probe-guard-strength.py` 的先例）。

四处注入各代表一种退化方式：

- ① **谓词放宽**：不再按目录名排除（本机库备份又变成产品文件，会被发给用户）；
- ② **筛选被摘掉**：候选清单原样进包（小发版又开始多发）；
- ③ **判据被抄回扫描函数**：行为等价但单源被破坏（这正是静态守卫存在的意义）；
- ④ **打包脚本里手抄白名单**：漂移的老路（静态守卫必须抓住）。

每一个用例：改坏一处 → 跑对应测试 → 记「红/绿」→ **无论结果如何都复原**
（`finally` 里按原字节写回，并复核 sha256）。

判据：**每一条注入都必须转红**。有绿的 = 那条守卫是摆设 → 探针退出码非 0。

用法::

    python .scratch/update-orphan-files/probe-guard-strength.py
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
PACK_UPDATE = "src/contest_generator/pack_update.py"
PACK_UPDATE_PS1 = "tools/pack-update.ps1"

#: (名字, 文件, 改前（必须唯一命中）, 改后, -k 表达式)
CASES: list[tuple[str, str, str, str, str]] = [
    (
        "① 谓词放宽：不再按目录名排除（本机库备份又成产品文件）",
        FULL_PACK,
        '    if any(part in dir_skips for part in parts[:-1]):\n        return "dir-name"',
        '    if False:  # 注入：不看目录名\n        return "dir-name"',
        "product_file_predicate or scan_tree_matches",
    ),
    (
        "② 筛选被摘掉：候选清单原样进包（小发版又开始多发）",
        PACK_UPDATE,
        "        if not name or name in seen or not is_product_file(name):",
        "        if not name or name in seen:  # 注入：不筛",
        "non_product_candidates",
    ),
    (
        "③ 判据被抄回扫描函数（行为等价，但单源被破坏）",
        FULL_PACK,
        "        if product_file_reason(relative, skip_dir_names=dir_skips) is not None:\n"
        "            continue",
        "        if not parts or parts[0] not in TOP_LEVEL_ENTRIES:  # 注入：内联规则\n"
        "            continue\n"
        "        if any(part in dir_skips for part in parts[:-1]):\n"
        "            continue",
        "scan_tree_asks_the_single_predicate",
    ),
    (
        "④ 打包脚本里手抄顶层白名单（漂移的老路）",
        PACK_UPDATE_PS1,
        "$Files = @(git -c core.quotepath=false ls-files)",
        "$TopLevels = @('src', 'library')\n"
        "$Files = @(git -c core.quotepath=false ls-files)",
        "shares_the_product_predicate",
    ),
    (
        "⑤ 删除清单退回「只看上一版清单」（上一版的删除清单不再参与）",
        FULL_PACK,
        "        if sibling.is_file():\n"
        "            shipped.update(read_release_file_list(sibling))",
        "        if False:  # 注入：不看上一版的删除清单\n"
        "            shipped.update(read_release_file_list(sibling))",
        "unions_both_packers or removed_list_is_cumulative",
    ),
    (
        "⑥ 删除清单只按小发版清单算（完整包发过的那些不再参与）",
        FULL_PACK,
        "            full_manifest=Path(baseline_path) if baseline_path is not None else None,",
        "            full_manifest=None,  # 注入：不看完整包清单",
        "removed_list_is_cumulative",
    ),
]

LINES: list[str] = []
RESULTS: dict = {"cases": []}


def log(text: str = "") -> None:
    print(text, flush=True)
    LINES.append(text)


def _encoding(relative: str) -> str:
    if relative.endswith(".ps1") or relative.endswith(".bat"):
        return "utf-8-sig"          # .ps1 必须带 BOM（本仓硬约定）
    return "utf-8"


def read_text(relative: str) -> str:
    """按**字节**读再解码（不用 `Path.read_text`）。

    为什么：文本模式读会把 CRLF 归一成 LF、写回时再按平台换回 CRLF——文件里只要有一处
    混行（例如编辑器只改了其中几行），一次往返就把整份文件的换行统一了，于是「复原复核」
    报假红（实测踩到过）。判据要的是**逐字节复原**，所以这里不经过换行归一化。
    """
    return (ROOT / relative).read_bytes().decode(_encoding(relative))


def write_text(relative: str, text: str) -> None:
    (ROOT / relative).write_bytes(text.encode(_encoding(relative)))


def newline_of(text: str) -> str:
    """目标文件的换行风格（探针里的锚点一律以 LF 书写，注入前要适配）。"""
    return "\r\n" if "\r\n" in text else "\n"


def adapt(text: str, newline: str) -> str:
    """把 LF 书写的锚点 / 注入文本适配到目标文件的换行风格。

    为什么需要它：读侧是**逐字节保真**的（见 `read_text`），所以 CRLF 文件里的
    多行锚点在文本里带 `\\r\\n`，直接拿 LF 写的锚点去匹配会一条都命中不了。
    """
    return text.replace("\n", newline) if newline != "\n" else text


def sha256(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def run_tests(keyword: str) -> tuple[bool, str]:
    command = [sys.executable, "-m", "pytest",
               "tests/test_pack_update.py", "tests/test_full_pack.py",
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
    log("# 判据强度探针：「产品文件判据单源」（工单 update-orphan-files/01）")
    log(f"  仓库：{ROOT}")
    log("  判据：**每一条注入都必须转红**（有绿的 = 那条守卫是摆设）")
    log("")

    # 前置：所有被改的文件必须是干净状态（探针被强杀时 finally 跑不到，
    # 目标文件会停在注入态——那时后面每条都报「锚点失效」，看起来像探针写错了）。
    targets = sorted({case[1] for case in CASES})
    missing: list[str] = []
    for name, path, old, _new, _kw in CASES:
        text = read_text(path)
        if text.count(adapt(old, newline_of(text))) != 1:
            missing.append(f"{name}（{path}）")
    if missing:
        log("**拒绝开跑**：目标文件不是干净状态（可能上一轮探针被强杀、没来得及复原）。")
        for item in missing:
            log(f"  · 锚点不在：{item}")
        log("  修法：`git checkout -- " + " ".join(targets) + "` 之后重跑本探针。")
        RESULTS["preflight_missing"] = missing
        RESULTS["verdict"] = "FAIL"
        return 2

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
