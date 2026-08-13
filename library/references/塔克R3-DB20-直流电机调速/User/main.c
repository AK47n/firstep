/**

	 __  _______  _    ____  _  __      __  __    ____   ___  _____ _____ 

	 \ \/ /_   _|/ \  |  _ \| |/ / 塔   \ \/ /   / ___| / _ \|  ___|_   _| 软

	  \  /  | | / _ \ | |_) | ' /  克    \  /____\___ \| | | | |_    | |   件

	  /  \  | |/ ___ \|  _ <| . \  创    /  \_____|__) | |_| |  _|   | |   生

	 /_/\_\ |_/_/   \_\_| \_\_|\_\ 新   /_/\_\   |____/ \___/|_|     |_|   态

                              

  ******************************************************************************

  * 

  * 版权所有： XTARK@塔克创新  版权所有，盗版必究

  * 官网网站： www.xtark.cn

  * 淘宝店铺： https://shop246676508.taobao.com  

  * 塔克媒体： www.cnblogs.com/xtark（博客）

	* 塔克微信： 微信公众号：塔克创新（获取最新资讯）

  *                              

  ******************************************************************************

  * @作  者  Musk Han@XTARK

  * @版  本  V1.0

  * @日  期  2019-7-26

  * @内  容  主程序

  *

  ******************************************************************************

  * @说  明

  *

  ******************************************************************************

  */



/* Includes ------------------------------------------------------------------*/

#include "stm32f10x.h"

#include <stdio.h>



#include "ax_sys.h"    //系统设置

#include "ax_delay.h"  //软件延时

#include "ax_led.h"  //LED灯控制

#include "ax_key.h"  //按键检测

#include "ax_vin.h"  //输入电压检测

#include "ax_uart_db.h"  //调试串口，USB串口	

#include "ax_motor.h"   //直流电机驱动

#include "ax_encoder.h"  //编码器驱动	

#include "ax_servo.h"   //舵机驱动



#include "ax_oled.h"  //OLED显示

#include "ax_oled_chinese.h" //汉字字模数据

#include "ax_oled_picture.h" //图片数据



/******************************************************************************

例程名称：直流电机PWM调速控制

例程说明：控制电机变速正传和变速反转交替运行

操作说明：电机可连接至DB20电机学习板，可以看到电机做间隔的增速正转和反转

*******************************************************************************/

int main(void)

{

	uint16_t temp;

	

	//设置中断优先级分组

	NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);  

	

	//调试串口初始化

	AX_UART_DB_Init(115200); //调试串口

	printf("  \r\n"); //输出空格，CPUBUG

	

	//JTAG口设置

	AX_JTAG_Set(JTAG_SWD_DISABLE);  //关闭JTAG接口 

	AX_JTAG_Set(SWD_ENABLE);  //打开SWD接口 可以利用主板的SWD接口调试 		

	

	//软件延时初始化

	AX_DELAY_Init(); 	

  AX_LED_Init();  

	

	//OLED初始化及配置

	AX_OLED_Init();

	AX_OLED_DisplayAsciiStr(0, 0, "MOTOR TEST", 0);	

	AX_OLED_DisplayAsciiStr(0, 16, "SPD:", 0);	

	AX_OLED_RefreshScreen();

	

	//初始化+

	AX_MOTOR_Init(10);  //设置电机控制PWM频率为10K

	

	while (1) 

	{	

		//控制电机转动

		for(temp=0; temp<=100; temp++)

		{

			AX_MOTOR_SetSpeed(temp*20);  

			AX_Delayms(100);

			AX_OLED_DisplayValue(24, 16, (temp*20), 5, 0, 0);  //显示数值

			AX_OLED_RefreshScreen();			

		}

		AX_Delayms(1000);

		AX_MOTOR_SetSpeed(0); 

		AX_Delayms(3000);

		

		//控制电机反向转动

		for(temp=0; temp<=100; temp++)

		{

			AX_MOTOR_SetSpeed(-temp*20);  

			

			AX_Delayms(100);

			AX_OLED_DisplayValue(24, 16, (-temp*20), 5, 0, 0);  //显示数值

			AX_OLED_RefreshScreen();			

		}

		AX_Delayms(1000);

		AX_MOTOR_SetSpeed(0); 

		AX_Delayms(3000);

		

	}

}	



/******************* (C) 版权 2019 XTARK **************************************/

