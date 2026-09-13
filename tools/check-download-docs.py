"""发版前的「新用户下载链路」一致性校验（工单 newuser-download/06）。

**为什么需要它**：2026-09 出现过一次真实事故——README 教新用户去下
`firstep-full.7z.001~004`（约 6 GB），而那个形态只存在于 v1.0.0 那个 release，
最新版上根本没有；照做的人会白找一圈。**文档与线上分叉，是这类事故唯一的原因。**

它校三处公共入口是否讲同一个故事：

1. **README**：指向的是不是 `/releases/latest`、点名的完整包资产名在线上是否存在、
   写明的体积与线上字节是否同量级、有没有偷偷把已下线渠道写回来；
2. **Release 说明**：最新版的正文前几行有没有那两行固定指引（新用户只下一个文件 /
   已装用户走工具内更新）；
3. **包内文件**：README 点名「解压后先看」的那个文件，是不是真在完整包里
   （用 `full_pack.scan_tree` 判，与打包器同一判据）。

**为什么不写进 pytest**：本仓库的测试刻意不联网（见 `tests/fakes.py`「网络不进测试」），
所以做成**发版前手动跑**的脚本。建议加进发版清单（`docs/agents/releasing.md`）。

用法（仓库根）：

    python tools/check-download-docs.py            # 查线上（需要网络）
    python tools/check-download-docs.py --offline  # 只查包内一致性，不联网

退出码 0 = 三处一致；非 0 = 有分叉，输出逐条原因。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

REPO_SLUG = "AK47n/firstep"
LATEST_URL = f"https://github.com/{REPO_SLUG}/releases/latest"
API_LATEST = f"https://api.github.com/repos/{REPO_SLUG}/releases/latest"
TIMEOUT = 60

# 已下线 / 线上不存在的下载形态。与 `tests/test_onboarding_docs.py` 的守卫同口径
# （那边是"测试时"的硬门禁，这里是"发版前"的自检；两处判据要保持一致，
#   改一处记得改另一处——判据本身很短，不值得为共享它引入跨目录导入）。
DEAD_TOOL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"7-?[Zz]ip", "还在提第三方解压工具 7-Zip"),
    (r"Bandizip", "还在提第三方解压工具 Bandizip"),
    (r"WinRAR", "还在提第三方解压工具 WinRAR"),
)
DEAD_CHANNEL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"firstep-full\.7z", "还在提 v1.0.0 那个 7z 分卷形态"),
    (r"7z\.001", "还在引用 7z 分卷文件名"),
    (r"解压\s*`?\.001", "还在教解压 7z 分卷"),
)
# 否定词 → 与工具名的最大允许距离（「不用装 7-Zip」这类防坑提醒要放行）
NEGATION_WINDOWS: tuple[tuple[str, int], ...] = (
    ("无需", 16), ("不需", 16), ("没有", 16), ("不用", 10),
    ("不要", 10), ("别", 8), ("免", 8), ("不", 5), ("没", 4),
)
NEGATION_LOOKBACK = 20
TAIL_NEGATION_RE = re.compile(r"\s*(?:不用|不必|不需要|无需|不需|免|别)")


def dead_channel_hits(text: str) -> list[str]:
    """文本里「已下线渠道」的真实命中（原因列表）；否定式提醒不算命中。"""
    hits: list[str] = []
    for pattern, why in DEAD_TOOL_PATTERNS:
        for m in re.finditer(pattern, text):
            prefix = text[max(0, m.start() - NEGATION_LOOKBACK): m.start()]
            negated = False
            for word, window in NEGATION_WINDOWS:
                at = prefix.rfind(word)
                if at >= 0:
                    negated = len(prefix) - (at + len(word)) <= window
                    break
            if not negated:
                negated = bool(TAIL_NEGATION_RE.match(text[m.end(): m.end() + 4]))
            if not negated:
                hits.append(f"{why}（命中：{m.group(0)}）")
    for pattern, why in DEAD_CHANNEL_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            hits.append(f"{why}（命中：{m.group(0)}）")
    return hits


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def readme_download_section() -> str:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    start = text.find("## 获取方式")
    if start < 0:
        raise SystemExit("README 缺少「获取方式」章节")
    rest = text[start:]
    end = rest.find("\n## ", 3)
    return rest if end < 0 else rest[:end]


def full_pack_paths() -> set[str]:
    from contest_generator.full_pack import scan_tree

    return {f.path for f in scan_tree(REPO_ROOT)}


def _git_pack_mib() -> float | None:
    """git 自己报的 pack 体积（MiB）——`git clone` 下来大致就是这个量级。"""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "count-objects", "-vH"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    m = re.search(r"size-pack:\s*([\d.]+)\s*(\w+)", out.stdout)
    if not m:
        return None
    value, unit = float(m.group(1)), m.group(2).lower()
    if unit.startswith("k"):
        return value / 1024
    if unit.startswith("g"):
        return value * 1024
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check-download-docs", description=__doc__)
    parser.add_argument("--offline", action="store_true", help="跳过联网检查（只查包内一致性）")
    args = parser.parse_args(argv)

    problems: list[str] = []
    print("=== 1. README「获取方式」 ===")
    section = readme_download_section()
    dead = dead_channel_hits(section)
    if dead:
        problems.extend(f"README 出现已下线/线上不存在的形态：{d}" for d in dead)
    else:
        print("  [OK] 没有已下线形态（7z 分卷 / 需第三方解压工具 / 约 6 GB 那套）")
    if LATEST_URL not in section:
        problems.append("README 未指向 /releases/latest（写死 tag 深链会在下次发版后失效）")
    else:
        print(f"  [OK] 指向 {LATEST_URL}")

    # 包内一致性：README 点名「去包里看」的文件必须真在包里（与打包器同一判据）
    in_pack = full_pack_paths()
    promised = {
        t for t in re.findall(r"`([^`\n]+)`", section)
        if "." in t and " " not in t and 3 <= len(t) <= 40
        and not re.match(r"^(?:firstep-|v\d|\.)", t)
    }
    missing_in_pack = sorted(t for t in promised if t not in in_pack)
    if missing_in_pack:
        problems.append(f"README 点名了不在完整包里的文件：{missing_in_pack}")
    else:
        named = sorted(promised) or ["（章内未点名包内文件）"]
        print(f"  [OK] 点名的包内文件都在包里：{'、'.join(named)}")

    if args.offline:
        print("\n（--offline：只查了第 1 组「README 与包内文件」，**没有**校验线上资产与 Release 说明）")
        return _report(problems, offline=True)

    print("\n=== 2. 线上最新版 ===")
    try:
        release = fetch_json(API_LATEST)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        problems.append(f"取线上最新版失败（网络？）：{exc}")
        return _report(problems)

    tag = str(release.get("tag_name") or "")
    assets = {a["name"]: int(a["size"]) for a in release.get("assets") or []}
    print(f"  最新 tag：{tag}；资产 {len(assets)} 件")

    full_zip = f"firstep-full-{tag}.zip"
    if full_zip not in assets:
        problems.append(f"线上最新版缺完整包资产 {full_zip}——新用户没有入口（README 只指这一个文件）")
    else:
        size = assets[full_zip]
        print(f"  [OK] {full_zip} = {size:,} 字节（{size / 1000 / 1000:.0f} MB）")

    # 体积口径逐行校验：**只比同一行里出现的资产名与「约 N MB」**。
    # （第一版按「章内第一条 约 N MB」比，结果拿 git clone 的 270 MB 去比完整包，
    #   探针自己误报——踩过，所以按行绑定。）
    checked = 0
    for line in section.splitlines():
        if not line.startswith("| ") or "约" not in line:
            continue
        # README 的表格里资产名带占位符（`firstep-full-<版本>.zip`），所以按**前缀**认行；
        # 同时要求该行出现「<版本>」或本版 tag，避免把别的行误当成资产行。
        asset = next(
            (
                name
                for prefix, name in (
                    ("firstep-full-", full_zip),
                    ("firstep-update-", f"firstep-update-{tag}.zip"),
                )
                if prefix in line and name in assets and ("<版本>" in line or tag in line)
            ),
            "",
        )
        claimed = re.search(r"约\s*(\d+)\s*MB", line)
        if not asset or not claimed:
            continue
        claimed_mb, actual_mb = int(claimed.group(1)), assets[asset] / 1000 / 1000
        if not (0.5 * claimed_mb <= actual_mb <= 1.6 * claimed_mb):
            problems.append(
                f"README 写「约 {claimed_mb} MB」（{asset}），线上实际 {actual_mb:.0f} MB"
                "（差得太多会让人以为下错了）"
            )
        else:
            print(f"  [OK] 「约 {claimed_mb} MB」对应 {asset} 的线上 {actual_mb:.0f} MB")
        checked += 1
    if checked == 0:
        problems.append("README「获取方式」里没找到「资产名 + 约 N MB」绑定的行（表格结构变了？）")

    # git clone 那行的体积用 git 自己报的 pack 体积校验（clone 下来大致就是这个量级）
    if "git clone" in section:
        pack_mib = _git_pack_mib()
        if pack_mib is None:
            print("  [--] git 体积无法取得，跳过 clone 行校验")
        else:
            m = re.search(r"git clone[^\n]*?约\s*(\d+)\s*MB", section)
            if m and not (0.5 * int(m.group(1)) <= pack_mib <= 2.0 * int(m.group(1))):
                problems.append(
                    f"README 写 clone「约 {m.group(1)} MB」，git 实际 pack 体积 {pack_mib:.0f} MiB"
                )
            elif m:
                print(f"  [OK] clone「约 {m.group(1)} MB」与 git pack {pack_mib:.0f} MiB 同量级")

    print("\n=== 3. Release 说明的前几行 ===")
    body = str(release.get("body") or "")
    head = "\n".join([ln for ln in body.splitlines() if ln.strip()][:4])
    if "新用户" not in head:
        problems.append("最新版 Release 说明开头没有「新用户只下哪个文件」的指引（新用户第一眼看的是这里）")
    else:
        print("  [OK] 开头有面向新用户的指引")
    if "已装用户" not in head:
        problems.append("最新版 Release 说明开头没有「已装用户走工具内更新」的指引")
    else:
        print("  [OK] 开头有面向已装用户的指引")

    return _report(problems)


def _report(problems: list[str], *, offline: bool = False) -> int:
    print("\n=== 结论 ===")
    if problems:
        for p in problems:
            print(f"  FAIL {p}")
        return 1
    if offline:
        print("  PASS（离线）：README 与包内文件一致——**线上那一半没查**，发版前再跑一次完整版")
    else:
        print("  PASS：README / Release 说明 / 包内文件三处讲的是同一个故事")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
