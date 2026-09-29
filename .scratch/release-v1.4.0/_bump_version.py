# -*- coding: utf-8 -*-
"""发版 v1.4.0：三处版本号 + README 当前/上一版行 + VERSIONS.md 新区块 + `tests/test_changelog.py` 夹具。

口径照 `docs/agents/releasing.md`「发版前：三处版本号同步（必做）」：
`__init__.py`（唯一可信来源，注释里写着"发版时三处同步"）/ `pyproject.toml` /
`README.md` 当前版本行 + `VERSIONS.md` 区块。

`tests/test_changelog.py::test_load_versions_real_file_reflects_released_versions` 的期望列表
是「当时那一版」的夹具——用例自己的说明写着「下个版本发布时更新此断言（追加而非替换）」，
所以这里**追加** v1.4.0 并更新最新版日期，不替换任何既有项。

换行纪律（`docs/agents/local-environment.md` §0）：`core.autocrlf=true`，本工作树的文本文件
盘上是 CRLF、blob 里是 LF——一律 `newline=""` 逐字节读写，锚点只写单行（不跨行），
插入 VERSIONS.md 新区块时按文件**实际**换行拼。
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERSION = "1.4.0"
DATE = "2026-09-29"

# 用户视角要点（VERSIONS.md 顶部区块）：这一轮用户能看见的是**全站观感**
# ——字号档位 / 描边层级 / 间距；另三条是同一批里用户摸得到的（体积数字 / 词表 / 并发写）。
VERSIONS_BLOCK = """## v{V} ({D})
- 主题：十四个页面终于长成一套——字号、描边、间距全站统一
- 改进：**全站一套字号档位**。以前每一页各写各的（光字号就有 13 种写死的取值），同一个「正文」在 A 页 13px、B 页 14px；现在收进六个档位（大标题 22 / 页面标题 20 / 小节标题 16 / 正文 14 / 说明 13 / 标签 12），十四个页签一致
- 改进：**一屏只有一层完整描边，重点靠左边一条色条跳出来**。以前是框套框，一层又一层的边框反而把重点埋掉；现在分组、警示、当前项改用「左条 + 字重」表达，整圈框只留一层
- 改进：**间距走同一套刻度**。卡片内边距、块与块的距离、行距不再一页一个数——翻页时不再有「这是另一个工具」的感觉
- 修复：**更新面板里的体积数字改成实测值**。原来写着「6.2 GB」「5 GB+」「约 1 GB」，实测是「约 800 MB」「约 0.7 GB」「约 800 MB」（你按这个数判断要下多久）
- 修复：**模块说明里那句没依据的「预热 3-5 分钟」删了**（MQ 系列九件的手册里没有这条），换成有据的措辞
- 改进：**本地记录的并发写更稳**——想法草稿 / 想法商量 / 参数表 / 母版元数据 / 检测记录收进同一套写法，多开窗口同时改不再可能写出半截 JSON
""".format(V=VERSION, D=DATE)

EDITS = [
    (
        "src/contest_generator/__init__.py",
        '__version__ = "1.3.1"  # 与 GitHub Release v1.3.1 对齐；发版时三处同步'
        "（本文件 / pyproject.toml / README 当前版本）",
        f'__version__ = "{VERSION}"  # 与 GitHub Release v{VERSION} 对齐；发版时三处同步'
        "（本文件 / pyproject.toml / README 当前版本）",
    ),
    ("pyproject.toml", 'version = "1.3.1"', f'version = "{VERSION}"'),
    (
        "README.md",
        "- 当前版本：**v1.3.1**（含电赛资料库；2026-09-27 发布——页面上的星号记号清了"
        "（库里的说明文字现在真的显示成加粗）；两处「失败」各说各的实话；板载 LED 脚跟着板定义走；"
        "多实例件如实说「只验第一路」；键盘与读屏用户走得通了）",
        f"- 当前版本：**v{VERSION}**（含电赛资料库；{DATE} 发布——十四个页面终于是一套观感："
        "统一的字号档位、一屏一层完整描边、间距走同一套刻度；更新面板的体积数字改成实测值；"
        "模块说明里那句没依据的「预热 3-5 分钟」删了）",
    ),
    (
        "README.md",
        "- 上一版：v1.3.0（2026-09-25 发布——新增「硬件检测」栏目，先验硬件再做题；"
        "30 件器件有专精检测、库外的器件也能自己登记着测；地猛星生成的工程烧进去外设真的初始化了；"
        "三处库内驱动缺陷修掉）",
        "- 上一版：v1.3.1（2026-09-27 发布——页面上的星号记号清了（库里的说明文字现在真的显示成加粗）；"
        "两处「失败」各说各的实话；板载 LED 脚跟着板定义走；多实例件如实说「只验第一路」；"
        "键盘与读屏用户走得通了）",
    ),
    (
        "tests/test_changelog.py",
        '"""真实 VERSIONS.md：已发布 v1.3.1 / v1.3.0 / v1.2.2 / v1.2.1 / v1.2.0 / v1.1.1'
        '（六块进前台，v1.1.0 与 v1.0.0 沉到「更多」）。',
        '"""真实 VERSIONS.md：已发布 v1.4.0 / v1.3.1 / v1.3.0 / v1.2.2 / v1.2.1 / v1.2.0'
        '（六块进前台，v1.1.1 及更早沉到「更多」）。',
    ),
    (
        "tests/test_changelog.py",
        'assert versions == ["v1.3.1", "v1.3.0", "v1.2.2", "v1.2.1", "v1.2.0", "v1.1.1", '
        '"v1.1.0", "v1.0.0"], f"VERSIONS.md 版本块与顺序：{versions}"',
        f'assert versions == ["v{VERSION}", "v1.3.1", "v1.3.0", "v1.2.2", "v1.2.1", "v1.2.0", '
        '"v1.1.1", "v1.1.0", "v1.0.0"], f"VERSIONS.md 版本块与顺序：{versions}"',
    ),
    (
        "tests/test_changelog.py",
        'assert releases[0]["date"] == "2026-09-27", "最新版日期"',
        f'assert releases[0]["date"] == "{DATE}", "最新版日期"',
    ),
]

VERSIONS_ANCHOR = "## v1.3.1 (2026-09-27)"


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
