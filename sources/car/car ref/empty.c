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

#include "ti/devices/msp/m0p/mspm0g350x.h"
#include "ti_msp_dl_config.h"
#include "control.h"
#include "JY61P.h"
#include "Delay.h"


int main(void)
{
    uint8_t a=5;
    SYSCFG_DL_init();

    NVIC_EnableIRQ(TIMER_Encoder_Read_INST_INT_IRQN);                  //开启定时器
    NVIC_EnableIRQ(TIMER_0_INST_INT_IRQN);
    NVIC_EnableIRQ(GPIO_EncoderA_INT_IRQN);
    NVIC_EnableIRQ(GPIO_EncoderB_INT_IRQN);
    DL_Timer_startCounter(TIMER_Encoder_Read_INST);
    DL_Timer_startCounter(TIMER_0_INST);
    DL_Timer_startCounter(PWM_0_INST);                 //pwm定时器初始化
    NVIC_EnableIRQ(UART_JY61P_INST_INT_IRQN);           //使能中断

    Serial_JY61P_Zero_Yaw();

    int mode=0;
    int begin=0;
    //DL_GPIO_clearPins(GPIO_STBY_PORT,GPIO_STBY_PIN_STBY_PIN);
    DL_GPIO_setPins(GPIO_STBY_PORT,GPIO_STBY_PIN_STBY_PIN);
    while (1)
    {
        if(!DL_GPIO_readPins(GPIO_Key_PORT, GPIO_Key_PIN_S2_PIN))
        {
            Delay_ms(10);
            if(!DL_GPIO_readPins(GPIO_Key_PORT, GPIO_Key_PIN_S2_PIN))
            {
                 mode = (mode + 1)%4;
            }
            while(!DL_GPIO_readPins(GPIO_Key_PORT, GPIO_Key_PIN_S2_PIN));
        }
        else if(!DL_GPIO_readPins(GPIO_Key_PORT, GPIO_Key_PIN_S1_PIN))
        {
            Delay_ms(10);
            if(!DL_GPIO_readPins(GPIO_Key_PORT, GPIO_Key_PIN_S1_PIN))
            {
                Delay_ms(1000);
                DL_GPIO_setPins(GPIO_STBY_PORT,GPIO_STBY_PIN_STBY_PIN);
                begin=1;
            }
            while(!DL_GPIO_readPins(GPIO_Key_PORT, GPIO_Key_PIN_S1_PIN));
        }

        if (mode==0)
        {
            if (begin==1)
            {
                Control_AB();
            }
        }
        else if(mode==1)
        {
            if (begin==1)
            {
                Control_ABCDA();
            }
        }
        else if(mode==2)
        {
            if (begin==1)
            {
                Control_ACBDA();
            }
        }
        else if(mode==3)
        {
            if (begin==1)
            {
                Control_ACBDAx4();
            }
        }
    }
}


// /*********************串口重定向********************/
// int fputc(int c, FILE* stream)
// {
// 	DL_UART_Main_transmitDataBlocking(UART_0_INST, c);
//     return c;
// }

// int fputs(const char* restrict s, FILE* restrict stream)
// {
//     uint16_t i, len;
//     len = strlen(s);
//     for(i=0; i<len; i++)
//     {
//         DL_UART_Main_transmitDataBlocking(UART_0_INST, s[i]);           //发送完成后执行后续程序    串口0
//     }
//     return len;
// }

// int puts(const char *_ptr)
// {
//     int count = fputs(_ptr ,stdout);
//     count += fputs("\n",stdout);
//     return count;
// }
// /**********************************************************************************/
