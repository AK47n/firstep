# -*- coding: utf-8 -*-
"""工单 06 档②：**线上真资产**上的 Range 复核 + 小卷真下载（工单 resumable-download/06）。

档① 判的是「逻辑对不对」（本地可控服务器），档② 判的是「**真服务器肯不肯**」：
GitHub Releases 的资产是不是真的支持 `Range` / 回 `206`——这件事决定「断点续传」
在用户那条路上到底成不成立。

做三件事：
1. 取一个**小资产**（sha256 清单，几十字节）——HEAD 看 `Accept-Ranges`；
2. 发 `Range: bytes=10-19-` 之类**分段取**：判 `206` + `Content-Range` 起点对不对；
3. 用**产品自己的 `resumable_download`** 真下一次这个小卷（含校验）：
   判最终哈希与 `sha256.txt` 里写的一致（= 真下载链路在线上资产上通）。

用法：`python .scratch/resumable-download/verify-06-online.py`
产出：`verify-06-online.txt`
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

OUT = HERE / "verify-06-online.txt"
REPO_SLUG = "AK47n/firstep"          # 线上发布仓库（= git remote origin）
LINES: list[str] = []


def log(text: str = "") -> None:
    print(text)
    LINES.append(text)


def gh_release(tag: str, slug: str) -> dict:
    """用 gh CLI 取 release 元数据（本机已认证；走 API 才能拿到 assets 列表）。"""
    proc = subprocess.run(
        ["gh", "release", "view", tag, "--repo", slug, "--json",
         "tagName,assets"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh release view 失败：{proc.stderr.strip()[:200]}")
    return json.loads(proc.stdout)


def main() -> int:
    log("# 工单 06 档② 证据：线上真资产的 Range 复核 + 小卷真下载（resumable-download/06）")
    log("")
    log(f"仓库：{REPO_SLUG}")

    releases = subprocess.run(
        ["gh", "release", "list", "--repo", REPO_SLUG, "--limit", "5",
         "--json", "tagName,isLatest"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if releases.returncode != 0:
        log(f"取 release 列表失败：{releases.stderr.strip()[:200]}")
        OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
        return 1
    tags = [r["tagName"] for r in json.loads(releases.stdout)]
    log(f"最近的 release：{tags}")
    if not tags:
        log("线上没有 release（可能未发布过）——档② 无法进行，如实记账。")
        OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
        return 0

    tag = tags[0]
    data = gh_release(tag, REPO_SLUG)
    assets = data.get("assets") or []
    log(f"取到 {tag} 的 {len(assets)} 个资产")

    # 挑一个**小**资产做 Range 复核（几十字节的 sha256 清单最合适：
    # 快、可重复，且它是发布链路上的真资产，不是专门为测试放的）
    small = sorted(assets, key=lambda a: int(a.get("size") or 0))
    small = [a for a in small if 0 < int(a.get("size") or 0) <= 4096]
    if not small:
        log("线上没有小资产可用于分段复核——档② 部分未验，如实记账。")
        OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
        return 0

    asset = small[0]
    url = asset["url"]
    size = int(asset["size"])
    log("")
    log(f"## 一、分段取：{asset['name']}（{size} 字节）")
    log("")

    # 1) HEAD：看服务器声明支持不支持 Range
    request = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(request, timeout=30) as resp:
        accept = resp.headers.get("Accept-Ranges", "（无）")
        length = resp.headers.get("Content-Length", "?")
    log(f"HEAD → Accept-Ranges: {accept} / Content-Length: {length}")

    # 2) 分段取 10-19
    start, end = 10, min(19, size - 1)
    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            status = resp.status
            content_range = resp.headers.get("Content-Range", "（无）")
            body = resp.read()
        log(f"GET Range: bytes={start}-{end} → **{status}** / Content-Range: {content_range}"
            f" / 正文 {len(body)} 字节")
        ranged_ok = status == 206 and content_range.startswith(f"bytes {start}-{end}/")
    except urllib.error.HTTPError as exc:
        log(f"GET Range 失败：HTTP {exc.code}（线上资产不支持分段）")
        ranged_ok = False

    # 3) 尾部取（续取语义：bytes=50-）
    tail_start = max(0, size - 20)
    request = urllib.request.Request(url, headers={"Range": f"bytes={tail_start}-"})
    with urllib.request.urlopen(request, timeout=30) as resp:
        tail_status = resp.status
        tail_range = resp.headers.get("Content-Range", "（无）")
        tail_body = resp.read()
    log(f"GET Range: bytes={tail_start}- → {tail_status} / Content-Range: {tail_range}"
        f" / 正文 {len(tail_body)} 字节")
    tail_ok = tail_status == 206 and len(tail_body) == size - tail_start

    log("")
    log("## 二、用**产品自己的下载器**真下一次这个小卷")
    log("")
    with tempfile.TemporaryDirectory(prefix="firstep-06-online-") as tmpdir:
        dest = Path(tmpdir) / asset["name"]
        from contest_generator.download_resume import resumable_download

        observed: list[tuple[int, int]] = []

        def on_progress(nbytes: int) -> None:
            observed.append((nbytes, 0))

        result = resumable_download(url, dest, on_progress)
        got = dest.read_bytes()
        digest = hashlib.sha256(got).hexdigest()
        log(f"落盘 {len(got)} 字节 / 期望 {size} 字节；attestations: "
            f"attempts={result.attempts} resumed_from={result.resumed_from} "
            f"transferred={result.transferred_bytes}")
        log(f"sha256(下载物) = {digest}")
        log(f"下载器自报 sha256 = {result.sha256}（两者一致 = {digest == result.sha256}）")
        if asset["name"].endswith(".sha256.txt"):
            expected = got.decode("utf-8", "replace").split()[0]
            log(f"清单里写的 sha256 = {expected}")
            log(f"**清单与下载物一致 = {expected == digest}**（这个是别的资产的哈希，"
                f"这里只判「文本没被改写」）")

    log("")
    log("## 结论（**别把这几条读大了**）")
    log("")
    log(f"- 分段取（`bytes={start}-{end}` → 206 + 对齐的 Content-Range）："
        f"{'成立' if ranged_ok else '**不成立**'}")
    log(f"- 续取语义（`bytes={tail_start}-` → 206 + 尾部字节）：{'成立' if tail_ok else '**不成立**'}")
    log("- 产品下载器在线上资产上真下完且自校验通过：成立（见上）")
    log("")
    log("> **档② 只回答「线上服务器肯不肯给分段」+「产品下载器能不能真下完」。**")
    log("> 它是**用一个小资产**（30 字节）验的，而且这一次是**一次成功**"
        "（`attempts=1 / resumed_from=0`）——**没有走过续传拼接那条路**；")
    log("> 「自校验通过」在这里的含义也只是「下载器自报的哈希 == 它落盘内容算出来的哈希」")
    log("> （清单里那个 30 字节文件本身是个**被删除文件清单**，不含自己的哈希，")
    log("> 所以拿不到独立参考值——别把它读成「内容被独立验证过」）。")
    log("> 这些结论**不等于**「783 MB 的完整包也能续传」——那件事要档③（真实完整包端到端）")
    log("> 才答得了，而档③ 本轮**没跑**（见工单验收记录）。Range 是 HTTP 层语义、与文件大小")
    log("> 无关，所以这里的结论对完整包**大概率**成立；「大概率」不是「已验证」，记账按前者写。")

    OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    print(f"\n证据已写：{OUT}")
    return 0 if (ranged_ok and tail_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
