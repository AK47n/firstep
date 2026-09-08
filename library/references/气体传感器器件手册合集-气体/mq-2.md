# MQ-2烟雾检测传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/mq-2-sensor.html
- 标题：MQ-2烟雾检测传感器
- 代码块：3 个 · 图片：0 张

MQ-2型烟雾传感器属于二氧化锡半导体气敏材料，属于表面离子式N型半导体。处于200~3000摄氏度时，二氧化锡表面吸附空气中的氧，形成氧的负离子吸附，使半导体中的电子密度减少，从而使其电阻值增加。当与烟雾接触时，如果晶粒间界处的势垒收到烟雾的调至面变化，就会引起表面导电率的变化。利用这一点就可以获得这种烟雾存在的信息。烟雾浓度越大导电率越大，输出电阻越低，则输出的模拟信号就越大。

## 一、模块来源

采购链接：

[MQ-2烟雾传感器模块 MQ2 气体传感器](https://item.taobao.com/item.htm?spm=a1z10.3-c-s.w4002-24706531953.12.4cd36a4bho6MgR&id=522572009794)

资料下载链接：

[https://pan.baidu.com/s/1ETxqg03p5fEjKS7AZ2kV6w](https://pan.baidu.com/s/1ETxqg03p5fEjKS7AZ2kV6w)

资料提取码：dfr1

## 二、规格参数

**工作电压**：5V

**工作电流**：150MA

**输出方式**: DO接口为数字量输出 AO接口为模拟量输出

**读取方式**：ADC

**管脚数量**：4 Pin（2.54mm间距排针）

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【判断当前环境状况的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

MQ-2烟雾传感器对液化气、天然气、城市煤气灵敏度较高。需要注意的是：在使用之前必须加热一段时间，否则其输出的电阻和电压不准确。其检测可燃气体与烟雾的范围是100~10000ppm(ppm为体积浓度。 1ppm=1立方厘米/1立方米)。带有双路信号输出（模拟量输出AO和数字量输出DO）。当气体浓度未超过设定阈值时，数字接口DO口输出低电平，模拟接口AO电压基本为0v左右；当气体影响超过设定阈值时，模块数字接口DO输出高电平，模拟接口AO输出的电压会随着气体的影响慢慢增大。阈值由模块上的可调电阻控制。

其对应的原理图，AO输出为MQ-2传感器直接输出的电压，所以为模拟量；DO为经过LM393进行电压比较后，输出高低电平，所以为数字量。

因此DO引脚可以配置为GPIO的输入模式，AO引脚需要配置为ADC模拟输入模式。

### 2、引脚选择

当前只有AO引脚需要使用到ADC接口，所以DO引脚可以使用开发板上其他的GPIO。**这里选择使用PA27的附加ADC功能**。

### 3、移植至工程

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】
5. 添加GPIO配置【根据下方图片进行添加】
6. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

7. 然后点击编译（**可能会报错，我们不用管！**）
8. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_mq2.c**与**bsp_mq2.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_mq2.c**中，编写如下代码。

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
#include "bsp_mq2.h"
#include "stdio.h"

volatile bool gCheckADC;        //ADC采集成功标志位

/******************************************************************
 * 函 数 名 称：Adc_Init
 * 函 数 说 明：初始化ADC功能
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void Adc_Init(void)
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

    int timeout = 20;

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
/******************************************************************
 * 函 数 名 称：Get_Adc_Value
 * 函 数 说 明：
 * 函 数 形 参：
 * 函 数 返 回：对应扫描的ADC值
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int Get_Adc_Value(void)
{
    unsigned char i = 0;
    unsigned int AdcValue = 0;

    /* 因为采集 SAMPLES 次，故循环 SAMPLES 次 */
    for(i=0; i< SAMPLES; i++)
    {
        /* 累加 */
        AdcValue += ADC_GET();
    }
    /* 求平均值 */
    AdcValue = AdcValue / SAMPLES;

    return AdcValue;
}

/******************************************************************
 * 函 数 名 称：Get_MQ2_Percentage_value
 * 函 数 说 明：读取MQ2值，并且返回百分比
 * 函 数 形 参：无
 * 函 数 返 回：返回百分比
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int Get_MQ2_Percentage_value(void)
{
    int adc_max = 4095;
    int adc_new = 0;
    int Percentage_value = 0;

    adc_new = Get_Adc_Value();

    Percentage_value = ((float)adc_new/(float)adc_max) * 100.f;
    return Percentage_value;
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

在文件**bsp_mq2.h**中，编写如下代码。

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
#ifndef _BSP_MQ2_H_
#define _BSP_MQ2_H_

#include "board.h"

 //采样次数
#define SAMPLES    30

#define GET_DO     ( ( DL_GPIO_readPins( GPIO_PORT, GPIO_DO_PIN ) & GPIO_DO_PIN ) ? 1 : 0 )

/************************

//之前的单路采集
void ADC_Init(void);
unsigned int Get_ADC_Value(void);

**************************/
void Adc_Init(void);
unsigned int Get_Adc_Value(void);
unsigned int Get_MQ2_Percentage_value(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_mq2.h"

int main(void)
{
    //开发板初始化
    board_init();

    Adc_Init();
    printf("ADC demo start\r\n");

    while (1)
    {
        printf("ADC_Value = %d\r\n", Get_Adc_Value() );
        printf("MQ2 = %d %%\r\n", Get_MQ2_Percentage_value() );
        printf("DO = [%d] \r\n", GET_DO);
        delay_ms(1000);
    }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1j9OvgMqMXEhNmfQDwBK8cg?pwd=2ie0](https://pan.baidu.com/s/1j9OvgMqMXEhNmfQDwBK8cg?pwd=2ie0)**提取码**：2ie0

## 百度网盘下载

- https://pan.baidu.com/s/1ETxqg03p5fEjKS7AZ2kV6w
- https://pan.baidu.com/s/1j9OvgMqMXEhNmfQDwBK8cg?pwd=2ie0
