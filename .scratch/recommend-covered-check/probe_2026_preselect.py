"""真实 2026 赛题 × 预筛覆盖探测（工单 module-preselect/03 前置验证）：

对 .scratch/contest-2026/txt/ 的 8 道真题跑 mspm0 线预筛，输出：
- 命中集（得分 > 0 的 slug）
- 预筛子集大小 / 全量
- 批次 13 新模块（relay / as32 / bmp180 / ms5611）是否在子集内
- 常见控制常识件（led_beep / key / motor / adc 等）是否在零命中形态子集内
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from contest_generator.budget import MODULE_SUMMARY_BYTES
from contest_generator.library import list_modules
from contest_generator.manifest import build_manifest_summaries
from contest_generator.selection import filter_manifests_by_platform, preselect_module_summaries
from contest_generator.platforms import PLATFORM_MSPM0
from contest_generator.wordlist import load_wordlist

LIB = Path(__file__).resolve().parents[2] / "library" / "modules"
TXT = Path(__file__).resolve().parents[1] / "contest-2026" / "txt"
WATCH = ("relay", "as32", "bmp180", "ms5611")
COMMON = ("led_beep", "key", "motor", "adc", "uart", "oled", "lcd")

mods = list_modules(LIB)
summaries = build_manifest_summaries(filter_manifests_by_platform(mods, PLATFORM_MSPM0))
wl = load_wordlist()

for path in sorted(TXT.glob("*.txt")):
    text = path.read_text(encoding="utf-8", errors="ignore")
    result = preselect_module_summaries(summaries, text, wl, MODULE_SUMMARY_BYTES)
    in_set = {s.slug for s in result.summaries}
    watch_hit = [s for s in WATCH if s in in_set]
    common_hit = [s for s in COMMON if s in in_set]
    print(f"== {path.stem}")
    print(f"   子集 {len(result.summaries)}/{result.total}  truncated={result.truncated}")
    print(f"   批次13新件在子集: {watch_hit or '无'}")
    print(f"   常备件在子集: {common_hit or '无'}")
