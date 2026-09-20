# -*- coding: utf-8 -*-
"""工单 webapp-consolidation/02 的红证：单源守卫的判据不是摆设。

把**迁移前**（`git show HEAD:src/contest_generator/webapp.py`）的源码喂给
`tests/test_llm_run.py` 里那条判据（`_triple_sites`），它必须当场点出当年那 25 处
散落的三件套；工作树必须是四条各一处、且都在缝里。判据只有一份（测试里那个纯
函数），本探针不抄第二份。

用法：`python .scratch/webapp-consolidation/probe-02-triple-red-proof.py`
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))  # 测试模块 import 的 contest_generator
sys.path.insert(0, str(REPO))          # tests 包

from tests.test_llm_run import _triple_sites  # noqa: E402  （路径先注入，后导入）

WEBAPP = "src/contest_generator/webapp.py"
EXPECTED = {
    "collector": ["LLMRun.__init__"],
    "budget": ["LLMRun.__init__"],
    "dispatch": ["LLMRun.llm"],
    "settle": ["LLMRun.settle"],
}


def main() -> int:
    head = subprocess.run(
        ["git", "show", f"HEAD:{WEBAPP}"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    current = (REPO / WEBAPP).read_text(encoding="utf-8")
    head_sites = _triple_sites(head)
    current_sites = _triple_sites(current)
    print("HEAD 版（迁移前）：")
    for probe, owners in head_sites.items():
        print(f"  {probe}: {len(owners)} 处 → {owners[:6]}{' …' if len(owners) > 6 else ''}")
    print(f"工作树（迁移后）：{current_sites}")
    ok = (
        all(len(head_sites[probe]) >= 20 for probe in ("collector", "budget", "dispatch", "settle"))
        and current_sites == EXPECTED
    )
    print(
        "PASS：迁移前四处散落（各 ≥20 处）、迁移后四条各一处且在缝内"
        if ok else "FAIL：判据没认出迁移前的形态，或工作树不是单源"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
