# 人体红外传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/human-body-infrared-sensor.html
- 标题：人体红外传感器
- 代码块：3 个 · 图片：0 张

人体红外感应模块使用的是热释电红外传感器，它是利用温度变化的特征来探测红外线的辐射，利用双灵敏元互补的方法抑制温度变化产生的干扰，提高了传感器的工作稳定性。产品应用广泛，例如:保险装置、防盗报警器、感应门、自动灯具、智能玩具等。

## 一、模块来源

采购链接：

[HC-SR501 人体红外感应模块 热释电 红外传感器](https://item.taobao.com/item.htm?spm=a1z10.3-c-s.w4002-19589090137.18.2b9836b4sjtBQL&id=608680529121)

资料下载链接：

[https://pan.baidu.com/s/1Bu0DL-1quXvY1Ede4c9ELw](https://pan.baidu.com/s/1Bu0DL-1quXvY1Ede4c9ELw)

资料提取码：8888

## 二、规格参数

**工作电压**：4.5~20V

**工作电流**：< 50uA

**电平输出**：高3.3V/低0V

**感应角度**：< 100度锥角

**输出方式**: GPIO

**管脚数量**：3 Pin

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够测量人体】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

全自动感应：人进入其感应范围则输出高电平， 人离开感应范围则自动延时关闭高电平，输出低电平；

两种触发方式：（可跳线选择）

- 不可重复触发方式: 即感应输出高电平后，延时时间段一结束，输出将自动从高电平变成低电平；
- 可重复触发方式：即感应输出高电平后，在延时时间段内，如果有人体在其感应范围活动，其输出将一直保持高电平，直到人离开后才延时将高电平变为低电平。
1. 感应模块通电后有一分钟左右的初始化时间，在此期间模块会间隔地输出0-3 次，一分钟后进入待机状态。
2. 避免灯光等干扰源近距离直射模块表面的透镜，以免引进干扰信号产生误动作；尽量避免流动的风，风也会对感应器造成干扰。
3. 感应模块采用双元探头，探头的窗口为长方形，双元（A 元B 元）位于较长方向的两端，当人体从左到右或从右到左走过时,红外光谱到达双元的时间、距离有差值，差值越大，感应越灵敏，当人体从正面走向探头或从上到下或从下到上方向走过时，双元检测不到红外光谱距离的变化，无差值，因此感应不灵敏或不工作；所以安装感应器时应使探头双元的方向与人体活动最多的方向尽量相平行，保证人体经过时先后被探头双元所感应。为了增加感应角度范围，本模块采用圆形透镜，也使得探头四面都感应，但左右两侧仍然比上下两个方向感应范围大。

> **HC-SR501人体感应模块使用说明**

### 2、引脚选择

### 3、移植至工程

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 添加配置【根据下方图片进行添加】
4. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

5. 然后点击编译（**可能会报错，我们不用管！**）
6. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_HumanIR.c**与**bsp_HumanIR.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_HumanIR.c**中，编写如下代码。

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
 * 2024-07-03     LCKFB-LP    first version
 */

#include "bsp_HumanIR.h"

/******************************************************************
 * 函 数 名 称：Get_HumanIR
 * 函 数 说 明：获取人体红外输出引脚的电平状态
 * 函 数 形 参：无
 * 函 数 返 回：0=感应到人体红外    1=未感应到人体红外
 * 作       者：LC
 * 备       注：无
******************************************************************/
char Get_HumanIR(void)
{
    return GET;
}
```

在文件**bsp_HumanIR.h**中，编写如下代码。

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
 * 2024-07-03     LCKFB-LP    first version
 */
#ifndef _BSP_HUMANIR_H_
#define _BSP_HUMANIR_H_

#include "board.h"

#define GET   ( ( ( DL_GPIO_readPins(GPIO_PORT,GPIO_OUT_PIN) & GPIO_OUT_PIN ) > 0 ) ? 1 : 0 )

char Get_HumanIR(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_HumanIR.h"

int main(void)
{
      //开发板初始化
      board_init();

      printf("Start.....\r\n");

      while(1)
      {
            printf("%d\r\n", Get_HumanIR() );

            delay_ms(500);
      }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/18BBQfwFCtE9a7yhmuB2YQw?pwd=9p1o](https://pan.baidu.com/s/18BBQfwFCtE9a7yhmuB2YQw?pwd=9p1o)**提取码**：9p1o

## 百度网盘下载

- https://pan.baidu.com/s/1Bu0DL-1quXvY1Ede4c9ELw
- https://pan.baidu.com/s/18BBQfwFCtE9a7yhmuB2YQw?pwd=9p1o
