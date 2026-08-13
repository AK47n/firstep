#include "user.h"






int fputc(int ch, FILE *stream)
{
        while( DL_UART_isBusy(user_INST) == true );

        DL_UART_Main_transmitData(user_INST, ch);

        return ch;
}