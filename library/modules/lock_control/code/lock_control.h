#ifndef _lock_control_h_
#define _lock_control_h_

#include "headfile.h"
#include "zone.h"

// 锁状态
typedef enum {
    LOCK_CLOSED = 0,
    LOCK_OPEN   = 1
} LockState_t;

// 系统事件 (用于 OLED 短暂提示)
typedef enum {
    EVENT_NONE = 0,
    EVENT_ENTER_SENSING,    // 进入感应区
    EVENT_ENTER_WELCOME,    // 进入迎宾区
    EVENT_LEAVE_WELCOME,    // 离开迎宾区
    EVENT_ENTER_UNLOCK,     // 进入开锁区 → 开锁
    EVENT_LEAVE_UNLOCK,     // 离开开锁区 → 闭锁
    EVENT_ID_CHANGED,       // DIP 拨码 ID 已更改
    EVENT_ID_MISMATCH,      // ID 不匹配
    EVENT_TAG_LOST,         // 钥匙信号丢失 (超时)
} Event_t;

// 函数声明
void lock_control_init(void);
void lock_control_update(
    Zone_t zone,
    uint8_t id_match,
    uint8_t tag_present
);
LockState_t lock_get_state(void);
void lock_set_led(uint8_t red, uint8_t yellow, uint8_t green);
void buzzer_beep_ms(uint32_t ms);

// 事件系统：主循环读取事件后自动清零
void event_push(Event_t e);     // 推送事件 (仅保留最新一个)
Event_t event_pop(void);        // 取出并清除事件
const char* event_name(Event_t e);

#endif
