#include "oled.h"
#include "delay.h"
#include "stdlib.h"
#include "oledfont.h"

u8 OLED_GRAM[144][8];

/* ===========================================================================
 * SPI 总线变体（批次 12/07 决策 B）：软 SPI 位操作 5 脚 SCL/SDA/DC/CS/RES
 * （母版 syscfg 实例 OLED_SPI——宏 OLED_SPI_<引脚名>_PORT/PIN 由 SysConfig
 * 按引脚名分派各口；不占硬件 SPI 外设/TIMER，nrf24l01/max7219 先例——
 * SSD1306 SPI ≤10MHz，GPIO 翻转速度满足、无需节拍延时）
 * =========================================================================== */

#define OLED_SPI_SCL(x)                                                \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(OLED_SPI_SCL_PORT, OLED_SPI_SCL_PIN);      \
        } else {                                                       \
            DL_GPIO_clearPins(OLED_SPI_SCL_PORT, OLED_SPI_SCL_PIN);    \
        }                                                              \
    } while (0)

#define OLED_SPI_SDA(x)                                                \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(OLED_SPI_SDA_PORT, OLED_SPI_SDA_PIN);      \
        } else {                                                       \
            DL_GPIO_clearPins(OLED_SPI_SDA_PORT, OLED_SPI_SDA_PIN);    \
        }                                                              \
    } while (0)

#define OLED_SPI_DC(x)                                                 \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(OLED_SPI_DC_PORT, OLED_SPI_DC_PIN);        \
        } else {                                                       \
            DL_GPIO_clearPins(OLED_SPI_DC_PORT, OLED_SPI_DC_PIN);      \
        }                                                              \
    } while (0)

#define OLED_SPI_CS(x)                                                 \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(OLED_SPI_CS_PORT, OLED_SPI_CS_PIN);        \
        } else {                                                       \
            DL_GPIO_clearPins(OLED_SPI_CS_PORT, OLED_SPI_CS_PIN);      \
        }                                                              \
    } while (0)

#define OLED_SPI_RES(x)                                                \
    do {                                                               \
        if (x) {                                                       \
            DL_GPIO_setPins(OLED_SPI_RES_PORT, OLED_SPI_RES_PIN);      \
        } else {                                                       \
            DL_GPIO_clearPins(OLED_SPI_RES_PORT, OLED_SPI_RES_PIN);    \
        }                                                              \
    } while (0)

/* 总线模式静态态：0 = I2C1 硬件 I2C（默认，OLED_Init）、1 = SPI 位操作
 * （OLED_SPI_Init）；两种模式共用同一初始化序列与显存 API（厂家 SPI/I2C
 * 例程同参核对）。 */
static uint8_t s_bus_spi = 0;

/* 分辨率静态态：0 = 128×64（默认）、1 = 128×32（0.91 寸，oled_set_res）。 */
static uint8_t s_res = OLED_RES_128X64;

/* SPI 位操作写一个字节（vendor SPI 例程 OLED_WR_Byte：DC 按 mode 控、
 * CS 每字节选通/释放——SCL 上升沿采样 SPI 模式 0） */
static void oled_spi_write_byte(uint8_t dat, uint8_t mode)
{
    uint8_t i;
    if (mode) {
        OLED_SPI_DC(1);
    } else {
        OLED_SPI_DC(0);
    }
    OLED_SPI_CS(0);
    for (i = 0; i < 8; i++) {
        OLED_SPI_SCL(0);
        if (dat & 0x80u) {
            OLED_SPI_SDA(1);
        } else {
            OLED_SPI_SDA(0);
        }
        OLED_SPI_SCL(1);
        dat <<= 1;
    }
    OLED_SPI_CS(1);
    OLED_SPI_DC(1);
}

//反显函数
void OLED_ColorTurn(u8 i)
{
	if(i==0) OLED_WR_Byte(0xA6,OLED_CMD);//正常显示
	if(i==1) OLED_WR_Byte(0xA7,OLED_CMD);//反色显示
}

//屏幕旋转180度
void OLED_DisplayTurn(u8 i)
{
	if(i==0)
	{
		OLED_WR_Byte(0xC8,OLED_CMD);//正常显示
		OLED_WR_Byte(0xA1,OLED_CMD);
	}
	if(i==1)
	{
		OLED_WR_Byte(0xC0,OLED_CMD);//反转显示
		OLED_WR_Byte(0xA0,OLED_CMD);
	}
}

void OLED_WR_Byte(uint8_t dat, uint8_t mode)
{
    uint8_t txData[2];

    if (s_bus_spi) { /* SPI 总线变体：位操作（零回归——I2C 路径不进入） */
        oled_spi_write_byte(dat, mode);
        return;
    }

    // 控制字节: 0x00为命令, 0x40为数据
    txData[0] = mode ? 0x40 : 0x00;
    txData[1] = dat;

    // 1. 等待 I2C 控制器空闲
    while (!(DL_I2C_getControllerStatus(OLED_INST) & DL_I2C_CONTROLLER_STATUS_IDLE));

    // 2. 将 2 个字节填入发送 FIFO
    DL_I2C_fillControllerTXFIFO(OLED_INST, txData, 2);

    // 3. 启动传输：7位地址 0x3C，TX方向，2字节
    DL_I2C_startControllerTransfer(OLED_INST, 0x3C, DL_I2C_CONTROLLER_DIRECTION_TX, 2);

    // 4. 等待控制器进入 BUSY 状态（确认传输已真正启动）
    //    改用 BUSY（控制器状态）而非 BUSY_BUS（总线状态），更可靠
    while (!(DL_I2C_getControllerStatus(OLED_INST) & DL_I2C_CONTROLLER_STATUS_BUSY));

    // 5. 等待 I2C 回到空闲状态（传输完成）
    while (!(DL_I2C_getControllerStatus(OLED_INST) & DL_I2C_CONTROLLER_STATUS_IDLE));
}

//开启OLED显示 
void OLED_DisPlay_On(void)
{
	OLED_WR_Byte(0x8D,OLED_CMD);//电荷泵使能
	OLED_WR_Byte(0x14,OLED_CMD);//开启电荷泵
	OLED_WR_Byte(0xAF,OLED_CMD);//点亮屏幕
}

//关闭OLED显示 
void OLED_DisPlay_Off(void)
{
	OLED_WR_Byte(0x8D,OLED_CMD);//电荷泵使能
	OLED_WR_Byte(0x10,OLED_CMD);//关闭电荷泵
	OLED_WR_Byte(0xAF,OLED_CMD);//关闭屏幕
}

//更新显存到OLED	
void OLED_Refresh(void)
{
	u8 i,n;
	for(i=0;i<8;i++)
	{
	   OLED_WR_Byte(0xb0+i,OLED_CMD); //设置行起始地址
	   OLED_WR_Byte(0x00,OLED_CMD);   //设置低列起始地址
	   OLED_WR_Byte(0x10,OLED_CMD);   //设置高列起始地址
	   for(n=0;n<128;n++)
		 OLED_WR_Byte(OLED_GRAM[n][i],OLED_DATA);
	}
}

//清屏函数
void OLED_Clear(void)
{
	u8 i,n;
	for(i=0;i<8;i++)
	{
	   for(n=0;n<128;n++)
		{
			 OLED_GRAM[n][i]=0;//清除所有数据
		}
	}
	OLED_Refresh();//更新显示
}

//画点 
void OLED_DrawPoint(u8 x,u8 y)
{
	u8 i,m,n;
	i=y/8;
	m=y%8;
	n=1<<m;
	OLED_GRAM[x][i]|=n;
}

//清除一个点
void OLED_ClearPoint(u8 x,u8 y)
{
	u8 i,m,n;
	i=y/8;
	m=y%8;
	n=1<<m;
	OLED_GRAM[x][i]=~OLED_GRAM[x][i];
	OLED_GRAM[x][i]|=n;
	OLED_GRAM[x][i]=~OLED_GRAM[x][i];
}

//画线
void OLED_DrawLine(u8 x1,u8 y1,u8 x2,u8 y2)
{
	u8 i,k,k1,k2;
	if((x1<0)||(x2>128)||(y1<0)||(y2>64)||(x1>x2)||(y1>y2))return;
	if(x1==x2)    //画竖线
	{
		for(i=0;i<(y2-y1);i++) OLED_DrawPoint(x1,y1+i);
	}
	else if(y1==y2)   //画横线
	{
		for(i=0;i<(x2-x1);i++) OLED_DrawPoint(x1+i,y1);
	}
	else      //画斜线
	{
		k1=y2-y1;
		k2=x2-x1;
		k=k1*10/k2;
		for(i=0;i<(x2-x1);i++) OLED_DrawPoint(x1+i,y1+i*k/10);
	}
}

//画圆
void OLED_DrawCircle(u8 x,u8 y,u8 r)
{
	int a = 0, b = r, num;
	while(2 * b * b >= r * r)      
	{
		OLED_DrawPoint(x + a, y - b);
		OLED_DrawPoint(x - a, y - b);
		OLED_DrawPoint(x - a, y + b);
		OLED_DrawPoint(x + a, y + b);
		OLED_DrawPoint(x + b, y + a);
		OLED_DrawPoint(x + b, y - a);
		OLED_DrawPoint(x - b, y - a);
		OLED_DrawPoint(x - b, y + a);
		
		a++;
		num = (a * a + b * b) - r*r;
		if(num > 0) { b--; a--; }
	}
}

//显示字符
void OLED_ShowChar(u8 x,u8 y,u8 chr,u8 size1)
{
	u8 i,m,temp,size2,chr1;
	u8 y0=y;
	size2=(size1/8+((size1%8)?1:0))*(size1/2);  
	chr1=chr-' ';  
	for(i=0;i<size2;i++)
	{
		if(size1==12) {temp=asc2_1206[chr1][i];} 
		else if(size1==16) {temp=asc2_1608[chr1][i];} 
		else if(size1==24) {temp=asc2_2412[chr1][i];} 
		else return;
		for(m=0;m<8;m++)           
		{
			if(temp&0x80)OLED_DrawPoint(x,y);
			else OLED_ClearPoint(x,y);
			temp<<=1;
			y++;
			if((y-y0)==size1)
			{
				y=y0;
				x++;
				break;
			}
		}
	}
}

//显示字符串
void OLED_ShowString(u8 x,u8 y,u8 *chr,u8 size1)
{
	while((*chr>=' ')&&(*chr<='~'))
	{
		OLED_ShowChar(x,y,*chr,size1);
		x+=size1/2;
		if(x>128-size1)  //换行
		{
			x=0;
			y+=size1; // 修复了原代码的y+=2的bug
		}
		chr++;
	}
}

//m^n
u32 OLED_Pow(u8 m,u8 n)
{
	u32 result=1;
	while(n--) result*=m;
	return result;
}

//显示数字
void OLED_ShowNum(u8 x,u8 y,u32 num,u8 len,u8 size1)
{
	u8 t,temp;
	for(t=0;t<len;t++)
	{
		temp=(num/OLED_Pow(10,len-t-1))%10;
		if(temp==0) OLED_ShowChar(x+(size1/2)*t,y,'0',size1);
		else OLED_ShowChar(x+(size1/2)*t,y,temp+'0',size1);
	}
}

//显示汉字
void OLED_ShowChinese(u8 x,u8 y,u8 num,u8 size1)
{
	u8 i,m,n=0,temp,chr1;
	u8 x0=x,y0=y;
	u8 size3=size1/8;
	while(size3--)
	{
		chr1=num*size1/8+n;
		n++;
		for(i=0;i<size1;i++)
		{
			if(size1==16) {temp=Hzk1[chr1][i];}
			else if(size1==24) {temp=Hzk2[chr1][i];}
			else if(size1==32) {temp=Hzk3[chr1][i];}
			else if(size1==64) {temp=Hzk4[chr1][i];}
			else return;
						
			for(m=0;m<8;m++)
			{
				if(temp&0x01)OLED_DrawPoint(x,y);
				else OLED_ClearPoint(x,y);
				temp>>=1;
				y++;
			}
			x++;
			if((x-x0)==size1) {x=x0;y0=y0+8;}
			y=y0;
		}
	}
}

//配置写入数据的起始位置
void OLED_WR_BP(u8 x,u8 y)
{
	OLED_WR_Byte(0xb0+y,OLED_CMD);//设置行起始地址
	OLED_WR_Byte(((x&0xf0)>>4)|0x10,OLED_CMD);
	OLED_WR_Byte((x&0x0f)|0x01,OLED_CMD);
}

//显示图片
void OLED_ShowPicture(u8 x0,u8 y0,u8 x1,u8 y1,u8 BMP[])
{
	u32 j=0;
	u8 x=0,y=0;
	if(y%8==0)y=0;
	else y+=1;
	for(y=y0;y<y1;y++)
	{
		 OLED_WR_BP(x0,y);
		 for(x=x0;x<x1;x++)
		 {
			 OLED_WR_Byte(BMP[j],OLED_DATA);
			 j++;
		 }
	}
}

// OLED 自检函数：验证屏幕接线是否正常
void OLED_Test(void)
{
    // 1. 全屏清空
    OLED_Clear();

    // 2. 显示文字
    OLED_ShowString(0, 0,  (u8 *)"OLED OK!", 16);

    // 3. 显示数字
    OLED_ShowNum(80, 0, 123, 3, 16);

    // 4. 画一个矩形边框
    OLED_DrawLine(0,  20, 127, 20);  // 顶边
    OLED_DrawLine(0,  20, 0,   63);  // 左边
    OLED_DrawLine(0,  63, 127, 63);  // 底边
    OLED_DrawLine(127, 20, 127, 63); // 右边

    // 5. 画两个同心圆
    OLED_DrawCircle(64, 42, 10);
    OLED_DrawCircle(64, 42, 5);

    // 6. 刷新到屏幕
    OLED_Refresh();
}

//OLED的初始化
static void oled_drv_init(void); /* 初始化序列（总线无关，定义在下方） */

void OLED_Init(void)
{
	// 4针OLED没有RST引脚，直接延时等待屏幕内部RC电路上电复位完成
	s_bus_spi = 0; /* I2C 路径（缺省；OLED_SPI_Init 曾调用时可切回） */
	delay_ms(100);
	oled_drv_init();
}

/* SPI 总线变体初始化（批次 12/07 决策 B：同序列同 API，仅总线层不同；
 * 复位走 RES 引脚——厂家 SPI 例程 RES 200ms 低脉冲） */
void OLED_SPI_Init(void)
{
	s_bus_spi = 1;
	OLED_SPI_RES(0);
	delay_ms(200);
	OLED_SPI_RES(1);
	oled_drv_init();
}

/* 分辨率设置（128×32 = 0.91 寸屏；须在初始化前调用——初始化序列的
 * MUX/COM 参数随 s_res 分支） */
void oled_set_res(uint8_t res)
{
	s_res = res ? OLED_RES_128X32 : OLED_RES_128X64;
}

/* 初始化序列（总线无关——OLED_WR_Byte 按 s_bus_spi 分发；厂家 I2C/SPI
 * 例程同参核对：0xAE/0xA8 0x3F/0xDA 0x12/0x8D 0x14…逐字节一致，仅总线
 * 层不同；128×32 按厂家 0.91 例程 MUX=0x1F/COM=0x00 分支） */
static void oled_drv_init(void)
{
	OLED_WR_Byte(0xAE,OLED_CMD);//--turn off oled panel
	OLED_WR_Byte(0x00,OLED_CMD);//---set low column address
	OLED_WR_Byte(0x10,OLED_CMD);//---set high column address
	OLED_WR_Byte(0x40,OLED_CMD);//--set start line address  Set Mapping RAM Display Start Line (0x00~0x3F)
	OLED_WR_Byte(0x81,OLED_CMD);//--set contrast control register
	OLED_WR_Byte(0xCF,OLED_CMD);// Set SEG Output Current Brightness
	OLED_WR_Byte(0xA1,OLED_CMD);//--Set SEG/Column Mapping     0xa0左右反置 0xa1正常
	OLED_WR_Byte(0xC8,OLED_CMD);//Set COM/Row Scan Direction   0xc0上下反置 0xc8正常
	OLED_WR_Byte(0xA6,OLED_CMD);//--set normal display
	OLED_WR_Byte(0xA8,OLED_CMD);//--set multiplex ratio(1 to 64)
	OLED_WR_Byte((s_res == OLED_RES_128X32) ? 0x1F : 0x3F, OLED_CMD);//1/64 duty（128×32 = 1/32）
	OLED_WR_Byte(0xD3,OLED_CMD);//-set display offset	Shift Mapping RAM Counter (0x00~0x3F)
	OLED_WR_Byte(0x00,OLED_CMD);//-not offset
	OLED_WR_Byte(0xd5,OLED_CMD);//--set display clock divide ratio/oscillator frequency
	OLED_WR_Byte(0x80,OLED_CMD);//--set divide ratio, Set Clock as 100 Frames/Sec
	OLED_WR_Byte(0xD9,OLED_CMD);//--set pre-charge period
	OLED_WR_Byte(0xF1,OLED_CMD);//Set Pre-Charge as 15 Clocks & Discharge as 1 Clock
	OLED_WR_Byte(0xDA,OLED_CMD);//--set com pins hardware configuration
	OLED_WR_Byte((s_res == OLED_RES_128X32) ? 0x00 : 0x12, OLED_CMD);
	OLED_WR_Byte(0xDB,OLED_CMD);//--set vcomh
	OLED_WR_Byte(0x40,OLED_CMD);//Set VCOM Deselect Level
	OLED_WR_Byte(0x20,OLED_CMD);//-Set Page Addressing Mode (0x00/0x01/0x02)
	OLED_WR_Byte(0x02,OLED_CMD);//
	OLED_WR_Byte(0x8D,OLED_CMD);//--set Charge Pump enable/disable
	OLED_WR_Byte(0x14,OLED_CMD);//--set(0x10) disable
	OLED_WR_Byte(0xA4,OLED_CMD);// Disable Entire Display On (0xa4/0xa5)
	OLED_WR_Byte(0xA6,OLED_CMD);// Disable Inverse Display On (0xa6/a7)

		// 先清软件 GRAM，再开显示 + 刷新 → 无花屏
		{
			u8 i, n;
			for (i = 0; i < 8; i++)
				for (n = 0; n < 128; n++)
					OLED_GRAM[n][i] = 0;
		}
		OLED_WR_Byte(0xAF,OLED_CMD);//--turn on oled panel
		OLED_Refresh();
}


/* ============================================================
 * 双平台共同小写 API：line/column → 像素坐标（16×8 字符网格，
 * 字号 16；OLED_ShowString/ShowNum 写完显存后由 oled_refresh 刷新）。
 * ============================================================ */
void oled_show_text(uint8_t line, uint8_t column, const char *text)
{
    OLED_ShowString((u8)(column * 8), (u8)(line * 16), (u8 *)text, 16);
}

void oled_show_number(uint8_t line, uint8_t column, uint32_t number, uint8_t length)
{
    OLED_ShowNum((u8)(column * 8), (u8)(line * 16), number, length, 16);
}

void oled_refresh(void)
{
    OLED_Refresh();
}
