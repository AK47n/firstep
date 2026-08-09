################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

# Each subdirectory must supply rules for building sources it contributes
%.o: ../%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:/ti/ccs2051/ti_cgt_arm_llvm_4.0.2.LTS/bin/tiarmclang.exe" -c @"device.opt"  -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -I"C:/Users/luoji/Desktop/car/car 1.1" -I"C:/Users/luoji/Desktop/car/car 1.1/USART_JY61P" -I"C:/Users/luoji/Desktop/car/car 1.1/Debug" -I"C:/ti/ccs2051/mspm0_sdk_2_10_00_04/source/third_party/CMSIS/Core/Include" -I"C:/ti/ccs2051/mspm0_sdk_2_10_00_04/source" -D__MSPM0G3507__ -gdwarf-3 -MMD -MP -MF"$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

build-474970721: ../empty.syscfg
	@echo 'SysConfig - building file: "$<"'
	"C:/ti/ccs2051/sysconfig_1.26.2/sysconfig_cli.bat" -s "C:/ti/ccs2051/mspm0_sdk_2_10_00_04/.metadata/product.json" --script "C:/Users/luoji/Desktop/car/car 1.1/empty.syscfg" -o "." --compiler ticlang
	@echo 'Finished building: "$<"'
	@echo ' '

device_linker.cmd: build-474970721 ../empty.syscfg
device.opt: build-474970721
device.cmd.genlibs: build-474970721
ti_msp_dl_config.c: build-474970721
ti_msp_dl_config.h: build-474970721
Event.dot: build-474970721

%.o: ./%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:/ti/ccs2051/ti_cgt_arm_llvm_4.0.2.LTS/bin/tiarmclang.exe" -c @"device.opt"  -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -I"C:/Users/luoji/Desktop/car/car 1.1" -I"C:/Users/luoji/Desktop/car/car 1.1/USART_JY61P" -I"C:/Users/luoji/Desktop/car/car 1.1/Debug" -I"C:/ti/ccs2051/mspm0_sdk_2_10_00_04/source/third_party/CMSIS/Core/Include" -I"C:/ti/ccs2051/mspm0_sdk_2_10_00_04/source" -D__MSPM0G3507__ -gdwarf-3 -MMD -MP -MF"$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '

startup_mspm0g350x_ticlang.o: C:/ti/ccs2051/mspm0_sdk_2_10_00_04/source/ti/devices/msp/m0p/startup_system_files/ticlang/startup_mspm0g350x_ticlang.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:/ti/ccs2051/ti_cgt_arm_llvm_4.0.2.LTS/bin/tiarmclang.exe" -c @"device.opt"  -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -I"C:/Users/luoji/Desktop/car/car 1.1" -I"C:/Users/luoji/Desktop/car/car 1.1/USART_JY61P" -I"C:/Users/luoji/Desktop/car/car 1.1/Debug" -I"C:/ti/ccs2051/mspm0_sdk_2_10_00_04/source/third_party/CMSIS/Core/Include" -I"C:/ti/ccs2051/mspm0_sdk_2_10_00_04/source" -D__MSPM0G3507__ -gdwarf-3 -MMD -MP -MF"$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '


