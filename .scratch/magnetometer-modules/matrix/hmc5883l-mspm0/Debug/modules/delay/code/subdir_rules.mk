################################################################################
# Automatically-generated file. Do not edit!
################################################################################

SHELL = cmd.exe

modules/delay/code/%.o: ../modules/delay/code/%.c $(GEN_OPTS) | $(GEN_FILES) $(GEN_MISC_FILES)
	@echo 'Arm Compiler - building file: "$<"'
	"C:\ti\ccs2050\ccs\tools\compiler\ti-cgt-armllvm_4.0.4.LTS/bin/tiarmclang.exe" -c @"./device.opt" -march=thumbv6m -mcpu=cortex-m0plus -mfloat-abi=soft -mlittle-endian -mthumb -O0 -gdwarf-3 -Wall -MMD -MP -I".." -I"." -I"../modules/delay/code" -I"../modules/hmc5883l/code" -I"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/source/third_party/CMSIS/Core/Include" -I"C:\ti\ccs2051\mspm0_sdk_2_10_00_04/source" -MF"modules/delay/code/$(basename $(<F)).d_raw" -MT"$(@)"  $(GEN_OPTS__FLAG) -o"$@" "$<"
	@echo 'Finished building: "$<"'
	@echo ' '
