"""包内抽检 + 两个 zip 实算 sha256（发版 v1.4.3，工单 04）。

照 `docs/agents/releasing.md` 的清单来，判据全部**从包里读**（不读工作树）：
  1. `VERSIONS.md` 首块 = `## v1.4.3 (2026-10-01)`；
  2. `src/contest_generator/__init__.py` 的 `__version__ = "1.4.3"`；
  3. 不该进包的三处**命中 0**：`.scratch/` / `.venv/` / `sources/materials/`；
  4. 完整包里 `00-START-HERE.txt` 在场（README 只指这一个入口）；
  5. 两个 zip **实算 sha256** 与各自 `.sha256.txt` 里写的值逐字相同；
  6. 顺带报条目数与解压总字节（与上一版对照用）。

跑法（仓库根）：`python .scratch\\release-v1.4.3\\check-packs.py`
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import sys
import zipfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PACK = pathlib.Path.home() / "Desktop" / "firstep-pack"
UPDATE = PACK / "firstep-update-v1.4.3.zip"
FULL = PACK / "firstep-full-v1.4.3.zip"
TAG = "v1.4.3"
DATE = "2026-10-01"
# ⚠ 口径（第一版在这里白红过一条）：`sources/materials` **只对更新包**是禁止面——
# **完整包本来就带资料库内容文件**（12 批次 / 5066 个文件，新用户唯一的安装包）。
# 两个包共有的禁止面只有 `.scratch/` 与 `.venv/`。
FORBIDDEN_BOTH = (".scratch/", ".venv/")
FORBIDDEN_UPDATE_ONLY = ("sources/materials/",)
FORBIDDEN = FORBIDDEN_BOTH + FORBIDDEN_UPDATE_ONLY  # 打印用（更新包口径）

problems: list[str] = []


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def declared(path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\b([0-9a-f]{64})\b", text)
    return match.group(1) if match else ""


def check_zip(path: pathlib.Path) -> None:
    print("=" * 100)
    print(f"§ {path.name}（{path.stat().st_size:,} B = {path.stat().st_size / 1048576:.1f} MB）")
    print("=" * 100)
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        total = sum(info.file_size for info in zf.infolist())
        print(f"  条目 {len(names):,} 个 / 解压后 {total:,} B = {total / 1048576:.1f} MB")

        forbidden = FORBIDDEN_BOTH + (FORBIDDEN_UPDATE_ONLY if path is UPDATE else ())
        hits = sorted({n for n in names for bad in forbidden if n.startswith(bad) or f"/{bad}" in n})
        ok = not hits
        scope = "更新包口径（含 sources/materials）" if path is UPDATE else "完整包口径（资料库内容文件本来就该在）"
        print(f"  {'[OK]' if ok else '[!!]'} 不该进包的内容命中 {len(hits)}——口径：{scope}"
              + ("" if ok else f"：{hits[:5]}"))
        if not ok:
            problems.append(f"{path.name} 混进不该进包的内容：{hits[:5]}")

        if path is FULL:
            start = [n for n in names if n.endswith("00-START-HERE.txt")]
            print(f"  {'[OK]' if start else '[!!]'} 00-START-HERE.txt 在包内：{start[:2]}")
            if not start:
                problems.append("完整包里没有 00-START-HERE.txt（新用户唯一入口）")

        versions = next((n for n in names if n.endswith("VERSIONS.md") and n.count("/") <= 1), None)
        if versions:
            head = zf.read(versions).decode("utf-8", "replace").splitlines()
            first = next((ln.strip() for ln in head if ln.startswith("## v")), "")
            want = f"## {TAG} ({DATE})"
            ok = first == want
            print(f"  {'[OK]' if ok else '[!!]'} {versions} 首块 = {first!r}（应为 {want!r}）")
            if not ok:
                problems.append(f"{path.name} 的 VERSIONS.md 首块不是 {want}")
        else:
            problems.append(f"{path.name} 里找不到 VERSIONS.md")
            print("  [!!] 找不到 VERSIONS.md")

        init = next((n for n in names if n.endswith("contest_generator/__init__.py")), None)
        if init:
            body = zf.read(init).decode("utf-8", "replace")
            match = re.search(r'__version__\s*=\s*"([^"]+)"', body)
            got = match.group(1) if match else "?"
            ok = got == TAG.lstrip("v")
            print(f"  {'[OK]' if ok else '[!!]'} {init} → __version__ = {got!r}（应为 {TAG.lstrip('v')!r}）")
            if not ok:
                problems.append(f"{path.name} 的 __version__ = {got}")
        else:
            problems.append(f"{path.name} 里找不到 __init__.py")

    side = path.with_suffix(".sha256.txt")
    real = sha256_of(path)
    want = declared(side)
    ok = bool(want) and real == want
    print(f"  {'[OK]' if ok else '[!!]'} 实算 sha256 = {real}")
    print(f"       {side.name} 写的 = {want or '（读不到）'}")
    if not ok:
        problems.append(f"{path.name} 实算 sha256 与 {side.name} 不一致")


def main() -> int:
    for path in (UPDATE, FULL):
        if not path.is_file():
            print(f"缺包：{path}")
            return 2
        check_zip(path)
    print("=" * 100)
    if problems:
        print("结论：有问题")
        for item in problems:
            print(f"  · {item}")
        return 1
    print("结论：抽检全过（版本块 / __version__ / 禁止面 0 / START-HERE / 两个 sha256）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
