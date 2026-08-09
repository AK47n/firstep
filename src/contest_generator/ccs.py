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

双格式认知：同时认 CCS classic 与 Theia 20.5（TMS470_TICLANG 4.0）——
同结构语义（cconfiguration / toolChain / option / sourceEntries），差异在
cdtBuildSystem 的 storageModule 位置（classic 在 settings 内，Theia 独立）
与 include/define 选项的 superClass 命名空间（见 INCLUDE_OPTION_SUPERCLASSES），
单实现路径通吃，不分支双写。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

from .projectfile import parse_project_file, write_project_file
from .treewalk import iter_project_files

# 工具链外部头（工程树外提供，门禁豁免 include 解析）：ti_msp_dl_config.h 由
# CCS SysConfig 在构建时生成（工程树里没有，构建时经 ${SYSCONFIG_TOOL_INCLUDE_PATH}
# 解析）。平台事实单源声明处——patchers.external_headers 读侧分派消费（工单 03）。
EXTERNAL_HEADERS = frozenset({"ti_msp_dl_config.h"})

# include / define 选项的 superClass 双命名空间：classic（ti.ccs.misc.*）与
# CCS Theia 20.5（com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.*）
# ——匹配一律按多值集合，两格式同一实现路径
INCLUDE_OPTION_SUPERCLASSES = (
    "ti.ccs.misc.options.buildIncludePath",
    "com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.INCLUDE_PATH",
)
DEFINE_OPTION_SUPERCLASSES = (
    "ti.ccs.misc.options.buildDefine",
    "com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.DEFINE",
)
# 工程根宏：classic 用 ${PROJECT_LOC}，Theia 用 ${PROJECT_ROOT}（同语义展开）
_PROJECT_ROOT_MACROS = ("${PROJECT_LOC}", "${PROJECT_ROOT}")
MODULES_SOURCE_ENTRY_NAME = "modules"
SOURCE_ENTRY_FLAGS = "VALUE_WORKSPACE_PATH"
_SETTINGS_MODULE_ID = "org.eclipse.cdt.core.settings"
_BUILD_SYSTEM_MODULE_ID = "cdtBuildSystem"

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
    顺序。条目相对 .cproject 所在目录（CCS 惯例，${PROJECT_LOC} /
    ${PROJECT_ROOT} = 工程根，展开为该目录），绝对路径原样保留，其余相对
    路径以 .cproject 所在目录为基准；以 `${` 开头且不可展开的条目跳过
    （SDK / 工具链环境宏如 ${COM_TI_MSPM0_SDK_*} 由 CCS 构建时解析，Python
    侧不做变量引擎——母版头不在这些目录，解析不了也不参与门禁）；按出现
    顺序去重。找不到 .cproject 返回空列表——生成路径母版必有 cproject
    （CcsPatcher 兜底报错），此函数只为解析 include 搜索目录。
    """
    try:
        cproject = _find_cproject(project_dir)
    except CcsProjectError:
        return []
    root = ET.parse(cproject).getroot()
    dirs: list[Path] = []
    seen: set[str] = set()
    for configuration in _build_configurations(root):
        for value in _option_values(configuration, INCLUDE_OPTION_SUPERCLASSES):
            if value.startswith(
                ("${PROJECT_LOC}/", "${PROJECT_ROOT}/")
            ):
                resolved = cproject.parent / value[value.index("/") + 1 :]
            elif value in _PROJECT_ROOT_MACROS:
                resolved = cproject.parent
            elif value.startswith("${"):
                # SDK / 工具链环境宏（${COM_TI_MSPM0_SDK_*} 等）由 CCS 构建时
                # 解析，Python 侧不做变量引擎：跳过（母版头不在这些目录）
                continue
            else:
                p = Path(value)
                resolved = p if p.is_absolute() else (cproject.parent / p)
            if "${" in str(resolved):
                # 展开后仍含宏（如 ${PROJECT_ROOT}/${ConfigName}）：真实目录
                # 由构建时解析，无法确定，同样跳过
                continue
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
        include_paths = _option_values(configuration, INCLUDE_OPTION_SUPERCLASSES)
        defines = _option_values(configuration, DEFINE_OPTION_SUPERCLASSES)
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
    """所有 build configuration 元素（cconfiguration 内 cdtBuildSystem 持有的）。

    单实现路径走查两种格式：classic 的 cdtBuildSystem 是 settings
    storageModule 里的元素（configuration 在其下），Theia 20.5 把它放独立的
    moduleId="cdtBuildSystem" storageModule（configuration 是直接子元素）——
    对每个 cconfiguration 遍历全部内层 storageModule，谁持有 cdtBuildSystem
    就从谁取 configuration，同一段遍历两格式通吃。cproject 根级 storageModule
    的 <project> 元素不在 cconfiguration 内，天然不受影响。
    """
    result: list[ET.Element] = []
    for storage in root.findall("storageModule"):
        if storage.get("moduleId") != _SETTINGS_MODULE_ID:
            continue
        for cconfig in storage.findall("cconfiguration"):
            for inner in cconfig.findall("storageModule"):
                build_system = inner.find("cdtBuildSystem")
                if build_system is None:
                    if inner.get("moduleId") != _BUILD_SYSTEM_MODULE_ID:
                        continue
                    build_system = inner  # Theia：configuration 是该 storageModule 的直接子元素
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
    configuration: ET.Element,
    super_classes: Sequence[str] = INCLUDE_OPTION_SUPERCLASSES,
) -> ET.Element | None:
    """toolchain 里 superClass 命中任一命名空间（classic / Theia）的 option 元素。

    位置也双格式：classic 的 include/define 选项是 toolChain 直接子元素，
    Theia 20.5 在编译器 <tool> 元素内（TMS470_TICLANG_4.0 命名空间的
    superClass 指示编译器工具）——先查 toolChain 直接子元素、再查 tool 内层，
    同一条多值匹配通吃。
    """
    tool_chain = configuration.find("folderInfo/toolChain")
    if tool_chain is None:
        return None
    for option in tool_chain.findall("option"):
        if option.get("superClass") in super_classes:
            return option
    for tool in tool_chain.findall("tool"):
        for option in tool.findall("option"):
            if option.get("superClass") in super_classes:
                return option
    return None


def _option_values(configuration: ET.Element, super_classes: Sequence[str]) -> list[str]:
    """toolchain 里 superClass 命中任一命名空间的 option 的 listOptionValue 值列表（配置摘要用）。"""
    option = _include_option(configuration, super_classes)
    if option is None:
        return []
    return [
        value.get("value", "")
        for value in option.findall("listOptionValue")
        if value.get("value")
    ]


def _ensure_modules_source_entry(configuration: ET.Element) -> None:
    """保证 modules/ 目录被 sourceEntry 覆盖；根条目已覆盖时不做任何事。

    Theia 20.5 母版没有 sourceEntries 元素（CDT 缺省 = 全树为源，modules
    本就在覆盖内）——但显式补一条 classic 同款根条目（name="", excluding
    构建目录）把覆盖说死：sourceEntries 一旦存在，CDT 就把条目当完整源集
    （只加 modules 条目会让 main.c 等母版源码不再被编译，真机验收必挂）。
    """
    entries = configuration.find("sourceEntries")
    if entries is None:
        entries = ET.SubElement(configuration, "sourceEntries")
        ET.SubElement(
            entries,
            "entry",
            {
                "excluding": "Debug",
                "flags": SOURCE_ENTRY_FLAGS,
                "kind": "sourcePath",
                "name": "",
            },
        )
        return
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
