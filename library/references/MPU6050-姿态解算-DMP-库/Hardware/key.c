#include "key.h"

uint8_t click(void)
{
	uint8_t key_num=0;
	if(DL_GPIO_readPins(KEY_PORT,KEY_PIN_21_PIN)==0)
	{
		delay_ms(50);
		while(DL_GPIO_readPins(KEY_PORT,KEY_PIN_21_PIN)==0);
		delay_ms(50);
		key_num=1;
	}
	return key_num;
}



