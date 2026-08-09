#include "headfile.h"

GPIO_TypeDef *gpio_index[3] = { GPIOA , GPIOB , GPIOC };

//-------------------------------------------------------------------------------------------------------------------
// @brief		GPIO��ʼ��
// @param	  GPIOn	  ѡ��GPIO�˿�	
// @param	  Pinx    ѡ�����ź�
// @param	  mode    ѡ����ģʽ
// @return		void  
// Sample usage:		gpio_init(GPIO_A,Pin_0,OUT_PP);
//-------------------------------------------------------------------------------------------------------------------
void gpio_init(GPIOn_enum GPIOn,Pinx_enum Pinx,GPIO_MODE_enum mode)
{
	uint32_t temp;
	
	RCC->APB2ENR |= 4<<GPIOn;         //ʹ��ʱ��
  
	if(Pinx<8)
	{
			gpio_index[GPIOn]->CRL &= ~((0x0000000F)<<(Pinx*4));     //���ּĴ�������λ���� ��ѡ��λ����
			if(mode == OUT_PP || mode == AF_PP || mode == OUT_OD)
				gpio_index[GPIOn]->CRL |= ((0x00000003)|(1<<mode))<<(Pinx*4);        //�������(Ĭ������͵�ƽ)
			else if(mode == IU || mode == ID)
			{
				gpio_index[GPIOn]->CRL |= 0x00000008<<(Pinx*4);        //����/����
				if(mode == IU)
				{
					temp = gpio_index[GPIOn]->ODR&(~(1<<Pinx));          //��������λ���� ��ѡ��λ����
					gpio_index[GPIOn]->ODR = temp|(1<<Pinx);             //��������λ���� ��ѡ��λ��1
				}
				if(mode == ID)
					gpio_index[GPIOn]->ODR &= ~(1<<Pinx);                //��������λ���� ��ѡ��λ����
			}
			else
				gpio_index[GPIOn]->CRL |= (0x00000004<<mode)<<(Pinx*4);								
	}
	else
  {
			gpio_index[GPIOn]->CRH &= ~((0x0000000F)<<((Pinx-8)*4));     //���ּĴ�������λ���� ��ѡ��λ����
			if(mode == OUT_PP || mode == AF_PP || mode == OUT_OD)
				gpio_index[GPIOn]->CRH |= ((0x00000003)|(1<<mode))<<((Pinx-8)*4);        //�������(Ĭ������͵�ƽ)
			else if(mode == IU || mode == ID)
			{
				gpio_index[GPIOn]->CRH |= 0x00000008<<((Pinx-8)*4);        //����/����
				if(mode == IU)
				{
					temp = gpio_index[GPIOn]->ODR&(~(1<<Pinx));  // 修复：原写死GPIOA的bug
					gpio_index[GPIOn]->ODR = temp|(1<<Pinx);             //��������λ���� ��ѡ��λ��1
				}
				if(mode == ID)
					gpio_index[GPIOn]->ODR &= ~(1<<Pinx);                //��������λ���� ��ѡ��λ����
			}
			else
				gpio_index[GPIOn]->CRH |= (0x00000004<<mode)<<((Pinx-8)*4);	
			
		}

}

//-------------------------------------------------------------------------------------------------------------------
// @brief		����GPIO�����ƽ
// @param	  GPIOn	  ѡ��GPIO�˿�	
// @param	  Pinx    ѡ�����ź�
// @param	  mode    ��1Ϊ�ߵ�ƽ ��0Ϊ�͵�ƽ
// @return		void  
// Sample usage:			gpio_set(GPIO_A,Pin_0,1);
//-------------------------------------------------------------------------------------------------------------------
void gpio_set(GPIOn_enum GPIOn,Pinx_enum Pinx,uint8_t mode)
{
	uint32_t temp;
	
	if(mode)
	{
		temp = gpio_index[GPIOn]->ODR&(~(1<<Pinx));   //��������λ���� ��ѡ��λ����
		gpio_index[GPIOn]->ODR = temp|(1<<Pinx);      //��������λ���� ��ѡ��λ��1
	}
	else
		gpio_index[GPIOn]->ODR &= ~(1<<Pinx);         //��������λ���� ��ѡ��λ����
}

//-------------------------------------------------------------------------------------------------------------------
// @brief		��ȡGPIO����
// @param	  GPIOn	  ѡ��GPIO�˿�	
// @param	  Pinx    ѡ�����ź�
// @return		uint8_t  
// Sample usage:			gpio_get(GPIO_A,Pin_4)
//-------------------------------------------------------------------------------------------------------------------
uint8_t gpio_get(GPIOn_enum GPIOn,Pinx_enum Pinx)
{
	uint32_t temp;
	
	temp = gpio_index[GPIOn]->IDR&(1<<Pinx);   //����λȫ����0 ѡ��λΪ1��temp��Ϊ0 ����tempΪ0
	
	if(temp)                          //temp��Ϊ0 ˵��ѡ��λΪ1 ������ߵ�ƽ
		return 1;
	else                              //tempΪ0 ˵��ѡ��λΪ0 ������͵�ƽ
		return 0;
}
