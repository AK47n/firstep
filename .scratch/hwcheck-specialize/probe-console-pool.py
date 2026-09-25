# -*- coding: utf-8 -*-
"""工单 07 的反证 B：**撤掉共享候选池**，命令表组合守卫必须红。

判据（spec「反证要求」②的同类形态）：本批为"`|S| <= 6` 全子集零撞车"补的那个共享后备池
（`n z i 0 1 2 3`，见 `_topup_console_pool.py`）如果被撤回，新立的守卫
`tests/test_hwcheck_console.py::test_any_small_selection_of_real_recipes_builds_one_console_table`
必须**当场红**、且红因点到撞车的那一件；把池子补回来必须又全绿。

做法与 `probe-expansion-floor.py` 同款：**只在文件仍逐字节等于我们写进去的那份时**才写回
原字节（窗口期内被外力改动就不碰它并大声报错）。配方文件在盘上是 CRLF，改写按原换行形态。

用法：`py -3 .scratch/hwcheck-specialize/probe-console-pool.py`
读数先落盘 `probe-console-pool.txt` 再打印；退出码 0 = 反证成立。
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECIPES = REPO / "library" / "hwcheck_recipes.json"
OUT = REPO / ".scratch" / "hwcheck-specialize" / "probe-console-pool.txt"
GUARD = "tests/test_hwcheck_console.py"
POOL = ("n", "z", "i", "0", "1", "2", "3")
LINES: list[str] = ["=== 反证 B：撤掉共享候选池 → 命令表组合守卫必须红 ===", ""]
FAILURES: list[str] = []


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_guard() -> tuple[int, str, str]:
    # `PYTHONIOENCODING=utf-8`：本机 python 的默认 stdio 编码是 GBK，中文判据会被替换字符
    # 吃掉（"分不出来了" 变成乱码），反证就判不出"红因里点名了哪一件"。
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", GUARD, "-q", "-k", "small_selection"],
        cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env,
    )
    out = proc.stdout or ""
    last = [ln.strip() for ln in out.splitlines() if ln.strip()][-1:]
    return proc.returncode, (last[0] if last else "(无输出)"), out


original = RECIPES.read_bytes()
before = _digest(original)
document = json.loads(original.decode("utf-8"))

rc_before, tail_before, _ = _run_guard()
LINES.append(f"0) 前置：配方文件 sha256 = {before[:16]}…；守卫射程 = |S| <= 3 全子集 + 抽样到 8 件")
LINES.append(f"1) 撤之前：守卫 rc={rc_before}（{tail_before[:110]}）")
if rc_before != 0:
    FAILURES.append("撤之前守卫就已经红了——前置不干净，先修好再跑反证")
LINES.append("")

patched_bytes: bytes | None = None
restored = False
try:
    # 撤回：把每条 console 候选里的共享池字符摘掉（回到本批落地前的形态）
    removed: list[str] = []
    for slug, entry in document.items():
        if not isinstance(entry, dict):
            continue
        for platform, section in entry.items():
            console = section.get("console")
            if console is None or not console.get("candidates"):
                continue
            kept = [c for c in console["candidates"] if c not in POOL]
            if len(kept) != len(console["candidates"]):
                removed.append(f"{slug}×{platform}")
                console["candidates"] = kept
    LINES.append(f"2) 撤回共享池：动了 {len(removed)} 格（候选里摘掉 {' '.join(POOL)}）")
    newline = "\r\n" if "\r\n" in original.decode("utf-8") else "\n"
    patched_bytes = (
        json.dumps(document, ensure_ascii=False, indent=2).replace("\n", newline) + newline
    ).encode("utf-8")
    RECIPES.write_bytes(patched_bytes)
    rc_after, tail_after, out_after = _run_guard()
    LINES.append(f"3) 撤回之后：守卫 rc={rc_after}（{tail_after[:120]}）")
    named = "分不出来了" in out_after
    if rc_after == 0:
        FAILURES.append("撤回共享池后守卫仍然绿——这条守卫没钉住候选池")
    elif not named:
        FAILURES.append("守卫红了，但红因不像「字符分不出来」——这条红不一定是它")
    LINES.append("   红因里点名了候选分不出来吗："
                 f"{'✓ 点名了' if named else '✗ 没点名'}"
                 f"（{'✓ 红了且红因对' if rc_after != 0 and named else '✗ 不成立'}）")
finally:
    current = RECIPES.read_bytes()
    if patched_bytes is not None and current == patched_bytes:
        RECIPES.write_bytes(original)
        restored = _digest(RECIPES.read_bytes()) == before
    else:
        FAILURES.append("配方文件在反证窗口期内被外力改动，未回滚（不覆盖别人的改动）")
    LINES.append("")
    LINES.append(f"4) 回滚：{'✓ 按原字节写回，sha256 与前置一致' if restored else '✗ 未回滚或回滚不保真'}"
                 f"（{_digest(RECIPES.read_bytes())[:16]}…）")

if restored:
    rc_final, tail_final, _ = _run_guard()
    LINES.append(f"5) 补回来之后：守卫 rc={rc_final}（{tail_final[:110]}）")
    if rc_final != 0:
        FAILURES.append("补回共享池后守卫仍然红——配方文件没回到原状")

verdict = not FAILURES
LINES.append("")
LINES.append("结论：" + ("✓ 反证成立——撤掉必红、补回必绿、文件逐字节还原"
                        if verdict else "✗ 反证不成立：" + "；".join(FAILURES)))

text = "\n".join(LINES) + "\n"
OUT.write_text(text, encoding="utf-8")
print(text)
raise SystemExit(0 if verdict else 1)
