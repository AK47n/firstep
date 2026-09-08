# SHT20温湿度传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/sht20-temp-humi-sensor.html
- 标题：SHT20温湿度传感器
- 代码块：3 个 · 图片：0 张

由瑞士Sensirion推出的 SHT20数字温湿度传感器，基于领先世界的CMOSens ® 数字传感技术，具有极高的可靠性和卓越的长期稳定性。全量程标定，两线数字接口，可与单片机直接相连，大大缩短研发时间、简化外围电路并降低费用。此外，体积微小、响应迅速、低能耗、可浸没、抗干扰能力强、温湿一体，兼有露点测量，性价比高，使该产品能够适于多种场合的应用。

## 一、模块来源

采购链接：

[SHT20温湿度传感器模块/数字型温湿度测量模块 I2C通讯小体积模块](https://item.taobao.com/item.htm?spm=a21n57.1.0.0.700a523chCfvAP&id=615550651141&ns=1&abbucket=0#detail)

资料下载链接：

[https://pan.baidu.com/s/1HrQkwECvGgQSHvt_RNdLdA](https://pan.baidu.com/s/1HrQkwECvGgQSHvt_RNdLdA)

## 二、规格参数

**工作电压**：2.1~3.6V

**工作电流**：0.1~1000uA

**温度精度**：±0.3℃

**温度范围**：-40~125℃

**湿度范围**：0~100 %RH

**湿度精度**：±3%RH

**输出方式**: IIC

**管脚数量**：4 Pin

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够测量环境温湿度】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

开始传输后，随后先传输首字节包括I2C设备地址（7bit）和一个SDA方向位（R:1, W:0）。

一个时钟发送一个位，在第8个下降沿之后，通过拉低SDA引脚（ACK位 为0），只是传感器数据接收正常。在发出测量命令之后（‘1110’‘0011’代表温度测量，‘1110’‘0101’代表相对湿度测量 ，这种为主机模式），MCU必须等待测量完成。

> **主机模式：**：测量过程中，SCL线被封锁（由传感器控制），在测量时，SHT2x将SCL拉低强制主机进入等待状态。当释放SCL线，表示传感器内部工作接收，可以继续进行数据传送

灰色的部分是传感器控制的，当传感器给MCU返回数据时，每返回一个字节，MCU要返回一个ACK信号，当接收完毕之后，返回一个NACK并接着传输停止时序（P）。

> 注：校验和可以不需要，不需要则就在数据接收完之后返回NACK

> **非主机模式：**：测量过程中，SCL线是开发状态，可进行其他通信，可以在总线上处理其他I2C总线通信任务。

当MCU要对传感器状态进行查询时，先发起一个开始信号，在发送从机地址和SDA方向位（写），此时从机匹配地址成功，则发送ACK信号，并开始测量。如果传感器完成了测量过程，并且发送ASK信号，那么MCU就可以读取相关数据。如果测量没有完成，传感器发送NACK信号，此时MCU必须重新发送启动传输时序，直至测量完成，MCU读取数据。

> 注意：测量的数据，温度和湿度均为两个字节。而且无论哪一种传输模式，测量的最大分辨率最大是14bit，数据的第二个字节SDA上最后两位是用来标记相关状态信息。其中bit1表示测量类型（0是温度，1是湿度）

灰色的区域是传感器控制的，如果不需要校验和，那么在接收完两个字节的数据之后就MCU直接发出NACK信号再接着发出停止时序(P)，则结束通信。

通常测量的最长时间取决于测量类型和分辨率.

在计算MCU通信时间时，测量温度选择最长测量时间是85ms，而测量相对湿度选择最长的时间是29ms。

传感器内部设置的默认分辨率为相对湿度12位和温度14位。SDA的输出数据被转换成两个字节的数据包，高字节MSB在前(左对齐)。每个字节后面都跟随一个应答位。两个状态位，即 LSB的后两位在进行物理计算前须置0。 计算湿度：其中SRH表示我们读取到的湿度原始数据。

计算温度：其中ST表示我们读取到的温度原始数据。

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_sht20.c**与**bsp_sht20.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_sht20.c**中，编写如下代码。

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
 * 2024-07-02     LCKFB-LP    first version
 */
#include "bsp_sht20.h"
#include "stdio.h"

/******************************************************************
 * 函 数 名 称：IIC_Start
 * 函 数 说 明：IIC起始信号
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void IIC_Start(void)
{
        SDA_OUT();

        SCL(0);
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
 * 函 数 说 明：主机发送应答
 * 函 数 形 参：0应答  1非应答
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void IIC_Send_Ack(uint8_t ack)
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
 * 函 数 名 称：IIC_Wait_Ack
 * 函 数 说 明：等待从机应答
 * 函 数 形 参：无
 * 函 数 返 回：1=无应答   0=有应答
 * 作       者：LC
 * 备       注：无
******************************************************************/
uint8_t IIC_Wait_Ack(void)
{
      char ack = 0;
      unsigned char ack_flag = 10;
      SDA_IN();
      SDA(1);
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
 * 函 数 名 称：IIC_Write
 * 函 数 说 明：IIC写一个字节
 * 函 数 形 参：dat写入的数据
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void IIC_Write(uint8_t data)
{
      int i = 0;
      SDA_OUT();
      SCL(0);//拉低时钟开始数据传输

      for( i = 0; i < 8; i++ )
      {
            SDA( (data & 0x80) >> 7 );
            delay_us(2);
            data<<=1;
            delay_us(6);
            SCL(1);
            delay_us(4);
            SCL(0);
            delay_us(4);
      }
}

/******************************************************************
 * 函 数 名 称：IIC_Read
 * 函 数 说 明：IIC读1个字节
 * 函 数 形 参：无
 * 函 数 返 回：读出的1个字节数据
 * 作       者：LC
 * 备       注：无
******************************************************************/
uint8_t IIC_Read(void)
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
      return receive;
}

/******************************************************************
 * 函 数 名 称：SHT20_Read
 * 函 数 说 明：测量温湿度
 * 函 数 形 参：regaddr寄存器地址 regaddr=0xF3测量温度 =0xF5测量湿度
 * 函 数 返 回：regaddr=0xE3时返回温度，regaddr=0xE5时返回湿度
 * 作       者：LC
 * 备       注：无
******************************************************************/
float SHT20_Read(uint8_t regaddr)
{
      unsigned char data_H = 0;
      unsigned char data_L = 0;
      float temp = 0;
      IIC_Start();
      IIC_Write(0x80|0);
      if( IIC_Wait_Ack() == 1 ) printf("error -1\r\n");
      IIC_Write(regaddr);
      if( IIC_Wait_Ack() == 1 ) printf("error -2\r\n");

      do{
      delay_us(10);
      IIC_Start();
      IIC_Write(0x80|1);

      }while( IIC_Wait_Ack() == 1 );

      delay_us(20);

      data_H = IIC_Read();
      IIC_Send_Ack(0);
      data_L = IIC_Read();
      IIC_Send_Ack(1);
      IIC_Stop();

      if( regaddr == 0xf3 )
      {
            temp = ((data_H<<8)|data_L) / 65536.0 * 175.72 - 46.85;
      }
      if( regaddr == 0xf5 )
      {
            temp = ((data_H<<8)|data_L) / 65536.0 * 125.0 - 6;
      }
      return temp;

}
```

在文件**bsp_sht20.h**中，编写如下代码。

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
 * 2024-07-02     LCKFB-LP    first version
 */
#ifndef __BSP_SHT20_H__
#define __BSP_SHT20_H__

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

float SHT20_Read(unsigned char regaddr);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_sht20.h"

#define T_ADDR     0xf3   // 温度
#define PH_ADDR    0xf5   // 湿度

int main(void)
{
      //开发板初始化
      board_init();

      printf("SHT20 Start!!\r\n");

      while(1)
      {
            uint32_t TEMP = SHT20_Read(T_ADDR) * 100;
            uint32_t PH   = SHT20_Read(PH_ADDR) * 100;

            printf("温度 = %d.%02d ℃\r\n", TEMP/100,TEMP%100);
            printf("湿度 = %d.%02d %%RH\r\n", PH/100,PH%100);

            printf("\n");
            delay_ms(1000);
      }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1Yl84ZDRKFyw5sUmtYn3c5g?pwd=sujd](https://pan.baidu.com/s/1Yl84ZDRKFyw5sUmtYn3c5g?pwd=sujd)**提取码**：sujd

## 百度网盘下载

- https://pan.baidu.com/s/1HrQkwECvGgQSHvt_RNdLdA
- https://pan.baidu.com/s/1Yl84ZDRKFyw5sUmtYn3c5g?pwd=sujd
