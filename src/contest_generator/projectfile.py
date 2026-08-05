"""平台工程文件 XML 读写底座：解析（带错误）与重序列化（缩进 + 头部回注）。

keil.py / ccs.py 共用同一套 ElementTree 读写基础设施——ET 重序列化会丢掉
各平台工程文件特有的头部信息（keil 根元素的 xmlns 声明、ccs 根元素前的
<?fileVersion?> 处理指令），写回前必须按原文补回；声明行与缩进也随平台
不同。格式结构知识（include 语法、源文件注册）留在各修改器模块，这里只做
读写的公共部分。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

DEFAULT_XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'


def parse_project_file(
    path: Path, error_type: type[Exception]
) -> tuple[ET.Element, str]:
    """读取工程文件并解析为元素树，返回（根元素, 原文全文）。

    解析失败抛 error_type（各修改器的工程错误类型），message 带路径与原因。
    原文全文用于写回时补回 ET 丢失的头部。
    """
    try:
        original_text = path.read_text(encoding="utf-8")
        root = ET.fromstring(original_text)
    except ET.ParseError as exc:
        raise error_type(f"{path} 不是合法 XML：{exc}") from exc
    return root, original_text


def write_project_file(
    path: Path,
    root: ET.Element,
    original_text: str,
    *,
    indent: str,
    declaration: str = DEFAULT_XML_DECLARATION,
    head_extra: str = "",
    restore: Callable[[str], str] | None = None,
) -> None:
    """重序列化写回：声明行 + 头部补回 + 缩进 + 写盘。

    ET 解析时丢弃的头部信息按调用方给的两个通道补回：head_extra 插在声明行
    之后（如 ccs 的 <?fileVersion?> 处理指令）；restore 收全文返回修正后的
    全文（如 keil 的根元素 xmlns 声明）。声明行与缩进随平台格式不同而不同。
    """
    ET.indent(root, space=indent)
    serialized = (
        declaration + "\n" + head_extra + ET.tostring(root, encoding="unicode")
    )
    if restore is not None:
        serialized = restore(serialized)
    path.write_text(serialized, encoding="utf-8")
