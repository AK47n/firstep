# AGS10有害气体传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/ags10-harmful-gas-sensor.html
- 标题：AGS10有害气体传感器
- 代码块：3 个 · 图片：0 张

AGS10是一款采用数字信号输出的MEMS TVOC传感器。配置了专用的数字模块采集技术和气体感应传感技术，确保了产品具有极高的可靠性与卓越的长期稳定性，同时具有低功耗、高灵敏度、快速响应、成本低、驱动电路简单等特点。

## 一、模块来源

采购链接：

[AGS10有害气体传感器](https://item.taobao.com/item.htm?spm=a21n57.1.0.0.148e523cqcVeUq&id=709434114260&ns=1&abbucket=8#detail)

## 二、规格参数

**工作电压** : 3.0-6.0 V

**典型功率** : 75mW

**采样周期** : ≥2s

**接口速率** ：I2C从机模式（≤15kHz）

**预热时间** : ≥120s

**工作温度** : 0～50℃

**工作湿度** : 0～95%RH

**寿命** : ＞5年（25℃，清洁空气中）

**输出单位** : ppb

**测量范围** : 0～99999 ppb

**典型精度**（ 25℃/50%RH）: 25% 读数

**标准测试气体** : 乙醇

**模块尺寸**：15\*10.6mm

以上信息见厂家资料文件

## 三、移植过程

### 1、查看资料

> **工作原理**

AGS10传感器采用标准I 2C通信协议，适应多种设备。IIC的物理接口包含串行数据信号（SDA）与串行时钟信号（SCL）两个接口。两个接口需通过1kΩ～10kΩ电阻上拉至VDD。SDA用于读、写传感器数据。SCL上电必须保持高电平直到进行IIC通信开始，否则会引起I 2C通讯不良。当I 2C通信时SCL用于主机与传感器之间的通讯同步。多个I2C设备可以共享总线，但是只能允许一个主机设备出现在总线上。既然采用的是IIC，那么我们需要知道它的IIC通信地址。

读取TVOC数据的步骤：

### 2、引脚选择

### 3、移植至工程

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】【添加2个GPIO配置】

点击添加GPIO配置：

5. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

6. 然后点击编译（**可能会报错，我们不用管！**）
7. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_ags10.c**与**bsp_ags10.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_ags10.c**中，编写如下代码。

```c
/*
 * 立创开发板软硬件资料与相关扩展板软硬件资料官网全部开源
 * 开发板官网：www.lckfb.com
 * 技术支持常驻论坛，任何技术问题欢迎随时交流学习
 * 立创论坛：https://oshwhub.com/forum
 * 关注bilibili账号：【立创开发板】，掌握我们的最新动态！
 * 不靠卖板赚钱，以培养中国工程师为己任
 * Change Logs:
 * Date           Author       Notes
 * 2024-07-04     LCKFB-LP    first version
 */
#include "bsp_ags10.h"

//起始信号
void AGS10_IIC_Start(void)
{
        AGS10_SDA_OUT();
        AGS10_SDA(1);
        AGS10_SCL(1);
        delay_1us(5);
        AGS10_SDA(0);
        delay_1us(5);
        AGS10_SCL(0);
        delay_1us(5);
}

//停止信号
void AGS10_IIC_Stop(void)
{
        AGS10_SDA_OUT();
        AGS10_SCL(0);
        AGS10_SDA(0);
        AGS10_SCL(1);
        delay_1us(5);
        AGS10_SDA(1);
        delay_1us(5);
}

//发送非应答
void AGS10_IIC_Send_Nack(void)
{
        AGS10_SDA_OUT();
        AGS10_SCL(0);
        AGS10_SDA(0);
        AGS10_SDA(1);
        AGS10_SCL(1);
        delay_1us(5);
        AGS10_SCL(0);
        AGS10_SDA(0);
}

//发送应答
void AGS10_IIC_Send_Ack(void)
{
        AGS10_SDA_OUT();
        AGS10_SCL(0);
        AGS10_SDA(1);
        AGS10_SDA(0);
        AGS10_SCL(1);
        delay_1us(5);
        AGS10_SCL(0);
        AGS10_SDA(1);
}

/**********************************************************
 * 函 数 名 称：I2C_WaitAck
 * 函 数 功 能：等待从机应答
 * 传 入 参 数：无
 * 函 数 返 回：1=非应答         0=应答
 * 作       者：LC
 * 备       注：无
**********************************************************/
unsigned char AGS10_I2C_WaitAck(void)
{
        char ack = 0;
        unsigned char ack_flag = 10;
        AGS10_SCL(0);
        AGS10_SDA(1);
        AGS10_SDA_IN();
        delay_1us(5);
        AGS10_SCL(1);
		delay_1us(5);

        while( (AGS10_GETSDA()==1)  &&  ( ack_flag ) )
        {
                ack_flag--;
                delay_1us(5);
        }

        //非应答
        if( ack_flag <= 0 )
        {
                AGS10_IIC_Stop();
                return 1;
        }
        else//应答
        {
                AGS10_SCL(0);
                AGS10_SDA_OUT();
        }
        return ack;
}

//发送一个字节
void AGS10_IIC_Send_Byte(uint8_t dat)
{
        int i = 0;
        AGS10_SDA_OUT();
        AGS10_SCL(0);

        for( i = 0; i < 8; i++ )
        {
                AGS10_SDA( (dat & 0x80) >> 7 );
                delay_1us(1);
                AGS10_SCL(1);
                delay_1us(5);
                AGS10_SCL(0);
                delay_1us(5);
                dat<<=1;
        }
}

//接收一个字节
unsigned char AGS10_IIC_Read_Byte(void)
{
        unsigned char i,receive=0;
        AGS10_SDA_IN();//SDA设置为输入
        for(i=0;i<8;i++ )
        {
                AGS10_SCL(0);
                delay_1us(5);
                AGS10_SCL(1);
                delay_1us(5);
                receive<<=1;
                if( AGS10_GETSDA() )
                {
                        receive |= 1;
                }
        }
        AGS10_SCL(0);
        return receive;
}

//********************************************************************
//函数名称：Calc_CRC8
//功能 ：CRC8 计算，初值：0xFF，多项式：0x31(x8 + x5 + x4 +1)
//参数 ：u8* dat：需要校验数据的首地址；u8 Num：CRC 校验数据长度
//返回 ：crc：计算出的校验值
//********************************************************************
uint8_t Calc_CRC8(uint8_t *dat, uint8_t Num)
{
		uint8_t i, byte, crc=0xFF;
		for(byte=0; byte<Num; byte++)
		{
				crc ^= (dat[byte]);
				for( i = 0; i < 8; i++ )
				{
						if(crc & 0x80)  crc = ( crc << 1 ) ^ 0x31;
						else            crc = ( crc << 1 );
				}
		}
		return crc;
}

/**********************************************************
 * 函 数 名 称：ags10_read
 * 函 数 功 能：读取AGS10的TVOC浓度数据
 * 传 入 参 数：无
 * 函 数 返 回：1： 通信失败
 *             2：发送失败
 *             3：等待超时
 *             4: 校验失败
 * 作       者：LCKFB
 * 备       注：
**********************************************************/
uint32_t ags10_read(void)
{
		uint8_t timeout = 0;
		uint8_t data[5] = {0};
		uint32_t TVOC_data = 0;

		AGS10_IIC_Start();
		AGS10_IIC_Send_Byte(0X34);
		if( AGS10_I2C_WaitAck() == 1 ) return 1;
		AGS10_IIC_Send_Byte(0X00);
		if( AGS10_I2C_WaitAck() == 1 ) return 2;
		AGS10_IIC_Stop();

		do{
				delay_1ms(1);
				timeout++;
				AGS10_IIC_Start();
				AGS10_IIC_Send_Byte(0X35);
		}while( (AGS10_I2C_WaitAck() == 1) && (timeout >= 50) );

		//如果超时
		if( timeout >= 50 ) return 3;

		data[0] = AGS10_IIC_Read_Byte();
		AGS10_IIC_Send_Ack();
		data[1] = AGS10_IIC_Read_Byte();
		AGS10_IIC_Send_Ack();
		data[2] = AGS10_IIC_Read_Byte();
		AGS10_IIC_Send_Ack();
		data[3] = AGS10_IIC_Read_Byte();
		AGS10_IIC_Send_Ack();
		data[4] = AGS10_IIC_Read_Byte();
		AGS10_IIC_Send_Nack();

		AGS10_IIC_Stop();

		if( Calc_CRC8(data,4) != data[4] )
		{
			    // printf("Check failed\r\n");
				return 4;
		}
		TVOC_data = (data[1]<<16) | (data[2]<<8) | data[3] ;
		return TVOC_data;
}
```

在文件**bsp_ags10.h**中，编写如下代码。

```c
/*
 * 立创开发板软硬件资料与相关扩展板软硬件资料官网全部开源
 * 开发板官网：www.lckfb.com
 * 技术支持常驻论坛，任何技术问题欢迎随时交流学习
 * 立创论坛：https://oshwhub.com/forum
 * 关注bilibili账号：【立创开发板】，掌握我们的最新动态！
 * 不靠卖板赚钱，以培养中国工程师为己任
 * Change Logs:
 * Date           Author       Notes
 * 2024-07-04     LCKFB-LP    first version
 */
#ifndef _BSP_AGS10_H_
#define _BSP_AGS10_H_

#include "board.h"

//设置SDA输出模式
#define AGS10_SDA_OUT()   {                                                  \
                            DL_GPIO_initDigitalOutput(GPIO_SDA_IOMUX);     \
                            DL_GPIO_setPins(GPIO_PORT, GPIO_SDA_PIN);      \
                            DL_GPIO_enableOutput(GPIO_PORT, GPIO_SDA_PIN); \
                          }
//设置SDA输入模式
#define AGS10_SDA_IN()    { DL_GPIO_initDigitalInput(GPIO_SDA_IOMUX); }
//获取SDA引脚的电平变化
#define AGS10_GETSDA()   ( ( ( DL_GPIO_readPins(GPIO_PORT,GPIO_SDA_PIN) & GPIO_SDA_PIN ) > 0 ) ? 1 : 0 )
//SDA与SCL输出
#define AGS10_SDA(x)      ( (x) ? (DL_GPIO_setPins(GPIO_PORT,GPIO_SDA_PIN)) : (DL_GPIO_clearPins(GPIO_PORT,GPIO_SDA_PIN)) )
#define AGS10_SCL(x)      ( (x) ? (DL_GPIO_setPins(GPIO_PORT,GPIO_SCL_PIN)) : (DL_GPIO_clearPins(GPIO_PORT,GPIO_SCL_PIN)) )

uint32_t ags10_read(void);
#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_ags10.h"

int main(void)
{
      //开发板初始化
      board_init();

      printf("Start\r\n");

      while(1)
      {
            //显示TVOC浓度
            printf("TVOC = %d ppb\r\n",ags10_read() );
            delay_1ms(1000);
      }
}
```

上电效果：

模块代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1PMb5bFHRhmIujXx97FZePg?pwd=2z5o](https://pan.baidu.com/s/1PMb5bFHRhmIujXx97FZePg?pwd=2z5o)**提取码**：2z5o

## 百度网盘下载

- https://pan.baidu.com/s/1PMb5bFHRhmIujXx97FZePg?pwd=2z5o
