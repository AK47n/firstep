/**

  ******************************************************************************

  * @file    ax_timer_int.c

  * @author  Musk Han @ XTARK

  * @version V1.0

  * @date    2018-01-01

  * @brief   X-CTR100 定时器计数溢出中断文件

  *

  ******************************************************************************

  * @xtark  实验平台：塔克出品 X-CTR100 控制器

  *         塔克官网社区：http://www.xtark.cn

  * 

  ******************************************************************************

  */  



#include "ax_tim.h" 



//中断循环状态控制标志位

uint8_t ax_flag_tim = 0;



/**

  * @简  述  TIM定时器初始化（溢出中断）

  * @参  数  cnt_us 设置溢出计数值，单位1us，范围0-65535 

  * @返回值  无

  */

void AX_TIM_Init(uint16_t cnt_us)

{

	TIM_TimeBaseInitTypeDef TIM_TimeBaseInitStructure;

	NVIC_InitTypeDef NVIC_InitStructure; 



	RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM4, ENABLE); //时钟使能

	

  // 累计 TIM_Period个后产生一个更新或者中断

	TIM_TimeBaseInitStructure.TIM_Period = cnt_us-1;  //自动重装载值，最大65535

	// 设定定时器频率为=TIMxCLK/(TIM_Prescaler+1)=1000000Hz

	TIM_TimeBaseInitStructure.TIM_Prescaler = 72-1; //定时器分频,计数周期（period x 1us）

	TIM_TimeBaseInitStructure.TIM_CounterMode=TIM_CounterMode_Up; //向上计数模式

	TIM_TimeBaseInitStructure.TIM_ClockDivision=TIM_CKD_DIV1;

	

	TIM_TimeBaseInit(TIM4, &TIM_TimeBaseInitStructure); //根据指定的参数初始化TIMx的时间基数单位

 

	TIM_ITConfig(TIM4,TIM_IT_Update,ENABLE ); //使能指定的TIM中断,允许更新中断



	//中断优先级NVIC设置

	NVIC_InitStructure.NVIC_IRQChannel = TIM4_IRQn;  //TIM中断

	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 0;  //先占优先级0级

	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 3;  //从优先级3级

	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE; //IRQ通道被使能

	NVIC_Init(&NVIC_InitStructure);  //初始化NVIC寄存器



	TIM_Cmd(TIM4, ENABLE);  //使能TIMx					 

}





/**

  * @简  述  TIM 定时器开启关闭

  * @参  数  NewState  This parameter can be: ENABLE or DISABLE.

  * @返回值  无

  */

void AX_TIM_Cmd(FunctionalState NewState)

{

	TIM_SetCounter(TIM4, 0);

	TIM_Cmd(TIM4, NewState);

}



/**

  * @简  述  TIM 中断处理函数

  * @参  数  无

  * @返回值  无

  */

void  TIM4_IRQHandler(void)

{

	if ( TIM_GetITStatus( TIM4, TIM_IT_Update) != RESET ) 

	{	

		//中断处理内容

		ax_flag_tim = 1;  //置位10ms标志位

		

		TIM_ClearITPendingBit(TIM4 , TIM_IT_Update);  		 

	}		 	

}



/**

  * @brief  检测是否产生中断

  * @param  None

  * @retval None

  */

uint8_t AX_TIM_CheckIrqStatus(void)

{

	//确认中断,进入控制周期

	if(ax_flag_tim != 0) 

	{

		ax_flag_tim = 0;

		return 1;

	}

	else

	{

		return 0;

	}

}





/******************* (C) 版权 2018 XTARK **************************************/

