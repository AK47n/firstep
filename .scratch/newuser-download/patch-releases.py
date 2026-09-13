"""重写三个 GitHub Release 的说明正文（工单 newuser-download/06）。

**为什么**：README 已经改成「新用户只下一个文件」，但 Release 页还挂着旧说明——
v1.0.0 那个 release 的正文写着「完整包 = ... 约 6.2 GB / 4 个 7z 分卷」，
而新用户从 README 的 `/releases/latest` 链接进来第一眼看的就是这里。**文档改一半等于没改。**

口径（与 README、`docs/agents/releasing.md` 的模板一致）：
- 每条 release 的**前两行固定**：新用户只下哪个文件 / 已装用户走工具内更新；
- 中间的历史内容**保留**（不删改历史），只在其上追加；
- v1.0.0 标注为历史归档，说明为什么别再照它做。

脚本幂等：已经加过标记（`> **新用户**`）的 release 跳过，可重复运行。
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

REPO = "AK47n/firstep"
NEWCOMER_BLOCK = (
    "> **新用户**：只下 [`firstep-full-v1.1.1.zip`](https://github.com/AK47n/firstep/releases/latest/download/firstep-full-v1.1.1.zip)"
    "（约 821 MB）——Windows 右键「全部解压缩」即可，**不用装 7-Zip**；"
    "解压后**第一个文件就是 `00-START-HERE.txt`**，照它走三步。\n"
    "> **已装用户**：不用看这里——打开工具「设置 → 软件更新 → 检查更新 → 一键更新」。\n"
)


def gh(*args: str) -> str:
    out = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=180)
    if out.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} 失败：{out.stderr}")
    return out.stdout


def view(tag: str) -> dict:
    return json.loads(gh("release", "view", tag, "--json", "name,body"))


def edit(tag: str, body: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8", newline="\n") as fh:
        fh.write(body)
        path = fh.name
    try:
        gh("release", "edit", tag, "--notes-file", path, "--repo", REPO)
    finally:
        Path(path).unlink(missing_ok=True)


def patch_v111(body: str) -> str:
    """最新版：标题行后插入新用户指引（正文其余部分原样保留）。"""
    header = "# firstep 电赛工程生成器 · v1.1.1\n"
    assert body.startswith(header), "v1.1.1 正文首行不是预期标题"
    rest = body[len(header):]
    return f"{header}\n{NEWCOMER_BLOCK}{rest}"


def patch_v110(body: str) -> str:
    """上一版：加「已被取代」提示 + 新用户指引。"""
    header = "# firstep 电赛工程生成器 · v1.1.0\n"
    assert body.startswith(header), "v1.1.0 正文首行不是预期标题"
    warning = (
        "\n> ⚠️ **本版已被 [v1.1.1](https://github.com/AK47n/firstep/releases/tag/v1.1.1) 取代**："
        "v1.1.0 的「下载完整 firstep」会白下 783 MB 且不做替换。已装 v1.1.0 的用户请到"
        "「设置 → 软件更新 → 检查更新 → 一键更新」升到 v1.1.1；新用户请直接下最新版。\n\n"
    )
    return f"{header}{warning}{NEWCOMER_BLOCK}{body[len(header):]}"


def patch_v100(body: str) -> str:
    """首个完整包：标注历史归档 + 说明为什么别再照它做。"""
    header = "# firstep 电赛工程生成器 · 完整包 v1.0.0\n"
    assert body.startswith(header), "v1.0.0 正文首行不是预期标题"
    archive = (
        "\n> ## ⚠️ 历史归档，不要照这一页做\n"
        ">\n"
        "> 这是 2026-08-30 的**首个完整包**，形态是「4 个 7z 分卷、约 6.2 GB、需要 7-Zip」，"
        "而且**不含** v1.1.0 起才有的增量更新能力。\n"
        "> **新用户请到 [最新版](https://github.com/AK47n/firstep/releases/latest) 下单个 zip**"
        "（约 821 MB，系统自带解压即可，包内 `00-START-HERE.txt` 带你三步装好）。\n"
        ">\n"
        "> 这一页保留，只为「已经装的是 v1.0.0、想原地补齐」的人。\n\n"
    )
    return f"{header}{archive}{body[len(header):]}"


PATCHERS = {"v1.1.1": patch_v111, "v1.1.0": patch_v110, "v1.0.0": patch_v100}


def main() -> int:
    for tag, patcher in PATCHERS.items():
        body = view(tag)["body"]
        if "> **新用户**" in body or "历史归档" in body:
            print(f"  [跳过] {tag}：已改过（幂等）")
            continue
        new_body = patcher(body)
        edit(tag, new_body)
        after = view(tag)["body"]
        assert "> **新用户**" in after or "历史归档" in after, f"{tag} 改完没生效"
        print(f"  [已改] {tag}：{len(body)} → {len(after)} 字符")
    print("\n=== 复核：三个 release 现在的首几行 ===")
    for tag in PATCHERS:
        body = view(tag)["body"]
        lines = [ln for ln in body.splitlines() if ln.strip()][:4]
        print(f"  --- {tag} ---")
        for ln in lines:
            print(f"    {ln[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
