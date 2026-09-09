"""立创 wiki 素材来源标注结构测试（lckfb-attribution/01）。

遍历真实模块库：凡**源码头带来源标注块**（`source_notes` 注入的 `/* 来源：…`，
判据 = 代码事实）的 .c/.h → 该文件的平台条目 `source_url` 必须命中 wiki 判据
（`manifest.is_wiki_source_url` 单源）且**头部窗口含该条目自己的**原页 URL
（立创版权要求第三条——复制 / 传播 / 修改 / 公开展示须标明来源与链接的源码面
兜底），逐条目独立断言、不做跨条目互证；非 wiki 派生模块不要求。

**为什么不按 source_url 反推**（工单 identity-fields/03 修正）：`source_url` 是
硬件身份字段（购买 / 手册页），它**也能**标注代码来源，但两者不等价——本轮把
OLED / motor / xunji / pid / servo / k230 的硬件出处补成 wiki 手册页后，若仍按
`is_wiki_source_url(source_url)` 反推「wiki 派生」，这些**原生移植**的驱动会被
误要求补来源注释（`motor.c` 来自 2021F 原工程、`oled.c` 内嵌母版 ml_oled）。
判据改取代码事实（头部来源块）后：**有块 → 条目的 source_url 必须是该块所属的
wiki 页**（块是「本文件改写自该页」的声明，条目改指别处就是标注与身份脱钩，会红）；
**没有块 → 不要求**（原生移植代码不受 wiki 版权条款约束）。
两个方向都守：有块必须有 wiki source_url；条目 source_url 是 wiki 页且源码头部
引用了该页 → 必须有块。第三个方向是**覆盖面地板**：wiki 来源的模块数与文件数
不得低于 `WIKI_COVERAGE_FLOOR`（CONTEXT.md 不承诺数字，测试守事实不缩水）。

注入纯函数（source_notes.inject_source_note）幂等性单测。
不做的事：不断言注入注释块的确切文案（防脆——文案迭代时只断言 URL 存在 +
「来源」字样）；不遍历 sources/materials 手册（资料库可能轻量 clone 缺失，
非本库领域；手册头部「来源：」行由 wiki_md.py 抓取期写入，另有抓取测试守）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from contest_generator.manifest import (
    WIKI_SOURCE_URL_PREFIX,
    ModuleManifest,
    is_wiki_source_url,
)
from contest_generator.source_notes import (
    HEAD_WINDOW,
    inject_source_note,
    source_note_block,
)

LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"

WIKI_URL = "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/aht10-temp-humi-sensor.html"

# 来源标注块的机械判据（头部窗口内出现 `来源：` 注释）——与注入文案解耦：
# 文案改字不影响本判据，只要还是「来源：」注释块。
SOURCE_NOTE_MARKER = "来源："
_URL_RE = re.compile(r"https?://\S+")

# 顶部窗口（判定窗，单源 = source_notes.HEAD_WINDOW）：注入块在文件头，窗口取
# 600 字符足够宽松，防「只标在文件尾部 / notes 里」的伪合规；脚本幂等判据与
# 本测试共用同一常量（c2 判例：漂移 = 脚本报 0 变更 / 测试红灯）。

# 覆盖面地板（2026-09-09）：CONTEXT.md 不再写死「N 模块 M 文件」——无守卫的计数
# 必漂（56/115 → 71/268 已漂过一次），文档改述覆盖面口径，由本测试守「覆盖面
# 不缩水」：wiki 来源模块数与这些条目的 .c/.h 文件数不得低于地板。只判下界，
# 库增长不触发红；确需下调（模块下架 / 换来源）时改这里 = 显式决定而非静默漂移。
WIKI_COVERAGE_FLOOR = (71, 268)  # 2026-09-09 实测：71 模块 / 268 文件


def _head(text: str) -> str:
    return text[:HEAD_WINDOW]


def _source_note_files():
    """(slug, 平台, 相对文件路径, 文件对象, 头部窗口文本) —— 头部带来源标注块的
    .c/.h（判据 = 代码事实，不按 source_url 反推）。"""
    for manifest_path in sorted(LIBRARY_MODULES.glob("*/manifest.json")):
        manifest = ModuleManifest.load(manifest_path.parent)
        for platform, entry in manifest.platforms.items():
            for rel in entry.files:
                if not rel.endswith((".c", ".h")):
                    continue
                path = manifest_path.parent / rel
                if not path.is_file():
                    yield manifest.slug, platform, rel, path, ""
                    continue
                head = _head(path.read_text(encoding="utf-8", errors="replace"))
                if SOURCE_NOTE_MARKER in head:
                    yield manifest.slug, platform, rel, path, head


def test_wiki_derived_module_sources_carry_page_url():
    """源码头带来源标注块的文件：其平台条目 `source_url` 必须是 wiki 页（立创
    版权要求第三条的源码面兜底）。

    逐条目独立断言（不跨条目互证）。「块里写的页 = 条目 source_url 指的页」由
    `test_single_url_source_note_matches_entry_source_url` 单独守——本轮实测存在
    合法不等的两类：一个文件改写多页（`oled_extra_stm32.c`）、一条目对应多平台
    原页（`servo.h` 写 dkx 页、mspm0 条目指 dmx 页），故此处只判「是 wiki 页」。
    """
    problems: list[str] = []
    checked = 0
    for slug, platform, rel, _path, head in _source_note_files():
        manifest = ModuleManifest.load(LIBRARY_MODULES / slug)
        entry = manifest.platforms[platform]
        checked += 1
        if not is_wiki_source_url(entry.source_url):
            problems.append(
                f"{slug}/{platform}/{rel} 源码标了来源但条目 source_url 不是 wiki 页："
                f"{entry.source_url!r}"
            )
        if not any(is_wiki_source_url(url) for url in _URL_RE.findall(head)):
            problems.append(f"{slug}/{platform}/{rel} 来源块里没有 wiki 原页 URL")
    assert checked >= 100, f"带来源标注的 .c/.h 数量异常：{checked}（预期 100+，判据或库漂移）"
    assert not problems, (
        "wiki 派生模块源码来源标注与条目 source_url 不一致：\n- " + "\n- ".join(problems)
    )


def test_wiki_source_url_entries_carry_source_note():
    """反向：条目 source_url 是 wiki 页且源码确实引用了该页（头部出现该 URL）
    → 头部必须有来源标注块——防「URL 只在正文深处出现、来源声明缺失」。"""
    problems: list[str] = []
    for manifest_path in sorted(LIBRARY_MODULES.glob("*/manifest.json")):
        manifest = ModuleManifest.load(manifest_path.parent)
        for platform, entry in manifest.platforms.items():
            if not is_wiki_source_url(entry.source_url):
                continue
            for rel in entry.files:
                if not rel.endswith((".c", ".h")):
                    continue
                path = manifest_path.parent / rel
                if not path.is_file():
                    continue
                head = _head(path.read_text(encoding="utf-8", errors="replace"))
                if entry.source_url in head and SOURCE_NOTE_MARKER not in head:
                    problems.append(f"{manifest.slug}/{platform}/{rel}")
    assert not problems, (
        "源码头部引用了 wiki 原页 URL 但没有来源标注块：\n- " + "\n- ".join(problems)
    )


def _wiki_source_coverage() -> tuple[int, int]:
    """(wiki 来源模块数, 其平台条目 .c/.h 文件数)——判据单源 is_wiki_source_url。"""
    modules = files = 0
    for manifest_path in sorted(LIBRARY_MODULES.glob("*/manifest.json")):
        manifest = ModuleManifest.load(manifest_path.parent)
        hit = False
        for entry in manifest.platforms.values():
            if not is_wiki_source_url(entry.source_url):
                continue
            hit = True
            files += sum(1 for rel in entry.files if rel.endswith((".c", ".h")))
        modules += 1 if hit else 0
    return modules, files


def test_wiki_source_coverage_does_not_shrink():
    """覆盖面地板：wiki 来源的模块数与文件数不得低于冻结下限。

    为什么是地板而不是「文档里写死计数」：计数没有消费方也没有守卫，写进
    CONTEXT.md 只会漂（56/115 → 71/268）；文档改述覆盖面口径后，真正要守的
    「覆盖面 = 全部 is_wiki_source_url 命中模块」由本断言兜底——条目 source_url
    被静默清空、wiki 模块被删都会红。库增长只判下界，不触发红。
    """
    modules, files = _wiki_source_coverage()
    floor_modules, floor_files = WIKI_COVERAGE_FLOOR
    assert modules >= floor_modules, (
        f"wiki 来源模块数 {modules} < 地板 {floor_modules}：条目 source_url 被清空"
        "或 wiki 模块被删？确需下调请显式改 WIKI_COVERAGE_FLOOR 并说明理由"
    )
    assert files >= floor_files, (
        f"wiki 来源条目的 .c/.h 文件数 {files} < 地板 {floor_files}：同上"
    )


def _page_path(url: str) -> str:
    """wiki URL 的页面路径（去掉 `/zh-hans/<board>` 前缀）——同一页的两平台版本
    只差板前缀，共享源码文件合法地引用另一平台版本（`servo.h`）。"""
    match = re.match(r"https://wiki\.lckfb\.com/zh-hans/[^/]+/(.*)$", url)
    return match.group(1) if match else url


def test_single_url_source_note_matches_entry_source_url():
    """来源块只写一个 URL 时，该 URL 必须与条目 source_url 指同一页（写错页 /
    引用旧页即红；同页的另一平台版本合法）。

    只约束单 URL 块：多 URL 块（`oled_extra_stm32.c` 同时改写两页）合法地不等，
    强行相等会让测试比事实更严（假红）。"""
    problems: list[str] = []
    for slug, platform, rel, _path, head in _source_note_files():
        entry = ModuleManifest.load(LIBRARY_MODULES / slug).platforms[platform]
        wiki_urls = [url for url in _URL_RE.findall(head) if is_wiki_source_url(url)]
        if len(wiki_urls) == 1 and _page_path(wiki_urls[0]) != _page_path(
            entry.source_url
        ):
            problems.append(
                f"{slug}/{platform}/{rel} 来源块 URL {wiki_urls[0]} 与条目 source_url "
                f"{entry.source_url!r} 不是同一页"
            )
    assert not problems, "来源标注块 URL 与条目 source_url 不一致：\n- " + "\n- ".join(problems)


def test_inject_source_note_idempotent():
    """注入纯函数幂等：顶部窗口已含 URL 原样返回；注入两遍结果一致。"""
    body = '#include "aht10.h"\nint main(void) { return 0; }\n'
    once = inject_source_note(body, WIKI_URL, "AHT10温湿度传感器")
    twice = inject_source_note(once, WIKI_URL, "AHT10温湿度传感器")
    assert once == twice
    assert once != body  # 确有注入
    assert WIKI_URL in once
    assert "来源" in once
    assert once.startswith("/* 来源：")


def test_inject_source_note_idempotency_matches_test_window():
    """幂等判据与结构测试同口径（顶部 HEAD_WINDOW 窗内含 URL = 已标注）：
    URL 出现在窗口之外（文件深处）≠ 已标注——仍注入（c2 判例：脚本与测试
    判定漂移 = 脚本报 0 变更 / 测试红灯，现已共用同一窗口常量统一）。"""
    body = "#include \"aht10.h\"\n" + ("/* 填充 */\n" * 80) + "/* 正文引用 " + WIKI_URL + " */\n"
    assert len(body) > HEAD_WINDOW  # 前置：URL 确实在窗口外
    out = inject_source_note(body, WIKI_URL, "AHT10温湿度传感器")
    assert out != body  # 窗口外 URL 不算已标注，仍注入
    assert out.startswith("/* 来源：")


def test_inject_source_note_keeps_crlf():
    """CRLF 文件注入不混行：注释块换行风格跟随原文。"""
    body = '#include "aht10.h"\r\nint main(void) { return 0; }\r\n'
    out = inject_source_note(body, WIKI_URL, "AHT10温湿度传感器")
    assert "\r\n" in out
    assert "\n" not in out.replace("\r\n", "")


def test_inject_source_note_crlf_real_file_roundtrip(tmp_path):
    """CRLF 保真真实路径（code-review c1 判例）：open(newline="") 读盘 → 注入 →
    open(newline="") 写盘，CRLF 文件注入后仍是 CRLF（read_text/write_text
    universal newlines 会归一化，禁止用于本注入路径）。"""
    f = tmp_path / "x.c"
    body = '#include "x.h"\r\nint main(void) { return 0; }\r\n'
    f.write_bytes(body.encode("utf-8"))
    with open(f, encoding="utf-8", errors="replace", newline="") as fh:
        text = fh.read()
    new = inject_source_note(text, WIKI_URL, "AHT10温湿度传感器")
    with open(f, "w", encoding="utf-8", newline="") as fh:
        fh.write(new)
    result = f.read_bytes().decode("utf-8")
    assert result.startswith("/* 来源：")
    assert "/* 来源：" in result
    assert "\r\n" in result
    assert "\n" not in result.replace("\r\n", "")  # 无裸 \n（独行）


def test_inject_source_note_header_guard_position():
    """注入块置于 .h 的 #ifndef 之前（不会挡住 include guard）。"""
    body = "#ifndef AHT10_H\n#define AHT10_H\n\n#endif\n"
    out = inject_source_note(body, WIKI_URL, "AHT10温湿度传感器")
    assert out.index("#ifndef") > out.index("页面：")
    assert out.index("#ifndef") > out.index("来源：")


def test_source_note_block_contains_title_url_and_license_line():
    """标准注释块含标题 / 页面 / 版权要求行（文案迭代防漏）。"""
    block = source_note_block(WIKI_URL, "AHT10温湿度传感器")
    assert "《AHT10温湿度传感器》" in block
    assert "页面：" + WIKI_URL in block
    assert "标明来源与链接" in block


def test_source_note_block_comment_closed():
    """注释块必须闭合（` */`）：不闭合会吞掉后续 include 行（self include
    门禁判例回潮防再犯——正文含 `*/` 的 URL / 文案迭代都可能改坏闭合）。"""
    block = source_note_block(WIKI_URL, "AHT10温湿度传感器")
    assert block.rstrip().endswith("*/")
    body = '#include "aht10.h"\n'
    out = inject_source_note(body, WIKI_URL, "AHT10温湿度传感器")
    # 闭合后，注释块之外的原正文完整保留（被吞 = include 行丢失）
    assert out.endswith(body)
    assert out.count("*/") == 1


def test_wiki_url_judgment():
    """判据单源：wiki 前缀命中，淘宝 / 空串 / 其他站点不命中。"""
    assert is_wiki_source_url(WIKI_URL)
    assert is_wiki_source_url("https://wiki.lckfb.com/zh-hans/dmx/")
    assert not is_wiki_source_url("")
    assert not is_wiki_source_url("https://e.tb.cn/h.86Mb3gU2D8LNQAM")
    assert not is_wiki_source_url("https://other.example.com/wiki/lckfb")


def test_js_wiki_prefix_mirrors_python():
    """跨语言常量同步：fx/module.js 的 URL 前缀字面量必须与后端判据一致。

    JS 与 Python 不能共享常量，模块详情标签（来源（立创 wiki））与后端判据
    （is_wiki_source_url）用同一前缀——改任一侧此测试即红（防静默漂移）。
    """
    js_src = (
        Path(__file__).resolve().parents[1]
        / "src" / "contest_generator" / "static" / "js" / "fx" / "module.js"
    ).read_text(encoding="utf-8")
    assert js_src.count(WIKI_SOURCE_URL_PREFIX) >= 1
    assert (
        'startsWith("' + WIKI_SOURCE_URL_PREFIX + '")' in js_src
    ), f"module.js 前缀与后端判据漂移：{WIKI_SOURCE_URL_PREFIX!r}"


def test_wiki_md_files_carry_source_line():
    """手册 .md 头部来源行（资料库存在时；轻量 clone 缺失则跳过）。

    wiki_md 抓取期写入「- 来源：<原页>」头（wiki_md.py 单源）；资料库在本机
    存在时逐个断言，缺失（git 轻量 clone 无 sources/materials）不硬遍历。
    """
    md_root = (
        Path(__file__).resolve().parents[1]
        / "sources" / "materials" / "lckfb-地猛星移植手册"
    )
    if not md_root.is_dir():
        pytest.skip("轻量 clone 无资料库（sources/materials 独立分发）")
    missing = []
    checked = 0
    for md in sorted(md_root.glob("*.md")):
        if md.name in ("模块索引.md", "网盘索引.md"):
            continue  # 汇总索引非单页手册，无「来源：」头
        text = md.read_text(encoding="utf-8", errors="replace")
        checked += 1
        if "来源：" not in text[:200] or "https://wiki.lckfb.com/" not in text[:200]:
            missing.append(md.name)
    assert checked >= 70, f"wiki 手册 .md 数量异常：{checked}（预期 70+，抓取批次漂移）"
    assert not missing, f"wiki 手册 .md 头部缺来源行：{missing}"
