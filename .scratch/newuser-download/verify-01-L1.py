"""L1 演练证据采集（工单 newuser-download/01）：把 README 承诺的每一件事对着线上实测一遍。

只读、不写仓库：核 README 的 URL / 资产名 / 体积 / 校验和，以及解压后包内第一眼。
输出直接贴进 `.scratch/newuser-download/E2E-8020.md` 的 L1 证据区。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

REPO = "AK47n/firstep"
TAG_EXPECTED = "v1.1.1"
LATEST_URL = "https://github.com/AK47n/firstep/releases/latest"
LOCAL_ZIP = Path(r"C:\Users\luoji\Desktop\firstep-dl-test\firstep-full-v1.1.1.zip")
README = Path(__file__).resolve().parents[2] / "README.md"

failures: list[str] = []


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def check(label: str, ok: bool, detail: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}：{detail}")
    if not ok:
        failures.append(f"{label} → {detail}")


def gh_json(path: str) -> dict:
    out = subprocess.run(
        ["gh", "api", path], capture_output=True, text=True, encoding="utf-8", timeout=120
    )
    if out.returncode != 0:
        raise RuntimeError(f"gh api 失败：{out.stderr}")
    return json.loads(out.stdout)


section("1. README 承诺 vs 线上事实")
readme = README.read_text(encoding="utf-8")
check("README 给出完整包资产名形态", "firstep-full-<版本>.zip" in readme, "`firstep-full-<版本>.zip`")
check("README 指向 Releases 最新版", LATEST_URL in readme, LATEST_URL)

release = gh_json(f"repos/{REPO}/releases/latest")
check("latest tag", release["tag_name"] == TAG_EXPECTED, release["tag_name"])

assets = {a["name"]: a["size"] for a in release["assets"]}
zip_name = f"firstep-full-{TAG_EXPECTED}.zip"
check("完整包资产在场", zip_name in assets, zip_name)
zip_size = assets.get(zip_name, 0)
check(
    "体积与 README「约 821 MB」同量级",
    780_000_000 <= zip_size <= 900_000_000,
    f"{zip_size:,} 字节 = {zip_size / 1024 / 1024:.1f} MiB（README 写约 821 MB）",
)
for name in (
    f"firstep-update-{TAG_EXPECTED}.zip",
    f"firstep-full-{TAG_EXPECTED}.manifest.json",
    f"firstep-full-{TAG_EXPECTED}.sha256.txt",
):
    check("README 表格提到的资产在场", name in assets, f"{name} = {assets.get(name, 0):,} 字节")

section("2. 已下线形态不得被「推荐式」提及（正向扫 README）")
import sys  # noqa: E402

sys.path.insert(0, str(README.parent / "tests"))
from test_onboarding_docs import dead_channel_hits  # noqa: E402

hits = dead_channel_hits(readme)
check("README 无已下线渠道命中", not hits, str(hits) if hits else "0 命中")

section("3. 本地真实下载件核对（线上资产 → 落地字节 → 校验和）")
check("本地 zip 在场", LOCAL_ZIP.is_file(), str(LOCAL_ZIP))
if LOCAL_ZIP.is_file():
    local_size = LOCAL_ZIP.stat().st_size
    check("落地字节 == 线上字节", local_size == zip_size, f"{local_size:,} vs {zip_size:,}")
    digest = hashlib.sha256()
    with LOCAL_ZIP.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    local_sha = digest.hexdigest()
    with urllib.request.urlopen(
        f"https://github.com/{REPO}/releases/download/{TAG_EXPECTED}/firstep-full-{TAG_EXPECTED}.sha256.txt",
        timeout=60,
    ) as resp:
        remote_sha = resp.read().decode("utf-8").split()[0]
    check("SHA256 与线上 sha256.txt 一致", local_sha == remote_sha, f"{local_sha} == {remote_sha}")

section("4. 解压后第一眼（Windows 自带能力，非 7-Zip）")
if LOCAL_ZIP.is_file():
    # 注意：bsdtar 列中文条目按控制台代码页（本机 GBK）输出，不能按 UTF-8 解——按字节收、宽松解码。
    listing = subprocess.run(
        ["tar.exe", "-tf", str(LOCAL_ZIP)], capture_output=True, timeout=600
    )
    raw = listing.stdout.decode("utf-8", errors="replace")
    if "\ufffd" in raw:
        raw = listing.stdout.decode("gbk", errors="replace")
    entries = [ln for ln in raw.splitlines() if ln.strip()]
    roots = sorted({e.split("/")[0] for e in entries})
    check("包内条目数", len(entries) > 8000, f"{len(entries):,} 条")
    loose = [e for e in entries if "/" not in e]
    print(f"  根级文件（用户解压后第一眼看到的）：{len(loose)} 个")
    for name in loose:
        print(f"    - {name}")
    has_start_here = any(s.lower().startswith("start-here") for s in roots)
    print(
        f"  [{'PASS' if has_start_here else '待办'}] 包内「从这里开始」文件："
        f"{'在场' if has_start_here else '不在场（工单 02 的目标；这正是 L1 的卡点 K1）'}"
    )

section("结论")
if failures:
    for f in failures:
        print(f"  FAIL {f}")
    raise SystemExit(1)
print("  PASS：README 承诺的每一件事都在线上成立（包内 START-HERE 属工单 02，不在本工单判据内）")
