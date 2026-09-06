"""模块源码来源标注纯函数（lckfb-attribution/01）。

立创版权要求第三条：任何使用手册模块资料的个人或组织，将其复制、传播、
修改、公开展示或在其他网站上使用，都需要在使用时清楚的标明文件的来源以及
链接。本模块 = 「来源注释块」的唯一生成地：注入脚本（.scratch/
lckfb-attribution/inject_source_notes.py）与结构测试共用同一纯函数，
注释块文案只此一处（改文案只改这里，脚本 / 测试不漂移）。

判据（URL 是否为立创 wiki 原页）单源 = manifest.is_wiki_source_url。
"""

from __future__ import annotations

# 版权要求说明文案。注意：措辞刻意避开各模块结构测试的「xxx not in source」
# 防回潮守卫词（printf / main / IRQHandler / NVIC_ / flag / time / encoder 等），
# 故用「演示与调试输出」而不直呼函数名；守卫只查 .c，.h 无此约束，但统一
# 用安全措辞保证 .c/.h 同款块都可复用。改动须与 README 声明段
# （readme.SOURCE_NOTICE_*）保持同义。
NOTE_TEXT = (
    "本代码按模块库规范改写（去演示与调试输出、函数名规范化、\n"
    " * 引脚宏参数化等）；使用 / 复制 / 修改 / 传播请遵循立创版权要求：\n"
    " * 标明来源与链接。 */"
)


# 合规判定窗口（单源）：来源注释块注入位置 = 文件头部，故「已注入」判定只看
# 顶部 HEAD_WINDOW 字符（与结构测试同口径——头部无块而正文中部出现 URL 不算
# 已标注；脚本幂等判据与测试共用本常量，防「脚本报 0 变更 / 测试亮红灯」漂移）。
HEAD_WINDOW = 600


def source_note_block(url: str, title: str) -> str:
    """标准来源注释块（纯函数）：标题 + 原页 URL + 改写与版权要求说明。

    必须闭合（末尾 ` */`）：注释不闭合会吞掉后续 include 行——self include
    门禁（generator._check_module_self_include）会拦，但这是硬伤，勿改。
    """
    return (
        "/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《" + title + "》\n"
        " * 页面：" + url + "\n"
        " * " + NOTE_TEXT + "\n"
        "\n"
    )


def inject_source_note(text: str, url: str, title: str) -> str:
    """注入纯函数：顶部 HEAD_WINDOW 内已含 URL → 原样返回（幂等）；否则顶部
    插入注释块。

    换行风格跟随原文（\r\n 字符串用 \r\n 连接，避免混行）。调用方（脚本）须用
    open(newline="") 读盘保留原始换行——read_text() 的 universal newlines
    会把 \r\n 归一化为 \n，CRLF 分支将永不触发（code-review c1 判例）。
    """
    if url in text[:HEAD_WINDOW]:
        return text
    block = source_note_block(url, title)
    if "\r\n" in text:
        block = block.replace("\n", "\r\n")
    return block + text
