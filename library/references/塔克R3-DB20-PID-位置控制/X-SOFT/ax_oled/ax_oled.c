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

  * @说  明

  *

  * 1.OLED为无字库128x64模组，驱动芯片为SSD1306，SPI驱动

  * 2.英文ASCII字符显示无须自己取模，已取模完成16X8规格，见ax_oled_ascii.h

  * 3.汉字和图片，需要用户自己取模，汉字规格16X16

  * 4.支持数字数值直接显示，可显示小数

  * 5.所有显示，字符、汉字、数字、图片均支持反色显示

  * 

  ******************************************************************************

  */

 

#include "ax_oled.h"

#include "ax_oled_ascii.h"





//OLED信号定义

#define OLED_DC_L()    GPIO_ResetBits(GPIOA,GPIO_Pin_15)

#define OLED_DC_H()    GPIO_SetBits(GPIOA,GPIO_Pin_15)



#define OLED_RST_L()   GPIO_ResetBits(GPIOB,GPIO_Pin_4)

#define OLED_RST_H()   GPIO_SetBits(GPIOB,GPIO_Pin_4)



static uint8_t SPI1_Send_Byte(uint8_t dat);

static void OLED_WriteCmd(u8 data);

static void OLED_WriteData(u8 data);

static void OLED_DrawPoint(u8 x,u8 y,u8 t);

u8 OLED_GRAM[128][8];



/**

  * @简  述  OLED初始化

  * @参  数  无	  

  * @返回值  无

  */

void AX_OLED_Init(void)

{

	SPI_InitTypeDef  SPI_InitStructure;

	GPIO_InitTypeDef GPIO_InitStructure;

	

		//使配置GPIO

 	RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOB|RCC_APB2Periph_GPIOA|RCC_APB2Periph_AFIO,ENABLE);

  GPIO_PinRemapConfig(GPIO_Remap_SPI1, ENABLE);

//	GPIO_PinRemapConfig(GPIO_Remap_SWJ_JTAGDisable, ENABLE);

	//配置SPI的SCK MOSI引脚

	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_3 | GPIO_Pin_5;

	GPIO_InitStructure.GPIO_Speed = GPIO_Speed_50MHz;

	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_AF_PP;

	GPIO_Init(GPIOB, &GPIO_InitStructure);	

	//DC 

	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_4;

	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;

	GPIO_Init(GPIOB, &GPIO_InitStructure);

	

	//CS

	GPIO_InitStructure.GPIO_Pin = GPIO_Pin_15;

	GPIO_InitStructure.GPIO_Mode = GPIO_Mode_Out_PP;

	GPIO_Init(GPIOA, &GPIO_InitStructure);

	

	

	//配置 SPI 接口

	RCC_APB2PeriphClockCmd(RCC_APB2Periph_SPI1, ENABLE);

	

	SPI_InitStructure.SPI_Direction = SPI_Direction_2Lines_FullDuplex;    //设置SPI单向或者双向的数据模式:SPI设置为双线双向全双工

	SPI_InitStructure.SPI_Mode = SPI_Mode_Master;		                  //设置SPI工作模式:设置为主SPI

	SPI_InitStructure.SPI_DataSize = SPI_DataSize_8b;		              //设置SPI的数据大小:SPI发送接收8位帧结构

	SPI_InitStructure.SPI_CPOL = SPI_CPOL_High;		                      //选择了串行时钟的稳态:时钟悬空高

	SPI_InitStructure.SPI_CPHA = SPI_CPHA_2Edge;	                      //数据捕获于第二个时钟沿

	SPI_InitStructure.SPI_NSS = SPI_NSS_Soft;		                      //NSS信号由硬件（NSS管脚）还是软件（使用SSI位）管理:内部NSS信号有SSI位控制

	SPI_InitStructure.SPI_BaudRatePrescaler = SPI_BaudRatePrescaler_2;    //定义波特率预分频的值:波特率预分频值为256

	SPI_InitStructure.SPI_FirstBit = SPI_FirstBit_MSB;	                  //指定数据传输从MSB位还是LSB位开始:数据传输从MSB位开始

	SPI_InitStructure.SPI_CRCPolynomial = 7;	                          //CRC值计算的多项式

//SPI_RxFIFOThresholdConfig(SPI1, SPI_RxFIFOThreshold_QF);



	SPI_Init(SPI1, &SPI_InitStructure);



	/* Enable SPI1  */

	SPI_Cmd(SPI1, ENABLE);//使能SPI外设



	SPI1_Send_Byte(0xff);//启动传输

	

	//OLED_CS_L();



	OLED_RST_H();

	AX_Delayms(100);

	OLED_RST_L();

	AX_Delayms(200);

	OLED_RST_H(); 

					  

	

	OLED_WriteCmd(0xAE); //关闭显示

	OLED_WriteCmd(0xD5); //设置时钟分频因子,震荡频率

	OLED_WriteCmd(80);   //[3:0],分频因子;[7:4],震荡频率

	OLED_WriteCmd(0xA8); //设置驱动路数

	OLED_WriteCmd(0X3F); //默认0X3F(1/64) 

	OLED_WriteCmd(0xD3); //设置显示偏移

	OLED_WriteCmd(0X00); //默认为0



	OLED_WriteCmd(0x40); //设置显示开始行 [5:0],行数.

													    

	OLED_WriteCmd(0x8D); //电荷泵设置

	OLED_WriteCmd(0x14); //bit2，开启/关闭

	OLED_WriteCmd(0x20); //设置内存地址模式

	OLED_WriteCmd(0x02); //[1:0],00，列地址模式;01，行地址模式;10,页地址模式;默认10;

	OLED_WriteCmd(0xA1); //段重定义设置,bit0:0,0->0;1,0->127;

	OLED_WriteCmd(0xC0); //设置COM扫描方向;bit3:0,普通模式;1,重定义模式 COM[N-1]->COM0;N:驱动路数

	OLED_WriteCmd(0xDA); //设置COM硬件引脚配置

	OLED_WriteCmd(0x12); //[5:4]配置

		 

	OLED_WriteCmd(0x81); //对比度设置

	OLED_WriteCmd(0xEF); //1~255;默认0X7F (亮度设置,越大越亮)

	OLED_WriteCmd(0xD9); //设置预充电周期

	OLED_WriteCmd(0xf1); //[3:0],PHASE 1;[7:4],PHASE 2;

	OLED_WriteCmd(0xDB); //设置VCOMH 电压倍率

	OLED_WriteCmd(0x30); //[6:4] 000,0.65*vcc;001,0.77*vcc;011,0.83*vcc;



	OLED_WriteCmd(0xA4); //全局显示开启;bit0:1,开启;0,关闭;(白屏/黑屏)

	OLED_WriteCmd(0xA6); //设置显示方式;bit0:1,反相显示;0,正常显示	    						   

	OLED_WriteCmd(0xAF); //开启显示	 

	

	AX_OLED_ClearScreen();

}



/**

  * @简  述  开启OLED显示 

  * @参  数  无

  * @返回值	 无

  */

void AX_OLED_Display_On(void)

{

	OLED_WriteCmd(0X8D);  //SET DCDC命令

	OLED_WriteCmd(0X14);  //DCDC ON

	OLED_WriteCmd(0XAF);  //DISPLAY ON

}

/**

  * @简  述  关闭OLED显示 

  * @参  数  无

  * @返回值	 无

  */

void AX_OLED_Display_Off(void)

{

	OLED_WriteCmd(0X8D);  //SET DCDC命令

	OLED_WriteCmd(0X10);  //DCDC OFF

	OLED_WriteCmd(0XAE);  //DISPLAY OFF

}	

/**

  * @简  述  OLED屏幕显示更新

  * @参  数  无

  * @返回值	 无

  */

void AX_OLED_RefreshScreen(void)

{

	u8 i,n;		    

	for(i=0;i<8;i++)  

	{  

		OLED_WriteCmd (0xb0+i);    //设置页地址（0~7）

		OLED_WriteCmd (0x00);      //设置显示位置—列低地址

		OLED_WriteCmd (0x10);      //设置显示位置—列高地址   

		for(n=0;n<128;n++)

			OLED_WriteData(OLED_GRAM[n][i]); 

	}   

}

/**

  * @简  述  OLED屏幕清除

  * @参  数  无

  * @返回值	 无

  */

//清完屏,整个屏幕是黑色的!和没点亮一样!!!	  

void AX_OLED_ClearScreen(void)  

{  

	u8 i,n;  

	for(i=0;i<8;i++)for(n=0;n<128;n++)

		OLED_GRAM[n][i]=0X00;  

	AX_OLED_RefreshScreen();//更新显示

}



/**

  * @简  述  OLED指定位置显示一个ASCII字符（6X12）

  * @参  数  x：横坐标 0~120，超出范围不显示

  *          y：纵坐标 0~6，超出范围不显示

	*          ch：显示字符 

  *          mode：显示模式，0-正常显示，1-反白显示

  * @返回值	 

  */

void AX_OLED_DisplayChar(uint8_t x, uint8_t y, uint8_t ch, uint8_t mode)

{      			    

	u8 temp,t,t1;

	u8 y0=y;

	ch=ch-' ';//得到偏移后的值	

	

	for(t=0;t<12;t++)

	{

		temp=ASCII6X12[ch][t];  //调用1206字体

		

		for(t1=0;t1<8;t1++)

	  {

			if(temp&0x80)

				OLED_DrawPoint(x,y,!mode);

			else 

				OLED_DrawPoint(x,y,mode);

			

			temp<<=1;

			y++;

			

			if((y-y0)==12)

			{

				y=y0;

				x++;

				break;

			}

		}  	 

	}          

}

	

/**

  * @简  述  OLED指定位置显示ASCII字符串（6X12）,自动换行。

  * @参  数  x：横坐标 0~120，超出范围不显示

  *          y：纵坐标 0~52，超出范围不显示

  *          p：字符串指针

  *          mode：显示模式，0-正常显示，1-反白显示

  * @返回值	 

  */

void AX_OLED_DisplayAsciiStr(uint8_t x, uint8_t y, uint8_t *ch, uint8_t mode)

{

	

	uint8_t j=0;

	

	if((x<123) && (y<58))

	{

		while (ch[j]!='\0')

		{

			AX_OLED_DisplayChar(x, y, ch[j], mode);

			x+=6;

			

			if(x>122)

			{

				x=0;

				y+=12;  //当y>6时，超出部分不再显示

			}

			j++;

		}				

	}

}	   



/**

  * @简  述  OLED指定位置显示一个汉字（12X12）

  * @参  数  x：横坐标 0~112，超出范围不显示

  *          y：纵坐标 0~6，超出范围不显示

  *          pbuf：汉字编码数据指针

  *          mode：显示模式，0-正常显示，1-反白显示

  * @返回值	 

  */      	

void AX_OLED_DisplayChinese(uint8_t x, uint8_t y, const uint8_t *pbuf, uint8_t mode)

{                   

    u16 temp,t,t1;

    u8 y0=y; 	

	

    for(t=0;t<24;t++)

    {   

        temp=pbuf[t];                                  

        for(t1=0;t1<8;t1++)

        {

            if(temp&0x80)

				OLED_DrawPoint(x,y,!mode);

            else 

				OLED_DrawPoint(x,y,mode);

            temp<<=1;

            y++;

						

            if((y-y0)==12)

            {

                y=y0;

                x++;

                break;

            }

        }    

    } 

}



/**

  * @简  述  OLED指定位置显示一个数字（8X16）

  * @参  数  x：横坐标 0~120，超出范围不显示

  *          y：纵坐标 0~6，超出范围不显示

  *          num：显示的数字

  *          mode：显示模式，0-正常显示，1-反白显示

  * @返回值	 

  */

void AX_OLED_DisplayNum(uint8_t x, uint8_t y, uint8_t num, uint8_t mode)    //显示单个数字

{

	if(num < 10) 

	{	

		AX_OLED_DisplayChar(x, y, ('0'+num), mode);

	}

}

 

/**

  * @简  述  OLED指定位置显示数值（可显示负数）

  * @参  数  x：横坐标 0~120，超出范围不显示

  *          y：纵坐标 0~64，超出范围不显示

  *          value：显示的数值，32位整型数据，最大显示10位（inte + deci < 10）

  *          inte：整数位数，范围（>0, inte + deci < 10）

  *          deci：小数位数, 范围（inte + deci < 10）（取0时，为整数）

  *          mode：显示模式，0-正常显示，1-反白显示

  * @说  明  输入value为整型，如果是小数，可扩大相应倍数实现。例如123.45,先乘100，显示时整数位取3，小数位取2。

  *          如果显示数据可能为负数时，整数位数需要比最大位数多一位。例如-122，整数位取4。

  * @返回值	 

  */

void AX_OLED_DisplayValue(uint8_t x, uint8_t y, int32_t value, uint8_t inte, uint8_t deci, uint8_t mode)

{

	

	u8 dis_number[10];

	u8 i;

	u32 temp;

	

	if((inte>0) && ((inte+deci)<10))

	{

		if(value < 0)

			temp = (0-value);

		else

			temp = value;

		

		dis_number[1] = temp%10; 

		dis_number[2] = (temp%100)/10;

		dis_number[3] = (temp%1000)/100;

		dis_number[4] = (temp%10000)/1000;

		dis_number[5] = (temp%100000)/10000;

		dis_number[6] = (temp%1000000)/100000;

		dis_number[7] = (temp%10000000)/1000000;

		dis_number[8] = (temp%100000000)/10000000;

		dis_number[9] = (temp%1000000000)/100000000;		

		  

		if(value<0)

		{

		  AX_OLED_DisplayChar(x, y, '-', mode);

		   

		   for(i=0; i<(inte-1); i++ )

		   {

			   AX_OLED_DisplayNum(x+6+(i*6), y, dis_number[inte+deci-i-1],mode);

		   }

		   if(deci != 0 )

		   {

			  AX_OLED_DisplayChar(x+(inte*6), y, '.', mode);

			   

			   for(i=0; i<deci;i++ )

			   {

				   AX_OLED_DisplayNum(x+(inte*6)+6+(i*6), y, dis_number[deci-i],mode);

			   }

		   } 

		}

		else

		{	   

		   for(i=0; i<inte; i++ )

		   {

			   AX_OLED_DisplayNum(x+(i*6), y,dis_number[inte+deci-i],mode);

		   }

		   if(deci != 0 )

		   {

			   AX_OLED_DisplayChar(x+(inte*6), y, '.', mode);

			   

			   for(i=0; i<deci;i++ )

			   {

				   AX_OLED_DisplayNum(x+(inte*6)+6+(i*6), y, dis_number[deci-i], mode);

			   }

		   } 	   

		}

	}

	else // 参数错误

	{

		//AX_OLED_DisplayChar(x, y, 'X', 0);

	}	

	

}



/* 底层操作函数-----------------------------------------------------*/

/**

  * @简  述  SPI3写入读取一个字节函数

  * @参  数  dat：要写入的字节

  * @返回值  读出字节

  */

static uint8_t SPI1_Send_Byte(uint8_t dat)

{

  /* Loop while DR register in not emplty */

  while(SPI_I2S_GetFlagStatus(SPI1, SPI_I2S_FLAG_TXE) == RESET);



  /* Send byte through the SPI peripheral */

  SPI_I2S_SendData(SPI1, dat);



  /* Wait to receive a byte */

  while(SPI_I2S_GetFlagStatus(SPI1, SPI_I2S_FLAG_RXNE) == RESET);





  /* Return the byte read from the SPI bus */

  return SPI_I2S_ReceiveData(SPI1);

}



/**

  * @brief  

  * @param  None

  * @retval None

  */

static void OLED_WriteCmd(u8 data)

{	  

	OLED_DC_L();

	                  

    SPI1_Send_Byte(data);      //发送片擦除命令  



	OLED_DC_H(); 

}



/**

  * @brief  

  * @param  None

  * @retval None

  */

static void OLED_WriteData(u8 data)

{	               

    SPI1_Send_Byte(data);      //发送片擦除命令  	

}





//画点 

//x:0~127

//y:0~63

//t:1 填充 0,清空		

void OLED_DrawPoint(u8 x,u8 y,u8 t)

{

	u8 pos,bx,temp=0;

	if(x>127||y>63)return;//超出范围了.

	pos=7-y/8;

	bx=y%8;

	temp=1<<(7-bx);

	if(t)OLED_GRAM[x][pos]|=temp;

	else OLED_GRAM[x][pos]&=~temp;	    

}



/******************* (C) 版权 2018 XTARK **************************************/

