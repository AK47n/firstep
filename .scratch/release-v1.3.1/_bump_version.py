# -*- coding: utf-8 -*-
"""发版 v1.3.1：三处版本号 + README 当前/上一版行 + VERSIONS.md 新区块 + `tests/test_changelog.py` 夹具。

口径照 `docs/agents/releasing.md`「发版前：三处版本号同步（必做）」：
`__init__.py`（唯一可信来源）/ `pyproject.toml` / `README.md` 当前版本行 + `VERSIONS.md` 区块。

`tests/test_changelog.py::test_load_versions_real_file_reflects_released_versions` 的期望列表
是「当时那一版」的夹具——用例自己的说明写着「下个版本发布时更新此断言（追加而非替换）」，
所以这里**追加** v1.3.1 并更新最新版日期，不替换任何既有项。

换行纪律（`docs/agents/local-environment.md` §0）：`core.autocrlf=true`，本工作树的文本文件
盘上是 CRLF、blob 里是 LF——一律 `newline=""` 逐字节读写，锚点只写单行（不跨行），
插入 VERSIONS.md 新区块时按文件**实际**换行拼。
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERSION = "1.3.1"
DATE = "2026-09-27"

VERSIONS_BLOCK = """## v{V} ({D})
- 主题：把页面上那些「星号」擦干净——库里的说明文字现在真的显示成加粗
- 修复：**页面上到处冒出来的 `**` 记号清了**。它来自两处——页面自己的文字 5 处，以及库数据里成对的标记（配方说明 2434 处、74 个模块的简介与平台备注 1844 处）；此前它们原样显示，你看到的是 `**未上板**` 而不是加粗的「未上板」
- 修复：**两处「失败」各说各的实话**：母版配置读不出来时给一句中文原因（不再含糊其辞）；检测记录读不出来时，不再被说成「记录坏了、删掉重填」
- 修复：**板载 LED 脚以你的选型数据为源**——改了板定义，检测页上的板载 LED 脚跟着变（此前写死在页面里）
- 改进：**多实例件（LED / 按键）如实说「只验第一路」**，不再默默只测一路
- 改进：**键盘与读屏用户走得通了**——勾完器件焦点留在原位、器件卡能用 Tab 到达、编译与烧录状态能被读屏念出
""".format(V=VERSION, D=DATE)

EDITS = [
    (
        "src/contest_generator/__init__.py",
        '__version__ = "1.3.0"  # 与 GitHub Release v1.3.0 对齐；发版时三处同步'
        "（本文件 / pyproject.toml / README 当前版本）",
        f'__version__ = "{VERSION}"  # 与 GitHub Release v{VERSION} 对齐；发版时三处同步'
        "（本文件 / pyproject.toml / README 当前版本）",
    ),
    ("pyproject.toml", 'version = "1.3.0"', f'version = "{VERSION}"'),
    (
        "README.md",
        "- 当前版本：**v1.3.0**（含电赛资料库；2026-09-25 发布——新增「硬件检测」栏目，先验硬件再做题；"
        "30 件器件有专精检测、库外的器件也能自己登记着测；地猛星生成的工程烧进去外设真的初始化了；"
        "三处库内驱动缺陷修掉）",
        f"- 当前版本：**v{VERSION}**（含电赛资料库；{DATE} 发布——页面上的星号记号清了"
        "（库里的说明文字现在真的显示成加粗）；两处「失败」各说各的实话；板载 LED 脚跟着板定义走；"
        "多实例件如实说「只验第一路」；键盘与读屏用户走得通了）",
    ),
    (
        "README.md",
        "- 上一版：v1.2.2（2026-09-19 发布——升级不再往你盘上写别人的库备份、不再漏发新增文件，"
        "校验失败不再留整卷残骸，持久「内容不符」半分钟内明确失败）",
        "- 上一版：v1.3.0（2026-09-25 发布——新增「硬件检测」栏目，先验硬件再做题；"
        "30 件器件有专精检测、库外的器件也能自己登记着测；地猛星生成的工程烧进去外设真的初始化了；"
        "三处库内驱动缺陷修掉）",
    ),
    (
        "tests/test_changelog.py",
        '"""真实 VERSIONS.md：已发布 v1.3.0 / v1.2.2 / v1.2.1 / v1.2.0 / v1.1.1 / v1.1.0'
        '（六块进前台，v1.0.0 沉到「更多」）。',
        '"""真实 VERSIONS.md：已发布 v1.3.1 / v1.3.0 / v1.2.2 / v1.2.1 / v1.2.0 / v1.1.1'
        '（六块进前台，v1.1.0 与 v1.0.0 沉到「更多」）。',
    ),
    (
        "tests/test_changelog.py",
        'assert versions == ["v1.3.0", "v1.2.2", "v1.2.1", "v1.2.0", "v1.1.1", "v1.1.0", "v1.0.0"], '
        'f"VERSIONS.md 版本块与顺序：{versions}"',
        f'assert versions == ["v{VERSION}", "v1.3.0", "v1.2.2", "v1.2.1", "v1.2.0", "v1.1.1", '
        '"v1.1.0", "v1.0.0"], f"VERSIONS.md 版本块与顺序：{versions}"',
    ),
    (
        "tests/test_changelog.py",
        'assert releases[0]["date"] == "2026-09-25", "最新版日期"',
        f'assert releases[0]["date"] == "{DATE}", "最新版日期"',
    ),
]

VERSIONS_ANCHOR = "## v1.3.0 (2026-09-25)"


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", newline="")


def write(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def main() -> int:
    for rel, old, new in EDITS:
        path = REPO / rel
        text = read(path)
        count = text.count(old)
        assert count == 1, f"{rel}：锚点命中 {count} 次（应为 1）——{old[:60]!r}"
        write(path, text.replace(old, new))
        print(f"已改 {rel}")

    # VERSIONS.md：新区块插在首个版本块之前（按文件实际换行拼）
    path = REPO / "VERSIONS.md"
    text = read(path)
    nl = "\r\n" if "\r\n" in text else "\n"
    assert text.count(VERSIONS_ANCHOR) == 1, "VERSIONS.md 首个版本块锚点不是 1 次"
    block = VERSIONS_BLOCK.replace("\n", nl)
    write(path, text.replace(VERSIONS_ANCHOR, block + VERSIONS_ANCHOR, 1))
    print(f"已改 VERSIONS.md（新区块 v{VERSION} ({DATE})，换行 = {'CRLF' if nl == chr(13) + chr(10) else 'LF'}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
