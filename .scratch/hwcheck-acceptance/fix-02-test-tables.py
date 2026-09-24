# -*- coding: utf-8 -*-
"""工单 02 的测试侧表格修补：`tests/test_pins.py` 的 `MSPM0_DEFAULT_MAP`。

那张表把 `(slug, role_id) → (syscfg 实例, $name 符号)` 钉成数据（判据是
"声明默认脚 == 母版那一行"）。GPIO 组的第二项就是引脚符号名，母版改名后必须
跟着改——本脚本按 `rename-02-pin-labels.py` 同一份计划（从 `--base-rev` 复算）
改，外设尾字段（txPin/sclPin/ccp0Pin…）一个字不碰。

用法：
    python .scratch/hwcheck-acceptance/fix-02-test-tables.py [--write]
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
REPO = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from importlib import import_module  # noqa: E402

_rename = import_module("rename-02-pin-labels")

TARGET = REPO / "tests" / "test_pins.py"
ENTRY = re.compile(
    r'\(\s*"(?P<slug>[a-z_0-9]+)"\s*,\s*"(?P<role>[A-Z0-9_]+)"\s*\)\s*:\s*'
    r'\(\s*"(?P<inst>[A-Z_0-9]+)"\s*,\s*"(?P<label>[A-Za-z_0-9]+)"\s*\)'
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--base-rev", default="HEAD")
    args = parser.parse_args()

    plan = _rename.rename_plan_from_rev(args.base_rev)
    text = TARGET.read_text(encoding="utf-8", newline="")
    hits = 0

    def sub(match: re.Match[str]) -> str:
        nonlocal hits
        new = plan.get(match.group("inst"), {}).get(match.group("label"))
        if new is None:
            return match.group(0)
        hits += 1
        print(
            f"  {match.group('slug')}.{match.group('role')}："
            f"{match.group('label')} → {new}"
        )
        return (
            f'("{match.group("slug")}", "{match.group("role")}"): '
            f'("{match.group("inst")}", "{new}")'
        )

    new_text = ENTRY.sub(sub, text)
    print(f"合计 {hits} 处" + ("" if args.write else "（dry-run）"))
    if args.write and hits:
        TARGET.write_text(new_text, encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
