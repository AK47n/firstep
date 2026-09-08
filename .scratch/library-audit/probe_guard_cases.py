"""临时探针：候选覆盖率守卫用例的现状（哪些题面 × 平台下关键模块可见）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator import wordlist as wordlist_mod  # noqa: E402
from contest_generator.budget import MODULE_SUMMARY_BYTES  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.manifest import build_manifest_summaries  # noqa: E402
from contest_generator.selection import preselect_module_summaries  # noqa: E402

CANDIDATES = [
    ("2024H", "stm32", ("motor", "pid", "servo", "led", "key")),
    ("2024H", "mspm0", ("motor", "pid", "servo", "led", "key")),
    # 2021F 的循迹核心在 stm32 侧由 pid 承担（xunji 只有 mspm0 条目）
    ("2021F", "stm32", ("motor", "pid", "key", "oled")),
    ("2026C", "stm32", ("led", "beep", "key", "oled")),
    ("2026A", "mspm0", ("motor", "servo", "led", "key")),
    ("2022C", "stm32", ("motor", "pid", "oled", "key")),
]

manifests = list_modules(ROOT / "library" / "modules")
words = wordlist_mod.load_wordlist()

for topic, platform, probes in CANDIDATES:
    summaries = build_manifest_summaries(
        [m for m in manifests if platform in m.platforms]
    )
    # 瘦身行形态（工单 preselect-visibility/02）：与路由同源，否则测的不是
    # 生产路径（完整行会截断，可见性结论完全相反）
    summaries = [s.lean_copy() for s in summaries]
    text = (ROOT / "library" / "topics" / topic / "topic.md").read_text(
        encoding="utf-8", errors="replace"
    )
    result = preselect_module_summaries(summaries, text, words, MODULE_SUMMARY_BYTES)
    visible = {s.slug for s in result.summaries}
    missing = [slug for slug in probes if slug not in visible]
    state = "PASS" if not missing else "XFAIL"
    print(
        f"{topic}/{platform:<6} 可见 {len(result.summaries)}/{result.total}  "
        f"{state}  缺：{'、'.join(missing) or '（无）'}"
    )
