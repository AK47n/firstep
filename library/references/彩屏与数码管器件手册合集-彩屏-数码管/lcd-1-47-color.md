# 1.47寸彩屏

- 分类：显示类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/screen/1-47-color-screen.html
- 标题：1.47寸彩屏
- 代码块：4 个 · 图片：1 张

## 一、模块来源

**采购链接**： [1.47寸lcd显示屏高清ips172x320 st7789驱动液晶屏高清液晶显示屏](https://item.taobao.com/item.htm?id=652498199222&_u=n1q56pn3a895)

**资料下载链接**： [https://pan.baidu.com/s/15OWpndYzyW8kFPqmfKNfxQ](https://pan.baidu.com/s/15OWpndYzyW8kFPqmfKNfxQ)

**资料提取码**：8888

## 二、规格参数

**工作电压**：3.3V

**工作电流**：90MA

**模块尺寸**：30(H) x 37(V) MM

**像素大小**：172(H) x 320(V)RGB

**驱动芯片**：ST7789V3

**通信协议**：SPI

**管脚数量**：8 Pin（2.54mm间距排针）

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

![img](images/1-47-color-screen/img1.gif)

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

该屏幕需要设置8个接口，具体接口说明见 **各引脚说明**。

- 模块为SPI通信协议的从机，SCL为SPI信号线（SCK），SDA为SPI输出线（MOSI），CS为SPI片选线（NSS）。 如果MCU的GPIO引脚不足，可以将屏幕的两个引脚接口不接入MCU的GPIO。将RES接入MCU的复位引脚，当MCU复位时，屏幕也跟着复位；
- 可以将BLK接入3.3V或悬空，代价是无法控制背光亮度。

#### 软件SPI移植

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】【添加**6**个】
5. 开始添加配置，根据引脚选择设定
6. 剩下的引脚也是一样的配置
7. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

8. 然后点击编译（**可能会报错，我们不用管！**）
9. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

选择好引脚后，进入工程开始编写屏幕引脚初始化代码。

我们更改lcd_init.h中的LCD端口定义

```c
//-----------------LCD端口定义----------------

#define LCD_SCLK_Clr() DL_GPIO_clearPins(GPIO_PORT,GPIO_SCL_PIN)//SCL=SCLK
#define LCD_SCLK_Set() DL_GPIO_setPins(GPIO_PORT,GPIO_SCL_PIN)

#define LCD_MOSI_Clr() DL_GPIO_clearPins(GPIO_PORT,GPIO_SDA_PIN)//SDA=MOSI
#define LCD_MOSI_Set() DL_GPIO_setPins(GPIO_PORT,GPIO_SDA_PIN)

#define LCD_RES_Clr()  DL_GPIO_clearPins(GPIO_PORT,GPIO_RES_PIN)//RES
#define LCD_RES_Set()  DL_GPIO_setPins(GPIO_PORT,GPIO_RES_PIN)

#define LCD_DC_Clr()   DL_GPIO_clearPins(GPIO_PORT,GPIO_DC_PIN)//DC
#define LCD_DC_Set()   DL_GPIO_setPins(GPIO_PORT,GPIO_DC_PIN)

#define LCD_CS_Clr()   DL_GPIO_clearPins(GPIO_PORT,GPIO_CS_PIN)//CS
#define LCD_CS_Set()   DL_GPIO_setPins(GPIO_PORT,GPIO_CS_PIN)

#define LCD_BLK_Clr()  DL_GPIO_clearPins(GPIO_PORT,GPIO_BLK_PIN)//BLK
#define LCD_BLK_Set()  DL_GPIO_setPins(GPIO_PORT,GPIO_BLK_PIN)
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
#include "lcd.h"
#include "lcd_init.h"

int main(void)
{
    //开发板初始化
    board_init();

    LCD_Init();//屏幕初始化
    LCD_Fill(0,0,LCD_W,LCD_H,BLACK);//清全屏为黑色

    float t = 0;

    while(1)
    {
        LCD_ShowString(0,16*2,(uint8_t *)"LCD_W:",WHITE,BLACK,16,0);
        LCD_ShowIntNum(48,16*2,LCD_W,3,WHITE,BLACK,16);
        LCD_ShowString(80,16*2,(uint8_t *)"LCD_H:",WHITE,BLACK,16,0);
        LCD_ShowIntNum(128,16*2,LCD_H,3,WHITE,BLACK,16);

        LCD_ShowString(0,16*3,(uint8_t *)"Nun:",WHITE,BLACK,16,0);
        LCD_ShowFloatNum1(8*4,16*3,t,4,WHITE,BLACK,16);
        t+=0.11;

        delay_ms(1000);
    }
}
```

上电效果：

> **【百度网盘下载链接】【软件SPI】**：**链接**：[https://pan.baidu.com/s/1Me5n-OHeS5my3eN3VD8koA?pwd=448j](https://pan.baidu.com/s/1Me5n-OHeS5my3eN3VD8koA?pwd=448j)**提取码**：448j

## 百度网盘下载

- https://pan.baidu.com/s/15OWpndYzyW8kFPqmfKNfxQ
- https://pan.baidu.com/s/1Me5n-OHeS5my3eN3VD8koA?pwd=448j
