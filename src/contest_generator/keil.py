"""Keil5 工程文件：生成时改写 .uvprojx 与母版提炼时确定性现写。

两条路径共用的格式知识归本模块所有：
- 生成：KeilPatcher 把模块源文件注册进工程树（新增 modules 分组）、把模块
  目录追加进 IncludePath——文件引用与 include path 相对 .uvprojx 所在目录
  （Keil 惯例：USER/ 工程里 .\..\sys\delay.c = 工程根的 sys/delay.c）。
  重复调用幂等：先移除上次加的 modules 分组，再按同一顺序重新添加。
- 母版提炼（工单 09）：render_master_uvprojx 确定性现写完整 .uvprojx——
  设备块硬编码 C8T6（参考真实母版 2026C/21F 的已知良好格式，用户机器可编译），
  文件树按顶层目录分组、引用全部保留 .c/.s + 模板 main.c（落位工程根），
  IncludePath = 保留 .h 所在目录。工程配置文件移出 AI 判定（判例 09：AI 手写
  整合 XML 结构残缺——组清空、Cads/IncludePath 丢失——照样入库），结构一致性
  由构造保证；ticket 08 的结构校验保留为入库安全网（防手工导入的坏母版）。
  现写路径直接拼字符串（确定性输出、无 ET 命名空间回注问题），生成路径经
  ElementTree 重序列化（.uvprojx 由 Keil 生成、不含注释，格式变化无信息损失）。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence
from xml.sax.saxutils import escape

from .projectfile import parse_project_file, write_project_file
from .treewalk import iter_project_files

# 工具链外部头（工程树外提供，门禁豁免 include 解析）：stm32f10x_conf.h 由
# STM32F1xx DFP 器件包提供（标准外设库配置头，Keil 按 DFP 路径解析）。
# 平台事实单源声明处——patchers.external_headers 读侧分派消费（工单 03）。
EXTERNAL_HEADERS = frozenset({"stm32f10x_conf.h"})

MODULES_GROUP = "modules"

_SOURCE_FILETYPES = {
    ".c": "1",  # Keil FileType 码：1=C 源文件
    ".s": "2",  # 2=汇编源文件
    ".S": "2",
}

# 现写 .uvprojx 的固定落位（正点原子风格，与真实母版 2026C/21F 一致）。
# 布局的唯一出处：默认组名 / 文件引用前缀 / IncludePath 都从它推导——
# 换布局只改这一处（此前三处硬编码 "user"：组名、user\ 前缀、落位常量）。
UVPROJX_RENDER_LOCATION = "user/Project.uvprojx"
_UVPROJX_RENDER_DIR = Path(UVPROJX_RENDER_LOCATION).parent  # "user/"

# 启动文件候选命名：官方密度变体（md/hd/vd/xl/cl）统一为 startup_stm32f10x_*.s
_STARTUP_PATTERN = re.compile(r"^startup_stm32f10x_.*\.s$", re.IGNORECASE)


def is_startup_candidate(rel_path: str) -> bool:
    """启动文件候选识别：文件名匹配 startup_stm32f10x_*.s（大小写不敏感）。

    命中即"启动文件候选"：同一器件只需一份启动文件（决策 2），去重时优先
    _md（与目标板 C8T6 中密度匹配），落选候选规则剔除。非此命名的 .s
    （自定义汇编）不受影响。
    """
    return _STARTUP_PATTERN.match(Path(rel_path).name) is not None


def is_md_startup(rel_path: str) -> bool:
    """密度匹配判定：_md = 中容量，目标板 STM32F103C8T6 属中密度（决策 4）。

    密度守卫（入库前）：保留启动文件必须为 _md，否则大声失败"导入工程与
    目标板 STM32F103C8T6 不符"。
    """
    return Path(rel_path).name.lower().endswith("_md.s")


class KeilProjectError(Exception):
    """.uvprojx 缺失、重复或不是合法 XML。"""


class KeilPatcher:
    """ProjectPatcher 的 Keil 实现：注册模块文件 + 追加 include path。

    文件引用与 include path 相对 .uvprojx 所在目录（Keil 惯例）——母版
    .uvprojx 在 user/ 子目录（正点原子风格）时，模块文件在工程根的
    modules/ 下，条目写 .\..\modules\...（工单 09：母版现写后落位 user/，
    根级相对路径会解析到 user/modules/ 导致编译缺文件）。
    """

    def patch(
        self,
        project_dir: Path,
        module_files: Sequence[Path],
        include_dirs: Sequence[Path],
    ) -> None:
        uvprojx = _find_uvprojx(project_dir)
        root, original_text = parse_project_file(uvprojx, KeilProjectError)
        uvprojx_parts = uvprojx.parent.relative_to(project_dir).parts
        targets = root.findall("Targets/Target")
        if not targets:
            raise KeilProjectError(f"{uvprojx} 里没有 <Targets><Target>，无法注册模块")
        for target in targets:
            _register_module_files(target, module_files, uvprojx_parts)
            _append_include_dirs(target, include_dirs, uvprojx_parts)
        write_project_file(
            uvprojx,
            root,
            original_text,
            indent="  ",
            declaration='<?xml version="1.0" encoding="UTF-8" ?>',
            restore=lambda serialized: _restore_xmlns(serialized, root, original_text),
        )


def validate_project_structure(
    project_dir: Path, expected_sources: Sequence[str]
) -> None:
    """校验 .uvprojx 的编译链完整性（母版入库前调用）：配置节点齐全 + 树引用
    覆盖全部保留源码，失败抛 KeilProjectError。

    XML 合法不等于能编译——AI 整合出的 .uvprojx 曾把组清空（丢了启动文件 /
    system_stm32f10x.c 的引用）、Cads/IncludePath 节点整个消失，母版照常
    入库、生成时 KeilPatcher 才拒绝（判例 09）。三层校验：
    1. XML 语法合法（parse_project_file 既有职责，坏了直接抛）；
    2. 配置节点齐全：至少一个 Targets/Target、每个 Target 的
       TargetOption/TargetArmAds/Cads/VariousControls/IncludePath 存在——没有
       它模块 include path 无处可加，头文件无法解析（真实格式：IncludePath
       在 VariousControls 下，2026C/21F 母版同款）；
    3. 编译链完整：expected_sources（调用方按扫描同一套忽略规则计算的工程内
       全部 .c/.s）必须每个都在工程树里有引用（跨全部 Target 并集）——Keil
       只编译树里的文件，未引用的源码等于没有，"打开就能编译"不成立。
    解析基准与 KeilPatcher 相同（FilePath 相对 .uvprojx 所在目录），引用解析
    复用 _resolve_root_path。
    """
    uvprojx = _find_uvprojx(project_dir)
    root, _ = parse_project_file(uvprojx, KeilProjectError)
    uvprojx_parts = uvprojx.parent.relative_to(project_dir).parts
    targets = root.findall("Targets/Target")
    if not targets:
        raise KeilProjectError(f"{uvprojx.name} 里没有 <Targets><Target>，无法编译")
    for target in targets:
        if _find_include_path(target) is None:
            raise KeilProjectError(
                f"{uvprojx.name} 的 Target 缺少 Cads/VariousControls/IncludePath"
                " 节点，头文件无法解析"
            )
    referenced: set[str] = set()
    for target in targets:
        for group in target.findall("Groups/Group"):
            for files_el in group.findall("Files"):
                for file_el in files_el.findall("File"):
                    file_path = file_el.findtext("FilePath")
                    if file_path is None:
                        continue
                    resolved = _resolve_root_path(uvprojx_parts, file_path)
                    if resolved is not None:
                        referenced.add(resolved)
    missing = sorted(set(expected_sources) - referenced)
    if missing:
        shown = "、".join(missing[:10])
        if len(missing) > 10:
            shown += f"…（共 {len(missing)} 个）"
        raise KeilProjectError(
            f"{uvprojx.name} 工程树缺少 {len(missing)} 个保留源码的引用：{shown}"
        )


def _resolve_root_path(
    uvprojx_dir_parts: tuple[str, ...], file_path: str
) -> str | None:
    r"""把 .uvprojx 里的文件引用解析为工程根相对路径（小写 POSIX）。

    Keil 的 FilePath 相对 .uvprojx 所在目录（如 USER/proj.uvprojx 里的
    `.\..\sys\delay.c` = 工程根的 sys/delay.c）。`..` 弹出工程根之外（引用
    工程外文件）返回 None——保守视为悬空引用，不匹配保留集合、按原逻辑删除。
    """
    parts = [p for p in file_path.replace("\\", "/").split("/") if p not in ("", ".")]
    stack = list(uvprojx_dir_parts)
    for part in parts:
        if part == "..":
            if not stack:
                return None
            stack.pop()
        else:
            stack.append(part)
    return "/".join(stack).lower()


def _keil_rel_path_from(uvprojx_dir_parts: tuple[str, ...], target: str) -> str:
    r"""从 .uvprojx 所在目录到工程根相对目标文件的 Keil 路径（.\\ 前缀 + 反斜杠）。

    Keil 原生风格（补丁写引用用）：.uvprojx 在工程根时 = `.\main.c`；
    在 user/ 下时 = `.\..\main.c`。与渲染器的 _keil_rel_flat（正点原子风格，
    无 `.\..\` 前缀）同一相对规则、两种输出惯例——补丁不改写现写产物，
    各自保持各自的字节形态。
    """
    parts = [".."] * len(uvprojx_dir_parts) + target.split("/")
    return ".\\" + "\\".join(parts)


def _keil_rel_flat(uvprojx_dir_parts: tuple[str, ...], target: str) -> str:
    r"""相对 .uvprojx 所在目录的渲染器风格路径（正点原子惯例，唯一实现）。

    同目录文件（target 首段 = 所在目录名）→ `.\名`；其余 → `..\dir\名`
    （target "." = 所在目录自身 → `..`，IncludePath 的工程根写法）。渲染器
    产出与真实母版逐字节一致（2026C 实测：.\main.c / ..\code\motor.c /
    ..\sys\startup_stm32f10x_md.s）。
    """
    posix = target.replace("/", "\\")
    if posix == ".":
        return "\\".join([".."] * len(uvprojx_dir_parts))
    prefix = uvprojx_dir_parts[-1] + "\\"
    if posix.lower().startswith(prefix.lower()):
        return ".\\" + posix[len(prefix) :]
    return "..\\" + posix


def include_search_dirs(project_dir: Path) -> list[Path]:
    """工程 .uvprojx IncludePath 的目录（Keil 对引号头文件的搜索范围）。

    IncludePath 条目相对 .uvprojx 所在目录（Keil 惯例），解析为绝对目录、
    按出现顺序去重。找不到 .uvprojx 返回空列表——生成路径母版必有 uvprojx
    （KeilPatcher 兜底报错），此函数只为解析 include 搜索目录。
    """
    try:
        uvprojx = _find_uvprojx(project_dir)
    except KeilProjectError:
        return []
    root, _ = parse_project_file(uvprojx, KeilProjectError)
    dirs: list[Path] = []
    seen: set[str] = set()
    for target in root.findall("Targets/Target"):
        include_el = _find_include_path(target)
        if include_el is None or not include_el.text:
            continue
        for entry in include_el.text.split(";"):
            entry = entry.strip().replace("\\", "/")
            if not entry:
                continue
            p = Path(entry)
            resolved = p if p.is_absolute() else (uvprojx.parent / p)
            key = str(resolved).lower()
            if key not in seen:
                seen.add(key)
                dirs.append(resolved.resolve())
    return dirs


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
        include_path = _find_include_path(target)
        if device:
            lines.append(f"{uvprojx.name} 设备：{device}")
        if include_path is not None and include_path.text:
            lines.append(f"{uvprojx.name} include path：{include_path.text}")
    if not lines:
        lines.append(f"{uvprojx.name}：未找到设备 / include path 配置")
    return tuple(lines)


def _find_uvprojx(project_dir: Path) -> Path:
    """定位工程文件 .uvprojx：任意层级（正点原子风格在 USER/ 子目录），统一
    噪音跳过规则（treewalk：.git 任意层级 + 构建输出目录——Listings/ 下的
    拷贝不算数，与 master 扫描同一规则）。"""
    candidates = sorted(iter_project_files(project_dir, pattern="*.uvprojx"))
    if not candidates:
        raise KeilProjectError(f"工程目录里没有 .uvprojx 文件：{project_dir}")
    if len(candidates) > 1:
        raise KeilProjectError(
            "工程目录里有多个 .uvprojx，无法确定改哪个："
            + "、".join(p.name for p in candidates)
        )
    return candidates[0]


# ---------------------------------------------------------------------------
# 母版提炼（工单 09）：.uvprojx 确定性现写
# ---------------------------------------------------------------------------

_MASTER_XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>'
_MASTER_ROOT_OPEN = (
    '<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    ' xsi:noNamespaceSchemaLocation="project_projx.xsd">'
)

# 设备块模板：从真实工程（2026C / 21F，用户机器可编译）原样提取的静态部分，
# 只有两个动态占位符——{INCLUDE_PATH}（Cads/VariousControls/IncludePath 的值）
# 与 {GROUPS}（文件树整块）。设备配置硬编码 C8T6（决策 4：平台线即
# STM32F103C8T6/Keil5）：Device STM32F103C8、IRAM(0x20000000,0x5000) IROM
# (0x08000000,0x10000)（C8T6 20KB RAM / 64KB Flash）、ToolsetNumber 0x4
# （ARM-ADS）、SchemaVersion 2.1。StartupFile 留空——与两份真实母版一致：
# 启动文件经工程树注册（FileType 2）即可编译，不设 StartupFile（grilling
# 决策 1 的"StartupFile 指向启动文件"以此为准修正，见 ADR 0003）。
_MASTER_UVPROJX_TEMPLATE = r"""  <SchemaVersion>2.1</SchemaVersion>

  <Header>### uVision Project, (C) Keil Software</Header>

  <Targets>
    <Target>
      <TargetName>Target 1</TargetName>
      <ToolsetNumber>0x4</ToolsetNumber>
      <ToolsetName>ARM-ADS</ToolsetName>
      <pCCUsed>5060960::V5.06 update 7 (build 960)::.\ARMCC</pCCUsed>
      <uAC6>0</uAC6>
      <TargetOption>
        <TargetCommonOption>
          <Device>STM32F103C8</Device>
          <Vendor>STMicroelectronics</Vendor>
          <PackID>Keil.STM32F1xx_DFP.2.4.0</PackID>
          <PackURL>http://www.keil.com/pack/</PackURL>
          <Cpu>IRAM(0x20000000,0x5000) IROM(0x08000000,0x10000) CPUTYPE("Cortex-M3") CLOCK(12000000) ELITTLE</Cpu>
          <FlashUtilSpec></FlashUtilSpec>
          <StartupFile></StartupFile>
          <FlashDriverDll>UL2CM3(-S0 -C0 -P0 -FD20000000 -FC1000 -FN1 -FF0STM32F10x_128 -FS08000000 -FL020000 -FP0($$Device:STM32F103C8$Flash\STM32F10x_128.FLM))</FlashDriverDll>
          <DeviceId>0</DeviceId>
          <RegisterFile>$$Device:STM32F103C8$Device\Include\stm32f10x.h</RegisterFile>
          <MemoryEnv></MemoryEnv>
          <Cmp></Cmp>
          <Asm></Asm>
          <Linker></Linker>
          <OHString></OHString>
          <InfinionOptionDll></InfinionOptionDll>
          <SLE66CMisc></SLE66CMisc>
          <SLE66AMisc></SLE66AMisc>
          <SLE66LinkerMisc></SLE66LinkerMisc>
          <SFDFile>$$Device:STM32F103C8$SVD\STM32F103xx.svd</SFDFile>
          <bCustSvd>0</bCustSvd>
          <UseEnv>0</UseEnv>
          <BinPath></BinPath>
          <IncludePath></IncludePath>
          <LibPath></LibPath>
          <RegisterFilePath></RegisterFilePath>
          <DBRegisterFilePath></DBRegisterFilePath>
          <TargetStatus>
            <Error>0</Error>
            <ExitCodeStop>0</ExitCodeStop>
            <ButtonStop>0</ButtonStop>
            <NotGenerated>0</NotGenerated>
            <InvalidFlash>1</InvalidFlash>
          </TargetStatus>
          <OutputDirectory>.\Objects\</OutputDirectory>
          <OutputName>Project</OutputName>
          <CreateExecutable>1</CreateExecutable>
          <CreateLib>0</CreateLib>
          <CreateHexFile>1</CreateHexFile>
          <DebugInformation>1</DebugInformation>
          <BrowseInformation>1</BrowseInformation>
          <ListingPath>.\Listings\</ListingPath>
          <HexFormatSelection>1</HexFormatSelection>
          <Merge32K>0</Merge32K>
          <CreateBatchFile>0</CreateBatchFile>
          <BeforeCompile>
            <RunUserProg1>0</RunUserProg1>
            <RunUserProg2>0</RunUserProg2>
            <UserProg1Name></UserProg1Name>
            <UserProg2Name></UserProg2Name>
            <UserProg1Dos16Mode>0</UserProg1Dos16Mode>
            <UserProg2Dos16Mode>0</UserProg2Dos16Mode>
            <nStopU1X>0</nStopU1X>
            <nStopU2X>0</nStopU2X>
          </BeforeCompile>
          <BeforeMake>
            <RunUserProg1>0</RunUserProg1>
            <RunUserProg2>0</RunUserProg2>
            <UserProg1Name></UserProg1Name>
            <UserProg2Name></UserProg2Name>
            <UserProg1Dos16Mode>0</UserProg1Dos16Mode>
            <UserProg2Dos16Mode>0</UserProg2Dos16Mode>
            <nStopB1X>0</nStopB1X>
            <nStopB2X>0</nStopB2X>
          </BeforeMake>
          <AfterMake>
            <RunUserProg1>0</RunUserProg1>
            <RunUserProg2>0</RunUserProg2>
            <UserProg1Name></UserProg1Name>
            <UserProg2Name></UserProg2Name>
            <UserProg1Dos16Mode>0</UserProg1Dos16Mode>
            <UserProg2Dos16Mode>0</UserProg2Dos16Mode>
            <nStopA1X>0</nStopA1X>
            <nStopA2X>0</nStopA2X>
          </AfterMake>
          <SelectedForBatchBuild>0</SelectedForBatchBuild>
          <SVCSIdString></SVCSIdString>
        </TargetCommonOption>
        <CommonProperty>
          <UseCPPCompiler>0</UseCPPCompiler>
          <RVCTCodeConst>0</RVCTCodeConst>
          <RVCTZI>0</RVCTZI>
          <RVCTOtherData>0</RVCTOtherData>
          <ModuleSelection>0</ModuleSelection>
          <IncludeInBuild>1</IncludeInBuild>
          <AlwaysBuild>0</AlwaysBuild>
          <GenerateAssemblyFile>0</GenerateAssemblyFile>
          <AssembleAssemblyFile>0</AssembleAssemblyFile>
          <PublicsOnly>0</PublicsOnly>
          <StopOnExitCode>3</StopOnExitCode>
          <CustomArgument></CustomArgument>
          <IncludeLibraryModules></IncludeLibraryModules>
          <ComprImg>1</ComprImg>
        </CommonProperty>
        <DllOption>
          <SimDllName>SARMCM3.DLL</SimDllName>
          <SimDllArguments> -REMAP</SimDllArguments>
          <SimDlgDll>DCM.DLL</SimDlgDll>
          <SimDlgDllArguments>-pCM3</SimDlgDllArguments>
          <TargetDllName>SARMCM3.DLL</TargetDllName>
          <TargetDllArguments></TargetDllArguments>
          <TargetDlgDll>TCM.DLL</TargetDlgDll>
          <TargetDlgDllArguments>-pCM3</TargetDlgDllArguments>
        </DllOption>
        <DebugOption>
          <OPTHX>
            <HexSelection>1</HexSelection>
            <HexRangeLowAddress>0</HexRangeLowAddress>
            <HexRangeHighAddress>0</HexRangeHighAddress>
            <HexOffset>0</HexOffset>
            <Oh166RecLen>16</Oh166RecLen>
          </OPTHX>
        </DebugOption>
        <Utilities>
          <Flash1>
            <UseTargetDll>1</UseTargetDll>
            <UseExternalTool>0</UseExternalTool>
            <RunIndependent>0</RunIndependent>
            <UpdateFlashBeforeDebugging>1</UpdateFlashBeforeDebugging>
            <Capability>1</Capability>
            <DriverSelection>-1</DriverSelection>
          </Flash1>
          <bUseTDR>1</bUseTDR>
          <Flash2>BIN\UL2CM3.DLL</Flash2>
          <Flash3></Flash3>
          <Flash4></Flash4>
          <pFcarmOut></pFcarmOut>
          <pFcarmGrp></pFcarmGrp>
          <pFcArmRoot></pFcArmRoot>
          <FcArmLst>0</FcArmLst>
        </Utilities>
        <TargetArmAds>
          <ArmAdsMisc>
            <GenerateListings>0</GenerateListings>
            <asHll>1</asHll>
            <asAsm>1</asAsm>
            <asMacX>1</asMacX>
            <asSyms>1</asSyms>
            <asFals>1</asFals>
            <asDbgD>1</asDbgD>
            <asForm>1</asForm>
            <ldLst>0</ldLst>
            <ldmm>1</ldmm>
            <ldXref>1</ldXref>
            <BigEnd>0</BigEnd>
            <AdsALst>1</AdsALst>
            <AdsACrf>1</AdsACrf>
            <AdsANop>0</AdsANop>
            <AdsANot>0</AdsANot>
            <AdsLLst>1</AdsLLst>
            <AdsLmap>1</AdsLmap>
            <AdsLcgr>1</AdsLcgr>
            <AdsLsym>1</AdsLsym>
            <AdsLszi>1</AdsLszi>
            <AdsLtoi>1</AdsLtoi>
            <AdsLsun>1</AdsLsun>
            <AdsLven>1</AdsLven>
            <AdsLsxf>1</AdsLsxf>
            <RvctClst>0</RvctClst>
            <GenPPlst>0</GenPPlst>
            <AdsCpuType>"Cortex-M3"</AdsCpuType>
            <RvctDeviceName></RvctDeviceName>
            <mOS>0</mOS>
            <uocRom>0</uocRom>
            <uocRam>0</uocRam>
            <hadIROM>1</hadIROM>
            <hadIRAM>1</hadIRAM>
            <hadXRAM>0</hadXRAM>
            <uocXRam>0</uocXRam>
            <RvdsVP>0</RvdsVP>
            <RvdsMve>0</RvdsMve>
            <RvdsCdeCp>0</RvdsCdeCp>
            <nBranchProt>0</nBranchProt>
            <hadIRAM2>0</hadIRAM2>
            <hadIROM2>0</hadIROM2>
            <StupSel>8</StupSel>
            <useUlib>0</useUlib>
            <EndSel>0</EndSel>
            <uLtcg>0</uLtcg>
            <nSecure>0</nSecure>
            <RoSelD>3</RoSelD>
            <RwSelD>3</RwSelD>
            <CodeSel>0</CodeSel>
            <OptFeed>0</OptFeed>
            <NoZi1>0</NoZi1>
            <NoZi2>0</NoZi2>
            <NoZi3>0</NoZi3>
            <NoZi4>0</NoZi4>
            <NoZi5>0</NoZi5>
            <Ro1Chk>0</Ro1Chk>
            <Ro2Chk>0</Ro2Chk>
            <Ro3Chk>0</Ro3Chk>
            <Ir1Chk>1</Ir1Chk>
            <Ir2Chk>0</Ir2Chk>
            <Ra1Chk>0</Ra1Chk>
            <Ra2Chk>0</Ra2Chk>
            <Ra3Chk>0</Ra3Chk>
            <Im1Chk>1</Im1Chk>
            <Im2Chk>0</Im2Chk>
            <OnChipMemories>
              <Ocm1>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </Ocm1>
              <Ocm2>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </Ocm2>
              <Ocm3>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </Ocm3>
              <Ocm4>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </Ocm4>
              <Ocm5>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </Ocm5>
              <Ocm6>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </Ocm6>
              <IRAM>
                <Type>0</Type>
                <StartAddress>0x20000000</StartAddress>
                <Size>0x5000</Size>
              </IRAM>
              <IROM>
                <Type>1</Type>
                <StartAddress>0x8000000</StartAddress>
                <Size>0x10000</Size>
              </IROM>
              <XRAM>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </XRAM>
              <OCR_RVCT1>
                <Type>1</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </OCR_RVCT1>
              <OCR_RVCT2>
                <Type>1</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </OCR_RVCT2>
              <OCR_RVCT3>
                <Type>1</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </OCR_RVCT3>
              <OCR_RVCT4>
                <Type>1</Type>
                <StartAddress>0x8000000</StartAddress>
                <Size>0x10000</Size>
              </OCR_RVCT4>
              <OCR_RVCT5>
                <Type>1</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </OCR_RVCT5>
              <OCR_RVCT6>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </OCR_RVCT6>
              <OCR_RVCT7>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </OCR_RVCT7>
              <OCR_RVCT8>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </OCR_RVCT8>
              <OCR_RVCT9>
                <Type>0</Type>
                <StartAddress>0x20000000</StartAddress>
                <Size>0x5000</Size>
              </OCR_RVCT9>
              <OCR_RVCT10>
                <Type>0</Type>
                <StartAddress>0x0</StartAddress>
                <Size>0x0</Size>
              </OCR_RVCT10>
            </OnChipMemories>
            <RvctStartVector></RvctStartVector>
          </ArmAdsMisc>
          <Cads>
            <interw>1</interw>
            <Optim>1</Optim>
            <oTime>0</oTime>
            <SplitLS>0</SplitLS>
            <OneElfS>1</OneElfS>
            <Strict>0</Strict>
            <EnumInt>0</EnumInt>
            <PlainCh>0</PlainCh>
            <Ropi>0</Ropi>
            <Rwpi>0</Rwpi>
            <wLevel>2</wLevel>
            <uThumb>0</uThumb>
            <uSurpInc>0</uSurpInc>
            <uC99>1</uC99>
            <uGnu>1</uGnu>
            <useXO>0</useXO>
            <v6Lang>1</v6Lang>
            <v6LangP>1</v6LangP>
            <vShortEn>1</vShortEn>
            <vShortWch>1</vShortWch>
            <v6Lto>0</v6Lto>
            <v6WtE>0</v6WtE>
            <v6Rtti>0</v6Rtti>
            <VariousControls>
              <MiscControls></MiscControls>
              <Define></Define>
              <Undefine></Undefine>
              <IncludePath>{INCLUDE_PATH}</IncludePath>
            </VariousControls>
          </Cads>
          <Aads>
            <interw>1</interw>
            <Ropi>0</Ropi>
            <Rwpi>0</Rwpi>
            <thumb>0</thumb>
            <SplitLS>0</SplitLS>
            <SwStkChk>0</SwStkChk>
            <NoWarn>0</NoWarn>
            <uSurpInc>0</uSurpInc>
            <useXO>0</useXO>
            <ClangAsOpt>4</ClangAsOpt>
            <VariousControls>
              <MiscControls></MiscControls>
              <Define></Define>
              <Undefine></Undefine>
              <IncludePath></IncludePath>
            </VariousControls>
          </Aads>
          <LDads>
            <umfTarg>1</umfTarg>
            <Ropi>0</Ropi>
            <Rwpi>0</Rwpi>
            <noStLib>0</noStLib>
            <RepFail>1</RepFail>
            <useFile>0</useFile>
            <TextAddressRange>0x08000000</TextAddressRange>
            <DataAddressRange>0x20000000</DataAddressRange>
            <pXoBase></pXoBase>
            <ScatterFile></ScatterFile>
            <IncludeLibs></IncludeLibs>
            <IncludeLibsPath></IncludeLibsPath>
            <Misc></Misc>
            <LinkerInputFile></LinkerInputFile>
            <DisabledWarnings></DisabledWarnings>
          </LDads>
        </TargetArmAds>
      </TargetOption>
      {GROUPS}
    </Target>
  </Targets>

  <RTE>
    <apis/>
    <components/>
    <files/>
  </RTE>
"""


def build_master_uvprojx(
    kept_paths: Sequence[str],
    startup_path: str | None,
    include_dirs: Sequence[str],
) -> str:
    """确定性渲染 .uvprojx 全文（不落盘）：设备块 + 文件树 + IncludePath。

    kept_paths 是母版里保留文件的工程根相对路径（.c/.s 全量入树，其余不进
    树；模板 main.c 自动补条目——落位工程根，见 _build_groups）；startup_path
    是保留的启动文件（密度守卫在此：非 _md 拒绝，目标板 STM32F103C8T6 中
    密度，决策 4）；include_dirs 是保留 .h 所在目录（工程根相对）。

    同一输入必然同一输出（字符串拼接 + 全排序），结构一致性由构造保证——
    判例 09 治本：工程配置文件移出 AI 手写 XML（结构残缺照样入库），渲染
    产物无悬空引用、无缺失节点。
    """
    if startup_path is not None and not is_md_startup(startup_path):
        raise KeilProjectError(
            f"导入工程与目标板 STM32F103C8T6 不符"
            f"（启动文件为 {Path(startup_path).name}）"
        )
    return (
        _MASTER_XML_DECLARATION
        + "\n"
        + _MASTER_ROOT_OPEN
        + "\n\n"
        + _MASTER_UVPROJX_TEMPLATE.format(
            INCLUDE_PATH=_render_include_path(include_dirs),
            GROUPS=_build_groups(kept_paths),
        )
        + "\n</Project>\n"
    )


def render_master_uvprojx(
    project_dir: Path,
    kept_paths: Sequence[str],
    startup_path: str | None,
    include_dirs: Sequence[str],
) -> Path:
    """把 .uvprojx 现写落盘（固定 user/Project.uvprojx，正点原子风格），
    返回落盘路径。密度守卫（非 _md 启动）在 build_master_uvprojx 里。"""
    target = project_dir / UVPROJX_RENDER_LOCATION
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        build_master_uvprojx(kept_paths, startup_path, include_dirs),
        encoding="utf-8",
    )
    return target


def _render_include_path(include_dirs: Sequence[str]) -> str:
    r"""IncludePath 值：保留 .h 所在目录，去重、排序、相对 .uvprojx 所在目录
    （真实惯例：..\dir;..\dir——2026C 为 ..\user;..\ml_libs;..\code;..\sys；
    路径语义与文件引用同一实现 _keil_rel_flat，布局只随 UVPROJX_RENDER_LOCATION）。"""
    seen: list[str] = []
    for directory in sorted({d for d in include_dirs if d}):
        rel = _keil_rel_flat(_UVPROJX_RENDER_DIR.parts, directory)
        if rel not in seen:
            seen.append(rel)
    return ";".join(seen)


def _build_groups(kept_paths: Sequence[str]) -> str:
    """文件树整块 XML（<Groups>…</Groups>）：按顶层目录分组（真实母版
    sys/ml_libs/user 风格）、组内按路径排序，引用全部保留 .c/.s。

    模板 main.c 自动补条目：落位工程根、进 user 组（正点原子风格：工程自身
    目录组）、引用 ..\main.c（相对 user/ 的工程根）。启动文件作为保留 .s
    正常入组（FileType 2，编译链必需件由构造保证在树内）。
    """
    groups: dict[str, list[str]] = {}
    for path in sorted(kept_paths):
        suffix = Path(path).suffix.lower()
        if suffix not in _SOURCE_FILETYPES:
            continue
        parent = Path(path).parent
        group = parent.parts[0] if parent.parts else _UVPROJX_RENDER_DIR.parts[-1]
        groups.setdefault(group, []).append(path)
    groups.setdefault(_UVPROJX_RENDER_DIR.parts[-1], []).append("main.c")

    blocks: list[str] = []
    for name in sorted(groups):
        file_lines = "\n".join(_render_file_entry(p) for p in sorted(groups[name]))
        blocks.append(
            "        <Group>\n"
            f"          <GroupName>{escape(name)}</GroupName>\n"
            "          <Files>\n"
            f"{file_lines}\n"
            "          </Files>\n"
            "        </Group>"
        )
    return "      <Groups>\n" + "\n".join(blocks) + "\n      </Groups>"


def _render_file_entry(path: str) -> str:
    """单个文件条目：FileName / FileType / FilePath（相对 .uvprojx 所在目录）。"""
    suffix = Path(path).suffix.lower()
    file_type = _SOURCE_FILETYPES[suffix]
    return (
        "            <File>\n"
        f"              <FileName>{escape(Path(path).name)}</FileName>\n"
        f"              <FileType>{file_type}</FileType>\n"
        f"              <FilePath>{escape(_render_file_path(path))}</FilePath>\n"
        "            </File>"
    )


def _render_file_path(path: str) -> str:
    r"""文件引用路径（相对 .uvprojx 所在目录，正点原子惯例）：同目录 .\name，
    其余 ..\dir\name——真实母版惯例（2026C：.\main.c / ..\code\motor.c /
    ..\sys\startup_stm32f10x_md.s）。main.c 落位工程根 → ..\main.c。"""
    return _keil_rel_flat(_UVPROJX_RENDER_DIR.parts, path)


_XMLNS_DECL_RE = re.compile(r'xmlns(?:[:\w-]+)?="[^"]*"')


def _restore_xmlns(serialized: str, root: ET.Element, original_text: str) -> str:
    """补回 ET 解析时丢弃的根元素 xmlns 声明（对 Keil 无影响，尽量少动母版）。"""
    decls = _XMLNS_DECL_RE.findall(original_text)
    if not decls:
        return serialized
    return serialized.replace(
        f"<{root.tag}>", f"<{root.tag} " + " ".join(decls) + ">", 1
    )


def _find_include_path(target: ET.Element) -> ET.Element | None:
    """Target 的 Cads/IncludePath 元素（真实格式在 VariousControls 下）。

    格式知识唯一走查实现：patch 追加、validate 校验、config 摘要共用，
    不各自另抄路径。
    """
    return target.find("TargetOption/TargetArmAds/Cads/VariousControls/IncludePath")


def _register_module_files(
    target: ET.Element, module_files: Sequence[Path], uvprojx_parts: tuple[str, ...]
) -> None:
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
        ET.SubElement(entry, "FilePath").text = _keil_rel_path_from(
            uvprojx_parts, str(file)
        )


def _append_include_dirs(
    target: ET.Element, include_dirs: Sequence[Path], uvprojx_parts: tuple[str, ...]
) -> None:
    include_el = _find_include_path(target)
    if include_el is None:
        raise KeilProjectError(
            "工程里没有 Cads/VariousControls/IncludePath 节点，无法加入模块"
            " include path，拒绝产出残缺工程"
        )
    existing = [s for s in (include_el.text or "").split(";") if s]
    existing_lower = {s.lower() for s in existing}
    additions = [
        _keil_rel_path_from(uvprojx_parts, str(d))
        for d in include_dirs
        if _keil_rel_path_from(uvprojx_parts, str(d)).lower() not in existing_lower
    ]
    if additions:
        prefix = include_el.text + ";" if include_el.text else ""
        include_el.text = prefix + ";".join(additions)
