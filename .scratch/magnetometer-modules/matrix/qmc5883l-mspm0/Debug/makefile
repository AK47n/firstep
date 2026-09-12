################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

CG_TOOL_ROOT := C:\ti\ccs2050\ccs\tools\compiler\ti-cgt-armllvm_4.0.4.LTS

GEN_OPTS__FLAG := @"./device.opt"
GEN_CMDS__FLAG := -Wl,-l"./device_linker.cmd"

ORDERED_OBJS += \
./ti_msp_dl_config.o \
./startup_mspm0g350x_ticlang.o \
./main.o \
./modules/delay/code/delay.o \
./modules/qmc5883l/code/qmc5883l.o \
$(GEN_CMDS__FLAG) \
-Wl,-ldevice.cmd.genlibs \
-Wl,-llibc.a

-include ../makefile.init

RM := DEL /F
RMDIR := RMDIR /S/Q

-include sources.mk
-include subdir_vars.mk
-include modules/delay/code/subdir_vars.mk
-include modules/qmc5883l/code/subdir_vars.mk
-include subdir_rules.mk
-include modules/delay/code/subdir_rules.mk
-include modules/qmc5883l/code/subdir_rules.mk
-include objects.mk

ifneq ($(MAKECMDGOALS),clean)
ifneq ($(strip $(C_DEPS)),)
-include $(C_DEPS)
endif
endif

-include ../makefile.defs

# Add inputs and outputs from these tool invocations to the build variables
EXE_OUTPUTS += \
mspm0_project.out

EXE_OUTPUTS__QUOTED += \
"mspm0_project.out"


# All Target
all: $(OBJS) $(GEN_CMDS)
	@$(MAKE) --no-print-directory -Onone mspm0_project.out

# Tool invocations
mspm0_project.out: $(OBJS) $(GEN_CMDS)
	@echo 'Arm Linker - building target: "$@"'
	"C:\ti\ccs2050\ccs\tools\compiler\ti-cgt-armllvm_4.0.4.LTS/bin/tiarmclang.exe" @"device.opt"  -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -gdwarf-3 -Wall -Wl,-m"mspm0_project.map" -Wl,-i"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/source" -Wl,-i".." -Wl,-i"./syscfg" -Wl,-i"C:\ti\ccs2050\ccs\tools\compiler\ti-cgt-armllvm_4.0.4.LTS/lib" -Wl,--diag_wrap=off -Wl,--display_error_number -Wl,--warn_sections -Wl,--xml_link_info="mspm0_project_linkInfo.xml" -Wl,--rom_model -o "mspm0_project.out" $(ORDERED_OBJS)
	@echo 'Finished building target: "$@"'
	@echo ' '

# Other Targets
clean:
	-$(RM) $(GEN_MISC_FILES__QUOTED)$(GEN_FILES__QUOTED)$(EXE_OUTPUTS__QUOTED)
	-$(RM) "ti_msp_dl_config.o" "startup_mspm0g350x_ticlang.o" "main.o" "modules\delay\code\delay.o" "modules\qmc5883l\code\qmc5883l.o"
	-$(RM) "ti_msp_dl_config.d" "startup_mspm0g350x_ticlang.d" "main.d" "modules\delay\code\delay.d" "modules\qmc5883l\code\qmc5883l.d"
	-@echo ' '

.PHONY: all clean dependents
.SECONDARY:

-include ../makefile.targets
