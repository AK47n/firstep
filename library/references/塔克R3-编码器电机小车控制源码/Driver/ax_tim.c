/**			                                                    

		   ____                    _____ _______ _____       XTARK@塔克创新

		  / __ \                  / ____|__   __|  __ \ 

		 | |  | |_ __   ___ _ __ | |       | |  | |__) |

		 | |  | | '_ \ / _ \ '_ \| |       | |  |  _  / 

		 | |__| | |_) |  __/ | | | |____   | |  | | \ \ 

		  \____/| .__/ \___|_| |_|\_____|  |_|  |_|  \_\

				| |                                     

				|_|                OpenCTR   机器人控制器

									 

  ****************************************************************************** 

  *           

  * 版权所有： XTARK@塔克创新  版权所有，盗版必究

  * 公司网站： www.xtark.cn   www.tarkbot.com

  * 淘宝店铺： https://xtark.taobao.com  

  * 塔克微信： 塔克创新（关注公众号，获取最新更新资讯）

  *      

  ******************************************************************************

  * @作  者  塔克创新团队

  * @内  容  TIM7定时器产生控制周期

  *

  ******************************************************************************

  * @说  明

  *

  * TIM7定时器终于产生定时信号，通过标志位判断的函数传递

  * 

  ******************************************************************************

  */



#include "ax_tim.h" 



//中断循环状态控制标志位

uint8_t flag_tim7 = 0;



/**

  * @简  述  TIM7 定时器初始化（溢出中断）

  * @参  数  cnt_us 设置溢出计数值，单位1us，范围0-65535 

  * @返回值  无

  */

void AX_TIM7_Init(uint16_t cnt_us)

{ 

	TIM_TimeBaseInitTypeDef TIM_TimeBaseInitStructure;

	NVIC_InitTypeDef NVIC_InitStructure; 



	RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM7,ENABLE); //使能时钟

	

	 // 累计 TIM_Period个后产生一个更新或者中断

	TIM_TimeBaseInitStructure.TIM_Period = cnt_us-1;  //自动重装载值，最大65535

	TIM_TimeBaseInitStructure.TIM_Prescaler = 84-1; //定时器分频,计数周期（period x 1us）

	TIM_TimeBaseInitStructure.TIM_CounterMode=TIM_CounterMode_Up; //向上计数模式

	TIM_TimeBaseInitStructure.TIM_ClockDivision=TIM_CKD_DIV1;

	TIM_TimeBaseInit(TIM7,&TIM_TimeBaseInitStructure); //初始化定时器

	

	//清除定时器更新中断标志位

	TIM_ClearFlag(TIM7, TIM_FLAG_Update);

	

	//开启定时器更新中断

	TIM_ITConfig(TIM7, TIM_IT_Update, ENABLE);

	

	TIM_Cmd(TIM7, ENABLE); //使能定时器 

	

	// 设置中断来源

	NVIC_InitStructure.NVIC_IRQChannel = TIM7_IRQn; 	

	NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 2;	 	// 设置抢占优先级

	NVIC_InitStructure.NVIC_IRQChannelSubPriority = 1;		// 设置子优先级

	NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;

	NVIC_Init(&NVIC_InitStructure);

}



/**

  * @简  述  TIM7 定时器开启关闭

  * @参  数  NewState  This parameter can be: ENABLE or DISABLE.

  * @返回值  无

  */

void AX_TIM7_Cmd(FunctionalState NewState)

{

	TIM_SetCounter(TIM7, 0);

	TIM_Cmd(TIM7, NewState);

}



/**

  * @简  述  TIM7 中断处理函数

  * @参  数  无

  * @返回值  无

  */

void  TIM7_IRQHandler(void)

{

	if ( TIM_GetITStatus( TIM7, TIM_IT_Update) != RESET ) 

	{	

		//中断处理内容

		flag_tim7 = 1;  //置位标志位

		

		TIM_ClearITPendingBit(TIM7 , TIM_IT_Update);  		 

	}		 	

}



/**

  * @brief  检测是否产生中断

  * @param  None

  * @retval None

  */

uint8_t AX_TIM7_CheckIrqStatus(void)

{

	//确认中断,进入控制周期

	if(flag_tim7 != 0) 

	{

		flag_tim7 = 0;

		return 1;

	}

	else

	{

		return 0;

	}

}



/******************* (C) 版权 2023 XTARK **************************************/

