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

  * @内  容  编码器电机智能小车控制程序

  * 

  ******************************************************************************

  * @说  明

  *

  *  

  ******************************************************************************

  */



#include "stm32f4xx.h"

#include <stdio.h>



#include "ax_robot.h"

#include "ax_tim.h"    



#include "ax_kinematics.h"



/**

  * @简  述  机器人发送里程计数据

  * @参  数  无

  * @返回值  无

  */

void ROBOT_SendDataToRos(void)

{

    //串口发送数据

	static uint8_t comdata[6]; 	

	

	//机器人速度值 单位为m/s，放大1000倍

	comdata[0] = (u8)( R_Vel.RT_IX >> 8 );

	comdata[1] = (u8)( R_Vel.RT_IX );

	comdata[2] = (u8)( R_Vel.RT_IY >> 8 );

	comdata[3] = (u8)( R_Vel.RT_IY );

	comdata[4] = (u8)( R_Vel.RT_IW >> 8 );

	comdata[5] = (u8)( R_Vel.RT_IW );

	

	//USB串口发送数据

    AX_UART1_SendPacket(comdata, 6, ID_UTX_DATA);		

}



/**

  * @简  述  PS2手柄控制程序

  * @参  数  无

  * @返回值  无

  */

void ROBOT_PS2_Control(void)

{

	static uint8_t speed = 4;  //底盘速度

	

	//读取PS2手柄键值

	AX_PS2_ScanKey(&my_joystick);

	

	//红绿灯模式下，执行控制操作

	if(my_joystick.mode ==  0x73)

	{

		R_Vel.TG_IX = (int16_t)(speed*(0x80 - my_joystick.RJoy_UD));

		R_Vel.TG_IY = (int16_t)(speed*(0x80 - my_joystick.RJoy_LR));

		

		//如果是阿克曼机器人

		#if (ROBOT_TYPE == ROBOT_AKM)

			ax_akm_angle = (int16_t)(4*(0x80 - my_joystick.LJoy_LR));

		#else

			R_Vel.TG_IW = (int16_t)(4*speed*(0x80 - my_joystick.LJoy_LR));

		#endif	

	}

}



/**

  * @简  述  程序主函数

  * @参  数  无

  * @返回值  无

  */

int main(void)

{

	//设置中断优先级分组

	NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);    



	//舵机接口初始化

	AX_SERVO_S1_Init();

	AX_SERVO_S2_Init();

	

	//电机初始化，频率20KHZ

	AX_MOTOR_AB_Init();

	AX_MOTOR_CD_Init();

	

	//延时函数初始化

	AX_DELAY_Init();  

	

	//LED初始化

	AX_LED_Init();  

	

	//蜂鸣器初始化

	AX_BEEP_Init();    

	

	//调试串口初始化

	AX_UART1_Init(230400);

	

	//编码器初始化，

	AX_ENCODER_A_Init();  

	AX_ENCODER_B_Init();  

	AX_ENCODER_C_Init();  

	AX_ENCODER_D_Init(); 

	

	//PS2手柄初始化

	AX_PS2_Init();

	

	//定时器初始化

	AX_TIM7_Init(20000);//设置定时器周期定时时间

    AX_TIM7_Cmd(ENABLE);//定时器使能

	

	while (1)

	{	

		//执行周期（20ms）50Hz

		if(AX_TIM7_CheckIrqStatus())

		{

			//PS2手柄控制处理

			ROBOT_PS2_Control();	

			

			//机器人运动学处理

			AX_ROBOT_Kinematics();	



			//里程计数据发送

			ROBOT_SendDataToRos();		

			

			//LED反转

			AX_LED_Green_Toggle();			

		}

	}

}



/******************* (C) 版权 2023 XTARK *******************************/

