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
  ******************************************************************************
  *  PID速度控制程序
	*  通过OLED显示屏查看PID参数，当前速度和目标速度
	*  通过X-PrintfScope软件查看当前速度和目标速度的曲线
	*  通过X-PrintfScope软件可以设定目标速度和PID参数
	*  具体操作请参考说明手册
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
#include "ax_tim.h" //定时器

#define PID_SCALE  0.01f  //PID缩放系数

//编码器控制
int16_t ax_encoder;	//编码器绝对值
int16_t ax_encoder_delta;	//编码器相对变化值,代表实际速度
int16_t ax_encoder_delta_target = 10; //编码器目标值，代表目标速度
int16_t ax_motor_pwm;  //电机PWM速度

//PID参数
int16_t ax_motor_kp=300;  
int16_t ax_motor_ki=0;    
int16_t ax_motor_kd=0;  

void AX_UART_DB_Unpack(uint8_t *comdata);
int16_t PID_MotorVelocityPidCtl(int16_t spd_target, int16_t spd_current);

int main(void)
{
	uint8_t cnt = 1;  //周期计数变量
	uint8_t comdata[32];
	
	AX_Delayms(500);
	
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
  AX_KEY_Init();	
	
	//OLED初始化及配置
	AX_OLED_Init();
	AX_OLED_DisplayAsciiStr(0, 0, "  PID SPEED CONTROL", 0);
	AX_OLED_DisplayAsciiStr(0, 13, "KP:", 0);	
	AX_OLED_DisplayAsciiStr(64, 13, "KI:", 0);	
	AX_OLED_DisplayAsciiStr(0, 26, "KD:", 0);	
	AX_OLED_DisplayAsciiStr(0, 39, "SPD TARGET :", 0);	
	AX_OLED_DisplayAsciiStr(0, 52, "SPD CURRENT:", 0);	
	AX_OLED_RefreshScreen();
	
	//电机初始化
	AX_MOTOR_Init(10);

	//正交编码器初始化
  AX_ENCODER_Init(60000);  
	//设定中间值30000
	AX_ENCODER_SetCounter(30000); 
	
	//定时器初始化
	AX_TIM_Init(10000);//设置定时器周期定时时间，10ms
  AX_TIM_Cmd(ENABLE);//定时器使能
	
	while (1) 
	{		
		//执行周期（10ms）100Hz
		if(AX_TIM_CheckIrqStatus())
		{
			//执行周期（40ms）25HZ
			if(cnt%4 == 0)
			{
				//计算编码器速度
				ax_encoder_delta = (AX_ENCODER_GetCounter()-30000);
				//设置编码器初始中间值
				AX_ENCODER_SetCounter(30000);				
				
				//PID控制
				ax_motor_pwm = PID_MotorVelocityPidCtl(ax_encoder_delta_target, ax_encoder_delta);   
				
				//电机执行动作
				AX_MOTOR_SetSpeed(-ax_motor_pwm);
				
				//接收串口指令
				if( AX_UART_DB_GetRxData(comdata))
				{
					AX_UART_DB_Unpack(comdata);	//控制数据解析
				}
				
				//发送目标值和当前值数据
				comdata[0] = (u8)( ax_encoder_delta >> 8 );
				comdata[1] = (u8)( ax_encoder_delta );
				comdata[2] = (u8)( ax_encoder_delta_target >> 8 );
				comdata[3] = (u8)( ax_encoder_delta_target );
				AX_UART_DB_SendPacket(comdata, 4, 0x01);	
				
				//检测是否按下保护按键
				if(AX_KEYA_Scan() == 1)
				{
					//目标值为0，PID恢复默认参数
					ax_encoder_delta_target = 0;
					ax_motor_kp=300;  
					ax_motor_ki=0;    
					ax_motor_kd=0;  
				}
			}
			
			//执行周期（200ms）
			if(cnt%20 == 1)  
			{
				//OLED显示更新
				AX_OLED_DisplayValue(18, 13, ax_motor_kp, 5, 0, 0);  //KP 
				AX_OLED_DisplayValue(82, 13, ax_motor_ki, 5, 0, 0);  //KI
				AX_OLED_DisplayValue(18, 26, ax_motor_kd, 5, 0, 0);  //KD
				AX_OLED_DisplayValue(72, 39, ax_encoder_delta_target, 5, 0, 0);  //目标速度
				AX_OLED_DisplayValue(72, 52, ax_encoder_delta, 5, 0, 0);  //当前速度
			  AX_OLED_RefreshScreen();			

				AX_LED_Green_Toggle();				
			}
			
			//更新周期计数
			if(cnt != 200)
				cnt++;
			else
				cnt = 1;			
		}
	}
}	

/**
  * @简  述   PID控制函数
  * @参  数   spd_target:编码器速度目标值 ,范围（±250）
  *           spd_current: 编码器速度当前值
  * @返回值  电机PWM速度
  */
int16_t PID_MotorVelocityPidCtl(int16_t spd_target, int16_t spd_current)
{
	static int16_t motor_pwm_out;
	static int32_t bias,bias_last,bias_integral = 0;
	
	bias = spd_target - spd_current;
	
	bias_integral += bias;
	
	motor_pwm_out += ax_motor_kp*bias*PID_SCALE + ax_motor_kd*(bias-bias_last)*PID_SCALE + ax_motor_ki*bias_integral*PID_SCALE;
	
	bias_last = bias;	
	
	return motor_pwm_out;
}	

/**
  * @简  述  树串口数据解析
  * @参  数  comdata 串口通信数据
  * @返回值  无
  */
void AX_UART_DB_Unpack(uint8_t *comdata)
{	
	//ID=1，设定电机目标速度，范围±250
	if(comdata[0] == 0x01)
	{
		ax_encoder_delta_target = (int16_t)((comdata[1]<<8) | comdata[2]);
	}
	
	//其它命令
	else
	{
		//ID=2，设置PID参数
		if(comdata[0] == 0x02)
		{
			ax_motor_kp = (int16_t)((comdata[1]<<8) | comdata[2]);
			ax_motor_ki = (int16_t)((comdata[3]<<8) | comdata[4]);
			ax_motor_kd = (int16_t)((comdata[5]<<8) | comdata[6]);
		}
	}
}


/******************* (C) 版权 2019 XTARK **************************************/
