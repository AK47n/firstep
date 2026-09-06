"""立创 wiki 素材来源标注结构测试（lckfb-attribution/01）。

遍历真实模块库：凡平台条目 source_url 命中 wiki 判据（manifest.is_wiki_source_url
单源）→ 该条目每个 .c/.h 文件顶部必须含**该平台条目自己的**原页 URL（立创版权
要求第三条——复制 / 传播 / 修改 / 公开展示须标明来源与链接的源码面兜底），
逐条目独立断言、不做跨条目互证；非 wiki 模块不要求。
注入纯函数（source_notes.inject_source_note）幂等性单测。

不做的事：不断言注入注释块的确切文案（防脆——文案迭代时只断言 URL 存在 +
「来源」字样）；不遍历 sources/materials 手册（资料库可能轻量 clone 缺失，
非本库领域；手册头部「来源：」行由 wiki_md.py 抓取期写入，另有抓取测试守）。
"""

from __future__ import annotations

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

# 顶部窗口（判定窗，单源 = source_notes.HEAD_WINDOW）：注入块在文件头，窗口取
# 600 字符足够宽松，防「只标在文件尾部 / notes 里」的伪合规；脚本幂等判据与
# 本测试共用同一常量（c2 判例：漂移 = 脚本报 0 变更 / 测试红灯）。


def _iter_wiki_c_entries():
    """(模块 slug, 相对文件路径, 文件对象, source_url) 生成器——wiki 条目下的
    .c/.h，source_url = **该平台条目自己的** URL（逐条目断言，不聚合跨条目）。"""
    for manifest_path in sorted(LIBRARY_MODULES.glob("*/manifest.json")):
        manifest = ModuleManifest.load(manifest_path.parent)
        for platform, entry in manifest.platforms.items():
            if not is_wiki_source_url(entry.source_url):
                continue
            for rel in entry.files:
                if rel.endswith((".c", ".h")):
                    yield manifest.slug, rel, manifest_path.parent / rel, entry.source_url


def test_wiki_derived_module_sources_carry_page_url():
    """wiki 派生模块（真实库）每个 .c/.h 顶部 600 字符内必须含**该条目**原页 URL。

    断言按条目逐文件独立检查（不用 any() 跨 URL 互证——多 wiki 平台条目场景
    下互证会让漏标条目被同模块另一 URL 蒙混过关）。
    """
    missing = []
    checked = 0
    for slug, rel, f, url in _iter_wiki_c_entries():
        if not f.is_file():
            missing.append(f"{slug}/{rel}（文件不存在）")
            continue
        checked += 1
        text = f.read_text(encoding="utf-8", errors="replace")
        if url not in text[:HEAD_WINDOW]:
            missing.append(f"{slug}/{rel}")
    assert checked >= 100, f"wiki 模块 .c/.h 数量异常：{checked}（预期 100+，判据或库漂移）"
    assert not missing, f"wiki 派生模块源码缺原页 URL：{missing}"


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
