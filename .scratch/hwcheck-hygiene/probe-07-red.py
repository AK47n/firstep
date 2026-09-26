"""probe-07-red.py — 工单 hwcheck-hygiene/07 的**判据强度反证**（三处注入，各自跑完复原）。

* **A 自述整句撤掉**（= 本单开单前的老形态）→ pytest 那支守卫（载荷两个出口）必须红。
* **B 自述还在，但把"只验第一路"说成"每一路都验过了"** → 判据的**第二半**
  （"不许把只验一路说成全验了"）必须红——只有 A 的话，把断言写成"只要含『第一路』"
  就够；B 证明那半条也在真跑。
* **C 自述撤掉 → 真浏览器用例必须红**：这是评审整改加的一条——工单要的是"页面渲染出来的
  文本"，而 pytest 只能看到服务端**载荷**；`tests/browser/hwcheck.spec.mjs` 那条读的是
  真 DOM 文本，它红了才证明"载荷 → 页面"这最后一跳也在判据面里。

三处都改**数据面**（`library/hwcheck_recipes.json`），不改判据：判据强度是"撤掉产品侧
那句实话，用例红不红"，改判据本身证明不了任何事。

⚠ 这个文件在盘上是 **LF**（`core.autocrlf=true`，checkout 出来仍是 LF），且
`json.dump` 会把整档重排——所以一律按**字节**锚点替换，跑完逐字节复原并复核 sha256。
⚠ 跑法**分岔**：A/B 只跑那条 pytest 用例（秒级）；C 只跑 `tests/browser/hwcheck.spec.mjs`
（真浏览器 + 真后端，约 1–2 分钟），**不跑整套浏览器门禁**——那 4 分多钟里绝大部分
用例与本单无关，而反证只需要那条点名用例作答。

用法：`python .scratch/hwcheck-hygiene/probe-07-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from patch_bytes import encode_anchor, newline_of  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
RECIPES = REPO / "library/hwcheck_recipes.json"
OUT = pathlib.Path(__file__).resolve().parent / "probe-07-red.txt"

PYTEST_NODE = ("tests/test_hwcheck_recipe.py"
               "::test_every_multi_instance_recipe_cell_discloses_it_only_tests_the_first_channel")
BROWSER_SPEC = "tests/browser/hwcheck.spec.mjs"

ANSI = re.compile(r"\x1b\[[0-9;]*m")

# ---- A：把 led × stm32 那句自述整条撤掉（老形态） ---------------------------------
A_NEW = ("多实例只验第一路：工程里配了 4 路 LED 时（生成器覆写 led_instances.h，"
         "通道数会大于 1），检测程序这一趟只驱动第一路（LED_RED）——通道数不是"
         "「每一路都验过」的意思，另外几路这一趟一个动作都没有。")
A_OLD = ""

# ---- B：自述还在，但结论反过来（把"只验一路"说成"全验了"） -------------------------
B_OLD = "所以本件只读首通道；多实例只验第一路（检测程序这一趟只驱动第一路，另外几路一个动作都没有）。"
B_NEW = "所以本件只读首通道；多实例每一路都验过了，放心开始。"

CASES = [
    ("A 自述整句撤掉（老形态）→ pytest 守卫", A_NEW, A_OLD, 1, "pytest"),
    ("B 自述反过来（说成全验了）→ pytest 守卫", B_OLD, B_NEW, 2, "pytest"),
    ("C 自述撤掉 → 真浏览器用例", A_NEW, A_OLD, 1, "browser"),
]

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(cmd: list[str], timeout: int) -> tuple[int, str]:
    proc = subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout)
    body = ANSI.sub("", (proc.stdout or "") + (proc.stderr or ""))
    return proc.returncode, body.replace("\r\n", "\n").replace("\r", "\n")


def failed_tests(out: str) -> set[str]:
    """node 的 spec reporter 与 pytest 的失败行都收（两行的格式不同，别只按一支写）。

    pytest：`FAILED tests/x.py::test_y`
    node：`✖ 用例名 (1234ms)` —— 名字里可能带空格、方括号、冒号，
    所以取 ✖ 之后、去掉结尾的耗时括号当整名（**别按 `::` 切**）。
    """
    found = set()
    for ln in out.splitlines():
        stripped = ln.strip()
        m = re.match(r"FAILED\s+(\S+)", stripped)
        if m:
            found.add(m.group(1).replace("\\", "/"))
            continue
        m = re.match(r"[✖×]\s+(.+?)(?:\s+\(\d+(?:\.\d+)?ms\))?$", stripped)
        if m and not stripped.startswith("✖ failing"):
            found.add(m.group(1).strip())
    return found


def summary(out: str) -> str:
    for ln in reversed(out.splitlines()):
        if re.search(r"\d+ (passed|failed|error)", ln) or ln.strip().startswith("ℹ fail"):
            return ln.strip()
    return "（没读到摘要行）"


def write_and_print(code: int) -> None:
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    print(f"\n读数已落盘：{OUT.relative_to(REPO).as_posix()}")


def main() -> int:
    original_blob = RECIPES.read_bytes()
    digest = sha256(original_blob)
    say(f"目标：{RECIPES.relative_to(REPO).as_posix()}  前置 sha256：{digest}  "
        f"换行：{'CRLF' if newline_of(original_blob) == chr(13) + chr(10) else 'LF'}")
    say(f"判据用例：pytest → {PYTEST_NODE}")
    say(f"判据用例：browser → {BROWSER_SPEC}（「专精小节：选上 led…」那条）")

    for label, new_text, _old, want, _runner in CASES:
        hits = original_blob.count(encode_anchor(new_text, original_blob))
        if hits != want:
            say(f"✗ 前置检查不通过：{label} 的锚点命中 {hits} 次（应为 {want}）"
                f"——未改动任何字节")
            write_and_print(1)
            return 1
    say("前置检查：三处新形态锚点各命中预期次数 ✓")

    all_ok = True
    for label, new_text, old_text, want, runner in CASES:
        say("")
        say(f"=== {label} ===")
        original = RECIPES.read_bytes()
        try:
            RECIPES.write_bytes(original.replace(
                encode_anchor(new_text, original), encode_anchor(old_text, original), want))
            say(f"注入：{want} 处；注入后 sha256：{sha256(RECIPES.read_bytes())}"
                f"（应不等于前置值）")
            if runner == "pytest":
                code, out = run([sys.executable, "-m", "pytest", "-q", PYTEST_NODE], 300)
            else:
                code, out = run(["node", "--test", "--test-concurrency=1", BROWSER_SPEC], 900)
            failed = failed_tests(out)
            say(f"注入态读数：{summary(out)}  退出码：{code}")
            say(f"实得红（{len(failed)} 条）：")
            for node in sorted(failed):
                say(f"  · {node}")
            if runner == "pytest":
                ok = code != 0 and PYTEST_NODE.replace("\\", "/") in failed
            else:
                # 浏览器用例只跑一个 spec 文件，红的是哪一条读**堆栈里的行号**
                # （`test at tests\browser\hwcheck.spec.mjs:628:10`）——按用例名猜
                # 会在改名时静默失效，行号是本条判据更硬的锚。
                ok = code != 0 and bool(
                    re.search(r"test at " + re.escape(BROWSER_SPEC.replace("/", "\\"))
                              + r":\d+:", out))
            if not ok:
                # 自证一下"红在哪"：把**原始输出**落一份旁证，免得"解析器没认出来"
                # 被读成"判据没强度"（这个探针第一版就在这里栽过——`ℹ fail 1` 在、
                # 失败行却一条没抓到，是解析面写窄了，不是浏览器用例没红）。
                dump = OUT.with_name(f"probe-07-raw-{'pytest' if runner == 'pytest' else 'browser'}"
                                     f"-injected.txt")
                dump.write_text(out, encoding="utf-8", newline="")
                say(f"⚠ 未按预期认出红——该跑的原始输出已落盘旁证：{dump.name}")
            say("声明的用例红了 ✓" if ok else "✗ 声明要红的用例没红——判据挡不住这一处")
        finally:
            RECIPES.write_bytes(original)
        after = sha256(RECIPES.read_bytes())
        say(f"复原 sha256：{after}  逐字节相同：{'✓' if after == digest else '✗'}")
        if runner == "pytest":
            code2, out2 = run([sys.executable, "-m", "pytest", "-q", PYTEST_NODE], 300)
        else:
            code2, out2 = run(["node", "--test", "--test-concurrency=1", BROWSER_SPEC], 900)
        say(f"复原态读数：{summary(out2)}  退出码：{code2}  回绿：{'✓' if code2 == 0 else '✗'}")
        all_ok = all_ok and ok and after == digest and code2 == 0

    say("")
    say("结论：" + ("PASS —— 载荷侧与页面侧的判据都有强度，且探针未留下任何改动"
                    if all_ok else "FAIL"))
    write_and_print(0 if all_ok else 1)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
