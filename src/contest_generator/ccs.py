"""CCS 工程修改器：改写 .cproject。

与 Keil 的关键差异：.cproject（Eclipse CDT managed build）不逐文件枚举
源文件，构建系统扫描 sourceEntries 声明的源码目录。因此本修改器只做两件事：
把模块头文件目录追加进 toolchain 的 buildIncludePath 选项（每个 build
configuration 都加）；确保 modules/ 目录被某个 sourceEntry 覆盖（母版已有
根条目时无需添加），CCS 工程树与编译都能看到模块文件。设备型号、烧录配置
等其余配置语义全部保留。文件经 ElementTree 重序列化，空白格式会规范化——
.cproject 由 CCS 生成、不含注释，格式变化无信息损失。
重复调用幂等：include 值按去重追加，sourceEntry 按存在性补齐，不重复添加。
XML 解析 / 写回 / 头部回注基础设施与 keil 共用 projectfile.py 底座，
这里只留 .cproject 的格式结构知识。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

from .projectfile import parse_project_file, write_project_file
from .treewalk import iter_project_files

INCLUDE_OPTION_SUPERCLASS = "ti.ccs.misc.options.buildIncludePath"
MODULES_SOURCE_ENTRY_NAME = "modules"
SOURCE_ENTRY_FLAGS = "VALUE_WORKSPACE_PATH"
_SETTINGS_MODULE_ID = "org.eclipse.cdt.core.settings"

_XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
_FILEVERSION_PI_RE = re.compile(r"<\?fileVersion[^>]*\?>")


class CcsProjectError(Exception):
    """.cproject 缺失、重复或不是合法 XML。"""


class CcsPatcher:
    """ProjectPatcher 的 CCS 实现：追加 include path + 补齐 modules 源条目。"""

    def patch(
        self,
        project_dir: Path,
        module_files: Sequence[Path],
        include_dirs: Sequence[Path],
    ) -> None:
        cproject = _find_cproject(project_dir)
        root, original_text = parse_project_file(cproject, CcsProjectError)
        configurations = _build_configurations(root)
        if not configurations:
            raise CcsProjectError(
                f"{cproject} 里没有 build configuration（cdtBuildSystem/configuration），无法注册模块"
            )
        for configuration in configurations:
            _append_include_dirs(configuration, include_dirs)
            _ensure_modules_source_entry(configuration)
        file_version = _FILEVERSION_PI_RE.search(original_text)
        write_project_file(
            cproject,
            root,
            original_text,
            indent="\t",
            declaration=_XML_DECLARATION,
            head_extra=file_version.group(0) if file_version else "",
        )


def include_search_dirs(project_dir: Path) -> list[Path]:
    """工程 .cproject buildIncludePath 的目录（CCS 对引号头文件的搜索范围）。

    引号头搜索范围与 Keil 对偶：先当前文件所在目录，再按 buildIncludePath
    顺序。条目相对 .cproject 所在目录（CCS 惯例，${PROJECT_LOC} = 工程根，
    展开为该目录），绝对路径原样保留，其余相对路径以 .cproject 所在目录为
    基准；按出现顺序去重。找不到 .cproject 返回空列表——生成路径母版必有
    cproject（CcsPatcher 兜底报错），此函数只为解析 include 搜索目录。
    """
    try:
        cproject = _find_cproject(project_dir)
    except CcsProjectError:
        return []
    root = ET.parse(cproject).getroot()
    dirs: list[Path] = []
    seen: set[str] = set()
    for configuration in _build_configurations(root):
        for value in _option_values(
            configuration, "ti.ccs.misc.options.buildIncludePath"
        ):
            if value.startswith("${PROJECT_LOC}/"):
                resolved = cproject.parent / value[len("${PROJECT_LOC}/") :]
            elif value == "${PROJECT_LOC}":
                resolved = cproject.parent
            else:
                p = Path(value)
                resolved = p if p.is_absolute() else (cproject.parent / p)
            key = str(resolved).lower()
            if key not in seen:
                seen.add(key)
                dirs.append(resolved.resolve())
    return dirs


def extract_config_summary(project_dir: Path) -> tuple[str, ...]:
    """.cproject 的只读配置摘要：include path / 编译宏（母版提炼的配置对比素材）。

    格式知识归本模块所有：patch 的改写与这里的摘要共用同一套 XML 结构认知
    （_build_configurations 是唯一走查实现），母版提炼不再另抄一份。解析
    失败只记一行，由调用方决定是否中断。
    """
    cproject = _find_cproject(project_dir)
    try:
        root = ET.parse(cproject).getroot()
    except ET.ParseError as exc:
        return (f"{cproject.name} 无法解析为 XML：{exc}",)
    lines: list[str] = []
    for configuration in _build_configurations(root):
        name = configuration.get("name", "?")
        include_paths = _option_values(
            configuration, "ti.ccs.misc.options.buildIncludePath"
        )
        defines = _option_values(configuration, "ti.ccs.misc.options.buildDefine")
        parts: list[str] = []
        if include_paths:
            parts.append("include path: " + ", ".join(include_paths))
        if defines:
            parts.append("defines: " + ", ".join(defines))
        if parts:
            lines.append(f"{cproject.name} 配置 {name}：{'；'.join(parts)}")
    if not lines:
        lines.append(f"{cproject.name}：未找到配置摘要")
    return tuple(lines)


def _find_cproject(project_dir: Path) -> Path:
    """定位工程文件 .cproject：任意层级 + 统一噪音跳过规则（treewalk，与
    master 扫描同一规则；旧实现只查顶层，嵌套工程会漏判）。"""
    candidates = sorted(iter_project_files(project_dir, pattern="*.cproject"))
    if not candidates:
        raise CcsProjectError(f"工程目录里没有 .cproject 文件：{project_dir}")
    if len(candidates) > 1:
        raise CcsProjectError(
            "工程目录里有多个 .cproject，无法确定改哪个："
            + "、".join(p.name for p in candidates)
        )
    return candidates[0]


def _build_configurations(root: ET.Element) -> list[ET.Element]:
    """所有 build configuration 元素（cconfiguration/cdtBuildSystem/configuration）。"""
    result: list[ET.Element] = []
    for storage in root.findall("storageModule"):
        if storage.get("moduleId") != _SETTINGS_MODULE_ID:
            continue
        for cconfig in storage.findall("cconfiguration"):
            for inner in cconfig.findall("storageModule"):
                if inner.get("moduleId") != _SETTINGS_MODULE_ID:
                    continue
                build_system = inner.find("cdtBuildSystem")
                if build_system is None:
                    continue
                result.extend(build_system.findall("configuration"))
    return result


def _append_include_dirs(
    configuration: ET.Element, include_dirs: Sequence[Path]
) -> None:
    option = _include_option(configuration)
    if option is None:
        raise CcsProjectError(
            "工程里没有 buildIncludePath 选项，无法加入模块 include path，拒绝产出残缺工程"
        )
    existing = {
        v.get("value", "").lower() for v in option.findall("listOptionValue")
    }
    for value in (_ccs_include_value(d) for d in include_dirs):
        if value.lower() not in existing:
            ET.SubElement(option, "listOptionValue", {"builtIn": "false", "value": value})
            existing.add(value.lower())


def _include_option(
    configuration: ET.Element, super_class: str = INCLUDE_OPTION_SUPERCLASS
) -> ET.Element | None:
    """toolchain 里指定 superClass 的 option 元素。"""
    tool_chain = configuration.find("folderInfo/toolChain")
    if tool_chain is None:
        return None
    for option in tool_chain.findall("option"):
        if option.get("superClass") == super_class:
            return option
    return None


def _option_values(configuration: ET.Element, super_class: str) -> list[str]:
    """toolchain 里指定 superClass 的 option 的 listOptionValue 值列表（配置摘要用）。"""
    option = _include_option(configuration, super_class)
    if option is None:
        return []
    return [
        value.get("value", "")
        for value in option.findall("listOptionValue")
        if value.get("value")
    ]


def _ensure_modules_source_entry(configuration: ET.Element) -> None:
    """保证 modules/ 目录被 sourceEntry 覆盖；根条目已覆盖时不做任何事。"""
    entries = configuration.find("sourceEntries")
    if entries is None:
        entries = ET.SubElement(configuration, "sourceEntries")
    for entry in entries.findall("entry"):
        if entry.get("kind") != "sourcePath":
            continue
        if entry.get("name") in ("", MODULES_SOURCE_ENTRY_NAME):
            return
    ET.SubElement(
        entries,
        "entry",
        {
            "flags": SOURCE_ENTRY_FLAGS,
            "kind": "sourcePath",
            "name": MODULES_SOURCE_ENTRY_NAME,
        },
    )


def _ccs_include_value(rel_dir: Path) -> str:
    """相对工程目录的路径，转成 CCS 惯例的 ${PROJECT_LOC}/ 前缀 + 正斜杠。"""
    return "${PROJECT_LOC}/" + rel_dir.as_posix()
