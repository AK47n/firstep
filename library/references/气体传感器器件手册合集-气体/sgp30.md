# SGP30气体传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/sgp30-gas-sensor.html
- 标题：SGP30气体传感器
- 代码块：3 个 · 图片：0 张

SGP30是一款单一芯片上具有多个传感元件的金属氧化物气体传感器，内集成4个气体传感元件，具有完全校准的空气质量输出信号。另外，SGP易于集成，能够将金属氧化物气体传感器集成到移动设备中，为智能家居、家电和物联网应用中的环境监测开辟了新的可能性。主要用于甲醛的检测!

## 一、模块来源

采购链接：

[GY-SGP30 气体传感器 空气质量 TVOC eCO2 二氧化碳测量甲醛模块](https://item.taobao.com/item.htm?spm=a21n57.1.0.0.1925523cK81vXF&id=629652345522&ns=1&abbucket=0#detail)

也可以购买：

[GY-SGP30 气体传感器 空气质量 TVOC eCO2 二氧化碳测量甲醛模块](https://item.taobao.com/item.htm?spm=a21n57.1.0.0.1925523cK81vXF&id=609271054989&ns=1&abbucket=0#detail)

资料下载链接：

[https://pan.baidu.com/s/16ITjdV34J8K2Wu24sB_iPg](https://pan.baidu.com/s/16ITjdV34J8K2Wu24sB_iPg)

提取码：1vds

## 二、规格参数

**工作电压**：3.3V

**工作电流**：40mA

**输出方式**: IIC

**管脚数量**：4 Pin

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【测量甲醛】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

SGP30是一款单一芯片上具有多个传感元件的金属氧化物室内气体传感器，内部集成4个气体传感元件，具有完全校准的空气质量输出信号，主要是对空气质量进行检测。可以输出：

TVOC（Total Volatile Organic Compounds，总挥发性有机物），量程为0~60000ppb；CO2浓度，量程400~60000ppm。

SGP30的传感（MEMS）部分基于金属氧化物（MOx）纳米颗粒的加热膜。气敏材料——金属氧化物颗粒上吸附的氧气与目标气体发生反应，从而释放出电子。这导致由传感器测量的金属氧化物层的电阻发生改变。简而言之，还原性气体的出现造成气敏材料表面氧浓度降低，改变了半导体的电阻（或电导率）。后续通过电路（ASIC）部分对电阻进行检测、信号处理与转换等，最终获取到气体值。

I2C从机地址是0X58，由于地址只用到了7bit，最高位未使用，最低位为判断是读还是写，为0是读，为1是写，所以：

- 对于写SGP30，地址为(0X58 << 1) = 0XB0
- 对于读SGP30，地址为((0X58 << 1)) | 0X01 = 0XB1

SGP30的命令都是双字节的，先发高位。有如下命令：

常用的有两个，一个是0x2003为初始化SGP30命令，另一个0x2008为获取空气质量值命令。

SGP30获取的数据格式为：2位CO2数据+1位CO2的CRC校验+2位TVOC数据+1位TVOC的CRC校验。模块上电需要15s左右初始化，在初始化阶段读取的CO2浓度为400ppm，TVOC为0ppd且恒定不变。因此上电后一直读，直到TVOC不为0并且CO2不为400，SGP30模块才初始化完成。

初始化完成后刚开始读出数据会波动比较大，属于正常现象，一段时间后会逐渐趋于稳定。气体类传感器比较容易受环境影响，测量数据出现波动是正常的，可以添加滤波函数进行滤波。

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_sgp30.c**与**bsp_sgp30.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_sgp30.c**中，编写如下代码。

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
 * 2024-07-03     LCKFB-LP    first version
 */

#include "bsp_sgp30.h"
#include "stdio.h"

/******************************************************************
 * 函 数 名 称：IIC_Start
 * 函 数 说 明：IIC起始时序
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void IIC_Start(void)
{
        SDA_OUT();

        SCL(0);
        delay_us(1);

        SDA(1);
        SCL(1);
        delay_us(5);

        SDA(0);
        delay_us(5);
        SCL(0);
        delay_us(5);

}
/******************************************************************
 * 函 数 名 称：IIC_Stop
 * 函 数 说 明：IIC停止信号
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void IIC_Stop(void)
{
        SDA_OUT();

        SCL(0);
        SDA(0);

        SCL(1);
        delay_us(5);
        SDA(1);
        delay_us(5);

}

/******************************************************************
 * 函 数 名 称：IIC_Send_Ack
 * 函 数 说 明：主机发送应答或者非应答信号
 * 函 数 形 参：0发送应答  1发送非应答
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void IIC_Send_Ack(unsigned char ack)
{
        SDA_OUT();
        SCL(0);
        SDA(0);
        delay_us(5);
        if(!ack) SDA(0);
        else     SDA(1);
        SCL(1);
        delay_us(5);
        SCL(0);
        SDA(1);
}

/******************************************************************
 * 函 数 名 称：I2C_WaitAck
 * 函 数 说 明：等待从机应答
 * 函 数 形 参：无
 * 函 数 返 回：0有应答  1超时无应答
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned char I2C_WaitAck(void)
{

        char ack = 0;
        unsigned char ack_flag = 10;
        SCL(0);
        SDA(1);
        SDA_IN();
        delay_us(5);
        SCL(1);
        delay_us(5);

        while( (SDA_GET()==1) && ( ack_flag ) )
        {
                ack_flag--;
                delay_us(5);
        }

        if( ack_flag <= 0 )
        {
                IIC_Stop();
                return 1;
        }
        else
        {
                SCL(0);
                SDA_OUT();
        }
        return ack;
}

/******************************************************************
 * 函 数 名 称：Send_Byte
 * 函 数 说 明：写入一个字节
 * 函 数 形 参：dat要写人的数据
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void Send_Byte(uint8_t dat)
{
        int i = 0;
        SDA_OUT();
        SCL(0);//拉低时钟开始数据传输

        for( i = 0; i < 8; i++ )
        {
                SDA( (dat & 0x80) >> 7 );
                delay_us(1);
                SCL(1);
                delay_us(5);
                SCL(0);
                delay_us(5);
                dat<<=1;
        }
}

/******************************************************************
 * 函 数 名 称：Read_Byte
 * 函 数 说 明：IIC读时序
 * 函 数 形 参：无
 * 函 数 返 回：读到的数据
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned char Read_Byte(void)
{
        unsigned char i,receive=0;
        SDA_IN();//SDA设置为输入
        for(i=0;i<8;i++ )
        {
                SCL(0);
                delay_us(5);
                SCL(1);
                delay_us(5);
                receive<<=1;
                if( SDA_GET() )
                {
                        receive|=1;
                }
                delay_us(5);
        }
        SCL(0);
		return receive;
}

/******************************************************************
 * 函 数 名 称：SGP30_Write
 * 函 数 说 明：SGP30写命令
 * 函 数 形 参：regaddr_H命令高8位   regaddr_L命令低8位
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void SGP30_Write_cmd(uint8_t regaddr_H, uint8_t regaddr_L)
{
	  IIC_Start();
	  Send_Byte(0XB0);         //发送器件地址+写指令
	  I2C_WaitAck();
	  Send_Byte(regaddr_H);    //发送控制地址
	  I2C_WaitAck();
	  Send_Byte(regaddr_L);    //发送数据
	  I2C_WaitAck();
	  IIC_Stop();
	  delay_ms(100);
}

/******************************************************************
 * 函 数 名 称：
 * 函 数 说 明：
 * 函 数 形 参：
 * 函 数 返 回：
 * 作       者：LC
 * 备       注：SGP30获取的数据格式为：2位CO2数据+1位CO2的CRC校验+2位TVOC数据+1位TVOC的CRC校验。
                模块上电需要15s左右初始化，在初始化阶段读取的CO2浓度为400ppm，TVOC为0ppd且恒定不变。
                因此上电后一直读，直到TVOC不为0并且CO2不为400，SGP30模块才初始化完成。
                初始化完成后刚开始读出数据会波动比较大，属于正常现象，一段时间后会逐渐趋于稳定。
                气体类传感器比较容易受环境影响，测量数据出现波动是正常的，可以添加滤波函数进行滤波。
******************************************************************/
uint32_t SGP30_Read(void)
{
	  uint32_t dat;
	  uint8_t crc;

	  IIC_Start();
	  Send_Byte(0XB1); //发送器件地址+读指令
	  I2C_WaitAck();

	  dat = Read_Byte();//CO2数据高8位
	  IIC_Send_Ack(0);
	  dat <<= 8;

	  dat += Read_Byte();//CO2数据低8位
	  IIC_Send_Ack(0);

	  crc = Read_Byte(); //CO2的CRC校验
	  IIC_Send_Ack(0);
	  crc = crc;

	  dat <<= 8;
	  dat += Read_Byte();//TVOC数据高8位
	  IIC_Send_Ack(0);

	  dat <<= 8;
	  dat += Read_Byte();//TVOC数据低8位
	  IIC_Send_Ack(1);

	  IIC_Stop();
	  return(dat);
}

/******************************************************************
 * 函 数 名 称：SGP30_Init
 * 函 数 说 明：SGP30初始化
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void SGP30_Init(void)
{
		SGP30_Write_cmd(0x20, 0x03);
}
```

在文件**bsp_sgp30.h**中，编写如下代码。

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
 * 2024-07-03     LCKFB-LP    first version
 */
#ifndef _BSP_SGP30_H_
#define _BSP_SGP30_H_

#include "board.h"

//设置SDA输出模式
#define SDA_OUT()   {                                                  \
                        DL_GPIO_initDigitalOutput(GPIO_SDA_IOMUX);     \
                        DL_GPIO_setPins(GPIO_PORT, GPIO_SDA_PIN);      \
                        DL_GPIO_enableOutput(GPIO_PORT, GPIO_SDA_PIN); \
                    }
//设置SDA输入模式
#define SDA_IN()    { DL_GPIO_initDigitalInput(GPIO_SDA_IOMUX); }
//获取SDA引脚的电平变化
#define SDA_GET()   ( ( ( DL_GPIO_readPins(GPIO_PORT,GPIO_SDA_PIN) & GPIO_SDA_PIN ) > 0 ) ? 1 : 0 )
//SDA与SCL输出
#define SDA(x)      ( (x) ? (DL_GPIO_setPins(GPIO_PORT,GPIO_SDA_PIN)) : (DL_GPIO_clearPins(GPIO_PORT,GPIO_SDA_PIN)) )
#define SCL(x)      ( (x) ? (DL_GPIO_setPins(GPIO_PORT,GPIO_SCL_PIN)) : (DL_GPIO_clearPins(GPIO_PORT,GPIO_SCL_PIN)) )

void SGP30_Init(void);
uint32_t SGP30_Read(void);
void SGP30_Write_cmd(uint8_t a, uint8_t b);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_sgp30.h"

int main(void)
{
      uint32_t CO2Data, TVOCData;  //定义CO2浓度变量与TVOC浓度变量
      uint32_t sgp30_dat;          //定义SGP30读取到的数据

      //开发板初始化
      board_init();

      SGP30_Init();
      delay_ms(100);

      while (1)
      {
            SGP30_Write_cmd(0x20,0x08);
            sgp30_dat = SGP30_Read();                  //读取SGP30的值
            CO2Data = (sgp30_dat & 0xffff0000) >> 16;  //获取CO2的值
            TVOCData = sgp30_dat & 0x0000ffff;         //获取TVOC的值
            printf("CO2 : %0.2d\r\nTVOC : %0.2d\r\n",CO2Data,TVOCData);
            delay_ms(1000);
      }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1-jzfg_zgpZXJdvWiPrkftQ?pwd=1x3e](https://pan.baidu.com/s/1-jzfg_zgpZXJdvWiPrkftQ?pwd=1x3e)**提取码**：1x3e

## 百度网盘下载

- https://pan.baidu.com/s/16ITjdV34J8K2Wu24sB_iPg
- https://pan.baidu.com/s/1-jzfg_zgpZXJdvWiPrkftQ?pwd=1x3e
