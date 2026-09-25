# -*- coding: utf-8 -*-
"""判据强度反证（工单 `driver-defect-fixes/01`）：把修复撤掉 → 新用例必须变红。

三条注入，逐条独立跑（每条注入 → 跑两条新用例 → **逐字节复原** → 复核 sha256）：

  A. **判据①（时间是时间）**：把超时上限的安全系数 4 换成 `/ 2`（= 只等半次序列）
     ⇒「超时上限 ≥ 一次完整转换时间 × 安全系数」必须红；
  A2. **判据①（常量挂在事实上）**：把 `JOYSTICK_ADC_SEQ_SLOTS` 从 8 改成 4
     ⇒「槽数常量与 syscfg 不符」必须红；
  B. **判据②（不许拿 0 冒充读数）**：把 `_joystick_adc_read` 里那支
     `return JOYSTICK_ADC_INVALID;` 改回 `return 0;` ⇒ 必须红。

纪律（本仓既有，见 `docs/agents/local-environment.md` 第 2 节）：
  * 探针**会真改库内文件**——**别和测试套件同时跑**；
  * 探针读写走**二进制**（逐字节保真），文本模式的 CRLF↔LF 归一会让「复原复核」假红；
  * **前置干净性检查**：文件不是「已修」形态就当场退出（上一次探针被强杀留下的注入态）。

用法：`py -3 .scratch/driver-defect-fixes/probe-guard-strength-01.py`
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "library" / "modules" / "joystick" / "code" / "joystick.c"
REPORT = REPO / ".scratch" / "driver-defect-fixes" / "probe-guard-strength-01.txt"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CASES = [
    "tests/test_module_joystick.py::test_joystick_mspm0_timeout_is_a_time_budget_not_a_spin_count",
    "tests/test_module_joystick.py::test_joystick_mspm0_timeout_never_masquerades_as_a_reading",
]

# (注入名, 目标判据, 原字节 → 注入字节)
INJECTIONS = [
    (
        "A：超时上限只等半次序列（安全系数 4 → /2）",
        "判据①（超时 ≥ 一次完整转换 × 安全系数）",
        b"#define JOYSTICK_ADC_TIMEOUT_US  (JOYSTICK_ADC_SEQ_US * 4u) /* \xe5\xae\x89\xe5\x85\xa8\xe7\xb3\xbb\xe6\x95\xb0 4 \xe2\x87\x92 4000\xc2\xb5s */",
        b"#define JOYSTICK_ADC_TIMEOUT_US  (JOYSTICK_ADC_SEQ_US / 2u)",
    ),
    (
        "A2：槽数常量脱离 syscfg 事实（8 → 4）",
        "判据①（槽数常量 == syscfg 的 endAdd-startAdd+1）",
        b"#define JOYSTICK_ADC_SEQ_SLOTS   8u",
        b"#define JOYSTICK_ADC_SEQ_SLOTS   4u",
    ),
    (
        "B：一圈都没采到时又拿 0 冒充读数",
        "判据②（不许 return 0，必须报「本次无效」）",
        b"        return JOYSTICK_ADC_INVALID; /* \xe4\xb8\x80\xe5\x9c\x88\xe9\x83\xbd\xe6\xb2\xa1\xe9\x87\x87\xe5\x88\xb0",
        b"        return 0; /* INJECTED",
    ),
    (
        "C：退出界换成字面量 50（常量算对了、循环里没等）",
        "判据①尾巴（循环的退出界必须是 JOYSTICK_ADC_TIMEOUT_US）",
        b"            if (waited_us >= JOYSTICK_ADC_TIMEOUT_US) {",
        b"            if (waited_us >= 50) {",
    ),
    (
        "D：整体退回旧形态（50 圈自旋 + 首圈 return sum/(i?i:1)）——工单点名的那条反证",
        "判据②（返回出口只许有「均值」与「本次无效」两个）",
        b"        uint32_t waited_us = 0;\r\n"
        b"        while (DL_ADC12_getStatus(ADC12_0_INST) & ADC12_STATUS_BUSY_ACTIVE) {\r\n"
        b"            if (waited_us >= JOYSTICK_ADC_TIMEOUT_US) {\r\n"
        b"                break; /* \xe8\xbf\x99\xe4\xb8\x80\xe5\x9c\x88\xe8\xb6\x85\xe6\x97\xb6\xe4\xbd\x9c\xe5\xba\x9f",
        b"        int32_t timeout = 50;\r\n"
        b"        while (DL_ADC12_getStatus(ADC12_0_INST) & ADC12_STATUS_BUSY_ACTIVE) {\r\n"
        b"            if (--timeout <= 0) {\r\n"
        b"                return (uint16_t)(sum / (i ? i : 1)); /* INJECTED */",
    ),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_cases() -> tuple[bool, str]:
    """跑两条新用例 → (是否全绿, 「哪几条红了」+ 汇总行)。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *CASES, "-q", "--no-header", "-p", "no:cacheprovider",
         "-rf"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    text = proc.stdout or ""
    reds = [
        line.split("::")[-1].split(" ")[0]
        for line in text.splitlines()
        if line.startswith("FAILED ")
    ]
    tail = text.strip().splitlines()
    summary = tail[-1] if tail else "(无输出)"
    detail = ("红了：" + "、".join(reds)) if reds else "无红"
    return proc.returncode == 0, f"{summary}（{detail}）"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPORT))
    args = parser.parse_args()
    out_path = Path(args.out)

    original = TARGET.read_bytes()
    before = sha256(original)
    rows: list[str] = [
        "=== 判据强度反证：driver-defect-fixes/01（joystick × mspm0 超时判据）===",
        f"目标文件：{TARGET.relative_to(REPO)}",
        f"注入前 sha256：{before}",
        "",
    ]
    if b"JOYSTICK_ADC_INVALID" not in original or b"JOYSTICK_ADC_SEQ_US" not in original:
        rows.append("✗ 前置干净性检查失败：文件不是「已修」形态——上一次探针可能被强杀，"
                    "先 `git checkout -- <文件>` 复原再跑。")
        out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        print(rows[-1])
        return 2

    ok, summary = run_cases()
    rows.append(f"[对照] 未注入：{'PASS' if ok else 'FAIL'}  —— {summary}")
    rows.append("")

    failures = 0
    try:
        for name, criterion, src, dst in INJECTIONS:
            assert original.count(src) == 1, f"注入锚点在原文里出现 {original.count(src)} 次：{name}"
            TARGET.write_bytes(original.replace(src, dst))
            try:
                ok, summary = run_cases()
            finally:
                TARGET.write_bytes(original)  # 逐字节复原（二进制读写，零归一）
            restored = sha256(TARGET.read_bytes()) == before
            verdict = "红（符合预期）" if not ok else "**仍然绿——判据没抓住这一条！**"
            if ok:
                failures += 1
            if not restored:
                failures += 1
            rows.append(f"[注入] {name}")
            rows.append(f"       目标判据：{criterion}")
            rows.append(f"       结果：{verdict}  —— {summary}")
            rows.append(f"       复原复核：sha256 {'一致' if restored else '**不一致**'}")
            rows.append("")
    finally:
        TARGET.write_bytes(original)

    rows.append(f"=== 结论：{'全部符合预期（每条注入都让对应用例变红，且文件逐字节复原）' if not failures else f'有 {failures} 处不符'} ===")
    out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("\n".join(rows))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
