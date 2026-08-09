#include "headfile.h"
#include "lock_control.h"
#include "config.h"

// ============================================================
//  内部状态
// ============================================================
static LockState_t lock_state       = LOCK_CLOSED;
static Zone_t      prev_zone        = ZONE_NONE;
static uint8_t     prev_id_match    = 0;
static uint8_t     prev_tag_present = 0;
static uint32_t    buzzer_off_at       = 0;  // 蜂鸣器自动关闭时刻 (非阻塞)
static uint32_t    welcome_beep_next   = 0;  // 迎宾区下次蜂鸣时刻

// 事件队列 (只存最近一个事件)
static Event_t     pending_event   = EVENT_NONE;

// ============================================================
//  初始化
// ============================================================
void lock_control_init(void)
{
    gpio_init(LED_GPIO, LED_RED_PIN, OUT_PP);
    gpio_init(LED_GPIO, LED_YELLOW_PIN, OUT_PP);
    gpio_init(LED_GPIO, LED_GREEN_PIN, OUT_PP);
    gpio_init(BUZZER_GPIO, BUZZER_PIN, OUT_PP);

    lock_set_led(0, 0, 0);
    gpio_set(BUZZER_GPIO, BUZZER_PIN, 1);  // 低电平触发，初始高=蜂鸣器关

    prev_zone        = ZONE_NONE;
    prev_id_match    = 0;
    prev_tag_present = 0;
}

// ============================================================
//  LED 控制
// ============================================================
void lock_set_led(uint8_t red, uint8_t yellow, uint8_t green)
{
    gpio_set(LED_GPIO, LED_RED_PIN,   red    ? 1 : 0);
    gpio_set(LED_GPIO, LED_YELLOW_PIN, yellow ? 1 : 0);
    gpio_set(LED_GPIO, LED_GREEN_PIN,  green  ? 1 : 0);
}

// ============================================================
//  蜂鸣器
// ============================================================
void buzzer_beep_ms(uint32_t ms)
{
    gpio_set(BUZZER_GPIO, BUZZER_PIN, 0);  // 低电平=蜂鸣器响
    buzzer_off_at = g_systick + ms;
}

LockState_t lock_get_state(void) { return lock_state; }

// ============================================================
//  事件系统
// ============================================================
void event_push(Event_t e)
{
    pending_event = e;
}

Event_t event_pop(void)
{
    Event_t e = pending_event;
    pending_event = EVENT_NONE;
    return e;
}

const char* event_name(Event_t e)
{
    switch (e)
    {
        case EVENT_ENTER_SENSING: return "Enter Sensing";
        case EVENT_ENTER_WELCOME: return "Enter Welcome";
        case EVENT_LEAVE_WELCOME: return "Leave Welcome";
        case EVENT_ENTER_UNLOCK:  return "UNLOCK";
        case EVENT_LEAVE_UNLOCK:  return "LOCKED";
        case EVENT_ID_CHANGED:    return "ID Changed";
        case EVENT_ID_MISMATCH:   return "Bad ID";
        case EVENT_TAG_LOST:      return "Tag Lost";
        default:                  return "";
    }
}

// ============================================================
//  状态更新
// ============================================================
void lock_control_update(Zone_t zone, uint8_t id_match, uint8_t tag_present)
{
    // ====== 蜂鸣器自动关闭 (非阻塞，每轮检查) ======
    if (buzzer_off_at > 0 && g_systick >= buzzer_off_at)
    {
        gpio_set(BUZZER_GPIO, BUZZER_PIN, 1);  // 高电平=蜂鸣器关
        buzzer_off_at = 0;
    }

    // ====== 事件检测 ======

    // 钥匙丢失
    if (!tag_present && prev_tag_present)
        event_push(EVENT_TAG_LOST);

    // ID 不匹配
    if (tag_present && !id_match && prev_id_match)
        event_push(EVENT_ID_MISMATCH);

    // 区域变化 (仅 ID 匹配时触发)
    if (id_match && tag_present)
    {
        if (zone != prev_zone)
        {
            switch (zone)
            {
                case ZONE_SENSING: event_push(EVENT_ENTER_SENSING); break;
                case ZONE_WELCOME:
                    event_push(EVENT_ENTER_WELCOME);
                    welcome_beep_next = g_systick;  // 立即触发第一次蜂鸣
                    break;
                case ZONE_UNLOCK:  event_push(EVENT_ENTER_UNLOCK);  break;
                default: break;
            }
            if (prev_zone == ZONE_WELCOME && zone != ZONE_WELCOME)
            {
                event_push(EVENT_LEAVE_WELCOME);
                welcome_beep_next = 0;  // 离开迎宾区，停止蜂鸣
            }
            if (prev_zone == ZONE_UNLOCK && zone != ZONE_UNLOCK)
                event_push(EVENT_LEAVE_UNLOCK);
        }
    }

    prev_tag_present = tag_present;
    prev_id_match    = id_match;

    // ====== 无钥匙 ----
    if (!tag_present)
    {
        lock_set_led(1, 0, 0);
        lock_state = LOCK_CLOSED;
        prev_zone  = ZONE_NONE;
        return;
    }

    // ====== ID 不匹配 — 红灯 + OLED 显示即可，无需特殊灯效 ======
    if (!id_match)
    {
        lock_set_led(1, 0, 0);
        lock_state = LOCK_CLOSED;
        prev_zone  = ZONE_NONE;
        return;
    }

    // ====== ID 匹配 — 按区域执行 ----

    // 区域切换 → 锁动作
    if (zone == ZONE_UNLOCK && prev_zone != ZONE_UNLOCK)
        lock_state = LOCK_OPEN;
    if (zone != ZONE_UNLOCK && prev_zone == ZONE_UNLOCK)
        lock_state = LOCK_CLOSED;
    prev_zone = zone;

    // 当前区域 LED
    switch (zone)
    {
        case ZONE_UNLOCK:
            lock_set_led(0, 0, 1);      // 绿灯常亮
            break;

        case ZONE_WELCOME:
            lock_set_led(1, 1, 0);      // 红灯+黄灯一起亮 (赛题要求)
            // 每1s蜂鸣器短鸣 (赛题要求4: 迎宾区声光提示)
            if (welcome_beep_next > 0 && g_systick >= welcome_beep_next)
            {
                buzzer_beep_ms(50);
                welcome_beep_next = g_systick + 1000;
            }
            break;

        case ZONE_SENSING:
            lock_set_led(1, 0, 0);
            break;

        case ZONE_NONE:
        default:
            lock_set_led(1, 0, 0);
            break;
    }

}
