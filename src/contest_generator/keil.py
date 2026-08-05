"""Keil5 工程修改器：改写 .uvprojx。

把模块源文件注册进工程树（新增 modules 分组）、把模块目录追加进
IncludePath；设备型号、烧录配置等其余配置语义全部保留。文件经
ElementTree 重序列化，空白格式会规范化——.uvprojx 由 Keil 生成、不含
注释，格式变化无信息损失。
重复调用幂等：先移除上次加的 modules 分组，再按同一顺序重新添加。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

MODULES_GROUP = "modules"

_SOURCE_FILETYPES = {
    ".c": "1",  # Keil FileType 码：1=C 源文件
    ".s": "2",  # 2=汇编源文件
    ".S": "2",
}


class KeilProjectError(Exception):
    """.uvprojx 缺失、重复或不是合法 XML。"""


class KeilPatcher:
    """ProjectPatcher 的 Keil 实现：注册模块文件 + 追加 include path。"""

    def patch(
        self,
        project_dir: Path,
        module_files: Sequence[Path],
        include_dirs: Sequence[Path],
    ) -> None:
        uvprojx = _find_uvprojx(project_dir)
        root, original_text = _parse(uvprojx)
        targets = root.findall("Targets/Target")
        if not targets:
            raise KeilProjectError(f"{uvprojx} 里没有 <Targets><Target>，无法注册模块")
        for target in targets:
            _register_module_files(target, module_files)
            _append_include_dirs(target, include_dirs)
        _write(uvprojx, root, original_text)


def _find_uvprojx(project_dir: Path) -> Path:
    candidates = sorted(project_dir.glob("*.uvprojx"))
    if not candidates:
        raise KeilProjectError(f"工程目录里没有 .uvprojx 文件：{project_dir}")
    if len(candidates) > 1:
        raise KeilProjectError(
            "工程目录里有多个 .uvprojx，无法确定改哪个："
            + "、".join(p.name for p in candidates)
        )
    return candidates[0]


_XMLNS_DECL_RE = re.compile(r'xmlns(?:[:\w-]+)?="[^"]*"')


def _parse(path: Path) -> tuple[ET.Element, str]:
    try:
        original_text = path.read_text(encoding="utf-8")
        root = ET.fromstring(original_text)
    except ET.ParseError as exc:
        raise KeilProjectError(f"{path} 不是合法 XML：{exc}") from exc
    return root, original_text


def _register_module_files(target: ET.Element, module_files: Sequence[Path]) -> None:
    groups = target.find("Groups")
    if groups is not None:
        for old in groups.findall("Group"):
            if old.findtext("GroupName") == MODULES_GROUP:
                groups.remove(old)

    source_files = [f for f in module_files if f.suffix in _SOURCE_FILETYPES]
    if not source_files:
        return
    if groups is None:
        groups = ET.SubElement(target, "Groups")

    group = ET.SubElement(groups, "Group")
    ET.SubElement(group, "GroupName").text = MODULES_GROUP
    files = ET.SubElement(group, "Files")
    for file in source_files:
        entry = ET.SubElement(files, "File")
        ET.SubElement(entry, "FileName").text = file.name
        ET.SubElement(entry, "FileType").text = _SOURCE_FILETYPES[file.suffix]
        ET.SubElement(entry, "FilePath").text = _keil_rel_path(file)


def _append_include_dirs(target: ET.Element, include_dirs: Sequence[Path]) -> None:
    include_el = target.find("TargetOption/TargetArmAds/Cads/IncludePath")
    if include_el is None:
        raise KeilProjectError(
            "工程里没有 Cads/IncludePath 节点，无法加入模块 include path，拒绝产出残缺工程"
        )
    existing = [s for s in (include_el.text or "").split(";") if s]
    existing_lower = {s.lower() for s in existing}
    additions = [
        _keil_rel_path(d)
        for d in include_dirs
        if _keil_rel_path(d).lower() not in existing_lower
    ]
    if additions:
        prefix = include_el.text + ";" if include_el.text else ""
        include_el.text = prefix + ";".join(additions)


def _keil_rel_path(path: Path) -> str:
    """相对工程目录的路径，转成 Keil 惯例的 .\\ 前缀 + 反斜杠。"""
    return ".\\" + str(path).replace("/", "\\")


def _write(path: Path, root: ET.Element, original_text: str) -> None:
    ET.indent(root, space="  ")
    serialized = (
        '<?xml version="1.0" encoding="UTF-8" ?>\n'
        + ET.tostring(root, encoding="unicode")
    )
    # ET 解析时丢弃根元素的 xmlns 声明（对 Keil 无影响），按原文补回，尽量少动母版
    decls = _XMLNS_DECL_RE.findall(original_text)
    if decls:
        serialized = serialized.replace(
            f"<{root.tag}>", f"<{root.tag} " + " ".join(decls) + ">", 1
        )
    path.write_text(serialized, encoding="utf-8")
