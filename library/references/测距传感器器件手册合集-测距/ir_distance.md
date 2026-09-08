# 红外测距传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/Infrared-distance-sensor.html
- 标题：红外测距传感器
- 代码块：3 个 · 图片：0 张

GP2Y0A02YKOF是夏普的一款距离测量传感器模块。它由PSD(position sensitive detector)和IRED(infrared emitting diode)以及信号处理电路三部分组成。由于采用了三角测量方法,被测物体的材质、环境温度以及测量时间都不会影响传感器的测量精度。传感器输出电压值对应探测的距离。通过测量电压值就可以得出所探测物体的距离,所以这款传感器可以用于距离测量、避障等场合。

## 一、模块来源

采购链接：

[GP2Y0A02YK0F 红外激光测距传感器 避障测距20-150cm](https://item.taobao.com/item.htm?spm=a230r.1.14.16.7def2810sScrt7&id=580318855469&ns=1&abbucket=12#detail)

资料下载链接：

[https://pan.baidu.com/s/11dDQHyYJfi0nNyC28vkpoA](https://pan.baidu.com/s/11dDQHyYJfi0nNyC28vkpoA)

资料提取码：qvpm

## 二、规格参数

**工作电压**：3.3-5V

**工作电流**：33MA

**模块尺寸**：37 x 21.6mm

**输出方式**: 模拟量输出

**读取方式**：ADC

**管脚数量**：3 Pin

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够判断前方障碍物的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

红外测距传感器的输出是非线性的。每个型号的输出曲线都不同。所以，在实际使用前，最好能对所使用的传感器进行一下校正。对每个型号的传感器创建一张曲线图，以便在实际使用中获得真实有效的测量数据。下图是测距距离为20-150CM型号的输出曲线图。

从上图中，可以看到，当被探测物体的距离小于大约 15cm 的时候，输出电压急剧下降，也就是说从电压读数来看，物体的距离应该是越来越远了。但是实际上并不是这样的，想象一下，你的机器人本来正在慢慢的 靠近障碍物，突然发现障碍物消失了，一般来说，你的控制程序会让你的机器人以全速移动，结果是，"砰"的一声。当然了，解决这个方法也不是没有，这里有个小技巧。只需要改变一下传感器的安装位置，使它到机器人的外围的距离大于最小探测距离就可以了。

红外测距传感器的输出数据线是通过电压的变化来确定距离，我们可以使用ADC功能获取传感器的电压变化，将其转换为实际距离即可。电压距离转换公式见官方代码库链接：[https://github.com/zoubworldArduino/ZSharpIR找到我们20-150CM型号的传感器，在下方有换算公式。](https://github.com/zoubworldArduino/ZSharpIR%E6%89%BE%E5%88%B0%E6%88%91%E4%BB%AC20-150CM%E5%9E%8B%E5%8F%B7%E7%9A%84%E4%BC%A0%E6%84%9F%E5%99%A8%EF%BC%8C%E5%9C%A8%E4%B8%8B%E6%96%B9%E6%9C%89%E6%8D%A2%E7%AE%97%E5%85%AC%E5%BC%8F%E3%80%82)

### 2、引脚选择

**这里选择使用PA27的附加ADC功能**。

### 3、移植至工程

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】
5. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

6. 然后点击编译（**可能会报错，我们不用管！**）
7. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_IRdistance.c**与**bsp_IRdistance.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_IRdistance.c**中，编写如下代码。

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
 * 2024-06-28     LCKFB-LP    first version
 */
#include "bsp_IRdistance.h"
#include "stdio.h"
#include "math.h"

volatile bool gCheckADC;        //ADC采集成功标志位

/**********************************************************
 * 函 数 名 称：IRdistance_Init
 * 函 数 功 能：初始化ADC
 * 传 入 参 数：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：LP
**********************************************************/
void IRdistance_Init(void)
{
    SYSCFG_DL_init();

    //开启ADC中断
    NVIC_EnableIRQ(ADC12_0_INST_INT_IRQN);

    printf("adc Demo start\r\n");
}
/**********************************************************
 * 函 数 名 称：ADC_GET
 * 函 数 功 能：读取一次ADC数据
 * 传 入 参 数：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：LP
**********************************************************/
uint32_t ADC_GET(void)
{
    unsigned int gAdcResult = 0;

    int timeout = 100;

    //软件触发ADC开始转换
    DL_ADC12_startConversion(ADC12_0_INST);
    //如果当前状态为正在转换中则等待转换结束
    while (false == gCheckADC)
    {
        delay_us(1);
        timeout--;

        if(timeout <= 0)
        {
            printf("DL_ADC12_startConversion ERROR!! LINE:%d\r\n",__LINE__);
            return 1;
        }
    }
    //获取数据
    gAdcResult = DL_ADC12_getMemResult(ADC12_0_INST, ADC12_0_ADCMEM_ADC_CH0);

    //清除标志位
    gCheckADC = false;

    return gAdcResult;
}

/**********************************************************
 * 函 数 名 称：Get_Adc_Value
 * 函 数 功 能：获得某个通道的值
 * 传 入 参 数：Count：采集次数
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：LP
**********************************************************/
uint32_t Get_Adc_Value(uint8_t Count)
{
    unsigned int gAdcResult = 0;
    uint8_t i = 0;
    for(i = 0; i < Count; i++)
    {
        //获取数据
        gAdcResult += ADC_GET();
    }

    return (gAdcResult / Count);
}

/******************************************************************
 * 函 数 名 称：Get_illume_Percentage_value
 * 函 数 说 明：计算红外测距的测量距离
 * 函 数 形 参：无
 * 函 数 返 回：返回测量距离
 * 作       者：LC
 * 备       注：无
******************************************************************/
double Get_IRdistance_Distance(void)
{
    double adc_new = 0;
    double Distance = 0;

    adc_new = (((double)Get_Adc_Value(10.f) / 4095.f) * 3.3f);

//    根据官方代码库链接：https://github.com/zoubworldArduino/ZSharpIR
//    得到距离换算公式：
//    【GP2Y0A02YK0F：Using MS Excel, we can calculate function (For distance > 15cm) :
//    Distance = 60.374 X POW(Volt , -1.16)】
    Distance = 60.374 * pow(adc_new,-1.16);

    return Distance;
}

//ADC中断服务函数
void ADC12_0_INST_IRQHandler(void)
{
    //查询并清除ADC中断
    switch (DL_ADC12_getPendingInterrupt(ADC12_0_INST))
    {
        //检查是否完成数据采集
        case DL_ADC12_IIDX_MEM0_RESULT_LOADED:
                  gCheckADC = true;//将标志位置1
                  break;
        default:
                  break;
    }
}
```

在文件**bsp_IRdistance.h**中，编写如下代码。

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
 * 2024-06-28     LCKFB-LP    first version
 */
#ifndef _BSP_IRDISTANCE_H_
#define _BSP_IRDISTANCE_H_

#include "board.h"

void IRdistance_Init(void);
uint32_t Get_Adc_Value(uint8_t Count);
double Get_IRdistance_Distance(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_IRdistance.h"

int main(void)
{
    //开发板初始化
    board_init();

    IRdistance_Init();

    while (1)
    {
        printf("Distance = %d CM\r\n", (int)Get_IRdistance_Distance() );

        delay_ms(1000);
    }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1M47qNl6mt6vmMwT214tvKg?pwd=emd3](https://pan.baidu.com/s/1M47qNl6mt6vmMwT214tvKg?pwd=emd3)**提取码**：emd3

## 百度网盘下载

- https://pan.baidu.com/s/11dDQHyYJfi0nNyC28vkpoA
- https://pan.baidu.com/s/1M47qNl6mt6vmMwT214tvKg?pwd=emd3
