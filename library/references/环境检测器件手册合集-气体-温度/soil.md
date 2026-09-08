# 土壤湿度传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/soil-moisture-sensor.html
- 标题：土壤湿度传感器
- 代码块：3 个 · 图片：0 张

土壤湿度模块是一个简易的水分传感器可用于检测土壤的水分,表面镀镍而不易生锈,延长使用寿命感应面积宽提高导电性能。模块双输出模式,数字量输出简单模拟量输出更精确。灵敏度可调（图中蓝电位器调节阀值)。比较器采用LM393芯片工作稳定,信号干净。设有固定螺栓孔方便安装。使用这个传感器制作一款自动浇花装置，让您的花园里的植物不用人去管理。

## 一、模块来源

采购链接：

[土壤湿度传感器 土壤湿度计检测模块](https://detail.tmall.com/item.htm?abbucket=15&id=691640308824&ns=1&spm=a21n57.1.0.0.76ea523cQF7VPZ)

资料下载链接：

[https://pan.baidu.com/s/1HJ3WhTG6dpNf-BdgW3zLlg?pwd=8889](https://pan.baidu.com/s/1HJ3WhTG6dpNf-BdgW3zLlg?pwd=8889)

资料提取码：8889

## 二、规格参数

**工作电压**：3.3V-5V

**工作电流**：150MA

**输出方式**: DO接口为数字量输出 AO接口为模拟量输出

**读取方式**：ADC

**管脚数量**：4 Pin（2.54mm间距排针）

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够判断当前环境状况的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

1. 传感器适用于土壤的湿度检测;
2. 模块中蓝色的电位器是用于土壤湿度的阀值调节,顺时针调节，控制的湿度会越大，逆时针越小；
3. 数字量输出DO可以与单片机直接相连,通过单片机来检测高低电平，由此来检测土壤湿度；
4. 小板模拟量输出A0可以和AD模块相连,通过AD转换,可以获得土壤湿度更精确的数值；

原理就是将买模块自带的叉子插入土壤，水分充足的时候导电，土壤中的水将叉子的两端连通。 可以做一个小实验，拿一个金属制品，贴在叉子上将叉子两端短接，就会发现模块上面的DO_LED亮了。

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_soilHumidity.c**与**bsp_soilHumidity.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_soilHumidity.c**中，编写如下代码。

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
 * 2024-07-04     LCKFB-LP    first version
 */

#include "bsp_soilHumidity.h"
#include <stdio.h>

volatile bool gCheckADC;        //ADC采集成功标志位

/******************************************************************
 * 函 数 名 称：ADC_SOILHUMIDITY_Init
 * 函 数 说 明：初始化ADC功能
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void ADC_SOILHUMIDITY_Init(void)
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
 * 函 数 名 称：Get_Adc_Dma_Value
 * 函 数 说 明：对DMA保存的数据进行平均值计算后输出
 * 函 数 形 参：CHx 第几个扫描的数据
 * 函 数 返 回：对应扫描的ADC值
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int Get_Adc_Value(void)
{
        uint32_t Data = 0;

        for(int i = 0; i < SAMPLES; i++)
        {
                Data += ADC_GET();

                delay_ms(5);
        }

        Data = Data / SAMPLES;

        return Data;
}

/******************************************************************
 * 函 数 名 称：Get_SH_Percentage_value
 * 函 数 说 明：读取值，并且返回百分比
 * 函 数 形 参：无
 * 函 数 返 回：返回百分比
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int Get_SH_Percentage_value(void)
{
      int adc_max = 4095;
      int adc_new = 0;
      int Percentage_value = 0;

      adc_new = Get_Adc_Value();

      Percentage_value = ((float)adc_new/(float)adc_max) * 100.f;
      return Percentage_value;
}

/******************************************************************
 * 函 数 名 称：Get_SH_DO_value
 * 函 数 说 明：获取引脚的电平状态
 * 函 数 形 参：无
 * 函 数 返 回：0=未检测到高于灵敏度的可燃气体值 1=检测到高于灵敏度的可燃气体值
 * 作       者：LC
 * 备       注：调整模块上的滑动电阻即可调整灵敏度
******************************************************************/
char Get_SH_DO_value(void)
{
      if( GET_DO == 0 )
      {
            return 0;
      }
      else
      {
            return 1;
      }
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

在文件**bsp_soilHumidity.h**中，编写如下代码。

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
 * 2024-07-04     LCKFB-LP    first version
 */

#ifndef _BSP_SOILHUMIDITY_H_
#define _BSP_SOILHUMIDITY_H_

#include "board.h"

#define GET_DO  ( ( DL_GPIO_readPins( GPIO_PORT, GPIO_DO_PIN ) & GPIO_DO_PIN ) ? 1 : 0 )

 //采样次数
#define SAMPLES         30

void ADC_SOILHUMIDITY_Init(void);
unsigned int Get_Adc_Value(void);
unsigned int Get_SH_Percentage_value(void);
char Get_SH_DO_value(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c

#include "board.h"
#include <stdio.h>
#include "bsp_soilHumidity.h"

int main(void)
{
      //开发板初始化
      board_init();

      ADC_SOILHUMIDITY_Init();
      printf("ADC demo start\r\n");
      while(1)
      {
            printf("Soil Humidity = %d%%\r\n", Get_SH_Percentage_value() );
            delay_ms(1000);
      }
}
```

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1Zo1GitadhD6nMRYqFcZS4Q?pwd=5mtq](https://pan.baidu.com/s/1Zo1GitadhD6nMRYqFcZS4Q?pwd=5mtq)**提取码**：5mtq

## 百度网盘下载

- https://pan.baidu.com/s/1HJ3WhTG6dpNf-BdgW3zLlg?pwd=8889
- https://pan.baidu.com/s/1Zo1GitadhD6nMRYqFcZS4Q?pwd=5mtq
