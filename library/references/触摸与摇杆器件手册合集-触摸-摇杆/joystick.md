# 双轴按键摇杆模块

- 分类：控制类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/control/two-axis-keystroke-rocker-module.html
- 标题：双轴按键摇杆模块
- 代码块：3 个 · 图片：0 张

双轴按键游戏摇杆模块,采用 PS2游戏手柄上金属按键摇杆电位器。模块特设二路模拟输出和一路数字输出接口、输出值分别对应（X、Y）双轴偏移量、其类型为模拟量、按键表示用户是否在Z轴上按下、其类型为数字开关量、用其可以轻松控制物体,在二维空间运动、因此可以通控制器编程、传感器扩展板插接、完成具有创意性遥控互动作品。

## 一、模块来源

采购链接：

[双轴按键摇杆传感器 游戏摇杆控制杆模块 电子积木](https://detail.tmall.com/item.htm?abbucket=0&id=609784733201&ns=1&spm=a21n57.1.0.0.7b97523cuNeQqX)

## 二、规格参数

**驱动电压**：3.3V~5V

**控制方式**：ADC+GPIO

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够控制电机旋转速度的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

输出信号:模块特设二路模拟输出(VRX，VRY)和一路数字输出接口(SW)，二路模拟输出值分别对应(X,Y)双轴偏移量，其类型为模拟量；按键表示用户是否在Z轴上按下，其类型为数字开关量。

十字摇杆为一个双向的10K电阻器,随着摇杆方向不同，抽头的阻值随着变化。本模块如果使用5V供电，原始状态下X，Y读出电压为2.5V左右，当随箭头方向按下，读出电压值减少，限小为0V。

### 2、引脚选择

VRX与VRY使用ADC功能。

想要使用ADC，需要确定使用的引脚是否有ADC外设功能。

### 3、移植至工程

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】
5. 开始添加GPIO配置，根据引脚选择设定
6. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

7. 然后点击编译（**可能会报错，我们不用管！**）
8. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

移植步骤中的导入.c和.h文件与传感器章节的【DHT11温湿度传感器】相同，只是将.c和.h文件更改为**bsp_joystick.c**与**bsp_joystick.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_joystick.c**中，编写如下代码。

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
 * 2024-07-08     LCKFB-LP    first version
 */

#include "bsp_joystick.h"
#include "stdio.h"

volatile bool gCheckADC_0;        // ADC_CH0 采集成功标志位
volatile bool gCheckADC_1;        // ADC_CH1 采集成功标志位

/******************************************************************
 * 函 数 名 称：ADC_Joystick_Init
 * 函 数 说 明：初始化ADC功能
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void ADC_Joystick_Init(void)
{
        //开启ADC中断+
        NVIC_EnableIRQ(ADC12_0_INST_INT_IRQN);
}

/**********************************************************
 * 函 数 名 称：ADC_GET
 * 函 数 功 能：读取一次ADC数据
 * 传 入 参 数：chx : 0为通道0，1为通道1
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：LP
**********************************************************/
uint32_t ADC_GET(uint8_t CHx)
{
      uint32_t gAdcResult = 0;

      int timeout = 5000;

      //软件触发ADC开始转换
      DL_ADC12_startConversion(ADC12_0_INST);

      if(CHx == 0)
      {
            //如果当前状态为正在转换中则等待转换结束
            while (false == gCheckADC_0)
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

            //清除通道0标志位
            gCheckADC_0 = false;
      }
      else
      {
            //如果当前状态为正在转换中则等待转换结束
            while (false == gCheckADC_1)
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
            gAdcResult = DL_ADC12_getMemResult(ADC12_0_INST, ADC12_0_ADCMEM_ADC_CH1);

            //清除通道1标志位
            gCheckADC_1 = false;
      }

      return gAdcResult;
}
/******************************************************************
 * 函 数 名 称：Get_Adc_Joystick_Value
 * 函 数 说 明：对保存的数据进行平均值计算后输出
 * 函 数 形 参：CHx 那个通道值
 * 函 数 返 回：对应扫描的ADC值
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int Get_Adc_Joystick_Value(char CHx)
{
      uint32_t Data = 0;

      for(int i = 0; i < SAMPLES; i++)
      {
            Data += ADC_GET(CHx);

            delay_ms(5);
      }

      Data = Data / SAMPLES;

      return Data;
}

/******************************************************************
 * 函 数 名 称：Get_MQ2_Percentage_value
 * 函 数 说 明：读取摇杆值，并且返回百分比
 * 函 数 形 参：0=读取摇杆左右值，1=读取摇杆上下值
 * 函 数 返 回：返回百分比
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int Get_Joystick_Percentage_value(char dir)
{
      int adc_new = 0;
      int Percentage_value = 0;

      if( dir == 0)
      {
            adc_new = Get_Adc_Joystick_Value(0); // 通道0：X的值
      }
      else
      {
            adc_new = Get_Adc_Joystick_Value(1); // 通道1：Y的值
      }

      Percentage_value = ((float)adc_new/4095.0f) * 100.f;
      return Percentage_value;
}

/******************************************************************
 * 函 数 名 称：Get_SW_state
 * 函 数 说 明：读取摇杆是否有按下
 * 函 数 形 参：无
 * 函 数 返 回：0摇杆被按下   1摇杆没有按下
 * 作       者：LC
 * 备       注：无
******************************************************************/
char Get_SW_state(void)
{
      //如果被按下
      if( GET_SW == 0 )
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

                  gCheckADC_0 = true;//将通道0标志位置1
                  break;

          case DL_ADC12_IIDX_MEM1_RESULT_LOADED:

                  gCheckADC_1 = true;//将通道1标志位置1
                  break;

          default:
                  break;
      }
}
```

在文件**bsp_joystick.h**中，编写如下代码。

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
 * 2024-07-08     LCKFB-LP    first version
 */
#ifndef _BSP_JOYSTICK_H_
#define _BSP_JOYSTICK_H_

#include "board.h"

#define GET_SW  ( ( ( DL_GPIO_readPins(GPIO_PORT,GPIO_SW_PIN) & GPIO_SW_PIN ) > 0 ) ? 1 : 0 )

 //采样次数
#define SAMPLES   30

void ADC_Joystick_Init(void);
unsigned int Get_Joystick_Percentage_value(char dir);
char Get_SW_state(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_joystick.h"

int main(void)
{
      //开发板初始化
      board_init();

      ADC_Joystick_Init();

      printf("Demo Start.....\r\n");

      while(1)
      {
            if( Get_SW_state() == 0 )
            {
                  printf("按钮按下!!\r\n");
            }

            printf("X = [%d]\r\n",Get_Joystick_Percentage_value(0));
            printf("Y = [%d]\r\n",Get_Joystick_Percentage_value(1));
            printf("\n");

            delay_ms(50);
      }
}
```

上电效果：移动摇杆并且按下，输出摇杆移动的数据。

模块代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/15xVEt4G8DBrRQpZpbXyfJw?pwd=8z0w](https://pan.baidu.com/s/15xVEt4G8DBrRQpZpbXyfJw?pwd=8z0w)**提取码**：8z0w

## 百度网盘下载

- https://pan.baidu.com/s/15xVEt4G8DBrRQpZpbXyfJw?pwd=8z0w
