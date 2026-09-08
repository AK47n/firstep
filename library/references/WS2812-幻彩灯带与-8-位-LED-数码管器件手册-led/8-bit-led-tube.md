# 8位数码管显示模块

- 分类：显示类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/screen/8-bit-led-tube.html
- 标题：8位数码管显示模块
- 代码块：7 个 · 图片：0 张

## 一、模块来源

**采购链接**： [0.36寸 8位数码管显示模块 MAX7219控制8位数码管/串口/级联](https://item.taobao.com/item.htm?spm=a1z10.3-c-s.w4002-24706531953.10.43be6a4bCZwggY&id=575339214274)

**资料下载链接**： [https://pan.baidu.com/s/15TcV9HevtfVBWcm7pgRNTw](https://pan.baidu.com/s/15TcV9HevtfVBWcm7pgRNTw)

**资料提取码**：e1q5

## 二、规格参数

**工作电压**：4-5.5V

**工作电流**：8-330MA

**扫描速率**：500-1300Hz

**通信协议**：单总线

**管脚数量**：5 Pin（2.54mm间距排针）

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

#### 时序讲解

- 无论数据输入或输出CS端必须为低电平。然后数据在CS端的上升沿被载入数据寄存器或控制寄存器。CS端在第 16个时钟的上升沿之后，下个时钟上升沿之前变为高电平，否则数据将会丢失。
- 对 MAX7219 来说，串行数据在 DIN 输入 16 位数据包，在CLK的上升沿数据均移入到内部 16 位移位寄存器。即DIN不能在CLK的上升沿时进行数据变换。

#### 数据位讲解

DIN传输的16位数据包说明，见表格000。其中D8-D11 为寄存器地址位。D0-D7 为数据位。D12-D15 为无效位。

根据以上的时序说明和传输格式，实现的数据传输代码。

```c
//向MAX7219写入字节
//dat写入的数据
void Write_Max7219_byte(uint8_t dat)
{
    uint8_t i;
    MAX7219_CS(0);//确认CS拉低
    for(i=8;i>=1;i--)//传输8位
    {
        MAX7219_CLK(0);//拉低CLK
        //当前数据位是否为1
        if( dat&0x80 )
        {
            MAX7219_DIN(1);
        }
        else
        {
            MAX7219_DIN(0);
        }
        dat=dat<<1;//准备下一位数据
        //CLK拉高将数据载入寄存器
        MAX7219_CLK(1);
    }
}
```

```c
//向MAX7219写入数据
//address写入地址  dat写入数据
void Write_Max7219(uint8_t address,uint8_t dat)
{
    //CS拉低
    MAX7219_CS(0);
    //传输高8位数据（寄存器地址）
    Write_Max7219_byte(address);
    //传输低8位数据（数据）
    Write_Max7219_byte(dat);
    //CS拉高
    MAX7219_CS(1);
}
```

#### 关键寄存器讲解

相关寄存器地址，见下表。这里先讲解0X09译码方式寄存器。

我们发送的数据位是16位，而进入译码方式寄存器只使用到了D15-D8数据位（0x09），还有D7到D0没有设置。而根据数据手册的说明，关于译码方式寄存器的D7-D0的设置在数据手册的表格4.

按照图中所示，如果要设置译码方式为全部数码管都进行译码，那么要发送：

```c
//高8位=0x09（寄存器地址）, 低8位=0xff（数据）
Write_Max7219(0x09,0xff);
```

**在全部数码管都进行译码的情况下，如果想要第0个数码管显示数字3，第1个数码管不显示应如何操作？**

> 先在数据手册中找到关于第0个数码管和第1个数码管的寄存器地址。根据右图显示得知，第0个数码管的地址是0X01；第1个数码管的地址是0X02。知道地址后，根据数据手册提示找到数据位设置表，因为全部数码管都进行了译码，那么只需要发送：

```c
//高8位=0x01（寄存器地址）, 低8位=0x03（数据）
Write_Max7219(0x01,0x03);//第0个数码管显示数字3
//高8位=0x02（寄存器地址）, 低8位=0x0F（数据）
Write_Max7219(0x02,0x0F);//第1个数码管b不显示
```

### 2、引脚选择

该模块有10个引脚，其中有5个是接入下一个级联的数码管。如果不接入下一个级联的数码管，则只要接5个引脚，具体引脚连接见**各引脚连接**。

### 3、移植至工程

我们新建两个文件分别是 **bsp_max7219.c** 和 **bsp_max7219.h** ，然后将C文件添加至工程中，将h文件路径添加到工程中。

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】【添加**3**个】
5. 开始添加配置，根据引脚选择设定
6. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

7. 然后点击编译（**可能会报错，我们不用管！**）
8. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

在文件**bsp_max7219.c**中，编写如下代码。

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
 * 2024-06-27     LCKFB-LP    first version
 */
#include "bsp_max7219.h"
#include "stdio.h"

/******************************************************************
 * 函 数 名 称：Write_Max7219_byte
 * 函 数 说 明：向MAX7219写入字节
 * 函 数 形 参：dat写入的数据
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void Write_Max7219_byte(uint8_t dat)
{
    uint8_t i;
    MAX7219_CS(0);
    for(i=8;i>=1;i--)
    {
        MAX7219_CLK(0);
        if( dat&0x80 )
        {
            MAX7219_DIN(1);
        }
        else
        {
            MAX7219_DIN(0);
        }
        dat=dat<<1;
        MAX7219_CLK(1);
    }
}

/******************************************************************
 * 函 数 名 称：Write_Max7219
 * 函 数 说 明：向MAX7219写入数据
 * 函 数 形 参：address写入地址  dat写入数据
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void Write_Max7219(uint8_t address,uint8_t dat)
{
        MAX7219_CS(0);
        Write_Max7219_byte(address);           //写入地址，即数码管编号1-8
        Write_Max7219_byte(dat);               //写入数据，即数码管显示内容字
        MAX7219_CS(1);
}

/******************************************************************
 * 函 数 名 称：Write_Max7219_2
 * 函 数 说 明：向第二片MAX7219写入数据
 * 函 数 形 参：address写入地址  dat写入数据
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：只有接入第二片MAX7219才可以用
******************************************************************/
void Write_Max7219_2(uint8_t address,uint8_t dat)
{
        MAX7219_CS(0);
        Write_Max7219_byte(address);   //写入地址，即数码管编号1-8
        Write_Max7219_byte(dat);       //写入数据，即数码管显示内容
        MAX7219_CLK(1);
        Write_Max7219_byte(0X00);      //对第一片执行空操作
        Write_Max7219_byte(0X00);
        MAX7219_CS(1);
}

/******************************************************************
 * 函 数 名 称：Write_Max7219_AllOff
 * 函 数 说 明：控制第一片MAX7219的全部数码管全灭
 * 函 数 形 参：address写入地址  dat写入数据
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：
******************************************************************/
void Write_Max7219_AllOff(void)
{
    int i =  0;
    for( i = 1; i < 9; i++ )
    {
        MAX7219_CS(0);
        Write_Max7219_byte(i);   //写入地址，即数码管编号1-8
        Write_Max7219_byte(15);  //全灭
        MAX7219_CS(1);
    }

}
/******************************************************************
 * 函 数 名 称：MAX7219_Init
 * 函 数 说 明：MAX7219初始化
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void MAX7219_Init(void)
{
    Write_Max7219(0x09, 0xff);       //译码方式：BCD码
    Write_Max7219(0x0a, 0x03);       //亮度
    Write_Max7219(0x0b, 0x07);       //扫描界限；4个数码管显示
    Write_Max7219(0x0c, 0x01);       //掉电模式：0，普通模式：1
    Write_Max7219(0x0f, 0x01);       //显示测试：1；测试结束，正常显示：0
}
```

在文件**bsp_max7219.h**中，编写如下代码。

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
 * 2024-06-27     LCKFB-LP    first version
 */
#ifndef _BSP_MAX7219_H_
#define _BSP_MAX7219_H_

#include "board.h"

#define MAX7219_CLK(X) ( X ? DL_GPIO_setPins(MAX7219_PORT,MAX7219_CLK_PIN) : DL_GPIO_clearPins(MAX7219_PORT,MAX7219_CLK_PIN) )
#define MAX7219_DIN(X) ( X ? DL_GPIO_setPins(MAX7219_PORT,MAX7219_DIN_PIN) : DL_GPIO_clearPins(MAX7219_PORT,MAX7219_DIN_PIN) )
#define MAX7219_CS(X)  ( X ? DL_GPIO_setPins(MAX7219_PORT,MAX7219_CS_PIN) : DL_GPIO_clearPins(MAX7219_PORT,MAX7219_CS_PIN) )

void Write_Max7219(uint8_t address,uint8_t dat);
void Write_Max7219_2(uint8_t address,uint8_t dat);
void Write_Max7219_AllOff(void);
void MAX7219_Init(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_max7219.h"

int main(void)
{
    //开发板初始化
    board_init();

    int i =0;

    MAX7219_Init();
    delay_ms(1000);

    Write_Max7219(0x0f, 0x00);       //显示测试：1；测试结束，正常显示：0

    Write_Max7219_AllOff();//数码管全灭
    printf("MAX7219 demo start\r\n");
    while(1)
    {
        //第一个显示1，第二个显示2，第三个显示3...
        for( i = 1; i < 9; i++ )//从1显示到8
        {
            Write_Max7219(i, i);
            delay_ms(1000);
        }
    }
}
```

上电效果：

> **【百度网盘下载链接】**：**链接**：[https://pan.baidu.com/s/1-butixB64YlI5apjZIl3xQ?pwd=et5o](https://pan.baidu.com/s/1-butixB64YlI5apjZIl3xQ?pwd=et5o)**提取码**：et5o

## 百度网盘下载

- https://pan.baidu.com/s/15TcV9HevtfVBWcm7pgRNTw
- https://pan.baidu.com/s/1-butixB64YlI5apjZIl3xQ?pwd=et5o
