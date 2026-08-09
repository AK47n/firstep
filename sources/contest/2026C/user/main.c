#include "headfile.h"
#include "config.h"
#include "filter.h"
#include "uwb_uart.h"
#include "zone.h"
#include "lock_control.h"
#include "debug_uart.h"
#include "zigbee_uart.h"

// ============================================================
//  C题：基于无线通信的数字钥匙实验系统 — 智能门锁端
//  主控：STM32F103C8T6
//
//  ID验证方式 (v2.0)：
//    钥匙端 DIP-4 → MCU → Zigbee DL-20 → 无线 → 门锁端 Zigbee DL-20 → STM32
//    门锁端 DIP-4 与收到的钥匙ID比对，一致=授权
//    UWB 只负责测距/测角（定位），不再参与身份识别
//
//  按题目要求逐项实现:
//   [1] UWB通信 + ID检测 + OLED显示 (20分)
//   [3] 距离/方位角定位 (30分) + 滑动平均滤波
//   [4] 迎宾区判定 + 声光提示 (18分) + 事件提示
//   [5] 开锁区判定 + 开锁/闭锁 (18分) + 事件提示
//   [6] DIP拨码手动修改ID (10分) + 变更检测 (两端独立)
//   [7] 其他: 调试串口 + 看门狗 (4分)
// ============================================================

// 全局毫秒计数器 (TIM2 1ms中断自增)
volatile uint32_t g_systick = 0;

// ============================================================
//  DIP-4 拨码开关读取
// ============================================================
static uint8_t dip_read(void)
{
    uint8_t val = 0;
    if (gpio_get(DIP_GPIO, DIP_PIN0) == 0) val |= 0x01;
    if (gpio_get(DIP_GPIO, DIP_PIN1) == 0) val |= 0x02;
    if (gpio_get(DIP_GPIO, DIP_PIN2) == 0) val |= 0x04;
    if (gpio_get(DIP_GPIO, DIP_PIN3) == 0) val |= 0x08;
    return val;
}

// ============================================================
//  OLED 辅助 — 自动补空格到16字符，防止上一帧残影
// ============================================================
static void oled_show(uint8_t row, const char *s)
{
    char line[17];
    int i;
    for (i = 0; s[i] && i < 16; i++) line[i] = s[i];
    for (; i < 16; i++) line[i] = ' ';
    line[16] = '\0';
    OLED_ShowString(row, 1, line);
}

static void oled_show_normal(uint8_t lock_id, uint8_t key_id, uint8_t key_present,
                             uint32_t distance, int16_t az, int16_t el,
                             uint8_t id_match, uint8_t tag_present,
                             Zone_t zone, LockState_t lock)
{
    char buf[17];

    // 锁ID (本机DIP) → 4位二进制 (bit0在左: 1000=拨码1号ON)
    char lock_bin[5];
    lock_bin[0] = (lock_id & 0x01) ? '1' : '0';
    lock_bin[1] = (lock_id & 0x02) ? '1' : '0';
    lock_bin[2] = (lock_id & 0x04) ? '1' : '0';
    lock_bin[3] = (lock_id & 0x08) ? '1' : '0';
    lock_bin[4] = '\0';

    // 钥匙ID → 4位二进制 (与LOCK一致，bit0在左)
    char key_bin[5];
    if (key_present) {
        key_bin[0] = (key_id & 0x01) ? '1' : '0';
        key_bin[1] = (key_id & 0x02) ? '1' : '0';
        key_bin[2] = (key_id & 0x04) ? '1' : '0';
        key_bin[3] = (key_id & 0x08) ? '1' : '0';
        key_bin[4] = '\0';
    } else {
        key_bin[0] = '-'; key_bin[1] = '-';
        key_bin[2] = '-'; key_bin[3] = '-';
        key_bin[4] = '\0';
    }

    // Line1: K:0000 L:1111  (最大15字符)
    sprintf(buf, "K:%s L:%s", key_bin, lock_bin);
    oled_show(1, buf);

    if (!tag_present) {
        // 无UWB信号时也显示ID匹配结果
        {
            const char *st;
            if (!key_present)
                st = "--";
            else
                st = id_match ? "ID:OK" : "ID:NG";
            sprintf(buf, "%s", st);
        }
        oled_show(2, buf);
        oled_show(3, ">> NONE");
        oled_show(4, "     LOCKED");
        return;
    }

    // Line2: 距离 + 方位角 + 匹配结果
    //   "123cm Az:15 OK" 最大16字符, 稳妥用缩写
    {
        const char *st;
        if (!key_present)
            st = "--";
        else
            st = id_match ? "OK" : "NG";
        sprintf(buf, "%ldcm A:%d %s", (int32_t)distance - 30, az, st);
    }
    oled_show(2, buf);

    // Line3: 区域
    sprintf(buf, ">> %s", zone_name(zone));
    oled_show(3, buf);

    // Line4: 锁状态
    oled_show(4, (lock == LOCK_OPEN) ? "     UNLOCK" : "     LOCKED");
}

// 事件提示：覆盖第3-4行
static void oled_show_event(const char *msg)
{
    oled_show(3, msg);
    oled_show(4, "");
}

// ============================================================
//  帧率统计 (仅调试串口输出，不在OLED上显示)
// ============================================================
static uint32_t frame_count_prev = 0;
static uint32_t last_fps_tick   = 0;
static uint32_t current_fps     = 0;

static void update_fps(void)
{
    if (g_systick - last_fps_tick >= 1000)
    {
        current_fps     = g_uwb_frame_count - frame_count_prev;
        frame_count_prev = g_uwb_frame_count;
        last_fps_tick    = g_systick;
        if (current_fps > 0)
            DEBUG_PRINTF("FPS:%lu\r\n", current_fps);
    }
}

// ============================================================
//  main
// ============================================================
int main(void)
{
    uint8_t  dip_id       = 0;
    uint8_t  dip_id_prev  = 0;
    uint8_t  id_match     = 0;
    uint8_t  tag_present  = 0;
    uint8_t  key_present  = 0;
    Zone_t   zone         = ZONE_NONE;
    Zone_t   zone_prev    = ZONE_NONE;  // 用于检测区域变化，触发即时刷新
    uint32_t last_oled    = 0;

    // ---- 事件提示状态 ----
    uint32_t event_show_until = 0;  // g_systick 值，在此之前显示事件
    uint8_t  event_active     = 0;

    // ---- 硬件初始化 ----
    // DIP-4 拨码
    gpio_init(DIP_GPIO, DIP_PIN0, IU);
    gpio_init(DIP_GPIO, DIP_PIN1, IU);
    gpio_init(DIP_GPIO, DIP_PIN2, IU);
    gpio_init(DIP_GPIO, DIP_PIN3, IU);
    dip_id_prev = dip_read();  // 记录初始值，避免开机误触发 ID_CHANGED

    // RGB LED + 蜂鸣器
    lock_control_init();

    // OLED 初始化 — 立即显示 DIP 值（调试用）
    OLED_Init();
    OLED_Clear();
    {
        uint8_t boot_dip = dip_read();
        char dip_bin[5];
        dip_bin[0] = (boot_dip & 0x01) ? '1' : '0';
        dip_bin[1] = (boot_dip & 0x02) ? '1' : '0';
        dip_bin[2] = (boot_dip & 0x04) ? '1' : '0';
        dip_bin[3] = (boot_dip & 0x08) ? '1' : '0';
        dip_bin[4] = '\0';
        OLED_ShowString(1, 1, "C: Digital Key");
        {
            char boot_buf[17];
            sprintf(boot_buf, "K:---- L:%s", dip_bin);
            OLED_ShowString(2, 1, boot_buf);
        }
        OLED_ShowString(3, 1, "Waiting key...");
        OLED_ShowString(4, 1, "     LOCKED");
    }

    // UWB 串口
    uwb_uart_init();

    // Zigbee DL-20 串口 (USART3) — 接收钥匙端ID
    zigbee_uart_init();

    // 调试串口 (UART2)
    debug_uart_init();

    // TIM2 1ms 系统滴答
    tim_interrupt_ms_init(TIM_2, 1, 0);

    // 看门狗 (IWDG) — 约 4 秒超时
    // LSI ≈ 40kHz, 预分频 256 → 156Hz, 重装载 625 → 4s
    IWDG->KR = 0x5555;              // 解锁
    IWDG->PR = 0x06;                // 预分频 256
    IWDG->RLR = 625;                // 重装载值
    IWDG->KR = 0xCCCC;              // 启动
    IWDG->KR = 0xAAAA;              // 喂狗

    OLED_ShowString(3, 1, "Waiting tag...");
    delay_ms(1000);
    OLED_Clear();

    DEBUG_PRINTF("=== C: Digital Key System Boot (v2.0 Zigbee ID) ===\r\n");
    DEBUG_PRINTF("Lock DIP: %d  |  Waiting key Zigbee ID...\r\n", dip_read());

    // ---- 主循环 ----
    while (1)
    {
        // 喂狗
        IWDG->KR = 0xAAAA;

        // ========== 1) 读取 DIP 拨码开关 ==========
        dip_id = dip_read();

        // DIP 变化检测 — 先推送事件 (低优先级)
        //   lock_control_update 随后可能覆盖为区域事件 (高优先级)
        if (dip_id != dip_id_prev)
        {
            DEBUG_PRINTF("DIP changed: %d -> %d\r\n", dip_id_prev, dip_id);
            event_push(EVENT_ID_CHANGED);
            dip_id_prev = dip_id;
            uwb_filter_reset();  // 清空滤波器旧数据 (要求6)
        }

        // ========== 2) UWB 数据 (定位) ==========
        if (g_uwb_updated)
        {
            g_uwb_updated = 0;

            // 区域判定 — 使用滤波后的数据 (要求3/4/5)
            // 注意: UWB 只负责定位，不再用于 ID 比对
            zone_prev = zone;
            zone = zone_determine(zone, g_uwb_filtered.distance, g_uwb_filtered.azimuth);

            // 区域变化 → 立即刷新OLED，不等定时器 (降低延迟)
            if (zone != zone_prev && !event_active)
                last_oled = 0;

            tag_present = 1;

            // 调试输出 (要求7)
            DEBUG_PRINTF("UWB: tag=%lu dist=%lu/%lu az=%+d el=%+d zone=%s\r\n",
                         g_uwb_raw.tag_id,
                         g_uwb_raw.distance, g_uwb_filtered.distance,
                         g_uwb_raw.azimuth, g_uwb_raw.elevation,
                         zone_name(zone));
        }

        // ========== 2.5) Zigbee 数据 (ID验证) ==========
        if (g_key_id_updated)
        {
            g_key_id_updated = 0;
            DEBUG_PRINTF("Zigbee: key_id=%d\r\n", g_key_id);
        }

        // 诊断：每秒输出一次 USART3 原始字节计数
        {
            static uint32_t last_diag = 0;
            static uint32_t prev_byte_count = 0;
            if (g_systick - last_diag >= 1000)
            {
                uint32_t new_bytes = g_zigbee_byte_count - prev_byte_count;
                if (new_bytes > 0)
                    DEBUG_PRINTF("ZIGBEE_DIAG: +%lu bytes/s (total=%lu)\r\n",
                                 new_bytes, g_zigbee_byte_count);
                prev_byte_count = g_zigbee_byte_count;
                last_diag = g_systick;
            }
        }

        // ========== 3) 超时检测 ==========
        // UWB 超时 — 标签不在范围内
        if (g_systick - g_uwb_last_tick > TAG_TIMEOUT_MS)
        {
            if (tag_present)
            {
                DEBUG_PRINTF("Tag timeout!\r\n");
            }
            if (tag_present && !event_active)
                last_oled = 0;  // 标签丢失 → 立即刷新
            tag_present = 0;
            zone        = ZONE_NONE;
        }

        // ========== 3.5) ID 比对 ==========
        // 钥匙端 DIP-4 → Zigbee → g_key_id，与门锁端 DIP-4 比对
        key_present = (g_systick - g_key_id_last_tick < ZIGBEE_TIMEOUT_MS) ? 1 : 0;
        id_match = key_present && (g_key_id == dip_id) ? 1 : 0;

        // Zigbee 超时日志 (仅状态变化时输出一次)
        {
            static uint8_t prev_key_present = 0;
            if (!key_present && prev_key_present)
            {
                DEBUG_PRINTF("Zigbee timeout!\r\n");
            }
            prev_key_present = key_present;
        }

        // ========== 4) 锁状态机 (要求4/5) ==========
        lock_control_update(zone, id_match, tag_present);

        // ========== 5) 事件处理 ==========
        {
            Event_t ev = event_pop();
            if (ev != EVENT_NONE)
            {
                event_show_until = g_systick + EVENT_SHOW_MS;
                event_active     = 1;
                DEBUG_PRINTF("Event: %s\r\n", event_name(ev));

                // 根据事件类型在 OLED 上显示不同文字
                oled_show_event(event_name(ev));

                // ID变更仅OLED提示，不触发蜂鸣器
            }

            // 事件超时 → 恢复普通显示 (不清屏，下次刷新自然覆盖)
            if (event_active && g_systick > event_show_until)
            {
                event_active = 0;
                last_oled = 0;  // 触发立即刷新
            }
        }

        // ========== 6) 帧率统计 (调试串口) ==========
        update_fps();

        // ========== 7) 调试命令 (调试时取消注释) ==========
        // debug_cmd_poll();

        // ========== 8) OLED 刷新 (正常显示) ==========
        if (!event_active && g_systick - last_oled >= OLED_UPDATE_MS)
        {
            last_oled = g_systick;
            oled_show_normal(dip_id,
                             g_key_id, key_present,
                             g_uwb_filtered.distance,
                             g_uwb_filtered.azimuth,
                             g_uwb_filtered.elevation,
                             id_match, tag_present,
                             zone, lock_get_state());
        }

        /*
        // ========== 8) OLED 诊断显示 (调试用) ==========
        if (!event_active && g_systick - last_oled >= OLED_UPDATE_MS)
        {
            last_oled = g_systick;

            char buf[17];
            char dip_bin[5];
            dip_bin[0] = (dip_id & 0x01) ? '1' : '0';
            dip_bin[1] = (dip_id & 0x02) ? '1' : '0';
            dip_bin[2] = (dip_id & 0x04) ? '1' : '0';
            dip_bin[3] = (dip_id & 0x08) ? '1' : '0';
            dip_bin[4] = '\0';

            // Line1: Zigbee 字节计数
            sprintf(buf, "ZB:%05lu up:%d", g_zigbee_byte_count, g_key_id_updated);
            oled_show(1, buf);

            // Line2: 收到的钥匙ID (4位二进制)
            {
                char key_bin[5];
                key_bin[0] = (g_key_id & 0x01) ? '1' : '0';
                key_bin[1] = (g_key_id & 0x02) ? '1' : '0';
                key_bin[2] = (g_key_id & 0x04) ? '1' : '0';
                key_bin[3] = (g_key_id & 0x08) ? '1' : '0';
                key_bin[4] = '\0';
                sprintf(buf, "Key:%s p:%d", key_bin, key_present);
            }
            oled_show(2, buf);

            // Line3: 本机DIP + 匹配
            sprintf(buf, "DIP:%s m:%d", dip_bin, id_match);
            oled_show(3, buf);

            // Line4: UWB + 区域
            if (tag_present)
                sprintf(buf, "%lucm %s", g_uwb_filtered.distance, zone_name(zone));
            else
                sprintf(buf, "No UWB");
            oled_show(4, buf);
        }
        */
    }
}
