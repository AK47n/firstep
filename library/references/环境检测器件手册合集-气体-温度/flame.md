# 火焰传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/flame-sensor.html
- 标题：火焰传感器
- 代码块：3 个 · 图片：0 张

红外火焰传感器可以用来探测火源或其他一些波长在700纳米~1000纳米范围内的热源，在机器人比赛中，远红外火焰探头起到非常重要的作用，它可以用作机器人的眼睛来寻找火源或足球。利用它可以制作灭火机器人等。

红外火焰传感器能够探测700纳米~1000纳米范围内的红外光，探测角度为60，其中红外光波长在880纳米附近时，其灵敏度达到最大。红外火焰探头将外界红外光的强弱变化转化为电流的变化，通过A/D转换器反映为0 ~4095范围内的数值的变化。外界红外光越强，数值越小；红外光越弱，数值越大。

## 一、模块来源

采购链接：

[(4线制)火光/火焰传感器模块火源探测 红外接收传感器 智能车配件](https://item.taobao.com/item.htm?spm=a21n57.1.0.0.4c52523cd1r9Zc&id=35124127482&ns=1&abbucket=0#detail)

资料下载链接：

[https://pan.baidu.com/s/14rzP9Gx7AjbmRSqD_A5Pyw](https://pan.baidu.com/s/14rzP9Gx7AjbmRSqD_A5Pyw)

资料提取码：risv

## 二、规格参数

**工作电压**：3.3V-5V

**探测距离**：1米

**输出方式**: DO接口为数字量输出 AO接口为模拟量输出

**读取方式**：ADC与数字量（0和1）

**管脚数量**：4 Pin（2.54mm间距排针）

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【判断当前检测范围是否有火光的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

火焰传感器模块的工作原理很简单。其背后的理论是热的物体会发出红外辐射。对于火焰或火灾，这种辐射会很高。我们将使用红外光电二极管检测这种红外辐射。光电二极管的电导率将根据其检测到的红外辐射而变化。我们使用 LM393 来比较这种辐射，当达到阈值时，数字输出会发生变化。

我们还可以使用模拟输出来测量红外辐射强度。模拟输出直接取自光电二极管的端子。板载 D0 LED 将在检测到时显示存在火灾。灵敏度可以通过调整板上的可变电阻来改变。这可用于消除误触发。

其对应的原理图，AO输出为火焰传感器直接输出的电压，所以为模拟量；DO为经过LM393进行电压比较后，输出高低电平，所以为数字量。具体原理见光敏电阻光照传感器章节的资料。

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_flame.c**与**bsp_flame.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_flame.c**中，编写如下代码。

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

#include "bsp_flame.h"
#include "stdio.h"

volatile bool gCheckADC;        //ADC采集成功标志位

/******************************************************************
 * 函 数 名 称：ADC_FLAME_Init
 * 函 数 说 明：初始化ADC
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void ADC_FLAME_Init(void)
{
        //开启ADC中断
        NVIC_EnableIRQ(ADC12_0_INST_INT_IRQN);
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
 * 函 数 名 称：Get_Adc_FLAME_Value
 * 函 数 说 明：
 * 函 数 形 参：
 * 函 数 返 回：对应扫描的ADC值
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int Get_Adc_FLAME_Value(void)
{
        uint32_t data = ADC_GET();
        delay_1ms(20);

        return data;
}

/******************************************************************
 * 函 数 名 称：Get_FLAME_Percentage_value
 * 函 数 说 明：读取火焰AO值，并且返回百分比
 * 函 数 形 参：无
 * 函 数 返 回：返回百分比
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int Get_FLAME_Percentage_value(void)
{
      uint32_t i = 0;
      uint32_t adc_max = 4095;
      uint32_t adc_new = 0;
      uint32_t Percentage_value = 0;

      /* 因为采集 SAMPLES 次，故循环 SAMPLES 次 */
      for(i = 0; i < SAMPLES; i++)
      {
              // 数值累加
              adc_new += Get_Adc_FLAME_Value();
              delay_ms(5);
      }

      adc_new = adc_new / SAMPLES;

      Percentage_value = ( 1.0f - ( (float)adc_new / (float)adc_max ) ) * 100.0f;

      return Percentage_value;
}
/******************************************************************
 * 函 数 名 称：Get_FLAME_Do_value
 * 函 数 说 明：读取火焰DO值，返回0或者1
 * 函 数 形 参：无
 * 函 数 返 回：
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned char Get_FLAME_Do_value(void)
{
    return GET_DO;
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

在文件**bsp_flame.h**中，编写如下代码。

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
#ifndef _BSP_FLAME_H_
#define _BSP_FLAME_H_

#include "board.h"

 //采样次数
#define SAMPLES    30

#define GET_DO   ( ( DL_GPIO_readPins( GPIO_PORT, GPIO_DO_PIN ) & GPIO_DO_PIN ) ? 1 : 0 )

void ADC_FLAME_Init(void);
unsigned int Get_Adc_FLAME_Value(void);
unsigned int Get_FLAME_Percentage_value(void);
unsigned char Get_FLAME_Do_value(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_flame.h"

int main(void)
{
    //开发板初始化
    board_init();

    ADC_FLAME_Init();
    while(1)
    {
        printf("Flame = %d%%\r\n",Get_FLAME_Percentage_value());
        delay_ms(500);
    }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1A8RenYd7L_N2X9lh5EYmRg?pwd=1x05](https://pan.baidu.com/s/1A8RenYd7L_N2X9lh5EYmRg?pwd=1x05)**提取码**：1x05

## 百度网盘下载

- https://pan.baidu.com/s/14rzP9Gx7AjbmRSqD_A5Pyw
- https://pan.baidu.com/s/1A8RenYd7L_N2X9lh5EYmRg?pwd=1x05
