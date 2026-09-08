# 雨滴传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/rain-sensor.html
- 标题：雨滴传感器
- 代码块：3 个 · 图片：0 张

雨滴传感器主要是用来检测是否下雨及雨量的大小。主要用于汽车智能灯光（AFS）系统、汽车自动雨刷系统、智能车窗系统。

该雨滴传感器基本上是一块板，上面以线形形式涂覆镍。雨滴传感器常见的工作原理是通过检测水滴的导电性来判断是否下雨。它是利用两个电极之间的电导性变化来测量水滴的存在。这两个电极之间会有一个空气间隙，正常状态下是断路状态。当水滴接触到电极上时，水滴的导电性会导致电流通过水滴形成电流回路，从而改变电极之间的电阻值。也就改变了其两端的压降。

## 一、模块来源

采购链接：

[雨滴感应模块 雨水传感器下雨感知模块天气模块 水位显示模块水滴](https://detail.tmall.com/item.htm?abbucket=0&id=41266204564&ns=1&spm=a21n57.1.0.0.4c52523cd1r9Zc)

资料下载链接：

[https://pan.baidu.com/s/10bjbsmcOh2N7YGDS3PquPw](https://pan.baidu.com/s/10bjbsmcOh2N7YGDS3PquPw)

资料提取码：psfm

## 二、规格参数

**工作电压**：3.3V-5V

**探测距离**：1米

**输出方式**: DO接口为数字量输出 AO接口为模拟量输出

**读取方式**：ADC与数字量（0和1）

**管脚数量**：4 Pin（2.54mm间距排针）

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【判断当前雨水采集板上是否有水的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

该模块基于LM393运算放大器。它包括电子模块和“收集”雨滴的印刷电路板。当雨滴积聚在电路板上时，它们会形成并联电阻路径，该路径可通过运算放大器进行测量。

控制板上有两个指示灯，电源指示灯PWR-LED和输出信号指示灯DO-LED。电源指示灯在通电后常亮，没有雨的时候出信号指示灯不亮；雨滴上去，候出信号指示灯亮。雨滴板和控制板是分开的，方便将线引出，大面积的雨滴板，更有利于检测到雨水。

控制板上有两个输出，数字输出DO，模拟输出AO。接上5V电源电源灯亮，感应板上没有水滴时，DO输出为高电平，滴上一滴水，DO输出为低电平，刷掉上面的水滴，又恢复到输出高电平状态，灵敏度可以通过蓝色的可变电阻调节。

AO模拟输出，连接到单片机的的模拟输入口，通过比对模拟值转化为的数字值大小，可以检测滴在上面的雨量大小，雨水越大，电阻值越小，模拟值转化为的数字值越大。 不同的值对应是降雨量的多少毫米，则需要实体测量，雨滴板的放置方式不同结果都不同，这里不作研究。

其对应的原理图，AO输出为雨滴传感器直接输出的电压，所以为模拟量；DO为经过LM393进行电压比较后，输出高低电平，所以为数字量。具体原理见光敏电阻光照传感器章节的资料。

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_raindrop.c**与**bsp_raindrop.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_raindrop.c**中，编写如下代码。

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
#include "bsp_raindrop.h"
#include "stdio.h"

volatile bool gCheckADC;        //ADC采集成功标志位

/******************************************************************
 * 函 数 名 称：raindrop_config
 * 函 数 说 明：初始化雨滴传感器
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void raindrop_config(void)
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
/**********************************************************
 * 函 数 名 称：get_adc_value
 * 函 数 功 能：读取ADC值
 * 传 入 参 数：
 * 函 数 返 回：测量到的值
 * 作       者：LC
 * 备       注：无
**********************************************************/
unsigned int get_adc_value(void)
{
    uint32_t data = ADC_GET();

    delay_ms(20);

    return data;
}

/******************************************************************
 * 函 数 名 称：get_raindrop_percentage_value
 * 函 数 说 明：读取雨滴AO值，并且返回百分比
 * 函 数 形 参：无
 * 函 数 返 回：返回百分比
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int get_raindrop_percentage_value(void)
{
    int adc_max = 4095;
    uint32_t adc_new = 0;
    int Percentage_value = 0;
    int i = 0;
        int count = 3;

        for( i = 0; i < count; i++)
        {
                adc_new += get_adc_value();
                delay_1ms(100);
        }

        adc_new = adc_new /  count;
        delay_1ms(100);

    Percentage_value = ( 1.0f - ( (float)adc_new / (float)adc_max ) ) * 100;
    return Percentage_value;
}

/******************************************************************
 * 函 数 名 称：get_raindrop_do_value
 * 函 数 说 明：读取雨滴DO值，返回0或者1
 * 函 数 形 参：无
 * 函 数 返 回：
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned char get_raindrop_do_value(void)
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

在文件**bsp_raindrop.h**中，编写如下代码。

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
#ifndef _BSP_RAINDROP_H__
#define _BSP_RAINDROP_H__

#include "board.h"

#define GET_DO   ( ( DL_GPIO_readPins( GPIO_PORT, GPIO_DO_PIN ) & GPIO_DO_PIN ) ? 1 : 0 )

void raindrop_config(void);
unsigned int get_raindrop_percentage_value(void);
#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_raindrop.h"

int main(void)
{
    //开发板初始化
    board_init();

    //ADC接口初始化
    raindrop_config();

    while(1)
    {
        printf("雨水百分比 = %d%%\r\n", get_raindrop_percentage_value() );
        delay_ms(500);
    }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1NovN1-zz2BUPAmmYkJV5aA?pwd=6aqg](https://pan.baidu.com/s/1NovN1-zz2BUPAmmYkJV5aA?pwd=6aqg)**提取码**：6aqg

## 百度网盘下载

- https://pan.baidu.com/s/10bjbsmcOh2N7YGDS3PquPw
- https://pan.baidu.com/s/1NovN1-zz2BUPAmmYkJV5aA?pwd=6aqg
