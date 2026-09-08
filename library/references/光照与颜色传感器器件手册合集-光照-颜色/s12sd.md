# S12SD紫外线传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/s12sd-uv-sensor.html
- 标题：S12SD紫外线传感器
- 代码块：3 个 · 图片：0 张

此紫外线检测模块采用氮化家基材料的肖特基光电二极管，具有高的响应度和低的暗电流,板载LM358放大器对光电二极管输出的微弱信号进行放大，所有元器件采用1%精度元器件制造。应用于紫外线测试仪，紫外线手表，户外运动设备，手机移动电话等。

## 一、模块来源

采购链接：

[S12SD 高灵敏UV紫外线传感器模块 太阳光照强度感应检测电路板](https://item.taobao.com/item.htm?spm=a21n57.1.0.0.d0e2523cw99pzo&id=656169130215&ns=1&abbucket=0#detail)

资料下载链接：

[https://pan.baidu.com/s/1YuwoCsbiJPaYH-8TaHEwVg](https://pan.baidu.com/s/1YuwoCsbiJPaYH-8TaHEwVg)

提取码：8888

## 二、规格参数

**工作电压**：2.7-5V

**工作电流**：1mA

**测量角度**：130度

**温飘**：0.08%/℃

**检测波长范围**：240nm~370nm

**输出方式**: ADC

**管脚数量**：3 Pin

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够测量紫外线强度】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

电路图中，SIG引脚是经过放大模拟电压后进行模拟信号输出，采集到模拟量后将其转换为电压，根据下图电压与紫外线强度对照表，则可得知紫外线强度。

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_ultraviolet.c**与**bsp_ultraviolet.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_ultraviolet.c**中，编写如下代码。

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
#include "bsp_ultraviolet.h"
#include "stdio.h"

volatile bool gCheckADC;        //ADC采集成功标志位

/******************************************************************
 * 函 数 名 称：ULTRAVIOLET_Init
 * 函 数 说 明：UV紫外线模块引脚初始化
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：
******************************************************************/
void ULTRAVIOLET_Init(void)
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
 * 函 数 名 称：Get_ADC_Value
 * 函 数 说 明：对ADC值进行平均值计算后输出
 * 函 数 形 参：num采集次数
 * 函 数 返 回：对应扫描的ADC值
 * 作       者：LC
 * 备       注：误差80mV左右
******************************************************************/
unsigned int Get_ADC_Value( void )
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
 * 函 数 名 称：Get_Ultraviolet_Intensity
 * 函 数 说 明：判断当前紫外线强度等级
 * 函 数 形 参：value=ADC读取的值
 * 函 数 返 回：0~11 紫外线强度等级由低到高，11最高
 * 作       者：LC
 * 备       注：无
******************************************************************/
char Get_Ultraviolet_Intensity(uint16_t value)
{
      char ret = 0;
      if( value < 227 )//紫外线强度0级
      {
            ret = 0;
      }
      if( value >= 227 && value < 318 )//紫外线强度1级
      {
            ret = 1;
      }
      if( value >= 318 && value < 408 )//紫外线强度2级
      {
            ret = 2;
      }
      if( value >= 408 && value < 503 )//紫外线强度3级
      {
            ret = 3;
      }
      if( value >= 503 && value < 606 )//紫外线强度4级
      {
            ret = 4;
      }
      if( value >= 606 && value < 696 )//紫外线强度5级
      {
            ret = 5;
      }
      if( value >= 696 && value < 795 )//紫外线强度6级
      {
            ret = 6;
      }

      if( value >= 795 && value < 881 )//紫外线强度7级
      {
            ret = 7;
      }
      if( value >= 881 && value < 976 )//紫外线强度8级
      {
            ret = 8;
      }
      if( value >= 976 && value < 1079 )//紫外线强度9级
      {
            ret = 9;
      }
      if( value >= 1079 && value < 1170 )//紫外线强度10级
      {
            ret = 10;
      }
      if( value >= 1170  )//紫外线强度11级
      {
            ret = 11;
      }

      return ret;
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

在文件**bsp_ultraviolet.h**中，编写如下代码。

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
#ifndef _BSP_ULTRAVIOLET_H_
#define _BSP_ULTRAVIOLET_H_

#include "board.h"

//采样次数
#define SAMPLES     30

void ULTRAVIOLET_Init(void);
unsigned int Get_ADC_Value(void);
char Get_Ultraviolet_Intensity(uint16_t value);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_ultraviolet.h"

int main(void)
{
      uint16_t value = 0;

      //开发板初始化
      board_init();

      ULTRAVIOLET_Init();

      printf("IRtracking demo start\r\n");

      while(1)
      {
            value = Get_ADC_Value();
            //串口显示紫外线强度
            printf("Grade = %d\r\n", Get_Ultraviolet_Intensity( value ) );
            delay_ms(1000);
      }
}
```

上电效果：测量室内紫外线强度为0级。

模块代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1RP-wVQ_UDaeR_eYP5W-dqg?pwd=pri6](https://pan.baidu.com/s/1RP-wVQ_UDaeR_eYP5W-dqg?pwd=pri6)**提取码**：pri6

## 百度网盘下载

- https://pan.baidu.com/s/1YuwoCsbiJPaYH-8TaHEwVg
- https://pan.baidu.com/s/1RP-wVQ_UDaeR_eYP5W-dqg?pwd=pri6
