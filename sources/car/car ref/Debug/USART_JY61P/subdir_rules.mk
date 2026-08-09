################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

# Each subdirectory must supply rules for building sources it contributes
USART_JY61P/%.o: ../USART_JY61P/%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:/ti/ccs2051/ti_cgt_arm_llvm_4.0.2.LTS/bin/tiarmclang.exe" -c @"device.opt"  -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -I"C:/Users/luoji/Desktop/car/car ref" -I"C:/Users/luoji/Desktop/car/car ref/USART_JY61P" -I"C:/Users/luoji/Desktop/car/car ref/Debug" -I"C:/ti/ccs2051/mspm0_sdk_2_10_00_04/source/third_party/CMSIS/Core/Include" -I"C:/ti/ccs2051/mspm0_sdk_2_10_00_04/source" -D__MSPM0G3507__ -gdwarf-3 -MMD -MP -MF"USART_JY61P/$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '


