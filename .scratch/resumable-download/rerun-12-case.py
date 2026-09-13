"""工单 12 探针的**单格复跑器**（诊断用）：只跑指定的几格，原文不截断。

为什么要它：整支探针一次跑十格，某一格「探针失效」时看不到原始输出（探针只留摘要），
而「超时」与「注入没生效」是两种完全不同的失效。本脚本按案件名复跑，把
pytest 原始输出与 sitecustomize 报错整段打出来。

用法：python .scratch/resumable-download/rerun-12-case.py full:no_retry_fields [超时秒]
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

spec = importlib.util.spec_from_file_location("p12", HERE / "probe-12-guard-strength.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def main() -> int:
    wanted = sys.argv[1]
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0
    case = next(c for c in probe.CASES if c[0] == wanted)
    _, kind, flavor, files = case
    src = probe.STATUS_NAIVE[wanted]
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "sitecustomize.py").write_text(
            probe.build_plugin(kind, flavor, src), encoding="utf-8"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([tmp, str(ROOT / "src")])
        env["PYTHONIOENCODING"] = "utf-8"
        print(f"== 复跑 {wanted}（上限 {timeout}s，逐文件） ==", flush=True)
        # 逐文件跑才分得清「卡住」与「红」（本机间歇性卡住，工单 11/12 都记过）。
        import time

        probe.CASE_TIMEOUT_SECONDS = timeout
        for verdict, detail in probe.run(wanted, kind, flavor, src, files):
            print(f"  [{verdict}] {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
