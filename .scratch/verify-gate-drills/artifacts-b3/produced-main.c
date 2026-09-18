#include "ti_msp_dl_config.h"
#include "servo.h"

int main(void)
{
    /* TODO: 若使用 SysConfig 生成的外设初始化，请取消下面注释 */
    // SYSCFG_DL_init();
    servo_init(1, 0);
    servo_set_angle(1, 90);
    while (1) {
    }
}
