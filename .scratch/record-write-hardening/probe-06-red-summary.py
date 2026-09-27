"""反证汇总（工单 record-write-hardening/06）：把五张单的探针**重跑一遍**并汇总成一份读数。

做两件事：
1. 逐张单调 `.scratch/hwcheck-hygiene/readings.py` 重跑 `probe-0X-red.py` ——
   读数绑到**当前字节**（代码收口后 atomic_io / 各判据文件都动过，旧读数已脱钩）；
2. 把刚写下的五份读数正文（含每段的「声明必须红 / 实得 FAILED / 复原 sha256」）拼成一份，
   并在末尾给一张判定表：每张单的探针结论行 + 是否每段都对上。

**不重新实现判据**：汇总只搬运各探针自己的输出与结论，不替它们判 PASS。
用法：`python .scratch/record-write-hardening/probe-06-red-summary.py`
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".scratch" / "record-write-hardening"
READINGS = ROOT / ".scratch" / "hwcheck-hygiene" / "readings.py"
PROBES = [
    ("probe-01-red", "01 共享原语"),
    ("probe-02-red", "02 想法草稿"),
    ("probe-03-red", "03 想法商量"),
    ("probe-04-red", "04 参数表"),
    ("probe-05-red", "05 母版元数据"),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("# 反证汇总（工单 record-write-hardening/06 收口）")
    print("# 每张单都是三段式：逐条声明必须红 + 与实得 FAILED 对账 + 每段复原 sha256 逐字节相同；")
    print("# 每份读数头部记着被撤源码与判据文件的 sha256（下面逐份贴出）。")
    print()
    verdicts: list[tuple[str, str, bool]] = []
    for name, issue in PROBES:
        printed = subprocess.run(
            [
                sys.executable,
                str(READINGS),
                name,
                "--out-dir",
                str(OUT_DIR),
                "--",
                sys.executable,
                str(OUT_DIR / f"{name}.py"),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        body = (OUT_DIR / f"{name}.txt").read_text(encoding="utf-8")
        # 保留探针自己的 `# 被撤的源码…` 头，去掉 readings.py 那五行头
        lines = [line for line in body.splitlines() if not line.startswith("# 读数：")]
        lines = [
            line
            for line in lines
            if not line.startswith(("# 命令：", "# 工作树：", "# 开始：", "# 退出码："))
        ]
        print(f"===== {name}（工单 {issue}）· readings.py 退出码 {printed.returncode} =====")
        print("\n".join(lines).strip())
        print()
        conclusion = next(
            (line for line in lines if line.startswith("结论：")), "（没找到结论行）"
        )
        mismatched = [
            line
            for line in lines
            if line.strip().startswith(("[x]"))
        ]
        ok = printed.returncode == 0 and "PASS" in conclusion and not mismatched
        verdicts.append((name, conclusion.strip(), ok))

    print("===== 判定表（只看各探针自己的结论行 + 有没有对账不上的段） =====")
    for name, conclusion, ok in verdicts:
        print(f"{'[OK]  ' if ok else '[FAIL]'} {name}：{conclusion}")
    print()
    all_ok = all(ok for _name, _conclusion, ok in verdicts)
    print("汇总结论：" + ("五张单的反证全部成立、读数已绑当前字节" if all_ok else "有单不成立，见上"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
