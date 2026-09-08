# 继电器模块

- 分类：控制类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/control/relay-module.html
- 标题：继电器模块
- 代码块：3 个 · 图片：0 张

继电器是控制电路的电子元器件，通过感应输入电流的变化控制电路的通断，通常用于自动化控制电路中，在电路中起着自动调节、隔离、安全保护和转换等作用。直流继电器通常有5个引脚，其中有两个引脚是线圈控制引脚，其他3个引脚分别是是常开端、常闭端和公共端。在没有上电时，线圈没有通电，常闭端和公共端相连，常开端和公共端断开；上电后，线圈通电，常开端和公共端相连，常闭端和公共端断开。所以继电器就相当于是一个开关，可以使用低压控制高压。

## 一、模块来源

采购链接：

[1路5V继电器模块 光耦隔离/低电平吸合 智能小车](https://item.taobao.com/item.htm?spm=a1z10.5-c-s.w4002-24706531925.33.886b4450Jc12tZ&id=546724904969)

资料下载链接：

[http://pan.baidu.com/share/link?shareid=3950641169&uk=2302102993](http://pan.baidu.com/share/link?shareid=3950641169&uk=2302102993)

## 二、规格参数

**工作电压**：5V

**可控制的交流电压范围**：可达250V，10A

**可控制的交流电压范围**：可达30V，10A

**控制方式**：GPIO

**管脚数量**：4 Pin（2.54mm间距排针）

**说明**：采用光耦隔离保护MCU引脚；采用三极管驱动；

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够实现控制继电器的吸合与释放的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

如果继电器在低压电源导通的状态下，电磁铁有了磁力，吸合衔铁，触点闭合，高压电源形成回路处于导通状态；如果继电器在低压电源断开的状态下，电磁铁没有磁力，因为弹簧的缘故，弹簧将触点断开，高压电源没有形成回路处于断开状态；

知道了控制原理，再来看原理图。K1为继电器，其中的4脚和5脚是继电器的低压电源控制引脚，当IN1输出低电平，U1光耦隔离器的1脚2脚导通使得4脚和3脚导通，VCC通过4脚到3脚经过R2给三极管的基极得电，因为三极管的基极得电，使得三极管导通，VCC经过继电器的4脚到5脚到三极管到地。因此继电器的线圈得电，继电器的1脚触点由2脚吸合到3脚，达到了我们控制开关的目的。其中原理图中的P1端子的1脚是常闭触点，2脚是公共触点，3脚是常开触点。对应的接线图见下方右图。

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

移植步骤中的导入.c和.h文件与传感器章节的【DHT11温湿度传感器】相同，只是将.c和.h文件更改为**bsp_relay.c**与**bsp_relay.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_relay.c**中，编写如下代码。

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

#include "bsp_relay.h"
#include "stdio.h"

/******************************************************************
 * 函 数 名 称：Set_Relay_Switch
 * 函 数 说 明：设置继电器状态
 * 函 数 形 参：0继电器吸合   1继电器断开
 * 函 数 返 回：
 * 作       者：LC
 * 备       注：
******************************************************************/
void Set_Relay_Switch(unsigned char state)
{
      RELAY_OUT(state);
}
```

在文件**bsp_relay.h**中，编写如下代码。

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

#ifndef _BSP_RELAY_H_
#define _BSP_RELAY_H_

#include "board.h"

#define RELAY_OUT(x)     ( (x) ? (DL_GPIO_setPins(GPIO_PORT,GPIO_IN1_PIN)) : (DL_GPIO_clearPins(GPIO_PORT,GPIO_IN1_PIN)) )

void Set_Relay_Switch(unsigned char state);//设置继电器状态

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_relay.h"

int main(void)
{
      //开发板初始化
      board_init();

      printf("Demo Start...\r\n");
      while(1)
      {
            Set_Relay_Switch(0);//控制继电器吸合
            delay_ms(1000);

            Set_Relay_Switch(1);//控制继电器松开
            delay_ms(1000);
      }
}
```

上电效果：一上电就会听到继电器吸合的声音

模块代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/16Ls-5M1FOE3bxCDw6l9z2A?pwd=3tfd](https://pan.baidu.com/s/16Ls-5M1FOE3bxCDw6l9z2A?pwd=3tfd)**提取码**：3tfd

## 百度网盘下载

- https://pan.baidu.com/s/16Ls-5M1FOE3bxCDw6l9z2A?pwd=3tfd
