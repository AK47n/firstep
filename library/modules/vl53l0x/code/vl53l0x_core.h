/* 来源：立创开发板技术文档中心（wiki.lckfb.com）《VL53L0X激光测距传感器》
 * 页面：https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/vl53l0x-laser-distance-sensor.html
 * 驱动源码：立创地阔星 STM32F103C8T6 移植工程（网盘下载并解压）——
 * 网盘包：sources/materials/lckfb-地阔星移植手册/网盘下载/vl53l0x/
 *        STM32F103C8T6_ProjectTemplate/bsp/VL53L0X/ （ST 官方 VL53L0X API
 *        类型/宏集 + 立创 BSP 平台适配；BSD-3-Clause，文件头保留 ST 版权
 *        声明；使用 / 复制 / 修改 / 传播请遵循 ST 许可与立创版权要求）。
 * 本头 = 最小切片的合并裁剪：原 5 个头（types/device/def/tuning/
 * interrupt_threshold_settings）+ 立创 platform.h 的类型/宏合并为一，
 * 外部 include 全部剔除（stm32f10x.h/i2c/platform_log 等），stdint/math
 * 等标准头保留；日志宏（ST 的 LOG_*）以空实现内联。
 */

#ifndef VL53L0X_CORE_H
#define VL53L0X_CORE_H

#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* ST 日志/字符串宏空实现（原 vl53l0x_platform_log.h 无日志编译——内联） */
#define VL53L0X_ErrLog(...) (void)0
#define _LOG_FUNCTION_START(module, fmt, ...) (void)0
#define _LOG_FUNCTION_END(module, status, ...) (void)0
#define _LOG_FUNCTION_END_FMT(module, status, fmt, ...) (void)0
#define LOG_FUNCTION_START(...) (void)0
#define LOG_FUNCTION_END(...) (void)0
#define LOG_FUNCTION_END_FMT(...) (void)0
#define VL53L0X_COPYSTRING(str, ...) strcpy(str, __VA_ARGS__)

/*******************************************************************************
Copyright ?2015, STMicroelectronics International N.V.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of STMicroelectronics nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
NON-INFRINGEMENT OF INTELLECTUAL PROPERTY RIGHTS ARE DISCLAIMED.
IN NO EVENT SHALL STMICROELECTRONICS INTERNATIONAL N.V. BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
********************************************************************************/
/**
 * @file  vl53l0_types.h
 * @brief VL53L0 types definition
 */

#ifndef VL53L0X_TYPES_H_
#define VL53L0X_TYPES_H_

/** @defgroup porting_type  Basic type definition
 *  @ingroup  VL53L0X_platform_group
 *
 *  @brief  file vl53l0_types.h files hold basic type definition that may requires porting
 *
 *  contains type that must be defined for the platform\n
 *  when target platform and compiler provide stdint.h and stddef.h it is enough to include it.\n
 *  If stdint.h is not available review and adapt all signed and unsigned 8/16/32 bits basic types. \n
 *  If stddef.h is not available review and adapt NULL definition .
 */
#include <stdint.h>
#include <stddef.h>

#ifndef NULL
#error "Error NULL definition should be done. Please add required include "
#endif


#if ! defined(STDINT_H) &&  !defined(_GCC_STDINT_H) &&!defined(__STDINT_DECLS) && !defined(_GCC_WRAP_STDINT_H)

 #pragma message("Please review  type definition of STDINT define for your platform and add to list above ")

 /*
  *  target platform do not provide stdint or use a different #define than above
  *  to avoid seeing the message below addapt the #define list above or implement
  *  all type and delete these pragma
  */

/** \ingroup VL53L0X_portingType_group
 * @{
 */


//typedef unsigned long long uint64_t;


/** @brief Typedef defining 32 bit unsigned int type.\n
 * The developer should modify this to suit the platform being deployed.
 */
//typedef unsigned int uint32_t;

/** @brief Typedef defining 32 bit int type.\n
 * The developer should modify this to suit the platform being deployed.
 */
//typedef int int32_t;

/** @brief Typedef defining 16 bit unsigned short type.\n
 * The developer should modify this to suit the platform being deployed.
 */
//typedef unsigned short uint16_t;

/** @brief Typedef defining 16 bit short type.\n
 * The developer should modify this to suit the platform being deployed.
 */
//typedef short int16_t;

/** @brief Typedef defining 8 bit unsigned char type.\n
 * The developer should modify this to suit the platform being deployed.
 */
//typedef unsigned char uint8_t;

/** @brief Typedef defining 8 bit char type.\n
 * The developer should modify this to suit the platform being deployed.
 */
//typedef signed char int8_t;

/** @}  */
#endif /* _STDINT_H */


/** use where fractional values are expected
 *
 * Given a floating point value f it's .16 bit point is (int)(f*(1<<16))*/
typedef uint32_t FixPoint1616_t;

#endif /* VL53L0X_TYPES_H_ */


/*******************************************************************************
Copyright � 2016, STMicroelectronics International N.V.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of STMicroelectronics nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
NON-INFRINGEMENT OF INTELLECTUAL PROPERTY RIGHTS ARE DISCLAIMED.
IN NO EVENT SHALL STMICROELECTRONICS INTERNATIONAL N.V. BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*******************************************************************************/

/**
 * Device specific defines. To be adapted by implementer for the targeted
 * device.
 */

#ifndef _VL53L0X_DEVICE_H_
#define _VL53L0X_DEVICE_H_



/** @defgroup VL53L0X_DevSpecDefines_group VL53L0X cut1.1 Device Specific Defines
 *  @brief VL53L0X cut1.1 Device Specific Defines
 *  @{
 */


/** @defgroup VL53L0X_DeviceError_group Device Error
 *  @brief Device Error code
 *
 *  This enum is Device specific it should be updated in the implementation
 *  Use @a VL53L0X_GetStatusErrorString() to get the string.
 *  It is related to Status Register of the Device.
 *  @{
 */
typedef uint8_t VL53L0X_DeviceError;

#define VL53L0X_DEVICEERROR_NONE                        ((VL53L0X_DeviceError) 0)
	/*!< 0  NoError  */
#define VL53L0X_DEVICEERROR_VCSELCONTINUITYTESTFAILURE  ((VL53L0X_DeviceError) 1)
#define VL53L0X_DEVICEERROR_VCSELWATCHDOGTESTFAILURE    ((VL53L0X_DeviceError) 2)
#define VL53L0X_DEVICEERROR_NOVHVVALUEFOUND             ((VL53L0X_DeviceError) 3)
#define VL53L0X_DEVICEERROR_MSRCNOTARGET                ((VL53L0X_DeviceError) 4)
#define VL53L0X_DEVICEERROR_SNRCHECK                    ((VL53L0X_DeviceError) 5)
#define VL53L0X_DEVICEERROR_RANGEPHASECHECK             ((VL53L0X_DeviceError) 6)
#define VL53L0X_DEVICEERROR_SIGMATHRESHOLDCHECK         ((VL53L0X_DeviceError) 7)
#define VL53L0X_DEVICEERROR_TCC                         ((VL53L0X_DeviceError) 8)
#define VL53L0X_DEVICEERROR_PHASECONSISTENCY            ((VL53L0X_DeviceError) 9)
#define VL53L0X_DEVICEERROR_MINCLIP                     ((VL53L0X_DeviceError) 10)
#define VL53L0X_DEVICEERROR_RANGECOMPLETE               ((VL53L0X_DeviceError) 11)
#define VL53L0X_DEVICEERROR_ALGOUNDERFLOW               ((VL53L0X_DeviceError) 12)
#define VL53L0X_DEVICEERROR_ALGOOVERFLOW                ((VL53L0X_DeviceError) 13)
#define VL53L0X_DEVICEERROR_RANGEIGNORETHRESHOLD        ((VL53L0X_DeviceError) 14)

/** @} end of VL53L0X_DeviceError_group */


/** @defgroup VL53L0X_CheckEnable_group Check Enable list
 *  @brief Check Enable code
 *
 *  Define used to specify the LimitCheckId.
 *  Use @a VL53L0X_GetLimitCheckInfo() to get the string.
 *  @{
 */

#define VL53L0X_CHECKENABLE_SIGMA_FINAL_RANGE           0
#define VL53L0X_CHECKENABLE_SIGNAL_RATE_FINAL_RANGE     1
#define VL53L0X_CHECKENABLE_SIGNAL_REF_CLIP             2
#define VL53L0X_CHECKENABLE_RANGE_IGNORE_THRESHOLD      3
#define VL53L0X_CHECKENABLE_SIGNAL_RATE_MSRC            4
#define VL53L0X_CHECKENABLE_SIGNAL_RATE_PRE_RANGE       5

#define VL53L0X_CHECKENABLE_NUMBER_OF_CHECKS            6

/** @}  end of VL53L0X_CheckEnable_group */


/** @defgroup VL53L0X_GpioFunctionality_group Gpio Functionality
 *  @brief Defines the different functionalities for the device GPIO(s)
 *  @{
 */
typedef uint8_t VL53L0X_GpioFunctionality;

#define VL53L0X_GPIOFUNCTIONALITY_OFF                     \
	((VL53L0X_GpioFunctionality)  0) /*!< NO Interrupt  */
#define VL53L0X_GPIOFUNCTIONALITY_THRESHOLD_CROSSED_LOW   \
	((VL53L0X_GpioFunctionality)  1) /*!< Level Low (value < thresh_low)  */
#define VL53L0X_GPIOFUNCTIONALITY_THRESHOLD_CROSSED_HIGH   \
	((VL53L0X_GpioFunctionality)  2) /*!< Level High (value > thresh_high) */
#define VL53L0X_GPIOFUNCTIONALITY_THRESHOLD_CROSSED_OUT    \
	((VL53L0X_GpioFunctionality)  3)
	/*!< Out Of Window (value < thresh_low OR value > thresh_high)  */
#define VL53L0X_GPIOFUNCTIONALITY_NEW_MEASURE_READY        \
	((VL53L0X_GpioFunctionality)  4) /*!< New Sample Ready  */

/** @} end of VL53L0X_GpioFunctionality_group */


/* Device register map */

/** @defgroup VL53L0X_DefineRegisters_group Define Registers
 *  @brief List of all the defined registers
 *  @{
 */
#define VL53L0X_REG_SYSRANGE_START                        0x000
	/** mask existing bit in #VL53L0X_REG_SYSRANGE_START*/
	#define VL53L0X_REG_SYSRANGE_MODE_MASK          0x0F
	/** bit 0 in #VL53L0X_REG_SYSRANGE_START write 1 toggle state in
	 * continuous mode and arm next shot in single shot mode */
	#define VL53L0X_REG_SYSRANGE_MODE_START_STOP    0x01
	/** bit 1 write 0 in #VL53L0X_REG_SYSRANGE_START set single shot mode */
	#define VL53L0X_REG_SYSRANGE_MODE_SINGLESHOT    0x00
	/** bit 1 write 1 in #VL53L0X_REG_SYSRANGE_START set back-to-back
	 *  operation mode */
	#define VL53L0X_REG_SYSRANGE_MODE_BACKTOBACK    0x02
	/** bit 2 write 1 in #VL53L0X_REG_SYSRANGE_START set timed operation
	 *  mode */
	#define VL53L0X_REG_SYSRANGE_MODE_TIMED         0x04
	/** bit 3 write 1 in #VL53L0X_REG_SYSRANGE_START set histogram operation
	 *  mode */
	#define VL53L0X_REG_SYSRANGE_MODE_HISTOGRAM     0x08


#define VL53L0X_REG_SYSTEM_THRESH_HIGH               0x000C
#define VL53L0X_REG_SYSTEM_THRESH_LOW                0x000E


#define VL53L0X_REG_SYSTEM_SEQUENCE_CONFIG		0x0001
#define VL53L0X_REG_SYSTEM_RANGE_CONFIG			0x0009
#define VL53L0X_REG_SYSTEM_INTERMEASUREMENT_PERIOD	0x0004


#define VL53L0X_REG_SYSTEM_INTERRUPT_CONFIG_GPIO               0x000A
	#define VL53L0X_REG_SYSTEM_INTERRUPT_GPIO_DISABLED	0x00
	#define VL53L0X_REG_SYSTEM_INTERRUPT_GPIO_LEVEL_LOW	0x01
	#define VL53L0X_REG_SYSTEM_INTERRUPT_GPIO_LEVEL_HIGH	0x02
	#define VL53L0X_REG_SYSTEM_INTERRUPT_GPIO_OUT_OF_WINDOW	0x03
	#define VL53L0X_REG_SYSTEM_INTERRUPT_GPIO_NEW_SAMPLE_READY	0x04

#define VL53L0X_REG_GPIO_HV_MUX_ACTIVE_HIGH          0x0084


#define VL53L0X_REG_SYSTEM_INTERRUPT_CLEAR           0x000B

/* Result registers */
#define VL53L0X_REG_RESULT_INTERRUPT_STATUS          0x0013
#define VL53L0X_REG_RESULT_RANGE_STATUS              0x0014

#define VL53L0X_REG_RESULT_CORE_PAGE  1
#define VL53L0X_REG_RESULT_CORE_AMBIENT_WINDOW_EVENTS_RTN   0x00BC
#define VL53L0X_REG_RESULT_CORE_RANGING_TOTAL_EVENTS_RTN    0x00C0
#define VL53L0X_REG_RESULT_CORE_AMBIENT_WINDOW_EVENTS_REF   0x00D0
#define VL53L0X_REG_RESULT_CORE_RANGING_TOTAL_EVENTS_REF    0x00D4
#define VL53L0X_REG_RESULT_PEAK_SIGNAL_RATE_REF             0x00B6

/* Algo register */

#define VL53L0X_REG_ALGO_PART_TO_PART_RANGE_OFFSET_MM       0x0028

#define VL53L0X_REG_I2C_SLAVE_DEVICE_ADDRESS                0x008a

/* Check Limit registers */
#define VL53L0X_REG_MSRC_CONFIG_CONTROL                     0x0060

#define VL53L0X_REG_PRE_RANGE_CONFIG_MIN_SNR                      0X0027
#define VL53L0X_REG_PRE_RANGE_CONFIG_VALID_PHASE_LOW              0x0056
#define VL53L0X_REG_PRE_RANGE_CONFIG_VALID_PHASE_HIGH             0x0057
#define VL53L0X_REG_PRE_RANGE_MIN_COUNT_RATE_RTN_LIMIT            0x0064

#define VL53L0X_REG_FINAL_RANGE_CONFIG_MIN_SNR                    0X0067
#define VL53L0X_REG_FINAL_RANGE_CONFIG_VALID_PHASE_LOW            0x0047
#define VL53L0X_REG_FINAL_RANGE_CONFIG_VALID_PHASE_HIGH           0x0048
#define VL53L0X_REG_FINAL_RANGE_CONFIG_MIN_COUNT_RATE_RTN_LIMIT   0x0044


#define VL53L0X_REG_PRE_RANGE_CONFIG_SIGMA_THRESH_HI              0X0061
#define VL53L0X_REG_PRE_RANGE_CONFIG_SIGMA_THRESH_LO              0X0062

/* PRE RANGE registers */
#define VL53L0X_REG_PRE_RANGE_CONFIG_VCSEL_PERIOD                 0x0050
#define VL53L0X_REG_PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI            0x0051
#define VL53L0X_REG_PRE_RANGE_CONFIG_TIMEOUT_MACROP_LO            0x0052

#define VL53L0X_REG_SYSTEM_HISTOGRAM_BIN                          0x0081
#define VL53L0X_REG_HISTOGRAM_CONFIG_INITIAL_PHASE_SELECT         0x0033
#define VL53L0X_REG_HISTOGRAM_CONFIG_READOUT_CTRL                 0x0055

#define VL53L0X_REG_FINAL_RANGE_CONFIG_VCSEL_PERIOD               0x0070
#define VL53L0X_REG_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI          0x0071
#define VL53L0X_REG_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_LO          0x0072
#define VL53L0X_REG_CROSSTALK_COMPENSATION_PEAK_RATE_MCPS         0x0020

#define VL53L0X_REG_MSRC_CONFIG_TIMEOUT_MACROP                    0x0046


#define VL53L0X_REG_SOFT_RESET_GO2_SOFT_RESET_N	                 0x00bf
#define VL53L0X_REG_IDENTIFICATION_MODEL_ID                       0x00c0
#define VL53L0X_REG_IDENTIFICATION_REVISION_ID                    0x00c2

#define VL53L0X_REG_OSC_CALIBRATE_VAL                             0x00f8


#define VL53L0X_SIGMA_ESTIMATE_MAX_VALUE                          65535
/* equivalent to a range sigma of 655.35mm */

#define VL53L0X_REG_GLOBAL_CONFIG_VCSEL_WIDTH          0x032
#define VL53L0X_REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_0   0x0B0
#define VL53L0X_REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_1   0x0B1
#define VL53L0X_REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_2   0x0B2
#define VL53L0X_REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_3   0x0B3
#define VL53L0X_REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_4   0x0B4
#define VL53L0X_REG_GLOBAL_CONFIG_SPAD_ENABLES_REF_5   0x0B5

#define VL53L0X_REG_GLOBAL_CONFIG_REF_EN_START_SELECT   0xB6
#define VL53L0X_REG_DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD 0x4E /* 0x14E */
#define VL53L0X_REG_DYNAMIC_SPAD_REF_EN_START_OFFSET    0x4F /* 0x14F */
#define VL53L0X_REG_POWER_MANAGEMENT_GO1_POWER_FORCE    0x80

/*
 * Speed of light in um per 1E-10 Seconds
 */

#define VL53L0X_SPEED_OF_LIGHT_IN_AIR 2997

#define VL53L0X_REG_VHV_CONFIG_PAD_SCL_SDA__EXTSUP_HV     0x0089

#define VL53L0X_REG_ALGO_PHASECAL_LIM                         0x0030 /* 0x130 */
#define VL53L0X_REG_ALGO_PHASECAL_CONFIG_TIMEOUT              0x0030

/** @} VL53L0X_DefineRegisters_group */

/** @} VL53L0X_DevSpecDefines_group */


#endif

/* _VL53L0X_DEVICE_H_ */




/*******************************************************************************
Copyright � 2016, STMicroelectronics International N.V.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
	* Redistributions of source code must retain the above copyright
	  notice, this list of conditions and the following disclaimer.
	* Redistributions in binary form must reproduce the above copyright
	  notice, this list of conditions and the following disclaimer in the
	  documentation and/or other materials provided with the distribution.
	* Neither the name of STMicroelectronics nor the
	  names of its contributors may be used to endorse or promote products
	  derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
NON-INFRINGEMENT OF INTELLECTUAL PROPERTY RIGHTS ARE DISCLAIMED.
IN NO EVENT SHALL STMICROELECTRONICS INTERNATIONAL N.V. BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*******************************************************************************/

/**
 * @file VL53L0X_def.h
 *
 * @brief Type definitions for VL53L0X API.
 *
 */


#ifndef _VL53L0X_DEF_H_
#define _VL53L0X_DEF_H_


#ifdef __cplusplus
extern "C" {
#endif

/** @defgroup VL53L0X_globaldefine_group VL53L0X Defines
 *	@brief	  VL53L0X Defines
 *	@{
 */


/** PAL SPECIFICATION major version */
#define VL53L0X10_SPECIFICATION_VER_MAJOR   1
/** PAL SPECIFICATION minor version */
#define VL53L0X10_SPECIFICATION_VER_MINOR   2
/** PAL SPECIFICATION sub version */
#define VL53L0X10_SPECIFICATION_VER_SUB	   7
/** PAL SPECIFICATION sub version */
#define VL53L0X10_SPECIFICATION_VER_REVISION 1440

/** VL53L0X PAL IMPLEMENTATION major version */
#define VL53L0X10_IMPLEMENTATION_VER_MAJOR	1
/** VL53L0X PAL IMPLEMENTATION minor version */
#define VL53L0X10_IMPLEMENTATION_VER_MINOR	0
/** VL53L0X PAL IMPLEMENTATION sub version */
#define VL53L0X10_IMPLEMENTATION_VER_SUB		9
/** VL53L0X PAL IMPLEMENTATION sub version */
#define VL53L0X10_IMPLEMENTATION_VER_REVISION	3673

/** PAL SPECIFICATION major version */
#define VL53L0X_SPECIFICATION_VER_MAJOR	 1
/** PAL SPECIFICATION minor version */
#define VL53L0X_SPECIFICATION_VER_MINOR	 2
/** PAL SPECIFICATION sub version */
#define VL53L0X_SPECIFICATION_VER_SUB	 7
/** PAL SPECIFICATION sub version */
#define VL53L0X_SPECIFICATION_VER_REVISION 1440

/** VL53L0X PAL IMPLEMENTATION major version */
#define VL53L0X_IMPLEMENTATION_VER_MAJOR	  1
/** VL53L0X PAL IMPLEMENTATION minor version */
#define VL53L0X_IMPLEMENTATION_VER_MINOR	  0
/** VL53L0X PAL IMPLEMENTATION sub version */
#define VL53L0X_IMPLEMENTATION_VER_SUB	  2
/** VL53L0X PAL IMPLEMENTATION sub version */
#define VL53L0X_IMPLEMENTATION_VER_REVISION	  4823
#define VL53L0X_DEFAULT_MAX_LOOP 2000
#define VL53L0X_MAX_STRING_LENGTH 32




/****************************************
 * PRIVATE define do not edit
 ****************************************/

/** @brief Defines the parameters of the Get Version Functions
 */
typedef struct {
	uint32_t	 revision; /*!< revision number */
	uint8_t		 major;	   /*!< major number */
	uint8_t		 minor;	   /*!< minor number */
	uint8_t		 build;	   /*!< build number */
} VL53L0X_Version_t;


/** @brief Defines the parameters of the Get Device Info Functions
 */
typedef struct {
	char Name[VL53L0X_MAX_STRING_LENGTH];
		/*!< Name of the Device e.g. Left_Distance */
	char Type[VL53L0X_MAX_STRING_LENGTH];
		/*!< Type of the Device e.g VL53L0X */
	char ProductId[VL53L0X_MAX_STRING_LENGTH];
		/*!< Product Identifier String	*/
	uint8_t ProductType;
		/*!< Product Type, VL53L0X = 1, VL53L1 = 2 */
	uint8_t ProductRevisionMajor;
		/*!< Product revision major */
	uint8_t ProductRevisionMinor;
		/*!< Product revision minor */
} VL53L0X_DeviceInfo_t;


/** @defgroup VL53L0X_define_Error_group Error and Warning code returned by API
 *	The following DEFINE are used to identify the PAL ERROR
 *	@{
 */

typedef int8_t VL53L0X_Error;

#define VL53L0X_ERROR_NONE		((VL53L0X_Error)	0)
#define VL53L0X_ERROR_CALIBRATION_WARNING	((VL53L0X_Error) -1)
	/*!< Warning invalid calibration data may be in used
		\a	VL53L0X_InitData()
		\a VL53L0X_GetOffsetCalibrationData
		\a VL53L0X_SetOffsetCalibrationData */
#define VL53L0X_ERROR_MIN_CLIPPED			((VL53L0X_Error) -2)
	/*!< Warning parameter passed was clipped to min before to be applied */

#define VL53L0X_ERROR_UNDEFINED				((VL53L0X_Error) -3)
	/*!< Unqualified error */
#define VL53L0X_ERROR_INVALID_PARAMS			((VL53L0X_Error) -4)
	/*!< Parameter passed is invalid or out of range */
#define VL53L0X_ERROR_NOT_SUPPORTED			((VL53L0X_Error) -5)
	/*!< Function is not supported in current mode or configuration */
#define VL53L0X_ERROR_RANGE_ERROR			((VL53L0X_Error) -6)
	/*!< Device report a ranging error interrupt status */
#define VL53L0X_ERROR_TIME_OUT				((VL53L0X_Error) -7)
	/*!< Aborted due to time out */
#define VL53L0X_ERROR_MODE_NOT_SUPPORTED			((VL53L0X_Error) -8)
	/*!< Asked mode is not supported by the device */
#define VL53L0X_ERROR_BUFFER_TOO_SMALL			((VL53L0X_Error) -9)
	/*!< ... */
#define VL53L0X_ERROR_GPIO_NOT_EXISTING			((VL53L0X_Error) -10)
	/*!< User tried to setup a non-existing GPIO pin */
#define VL53L0X_ERROR_GPIO_FUNCTIONALITY_NOT_SUPPORTED  ((VL53L0X_Error) -11)
	/*!< unsupported GPIO functionality */
#define VL53L0X_ERROR_INTERRUPT_NOT_CLEARED		((VL53L0X_Error) -12)
	/*!< Error during interrupt clear */
#define VL53L0X_ERROR_CONTROL_INTERFACE			((VL53L0X_Error) -20)
	/*!< error reported from IO functions */
#define VL53L0X_ERROR_INVALID_COMMAND			((VL53L0X_Error) -30)
	/*!< The command is not allowed in the current device state
	 *	(power down) */
#define VL53L0X_ERROR_DIVISION_BY_ZERO			((VL53L0X_Error) -40)
	/*!< In the function a division by zero occurs */
#define VL53L0X_ERROR_REF_SPAD_INIT			((VL53L0X_Error) -50)
	/*!< Error during reference SPAD initialization */
#define VL53L0X_ERROR_NOT_IMPLEMENTED			((VL53L0X_Error) -99)
	/*!< Tells requested functionality has not been implemented yet or
	 * not compatible with the device */
/** @} VL53L0X_define_Error_group */


/** @defgroup VL53L0X_define_DeviceModes_group Defines Device modes
 *	Defines all possible modes for the device
 *	@{
 */
typedef uint8_t VL53L0X_DeviceModes;

#define VL53L0X_DEVICEMODE_SINGLE_RANGING	((VL53L0X_DeviceModes)  0)
#define VL53L0X_DEVICEMODE_CONTINUOUS_RANGING	((VL53L0X_DeviceModes)  1)
#define VL53L0X_DEVICEMODE_SINGLE_HISTOGRAM	((VL53L0X_DeviceModes)  2)
#define VL53L0X_DEVICEMODE_CONTINUOUS_TIMED_RANGING ((VL53L0X_DeviceModes) 3)
#define VL53L0X_DEVICEMODE_SINGLE_ALS		((VL53L0X_DeviceModes) 10)
#define VL53L0X_DEVICEMODE_GPIO_DRIVE		((VL53L0X_DeviceModes) 20)
#define VL53L0X_DEVICEMODE_GPIO_OSC		((VL53L0X_DeviceModes) 21)
	/* ... Modes to be added depending on device */
/** @} VL53L0X_define_DeviceModes_group */



/** @defgroup VL53L0X_define_HistogramModes_group Defines Histogram modes
 *	Defines all possible Histogram modes for the device
 *	@{
 */
typedef uint8_t VL53L0X_HistogramModes;

#define VL53L0X_HISTOGRAMMODE_DISABLED		((VL53L0X_HistogramModes) 0)
	/*!< Histogram Disabled */
#define VL53L0X_HISTOGRAMMODE_REFERENCE_ONLY	((VL53L0X_HistogramModes) 1)
	/*!< Histogram Reference array only */
#define VL53L0X_HISTOGRAMMODE_RETURN_ONLY	((VL53L0X_HistogramModes) 2)
	/*!< Histogram Return array only */
#define VL53L0X_HISTOGRAMMODE_BOTH		((VL53L0X_HistogramModes) 3)
	/*!< Histogram both Reference and Return Arrays */
	/* ... Modes to be added depending on device */
/** @} VL53L0X_define_HistogramModes_group */


/** @defgroup VL53L0X_define_PowerModes_group List of available Power Modes
 *	List of available Power Modes
 *	@{
 */

typedef uint8_t VL53L0X_PowerModes;

#define VL53L0X_POWERMODE_STANDBY_LEVEL1 ((VL53L0X_PowerModes) 0)
	/*!< Standby level 1 */
#define VL53L0X_POWERMODE_STANDBY_LEVEL2 ((VL53L0X_PowerModes) 1)
	/*!< Standby level 2 */
#define VL53L0X_POWERMODE_IDLE_LEVEL1	((VL53L0X_PowerModes) 2)
	/*!< Idle level 1 */
#define VL53L0X_POWERMODE_IDLE_LEVEL2	((VL53L0X_PowerModes) 3)
	/*!< Idle level 2 */

/** @} VL53L0X_define_PowerModes_group */


/** @brief Defines all parameters for the device
 */
typedef struct {
	VL53L0X_DeviceModes DeviceMode;
	/*!< Defines type of measurement to be done for the next measure */
	VL53L0X_HistogramModes HistogramMode;
	/*!< Defines type of histogram measurement to be done for the next
	 *	measure */
	uint32_t MeasurementTimingBudgetMicroSeconds;
	/*!< Defines the allowed total time for a single measurement */
	uint32_t InterMeasurementPeriodMilliSeconds;
	/*!< Defines time between two consecutive measurements (between two
	 *	measurement starts). If set to 0 means back-to-back mode */
	uint8_t XTalkCompensationEnable;
	/*!< Tells if Crosstalk compensation shall be enable or not	 */
	uint16_t XTalkCompensationRangeMilliMeter;
	/*!< CrossTalk compensation range in millimeter	 */
	FixPoint1616_t XTalkCompensationRateMegaCps;
	/*!< CrossTalk compensation rate in Mega counts per seconds.
	 *	Expressed in 16.16 fixed point format.	*/
	int32_t RangeOffsetMicroMeters;
	/*!< Range offset adjustment (mm).	*/

	uint8_t LimitChecksEnable[VL53L0X_CHECKENABLE_NUMBER_OF_CHECKS];
	/*!< This Array store all the Limit Check enable for this device. */
	uint8_t LimitChecksStatus[VL53L0X_CHECKENABLE_NUMBER_OF_CHECKS];
	/*!< This Array store all the Status of the check linked to last
	* measurement. */
	FixPoint1616_t LimitChecksValue[VL53L0X_CHECKENABLE_NUMBER_OF_CHECKS];
	/*!< This Array store all the Limit Check value for this device */

	uint8_t WrapAroundCheckEnable;
	/*!< Tells if Wrap Around Check shall be enable or not */
} VL53L0X_DeviceParameters_t;


/** @defgroup VL53L0X_define_State_group Defines the current status of the device
 *	Defines the current status of the device
 *	@{
 */

typedef uint8_t VL53L0X_State;

#define VL53L0X_STATE_POWERDOWN		 ((VL53L0X_State)  0)
	/*!< Device is in HW reset	*/
#define VL53L0X_STATE_WAIT_STATICINIT ((VL53L0X_State)  1)
	/*!< Device is initialized and wait for static initialization  */
#define VL53L0X_STATE_STANDBY		 ((VL53L0X_State)  2)
	/*!< Device is in Low power Standby mode   */
#define VL53L0X_STATE_IDLE			 ((VL53L0X_State)  3)
	/*!< Device has been initialized and ready to do measurements  */
#define VL53L0X_STATE_RUNNING		 ((VL53L0X_State)  4)
	/*!< Device is performing measurement */
#define VL53L0X_STATE_UNKNOWN		 ((VL53L0X_State)  98)
	/*!< Device is in unknown state and need to be rebooted	 */
#define VL53L0X_STATE_ERROR			 ((VL53L0X_State)  99)
	/*!< Device is in error state and need to be rebooted  */

/** @} VL53L0X_define_State_group */


/** @brief Structure containing the Dmax computation parameters and data
 */
typedef struct {
	int32_t AmbTuningWindowFactor_K;
		/*!<  internal algo tuning (*1000) */
	int32_t RetSignalAt0mm;
		/*!< intermediate dmax computation value caching */
} VL53L0X_DMaxData_t;

/**
 * @struct VL53L0X_RangeData_t
 * @brief Range measurement data.
 */
typedef struct {
	uint32_t TimeStamp;		/*!< 32-bit time stamp. */
	uint32_t MeasurementTimeUsec;
		/*!< Give the Measurement time needed by the device to do the
		 * measurement.*/


	uint16_t RangeMilliMeter;	/*!< range distance in millimeter. */

	uint16_t RangeDMaxMilliMeter;
		/*!< Tells what is the maximum detection distance of the device
		 * in current setup and environment conditions (Filled when
		 *	applicable) */

	FixPoint1616_t SignalRateRtnMegaCps;
		/*!< Return signal rate (MCPS)\n these is a 16.16 fix point
		 *	value, which is effectively a measure of target
		 *	 reflectance.*/
	FixPoint1616_t AmbientRateRtnMegaCps;
		/*!< Return ambient rate (MCPS)\n these is a 16.16 fix point
		 *	value, which is effectively a measure of the ambien
		 *	t light.*/

	uint16_t EffectiveSpadRtnCount;
		/*!< Return the effective SPAD count for the return signal.
		 *	To obtain Real value it should be divided by 256 */

	uint8_t ZoneId;
		/*!< Denotes which zone and range scheduler stage the range
		 *	data relates to. */
	uint8_t RangeFractionalPart;
		/*!< Fractional part of range distance. Final value is a
		 *	FixPoint168 value. */
	uint8_t RangeStatus;
		/*!< Range Status for the current measurement. This is device
		 *	dependent. Value = 0 means value is valid.
		 *	See \ref RangeStatusPage */
} VL53L0X_RangingMeasurementData_t;


#define VL53L0X_HISTOGRAM_BUFFER_SIZE 24

/**
 * @struct VL53L0X_HistogramData_t
 * @brief Histogram measurement data.
 */
typedef struct {
	/* Histogram Measurement data */
	uint32_t HistogramData[VL53L0X_HISTOGRAM_BUFFER_SIZE];
	/*!< Histogram data */
	uint8_t HistogramType; /*!< Indicate the types of histogram data :
	Return only, Reference only, both Return and Reference */
	uint8_t FirstBin; /*!< First Bin value */
	uint8_t BufferSize; /*!< Buffer Size - Set by the user.*/
	uint8_t NumberOfBins;
	/*!< Number of bins filled by the histogram measurement */

	VL53L0X_DeviceError ErrorStatus;
	/*!< Error status of the current measurement. \n
	see @a ::VL53L0X_DeviceError @a VL53L0X_GetStatusErrorString() */
} VL53L0X_HistogramMeasurementData_t;

#define VL53L0X_REF_SPAD_BUFFER_SIZE 6

/**
 * @struct VL53L0X_SpadData_t
 * @brief Spad Configuration Data.
 */
typedef struct {
	uint8_t RefSpadEnables[VL53L0X_REF_SPAD_BUFFER_SIZE];
	/*!< Reference Spad Enables */
	uint8_t RefGoodSpadMap[VL53L0X_REF_SPAD_BUFFER_SIZE];
	/*!< Reference Spad Good Spad Map */
} VL53L0X_SpadData_t;

typedef struct {
	FixPoint1616_t OscFrequencyMHz; /* Frequency used */

	uint16_t LastEncodedTimeout;
	/* last encoded Time out used for timing budget*/

	VL53L0X_GpioFunctionality Pin0GpioFunctionality;
	/* store the functionality of the GPIO: pin0 */

	uint32_t FinalRangeTimeoutMicroSecs;
	 /*!< Execution time of the final range*/
	uint8_t FinalRangeVcselPulsePeriod;
	 /*!< Vcsel pulse period (pll clocks) for the final range measurement*/
	uint32_t PreRangeTimeoutMicroSecs;
	 /*!< Execution time of the final range*/
	uint8_t PreRangeVcselPulsePeriod;
	 /*!< Vcsel pulse period (pll clocks) for the pre-range measurement*/

	uint16_t SigmaEstRefArray;
	 /*!< Reference array sigma value in 1/100th of [mm] e.g. 100 = 1mm */
	uint16_t SigmaEstEffPulseWidth;
	 /*!< Effective Pulse width for sigma estimate in 1/100th
	  * of ns e.g. 900 = 9.0ns */
	uint16_t SigmaEstEffAmbWidth;
	 /*!< Effective Ambient width for sigma estimate in 1/100th of ns
	  * e.g. 500 = 5.0ns */


	uint8_t ReadDataFromDeviceDone; /* Indicate if read from device has
	been done (==1) or not (==0) */
	uint8_t ModuleId; /* Module ID */
	uint8_t Revision; /* test Revision */
	char ProductId[VL53L0X_MAX_STRING_LENGTH];
		/* Product Identifier String  */
	uint8_t ReferenceSpadCount; /* used for ref spad management */
	uint8_t ReferenceSpadType;	/* used for ref spad management */
	uint8_t RefSpadsInitialised; /* reports if ref spads are initialised. */
	uint32_t PartUIDUpper; /*!< Unique Part ID Upper */
	uint32_t PartUIDLower; /*!< Unique Part ID Lower */
	FixPoint1616_t SignalRateMeasFixed400mm; /*!< Peek Signal rate
	at 400 mm*/

} VL53L0X_DeviceSpecificParameters_t;

/**
 * @struct VL53L0X_DevData_t
 *
 * @brief VL53L0X PAL device ST private data structure \n
 * End user should never access any of these field directly
 *
 * These must never access directly but only via macro
 */
typedef struct {
	VL53L0X_DMaxData_t DMaxData;
	/*!< Dmax Data */
	int32_t	 Part2PartOffsetNVMMicroMeter;
	/*!< backed up NVM value */
	int32_t	 Part2PartOffsetAdjustmentNVMMicroMeter;
	/*!< backed up NVM value representing additional offset adjustment */
	VL53L0X_DeviceParameters_t CurrentParameters;
	/*!< Current Device Parameter */
	VL53L0X_RangingMeasurementData_t LastRangeMeasure;
	/*!< Ranging Data */
	VL53L0X_HistogramMeasurementData_t LastHistogramMeasure;
	/*!< Histogram Data */
	VL53L0X_DeviceSpecificParameters_t DeviceSpecificParameters;
	/*!< Parameters specific to the device */
	VL53L0X_SpadData_t SpadData;
	/*!< Spad Data */
	uint8_t SequenceConfig;
	/*!< Internal value for the sequence config */
	uint8_t RangeFractionalEnable;
	/*!< Enable/Disable fractional part of ranging data */
	VL53L0X_State PalState;
	/*!< Current state of the PAL for this device */
	VL53L0X_PowerModes PowerMode;
	/*!< Current Power Mode	 */
	uint16_t SigmaEstRefArray;
	/*!< Reference array sigma value in 1/100th of [mm] e.g. 100 = 1mm */
	uint16_t SigmaEstEffPulseWidth;
	/*!< Effective Pulse width for sigma estimate in 1/100th
	* of ns e.g. 900 = 9.0ns */
	uint16_t SigmaEstEffAmbWidth;
	/*!< Effective Ambient width for sigma estimate in 1/100th of ns
	* e.g. 500 = 5.0ns */
	uint8_t StopVariable;
	/*!< StopVariable used during the stop sequence */
	uint16_t targetRefRate;
	/*!< Target Ambient Rate for Ref spad management */
	FixPoint1616_t SigmaEstimate;
	/*!< Sigma Estimate - based on ambient & VCSEL rates and
	* signal_total_events */
	FixPoint1616_t SignalEstimate;
	/*!< Signal Estimate - based on ambient & VCSEL rates and cross talk */
	FixPoint1616_t LastSignalRefMcps;
	/*!< Latest Signal ref in Mcps */
	uint8_t *pTuningSettingsPointer;
	/*!< Pointer for Tuning Settings table */
	uint8_t UseInternalTuningSettings;
	/*!< Indicate if we use	 Tuning Settings table */
	uint16_t LinearityCorrectiveGain;
	/*!< Linearity Corrective Gain value in x1000 */
	uint16_t DmaxCalRangeMilliMeter;
	/*!< Dmax Calibration Range millimeter */
	FixPoint1616_t DmaxCalSignalRateRtnMegaCps;
	/*!< Dmax Calibration Signal Rate Return MegaCps */

} VL53L0X_DevData_t;


/** @defgroup VL53L0X_define_InterruptPolarity_group Defines the Polarity
 * of the Interrupt
 *	Defines the Polarity of the Interrupt
 *	@{
 */
typedef uint8_t VL53L0X_InterruptPolarity;

#define VL53L0X_INTERRUPTPOLARITY_LOW	   ((VL53L0X_InterruptPolarity)	0)
/*!< Set active low polarity best setup for falling edge. */
#define VL53L0X_INTERRUPTPOLARITY_HIGH	   ((VL53L0X_InterruptPolarity)	1)
/*!< Set active high polarity best setup for rising edge. */

/** @} VL53L0X_define_InterruptPolarity_group */


/** @defgroup VL53L0X_define_VcselPeriod_group Vcsel Period Defines
 *	Defines the range measurement for which to access the vcsel period.
 *	@{
 */
typedef uint8_t VL53L0X_VcselPeriod;

#define VL53L0X_VCSEL_PERIOD_PRE_RANGE	((VL53L0X_VcselPeriod) 0)
/*!<Identifies the pre-range vcsel period. */
#define VL53L0X_VCSEL_PERIOD_FINAL_RANGE ((VL53L0X_VcselPeriod) 1)
/*!<Identifies the final range vcsel period. */

/** @} VL53L0X_define_VcselPeriod_group */

/** @defgroup VL53L0X_define_SchedulerSequence_group Defines the steps
 * carried out by the scheduler during a range measurement.
 *	@{
 *	Defines the states of all the steps in the scheduler
 *	i.e. enabled/disabled.
 */
typedef struct {
	uint8_t		 TccOn;	   /*!<Reports if Target Centre Check On  */
	uint8_t		 MsrcOn;	   /*!<Reports if MSRC On  */
	uint8_t		 DssOn;		   /*!<Reports if DSS On  */
	uint8_t		 PreRangeOn;   /*!<Reports if Pre-Range On	*/
	uint8_t		 FinalRangeOn; /*!<Reports if Final-Range On  */
} VL53L0X_SchedulerSequenceSteps_t;

/** @} VL53L0X_define_SchedulerSequence_group */

/** @defgroup VL53L0X_define_SequenceStepId_group Defines the Polarity
 *	of the Interrupt
 *	Defines the the sequence steps performed during ranging..
 *	@{
 */
typedef uint8_t VL53L0X_SequenceStepId;

#define	 VL53L0X_SEQUENCESTEP_TCC		 ((VL53L0X_VcselPeriod) 0)
/*!<Target CentreCheck identifier. */
#define	 VL53L0X_SEQUENCESTEP_DSS		 ((VL53L0X_VcselPeriod) 1)
/*!<Dynamic Spad Selection function Identifier. */
#define	 VL53L0X_SEQUENCESTEP_MSRC		 ((VL53L0X_VcselPeriod) 2)
/*!<Minimum Signal Rate Check function Identifier. */
#define	 VL53L0X_SEQUENCESTEP_PRE_RANGE	 ((VL53L0X_VcselPeriod) 3)
/*!<Pre-Range check Identifier. */
#define	 VL53L0X_SEQUENCESTEP_FINAL_RANGE ((VL53L0X_VcselPeriod) 4)
/*!<Final Range Check Identifier. */

#define	 VL53L0X_SEQUENCESTEP_NUMBER_OF_CHECKS			 5
/*!<Number of Sequence Step Managed by the API. */

/** @} VL53L0X_define_SequenceStepId_group */


/* MACRO Definitions */
/** @defgroup VL53L0X_define_GeneralMacro_group General Macro Defines
 *	General Macro Defines
 *	@{
 */

/* Defines */
#define VL53L0X_SETPARAMETERFIELD(Dev, field, value) \
	PALDevDataSet(Dev, CurrentParameters.field, value)

#define VL53L0X_GETPARAMETERFIELD(Dev, field, variable) \
	variable = PALDevDataGet(Dev, CurrentParameters).field


#define VL53L0X_SETARRAYPARAMETERFIELD(Dev, field, index, value) \
	PALDevDataSet(Dev, CurrentParameters.field[index], value)

#define VL53L0X_GETARRAYPARAMETERFIELD(Dev, field, index, variable) \
	variable = PALDevDataGet(Dev, CurrentParameters).field[index]


#define VL53L0X_SETDEVICESPECIFICPARAMETER(Dev, field, value) \
		PALDevDataSet(Dev, DeviceSpecificParameters.field, value)

#define VL53L0X_GETDEVICESPECIFICPARAMETER(Dev, field) \
		PALDevDataGet(Dev, DeviceSpecificParameters).field


#define VL53L0X_FIXPOINT1616TOFIXPOINT97(Value) \
	(uint16_t)((Value>>9)&0xFFFF)
#define VL53L0X_FIXPOINT97TOFIXPOINT1616(Value) \
	(FixPoint1616_t)(Value<<9)

#define VL53L0X_FIXPOINT1616TOFIXPOINT88(Value) \
	(uint16_t)((Value>>8)&0xFFFF)
#define VL53L0X_FIXPOINT88TOFIXPOINT1616(Value) \
	(FixPoint1616_t)(Value<<8)

#define VL53L0X_FIXPOINT1616TOFIXPOINT412(Value) \
	(uint16_t)((Value>>4)&0xFFFF)
#define VL53L0X_FIXPOINT412TOFIXPOINT1616(Value) \
	(FixPoint1616_t)(Value<<4)

#define VL53L0X_FIXPOINT1616TOFIXPOINT313(Value) \
	(uint16_t)((Value>>3)&0xFFFF)
#define VL53L0X_FIXPOINT313TOFIXPOINT1616(Value) \
	(FixPoint1616_t)(Value<<3)

#define VL53L0X_FIXPOINT1616TOFIXPOINT08(Value) \
	(uint8_t)((Value>>8)&0x00FF)
#define VL53L0X_FIXPOINT08TOFIXPOINT1616(Value) \
	(FixPoint1616_t)(Value<<8)

#define VL53L0X_FIXPOINT1616TOFIXPOINT53(Value) \
	(uint8_t)((Value>>13)&0x00FF)
#define VL53L0X_FIXPOINT53TOFIXPOINT1616(Value) \
	(FixPoint1616_t)(Value<<13)

#define VL53L0X_FIXPOINT1616TOFIXPOINT102(Value) \
	(uint16_t)((Value>>14)&0x0FFF)
#define VL53L0X_FIXPOINT102TOFIXPOINT1616(Value) \
	(FixPoint1616_t)(Value<<12)

#define VL53L0X_MAKEUINT16(lsb, msb) (uint16_t)((((uint16_t)msb)<<8) + \
		(uint16_t)lsb)

/** @} VL53L0X_define_GeneralMacro_group */

/** @} VL53L0X_globaldefine_group */







#ifdef __cplusplus
}
#endif


#endif /* _VL53L0X_DEF_H_ */


#ifndef __VL53L0X_PLATFORM_H
#define __VL53L0X_PLATFORM_H



//vl53l0x�豸I2C��Ϣ
typedef struct {
    VL53L0X_DevData_t Data;              /*!< embed ST Ewok Dev  data as "Data"*/
    /*!< user specific field */
    uint8_t   I2cDevAddr;                /*!< i2c device address user specific field */
    uint8_t   comms_type;                /*!< Type of comms : VL53L0X_COMMS_I2C or VL53L0X_COMMS_SPI */
    uint16_t  comms_speed_khz;           /*!< Comms speed [kHz] : typically 400kHz for I2C           */

} VL53L0X_Dev_t;


typedef VL53L0X_Dev_t* VL53L0X_DEV;

#define VL53L0X_MAX_I2C_XFER_SIZE  64 //����I2Cд������ֽ���
#define PALDevDataGet(Dev, field) (Dev->Data.field)
#define PALDevDataSet(Dev, field, data) (Dev->Data.field)=(data)


VL53L0X_Error VL53L0X_WriteMulti(VL53L0X_DEV Dev, uint8_t index, uint8_t *pdata,uint32_t count);
VL53L0X_Error VL53L0X_ReadMulti(VL53L0X_DEV Dev, uint8_t index, uint8_t *pdata,uint32_t count);
VL53L0X_Error VL53L0X_WrByte(VL53L0X_DEV Dev, uint8_t index, uint8_t data);
VL53L0X_Error VL53L0X_WrWord(VL53L0X_DEV Dev, uint8_t index, uint16_t data);
VL53L0X_Error VL53L0X_WrDWord(VL53L0X_DEV Dev, uint8_t index, uint32_t data);
VL53L0X_Error VL53L0X_UpdateByte(VL53L0X_DEV Dev, uint8_t index, uint8_t AndData, uint8_t OrData);
VL53L0X_Error VL53L0X_RdByte(VL53L0X_DEV Dev, uint8_t index, uint8_t *data);
VL53L0X_Error VL53L0X_RdWord(VL53L0X_DEV Dev, uint8_t index, uint16_t *data);
VL53L0X_Error VL53L0X_RdDWord(VL53L0X_DEV Dev, uint8_t index, uint32_t *data);
VL53L0X_Error VL53L0X_PollingDelay(VL53L0X_DEV Dev);


#endif 



/*******************************************************************************
 Copyright � 2016, STMicroelectronics International N.V.
 All rights reserved.

 Redistribution and use in source and binary forms, with or without
 modification, are permitted provided that the following conditions are met:
 * Redistributions of source code must retain the above copyright
 notice, this list of conditions and the following disclaimer.
 * Redistributions in binary form must reproduce the above copyright
 notice, this list of conditions and the following disclaimer in the
 documentation and/or other materials provided with the distribution.
 * Neither the name of STMicroelectronics nor the
 names of its contributors may be used to endorse or promote products
 derived from this software without specific prior written permission.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
 ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
 NON-INFRINGEMENT OF INTELLECTUAL PROPERTY RIGHTS ARE DISCLAIMED.
 IN NO EVENT SHALL STMICROELECTRONICS INTERNATIONAL N.V. BE LIABLE FOR ANY
 DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
 ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *****************************************************************************/

#ifndef _VL53L0X_API_H_
#define _VL53L0X_API_H_




#ifdef __cplusplus
extern "C"
{
#endif

#ifdef _MSC_VER
#   ifdef VL53L0X_API_EXPORTS
#       define VL53L0X_API  __declspec(dllexport)
#   else
#       define VL53L0X_API
#   endif
#else
#   define VL53L0X_API
#endif

/** @defgroup VL53L0X_cut11_group VL53L0X cut1.1 Function Definition
 *  @brief    VL53L0X cut1.1 Function Definition
 *  @{
 */

/** @defgroup VL53L0X_general_group VL53L0X General Functions
 *  @brief    General functions and definitions
 *  @{
 */

/**
 * @brief Return the VL53L0X PAL Implementation Version
 *
 * @note This function doesn't access to the device
 *
 * @param   pVersion              Pointer to current PAL Implementation Version
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetVersion(VL53L0X_Version_t *pVersion);

/**
 * @brief Return the PAL Specification Version used for the current
 * implementation.
 *
 * @note This function doesn't access to the device
 *
 * @param   pPalSpecVersion       Pointer to current PAL Specification Version
 * @return  VL53L0X_ERROR_NONE        Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetPalSpecVersion(
	VL53L0X_Version_t *pPalSpecVersion);

/**
 * @brief Reads the Product Revision for a for given Device
 * This function can be used to distinguish cut1.0 from cut1.1.
 *
 * @note This function Access to the device
 *
 * @param   Dev                 Device Handle
 * @param   pProductRevisionMajor  Pointer to Product Revision Major
 * for a given Device
 * @param   pProductRevisionMinor  Pointer to Product Revision Minor
 * for a given Device
 * @return  VL53L0X_ERROR_NONE      Success
 * @return  "Other error code"  See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetProductRevision(VL53L0X_DEV Dev,
	uint8_t *pProductRevisionMajor, uint8_t *pProductRevisionMinor);

/**
 * @brief Reads the Device information for given Device
 *
 * @note This function Access to the device
 *
 * @param   Dev                 Device Handle
 * @param   pVL53L0X_DeviceInfo  Pointer to current device info for a given
 *  Device
 * @return  VL53L0X_ERROR_NONE   Success
 * @return  "Other error code"  See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetDeviceInfo(VL53L0X_DEV Dev,
	VL53L0X_DeviceInfo_t *pVL53L0X_DeviceInfo);

/**
 * @brief Read current status of the error register for the selected device
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   pDeviceErrorStatus    Pointer to current error code of the device
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetDeviceErrorStatus(VL53L0X_DEV Dev,
	VL53L0X_DeviceError *pDeviceErrorStatus);

/**
 * @brief Human readable Range Status string for a given RangeStatus
 *
 * @note This function doesn't access to the device
 *
 * @param   RangeStatus         The RangeStatus code as stored on
 * @a VL53L0X_RangingMeasurementData_t
 * @param   pRangeStatusString  The returned RangeStatus string.
 * @return  VL53L0X_ERROR_NONE   Success
 * @return  "Other error code"  See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetRangeStatusString(uint8_t RangeStatus,
	char *pRangeStatusString);

/**
 * @brief Human readable error string for a given Error Code
 *
 * @note This function doesn't access to the device
 *
 * @param   ErrorCode           The error code as stored on ::VL53L0X_DeviceError
 * @param   pDeviceErrorString  The error string corresponding to the ErrorCode
 * @return  VL53L0X_ERROR_NONE   Success
 * @return  "Other error code"  See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetDeviceErrorString(
	VL53L0X_DeviceError ErrorCode, char *pDeviceErrorString);

/**
 * @brief Human readable error string for current PAL error status
 *
 * @note This function doesn't access to the device
 *
 * @param   PalErrorCode       The error code as stored on @a VL53L0X_Error
 * @param   pPalErrorString    The error string corresponding to the
 * PalErrorCode
 * @return  VL53L0X_ERROR_NONE  Success
 * @return  "Other error code" See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetPalErrorString(VL53L0X_Error PalErrorCode,
	char *pPalErrorString);

/**
 * @brief Human readable PAL State string
 *
 * @note This function doesn't access to the device
 *
 * @param   PalStateCode          The State code as stored on @a VL53L0X_State
 * @param   pPalStateString       The State string corresponding to the
 * PalStateCode
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetPalStateString(VL53L0X_State PalStateCode,
	char *pPalStateString);

/**
 * @brief Reads the internal state of the PAL for a given Device
 *
 * @note This function doesn't access to the device
 *
 * @param   Dev                   Device Handle
 * @param   pPalState             Pointer to current state of the PAL for a
 * given Device
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetPalState(VL53L0X_DEV Dev,
	VL53L0X_State *pPalState);

/**
 * @brief Set the power mode for a given Device
 * The power mode can be Standby or Idle. Different level of both Standby and
 * Idle can exists.
 * This function should not be used when device is in Ranging state.
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   PowerMode             The value of the power mode to set.
 * see ::VL53L0X_PowerModes
 *                                Valid values are:
 *                                VL53L0X_POWERMODE_STANDBY_LEVEL1,
 *                                VL53L0X_POWERMODE_IDLE_LEVEL1
 * @return  VL53L0X_ERROR_NONE                  Success
 * @return  VL53L0X_ERROR_MODE_NOT_SUPPORTED    This error occurs when PowerMode
 * is not in the supported list
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetPowerMode(VL53L0X_DEV Dev,
	VL53L0X_PowerModes PowerMode);

/**
 * @brief Get the power mode for a given Device
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   pPowerMode            Pointer to the current value of the power
 * mode. see ::VL53L0X_PowerModes
 *                                Valid values are:
 *                                VL53L0X_POWERMODE_STANDBY_LEVEL1,
 *                                VL53L0X_POWERMODE_IDLE_LEVEL1
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetPowerMode(VL53L0X_DEV Dev,
	VL53L0X_PowerModes *pPowerMode);

/**
 * Set or over-hide part to part calibration offset
 * \sa VL53L0X_DataInit()   VL53L0X_GetOffsetCalibrationDataMicroMeter()
 *
 * @note This function Access to the device
 *
 * @param   Dev                                Device Handle
 * @param   OffsetCalibrationDataMicroMeter    Offset (microns)
 * @return  VL53L0X_ERROR_NONE                  Success
 * @return  "Other error code"                 See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetOffsetCalibrationDataMicroMeter(
	VL53L0X_DEV Dev, int32_t OffsetCalibrationDataMicroMeter);

/**
 * @brief Get part to part calibration offset
 *
 * @par Function Description
 * Should only be used after a successful call to @a VL53L0X_DataInit to backup
 * device NVM value
 *
 * @note This function Access to the device
 *
 * @param   Dev                                Device Handle
 * @param   pOffsetCalibrationDataMicroMeter   Return part to part
 * calibration offset from device (microns)
 * @return  VL53L0X_ERROR_NONE                  Success
 * @return  "Other error code"                 See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetOffsetCalibrationDataMicroMeter(
	VL53L0X_DEV Dev, int32_t *pOffsetCalibrationDataMicroMeter);

/**
 * Set the linearity corrective gain
 *
 * @note This function Access to the device
 *
 * @param   Dev                                Device Handle
 * @param   LinearityCorrectiveGain            Linearity corrective
 * gain in x1000
 * if value is 1000 then no modification is applied.
 * @return  VL53L0X_ERROR_NONE                  Success
 * @return  "Other error code"                 See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetLinearityCorrectiveGain(VL53L0X_DEV Dev,
	int16_t LinearityCorrectiveGain);

/**
 * @brief Get the linearity corrective gain
 *
 * @par Function Description
 * Should only be used after a successful call to @a VL53L0X_DataInit to backup
 * device NVM value
 *
 * @note This function Access to the device
 *
 * @param   Dev                                Device Handle
 * @param   pLinearityCorrectiveGain           Pointer to the linearity
 * corrective gain in x1000
 * if value is 1000 then no modification is applied.
 * @return  VL53L0X_ERROR_NONE                  Success
 * @return  "Other error code"                 See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetLinearityCorrectiveGain(VL53L0X_DEV Dev,
	uint16_t *pLinearityCorrectiveGain);

/**
 * Set Group parameter Hold state
 *
 * @par Function Description
 * Set or remove device internal group parameter hold
 *
 * @note This function is not Implemented
 *
 * @param   Dev      Device Handle
 * @param   GroupParamHold   Group parameter Hold state to be set (on/off)
 * @return  VL53L0X_ERROR_NOT_IMPLEMENTED        Not implemented
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetGroupParamHold(VL53L0X_DEV Dev,
	uint8_t GroupParamHold);

/**
 * @brief Get the maximal distance for actual setup
 * @par Function Description
 * Device must be initialized through @a VL53L0X_SetParameters() prior calling
 * this function.
 *
 * Any range value more than the value returned is to be considered as
 * "no target detected" or
 * "no target in detectable range"\n
 * @warning The maximal distance depends on the setup
 *
 * @note This function is not Implemented
 *
 * @param   Dev      Device Handle
 * @param   pUpperLimitMilliMeter   The maximal range limit for actual setup
 * (in millimeter)
 * @return  VL53L0X_ERROR_NOT_IMPLEMENTED        Not implemented
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetUpperLimitMilliMeter(VL53L0X_DEV Dev,
	uint16_t *pUpperLimitMilliMeter);


/**
 * @brief Get the Total Signal Rate
 * @par Function Description
 * This function will return the Total Signal Rate after a good ranging is done.
 *
 * @note This function access to Device
 *
 * @param   Dev      Device Handle
 * @param   pTotalSignalRate   Total Signal Rate value in Mega count per second
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_Error VL53L0X_GetTotalSignalRate(VL53L0X_DEV Dev,
	FixPoint1616_t *pTotalSignalRate);

/** @} VL53L0X_general_group */

/** @defgroup VL53L0X_init_group VL53L0X Init Functions
 *  @brief    VL53L0X Init Functions
 *  @{
 */

/**
 * @brief Set new device address
 *
 * After completion the device will answer to the new address programmed.
 * This function should be called when several devices are used in parallel
 * before start programming the sensor.
 * When a single device us used, there is no need to call this function.
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   DeviceAddress         The new Device address
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetDeviceAddress(VL53L0X_DEV Dev,
	uint8_t DeviceAddress);

/**
 *
 * @brief One time device initialization
 *
 * To be called once and only once after device is brought out of reset
 * (Chip enable) and booted see @a VL53L0X_WaitDeviceBooted()
 *
 * @par Function Description
 * When not used after a fresh device "power up" or reset, it may return
 * @a #VL53L0X_ERROR_CALIBRATION_WARNING meaning wrong calibration data
 * may have been fetched from device that can result in ranging offset error\n
 * If application cannot execute device reset or need to run VL53L0X_DataInit
 * multiple time then it  must ensure proper offset calibration saving and
 * restore on its own by using @a VL53L0X_GetOffsetCalibrationData() on first
 * power up and then @a VL53L0X_SetOffsetCalibrationData() in all subsequent init
 * This function will change the VL53L0X_State from VL53L0X_STATE_POWERDOWN to
 * VL53L0X_STATE_WAIT_STATICINIT.
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_DataInit(VL53L0X_DEV Dev);

/**
 * @brief Set the tuning settings pointer
 *
 * This function is used to specify the Tuning settings buffer to be used
 * for a given device. The buffer contains all the necessary data to permit
 * the API to write tuning settings.
 * This function permit to force the usage of either external or internal
 * tuning settings.
 *
 * @note This function Access to the device
 *
 * @param   Dev                             Device Handle
 * @param   pTuningSettingBuffer            Pointer to tuning settings buffer.
 * @param   UseInternalTuningSettings       Use internal tuning settings value.
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetTuningSettingBuffer(VL53L0X_DEV Dev,
	uint8_t *pTuningSettingBuffer, uint8_t UseInternalTuningSettings);

/**
 * @brief Get the tuning settings pointer and the internal external switch
 * value.
 *
 * This function is used to get the Tuning settings buffer pointer and the
 * value.
 * of the switch to select either external or internal tuning settings.
 *
 * @note This function Access to the device
 *
 * @param   Dev                        Device Handle
 * @param   ppTuningSettingBuffer      Pointer to tuning settings buffer.
 * @param   pUseInternalTuningSettings Pointer to store Use internal tuning
 *                                     settings value.
 * @return  VL53L0X_ERROR_NONE          Success
 * @return  "Other error code"         See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetTuningSettingBuffer(VL53L0X_DEV Dev,
	uint8_t **ppTuningSettingBuffer, uint8_t *pUseInternalTuningSettings);

/**
 * @brief Do basic device init (and eventually patch loading)
 * This function will change the VL53L0X_State from
 * VL53L0X_STATE_WAIT_STATICINIT to VL53L0X_STATE_IDLE.
 * In this stage all default setting will be applied.
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_StaticInit(VL53L0X_DEV Dev);

/**
 * @brief Wait for device booted after chip enable (hardware standby)
 * This function can be run only when VL53L0X_State is VL53L0X_STATE_POWERDOWN.
 *
 * @note This function is not Implemented
 *
 * @param   Dev      Device Handle
 * @return  VL53L0X_ERROR_NOT_IMPLEMENTED Not implemented
 *
 */
VL53L0X_API VL53L0X_Error VL53L0X_WaitDeviceBooted(VL53L0X_DEV Dev);

/**
 * @brief Do an hard reset or soft reset (depending on implementation) of the
 * device \nAfter call of this function, device must be in same state as right
 * after a power-up sequence.This function will change the VL53L0X_State to
 * VL53L0X_STATE_POWERDOWN.
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_ResetDevice(VL53L0X_DEV Dev);

/** @} VL53L0X_init_group */

/** @defgroup VL53L0X_parameters_group VL53L0X Parameters Functions
 *  @brief    Functions used to prepare and setup the device
 *  @{
 */

/**
 * @brief  Prepare device for operation
 * @par Function Description
 * Update device with provided parameters
 * @li Then start ranging operation.
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   pDeviceParameters     Pointer to store current device parameters.
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetDeviceParameters(VL53L0X_DEV Dev,
	const VL53L0X_DeviceParameters_t *pDeviceParameters);

/**
 * @brief  Retrieve current device parameters
 * @par Function Description
 * Get actual parameters of the device
 * @li Then start ranging operation.
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   pDeviceParameters     Pointer to store current device parameters.
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetDeviceParameters(VL53L0X_DEV Dev,
	VL53L0X_DeviceParameters_t *pDeviceParameters);

/**
 * @brief  Set a new device mode
 * @par Function Description
 * Set device to a new mode (ranging, histogram ...)
 *
 * @note This function doesn't Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   DeviceMode            New device mode to apply
 *                                Valid values are:
 *                                VL53L0X_DEVICEMODE_SINGLE_RANGING
 *                                VL53L0X_DEVICEMODE_CONTINUOUS_RANGING
 *                                VL53L0X_DEVICEMODE_CONTINUOUS_TIMED_RANGING
 *                                VL53L0X_DEVICEMODE_SINGLE_HISTOGRAM
 *                                VL53L0X_HISTOGRAMMODE_REFERENCE_ONLY
 *                                VL53L0X_HISTOGRAMMODE_RETURN_ONLY
 *                                VL53L0X_HISTOGRAMMODE_BOTH
 *
 *
 * @return  VL53L0X_ERROR_NONE               Success
 * @return  VL53L0X_ERROR_MODE_NOT_SUPPORTED This error occurs when DeviceMode is
 *                                          not in the supported list
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetDeviceMode(VL53L0X_DEV Dev,
	VL53L0X_DeviceModes DeviceMode);

/**
 * @brief  Get current new device mode
 * @par Function Description
 * Get actual mode of the device(ranging, histogram ...)
 *
 * @note This function doesn't Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   pDeviceMode           Pointer to current apply mode value
 *                                Valid values are:
 *                                VL53L0X_DEVICEMODE_SINGLE_RANGING
 *                                VL53L0X_DEVICEMODE_CONTINUOUS_RANGING
 *                                VL53L0X_DEVICEMODE_CONTINUOUS_TIMED_RANGING
 *                                VL53L0X_DEVICEMODE_SINGLE_HISTOGRAM
 *                                VL53L0X_HISTOGRAMMODE_REFERENCE_ONLY
 *                                VL53L0X_HISTOGRAMMODE_RETURN_ONLY
 *                                VL53L0X_HISTOGRAMMODE_BOTH
 *
 * @return  VL53L0X_ERROR_NONE                   Success
 * @return  VL53L0X_ERROR_MODE_NOT_SUPPORTED     This error occurs when
 * DeviceMode is not in the supported list
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetDeviceMode(VL53L0X_DEV Dev,
	VL53L0X_DeviceModes *pDeviceMode);

/**
 * @brief  Sets the resolution of range measurements.
 * @par Function Description
 * Set resolution of range measurements to either 0.25mm if
 * fraction enabled or 1mm if not enabled.
 *
 * @note This function Accesses the device
 *
 * @param   Dev               Device Handle
 * @param   Enable            Enable high resolution
 *
 * @return  VL53L0X_ERROR_NONE               Success
 * @return  "Other error code"              See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetRangeFractionEnable(VL53L0X_DEV Dev,
	uint8_t Enable);

/**
 * @brief  Gets the fraction enable parameter indicating the resolution of
 * range measurements.
 *
 * @par Function Description
 * Gets the fraction enable state, which translates to the resolution of
 * range measurements as follows :Enabled:=0.25mm resolution,
 * Not Enabled:=1mm resolution.
 *
 * @note This function Accesses the device
 *
 * @param   Dev               Device Handle
 * @param   pEnable           Output Parameter reporting the fraction enable state.
 *
 * @return  VL53L0X_ERROR_NONE                   Success
 * @return  "Other error code"                  See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetFractionEnable(VL53L0X_DEV Dev,
	uint8_t *pEnable);

/**
 * @brief  Set a new Histogram mode
 * @par Function Description
 * Set device to a new Histogram mode
 *
 * @note This function doesn't Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   HistogramMode         New device mode to apply
 *                                Valid values are:
 *                                VL53L0X_HISTOGRAMMODE_DISABLED
 *                                VL53L0X_DEVICEMODE_SINGLE_HISTOGRAM
 *                                VL53L0X_HISTOGRAMMODE_REFERENCE_ONLY
 *                                VL53L0X_HISTOGRAMMODE_RETURN_ONLY
 *                                VL53L0X_HISTOGRAMMODE_BOTH
 *
 * @return  VL53L0X_ERROR_NONE                   Success
 * @return  VL53L0X_ERROR_MODE_NOT_SUPPORTED     This error occurs when
 * HistogramMode is not in the supported list
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetHistogramMode(VL53L0X_DEV Dev,
	VL53L0X_HistogramModes HistogramMode);

/**
 * @brief  Get current new device mode
 * @par Function Description
 * Get current Histogram mode of a Device
 *
 * @note This function doesn't Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   pHistogramMode        Pointer to current Histogram Mode value
 *                                Valid values are:
 *                                VL53L0X_HISTOGRAMMODE_DISABLED
 *                                VL53L0X_DEVICEMODE_SINGLE_HISTOGRAM
 *                                VL53L0X_HISTOGRAMMODE_REFERENCE_ONLY
 *                                VL53L0X_HISTOGRAMMODE_RETURN_ONLY
 *                                VL53L0X_HISTOGRAMMODE_BOTH
 * @return  VL53L0X_ERROR_NONE     Success
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetHistogramMode(VL53L0X_DEV Dev,
	VL53L0X_HistogramModes *pHistogramMode);

/**
 * @brief Set Ranging Timing Budget in microseconds
 *
 * @par Function Description
 * Defines the maximum time allowed by the user to the device to run a
 * full ranging sequence for the current mode (ranging, histogram, ASL ...)
 *
 * @note This function Access to the device
 *
 * @param   Dev                                Device Handle
 * @param MeasurementTimingBudgetMicroSeconds  Max measurement time in
 * microseconds.
 *                                   Valid values are:
 *                                   >= 17000 microsecs when wraparound enabled
 *                                   >= 12000 microsecs when wraparound disabled
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS   This error is returned if
 MeasurementTimingBudgetMicroSeconds out of range
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetMeasurementTimingBudgetMicroSeconds(
	VL53L0X_DEV Dev, uint32_t MeasurementTimingBudgetMicroSeconds);

/**
 * @brief Get Ranging Timing Budget in microseconds
 *
 * @par Function Description
 * Returns the programmed the maximum time allowed by the user to the
 * device to run a full ranging sequence for the current mode
 * (ranging, histogram, ASL ...)
 *
 * @note This function Access to the device
 *
 * @param   Dev                                    Device Handle
 * @param   pMeasurementTimingBudgetMicroSeconds   Max measurement time in
 * microseconds.
 *                                   Valid values are:
 *                                   >= 17000 microsecs when wraparound enabled
 *                                   >= 12000 microsecs when wraparound disabled
 * @return  VL53L0X_ERROR_NONE                      Success
 * @return  "Other error code"                     See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetMeasurementTimingBudgetMicroSeconds(
	VL53L0X_DEV Dev, uint32_t *pMeasurementTimingBudgetMicroSeconds);

/**
 * @brief Gets the VCSEL pulse period.
 *
 * @par Function Description
 * This function retrieves the VCSEL pulse period for the given period type.
 *
 * @note This function Accesses the device
 *
 * @param   Dev                      Device Handle
 * @param   VcselPeriodType          VCSEL period identifier (pre-range|final).
 * @param   pVCSELPulsePeriod        Pointer to VCSEL period value.
 * @return  VL53L0X_ERROR_NONE        Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS  Error VcselPeriodType parameter not
 *                                       supported.
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetVcselPulsePeriod(VL53L0X_DEV Dev,
	VL53L0X_VcselPeriod VcselPeriodType, uint8_t *pVCSELPulsePeriod);

/**
 * @brief Sets the VCSEL pulse period.
 *
 * @par Function Description
 * This function retrieves the VCSEL pulse period for the given period type.
 *
 * @note This function Accesses the device
 *
 * @param   Dev                       Device Handle
 * @param   VcselPeriodType	      VCSEL period identifier (pre-range|final).
 * @param   VCSELPulsePeriod          VCSEL period value
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS  Error VcselPeriodType parameter not
 *                                       supported.
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetVcselPulsePeriod(VL53L0X_DEV Dev,
	VL53L0X_VcselPeriod VcselPeriodType, uint8_t VCSELPulsePeriod);

/**
 * @brief Sets the (on/off) state of a requested sequence step.
 *
 * @par Function Description
 * This function enables/disables a requested sequence step.
 *
 * @note This function Accesses the device
 *
 * @param   Dev                          Device Handle
 * @param   SequenceStepId	         Sequence step identifier.
 * @param   SequenceStepEnabled          Demanded state {0=Off,1=On}
 *                                       is enabled.
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS  Error SequenceStepId parameter not
 *                                       supported.
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetSequenceStepEnable(VL53L0X_DEV Dev,
	VL53L0X_SequenceStepId SequenceStepId, uint8_t SequenceStepEnabled);

/**
 * @brief Gets the (on/off) state of a requested sequence step.
 *
 * @par Function Description
 * This function retrieves the state of a requested sequence step, i.e. on/off.
 *
 * @note This function Accesses the device
 *
 * @param   Dev                    Device Handle
 * @param   SequenceStepId         Sequence step identifier.
 * @param   pSequenceStepEnabled   Out parameter reporting if the sequence step
 *                                 is enabled {0=Off,1=On}.
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS  Error SequenceStepId parameter not
 *                                       supported.
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetSequenceStepEnable(VL53L0X_DEV Dev,
	VL53L0X_SequenceStepId SequenceStepId, uint8_t *pSequenceStepEnabled);

/**
 * @brief Gets the (on/off) state of all sequence steps.
 *
 * @par Function Description
 * This function retrieves the state of all sequence step in the scheduler.
 *
 * @note This function Accesses the device
 *
 * @param   Dev                          Device Handle
 * @param   pSchedulerSequenceSteps      Pointer to struct containing result.
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetSequenceStepEnables(VL53L0X_DEV Dev,
	VL53L0X_SchedulerSequenceSteps_t *pSchedulerSequenceSteps);

/**
 * @brief Sets the timeout of a requested sequence step.
 *
 * @par Function Description
 * This function sets the timeout of a requested sequence step.
 *
 * @note This function Accesses the device
 *
 * @param   Dev                          Device Handle
 * @param   SequenceStepId               Sequence step identifier.
 * @param   TimeOutMilliSecs             Demanded timeout
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS  Error SequenceStepId parameter not
 *                                       supported.
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetSequenceStepTimeout(VL53L0X_DEV Dev,
	VL53L0X_SequenceStepId SequenceStepId, FixPoint1616_t TimeOutMilliSecs);

/**
 * @brief Gets the timeout of a requested sequence step.
 *
 * @par Function Description
 * This function retrieves the timeout of a requested sequence step.
 *
 * @note This function Accesses the device
 *
 * @param   Dev                          Device Handle
 * @param   SequenceStepId               Sequence step identifier.
 * @param   pTimeOutMilliSecs            Timeout value.
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS  Error SequenceStepId parameter not
 *                                       supported.
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetSequenceStepTimeout(VL53L0X_DEV Dev,
	VL53L0X_SequenceStepId SequenceStepId,
	FixPoint1616_t *pTimeOutMilliSecs);

/**
 * @brief Gets number of sequence steps managed by the API.
 *
 * @par Function Description
 * This function retrieves the number of sequence steps currently managed
 * by the API
 *
 * @note This function Accesses the device
 *
 * @param   Dev                          Device Handle
 * @param   pNumberOfSequenceSteps       Out parameter reporting the number of
 *                                       sequence steps.
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetNumberOfSequenceSteps(VL53L0X_DEV Dev,
	uint8_t *pNumberOfSequenceSteps);

/**
 * @brief Gets the name of a given sequence step.
 *
 * @par Function Description
 * This function retrieves the name of sequence steps corresponding to
 * SequenceStepId.
 *
 * @note This function doesn't Accesses the device
 *
 * @param   SequenceStepId               Sequence step identifier.
 * @param   pSequenceStepsString         Pointer to Info string
 *
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetSequenceStepsInfo(
	VL53L0X_SequenceStepId SequenceStepId, char *pSequenceStepsString);

/**
 * Program continuous mode Inter-Measurement period in milliseconds
 *
 * @par Function Description
 * When trying to set too short time return  INVALID_PARAMS minimal value
 *
 * @note This function Access to the device
 *
 * @param   Dev                                  Device Handle
 * @param   InterMeasurementPeriodMilliSeconds   Inter-Measurement Period in ms.
 * @return  VL53L0X_ERROR_NONE                    Success
 * @return  "Other error code"                   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetInterMeasurementPeriodMilliSeconds(
	VL53L0X_DEV Dev, uint32_t InterMeasurementPeriodMilliSeconds);

/**
 * Get continuous mode Inter-Measurement period in milliseconds
 *
 * @par Function Description
 * When trying to set too short time return  INVALID_PARAMS minimal value
 *
 * @note This function Access to the device
 *
 * @param   Dev                                  Device Handle
 * @param   pInterMeasurementPeriodMilliSeconds  Pointer to programmed
 *  Inter-Measurement Period in milliseconds.
 * @return  VL53L0X_ERROR_NONE                    Success
 * @return  "Other error code"                   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetInterMeasurementPeriodMilliSeconds(
	VL53L0X_DEV Dev, uint32_t *pInterMeasurementPeriodMilliSeconds);

/**
 * @brief Enable/Disable Cross talk compensation feature
 *
 * @note This function is not Implemented.
 * Enable/Disable Cross Talk by set to zero the Cross Talk value
 * by using @a VL53L0X_SetXTalkCompensationRateMegaCps().
 *
 * @param   Dev                       Device Handle
 * @param   XTalkCompensationEnable   Cross talk compensation
 *  to be set 0=disabled else = enabled
 * @return  VL53L0X_ERROR_NOT_IMPLEMENTED   Not implemented
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetXTalkCompensationEnable(VL53L0X_DEV Dev,
	uint8_t XTalkCompensationEnable);

/**
 * @brief Get Cross talk compensation rate
 *
 * @note This function is not Implemented.
 * Enable/Disable Cross Talk by set to zero the Cross Talk value by
 * using @a VL53L0X_SetXTalkCompensationRateMegaCps().
 *
 * @param   Dev                        Device Handle
 * @param   pXTalkCompensationEnable   Pointer to the Cross talk compensation
 *  state 0=disabled or 1 = enabled
 * @return  VL53L0X_ERROR_NOT_IMPLEMENTED   Not implemented
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetXTalkCompensationEnable(VL53L0X_DEV Dev,
	uint8_t *pXTalkCompensationEnable);

/**
 * @brief Set Cross talk compensation rate
 *
 * @par Function Description
 * Set Cross talk compensation rate.
 *
 * @note This function Access to the device
 *
 * @param   Dev                            Device Handle
 * @param   XTalkCompensationRateMegaCps   Compensation rate in
 *  Mega counts per second (16.16 fix point) see datasheet for details
 * @return  VL53L0X_ERROR_NONE              Success
 * @return  "Other error code"             See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetXTalkCompensationRateMegaCps(VL53L0X_DEV Dev,
	FixPoint1616_t XTalkCompensationRateMegaCps);

/**
 * @brief Get Cross talk compensation rate
 *
 * @par Function Description
 * Get Cross talk compensation rate.
 *
 * @note This function Access to the device
 *
 * @param   Dev                            Device Handle
 * @param   pXTalkCompensationRateMegaCps  Pointer to Compensation rate
 in Mega counts per second (16.16 fix point) see datasheet for details
 * @return  VL53L0X_ERROR_NONE              Success
 * @return  "Other error code"             See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetXTalkCompensationRateMegaCps(VL53L0X_DEV Dev,
	FixPoint1616_t *pXTalkCompensationRateMegaCps);

/**
 * @brief Set Reference Calibration Parameters
 *
 * @par Function Description
 * Set Reference Calibration Parameters.
 *
 * @note This function Access to the device
 *
 * @param   Dev                            Device Handle
 * @param   VhvSettings                    Parameter for VHV
 * @param   PhaseCal                       Parameter for PhaseCal
 * @return  VL53L0X_ERROR_NONE              Success
 * @return  "Other error code"             See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetRefCalibration(VL53L0X_DEV Dev,
	uint8_t VhvSettings, uint8_t PhaseCal);

/**
 * @brief Get Reference Calibration Parameters
 *
 * @par Function Description
 * Get Reference Calibration Parameters.
 *
 * @note This function Access to the device
 *
 * @param   Dev                            Device Handle
 * @param   pVhvSettings                   Pointer to VHV parameter
 * @param   pPhaseCal                      Pointer to PhaseCal Parameter
 * @return  VL53L0X_ERROR_NONE              Success
 * @return  "Other error code"             See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetRefCalibration(VL53L0X_DEV Dev,
	uint8_t *pVhvSettings, uint8_t *pPhaseCal);

/**
 * @brief  Get the number of the check limit managed by a given Device
 *
 * @par Function Description
 * This function give the number of the check limit managed by the Device
 *
 * @note This function doesn't Access to the device
 *
 * @param   pNumberOfLimitCheck           Pointer to the number of check limit.
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetNumberOfLimitCheck(
	uint16_t *pNumberOfLimitCheck);

/**
 * @brief  Return a description string for a given limit check number
 *
 * @par Function Description
 * This function returns a description string for a given limit check number.
 * The limit check is identified with the LimitCheckId.
 *
 * @note This function doesn't Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   LimitCheckId                  Limit Check ID
 (0<= LimitCheckId < VL53L0X_GetNumberOfLimitCheck() ).
 * @param   pLimitCheckString             Pointer to the
 description string of the given check limit.
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS   This error is
 returned when LimitCheckId value is out of range.
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetLimitCheckInfo(VL53L0X_DEV Dev,
	uint16_t LimitCheckId, char *pLimitCheckString);

/**
 * @brief  Return a the Status of the specified check limit
 *
 * @par Function Description
 * This function returns the Status of the specified check limit.
 * The value indicate if the check is fail or not.
 * The limit check is identified with the LimitCheckId.
 *
 * @note This function doesn't Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   LimitCheckId                  Limit Check ID
 (0<= LimitCheckId < VL53L0X_GetNumberOfLimitCheck() ).
 * @param   pLimitCheckStatus             Pointer to the
 Limit Check Status of the given check limit.
 * LimitCheckStatus :
 * 0 the check is not fail
 * 1 the check if fail or not enabled
 *
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS   This error is
 returned when LimitCheckId value is out of range.
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetLimitCheckStatus(VL53L0X_DEV Dev,
	uint16_t LimitCheckId, uint8_t *pLimitCheckStatus);

/**
 * @brief  Enable/Disable a specific limit check
 *
 * @par Function Description
 * This function Enable/Disable a specific limit check.
 * The limit check is identified with the LimitCheckId.
 *
 * @note This function doesn't Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   LimitCheckId                  Limit Check ID
 *  (0<= LimitCheckId < VL53L0X_GetNumberOfLimitCheck() ).
 * @param   LimitCheckEnable              if 1 the check limit
 *  corresponding to LimitCheckId is Enabled
 *                                        if 0 the check limit
 *  corresponding to LimitCheckId is disabled
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS   This error is returned
 *  when LimitCheckId value is out of range.
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetLimitCheckEnable(VL53L0X_DEV Dev,
	uint16_t LimitCheckId, uint8_t LimitCheckEnable);

/**
 * @brief  Get specific limit check enable state
 *
 * @par Function Description
 * This function get the enable state of a specific limit check.
 * The limit check is identified with the LimitCheckId.
 *
 * @note This function Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   LimitCheckId                  Limit Check ID
 *  (0<= LimitCheckId < VL53L0X_GetNumberOfLimitCheck() ).
 * @param   pLimitCheckEnable             Pointer to the check limit enable
 * value.
 *  if 1 the check limit
 *        corresponding to LimitCheckId is Enabled
 *  if 0 the check limit
 *        corresponding to LimitCheckId is disabled
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS   This error is returned
 *  when LimitCheckId value is out of range.
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetLimitCheckEnable(VL53L0X_DEV Dev,
	uint16_t LimitCheckId, uint8_t *pLimitCheckEnable);

/**
 * @brief  Set a specific limit check value
 *
 * @par Function Description
 * This function set a specific limit check value.
 * The limit check is identified with the LimitCheckId.
 *
 * @note This function Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   LimitCheckId                  Limit Check ID
 *  (0<= LimitCheckId < VL53L0X_GetNumberOfLimitCheck() ).
 * @param   LimitCheckValue               Limit check Value for a given
 * LimitCheckId
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS   This error is returned when either
 *  LimitCheckId or LimitCheckValue value is out of range.
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetLimitCheckValue(VL53L0X_DEV Dev,
	uint16_t LimitCheckId, FixPoint1616_t LimitCheckValue);

/**
 * @brief  Get a specific limit check value
 *
 * @par Function Description
 * This function get a specific limit check value from device then it updates
 * internal values and check enables.
 * The limit check is identified with the LimitCheckId.
 *
 * @note This function Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   LimitCheckId                  Limit Check ID
 *  (0<= LimitCheckId < VL53L0X_GetNumberOfLimitCheck() ).
 * @param   pLimitCheckValue              Pointer to Limit
 *  check Value for a given LimitCheckId.
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS   This error is returned
 *  when LimitCheckId value is out of range.
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetLimitCheckValue(VL53L0X_DEV Dev,
	uint16_t LimitCheckId, FixPoint1616_t *pLimitCheckValue);

/**
 * @brief  Get the current value of the signal used for the limit check
 *
 * @par Function Description
 * This function get a the current value of the signal used for the limit check.
 * To obtain the latest value you should run a ranging before.
 * The value reported is linked to the limit check identified with the
 * LimitCheckId.
 *
 * @note This function Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   LimitCheckId                  Limit Check ID
 *  (0<= LimitCheckId < VL53L0X_GetNumberOfLimitCheck() ).
 * @param   pLimitCheckCurrent            Pointer to current Value for a
 * given LimitCheckId.
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS   This error is returned when
 * LimitCheckId value is out of range.
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetLimitCheckCurrent(VL53L0X_DEV Dev,
	uint16_t LimitCheckId, FixPoint1616_t *pLimitCheckCurrent);

/**
 * @brief  Enable (or disable) Wrap around Check
 *
 * @note This function Access to the device
 *
 * @param   Dev                    Device Handle
 * @param   WrapAroundCheckEnable  Wrap around Check to be set
 *                                 0=disabled, other = enabled
 * @return  VL53L0X_ERROR_NONE      Success
 * @return  "Other error code"     See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetWrapAroundCheckEnable(VL53L0X_DEV Dev,
		uint8_t WrapAroundCheckEnable);

/**
 * @brief  Get setup of Wrap around Check
 *
 * @par Function Description
 * This function get the wrapAround check enable parameters
 *
 * @note This function Access to the device
 *
 * @param   Dev                     Device Handle
 * @param   pWrapAroundCheckEnable  Pointer to the Wrap around Check state
 *                                  0=disabled or 1 = enabled
 * @return  VL53L0X_ERROR_NONE       Success
 * @return  "Other error code"      See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetWrapAroundCheckEnable(VL53L0X_DEV Dev,
		uint8_t *pWrapAroundCheckEnable);

/**
 * @brief   Set Dmax Calibration Parameters for a given device
 * When one of the parameter is zero, this function will get parameter
 * from NVM.
 * @note This function doesn't Access to the device
 *
 * @param   Dev                    Device Handle
 * @param   RangeMilliMeter        Calibration Distance
 * @param   SignalRateRtnMegaCps   Signal rate return read at CalDistance
 * @return  VL53L0X_ERROR_NONE      Success
 * @return  "Other error code"     See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetDmaxCalParameters(VL53L0X_DEV Dev,
		uint16_t RangeMilliMeter, FixPoint1616_t SignalRateRtnMegaCps);

/**
 * @brief  Get Dmax Calibration Parameters for a given device
 *
 *
 * @note This function Access to the device
 *
 * @param   Dev                     Device Handle
 * @param   pRangeMilliMeter        Pointer to Calibration Distance
 * @param   pSignalRateRtnMegaCps   Pointer to Signal rate return
 * @return  VL53L0X_ERROR_NONE       Success
 * @return  "Other error code"      See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetDmaxCalParameters(VL53L0X_DEV Dev,
	uint16_t *pRangeMilliMeter, FixPoint1616_t *pSignalRateRtnMegaCps);

/** @} VL53L0X_parameters_group */

/** @defgroup VL53L0X_measurement_group VL53L0X Measurement Functions
 *  @brief    Functions used for the measurements
 *  @{
 */

/**
 * @brief Single shot measurement.
 *
 * @par Function Description
 * Perform simple measurement sequence (Start measure, Wait measure to end,
 * and returns when measurement is done).
 * Once function returns, user can get valid data by calling
 * VL53L0X_GetRangingMeasurement or VL53L0X_GetHistogramMeasurement
 * depending on defined measurement mode
 * User should Clear the interrupt in case this are enabled by using the
 * function VL53L0X_ClearInterruptMask().
 *
 * @warning This function is a blocking function
 *
 * @note This function Access to the device
 *
 * @param   Dev                  Device Handle
 * @return  VL53L0X_ERROR_NONE    Success
 * @return  "Other error code"   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_PerformSingleMeasurement(VL53L0X_DEV Dev);

/**
 * @brief Perform Reference Calibration
 *
 * @details Perform a reference calibration of the Device.
 * This function should be run from time to time before doing
 * a ranging measurement.
 * This function will launch a special ranging measurement, so
 * if interrupt are enable an interrupt will be done.
 * This function will clear the interrupt generated automatically.
 *
 * @warning This function is a blocking function
 *
 * @note This function Access to the device
 *
 * @param   Dev                  Device Handle
 * @param   pVhvSettings         Pointer to vhv settings parameter.
 * @param   pPhaseCal            Pointer to PhaseCal parameter.
 * @return  VL53L0X_ERROR_NONE    Success
 * @return  "Other error code"   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_PerformRefCalibration(VL53L0X_DEV Dev,
	uint8_t *pVhvSettings, uint8_t *pPhaseCal);

/**
 * @brief Perform XTalk Measurement
 *
 * @details Measures the current cross talk from glass in front
 * of the sensor.
 * This functions performs a histogram measurement and uses the results
 * to measure the crosstalk. For the function to be successful, there
 * must be no target in front of the sensor.
 *
 * @warning This function is a blocking function
 *
 * @warning This function is not supported when the final range
 * vcsel clock period is set below 10 PCLKS.
 *
 * @note This function Access to the device
 *
 * @param   Dev                  Device Handle
 * @param   TimeoutMs            Histogram measurement duration.
 * @param   pXtalkPerSpad        Output parameter containing the crosstalk
 * measurement result, in MCPS/Spad. Format fixpoint 16:16.
 * @param   pAmbientTooHigh      Output parameter which indicate that
 * pXtalkPerSpad is not good if the Ambient is too high.
 * @return  VL53L0X_ERROR_NONE    Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS vcsel clock period not supported
 * for this operation. Must not be less than 10PCLKS.
 * @return  "Other error code"   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_PerformXTalkMeasurement(VL53L0X_DEV Dev,
	uint32_t TimeoutMs, FixPoint1616_t *pXtalkPerSpad,
	uint8_t *pAmbientTooHigh);

/**
 * @brief Perform XTalk Calibration
 *
 * @details Perform a XTalk calibration of the Device.
 * This function will launch a ranging measurement, if interrupts
 * are enabled an interrupt will be done.
 * This function will clear the interrupt generated automatically.
 * This function will program a new value for the XTalk compensation
 * and it will enable the cross talk before exit.
 * This function will disable the VL53L0X_CHECKENABLE_RANGE_IGNORE_THRESHOLD.
 *
 * @warning This function is a blocking function
 *
 * @note This function Access to the device
 *
 * @note This function change the device mode to
 * VL53L0X_DEVICEMODE_SINGLE_RANGING
 *
 * @param   Dev                  Device Handle
 * @param   XTalkCalDistance     XTalkCalDistance value used for the XTalk
 * computation.
 * @param   pXTalkCompensationRateMegaCps  Pointer to new
 * XTalkCompensation value.
 * @return  VL53L0X_ERROR_NONE    Success
 * @return  "Other error code"   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_PerformXTalkCalibration(VL53L0X_DEV Dev,
	FixPoint1616_t XTalkCalDistance,
	FixPoint1616_t *pXTalkCompensationRateMegaCps);

/**
 * @brief Perform Offset Calibration
 *
 * @details Perform a Offset calibration of the Device.
 * This function will launch a ranging measurement, if interrupts are
 * enabled an interrupt will be done.
 * This function will clear the interrupt generated automatically.
 * This function will program a new value for the Offset calibration value
 * This function will disable the VL53L0X_CHECKENABLE_RANGE_IGNORE_THRESHOLD.
 *
 * @warning This function is a blocking function
 *
 * @note This function Access to the device
 *
 * @note This function does not change the device mode.
 *
 * @param   Dev                  Device Handle
 * @param   CalDistanceMilliMeter     Calibration distance value used for the
 * offset compensation.
 * @param   pOffsetMicroMeter  Pointer to new Offset value computed by the
 * function.
 *
 * @return  VL53L0X_ERROR_NONE    Success
 * @return  "Other error code"   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_PerformOffsetCalibration(VL53L0X_DEV Dev,
	FixPoint1616_t CalDistanceMilliMeter, int32_t *pOffsetMicroMeter);

/**
 * @brief Start device measurement
 *
 * @details Started measurement will depend on device parameters set through
 * @a VL53L0X_SetParameters()
 * This is a non-blocking function.
 * This function will change the VL53L0X_State from VL53L0X_STATE_IDLE to
 * VL53L0X_STATE_RUNNING.
 *
 * @note This function Access to the device
 *

 * @param   Dev                  Device Handle
 * @return  VL53L0X_ERROR_NONE                  Success
 * @return  VL53L0X_ERROR_MODE_NOT_SUPPORTED    This error occurs when
 * DeviceMode programmed with @a VL53L0X_SetDeviceMode is not in the supported
 * list:
 *                                   Supported mode are:
 *                                   VL53L0X_DEVICEMODE_SINGLE_RANGING,
 *                                   VL53L0X_DEVICEMODE_CONTINUOUS_RANGING,
 *                                   VL53L0X_DEVICEMODE_CONTINUOUS_TIMED_RANGING
 * @return  VL53L0X_ERROR_TIME_OUT    Time out on start measurement
 * @return  "Other error code"   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_StartMeasurement(VL53L0X_DEV Dev);

/**
 * @brief Stop device measurement
 *
 * @details Will set the device in standby mode at end of current measurement\n
 *          Not necessary in single mode as device shall return automatically
 *          in standby mode at end of measurement.
 *          This function will change the VL53L0X_State from VL53L0X_STATE_RUNNING
 *          to VL53L0X_STATE_IDLE.
 *
 * @note This function Access to the device
 *
 * @param   Dev                  Device Handle
 * @return  VL53L0X_ERROR_NONE    Success
 * @return  "Other error code"   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_StopMeasurement(VL53L0X_DEV Dev);

/**
 * @brief Return Measurement Data Ready
 *
 * @par Function Description
 * This function indicate that a measurement data is ready.
 * This function check if interrupt mode is used then check is done accordingly.
 * If perform function clear the interrupt, this function will not work,
 * like in case of @a VL53L0X_PerformSingleRangingMeasurement().
 * The previous function is blocking function, VL53L0X_GetMeasurementDataReady
 * is used for non-blocking capture.
 *
 * @note This function Access to the device
 *
 * @param   Dev                    Device Handle
 * @param   pMeasurementDataReady  Pointer to Measurement Data Ready.
 *  0=data not ready, 1 = data ready
 * @return  VL53L0X_ERROR_NONE      Success
 * @return  "Other error code"     See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetMeasurementDataReady(VL53L0X_DEV Dev,
	uint8_t *pMeasurementDataReady);

/**
 * @brief Wait for device ready for a new measurement command.
 * Blocking function.
 *
 * @note This function is not Implemented
 *
 * @param   Dev      Device Handle
 * @param   MaxLoop    Max Number of polling loop (timeout).
 * @return  VL53L0X_ERROR_NOT_IMPLEMENTED   Not implemented
 */
VL53L0X_API VL53L0X_Error VL53L0X_WaitDeviceReadyForNewMeasurement(VL53L0X_DEV Dev,
	uint32_t MaxLoop);

/**
 * @brief Retrieve the Reference Signal after a measurements
 *
 * @par Function Description
 * Get Reference Signal from last successful Ranging measurement
 * This function return a valid value after that you call the
 * @a VL53L0X_GetRangingMeasurementData().
 *
 * @note This function Access to the device
 *
 * @param   Dev                      Device Handle
 * @param   pMeasurementRefSignal    Pointer to the Ref Signal to fill up.
 * @return  VL53L0X_ERROR_NONE        Success
 * @return  "Other error code"       See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetMeasurementRefSignal(VL53L0X_DEV Dev,
	FixPoint1616_t *pMeasurementRefSignal);

/**
 * @brief Retrieve the measurements from device for a given setup
 *
 * @par Function Description
 * Get data from last successful Ranging measurement
 * @warning USER should take care about  @a VL53L0X_GetNumberOfROIZones()
 * before get data.
 * PAL will fill a NumberOfROIZones times the corresponding data
 * structure used in the measurement function.
 *
 * @note This function Access to the device
 *
 * @param   Dev                      Device Handle
 * @param   pRangingMeasurementData  Pointer to the data structure to fill up.
 * @return  VL53L0X_ERROR_NONE        Success
 * @return  "Other error code"       See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetRangingMeasurementData(VL53L0X_DEV Dev,
	VL53L0X_RangingMeasurementData_t *pRangingMeasurementData);

/**
 * @brief Retrieve the measurements from device for a given setup
 *
 * @par Function Description
 * Get data from last successful Histogram measurement
 * @warning USER should take care about  @a VL53L0X_GetNumberOfROIZones()
 * before get data.
 * PAL will fill a NumberOfROIZones times the corresponding data structure
 * used in the measurement function.
 *
 * @note This function is not Implemented
 *
 * @param   Dev                         Device Handle
 * @param   pHistogramMeasurementData   Pointer to the histogram data structure.
 * @return  VL53L0X_ERROR_NOT_IMPLEMENTED   Not implemented
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetHistogramMeasurementData(VL53L0X_DEV Dev,
	VL53L0X_HistogramMeasurementData_t *pHistogramMeasurementData);

/**
 * @brief Performs a single ranging measurement and retrieve the ranging
 * measurement data
 *
 * @par Function Description
 * This function will change the device mode to VL53L0X_DEVICEMODE_SINGLE_RANGING
 * with @a VL53L0X_SetDeviceMode(),
 * It performs measurement with @a VL53L0X_PerformSingleMeasurement()
 * It get data from last successful Ranging measurement with
 * @a VL53L0X_GetRangingMeasurementData.
 * Finally it clear the interrupt with @a VL53L0X_ClearInterruptMask().
 *
 * @note This function Access to the device
 *
 * @note This function change the device mode to
 * VL53L0X_DEVICEMODE_SINGLE_RANGING
 *
 * @param   Dev                       Device Handle
 * @param   pRangingMeasurementData   Pointer to the data structure to fill up.
 * @return  VL53L0X_ERROR_NONE         Success
 * @return  "Other error code"        See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_PerformSingleRangingMeasurement(VL53L0X_DEV Dev,
	VL53L0X_RangingMeasurementData_t *pRangingMeasurementData);

/**
 * @brief Performs a single histogram measurement and retrieve the histogram
 * measurement data
 *   Is equivalent to VL53L0X_PerformSingleMeasurement +
 *   VL53L0X_GetHistogramMeasurementData
 *
 * @par Function Description
 * Get data from last successful Ranging measurement.
 * This function will clear the interrupt in case of these are enabled.
 *
 * @note This function is not Implemented
 *
 * @param   Dev                        Device Handle
 * @param   pHistogramMeasurementData  Pointer to the data structure to fill up.
 * @return  VL53L0X_ERROR_NOT_IMPLEMENTED   Not implemented
 */
VL53L0X_API VL53L0X_Error VL53L0X_PerformSingleHistogramMeasurement(VL53L0X_DEV Dev,
	VL53L0X_HistogramMeasurementData_t *pHistogramMeasurementData);

/**
 * @brief Set the number of ROI Zones to be used for a specific Device
 *
 * @par Function Description
 * Set the number of ROI Zones to be used for a specific Device.
 * The programmed value should be less than the max number of ROI Zones given
 * with @a VL53L0X_GetMaxNumberOfROIZones().
 * This version of API manage only one zone.
 *
 * @param   Dev                           Device Handle
 * @param   NumberOfROIZones              Number of ROI Zones to be used for a
 *  specific Device.
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  VL53L0X_ERROR_INVALID_PARAMS   This error is returned if
 * NumberOfROIZones != 1
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetNumberOfROIZones(VL53L0X_DEV Dev,
	uint8_t NumberOfROIZones);

/**
 * @brief Get the number of ROI Zones managed by the Device
 *
 * @par Function Description
 * Get number of ROI Zones managed by the Device
 * USER should take care about  @a VL53L0X_GetNumberOfROIZones()
 * before get data after a perform measurement.
 * PAL will fill a NumberOfROIZones times the corresponding data
 * structure used in the measurement function.
 *
 * @note This function doesn't Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   pNumberOfROIZones     Pointer to the Number of ROI Zones value.
 * @return  VL53L0X_ERROR_NONE     Success
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetNumberOfROIZones(VL53L0X_DEV Dev,
	uint8_t *pNumberOfROIZones);

/**
 * @brief Get the Maximum number of ROI Zones managed by the Device
 *
 * @par Function Description
 * Get Maximum number of ROI Zones managed by the Device.
 *
 * @note This function doesn't Access to the device
 *
 * @param   Dev                    Device Handle
 * @param   pMaxNumberOfROIZones   Pointer to the Maximum Number
 *  of ROI Zones value.
 * @return  VL53L0X_ERROR_NONE      Success
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetMaxNumberOfROIZones(VL53L0X_DEV Dev,
	uint8_t *pMaxNumberOfROIZones);

/** @} VL53L0X_measurement_group */

/** @defgroup VL53L0X_interrupt_group VL53L0X Interrupt Functions
 *  @brief    Functions used for interrupt managements
 *  @{
 */

/**
 * @brief Set the configuration of GPIO pin for a given device
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   Pin                   ID of the GPIO Pin
 * @param   Functionality         Select Pin functionality.
 *  Refer to ::VL53L0X_GpioFunctionality
 * @param   DeviceMode            Device Mode associated to the Gpio.
 * @param   Polarity              Set interrupt polarity. Active high
 *   or active low see ::VL53L0X_InterruptPolarity
 * @return  VL53L0X_ERROR_NONE                            Success
 * @return  VL53L0X_ERROR_GPIO_NOT_EXISTING               Only Pin=0 is accepted.
 * @return  VL53L0X_ERROR_GPIO_FUNCTIONALITY_NOT_SUPPORTED    This error occurs
 * when Functionality programmed is not in the supported list:
 *                             Supported value are:
 *                             VL53L0X_GPIOFUNCTIONALITY_OFF,
 *                             VL53L0X_GPIOFUNCTIONALITY_THRESHOLD_CROSSED_LOW,
 *                             VL53L0X_GPIOFUNCTIONALITY_THRESHOLD_CROSSED_HIGH,
 VL53L0X_GPIOFUNCTIONALITY_THRESHOLD_CROSSED_OUT,
 *                               VL53L0X_GPIOFUNCTIONALITY_NEW_MEASURE_READY
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetGpioConfig(VL53L0X_DEV Dev, uint8_t Pin,
	VL53L0X_DeviceModes DeviceMode, VL53L0X_GpioFunctionality Functionality,
	VL53L0X_InterruptPolarity Polarity);

/**
 * @brief Get current configuration for GPIO pin for a given device
 *
 * @note This function Access to the device
 *
 * @param   Dev                   Device Handle
 * @param   Pin                   ID of the GPIO Pin
 * @param   pDeviceMode           Pointer to Device Mode associated to the Gpio.
 * @param   pFunctionality        Pointer to Pin functionality.
 *  Refer to ::VL53L0X_GpioFunctionality
 * @param   pPolarity             Pointer to interrupt polarity.
 *  Active high or active low see ::VL53L0X_InterruptPolarity
 * @return  VL53L0X_ERROR_NONE                            Success
 * @return  VL53L0X_ERROR_GPIO_NOT_EXISTING               Only Pin=0 is accepted.
 * @return  VL53L0X_ERROR_GPIO_FUNCTIONALITY_NOT_SUPPORTED   This error occurs
 * when Functionality programmed is not in the supported list:
 *                      Supported value are:
 *                      VL53L0X_GPIOFUNCTIONALITY_OFF,
 *                      VL53L0X_GPIOFUNCTIONALITY_THRESHOLD_CROSSED_LOW,
 *                      VL53L0X_GPIOFUNCTIONALITY_THRESHOLD_CROSSED_HIGH,
 *                      VL53L0X_GPIOFUNCTIONALITY_THRESHOLD_CROSSED_OUT,
 *                      VL53L0X_GPIOFUNCTIONALITY_NEW_MEASURE_READY
 * @return  "Other error code"    See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetGpioConfig(VL53L0X_DEV Dev, uint8_t Pin,
	VL53L0X_DeviceModes *pDeviceMode,
	VL53L0X_GpioFunctionality *pFunctionality,
	VL53L0X_InterruptPolarity *pPolarity);

/**
 * @brief Set low and high Interrupt thresholds for a given mode
 * (ranging, ALS, ...) for a given device
 *
 * @par Function Description
 * Set low and high Interrupt thresholds for a given mode (ranging, ALS, ...)
 * for a given device
 *
 * @note This function Access to the device
 *
 * @note DeviceMode is ignored for the current device
 *
 * @param   Dev              Device Handle
 * @param   DeviceMode       Device Mode for which change thresholds
 * @param   ThresholdLow     Low threshold (mm, lux ..., depending on the mode)
 * @param   ThresholdHigh    High threshold (mm, lux ..., depending on the mode)
 * @return  VL53L0X_ERROR_NONE    Success
 * @return  "Other error code"   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetInterruptThresholds(VL53L0X_DEV Dev,
	VL53L0X_DeviceModes DeviceMode, FixPoint1616_t ThresholdLow,
	FixPoint1616_t ThresholdHigh);

/**
 * @brief  Get high and low Interrupt thresholds for a given mode
 *  (ranging, ALS, ...) for a given device
 *
 * @par Function Description
 * Get high and low Interrupt thresholds for a given mode (ranging, ALS, ...)
 * for a given device
 *
 * @note This function Access to the device
 *
 * @note DeviceMode is ignored for the current device
 *
 * @param   Dev              Device Handle
 * @param   DeviceMode       Device Mode from which read thresholds
 * @param   pThresholdLow    Low threshold (mm, lux ..., depending on the mode)
 * @param   pThresholdHigh   High threshold (mm, lux ..., depending on the mode)
 * @return  VL53L0X_ERROR_NONE   Success
 * @return  "Other error code"  See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetInterruptThresholds(VL53L0X_DEV Dev,
	VL53L0X_DeviceModes DeviceMode, FixPoint1616_t *pThresholdLow,
	FixPoint1616_t *pThresholdHigh);

/**
 * @brief Return device stop completion status
 *
 * @par Function Description
 * Returns stop completiob status.
 * User shall call this function after a stop command
 *
 * @note This function Access to the device
 *
 * @param   Dev                    Device Handle
 * @param   pStopStatus            Pointer to status variable to update
 * @return  VL53L0X_ERROR_NONE      Success
 * @return  "Other error code"     See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetStopCompletedStatus(VL53L0X_DEV Dev,
	uint32_t *pStopStatus);


/**
 * @brief Clear given system interrupt condition
 *
 * @par Function Description
 * Clear given interrupt(s).
 *
 * @note This function Access to the device
 *
 * @param   Dev                  Device Handle
 * @param   InterruptMask        Mask of interrupts to clear
 * @return  VL53L0X_ERROR_NONE    Success
 * @return  VL53L0X_ERROR_INTERRUPT_NOT_CLEARED    Cannot clear interrupts
 *
 * @return  "Other error code"   See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_ClearInterruptMask(VL53L0X_DEV Dev,
	uint32_t InterruptMask);

/**
 * @brief Return device interrupt status
 *
 * @par Function Description
 * Returns currently raised interrupts by the device.
 * User shall be able to activate/deactivate interrupts through
 * @a VL53L0X_SetGpioConfig()
 *
 * @note This function Access to the device
 *
 * @param   Dev                    Device Handle
 * @param   pInterruptMaskStatus   Pointer to status variable to update
 * @return  VL53L0X_ERROR_NONE      Success
 * @return  "Other error code"     See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetInterruptMaskStatus(VL53L0X_DEV Dev,
	uint32_t *pInterruptMaskStatus);

/**
 * @brief Configure ranging interrupt reported to system
 *
 * @note This function is not Implemented
 *
 * @param   Dev                  Device Handle
 * @param   InterruptMask         Mask of interrupt to Enable/disable
 *  (0:interrupt disabled or 1: interrupt enabled)
 * @return  VL53L0X_ERROR_NOT_IMPLEMENTED   Not implemented
 */
VL53L0X_API VL53L0X_Error VL53L0X_EnableInterruptMask(VL53L0X_DEV Dev,
	uint32_t InterruptMask);

/** @} VL53L0X_interrupt_group */

/** @defgroup VL53L0X_SPADfunctions_group VL53L0X SPAD Functions
 *  @brief    Functions used for SPAD managements
 *  @{
 */

/**
 * @brief  Set the SPAD Ambient Damper Threshold value
 *
 * @par Function Description
 * This function set the SPAD Ambient Damper Threshold value
 *
 * @note This function Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   SpadAmbientDamperThreshold    SPAD Ambient Damper Threshold value
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetSpadAmbientDamperThreshold(VL53L0X_DEV Dev,
	uint16_t SpadAmbientDamperThreshold);

/**
 * @brief  Get the current SPAD Ambient Damper Threshold value
 *
 * @par Function Description
 * This function get the SPAD Ambient Damper Threshold value
 *
 * @note This function Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   pSpadAmbientDamperThreshold   Pointer to programmed
 *                                        SPAD Ambient Damper Threshold value
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetSpadAmbientDamperThreshold(VL53L0X_DEV Dev,
	uint16_t *pSpadAmbientDamperThreshold);

/**
 * @brief  Set the SPAD Ambient Damper Factor value
 *
 * @par Function Description
 * This function set the SPAD Ambient Damper Factor value
 *
 * @note This function Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   SpadAmbientDamperFactor       SPAD Ambient Damper Factor value
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetSpadAmbientDamperFactor(VL53L0X_DEV Dev,
	uint16_t SpadAmbientDamperFactor);

/**
 * @brief  Get the current SPAD Ambient Damper Factor value
 *
 * @par Function Description
 * This function get the SPAD Ambient Damper Factor value
 *
 * @note This function Access to the device
 *
 * @param   Dev                           Device Handle
 * @param   pSpadAmbientDamperFactor      Pointer to programmed SPAD Ambient
 * Damper Factor value
 * @return  VL53L0X_ERROR_NONE             Success
 * @return  "Other error code"            See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetSpadAmbientDamperFactor(VL53L0X_DEV Dev,
	uint16_t *pSpadAmbientDamperFactor);

/**
 * @brief Performs Reference Spad Management
 *
 * @par Function Description
 * The reference SPAD initialization procedure determines the minimum amount
 * of reference spads to be enables to achieve a target reference signal rate
 * and should be performed once during initialization.
 *
 * @note This function Access to the device
 *
 * @note This function change the device mode to
 * VL53L0X_DEVICEMODE_SINGLE_RANGING
 *
 * @param   Dev                          Device Handle
 * @param   refSpadCount                 Reports ref Spad Count
 * @param   isApertureSpads              Reports if spads are of type
 *                                       aperture or non-aperture.
 *                                       1:=aperture, 0:=Non-Aperture
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  VL53L0X_ERROR_REF_SPAD_INIT   Error in the Ref Spad procedure.
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_PerformRefSpadManagement(VL53L0X_DEV Dev,
	uint32_t *refSpadCount, uint8_t *isApertureSpads);

/**
 * @brief Applies Reference SPAD configuration
 *
 * @par Function Description
 * This function applies a given number of reference spads, identified as
 * either Aperture or Non-Aperture.
 * The requested spad count and type are stored within the device specific
 * parameters data for access by the host.
 *
 * @note This function Access to the device
 *
 * @param   Dev                          Device Handle
 * @param   refSpadCount                 Number of ref spads.
 * @param   isApertureSpads              Defines if spads are of type
 *                                       aperture or non-aperture.
 *                                       1:=aperture, 0:=Non-Aperture
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  VL53L0X_ERROR_REF_SPAD_INIT   Error in the in the reference
 *                                       spad configuration.
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_SetReferenceSpads(VL53L0X_DEV Dev,
	uint32_t refSpadCount, uint8_t isApertureSpads);

/**
 * @brief Retrieves SPAD configuration
 *
 * @par Function Description
 * This function retrieves the current number of applied reference spads
 * and also their type : Aperture or Non-Aperture.
 *
 * @note This function Access to the device
 *
 * @param   Dev                          Device Handle
 * @param   refSpadCount                 Number ref Spad Count
 * @param   isApertureSpads              Reports if spads are of type
 *                                       aperture or non-aperture.
 *                                       1:=aperture, 0:=Non-Aperture
 * @return  VL53L0X_ERROR_NONE            Success
 * @return  VL53L0X_ERROR_REF_SPAD_INIT   Error in the in the reference
 *                                       spad configuration.
 * @return  "Other error code"           See ::VL53L0X_Error
 */
VL53L0X_API VL53L0X_Error VL53L0X_GetReferenceSpads(VL53L0X_DEV Dev,
	uint32_t *refSpadCount, uint8_t *isApertureSpads);

/** @} VL53L0X_SPADfunctions_group */

/** @} VL53L0X_cut11_group */

#ifdef __cplusplus
}
#endif

#endif /* _VL53L0X_API_H_ */


/*******************************************************************************
Copyright � 2016, STMicroelectronics International N.V.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
	* Redistributions of source code must retain the above copyright
	  notice, this list of conditions and the following disclaimer.
	* Redistributions in binary form must reproduce the above copyright
	  notice, this list of conditions and the following disclaimer in the
	  documentation and/or other materials provided with the distribution.
	* Neither the name of STMicroelectronics nor the
	  names of its contributors may be used to endorse or promote products
	  derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
NON-INFRINGEMENT OF INTELLECTUAL PROPERTY RIGHTS ARE DISCLAIMED.
IN NO EVENT SHALL STMICROELECTRONICS INTERNATIONAL N.V. BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*******************************************************************************/


#ifndef _VL53L0X_TUNING_H_
#define _VL53L0X_TUNING_H_



#ifdef __cplusplus
extern "C" {
#endif



extern uint8_t DefaultTuningSettings[];


#ifdef __cplusplus
}
#endif

#endif /* _VL53L0X_TUNING_H_ */



/*******************************************************************************
Copyright � 2016, STMicroelectronics International N.V.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
	* Redistributions of source code must retain the above copyright
	  notice, this list of conditions and the following disclaimer.
	* Redistributions in binary form must reproduce the above copyright
	  notice, this list of conditions and the following disclaimer in the
	  documentation and/or other materials provided with the distribution.
	* Neither the name of STMicroelectronics nor the
	  names of its contributors may be used to endorse or promote products
	  derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
NON-INFRINGEMENT OF INTELLECTUAL PROPERTY RIGHTS ARE DISCLAIMED.
IN NO EVENT SHALL STMICROELECTRONICS INTERNATIONAL N.V. BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*******************************************************************************/


#ifndef _VL53L0X_INTERRUPT_THRESHOLD_SETTINGS_H_
#define _VL53L0X_INTERRUPT_THRESHOLD_SETTINGS_H_


#ifdef __cplusplus
extern "C" {
#endif



extern uint8_t InterruptThresholdSettings[];


#ifdef __cplusplus
}
#endif

#endif /* _VL53L0X_INTERRUPT_THRESHOLD_SETTINGS_H_ */



/*******************************************************************************
Copyright � 2016, STMicroelectronics International N.V.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.
    * Neither the name of STMicroelectronics nor the
      names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
NON-INFRINGEMENT OF INTELLECTUAL PROPERTY RIGHTS ARE DISCLAIMED.
IN NO EVENT SHALL STMICROELECTRONICS INTERNATIONAL N.V. BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*******************************************************************************/

#ifndef _VL53L0X_API_CORE_H_
#define _VL53L0X_API_CORE_H_



#ifdef __cplusplus
extern "C" {
#endif


VL53L0X_Error VL53L0X_reverse_bytes(uint8_t *data, uint32_t size);

VL53L0X_Error VL53L0X_measurement_poll_for_completion(VL53L0X_DEV Dev);

uint8_t VL53L0X_encode_vcsel_period(uint8_t vcsel_period_pclks);

uint8_t VL53L0X_decode_vcsel_period(uint8_t vcsel_period_reg);

uint32_t VL53L0X_isqrt(uint32_t num);

uint32_t VL53L0X_quadrature_sum(uint32_t a, uint32_t b);

VL53L0X_Error VL53L0X_get_info_from_device(VL53L0X_DEV Dev, uint8_t option);

VL53L0X_Error VL53L0X_set_vcsel_pulse_period(VL53L0X_DEV Dev,
	VL53L0X_VcselPeriod VcselPeriodType, uint8_t VCSELPulsePeriodPCLK);

VL53L0X_Error VL53L0X_get_vcsel_pulse_period(VL53L0X_DEV Dev,
	VL53L0X_VcselPeriod VcselPeriodType, uint8_t *pVCSELPulsePeriodPCLK);

uint32_t VL53L0X_decode_timeout(uint16_t encoded_timeout);

VL53L0X_Error get_sequence_step_timeout(VL53L0X_DEV Dev,
			VL53L0X_SequenceStepId SequenceStepId,
			uint32_t *pTimeOutMicroSecs);

VL53L0X_Error set_sequence_step_timeout(VL53L0X_DEV Dev,
			VL53L0X_SequenceStepId SequenceStepId,
			uint32_t TimeOutMicroSecs);

VL53L0X_Error VL53L0X_set_measurement_timing_budget_micro_seconds(VL53L0X_DEV Dev,
	uint32_t MeasurementTimingBudgetMicroSeconds);

VL53L0X_Error VL53L0X_get_measurement_timing_budget_micro_seconds(VL53L0X_DEV Dev,
		uint32_t *pMeasurementTimingBudgetMicroSeconds);

VL53L0X_Error VL53L0X_load_tuning_settings(VL53L0X_DEV Dev,
		uint8_t *pTuningSettingBuffer);

VL53L0X_Error VL53L0X_calc_sigma_estimate(VL53L0X_DEV Dev,
		VL53L0X_RangingMeasurementData_t *pRangingMeasurementData,
		FixPoint1616_t *pSigmaEstimate, uint32_t *pDmax_mm);

VL53L0X_Error VL53L0X_get_total_xtalk_rate(VL53L0X_DEV Dev,
	VL53L0X_RangingMeasurementData_t *pRangingMeasurementData,
	FixPoint1616_t *ptotal_xtalk_rate_mcps);

VL53L0X_Error VL53L0X_get_total_signal_rate(VL53L0X_DEV Dev,
	VL53L0X_RangingMeasurementData_t *pRangingMeasurementData,
	FixPoint1616_t *ptotal_signal_rate_mcps);

VL53L0X_Error VL53L0X_get_pal_range_status(VL53L0X_DEV Dev,
		 uint8_t DeviceRangeStatus,
		 FixPoint1616_t SignalRate,
		 uint16_t EffectiveSpadRtnCount,
		 VL53L0X_RangingMeasurementData_t *pRangingMeasurementData,
		 uint8_t *pPalRangeStatus);

uint32_t VL53L0X_calc_timeout_mclks(VL53L0X_DEV Dev,
	uint32_t timeout_period_us, uint8_t vcsel_period_pclks);

uint16_t VL53L0X_encode_timeout(uint32_t timeout_macro_clks);

#ifdef __cplusplus
}
#endif

#endif /* _VL53L0X_API_CORE_H_ */


/*******************************************************************************
Copyright � 2016, STMicroelectronics International N.V.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
	* Redistributions of source code must retain the above copyright
	  notice, this list of conditions and the following disclaimer.
	* Redistributions in binary form must reproduce the above copyright
	  notice, this list of conditions and the following disclaimer in the
	  documentation and/or other materials provided with the distribution.
	* Neither the name of STMicroelectronics nor the
	  names of its contributors may be used to endorse or promote products
	  derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
NON-INFRINGEMENT OF INTELLECTUAL PROPERTY RIGHTS ARE DISCLAIMED.
IN NO EVENT SHALL STMICROELECTRONICS INTERNATIONAL N.V. BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*******************************************************************************/

#ifndef _VL53L0X_API_CALIBRATION_H_
#define _VL53L0X_API_CALIBRATION_H_



#ifdef __cplusplus
extern "C" {
#endif

VL53L0X_Error VL53L0X_perform_xtalk_calibration(VL53L0X_DEV Dev,
		FixPoint1616_t XTalkCalDistance,
		FixPoint1616_t *pXTalkCompensationRateMegaCps);

VL53L0X_Error VL53L0X_perform_offset_calibration(VL53L0X_DEV Dev,
		FixPoint1616_t CalDistanceMilliMeter,
		int32_t *pOffsetMicroMeter);

VL53L0X_Error VL53L0X_set_offset_calibration_data_micro_meter(VL53L0X_DEV Dev,
		int32_t OffsetCalibrationDataMicroMeter);

VL53L0X_Error VL53L0X_get_offset_calibration_data_micro_meter(VL53L0X_DEV Dev,
		int32_t *pOffsetCalibrationDataMicroMeter);

VL53L0X_Error VL53L0X_apply_offset_adjustment(VL53L0X_DEV Dev);

VL53L0X_Error VL53L0X_perform_ref_spad_management(VL53L0X_DEV Dev,
		uint32_t *refSpadCount, uint8_t *isApertureSpads);

VL53L0X_Error VL53L0X_set_reference_spads(VL53L0X_DEV Dev,
		uint32_t count, uint8_t isApertureSpads);

VL53L0X_Error VL53L0X_get_reference_spads(VL53L0X_DEV Dev,
		uint32_t *pSpadCount, uint8_t *pIsApertureSpads);

VL53L0X_Error VL53L0X_perform_phase_calibration(VL53L0X_DEV Dev,
	uint8_t *pPhaseCal, const uint8_t get_data_enable,
	const uint8_t restore_config);

VL53L0X_Error VL53L0X_perform_ref_calibration(VL53L0X_DEV Dev,
	uint8_t *pVhvSettings, uint8_t *pPhaseCal, uint8_t get_data_enable);

VL53L0X_Error VL53L0X_set_ref_calibration(VL53L0X_DEV Dev,
		uint8_t VhvSettings, uint8_t PhaseCal);

VL53L0X_Error VL53L0X_get_ref_calibration(VL53L0X_DEV Dev,
		uint8_t *pVhvSettings, uint8_t *pPhaseCal);




#ifdef __cplusplus
}
#endif

#endif /* _VL53L0X_API_CALIBRATION_H_ */


/* ---- 裁剪闭包函数前向声明（生成自核心源码——消除隐式声明）---- */
VL53L0X_Error VL53L0X_SetOffsetCalibrationDataMicroMeter(VL53L0X_DEV Dev, int32_t OffsetCalibrationDataMicroMeter);
VL53L0X_Error VL53L0X_GetOffsetCalibrationDataMicroMeter(VL53L0X_DEV Dev, int32_t *pOffsetCalibrationDataMicroMeter);
VL53L0X_Error VL53L0X_DataInit(VL53L0X_DEV Dev);
VL53L0X_Error VL53L0X_StaticInit(VL53L0X_DEV Dev);
VL53L0X_Error VL53L0X_GetDeviceParameters(VL53L0X_DEV Dev, VL53L0X_DeviceParameters_t *pDeviceParameters);
VL53L0X_Error VL53L0X_SetDeviceMode(VL53L0X_DEV Dev, VL53L0X_DeviceModes DeviceMode);
VL53L0X_Error VL53L0X_GetDeviceMode(VL53L0X_DEV Dev, VL53L0X_DeviceModes *pDeviceMode);
VL53L0X_Error VL53L0X_GetFractionEnable(VL53L0X_DEV Dev, uint8_t *pEnabled);
VL53L0X_Error VL53L0X_SetMeasurementTimingBudgetMicroSeconds(VL53L0X_DEV Dev, uint32_t MeasurementTimingBudgetMicroSeconds);
VL53L0X_Error VL53L0X_GetMeasurementTimingBudgetMicroSeconds(VL53L0X_DEV Dev, uint32_t *pMeasurementTimingBudgetMicroSeconds);
VL53L0X_Error VL53L0X_SetVcselPulsePeriod(VL53L0X_DEV Dev, VL53L0X_VcselPeriod VcselPeriodType, uint8_t VCSELPulsePeriodPCLK);
VL53L0X_Error VL53L0X_GetVcselPulsePeriod(VL53L0X_DEV Dev, VL53L0X_VcselPeriod VcselPeriodType, uint8_t *pVCSELPulsePeriodPCLK);
VL53L0X_Error VL53L0X_SetSequenceStepEnable(VL53L0X_DEV Dev, VL53L0X_SequenceStepId SequenceStepId, uint8_t SequenceStepEnabled);
VL53L0X_Error sequence_step_enabled(VL53L0X_DEV Dev, VL53L0X_SequenceStepId SequenceStepId, uint8_t SequenceConfig, uint8_t *pSequenceStepEnabled);
VL53L0X_Error VL53L0X_GetSequenceStepEnables(VL53L0X_DEV Dev, VL53L0X_SchedulerSequenceSteps_t *pSchedulerSequenceSteps);
VL53L0X_Error VL53L0X_GetInterMeasurementPeriodMilliSeconds(VL53L0X_DEV Dev, uint32_t *pInterMeasurementPeriodMilliSeconds);
VL53L0X_Error VL53L0X_GetXTalkCompensationEnable(VL53L0X_DEV Dev, uint8_t *pXTalkCompensationEnable);
VL53L0X_Error VL53L0X_GetXTalkCompensationRateMegaCps(VL53L0X_DEV Dev, FixPoint1616_t *pXTalkCompensationRateMegaCps);
VL53L0X_Error VL53L0X_SetLimitCheckEnable(VL53L0X_DEV Dev, uint16_t LimitCheckId, uint8_t LimitCheckEnable);
VL53L0X_Error VL53L0X_GetLimitCheckEnable(VL53L0X_DEV Dev, uint16_t LimitCheckId, uint8_t *pLimitCheckEnable);
VL53L0X_Error VL53L0X_SetLimitCheckValue(VL53L0X_DEV Dev, uint16_t LimitCheckId, FixPoint1616_t LimitCheckValue);
VL53L0X_Error VL53L0X_GetLimitCheckValue(VL53L0X_DEV Dev, uint16_t LimitCheckId, FixPoint1616_t *pLimitCheckValue);
VL53L0X_Error VL53L0X_GetWrapAroundCheckEnable(VL53L0X_DEV Dev, uint8_t *pWrapAroundCheckEnable);
VL53L0X_Error VL53L0X_PerformSingleMeasurement(VL53L0X_DEV Dev);
VL53L0X_Error VL53L0X_PerformRefCalibration(VL53L0X_DEV Dev, uint8_t *pVhvSettings, uint8_t *pPhaseCal);
VL53L0X_Error VL53L0X_CheckAndLoadInterruptSettings(VL53L0X_DEV Dev, uint8_t StartNotStopFlag);
VL53L0X_Error VL53L0X_StartMeasurement(VL53L0X_DEV Dev);
VL53L0X_Error VL53L0X_GetMeasurementDataReady(VL53L0X_DEV Dev, uint8_t *pMeasurementDataReady);
VL53L0X_Error VL53L0X_GetRangingMeasurementData(VL53L0X_DEV Dev, VL53L0X_RangingMeasurementData_t *pRangingMeasurementData);
VL53L0X_Error VL53L0X_PerformSingleRangingMeasurement(VL53L0X_DEV Dev, VL53L0X_RangingMeasurementData_t *pRangingMeasurementData);
VL53L0X_Error VL53L0X_SetGpioConfig(VL53L0X_DEV Dev, uint8_t Pin, VL53L0X_DeviceModes DeviceMode, VL53L0X_GpioFunctionality Functionality, VL53L0X_InterruptPolarity Polarity);
VL53L0X_Error VL53L0X_GetInterruptThresholds(VL53L0X_DEV Dev, VL53L0X_DeviceModes DeviceMode, FixPoint1616_t *pThresholdLow, FixPoint1616_t *pThresholdHigh);
VL53L0X_Error VL53L0X_ClearInterruptMask(VL53L0X_DEV Dev, uint32_t InterruptMask);
VL53L0X_Error VL53L0X_GetInterruptMaskStatus(VL53L0X_DEV Dev, uint32_t *pInterruptMaskStatus);
VL53L0X_Error VL53L0X_PerformRefSpadManagement(VL53L0X_DEV Dev, uint32_t *refSpadCount, uint8_t *isApertureSpads);
VL53L0X_Error VL53L0X_set_offset_calibration_data_micro_meter(VL53L0X_DEV Dev, int32_t OffsetCalibrationDataMicroMeter);
VL53L0X_Error VL53L0X_get_offset_calibration_data_micro_meter(VL53L0X_DEV Dev, int32_t *pOffsetCalibrationDataMicroMeter);
VL53L0X_Error VL53L0X_apply_offset_adjustment(VL53L0X_DEV Dev);
void get_next_good_spad(uint8_t goodSpadArray[], uint32_t size, uint32_t curr, int32_t *next);
uint8_t is_aperture(uint32_t spadIndex);
VL53L0X_Error enable_spad_bit(uint8_t spadArray[], uint32_t size, uint32_t spadIndex);
VL53L0X_Error set_ref_spad_map(VL53L0X_DEV Dev, uint8_t *refSpadArray);
VL53L0X_Error get_ref_spad_map(VL53L0X_DEV Dev, uint8_t *refSpadArray);
VL53L0X_Error enable_ref_spads(VL53L0X_DEV Dev, uint8_t apertureSpads, uint8_t goodSpadArray[], uint8_t spadArray[], uint32_t size, uint32_t start, uint32_t offset, uint32_t spadCount, uint32_t *lastSpad);
VL53L0X_Error perform_ref_signal_measurement(VL53L0X_DEV Dev, uint16_t *refSignalRate);
VL53L0X_Error VL53L0X_perform_ref_spad_management(VL53L0X_DEV Dev, uint32_t *refSpadCount, uint8_t *isApertureSpads);
VL53L0X_Error VL53L0X_set_reference_spads(VL53L0X_DEV Dev, uint32_t count, uint8_t isApertureSpads);
VL53L0X_Error VL53L0X_perform_single_ref_calibration(VL53L0X_DEV Dev, uint8_t vhv_init_byte);
VL53L0X_Error VL53L0X_ref_calibration_io(VL53L0X_DEV Dev, uint8_t read_not_write, uint8_t VhvSettings, uint8_t PhaseCal, uint8_t *pVhvSettings, uint8_t *pPhaseCal, const uint8_t vhv_enable, const uint8_t phase_enable);
VL53L0X_Error VL53L0X_perform_vhv_calibration(VL53L0X_DEV Dev, uint8_t *pVhvSettings, const uint8_t get_data_enable, const uint8_t restore_config);
VL53L0X_Error VL53L0X_perform_phase_calibration(VL53L0X_DEV Dev, uint8_t *pPhaseCal, const uint8_t get_data_enable, const uint8_t restore_config);
VL53L0X_Error VL53L0X_perform_ref_calibration(VL53L0X_DEV Dev, uint8_t *pVhvSettings, uint8_t *pPhaseCal, uint8_t get_data_enable);
VL53L0X_Error VL53L0X_measurement_poll_for_completion(VL53L0X_DEV Dev);
uint8_t VL53L0X_decode_vcsel_period(uint8_t vcsel_period_reg);
uint8_t VL53L0X_encode_vcsel_period(uint8_t vcsel_period_pclks);
uint32_t VL53L0X_isqrt(uint32_t num);
VL53L0X_Error VL53L0X_device_read_strobe(VL53L0X_DEV Dev);
VL53L0X_Error VL53L0X_get_info_from_device(VL53L0X_DEV Dev, uint8_t option);
uint32_t VL53L0X_calc_macro_period_ps(VL53L0X_DEV Dev, uint8_t vcsel_period_pclks);
uint16_t VL53L0X_encode_timeout(uint32_t timeout_macro_clks);
uint32_t VL53L0X_decode_timeout(uint16_t encoded_timeout);
uint32_t VL53L0X_calc_timeout_mclks(VL53L0X_DEV Dev, uint32_t timeout_period_us, uint8_t vcsel_period_pclks);
uint32_t VL53L0X_calc_timeout_us(VL53L0X_DEV Dev, uint16_t timeout_period_mclks, uint8_t vcsel_period_pclks);
VL53L0X_Error get_sequence_step_timeout(VL53L0X_DEV Dev, VL53L0X_SequenceStepId SequenceStepId, uint32_t *pTimeOutMicroSecs);
VL53L0X_Error set_sequence_step_timeout(VL53L0X_DEV Dev, VL53L0X_SequenceStepId SequenceStepId, uint32_t TimeOutMicroSecs);
VL53L0X_Error VL53L0X_set_vcsel_pulse_period(VL53L0X_DEV Dev, VL53L0X_VcselPeriod VcselPeriodType, uint8_t VCSELPulsePeriodPCLK);
VL53L0X_Error VL53L0X_get_vcsel_pulse_period(VL53L0X_DEV Dev, VL53L0X_VcselPeriod VcselPeriodType, uint8_t *pVCSELPulsePeriodPCLK);
VL53L0X_Error VL53L0X_set_measurement_timing_budget_micro_seconds(VL53L0X_DEV Dev, uint32_t MeasurementTimingBudgetMicroSeconds);
VL53L0X_Error VL53L0X_get_measurement_timing_budget_micro_seconds(VL53L0X_DEV Dev, uint32_t *pMeasurementTimingBudgetMicroSeconds);
VL53L0X_Error VL53L0X_load_tuning_settings(VL53L0X_DEV Dev, uint8_t *pTuningSettingBuffer);
VL53L0X_Error VL53L0X_get_total_xtalk_rate(VL53L0X_DEV Dev, VL53L0X_RangingMeasurementData_t *pRangingMeasurementData, FixPoint1616_t *ptotal_xtalk_rate_mcps);
VL53L0X_Error VL53L0X_get_total_signal_rate(VL53L0X_DEV Dev, VL53L0X_RangingMeasurementData_t *pRangingMeasurementData, FixPoint1616_t *ptotal_signal_rate_mcps);
VL53L0X_Error VL53L0X_calc_dmax( VL53L0X_DEV Dev, FixPoint1616_t totalSignalRate_mcps, FixPoint1616_t totalCorrSignalRate_mcps, FixPoint1616_t pwMult, uint32_t sigmaEstimateP1, FixPoint1616_t sigmaEstimateP2, uint32_t peakVcselDuration_us, uint32_t *pdmax_mm);
VL53L0X_Error VL53L0X_calc_sigma_estimate(VL53L0X_DEV Dev, VL53L0X_RangingMeasurementData_t *pRangingMeasurementData, FixPoint1616_t *pSigmaEstimate, uint32_t *pDmax_mm);
VL53L0X_Error VL53L0X_get_pal_range_status(VL53L0X_DEV Dev, uint8_t DeviceRangeStatus, FixPoint1616_t SignalRate, uint16_t EffectiveSpadRtnCount, VL53L0X_RangingMeasurementData_t *pRangingMeasurementData, uint8_t *pPalRangeStatus);


#endif /* VL53L0X_CORE_H */
