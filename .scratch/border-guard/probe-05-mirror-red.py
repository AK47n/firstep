r"""反证探针：**跨语言镜像守卫自己判得红吗**（工单 border-guard/01）。

为什么要有它：`tests/test_border_register_mirror.py` 是"判据的判据"——它要是永远绿，
等于给"两侧同源"这句话盖了个假章。照本仓惯例（08 账第 3 条：**新腿要自证**），
往 JS 侧真注入漂移、跑那条守卫、必须红；复原后必须逐字节相同、复跑必须绿。

按文件实际换行算字节（`index.html` 是 CRLF、`tests/js/**` 是 LF——那轮踩过两次的坑）。
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from probe_lib import GUARD, ROOT, inject_and_check, sha256  # noqa: E402

PY = sys.executable
TEST = "tests/test_border_register_mirror.py"

# (名字, 锚点, 替换成什么) —— 每一处都对应镜子里的一条口径
INJECTIONS = [
    ("整圈完整框正则：去掉前置断言",
     r"body.matchAll(/(?<![\w-])border:\s*([^;]+);/g)",
     r"body.matchAll(/border:\s*([^;]+);/g)"),
    ("DEAD_BORDER：多算一个撤框取值",
     'const DEAD_BORDER = ["none", "0"];',
     'const DEAD_BORDER = ["none", "0", "transparent"];'),
    ("transparent 判定：换成宽松写法",
     r"const transparent = /(?:^|\s)transparent(?:\s|$)/.test(e.value);",
     r"const transparent = e.value.includes('transparent');"),
    ("剥前导注释：不剥了",
     r'return sel.replace(/^(\/\*[\s\S]*?\*\/\s*)+/, "").trim();',
     r"return sel.trim();"),
    ("渲染方内联框正则（02 单那条）：把取值终止符收窄成只认分号",
     r"""raw.matchAll(/(?<![\w-])border\s*:\s*([^;"]+)|\.border\s*=\s*["\u0027]([^"\u0027]+)["\u0027]/g)""",
     r'raw.matchAll(/(?<![\w-])border:\s*([^;]+);/g)'),
]


def run_pytest() -> tuple[int, str]:
    proc = subprocess.run([PY, "-m", "pytest", TEST, "-q"], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    bad = [ln for ln in out.splitlines() if ln.startswith("FAILED")]
    return proc.returncode, (bad[0].split("::")[-1] if bad else out.strip().splitlines()[-1] if out.strip() else "")


def main() -> int:
    before = sha256(GUARD)
    print(f"前置：{TEST} 在干净树上必须绿")
    code, note = run_pytest()
    print(f"  → 退出码 {code}（{note}）")
    if code != 0:
        print("干净树上就不绿——先修守卫，别往下走")
        return 1

    failures = 0
    for name, anchor, repl in INJECTIONS:
        failures += inject_and_check(GUARD, name, anchor.encode("utf-8"), repl.encode("utf-8"), run_pytest)

    after = sha256(GUARD)
    print(f"\n复原：sha256 {'逐字节相同 ✅' if before == after else '**不同 ❌**'}（{before[:12]}…）")
    code, note = run_pytest()
    print(f"复原后复跑：退出码 {code}" + ("（绿 ✅）" if code == 0 else f"（**红 ❌** {note}）"))
    if before != after or code != 0:
        failures += 1
    print(f"\n结论：{'全部按预期 ✅' if failures == 0 else f'有 {failures} 处不符预期 ❌'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
