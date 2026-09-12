"""定性：小发版包与完整包的同名文件差异是「换行符」还是「真实内容」？"""

from __future__ import annotations

import zipfile
from pathlib import Path

PACK = Path.home() / "Desktop" / "firstep-pack"
with zipfile.ZipFile(PACK / "firstep-update-v1.1.0.zip") as a, zipfile.ZipFile(
    PACK / "firstep-full-v1.1.0.zip"
) as b:
    up = {n for n in a.namelist() if not n.endswith("/")}
    full = {n for n in b.namelist() if not n.endswith("/")}
    common = sorted(up & full)
    raw_diff: list[str] = []
    eol_only: list[str] = []
    real_diff: list[str] = []
    for name in common:
        left = a.read(name)
        right = b.read(name)
        if left == right:
            continue
        raw_diff.append(name)
        # 归一化换行后再比：只差 CRLF/LF 的归入 eol_only
        if left.replace(b"\r\n", b"\n") == right.replace(b"\r\n", b"\n"):
            eol_only.append(name)
        else:
            real_diff.append(name)
    print(f"共有 {len(common)} 个文件；字节不同 {len(raw_diff)} 个")
    print(f"  其中仅换行符差异：{len(eol_only)} 个")
    print(f"  真实内容差异：{len(real_diff)} 个")
    for name in real_diff[:15]:
        print("    -", name)
    # 抽查一个真实差异文件的头部，看是谁新谁旧
    if real_diff:
        name = real_diff[0]
        left = a.read(name).decode("utf-8", "replace").splitlines()[:6]
        right = b.read(name).decode("utf-8", "replace").splitlines()[:6]
        print(f"\n抽查 {name}")
        print("  更新包：", left)
        print("  完整包：", right)
