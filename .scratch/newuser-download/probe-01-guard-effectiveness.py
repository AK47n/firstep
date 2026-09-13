"""守卫有效性探针（工单 newuser-download/01）：证明 README 下载渠道门禁真的会红、且不误伤。

不改任何文件：用**旧版 README 原文**（逐字取自 v1.1.1）拼出「回归样本」，断言每条人工构造的
违规写法都被抓住；再用当前 README 断言 0 命中；最后用一批**应当放行**的写法（防坑提醒、
边界表达）断言不误伤。红→绿两向都验，避免「模式写宽了」与「写窄了」两种假绿。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))

from test_onboarding_docs import (  # noqa: E402
    _DOWNLOAD_SECTION_BANNED,
    _readme_download_section,
    _readme_text,
    dead_channel_hits,
)

# 旧版 README 里真实出现过的写法（逐字取自 v1.1.1 的 README 原文）
REGRESSED = (
    "从 [GitHub Releases](https://github.com/AK47n/firstep/releases) 下载 "
    "`firstep-full.7z.001~004` 四个分卷，全部下载后解压 `.001` 即可；需 "
    "[7-Zip](https://www.7-zip.org/) 或 Bandizip。**已装用户不必再走这条**\n"
    "- **小发版**（代码 / 模块库 / 文档变更，不用重下 6 GB）\n"
    "- **完整包**（开箱即用，约 6 GB）\n"
)

# 应当**被抓**的写法（人工构造，覆盖不同动词与工具名）
MUST_CATCH = (
    "需 [7-Zip](https://www.7-zip.org/) 或 Bandizip",
    "下载 7z 分卷后解压 .001",
    "首先安装 WinRAR，然后右键解压",
    "用 7zip 打开合并",
    "需要 7-Zip",
)

# 应当**放行**的写法（防坑提醒 / 边界）
MUST_PASS = (
    "不用装 7-Zip 或 Bandizip",
    "不需要 7-Zip / Bandizip",
    "无需安装 7-Zip",
    "免装 7-Zip",
    "别用 WinRAR",
    "系统自带解压即可（没有 7-Zip 也行）",
    "Windows 右键「全部解压缩」",
    "7-Zip 不用装",
    "7-Zip 免安装，直接解压即可",
)

failures: list[str] = []

print("=== A. 回归样本（旧版 README 原文）必须被抓住 ===")
hits = dead_channel_hits(REGRESSED)
seen = {why for why, _ in hits}
for why in (
    "README 仍在提 v1.0.0 那个 7z 分卷形态（最新 release 上不存在）",
    "README 仍引用 7z 分卷文件名（已下线渠道）",
    "README 在教解压 7z 分卷（已下线渠道）",
    "README 仍在提第三方解压工具 7-Zip",
    "README 仍在提第三方解压工具 Bandizip",
):
    mark = "命中" if why in seen else "**漏检**"
    print(f"  [{mark}] {why}")
    if why not in seen:
        failures.append(f"回归样本漏检：{why}")
print(f"  → 共命中 {len(hits)} 处：{[frag for _, frag in hits]}")

print("\n=== B. 逐条违规写法必须被抓 ===")
for bad in MUST_CATCH:
    got = dead_channel_hits(bad)
    print(f"  [{'命中' if got else '**漏检**'}] {bad}")
    if not got:
        failures.append(f"违规写法漏检：{bad}")

print("\n=== C. 防坑提醒与边界写法必须放行（不误伤）===")
for good in MUST_PASS:
    got = dead_channel_hits(good)
    print(f"  [{'误伤' if got else '放行'}] {good}" + (f"  → {got}" if got else ""))
    if got:
        failures.append(f"误伤：{good} → {got}")

print("\n=== D. 当前 README 必须 0 命中 ===")
live = dead_channel_hits(_readme_text())
print(f"  [{'违规' if live else '干净'}] README.md → {live}")
if live:
    failures.append(f"当前 README 误伤：{live}")

print("\n=== E. 「获取方式」章更严门禁（一个字都不许提第三方解压工具）===")
section = _readme_download_section().lower()
for banned in _DOWNLOAD_SECTION_BANNED:
    present = banned in section
    print(f"  [{'违规' if present else '干净'}] {banned}")
    if present:
        failures.append(f"「获取方式」章出现禁用词：{banned}")
bad_section = "| **完整包** | 下载 `firstep-full.7z.001~004`，需 [7-Zip](https://www.7-zip.org/) |"
banned_hit = [b for b in _DOWNLOAD_SECTION_BANNED if b in bad_section.lower()]
print(f"  反例：旧口径写回「获取方式」→ 章内禁用词命中 {banned_hit}")
if not banned_hit:
    failures.append("旧口径写回「获取方式」未被章内门禁拦下")

print("\n=== 结论 ===")
if failures:
    for f in failures:
        print(f"  FAIL {f}")
    raise SystemExit(1)
print("  PASS：回归样本与逐条违规写法全部命中、防坑提醒放行、当前 README 干净、章内门禁生效")
