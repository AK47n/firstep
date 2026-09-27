"""反证探针（工单 backlog-closeout/01）：撤掉界面那三处修 → 新判据必须**点名红**。

三段（每段一类机制，逐条声明必须红 + 与实得 FAILED 对账 + 复原 sha256 逐字节）：

- **A 撤「6.2 GB」那句**：界面改回「不用重下 6.2 GB 完整包」（已下线的 7z 渠道体量）
- **B 撤「5 GB+」那句**：资料库那行改回「5 GB+」（真值约 0.7 GB；5 GB 是"故意不进包的
  第三方安装件"，不是资料库）
- **C 撤「否定式」写法**：把「不用装 7-Zip」改成「需要装 7-Zip」——`dead_channel_hits`
  的否定式回看那半也要在新扫描面上真的活着

三段都打**同一条判据**（`tests/test_onboarding_docs.py::test_ui_download_size_claims_are_live_shape`），
所以每段的"声明必须红"都是它——对账仍然照做：多出来的红如实打印、不据此判 PASS。

形状照 `.scratch/record-write-hardening/probe-01-red.py`：逐条声明 + 对账 + 每段复原
sha256 逐字节相同（**字节往返**，不用文本模式）。多行锚点按**文件实际行尾**拼。

用法：`python .scratch/backlog-closeout/probe-01-red.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
UI = ROOT / "src" / "contest_generator" / "static" / "index.html"
CASES = "tests/test_onboarding_docs.py"
GUARD = "tests/test_onboarding_docs.py::test_ui_download_size_claims_are_live_shape"

STALE_SIX_GB = "不用重下完整包（约 800 MB）"
RETIRED_SIX_GB = "不用重下 6.2 GB 完整包"
FRESH_LIBRARY = "电赛资料库（<code>sources\\materials</code>，约 0.7 GB / 5000+ 个文件）"
STALE_LIBRARY = "电赛资料库（<code>sources\\materials</code>，5 GB+）"
NEGATED_TOOL = "不用装 7-Zip"
POSITIVE_TOOL = "需要装 7-Zip"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tests() -> tuple[set[str], str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", CASES, "-q", "--tb=no", "-rf"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    failed = set(re.findall(r"^FAILED (\S+)", out, flags=re.MULTILINE))
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return failed, tail


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raw = UI.read_bytes()
    source = raw.decode("utf-8")
    print(f"# 被撤的源码：{UI.relative_to(ROOT).as_posix()} sha256={sha256(UI)}")
    print(f"# 判据文件：{CASES} sha256={sha256(ROOT / CASES)}")
    print()
    segments = [
        ("A 撤「6.2 GB 完整包」那句", STALE_SIX_GB, RETIRED_SIX_GB),
        ("B 撤「5 GB+ 资料库」那句", FRESH_LIBRARY, STALE_LIBRARY),
        ("C 撤「不用装 7-Zip」的否定式", NEGATED_TOOL, POSITIVE_TOOL),
    ]
    verdicts: list[bool] = []
    for name, old, new in segments:
        print(f"== {name} ==")
        if old not in source:
            print(f"   [!] 锚点失效（源码里找不到：{old!r}）——探针该修了\n")
            verdicts.append(False)
            continue
        try:
            UI.write_bytes(source.replace(old, new, 1).encode("utf-8"))
            failed, tail = run_tests()
        finally:
            UI.write_bytes(raw)
        restored = sha256(UI) == hashlib.sha256(raw).hexdigest()
        declared = {GUARD}
        missing = declared - failed
        extra = failed - declared
        print(f"   声明必须红：{sorted(declared)}")
        print(f"   实得 FAILED：{sorted(failed) if failed else '（无）'}")
        print(f"   pytest 尾行：{tail}")
        print(f"   复原 sha256 逐字节相同：{restored}")
        if missing:
            print(f"   [x] 声明必须红的没红：{sorted(missing)}")
        if extra:
            print(f"   [x] 多出来的红（如实打印，不据此判 PASS）：{sorted(extra)}")
        verdicts.append(not missing and not extra and restored)
        print()

    print("== 复原后必须回绿 ==")
    green_failed, green_tail = run_tests()
    print(f"   实得 FAILED：{sorted(green_failed) if green_failed else '（无）'}")
    print(f"   pytest 尾行：{green_tail}")
    print()
    ok = all(verdicts) and not green_failed
    print("结论：" + ("PASS（三段反证全成立）" if ok else "不成立，见上"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
