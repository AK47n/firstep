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

  * @日  期  2019-8-2

  * @内  容  OLED显示

  *

  ******************************************************************************

  */

  

/* Define to prevent recursive inclusion -------------------------------------*/

#ifndef __AX_OLED_H

#define __AX_OLED_H



/* Includes ------------------------------------------------------------------*/

#include "stm32f10x.h"

#include "ax_delay.h"







/*******X-SOFT软件生态 接口规范的代码共享软件生态 ******/



//OLED显示操作函数

void AX_OLED_Init(void);    //OLED初始化

void AX_OLED_DisplayOff(void);  //关闭OLED显示

void AX_OLED_DisplayOn(void);  //开启OLED显示 

void AX_OLED_RefreshScreen(void);   //OLED屏幕显示更新

void AX_OLED_ClearScreen(void);    //OLED清除屏幕



void AX_OLED_DisplayChar(uint8_t x, uint8_t y, uint8_t ch, uint8_t mode);    // OLED指定位置显示一个ASCII字符（6X12）

void AX_OLED_DisplayAsciiStr(uint8_t x, uint8_t y, uint8_t *ch, uint8_t mode);    //OLED指定位置显示ASCII字符串（6X12）

void AX_OLED_DisplayChinese(uint8_t x, uint8_t y, const uint8_t *pbuf, uint8_t mode);    //OLED指定位置显示一个汉字（6X12）

void AX_OLED_DisplayPicture(uint8_t x, uint8_t y, uint8_t xsize, uint8_t ysize, const uint8_t *pbuf, uint8_t mode);    //OLED指定位置显示一个指定尺寸图片

void AX_OLED_DisplayNum(uint8_t x, uint8_t y, uint8_t num, uint8_t mode);    //OLED指定位置显示一个数字（6X12）

void AX_OLED_DisplayValue(uint8_t x, uint8_t y, int32_t value, uint8_t inte, uint8_t deci, uint8_t mode);    //OLED指定位置显示数值



#endif



/******************* (C) 版权 2018 XTARK **************************************/

