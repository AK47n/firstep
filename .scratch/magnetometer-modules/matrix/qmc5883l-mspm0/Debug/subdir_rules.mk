################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

build-1290584808: ../mspm0.syscfg
	@echo 'SysConfig - building file: "$<"'
	"C:\ti\ccs2051\sysconfig_1.26.2\sysconfig_cli.bat" -s "C:\ti\ccs2051\mspm0_sdk_2_10_00_04/.metadata/product.json" --script "../mspm0.syscfg" -o "." --compiler ticlang
	@echo 'Finished building: "$<"'
	@echo ' '

device_linker.cmd: build-1290584808
device.opt: build-1290584808
device.cmd.genlibs: build-1290584808
ti_msp_dl_config.c: build-1290584808
ti_msp_dl_config.h: build-1290584808
Event.dot: build-1290584808

%.o: ./%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:\ti\ccs2050\ccs\tools\compiler\ti-cgt-armllvm_4.0.4.LTS/bin/tiarmclang.exe" -c @"./device.opt" -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -gdwarf-3 -Wall -MMD -MP -I".." -I"." -I"../modules/delay/code" -I"../modules/qmc5883l/code" -I"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/source/third_party/CMSIS/Core/Include" -I"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/source" -MF"$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

startup_mspm0g350x_ticlang.o: C:\ti\ccs2051\mspm0_sdk_2_10_00_04/source/ti/devices/msp/m0p/startup_system_files/ticlang/startup_mspm0g350x_ticlang.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:\ti\ccs2050\ccs\tools\compiler\ti-cgt-armllvm_4.0.4.LTS/bin/tiarmclang.exe" -c @"./device.opt" -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -gdwarf-3 -Wall -MMD -MP -I".." -I"." -I"../modules/delay/code" -I"../modules/qmc5883l/code" -I"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/source/third_party/CMSIS/Core/Include" -I"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/source" -MF"$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

%.o: ../%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:\ti\ccs2050\ccs\tools\compiler\ti-cgt-armllvm_4.0.4.LTS/bin/tiarmclang.exe" -c @"./device.opt" -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -gdwarf-3 -Wall -MMD -MP -I".." -I"." -I"../modules/delay/code" -I"../modules/qmc5883l/code" -I"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/source/third_party/CMSIS/Core/Include" -I"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/source" -MF"$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '
