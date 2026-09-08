# 0.96寸SPI单色屏

- 分类：显示类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/screen/0-96-single-spi-screen.html
- 标题：0.96寸SPI单色屏
- 代码块：4 个 · 图片：1 张

## 一、模块来源

**采购链接**： [黄保凯中景园0.96寸OLED显示屏12864液晶屏12864显示屏ssd1306](https://item.taobao.com/item.htm?id=37849023766&_u=n1q56pn343e4)

**资料下载链接**： [https://pan.baidu.com/s/1U9r32qeS2jOANB0SNwtwnw](https://pan.baidu.com/s/1U9r32qeS2jOANB0SNwtwnw) **资料提取码**：8888

## 二、规格参数

**工作电压**：3.3V

**工作电流**：15MA

**模块尺寸**：27.3 x 27.8 MM

**像素大小**：128(H) x 64(V)RGB

**驱动芯片**：SSD1306

**通信协议**：SPI

**管脚数量**：7 Pin（2.54mm间距排针）

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

将厂家资料路径下的【OLED】文件夹，复制到自己的工程中的**BSP文件夹**中。（工程可以参考**入门手册工程模板**）

我们打开工程文件，将我们刚刚复制到文件夹中的文件，导入C文件和路径。

![img](images/0-96-single-spi-screen/img1.gif)

将**oled.h**文件下的 **sys.h** 改为 **board.h**。

> **TIP**：(在左边将 **oled.h** 的工程目录展开，就发现有 **oled.h** )

将 **oled.c** 中的 **delay.h** 注释掉

首先分别在**oled.h**文件中定义三个宏，u32、u16与u8。

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

该屏幕需要设置7个接口，具体接口说明见 **各引脚说明**。

> 模块为SPI通信协议的从机，D0为SPI信号线（SCK），D1为SPI输出线（MOSI），CS为SPI片选线（NSS）。

#### 软件SPI移植

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】【添加**5**个】
5. 开始添加配置，根据引脚选择设定
6. 剩下的引脚也是一样的配置
7. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

8. 然后点击编译（**可能会报错，我们不用管！**）
9. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

选择好引脚后，进入工程开始修改初始化代码。

将 **oled.c** 源代码中的 **void OLED_Init(void)** 修改为如下代码。

```c
//OLED的初始化
void OLED_Init(void)
{
    OLED_RES_Clr();
    delay_ms(200);
    OLED_RES_Set();

    OLED_WR_Byte(0xAE,OLED_CMD);//--turn off oled panel
    OLED_WR_Byte(0x00,OLED_CMD);//---set low column address
    OLED_WR_Byte(0x10,OLED_CMD);//---set high column address
    OLED_WR_Byte(0x40,OLED_CMD);//--set start line address  Set Mapping RAM Display Start Line (0x00~0x3F)
    OLED_WR_Byte(0x81,OLED_CMD);//--set contrast control register
    OLED_WR_Byte(0xCF,OLED_CMD);// Set SEG Output Current Brightness
    OLED_WR_Byte(0xA1,OLED_CMD);//--Set SEG/Column Mapping     0xa0左右反置 0xa1正常
    OLED_WR_Byte(0xC8,OLED_CMD);//Set COM/Row Scan Direction   0xc0上下反置 0xc8正常
    OLED_WR_Byte(0xA6,OLED_CMD);//--set normal display
    OLED_WR_Byte(0xA8,OLED_CMD);//--set multiplex ratio(1 to 64)
    OLED_WR_Byte(0x3f,OLED_CMD);//--1/64 duty
    OLED_WR_Byte(0xD3,OLED_CMD);//-set display offset        Shift Mapping RAM Counter (0x00~0x3F)
    OLED_WR_Byte(0x00,OLED_CMD);//-not offset
    OLED_WR_Byte(0xd5,OLED_CMD);//--set display clock divide ratio/oscillator frequency
    OLED_WR_Byte(0x80,OLED_CMD);//--set divide ratio, Set Clock as 100 Frames/Sec
    OLED_WR_Byte(0xD9,OLED_CMD);//--set pre-charge period
    OLED_WR_Byte(0xF1,OLED_CMD);//Set Pre-Charge as 15 Clocks & Discharge as 1 Clock
    OLED_WR_Byte(0xDA,OLED_CMD);//--set com pins hardware configuration
    OLED_WR_Byte(0x12,OLED_CMD);
    OLED_WR_Byte(0xDB,OLED_CMD);//--set vcomh
    OLED_WR_Byte(0x40,OLED_CMD);//Set VCOM Deselect Level
    OLED_WR_Byte(0x20,OLED_CMD);//-Set Page Addressing Mode (0x00/0x01/0x02)
    OLED_WR_Byte(0x02,OLED_CMD);//
    OLED_WR_Byte(0x8D,OLED_CMD);//--set Charge Pump enable/disable
    OLED_WR_Byte(0x14,OLED_CMD);//--set(0x10) disable
    OLED_WR_Byte(0xA4,OLED_CMD);// Disable Entire Display On (0xa4/0xa5)
    OLED_WR_Byte(0xA6,OLED_CMD);// Disable Inverse Display On (0xa6/a7)
    OLED_Clear();
    OLED_WR_Byte(0xAF,OLED_CMD);
}
```

因为引脚已经在 **SYSCONFIG** 中自动配置了，不需要进行初始化了。

将lcd_init.h中的 OLED端口定义 宏，修改为下方代码框中的代码。

```c
//-----------------OLED端口定义----------------

#define OLED_SCL_Clr() DL_GPIO_clearPins(GPIO_PORT,GPIO_SCL_PIN)//SCL=SCLK
#define OLED_SCL_Set() DL_GPIO_setPins(GPIO_PORT,GPIO_SCL_PIN)

#define OLED_SDA_Clr() DL_GPIO_clearPins(GPIO_PORT,GPIO_SDA_PIN)//SDA=MOSI
#define OLED_SDA_Set() DL_GPIO_setPins(GPIO_PORT,GPIO_SDA_PIN)

#define OLED_RES_Clr()  DL_GPIO_clearPins(GPIO_PORT,GPIO_RES_PIN)//RES
#define OLED_RES_Set()  DL_GPIO_setPins(GPIO_PORT,GPIO_RES_PIN)

#define OLED_DC_Clr()   DL_GPIO_clearPins(GPIO_PORT,GPIO_DC_PIN)//DC
#define OLED_DC_Set()   DL_GPIO_setPins(GPIO_PORT,GPIO_DC_PIN)

#define OLED_CS_Clr()   DL_GPIO_clearPins(GPIO_PORT,GPIO_CS_PIN)//CS
#define OLED_CS_Set()   DL_GPIO_setPins(GPIO_PORT,GPIO_CS_PIN)
```

到这里软件SPI就移植完成了，可移步到第四节进行移植验证。

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "oled.h"

int main(void)
{
    //开发板初始化
    board_init();
    OLED_Init();    //初始化OLED
    OLED_Clear();

    while(1)
    {
        OLED_ShowString(0,0,(uint8_t *)"ABC",8,1);//6*8 “ABC”
        OLED_ShowString(0,8,(uint8_t *)"ABC",12,1);//6*12 “ABC”
        OLED_ShowString(0,20,(uint8_t *)"ABC",16,1);//8*16 “ABC”
        OLED_ShowString(0,36,(uint8_t *)"ABC",24,1);//12*24 “ABC”
        OLED_Refresh();
        delay_ms(500);
    }
}
```

上电效果：

> **【百度网盘下载链接】【软件SPI】**：**链接**：[https://pan.baidu.com/s/1P15HjWaKHdPo2NtgO3oMBQ?pwd=ugwp](https://pan.baidu.com/s/1P15HjWaKHdPo2NtgO3oMBQ?pwd=ugwp)**提取码**：ugwp

## 百度网盘下载

- https://pan.baidu.com/s/1U9r32qeS2jOANB0SNwtwnw
- https://pan.baidu.com/s/1P15HjWaKHdPo2NtgO3oMBQ?pwd=ugwp
