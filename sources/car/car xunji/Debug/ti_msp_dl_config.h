/*
 * Copyright (c) 2023, Texas Instruments Incorporated - http://www.ti.com
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * *  Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * *  Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * *  Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

/*
 *  ============ ti_msp_dl_config.h =============
 *  Configured MSPM0 DriverLib module declarations
 *
 *  DO NOT EDIT - This file is generated for the MSPM0G350X
 *  by the SysConfig tool.
 */
#ifndef ti_msp_dl_config_h
#define ti_msp_dl_config_h

#define CONFIG_MSPM0G350X
#define CONFIG_MSPM0G3507

#if defined(__ti_version__) || defined(__TI_COMPILER_VERSION__)
#define SYSCONFIG_WEAK __attribute__((weak))
#elif defined(__IAR_SYSTEMS_ICC__)
#define SYSCONFIG_WEAK __weak
#elif defined(__GNUC__)
#define SYSCONFIG_WEAK __attribute__((weak))
#endif

#include <ti/devices/msp/msp.h>
#include <ti/driverlib/driverlib.h>
#include <ti/driverlib/m0p/dl_core.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 *  ======== SYSCFG_DL_init ========
 *  Perform all required MSP DL initialization
 *
 *  This function should be called once at a point before any use of
 *  MSP DL.
 */


/* clang-format off */

#define POWER_STARTUP_DELAY                                                (16)



#define CPUCLK_FREQ                                                     80000000
/* Defines for SYSPLL_ERR_01 Workaround */
/* Represent 1.000 as 1000 */
#define FLOAT_TO_INT_SCALE                                               (1000U)
#define FCC_EXPECTED_RATIO                                                  2500
#define FCC_UPPER_BOUND                       (FCC_EXPECTED_RATIO * (1 + 0.003))
#define FCC_LOWER_BOUND                       (FCC_EXPECTED_RATIO * (1 - 0.003))

bool SYSCFG_DL_SYSCTL_SYSPLL_init(void);


/* Defines for PWM_0 */
#define PWM_0_INST                                                         TIMG0
#define PWM_0_INST_IRQHandler                                   TIMG0_IRQHandler
#define PWM_0_INST_INT_IRQN                                     (TIMG0_INT_IRQn)
#define PWM_0_INST_CLK_FREQ                                             40000000
/* GPIO defines for channel 0 */
#define GPIO_PWM_0_C0_PORT                                                 GPIOA
#define GPIO_PWM_0_C0_PIN                                         DL_GPIO_PIN_12
#define GPIO_PWM_0_C0_IOMUX                                      (IOMUX_PINCM34)
#define GPIO_PWM_0_C0_IOMUX_FUNC                     IOMUX_PINCM34_PF_TIMG0_CCP0
#define GPIO_PWM_0_C0_IDX                                    DL_TIMER_CC_0_INDEX
/* GPIO defines for channel 1 */
#define GPIO_PWM_0_C1_PORT                                                 GPIOA
#define GPIO_PWM_0_C1_PIN                                         DL_GPIO_PIN_13
#define GPIO_PWM_0_C1_IOMUX                                      (IOMUX_PINCM35)
#define GPIO_PWM_0_C1_IOMUX_FUNC                     IOMUX_PINCM35_PF_TIMG0_CCP1
#define GPIO_PWM_0_C1_IDX                                    DL_TIMER_CC_1_INDEX



/* Defines for TIMER_Encoder_Read */
#define TIMER_Encoder_Read_INST                                          (TIMG6)
#define TIMER_Encoder_Read_INST_IRQHandler                        TIMG6_IRQHandler
#define TIMER_Encoder_Read_INST_INT_IRQN                        (TIMG6_INT_IRQn)
#define TIMER_Encoder_Read_INST_LOAD_VALUE                                (15624U)
/* Defines for TIMER_0 */
#define TIMER_0_INST                                                     (TIMG7)
#define TIMER_0_INST_IRQHandler                                 TIMG7_IRQHandler
#define TIMER_0_INST_INT_IRQN                                   (TIMG7_INT_IRQn)
#define TIMER_0_INST_LOAD_VALUE                                          (3124U)




/* Defines for I2C_MPU6050 */
#define I2C_MPU6050_INST                                                    I2C1
#define I2C_MPU6050_INST_IRQHandler                              I2C1_IRQHandler
#define I2C_MPU6050_INST_INT_IRQN                                  I2C1_INT_IRQn
#define I2C_MPU6050_BUS_SPEED_HZ                                          100000
#define GPIO_I2C_MPU6050_SDA_PORT                                          GPIOB
#define GPIO_I2C_MPU6050_SDA_PIN                                   DL_GPIO_PIN_3
#define GPIO_I2C_MPU6050_IOMUX_SDA                               (IOMUX_PINCM16)
#define GPIO_I2C_MPU6050_IOMUX_SDA_FUNC                IOMUX_PINCM16_PF_I2C1_SDA
#define GPIO_I2C_MPU6050_SCL_PORT                                          GPIOB
#define GPIO_I2C_MPU6050_SCL_PIN                                   DL_GPIO_PIN_2
#define GPIO_I2C_MPU6050_IOMUX_SCL                               (IOMUX_PINCM15)
#define GPIO_I2C_MPU6050_IOMUX_SCL_FUNC                IOMUX_PINCM15_PF_I2C1_SCL


/* Defines for UART_0 */
#define UART_0_INST                                                        UART0
#define UART_0_INST_FREQUENCY                                           40000000
#define UART_0_INST_IRQHandler                                  UART0_IRQHandler
#define UART_0_INST_INT_IRQN                                      UART0_INT_IRQn
#define GPIO_UART_0_RX_PORT                                                GPIOA
#define GPIO_UART_0_TX_PORT                                                GPIOA
#define GPIO_UART_0_RX_PIN                                        DL_GPIO_PIN_11
#define GPIO_UART_0_TX_PIN                                        DL_GPIO_PIN_10
#define GPIO_UART_0_IOMUX_RX                                     (IOMUX_PINCM22)
#define GPIO_UART_0_IOMUX_TX                                     (IOMUX_PINCM21)
#define GPIO_UART_0_IOMUX_RX_FUNC                      IOMUX_PINCM22_PF_UART0_RX
#define GPIO_UART_0_IOMUX_TX_FUNC                      IOMUX_PINCM21_PF_UART0_TX
#define UART_0_BAUD_RATE                                                (115200)
#define UART_0_IBRD_40_MHZ_115200_BAUD                                      (21)
#define UART_0_FBRD_40_MHZ_115200_BAUD                                      (45)
/* Defines for UART_JY61P */
#define UART_JY61P_INST                                                    UART2
#define UART_JY61P_INST_FREQUENCY                                       40000000
#define UART_JY61P_INST_IRQHandler                              UART2_IRQHandler
#define UART_JY61P_INST_INT_IRQN                                  UART2_INT_IRQn
#define GPIO_UART_JY61P_RX_PORT                                            GPIOA
#define GPIO_UART_JY61P_TX_PORT                                            GPIOA
#define GPIO_UART_JY61P_RX_PIN                                    DL_GPIO_PIN_22
#define GPIO_UART_JY61P_TX_PIN                                    DL_GPIO_PIN_23
#define GPIO_UART_JY61P_IOMUX_RX                                 (IOMUX_PINCM47)
#define GPIO_UART_JY61P_IOMUX_TX                                 (IOMUX_PINCM53)
#define GPIO_UART_JY61P_IOMUX_RX_FUNC                  IOMUX_PINCM47_PF_UART2_RX
#define GPIO_UART_JY61P_IOMUX_TX_FUNC                  IOMUX_PINCM53_PF_UART2_TX
#define UART_JY61P_BAUD_RATE                                            (115200)
#define UART_JY61P_IBRD_40_MHZ_115200_BAUD                                  (21)
#define UART_JY61P_FBRD_40_MHZ_115200_BAUD                                  (45)





/* Port definition for Pin Group GPIO_LED */
#define GPIO_LED_PORT                                                    (GPIOA)

/* Defines for PIN_LED: GPIOA.26 with pinCMx 59 on package pin 46 */
#define GPIO_LED_PIN_LED_PIN                                    (DL_GPIO_PIN_26)
#define GPIO_LED_PIN_LED_IOMUX                                   (IOMUX_PINCM59)
/* Port definition for Pin Group GPIO_STBY */
#define GPIO_STBY_PORT                                                   (GPIOA)

/* Defines for PIN_STBY: GPIOA.7 with pinCMx 14 on package pin 13 */
#define GPIO_STBY_PIN_STBY_PIN                                   (DL_GPIO_PIN_7)
#define GPIO_STBY_PIN_STBY_IOMUX                                 (IOMUX_PINCM14)
/* Port definition for Pin Group GPIO_EncoderA */
#define GPIO_EncoderA_PORT                                               (GPIOA)

/* Defines for PIN_0: GPIOA.17 with pinCMx 39 on package pin 32 */
// pins affected by this interrupt request:["PIN_0","PIN_1"]
#define GPIO_EncoderA_INT_IRQN                                  (GPIOA_INT_IRQn)
#define GPIO_EncoderA_INT_IIDX                  (DL_INTERRUPT_GROUP1_IIDX_GPIOA)
#define GPIO_EncoderA_PIN_0_IIDX                            (DL_GPIO_IIDX_DIO17)
#define GPIO_EncoderA_PIN_0_PIN                                 (DL_GPIO_PIN_17)
#define GPIO_EncoderA_PIN_0_IOMUX                                (IOMUX_PINCM39)
/* Defines for PIN_1: GPIOA.24 with pinCMx 54 on package pin 44 */
#define GPIO_EncoderA_PIN_1_IIDX                            (DL_GPIO_IIDX_DIO24)
#define GPIO_EncoderA_PIN_1_PIN                                 (DL_GPIO_PIN_24)
#define GPIO_EncoderA_PIN_1_IOMUX                                (IOMUX_PINCM54)
/* Port definition for Pin Group GPIO_EncoderB */
#define GPIO_EncoderB_PORT                                               (GPIOB)

/* Defines for PIN_2: GPIOB.18 with pinCMx 44 on package pin 37 */
// pins affected by this interrupt request:["PIN_2","PIN_3"]
#define GPIO_EncoderB_INT_IRQN                                  (GPIOB_INT_IRQn)
#define GPIO_EncoderB_INT_IIDX                  (DL_INTERRUPT_GROUP1_IIDX_GPIOB)
#define GPIO_EncoderB_PIN_2_IIDX                            (DL_GPIO_IIDX_DIO18)
#define GPIO_EncoderB_PIN_2_PIN                                 (DL_GPIO_PIN_18)
#define GPIO_EncoderB_PIN_2_IOMUX                                (IOMUX_PINCM44)
/* Defines for PIN_3: GPIOB.19 with pinCMx 45 on package pin 38 */
#define GPIO_EncoderB_PIN_3_IIDX                            (DL_GPIO_IIDX_DIO19)
#define GPIO_EncoderB_PIN_3_PIN                                 (DL_GPIO_PIN_19)
#define GPIO_EncoderB_PIN_3_IOMUX                                (IOMUX_PINCM45)
/* Defines for PIN_AIN1: GPIOA.15 with pinCMx 37 on package pin 30 */
#define GPIO_IN_PIN_AIN1_PORT                                            (GPIOA)
#define GPIO_IN_PIN_AIN1_PIN                                    (DL_GPIO_PIN_15)
#define GPIO_IN_PIN_AIN1_IOMUX                                   (IOMUX_PINCM37)
/* Defines for PIN_AIN2: GPIOA.2 with pinCMx 7 on package pin 8 */
#define GPIO_IN_PIN_AIN2_PORT                                            (GPIOA)
#define GPIO_IN_PIN_AIN2_PIN                                     (DL_GPIO_PIN_2)
#define GPIO_IN_PIN_AIN2_IOMUX                                    (IOMUX_PINCM7)
/* Defines for PIN_BIN1: GPIOB.7 with pinCMx 24 on package pin 21 */
#define GPIO_IN_PIN_BIN1_PORT                                            (GPIOB)
#define GPIO_IN_PIN_BIN1_PIN                                     (DL_GPIO_PIN_7)
#define GPIO_IN_PIN_BIN1_IOMUX                                   (IOMUX_PINCM24)
/* Defines for PIN_BIN2: GPIOB.6 with pinCMx 23 on package pin 20 */
#define GPIO_IN_PIN_BIN2_PORT                                            (GPIOB)
#define GPIO_IN_PIN_BIN2_PIN                                     (DL_GPIO_PIN_6)
#define GPIO_IN_PIN_BIN2_IOMUX                                   (IOMUX_PINCM23)
/* Defines for PIN_Gray_1: GPIOA.27 with pinCMx 60 on package pin 47 */
#define GPIO_Gray_PIN_Gray_1_PORT                                        (GPIOA)
#define GPIO_Gray_PIN_Gray_1_PIN                                (DL_GPIO_PIN_27)
#define GPIO_Gray_PIN_Gray_1_IOMUX                               (IOMUX_PINCM60)
/* Defines for PIN_Gray_2: GPIOB.9 with pinCMx 26 on package pin 23 */
#define GPIO_Gray_PIN_Gray_2_PORT                                        (GPIOB)
#define GPIO_Gray_PIN_Gray_2_PIN                                 (DL_GPIO_PIN_9)
#define GPIO_Gray_PIN_Gray_2_IOMUX                               (IOMUX_PINCM26)
/* Defines for PIN_Gray_3: GPIOB.24 with pinCMx 52 on package pin 42 */
#define GPIO_Gray_PIN_Gray_3_PORT                                        (GPIOB)
#define GPIO_Gray_PIN_Gray_3_PIN                                (DL_GPIO_PIN_24)
#define GPIO_Gray_PIN_Gray_3_IOMUX                               (IOMUX_PINCM52)
/* Defines for PIN_Gray_4: GPIOA.16 with pinCMx 38 on package pin 31 */
#define GPIO_Gray_PIN_Gray_4_PORT                                        (GPIOA)
#define GPIO_Gray_PIN_Gray_4_PIN                                (DL_GPIO_PIN_16)
#define GPIO_Gray_PIN_Gray_4_IOMUX                               (IOMUX_PINCM38)
/* Defines for PIN_Gray_5: GPIOA.8 with pinCMx 19 on package pin 16 */
#define GPIO_Gray_PIN_Gray_5_PORT                                        (GPIOA)
#define GPIO_Gray_PIN_Gray_5_PIN                                 (DL_GPIO_PIN_8)
#define GPIO_Gray_PIN_Gray_5_IOMUX                               (IOMUX_PINCM19)
/* Defines for PIN_Gray_6: GPIOA.0 with pinCMx 1 on package pin 1 */
#define GPIO_Gray_PIN_Gray_6_PORT                                        (GPIOA)
#define GPIO_Gray_PIN_Gray_6_PIN                                 (DL_GPIO_PIN_0)
#define GPIO_Gray_PIN_Gray_6_IOMUX                                (IOMUX_PINCM1)
/* Defines for PIN_Gray_7: GPIOA.1 with pinCMx 2 on package pin 2 */
#define GPIO_Gray_PIN_Gray_7_PORT                                        (GPIOA)
#define GPIO_Gray_PIN_Gray_7_PIN                                 (DL_GPIO_PIN_1)
#define GPIO_Gray_PIN_Gray_7_IOMUX                                (IOMUX_PINCM2)
/* Defines for PIN_Gray_8: GPIOB.20 with pinCMx 48 on package pin 41 */
#define GPIO_Gray_PIN_Gray_8_PORT                                        (GPIOB)
#define GPIO_Gray_PIN_Gray_8_PIN                                (DL_GPIO_PIN_20)
#define GPIO_Gray_PIN_Gray_8_IOMUX                               (IOMUX_PINCM48)
/* Port definition for Pin Group GPIO_Key */
#define GPIO_Key_PORT                                                    (GPIOA)

/* Defines for PIN_S2: GPIOA.21 with pinCMx 46 on package pin 39 */
#define GPIO_Key_PIN_S2_PIN                                     (DL_GPIO_PIN_21)
#define GPIO_Key_PIN_S2_IOMUX                                    (IOMUX_PINCM46)
/* Defines for PIN_S1: GPIOA.28 with pinCMx 3 on package pin 3 */
#define GPIO_Key_PIN_S1_PIN                                     (DL_GPIO_PIN_28)
#define GPIO_Key_PIN_S1_IOMUX                                     (IOMUX_PINCM3)


/* clang-format on */

void SYSCFG_DL_init(void);
void SYSCFG_DL_initPower(void);
void SYSCFG_DL_GPIO_init(void);
void SYSCFG_DL_SYSCTL_init(void);

bool SYSCFG_DL_SYSCTL_SYSPLL_init(void);
void SYSCFG_DL_PWM_0_init(void);
void SYSCFG_DL_TIMER_Encoder_Read_init(void);
void SYSCFG_DL_TIMER_0_init(void);
void SYSCFG_DL_I2C_MPU6050_init(void);
void SYSCFG_DL_UART_0_init(void);
void SYSCFG_DL_UART_JY61P_init(void);


bool SYSCFG_DL_saveConfiguration(void);
bool SYSCFG_DL_restoreConfiguration(void);

#ifdef __cplusplus
}
#endif

#endif /* ti_msp_dl_config_h */
