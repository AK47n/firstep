"""平台工程文件底座：工程文件定位 / include 条目解析核心 / XML 读写。

keil.py / ccs.py 共用同一套 ElementTree 读写基础设施——ET 重序列化会丢掉
各平台工程文件特有的头部信息（keil 根元素的 xmlns 声明、ccs 根元素前的
<?fileVersion?> 处理指令），写回前必须按原文补回；声明行与缩进也随平台
不同。格式结构知识（include 语法、宏策略、源文件注册）留在各修改器模块，
这里只做公共部分：孪生查找器 find_project_file（*.uvprojx / *.cproject
只差 pattern 与错误类）与 include 条目解析核心 resolve_include_entries
（绝对保留 / 相对基准 / 去重保序 / resolve）。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Iterable

from .treewalk import iter_project_files

DEFAULT_XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>'


def find_project_file(
    project_dir: Path, pattern: str, error_cls: type[Exception]
) -> Path:
    """定位平台工程文件（*.uvprojx / *.cproject）：任意层级 + 统一噪音跳过。

    孪生查找器 _find_uvprojx / _find_cproject 的共享实现——两平台只差 pattern
    与错误类型，错误文案从 pattern 派生逐字（"*.uvprojx" → ".uvprojx"）。
    0 个 / 多个都抛 error_cls；treewalk 跳过规则（.git 任意层级 + 构建产物
    目录）保证 .git 里的工程文件与 Listings/ 下的拷贝都不算数。
    """
    candidates = sorted(iter_project_files(project_dir, pattern=pattern))
    if not candidates:
        raise error_cls(f"工程目录里没有 {pattern[1:]} 文件：{project_dir}")
    if len(candidates) > 1:
        raise error_cls(
            f"工程目录里有多个 {pattern[1:]}，无法确定改哪个："
            + "、".join(p.name for p in candidates)
        )
    return candidates[0]


def resolve_include_entries(entries: Iterable[str], base: Path) -> list[Path]:
    """include 搜索目录条目的共享解析核心（keil/ccs 同构部分）。

    strip + 反斜杠归一 → 空条目跳过；绝对路径原样保留，相对路径以 base 为
    基准（keil 惯例 .uvprojx 所在目录 / ccs 惯例 .cproject 所在目录）；
    按出现顺序去重（大小写不敏感）；resolve 为绝对目录。宏展开等平台格式
    知识由调用方处理完再喂进来（keil 无宏，ccs 预处理后同缝）。
    """
    dirs: list[Path] = []
    seen: set[str] = set()
    for entry in entries:
        entry = entry.strip().replace("\\", "/")
        if not entry:
            continue
        p = Path(entry)
        resolved = p if p.is_absolute() else (base / p)
        key = str(resolved).lower()
        if key not in seen:
            seen.add(key)
            dirs.append(resolved.resolve())
    return dirs


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
