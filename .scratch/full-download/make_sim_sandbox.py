"""搭一个「模拟用户机」沙箱：瘦身但同构的 firstep 安装副本。

**当前沙箱的状态与使用注意见 `docs/agents/local-environment.md`**（沙箱在哪、哪些是
故意造假的、本机在跑哪些端口、main 与线上发布包的落差都记在那里——改完沙箱记得回去改那份）。

复制内容（对应真实用户的工具根）：
  src / library / docs / assets / tools / tests / .githooks / 根级脚本与配置（tracked 部分）
  sources/materials 的两个目录（每个只取一个真实文件）+ **一个第三方安装包**（干扰件，
  校验更新后不被误删）
  一个真实的空目录 library/fix-backups（本地备份目录，不该进包）

排除：.git / .scratch / node_modules / __pycache__ / 缓存 / 5.4 GB 第三方安装包主体
不建 .venv（沙箱用系统 Python 跑，避免下载依赖；不影响被验证的链路）
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

SRC = Path(r"C:\Users\luoji\Desktop\firstep")
DST = Path(r"C:\Users\luoji\Desktop\firstep-sim")
DATA = Path(r"C:\Users\luoji\.contest_generator_sim")

SKIP_DIRS = {
    ".git", ".scratch", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".venv", "fix-backups", "revise-backups", ".trash-pdf",
    ".claude", "_pycache_",
}


def copy_tree(relative: str) -> int:
    source = SRC / relative
    target = DST / relative
    if not source.exists():
        return 0
    count = 0
    for path in source.rglob("*"):
        parts = set(path.relative_to(source).parts)
        if parts & SKIP_DIRS:
            continue
        if not path.is_file():
            continue
        dest = target / path.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        count += 1
    return count


def main() -> int:
    if DST.exists():
        print(f"沙箱已存在，先删除：{DST}")
        shutil.rmtree(DST, ignore_errors=True)
    DST.mkdir(parents=True)

    total = 0
    for relative in ("src", "library", "docs", "assets", "tools", "tests", ".githooks"):
        copied = copy_tree(relative)
        total += copied
        print(f"  {relative:12} {copied:5} 个文件")
    for name in (
        ".gitattributes", ".gitignore", "CLAUDE.md", "README.md", "CONTEXT.md",
        "CHANGELOG.md", "VERSIONS.md", "pyproject.toml",
        "install.bat", "start-app.bat", "start-app.vbs", "stop-firstep.bat",
        "stop-firstep.vbs",
    ):
        source = SRC / name
        if source.is_file():
            shutil.copy2(source, DST / name)
            total += 1
    print(f"  根级文件     12 个")

    # 资料库：两个真实目录各取一个文件（够 check/基线/落位断言用）
    materials_pairs = [
        ("2026_08_MSPM0G3507与常用芯片手册", "MSPM0G3507用户指南(中文).pdf"),
        ("2026_08_STM32F103手册", None),
    ]
    materials_root = SRC / "sources" / "materials"
    target_root = DST / "sources" / "materials"
    for dirname, filename in materials_pairs:
        source_dir = materials_root / dirname
        if not source_dir.is_dir():
            print(f"  （缺资料库目录 {dirname}，跳过）")
            continue
        if filename:
            source_file = source_dir / filename
        else:
            candidates = sorted(p for p in source_dir.rglob("*") if p.is_file())
            source_file = candidates[0] if candidates else None
        if source_file is None or not source_file.is_file():
            print(f"  （{dirname} 没找到文件，跳过）")
            continue
        dest = target_root / dirname / source_file.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, dest)
        total += 1
        print(f"  资料库        {dirname}/{source_file.name}（{source_file.stat().st_size / 1048576:.1f} MB）")

    # 干扰件：第三方安装包（更新后必须原地不动）
    installer_dir = target_root / "2026_04_地猛星电赛控制题配套资料"
    installer_dir.mkdir(parents=True, exist_ok=True)
    installer = installer_dir / "01_CCS_20.5.0.00028_win.zip"
    installer.write_text("模拟第三方安装包（不该进包、也不该被更新删掉）", encoding="utf-8")
    print(f"  干扰件        {installer.name}（{installer.stat().st_size} B）")

    # 本地备份目录（不该进包）
    (DST / "library" / "fix-backups" / "20260101-000000").mkdir(parents=True, exist_ok=True)
    (DST / "library" / "fix-backups" / "20260101-000000" / "main.c").write_text("旧备份\n", encoding="utf-8")

    # 用户数据目录（独立，不碰真身）
    if DATA.exists():
        shutil.rmtree(DATA, ignore_errors=True)
    (DATA / "updates").mkdir(parents=True)
    (DATA / "config.json").write_text(
        '{\n  "deepseek_api_key": "sk-simulated-for-test",\n  "modules_dir": "'
        + str(DST / "library" / "modules").replace("\\", "\\\\")
        + '",\n  "masters_dir": "'
        + str(DST / "library" / "masters").replace("\\", "\\\\")
        + '"\n}\n',
        encoding="utf-8",
    )
    (DATA / "recent.json").write_text('{"items": [{"name": "模拟的最近工程"}]}\n', encoding="utf-8")
    (DATA / "tasks-simulated.json").write_text('{"note": "模拟的任务状态，更新后必须还在"}\n', encoding="utf-8")
    print(f"  用户数据      {DATA}（config.json + recent.json + tasks-simulated.json）")

    size_mb = sum(p.stat().st_size for p in DST.rglob("*") if p.is_file()) / 1048576
    print(f"\n沙箱就绪：{DST}（{total} 个文件 / {size_mb:.1f} MB）")
    print(f"沙箱数据目录：{DATA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
