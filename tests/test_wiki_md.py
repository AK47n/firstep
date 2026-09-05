"""wiki 页面转换器（wiki_md）：Shiki 代码逐行还原 + <main> 按原页顺序转规范 Markdown。

夹具 = 从 wiki.lckfb.com 实际抓包结构提炼的合成 HTML 片段（VitePress + Shiki）：
代码块每行一个 <span class="line">、行号在兄弟 <div class="line-numbers-wrapper">、
标题带 <a class="header-anchor"> 锚点与 \u200b、有序列表 <ol start="N">。
"""

from __future__ import annotations

import re

from contest_generator.wiki_md import build_markdown, code_block_count, img_ext, parse_main, shiki_lines

# —— shiki_lines：<pre><code> 内部原始 HTML → 逐行代码 ——


def test_shiki_lines_restores_one_line_per_span():
    raw = ('<span class="line"><span style="--shiki-light:#6A737D;--shiki-dark:#6A737D;">/*</span></span>\n'
           '<span class="line"><span style="--shiki-light:#6A737D;--shiki-dark:#6A737D;"> * 立创开发板</span></span>\n'
           '<span class="line"><span style="--shiki-light:#6A737D;--shiki-dark:#6A737D;"> */</span></span>')
    assert shiki_lines(raw) == ["/*", " * 立创开发板", " */"]


def test_shiki_lines_joins_tokens_within_one_line():
    # 一行源码 = 多个 token span 连续（无换行）
    raw = ('<span class="line"><span style="--shiki-light:#24292E;">#include</span>'
           '<span style="--shiki-light:#24292E;"> </span>'
           '<span style="--shiki-light:#032F62;">"bsp_sht30.h"</span></span>')
    assert shiki_lines(raw) == ['#include "bsp_sht30.h"']


def test_shiki_lines_keeps_code_blank_lines():
    raw = ('<span class="line"><span style="--shiki-light:#000;">a</span></span>\n'
           '<span class="line"></span>\n'
           '<span class="line"><span style="--shiki-light:#000;">b</span></span>')
    assert shiki_lines(raw) == ["a", "", "b"]


def test_shiki_lines_drops_line_number_spans_defensively():
    # 行号 span 理论上在 <pre> 兄弟节点，此处验证防御性剔除（意外混入也不进代码）
    raw = ('<span class="line"><span style="--shiki-light:#000;">a</span></span>\n'
           '<span class="line-number">7</span>'
           '<span class="line"><span style="--shiki-light:#000;">b</span></span>')
    assert shiki_lines(raw) == ["a", "b"]


def test_shiki_lines_keeps_leading_indent():
    raw = ('<span class="line"><span style="--shiki-light:#000;">        SDA(0);</span></span>')
    assert shiki_lines(raw) == ["        SDA(0);"]


def test_shiki_lines_preserves_angle_bracket_code():
    # html.parser 已把 &lt;stdio.h&gt; 还原为字面 <stdio.h>（尖括号是代码文本，不是标签）
    raw = ('<span class="line"><span style="--shiki-light:#D73A49;">#include</span>'
           '<span style="--shiki-light:#032F62;"> <stdio.h></span></span>'
           '<span class="line"><span style="--shiki-light:#D73A49;">#include</span>'
           '<span style="--shiki-light:#032F62;"> "bsp_sht30.h"</span></span>')
    assert shiki_lines(raw) == ['#include <stdio.h>', '#include "bsp_sht30.h"']


def test_shiki_lines_no_line_marker_returns_empty():
    assert shiki_lines("<span style='x'>no marker</span>") == []


# —— parse_main：<main> 内容区 → (markdown, 图片 URL 列表) ——


def _main(*parts):
    return '<main class="page"><div class="vp-doc">' + "".join(parts) + "</div></main>"


def _anchor(zws="\u200b"):
    return (f'<a class="header-anchor" href="#x" aria-label="Permalink to \u201cx\u201d">{zws}</a>')


def test_headings_strip_anchor_and_zero_width():
    html = _main(f'<h2 id="\u4e00\u3001\u6a21\u5757\u6765\u6e90">\u4e00\u3001\u6a21\u5757\u6765\u6e90\u200b {_anchor()}</h2>')
    md, _ = parse_main(html, "s")
    assert md == "## 一、模块来源"


def test_paragraph_inline_bold_code_link():
    html = _main(
        '<p><strong>工作电压</strong>：2.4-5.5V</p>'
        '<p><strong><code>Yes to All</code></strong></p>'
        '<p><a href="https://pan.baidu.com/s/abc">https://pan.baidu.com/s/abc</a></p>'
    )
    md, _ = parse_main(html, "s")
    assert "**工作电压**：2.4-5.5V" in md
    assert "**`Yes to All`**" in md
    assert "[https://pan.baidu.com/s/abc](https://pan.baidu.com/s/abc)" in md


def test_ordered_lists_merge_with_start_numbers():
    html = _main(
        '<ol start="5"><li>点击保存</li></ol>'
        '<ol start="6"><li>然后点击编译</li></ol>'
        '<ol start="7"><li>引脚就会默认分配</li></ol>'
    )
    md, _ = parse_main(html, "s")
    # 连续 ol（每 li 一个）合并为一块，编号取自 start
    assert "5. 点击保存\n6. 然后点击编译\n7. 引脚就会默认分配" in md


def test_unordered_list():
    html = _main("<ul><li>甲</li><li>乙</li></ul>")
    md, _ = parse_main(html, "s")
    assert "- 甲\n- 乙" in md


def test_custom_block_becomes_quote():
    html = _main(
        '<div class="warning custom-block">'
        '<p class="custom-block-title custom-block-title-default">WARNING</p>'
        '<p>出现只要出现下面的框就一定要选择：<strong><code>Yes to All</code></strong></p>'
        "</div>"
    )
    md, _ = parse_main(html, "s")
    assert "> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**" in md


def test_custom_block_body_not_leak_into_following_list():
    # 评审实锤：custom-block 正文曾残留 _cur，注入到后续段落/列表项
    html = _main(
        '<div class="warning custom-block">'
        '<p class="custom-block-title custom-block-title-default">WARNING</p>'
        '<p>出现只要出现下面的框就一定要选择</p>'
        "</div>"
        '<ol start="6"><li>然后点击编译（<strong>可能会报错，我们不用管！</strong>）</li></ol>'
        '<p>移植完成后修改相关代码。</p>'
    )
    md, _ = parse_main(html, "s")
    assert "> **WARNING**：出现只要出现下面的框就一定要选择" in md
    assert "6. 然后点击编译（**可能会报错，我们不用管！**）" in md
    assert "移植完成后修改相关代码。" in md
    # 泄漏检查：列表项与后续段落不得再包含提示块正文
    for line in md.splitlines():
        if line.startswith("6. ") or line.startswith("移植"):
            assert "出现只要" not in line


def test_line_number_wrapper_not_leak_into_prose():
    # 评审实锤：行号 wrapper 与 <pre> 同级，数字曾经 prose 路径泄漏成 "1 2 3 …"
    html = _main(
        '<div class="language-c line-numbers-mode"><span class="lang">c</span>'
        '<pre class="shiki"><code>'
        '<span class="line"><span style="--shiki-light:#000;">#include "board.h"</span></span>'
        "</code></pre>"
        '<div class="line-numbers-wrapper" aria-hidden="true">'
        '<span class="line-number">1</span><br><span class="line-number">2</span><br>'
        '<span class="line-number">3</span><br>'
        "</div></div>"
        '<p>在文件 bsp_sht30.h 中，编写如下代码。</p>'
    )
    md, _ = parse_main(html, "s")
    assert '```c\n#include "board.h"\n```' in md
    assert "在文件 bsp_sht30.h 中，编写如下代码。" in md
    # 泄漏检查：正文里不得出现行号序列
    assert re.search(r"\b1 2 3\b", md) is None


def test_inline_del_and_em():
    html = _main("<p><del>旧文本</del><em>新文本</em></p>")
    md, _ = parse_main(html, "s")
    assert "~~旧文本~~" in md
    assert "*新文本*" in md


def test_paragraphs_separated_by_blank_line():
    html = _main("<p>第一段。</p><p>第二段。</p>")
    md, _ = parse_main(html, "s")
    assert "第一段。\n\n第二段。" in md


def test_images_dedup_numbered_with_ext():
    html = _main(
        '<h3>模块原理图</h3>'
        '<p><img src="/storage/images/zh-hans/dmx/module/0-96-color-screen/0-96-color-screen_20240626_171132.gif" alt=""></p>'
        '<p><img src="/storage/images/zh-hans/dmx/module/0-96-color-screen/0-96-color-screen_20240626_171132.gif" alt=""></p>'
    )
    md, urls = parse_main(html, "demo")
    assert urls == ["https://wiki.lckfb.com/storage/images/zh-hans/dmx/module/0-96-color-screen/0-96-color-screen_20240626_171132.gif"]
    assert md.count("![img](images/demo/img1.gif)") == 2  # 去重后两处引用同一本地文件


def test_drops_comments_and_h1():
    html = _main("<h1>SHT30温湿度传感器</h1><!----><p>正文</p>")
    md, _ = parse_main(html, "s")
    assert "SHT30温湿度传感器" not in md  # h1 抛弃（元数据里已有标题行）
    assert "正文" in md


def test_code_fence_with_lang():
    html = _main(
        '<div class="language-c line-numbers-mode"><span class="lang">c</span>'
        '<pre class="shiki"><code>'
        '<span class="line"><span style="--shiki-light:#000;">#include</span><span style="--shiki-light:#000;"> </span><span style="--shiki-light:#000;">&quot;board.h&quot;</span></span>'
        '<span class="line"><span style="--shiki-light:#000;">int main(void)</span></span>'
        "</code></pre></div>"
    )
    md, _ = parse_main(html, "s")
    assert '```c\n#include "board.h"\nint main(void)\n```' in md


def test_escapes_markdown_specials_in_prose():
    html = _main("<p>说明：A*B 与 _x_ 与 [y] 与 `z`</p>")
    md, _ = parse_main(html, "s")
    # * [ backtick 转义；词内 _ 不转义（CommonMark 词内下划线按字面，转义污染原文）
    assert "A\\*B 与 _x_ 与 \\[y] 与 \\`z\\`" in md


# —— build_markdown：单篇组装 ——


def test_build_markdown_assembles_doc():
    body = "## 一、模块来源\n\n正文\n\n```c\nint a;\n```"
    md = build_markdown(
        slug="sensor--demo",
        cat="sensor",
        url="https://wiki.lckfb.com/zh-hans/dmx/module/sensor/demo.html",
        title="Demo | 立创开发板技术文档中心",
        md_body=body,
        img_urls=["https://wiki.lckfb.com/x/a.gif"],
        pan_links=["https://pan.baidu.com/s/abc"],
    )
    assert md.startswith("# sensor--demo\n")
    assert "- 分类：sensor" in md
    assert "- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/demo.html" in md
    assert "- 标题：Demo | 立创开发板技术文档中心" in md
    assert "- 代码块：1 个 · 图片：1 张" in md
    assert "## 百度网盘下载" in md
    assert "- https://pan.baidu.com/s/abc" in md


def test_img_ext_extracts_suffix():
    assert img_ext("https://wiki.lckfb.com/storage/x/y.gif") == ".gif"
    assert img_ext("https://wiki.lckfb.com/storage/x/y.PNG?t=1") == ".png"
    assert img_ext("https://wiki.lckfb.com/storage/x/y") == ".png"
