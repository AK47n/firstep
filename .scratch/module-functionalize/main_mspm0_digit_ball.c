#include "ti_msp_dl_config.h"
#include "digit_uart_mspm0.h"
#include "ball_detect.h"

/* module-functionalize/05+09 编译验收 main：DIGIT_UART 共享实例（UART1），
 * main.c 单个 IRQHandler 聚合两个 rx_handler。 */

int main(void)
{
    /* 产物编译验收：母版头在 SysConfig 生成后才存在，门禁不允许裸调
     * SYSCFG_DL_init；上板工程请取消下面注释。 */
    /* SYSCFG_DL_init(); */
    digit_uart_init();
    ball_detect_init();

    while (1)
    {
        digit_uart_parse();
        ball_detect_parse();
    }
}

void DIGIT_UART_INST_IRQHandler(void)
{
    digit_uart_rx_handler();
    ball_detect_rx_handler();
}
