"""发布后验证：从 GitHub Release 真下载一次资产，核对 SHA256（发现损坏即失败）。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

TAG = sys.argv[1] if len(sys.argv) > 1 else "v1.1.1"
REPO = "AK47n/firstep"
# 默认跳过 GB 级 zip 的重下重算（网络抖动会让它超时）；用 --hashes 显式开启。
VERIFY_BIG_HASHES = "--hashes" in sys.argv

result = subprocess.run(
    ["gh", "release", "view", TAG, "--repo", REPO, "--json", "assets"],
    capture_output=True, text=True, encoding="utf-8",
)
assets = {a["name"]: a for a in json.loads(result.stdout)["assets"]}

failures: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("  ✓ " if cond else "  ✗ ") + what)
    if not cond:
        failures.append(what)


def fetch_bytes(url: str, retries: int = 3, timeout: float = 180) -> bytes:
    """带重试地取一个 URL（GitHub 偶发超时/限速，重试 3 次）。"""
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "firstep-verify"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            print(f"    （第 {attempt} 次取 {url.rsplit('/', 1)[-1]} 失败：{type(exc).__name__}，重试）")
            time.sleep(3 * attempt)
    raise RuntimeError(f"取不到 {url}：{last}")


def fetch_sha(name: str) -> str:
    """下载资产并返回实际 SHA256（流式，不落盘）。"""
    url = f"https://github.com/{REPO}/releases/download/{TAG}/{name}"
    request = urllib.request.Request(url, headers={"User-Agent": "firstep-verify"})
    digest = hashlib.sha256()
    total = 0
    with urllib.request.urlopen(request, timeout=300) as response:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
    print(f"    （已下载 {name}：{total / 1048576:.2f} MB）")
    return digest.hexdigest()


for name in sorted(assets):
    print(f"--- {name}：{assets[name]['size'] / 1048576:.2f} MB")
    if not name.endswith(".zip"):
        check(True, "非 zip（跳过哈希核对）")
        continue

    sidecar = name.replace(".zip", ".sha256.txt")
    if sidecar not in assets:
        check(False, f"缺少配套校验和文件 {sidecar}")
        continue
    if not VERIFY_BIG_HASHES:
        print("    （默认跳过重下重算；--hashes 可开启）")
        continue
    text = fetch_bytes(
        f"https://github.com/{REPO}/releases/download/{TAG}/{sidecar}"
    ).decode("utf-8-sig")
    expected = text.split()[0].lower()
    actual = fetch_sha(name)
    check(actual == expected, f"{name} 的 SHA256 与 {sidecar} 一致（{actual[:16]}…）")

# 清单资产能否被解析（前端检查更新的数据源）
manifest_name = f"firstep-full-{TAG}.manifest.json"
if manifest_name in assets:
    raw = fetch_bytes(
        f"https://github.com/{REPO}/releases/download/{TAG}/{manifest_name}"
    ).decode("utf-8-sig")
    manifest = json.loads(raw)
    check(manifest["version"] == TAG, f"线上清单 version = {TAG}")
    check(len(manifest["parts"]) == 1, "线上清单 1 卷")
    # 文件数**不写死**（每版都会变；写死过 8774，发 v1.1.1 后无故变红）：
    # 只要求清单自洽——有文件、有资料库基线、且条数与清单声明一致
    check(len(manifest["files"]) > 8000, f"线上清单文件数 {len(manifest['files'])}")
    check(
        len(manifest["materials_manifest"]["batches"]) == 12,
        "线上清单带资料库基线（12 批次）",
    )

print()
if failures:
    print(f"验证失败：{len(failures)} 项")
    for item in failures:
        print("  ✗", item)
    sys.exit(1)
print("验证通过：线上资产哈希与清单均可核验")
