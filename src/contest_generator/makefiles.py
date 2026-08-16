"""CCS 标准 Debug/makefile 集模板（工单 mspm0-build-makefiles/01）。

把 scratch 后处理脚本（.scratch/real-run/build_makefiles.py，硬编码 CCS 路径 +
静态 MODULES 表）产品化为生成器的一步：mspm0 平台生成时自动产出 CCS 标准
Debug/makefile 集——makefile + sources.mk + objects.mk + 根 subdir_vars.mk /
subdir_rules.mk + 逐模块目录 subdir_vars.mk / subdir_rules.mk，模板镜像 IDE
生成的 makefile 集（2024H 真机 gmake 0 错验证），`gmake -C Debug -f makefile`
即可全量构建。路径全部参数化（proj / SDK / 编译器 / SysConfig CLI），零硬编码。

纯函数模板：render_makefile_set 参数化产出 {相对路径: 文本}（同参必同文，
测试钉死确定性）；write_makefile_set 落盘（mkdir + 写文件）。module_sources
= ((slug, 子目录, (源文件名, ...)), ...)——由生成侧从选中模块 manifest 平台
条目的 files 推导（知识源头 = manifest 单源，本模块不维护静态 MODULES 表、
不 import manifest）；子目录 = 源文件在 modules/<slug>/ 下的父目录（空串 =
平铺，ml_mpu6050 的 ml_libs 形态天然覆盖）。

依赖方向：只 import 标准库，叶子模块（compile_runner / generator 依赖它）。
"""

from __future__ import annotations

from pathlib import Path
from collections.abc import Sequence

# 链接产物名（与母版 .project 的工程名一致，IDE 同款）
_OUT_NAME = "mspm0_project"

# 编译 / 链接公共 flag（IDE Debug 配置同款，scratch 脚本逐字迁移）
_FLAGS = (
    "-march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft "
    "-mlittle-endian -mthumb -O0 -gdwarf-3 -Wall -MMD -MP"
)

# SDK 内启动文件（相对 SDK 根，路径形态 IDE 生成同款）
_STARTUP_REL = (
    "source/ti/devices/msp/m0p/startup_system_files/ticlang/"
    "startup_mspm0g350x_ticlang.c"
)

# SysConfig 生成文件（build-1290584808 目标产出，IDE 生成同款清单）
_GEN_FILES = (
    "device_linker.cmd",
    "device.opt",
    "device.cmd.genlibs",
    "ti_msp_dl_config.c",
    "ti_msp_dl_config.h",
    "Event.dot",
)

# sources.mk 的空壳变量表（IDE 生成同款，全空——构建变量由下方各 subdir_vars
# 与 makefile 本体提供）
_EMPTY_VARS = (
    "C55_SRCS", "A_SRCS", "ASM_UPPER_SRCS", "PINMUX_SRCS", "EXE_SRCS",
    "LDS_UPPER_SRCS", "CPP_SRCS", "CMD_SRCS", "O_SRCS", "ELF_SRCS", "C??_SRCS",
    "C64_SRCS", "C67_SRCS", "SA_SRCS", "S64_SRCS", "OPT_SRCS", "CXX_SRCS",
    "S67_SRCS", "S??_SRCS", "SV7A_SRCS", "SYSCFG_SRCS", "K_SRCS", "CLA_SRCS",
    "S55_SRCS", "LD_UPPER_SRCS", "OUT_SRCS", "LIB_SRCS", "ASM_SRCS",
    "S_UPPER_SRCS", "SYSCONFIG_SRCS", "S43_SRCS", "LD_SRCS", "CMD_UPPER_SRCS",
    "C_UPPER_SRCS", "C++_SRCS", "C43_SRCS", "OBJ_SRCS", "LDS_SRCS", "S_SRCS",
    "CC_SRCS", "S62_SRCS", "C62_SRCS", "C_SRCS", "C55_DEPS", "C_UPPER_DEPS",
    "S67_DEPS", "S62_DEPS", "S_DEPS", "OPT_DEPS", "C??_DEPS", "ASM_UPPER_DEPS",
    "S??_DEPS", "C64_DEPS", "CXX_DEPS", "S64_DEPS", "GEN_CMDS", "GEN_FILES",
    "CLA_DEPS", "S55_DEPS", "SV7A_DEPS", "EXE_OUTPUTS", "C62_DEPS",
    "C67_DEPS", "GEN_MISC_DIRS", "K_DEPS", "C_DEPS", "CC_DEPS", "BIN_OUTPUTS",
    "GEN_OPTS", "C++_DEPS", "C43_DEPS", "S43_DEPS", "OBJS", "ASM_DEPS",
    "GEN_MISC_FILES", "S_UPPER_DEPS", "CPP_DEPS", "SA_DEPS",
)

_HEADER = (
    "################################################################################\n"
    "# Automatically-generated file. Do not edit!\n"
    "################################################################################\n"
    "\n"
    "SHELL = cmd.exe\n"
    "\n"
)

_SOURCES_MK = _HEADER + "".join(f"{name} := \n" for name in _EMPTY_VARS) + "\n"

_OBJECTS_MK = (
    _HEADER
    + "USER_OBJS :=\n\nLIBS := -Wl,-ldevice.cmd.genlibs -Wl,-llibc.a\n"
)

# (slug, 子目录, (源文件名, ...))：子目录 = 源文件在 modules/<slug>/ 下的父目录
# （空串 = 平铺）；源文件 = 该目录下的 .c 清单
ModuleSources = tuple[tuple[str, str, tuple[str, ...]], ...]


def _quoted(name: str, values: tuple[str, ...]) -> str:
    """quoted 变量块（OBJS__QUOTED 等）：每行一个带引号值 + 续行符，IDE 同款形态。"""
    return (
        f"{name} += \\\n"
        + "\n".join(f'"{value}" \\' for value in values)
        + " \n\n"
    )


def _module_dir(slug: str, subdir: str) -> str:
    """模块文件所在目录（相对工程根）：modules/<slug>/[<subdir>/]。"""
    return f"modules/{slug}/{subdir}" if subdir else f"modules/{slug}"


def _compile_recipe(
    compiler_dir: str, inc: str, dep_dir: str | None = None
) -> str:
    """tiarmclang 编译 recipe 行（root 与逐模块规则的唯一区别是 -MF 前缀）。"""
    prefix = f"{dep_dir}/" if dep_dir else ""
    return (
        f'\t"{compiler_dir}/bin/tiarmclang.exe" -c @"./device.opt" {_FLAGS} {inc} '
        f'-MF"{prefix}$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) '
        f'-o"$@" "$<"\n'
    )


def _root_subdir_vars(startup: str) -> str:
    """Debug/subdir_vars.mk（根）：工程根三源（ti_msp_dl_config / startup / main）
    与 SysConfig 生成文件清单，IDE 生成同款。"""
    return (
        _HEADER
        + "SYSCFG_SRCS += \\\n../mspm0.syscfg \n\n"
        + "C_SRCS += \\\n./ti_msp_dl_config.c \\\n"
        + f"{startup} \\\n../main.c \n\n"
        + "GEN_CMDS += \\\n./device_linker.cmd \n\n"
        + "GEN_FILES += \\\n./device_linker.cmd \\\n./device.opt \\\n"
        + "./ti_msp_dl_config.c \n\n"
        + "C_DEPS += \\\n./ti_msp_dl_config.d \\\n./startup_mspm0g350x_ticlang.d \\\n"
        + "./main.d \n\n"
        + "GEN_OPTS += \\\n./device.opt \n\n"
        + "OBJS += \\\n./ti_msp_dl_config.o \\\n./startup_mspm0g350x_ticlang.o \\\n"
        + "./main.o \n\n"
        + "GEN_MISC_FILES += \\\n./device.cmd.genlibs \\\n./ti_msp_dl_config.h \\\n"
        + "./Event.dot \n\n"
        + _quoted(
            "OBJS__QUOTED",
            ("ti_msp_dl_config.o", "startup_mspm0g350x_ticlang.o", "main.o"),
        )
        + _quoted(
            "GEN_MISC_FILES__QUOTED",
            ("device.cmd.genlibs", "ti_msp_dl_config.h", "Event.dot"),
        )
        + _quoted(
            "C_DEPS__QUOTED",
            ("ti_msp_dl_config.d", "startup_mspm0g350x_ticlang.d", "main.d"),
        )
        + _quoted(
            "GEN_FILES__QUOTED",
            ("device_linker.cmd", "device.opt", "ti_msp_dl_config.c"),
        )
        + 'SYSCFG_SRCS__QUOTED += \\\n"../mspm0.syscfg" \n\n'
        + _quoted(
            "C_SRCS__QUOTED",
            ("./ti_msp_dl_config.c", startup, "../main.c"),
        )
    )


def _root_subdir_rules(
    proj: str,
    sdk_dir: str,
    compiler_dir: str,
    sysconfig_cli: str,
    inc: str,
    startup: str,
) -> str:
    """Debug/subdir_rules.mk（根）：SysConfig 生成规则 + 根三源的编译规则。"""
    compile_line = _compile_recipe(compiler_dir, inc)
    parts = [
        _HEADER,
        "build-1290584808: ../mspm0.syscfg\n",
        '\t@echo \'SysConfig - building file: "$<"\'\n',
        f'\t"{sysconfig_cli}" -s "{sdk_dir}/.metadata/product.json" '
        f'--script "{proj}/mspm0.syscfg" -o "." --compiler ticlang\n',
        "\t@echo 'Finished building: \"$<\"'\n\t@echo ' '\n\n",
    ]
    for gen in _GEN_FILES:
        parts.append(f"{gen}: build-1290584808\n")
    parts += [
        "\n%.o: ./%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)\n",
        '\t@echo \'Arm Compiler - building file: "$<"\'\n',
        compile_line,
        "\t@echo 'Finished building: \"$<\"'\n\t@echo ' '\n\n",
        f"startup_mspm0g350x_ticlang.o: {startup} $(GEN_OPTS) "
        "| $(GEN_FILES) $(GEN_MISC_FILES)\n",
        '\t@echo \'Arm Compiler - building file: "$<"\'\n',
        compile_line,
        "\t@echo 'Finished building: \"$<\"'\n\t@echo ' '\n\n",
        "%.o: ../%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)\n",
        '\t@echo \'Arm Compiler - building file: "$<"\'\n',
        compile_line,
        "\t@echo 'Finished building: \"$<\"'\n\t@echo ' '\n",
    ]
    return "".join(parts)


def _module_makefiles(
    slug: str, subdir: str, cfiles: tuple[str, ...], compiler_dir: str, inc: str
) -> tuple[str, str]:
    """逐模块目录的 (subdir_vars.mk, subdir_rules.mk)：源文件清单 + 编译规则。"""
    rel = _module_dir(slug, subdir)
    vars_parts = [_HEADER]
    for cfile in cfiles:
        obj = cfile[:-2] + ".o"
        dep = cfile[:-2] + ".d"
        vars_parts.append(f"C_SRCS += \\\n../{rel}/{cfile} \n\n")
        vars_parts.append(f"C_DEPS += \\\n./{rel}/{dep} \n\n")
        vars_parts.append(f"OBJS += \\\n./{rel}/{obj} \n\n")
        vars_parts.append(f'OBJS__QUOTED += \\\n"{rel}/{obj}" \n\n')
        vars_parts.append(f'C_DEPS__QUOTED += \\\n"{rel}/{dep}" \n\n')
        vars_parts.append(f'C_SRCS__QUOTED += \\\n"../{rel}/{cfile}" \n\n')
    rules_parts = [
        _HEADER,
        f"{rel}/%.o: ../{rel}/%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)\n",
        '\t@echo \'Arm Compiler - building file: "$<"\'\n',
        _compile_recipe(compiler_dir, inc, dep_dir=rel),
        "\t@echo 'Finished building: \"$<\"'\n\t@echo ' '\n",
    ]
    return "".join(vars_parts), "".join(rules_parts)


def _render_makefile(
    module_sources: ModuleSources, proj: str, sdk_dir: str, compiler_dir: str
) -> str:
    """Debug/makefile：include 全量 subdir 文件 + ORDERED_OBJS + 链接 / clean 规则。"""
    mod_dirs = [_module_dir(slug, subdir) for slug, subdir, _ in module_sources]
    includes = "\n".join(
        ["-include sources.mk", "-include subdir_vars.mk"]
        + [f"-include {d}/subdir_vars.mk" for d in mod_dirs]
        + ["-include subdir_rules.mk"]
        + [f"-include {d}/subdir_rules.mk" for d in mod_dirs]
        + ["-include objects.mk"]
    )
    module_objs = [
        f"./{d}/{cfile[:-2]}.o"
        for d, (_, _, cfiles) in zip(mod_dirs, module_sources)
        for cfile in cfiles
    ]
    # 注意：ORDERED_OBJS 续行块内不得有空行（gmake 空行终止变量定义——
    # 空行会让后半段变成裸行解析错误）
    ordered = (
        "".join(
            f"{obj} \\\n"
            for obj in (
                "./ti_msp_dl_config.o",
                "./startup_mspm0g350x_ticlang.o",
                "./main.o",
                *module_objs,
            )
        )
        + "$(GEN_CMDS__FLAG) \\\n-Wl,-ldevice.cmd.genlibs \\\n-Wl,-llibc.a"
    )
    # clean 的 -$(RM) 清单：IDE 同款反斜杠路径（cmd DEL 语义，逐字保留）
    clean_objs = " ".join(
        ['"ti_msp_dl_config.o"', '"startup_mspm0g350x_ticlang.o"', '"main.o"']
        + [f'"{d.replace("/", "\\")}\\{cfile[:-2]}.o"'
           for d, (_, _, cfiles) in zip(mod_dirs, module_sources) for cfile in cfiles]
    )
    clean_deps = " ".join(
        ['"ti_msp_dl_config.d"', '"startup_mspm0g350x_ticlang.d"', '"main.d"']
        + [f'"{d.replace("/", "\\")}\\{cfile[:-2]}.d"'
           for d, (_, _, cfiles) in zip(mod_dirs, module_sources) for cfile in cfiles]
    )
    link = (
        f'\t"{compiler_dir}/bin/tiarmclang.exe" @"device.opt"  '
        "-march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian "
        f'-mthumb -O0 -gdwarf-3 -Wall -Wl,-m"{_OUT_NAME}.map" '
        f'-Wl,-i"{sdk_dir}/source" -Wl,-i"{proj}" -Wl,-i"{proj}/Debug/syscfg" '
        f'-Wl,-i"{compiler_dir}/lib" -Wl,--diag_wrap=off '
        f'-Wl,--display_error_number -Wl,--warn_sections '
        f'-Wl,--xml_link_info="{_OUT_NAME}_linkInfo.xml" -Wl,--rom_model '
        f'-o "{_OUT_NAME}.out" $(ORDERED_OBJS)\n'
    )
    return (
        _HEADER
        + f"CG_TOOL_ROOT := {compiler_dir}\n\n"
        + 'GEN_OPTS__FLAG := @"./device.opt"\n'
        + 'GEN_CMDS__FLAG := -Wl,-l"./device_linker.cmd"\n\n'
        + "ORDERED_OBJS += \\\n" + ordered + "\n"
        + "\n-include ../makefile.init\n\nRM := DEL /F\nRMDIR := RMDIR /S/Q\n\n"
        + includes
        + "\n\nifneq ($(MAKECMDGOALS),clean)\n"
        + "ifneq ($(strip $(C_DEPS)),)\n"
        + "-include $(C_DEPS)\nendif\nendif\n"
        + "\n-include ../makefile.defs\n\n"
        + "# Add inputs and outputs from these tool invocations to the build "
        + "variables\n"
        + f"EXE_OUTPUTS += \\\n{_OUT_NAME}.out\n\n"
        + f'EXE_OUTPUTS__QUOTED += \\\n"{_OUT_NAME}.out"\n\n\n'
        + "# All Target\nall: $(OBJS) $(GEN_CMDS)\n"
        + f"\t@$(MAKE) --no-print-directory -Onone {_OUT_NAME}.out\n\n"
        + "# Tool invocations\n"
        + f"{_OUT_NAME}.out: $(OBJS) $(GEN_CMDS)\n"
        + '\t@echo \'Arm Linker - building target: "$@"\'\n'
        + link
        + "\t@echo 'Finished building target: \"$@\"'\n\t@echo ' '\n\n"
        + "# Other Targets\nclean:\n"
        + "\t-$(RM) $(GEN_MISC_FILES__QUOTED)$(GEN_FILES__QUOTED)$(EXE_OUTPUTS__QUOTED)\n"
        + f"\t-$(RM) {clean_objs}\n"
        + f"\t-$(RM) {clean_deps}\n"
        + "\t-@echo ' '\n\n"
        + ".PHONY: all clean dependents\n.SECONDARY:\n\n"
        + "-include ../makefile.targets\n"
    )


def _compile_includes(
    proj: str,
    sdk_dir: str,
    module_dirs: Sequence[str],
    extra_include_dirs: Sequence[Path],
) -> str:
    """tiarmclang -I 参数串：工程根/Debug + 编译模块目录 + 仅头模块目录 + SDK。

    extra_include_dirs 为相对工程根的 Path（生成侧 include_dirs 单源）——只含
    .h 的模块（config）不产生模块源条目、mod_dirs 不会收录，但它的头目录必须
    进 -I，否则 uwb_uart_mspm0.c 的 #include "config_mspm0.h" 在命令行构建
    找不到（IDE 读 .cproject，gmake 只读本串）。
    """
    dirs: list[str] = [proj, f"{proj}/Debug"]
    seen = set(dirs)
    for rel in [*module_dirs, *(d.as_posix() for d in extra_include_dirs)]:
        if rel in seen:
            continue
        seen.add(rel)
        dirs.append(f"{proj}/{rel}")
    dirs.extend(
        [
            f"{sdk_dir}/source/third_party/CMSIS/Core/Include",
            f"{sdk_dir}/source",
        ]
    )
    return " ".join(f'-I"{d}"' for d in dirs)


def render_makefile_set(
    module_sources: ModuleSources,
    proj_dir: Path,
    sdk_dir: str,
    compiler_dir: str,
    sysconfig_cli: str,
    extra_include_dirs: Sequence[Path] = (),
) -> dict[str, str]:
    """参数化渲染完整 makefile 集 → {相对 Debug 目录的路径（POSIX）: 文本}。

    纯函数（不碰盘）：同参必同文——测试钉死确定性；路径全部入参（工程根 /
    SDK / 编译器 / SysConfig CLI），零硬编码。
    """
    proj = str(proj_dir)
    startup = f"{sdk_dir}/{_STARTUP_REL}"
    mod_dirs = [_module_dir(slug, subdir) for slug, subdir, _ in module_sources]
    inc = _compile_includes(proj, sdk_dir, mod_dirs, extra_include_dirs)
    files: dict[str, str] = {
        "sources.mk": _SOURCES_MK,
        "objects.mk": _OBJECTS_MK,
        "subdir_vars.mk": _root_subdir_vars(startup),
        "subdir_rules.mk": _root_subdir_rules(
            proj, sdk_dir, compiler_dir, sysconfig_cli, inc, startup
        ),
    }
    for (slug, subdir, cfiles), mod_dir in zip(module_sources, mod_dirs):
        vars_text, rules_text = _module_makefiles(
            slug, subdir, cfiles, compiler_dir, inc
        )
        files[f"{mod_dir}/subdir_vars.mk"] = vars_text
        files[f"{mod_dir}/subdir_rules.mk"] = rules_text
    files["makefile"] = _render_makefile(module_sources, proj, sdk_dir, compiler_dir)
    return files


def write_makefile_set(
    output_dir: Path,
    module_sources: ModuleSources,
    sdk_dir: str,
    compiler_dir: str,
    sysconfig_cli: str,
    extra_include_dirs: Sequence[Path] = (),
) -> tuple[str, ...]:
    """落盘 Debug/ 下完整 makefile 集（工程根相对输出目录），返回写入的
    相对路径（POSIX，排序，结构测试 / 生成摘要可用）。"""
    rendered = render_makefile_set(
        module_sources,
        output_dir.resolve(),
        sdk_dir,
        compiler_dir,
        sysconfig_cli,
        extra_include_dirs,
    )
    debug = output_dir / "Debug"
    for rel, text in rendered.items():
        target = debug / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tuple(sorted(rendered))
