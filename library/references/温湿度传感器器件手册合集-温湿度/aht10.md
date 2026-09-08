# AHT10温湿度传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/aht10-temp-humi-sensor.html
- 标题：AHT10温湿度传感器
- 代码块：4 个 · 图片：0 张

AHT10，新一代温湿度传感器在尺寸与智能方面建立了新的标准：它嵌入了适于回流焊的双列扁平无引脚SMD 封装，底面 4 x 5mm ，高度1.6mm。传感器输出经过标定的数字信号，标准 I 2 C 格式。AHT10 配有一个全新设计的 ASIC专用芯片、一个经过改进的MEMS半导体电容式湿度传感元件和一个标准的片上温度传感元件，其性能已经大大提升甚至超出了前一代传感器的可靠性水平，新一代温湿度传感器，经过改进使其在恶劣环境下的性能更稳定。每一个传感器都经过校准和测试，在产品表面印有产品批号。由于对传感器做了改良和微型化改进，因此它的性价比更高，并且最终所有设备都将得益于尖端的节能运行模式。

应用范围主要在暖通空调 、除湿器、测试及检测设备、消费品、汽车 、自动控制、数据记录器、气象站、家电、湿度调节、医疗及其他相关温湿度检测控制。

## 一、模块来源

采购链接：

[AHT10 高精度数字型温湿度传感器测量模块 I2C通讯 代替sht20](https://item.taobao.com/item.htm?spm=a230r.1.14.28.5b982786BAvoXy&id=630894804483&ns=1&abbucket=19#detail)

资料下载链接：

[https://pan.baidu.com/s/1xTX_QCmEmy8DWgxgtgXXFw](https://pan.baidu.com/s/1xTX_QCmEmy8DWgxgtgXXFw)

提取码：pp3k

## 二、规格参数

**工作电压**：1.8~3.6V

**工作电流**：0.25~23uA

**湿度误差**：±2%RH

**温度误差**：±0.3℃

**输出方式**: IIC

**管脚数量**：3 Pin

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够测量环境温湿度】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

器件地址为 **0x38** ，但是最后一位是读写位，需要空出一位给读写位，因此需要左移一位，即 **0x38<<1** 得到 **0X70**

采集步骤：(写=0，读=1)

起始信号->器件地址左移1位+写 -> 等待传感器应答 -> 发送触发测量命令（0XAC）-> 等待传感器应答 -> 发送数据位0X33 -> 等待传感器应答 -> 发送数据位0x00 -> 等待传感器应答 -> 停止信号（可不加）-> 起始信号 ->器件地址左移1位+读 -> 等待传感器应答 -> 读取8位数据（状态字）-> 主机发送应答 -> 读取湿度高位数据 -> 主机发送应答 -> 读取湿度低位数据 -> 主机发送应答-> 读取湿度最后4位数据和温度最高的4位数据 -> -> 主机发送应答 -> 读取温度8数据 -> 主机发送应答-> 读取温度8位数据 -> 主机发送应答 -> 停止信号。

8位状态字，各个位表示的意义。

示例：

```c
状态位 = 0x1C

        0X1C = 0001 1100
        bit7  = 设备空闲
        bit6~5= NOR mode
        bit4  = 保留
        BIT3  = 1已校准
        bit0~2= 保留
```

湿度换算公式：其中SRH等于读取到的20位湿度数据整合后的数据。

温度换算公式：其中ST等于读取到的20位温度数据整合后的数据。

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_aht10.c**与**bsp_aht10.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_aht10.c**中，编写如下代码。

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

#include "bsp_aht10.h"
#include "stdio.h"

float Temperature = 0;
float Humidity = 0;

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

        SDA(1);
        SCL(1);
        delay_us(4);

        SDA(0);
        delay_us(4);
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
        delay_us(4);

        SCL(1);
        SDA(1);
        delay_us(4);

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
        delay_us(2);
        if(!ack) SDA(0);
        else     SDA(1);
        SCL(1);
        delay_us(2);
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

        SDA(1);
		delay_us(1);
		SCL(1);
		delay_us(1);

        SDA_IN();
        delay_us(2);

        while( (SDA_GET()==1) && ( ack_flag ) )
        {
                ack_flag--;
                delay_us(3);
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
                SDA(0);
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
			delay_us(2);
			SCL(0);
			delay_us(2);
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
			delay_us(2);
			SCL(1);
			delay_us(2);
			receive<<=1;
			if( SDA_GET() )
			{
					receive|=1;
			}
			delay_us(1);
        }
        SCL(0);
        return receive;
}

/******************************************************************
 * 函 数 名 称：AHT10Reset
 * 函 数 说 明：软件复位
 * 函 数 形 参：
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void AHT10Reset(void)
{
        IIC_Start();
        Send_Byte(0x70);
        I2C_WaitAck();
        Send_Byte(0xba);
        I2C_WaitAck();
        IIC_Stop();
}

/******************************************************************
 * 函 数 名 称：AHT10_Init
 * 函 数 说 明：AHT10的初始化
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void AHT10_Init(void)
{
        delay_ms(50);//延时50ms让传感器稳定
        IIC_Start();
        Send_Byte(0x70);  //获取状态
        //初始化校准
        Send_Byte(0xe1);
        Send_Byte(0x08);
        Send_Byte(0x00);
        IIC_Stop();
        delay_ms(50);//延时50ms让传感器稳定
}

/**********************************************************
 * 函 数 名 称：AHT10_Read
 * 函 数 功 能：读取AHT10的温湿度数据
 * 传 入 参 数：无
 * 函 数 返 回：0读取成功
 * 作       者：LC
 * 备       注：无
**********************************************************/
unsigned char AHT10_Read(void)
{
        char timeout = 0;
        unsigned char buff[6] = {0};
        unsigned int dat = 0;

        IIC_Start();//起始信号
        Send_Byte(0X38<<1 | 0); //器件地址+写命令
        I2C_WaitAck();          //等待传感器应答
        Send_Byte(0XAC);//寄存器地址：触发测量命令
        I2C_WaitAck();//等待传感器应答

        Send_Byte(0X33);//发送数据位
        I2C_WaitAck();//等待传感器应答

        Send_Byte(0X00);//发送数据位
        I2C_WaitAck();  //等待传感器应答

        IIC_Stop();     //停止信号

        do{
				delay_ms(1);//超时判断，等待传感器采集数据
				timeout++;
				IIC_Start();//重新发送起始信号
				Send_Byte(0X38<<1  | 1);//器件地址+写命令
        }while( I2C_WaitAck() == 1 && timeout < 5 );

        buff[0] = Read_Byte();//读取状态字
        IIC_Send_Ack(0);//主机发送应答

        buff[1] = Read_Byte();//湿度高8位数据
        IIC_Send_Ack(0);//主机发送应答

        buff[2] = Read_Byte();//湿度低8位数据
        IIC_Send_Ack(0);//主机发送应答

        buff[3] = Read_Byte();
        IIC_Send_Ack(0);//主机发送应答

        buff[4] = Read_Byte();
        IIC_Send_Ack(0);//主机发送应答

        buff[5] = Read_Byte();
        IIC_Send_Ack(1);//主机发送应答

        IIC_Stop();//停止信号

        delay_ms(20);

        //高位在前
        dat = (((buff[1]<<12) | (buff[2]<<4)) | (buff[3]>>4));
        Humidity = dat / 1048576.0 * 100.0;

        dat = 0;
        dat = ((buff[3] &0x0F) << 16 ) | ( buff[4] << 8) | buff[5];
        Temperature = (dat/1048576.0) * 200 - 50;

        AHT10Reset();                // AHT10复位
        AHT10_Init();        // GPIO重新初始化

        return 0;
}

/**********************************************************
 * 函 数 名 称：Get_Temperature
 * 函 数 功 能：获取采集后的温度数据
 * 传 入 参 数：无
 * 函 数 返 回：温度数据，单位℃
 * 作       者：LC
 * 备       注：必须先采集与数据，否则返回0或者之前的数据
**********************************************************/
float Get_Temperature(void)
{
        return Temperature;
}

/**********************************************************
 * 函 数 名 称：Get_Humidity
 * 函 数 功 能：获取采集后的湿度数据
 * 传 入 参 数：无
 * 函 数 返 回：湿度数据，单位%RH
 * 作       者：LC
 * 备       注：必须先采集与数据，否则返回0或者之前的数据
**********************************************************/
float Get_Humidity(void)
{
        return Humidity;
}
```

在文件**bsp_aht10.h**中，编写如下代码。

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

#ifndef _BSP_AHT10_H_
#define _BSP_AHT10_H_

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

void AHT10_Init(void);
unsigned char AHT10_Read(void);
float Get_Temperature(void);
float Get_Humidity(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_aht10.h"

int main(void)
{
    //开发板初始化
    board_init();

    AHT10_Init();//AHT10初始化

    printf("Start\r\n");

    while(1)
    {
        //采集温湿度
        AHT10_Read();

        uint32_t Temperature = Get_Temperature();
        uint32_t Humidity = Get_Humidity();

        //串口打印温度数据
        printf("温度 = %d.%02d *C\r\n",(int)Temperature,(((uint32_t)(Temperature*100))%100));
        //串口打印湿度数据
        printf("湿度 = %d.%02d %%\r\n",(int)Humidity,(((uint32_t)(Humidity*100))%100));

        printf("\n");
        delay_ms(1000);

    }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1jVicGsVI5zxcbZracdj6VA?pwd=trjc](https://pan.baidu.com/s/1jVicGsVI5zxcbZracdj6VA?pwd=trjc)**提取码**：trjc

## 百度网盘下载

- https://pan.baidu.com/s/1xTX_QCmEmy8DWgxgtgXXFw
- https://pan.baidu.com/s/1jVicGsVI5zxcbZracdj6VA?pwd=trjc
