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

  * @内  容  机器人控制主函数

  *

  ******************************************************************************

  */



/* Define to prevent recursive inclusion -------------------------------------*/

#ifndef __AX_ROBOT_H

#define __AX_ROBOT_H



/* Includes ------------------------------------------------------------------*/	 

#include "stm32f4xx.h"



//C库函数的相关头文件

#include <stdio.h> 

#include <stdint.h>

#include <stdlib.h>

#include <string.h>

#include <math.h>



//外设相关头文件

#include "ax_sys.h"      //系统设置

#include "ax_delay.h"    //软件延时

#include "ax_led.h"      //LED灯控制

#include "ax_beep.h"     //蜂鸣器控制

#include "ax_uart1.h"    //调试串口



#include "ax_motor.h"    //直流电机调速控制

#include "ax_encoder.h"  //编码器控制

#include "ax_servo.h"    //舵机控制



#include "ax_ps2.h"      //PS2手柄





//机器人轮子速度数据结构体

typedef struct  

{

	double  RT;       //车轮实时速度，单位m/s

	float  TG;       //车轮目标速度，单位m/s

	short  PWM;      //车轮PWM控制速度

	

}ROBOT_Wheel;



//机器人速度结构体

typedef struct  

{

	short  RT_IX;     //实时X轴速度（16位整数）

	short  RT_IY;     //实时Y轴速度（16位整数）

	short  RT_IW;     //实时Yaw旋转轴速度（16位整数）

	

	short  TG_IX;     //目标X轴速度（16位整数）

	short  TG_IY;     //目标Y轴速度（16位整数）

	short  TG_IW;     //目标Yaw旋转轴速度（16位整数）

	

	float  RT_FX;     //实时X轴速度（浮点）

	float  RT_FY;     //实时Y轴速度（浮点）

	float  RT_FW;     //实时Yaw旋转轴速度（浮点）

	

	float  TG_FX;     //目标X轴速度（浮点）

	float  TG_FY;     //目标Y轴速度（浮点）

	float  TG_FW;     //目标Yaw旋转轴速度（浮点）

	

}ROBOT_Velocity;



//杂类

#define  PI           3.1416     //圆周率PI

#define  SQRT3        1.732      //3开平方

#define  PID_RATE     50         //PID频率



/******机器人类型***********************************/



//机器人类型

#define ROBOT_MEC   0x01   //麦克纳姆轮底盘

#define ROBOT_FWD   0x02   //四轮差速底盘

#define ROBOT_TWD   0x03   //两轮差速转向底盘

#define ROBOT_AKM   0x04   //阿克曼转向底盘

#define ROBOT_OMT   0x05   //三轮全向底盘



//机器人定义类型

#define ROBOT_TYPE   ROBOT_FWD



/******机器人参数*************************************/



//麦轮机器人参数

#define  MEC_WHEEL_BASE           0.182	      //轮距，左右轮的距离

#define  MEC_ACLE_BASE            0.124       //轴距，前后轮的距离

#define  MEC_WHEEL_DIAMETER	      0.080		  //轮子直径

#define  MEC_WHEEL_RESOLUTION     1560.0      //编码器分辨率(13线),减速比30,13x30x4=1560

#define  MEC_WHEEL_SCALE          (PI*MEC_WHEEL_DIAMETER*PID_RATE/MEC_WHEEL_RESOLUTION) //轮子速度m/s与编码器转换系数



//四轮差速机器人参数

#define  FWD_WHEEL_BASE           0.162	     //轮距，左右轮的距离

#define  FWD_WB_SCALE             1.75       //轮距系数，轮距系数与机器人的总负载、轮胎与地面的相对摩擦系数、转弯半径及质心位置都是有关系是一个非常复杂的参数，所以常用的方法就是做实验

#define  FWD_WHEEL_DIAMETER	      0.065		 //轮子直径

#define  FWD_WHEEL_RESOLUTION     1560.0     //编码器分辨率(13线),减速比30,13x30x4=1560

#define  FWD_WHEEL_SCALE          (PI*FWD_WHEEL_DIAMETER*PID_RATE/FWD_WHEEL_RESOLUTION) //轮子速度m/s与编码器转换系数



//两轮差速机器人参数 

#define  TWD_WHEEL_DIAMETER	      0.0724	 //轮子直径

#define  TWD_WHEEL_BASE           0.206	     //轮距，左右轮的距离

#define  TWD_WHEEL_RESOLUTION     1560.0      //编码器分辨率(13线),减速比30,13x30x4=1560

#define  TWD_WHEEL_SCALE          (PI*TWD_WHEEL_DIAMETER*PID_RATE/TWD_WHEEL_RESOLUTION)  //轮子速度m/s与编码器转换系数



//阿克曼机器人参数

#define  AKM_WHEEL_BASE           0.165	     //轮距，左右轮的距离

#define  AKM_ACLE_BASE            0.175f     //轴距，前后轮的距离

#define  AKM_WHEEL_DIAMETER	      0.075		 //轮子直径

#define  AKM_WHEEL_RESOLUTION     1560.0      //编码器分辨率(13线),减速比30,13x30x4=1560

#define  AKM_TURN_R_MINI          0.35f      //最小转弯半径( L*cot30-W/2)

#define  AKM_WHEEL_SCALE          (PI*AKM_WHEEL_DIAMETER*PID_RATE/AKM_WHEEL_RESOLUTION)  //轮子速度m/s与编码器转换系数



//三轮全向机器人参数 

#define  OMT_WHEEL_DIAMETER	      0.058	     //轮子直径

#define  OMT_WHEEL_RADIUS         0.206	     //机器人半径，轮子与机器人中心距离

#define  OMT_WHEEL_RESOLUTION     1560.0     //编码器分辨率(13线),减速比30,13x30x4=1560

#define  OMT_WHEEL_SCALE          (PI*TWD_WHEEL_DIAMETER*PID_RATE/OMT_WHEEL_RESOLUTION)  //轮子速度m/s与编码器转换系数



/******机器人通信协议*************************************/



//串口通信帧头定义

#define  ID_UTX_DATA     0x10    //发送的综合数据

#define  ID_URX_VEL      0x50    //接收的速度数据



//机器人速度限制

#define R_VX_LIMIT  1500   //X轴速度限值 m/s*1000

#define R_VY_LIMIT  1200   //Y轴速度限值 m/s*1000

#define R_VW_LIMIT  6280   //W旋转角速度限值 rad/s*1000





//机器人关键全局变量

extern  ROBOT_Velocity  R_Vel; //机器人速度数据

extern  ROBOT_Wheel  R_Wheel_A,R_Wheel_B,R_Wheel_C,R_Wheel_D; //机器人轮子数据



extern uint8_t ax_robot_type;

extern uint8_t ax_robot_move_enable;



extern int16_t ax_motor_kp;    

extern int16_t ax_motor_kd; 



//阿克曼机器人

extern int16_t ax_akm_offset;

extern int16_t ax_akm_angle;



//PS2手柄键值结构体

extern JOYSTICK_TypeDef my_joystick;  



#endif



/******************* (C) 版权 2023 XTARK **************************************/

