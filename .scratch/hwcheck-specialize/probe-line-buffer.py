# -*- coding: utf-8 -*-
"""工单 04 新守卫的**反证**：把某一格的读数单位撑宽 → 行缓冲守卫必须红。

工单 04 立了一条新用例 `tests/test_hwcheck_recipe.py::
test_expansion_read_lines_fit_the_device_line_buffer`（扩张格的每条读数行都得放得进板上
的 `hwcheck_line[128]`）。spec 的纪律是「每一条新守卫都配一次反证」，否则守卫是不是
真的在看东西没人知道。判据三条：

  0) 前置：**改之前**这条用例必须绿（不干净就先修，别拿脏前提跑反证）；
  1) 把被点名那一格的单位**撑宽**（追加一段中文）→ 该用例必须**红**，而且红因里
     点名了被撑宽的那一格（红因对不上就可能是别处坏了）；
  2) 按原字节回滚 → 用例必须回到绿，且配方文件 sha256 与前置一致。

换行纪律：配方文件在盘上是 **CRLF**，改写与回滚都按原形态（窗口期内被强杀也不会
留下 LF 半成品）。
退出码 0 = 反证成立。
用法：`py -3 .scratch/hwcheck-specialize/probe-line-buffer.py`
读数先落盘 `probe-line-buffer.txt` 再打印。
"""
import hashlib
import json
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECIPES = REPO / "library" / "hwcheck_recipes.json"
VICTIM = "bmp180"
PADDING = "（这段是反证用的填充文字，只为一件事：把这一行撑过板上的行缓冲上限）"
LINES: list[str] = ["=== 工单 04 反证：把读数单位撑宽 → 行缓冲守卫必须红 ===", ""]
FAILURES: list[str] = []
CASE = "tests/test_hwcheck_recipe.py"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_guard() -> tuple[int, str, str]:
    """跑行缓冲守卫 → (退出码, 末行, 全输出)。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", CASE, "-q", "-k", "line_buffer"],
        cwd=str(REPO), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    out = proc.stdout or ""
    last = [ln.strip() for ln in out.splitlines() if ln.strip()][-1:]
    return proc.returncode, (last[0] if last else "(无输出)"), out


original = RECIPES.read_bytes()
before = _digest(original)
document = json.loads(original.decode("utf-8"), object_pairs_hook=OrderedDict)
assert VICTIM in document, f"{VICTIM} 不在配方文件里——这条反证的前提变了"
_newline = "\r\n" if "\r\n" in original.decode("utf-8") else "\n"

LINES.append(f"0) 前置：配方文件 sha256 = {before[:16]}…；被撑宽的格 = "
             f"{VICTIM} × {sorted(document[VICTIM])}")
rc_before, tail_before, _ = _run_guard()
LINES.append(f"   撑宽之前：守卫 rc={rc_before}（{tail_before[:110]}）")
if rc_before != 0:
    FAILURES.append("撑宽之前守卫就已经红了——前置不干净，先修好再跑反证")
LINES.append("")

patched_bytes: bytes | None = None
restored = False
try:
    widened: list[str] = []
    for platform, section in document[VICTIM].items():
        items = section.get("read", {}).get("items", [])
        for item in items:
            item["unit"] = item["unit"] + PADDING
            widened.append(f"{platform}:{item['expression']}")
    text = json.dumps(document, ensure_ascii=False, indent=2).replace("\n", _newline)
    patched_bytes = (text + _newline).encode("utf-8")
    RECIPES.write_bytes(patched_bytes)

    rc_after, tail_after, out_after = _run_guard()
    LINES.append(f"1) 把 {VICTIM} 两平台 {len(widened)} 条读数的单位各撑宽 "
                 f"{len(PADDING)} 字之后：守卫 rc={rc_after}（{tail_after[:110]}）")
    named = any(mark in out_after for mark in
                (f"{VICTIM} × stm32", f"{VICTIM} × mspm0",
                 f"{VICTIM}-stm32", f"{VICTIM}-mspm0"))
    LINES.append(f"   红因里点名了被撑宽的那一格吗：{'✓ 点名了' if named else '✗ 没点名'}")
    if rc_after == 0:
        FAILURES.append("把单位撑宽后守卫仍然绿——这条守卫没在看行宽")
    elif not named:
        FAILURES.append("守卫红了，但红因里没点名被撑宽的那一格——这条红不一定是它")
finally:
    current = RECIPES.read_bytes()
    if patched_bytes is not None and current == patched_bytes:
        RECIPES.write_bytes(original)
        restored = _digest(RECIPES.read_bytes()) == before
    else:
        FAILURES.append("配方文件在反证窗口期内被外力改动，未回滚（不覆盖别人的改动）")
    LINES.append("")
    LINES.append(f"2) 回滚：{'✓ 按原字节写回，sha256 与前置一致' if restored else '✗ 未回滚'}"
                 f"（{_digest(RECIPES.read_bytes())[:16]}…）")

if restored:
    rc_final, tail_final, _ = _run_guard()
    LINES.append(f"3) 拿回来之后：守卫 rc={rc_final}（{tail_final[:110]}）")
    if rc_final != 0:
        FAILURES.append("还原后守卫仍然红——配方文件没回到原状")

verdict = not FAILURES
LINES.append("")
LINES.append("结论：" + ("✓ 反证成立——撑宽必红且红因点名该格、拿回来必绿、文件逐字节还原"
                        if verdict else "✗ 反证不成立：" + "；".join(FAILURES)))

out_text = "\n".join(LINES) + "\n"
(REPO / ".scratch" / "hwcheck-specialize" / "probe-line-buffer.txt").write_text(
    out_text, encoding="utf-8")
print(out_text)
raise SystemExit(0 if verdict else 1)
