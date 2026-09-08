# 微波多普勒无线雷达传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/microwave-doppler-radar-sensor.html
- 标题：微波多普勒无线雷达传感器
- 代码块：3 个 · 图片：0 张

微波运动传感器是利用多普勒雷达原理设计的微波移动物体探测器。不同于一般的红外探测器，微波传感器通过通过检测物体反射的微波来探测物体的运动状况，检测对象将并不会局限于人体，还有很多其他的事物。微波传感器不受环境温度的影响，探测距离远，灵敏度高，被广泛应用于工业、交通及民用装置中，如车辆测速、自动门、感应灯、倒车雷达等。

由于微波传感器检测对象存在普遍性，在实际的生活应用中，会搭配另一个传感器来做针对性的检测。如微波传感器+红外热释电传感器，能够有效的判断是否有人经过，不会被阳光，被衣物颜色所干扰，也不会对其他物体产生反应。

## 一、模块来源

采购链接：

[微波多普勒无线雷达探测器探头传感器模块10.525GHz HB100带底板](https://item.taobao.com/item.htm?spm=a1z10.3-c-s.w4002-19589090137.12.706136b40EmwBc&id=643727489100)

资料下载链接：

[https://pan.baidu.com/s/110NZE7hM3ifS1ho53fxmoA](https://pan.baidu.com/s/110NZE7hM3ifS1ho53fxmoA)

提取码：2cz6

## 二、规格参数

**工作电压**：5V±0.25V

**工作电流**：30~50mA

**探测距离**：2-16m 连续可调

**尺寸**： R=30.6mm

**输出方式**: GPIO

**管脚数量**：3 Pin

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够判断测量一定距离内是否物体运动】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

由于微波传感器检测对象存在普遍性，即只要有物体动作，都能够检测到，因此只需要检测OUT引脚的高低电平变化即可。

### 2、引脚选择

### 3、移植至工程

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】【添加配置】
5. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

6. 然后点击编译（**可能会报错，我们不用管！**）
7. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_mh100x.c**与**bsp_mh100x.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_mh100x.c**中，编写如下代码。

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
#include "bsp_mh100x.h"
#include "stdio.h"

/******************************************************************
 * 函 数 名 称：OUTPIN_Scanf
 * 函 数 说 明：返回OUT引脚电平状态
 * 函 数 形 参：无
 * 函 数 返 回：1=未检测到物体移动  0=检测到物体移动
 * 作       者：LC
 * 备       注：无
******************************************************************/
char OUTPIN_Scanf(void)
{
    return OUT_IN;
}
```

在文件**bsp_mh100x.h**中，编写如下代码。

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

#ifndef _BSP_MH100X_H_
#define _BSP_MH100X_H_

#include "board.h"

#define OUT_IN   ( ( DL_GPIO_readPins( GPIO_PORT, GPIO_OUT_PIN ) & GPIO_OUT_PIN ) ? 1 : 0 )

char OUTPIN_Scanf(void);//微波雷达的输入状态

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_mh100x.h"

int main(void)
{
      uint8_t flag = 0;
      uint16_t time = 0;

      //开发板初始化
      board_init();

      printf("Demo Start\r\n");
      while(1)
      {
            //检测到有物体移动
            if( OUTPIN_Scanf() == 0 )
            {
                flag = 1;
            }

            if( flag == 1 )
            {
                  if( time == 0 ) //打开门
                  {
                      printf("open\r\n");
                  }

                  time++;
                  if( time >= 2000 )//超过两秒则关门
                  {
                      time = 0;
                      flag = 0;
                      printf("close\r\n");
                  }
                  delay_ms(1);//时间基准
            }

      }
}
```

上电效果：对准自己，当检测到移动时，发送open，超过两秒之后发送close，反复循环。

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/13hf_c29sFmFo9DrUQkKPVw?pwd=86is](https://pan.baidu.com/s/13hf_c29sFmFo9DrUQkKPVw?pwd=86is)**提取码**：86is

## 百度网盘下载

- https://pan.baidu.com/s/110NZE7hM3ifS1ho53fxmoA
- https://pan.baidu.com/s/13hf_c29sFmFo9DrUQkKPVw?pwd=86is
