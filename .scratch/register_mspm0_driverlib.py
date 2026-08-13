"""把 TI MSPM0 SDK driverlib 例程注册为参考库条目（.scratch 工具脚本）。

源：C:\\ti\\mspm0_sdk_2_00_01_00\\examples\\nortos\\LP_MSPM0G3507\\driverlib
（149 例，152M——其中 35M+ 是 MSPM0G3507_MPU6050 例自带 SDK 副本树，不入库）。

入库范围（沿用 register_materials.py 规则：仅 UTF-8 文本）：
- 每例一条：title=例程目录名，type="TI MSPM0 SDK 例程"，platform=mspm0，
  anchor=none，description 取 README.md「Example Summary」段正文
- 文件：递归收 *.c / *.h / *.syscfg / *.md / *.txt
- 排除：工具链子目录（gcc/iar/keil/ticlang——构建胶水）、source/ti 与
  source/third_party（SDK 副本树）、*.html（README.md 重复）、empty* 空骨架
SDK 本体可重新获得（安装器在 C:\\ti），按素材保留规则不备份。

自动提交：跑前把 config.json 的 autocommit_enabled 置 false，跑完手动一条
提交（参考 8318b56「补录三批参考文件条目」先例，149 条不逐条进历史）。
幂等：标题已存在即跳过；跑完抽样回读校验。
配套：入库后跑 rename_mspm0_refs.py 把标题改中文直观名并删空工程模板
（重跑本脚本会按 SDK 目录名重新建条，跳过已存在的同名条目）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from contest_generator import config  # noqa: E402
from contest_generator.reference_library import (  # noqa: E402
    ANCHOR_KIND_NONE,
    PLATFORM_MSPM0,
    add_reference,
    get_reference,
    list_references,
)

SRC_ROOT = Path(r"C:\ti\mspm0_sdk_2_00_01_00\examples\nortos\LP_MSPM0G3507\driverlib")
# 参考库目录：与 webapp 同源推导（config 唯一出处，脚本不再硬编码）
REFERENCE_ROOT = config.reference_library_dir(REPO_ROOT / "library" / "modules")

TYPE = "TI MSPM0 SDK 例程"
TEXT_EXTS = (".c", ".h", ".syscfg", ".md", ".txt")
SKIP_PREFIXES = ("empty",)  # empty / empty_cpp / empty_driverlib_src 等空骨架
EXCLUDE_DIR_PARTS = {"gcc", "iar", "keil", "ticlang"}  # 工具链构建胶水
# SDK 副本树（例程自带整棵 ti/devices + CMSIS 源码，与安装器重复）
EXCLUDE_TREES = ("source/ti/", "source/third_party/")


def collect_text_files(example_dir: Path) -> tuple[dict[str, str], int]:
    """递归收集 UTF-8 文本文件（相对 POSIX 路径 → 内容）。

    二进制 / 非 UTF-8 跳过（素材规则：仅 UTF-8 文本入库）。
    """
    files: dict[str, str] = {}
    skipped_binary = 0
    for path in sorted(example_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
            continue
        rel = path.relative_to(example_dir).as_posix()
        parts = rel.split("/")
        if any(part in EXCLUDE_DIR_PARTS for part in parts):
            continue
        if rel.endswith(".html"):
            continue
        if any(rel.startswith(tree) for tree in EXCLUDE_TREES):
            continue
        try:
            files[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped_binary += 1
    return files, skipped_binary


def readme_summary(example_dir: Path, name: str) -> str:
    """README.md「Example Summary」段第一段正文；缺 README 时回退例程名。"""
    readme = example_dir / "README.md"
    if not readme.is_file():
        return f"TI MSPM0G3507 driverlib 例程（{name}）。"
    try:
        text = readme.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"TI MSPM0G3507 driverlib 例程（{name}）。"
    m = re.search(r"## Example Summary\s*\n(.*?)(?=\n## |\Z)", text, re.S)
    if not m:
        m = re.match(r"# .*?\n(.*?)(?=\n#|\Z)", text, re.S)
    body = (m.group(1) if m else text).strip()
    body = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", body)  # 链接去 URL
    first_para = body.split("\n\n", 1)[0].replace("\n", " ").strip()
    if not first_para:
        return f"TI MSPM0G3507 driverlib 例程（{name}）。"
    return first_para[:300]


def main() -> None:
    existing = {e.title for e in list_references(REFERENCE_ROOT)}
    added = skipped = 0
    total_bytes = 0
    first_added_id: str | None = None
    for example_dir in sorted(p for p in SRC_ROOT.iterdir() if p.is_dir()):
        name = example_dir.name
        if name.startswith(SKIP_PREFIXES):
            print(f"[跳过] 空骨架：{name}")
            continue
        if name in existing:
            print(f"[跳过] 条目已存在：{name}")
            skipped += 1
            continue
        files, bin_skipped = collect_text_files(example_dir)
        if not files:
            print(f"[警告] 无文本文件，未入库：{name}")
            continue
        entry = add_reference(
            REFERENCE_ROOT,
            title=name,
            type=TYPE,
            description=readme_summary(example_dir, name),
            anchor_kind=ANCHOR_KIND_NONE,
            anchor_value="",
            files=files,
            kit_vocabulary=(),
            platform=PLATFORM_MSPM0,
        )
        total_bytes += entry.size_bytes
        added += 1
        if first_added_id is None:
            first_added_id = entry.id
        note = f"（跳过二进制 {bin_skipped}）" if bin_skipped else ""
        print(
            f"[入库] {entry.id}  文件 {len(files)} 个  "
            f"{entry.file_count} files / {entry.size_bytes} bytes{note}"
        )
    print(f"\n完成：新增 {added} 条，已存在跳过 {skipped} 条，共 {total_bytes} bytes")
    if added and first_added_id:
        probe = get_reference(REFERENCE_ROOT, first_added_id)
        print(f"抽样回读：{probe.title}  {probe.platform}  {probe.files[:2]}")


if __name__ == "__main__":
    main()
