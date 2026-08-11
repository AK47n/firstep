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
例程名称：舵机控制例程
例程说明：控制8路舵机30度、90度、150度间隔运动
操作说明：可在8路舵机接口中任意一路插入舵机，舵机即可循环30°、90°、150°运动，
         如果插入多路舵机，或舵机负载扭矩大，请注意电源供电能力
*******************************************************************************/
int main(void)
{

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
	AX_OLED_DisplayAsciiStr(0, 0, "SERVO TEST", 0);	
	AX_OLED_RefreshScreen();
	
	//初始化
	AX_SERVO_Init();
	
	while (1) 
	{		
		AX_OLED_DisplayAsciiStr(0, 16, "ANG:30  ", 0);	
		AX_OLED_RefreshScreen();
		AX_SERVO_A_SetAngle(300);
		AX_SERVO_B_SetAngle(300);
		AX_Delayms(1000);
		
		AX_OLED_DisplayAsciiStr(0, 16, "ANG:90  ", 0);	
		AX_OLED_RefreshScreen();
		AX_SERVO_A_SetAngle(900);
		AX_SERVO_B_SetAngle(900);
		AX_Delayms(1000);
		
		AX_OLED_DisplayAsciiStr(0, 16, "ANG:150  ", 0);	
		AX_OLED_RefreshScreen();
		AX_SERVO_A_SetAngle(1500);
		AX_SERVO_B_SetAngle(1500);
		AX_Delayms(1000);
		
		AX_OLED_DisplayAsciiStr(0, 16, "ANG:90  ", 0);	
		AX_OLED_RefreshScreen();
		AX_SERVO_A_SetAngle(900);
		AX_SERVO_B_SetAngle(900);
		AX_Delayms(1000);
	}
}	

/******************* (C) 版权 2019 XTARK **************************************/
