# WS2812彩灯

- 分类：控制类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/control/ws2812-color-rgb-led.html
- 标题：WS2812彩灯
- 代码块：3 个 · 图片：0 张

WS2812E是一个集控制电路与发光电路于一体的智能外控LED光源。其外型与一个5050LED灯珠相同，每个 元件即为一个像素点。像素点内部包含了智能数字接口数据锁存信号整形放大驱动电路，还包含有高精度的内部 振荡器和可编程定电流控制部分，有效保证了像素点光的颜色高度一致。

## 一、模块来源

采购链接：

[8位WS2812 RGB全彩LED模块 5050LED灯珠内置全彩驱动直板DIY](https://item.taobao.com/item.htm?spm=a1z10.3-c-s.w4002-24706531953.16.223a6a4bKqBE02&id=558408103026)

资料下载链接：

[https://pan.baidu.com/s/1OkCpw8ooDyuw947V0b89Rw](https://pan.baidu.com/s/1OkCpw8ooDyuw947V0b89Rw)

提取码：AB12

## 二、规格参数

**工作电压**：3.7-5.3V

**工作电流**：16MA

**控制方式**：单总线

**管脚数量**：4 Pin（2.54mm间距排针）

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够实现设置彩灯颜色的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

WS2812的数据协议采用单线归零码的通讯方式，支持串行级联接口，能通过一根信号线完成数据的接收与解码。每个灯就是一个像素点，每个像素点的三基色颜色可实现256级亮度显示，完成16777216种颜色的全真色彩显示。

像素点在上电复位以后，DIN端接受从控制器传输过来的数据，首先送过来的24bit数据被第一个像素点提取后，送到像素点内部的数据锁存器，剩余的数据经过内部整形处理电路整 形放大后通过DO端口开始转发输出给下一个级联的像素点，每经过一个像素点的传输，信号减少24bit。像素点采用自动整形转发技术，使得该像素点的级联个数不受信号传送的限制，仅受限信号传输速度要求。

> **控制方式**：因为使用的是单总线，一根线完成一个灯要显示的24位颜色数据，是通过高低电平的时间长度来确定发送的是什么数据。24位的数据结构见下图。  其中G代表三色中的绿色，R代表三色中的红色，B表示三色中的蓝色。例如想要只显示红色则发送 0X00FF00即可。

> **控制时序**：发送24位颜色数据，是通过高低电平的时间长度来确定发送的是0还是1。发送一位数据0，需要总线拉高T0H的时间再拉低T0L的时间，WS2812才会自动识别该数据是0。发送一位数据1，需要总线拉高T1H的时间再拉低T1L的时间，WS2812才会自动识别该数据是1

### 2、引脚选择

该模块有3个引脚，具体引脚连接见**各引脚连接**。

### 3、移植至工程

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】【添加**1**个】
5. 开始添加配置，根据引脚选择设定
6. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

7. 然后点击编译（**可能会报错，我们不用管！**）
8. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

移植步骤中的导入.c和.h文件与传感器章节的【DHT11温湿度传感器】相同，只是将.c和.h文件更改为**bsp_ws2812.c**与**bsp_ws2812.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_ws2812.c**中，编写如下代码。

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
 * 2024-07-05     LCKFB-LP    first version
 */
#include "bsp_ws2812.h"
#include "stdio.h"
#include "math.h"

unsigned char LedsArray[WS2812_MAX * 3];      //定义颜色数据存储数组
unsigned int  ledsCount   = WS2812_NUMBERS;   //定义实际彩灯默认个数
unsigned int  nbLedsBytes = WS2812_NUMBERS*3; //定义实际彩灯颜色数据个数

// 延时0.25us
void delay_0_25us(void)
{
     for(int i = 0; i < 5; i++){}
}

/******************************************************************
 * 函 数 名 称：rgb_SetColor
 * 函 数 说 明：设置彩灯颜色
 * 函 数 形 参：LedId控制的第几个灯  color颜色数据
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：在这里我将绿和红色进行颠倒，这样比较符合我们日常生活的红绿蓝的顺序
******************************************************************/

void rgb_SetColor(unsigned char LedId, unsigned long color)
{
    if( LedId > ledsCount )
    {
        return;    //to avoid overflow
    }
    LedsArray[LedId * 3]     = (color>>8)&0xff;
    LedsArray[LedId * 3 + 1] = (color>>16)&0xff;
    LedsArray[LedId * 3 + 2] = (color>>0)&0xff;
}

/******************************************************************
 * 函 数 名 称：rgb_SetRGB
 * 函 数 说 明：设置彩灯颜色(三原色设置)
 * 函 数 形 参：LedId控制的第几个灯 red红色数据  green绿色数据  blue蓝色数据
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void rgb_SetRGB(unsigned char LedId, unsigned long red, unsigned long green, unsigned long blue)
{
    unsigned long Color=red<<16|green<<8|blue;
    rgb_SetColor(LedId,Color);
}

/******************************************************************
 * 函 数 名 称：rgb_SendArray
 * 函 数 说 明：发送彩灯数据
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void rgb_SendArray(void)
{
    unsigned int i;
    //发送数据
    for(i=0; i<nbLedsBytes; i++)
        Ws2812b_WriteByte(LedsArray[i]);
}

/******************************************************************
 * 函 数 名 称：RGB_LED_Reset
 * 函 数 说 明：复位ws2812
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：低电平280us以上
******************************************************************/
void RGB_LED_Reset(void)
{
        RGB_PIN_L();
        delay_us(285);
}

/******************************************************************
 * 函 数 名 称：Ws2812b_WriteByte
 * 函 数 说 明：向WS2812写入单字节数据
 * 函 数 形 参：byte写入的字节数据
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：1码的时序 = 高电平580ns~1us    再低电平220ns~420ns
 *              0码的时序 = 高电平220ns~380ns  再低电平580ns~1us
******************************************************************/
void Ws2812b_WriteByte(unsigned char byte)
{
      int i = 0, j = 0, k = 0;
      for(i = 0; i < 8; i++ )
      {
            if( byte & (0x80 >> i) )//当前位为1
            {
                  RGB_PIN_H();

                  //0.75us
                  delay_us(1);

                  RGB_PIN_L();

                  delay_0_25us(); //0.25us
            }
            else//当前位为0
            {
                  RGB_PIN_H();
                  delay_0_25us(); //0.25us
                  RGB_PIN_L();

                  //0.833us
                  delay_us(1);
            }
      }
}
```

在文件**bsp_ws2812.h**中，编写如下代码。

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
 * 2024-07-05     LCKFB-LP    first version
 */

#ifndef _BSP_WS2812_H_
#define _BSP_WS2812_H_

#include "board.h"

#define WS2812_MAX        8   //彩灯最大个数
#define WS2812_NUMBERS    8   //彩灯个数

//用户修改参数区
//#define WS2812_FREQUENCY
#define RGB_PIN_L()       DL_GPIO_clearPins(WS2812_PORT, WS2812_IN_PIN)  //控制彩灯引脚（需要配置为强推挽输出）
#define RGB_PIN_H()       DL_GPIO_setPins(WS2812_PORT, WS2812_IN_PIN)    //控制彩灯引脚（需要配置为强推挽输出）

#define RED               0xff0000                  //红色
#define GREEN             0x00ff00                  //绿色
#define BLUE              0x0000ff                  //蓝色
#define BLACK             0x000000                  //熄灭
#define WHITE             0xffffff                  //白色

//8.3 -8  0.000000083
//4.16 -9 0.00000000416
void Ws2812b_WriteByte(unsigned char byte);//发送一个字节数据（@12.000MHz,理论每个机器周期83ns,测试约为76ns）
void setLedCount(unsigned char count);//设置彩灯数目，范围0-25.
unsigned char getLedCount();//彩灯数目查询函数
void rgb_SetColor(unsigned char LedId, unsigned long color);//设置彩灯颜色
void rgb_SetRGB(unsigned char LedId, unsigned long red, unsigned long green, unsigned long blue);//设置彩灯颜色
void rgb_SendArray();//发送彩灯数据

void WS2812_GPIO_Init(void);

void RGB_LED_Write1(void);
void RGB_LED_Reset(void);

void delay_0_25us(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_ws2812.h"

uint8_t Co = 100;
unsigned int buff[]={RED,GREEN,BLUE,WHITE};

int main(void)
{
      //开发板初始化
      board_init();

      int i = 0;

      printf("Start--->\r\n");

      while(1)
      {
            for( i = 0; i < 8; i++ )
            {
                  rgb_SetColor(i,buff[i%3]);
                  rgb_SendArray();
                  delay_ms(10);
            }
            delay_ms(3000);

            i = 0;
            while( Co )
            {
                  rgb_SetColor((i+0)%8,buff[0]);
                  rgb_SetColor((i+1)%8,buff[1]);
                  rgb_SetColor((i+2)%8,buff[2]);
                  rgb_SetColor((i+3)%8,buff[3]);

                  rgb_SetColor((i+4)%8,BLACK);
                  rgb_SetColor((i+5)%8,BLACK);
                  rgb_SetColor((i+6)%8,BLACK);
                  rgb_SetColor((i+7)%8,BLACK);

                  rgb_SendArray();
                  delay_ms(200);
                  Co--;
                  i++;
            }
            Co = 100;
      }
}
```

上电效果：三秒前八个灯全亮，后面循环流水灯显示。

模块代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1NsfhskbwIaArsrKMfCYNgw?pwd=mw2n](https://pan.baidu.com/s/1NsfhskbwIaArsrKMfCYNgw?pwd=mw2n)**提取码**：mw2n

## 百度网盘下载

- https://pan.baidu.com/s/1OkCpw8ooDyuw947V0b89Rw
- https://pan.baidu.com/s/1NsfhskbwIaArsrKMfCYNgw?pwd=mw2n
