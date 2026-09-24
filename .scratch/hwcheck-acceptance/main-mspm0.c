/**
 * @file main.c
 * @brief 硬件检测程序 —— 确定性渲染，非 AI 生成
 *
 * 这一趟用来确认「板子活着 + 烧录链路通」：
 *   1. 板载 LED 按固定周期闪烁（心跳，肉眼可见）；
 *   2. 上电先报一句「板子活着」，随后逐件跑检测小节。
 *
 * 上电跑完一遍后进**串口命令台**（复测不用重烧，边动线边看现象）：
 *   - m  复测 ml_mpu6050：MPU6050 姿态：重跑 DMP 初始化与一帧角度读取
 *   - ?  显示全部命令（含下面那几条既有命令）
 * 既有 r / y / g / o / b<N>（点灯 / 蜂鸣）**语义不变**——它们仍由库内 debug_cmd_poll() 执行。
 *
 * 逐件检测小节（按库内配方渲染，非 AI 生成）：
 *   - [专精] ml_mpu6050（配方：初始化带判定、通信探头带判定、6 项读数、控制台命令 'm'）
 *
 * ⚠ 本平台已知限制：SysConfig 外设初始化（SYSCFG_DL_init）还没有被
 *   生成链注入出来，所以下面那行初始化是**注释状态**。
 *   上板前请先取消注释再重新编译，否则串口 / LED 都不会初始化
 *   （灯不闪 ≠ 板子坏）。
 *
 * 另外本平台母版**没有 SysTick 服务函数**（stm32 侧由 ml_systick.c 提供）
 *   ——文件末尾那个空的 SysTick_Handler 就是补这一格的：自己打开 SysTick
 *   中断的驱动（如 ml_mpu6050 的 DMP 端口）没有它会掉进启动文件的
 *   Default_Handler 死循环（现象是灯都不闪）。别删。
 *
 * 检测没过是正常结果：要么接线不对，要么库内驱动有问题。
 */
#include "ti_msp_dl_config.h"
#include "debug_uart_mspm0.h"
#include "oled.h"  /* OLED 屏 */
#include "delay.h"  /* 心跳节拍 */
#include "led.h"  /* 通道宏 LED_RED */
#include "mpu_port.h"

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
    /* 平台说明：**本平台（mspm0）走官方 DMP 姿态解算**：直接出 pitch / roll / yaw 三维角度（100Hz）——这是与 stm32 侧最大的不同（那边只有原始六轴）。 */
    /* 平台说明：**本平台没有浮点显示接口**，所以每个角度拆成两次回显：「整数部分」和「小数第一位」，读数时要**把相邻两行拼起来看**（例如 pitch 整数 = 12、pitch 小数 = 3 → 12.3°）。负数按截断显示（-12 与 -3 就是 -12.3°）。 */
    /* 平台说明：两级自证（都不信「初始化没报错就是好的」）：① DMP_Init() 返回 0——官方库内部会读设备 ID 做校验；② 探头 DMP_Read_Data() 返回 0——真的从 FIFO 读回一帧，顺带把角度搬进变量。探头判 FAIL 就不再打读数（读数只会是没意义的 0）。 */
    /* 平台说明：地猛星 MPU6050 默认 I2C0 = SDA PA0 / SCL PA1，**与板载 LED 同脚**（通信期间 LED 微闪是正常现象）；SysConfig 里必须有 I2C_0 实例（母版已含），否则 mpu_port.c 编不过（报 I2C_0_INST 缺失）。 */
    /* 平台说明：读数怎么算合理：板子**静止放平**时 pitch / roll ≈ 0°（真实值可能差个一两度，属正常）；**yaw 会缓慢漂移**——这套 DMP 只用陀螺仪与加速度计、没有磁力计做绝对朝向，漂是物理决定的，不是坏了。数值一直在跳或差得离谱，先确认线长 / 供电，再怀疑器件。 */
    /* 平台说明：DMP 端口（mpu_port.c 的 DMP_Init）自己会打开 SysTick 中断，而 mspm0 母版**没有** SysTick 服务函数（stm32 侧由母版 ml_systick.c 提供）——检测程序已在 main.c 里补了一个空的 SysTick_Handler：**别删**，删了会掉进启动文件的 Default_Handler 死循环，表现是灯都不闪。 */
    /* 专精件：这一节真的会驱动它 / 读它（库内配方给的动作）。未专精件走通用降级，出的是另一套小节（工单 07，不带 [专精] 标记）。 */
    hwcheck_section("[\344\270\223\347\262\276] ml_mpu6050");
    int r;
    float pitch = 0;
    float roll = 0;
    float yaw = 0;
    r = DMP_Init();
    hwcheck_report("  \345\210\235\345\247\213\345\214\226\357\274\232");
    hwcheck_report((r == 0) ? "OK" : "FAIL");
    if (r != 0) { hwcheck_detail("\345\210\235\345\247\213\345\214\226\346\262\241\346\234\211\346\214\211\346\216\245\345\217\243\347\272\246\345\256\232\350\277\224\345\233\236\346\234\237\346\234\233\345\200\274\342\200\224\342\200\224\345\205\210\346\237\245\346\216\245\347\272\277\344\270\216\344\276\233\347\224\265\357\274\214\345\206\215\346\237\245\351\251\261\345\212\250"); }
    hwcheck_verdict((r == 0), "ml_mpu6050\357\274\232\345\210\235\345\247\213\345\214\226\346\262\241\346\234\211\346\214\211\346\216\245\345\217\243\347\272\246\345\256\232\350\277\224\345\233\236\346\234\237\346\234\233\345\200\274");
    r = DMP_Read_Data(&pitch, &roll, &yaw);
    hwcheck_report("  \351\200\232\344\277\241\346\216\242\345\244\264\357\274\232");
    hwcheck_report((r == 0) ? "OK" : "FAIL");
    if (r != 0)
    {
        hwcheck_detail("\351\200\232\344\277\241\345\244\261\350\264\245\357\274\232\345\205\210\346\237\245\344\276\233\347\224\265 / \344\270\212\346\213\211 / \345\234\260\345\235\200 / \347\272\277\345\272\217\357\274\214\345\206\215\346\237\245\351\251\261\345\212\250");
        hwcheck_verdict(0, "ml_mpu6050\357\274\232\351\200\232\344\277\241\345\244\261\350\264\245\357\274\210\345\205\210\346\237\245\344\276\233\347\224\265 / \344\270\212\346\213\211 / \345\234\260\345\235\200 / \347\272\277\345\272\217\357\274\211");
        return;   /* 不通就不再打一堆无意义读数 */
    }
    hwcheck_verdict(1, "ml_mpu6050\357\274\232\351\200\232\344\277\241\346\255\243\345\270\270");
    hwcheck_report("  (int)pitch = ");
    hwcheck_report_int((int)pitch);
    hwcheck_report(" \345\272\246\357\274\210pitch \346\225\264\346\225\260\351\203\250\345\210\206\357\274\211");
    hwcheck_newline();
    hwcheck_report("  (int)((pitch - (int)pitch) * 10) = ");
    hwcheck_report_int((int)((pitch - (int)pitch) * 10));
    hwcheck_report(" \357\274\210pitch \345\260\217\346\225\260\347\254\254\344\270\200\344\275\215\357\274\211");
    hwcheck_newline();
    hwcheck_report("  (int)roll = ");
    hwcheck_report_int((int)roll);
    hwcheck_report(" \345\272\246\357\274\210roll \346\225\264\346\225\260\351\203\250\345\210\206\357\274\211");
    hwcheck_newline();
    hwcheck_report("  (int)((roll - (int)roll) * 10) = ");
    hwcheck_report_int((int)((roll - (int)roll) * 10));
    hwcheck_report(" \357\274\210roll \345\260\217\346\225\260\347\254\254\344\270\200\344\275\215\357\274\211");
    hwcheck_newline();
    hwcheck_report("  (int)yaw = ");
    hwcheck_report_int((int)yaw);
    hwcheck_report(" \345\272\246\357\274\210yaw \346\225\264\346\225\260\351\203\250\345\210\206\357\274\211");
    hwcheck_newline();
    hwcheck_report("  (int)((yaw - (int)yaw) * 10) = ");
    hwcheck_report_int((int)((yaw - (int)yaw) * 10));
    hwcheck_report(" \357\274\210yaw \345\260\217\346\225\260\347\254\254\344\270\200\344\275\215\357\274\211");
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
    hwcheck_report("  m  ml_mpu6050\357\274\232MPU6050 \345\247\277\346\200\201\357\274\232\351\207\215\350\267\221 DMP \345\210\235\345\247\213\345\214\226\344\270\216\344\270\200\345\270\247\350\247\222\345\272\246\350\257\273\345\217\226");
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
        /* ml_mpu6050：MPU6050 姿态：重跑 DMP 初始化与一帧角度读取 */
        hwcheck_section("[\345\244\215\346\265\213] ml_mpu6050");
        hwcheck_detail("\346\265\213\347\232\204\346\230\257\357\274\232MPU6050 \345\247\277\346\200\201\357\274\232\351\207\215\350\267\221 DMP \345\210\235\345\247\213\345\214\226\344\270\216\344\270\200\345\270\247\350\247\222\345\272\246\350\257\273\345\217\226");
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

/* mspm0：SysTick 中断服务函数（母版没有提供，见文件头的平台说明——
 * 缺了它，自己打开 SysTick 中断的驱动会掉进启动文件的死循环）。 */
void SysTick_Handler(void)
{
    /* 空实现就够：检测程序不用 SysTick 记账，只是别落进 Default_Handler。 */
}

int main(void)
{
    /* 本平台的 SysConfig 外设初始化：暂时注释——生成链还没有把这一行
     * 注入出来（见文件头说明）。上板前先取消注释，否则串口 / LED 都不会
     * 初始化（灯不闪不是板子坏）。 */
    /* SYSCFG_DL_init(); */
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
