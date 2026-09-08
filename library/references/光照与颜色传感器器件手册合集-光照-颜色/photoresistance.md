# 光敏电阻光照传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/photoresistance-sensor.html
- 标题：光敏电阻光照传感器
- 代码块：3 个 · 图片：0 张

光敏电阻是用硫化隔或硒化隔等半导体材料制成的特殊电阻器，其工作原理是基于内光电效应。随着光照强度的升高，电阻值迅速降低，由于光照产生的载流子都参与导电，在外加电场的作用下作漂移运动，电子奔向电源的正极，空穴奔向电源的负极，从而使光敏电阻器的阻值迅速下降。其在无光照时，几乎呈高阻状态，暗时电阻很大。光敏电阻模块一般用来检测周围环境的光线的亮度，触发单片机或继电器模块等。

## 一、模块来源

采购链接：

[光敏电阻传感器模块 光感应 智能车配件](https://item.taobao.com/item.htm?spm=2013.1.0.0.68c07a63p9f0me&id=522579320463)

资料下载链接：

[https://pan.baidu.com/s/1VMFN1fVo5jxB80IYTsY67A](https://pan.baidu.com/s/1VMFN1fVo5jxB80IYTsY67A)

资料提取码：y8jw

## 二、规格参数

**工作电压**：3.3-5V

**工作电流**：1MA

**模块尺寸**：31.1475 x 14.097mm

**输出方式**: DO接口为数字量输出 AO接口为模拟量输出

**读取方式**：ADC

**管脚数量**：4 Pin（2.54mm间距排针）

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【判断当前光照强度的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

这个模块采用的光敏电阻的型号是5516，对应下图，可以知道在光亮时的阻值在8到20KΩ左右，在光暗时的阻值在1MΩ左右。

其对应的原理图，其中U2.1为LM393，R3为光敏电阻。AO输出为R2和R3分压后直接输出电压，所以为模拟量；DO为经过LM393进行电压比较后，输出高低电平，所以为数字量。具体原理是，393的3号引脚电压与2号引脚进行电压比较。当3号引脚电压比2号引脚电压高时，1号引脚输出高电平；当3号引脚电压比2号引脚电压低时，1号引脚输出低电平；可以通过调整R4控制2号引脚的电压。

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_illume.c**与**bsp_illume.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_illume.c**中，编写如下代码。

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
#include "bsp_illume.h"
#include "stdio.h"

volatile bool gCheckADC;        //ADC采集成功标志位

/**********************************************************
 * 函 数 名 称：Illume_Init
 * 函 数 功 能：初始化ADC
 * 传 入 参 数：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：LP
**********************************************************/
void Illume_Init(void)
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
 * 函 数 说 明：读取光敏电阻值，并且返回百分比
 * 函 数 形 参：无
 * 函 数 返 回：返回百分比
 * 作       者：LC
 * 备       注：最亮100  最暗0
******************************************************************/
unsigned int Get_illume_Percentage_value(void)
{
    //ADC精度都是12位
    //2的12次方 = 4096
    //因为单片机是从0开始算，所以要4096-1=4095
    int adc_max = 4095;
    int adc_new = 0;
    int Percentage_value = 0;

    adc_new = Get_Adc_Value(10);
    //百分比 = （ 当前值 / 最大值 ）* 100
    Percentage_value = ( 1 - ( (float)adc_new / adc_max ) ) * 100;

    return Percentage_value;
}

/******************************************************************
 * 函 数 名 称：Get_DO_In
 * 函 数 说 明：读取DO引脚的电平状态
 * 函 数 形 参：无
 * 函 数 返 回：1=检测过亮   0=检测过暗
 * 作       者：LC
 * 备       注：无
******************************************************************/
uint8_t Get_DO_In(void)
{
    if( GET_DO_IN == 1 )
    {
        return 1;
    }
    return 0;
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

在文件**bsp_illume.h**中，编写如下代码。

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
#ifndef __BSP_ILLUME_H__
#define __BSP_ILLUME_H__

#include "board.h"

#define GET_DO_IN        DL_GPIO_readPins(GPIO_PORT, GPIO_DO_PIN)

void Illume_Init(void);
uint32_t Get_Adc_Value(uint8_t Count);
unsigned int Get_illume_Percentage_value(void);
uint8_t Get_DO_In(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_illume.h"

int main(void)
{
    //开发板初始化
    board_init();

    Illume_Init();

    while (1)
    {
        printf("ADC-%d\r\n", Get_Adc_Value(10) );
        printf("illume-%d%%\r\n", Get_illume_Percentage_value() );
        printf("\r\n");
        delay_ms(1000);
    }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1eFJO6n4xykISuRPoEYmnlA?pwd=ma8z](https://pan.baidu.com/s/1eFJO6n4xykISuRPoEYmnlA?pwd=ma8z)**提取码**：ma8z

## 百度网盘下载

- https://pan.baidu.com/s/1VMFN1fVo5jxB80IYTsY67A
- https://pan.baidu.com/s/1eFJO6n4xykISuRPoEYmnlA?pwd=ma8z
