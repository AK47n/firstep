# SHT30温湿度传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/sht30-temp-humi-sensor.html
- 标题：SHT30温湿度传感器
- 代码块：3 个 · 图片：0 张

## 一、模块来源

采购链接：

[GY-SHT31-D 数字温湿度传感器模块](https://item.taobao.com/item.htm?spm=a1z09.2.0.0.204e2e8d2hPeAl&id=556043263770&_u=h2t4uge5cf4f)

资料下载链接：

[https://pan.baidu.com/s/1kisMJspcV6Qdr1ye9ElOlQ](https://pan.baidu.com/s/1kisMJspcV6Qdr1ye9ElOlQ)

## 二、规格参数

**工作电压**：2.4-5.5V

**工作电流**：0.2~1500uA

**温度测量范围**：-40~125℃

**温度测量精度**：±0.3℃

**湿度测量范围**：0~100%RH

**湿度测量精度**：±2%RH

**输出方式**: IIC

**管脚数量**：4 Pin

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【测量温湿度的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

ADS1115是采用的IIC通信，所以首先要了解IIC的地址与时序，再确定根据寄存器的设置。

#### 模块原理图

#### SHT30地址

数据手册上说明，当ADDR引脚接入VSS（接地）时，地址为0X44。而原理图上已经通过R14这个下拉电阻接地。不过需要注意的是，实际地址为 0X44 左移一位，因需要空出最低位给读写位，所以实际的地址是 0X44 << 1。

#### 测量模式

SHT30有两种测量模式，分别是单次测量模式和周期测量模式。

在单次测量模式下，发出一个测量命令就触发一次数据采集。每个数据都由一个16位的温度值和一个16位的湿度值(按此顺序)组成。在传输过程中，每个数据值后面总是跟着一个CRC校验和。但是在该模式下又分有时钟拉伸模式和时钟不拉伸模式，具体情况见下图。

并且在单次测量模式下，可以选择不同的测量命令。它们在可重复性(低、中、高)和时钟拉伸(启用或禁用)方面有所不同。这里的可重复性设置影响测量持续时间，从而影响传感器的总体能耗。

在周期测量模式下，时钟拉伸模式禁用，但是可以分为高中低的可重复性测量，测量周期为0.5、1、2、4、10（单位 次/秒）（这种模式下最快的测量速度是1秒10次）如果传感器在一种工作模式下正在测量数据，此时要发送其他命令（推荐先发送一次中断命令），让传感器停止当前的测量，进入单次测量模式，然后再发送命令。**这里需要注意：如果测量频率过高，会导致传感器自热**。

设置好周期测量模式的测量周期和可重复性强度后，随时可以进行测量读取数据，需要发送一个读取命令(0XE000)。一旦读取时序结束之后，寄存器中的数值就会清零，如果这时再一次读取数据将得到0。下一次测量结束后，寄存器的值就会重新写入。

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_sht30.c**与**bsp_sht30.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_sht30.c**中，编写如下代码。

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
 * 2024-07-01     LCKFB-LP    first version
 */

#include "bsp_sht30.h"
#include "stdio.h"

double Temperature = 0.0, Humidity = 0.0;

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
        SCL(1);
        SDA(0);

        SDA(1);
        delay_us(5);
        SDA(0);
        delay_us(5);

        SCL(0);
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

      SCL(1);
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
void Send_Byte(u8 dat)
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
 * 函 数 名 称：SHT31_Write_mode
 * 函 数 说 明：在周期模式下设置测量周期与可重复性命令
 * 函 数 形 参：dat设置命令
                常用的有：每一秒采集0.5次  0x2024
                         每一秒采集1次    0x2126
                         每一秒采集2次    0x2220
                         每一秒采集4次    0x2334
                         每一秒采集10次   0x2721
 * 函 数 返 回：
 * 作       者：LC
 * 备       注：
******************************************************************/
char SHT31_Write_mode(uint16_t dat)
{
      IIC_Start();

      // << 1 是将最后一位置0，设置为写命令
      Send_Byte((0X44 << 1) | 0 );
      //返回0为产生了应答，返回1说明通信失败
      if( I2C_WaitAck() == 1 )return 1;
      //发送命令的高8位
      Send_Byte((dat >> 8 ) );
      //返回0为产生了应答，返回1说明通信失败
      if( I2C_WaitAck() == 1 )return 2;
      //发送命令的低8位
      Send_Byte(dat & 0xff );
      //返回0为产生了应答，返回1说明通信失败
      if( I2C_WaitAck() == 1 )return 3;
  //        IIC_Stop();
      return 0;
}

/******************************************************************
 * 函 数 名 称：crc8
 * 函 数 说 明：CRC校验
 * 函 数 形 参：data要校验的数据地址     len要校验的长度
 * 函 数 返 回：校验后的值
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned char crc8(const unsigned char *data, int len)
{
    const unsigned char POLYNOMIAL = 0x31;
    unsigned char crc = 0xFF;
    int j, i;

    for (j=0; j<len; j++)
    {
        crc ^= *data++;
        for ( i = 0; i <8; i++ )
        {
                crc = ( crc & 0x80 ) ? (crc << 1) ^ POLYNOMIAL : (crc << 1);
        }
    }
    return crc;
}

/******************************************************************
 * 函 数 名 称：SHT30_Read
 * 函 数 说 明：读取温湿度值
 * 函 数 形 参：dat读取的命令
                周期模式命令为：0xe000
                单次模式命令为：0x2c06 or 0x2400
 * 函 数 返 回：0读取成功  其他失败
 * 作       者：LC
 * 备       注：当前为周期模式读取，如使用单次模式，则将
 *              【设置周期模式命令】下的命令注释即可。
******************************************************************/
char SHT30_Read(uint16_t dat)
{
        uint16_t i = 0;
        unsigned char buff[6] = {0};
        uint16_t data_16 = 0;

        //设置周期模式命令
        SHT31_Write_mode(0x2130);//每1秒一次高重复测量(需要在周期模式下才有用)

        IIC_Start();
        Send_Byte( (0x44<<1) | 0);
        if( I2C_WaitAck() == 1 )return 1;
        Send_Byte((dat >> 8 ));
        if( I2C_WaitAck() == 1 )return 2;
        Send_Byte( dat & 0xff );
        if( I2C_WaitAck() == 1 )return 3;

        //如不使用超时判断，很容易数据错乱
        do
        {
                //超时判断
                i++;
                if( i > 20 ) return 4;
                delay_ms(2);

                IIC_Start();
                Send_Byte((0X44 << 1) | 1 );//读

        }while(I2C_WaitAck() == 1);        //读取到温湿度数据则结束读命令

        //温度高8位
        buff[0] = Read_Byte();
        IIC_Send_Ack(0);
        //温度低8位
        buff[1] = Read_Byte();
        IIC_Send_Ack(0);
        //温度CRC校验值
        buff[2] = Read_Byte();
        IIC_Send_Ack(0);
        //湿度高8位
        buff[3] = Read_Byte();
        IIC_Send_Ack(0);
        //湿度低8位
        buff[4] = Read_Byte();
        IIC_Send_Ack(0);
        //湿度CRC校验值
        buff[5] = Read_Byte();
        IIC_Send_Ack(1);

        IIC_Stop();

        //CRC校验（将要校验的数值带入，查看计算后的校验值是否和读取到的校验值一致）
        if( (crc8(buff,2) == buff[2]) && ( crc8(buff+3,2) == buff[5]) )
        {
                //计算温度值
                data_16 =(buff[0]<<8) | buff[1];
                Temperature = (data_16/65535.0)*175.0 - 45;
                //计算湿度值
                data_16 = 0;
                data_16 =(buff[3]<<8) | buff[4];
                Humidity = (data_16/65535.0) * 100.0;

                return 0;
        }
        else
        {
                printf("校验失败\r\n");
        }
        return 5;
}
```

在文件**bsp_sht30.h**中，编写如下代码。

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
 * 2024-07-01     LCKFB-LP    first version
 */
#ifndef _BSP_SHT30_H_
#define _BSP_SHT30_H_

#include "board.h"

extern double Temperature, Humidity;

#define u8 unsigned char

//SDA输入模式
#define SDA_IN()   {  DL_GPIO_initDigitalInput(SHT30_SDA_IOMUX); }
//SDA输出模式
#define SDA_OUT()  {  DL_GPIO_initDigitalOutput(SHT30_SDA_IOMUX); \
                      DL_GPIO_enableOutput(SHT30_PORT, SHT30_SDA_PIN); \
                   }

#define SCL(BIT)  ( BIT ? DL_GPIO_setPins(SHT30_PORT,SHT30_SCL_PIN) : DL_GPIO_clearPins(SHT30_PORT,SHT30_SCL_PIN) )
#define SDA(BIT)  ( BIT ? DL_GPIO_setPins(SHT30_PORT,SHT30_SDA_PIN) : DL_GPIO_clearPins(SHT30_PORT,SHT30_SDA_PIN) )
#define SDA_GET() ( ( DL_GPIO_readPins( SHT30_PORT, SHT30_SDA_PIN ) & SHT30_SDA_PIN ) ? 1 : 0 )

char SHT30_Read(uint16_t dat);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_sht30.h"

int main(void)
{
    //开发板初始化
    board_init();

    printf("start\r\n");
    while(1)
    {
        SHT30_Read(0xe000);

        printf((const char *)"Temp = %d.%02d *C\r\n",(int)Temperature,(((uint32_t)(Temperature*100))%100) );
        printf((const char *)"Humi = %d.%02d %%\r\n",(int)Humidity,(((uint32_t)(Humidity*100))%100));
        printf("\r\n");
        delay_ms(1000);

    }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/192dmEWwSI2ak9PleDP6qLg?pwd=0j41](https://pan.baidu.com/s/192dmEWwSI2ak9PleDP6qLg?pwd=0j41)**提取码**：0j41

## 百度网盘下载

- https://pan.baidu.com/s/1kisMJspcV6Qdr1ye9ElOlQ
- https://pan.baidu.com/s/192dmEWwSI2ak9PleDP6qLg?pwd=0j41
