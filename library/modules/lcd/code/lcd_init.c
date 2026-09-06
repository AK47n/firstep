#include "lcd_init.h"
#include "lcd.h"
#include "delay.h"

/* ===========================================================================
 * 软 SPI 总线原语（厂家 LCD_Writ_Bus 移植：每字节 CS 低 → 8 位 MSB 先 →
 * CS 高——片选空闲高；SCL 上升沿采样，SPI 模式 0）
 * =========================================================================== */

static void lcd_writ_bus(uint8_t dat)
{
    uint8_t i;
    LCD_CS(0);
    for (i = 0; i < 8; i++) {
        LCD_SCL(0);
        if (dat & 0x80u) {
            LCD_SDA(1);
        } else {
            LCD_SDA(0);
        }
        LCD_SCL(1);
        dat <<= 1;
    }
    LCD_CS(1);
}

void lcd_wr_reg(uint8_t dat)
{
    LCD_DC(0); /* 写命令 */
    lcd_writ_bus(dat);
    LCD_DC(1); /* 写数据 */
}

void lcd_wr_data8(uint8_t dat)
{
    lcd_writ_bus(dat);
}

void lcd_wr_data(uint16_t dat)
{
    lcd_writ_bus((uint8_t)(dat >> 8));
    lcd_writ_bus((uint8_t)dat);
}

/* 初始化序列表项：reg = 寄存器命令；n = 数据字节数（0 = 仅命令）；
 * delay_ms = 命令发出后延时（毫秒，走库 delay 模块）；data = 数据字节。 */
typedef struct {
    uint8_t reg;
    uint8_t n;
    uint8_t delay_ms;
    uint8_t data[16];
} lcd_init_row_t;

/* ===========================================================================
 * 型号数据表（批次 12 决策 A：差异 = 初始化序列 + 分辨率 + 偏移表 + MADCTL，
 * 表驱动——工单 02-05 只追加表项，绘制/文本层零改动）
 * =========================================================================== */

/* 1.3 寸（ST7789V2，240×240）——厂家 1.3 带字库例程 lcd_init() 序列原样录入
 * （字库芯片 zk.c 不并入：汉字能力 = 内嵌 tfont16 常用集，见 spec 决策 A） */
static const lcd_init_row_t lcd_seq_130[] = {
    {0x11, 0, 120, {0x00}},                   /* Sleep out，延时 120ms */
    {0x36, 1, 0, {0x00}},                     /* MADCTL——占位按方向替换 */
    {0x3A, 1, 0, {0x05}},                     /* 16 位色 */
    {0xB2, 5, 0, {0x1F, 0x1F, 0x00, 0x33, 0x33}},
    {0xB7, 1, 0, {0x00}},                     /* VGH=12.2V VGL=-7.16V */
    {0xBB, 1, 0, {0x3F}},
    {0xC0, 1, 0, {0x2C}},
    {0xC2, 1, 0, {0x01}},
    {0xC3, 1, 0, {0x0F}},                     /* 4.3V */
    {0xC4, 1, 0, {0x20}},                     /* VDV 0v */
    {0xC6, 1, 0, {0x13}},
    {0xD0, 2, 0, {0xA4, 0xA1}},
    {0xD6, 1, 0, {0xA1}},                     /* sleep in 后 gate 输出 GND */
    {0xE0, 13, 0, {0xF0, 0x06, 0x0D, 0x0B, 0x0A, 0x07, 0x2E, 0x43,
                   0x45, 0x38, 0x14, 0x13, 0x25}},
    {0xE1, 13, 0, {0xF0, 0x07, 0x0A, 0x08, 0x07, 0x23, 0x2E, 0x33,
                   0x44, 0x3A, 0x16, 0x17, 0x26}},
    {0xE4, 3, 0, {0x1D, 0x00, 0x00}},         /* 240 根 gate (N+1)*8 */
    {0x21, 0, 0, {0x00}},                     /* Display inversion */
    {0x11, 0, 120, {0x00}},                   /* Sleep out（二次，延时 120ms） */
    {0x29, 0, 0, {0x00}},                     /* Display on */
};

/* 1.69 寸（ST7789V2，240×280）——厂家 1.69 例程 lcd_init() 序列原样录入 */
static const lcd_init_row_t lcd_seq_169[] = {
    {0x11, 0, 120, {0x00}},                   /* Sleep out，延时 120ms */
    {0x36, 1, 0, {0x00}},                     /* MADCTL——占位按方向替换 */
    {0x3A, 1, 0, {0x05}},                     /* 16 位色 */
    {0xB2, 5, 0, {0x0C, 0x0C, 0x00, 0x33, 0x33}},
    {0xB7, 1, 0, {0x35}},
    {0xBB, 1, 0, {0x32}},                     /* Vcom=1.35V */
    {0xC2, 1, 0, {0x01}},
    {0xC3, 1, 0, {0x15}},                     /* GVDD=4.8V */
    {0xC4, 1, 0, {0x20}},                     /* VDV 0v */
    {0xC6, 1, 0, {0x0F}},                     /* 60Hz */
    {0xD0, 2, 0, {0xA4, 0xA1}},
    {0xE0, 13, 0, {0xD0, 0x08, 0x0E, 0x09, 0x09, 0x05, 0x31, 0x33,
                   0x48, 0x17, 0x14, 0x15, 0x31}},
    {0xE1, 13, 0, {0xD0, 0x08, 0x0E, 0x09, 0x09, 0x15, 0x31, 0x33,
                   0x48, 0x17, 0x14, 0x15, 0x31}},
    {0x21, 0, 0, {0x00}},                     /* Display inversion */
    {0x29, 0, 0, {0x00}},                     /* Display on */
};

/* 初始化序列表项：reg = 寄存器命令；n = 数据字节数（0 = 仅命令）；
 * delay_ms = 命令发出后延时（毫秒，走库 delay 模块）；data = 数据字节。 */
/* 每型号初始化的公共前置（厂家各例程一致：RES 复位脉冲 → 开背光） */
static void lcd_power_up(void)
{
    LCD_RES(0);
    delay_ms(100);
    LCD_RES(1);
    delay_ms(100);
    LCD_BLK(1); /* 开背光 */
    delay_ms(100);
}

/* 0.96 寸（ST7735，80×160）——厂家 0.96 例程 lcd_init() 序列原样录入 */
static const lcd_init_row_t lcd_seq_096[] = {
    {0x11, 0, 120, {0x00}},                   /* Sleep out，延时 120ms */
    {0xB1, 3, 0, {0x05, 0x3C, 0x3C}},         /* Normal mode */
    {0xB2, 3, 0, {0x05, 0x3C, 0x3C}},         /* Idle mode */
    {0xB3, 6, 0, {0x05, 0x3C, 0x3C, 0x05, 0x3C, 0x3C}}, /* Partial mode */
    {0xB4, 1, 0, {0x03}},                     /* Dot inversion */
    {0xC0, 3, 0, {0xAB, 0x0B, 0x04}},         /* AVDD GVDD */
    {0xC1, 1, 0, {0xC5}},                     /* VGH VGL（C0） */
    {0xC2, 2, 0, {0x0D, 0x00}},               /* Normal mode */
    {0xC3, 2, 0, {0x8D, 0x6A}},               /* Idle */
    {0xC4, 2, 0, {0x8D, 0xEE}},               /* Partial+Full */
    {0xC5, 1, 0, {0x0F}},                     /* VCOM */
    {0xE0, 16, 0, {0x07, 0x0E, 0x08, 0x07, 0x10, 0x07, 0x02, 0x07,
                   0x09, 0x0F, 0x25, 0x36, 0x00, 0x08, 0x04, 0x10}}, /* +gamma */
    {0xE1, 16, 0, {0x0A, 0x0D, 0x08, 0x07, 0x0F, 0x07, 0x02, 0x07,
                   0x09, 0x0F, 0x25, 0x35, 0x00, 0x09, 0x04, 0x10}}, /* -gamma */
    {0xFC, 1, 0, {0x80}},
    {0x3A, 1, 0, {0x05}},                     /* 16 位色 65K RGB */
    {0x36, 1, 0, {0x00}},                     /* MADCTL——按方向写（占位，
                                               序列游走时经 madctl[dir] 替换） */
    {0x21, 0, 0, {0x00}},                     /* Display inversion */
    {0x29, 0, 0, {0x00}},                     /* Display on */
    {0x2A, 4, 0, {0x00, 0x1A, 0x00, 0x69}},   /* Set Column（26..105） */
    {0x2B, 4, 0, {0x00, 0x01, 0x00, 0xA0}},   /* Set Page（1..160） */
    {0x2C, 0, 0, {0x00}},                     /* 储存器写 */
};

typedef struct {
    uint8_t valid;        /* 1 = 型号已实现（工单 02-05 填齐前其余为 0） */
    uint16_t w[4];        /* 各方向宽度（dir 0-3） */
    uint16_t h[4];        /* 各方向高度 */
    uint8_t madctl[4];    /* MALCTL（0x36）各方向值 */
    int8_t xoff[4];       /* 各方向列偏移（加到 x1/x2 两限） */
    int8_t yoff[4];       /* 各方向行偏移 */
    uint8_t default_dir;  /* 出厂默认方向（LCD_DIR_DEFAULT 非默认值） */
    const lcd_init_row_t *seq;
    uint8_t seq_len;
} lcd_model_info_t;

static const lcd_model_info_t lcd_models[6] = {
    /* LCD_MODEL_096：0.96 寸 ST7735 80×160（厂家 USE_HORIZONTAL=2 横屏） */
    {1, {80, 80, 160, 160}, {160, 160, 80, 80},
     {0x08, 0xC8, 0x78, 0xA8}, {26, 26, 1, 1}, {1, 1, 26, 26}, 2,
     lcd_seq_096, (uint8_t)(sizeof(lcd_seq_096) / sizeof(lcd_seq_096[0]))},
    /* LCD_MODEL_128：1.28 寸 GC9A01 240×240 圆屏（工单 04 补录）
     * LCD_MODEL_147：1.47 寸 ST7789V3 172×320（工单 03 补录）
     * LCD_MODEL_180：1.8 寸 ST7735S 128×160（工单 05 补录） */
    {0, {0, 0, 0, 0}, {0, 0, 0, 0},
     {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, 0, NULL, 0},
    /* LCD_MODEL_130：1.3 寸 ST7789V2 240×240（厂家 USE_HORIZONTAL=0 竖屏；
     * dir1/3 行/列 +80 偏移——厂家 Address_Set 方向表原样） */
    {1, {240, 240, 240, 240}, {240, 240, 240, 240},
     {0x00, 0xC0, 0x70, 0xA0}, {0, 0, 0, 80}, {0, 80, 0, 0}, 0,
     lcd_seq_130, (uint8_t)(sizeof(lcd_seq_130) / sizeof(lcd_seq_130[0]))},
    {0, {0, 0, 0, 0}, {0, 0, 0, 0},
     {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, 0, NULL, 0},
    /* LCD_MODEL_169：1.69 寸 ST7789V2 240×280（厂家 USE_HORIZONTAL=0 竖屏；
     * dir0/1 行 +20、dir2/3 列 +20——厂家 Address_Set 方向表原样） */
    {1, {240, 240, 280, 280}, {280, 280, 240, 240},
     {0x00, 0xC0, 0x70, 0xA0}, {0, 0, 20, 20}, {20, 20, 0, 0}, 0,
     lcd_seq_169, (uint8_t)(sizeof(lcd_seq_169) / sizeof(lcd_seq_169[0]))},
    {0, {0, 0, 0, 0}, {0, 0, 0, 0},
     {0, 0, 0, 0}, {0, 0, 0, 0}, {0, 0, 0, 0}, 0, NULL, 0},
};

/* 当前状态（lcd_init 设置） */
static uint8_t s_model = 0;
static uint8_t s_dir = 0;
static uint16_t s_width = 0;
static uint16_t s_height = 0;

void lcd_address_set(uint16_t x1, uint16_t y1, uint16_t x2, uint16_t y2)
{
    const lcd_model_info_t *info = &lcd_models[s_model];
    int32_t xo = info->xoff[s_dir];
    int32_t yo = info->yoff[s_dir];
    lcd_wr_reg(0x2A); /* 列地址 */
    lcd_wr_data((uint16_t)((int32_t)x1 + xo));
    lcd_wr_data((uint16_t)((int32_t)x2 + xo));
    lcd_wr_reg(0x2B); /* 行地址 */
    lcd_wr_data((uint16_t)((int32_t)y1 + yo));
    lcd_wr_data((uint16_t)((int32_t)y2 + yo));
    lcd_wr_reg(0x2C); /* 储存器写 */
}

void lcd_init(uint8_t model, uint8_t dir)
{
    const lcd_model_info_t *info;
    uint8_t i;
    uint8_t k;
    uint8_t d;

    if (model >= 6) {
        return; /* 型号越界：调用方核对 */
    }
    info = &lcd_models[model];
    if (info->valid == 0 || info->seq == NULL) {
        return; /* 该型号未实现（工单 02-05 补录前占位） */
    }
    d = (dir == LCD_DIR_DEFAULT) ? info->default_dir : (uint8_t)(dir & 0x03u);
    s_model = model;
    s_dir = d;

    lcd_power_up();
    for (i = 0; i < info->seq_len; i++) {
        const lcd_init_row_t *row = &info->seq[i];
        lcd_wr_reg(row->reg);
        if (row->reg == 0x36u) {
            /* MADCTL：厂家序列内该行按方向写（本实现方向运行时参数） */
            lcd_wr_data8(info->madctl[d]);
            continue;
        }
        for (k = 0; k < row->n; k++) {
            lcd_wr_data8(row->data[k]);
        }
        if (row->delay_ms) {
            delay_ms(row->delay_ms);
        }
    }

    s_width = info->w[d];
    s_height = info->h[d];
}

uint16_t lcd_get_width(void)
{
    return s_width;
}

uint16_t lcd_get_height(void)
{
    return s_height;
}
