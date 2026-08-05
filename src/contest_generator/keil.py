"""Keil5 工程修改器：改写 .uvprojx。

把模块源文件注册进工程树（新增 modules 分组）、把模块目录追加进
IncludePath；设备型号、烧录配置等其余配置语义全部保留。文件经
ElementTree 重序列化，空白格式会规范化——.uvprojx 由 Keil 生成、不含
注释，格式变化无信息损失。
重复调用幂等：先移除上次加的 modules 分组，再按同一顺序重新添加。
XML 解析 / 写回 / 头部回注基础设施与 ccs 共用 projectfile.py 底座，
这里只留 .uvprojx 的格式结构知识。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

from .projectfile import parse_project_file, write_project_file

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
        root, original_text = parse_project_file(uvprojx, KeilProjectError)
        targets = root.findall("Targets/Target")
        if not targets:
            raise KeilProjectError(f"{uvprojx} 里没有 <Targets><Target>，无法注册模块")
        for target in targets:
            _register_module_files(target, module_files)
            _append_include_dirs(target, include_dirs)
        write_project_file(
            uvprojx,
            root,
            original_text,
            indent="  ",
            declaration='<?xml version="1.0" encoding="UTF-8" ?>',
            restore=lambda serialized: _restore_xmlns(serialized, root, original_text),
        )


def rewrite_project_references(project_dir: Path, kept_paths: Sequence[str]) -> None:
    """删除 .uvprojx 里引用但不在保留集合的源文件条目，main.c 条目统一重定向。

    母版落盘后调用（apply_distillation）：被剔除的文件不留悬空引用，否则
    Keil 打开工程编译会因缺文件失败，"打开就能编译烧录"不成立。保留集合 =
    落盘文件的相对路径（POSIX，大小写不敏感）。main.c 条目特殊处理：母版
    main.c 由确定性模板写死在母版根，旧工程可能在任意层级（正点原子风格在
    USER/ 子目录），引用路径统一重写指向模板落位，模板 main.c 才进工程树。
    空组保留（Keil 可容忍，少动结构）。格式知识归本模块所有：与 patch /
    extract_config_summary 共用同一套 XML 结构认知。
    """
    uvprojx = _find_uvprojx(project_dir)
    root, original_text = parse_project_file(uvprojx, KeilProjectError)
    kept = {_normalize_path(p) for p in kept_paths}
    template_main = _keil_rel_path("main.c")
    changed = False
    for target in root.findall("Targets/Target"):
        for group in target.findall("Groups/Group"):
            for files_el in group.findall("Files"):
                for file_el in list(files_el.findall("File")):
                    file_name = (file_el.findtext("FileName") or "").lower()
                    file_path = file_el.findtext("FilePath")
                    if file_name == "main.c":
                        # 旧工程 main.c 由模板替代（ADR 0002），引用一律指向模板落位
                        if file_path is not None and file_path != template_main:
                            file_el.find("FilePath").text = template_main
                            changed = True
                    elif file_path is None or _normalize_path(file_path) not in kept:
                        files_el.remove(file_el)
                        changed = True
    if not changed:
        return  # 无悬空引用也无需重定向——保持整合产物原样，不重写格式
    write_project_file(
        uvprojx,
        root,
        original_text,
        indent="  ",
        declaration='<?xml version="1.0" encoding="UTF-8" ?>',
        restore=lambda serialized: _restore_xmlns(serialized, root, original_text),
    )


def _normalize_path(path: str) -> str:
    """Keil 的 .\\ 前缀 + 反斜杠路径 → 小写 POSIX 相对路径（与扫描清单可比）。"""
    norm = path.replace("\\", "/").lower()
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def extract_config_summary(project_dir: Path) -> tuple[str, ...]:
    """.uvprojx 的只读配置摘要：设备 / include path（母版提炼的配置对比素材）。

    格式知识归本模块所有：patch 的改写与这里的摘要共用同一套 XML 结构认知，
    母版提炼不再另抄一份走查。解析失败只记一行，由调用方决定是否中断。
    """
    uvprojx = _find_uvprojx(project_dir)
    try:
        root = ET.parse(uvprojx).getroot()
    except ET.ParseError as exc:
        return (f"{uvprojx.name} 无法解析为 XML：{exc}",)
    lines: list[str] = []
    for target in root.findall("Targets/Target"):
        device = target.findtext("TargetOption/TargetCommonOption/Device")
        include_path = target.findtext("TargetOption/TargetArmAds/Cads/IncludePath")
        if device:
            lines.append(f"{uvprojx.name} 设备：{device}")
        if include_path:
            lines.append(f"{uvprojx.name} include path：{include_path}")
    if not lines:
        lines.append(f"{uvprojx.name}：未找到设备 / include path 配置")
    return tuple(lines)


def _find_uvprojx(project_dir: Path) -> Path:
    """定位工程文件 .uvprojx：任意层级（正点原子风格在 USER/ 子目录），跳过 .git。"""
    candidates = sorted(
        p for p in project_dir.rglob("*.uvprojx") if ".git" not in p.parts
    )
    if not candidates:
        raise KeilProjectError(f"工程目录里没有 .uvprojx 文件：{project_dir}")
    if len(candidates) > 1:
        raise KeilProjectError(
            "工程目录里有多个 .uvprojx，无法确定改哪个："
            + "、".join(p.name for p in candidates)
        )
    return candidates[0]


_XMLNS_DECL_RE = re.compile(r'xmlns(?:[:\w-]+)?="[^"]*"')


def _restore_xmlns(serialized: str, root: ET.Element, original_text: str) -> str:
    """补回 ET 解析时丢弃的根元素 xmlns 声明（对 Keil 无影响，尽量少动母版）。"""
    decls = _XMLNS_DECL_RE.findall(original_text)
    if not decls:
        return serialized
    return serialized.replace(
        f"<{root.tag}>", f"<{root.tag} " + " ".join(decls) + ">", 1
    )


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
