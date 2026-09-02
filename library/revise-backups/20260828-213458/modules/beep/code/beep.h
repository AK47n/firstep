#ifndef BEEP_H
#define BEEP_H

#include <stdint.h>

void beep_init(void);
void beep_on(void);
void beep_off(void);
void beep_toggle(void);

/* 响 N 声：on_ms 响 / off_ms 停（有源蜂鸣器，阻塞式） */
void beep_beep(uint16_t times, uint16_t on_ms, uint16_t off_ms);

#endif // BEEP_H
