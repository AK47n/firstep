# 16路舵机驱动模块

- 分类：控制类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/control/16-ch-servo-drive-module.html
- 标题：16路舵机驱动模块
- 代码块：4 个 · 图片：0 张

当你在一个项目中碰到了微控制器芯片的PWM输出引脚不够用的情况，那么这款PCA968516路舵机就能很快帮助您解决这个问题了。只要你的主控芯片具备了I2C通信，就能够让主控芯片和PCA9685通信，实现多个舵机的同时控制了。PCA9685 16路舵机是一个采用I2C通信，内置了PWM驱动器和一个时钟，这个意味着，这将和TLCG940系列有很大不同，你不需要不断发送信号占用你的单片机。它是5V的兼容，这意味你还可以用3.3V单片机控制并且安全地驱动到6V输出(当你想要控制白色或蓝色指示灯用3.4+正电压也是可以的)。地址选择引脚使你可以把62个驱动板挂在单个l2C总线上，总共有992路PWM输出，那将是非常庞大的资源，约1.6Khz可调频PWM输出，为步进电机准备输出12位分辨率，可配置的推拉输出或开路输出，输出使能引脚能够快速禁用所有输出。

## 一、模块来源

采购链接：

[16路PWM Servo 舵机驱动板机器人控制器IIC接口驱动器模块PCA9685](https://detail.tmall.com/item.htm?_u=52t4uge5cc3d&id=624960039615&spm=a1z09.2.0.0.47582e8dqqFD4i)

资料下载：

[https://pan.baidu.com/s/1FjoAuJm387bxaZxS6g9HEg](https://pan.baidu.com/s/1FjoAuJm387bxaZxS6g9HEg)

提取码：8888

## 二、规格参数

**输入电压**：3.3V~5V

**额定电流**：15mA

**控制方式**：IIC

**尺寸**： 21(长)\*21(宽)\[单位:mm]

以上信息见厂家资料文件

## 三、移植过程

### 1、查看资料

> **IIC器件地址**：PCA9685 是一个I2C 从设备，有个设备ID，或者叫从 地址。从地址是如下确定的：Board 0: Address = 0×40 Offset = binary 00000 (默认)Board 1: Address = 0×41 Offset = binary 00001 (A0接上拉)Board 2: Address = 0×42 Offset = binary 00010 (接上A1上拉)Board 3: Address = 0×43 Offset = binary 00011 (A0和A1上拉)Board 4: Address = 0×44 Offset = binary 00100 (A2上拉)以此类推；PCA9685的I2C总线从地址如下图所示。为了节约电力，硬件可选地址引脚上没有内部上拉电阻，它们必须被拉高或拉低。但是我们使用的是模块，而模块上已经为我们接好了上拉电阻。地址字节的最后一位定义要执行的操作。当设置为逻辑1时，将选择读操作，而逻辑0则选择写操作。 在原理图中，地址线全部接0，所以slave address是0x40。对应Fig 4上的位置，则为:则IIC地址是 0x80 ，写入时是0x80，读取时是0x81。

1. 舵机控制所需的 PWM 周期为20 ms． 在用 PCA9685 作为多舵机控制器时，需要将 其 PWM 输出周期设定为20 ms，即PWM 波的频率设定为50 Hz，PCA9685 输出频率与振荡器有关，频率的设置值refresh_rate见下面的公式；其中，EXTCLK是PCA9685的内部时钟频率为25Mhz；prescale是要设置的频率，我们设置为50Hz;refresh_rate = 25,000,000 /( 4096 \* ( 50 + 1 ))refresh_rate = 25,000,000 / 4096 / (50 + 1)refresh_rate = 6,103.52 / (50 + 1)refresh_rate = 6,103.52 / 51refresh_rate = 119.68所以我们需要设置的值是119.68，取整数就是120。需要注意的是，频率的更改只能在 PCA9685 芯片处于休眠状态下进行。以下加粗字体是数据手册内容：要使用EXTCLK引脚，该位必须按以下顺序设置:在mode1中设置SLEEP位。这就关闭了内部振荡器，使芯片处于休眠状态。
2. 将逻辑1写入MODE1中的SLEEP和EXTCLK位。这样就转换完成了。外部时钟可以在切换期间处于活动状态，因为设置了SLEEP位。

> **设置PWM频率**：这个位是一个“粘性位”，也就是说，它不能通过写入逻辑0来清除。EXTCLK位只能通过电源循环或软件重置来清除。 占空比或者脉冲宽度的设定每个PWM引脚输出的开启时间和PWM的占空比可以通过LEDn_ON和LEDn_OFF寄存器独立控制。每个PWM引脚输出将有两个12位寄存器。这些寄存器将由用户编程。两个寄存器都将保存从0到4095的值。一个12位寄存器将保存ON时间的值，另一个12位寄存器将保存OFF时间的值。将ON和OFF时间与12位计数器的值进行比较，该计数器将从0000h持续运行到0FFFh(0到4095十进制)。ON时间是可编程的，它是PWM输出ON的时间，OFF时间也是可编程的，它是PWM输出OFF的时间。这样相移就完全可编程了。相移的分辨率为目标频率的1 / 4096。表7列出了这些寄存器。以下用一个例子说明如何计算要加载到这些寄存器中的值。(假设使用LED0输出，(延时时间)+ (PWM占空比)<=100%)延迟时间 = 10%;PWM占空比= 20% (LEDON电平= 20%;LEDOFF时间= 80%)。延迟时间= 10% = 4096 \* 0.1 = 409.6 ~ 410，计数= 410（十进制） = 19Ah（十六进制）因为计数器从0开始，到4095结束，我们将减去1，所以延迟时间 = 199h 个数。LED0_ON_H = 1h;LED0_ON_L = 99h (LED开始打开后，这个延迟计数到409)LED开机时间= 20% = 819.2 ~ 819次LED关闭时间= 4CCh(十进制410 + 819-1 = 1228)LED0_OFF_H = 4h;LED0_OFF_L = CCh(此计数到1228后LED开始关闭)整个周期为4095， LED_ON 和 LED_OFF 2个的设定值确定脉宽，在后面的代码里，LED_ON 设为0， LED_OFF就是脉宽了。 这里都用2位字节来表示。

```c
// 相关地址表
// 这里只截图了需要的地址，分别是：
#define PCA_Addr            0x80    //IIC地址
#define PCA_Model           0x00
#define LED0_ON_L           0x06
#define LED0_ON_H           0x07
#define LED0_OFF_L          0x08
#define LED0_OFF_H          0x09
#define PCA_Pre             0xFE    //配置频率地址
```

> **相关地址表**

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_pca9685.c**与**bsp_pca9685.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_pca9685.c**中，编写如下代码。

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
 * 2024-07-08     LCKFB-LP    first version
 */

#include "bsp_pca9685.h"
#include "stdio.h"
#include <math.h>

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
        delay_us(5);
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
 * 函 数 名 称：PCA9685_Write
 * 函 数 说 明：向PCA9685写命令或数据
 * 函 数 形 参：addr写入的寄存器地址    data写入的命令或数据
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void PCA9685_Write(uint8_t addr,uint8_t data)
{
        IIC_Start();

        Send_Byte(PCA_Addr);
        I2C_WaitAck();

        Send_Byte(addr);
        I2C_WaitAck();

        Send_Byte(data);
        I2C_WaitAck();

        IIC_Stop();
}

/******************************************************************
 * 函 数 名 称：PCA9685_Read
 * 函 数 说 明：读取PCA9685数据
 * 函 数 形 参：addr读取的寄存器地址
 * 函 数 返 回：读取的数据
 * 作       者：LC
 * 备       注：无
******************************************************************/
uint8_t PCA9685_Read(uint8_t addr)
{
        uint8_t data;

        IIC_Start();

        Send_Byte(PCA_Addr);
        I2C_WaitAck();

        Send_Byte(addr);
        I2C_WaitAck();

        IIC_Stop();

        delay_us(10);

        IIC_Start();

        Send_Byte(PCA_Addr|0x01);
        I2C_WaitAck();

        data = Read_Byte();
        IIC_Send_Ack(1);
        IIC_Stop();

        return data;
}
/******************************************************************
 * 函 数 名 称：PCA9685_setPWM
 * 函 数 说 明：设置第num个PWM引脚，on默认为0，控制舵机旋转off角度
 * 函 数 形 参：num：设置第几个引脚输出，范围0~15
 *              on ：默认为0
 *              off：舵机旋转角度，范围：0~180
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void PCA9685_setPWM(uint8_t num,uint32_t on,uint32_t off)
{
        IIC_Start();

        Send_Byte(PCA_Addr);
        I2C_WaitAck();

        Send_Byte(LED0_ON_L+4*num);
        I2C_WaitAck();

        Send_Byte(on&0xFF);
        I2C_WaitAck();

        Send_Byte(on>>8);
        I2C_WaitAck();

        Send_Byte(off&0xFF);
        I2C_WaitAck();

        Send_Byte(off>>8);
        I2C_WaitAck();

        IIC_Stop();

}

/******************************************************************
 * 函 数 名 称：PCA9685_setFreq
 * 函 数 说 明：设置PCA9685的输出频率
 * 函 数 形 参：freq
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：
floor语法：
FLOOR(number, significance)
    Number必需。要舍入的数值。
    Significance必需。要舍入到的倍数。
说明
    将参数 number 向下舍入（沿绝对值减小的方向）为最接近的 significance 的倍数。
    如果任一参数为非数值型，则 FLOOR 将返回错误值 #VALUE!。
    如果 number 的符号为正，且 significance 的符号为负，则 FLOOR 将返回错误值 #NUM!
示例
    公式                                说明                                                                结果
    FLOOR(3.7,2)                将 3.7 沿绝对值减小的方向向下舍入，使其等于最接近的 2 的倍数                2
    FLOOR(-2.5, -2)                将 -2.5 沿绝对值减小的方向向下舍入，使其等于最接近的 -2 的倍数                -2
******************************************************************/
void PCA9685_setFreq(float freq)
{
        uint8_t prescale,oldmode,newmode;

        double prescaleval;

//        freq *= 0.9;  // Correct for overshoot in the frequency setting (see issue #11).

//        PCA9685的内部时钟频率是25Mhz
//        公式: presale_Volue = round( 25000000/(4096 * update_rate) ) - 1
//        round = floor();  floor是数学函数，需要导入 math.h 文件
//        update_rate = freq;
        prescaleval = 25000000;
        prescaleval /= 4096;
        prescaleval /= freq;
        prescaleval -= 1;
        prescale = floor(prescaleval+0.5f);

        //返回MODE1地址上的内容（保护其他内容）
        oldmode = PCA9685_Read(PCA_Model);

        //在MODE1中设置SLEEP位
        newmode = (oldmode&0x7F)|0x10;
        //将更改的MODE1的值写入MODE1地址,使芯片睡眠
        PCA9685_Write(PCA_Model,newmode);
        //写入我们计算的设置频率的值
        //PCA_Pre = presale 地址是0xFE，可以数据手册里查找到
        PCA9685_Write(PCA_Pre,prescale);
        //重新复位
        PCA9685_Write(PCA_Model,oldmode);
        //等待复位完成
        delay_1ms(5);
        //设置MODE1寄存器开启自动递增
        PCA9685_Write(PCA_Model,oldmode|0xa1);
}

//
/******************************************************************
 * 函 数 名 称：setAngle
 * 函 数 说 明：设置角度
 * 函 数 形 参：num要设置的PWM引脚     angle设置的角度
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void setAngle(uint8_t num,uint8_t angle)
{
        uint32_t off = 0;

        off = (uint32_t)(158+angle*2.2);

        PCA9685_setPWM(num,0,off);
}

/******************************************************************
 * 函 数 名 称：PCA9685_Init
 * 函 数 说 明：PCA9685初始化，所有PWM输出频率配置与所有PWM引脚输出的舵机角度
 * 函 数 形 参：hz设置的初始频率  angle设置的初始角度
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void PCA9685_Init(float hz,uint8_t angle)
{
        uint32_t off = 0;

        //在MODE1地址上写0x00
        PCA9685_Write(PCA_Model,0x00);        //这一步很关键，如果没有这一步PCA9685就不会正常工作。

//        pwm.setPWMFreq(SERVO_FREQ)函数主要是设置PCA9685的输出频率，
//        PCA9685的16路PWM输出频率是一致的，所以是不能实现不同引脚不同频率的。
//        下面是setPWMFreq函数的内容，主要是根据频率计算PRE_SCALE的值。
        PCA9685_setFreq(hz);
        //计算角度
        off = (uint32_t)(145+angle*2.4);

        //控制16个舵机输出off角度
        PCA9685_setPWM(0,0,off);
        PCA9685_setPWM(1,0,off);
        PCA9685_setPWM(2,0,off);
        PCA9685_setPWM(3,0,off);
        PCA9685_setPWM(4,0,off);
        PCA9685_setPWM(5,0,off);
        PCA9685_setPWM(6,0,off);
        PCA9685_setPWM(7,0,off);
        PCA9685_setPWM(8,0,off);
        PCA9685_setPWM(9,0,off);
        PCA9685_setPWM(10,0,off);
        PCA9685_setPWM(11,0,off);
        PCA9685_setPWM(12,0,off);
        PCA9685_setPWM(13,0,off);
        PCA9685_setPWM(14,0,off);
        PCA9685_setPWM(15,0,off);

        delay_1ms(100);

}
```

在文件**bsp_pca9685.h**中，编写如下代码。

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
 * 2024-07-08     LCKFB-LP    first version
 */

#ifndef _BSP_PCA9685_H_
#define _BSP_PCA9685_H_

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

#define PCA_Addr              0x80        //IIC地址
#define PCA_Model             0x00
#define LED0_ON_L             0x06
#define LED0_ON_H             0x07
#define LED0_OFF_L            0x08
#define LED0_OFF_H            0x09
#define PCA_Pre               0xFE        //配置频率地址

void PCA9685_Init(float hz,uint8_t angle);
void setAngle(uint8_t num,uint8_t angle);
void PCA9685_setFreq(float freq);
void PCA9685_setPWM(uint8_t num,uint32_t on,uint32_t off);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_pca9685.h"

int main(void)
{
    //开发板初始化
    board_init();

    uint8_t i = 0;

    PCA9685_Init(60,0);        //PCA9685--16路舵机初始化  频率60Hz -- 0度

    printf("start\r\n");

    delay_ms(1000);

    while(1)
    {
        i = ( i + 1 ) % 180;
        setAngle(0,i);
        delay_ms(10);
    }
}
```

上电效果：0号接口的舵机从0度一直移动到180度后，又回到0度。

模块代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1q4a8EzJPYC2jh-v7TtG9-g?pwd=ojep](https://pan.baidu.com/s/1q4a8EzJPYC2jh-v7TtG9-g?pwd=ojep)**提取码**：ojep

## 百度网盘下载

- https://pan.baidu.com/s/1FjoAuJm387bxaZxS6g9HEg
- https://pan.baidu.com/s/1q4a8EzJPYC2jh-v7TtG9-g?pwd=ojep
