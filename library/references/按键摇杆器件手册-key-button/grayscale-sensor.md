# 灰度传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/grayscale-sensor.html
- 标题：灰度传感器
- 代码块：3 个 · 图片：0 张

## 一、模块来源

采购链接：

[电子积木模拟灰度传感器 寻线传感器 循迹模块光感传感器 比赛用](https://detail.tmall.com/item.htm?abbucket=0&id=676917570259&ns=1&spm=a21n57.1.0.0.6a6b523c8GDuHU)

## 二、规格参数

**工作电压**：3.3V-5V

**工作电流**：< 20mA

**输出格式**：模拟信号输出

**控制接口**：ADC

**管脚数量**：3 Pin（2.54mm间距排针）

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够判断当前环境状况的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

灰度传感器包括一个白色高亮发光二极管和一个光敏电阻，由于发光二极管照射到灰度不同的纸张上返回的光是不同的，光敏电阻接收到返回的光，根据光的强度不同，光敏电阻的阻值也不同，从而实现灰度值的测试。

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_grayscale.c**与**bsp_grayscale.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_grayscale.c**中，编写如下代码。

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

#include "bsp_grayscale.h"
#include "stdio.h"

volatile bool gCheckADC;        //ADC采集成功标志位s

/******************************************************************
 * 函 数 名 称：ADC_GRAYSCALE_Init
 * 函 数 说 明：初始化ADC功能
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void ADC_GRAYSCALE_Init(void)
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
 * 函 数 名 称：Get_Adc_GRAYSCALE_Value
 * 函 数 说 明：对保存的数据进行平均值计算后输出
 * 函 数 形 参：
 * 函 数 返 回：对应扫描的ADC值
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int Get_Adc_GRAYSCALE_Value(void)
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
 * 函 数 名 称：Get_Grayscale_Percentage_value
 * 函 数 说 明：读取灰度传感器的值，并且返回百分比
 * 函 数 形 参：无
 * 函 数 返 回：返回百分比
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int Get_Grayscale_Percentage_Value(void)
{
      int adc_max = 4095;
      int adc_new = 0;
      int Percentage_value = 0;

      adc_new = Get_Adc_GRAYSCALE_Value();
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

在文件**bsp_grayscale.h**中，编写如下代码。

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

#ifndef _BSP_GRAYSCALE_H_
#define _BSP_GRAYSCALE_H_

#include "board.h"

 //采样次数
#define SAMPLES         30

void ADC_GRAYSCALE_Init(void);
unsigned int Get_Adc_GRAYSCALE_Value(void);
unsigned int Get_Grayscale_Percentage_Value(void);
#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_grayscale.h"

int main(void)
{
      //开发板初始化
      board_init();

      ADC_GRAYSCALE_Init();
      printf("ADC Demo Start\r\n");
      while(1)
      {
            printf("灰度百分比 = %d%%\r\n\n", Get_Grayscale_Percentage_Value() );
            delay_ms(1000);
      }
}
```

上电效果：【对着黑色数值较小】

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1t8shpT9AYb9t1cH1w0w6iw?pwd=437q](https://pan.baidu.com/s/1t8shpT9AYb9t1cH1w0w6iw?pwd=437q)**提取码**：437q

## 百度网盘下载

- https://pan.baidu.com/s/1t8shpT9AYb9t1cH1w0w6iw?pwd=437q
