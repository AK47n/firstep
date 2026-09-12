"""生成功能组「未选」判据的跨语言镜像 fixture（工单 group-choice-required/01）。

为什么要手工跑一次：`tests/js/group-choice-mirror.fixture.json` 是**前后端判据一致性**的
契约件——Python 侧 `missing_group_choices` 是场景表的出处与期望值的唯一计算者，JS 侧
`pendingGroupChoices` 必须给出同一结论。fixture **不随测试自动重写**：漂移时 pytest 会红，
必须显式跑本脚本、看清 diff（这次改动是有意的，还是漏改了另一侧）。

用法：`$env:PYTHONPATH='src'; python tools/gen_group_choice_mirror.py`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_group_choice_mirror import FIXTURE, mirror_payload  # noqa: E402


def main() -> int:
    payload = mirror_payload()
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    old = FIXTURE.read_text(encoding="utf-8") if FIXTURE.is_file() else ""
    if old == text:
        print(f"镜像 fixture 已是最新：{FIXTURE}（{len(payload['cases'])} 个场景）")
        return 0
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(text, encoding="utf-8")
    print(f"已重写：{FIXTURE}（{len(payload['cases'])} 个场景）——请 diff 确认这次改动是有意的")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
