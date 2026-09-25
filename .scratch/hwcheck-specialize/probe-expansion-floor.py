# -*- coding: utf-8 -*-
"""工单 03 的反证：**撤掉一条本轮专精化的配方**，扩张地板断言必须红。

判据（spec「反证要求」①）：把 `sht30` 那两格（stm32 / mspm0）从
`library/hwcheck_recipes.json` 里临时拿掉 → `tests/test_hwcheck_recipe.py` 的
扩张地板（逐格 + 条数）必须**当场红**；拿回来 → 又全绿。两条读数都要有，
否则"地板钉住了这一格"只是一句承诺。

回滚纪律与 `probe-sample-decouple.py` 同款：**只在文件仍逐字节等于我们写进去的那份时**
才写回原字节；窗口期内被外力改动就不碰它并大声报错（宁可不还原，也不回滚别人的改动）。
退出码 0 = 反证成立（撤掉必红 + 还原必绿 + 文件逐字节还原）。

用法：`py -3 .scratch/hwcheck-specialize/probe-expansion-floor.py`
读数先落盘 `probe-expansion-floor.txt` 再打印。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECIPES = REPO / "library" / "hwcheck_recipes.json"
VICTIM = "sht30"
LINES: list[str] = ["=== 工单 03 反证：撤掉一条新配方 → 扩张地板必须红 ===", ""]
FAILURES: list[str] = []
FLOOR = "tests/test_hwcheck_recipe.py"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_floor() -> tuple[int, str, str]:
    """跑扩张地板用例 → (退出码, 末行, 全输出)。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", FLOOR, "-q", "-k", "expansion"],
        cwd=str(REPO), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    out = proc.stdout or ""
    last = [ln.strip() for ln in out.splitlines() if ln.strip()][-1:]
    return proc.returncode, (last[0] if last else "(无输出)"), out


original = RECIPES.read_bytes()
before = _digest(original)
document = json.loads(original.decode("utf-8"))
assert VICTIM in document, f"{VICTIM} 不在配方文件里——这条反证的前提变了"

LINES.append(f"0) 前置：配方文件 sha256 = {before[:16]}…；"
             f"被撤的格 = {VICTIM} × {sorted(document[VICTIM])}")
rc_before, tail_before, _out_before = _run_floor()
LINES.append(f"1) 撤之前：地板 rc={rc_before}（{tail_before[:110]}）")
if rc_before != 0:
    FAILURES.append("撤之前地板就已经红了——前置不干净，先修好再跑反证")
LINES.append("")

patched_bytes: bytes | None = None
restored = False
try:
    victim = document.pop(VICTIM)
    patched_bytes = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    RECIPES.write_bytes(patched_bytes)
    rc_after, tail_after, out_after = _run_floor()
    LINES.append(f"2) 撤掉 {VICTIM} 之后：地板 rc={rc_after}（{tail_after[:110]}）")
    # 判据不止"非零"：红的**原因**必须点到被撤的那一格（否则可能是别处坏了而"假红"）
    named = any(mark in out_after for mark in (
        f"({VICTIM},", f"'{VICTIM}'", f"{VICTIM} ×", f"{VICTIM}×"))
    if rc_after == 0:
        FAILURES.append("撤掉配方后地板仍然绿——地板没钉住这一格")
    elif not named:
        FAILURES.append("地板红了，但红因里没点名被撤的那一格——这条红不一定是它")
    LINES.append("   红因里点名了被撤的那一格吗："
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
    LINES.append(f"3) 回滚：{'✓ 按原字节写回，sha256 与前置一致' if restored else '✗ 未回滚或回滚不保真'}"
                 f"（{_digest(RECIPES.read_bytes())[:16]}…）")

if restored:
    rc_final, tail_final, out_final = _run_floor()
    LINES.append(f"4) 拿回来之后：地板 rc={rc_final}（{tail_final[:110]}）")
    if rc_final != 0:
        FAILURES.append("还原后地板仍然红——配方文件没回到原状")

verdict = not FAILURES
LINES.append("")
LINES.append("结论：" + ("✓ 反证成立——撤掉必红、拿回来必绿、文件逐字节还原"
                        if verdict else "✗ 反证不成立：" + "；".join(FAILURES)))

text = "\n".join(LINES) + "\n"
(REPO / ".scratch" / "hwcheck-specialize" / "probe-expansion-floor.txt").write_text(
    text, encoding="utf-8")
print(text)
raise SystemExit(0 if verdict else 1)
