/*
 * Copyright (c) 2021, Texas Instruments Incorporated
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

#include "ti_msp_dl_config.h"
#include <string.h>
volatile uint8_t gLED2State = 0;
char uartBuffer[64];
int main(void)
{
    SYSCFG_DL_init();
		NVIC_EnableIRQ(GPIO_GRP_KEY_INT_IRQN);



    while (1) {
    }
}
void uart_send_string(const char* str) {
    for(uint32_t i = 0; i < strlen(str); i++) {
        DL_UART_transmitDataBlocking(UART2, str[i]);
    }
}
void GROUP1_IRQHandler(void) {
    uint32_t intStatus = DL_GPIO_getEnabledInterruptStatus(GPIOB, 
                          GPIO_GRP_KEY_PIN_KEY1_PIN | GPIO_GRP_KEY_PIN_KEY2_PIN);

    if (intStatus & GPIO_GRP_KEY_PIN_KEY1_PIN) {
        DL_GPIO_clearInterruptStatus(GPIOB, GPIO_GRP_KEY_PIN_KEY1_PIN);

        if (DL_GPIO_readPins(GPIOB, GPIO_GRP_KEY_PIN_KEY1_PIN) == 0) {
            DL_GPIO_setPins(GPIOA, GPIO_GRP_LED_PIN_LED1_PIN);
            uart_send_string("LED1: ON!\r\n");
        } else {
            DL_GPIO_clearPins(GPIOA, GPIO_GRP_LED_PIN_LED1_PIN);
            uart_send_string("LED1: OFF!\r\n");
        }
    }

    if (intStatus & GPIO_GRP_KEY_PIN_KEY2_PIN) {
        DL_GPIO_clearInterruptStatus(GPIOB, GPIO_GRP_KEY_PIN_KEY2_PIN);

        DL_GPIO_togglePins(GPIOA, GPIO_GRP_LED_PIN_LED2_PIN);
        gLED2State = !gLED2State;
        
        if (gLED2State) {
            uart_send_string("LED2: ON!\r\n");
        } else {
            uart_send_string("LED2: OFF!\r\n");
        }
    }
}
