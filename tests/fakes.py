"""测试假件与构造器：假模块库、假母版、假 LLM、记录桩。

只放纯数据/构造逻辑，不放 pytest fixture（fixture 见 conftest.py）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from contest_generator.llm import ModuleSelection

# ---------------------------------------------------------------------------
# 假模块文件内容（断言输出目录里文件内容用）
# ---------------------------------------------------------------------------

DHT11_STM32_C = "/* DHT11 driver for STM32 */\nfloat dht11_read(void);\n"
DHT11_MSPM0_C = "/* DHT11 driver for MSPM0 */\nfloat dht11_read(void);\n"
DHT11_H = "#pragma once\nfloat dht11_read(void);\n"
OLED_STM32_C = "/* OLED driver for STM32 */\nvoid oled_init(void);\n"
OLED_H = "#pragma once\nvoid oled_init(void);\n"

# 假 LLM 生成的 main.c 骨架（工单 05 前由测试直接传入生成器）
MAIN_SKELETON = "int main(void) { dht11_init(); oled_init(); while(1); }\n"

# 假母版的 .uvprojx：结构真实的 Keil5 工程文件（设备型号、Cpu、IncludePath、
# 一个含 main.c 的源组）。修改器只该动 IncludePath 与 Groups，其余原样保留。
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
            <IncludePath>.\inc;.\src</IncludePath>
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
        {"delay.c": "/* delay */\nvoid delay_ms(int ms);\n", "delay.h": "#pragma once\n"},
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


class FakeLLM:
    """假 LLM：固定返回，供后续工单（04/05）注入。"""

    def __init__(
        self,
        selection: ModuleSelection | None = None,
        main_skeleton: str = "/* skeleton placeholder */\n",
    ) -> None:
        self._selection = selection or ModuleSelection(modules=(), reasons={})
        self._main_skeleton = main_skeleton

    def select_modules(
        self, problem_text: str, manifest_summaries: Sequence[str]
    ) -> ModuleSelection:
        return self._selection

    def generate_main_skeleton(
        self, problem_text: str, module_summaries: Sequence[str]
    ) -> str:
        return self._main_skeleton

    def summarize_module(self, code: str) -> str:
        return "AI 生成的模块简介"


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
