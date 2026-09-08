# 指纹识别传感器

- 分类：传感器类
- 来源：https://wiki.lckfb.com/zh-hans/dmx/module/sensor/fingerprint-recognition-sensor.html
- 标题：指纹识别传感器
- 代码块：3 个 · 图片：0 张

光学指纹识别传感器采用了国内著名指纹识别芯片公司杭州晟元芯片技术有限公司(Synochip) 的 AS608 指纹识别芯片。芯片内置 DSP 运算单元，集成了指纹识别算法，能高效快速采集 图像并识别指纹特征。模块配备了串口、USB 通讯接口，用户无需研究复杂的图像处理及及指纹识别算法，只需通过简单的串口、USB 按照通讯协议便可控制模块。本模块可应用于各种考勤机、保险箱柜、指纹门禁系统、指纹锁等场合。

## 一、模块来源

采购链接：

[AS608光学指纹识别模块 指纹采集/STM32 51单片机](https://item.taobao.com/item.htm?spm=a1z10.3-c-s.w4002-24706531953.10.73946a4bXBZb14&id=566648022446)

资料下载链接：

[https://pan.baidu.com/s/1mCDdiU5nwtooxmHiPfYTFA](https://pan.baidu.com/s/1mCDdiU5nwtooxmHiPfYTFA)

资料提取码：kj8o

## 二、规格参数

**工作电压**：3.0-3.6V

**工作电流**：30~60mA

**指纹存容量**：300 枚(ID:0~299)

**认假率**：<0.001%

**搜索时间**：<0.3(S)

**控制方式**：串口或USB

**管脚数量**：8 Pin（2.54mm间距排针）

以上信息见厂家资料文件

## 三、移植过程

我们的目标是将例程移植至MSPM0G3507开发板上【实现添加指纹、删除指纹和搜索指纹的功能】。首先要获取资料，查看数据手册应如何实现读取数据，再移植至我们的工程。

### 1、查看资料

系统内设有一个72K字节的图像缓冲区与二个512bytes大小的特征文件缓冲区，名字分别称为:lmageBuffer，CharBuffer1和CharBuffer2。用户可以通过指令读写任意一个缓冲区。CharBufferl或 CharBuffer2既可以用于存放普通特征文件也可以用于存放模板特征文件。通过UART 口上传或下载图像时为了加快速度，只用到像素字节的高4位，即将两个像素合成一个字节传送。通过USB口则是整8位像素。

指纹库容量根据挂接的FLASH容量不同而改变，系统会自动判别。指纹模板按照序号存放，序号定义为:0—(N-1)(N为指纹库容量)。**用户只能根据序号访问指纹库内容**。

这里我们使用的是串口控制方式，USB的接口我们可以悬空不接。

1脚（**红线**）：模块主电源，接3.3V供电（请勿接3.3V以上电源，否则烧毁模块！）；

2脚（**黄线**）：模块串口TX(发送端)，接MCU或TTL串口的RX（接收端）；

3脚（**白线**）：模块串口RX(接收端)，接MCU或TTL串口的TX（发送端）；

4脚（**黑线**）：模块电源地，接3.3V电源地（负极）；

5脚（**蓝线**）：模块触摸感应信号输出（高电平为检测到触摸），需接VTI到3.3V。

6脚（**绿线**）：模块触摸感应电路电源（3.3V），可以与1脚（红线）并接。

7脚，8脚为USB信号线，使用串口控制模块时可以悬空不用。

### 2、引脚选择

**这里选择使用PA8和PA9的附加串口1功能。**

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

移植步骤中的导入.c和.h文件与**传感器章节**的【**DHT11温湿度传感器**】相同，只是将.c和.h文件更改为**bsp_as608.c**与**bsp_as608.h**。这里不再过多讲述，移植完成后面修改相关代码。

在文件**bsp_as608.c**中，编写如下代码。

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
 * 2024-07-01     LCKFB-LP    first version
 */
#include "bsp_as608.h"
#include "stdio.h"
#include "string.h"

volatile unsigned char FPM10A_RECEICE_BUFFER[32];
unsigned int finger_id = 0;

const unsigned char FPM10A_Get_Device[10] ={0x01,0x00,0x07,0x13,0x00,0x00,0x00,0x00,0x00,0x1b};//口令验证
const unsigned char FPM10A_Pack_Head[6] = {0xEF,0x01,0xFF,0xFF,0xFF,0xFF};  //协议包头
const unsigned char FPM10A_Get_Img[6] = {0x01,0x00,0x03,0x01,0x00,0x05};    //获得指纹图像
const unsigned char FPM10A_Get_Templete_Count[6] ={0x01,0x00,0x03,0x1D,0x00,0x21 }; //获得模版总数
const unsigned char FPM10A_Search[11]={0x01,0x00,0x08,0x04,0x01,0x00,0x00,0x03,0xE7,0x00,0xF8}; //搜索指纹搜索范围0 - 999,使用BUFFER1中的特征码搜索
const unsigned char FPM10A_Search_0_9[11]={0x01,0x00,0x08,0x04,0x01,0x00,0x00,0x00,0x13,0x00,0x21}; //搜索0-9号指纹
const unsigned char FPM10A_Img_To_Buffer1[7]={0x01,0x00,0x04,0x02,0x01,0x00,0x08}; //将图像放入到BUFFER1
const unsigned char FPM10A_Img_To_Buffer2[7]={0x01,0x00,0x04,0x02,0x02,0x00,0x09}; //将图像放入到BUFFER2
const unsigned char FPM10A_Reg_Model[6]={0x01,0x00,0x03,0x05,0x00,0x09}; //将BUFFER1跟BUFFER2合成特征模版
const unsigned char FPM10A_Delete_All_Model[6]={0x01,0x00,0x03,0x0d,0x00,0x11};//删除指纹模块里所有的模版
volatile unsigned char  FPM10A_Save_Finger[9]={0x01,0x00,0x06,0x06,0x01,0x00,0x0B,0x00,0x19};//将BUFFER1中的特征码存放到指定的位置

uint8_t  u1_recv_buff[USART1_RECEIVE_LENGTH]; // 接收缓冲区
uint16_t u1_recv_length;                      // 接收数据长度
uint8_t  u1_recv_flag;                        // 接收完成标志位

/******************************************************************
 * 函 数 名 称：as608_config
 * 函 数 说 明：初始化as608
 * 函 数 形 参：
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：as608的默认波特率是57600
******************************************************************/
void as608_config()
{
    SYSCFG_DL_init();
    //清除串口中断标志
    NVIC_ClearPendingIRQ(UART_1_INST_INT_IRQN);
    //使能串口中断
    NVIC_EnableIRQ(UART_1_INST_INT_IRQN);
}

/************************************************
函数名称 ： uart1_send_byte
功    能 ： 串口发送一个字节
参    数 ： ucch：要发送的字节
返 回 值 ：
作    者 ： LC
*************************************************/
void uart1_send_byte(uint8_t ucch)
{
    //当串口1忙的时候等待，不忙的时候再发送传进来的字符
    while( DL_UART_isBusy(UART_1_INST) == true );
    //发送单个字符
    DL_UART_Main_transmitData(UART_1_INST, ucch);
}

/************************************************
函数名称 ： uart1_receive_clear
功    能 ： 清除串口接收的全部数据
参    数 ： 无
返 回 值 ： 无
作    者 ： LC
*************************************************/
void  uart1_receive_clear(void)
{
    unsigned int i = 0;
    for( i = 0; i < USART1_RECEIVE_LENGTH; i++ )
    {
        u1_recv_buff[ i ] = 0;
    }
    u1_recv_length = 0;
	u1_recv_flag = 0;
}

/******************************************************************
 * 函 数 名 称：get_as608_touch
 * 函 数 说 明：获取是否有手指触摸识别区
 * 函 数 形 参：无
 * 函 数 返 回：0没有触摸    1有触摸
 * 作       者：LC
 * 备       注：无
******************************************************************/
char get_as608_touch(void)
{
	if( TOUCH_IN == 1 )//触摸为1
	{
		//printf("Touch-1\r\n");
		return 1;
	}
	else
	{
		//printf("Touch-0\r\n");
	}
	return 0;
}

/******************************************************************
 * 函 数 名 称：FPM10A_Cmd_Send_Pack_Head
 * 函 数 说 明：发送包头
 * 函 数 形 参：无
 * 函 数 返 回：wu
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FPM10A_Cmd_Send_Pack_Head(void)
{
	int i;
	for(i=0;i<6;i++) //包头
	{
		uart1_send_byte(FPM10A_Pack_Head[i]);
	}
}
/******************************************************************
 * 函 数 名 称：FPM10A_Cmd_Check
 * 函 数 说 明：发送指令
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FPM10A_Cmd_Check(void)
{
	int i=0;
	FPM10A_Cmd_Send_Pack_Head(); //发送通信协议包头

	for(i=0;i<10;i++)
	{
		uart1_send_byte(FPM10A_Get_Device[i]);
	}
}
/******************************************************************
 * 函 数 名 称：FPM10A_Receive_Data
 * 函 数 说 明：接收反馈数据缓冲
 * 函 数 形 参：ucLength 接收长度
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FPM10A_Receive_Data(unsigned char ucLength)
{
	unsigned char i = 0;
	unsigned int timeout = 1000;//超时时间,单位Ms
	//等待数据接收完毕
	while(u1_recv_flag==0 && timeout > 0 )
	{
		delay_ms(1);
		timeout--;
	}

	delay_ms(100);        // 一定要加延时！！！
	if( u1_recv_flag == 1 )
	{
		u1_recv_flag = 0;
		for (i=0;i<ucLength;i++)
		{
			FPM10A_RECEICE_BUFFER[i] = u1_recv_buff[i];
		}
		uart1_receive_clear();
	}
	else
	{
	  //Error, no data received
	}

}
/******************************************************************
 * 函 数 名 称：FPM10A_Cmd_Get_Img
 * 函 数 说 明：获得指纹图像命令
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FPM10A_Cmd_Get_Img(void)
{
    unsigned char i;
    FPM10A_Cmd_Send_Pack_Head(); //发送通信协议包头
    for(i=0;i<6;i++) //发送命令 0x1d
	{
		uart1_send_byte(FPM10A_Get_Img[i]);
	}
}
/******************************************************************
 * 函 数 名 称：FINGERPRINT_Cmd_Img_To_Buffer1
 * 函 数 说 明：将图像转换成特征码存放在Buffer1中
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FINGERPRINT_Cmd_Img_To_Buffer1(void)
{
	unsigned char i;
	FPM10A_Cmd_Send_Pack_Head(); //发送通信协议包头

	for(i=0;i<7;i++)   //发送命令 将图像转换成 特征码 存放在 CHAR_buffer1
	{
		uart1_send_byte(FPM10A_Img_To_Buffer1[i]);
	}
}
/******************************************************************
 * 函 数 名 称：FINGERPRINT_Cmd_Img_To_Buffer2
 * 函 数 说 明：将图像转换成特征码存放在Buffer2中
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FINGERPRINT_Cmd_Img_To_Buffer2(void)
{
	unsigned char i;
	for(i=0;i<6;i++)    //发送包头
	{
		uart1_send_byte(FPM10A_Pack_Head[i]);
	}
	for(i=0;i<7;i++)   //发送命令 将图像转换成 特征码 存放在 CHAR_buffer1
	{
		uart1_send_byte(FPM10A_Img_To_Buffer2[i]);
	}
}
/******************************************************************
 * 函 数 名 称：FPM10A_Cmd_Search_Finger
 * 函 数 说 明：搜索全部用户999枚
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FPM10A_Cmd_Search_Finger(void)
{
    unsigned char i;
    FPM10A_Cmd_Send_Pack_Head(); //发送通信协议包头

    for(i=0;i<11;i++)
    {
        uart1_send_byte(FPM10A_Search[i]);
    }
}
/******************************************************************
 * 函 数 名 称：FPM10A_Cmd_Reg_Model
 * 函 数 说 明：将BUFFER1跟BUFFER2合成特征模版
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FPM10A_Cmd_Reg_Model(void)
{
    unsigned char i;
    FPM10A_Cmd_Send_Pack_Head(); //发送通信协议包头

    for(i=0;i<6;i++)
    {
        uart1_send_byte(FPM10A_Reg_Model[i]);
    }
}
/******************************************************************
 * 函 数 名 称：FINGERPRINT_Cmd_Delete_All_Model
 * 函 数 说 明：删除指纹模块里的所有指纹模版
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FINGERPRINT_Cmd_Delete_All_Model(void)
{
	unsigned char i;

	for(i=0;i<6;i++) //包头
	{
		uart1_send_byte(FPM10A_Pack_Head[i]);
	}

	for(i=0;i<6;i++) //命令合并指纹模版
	{
		uart1_send_byte(FPM10A_Delete_All_Model[i]);
	}
}
/******************************************************************
 * 函 数 名 称：FPM10A_Cmd_Save_Finger
 * 函 数 说 明：保存指纹
 * 函 数 形 参：保存指纹的位置（ID号）
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FPM10A_Cmd_Save_Finger( unsigned int storeID )
{
    unsigned long temp = 0;
    unsigned char i;
    FPM10A_Save_Finger[5] =(storeID&0xFF00)>>8;
    FPM10A_Save_Finger[6] = (storeID&0x00FF);

    for(i=0;i<7;i++)   //计算校验和
    {
        temp = temp + FPM10A_Save_Finger[i];
    }

    FPM10A_Save_Finger[7]=(temp & 0x00FF00) >> 8; //存放校验数据
    FPM10A_Save_Finger[8]= temp & 0x0000FF;
    FPM10A_Cmd_Send_Pack_Head(); //发送通信协议包头

    for(i=0;i<9;i++)
    {
        //发送命令 将图像转换成 特征码 存放在 CHAR_buffer1
        uart1_send_byte(FPM10A_Save_Finger[i]);
    }
}

/******************************************************************
 * 函 数 名 称：key_scanf
 * 函 数 说 明：按键功能  确定-取消
 * 函 数 形 参：
 * 函 数 返 回：0=未动作  1=确定  2=取消
 * 作       者：LC
 * 备       注：当前是使用串口来模拟按键，如果你有按键请自行修改
 *              修改要求：按下确定键时返回1；按下取消键时，返回2。
******************************************************************/
extern volatile uint8_t  recv0_buff[USART1_RECEIVE_LENGTH];
extern volatile uint16_t recv0_length;
extern volatile uint8_t  recv0_flag;

void recv0_clear_buff()
{
	for(int i = 0; i < USART1_RECEIVE_LENGTH; i++)
	{
		recv0_buff[i] = 0;
	}

	recv0_length = 0;
	recv0_flag = 0;
}

char key_scanf(void)
{

    /***************    你的代码    ***************/
    if(strstr( (const char*)recv0_buff, "Yes") != NULL )
    {
        printf("key_scanf-YES\r\n");

		recv0_clear_buff();

        return 1;//返回 确定键被按下
    }
    if(strstr( (const char*)recv0_buff, "No") != NULL )
    {
        printf("key_scanf-NO\r\n");

		recv0_clear_buff();

        return 2;//返回 取消键被按下
    }
     /***************    你的代码    ***************/

    return 0;
}

/******************************************************************
 * 函 数 名 称：FPM10A_Add_Fingerprint
 * 函 数 说 明：添加指纹
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FPM10A_Add_Fingerprint(void)
{
//        unsigned char id_show[3]={0,0,0};
        unsigned char key_num= key_scanf();
        finger_id=0;

        printf("Do you want to add fingerprints? [Yes/No]\r\n");

        while( key_num != 2 )//按返回键直接回到主菜单
        {
			key_num= key_scanf();

			 //按确认键开始录入指纹信息
			 if( key_num == 1 )
			 {
				printf("start add\r\n");

				while( key_num != 2 )//按下返回键退出录入返回fingerID调整状态
				{
					key_num= key_scanf();
					FPM10A_Cmd_Get_Img(); //获得指纹图像
					FPM10A_Receive_Data(12);
					//判断接收到的确认码,等于0指纹获取成功
					if(FPM10A_RECEICE_BUFFER[9]==0)
					{
						delay_ms(100);
						FINGERPRINT_Cmd_Img_To_Buffer1();
						FPM10A_Receive_Data(12);
						delay_ms(1000);
						while( key_num != 2 )
						{
							key_num= key_scanf();
							FPM10A_Cmd_Get_Img(); //获得指纹图像
							FPM10A_Receive_Data(12);
							//判断接收到的确认码,等于0指纹获取成功
							if(FPM10A_RECEICE_BUFFER[9]==0)
							{
								delay_ms(200);
								printf("successfully added, ID = %d\r\n",finger_id);
								FINGERPRINT_Cmd_Img_To_Buffer2();
								FPM10A_Receive_Data(12);
								FPM10A_Cmd_Reg_Model();//转换成特征码
								FPM10A_Receive_Data(12);
								//保存指纹
								FPM10A_Cmd_Save_Finger(finger_id);
								FPM10A_Receive_Data(12);
								delay_ms(1000);
								finger_id=finger_id+1;
								break;
							}
						}

						break;
					}
				}
			}
        }
}
/******************************************************************
 * 函 数 名 称：FPM10A_Find_Fingerprint
 * 函 数 说 明：搜索指纹
 * 函 数 形 参：无
 * 函 数 返 回：指纹ID号
 * 作       者：LC
 * 备       注：255：未查到  其他：查找到了
******************************************************************/
unsigned int FPM10A_Find_Fingerprint(void)
{
	unsigned int find_fingerid = 255;

//    printf("Please put your finger in\r\n");

    if( get_as608_touch() == 1 )//有手指触摸识别区
    {
        FPM10A_Cmd_Get_Img(); //获得指纹图像
        FPM10A_Receive_Data(12);
        //判断接收到的确认码,等于0指纹获取成功
        if(FPM10A_RECEICE_BUFFER[9]==0)
        {
            delay_ms(100);
            FINGERPRINT_Cmd_Img_To_Buffer1();
            FPM10A_Receive_Data(12);
            FPM10A_Cmd_Search_Finger();
            FPM10A_Receive_Data(16);
            if(FPM10A_RECEICE_BUFFER[9] == 0) //搜索成功
            {
                //拼接指纹ID数
                find_fingerid = FPM10A_RECEICE_BUFFER[10]*256 + FPM10A_RECEICE_BUFFER[11];
                printf("ID = %d\r\n",find_fingerid);
                delay_ms(500);
            }
            else //没有找到
            {
                printf("not found\r\n");
            }
        }
    }
    return find_fingerid;
}
/******************************************************************
 * 函 数 名 称：FPM10A_Delete_All_Fingerprint
 * 函 数 说 明：删除所有存贮的指纹库
 * 函 数 形 参：无
 * 函 数 返 回：无
 * 作       者：LC
 * 备       注：无
******************************************************************/
void FPM10A_Delete_All_Fingerprint(void)
{
	unsigned char key_num=0;
	printf("Whether to delete fingerprint ?  [Yes/No]\r\n");

	do{
		key_num = key_scanf();
		if(key_num == 1 )//点击确定键
		{
			printf("deleting\r\n");
			delay_ms(300);
			FINGERPRINT_Cmd_Delete_All_Model();
			FPM10A_Receive_Data(12);
			printf("Have all been cleared\r\n");
			break;
		}
		if( u1_recv_flag == 1 )
		{
			u1_recv_flag = 0;
			printf("rev = %s\r\n", u1_recv_buff);
		}
	}while( key_num != 2 );//没有点击取消键，则继续循环
}

/******************************************************************
 * 函 数 名 称：Device_Check
 * 函 数 说 明：模块检查
 * 函 数 形 参：无
 * 函 数 返 回：0未检测到模块或者模块异常  1检测到模块并且通信成功
 * 作       者：LC
 * 备       注：返回0时要注意接线是否正确、串口配置是否可用
******************************************************************/
char Device_Check(void)
{
		FPM10A_RECEICE_BUFFER[9]=1; //串口数组第九位可判断是否通信正常

		FPM10A_Cmd_Check();    //单片机向指纹模块发送校对命令
		FPM10A_Receive_Data(12);     //将串口接收到的数据转存

		if(FPM10A_RECEICE_BUFFER[9] == 0)  //判断数据低第9位是否接收到0
		{
			return 1;
		}
		return 0;
}

//串口的中断服务函数
void UART_1_INST_IRQHandler(void)
{
    //如果产生了串口中断
    switch( DL_UART_getPendingInterrupt(UART_1_INST) )
    {
        case DL_UART_IIDX_RX://如果是接收中断
            //接发送过来的数据保存在变量中
            u1_recv_buff[u1_recv_length++] = DL_UART_Main_receiveData(UART_1_INST);

            u1_recv_buff[u1_recv_length] = '\0';  // 数据接收完毕，数组结束标志
            u1_recv_flag = 1;

            break;

        default://其他的串口中断
            break;
    }
}
```

在文件**bsp_as608.h**中，编写如下代码。

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
 * 2024-07-01     LCKFB-LP    first version
 */
#ifndef _BSP_AS608_H_
#define _BSP_AS608_H_

#include "board.h"

#define TOUCH_IN    ( ( DL_GPIO_readPins( GPIO_PORT, GPIO_TOUCH_PIN ) & GPIO_TOUCH_PIN ) ? 1 : 0 )

/* 串口缓冲区的数据长度 */
#define USART1_RECEIVE_LENGTH  128

extern uint8_t  u2_recv_buff[USART1_RECEIVE_LENGTH]; // 接收缓冲区
extern uint16_t u2_recv_length;                     // 接收数据长度
extern uint8_t  u2_recv_flag;                       // 接收完成标志位

void as608_config();
char get_as608_touch(void);
void uart1_receive_clear(void);

char Device_Check(void);
void FPM10A_Add_Fingerprint(void);//添加指纹
unsigned int FPM10A_Find_Fingerprint(void);//查找指纹
void FPM10A_Delete_All_Fingerprint(void);
#endif
```

## 四、移植验证

在empty.c中输入代码如下:

```c
#include "board.h"
#include <stdio.h>
#include "bsp_as608.h"

int main(void)
{
    //开发板初始化
    board_init();

    as608_config();

    printf("AS608 demo start\r\n");

	  delay_ms(1000);

    Device_Check();//模块检测

    FPM10A_Delete_All_Fingerprint();  //是否删除全部指纹

    FPM10A_Add_Fingerprint();//是否添加指纹

    while(1)
    {
        FPM10A_Find_Fingerprint();//查找指纹

    }
}
```

上电效果：

移植成功案例代码下载链接：

> **【百度网盘】**：**链接**：[https://pan.baidu.com/s/1HVBShqN2U08CXIDiznsF3Q?pwd=u61d](https://pan.baidu.com/s/1HVBShqN2U08CXIDiznsF3Q?pwd=u61d)**提取码**：u61d

## 百度网盘下载

- https://pan.baidu.com/s/1mCDdiU5nwtooxmHiPfYTFA
- https://pan.baidu.com/s/1HVBShqN2U08CXIDiznsF3Q?pwd=u61d
