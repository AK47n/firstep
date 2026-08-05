"""CCS 工程修改器：改写 .cproject。

与 Keil 的关键差异：.cproject（Eclipse CDT managed build）不逐文件枚举
源文件，构建系统扫描 sourceEntries 声明的源码目录。因此本修改器只做两件事：
把模块头文件目录追加进 toolchain 的 buildIncludePath 选项（每个 build
configuration 都加）；确保 modules/ 目录被某个 sourceEntry 覆盖（母版已有
根条目时无需添加），CCS 工程树与编译都能看到模块文件。设备型号、烧录配置
等其余配置语义全部保留。文件经 ElementTree 重序列化，空白格式会规范化——
.cproject 由 CCS 生成、不含注释，格式变化无信息损失。
重复调用幂等：include 值按去重追加，sourceEntry 按存在性补齐，不重复添加。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

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
        root, original_text = _parse(cproject)
        configurations = _build_configurations(root)
        if not configurations:
            raise CcsProjectError(
                f"{cproject} 里没有 build configuration（cdtBuildSystem/configuration），无法注册模块"
            )
        for configuration in configurations:
            _append_include_dirs(configuration, include_dirs)
            _ensure_modules_source_entry(configuration)
        _write(cproject, root, original_text)


def _find_cproject(project_dir: Path) -> Path:
    candidates = sorted(project_dir.glob("*.cproject"))
    if not candidates:
        raise CcsProjectError(f"工程目录里没有 .cproject 文件：{project_dir}")
    if len(candidates) > 1:
        raise CcsProjectError(
            "工程目录里有多个 .cproject，无法确定改哪个："
            + "、".join(p.name for p in candidates)
        )
    return candidates[0]


def _parse(path: Path) -> tuple[ET.Element, str]:
    try:
        original_text = path.read_text(encoding="utf-8")
        root = ET.fromstring(original_text)
    except ET.ParseError as exc:
        raise CcsProjectError(f"{path} 不是合法 XML：{exc}") from exc
    return root, original_text


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


def _include_option(configuration: ET.Element) -> ET.Element | None:
    tool_chain = configuration.find("folderInfo/toolChain")
    if tool_chain is None:
        return None
    for option in tool_chain.findall("option"):
        if option.get("superClass") == INCLUDE_OPTION_SUPERCLASS:
            return option
    return None


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


def _write(path: Path, root: ET.Element, original_text: str) -> None:
    ET.indent(root, space="\t")
    serialized = _XML_DECLARATION + "\n"
    # ET 解析时丢弃根元素前的 <?fileVersion ...?> 处理指令（CCS 的固定头），按原文补回
    file_version = _FILEVERSION_PI_RE.search(original_text)
    if file_version:
        serialized += file_version.group(0)
    serialized += ET.tostring(root, encoding="unicode")
    path.write_text(serialized, encoding="utf-8")
