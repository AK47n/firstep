# -*- coding: utf-8 -*-
"""发版 v1.3.0：三处版本号 + README 当前版本行 + `tests/test_changelog.py` 的版本列表。

口径照 `docs/agents/releasing.md`「发版前：三处版本号同步（必做）」：
`__init__.py`（唯一可信来源）/ `pyproject.toml` / `README.md` 当前版本行 + `VERSIONS.md` 区块
（VERSIONS.md 由 `_write_versions_block.py` 单独写，因为它要归纳 CHANGELOG）。

`tests/test_changelog.py::test_load_versions_real_file_reflects_released_versions` 的期望列表
是「当时那一版」的夹具——用例自己的说明写着「下个版本发布时更新此断言（追加而非替换）」，
所以这里**追加** v1.3.0 并更新最新版日期，不替换任何既有项。
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERSION = "1.3.0"
DATE = "2026-09-25"

EDITS = [
    (
        "src/contest_generator/__init__.py",
        '__version__ = "1.2.2"  # 与 GitHub Release v1.2.2 对齐；发版时三处同步'
        "（本文件 / pyproject.toml / README 当前版本）",
        f'__version__ = "{VERSION}"  # 与 GitHub Release v{VERSION} 对齐；发版时三处同步'
        "（本文件 / pyproject.toml / README 当前版本）",
    ),
    ("pyproject.toml", 'version = "1.2.2"', f'version = "{VERSION}"'),
    (
        "README.md",
        "- 当前版本：**v1.2.2**（含电赛资料库；2026-09-19 发布——升级不再往你盘上写别人的库备份、"
        "不再漏发新增文件，校验失败不再留整卷残骸，持久「内容不符」半分钟内明确失败）\n"
        "- 上一版：v1.2.1（2026-09-16 发布，2026-09-19 重发——补回 MSPM0（CCS）工程缺的编码设置文件，"
        "中文注释不再有乱码风险）",
        "- 当前版本：**v1.3.0**（含电赛资料库；2026-09-25 发布——新增「硬件检测」栏目，先验硬件再做题；"
        "30 件器件有专精检测、库外的器件也能自己登记着测；地猛星生成的工程烧进去外设真的初始化了；"
        "三处库内驱动缺陷修掉）\n"
        "- 上一版：v1.2.2（2026-09-19 发布——升级不再往你盘上写别人的库备份、不再漏发新增文件，"
        "校验失败不再留整卷残骸，持久「内容不符」半分钟内明确失败）",
    ),
    (
        "tests/test_changelog.py",
        '"""真实 VERSIONS.md：已发布 v1.2.2 / v1.2.1 / v1.2.0 / v1.1.1 / v1.1.0 / v1.0.0'
        '（六块都进前台）。',
        '"""真实 VERSIONS.md：已发布 v1.3.0 / v1.2.2 / v1.2.1 / v1.2.0 / v1.1.1 / v1.1.0'
        '（六块进前台，v1.0.0 沉到「更多」）。',
    ),
    (
        "tests/test_changelog.py",
        'assert versions == ["v1.2.2", "v1.2.1", "v1.2.0", "v1.1.1", "v1.1.0", "v1.0.0"], '
        'f"VERSIONS.md 版本块与顺序：{versions}"',
        'assert versions == ["v1.3.0", "v1.2.2", "v1.2.1", "v1.2.0", "v1.1.1", "v1.1.0", "v1.0.0"], '
        'f"VERSIONS.md 版本块与顺序：{versions}"',
    ),
]


def main() -> int:
    for rel, old, new in EDITS:
        path = REPO / rel
        text = path.read_text(encoding="utf-8", newline="")
        count = text.count(old)
        assert count == 1, f"{rel}：锚点命中 {count} 次（应为 1）——{old[:60]!r}"
        path.write_text(text.replace(old, new), encoding="utf-8", newline="")
        print(f"已改 {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
