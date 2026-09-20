"""生成同脚多角色 共享/冲突 判据的跨语言镜像 fixture
（工单 cross-lang-mirror-c5a/02）。

为什么要手工跑一次：`tests/js/pin-share-mirror.fixture.json` 是**前后端判据一致性**
的契约件——Python 侧 `pin_bindings._shared_groups`（经场景表
`tests/test_pin_share_mirror.py` 的 `CASES`）是期望值的唯一计算者，JS 侧
`fx/generate.js` 的 `pinShareClass` 必须给出同一结论。fixture **不随测试自动
重写**：漂移时 pytest 会红，必须显式跑本脚本、看清 diff（这次改动是有意的，
还是漏改了另一侧）。

用法：`$env:PYTHONPATH='src'; python tools/gen_pin_share_mirror.py`
先例：`tools/gen_group_choice_mirror.py`。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_pin_share_mirror import FIXTURE, mirror_payload  # noqa: E402


def main() -> int:
    payload = mirror_payload()
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    old = FIXTURE.read_text(encoding="utf-8") if FIXTURE.is_file() else ""
    if old == text:
        print(f"镜像 fixture 已是最新：{FIXTURE}（{len(payload['cases'])} 个场景）")
        return 0
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(text, encoding="utf-8")
    print(
        f"已重写：{FIXTURE}（{len(payload['cases'])} 个场景）"
        "——请 diff 确认这次改动是有意的"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
