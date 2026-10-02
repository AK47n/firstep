# -*- coding: utf-8 -*-
"""发版 v1.4.4：三处版本号 + README 当前/上一版行 + VERSIONS.md 新区块 + `tests/test_changelog.py` 夹具。

口径照 `docs/agents/releasing.md`「发版前：三处版本号同步（必做）」：
`__init__.py`（唯一可信来源）/ `pyproject.toml` / `README.md` 当前版本行 + `VERSIONS.md` 区块。

`tests/test_changelog.py::test_load_versions_real_file_reflects_released_versions` 的期望列表
是「当时那一版」的夹具——用例自己的说明写着「下个版本发布时更新此断言（追加而非替换）」，
所以这里**追加** v1.4.4 并更新最新版日期，不替换任何既有项。

换行纪律（`docs/agents/local-environment.md` §0）：`core.autocrlf=true`，本工作树的文本文件
盘上是 CRLF、blob 里是 LF——一律 `newline=""` 逐字节读写，锚点只写单行（不跨行），
插入 VERSIONS.md 新区块时按文件**实际**换行拼。
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERSION = "1.4.4"
DATE = "2026-10-02"

# 用户视角要点（VERSIONS.md 顶部区块）：这一轮用户能看见的是**浅色主题下引脚卡片的配色**
# ——类型标 / 状态文字 / 板图引脚名 / 色点；另两条（暗色两处、内部加固）照发布说明稿。
VERSIONS_BLOCK = """## v{V} ({D})
- 主题：浅色主题下引脚卡片的配色变清楚了——类型标、状态文字、板图上的引脚名与色点
- 修复：**浅色主题下引脚卡片的配色变清楚了**：引脚配置卡上的类型标（spi / exti / i2c 那类小字）、「已绑 / 现绑」状态文字、板图上已绑引脚的**名字**、图例与菜单里的色点——以前浅色下这些字最低只有 1.40:1（spi / exti 1.45、i2c 1.40），几乎看不见；现在八个色族各有自己的浅色取值，实测文字最低 4.70:1、色点这类非文字最低 3.76:1，都过了 WCAG AA。**暗色主题只动了 enc / uart 两处**（提亮一档）
- 改进：**取色写法改了，好让判据看得见**（观感无变化）：这一族的根因不是颜色选错，是取色用模板变量拼在内联样式里、所有现成判据都看不见它——现在取色回到样式块，并补了一条「不许再用模板变量拼内联取色」的正向判据；另立一条判据盯着「每个颜色族在浅色主题下必须成套」，防止下次漏掉某一族
""".format(V=VERSION, D=DATE)

EDITS = [
    (
        "src/contest_generator/__init__.py",
        '__version__ = "1.4.3"  # 与 GitHub Release v1.4.3 对齐；发版时三处同步'
        "（本文件 / pyproject.toml / README 当前版本）",
        f'__version__ = "{VERSION}"  # 与 GitHub Release v{VERSION} 对齐；发版时三处同步'
        "（本文件 / pyproject.toml / README 当前版本）",
    ),
    ("pyproject.toml", 'version = "1.4.3"', f'version = "{VERSION}"'),
    (
        "README.md",
        "- 当前版本：**v1.4.3**（含电赛资料库；2026-10-01 发布——**三条被「变淡」压得看不清的话变清楚了**："
        "资源总览的「非硬件资源」行、库外建议 chip 的「⤵ N 方案」计数、被点掉的推荐 chip 上的理由，"
        "浅色最低从 3.52:1 抬到 5.25:1 以上；**浅色主题板图的「固定/电源」焊盘**从近黑改成与"
        "「空闲 IO」同一套浅灰，暗色不变）",
        f"- 当前版本：**v{VERSION}**（含电赛资料库；{DATE} 发布——**浅色主题下引脚卡片的配色变清楚了**："
        "引脚卡上的类型标、（已绑 / 现绑）状态文字、板图上已绑引脚的名字、图例与菜单里的色点，"
        "浅色最低从 1.40:1 抬到文字 4.70:1 / 色点 3.76:1 以上；**暗色主题只动了 enc / uart 两处**，"
        "其余照旧）",
    ),
    (
        "README.md",
        "- 上一版：v1.4.2（2026-10-01 发布——三处「不可选」形态的样子变了：模块卡上「需切换平台」的卡、"
        "引脚菜单里「不兼容：…」的行、参数表里「位置已变」的卡，从整块变淡改成灰底灰字 + 虚线描边，"
        "说明字最低从 2.16:1 抬到 5.25:1）",
        "- 上一版：v1.4.3（2026-10-01 发布——三条被「变淡」压得看不清的话变清楚了：资源总览的"
        "「非硬件资源」行、库外建议 chip 的「⤵ N 方案」计数、被点掉的推荐 chip 上的理由，"
        "浅色最低从 3.52:1 抬到 5.25:1 以上；浅色主题板图的「固定/电源」焊盘从近黑改成与"
        "「空闲 IO」同一套浅灰）",
    ),
    (
        "tests/test_changelog.py",
        '"""真实 VERSIONS.md：已发布 v1.4.3 / v1.4.2 / v1.4.1 / v1.4.0 / v1.3.1 / v1.3.0 / v1.2.2 / '
        'v1.2.1 / v1.2.0（八块进前台，v1.1.1 及更早沉到「更多」）。',
        '"""真实 VERSIONS.md：已发布 v1.4.4 / v1.4.3 / v1.4.2 / v1.4.1 / v1.4.0 / v1.3.1 / v1.3.0 / '
        'v1.2.2 / v1.2.1 / v1.2.0（九块进前台，v1.1.1 及更早沉到「更多」）。',
    ),
    (
        "tests/test_changelog.py",
        'assert versions == ["v1.4.3", "v1.4.2", "v1.4.1", "v1.4.0", "v1.3.1", "v1.3.0", "v1.2.2", '
        '"v1.2.1", "v1.2.0", "v1.1.1", "v1.1.0", "v1.0.0"], f"VERSIONS.md 版本块与顺序：{versions}"',
        f'assert versions == ["v{VERSION}", "v1.4.3", "v1.4.2", "v1.4.1", "v1.4.0", "v1.3.1", "v1.3.0", '
        '"v1.2.2", "v1.2.1", "v1.2.0", "v1.1.1", "v1.1.0", "v1.0.0"], '
        'f"VERSIONS.md 版本块与顺序：{versions}"',
    ),
    (
        "tests/test_changelog.py",
        'assert releases[0]["date"] == "2026-10-01", "最新版日期"',
        f'assert releases[0]["date"] == "{DATE}", "最新版日期"',
    ),
]

VERSIONS_ANCHOR = "## v1.4.3 (2026-10-01)"


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
