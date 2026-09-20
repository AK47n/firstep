# -*- coding: utf-8 -*-
"""工单 webapp-consolidation/01 的红证：结构钉的判据不是摆设。

把**迁移前**（`git show HEAD:src/contest_generator/webapp.py`）的源码喂给
`tests/test_hwcheck_board.py` 里那条判据（`_hwcheck_import_leaks`），它必须当场
认出当年那批装配原语；工作树（迁移后）必须是空的。判据只有一份（测试里那个纯
函数），本探针不抄第二份。

用法：`python .scratch/webapp-consolidation/probe-01-pin-red-proof.py`
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))  # 测试模块 import 的 contest_generator
sys.path.insert(0, str(REPO))          # tests 包

from tests.test_hwcheck_assembly_home import (  # noqa: E402  （路径先注入，后导入）
    _hwcheck_import_leaks,
    _hwcheck_imports,
)

WEBAPP = "src/contest_generator/webapp.py"


def _head_source() -> str:
    result = subprocess.run(
        ["git", "show", f"HEAD:{WEBAPP}"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return result.stdout


def main() -> int:
    head = _head_source()
    current = (REPO / WEBAPP).read_text(encoding="utf-8")
    head_leaks = _hwcheck_import_leaks(head)
    current_leaks = _hwcheck_import_leaks(current)
    print(f"HEAD 版（迁移前）泄漏 {len(head_leaks)} 条：")
    for item in sorted(head_leaks):
        print(f"  - {item}")
    print(f"工作树（迁移后）泄漏 {len(current_leaks)} 条：{sorted(current_leaks)}")
    imported = sorted(f"{module}.{name}" for module, name in _hwcheck_imports(current))
    print(f"工作树 import 面：{imported}")
    ok = bool(head_leaks) and not current_leaks
    print("PASS：判据在迁移前为红、迁移后为绿" if ok else "FAIL：判据没认出迁移前的形态")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
