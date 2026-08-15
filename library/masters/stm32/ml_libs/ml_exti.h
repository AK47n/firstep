#ifndef _ml_exti_h
#define _ml_exti_h
#include "headfile.h"

typedef enum
{
	EXTI_PA0,
	EXTI_PB0,
	EXTI_PC0,
	EXTI_PA1,
	EXTI_PB1,
	EXTI_PC1,
	EXTI_PA2,
	EXTI_PB2,
	EXTI_PC2,
	EXTI_PA3,
	EXTI_PB3,
	EXTI_PC3,
	EXTI_PA4,
	EXTI_PB4,
	EXTI_PC4,
	EXTI_PA5,
	EXTI_PB5,
	EXTI_PC5,
	EXTI_PA6,
	EXTI_PB6,
	EXTI_PC6,
	EXTI_PA7,
	EXTI_PB7,
	EXTI_PC7,
	EXTI_PA8,
	EXTI_PB8,
	EXTI_PC8,
	EXTI_PA9,
	EXTI_PB9,
	EXTI_PC9,
	EXTI_PA10,
	EXTI_PB10,
	EXTI_PC10,
	EXTI_PA11,
	EXTI_PB11,
	EXTI_PC11,
	EXTI_PA12,
	EXTI_PB12,
	EXTI_PC12,
	EXTI_PA13,
	EXTI_PB13,
	EXTI_PC13,
	EXTI_PA14,
	EXTI_PB14,
	EXTI_PC14,
	EXTI_PA15,
	EXTI_PB15,
	EXTI_PC15,

}EXTI_Pnx_enum;

typedef enum
{
	RISING,       //上升沿触发
	FALLING,      //下降沿触发
}EXTI_Trigger_enum;

void exti_init(EXTI_Pnx_enum pin,EXTI_Trigger_enum trigger,uint8_t priority);

#endif
