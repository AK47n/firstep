# -*- coding: utf-8 -*-
"""工单 08 反证 C：把 `hx711 × stm32` 的探头**改回写错的样子**（采样存进 `r` 而不是 `raw`），
新立的守卫 `test_expansion_cells_that_declare_locals_actually_write_them` 必须红。

为什么单独立一条反证：这条缺陷的性质是「编译过、校验过、探头判 OK，**读数恒 0**」——
最像"测过了"的假绿。撤格反证抓不到它（配方在、格数在），只有这条守卫能。

窗口期纪律同 `probe-expansion-floor.py`：只在文件仍逐字节等于我们写进去的那份时才写回原字节。
"""
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RECIPES = REPO / "library" / "hwcheck_recipes.json"
OUT = REPO / ".scratch" / "hwcheck-specialize" / "probe-locals-guard-08.txt"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOOD = "raw = hx711_read_raw()"
BAD = "r = hx711_read_raw()"
LINES = ["=== 反证 C：把 hx711 × stm32 的探头改回写错的样子 → 局部变量守卫必须红 ===", ""]
FAILURES: list[str] = []

original = RECIPES.read_bytes()
_before = hashlib.sha256(original).hexdigest()
text = original.decode("utf-8")
assert text.count(GOOD) >= 1, "配方里找不到写对的探头——反证前提变了"

rc0 = subprocess_rc = None
import subprocess  # noqa: E402


def run_guard():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_hwcheck_recipe.py", "-q",
         "-k", "declare_locals"],
        cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = proc.stdout or ""
    last = [ln.strip() for ln in out.splitlines() if ln.strip()][-1:]
    return proc.returncode, (last[0] if last else "(无输出)"), out


rc_before, tail_before, _ = run_guard()
LINES.append(f"0) 前置：sha256 = {_before[:16]}…；判据 = 每格声明的 locals 必须真被写过")
LINES.append(f"1) 改之前：守卫 rc={rc_before}（{tail_before[:100]}）")
if rc_before != 0:
    FAILURES.append("改之前守卫就已经红了——前置不干净")

patched: bytes | None = None
restored = False
try:
    patched = text.replace(GOOD, BAD, 1).encode("utf-8")
    RECIPES.write_bytes(patched)
    rc_after, tail_after, out_after = run_guard()
    LINES.append(f"2) 改成 `{BAD}`（采样不再落进 raw）之后：守卫 rc={rc_after}"
                 f"（{tail_after[:100]}）")
    named = "raw" in out_after and "hx711" in out_after
    if rc_after == 0:
        FAILURES.append("写错之后守卫仍然绿——这条守卫没钉住「locals 真被写」")
    elif not named:
        FAILURES.append("守卫红了，但红因没点名 raw / hx711——这条红不一定是它")
    LINES.append("   红因里点名了 raw 与 hx711 吗："
                 f"{'✓ 点名了' if named else '✗ 没点名'}")
finally:
    if patched is not None and RECIPES.read_bytes() == patched:
        RECIPES.write_bytes(original)
        restored = hashlib.sha256(RECIPES.read_bytes()).hexdigest() == _before
    else:
        FAILURES.append("配方文件在反证窗口期内被外力改动，未回滚")
    LINES.append("")
    LINES.append(f"3) 回滚：{'✓ 按原字节写回，sha256 一致' if restored else '✗ 未回滚或回滚不保真'}")

if restored:
    rc_final, tail_final, _ = run_guard()
    LINES.append(f"4) 改回之后：守卫 rc={rc_final}（{tail_final[:100]}）")
    if rc_final != 0:
        FAILURES.append("改回之后守卫仍然红——配方没回到原状")

verdict = not FAILURES
LINES.append("")
LINES.append("结论：" + ("✓ 反证成立——写错必红、改回必绿、文件逐字节还原"
                        if verdict else "✗ 反证不成立：" + "；".join(FAILURES)))
text_out = "\n".join(LINES) + "\n"
OUT.write_text(text_out, encoding="utf-8")
print(text_out)
raise SystemExit(0 if verdict else 1)
