"""Generate CCS-standard Debug makefile set for a generated mspm0 project (command-line gmake build).

Template mirrors the IDE-generated makefile set of a real CCS project
(~/Desktop/base/Debug, user-verified 0-error build on 2026-08-11):
Debug/makefile + sources.mk + objects.mk + subdir_vars.mk/subdir_rules.mk per source dir.
Run: python build_makefiles.py <project_root>
"""
import sys
from pathlib import Path

PROJ = Path(sys.argv[1]).resolve()
DEBUG = PROJ / "Debug"

SDK = "C:/ti/ccs2051/mspm0_sdk_2_10_00_04"
COMPILER = "C:/ti/ccs2050/ccs/tools/compiler/ti-cgt-armllvm_4.0.4.LTS"
SYSCFG = "C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat"
OUT = "mspm0_project"

MODULES = [
    ("delay", "delay.c"),
    ("ntb_time", "ntb_time.c"),
    ("key", "key.c"),
    ("oled", "oled.c"),
    ("huidu", "huidu.c"),
    ("imu_uart", "imu.c"),
    ("led_beep", "led_beep.c"),
    ("motor", "motor.c"),
]
MOD_DIRS = [f"modules/{slug}/code" for slug, _ in MODULES]
INC = " ".join(
    [f'-I"{PROJ}"', f'-I"{PROJ}/Debug"']
    + [f'-I"{PROJ}/{d}"' for d in MOD_DIRS]
    + [f'-I"{SDK}/source/third_party/CMSIS/Core/Include"', f'-I"{SDK}/source"']
)
FLAGS = "-march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -gdwarf-3 -Wall -MMD -MP"
STARTUP = f"{SDK}/source/ti/devices/msp/m0p/startup_system_files/ticlang/startup_mspm0g350x_ticlang.c"

HEADER = "################################################################################\n# Automatically-generated file. Do not edit!\n################################################################################\n\nSHELL = cmd.exe\n\n"

# ---------- sources.mk (empty shell, same as IDE) ----------
(DEBUG / "sources.mk").write_text(
    HEADER + "\n".join(f"{v} := " for v in [
        "C55_SRCS","A_SRCS","ASM_UPPER_SRCS","PINMUX_SRCS","EXE_SRCS","LDS_UPPER_SRCS",
        "CPP_SRCS","CMD_SRCS","O_SRCS","ELF_SRCS","C??_SRCS","C64_SRCS","C67_SRCS",
        "SA_SRCS","S64_SRCS","OPT_SRCS","CXX_SRCS","S67_SRCS","S??_SRCS","SV7A_SRCS",
        "SYSCFG_SRCS","K_SRCS","CLA_SRCS","S55_SRCS","LD_UPPER_SRCS","OUT_SRCS",
        "LIB_SRCS","ASM_SRCS","S_UPPER_SRCS","SYSCONFIG_SRCS","S43_SRCS","LD_SRCS",
        "CMD_UPPER_SRCS","C_UPPER_SRCS","C++_SRCS","C43_SRCS","OBJ_SRCS","LDS_SRCS",
        "S_SRCS","CC_SRCS","S62_SRCS","C62_SRCS","C_SRCS","C55_DEPS","C_UPPER_DEPS",
        "S67_DEPS","S62_DEPS","S_DEPS","OPT_DEPS","C??_DEPS","ASM_UPPER_DEPS",
        "S??_DEPS","C64_DEPS","CXX_DEPS","S64_DEPS","GEN_CMDS","GEN_FILES",
        "CLA_DEPS","S55_DEPS","SV7A_DEPS","EXE_OUTPUTS","C62_DEPS","C67_DEPS",
        "GEN_MISC_DIRS","K_DEPS","C_DEPS","CC_DEPS","BIN_OUTPUTS","GEN_OPTS",
        "C++_DEPS","C43_DEPS","S43_DEPS","OBJS","ASM_DEPS","GEN_MISC_FILES",
        "S_UPPER_DEPS","CPP_DEPS","SA_DEPS",
    ]) + "\n\n",
    encoding="utf-8",
)

# ---------- objects.mk ----------
(DEBUG / "objects.mk").write_text(
    HEADER + "USER_OBJS :=\n\nLIBS := -Wl,-ldevice.cmd.genlibs -Wl,-llibc.a\n",
    encoding="utf-8",
)

# ---------- root subdir_vars.mk ----------
def quoted_lines(name, values, quote=True):
    return f"{name} += \\\n" + "\n".join(f"{chr(34)}{v}{chr(34)} \\" if quote else f"{v} \\" for v in values) + " \n\n"

root_vars = HEADER + "SYSCFG_SRCS += \\\n../mspm0.syscfg \n\n"
root_vars += "C_SRCS += \\\n./ti_msp_dl_config.c \\\n" + f"C:/ti/ccs2051/mspm0_sdk_2_10_00_04/source/ti/devices/msp/m0p/startup_system_files/ticlang/startup_mspm0g350x_ticlang.c \\\n../main.c \n\n"
root_vars += "GEN_CMDS += \\\n./device_linker.cmd \n\n"
root_vars += "GEN_FILES += \\\n./device_linker.cmd \\\n./device.opt \\\n./ti_msp_dl_config.c \n\n"
root_vars += "C_DEPS += \\\n./ti_msp_dl_config.d \\\n./startup_mspm0g350x_ticlang.d \\\n./main.d \n\n"
root_vars += "GEN_OPTS += \\\n./device.opt \n\n"
root_vars += "OBJS += \\\n./ti_msp_dl_config.o \\\n./startup_mspm0g350x_ticlang.o \\\n./main.o \n\n"
root_vars += "GEN_MISC_FILES += \\\n./device.cmd.genlibs \\\n./ti_msp_dl_config.h \\\n./Event.dot \n\n"
root_vars += quoted_lines("OBJS__QUOTED", ["ti_msp_dl_config.o", "startup_mspm0g350x_ticlang.o", "main.o"])
root_vars += quoted_lines("GEN_MISC_FILES__QUOTED", ["device.cmd.genlibs", "ti_msp_dl_config.h", "Event.dot"])
root_vars += quoted_lines("C_DEPS__QUOTED", ["ti_msp_dl_config.d", "startup_mspm0g350x_ticlang.d", "main.d"])
root_vars += quoted_lines("GEN_FILES__QUOTED", ["device_linker.cmd", "device.opt", "ti_msp_dl_config.c"])
root_vars += 'SYSCFG_SRCS__QUOTED += \\\n"../mspm0.syscfg" \n\n'
root_vars += quoted_lines("C_SRCS__QUOTED", ["./ti_msp_dl_config.c", STARTUP, "../main.c"])
(DEBUG / "subdir_vars.mk").write_text(root_vars, encoding="utf-8")

# ---------- root subdir_rules.mk ----------
root_rules = HEADER + "build-1290584808: ../mspm0.syscfg\n"
root_rules += '\t@echo \'SysConfig - building file: "$<"\'\n'
root_rules += f'\t"{SYSCFG}" -s "{SDK}/.metadata/product.json" --script "{PROJ}/mspm0.syscfg" -o "." --compiler ticlang\n'
root_rules += "\t@echo 'Finished building: \"$<\"'\n\t@echo ' '\n\n"
for gen in ["device_linker.cmd", "device.opt", "device.cmd.genlibs", "ti_msp_dl_config.c", "ti_msp_dl_config.h", "Event.dot"]:
    root_rules += f"{gen}: build-1290584808\n"
root_rules += "\n%.o: ./%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)\n"
root_rules += '\t@echo \'Arm Compiler - building file: "$<"\'\n'
root_rules += f'\t"{COMPILER}/bin/tiarmclang.exe" -c @"./device.opt" {FLAGS} {INC} -MF"$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"\n'
root_rules += "\t@echo 'Finished building: \"$<\"'\n\t@echo ' '\n\n"
root_rules += f"startup_mspm0g350x_ticlang.o: {STARTUP} $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)\n"
root_rules += '\t@echo \'Arm Compiler - building file: "$<"\'\n'
root_rules += f'\t"{COMPILER}/bin/tiarmclang.exe" -c @"./device.opt" {FLAGS} {INC} -MF"$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"\n'
root_rules += "\t@echo 'Finished building: \"$<\"'\n\t@echo ' '\n\n"
root_rules += "%.o: ../%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)\n"
root_rules += '\t@echo \'Arm Compiler - building file: "$<"\'\n'
root_rules += f'\t"{COMPILER}/bin/tiarmclang.exe" -c @"./device.opt" {FLAGS} {INC} -MF"$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"\n'
root_rules += "\t@echo 'Finished building: \"$<\"'\n\t@echo ' '\n"
(DEBUG / "subdir_rules.mk").write_text(root_rules, encoding="utf-8")

# ---------- per-module subdir_vars.mk / subdir_rules.mk ----------
for slug, cfile in MODULES:
    rel = f"modules/{slug}/code"
    d = DEBUG / rel
    d.mkdir(parents=True, exist_ok=True)
    src = f"../{rel}/{cfile}"
    deps = f"./{rel}/{cfile.replace('.c', '.d')}"
    obj = f"./{rel}/{cfile.replace('.c', '.o')}"
    vars = HEADER
    vars += f"C_SRCS += \\\n{src} \n\n"
    vars += f"C_DEPS += \\\n{deps} \n\n"
    vars += f"OBJS += \\\n{obj} \n\n"
    vars += f"OBJS__QUOTED += \\\n{chr(34)}{rel}/{cfile.replace('.c', '.o')}{chr(34)} \n\n"
    vars += f"C_DEPS__QUOTED += \\\n{chr(34)}{rel}/{cfile.replace('.c', '.d')}{chr(34)} \n\n"
    vars += f"C_SRCS__QUOTED += \\\n{chr(34)}{src}{chr(34)} \n\n"
    (d / "subdir_vars.mk").write_text(vars, encoding="utf-8")

    rules = HEADER
    rules += f"{rel}/%.o: ../{rel}/%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)\n"
    rules += '\t@echo \'Arm Compiler - building file: "$<"\'\n'
    rules += f'\t"{COMPILER}/bin/tiarmclang.exe" -c @"./device.opt" {FLAGS} {INC} -MF"{rel}/$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"\n'
    rules += "\t@echo 'Finished building: \"$<\"'\n\t@echo ' '\n"
    (d / "subdir_rules.mk").write_text(rules, encoding="utf-8")

# ---------- Debug/makefile ----------
includes = "\n".join(f"-include {f}" for f in [
    "sources.mk", "subdir_vars.mk",
] + [f"{rel}/subdir_vars.mk" for _, rel in [("", "")]] + [f"modules/{s}/code/subdir_vars.mk" for s, _ in MODULES]
  + ["subdir_rules.mk"] + [f"modules/{s}/code/subdir_rules.mk" for s, _ in MODULES] + ["objects.mk"])

ordered_objs = "\n".join(
    [o + " \\" for o in (
        ["./ti_msp_dl_config.o", "./startup_mspm0g350x_ticlang.o", "./main.o"]
        + [f"./modules/{s}/code/{c.replace('.c', '.o')}" for s, c in MODULES]
    )]
) + "\n$(GEN_CMDS__FLAG) \\\n-Wl,-ldevice.cmd.genlibs \\\n-Wl,-llibc.a"
objs_quoted = "\n".join(
    ['"ti_msp_dl_config.o"', '"startup_mspm0g350x_ticlang.o"', '"main.o"']
    + [f'"modules\\{s}\\code\\{c.replace(chr(46)+chr(99), chr(46)+chr(111))}"' for s, c in MODULES]
)

makefile = f"""################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

CG_TOOL_ROOT := {COMPILER}

GEN_OPTS__FLAG := @"./device.opt"
GEN_CMDS__FLAG := -Wl,-l"./device_linker.cmd"

ORDERED_OBJS += \\
{ordered_objs}
""" + "\n-include ../makefile.init\n\nRM := DEL /F\nRMDIR := RMDIR /S/Q\n\n" + includes + """

ifneq ($(MAKECMDGOALS),clean)
ifneq ($(strip $(C_DEPS)),)
-include $(C_DEPS)
endif
endif

-include ../makefile.defs

# Add inputs and outputs from these tool invocations to the build variables
EXE_OUTPUTS += \\
""" + OUT + """.out

EXE_OUTPUTS__QUOTED += \\
"mspm0_project.out"


# All Target
all: $(OBJS) $(GEN_CMDS)
	@$(MAKE) --no-print-directory -Onone """ + OUT + """.out"

# Tool invocations
""" + OUT + """.out: $(OBJS) $(GEN_CMDS)
	@echo 'Arm Linker - building target: "$@"'
	\"""" + COMPILER + """/bin/tiarmclang.exe" @"device.opt"  -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -gdwarf-3 -Wall -Wl,-m\"""" + OUT + """.map" -Wl,-i\"""" + SDK + """/source" -Wl,-i\"""" + str(PROJ) + """\" -Wl,-i\"""" + str(PROJ) + """/Debug/syscfg" -Wl,-i\"""" + COMPILER + """/lib" -Wl,--diag_wrap=off -Wl,--display_error_number -Wl,--warn_sections -Wl,--xml_link_info=\"""" + OUT + """_linkInfo.xml" -Wl,--rom_model -o \"""" + OUT + """.out" $(ORDERED_OBJS)
	@echo 'Finished building target: "$@"'
	@echo ' '

# Other Targets
clean:
	-$(RM) $(GEN_MISC_FILES__QUOTED)$(GEN_FILES__QUOTED)$(EXE_OUTPUTS__QUOTED)
	-$(RM) """ + objs_quoted.replace("\n", " ") + """
	-$(RM) """ + " ".join(['"ti_msp_dl_config.d"', '"startup_mspm0g350x_ticlang.d"', '"main.d"'] + [f'"modules\\{s}\\code\\{c.replace(".c", ".d")}"' for s, c in MODULES]) + """
	-@echo ' '

.PHONY: all clean dependents
.SECONDARY:

-include ../makefile.targets
"""
(DEBUG / "makefile").write_text(makefile, encoding="utf-8")

print(f"makefile set written to {DEBUG} for {len(MODULES)} modules")
