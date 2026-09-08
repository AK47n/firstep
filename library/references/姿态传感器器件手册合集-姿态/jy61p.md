# JY61P三维姿态测量传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/jy61p-measurement-sensor.html
- 标题：JY61P三维姿态测量传感器
- 代码块：8 个 · 图片：0 张

该产品是基于MEMS技术的高性能三维运动姿态测量系统。它包含三轴陀螺仪、三轴加速度计。通过集成各种高性能传感器和运用自主研发的姿态动力学核心算法引擎，结合高动态卡尔曼滤波融合算法，为客户提供高精度、高动态、实时补偿的三轴姿态角度，通过对各类数据的灵活选择配置，满足不同的应用场景。

领先的基于 Kalman 滤波原理并具有自主知识产权的传感器融合算法，可以实时提供高达 200Hz 更新率的数据，从而满足各种高精度的应用需求，实现准确的动作捕捉和姿态估计。

拥有国内领先的高精度转台设备仪器，产品内部集成自主研发的高精度校准和标定算法，提高产品的测量精度。

同时提供用户所需要的各种上位机、使用说明、开发手册、开发代码，使得针对各类需求的研发时间降至最低。

## 一、模块来源

> **采购链接**：[六轴加速度计电子陀螺仪模块姿态角度传感器振动JY61P](https://detail.tmall.com/item.htm?spm=a21n57.1.item.2.2db9523ckmewQg&priceTId=213e37a817223458250504475e1c03&utparam=%7B%22aplus_abtest%22:%224f08c0a89ff55147b7125347c6206fe7%22%7D&id=597951224577&ns=1&abbucket=5&xxc=taobaoSearch&pisk=f3Us90M3sdv1CsPIncCEA9yoFe3blR_yCIGYZSLwMV3tHkNuhA5cjVrIhJeIBF5GjmHbIVn0bxkZhqN0F6WPzaPgsqmAUT7yWeVxQ4xtMcpq9XhZj95eLaPgsxA6H_rdznOWQJUtM-ntvWhrphHxD-3L9fkpWjLtMpCIivHxkcnv9ehxMdKtDhhciQGffAV19E0pLQ53M5HBPW4I6ytg1vOB9yZIfYUrdELYRfVhnQAXPik8qAoreJQe5qNKGJizfTT_hSFuDDaXB1y8powxtkXXcYZY_u4nXIKTOrMs2PnBw_V76jexckXWzfgaA0a_jsvL68k_2VV2NOPIVkio9DdXXVrzarm8WN9oL0cbd0r1FFwR4zYrFknXcBiklXMPO6tD0jmcopsaAR7EXXcsY61BBomttXgOO6tmAchnTpCCOd6N.&skuId=4169726245141)

> **上位机下载**：[https://wit-motion.yuque.com/wumwnr/aqvq6y/qngktvx5grz81zkq](https://wit-motion.yuque.com/wumwnr/aqvq6y/qngktvx5grz81zkq)

> **产品规格书**：[https://wit-motion.yuque.com/wumwnr/docs/agok0k?# 《JY61P产品规格书》](https://wit-motion.yuque.com/wumwnr/docs/agok0k?#%20%E3%80%8AJY61P%E4%BA%A7%E5%93%81%E8%A7%84%E6%A0%BC%E4%B9%A6%E3%80%8B)

## 二、规格参数

**工作电压**：5V

**供电电流【工作5V】**：8343mA

**供电电流【休眠5V】**：9.91uA

**回传速率**：200HZ（最高）

**带宽**：256HZ（最高）

**控制方式1**：串口【默认9600】

**控制方式2**：IIC

**管脚数量**：12 Pin（2.54mm间距排针）

> **以上信息见产品资料**：**产品资料**：[https://wit-motion.yuque.com/wumwnr/docs/np25sf?singleDoc# 《JY61P产品资料》](https://wit-motion.yuque.com/wumwnr/docs/np25sf?singleDoc#%20%E3%80%8AJY61P%E4%BA%A7%E5%93%81%E8%B5%84%E6%96%99%E3%80%8B)

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【读取姿态数据】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

#### 模块设置

我们首先先使用一个**USB传TTL模块**，使用上位机对我们的姿态倾角传感器进行检查。

> **上位机下载地址【下载最新版本】**：[https://wit-motion.yuque.com/wumwnr/aqvq6y/qngktvx5grz81zkq](https://wit-motion.yuque.com/wumwnr/aqvq6y/qngktvx5grz81zkq)

将USB转TTL模块插入电脑的USB口之后，我们双击打开上位机。

在模块类别中输入：JY61P，然后点击【搜索设备】：

之后选择自己的那个串口，这里我的是COM8，不确定是哪个COM口的话可以去设备管理器插拔下USB转TTL模块，看看自己电脑中出现的是哪个COM口。

然后【勾选】这个COM口的前面【勾选框】

我们转动传感器就会发现数据发生变化

将你的模块设置为下方gif里面的样子：

#### 读写数据

> **写时序**

> **读时序**

我们可以在这个网站中查看所有的寄存器地址和协议说明：[https://wit-motion.yuque.com/wumwnr/ltst03/vl3tpy?#UFGm8](https://wit-motion.yuque.com/wumwnr/ltst03/vl3tpy?#UFGm8)

- ADDR(HEX)就是寄存器地址
- FUNCTION是寄存器作用
- SERIAL I/F 是寄存器读写权限【R/W寄存器代表可读可写】【R代表只能读不能写入数据】

如果我们想要将Z轴清零怎么办呢？因为传感器归零对于写程序非常友好。

从网站中的内容可以看出z轴清零需要三个步骤：

- 解锁寄存器【延时200ms】
- 校准【延时200ms】网站说要延时三秒，经过实验发现200ms也行！
- 保存【延时200ms】

需要一个函数，也是下方代码中使用到的函数：

```c
/******************************************************************
 * 函 数 名 称：writeDataJy61p
 * 函 数 说 明：写length长度的数据
 * 函 数 形 参：  dev 设备地址
				        reg 寄存器地址
				        data 数据首地址
				        length 数据长度
 * 函 数 返 回：返回1则写入成功
******************************************************************/
uint8_t writeDataJy61p(uint8_t dev, uint8_t reg, uint8_t* data, uint32_t length);
```

然后我们需要将串口的HEX数据转变为IIC发送的数据。

从上图中我们知道解锁的指令是: 0xFF 0xAA 0x69 0x88 0xB5

其中 0xFF 和 0xAA 不用管！0x69为寄存器地址 0x88 和 0xB5 才是数据。

```c
// 我们先发送低位的数据 后发送高位
// 将数据信息保存到一个数组中
uint8_t unlock_reg1[2] = {0x88,0xB5};

// 1. 地址为0x50
// 2. 寄存器地址为0x69
// 3. 数据数组为 unlock_reg1[]
// 4. 发送的数据为 2 个字节 因为0x88和0xB5只有两个字节
writeDataJy61p(0x50,0x69,unlock_reg1,2);
```

根据上面的例子应该很容易就知道怎么搞定剩下的东西了：

```c
	/*================Z轴归零==================*/

	// 寄存器解锁
	uint8_t unlock_reg1[2] = {0x88,0xB5};
	writeDataJy61p(0x50,0x69,unlock_reg1,2);
	delay_ms(200);

	// Z轴归零
	uint8_t z_axis_reg[2] = {0x04,0x00};
	writeDataJy61p(0x50,0x01,z_axis_reg,2);
	delay_ms(200);

	// 保存
	uint8_t save_reg1[2] = {0x00,0x00};
	writeDataJy61p(0x50,0x00,save_reg1,2);
	delay_ms(200);
```

想要读数据，我们直接使用一个函数：

```c
/******************************************************************
 * 函 数 名 称：readDataJy61p
 * 函 数 说 明：读数据数据
 * 函 数 形 参：dev 设备地址
				        reg 寄存器地址
				        data 数据存储地址
				        length 数据长度
 * 函 数 返 回：返回1则读取成功
******************************************************************/
uint8_t readDataJy61p(uint8_t dev, uint8_t reg, uint8_t *data, uint32_t length);
```

这个函数的用法和上面的函数很相似，我们只需要填入设备地址、寄存器地址、缓存区地址和要接收的数据长度。

我们只需要输入一个数据组中的开头寄存器地址，然后不停的读取6次，即可得到横滚角、俯仰角和航向角的数据。

> **重点！！**：**在readDataJy61p函数中，我们每次接到数据都会发送应答信号，而JY61P模块接收到主机发送的信号之后就会继续发送数据，直到没有我们不发送应答！JY61P模块才会停止发送数据！**

例如这样使用：

```c
// 数据缓存数组
volatile uint8_t sda_angle[6] = {0};

int ret = 0;

// 清空数据缓存
memset(sda_angle,0,sizeof(sda_angle));

// 读取寄存器数据
// 0x50为模块地址
// 0x3D为横滚角寄存器地址
// sda_angle为读取到的数据接收数组首地址
// 6为要读取的字节数
ret	= readDataJy61p(0x50,0x3D,sda_angle,6);
```

### 2、引脚选择

### 3、移植至工程

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】

点击添加GPIO配置：

5. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

6. 然后点击编译（**可能会报错，我们不用管！**）
7. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_gyro.c**与**bsp_gyro.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_gyro.c**中，编写如下代码。

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
 * 2024-07-30     LCKFB        陀螺仪
 */

#include "bsp_gyro.h"
#include "stdio.h"
#include "string.h"

volatile Gyro_Struct Gyro_Structure;

void jy61pInit(void)
{

	/*================Z轴归零==================*/

	// 寄存器解锁
	uint8_t unlock_reg1[2] = {0x88,0xB5};
	writeDataJy61p(IIC_ADDR,UN_REG,unlock_reg1,2);
	delay_ms(200);
	// Z轴归零
	uint8_t z_axis_reg[2] = {0x04,0x00};
	writeDataJy61p(IIC_ADDR,ANGLE_REFER_REG,z_axis_reg,2);
	delay_ms(200);
	// 保存
	uint8_t save_reg1[2] = {0x00,0x00};
	writeDataJy61p(IIC_ADDR,SAVE_REG,save_reg1,2);
	delay_ms(200);

	/*================角度归零==================*/

	// 寄存器解锁
	uint8_t unlock_reg[2] = {0x88,0xB5};
	writeDataJy61p(IIC_ADDR,UN_REG,unlock_reg,2);
	delay_ms(200);
	// 角度归零
	uint8_t angle_reg[2] = {0x08,0x00};
	writeDataJy61p(IIC_ADDR,ANGLE_REFER_REG,angle_reg,2);
	delay_ms(200);
	// 保存
	uint8_t save_reg[2] = {0x00,0x00};
	writeDataJy61p(IIC_ADDR,SAVE_REG,save_reg,2);
	delay_ms(200);

	// 清空结构体
	memset(&Gyro_Structure,0,sizeof(Gyro_Structure));
}

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
        char ack_flag = 50;

        SDA_IN();

        SDA(1);
        while( (SDA_GET()==1) && ( ack_flag ) )
        {
                ack_flag--;
                delay_us(5);
        }

        if( ack_flag == 0 )
        {
                IIC_Stop();
                return 1;
        }
        else
        {
				SCL(1);
				delay_us(5);
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
		delay_us(2);

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

    return receive;
}

/******************************************************************
 * 函 数 名 称：writeDataJy61p
 * 函 数 说 明：写数据
 * 函 数 形 参：dev 设备地址
				reg 寄存器地址
				data 数据首地址
				length 数据长度
 * 函 数 返 回：返回0则写入成功
 * 作       者：LC
 * 备       注：无
******************************************************************/
uint8_t writeDataJy61p(uint8_t dev, uint8_t reg, uint8_t* data, uint32_t length)
{
    uint32_t count = 0;

    IIC_Start();

    Send_Byte(dev<<1);
    if(I2C_WaitAck() == 1)return 0;

    Send_Byte(reg);
    if(I2C_WaitAck() == 1)return 0;

    for(count=0; count<length; count++)
    {
        Send_Byte(data[count]);
        if(I2C_WaitAck() == 1)return 0;
    }

    IIC_Stop();

    return 1;
}

/******************************************************************
 * 函 数 名 称：readDataJy61p
 * 函 数 说 明：读数据数据
 * 函 数 形 参：dev 设备地址
				reg 寄存器地址
				data 数据存储地址
				length 数据长度
 * 函 数 返 回：返回0则写入成功
 * 作       者：LC
 * 备       注：无
******************************************************************/
uint8_t readDataJy61p(uint8_t dev, uint8_t reg, uint8_t *data, uint32_t length)
{
    uint32_t count = 0;

    IIC_Start();

    Send_Byte((dev<<1)|0);
    if(I2C_WaitAck() == 1)return 0;

    Send_Byte(reg);
    if(I2C_WaitAck() == 1)return 0;

	delay_us(5);

    IIC_Start();

    Send_Byte((dev<<1)|1);
    if(I2C_WaitAck() == 1)return 0;

    for(count=0; count<length; count++)
    {
        if(count!=length-1)
		{
			data[count]=Read_Byte();
			IIC_Send_Ack(0);
		}
        else
		{
			data[count]=Read_Byte();
			IIC_Send_Ack(1);
		}

    }

    IIC_Stop();

    return 1;
}

/******************************************************************
 * 函 数 名 称：get_angle
 * 函 数 说 明：读角度数据
 * 函 数 形 参：无
 * 函 数 返 回：返回结构体
 * 作       者：LC
 * 备       注：无
******************************************************************/
float get_angle(void)
{
	// 数据缓存
	volatile uint8_t sda_angle[6] = {0};

	int ret = 0;

	// 清空数据缓存
	memset(sda_angle,0,sizeof(sda_angle));

	// 读取寄存器数据
	ret	= readDataJy61p(IIC_ADDR,0x3D,sda_angle,6);

	if(ret == 0)
	{
		// 读取失败
		printf("Read Error\r\n");
	}

	#if GYRO_DEBUG

	printf("RollL = %x\r\n",sda_angle[0]);
	printf("RollH = %x\r\n",sda_angle[1]);
	printf("PitchL = %x\r\n",sda_angle[2]);
	printf("PitchH = %x\r\n",sda_angle[3]);
	printf("YawL = %x\r\n",sda_angle[4]);
	printf("YawH = %x\r\n",sda_angle[5]);

	#endif

    // 计算 RollX, PitchY 和 YawZ 并确保它们在 -180 到 180 的范围内
    float RollX = (float)(((sda_angle[1] << 8) | sda_angle[0]) / 32768.0 * 180.0);
    if (RollX > 180.0)
    {
        RollX -= 360.0;
    }
    else if (RollX < -180.0)
    {
        RollX += 360.0;
    }

    float PitchY = (float)(((sda_angle[3] << 8) | sda_angle[2]) / 32768.0 * 180.0);
    if (PitchY > 180.0)
    {
        PitchY -= 360.0;
    }
    else if (PitchY < -180.0)
    {
        PitchY += 360.0;
    }

    float YawZ = (float)(((sda_angle[5] << 8) | sda_angle[4]) / 32768.0 * 180.0);
    if (YawZ > 180.0)
    {
        YawZ -= 360.0;
    }
    else if (YawZ < -180.0)
    {
        YawZ += 360.0;
    }

    // 将计算结果保存到结构体中
    Gyro_Structure.x = RollX;
    Gyro_Structure.y = PitchY;
    Gyro_Structure.z = YawZ;

	// 返回角度数据
	return YawZ;
}
```

在文件**bsp_gyro.h**中，编写如下代码。

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
 * 2024-07-30     LCKFB        陀螺仪
 */
#ifndef	__BSP_GYRO_H__
#define __BSP_GYRO_H__

#include "board.h"

// 调试开关
#define GYRO_DEBUG	0

// 定义一个结构体来存储
typedef struct {
    float x;
    float y;
    float z;
} Gyro_Struct;

extern volatile Gyro_Struct Gyro_Structure;

// 模块地址
#define	IIC_ADDR		0x50
// 航向角地址
#define YAW_REG_ADDR	0x3F
// 寄存器解锁
#define UN_REG			0x69
// 保存寄存器
#define SAVE_REG		0x00
// 角度参考寄存器
#define ANGLE_REFER_REG	0x01

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

void jy61pInit(void);
uint8_t readDataJy61p(uint8_t dev, uint8_t reg, uint8_t *data, uint32_t length);
uint8_t writeDataJy61p(uint8_t dev, uint8_t reg, uint8_t* data, uint32_t length);
float get_angle(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include "bsp_gyro.h"
#include "stdio.h"

int main(void)
{
      board_init();
      jy61pInit();

      while (1)
      {
            int data = (int)get_angle();

            printf("Z = %d\r\n",data);

            delay_ms(100);
      }
}
```

上电效果：读取角度数据，方向转动，可以看到角度的变化。

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1Rh_qMSrTtxkwjKnj9LBO1w?pwd=5t75](https://pan.baidu.com/s/1Rh_qMSrTtxkwjKnj9LBO1w?pwd=5t75)**提取码**：5t75

## 百度网盘下载

- https://pan.baidu.com/s/1Rh_qMSrTtxkwjKnj9LBO1w?pwd=5t75
