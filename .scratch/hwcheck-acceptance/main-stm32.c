/**
 * @file main.c
 * @brief 硬件检测程序 —— 确定性渲染，非 AI 生成
 *
 * 这一趟用来确认「板子活着 + 烧录链路通」：
 *   1. 板载 LED 按固定周期闪烁（心跳，肉眼可见）；
 *   2. 上电先报一句「板子活着」，随后逐件跑检测小节。
 *
 * 上电跑完一遍后进**串口命令台**（复测不用重烧，边动线边看现象）：
 *   - m  复测 ml_mpu6050：MPU6050 通信：读 WHO_AM_I 比对 0x68，再回显六轴原始值
 *   - ?  显示全部命令（含下面那几条既有命令）
 * 既有 r / y / g / o / b<N>（点灯 / 蜂鸣）**语义不变**——它们仍由库内 debug_cmd_poll() 执行。
 *
 * 逐件检测小节（按库内配方渲染，非 AI 生成）：
 *   - [专精] ml_mpu6050（配方：初始化、通信探头带判定、6 项读数、控制台命令 'm'）
 *
 * 检测没过是正常结果：要么接线不对，要么库内驱动有问题。
 */
#include "headfile.h"
#include "debug_uart.h"
#include "led_instances.h"  /* 通道宏 LED_RED */
#include "ml_mpu6050.h"
#include "ml_i2c.h"

/* 心跳周期（毫秒）：改这里改闪灯快慢 */
#define HWCHECK_HEARTBEAT_MS 200

static char hwcheck_line[128];
static int hwcheck_line_len;

static void hwcheck_write_serial(const char *s)
{
    /* 每行补 CRLF（行尾策略，工单 06）：串口助手上裸 LF 不回列，
     * 下一行会接着上一行的尾巴写。库内既有消息也是 \r\n 结尾。 */
    DEBUG_PRINTF("%s\r\n", s);
}

static void hwcheck_write_oled(const char *s)
{
    /* 本屏 16×8 字符网格、可见 4 行：整行从头写，保证每次都看得见。
     * 超过 16 列的整行会被屏自己截掉尾部（屏就这么宽）——检测页那几
     * 行文案都控制在 16 列内，超了也只是尾巴看不见，不影响判定。 */
    oled_show_text(0, 0, s);
    oled_refresh();
}

/** 把攒好的一行送到所有在场的输出通道。 */
static void hwcheck_write_line(const char *line)
{
    hwcheck_write_serial(line);
    hwcheck_write_oled(line);
}


/** 自检结果出口：一段文本攒进当前行；遇到换行就整行送出。 */
static void hwcheck_report(const char *text)
{
    int i = 0;
    while (text[i] != 0)
    {
        char ch = text[i++];
        if (ch == '\n')
        {
            hwcheck_line[hwcheck_line_len] = 0;
            hwcheck_write_line(hwcheck_line);
            hwcheck_line_len = 0;
            continue;
        }
        if (hwcheck_line_len < (int)sizeof(hwcheck_line) - 1)
        {
            hwcheck_line[hwcheck_line_len++] = ch;
        }
    }
}

/** 换行（把当前攒的这一行送出去）。 */
static void hwcheck_newline(void)
{
    hwcheck_report("\n");
}

/** 把一个整数写成十进制（读数回显用；不判阈值——数据合理性归人看）。 */
static void hwcheck_report_int(int value)
{
    char buf[12];
    int i = 0;
    int neg = (value < 0);
    unsigned int v = neg ? (unsigned int)(-value) : (unsigned int)value;
    if (v == 0)
    {
        buf[i++] = '0';
    }
    while (v > 0)
    {
        buf[i++] = (char)('0' + (int)(v % 10u));
        v /= 10u;
    }
    if (neg)
    {
        hwcheck_report("-");
    }
    while (i > 0)
    {
        char one[2];
        one[0] = buf[--i];
        one[1] = 0;
        hwcheck_report(one);
    }
}

/* ---- 逐件小节运行时（判定在板上算，工单 module-hwcheck/04）---- */
static int hwcheck_summary_ok;
static int hwcheck_summary_fail;

/** 小节头：空一行 + 标题（一串检测结果之间的分节）。 */
static void hwcheck_section(const char *title)
{
    hwcheck_report("");
    hwcheck_report(title);
    hwcheck_newline();
}

/** 细节行（排查线索 / 平台说明）：行首缩进，和判定行区分开。 */
static void hwcheck_detail(const char *text)
{
    hwcheck_report("    \302\267 ");
    hwcheck_report(text);
    hwcheck_newline();
}

/** 记一次判定（1 = 通过，0 = 失败）；失败顺带把排查话术打出来。 */
static void hwcheck_verdict(int ok, const char *trouble)
{
    if (ok)
    {
        hwcheck_summary_ok++;
    }
    else
    {
        hwcheck_summary_fail++;
        hwcheck_detail(trouble);
    }
}

/** 结尾汇总：三档分开数（没探头的绝不混进「通过」）。 */
static void hwcheck_summary(void)
{
    hwcheck_report("");
    hwcheck_report("==== \346\243\200\346\265\213\346\261\207\346\200\273 ====");
    hwcheck_newline();
    if (hwcheck_summary_ok > 0)
    {
        hwcheck_report("  \351\200\232\350\277\207\357\274\232");
        hwcheck_report_int(hwcheck_summary_ok);
        hwcheck_report(" \351\241\271");
        hwcheck_newline();
    }
    if (hwcheck_summary_fail > 0)
    {
        hwcheck_report("  \345\244\261\350\264\245\357\274\232");
        hwcheck_report_int(hwcheck_summary_fail);
        hwcheck_report(" \351\241\271\357\274\210\346\216\222\346\237\245\347\272\277\347\264\242\350\247\201\344\270\212\351\235\242\347\232\204 \302\267 \350\241\214\357\274\211");
        hwcheck_newline();
    }
    if (hwcheck_summary_ok == 0 && hwcheck_summary_fail == 0)
    {
        hwcheck_report("  \350\277\231\344\270\200\350\266\237\346\262\241\346\234\211\346\235\277\344\270\212\345\210\244\345\256\232\351\241\271\357\274\232\345\217\252\347\241\256\350\256\244\344\272\206\346\235\277\345\255\220\344\270\216\347\203\247\345\275\225\351\223\276\350\267\257\346\230\257\346\264\273\347\232\204");
        hwcheck_newline();
    }
}

/* ---- 逐件检测小节（按库内配方渲染；未专精件走通用降级）---- */
static void hwcheck_check_ml_mpu6050(void)
{
    /* ---- [专精] ml_mpu6050：按库内配方测这一件 ---- */
    /* 平台说明：**本平台（stm32）没有姿态解算**：这里的驱动只有原始六轴（ax / ay / az / gx / gy / gz），没有 pitch / roll / yaw——要角度请换到 mspm0 侧（官方 DMP 姿态解算），或改用串口姿态模块（jy61p / imu_uart）。**所以这一版在本平台不给你角度，别把「没有角度」读成「我接错了线」。** */
    /* 平台说明：前置调用：MPU6050_Init() **不初始化 I2C 总线**（它只写寄存器），检测程序已先调母版 I2C_Init() 初始化软 I2C（默认 SCL = PA11 / SDA = PA12，见工程 README 的引脚接线表）。总线没起来时读回来的是固定值（0x00 / 0xFF），不是「器件坏了」。 */
    /* 平台说明：本件自己带探头（不看驱动的初始化返回值）：读 WHO_AM_I（寄存器 0x75）比对 0x68。库里这份 stm32 驱动**不做身份校验**（通信失败也照样往下写寄存器），所以板上判 FAIL 就是通信真的没通——先查供电 / 上拉（SDA/SCL 要有 4.7k 上拉）/ 地址（AD0 接 GND = 0x68）/ 线序（SCL、SDA 有没有接反）。 */
    /* 平台说明：读数怎么算合理：加速度计 ±2g 量程 = 16384 LSB/g，板子放平静止时 Z 轴 ≈ ±16384、X/Y ≈ 0；陀螺仪 ±2000dps 量程 = 16.4 LSB/(°/s)，静止时三轴都 ≈ 0。数值一直在跳或差得很远，先确认线长 / 供电，再怀疑器件。 */
    /* 专精件：这一节真的会驱动它 / 读它（库内配方给的动作）。未专精件走通用降级，出的是另一套小节（工单 07，不带 [专精] 标记）。 */
    hwcheck_section("[\344\270\223\347\262\276] ml_mpu6050");
    int r;
    I2C_Init();
    MPU6050_Init();
    MPU6050_GetData();
    hwcheck_report("  \345\210\235\345\247\213\345\214\226\357\274\232");
    hwcheck_report("\345\267\262\350\260\203\347\224\250\357\274\210\346\234\254\344\273\266\344\270\215\345\210\244\350\277\224\345\233\236\345\200\274\357\274\211");
    hwcheck_newline();
    r = MPU6050_Read(WHO_AM_I);
    hwcheck_report("  \351\200\232\344\277\241\346\216\242\345\244\264\357\274\232");
    hwcheck_report((r == 0x68) ? "OK" : "FAIL");
    if (r != 0x68)
    {
        hwcheck_detail("\351\200\232\344\277\241\345\244\261\350\264\245\357\274\232\345\205\210\346\237\245\344\276\233\347\224\265 / \344\270\212\346\213\211 / \345\234\260\345\235\200 / \347\272\277\345\272\217\357\274\214\345\206\215\346\237\245\351\251\261\345\212\250");
        hwcheck_verdict(0, "ml_mpu6050\357\274\232\351\200\232\344\277\241\345\244\261\350\264\245\357\274\210\345\205\210\346\237\245\344\276\233\347\224\265 / \344\270\212\346\213\211 / \345\234\260\345\235\200 / \347\272\277\345\272\217\357\274\211");
        return;   /* 不通就不再打一堆无意义读数 */
    }
    hwcheck_verdict(1, "ml_mpu6050\357\274\232\351\200\232\344\277\241\346\255\243\345\270\270");
    hwcheck_report("  ax = ");
    hwcheck_report_int(ax);
    hwcheck_report(" \345\212\240\351\200\237\345\272\246 X\357\274\210LSB\357\274\214\302\2612g \351\207\217\347\250\213\357\274\23216384 LSB/g\357\274\211");
    hwcheck_newline();
    hwcheck_report("  ay = ");
    hwcheck_report_int(ay);
    hwcheck_report(" \345\212\240\351\200\237\345\272\246 Y\357\274\210LSB\357\274\211");
    hwcheck_newline();
    hwcheck_report("  az = ");
    hwcheck_report_int(az);
    hwcheck_report(" \345\212\240\351\200\237\345\272\246 Z\357\274\210LSB\357\274\214\346\224\276\345\271\263\346\227\266 \342\211\210 +16384\357\274\211");
    hwcheck_newline();
    hwcheck_report("  gx = ");
    hwcheck_report_int(gx);
    hwcheck_report(" \350\247\222\351\200\237\345\272\246 X\357\274\210LSB\357\274\214\302\2612000dps \351\207\217\347\250\213\357\274\23216.4 LSB/(\302\260/s)\357\274\211");
    hwcheck_newline();
    hwcheck_report("  gy = ");
    hwcheck_report_int(gy);
    hwcheck_report(" \350\247\222\351\200\237\345\272\246 Y\357\274\210LSB\357\274\211");
    hwcheck_newline();
    hwcheck_report("  gz = ");
    hwcheck_report_int(gz);
    hwcheck_report(" \350\247\222\351\200\237\345\272\246 Z\357\274\210LSB\357\274\214\351\235\231\346\255\242\346\227\266\344\270\211\350\275\264\351\203\275 \342\211\210 0\357\274\211");
    hwcheck_newline();

}

/* ---- 串口命令台（配方驱动的复测；工单 module-hwcheck/06）----
 * 既有 r/y/g/o/b 由库内 debug_cmd_poll() 原样执行：这里只 peek 一眼收到的
 * 字符，是配方命令 / 帮助才处理并 consume，其余一律不碰（既有语义一个字节
 * 不动）。复测不用重烧——边动线边看现象。 */
static void hwcheck_console_help(void)
{
    hwcheck_report("[\345\270\256\345\212\251] \345\217\257\347\224\250\345\221\275\344\273\244\357\274\210\345\215\225\345\255\227\347\254\246 + \345\233\236\350\275\246\357\274\211\357\274\232");
    hwcheck_newline();
    hwcheck_report("  \346\227\242\346\234\211\357\274\210\345\272\223\345\206\205 debug_cmd_poll \345\216\237\346\240\267\346\211\247\350\241\214\357\274\211\357\274\232");
    hwcheck_newline();
    hwcheck_report("    r \347\272\242\347\201\257\344\272\256\357\274\214\345\205\266\344\275\231\347\201\255 / y \351\273\204\347\201\257\344\272\256\357\274\214\345\205\266\344\275\231\347\201\255");
    hwcheck_newline();
    hwcheck_report("    g \347\273\277\347\201\257\344\272\256\357\274\214\345\205\266\344\275\231\347\201\255 / o \345\205\250\347\201\255");
    hwcheck_newline();
    hwcheck_report("    b \350\234\202\351\270\243\345\231\250\345\223\215 N \346\257\253\347\247\222\357\274\210\345\246\202 b50\357\274\211");
    hwcheck_newline();
    hwcheck_report("  m  ml_mpu6050\357\274\232MPU6050 \351\200\232\344\277\241\357\274\232\350\257\273 WHO_AM_I \346\257\224\345\257\271 0x68\357\274\214\345\206\215\345\233\236\346\230\276\345\205\255\350\275\264\345\216\237\345\247\213\345\200\274");
    hwcheck_newline();
    hwcheck_report("  ?  \346\230\276\347\244\272\350\277\231\344\273\275\345\270\256\345\212\251");
    hwcheck_newline();
}

/** 主循环轮询：认领配方命令 / 帮助，其余留给库内 debug_cmd_poll()。 */
static void hwcheck_console_poll(void)
{
    const char *line = debug_cmd_peek();
    char cmd;

    if (line[0] == '\0')
    {
        return;   /* 没收到完整命令：什么都不做（心跳照跑） */
    }
    cmd = line[0];   /* 命令粒度 = 首字符，与库内既有命令同一口径 */
    switch (cmd)
    {
    case 'm':
    case 'M':
        /* ml_mpu6050：MPU6050 通信：读 WHO_AM_I 比对 0x68，再回显六轴原始值 */
        hwcheck_section("[\345\244\215\346\265\213] ml_mpu6050");
        hwcheck_detail("\346\265\213\347\232\204\346\230\257\357\274\232MPU6050 \351\200\232\344\277\241\357\274\232\350\257\273 WHO_AM_I \346\257\224\345\257\271 0x68\357\274\214\345\206\215\345\233\236\346\230\276\345\205\255\350\275\264\345\216\237\345\247\213\345\200\274");
        hwcheck_check_ml_mpu6050();
        break;
    case '?':
        hwcheck_console_help();
        break;
    /* 既有命令：原样留给库内 debug_cmd_poll()——这里一个字都不动它 */
    case 'r':
    case 'R':
    case 'y':
    case 'Y':
    case 'g':
    case 'G':
    case 'o':
    case 'O':
    case 'b':
    case 'B':
        return;
    default:
        hwcheck_report("[\346\234\252\347\237\245\345\221\275\344\273\244] ");
        hwcheck_report(line);   /* 原样回显学生敲的那一行，别让人猜 */
        hwcheck_newline();
        hwcheck_console_help();
        break;
    }
    /* 只有我们处理过的才消费；既有命令在上面已经 return（留给库内那份） */
    debug_cmd_consume();
}

int main(void)
{
    SystemInit();  /* 时钟初始化（启动文件已调用，这里显式确保就绪） */
    debug_uart_init();
    OLED_Init();
    OLED_Clear();
    led_init(LED_RED);

    hwcheck_report("\344\270\212\347\224\265\357\274\232\346\235\277\345\255\220\346\264\273\347\235\200\357\274\214\346\243\200\346\265\213\347\250\213\345\272\217\345\274\200\345\247\213\350\267\221");
    hwcheck_newline();

    /* ---- 上电自动跑一遍逐件检测 ---- */
    hwcheck_check_ml_mpu6050();

    /* ---- 汇总：这一趟到底测了什么 ---- */
    hwcheck_detail("ml_mpu6050\357\274\232\351\200\232\344\277\241\345\244\261\350\264\245\357\274\210\345\205\210\346\237\245\344\276\233\347\224\265 / \344\270\212\346\213\211 / \345\234\260\345\235\200 / \347\272\277\345\272\217\357\274\211");
    hwcheck_summary();

    while (1)
    {
        hwcheck_console_poll();  /* 配方命令：复测不用重烧 */
        debug_cmd_poll();  /* 串口命令通道：复测不用重烧 */
        led_toggle(LED_RED);
        delay_ms(HWCHECK_HEARTBEAT_MS);
    }
}
