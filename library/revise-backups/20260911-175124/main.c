/* ============================================================
 *  main.c —— 2026 电赛 C 题：基于无线通信的数字钥匙实验系统
 *  本固件目标：智能门锁端（接收/判决端）
 *
 *  数据流：
 *    UWB 基站 --USART1--> uwb_uart 解析 --> filter 滑动平均 --> 区域判决
 *    数字钥匙 --USART3--> zigbee_link 收帧 --> 身份 ID
 *    判决结果 --> OLED 显示 / 状态灯 / 声光提示 / 继电器（模拟开锁闭锁）
 *
 *  ⚠️ 若本工程烧录的是“数字钥匙”端，请改为：
 *        zigbee_uart_key_init();
 *        循环内每 100ms 调 zigbee_uart_key_send_id(id);
 *     （zigbee_uart_key 与 zigbee_link 共用 ZIGBEE_UART，二者互斥，
 *       不可在同一固件中同时初始化）
 * ============================================================ */

#include "headfile.h"          /* 母版：delay/gpio/led/uart/nvic/oled/systick */
#include "config.h"            /* 波特率、刷新周期、滤波窗口、钳位参数 */
#include "filter.h"            /* 滑动平均滤波器 */
#include "uwb_uart.h"          /* UWB 基站定位帧 0x2001 (USART1) */
#include "zigbee_link.h"       /* Zigbee 透传链路，接收钥匙 ID (USART3) */
#include "key_stm32.h"         /* 按键 */
#include "beep_stm32.h"        /* 蜂鸣器 */
#include "led_beep_stm32.h"    /* 声光提示组合 */
#include "relay_stm32.h"       /* 继电器：模拟开锁 / 闭锁 */

/* ---- 区域门限 ------------------------------------------------
 * 题面：开锁区 <=1m；迎宾区 1~2m；感应区 2~3m；只判正前方 ±45°。
 * TODO: 现场标定——径向距离零点为门锁圆柱体边界，
 *       若实测存在固定偏差，在此处加距离补偿宏。
 * TODO: 可加入回差（例如 5cm）抑制边界来回跳变。
 */
#define LOCK_ZONE_CM      100
#define WELCOME_ZONE_CM   200
#define AZ_GATE_DEG        45

/* 滤波器缓冲与实例放文件作用域，避免占用栈 */
static int32_t       s_dist_buf[FILTER_WIN_SIZE];
static int32_t       s_az_buf[FILTER_AZ_WIN_SIZE];
static SlidingFilter s_dist_filter;
static SlidingFilter s_az_filter;

int main(void)
{
    /* ------------------- 局部变量 ------------------- */
    uint32_t oled_tick;                       /* 上次 OLED 刷新节拍(ms) */
    uint32_t key_id;                          /* 最近收到的钥匙 ID，0xFFFFFFFF=未收到 */
    uint8_t  key_last;                        /* 上一轮按键状态(边沿检测用) */
    uint8_t  stage;                           /* 本轮区域: 0=感应区 1=迎宾区 2=开锁区 */
    uint8_t  stage_last;                      /* 上一轮区域(用于判“进入/离开”事件) */
    uint8_t  locked;                          /* 1=闭锁 0=开锁 */
    uint8_t  rxbuf[ZIGBEE_LINK_MAX_PAYLOAD];  /* Zigbee 收帧缓冲 */
    uint8_t  rxlen;                           /* Zigbee 收帧长度，0=无新帧 */
    int32_t  dist_cm;                         /* 滤波后径向距离(cm) */
    int32_t  az_deg;                          /* 滤波后方位角(度) */

    /* 初值：无目标（远距离、正前方），保证首轮判决不会误开锁 */
    dist_cm    = 9999;
    az_deg     = 0;
    key_id     = 0xFFFFFFFFu;
    key_last   = 0;
    stage      = 0;
    stage_last = 0;
    locked     = 1;

    /* ================= 1. 系统节拍 ================= */
    systick_init();                 /* SysTick 1ms，g_systick 开始递增 */

    /* ================= 2. 执行部件 / 人机 ================= */
    led_init(LED_RED);              /* 红 = 闭锁指示 */
    led_init(LED_YELLOW);           /* 黄 = 迎宾区提示 */
    led_init(LED_GREEN);            /* 绿 = 开锁指示 */

    beep_init();                    /* 有源蜂鸣器 */
    led_beep_init();                /* 声光组合（内部会再次初始化 led/beep，重复无害） */

    relay_init();                   /* 上电默认断开 = 闭锁 */
    led_on(LED_RED);
    led_off(LED_GREEN);
    led_off(LED_YELLOW);

    key_init();                     /* 按键：手动闭锁（应急） */

    /* ================= 3. 显示 ================= */
    OLED_Init();                    /* I2C 路径（ml_oled）。
                                     * 若使用 SPI 屏，改为：
                                     *   oled_set_res(OLED_RES_128X64);
                                     *   oled_spi_init();      // 或 oled_init_sh1106();
                                     *   刷新改用 oled_spi_refresh();
                                     * （见 oled_extra_stm32.h） */
    OLED_Clear();
    oled_show_text(0, 0, "Digital Lock");

    /* ================= 4. 无线链路 ================= */
    uwb_uart_init();                /* USART1：UWB 基站 0x2001 帧 */
    zigbee_link_init();             /* USART3：接收数字钥匙身份 ID
                                     * （若是钥匙端：改为 zigbee_uart_key_init()） */

    /* ================= 5. 滤波器 ================= */
    filter_init(&s_dist_filter, s_dist_buf, FILTER_WIN_SIZE);
    filter_init(&s_az_filter,   s_az_buf,   FILTER_AZ_WIN_SIZE);

    oled_tick = g_systick;

    while (1)
    {
        /* ---------- 5.1 接收数字钥匙身份 ID ---------- */
        rxlen = zigbee_link_recv(rxbuf, ZIGBEE_LINK_MAX_PAYLOAD);
        if (rxlen > 0)
        {
            /* TODO: 负载格式需与数字钥匙端约定；暂定 rxbuf[0] 低 4 位 = 4bit ID */
            key_id = (uint32_t)(rxbuf[0] & 0x0Fu);
        }

        /* ---------- 5.2 UWB 数据滤波 ----------
         * 说明：uwb_uart 内部已有 g_uwb_filtered；此处再用 filter 模块做一次
         *       滑动平均压边界抖动。若嫌滞后，可直接改用
         *       g_uwb_filtered.distance / g_uwb_filtered.azimuth。
         * TODO: 增量钳位（DIST_MAX_STEP / AZ_MAX_STEP）如需在本层做，
         *       在此处加“与上帧差值超限则丢弃”的判断。 */
        if (g_uwb_updated)
        {
            g_uwb_updated = 0;
            dist_cm = filter_add(&s_dist_filter, (int32_t)g_uwb_raw.distance);
            az_deg  = filter_add(&s_az_filter,   (int32_t)g_uwb_raw.azimuth);
        }

        /* ---------- 5.3 区域判决（仅正前方 ±45° 内有效） ---------- */
        if (az_deg > AZ_GATE_DEG || az_deg < -AZ_GATE_DEG)
        {
            stage = 0;                          /* 方位超限：按感应区处理，不触发动作 */
        }
        else if (dist_cm <= LOCK_ZONE_CM)
        {
            stage = 2;                          /* 开锁区 */
        }
        else if (dist_cm <= WELCOME_ZONE_CM)
        {
            stage = 1;                          /* 迎宾区 */
        }
        else
        {
            stage = 0;                          /* 感应区 */
            /* TODO: 若需单独显示“是否进入感应区(<=3m)”，在此补 3m 门限判断 */
            /* TODO: ID 验证——读取 4 位拨码开关(DIP_*)设置的目标 ID 与 key_id
             *       比对，未通过验证的钥匙不参与开锁判决 */
        }

        /* ---------- 5.4 开锁 / 闭锁动作 ---------- */
        if (stage == 2 && locked)
        {
            relay_set(1);                       /* 吸合 = 开锁 */
            LED_GREEN_ON();
            LED_RED_OFF();
            locked = 0;
        }
        else if (stage != 2 && !locked)
        {
            relay_set(0);                       /* 断开 = 闭锁 */
            LED_RED_ON();
            LED_GREEN_OFF();
            locked = 1;
        }

        /* ---------- 5.5 迎宾区声光提示（进入 / 离开各触发一次） ---------- */
        if (stage == 1 && stage_last != 1)
        {
            LED_YELLOW_ON();
            led_beep_alarm(2, 100, 100);        /* 阻塞约 400ms
                                                 * TODO: 若影响 UWB 帧处理，改为非阻塞
                                                 *       （beep_on/beep_off + 节拍计时） */
        }
        else if (stage != 1 && stage_last == 1)
        {
            LED_YELLOW_OFF();                   /* 离开迎宾区：关闭声光提示 */
        }

        /* ---------- 5.6 按键：手动闭锁（应急） ----------
         * TODO: 可改为“手动修改身份 ID”或“一键自检”，视现场需要；
         *       注意手动置态会在下一轮被 5.4 的自动判决覆盖。 */
        {
            uint8_t key_now = get_key_state(KEY_START);
            if (key_now && !key_last)
            {
                relay_set(0);
                LED_RED_ON();
                LED_GREEN_OFF();
                locked = 1;
            }
            key_last = key_now;
        }

        /* ---------- 5.7 OLED 显示（每 OLED_UPDATE_MS 刷新） ---------- */
        if ((uint32_t)(g_systick - oled_tick) >= OLED_UPDATE_MS)
        {
            oled_tick = g_systick;

            oled_show_text(0, 0, "ID:");
            if (key_id <= 0x0Fu)
                OLED_ShowNum(0, 3, key_id, 1);          /* 4bit 身份 ID */
            else
                oled_show_text(0, 3, "--");

            oled_show_text(1, 0, "D=");
            OLED_ShowSignedNum(1, 2, dist_cm, 4);
            oled_show_text(1, 6, "cm");

            oled_show_text(2, 0, "A=");
            OLED_ShowSignedNum(2, 2, az_deg, 3);
            oled_show_text(2, 5, "deg");

            if (stage == 2)
                oled_show_text(3, 0, "ZONE:LOCK   ");
            else if (stage == 1)
                oled_show_text(3, 0, "ZONE:WELCOME");
            else
                oled_show_text(3, 0, "ZONE:SENSE  ");

            oled_show_text(3, 12, locked ? "LOCK" : "OPEN");

            oled_refresh();
        }

        stage_last = stage;

        /* ============================================================
         *  预留编写区（TODO）：
         *   - 抗多径 / 异常值剔除：帧率异常(uwb_get_frame_rate)或跳变过大时
         *     调 uwb_filter_reset() 重新起滤；
         *   - 事件提示：EVENT_SHOW_MS 内把“到达迎宾区/开锁区、离开开锁区/
         *     迎宾区”等判决结果以文字形式覆盖显示；
         *   - 身份 ID 变更（拨码开关变化）时调 uwb_filter_reset() 并清 key_id；
         *   - 扩展项（评分表第 7 项）：历史记录、超时自动闭锁等。
         * ============================================================ */
    }
}
