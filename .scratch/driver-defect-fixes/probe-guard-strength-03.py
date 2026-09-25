# -*- coding: utf-8 -*-
"""判据强度反证（工单 `driver-defect-fixes/03`）：把修复撤掉 → 新用例必须变红。

四条注入，逐条独立跑（注入 → 跑目标用例 → **逐字节复原** → 复核 sha256）：

  A. **判据①（窗口够长）**：把窗口从 2 × 转换周期改成 1/10 个周期（20ms 的老病）
     ⇒「窗口 ≥ 一个转换周期」必须红；
  B. **判据②（不许拿 0 冒充）**：把 mspm0 的 `return HX711_TIMEOUT_SENTINEL;`
     改回 `return 0;` ⇒ 必须红；
  C. **判据②（哨兵落在合法域外）**：把哨兵值改成 `0x800000`（= 空秤零点，24 位
     合法域**之内**）⇒ 必须红；
  D. **判据③（双平台一致）**：只改 stm32 的轮询步长 ⇒ 跨文件对拍必须红。

纪律（本仓既有）：探针**会真改库内文件**——**别和测试套件同时跑**；读写走**二进制**
（逐字节保真）；**前置干净性检查**：文件不是「已修」形态就当场退出。

用法：`py -3 .scratch/driver-defect-fixes/probe-guard-strength-03.py`
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REPORT = REPO / ".scratch" / "driver-defect-fixes" / "probe-guard-strength-03.txt"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HX_MSPM0 = REPO / "library" / "modules" / "hx711" / "code" / "hx711.c"
HX_MSPM0_H = REPO / "library" / "modules" / "hx711" / "code" / "hx711.h"
HX_STM32 = REPO / "library" / "modules" / "hx711" / "code" / "hx711_stm32.c"

CASE_WINDOW = "tests/test_module_hx711.py::test_hx711_ready_window_covers_a_conversion_period"
CASE_ZERO = "tests/test_module_hx711.py::test_hx711_timeout_is_never_disguised_as_a_zero_reading"
CASE_PARITY = "tests/test_module_hx711.py::test_hx711_window_and_sentinel_are_identical_on_both_platforms"
CASE_TARE = "tests/test_module_hx711.py::test_hx711_tare_never_stores_a_timeout_as_the_zero_point"

INJECTIONS = [
    (
        "A：窗口缩回 1/10 个转换周期（老病：20ms < 100ms）",
        "判据①（窗口 ≥ 一个转换周期）",
        HX_MSPM0,
        b"#define HX711_READY_TIMEOUT_MS    (HX711_CONV_PERIOD_MS * 2u)",
        b"#define HX711_READY_TIMEOUT_MS    (HX711_CONV_PERIOD_MS / 10u)",
        CASE_WINDOW,
    ),
    (
        "B：超时又拿 0 冒充读数",
        "判据②（不许 return 0，必须报哨兵值）",
        HX_MSPM0,
        b"            return HX711_TIMEOUT_SENTINEL;",
        b"            return 0;",
        CASE_ZERO,
    ),
    (
        "C：哨兵值落回 24 位合法域内（0x800000 = 空秤零点）",
        "判据②（哨兵必须 > 0xFFFFFF）",
        HX_MSPM0_H,
        b"#define HX711_TIMEOUT_SENTINEL 0xFFFFFFFFu",
        b"#define HX711_TIMEOUT_SENTINEL 0x800000u",
        CASE_ZERO,
    ),
    (
        "D：只改 stm32 的轮询步长（两平台悄悄分叉）",
        "判据③（双平台常量对拍）",
        HX_STM32,
        b"#define HX711_POLL_US             10u",
        b"#define HX711_POLL_US             5u",
        CASE_PARITY,
    ),
    (
        "E：去皮又把可能超时的读直接存成零点（评审抓出来的那处真缺陷）",
        "判据②尾巴（去皮的赋值必须过哨兵判断）",
        HX_MSPM0,
        b"    uint32_t raw = hx711_read_raw();\r\n"
        b"    if (raw != HX711_TIMEOUT_SENTINEL) {\r\n"
        b"        s_tare = raw;\r\n"
        b"    }",
        b"    s_tare = hx711_read_raw();",
        CASE_TARE,
    ),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_case(node: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "--no-header", "-p", "no:cacheprovider", "-rf"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    text = proc.stdout or ""
    reds = [ln.split("::")[-1].split(" ")[0] for ln in text.splitlines() if ln.startswith("FAILED ")]
    tail = text.strip().splitlines()
    summary = tail[-1] if tail else "(无输出)"
    return proc.returncode == 0, f"{summary}（{'红了：' + '、'.join(reds) if reds else '无红'}）"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPORT))
    args = parser.parse_args()
    out_path = Path(args.out)

    paths = (HX_MSPM0, HX_MSPM0_H, HX_STM32)
    originals = {path: path.read_bytes() for path in paths}
    digests = {path: sha256(data) for path, data in originals.items()}
    rows: list[str] = ["=== 判据强度反证：driver-defect-fixes/03（hx711 就绪窗口 + 0 的歧义）==="]
    for path, digest in digests.items():
        rows.append(f"{path.relative_to(REPO)} sha256 = {digest}")
    rows.append("")

    if b"HX711_READY_TIMEOUT_MS" not in originals[HX_MSPM0] or \
            b"HX711_TIMEOUT_SENTINEL 0xFFFFFFFFu" not in originals[HX_MSPM0_H]:
        rows.append("✗ 前置干净性检查失败：文件不是「已修」形态——上一次探针可能被强杀，"
                    "先 `git checkout -- <文件>` 复原再跑。")
        out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        print(rows[-1])
        return 2

    # 对照：未注入时四条目标用例都应绿（只跑一次全部）
    control = subprocess.run(
        [sys.executable, "-m", "pytest", CASE_WINDOW, CASE_ZERO, CASE_PARITY,
         "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    tail = (control.stdout or "").strip().splitlines()
    rows.append(f"[对照] 未注入：{'PASS' if control.returncode == 0 else 'FAIL'}  —— "
                f"{tail[-1] if tail else '(无输出)'}")
    rows.append("")

    failures = 0
    try:
        for name, criterion, path, src, dst, node in INJECTIONS:
            original = originals[path]
            assert original.count(src) == 1, f"注入锚点在原文里出现 {original.count(src)} 次：{name}"
            path.write_bytes(original.replace(src, dst))
            try:
                ok, summary = run_case(node)
            finally:
                path.write_bytes(original)
            restored = sha256(path.read_bytes()) == digests[path]
            verdict = "红（符合预期）" if not ok else "**仍然绿——判据没抓住这一条！**"
            if ok or not restored:
                failures += 1
            rows.append(f"[注入] {name}")
            rows.append(f"       目标判据：{criterion}")
            rows.append(f"       结果：{verdict}  —— {summary}")
            rows.append(f"       复原复核：sha256 {'一致' if restored else '**不一致**'}")
            rows.append("")
    finally:
        for path, data in originals.items():
            path.write_bytes(data)

    rows.append("=== 结论：" + (
        "全部符合预期（每条注入都让对应用例变红，且文件逐字节复原）" if not failures
        else f"有 {failures} 处不符"
    ) + " ===")
    out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("\n".join(rows))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
