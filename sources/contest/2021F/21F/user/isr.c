#include "stm32f10x.h"                  // Device header
#include "headfile.h"

//����Ϊ��ʱ���жϷ�����
void TIM2_IRQHandler(void)
{
	if(TIM2->SR&1)
	{
		//�˴���д�жϴ���
		TIM2->SR &= ~1; 
	}
}

void TIM3_IRQHandler(void)
{
	if(TIM3->SR&1)
	{
		// 读取编码器速度（10ms内脉冲数），关闭全局中断防止竞态
		__disable_irq();
		int enc1 = Encoder_count1;
		int enc2 = Encoder_count2;
		Encoder_count1 = 0;
		Encoder_count2 = 0;
		__enable_irq();
		motorA.now = (float)enc1;
		motorB.now = (float)enc2;

		pid_control();

		TIM3->SR &= ~1;
	}
}

void TIM4_IRQHandler(void)
{
	if(TIM4->SR&1)
	{
		//�˴���д�жϴ���
		TIM4->SR &= ~1; 
	}
}


//����Ϊ�����жϷ�����
void USART1_IRQHandler(void)
{
	// K230数字识别数据接收（handler内部处理RXNE/ORE/FE等所有状态）
	digit_uart_rx_handler();
}

void USART2_IRQHandler(void)
{
	if (USART2->SR&0x20)
	{
		USART2->SR &= ~0x20;
	}
}

void USART3_IRQHandler(void)
{
	if (USART3->SR&0x20)
	{
		//�˴���д�жϴ���

		USART3->SR &= ~0x20;   //�����־λ
	}
}


//����Ϊ�ⲿ�жϷ�����
void EXTI0_IRQHandler(void) // PA0/PB0/PC0
{
	if(EXTI->PR&(1<<0))
	{
		//�˴���д�жϴ���
		
		EXTI->PR = 1<<0; //�����־λ
	}
}

void EXTI1_IRQHandler(void) // PA1/PB1/PC1
{
	if(EXTI->PR&(1<<1))
	{
		//�˴���д�жϴ���
		
		EXTI->PR = 1<<1; //�����־λ
	}
}
void EXTI2_IRQHandler(void) // PA2/PB2/PC2
{
	if(EXTI->PR&(1<<2))
	{
		//�˴���д�жϴ���
		if(gpio_get(GPIO_A, Pin_3))
			Encoder_count1 ++;
		else
			Encoder_count1 --;
		
		EXTI->PR = 1<<2; //�����־λ
	}
}
void EXTI3_IRQHandler(void) // PA3/PB3/PC3
{
	if(EXTI->PR&(1<<3))
	{
		//�˴���д�жϴ���
		
		EXTI->PR = 1<<3; //�����־λ
	}
}
void EXTI4_IRQHandler(void) // PA4/PB4/PC4
{
	if(EXTI->PR&(1<<4))
	{
		//�˴���д�жϴ���
		if(gpio_get(GPIO_A, Pin_5))
			Encoder_count2 ++;
		else
			Encoder_count2 --;
		EXTI->PR = 1<<4; //�����־λ
	}
}

void EXTI9_5_IRQHandler(void)
{
	if(EXTI->PR&(1<<5))   //EXTI5  PA5/PB5/PC5
	{
		//�˴���д�жϴ���

		EXTI->PR = 1<<5; //�����־λ
	}
	
	if(EXTI->PR&(1<<6))   //EXTI6  PA6/PB6/PC6
	{
		//�˴���д�жϴ���
		
		EXTI->PR = 1<<6; //�����־λ
	}
	
	if(EXTI->PR&(1<<7))   //EXTI7  PA7/PB7/PC7
	{
		//�˴���д�жϴ���
		
		// ��ȡԭʼ����
		MPU6050_GetData();
		HMC5883L_GetData();
		
		// �����ǽǶ�
		roll_gyro += (float)gy / 16.4 * 0.005;
		pitch_gyro += (float)gx / 16.4 * 0.005;
		yaw_gyro += (float)gz / 16.4 * 0.005;
		
		// ���ٶȼƽǶ�
		roll_acc = atan((float)ax/az) * 57.296;
		pitch_acc = - atan((float)ay/az) * 57.296;	
		yaw_acc = atan((float)ax/ay) * 57.296;
		
		// �����ƽǶ�
		yaw_hmc = atan2((float)hmc_x, (float)hmc_y) * 57.296;
		
		// �������˲��ںϽǶ�
		roll_Kalman = Kalman_Filter(&KF_Roll, roll_acc, (float)gy / 16.4);
		pitch_Kalman = Kalman_Filter(&KF_Pitch, pitch_acc, (float)gx / 16.4);
		yaw_Kalman = Kalman_Filter(&KF_Yaw, yaw_hmc, (float)gz / 16.4);
		
		EXTI->PR = 1<<7; //�����־λ
	}
	
	if(EXTI->PR&(1<<8))   //EXTI8
	{
		//�˴���д�жϴ���
		
		EXTI->PR = 1<<8; //�����־λ
	}
	
	if(EXTI->PR&(1<<9))   //EXTI9
	{
		//�˴���д�жϴ���
		
		EXTI->PR = 1<<9; //�����־λ
	}
}
