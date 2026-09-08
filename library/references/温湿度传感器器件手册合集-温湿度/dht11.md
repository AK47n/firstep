# DHT11温湿度传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/dht11-temp-humi-sensor.html
- 标题：DHT11温湿度传感器
- 代码块：8 个 · 图片：0 张

DHT11数字温湿度传感器是一款含有已校准数字信号输出的温湿度复合传感器。其成本低、长期稳定、可以测量相对湿度和温度测量，并可以只使用一根数据线进行温湿度采集。

## 一、模块来源

采购链接：

[DHT11温度模块 湿度模块 温湿度模块 DHT11传感器](https://item.taobao.com/item.htm?spm=a230r.1.14.23.735720126ougj3&id=522553143872&ns=1&abbucket=12#detail)

资料下载链接：

[https://pan.baidu.com/s/1HQEL699-Yl5Jh3Hp87_FlQ](https://pan.baidu.com/s/1HQEL699-Yl5Jh3Hp87_FlQ)

资料提取码：2sgq

## 二、规格参数

**工作电压**：3-5.5V

**工作电流**：1MA

**测量分辨率**：8 bit

**湿度量程**: 20 - 90 %RH

**湿度精度**：±5 %RH

**温度量程**: 0 - 50 ℃

**温度精度**：±2 ℃

**通信协议**：单总线

**管脚数量**：3 Pin（2.54mm间距排针）

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【实现读取温湿度的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

DHT11使用的是单总线通信，即发送数据与接收数据都在一根数据线上，通过规定的时序进行控制。

从左向右看，时序一开始，主机信号就保持着高电平，所以引脚初始化完毕时，及时给引脚输出高电平。因为模块的数据线要求空闲时，要保持高电平状态。（其实模块上已经接了上拉电阻，使数据线一直保持高电平）

根据时序图可以知道，主机（开发板）发送一次开始信号，待主机开始信号结束后，DHT11 发送响应信号，送出 温湿度数据，并触发一次数据采集给下一次数据读取作准备。因此完成一次数据读取需要进行起始信号、响应信号、数据接收、结束信号。

读取数据步骤：

1. 起始信号：主机（开发板）接入数据线的I/O输出低电平，且低电平保持时间不能小于 18ms。

```c
DATA_GPIO_OUT(0);  //数据线输出低电平
delay_1ms(19);     //起始信号保持时间19ms
DATA_GPIO_OUT(1);  //主机释放总线
delay_uus( 20 );   //拉高等待
```

2. 响应信号：等待模块的响应信号到来。将数据线改为输入模式，如果接入到低电平，说明接收到模块的响应。

```c
DHT11_GPIO_Mode_IN();//数据线转为输入模式
//如果前面没有错误，则模块会发出低电平的应答信号，
//所以直接等待DHT11拉高，83us
timeout = 5000;
while( (! DATA_GPIO_IN ) && ( timeout >0 ) )
{
    timeout--;         //等待高电平的到来
}
//模块当前处于拉高准备输出数据，
//所以直接等待DHT11拉低，87us
timeout = 5000;//设置超时时间
while( DATA_GPIO_IN && ( timeout >0 ) )
{
    timeout-- ;         //等待低电平的到来
}
```

3. 数据传输：主机接收模块发送的40位数据，其中，位数据 ‘0’ 表示54us的低电平，27us的高电平；位数据 ‘1’ 表示54us的低电平，74us的高电平。两个格式的分辨主要是高电平的输出时长不同。

```c
#define CHECK_TIME 28 //超过0值的高电平时间

for(i=0;i<40;i++)//循环接收40位数据
{
    timeout = 5000;
    //等待低电平过去
    while( ( !DATA_GPIO_IN ) && (timeout > 0) ) timeout--; //54us
    delay_uus(CHECK_TIME);//等待超过位数据0值的高电平时间
    if ( DATA_GPIO_IN )//如果还是高电平，说明是1值
    {
        val=(val<<1)+1;
    }
    else //如果是低电平，说明是0值
    {
        val<<=1;
    }
    timeout = 5000;
    //如果当前还是高电平，等待高电平过去，准备接收下一位数据
    while( DATA_GPIO_IN && (timeout > 0) ) timeout-- ;
}
```

4. 结束信号：模块的数据线输出 40 位数据后，是以低电平结束，它会继续输出低电平 54 微秒后转为输入状态，主机需要转为输出状态，输出高电平释放总线。

```c
DHT11_GPIO_Mode_OUT();//转为输出模式
DATA_GPIO_OUT(1);//主机释放总线
```

数据接收完成，但是这40位数据要如何转化为温湿度数据？并如何保证传输的数据没有错误？

DHT11模块一次完整的数据传输为40bit,高位先出。 数据格式：

> **INFO**：**湿度小数部分数据一直为0！！**

数据传送正确时，校验和数据等于 “ 8bit湿度整数数据+8bit湿度小数数据 +8bi温度整数数据+8bit温度小数数据 ” 所得结果的末8位。举几个例子。

示例一：接收的40位数据分别为：

校验和为 0011 0101 + 0000 0000 + 0001 1000 + 0000 0100 = 0101 0001，与接收的数据一致

湿度为 0011 0101 + 0000 0000 = 35 + 0 = 35%RH

温度为 0001 1000 0000 0100 = 24 + 4 = 24.4℃

示例二：接收的40位数据分别为：

校验和为 0011 0101 + 0000 0000 + 0001 1000 + 0000 0100 = 0101 0001，与接收的数据不一致

计算的数据为0101 0001，接收的数据为0100 1001，两者不一致说明数据不准确，丢弃这次数据，重新接收。

以下为数据处理的实现代码：

```c
//val为接收到的40位数据。
//             湿高8   +   湿低8    +  温高8    +  温低8
verify_num = (val>>32) + (val>>24) + (val>>16) + (val>>8);
//计算的校验和 与 接收的校验和 的差为0说明一致，不为0说明不一致
//(val&0xff)是因为val的大小为64位，我们只需要val的最后8位校验和
verify_num = verify_num - (val&0xff);
//进行校验
if( verify_num )//如果不为0，说明校验失败
{
    // 校验错误
    return 0;
}
else //校验成功
{
    //数据处理
    humidity = (val>>32)&0xff;         //湿度前8位（小数点前数据）
    small_point = (val>>24)&0x00ff;    //湿度后8位（小数点后数据）
    small_point = small_point * 0.1;   //换算为小数点
    humidity = humidity + small_point; //小数前+小数后
    printf("湿度：%.2f\r\n",humidity);

    temperature = (val>>16)&0x0000ff;  //温度前8位（小数点前数据）
    small_point = (val>>8)&0x000000ff; //温度后8位（小数点后数据）
    small_point = small_point * 0.1;   //换算为小数点
    temperature = temperature + small_point;//小数前+小数后
    printf("温度：%.2f\r\n",temperature);

    return val>>8; //返回未处理的数据
}
```

### 2、引脚选择

该模块有3个引脚，具体引脚连接见**各引脚连接**。

### 3、移植至工程

我们新建两个文件分别是 **dht11.c** 和 **dht11.h** ，然后将C文件添加至工程中，将h文件路径添加到工程中。

接下来我们配置 **SYSCONFIG**

1. 双击 **empty.syscfg** 文件，打开它。
2. 在 **empty.syscfg** 文件界面点击 **Tools**，然后点击 **SYSCONFIG** 工具。
3. 点击 **ADD** 添加配置
4. 添加配置【根据下方图片进行添加】【添加**1**个】
5. 开始添加配置，根据引脚选择设定
6. 点击保存

> **WARNING**：出现只要出现下面的框就一定要选择：**`Yes to All`**

7. 然后点击编译（**可能会报错，我们不用管！**）
8. 然后我们所有设定的引脚和功能就会在 **ti_msp_dl_config.h** 中定义。因为这个文件我们包含进了 **board.h** 所以我们只需要引用 **board.h** 即可。【这里的 **board.h** 就充当了芯片头文件的作用】

在文件**dht11.c**中，编写如下代码。

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

#include "dht11.h"
#include "stdio.h"

float temperature = 0;
float humidity = 0;

/******************************************************************
 * 函 数 名 称：DHT11_GPIO_Mode_OUT
 * 函 数 说 明：配置DHT11的数据引脚为输出模式
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void DHT11_GPIO_Mode_OUT(void)
{
    DL_GPIO_initDigitalOutput(DHT11_DATA_IOMUX);

    DL_GPIO_setPins(DHT11_PORT, DHT11_DATA_PIN);

    DL_GPIO_enableOutput(DHT11_PORT, DHT11_DATA_PIN);

    DL_GPIO_setPins(DHT11_PORT, DHT11_DATA_PIN);
}

/******************************************************************
 * 函 数 名 称：DHT11_GPIO_Mode_IN
 * 函 数 说 明：配置DHT11的数据引脚为输入模式
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void DHT11_GPIO_Mode_IN(void)
{
	DL_GPIO_initDigitalInput(DHT11_DATA_IOMUX);
}

// DHT11 复位
void DHT11_RST(void)
{
	DHT11_GPIO_Mode_OUT();   //端口为输出
	DATA_GPIO_OUT(0);        //使总线为低电平
	delay_ms(22);            //拉低至少18ms
	DATA_GPIO_OUT(1);        //使总线为高电平
	delay_us(30);            //主机拉高20~40us
}

/******************************************************************
 * 函 数 名 称：DHT11_Read_Data
 * 函 数 说 明：根据时序读取温湿度数据
 * 函 数 形 参：无
 * 函 数 返 回：0=数据校验失败  其他=温湿度未处理的数据
 * 作       者：LC
 * 备       注：无
******************************************************************/
unsigned int DHT11_Read_Data(void)
{
    int i;
    long long val=0;
    int timeout=0;
    float small_point=0;
    unsigned char verify_num = 0;//验证值

    DATA_GPIO_OUT(0);//数据线输出低电平
    delay_ms(19);  //起始信号保持时间19ms
    DATA_GPIO_OUT(1);//主机释放总线
    delay_us( 20 );//拉高等待

    DHT11_GPIO_Mode_IN();//数据线转为输入模式
    //如果前面没有错误，则模块会发出低电平的应答信号，所以直接等待DHT11拉高，80us
    timeout = 80;
    while( (! DATA_GPIO_IN ) && ( timeout >0 ) )//等待高电平的到来
    {
        delay_us(1);
        timeout--;
    }

    //模块当前处于拉高准备输出数据，所以直接等待DHT11拉低，80us
    timeout = 80;//设置超时时间
    //DATA_GPIO_IN=0时,while条件不成立退出while 说明接收到响应信号
    //当timeout<=0时，while条件不成立退出while  说明超时
    while( DATA_GPIO_IN && ( timeout >0 ) )         //等待低电平的到来
    {
        delay_us(1);
        timeout--;
    }

    #define CHECK_TIME 28 //实测发现超过0值的高电平时间

    for(i=0;i<40;i++)//循环接收40位数据
    {
        timeout = 80;
        while( ( !DATA_GPIO_IN ) && (timeout > 0) )        //等待低电平过去
        {
            delay_us(1);
            timeout--;
        }

        delay_us(CHECK_TIME);//超过0值的高电平时间

        if ( DATA_GPIO_IN )//如果还是高电平，说明是1值
        {
            val=(val<<1)+1;
        }
        else //如果是低电平，说明是0值
        {
            val<<=1;
        }

        timeout = 80;
        while( DATA_GPIO_IN && (timeout > 0) )        //如果还是高电平
        {
            delay_us(1);
            timeout--;
        }
    }

    DHT11_GPIO_Mode_OUT();//转为输出模式
    DATA_GPIO_OUT(1);//主机释放总线

    //  湿高8     + 湿低8      + 温高8     + 温低8
    verify_num = (val>>32) + (val>>24) + (val>>16) + (val>>8);
    //计算的校验和 与 接收的校验和 的差为0说明一致，不为0说明不一致
    verify_num = verify_num - (val&0xff);
    //进行校验
    if( verify_num  )
    {
		printf("ERROR!!\r\n"); // 校验错误
        return 0;
    }
    else //校验成功
    {
        //数据处理
        humidity = (val>>32)&0xff;//湿度前8位（小数点前数据）
        small_point = (val>>24)&0x00ff;//湿度后8位（小数点后数据）
        small_point = small_point * 0.1;//换算为小数点
        humidity = humidity + small_point;//小数前+小数后
//        printf("湿度：%.2f\r\n",humidity);

        temperature = (val>>16)&0x0000ff;//温度前8位（小数点前数据）
        small_point = (val>>8)&0x000000ff;//温度后8位（小数点后数据）
        small_point = small_point * 0.1;//换算为小数点
        temperature = temperature + small_point;//小数前+小数后
//        printf("温度：%.2f\r\n",temperature);

        return val>>8; //返回未处理的数据
    }
}

/******************************************************************
 * 函 数 名 称：Get_temperature
 * 函 数 说 明：获取温度数据
 * 函 数 形 参：无
 * 函 数 返 回：温度值
 * 作       者：LC
 * 备       注：使用前必须先调用 DHT11_Read_Data 读取有数据
******************************************************************/
float Get_temperature(void)
{
    return temperature;
}

/******************************************************************
 * 函 数 名 称：Get_humidity
 * 函 数 说 明：获取湿度数据
 * 函 数 形 参：无
 * 函 数 返 回：湿度值
 * 作       者：LC
 * 备       注：使用前必须先调用 DHT11_Read_Data 读取有数据
******************************************************************/
float Get_humidity(void)
{
    return humidity;
}
```

在文件**dht11.h**中，编写如下代码。

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
#ifndef _BSP_DHT11_H_
#define _BSP_DHT11_H_

#include "board.h"

//设置DHT11输出高或低电平
#define DATA_GPIO_OUT(x)    ( (x) ? (DL_GPIO_setPins(DHT11_PORT,DHT11_DATA_PIN)) : (DL_GPIO_clearPins(DHT11_PORT,DHT11_DATA_PIN)) )
//获取DHT11数据引脚高低电平状态
#define DATA_GPIO_IN        DL_GPIO_readPins(DHT11_PORT, DHT11_DATA_PIN)

extern float temperature;
extern float humidity;

unsigned int DHT11_Read_Data(void);//读取模块数据
float Get_temperature(void);//返回读取模块后的温度数据
float Get_humidity(void);//返回读取模块后的湿度数据

#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "dht11.h"

int main(void)
{
    //开发板初始化
    board_init();

    delay_ms(1000);

    printf("DHT11 demo start\r\n");

    while(1)
    {
        //读取模块数据
        DHT11_Read_Data();

        //显示读取后的温度数据
        printf("temperature = %d\r\n", (int)Get_temperature() );
        //显示读取后的湿度数据
        printf("humidity = %d\r\n", (int)Get_humidity() );

        delay_ms(500);
    }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1lkXoNCUENntTzERcGEUsiQ?pwd=1fo8](https://pan.baidu.com/s/1lkXoNCUENntTzERcGEUsiQ?pwd=1fo8)**提取码**：1fo8

## 百度网盘下载

- https://pan.baidu.com/s/1HQEL699-Yl5Jh3Hp87_FlQ
- https://pan.baidu.com/s/1lkXoNCUENntTzERcGEUsiQ?pwd=1fo8
