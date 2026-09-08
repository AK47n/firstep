# SG90舵机

- 分类：控制类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/control/sg90-steering-engine.html
- 标题：SG90舵机
- 代码块：3 个 · 图片：0 张

## 一、模块来源

采购链接：

[SG90MG90s 9g舵机MG995/996R直升机固定翼遥控飞机马达航模机器人](https://detail.tmall.com/item.htm?abbucket=0&id=615779197448&ns=1&spm=a21n57.1.0.0.6f6f523cXTHwFh)

资料下载：

[https://pan.baidu.com/s/1QsTIKnoQsOTCkeYLLTTjTA?pwd=8889](https://pan.baidu.com/s/1QsTIKnoQsOTCkeYLLTTjTA?pwd=8889)

提取码：8889

## 二、规格参数

**驱动电压**：3V~7.2V

**工作扭矩**：1.6KG/CM

**控制方式**：PWM

**转动角度**：180度

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【能够控制舵机旋转的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

在购买时，需要分清楚你的舵机可以转180度，还是360度。360度的舵机是无法控制角度的，只可以控制旋转速度。

SG90的舵机转速不是很快，一般为0.22/60 度或0.18/60 度，所以假如你更改角度控制脉冲的宽度太快时，舵机可能反应不过来。如果需要更快速的反应，就需要更高的转速了。

### 2、引脚选择

我们选择定时器7通道0，PA28引脚。

### 3、移植至工程

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 开始添加配置，根据引脚选择设定
5. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

6. 然后点击编译（**可能会报错，我们不用管！**）
7. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

移植步骤中的导入.c和.h文件与传感器章节的【DHT11温湿度传感器】相同，只是将.c和.h文件更改为**bsp_sg90.c**与**bsp_sg90.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_sg90.c**中，编写如下代码。

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
#include "bsp_sg90.h"

unsigned int Servo_Angle = 0;//舵机角度

/******************************************************************
       配置占空比 范围 0 ~ (per-1)
   t = 0.5ms——————-舵机会转动 0 °
   t = 1.0ms——————-舵机会转动 45°
   t = 1.5ms——————-舵机会转动 90°
   t = 2.0ms——————-舵机会转动 135°
   t = 2.5ms——————-舵机会转动180°
******************************************************************/

/******************************************************************
 * 函 数 名 称：Set_Servo_Angle
 * 函 数 说 明：设置角度
 * 函 数 形 参：angle=要设置的角度，范围0-180
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void Set_Servo_Angle(unsigned int angle)
{
      uint32_t period = 400;

      if(angle > 180)
      {
            angle = 180; // 限制角度在0到180度之间
      }

      Servo_Angle = angle;

      // 计算PWM占空比
      // 0.5ms对应的计数 = 10
      // 2.5ms对应的计数 = 50
      float min_count = 10.0f;
      float max_count = 50.0f;
      float range = max_count - min_count;
      float ServoAngle = min_count + (((float)angle / 180.0f) * range);

      DL_TimerG_setCaptureCompareValue(PWM_INST, (unsigned int)(ServoAngle + 0.5f), GPIO_PWM_C0_IDX);
}

/******************************************************************
 * 函 数 名 称：读取当前角度
 * 函 数 说 明：Get_Servo_Angle
 * 函 数 形 参：无
 * 函 数 返 回：当前角度
 * 作       者：LC
 * 备       注：使用前必须确保之前使用过
                void Set_Servo_Angle(unsigned int angle)
                函数设置过角度
******************************************************************/
unsigned int Get_Servo_Angle(void)
{
      return Servo_Angle;
}
```

在文件**bsp_sg90.h**中，编写如下代码。

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

#ifndef _BSP_SG90_H
#define _BSP_SG90_H

#include "board.h"

void Set_Servo_Angle(unsigned int angle);
unsigned int Get_Servo_Angle(void);

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_sg90.h"

int main(void)
{
      //开发板初始化
      board_init();

      int i = 0;

      Set_Servo_Angle(180);
      delay_ms(1000);
      Set_Servo_Angle(0);
      delay_ms(1000);

      while(1)
      {

            Set_Servo_Angle(i++);
            if( i >= 180 )
            {
                i = 0;
            }

            delay_ms(10);
      }
}
```

上电效果：舵机从0度转到180度后，再从0度重新开始转。

模块代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1_9xotTk7SCUfgUJ89d-r0g?pwd=7pfl](https://pan.baidu.com/s/1_9xotTk7SCUfgUJ89d-r0g?pwd=7pfl)**提取码**：7pfl

## 百度网盘下载

- https://pan.baidu.com/s/1QsTIKnoQsOTCkeYLLTTjTA?pwd=8889
- https://pan.baidu.com/s/1_9xotTk7SCUfgUJ89d-r0g?pwd=7pfl
