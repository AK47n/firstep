"""测试假件与构造器：假模块库、假母版、假 LLM、记录桩。

只放纯数据/构造逻辑，不放 pytest fixture（fixture 见 conftest.py）。
"""

from __future__ import annotations

import json
import zlib
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.sax.saxutils import escape

from pypdf import PdfWriter

from contest_generator.events import ProgressEmitter
from contest_generator.library import ValidationResult
from contest_generator.manifest import ManifestSummary
from contest_generator.report import FileDecision, JudgmentFile, ReferenceCandidate
from contest_generator.selection import ModuleSelection, ReferenceSuggestion
from contest_generator.topic_library import TopicDraft

# ---------------------------------------------------------------------------
# 假模块文件内容（断言输出目录里文件内容用）
# ---------------------------------------------------------------------------

# 自包含约定：模块 .c 必须 include 自己的 .h（生成门禁 _check_module_self_include
# 强制，假模块与真实模块同规则）
DHT11_STM32_C = "#include \"dht11.h\"\n/* DHT11 driver for STM32 */\nfloat dht11_read(void);\n"
DHT11_MSPM0_C = "#include \"dht11.h\"\n/* DHT11 driver for MSPM0 */\nfloat dht11_read(void);\n"
DHT11_H = "#pragma once\nfloat dht11_read(void);\n"
OLED_STM32_C = "#include \"oled.h\"\n/* OLED driver for STM32 */\nvoid oled_init(void);\n"
OLED_H = "#pragma once\nvoid oled_init(void);\n"

# 测试直接传入生成器的 main.c 内容（生成器会静态自检，必须只调所选模块头文件
# 里真实存在的函数；自检逻辑见 skeleton.py）
MAIN_SKELETON = "int main(void) { float t = dht11_read(); while (1); }\n"

# 假母版的 .uvprojx：结构真实的 Keil5 工程文件（设备型号、Cpu、IncludePath
# 在 Cads/VariousControls 下——真实 Keil 格式（2026C/21F 同款）、一个含
# main.c 的源组）。修改器只该动 IncludePath 与 Groups，其余原样保留。
FAKE_UVPROJX = r'''<?xml version="1.0" encoding="UTF-8" ?>
<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <SchemaVersion>2.1</SchemaVersion>
  <HeaderVersion>1.0</HeaderVersion>
  <Targets>
    <Target>
      <TargetName>STM32F103C8</TargetName>
      <ToolsetNumber>0x4</ToolsetNumber>
      <ToolsetName>ARM-ADS</ToolsetName>
      <TargetOption>
        <TargetCommonOption>
          <Device>STM32F103C8</Device>
          <Vendor>STMicroelectronics</Vendor>
          <Cpu>IRAM(0x20000000,0x5000) IROM(0x08000000,0x10000)</Cpu>
        </TargetCommonOption>
        <TargetArmAds>
          <ArmAdsMisc>
            <useUlib>1</useUlib>
          </ArmAdsMisc>
          <Cads>
            <VariousControls>
              <MiscControls></MiscControls>
              <Define></Define>
              <Undefine></Undefine>
              <IncludePath>.\inc;.\src</IncludePath>
            </VariousControls>
          </Cads>
        </TargetArmAds>
      </TargetOption>
      <Groups>
        <Group>
          <GroupName>Source Group 1</GroupName>
          <Files>
            <File>
              <FileName>main.c</FileName>
              <FileType>1</FileType>
              <FilePath>.\main.c</FilePath>
            </File>
            <File>
              <FileName>system_stm32f10x.c</FileName>
              <FileType>1</FileType>
              <FilePath>.\src\system_stm32f10x.c</FilePath>
            </File>
          </Files>
        </Group>
      </Groups>
    </Target>
  </Targets>
</Project>
'''


def make_fake_module_library(library_dir: Path) -> Path:
    """假模块库：dht11（双平台验证过，依赖 delay）、oled（仅 stm32）、
    delay（双平台，平铺文件）、broken（manifest 指向不存在的文件）。"""
    _add_module(
        library_dir,
        {
            "slug": "dht11",
            "description": "DHT11 温湿度传感器驱动",
            "dependencies": ["delay"],
            "platforms": {
                "stm32": {
                    "files": ["stm32/src/dht11.c", "inc/dht11.h"],
                    "verified": True,
                    "hardware_bound": False,
                    "notes": "PA0",
                },
                "mspm0": {
                    "files": ["mspm0/src/dht11.c", "inc/dht11.h"],
                    "verified": True,
                },
            },
        },
        {
            "stm32/src/dht11.c": DHT11_STM32_C,
            "mspm0/src/dht11.c": DHT11_MSPM0_C,
            "inc/dht11.h": DHT11_H,
        },
    )
    _add_module(
        library_dir,
        {
            "slug": "oled",
            "description": "OLED 屏显驱动",
            "platforms": {
                "stm32": {"files": ["stm32/src/oled.c", "inc/oled.h"], "verified": True}
            },
        },
        {"stm32/src/oled.c": OLED_STM32_C, "inc/oled.h": OLED_H},
    )
    _add_module(
        library_dir,
        {
            "slug": "delay",
            "description": "软件延时",
            "platforms": {
                "stm32": {"files": ["delay.c", "delay.h"], "verified": True},
                "mspm0": {"files": ["delay.c", "delay.h"], "verified": True},
            },
        },
        {
            "delay.c": "#include \"delay.h\"\n/* delay */\nvoid delay_ms(int ms);\n",
            "delay.h": "#pragma once\nvoid delay_ms(int ms);\n",
        },
    )
    _add_module(
        library_dir,
        {
            "slug": "broken",
            "description": "manifest 指向的文件不存在",
            "platforms": {"stm32": {"files": ["stm32/src/broken.c"]}},
        },
        {},
    )
    return library_dir


# ---------------------------------------------------------------------------
# 母版提炼的假旧工程（工单 08）：proj-a / proj-b 两个同平台工程
# ---------------------------------------------------------------------------

# 提炼用假工程 .uvprojx：设备 / include path 两个对比点（A 多一个 .\src）+
# 工程树（Groups/Files，引用 proj-a 自己的 .c 源码——真实 Keil 工程的形态；
# 母版入库的结构校验要求每个保留源码都在工程树里有引用，无树配置 = 坏母版）。
# IncludePath 在 Cads/VariousControls 下（真实 Keil 格式，2026C/21F 同款）。
FAKE_DISTILL_UVPROJX_A = r'''<?xml version="1.0" encoding="UTF-8" ?>
<Project>
  <Targets>
    <Target>
      <TargetName>proj-a</TargetName>
      <TargetOption>
        <TargetCommonOption>
          <Device>STM32F103C8</Device>
        </TargetCommonOption>
        <TargetArmAds>
          <Cads>
            <VariousControls>
              <MiscControls></MiscControls>
              <Define></Define>
              <Undefine></Undefine>
              <IncludePath>.\inc;.\src</IncludePath>
            </VariousControls>
          </Cads>
        </TargetArmAds>
      </TargetOption>
      <Groups>
        <Group>
          <GroupName>Source Group 1</GroupName>
          <Files>
            <File>
              <FileName>main.c</FileName>
              <FileType>1</FileType>
              <FilePath>.\main.c</FilePath>
            </File>
            <File>
              <FileName>oled.c</FileName>
              <FileType>1</FileType>
              <FilePath>.\src\oled.c</FilePath>
            </File>
            <File>
              <FileName>system_stm32f10x.c</FileName>
              <FileType>1</FileType>
              <FilePath>.\src\system_stm32f10x.c</FilePath>
            </File>
            <File>
              <FileName>dht11.c</FileName>
              <FileType>1</FileType>
              <FilePath>.\sensors\dht11.c</FilePath>
            </File>
          </Files>
        </Group>
      </Groups>
    </Target>
  </Targets>
</Project>
'''

FAKE_DISTILL_UVPROJX_B = FAKE_DISTILL_UVPROJX_A.replace(
    "<TargetName>proj-a</TargetName>", "<TargetName>proj-b</TargetName>"
).replace(
    "<IncludePath>.\\inc;.\\src</IncludePath>", "<IncludePath>.\\inc</IncludePath>"
).replace(
    "</File>\n          </Files>",
    "</File>\n"
    "            <File>\n"
    "              <FileName>oled_fonts.c</FileName>\n"
    "              <FileType>1</FileType>\n"
    "              <FilePath>.\\ui\\oled_fonts.c</FilePath>\n"
    "            </File>\n"
    "          </Files>",
)


def make_fake_stm32_projects(base_dir: Path) -> tuple[Path, Path]:
    """两个同平台旧工程（母版提炼素材）：公共文件内容一致、两处冲突
    （project.uvprojx / src/oled.c）、各自独有的残留文件；.git 与构建产物
    目录（Debug/Release）应在扫描时被忽略；源码树内的残留（.o/.bak/.
    hex/~）应规则识别、确定性剔除但进报告。"""
    common = {
        "inc/stm32f10x_conf.h": "#pragma once\n",
        "src/system_stm32f10x.c": "/* startup/system */\n",
    }
    proj_a = base_dir / "proj-a"
    _write_files(proj_a, {
        **common,
        # 旧工程 main.c 内容两工程不同（各写各的赛题逻辑）——一律不进母版，
        # 由确定性模板 main.c 替代（ADR 0002），内容差异无碍
        "main.c": "/* proj-a 的赛题 main */\nint main(void) { while (1); }\n",
        "project.uvprojx": FAKE_DISTILL_UVPROJX_A,
        "project.uvoptx": "<ProjectOpt><Targets/></ProjectOpt>",  # IDE 用户选项
        "src/oled.c": "/* 通用 OLED 驱动（A 版本） */\nvoid oled_init(void);\n",
        "sensors/dht11.c": "/* 通用 DHT11 驱动 */\nfloat dht11_read(void);\n",
        "src/oled.o": "ELF junk",  # 构建产物
        "main.c.bak": "backup",  # 备份文件
        ".git/HEAD": "ref: refs/heads/main\n",
        "Debug/out.axf": "binary junk",
    })
    proj_b = base_dir / "proj-b"
    _write_files(proj_b, {
        **common,
        "main.c": "/* proj-b 的赛题 main（业务逻辑不同） */\nint main(void) { while (1); }\n",
        "project.uvprojx": FAKE_DISTILL_UVPROJX_B,
        "project.uvoptx": "<ProjectOpt><Targets/></ProjectOpt>",  # IDE 用户选项
        "src/oled.c": "/* 通用 OLED 驱动（B 版本） */\nvoid oled_init(void);\n",
        "ui/oled_fonts.c": "/* 上一场比赛的字体表 */\nconst unsigned char font[1];\n",
        "src/oled.hex": "hex junk",  # 构建产物
        "ui/oled_fonts.c~": "backup",  # 备份文件（编辑器临时备份）
        ".git/HEAD": "ref: refs/heads/main\n",
        "Release/oled.o": "binary junk",
    })
    return proj_a, proj_b


def _write_files(root: Path, files: dict[str, str]) -> None:
    for relpath, content in files.items():
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


# 假母版的 .cproject：结构真实的 CCS（Eclipse CDT managed build）工程文件。
# Debug/Release 双配置，toolchain 里带 buildIncludePath 选项，sourceEntries 有根条目。
# 与 .uvprojx 的关键差异：CCS 不逐文件枚举源文件，构建系统扫描 sourceEntries 目录。
FAKE_CPROJECT = r'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<?fileVersion 4.0.0?><cproject storage_type_id="org.eclipse.cdt.core.XmlProjectDescriptionStorage">
  <storageModule moduleId="org.eclipse.cdt.core.settings">
    <cconfiguration id="ti.ccs.project.toolchain.configuration.debug.12345">
      <storageModule moduleId="org.eclipse.cdt.core.externalSettings"/>
      <storageModule moduleId="org.eclipse.cdt.core.settings">
        <extensions>
          <extension id="org.eclipse.cdt.core.ELF" point="org.eclipse.cdt.core.BinaryParser"/>
          <extension id="org.eclipse.cdt.core.MakeErrorParser" point="org.eclipse.cdt.core.ErrorParser"/>
        </extensions>
        <cdtBuildSystem buildArtefactType="org.eclipse.cdt.build.core.buildArtefactType.exe" buildId="org.eclipse.cdt.build.core.buildArtefactType.exe" buildProperties="org.eclipse.cdt.build.core.buildArtefactType=org.eclipse.cdt.build.core.buildArtefactType.exe,org.eclipse.cdt.build.core.buildType=org.eclipse.cdt.build.core.buildType.debug" comment="Build configuration: Debug" id="ti.ccs.project.toolchain.configuration.debug.12345" name="Debug">
          <configuration artifactExtension="out" artifactName="${ProjName}" buildArtefactType="org.eclipse.cdt.build.core.buildArtefactType.exe" buildProperties="org.eclipse.cdt.build.core.buildArtefactType=org.eclipse.cdt.build.core.buildArtefactType.exe,org.eclipse.cdt.build.core.buildType=org.eclipse.cdt.build.core.buildType.debug" comment="Build configuration: Debug" id="ti.ccs.project.toolchain.configuration.debug.12345" name="Debug" parent="ti.ccs.project.toolchain.configuration.debug.12345">
            <folderInfo id="ti.ccs.project.toolchain.configuration.debug.12345." name="/" resourcePath="">
              <toolChain id="ti.ccs.project.toolchain.debug.23456" name="TI Code Generation Tools" superClass="ti.ccs.project.toolchain.debug">
                <option id="ti.ccs.misc.options.buildDefine.34567" name="Build Defines" superClass="ti.ccs.misc.options.buildDefine" valueType="define">
                  <listOptionValue builtIn="false" value="DEBUG"/>
                  <listOptionValue builtIn="false" value="MSPM0G3507"/>
                </option>
                <option id="ti.ccs.misc.options.buildIncludePath.34568" name="Include Options" superClass="ti.ccs.misc.options.buildIncludePath" valueType="includePath">
                  <listOptionValue builtIn="false" value="${PROJECT_LOC}/inc"/>
                  <listOptionValue builtIn="false" value="${PROJECT_LOC}/driverlib"/>
                </option>
                <option id="ti.ccs.misc.options.buildVar.34569" name="Build Variables" superClass="ti.ccs.misc.options.buildVar" valueType="buildVariables"/>
                <targetPlatform id="ti.ccs.project.toolchain.debug.23456.0" name="ti.platforms.mspm0" superClass="ti.ccs.platform.mspm0"/>
                <builder id="ti.ccs.project.toolchain.builder.debug.23457" superClass="ti.ccs.project.toolchain.builder.debug"/>
                <tool id="ti.ccs.project.toolchain.arm.compiler.debug.23458" name="TI Compiler" superClass="ti.ccs.project.toolchain.arm.compiler.debug">
                  <option id="ti.ccs.arm.compiler.options.optLevel.45670" superClass="ti.ccs.arm.compiler.options.optLevel" value="ti.ccs.arm.compiler.options.optLevel.off" valueType="enumerated"/>
                </tool>
                <tool id="ti.ccs.project.toolchain.arm.assembler.debug.23459" name="TI Assembler" superClass="ti.ccs.project.toolchain.arm.assembler.debug"/>
                <tool id="ti.ccs.project.toolchain.arm.linker.debug.23460" name="TI Linker" superClass="ti.ccs.project.toolchain.arm.linker.debug">
                  <option id="ti.ccs.arm.linker.options.commandFile.45671" superClass="ti.ccs.arm.linker.options.commandFile" valueType="string">
                    <listOptionValue builtIn="false" value="${PROJECT_LOC}/mspm0g3507.cmd"/>
                  </option>
                </tool>
              </toolChain>
            </folderInfo>
            <sourceEntries>
              <entry excluding="Debug" flags="VALUE_WORKSPACE_PATH" kind="sourcePath" name=""/>
            </sourceEntries>
          </configuration>
        </cdtBuildSystem>
      </storageModule>
      <storageModule moduleId="org.eclipse.cdt.core.language.mapping">
        <project-mappings>
          <projectMapping language="c" project="org.eclipse.cdt.core.c_cpp.language.c"/>
        </project-mappings>
      </storageModule>
    </cconfiguration>
    <cconfiguration id="ti.ccs.project.toolchain.configuration.release.54321">
      <storageModule moduleId="org.eclipse.cdt.core.externalSettings"/>
      <storageModule moduleId="org.eclipse.cdt.core.settings">
        <extensions>
          <extension id="org.eclipse.cdt.core.ELF" point="org.eclipse.cdt.core.BinaryParser"/>
        </extensions>
        <cdtBuildSystem buildArtefactType="org.eclipse.cdt.build.core.buildArtefactType.exe" buildId="org.eclipse.cdt.build.core.buildArtefactType.exe" buildProperties="org.eclipse.cdt.build.core.buildArtefactType=org.eclipse.cdt.build.core.buildArtefactType.exe,org.eclipse.cdt.build.core.buildType=org.eclipse.cdt.build.core.buildType.release" comment="Build configuration: Release" id="ti.ccs.project.toolchain.configuration.release.54321" name="Release">
          <configuration artifactExtension="out" artifactName="${ProjName}" buildArtefactType="org.eclipse.cdt.build.core.buildArtefactType.exe" buildProperties="org.eclipse.cdt.build.core.buildArtefactType=org.eclipse.cdt.build.core.buildArtefactType.exe,org.eclipse.cdt.build.core.buildType=org.eclipse.cdt.build.core.buildType.release" comment="Build configuration: Release" id="ti.ccs.project.toolchain.configuration.release.54321" name="Release" parent="ti.ccs.project.toolchain.configuration.release.54321">
            <folderInfo id="ti.ccs.project.toolchain.configuration.release.54321." name="/" resourcePath="">
              <toolChain id="ti.ccs.project.toolchain.release.65432" name="TI Code Generation Tools" superClass="ti.ccs.project.toolchain.release">
                <option id="ti.ccs.misc.options.buildIncludePath.65433" name="Include Options" superClass="ti.ccs.misc.options.buildIncludePath" valueType="includePath">
                  <listOptionValue builtIn="false" value="${PROJECT_LOC}/inc"/>
                </option>
                <option id="ti.ccs.misc.options.buildVar.65434" name="Build Variables" superClass="ti.ccs.misc.options.buildVar" valueType="buildVariables"/>
                <targetPlatform id="ti.ccs.project.toolchain.release.65432.0" name="ti.platforms.mspm0" superClass="ti.ccs.platform.mspm0"/>
                <builder id="ti.ccs.project.toolchain.builder.release.65433" superClass="ti.ccs.project.toolchain.builder.release"/>
                <tool id="ti.ccs.project.toolchain.arm.compiler.release.65434" name="TI Compiler" superClass="ti.ccs.project.toolchain.arm.compiler.release"/>
                <tool id="ti.ccs.project.toolchain.arm.assembler.release.65435" name="TI Assembler" superClass="ti.ccs.project.toolchain.arm.assembler.release"/>
                <tool id="ti.ccs.project.toolchain.arm.linker.release.65436" name="TI Linker" superClass="ti.ccs.project.toolchain.arm.linker.release"/>
              </toolChain>
            </folderInfo>
            <sourceEntries>
              <entry excluding="Release" flags="VALUE_WORKSPACE_PATH" kind="sourcePath" name=""/>
            </sourceEntries>
          </configuration>
        </cdtBuildSystem>
      </storageModule>
    </cconfiguration>
  </storageModule>
  <storageModule moduleId="cdtBuildSystem">
    <project id="mspm0g3507.12345" name="mspm0g3507" type="ti.ccs.project.toolchain.arm"/>
  </storageModule>
  <storageModule moduleId="scannerConfiguration"/>
</cproject>
'''


def make_fake_master_project(master_dir: Path) -> Path:
    """最小化的 Keil 风格母版工程（真实母版由工单 08 提炼，这里只求结构真实）。"""
    (master_dir / "inc").mkdir(parents=True)
    (master_dir / "src").mkdir()
    (master_dir / ".git").mkdir()
    (master_dir / "project.uvprojx").write_text(FAKE_UVPROJX, encoding="utf-8")
    (master_dir / "main.c").write_text("/* master's old main */", encoding="utf-8")
    (master_dir / "inc/stm32f10x_conf.h").write_text("#pragma once\n", encoding="utf-8")
    (master_dir / "src/system_stm32f10x.c").write_text(
        "/* startup/system */", encoding="utf-8"
    )
    (master_dir / ".git/HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
    return master_dir


# 假母版的 .project：CCS（Eclipse 底座）打开工程必需的工程描述文件，
# 声明 TI 与 CDT 的 natures——缺了它 CCS 无法打开工程。
FAKE_CCS_PROJECT = r'''<?xml version="1.0" encoding="UTF-8"?>
<projectDescription>
  <name>mspm0g3507</name>
  <comment></comment>
  <projects>
  </projects>
  <buildSpec>
    <buildCommand>
      <name>org.eclipse.cdt.managedbuilder.core.genmakebuilder</name>
      <triggers>clean,full,incremental,</triggers>
      <arguments>
      </arguments>
    </buildCommand>
    <buildCommand>
      <name>org.eclipse.cdt.managedbuilder.core.ScannerConfigBuilder</name>
      <triggers>full,incremental,</triggers>
      <arguments>
      </arguments>
    </buildCommand>
  </buildSpec>
  <natures>
    <nature>com.ti.ccstudio.core.ccsNature</nature>
    <nature>org.eclipse.cdt.core.cnature</nature>
    <nature>org.eclipse.cdt.managedbuilder.core.managedBuildNature</nature>
    <nature>org.eclipse.cdt.managedbuilder.core.ScannerConfigNature</nature>
  </natures>
</projectDescription>
'''


def make_fake_ccs_master_project(master_dir: Path) -> Path:
    """最小化的 CCS 风格母版工程（真实母版由工单 08 提炼，这里只求结构真实）。"""
    (master_dir / "inc").mkdir(parents=True)
    (master_dir / ".git").mkdir()
    (master_dir / ".project").write_text(FAKE_CCS_PROJECT, encoding="utf-8")
    (master_dir / "project.cproject").write_text(FAKE_CPROJECT, encoding="utf-8")
    (master_dir / "main.c").write_text("/* master's old main */", encoding="utf-8")
    (master_dir / "mspm0g3507.cmd").write_text(
        "--stack_size=512\n--heap_size=512\n", encoding="utf-8"
    )
    (master_dir / "inc/mspm0g3507.h").write_text("#pragma once\n", encoding="utf-8")
    (master_dir / ".git/HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
    return master_dir


# ---------------------------------------------------------------------------
# 假 Theia 20.5 母版（工单 08）：以真实 TI empty 示例 .cproject 为底
# ---------------------------------------------------------------------------

# Theia 与 classic 的三处差异（ccs.py 双格式认知的 fixture 对偶）：
# ① cdtBuildSystem 是 cconfiguration 内独立的 storageModule（configuration 是
#    其直接子元素），classic 是 settings storageModule 里的元素；
# ② include/define 选项 superClass 走 TMS470_TICLANG_4.0 命名空间；
# ③ 无 sourceEntries 元素（CDT 缺省 = 全树为源，patch 补根条目）。
FAKE_CPROJECT_THEIA = r'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<?fileVersion 4.0.0?><cproject storage_type_id="org.eclipse.cdt.core.XmlProjectDescriptionStorage">
    <storageModule moduleId="org.eclipse.cdt.core.settings">
        <cconfiguration id="com.ti.ccstudio.buildDefinitions.TMS470.Debug.56822270">
            <storageModule buildSystemId="org.eclipse.cdt.managedbuilder.core.configurationDataProvider" id="com.ti.ccstudio.buildDefinitions.TMS470.Debug.56822270" moduleId="org.eclipse.cdt.core.settings" name="Debug">
                <externalSettings/>
                <extensions>
                    <extension id="com.ti.ccs.errorparser.SysConfigErrorParser" point="com.ti.ccs.project.ErrorParser"/>
                    <extension id="com.ti.ccs.errorparser.CompilerErrorParser_TI" point="com.ti.ccs.project.ErrorParser"/>
                </extensions>
            </storageModule>
            <storageModule moduleId="cdtBuildSystem" version="4.0.0">
                <configuration artifactExtension="out" artifactName="${ProjName}" buildProperties="" cleanCommand="${CG_CLEAN_CMD}" description="" id="com.ti.ccstudio.buildDefinitions.TMS470.Debug.56822270" name="Debug" parent="com.ti.ccstudio.buildDefinitions.TMS470.Debug">
                    <folderInfo id="com.ti.ccstudio.buildDefinitions.TMS470.Debug.56822270." name="/" resourcePath="">
                        <toolChain id="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.DebugToolchain.1526877788" name="TI Build Tools" superClass="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.DebugToolchain" targetTool="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.linkerDebug.611227998">
                            <option id="com.ti.ccstudio.buildDefinitions.core.OPT_TAGS.321175198" superClass="com.ti.ccstudio.buildDefinitions.core.OPT_TAGS" valueType="stringList">
                                <listOptionValue value="DEVICE_CONFIGURATION_ID=Cortex M.MSPM0G3507"/>
                                <listOptionValue value="PRODUCTS=MSPM0-SDK:2.11.0.07;sysconfig:1.26.2;"/>
                            </option>
                            <targetPlatform id="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.targetPlatformDebug.1573660973" name="Platform" superClass="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.targetPlatformDebug"/>
                            <builder buildPath="${BuildDirectory}" id="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.builderDebug.2060080375" name="GNU Make.Debug" parallelBuildOn="true" parallelizationNumber="optimal" superClass="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.builderDebug"/>
                            <tool id="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.compilerDebug.1701041390" name="Arm Compiler" superClass="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.compilerDebug">
                                <option id="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.INCLUDE_PATH.1878044542" superClass="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.INCLUDE_PATH" valueType="includePath">
                                    <listOptionValue value="${COM_TI_MSPM0_SDK_INCLUDE_PATH}"/>
                                    <listOptionValue value="${SYSCONFIG_TOOL_INCLUDE_PATH}"/>
                                    <listOptionValue value="${PROJECT_ROOT}"/>
                                    <listOptionValue value="${PROJECT_ROOT}/${ConfigName}"/>
                                    <listOptionValue value="${COM_TI_MSPM0_SDK_INSTALL_DIR}/source/third_party/CMSIS/Core/Include"/>
                                    <listOptionValue value="${COM_TI_MSPM0_SDK_INSTALL_DIR}/source"/>
                                </option>
                                <option id="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.DEFINE.1080537059" superClass="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.compilerID.DEFINE" valueType="definedSymbols">
                                    <listOptionValue value="${COM_TI_MSPM0_SDK_SYMBOLS}"/>
                                    <listOptionValue value="${SYSCONFIG_TOOL_SYMBOLS}"/>
                                </option>
                            </tool>
                            <tool id="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.linkerDebug.611227998" name="Arm Linker" superClass="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.exe.linkerDebug">
                                <option id="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.linkerID.SEARCH_PATH.1371414595" superClass="com.ti.ccstudio.buildDefinitions.TMS470_TICLANG_4.0.linkerID.SEARCH_PATH" valueType="libPaths">
                                    <listOptionValue value="${COM_TI_MSPM0_SDK_LIBRARY_PATH}"/>
                                    <listOptionValue value="${PROJECT_ROOT}"/>
                                </option>
                            </tool>
                        </toolChain>
                    </folderInfo>
                </configuration>
            </storageModule>
            <storageModule moduleId="org.eclipse.cdt.core.externalSettings"/>
        </cconfiguration>
    </storageModule>
    <storageModule moduleId="cdtBuildSystem" version="4.0.0">
        <project id="empty.com.ti.ccstudio.buildDefinitions.TMS470.ProjectType.599460471" name="TMS470" projectType="com.ti.ccstudio.buildDefinitions.TMS470.ProjectType"/>
    </storageModule>
</cproject>
'''

# Theia 母版 .project（整理后 name = mspm0_project，生成工程在 CCS 工作区显示名）
FAKE_THEIA_CCS_PROJECT = r'''<?xml version="1.0" encoding="UTF-8"?>
<projectDescription>
	<name>mspm0_project</name>
	<comment></comment>
	<projects>
	</projects>
	<buildSpec>
		<buildCommand>
			<name>org.eclipse.cdt.managedbuilder.core.genmakebuilder</name>
			<arguments>
			</arguments>
		</buildCommand>
	</buildSpec>
	<natures>
		<nature>com.ti.ccstudio.core.ccsNature</nature>
		<nature>org.eclipse.cdt.core.cnature</nature>
		<nature>org.eclipse.cdt.managedbuilder.core.managedBuildNature</nature>
		<nature>org.eclipse.cdt.core.ccnature</nature>
	</natures>
</projectDescription>
'''

# Theia 母版 main.c：TI empty 示例原样（SYSCFG_DL_init + while(1)，正合 ADR 0002
# 模板 main.c 形态；生成时被骨架覆盖）
THEIA_MASTER_MAIN_C = (
    '#include "ti_msp_dl_config.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    SYSCFG_DL_init();\n"
    "\n"
    "    while (1) {\n"
    "    }\n"
    "}\n"
)

# Theia 母版 .syscfg：TI empty 示例原样（官方板 LP_MSPM0G3507，模板预期用户生成后自改）
FAKE_MSPM0_SYSCFG = (
    '//@cliArgs --device "MSPM0G350X" --package "LQFP-64(PM)" --part "Default"\n'
    '//@v2CliArgs --device "MSPM0G3507" --package "LQFP-64(PM)"\n'
    "// @cliArgs --board /ti/boards/LP_MSPM0G3507 --rtos nortos\n"
    "\n"
    'const SYSCTL = scripting.addModule("/ti/driverlib/SYSCTL");\n'
    "\n"
    'const Board = scripting.addModule("/ti/driverlib/Board", {}, false);\n'
    "\n"
    "SYSCTL.forceDefaultClkConfig = true;\n"
)


def make_fake_ccs_theia_master_project(master_dir: Path) -> Path:
    """Theia 20.5 母版工程（TI 官方 empty 示例整理后形态：main.c + mspm0.syscfg
    + .cproject + .project，无 .clangd / Debug / README 机器噪音）。"""
    master_dir.mkdir(parents=True)
    (master_dir / ".project").write_text(FAKE_THEIA_CCS_PROJECT, encoding="utf-8")
    (master_dir / "project.cproject").write_text(FAKE_CPROJECT_THEIA, encoding="utf-8")
    (master_dir / "main.c").write_text(THEIA_MASTER_MAIN_C, encoding="utf-8")
    (master_dir / "mspm0.syscfg").write_text(FAKE_MSPM0_SYSCFG, encoding="utf-8")
    return master_dir


class FakeTransport:
    """HTTP 传输假件：记录请求并返回固定响应（注入 DeepSeekLLM，网络不进测试）。"""

    def __init__(self, status: int = 200, body: str = "") -> None:
        self.status = status
        self.body = body
        self.calls: list[tuple[str, dict[str, str], dict[str, Any], float]] = []

    def post(
        self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
    ) -> tuple[int, str]:
        self.calls.append((url, headers, payload, timeout))
        return self.status, self.body


class FakeLLM:
    """假 LLM：固定返回并记录各职责的输入，供工单 04/05/07/08 注入。

    实现 LLM 协议的全部 11 个方法（与协议契约对齐——生产代码不再需要
    getattr 兜底）；默认行为只覆盖最常用的职责，其余返回空 / None。
    """

    def __init__(
        self,
        selection: ModuleSelection | None = None,
        main_skeleton: str = "/* skeleton placeholder */\n",
        summary: str = "AI 生成的模块简介",
        validation: ValidationResult = ValidationResult(consistent=True),
        distillation: tuple[FileDecision, ...] = (),
        clarify_questions: tuple[str, ...] = (),
        topic_summary: str = "AI 生成的赛题简介",
    ) -> None:
        self._selection = selection or ModuleSelection(modules=(), reasons={})
        self._main_skeleton = main_skeleton
        self._summary = summary
        self._validation = validation
        self._distillation = distillation
        self._clarify_questions = clarify_questions
        self._topic_summary = topic_summary
        self.skeleton_calls: list[tuple[str, tuple[str, ...]]] = []
        self.summary_calls: list[tuple[str, ...]] = []
        self.validation_calls: list[tuple[str, str]] = []
        self.distill_calls: list[
            tuple[str, tuple[str, ...], tuple[JudgmentFile, ...], str]
        ] = []
        self.reference_summarize_calls: list[tuple[str, ...]] = []
        self.reference_judge_calls: list[tuple[ReferenceCandidate, ...]] = []
        self.topic_split_calls: list[tuple[str, ...]] = []
        self.topic_extract_calls: list[tuple[str, ...]] = []
        self.clarify_calls: list[tuple[str, tuple[tuple[str, str], ...]]] = []
        self.topic_summarize_calls: list[tuple[str, ...]] = []

    def select_modules(
        self,
        problem_text: str,
        manifest_summaries: Sequence[ManifestSummary],
        references: Sequence[ReferenceSuggestion] = (),
        reference_fulltexts: Mapping[str, str] | None = None,
        manual_fulltexts: Mapping[str, str] | None = None,
    ) -> ModuleSelection:
        return self._selection

    def clarify(
        self, problem_text: str, clarifications: Sequence[tuple[str, str]]
    ) -> tuple[str, ...]:
        self.clarify_calls.append((problem_text, tuple(clarifications)))
        return self._clarify_questions

    def summarize_topic(self, problem_text: str) -> str:
        self.topic_summarize_calls.append((problem_text,))
        return self._topic_summary

    def generate_main_skeleton(
        self, problem_text: str, module_interfaces: Sequence[str]
    ) -> str:
        self.skeleton_calls.append((problem_text, tuple(module_interfaces)))
        return self._main_skeleton

    def summarize_module(self, code: str) -> str:
        self.summary_calls.append((code,))
        return self._summary

    def validate_module_description(
        self, description: str, code: str
    ) -> ValidationResult:
        self.validation_calls.append((description, code))
        return self._validation

    def distill_master(
        self,
        platform: str,
        project_names: Sequence[str],
        judgment_files: Sequence[JudgmentFile],
        comparison_summary: str,
        progress_emitter: ProgressEmitter | None = None,
    ) -> tuple[FileDecision, ...]:
        # 假 LLM 与真 LLM 走同一参数（spec「发射 seam」）：webapp 层可经假 LLM
        # 注入发射器断言事件序列，这里不消费、只保持签名兼容
        self.distill_calls.append(
            (platform, tuple(project_names), tuple(judgment_files), comparison_summary)
        )
        return self._distillation

    def reference_summarize(self, material: str) -> str:
        self.reference_summarize_calls.append((material,))
        return ""

    def reference_judge_archivable(
        self, candidates: Sequence[ReferenceCandidate]
    ) -> tuple[str, ...]:
        self.reference_judge_calls.append(tuple(candidates))
        return ()

    def topic_split_topics(self, pdf_text: str) -> tuple[TopicDraft, ...]:
        self.topic_split_calls.append((pdf_text,))
        return ()

    def topic_extract_number(self, text: str) -> str | None:
        self.topic_extract_calls.append((text,))
        return None


class RecordingPatcher:
    """记录调用参数的桩修改器，用于断言核心通过注册表委托。"""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, tuple[Path, ...], tuple[Path, ...]]] = []

    def patch(
        self,
        project_dir: Path,
        module_files: Sequence[Path],
        include_dirs: Sequence[Path],
    ) -> None:
        self.calls.append((project_dir, tuple(module_files), tuple(include_dirs)))


def _add_module(library_dir: Path, manifest: dict, files: dict[str, str]) -> None:
    module_dir = library_dir / manifest["slug"]
    module_dir.mkdir(parents=True)
    (module_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    for relpath, content in files.items():
        path = module_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# 样例赛题文件（文本抽取测试用）：tmp_path 现场构造，不提交二进制 fixture
# ---------------------------------------------------------------------------


def make_sample_docx(path: Path, paragraphs: Sequence[str]) -> Path:
    """手工构造最小 .docx：zip 内含 [Content_Types].xml 与 word/document.xml。"""
    body = "\n".join(
        f'<w:p><w:r><w:t xml:space="preserve">{_xml_escape(p)}</w:t></w:r></w:p>'
        for p in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
        f"<w:body>{body}</w:body>\n"
        "</w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document)
    return path


def _xml_escape(text: str) -> str:
    return escape(text, {"'": "&apos;", '"': "&quot;"})


def make_sample_pdf(path: Path, text: str) -> Path:
    """手工构造最小单页 PDF：Helvetica + WinAnsiEncoding + FlateDecode 内容流。

    只支持 ASCII 文本（PDF 字符串字面量），括号与反斜杠会被转义。
    """
    content = f"BT /F1 24 Tf 72 720 Td ({_pdf_escape(text)}) Tj ET\n"
    stream = zlib.compress(content.encode("ascii"))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        (
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding >>"
        ),
        (
            b"<< /Filter /FlateDecode /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        ),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{number} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(b"xref\n0 6\n")
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.write_bytes(bytes(out))
    return path


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_encrypted_pdf(path: Path) -> Path:
    """pypdf 生成带密码的 PDF，用于测试"已加密"报错路径。"""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("contest-password")
    with path.open("wb") as file:
        writer.write(file)
    return path


def make_blank_pdf(path: Path) -> Path:
    """pypdf 生成无任何文字的 PDF（模拟扫描件），抽取应报错而非给空文。"""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as file:
        writer.write(file)
    return path


# ---------------------------------------------------------------------------
# 工单 02 假件：stm32 电机链路（母版 ml_libs + pin_config.h、motor/pid 模块）
# ---------------------------------------------------------------------------

# 假母版 ml_libs（headfile.h + 驱动层头）与工程根 pin_config.h：内容与真实
# 母版同构（引脚宏集中、模块只引用宏），结构够生成门禁解析即可。
FAKE_ML_HEADFILE_H = (
    "#ifndef __HEADFILE_H\n#define __HEADFILE_H\n"
    '#include "ml_pwm.h"\n#include "ml_gpio.h"\n#include "ml_exti.h"\n'
    "#endif\n"
)
FAKE_ML_PWM_H = (
    "#ifndef _pwm_h_\n#define _pwm_h_\n#include \"headfile.h\"\n"
    "typedef enum { TIM2_CH1 = 0, TIM2_CH2 = 1 } TIMn_CHn_enum;\n"
    "typedef enum { TIM_2 = 0, TIM_3 = 1 } TIMn_enum;\n"
    "void pwm_init(TIMn_enum timn, TIMn_CHn_enum timn_chn, int fre);\n"
    "void pwm_update(TIMn_enum timn, TIMn_CHn_enum timn_chn, int duty);\n"
    "#endif\n"
)
FAKE_ML_GPIO_H = (
    "#ifndef _ml_gpio_h_\n#define _ml_gpio_h_\n#include \"headfile.h\"\n"
    "typedef enum { GPIO_A = 0, GPIO_B = 1 } GPIOn_enum;\n"
    "typedef enum { Pin_0 = 0, Pin_3 = 3, Pin_5 = 5, Pin_6 = 6, Pin_7 = 7 } Pinx_enum;\n"
    "typedef enum { OUT_PP = 0, IU = 1 } GPIO_MODE_enum;\n"
    "void gpio_init(GPIOn_enum GPIOn, Pinx_enum Pinx, GPIO_MODE_enum mode);\n"
    "void gpio_set(GPIOn_enum GPIOn, Pinx_enum Pinx, uint8_t mode);\n"
    "uint8_t gpio_get(GPIOn_enum GPIOn, Pinx_enum Pinx);\n"
    "#endif\n"
)
FAKE_ML_EXTI_H = (
    "#ifndef _ml_exti_h_\n#define _ml_exti_h_\n#include \"headfile.h\"\n"
    "typedef enum { EXTI_PA2 = 6, EXTI_PA4 = 12 } EXTI_Pnx_enum;\n"
    "typedef enum { RISING, FALLING } EXTI_Trigger_enum;\n"
    "void exti_init(EXTI_Pnx_enum pin, EXTI_Trigger_enum trigger, uint8_t priority);\n"
    "#endif\n"
)
FAKE_PIN_CONFIG_H = (
    "#ifndef __PIN_CONFIG_H\n#define __PIN_CONFIG_H\n"
    "#define MOTOR_A_PWM_TIM TIM_2\n#define MOTOR_A_PWM_CH TIM2_CH1\n"
    "#define MOTOR_B_PWM_TIM TIM_2\n#define MOTOR_B_PWM_CH TIM2_CH2\n"
    "#define MOTOR_PWM_FREQ 1000\n"
    "#define MOTOR_A_DIR_PORT GPIO_A\n#define MOTOR_A_DIR_PIN Pin_6\n"
    "#define MOTOR_A_DIR2_PORT GPIO_A\n#define MOTOR_A_DIR2_PIN Pin_7\n"
    "#define MOTOR_B_DIR_PORT GPIO_B\n#define MOTOR_B_DIR_PIN Pin_0\n"
    "#define MOTOR_B_DIR2_PORT GPIO_B\n#define MOTOR_B_DIR2_PIN Pin_1\n"
    "#define MOTOR_A_ENC_EXTI EXTI_PA2\n#define MOTOR_A_ENC_LINE 2\n"
    "#define MOTOR_A_ENC_DIR_PORT GPIO_A\n#define MOTOR_A_ENC_DIR_PIN Pin_3\n"
    "#define MOTOR_B_ENC_EXTI EXTI_PA4\n#define MOTOR_B_ENC_LINE 4\n"
    "#define MOTOR_B_ENC_DIR_PORT GPIO_A\n#define MOTOR_B_ENC_DIR_PIN Pin_5\n"
    "#endif\n"
)

# 假 stm32 母版 .uvprojx（真实母版同构：uvprojx 在 user/、IncludePath 含工程根
# `..`——pin_config.h 在工程根、ml_libs 由 ..\ml_libs 进搜索范围）。
FAKE_STM32_ML_UVPROJX = r'''<?xml version="1.0" encoding="UTF-8" ?>
<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <SchemaVersion>2.1</SchemaVersion>
  <Targets>
    <Target>
      <TargetName>STM32F103C8</TargetName>
      <ToolsetNumber>0x4</ToolsetNumber>
      <ToolsetName>ARM-ADS</ToolsetName>
      <TargetOption>
        <TargetCommonOption>
          <Device>STM32F103C8</Device>
          <Vendor>STMicroelectronics</Vendor>
        </TargetCommonOption>
        <TargetArmAds>
          <Cads>
            <VariousControls>
              <MiscControls></MiscControls>
              <Define></Define>
              <Undefine></Undefine>
              <IncludePath>..\ml_libs;..</IncludePath>
            </VariousControls>
          </Cads>
        </TargetArmAds>
      </TargetOption>
      <Groups>
        <Group>
          <GroupName>user</GroupName>
          <Files>
            <File>
              <FileName>main.c</FileName>
              <FileType>1</FileType>
              <FilePath>..\main.c</FilePath>
            </File>
          </Files>
        </Group>
      </Groups>
    </Target>
  </Targets>
</Project>
'''


def make_fake_stm32_ml_master(master_dir: Path) -> Path:
    """假 stm32 母版：ml_libs（headfile.h + ml_pwm/ml_gpio/ml_exti）+ 工程根
    pin_config.h + user/Project.uvprojx（IncludePath 含工程根，真实母版同构）。"""
    (master_dir / "ml_libs").mkdir(parents=True)
    (master_dir / "user").mkdir()
    (master_dir / "pin_config.h").write_text(FAKE_PIN_CONFIG_H, encoding="utf-8")
    (master_dir / "main.c").write_text("/* master's old main */", encoding="utf-8")
    (master_dir / "ml_libs" / "headfile.h").write_text(FAKE_ML_HEADFILE_H, encoding="utf-8")
    (master_dir / "ml_libs" / "ml_pwm.h").write_text(FAKE_ML_PWM_H, encoding="utf-8")
    (master_dir / "ml_libs" / "ml_gpio.h").write_text(FAKE_ML_GPIO_H, encoding="utf-8")
    (master_dir / "ml_libs" / "ml_exti.h").write_text(FAKE_ML_EXTI_H, encoding="utf-8")
    (master_dir / "user" / "Project.uvprojx").write_text(
        FAKE_STM32_ML_UVPROJX, encoding="utf-8"
    )
    return master_dir


# 假 motor/pid 模块（21F 提取形态）：motor_stm32.c 引脚全走 pin_config.h 宏 +
# EXTI2/4 编码器计数中断随模块；pid_isr.c 为 21F isr.c 的 TIM3_IRQHandler
# 原样提取（关中断读计数 → motorA/B.now → pid_control）。
MOTOR_STM32_H = (
    "#ifndef _MOTOR_STM32_H\n#define _MOTOR_STM32_H\n"
    '#include "headfile.h"\n'
    "void motor_init(void);\n"
    "void motorA_duty(int duty);\n"
    "void motorB_duty(int duty);\n"
    "void encoder_init(void);\n"
    "extern int Encoder_count1, Encoder_count2;\n"
    "extern uint8_t motorA_dir, motorB_dir;\n"
    "#endif\n"
)
MOTOR_STM32_C = (
    '#include "motor_stm32.h"\n'
    '#include "pin_config.h"\n'
    "uint8_t motorA_dir = 0;\n"
    "uint8_t motorB_dir = 0;\n"
    "int Encoder_count1 = 0;\n"
    "int Encoder_count2 = 0;\n"
    "void motor_init(void) {\n"
    "    pwm_init(MOTOR_A_PWM_TIM, MOTOR_A_PWM_CH, MOTOR_PWM_FREQ);\n"
    "    gpio_init(MOTOR_A_DIR_PORT, MOTOR_A_DIR_PIN, OUT_PP);\n"
    "    pwm_init(MOTOR_B_PWM_TIM, MOTOR_B_PWM_CH, MOTOR_PWM_FREQ);\n"
    "    gpio_init(MOTOR_B_DIR_PORT, MOTOR_B_DIR_PIN, OUT_PP);\n"
    "}\n"
    "void encoder_init(void) {\n"
    "    exti_init(MOTOR_A_ENC_EXTI, FALLING, 0);\n"
    "    gpio_init(MOTOR_A_ENC_DIR_PORT, MOTOR_A_ENC_DIR_PIN, IU);\n"
    "    exti_init(MOTOR_B_ENC_EXTI, FALLING, 0);\n"
    "    gpio_init(MOTOR_B_ENC_DIR_PORT, MOTOR_B_ENC_DIR_PIN, IU);\n"
    "}\n"
    "void EXTI2_IRQHandler(void) {\n"
    "    if (EXTI->PR & (1 << MOTOR_A_ENC_LINE)) {\n"
    "        Encoder_count1++;\n"
    "        EXTI->PR = 1 << MOTOR_A_ENC_LINE;\n"
    "    }\n"
    "}\n"
    "void EXTI4_IRQHandler(void) {\n"
    "    if (EXTI->PR & (1 << MOTOR_B_ENC_LINE)) {\n"
    "        Encoder_count2++;\n"
    "        EXTI->PR = 1 << MOTOR_B_ENC_LINE;\n"
    "    }\n"
    "}\n"
)
PID_H = (
    "#ifndef __PID_H\n#define __PID_H\n#include \"headfile.h\"\n"
    "typedef struct { float target; float now; } pid_t;\n"
    "void pid_control(void);\n"
    "void pid_init(pid_t *pid, int mode, float p, float i, float d);\n"
    "extern pid_t motorA;\n"
    "extern pid_t motorB;\n"
    "#endif\n"
)
PID_C = (
    '#include "pid.h"\n'
    '#include "motor_stm32.h"\n'
    "pid_t motorA = {0};\n"
    "pid_t motorB = {0};\n"
    "void pid_control(void) { motorA_duty(0); motorB_duty(0); }\n"
)
PID_ISR_C = (
    '#include "pid.h"\n'
    '#include "motor_stm32.h"\n'
    "void TIM3_IRQHandler(void) {\n"
    "    if (TIM3->SR & 1) {\n"
    "        __disable_irq();\n"
    "        int enc1 = Encoder_count1;\n"
    "        int enc2 = Encoder_count2;\n"
    "        Encoder_count1 = 0;\n"
    "        Encoder_count2 = 0;\n"
    "        __enable_irq();\n"
    "        motorA.now = (float)enc1;\n"
    "        motorB.now = (float)enc2;\n"
    "        pid_control();\n"
    "        TIM3->SR &= ~1;\n"
    "    }\n"
    "}\n"
)


def make_fake_motor_pid_library(library_dir: Path) -> Path:
    """假模块库：motor + pid（stm32，21F 提取形态）——工单 02 生成用例专用。"""
    _add_module(
        library_dir,
        {
            "slug": "motor",
            "description": "TB6612 双路直流电机驱动",
            "dependencies": [],
            "platforms": {
                "stm32": {
                    "files": ["code/motor_stm32.c", "code/motor_stm32.h"],
                    "verified": True,
                    "hardware_bound": False,
                    "notes": "21F 提取；引脚宏走母版 pin_config.h",
                }
            },
        },
        {
            "code/motor_stm32.c": MOTOR_STM32_C,
            "code/motor_stm32.h": MOTOR_STM32_H,
        },
    )
    _add_module(
        library_dir,
        {
            "slug": "pid",
            "description": "2021F 巡线题专用 PID 控制",
            "dependencies": ["motor"],
            "platforms": {
                "stm32": {
                    "files": ["code/pid.c", "code/pid.h", "code/pid_isr.c"],
                    "verified": True,
                    "hardware_bound": False,
                    "notes": "",
                }
            },
        },
        {
            "code/pid.c": PID_C,
            "code/pid.h": PID_H,
            "code/pid_isr.c": PID_ISR_C,
        },
    )
    return library_dir
