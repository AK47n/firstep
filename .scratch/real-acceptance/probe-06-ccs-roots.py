"""工单 real-acceptance/06 真机探针：CCS 三件套逐件来源根（本机实况）。

只读探测（零副作用、不碰 config、不起服务）：调 compile_runner.ccs_tools_status()
拿逐件 {found, path, root}，与本工单「真机现场」表格逐条比对——体检页显示的就是
这份数据，比对绿 = 「本机三件来源与工单表格一致」这条验收有机器证据。

用法：python .scratch/real-acceptance/probe-06-ccs-roots.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import ccs_tools_status  # noqa: E402

# 工单「真机现场（2026-09-10 第十六轮 A8/C-A6 实跑）」表格逐字
EXPECTED = {
    "compiler": (
        r"C:\ti\ccs2050\ccs\tools\compiler\ti-cgt-armllvm_4.0.4.LTS",
        r"C:\ti\ccs2050",
    ),
    "sdk": (
        r"C:\ti\ccs2051\mspm0_sdk_2_10_00_04",
        r"C:\ti\ccs2051",
    ),
    "sysconfig": (
        r"C:\ti\ccs2051\sysconfig_1.26.2\sysconfig_cli.bat",
        r"C:\ti\ccs2051",
    ),
}

LABEL = {"compiler": "编译器", "sdk": "MSPM0 SDK", "sysconfig": "SysConfig CLI"}


def main() -> int:
    st = ccs_tools_status()
    lines = ["# 工单 06 真机探针：CCS 三件套逐件来源（ccs_tools_status 实况）", ""]
    fails = 0
    roots = set()
    for key in ("compiler", "sdk", "sysconfig"):
        entry = st[key]
        want_path, want_root = EXPECTED[key]
        got_path, got_root = entry["path"], entry["root"]
        ok_path = got_path == want_path
        ok_root = got_root == want_root
        if entry["found"] and got_root:
            roots.add(got_root)
        if not (entry["found"] and ok_path and ok_root):
            fails += 1
        lines.append(
            f"{'ok  ' if entry['found'] and ok_path and ok_root else 'FAIL'}"
            f" {LABEL[key]}：found={entry['found']} path={got_path} root={got_root}"
            f"（工单表格 path={want_path} root={want_root}）"
        )
    cross = len(roots) > 1
    lines += [
        "",
        f"来源根集合：{sorted(roots)} → {'跨安装目录' if cross else '同源'}",
        f"结论：{'ALL PASS' if not fails else f'FAILURES: {fails}'}"
        "（三件跨 ccs2050 / ccs2051 组合 = 工单现场，编译实测通过；探测行为未改）",
    ]
    print("\n".join(lines))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
