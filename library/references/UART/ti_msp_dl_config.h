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


#define CPUCLK_FREQ                                                     32000000



/* Defines for UART_2 */
#define UART_2_INST                                                        UART2
#define UART_2_INST_IRQHandler                                  UART2_IRQHandler
#define UART_2_INST_INT_IRQN                                      UART2_INT_IRQn
#define GPIO_UART_2_RX_PORT                                                GPIOA
#define GPIO_UART_2_TX_PORT                                                GPIOA
#define GPIO_UART_2_RX_PIN                                        DL_GPIO_PIN_22
#define GPIO_UART_2_TX_PIN                                        DL_GPIO_PIN_21
#define GPIO_UART_2_IOMUX_RX                                     (IOMUX_PINCM47)
#define GPIO_UART_2_IOMUX_TX                                     (IOMUX_PINCM46)
#define GPIO_UART_2_IOMUX_RX_FUNC                      IOMUX_PINCM47_PF_UART2_RX
#define GPIO_UART_2_IOMUX_TX_FUNC                      IOMUX_PINCM46_PF_UART2_TX
#define UART_2_BAUD_RATE                                                  (9600)
#define UART_2_IBRD_32_MHZ_9600_BAUD                                       (208)
#define UART_2_FBRD_32_MHZ_9600_BAUD                                        (21)





/* Port definition for Pin Group GPIO_GRP_LED */
#define GPIO_GRP_LED_PORT                                                (GPIOA)

/* Defines for PIN_LED1: GPIOA.7 with pinCMx 14 on package pin 49 */
#define GPIO_GRP_LED_PIN_LED1_PIN                                (DL_GPIO_PIN_7)
#define GPIO_GRP_LED_PIN_LED1_IOMUX                              (IOMUX_PINCM14)
/* Defines for PIN_LED2: GPIOA.10 with pinCMx 21 on package pin 56 */
#define GPIO_GRP_LED_PIN_LED2_PIN                               (DL_GPIO_PIN_10)
#define GPIO_GRP_LED_PIN_LED2_IOMUX                              (IOMUX_PINCM21)
/* Port definition for Pin Group GPIO_GRP_KEY */
#define GPIO_GRP_KEY_PORT                                                (GPIOB)

/* Defines for PIN_KEY1: GPIOB.15 with pinCMx 32 on package pin 3 */
// pins affected by this interrupt request:["PIN_KEY1","PIN_KEY2"]
#define GPIO_GRP_KEY_INT_IRQN                                   (GPIOB_INT_IRQn)
#define GPIO_GRP_KEY_INT_IIDX                   (DL_INTERRUPT_GROUP1_IIDX_GPIOB)
#define GPIO_GRP_KEY_PIN_KEY1_IIDX                          (DL_GPIO_IIDX_DIO15)
#define GPIO_GRP_KEY_PIN_KEY1_PIN                               (DL_GPIO_PIN_15)
#define GPIO_GRP_KEY_PIN_KEY1_IOMUX                              (IOMUX_PINCM32)
/* Defines for PIN_KEY2: GPIOB.16 with pinCMx 33 on package pin 4 */
#define GPIO_GRP_KEY_PIN_KEY2_IIDX                          (DL_GPIO_IIDX_DIO16)
#define GPIO_GRP_KEY_PIN_KEY2_PIN                               (DL_GPIO_PIN_16)
#define GPIO_GRP_KEY_PIN_KEY2_IOMUX                              (IOMUX_PINCM33)

/* clang-format on */

void SYSCFG_DL_init(void);
void SYSCFG_DL_initPower(void);
void SYSCFG_DL_GPIO_init(void);
void SYSCFG_DL_SYSCTL_init(void);
void SYSCFG_DL_UART_2_init(void);


bool SYSCFG_DL_saveConfiguration(void);
bool SYSCFG_DL_restoreConfiguration(void);

#ifdef __cplusplus
}
#endif

#endif /* ti_msp_dl_config_h */
