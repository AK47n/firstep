"""立创 wiki 素材来源标注结构测试（lckfb-attribution/01）。

遍历真实模块库：凡平台条目 source_url 命中 wiki 判据（manifest.is_wiki_source_url
单源）→ 该条目每个 .c/.h 文件顶部必须含原页 URL（立创版权要求第三条——复制 /
传播 / 修改 / 公开展示须标明来源与链接的源码面兜底）；非 wiki 模块不要求。
注入纯函数（source_notes.inject_source_note）幂等性单测。

不做的事：不断言注入注释块的确切文案（防脆——文案迭代时只断言 URL 存在 +
「来源」字样）；不遍历 sources/materials（资料库可能轻量 clone 缺失）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.manifest import ModuleManifest, is_wiki_source_url
from contest_generator.source_notes import inject_source_note, source_note_block

LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"

WIKI_URL = "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/aht10-temp-humi-sensor.html"

# 顶部窗口（字节窗）：注入块在文件头，窗口取 600 字符足够宽松，防「只标在
# 文件尾部 / notes 里」的伪合规
HEAD_WINDOW = 600


def _iter_wiki_c_files():
    """(模块 slug, 相对文件路径, 文件对象) 生成器——wiki 条目下的 .c/.h。"""
    for manifest_path in sorted(LIBRARY_MODULES.glob("*/manifest.json")):
        manifest = ModuleManifest.load(manifest_path.parent)
        for platform, entry in manifest.platforms.items():
            if not is_wiki_source_url(entry.source_url):
                continue
            for rel in entry.files:
                if rel.endswith((".c", ".h")):
                    yield manifest.slug, rel, manifest_path.parent / rel


def test_wiki_derived_module_sources_carry_page_url():
    """wiki 派生模块（真实库）每个 .c/.h 顶部 600 字符内必须含原页 URL。"""
    missing = []
    checked = 0
    for slug, rel, f in _iter_wiki_c_files():
        if not f.is_file():
            missing.append(f"{slug}/{rel}（文件不存在）")
            continue
        checked += 1
        text = f.read_text(encoding="utf-8", errors="replace")
        # 判据 URL 从 manifest 取（不硬编码）：再次 load 该模块该平台条目
        if not any(
            url in text[:HEAD_WINDOW]
            for url in _wiki_urls_of(f)
        ):
            missing.append(f"{slug}/{rel}")
    assert checked >= 100, f"wiki 模块 .c/.h 数量异常：{checked}（预期 100+，判据或库漂移）"
    assert not missing, f"wiki 派生模块源码缺原页 URL：{missing}"


def _wiki_urls_of(file: Path) -> list[str]:
    """该文件所属模块的 wiki source_url 列表（从 manifest 重新解析）。"""
    manifest = ModuleManifest.load(file.parents[1])
    return [
        entry.source_url
        for entry in manifest.platforms.values()
        if is_wiki_source_url(entry.source_url)
    ]


def test_inject_source_note_idempotent():
    """注入纯函数幂等：已含 URL 原样返回；注入两遍结果一致。"""
    body = '#include "aht10.h"\nint main(void) { return 0; }\n'
    once = inject_source_note(body, WIKI_URL, "AHT10温湿度传感器")
    twice = inject_source_note(once, WIKI_URL, "AHT10温湿度传感器")
    assert once == twice
    assert once != body  # 确有注入
    assert WIKI_URL in once
    assert "来源" in once
    assert once.startswith("/* 来源：")


def test_inject_source_note_keeps_crlf():
    """CRLF 文件注入不混行：注释块换行风格跟随原文。"""
    body = '#include "aht10.h"\r\nint main(void) { return 0; }\r\n'
    out = inject_source_note(body, WIKI_URL, "AHT10温湿度传感器")
    assert "\r\n" in out
    assert "\n" not in out.replace("\r\n", "")


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
