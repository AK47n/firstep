# 1.3寸彩屏

- 分类：显示类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/screen/1-3-color-screen.html
- 标题：1.3寸彩屏
- 代码块：4 个 · 图片：1 张

## 一、模块来源

**采购链接**： [1.3寸ips 240X240TFT显示屏液晶st7789 ips显示屏带字库高清ips](https://item.taobao.com/item.htm?spm=a1z10.3-c-s.w4002-23991449512.34.a884703bPrf8rV&id=568022083426)

**资料下载链接**： [https://pan.baidu.com/s/18tt2PzcnTvqTRubdRy2yoQ](https://pan.baidu.com/s/18tt2PzcnTvqTRubdRy2yoQ)

**资料提取码**：8888

## 二、规格参数

**工作电压**：2.4V-3.3V

**工作电流**：40MA

**模块尺寸**：27.78(H) x 39.22(V) MM

**像素大小**：240(H) x 240(V)RGB

**驱动芯片**：ST7789V2

**通信协议**：SPI

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上。按照以下步骤，即可完成移植。

1. 将源码导入工程；
2. 根据编译报错处进行粗改；
3. 修改引脚配置；
4. 修改时序配置；
5. 移植验证。

### 1、查看资料

打开厂家资料例程（例程下载见**百度网盘链接**下载）。具体路径见**例程路径**

### 2、移植至工程

将厂家资料路径下的【LCD】文件夹，复制到自己的工程中。（工程可以参考**入门手册工程模板**）

我们打开工程文件，将我们刚刚复制到文件夹中的文件，导入C文件和路径。

![img](images/1-3-color-screen/img1.gif)

将**lcd_init.h**文件下的 **sys.h** 改为 **board.h**。还要将**lcd.h**文件下的 **sys.h** 改为 **board.h**

> **TIP**：(在左边将lcd.c和lcd_init.c的工程目录展开，就发现有lcd_init.h和lcd.h)

将 **lcd_init.c** 和 **lcd.c** 中的 **delay.h** 注释掉

首先分别在lcd_init.h与lcd.h文件中定义三个宏，u32、u16与u8。

```c
#ifndef u8
#define u8 uint8_t
#endif

#ifndef u16
#define u16 uint16_t
#endif

#ifndef u32
#define u32 uint32_t
#endif
```

### 3、引脚选择

该屏幕需要设置10个接口。

模块为SPI通信协议的从机，SCL为SPI信号线（SCK），SDA为SPI输出线（MOSI），CS为SPI片选线（NSS）。 如果MCU的GPIO引脚不足，可以将屏幕的两个引脚接口不接入MCU的GPIO。

- 将RES接入MCU的复位引脚，当MCU复位时，屏幕也跟着复位；
- 可以将BLK接入3.3V或悬空，代价是无法控制背光亮度。

#### 软件SPI移植

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】【添加**8**个】
5. 开始添加配置，根据引脚选择设定
6. FSO引脚的配置为输入，剩余的配置都和上面截图一致。
7. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

8. 然后点击编译（**可能会报错，我们不用管！**）
9. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

选择好引脚后，进入工程开始编写屏幕引脚初始化代码。

我们更改lcd_init.h中的LCD端口定义

```c
//-----------------LCD端口定义----------------

#define LCD_SCLK_Clr() DL_GPIO_clearPins(LCD_PORT,LCD_SCL_PIN)//SCL=SCLK
#define LCD_SCLK_Set() DL_GPIO_setPins(LCD_PORT,LCD_SCL_PIN)

#define LCD_MOSI_Clr() DL_GPIO_clearPins(LCD_PORT,LCD_SDA_PIN)//SDA=MOSI
#define LCD_MOSI_Set() DL_GPIO_setPins(LCD_PORT,LCD_SDA_PIN)

#define LCD_RES_Clr()  DL_GPIO_clearPins(LCD_PORT,LCD_RES_PIN)//RES
#define LCD_RES_Set()  DL_GPIO_setPins(LCD_PORT,LCD_RES_PIN)

#define LCD_DC_Clr()   DL_GPIO_clearPins(LCD_PORT,LCD_DC_PIN)//DC
#define LCD_DC_Set()   DL_GPIO_setPins(LCD_PORT,LCD_DC_PIN)

#define LCD_CS_Clr()   DL_GPIO_clearPins(LCD_PORT,LCD_CS1_PIN)//CS1
#define LCD_CS_Set()   DL_GPIO_setPins(LCD_PORT,LCD_CS1_PIN)

#define LCD_BLK_Clr()  DL_GPIO_clearPins(LCD_PORT,LCD_BLK_PIN)//BLK
#define LCD_BLK_Set()  DL_GPIO_setPins(LCD_PORT,LCD_BLK_PIN)

#define ZK_MISO        DL_GPIO_readPins(LCD_PORT,LCD_FSO_PIN)//MISO  读取字库数据引脚

#define ZK_CS_Clr()    DL_GPIO_clearPins(LCD_PORT,LCD_CS2_PIN)//CS2 字库片选
#define ZK_CS_Set()    DL_GPIO_setPins(LCD_PORT,LCD_CS2_PIN)
```

引脚初始化函数见如下代码。因为引脚已经在 **SYSCONFIG** 中自动配置了，不需要进行初始化了。

```c
void LCD_GPIO_Init(void)
{

}
```

到这里软件SPI就移植完成了，可移步到第四节进行移植验证。

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "lcd_init.h"
#include "lcd.h"
#include "pic.h"

int main(void)
{
    board_init();

    u8 i,j;
    float t=0;

    LCD_Init();//LCD初始化
    LCD_Fill(0,0,LCD_W,LCD_H,WHITE);

    while(1)
    {
        LCD_ShowString(0,40,(uint8_t *)"LCD_W:",RED,WHITE,16,0);
        LCD_ShowIntNum(48,40,LCD_W,3,RED,WHITE,16);
        LCD_ShowString(80,40,(uint8_t *)"LCD_H:",RED,WHITE,16,0);
        LCD_ShowIntNum(128,40,LCD_H,3,RED,WHITE,16);
        LCD_ShowString(80,40,(uint8_t *)"LCD_H:",RED,WHITE,16,0);
        LCD_ShowString(0,70,(uint8_t *)"Increaseing Nun:",RED,WHITE,16,0);
        LCD_ShowFloatNum1(128,70,t,4,RED,WHITE,16);
        for(j=0;j<3;j++)
        {
            for(i=0;i<6;i++)
            {
                LCD_ShowPicture(40*i,120+j*40,40,40,gImage_1);
            }
        }
        delay_ms(1000);
        LCD_Fill(0,0,LCD_W,LCD_H,WHITE);
        Display_Asc_String(0,15,7, (uint8_t *)"ASCII_5x7",RED,WHITE);      //ASC 5X7点阵
        Display_Asc_String(0,25,8, (uint8_t *)"ASCII_7x8",RED,WHITE);      //ASC 7X8点阵
        Display_Asc_String(0,35,12, (uint8_t *)"ASCII_6x12",RED,WHITE);    //ASC 6X12点阵
        Display_Asc_String(0,50,16, (uint8_t *)"ASCII_8x16",RED,WHITE);    //ASC 8X16点阵
        Display_Asc_String(0,70,24, (uint8_t *)"ASCII_12x24",RED,WHITE);   //ASC 12X24点阵
        Display_Asc_String(0,100,32, (uint8_t *)"ASCII_16x32",RED,WHITE);  //ASC 16X32点阵
        Display_GB2312_String(0,145,12, "屏幕１２ｘ１２",RED,WHITE);        //12x12汉字
        Display_GB2312_String(0,160,16, "屏幕１６ｘ１６",RED,WHITE);        //15x16汉字
        Display_GB2312_String(0,179,24, "屏幕２４ｘ２４",RED,WHITE);        //24x24汉字
        Display_GB2312_String(0,204,32, "屏幕３２ｘ３",RED,WHITE);          //32x32汉字
        delay_ms(1000);
        LCD_Fill(0,0,LCD_W,LCD_H,WHITE);

        Display_TimesNewRoman_String(0,15,12, (uint8_t *)"ASCII_8x12",RED,WHITE);   //ASC 8x12点阵(TimesNewRoman类型)
        Display_TimesNewRoman_String(0,30,16, (uint8_t *)"ASCII_12x16",RED,WHITE);  //ASC 12x16点阵(TimesNewRoman类型)
        Display_TimesNewRoman_String(0,50,24, (uint8_t *)"ASCII_16x24",RED,WHITE);  //ASC 16x24点阵(TimesNewRoman类型)
        Display_TimesNewRoman_String(0,80,32, (uint8_t *)"ASCII_24x",RED,WHITE);    //ASC 24x32点阵(TimesNewRoman类型)
        Display_Arial_String(0,120,12, (uint8_t *)"ASCII_8x12",RED,WHITE);    //ASC 8x12点阵(Arial类型)
        Display_Arial_String(0,140,16, (uint8_t *)"ASCII_12x16",RED,WHITE);   //ASC 12x16点阵(Arial类型)
        Display_Arial_String(0,160,24, (uint8_t *)"ASCII_16x24",RED,WHITE);   //ASC 16x24点阵(Arial类型)
        Display_Arial_String(0,190,32, (uint8_t *)"ASCII_24x",RED,WHITE);     //ASC 24x32点阵(Arial类型)
        delay_ms(1000);

//                t+=0.11;

        LCD_Fill(0,0,LCD_W,LCD_H,WHITE);
    }

}
```

上电效果：

移植成功案例下载链接（软件SPI）：

> **【百度网盘下载链接】【软件SPI】**：**链接**：[https://pan.baidu.com/s/1Ep0fDuX2Luofdtdq3SiGZg?pwd=v9i7](https://pan.baidu.com/s/1Ep0fDuX2Luofdtdq3SiGZg?pwd=v9i7)**提取码**：v9i7

## 百度网盘下载

- https://pan.baidu.com/s/18tt2PzcnTvqTRubdRy2yoQ
- https://pan.baidu.com/s/1Ep0fDuX2Luofdtdq3SiGZg?pwd=v9i7
