#include "control.h"
#include "stdio.h"
#include "string.h"

#define AIN11	DL_GPIO_setPins(GPIO_IN_PIN_AIN1_PORT,GPIO_IN_PIN_AIN1_PIN)
#define AIN10	DL_GPIO_clearPins(GPIO_IN_PIN_AIN1_PORT,GPIO_IN_PIN_AIN1_PIN)
#define AIN21	DL_GPIO_setPins(GPIO_IN_PIN_AIN2_PORT,GPIO_IN_PIN_AIN2_PIN)
#define AIN20	DL_GPIO_clearPins(GPIO_IN_PIN_AIN2_PORT,GPIO_IN_PIN_AIN2_PIN)

#define BIN11	DL_GPIO_setPins(GPIO_IN_PIN_BIN1_PORT,GPIO_IN_PIN_BIN1_PIN)
#define BIN10	DL_GPIO_clearPins(GPIO_IN_PIN_BIN1_PORT,GPIO_IN_PIN_BIN1_PIN)
#define BIN21	DL_GPIO_setPins(GPIO_IN_PIN_BIN2_PORT,GPIO_IN_PIN_BIN2_PIN)
#define BIN20	DL_GPIO_clearPins(GPIO_IN_PIN_BIN2_PORT,GPIO_IN_PIN_BIN2_PIN)

#define P1			DL_GPIO_readPins(GPIO_Gray_PIN_Gray_1_PORT,GPIO_Gray_PIN_Gray_1_PIN)
#define P2			DL_GPIO_readPins(GPIO_Gray_PIN_Gray_2_PORT,GPIO_Gray_PIN_Gray_2_PIN)
#define P3			DL_GPIO_readPins(GPIO_Gray_PIN_Gray_3_PORT,GPIO_Gray_PIN_Gray_3_PIN)
#define P4			DL_GPIO_readPins(GPIO_Gray_PIN_Gray_4_PORT,GPIO_Gray_PIN_Gray_4_PIN)
#define P5			DL_GPIO_readPins(GPIO_Gray_PIN_Gray_5_PORT,GPIO_Gray_PIN_Gray_5_PIN)
#define P6			DL_GPIO_readPins(GPIO_Gray_PIN_Gray_6_PORT,GPIO_Gray_PIN_Gray_6_PIN)
#define P7			DL_GPIO_readPins(GPIO_Gray_PIN_Gray_7_PORT,GPIO_Gray_PIN_Gray_7_PIN)
#define P8			DL_GPIO_readPins(GPIO_Gray_PIN_Gray_8_PORT,GPIO_Gray_PIN_Gray_8_PIN)

volatile uint32_t gpioA,gpioB;
volatile int32_t gEncoderCount_left = 0, gEncoderVal_left = 0;          //左轮编码器计数值；左轮编码器记录值，50ms定时中断输出
volatile int32_t gEncoderCount_right = 0, gEncoderVal_right = 0;        //右轮编码器计数值；右轮编码器记录值，50ms定时中断输出
extern float Yaw;                                                       //陀螺仪偏转角返回值

#define  Limit		200						//PWM波限幅，百分比制

//巡线增益（加权质心法），值越大转向越激进
#define  GAIN_NORMAL     3.4f             //普通速度巡线
// #define  GAIN_HIGH       7.0f             //高速巡线
// #define  GAIN_LOW        3.0f             //低速巡线
//  - 直道抖动 → 减小对应 gain
//  - 弯道跟不住/切外出轨 → 增大对应 gain
//  - 每次改 0.5 左右，烧录测试看效果

//速度环PID
#define   Kp1   			0.9
#define   Ki1     		    0              //经测试不需要I环和D环
#define   Kd1  				0

float CurrentA, CurrentB;			//编码器测得当前速度
float targetA=0, targetB=0;			//当前目标速度
float Speed_diff; 					//当前差速
volatile int flag=1,n=1,whiteflag=0,whiteflag1=0,whiteflag2=0;         //白色区域计数标志位；白色区域计数值；陀螺仪模式标志位
volatile int timebegin=0,timenum=0;          //陀螺仪模式启动延时标志位；延时计数值
volatile int timebegin1=0,timenum1=0;          //陀螺仪模式启动延时标志位；延时计数值
volatile int timebegin2=0,timenum2=0;          //陀螺仪模式启动延时标志位；延时计数值
volatile int ledbegin=0,lednum=0,ledflag=0,ledflag1=0,ledflag2=0;        //声光模块延时标志位；延时计数值；声光模块启动标志位
float error=180;                                                //两个方向的偏转
volatile int m=0;                                                        //模式切换计数值，用以判断是否跑完全程
volatile int a=0;                                                        //AB模式停止标志位
volatile int dirt_ignore_ticks=0;                                       //白区脏点忽略计时 (300 ticks = 3s)
volatile int pwmstart=1;
volatile float tim=0;
volatile int timbegin=0,timnum=0;

void Control_AB(void)                       //模式一
{
    float Speed_Middle=20;				//中值速度
    int Motor_Left, Motor_Right;            //电机赋值
    float bias;
    bias = Yaw;
    

    if ((P1==0 || P2==0 || P3==0 || P4==0 || P5==0 || P6==0 || P7==0 || P8==0)&&a==0)
    {
        // DL_GPIO_clearPins(GPIO_STBY_PORT,GPIO_STBY_PIN_STBY_PIN);
        timbegin=0;
        pwmstart=0;
        ledbegin=1;
        a=1;
    }

    if (ledflag==1)
    {
        DL_GPIO_setPins(GPIO_LED_PORT,GPIO_LED_PIN_LED_PIN);
        DL_GPIO_clearPins(GPIO_BEEP_PORT,GPIO_BEEP_PIN_BEEP_PIN);
    }
    else
    {
        DL_GPIO_clearPins(GPIO_LED_PORT,GPIO_LED_PIN_LED_PIN);
        DL_GPIO_setPins(GPIO_BEEP_PORT,GPIO_BEEP_PIN_BEEP_PIN);
    }

    targetA = Speed_Middle+bias;
	targetB = Speed_Middle-bias;
    CurrentA = (float)gEncoderVal_left/3; //left
	CurrentB = (float)gEncoderVal_right/3; //right
	Motor_Left  = (int)PWM_Limit(PID_A(CurrentA,targetA),Limit, -Limit);
	Motor_Right = (int)PWM_Limit(PID_B(CurrentB,targetB),Limit, -Limit);		//PWM限幅

    if(pwmstart==1) Set_Pwm(Motor_Left, Motor_Right);
    else if(pwmstart==0) Set_Pwm(1, 1);
}
	
void Control_ABCDA(void)
{
    float Speed_Middle=20;				//中值速度
	int Motor_Left, Motor_Right;
    float bias;
    
    // if(m==6)
    // {
    //     DL_GPIO_clearPins(GPIO_STBY_PORT,GPIO_STBY_PIN_STBY_PIN);
    // }

    if (ledflag==1)//**亮灯指示器
    {
        DL_GPIO_setPins(GPIO_LED_PORT,GPIO_LED_PIN_LED_PIN);
        DL_GPIO_clearPins(GPIO_BEEP_PORT,GPIO_BEEP_PIN_BEEP_PIN);
    }
    else
    {
        DL_GPIO_clearPins(GPIO_LED_PORT,GPIO_LED_PIN_LED_PIN);
        DL_GPIO_setPins(GPIO_BEEP_PORT,GPIO_BEEP_PIN_BEEP_PIN);
    }

    if (P1!=0 && P2!=0 && P3!=0 && P4!=0 && P5!=0 && P6!=0 && P7!=0 && P8!=0) timebegin=1;
    else if (dirt_ignore_ticks==0) whiteflag=0;

    if (whiteflag==1) //**白色区域标记 */
    {
        ledflag2=0;/*清楚巡线标记 */
        if(ledflag1==0)/*若是第一帧进入白色区域，则设立白色区域标志*/
        {
            ledflag1=1;/*第一帧则登记白色区域*/
            ledbegin=1;/*小灯开始*/
            dirt_ignore_ticks=300;/*白区脏点忽略计时3秒*/
            m++;/*第一帧进入白色区域时m+1*/
        }

        if (n%2==0)/*掉头n=2时*/
        {
            if(Yaw<0)
            {
                bias = error - myabs(Yaw);
            }
            else
            {
                bias = Yaw - error;
            }
        }
        else if(n%2==1)/*巡线*/
        {
            bias = Yaw;
        }
        flag=0;/*在白色区域时把黑色状态标记清0*/
    }
    else if(whiteflag==0)/*无白在巡线*/
    {
        ledflag1=0;/*把第一帧进入白色区域标志清0*/
        if(ledflag2==0)/*若是第一帧进入黑色区域*/
        {
            ledflag2=1;/*第一帧登记黑色区域*/
            ledbegin=1;/*小灯开始*/
            m++;/*第一帧进入黑色区域时m+1*/
        }

        if(flag==0)/*若是第一帧离开白色区域，即开始巡线*/
        {
            flag=1;/*登记黑色标记*/
            n=n+1;/*n初始为1，开始加1*/
        }
        bias = xunji_centroid(GAIN_NORMAL);
        whiteflag=0;/*在黑色区域时把白色状态标志清0*/
    }

    targetA = Speed_Middle+bias;
	targetB = Speed_Middle-bias;
    CurrentA = (float)gEncoderVal_left/3; //left
	CurrentB = (float)gEncoderVal_right/3; //right
	Motor_Left  = (int)PWM_Limit(PID_A(CurrentA,targetA),Limit, -Limit);
	Motor_Right = (int)PWM_Limit(PID_B(CurrentB,targetB),Limit, -Limit);		//PWM限幅

    if(m>=6) 
    {
        Set_Pwm(1,1);
        timbegin=0;
    }
	else Set_Pwm(Motor_Left, Motor_Right);
}

void Control_ACBDA(void)
{
    float Speed_Middle=20;				//中值速度
    int Motor_Left, Motor_Right;
    float bias;

    if (ledflag==1)
    {
        DL_GPIO_setPins(GPIO_LED_PORT,GPIO_LED_PIN_LED_PIN);
        DL_GPIO_clearPins(GPIO_BEEP_PORT,GPIO_BEEP_PIN_BEEP_PIN);
    }
    else
    {
        DL_GPIO_clearPins(GPIO_LED_PORT,GPIO_LED_PIN_LED_PIN);
        DL_GPIO_setPins(GPIO_BEEP_PORT,GPIO_BEEP_PIN_BEEP_PIN);
    }



    if (P1!=0 && P2!=0 && P3!=0 && P4!=0 && P5!=0 && P6!=0 && P7!=0 && P8!=0) timebegin1=1;/*初步认定白区*/
    else if (dirt_ignore_ticks==0) whiteflag1=0;/*不是白区*/

    if (whiteflag1==1) /*白区*/
    {
        ledflag2=0;/*黑区标志清0*/
        if(ledflag1==0)
        {
            ledflag1=1;
            ledbegin=1;
            dirt_ignore_ticks=300;/*白区脏点忽略计时3秒*/
            m++; /*第一帧进白m+1*/
        }

        if (n%2==0)/*n偶偏角*/
        {
            bias = Yaw + 103;
        }
        else if(n%2==1)
        {
            bias = Yaw;
        }
        flag=0;
    }
    else if(whiteflag1==0)/*巡线*/
    {
        ledflag1=0;
        if(ledflag2==0)
        {
            ledflag2=1;
            ledbegin=1;
            m++;
        }

        if(flag==0)
        {
            flag=1;
            n=n+1;
        }

        bias = xunji_centroid(GAIN_NORMAL);
        whiteflag1=0;
    }


    targetA = Speed_Middle+bias;
	targetB = Speed_Middle-bias;
    CurrentA = (float)gEncoderVal_left/3; //left
	CurrentB = (float)gEncoderVal_right/3; //right
	Motor_Left  = (int)PWM_Limit(PID_A(CurrentA,targetA),Limit, -Limit);
	Motor_Right = (int)PWM_Limit(PID_B(CurrentB,targetB),Limit, -Limit);		//PWM限幅

    if(m>=6) 
    {
        Set_Pwm(1,1);
        timbegin=0;
    }
	else Set_Pwm(Motor_Left, Motor_Right);
}

void Control_ACBDAx4(void)
{
    float Speed_Middle=20;	//20			//中值速度
    int Motor_Left, Motor_Right;
    float bias;

    if(m==18) DL_GPIO_clearPins(GPIO_STBY_PORT,GPIO_STBY_PIN_STBY_PIN);

    if (ledflag==1)
    {
        DL_GPIO_setPins(GPIO_LED_PORT,GPIO_LED_PIN_LED_PIN);
        DL_GPIO_clearPins(GPIO_BEEP_PORT,GPIO_BEEP_PIN_BEEP_PIN);
    }
    else
    {
        DL_GPIO_clearPins(GPIO_LED_PORT,GPIO_LED_PIN_LED_PIN);
        DL_GPIO_setPins(GPIO_BEEP_PORT,GPIO_BEEP_PIN_BEEP_PIN);
    }

    if (P1!=0 && P2!=0 && P3!=0 && P4!=0 && P5!=0 && P6!=0 && P7!=0 && P8!=0) timebegin2=1;
    else if (dirt_ignore_ticks==0) whiteflag2=0;

    if (whiteflag2==1)
    {
        ledflag2=0;
        if(ledflag1==0)
        {
            ledflag1=1;
            ledbegin=1;
            dirt_ignore_ticks=300;/*白区脏点忽略计时3秒*/
            m++;
        }

        if (n%2==0)
        {
            bias = Yaw + 103;
        }
        else if(n%2==1)
        {
            if (n==1)
            {
                bias = Yaw;
            }
            // if(n==5)
            // {
            //     bias = Yaw - 3;
            // }
            else bias = Yaw - 4;
        }
        flag=0;
    }
    else if(whiteflag2==0)
    {
        ledflag1=0;
        if(ledflag2==0)
        {
            ledflag2=1;
            ledbegin=1;
            m++;
        }

        if(flag==0)
        {
            flag=1;
            n=n+1;
        }
        
        bias = xunji_centroid(GAIN_NORMAL);
        whiteflag2=0;
    }


    targetA = Speed_Middle+bias;
	targetB = Speed_Middle-bias;
    CurrentA = (float)gEncoderVal_left/3; //left
	CurrentB = (float)gEncoderVal_right/3; //right
	Motor_Left  = (int)PWM_Limit(PID_A(CurrentA,targetA),Limit, -Limit);
	Motor_Right = (int)PWM_Limit(PID_B(CurrentB,targetB),Limit, -Limit);		//PWM限幅
    if(m==18) 
    {
        Set_Pwm(1,1);
        timbegin=0;
    }
	else Set_Pwm(Motor_Left, Motor_Right);
}

// 加权质心巡线：对所有压线传感器做加权平均，输出连续差速值
// gain: 增益系数，值越大转向越激进
// 返回: 正=右转，负=左转，0=未检测到线
float xunji_centroid(float gain)
{
    int32_t sum = 0;
    int32_t cnt = 0;

    if (P1) { sum += -7; cnt++; }
    if (P2) { sum += -5; cnt++; }
    if (P3) { sum += -3; cnt++; }
    if (P4) { sum += -1; cnt++; }
    if (P5) { sum +=  1; cnt++; }
    if (P6) { sum +=  3; cnt++; }
    if (P7) { sum +=  5; cnt++; }
    if (P8) { sum +=  7; cnt++; }

    if (cnt == 0) return 0.0f;
    return -(float)sum / cnt * gain;
}

//左/A轮PID
float PID_A(float Encoder,float Target)
{
	static float Bias, Last_bias, Last2_bias, Pwm;
	Bias = Target - Encoder;               																		//计算偏差
	Pwm += Kp1 * (Bias - Last_bias) + Ki1 * Bias + Kd1 * (Bias - 2 * Last_bias + Last2_bias);   									//增量式PI控制器
	Last_bias = Bias;	                   																			//保存上一次偏差
	Last2_bias = Last_bias;
	return Pwm;                        				                                        					//返回增量值
}

//右/B轮PID
float PID_B(float Encoder,float Target)
{
	static float Bias, Last_bias, Last2_bias, Pwm;
	Bias = Target-Encoder;               																		//计算偏差
	Pwm += Kp1 * (Bias - Last_bias) + Ki1 * Bias + Kd1 * (Bias - 2 * Last_bias + Last2_bias);   									//增量式PI控制器
	Last_bias = Bias;	                   																			//保存上一次偏差
	Last2_bias = Last_bias;
	return Pwm;
}

void Set_Pwm(int motor_left,int motor_right)
{
	if(motor_left > 0)	//前进
	{
        AIN11;
		AIN20;
	}
	else				//后退
	{
		AIN10;
		AIN21;
	}
	//PWMA = myabs(motor_left);
    set_Duty(myabs(motor_left),0);

	if(motor_right > 0) //前进
	{
		BIN11;
		BIN20;
	}
	else				//后退
	{
        BIN10;
		BIN21;
	}
	//PWMB = myabs(motor_right);
    set_Duty(myabs(motor_right),1);
}

void set_Duty(uint8_t duty,uint8_t channel)               //修改pwm波占空比  0~100                 //用timer不要用timerg或timera
{
    uint32_t CompareValue;
    CompareValue = 2500 - 2500/100*duty;                  //占空比转换

    if(channel == 0)
    {
        DL_Timer_setCaptureCompareValue(PWM_0_INST,CompareValue,DL_TIMER_CC_0_INDEX);           //修改占空比
    }
    else if(channel == 1)
    {
        DL_Timer_setCaptureCompareValue(PWM_0_INST,CompareValue,DL_TIMER_CC_1_INDEX);           
    }
}

void GROUP1_IRQHandler(void)                    //中断服务函数
{
    /**********************编码器读取***********************/
    gpioA = DL_GPIO_getEnabledInterruptStatus(GPIOA,GPIO_EncoderA_PIN_0_PIN | GPIO_EncoderA_PIN_1_PIN);
    gpioB = DL_GPIO_getEnabledInterruptStatus(GPIOB,GPIO_EncoderB_PIN_2_PIN | GPIO_EncoderB_PIN_3_PIN);
    if((gpioA & GPIO_EncoderA_PIN_0_PIN) == GPIO_EncoderA_PIN_0_PIN)
    {
        //Pin0上升沿
        if(!DL_GPIO_readPins(GPIOA,GPIO_EncoderA_PIN_1_PIN))//P1为高电平
        {
            gEncoderCount_left--;
        }
        else//P1为低电平
        {
            gEncoderCount_left++;
        }
    }
    else if((gpioA & GPIO_EncoderA_PIN_1_PIN) == GPIO_EncoderA_PIN_1_PIN)
    {
        //Pin1上升沿
        if(!DL_GPIO_readPins(GPIOA,GPIO_EncoderA_PIN_0_PIN))//P0为高电平
        {
            gEncoderCount_left++;
        }
        else//P1为低电平
        {
            gEncoderCount_left--;
        }
    }

    if((gpioB & GPIO_EncoderB_PIN_2_PIN) != 0)
    {
        if(!DL_GPIO_readPins(GPIOB,GPIO_EncoderB_PIN_3_PIN))
        {
            gEncoderCount_right--;
        }
        else
        {
            gEncoderCount_right++;
        }
    }
    else if((gpioB & GPIO_EncoderB_PIN_3_PIN) != 0)
    {
        if(!DL_GPIO_readPins(GPIOB,GPIO_EncoderB_PIN_2_PIN))
        {
            gEncoderCount_right++;
        }
        else
        {
            gEncoderCount_right--;
        }
    }
    DL_GPIO_clearInterruptStatus(GPIOA, GPIO_EncoderA_PIN_0_PIN|GPIO_EncoderA_PIN_1_PIN);
    DL_GPIO_clearInterruptStatus(GPIOB, GPIO_EncoderB_PIN_2_PIN|GPIO_EncoderB_PIN_3_PIN);
    /*********************************************************************************************/
}

void TIMER_Encoder_Read_INST_IRQHandler(void)                   //定时中断
{
    switch (DL_TimerG_getPendingInterrupt(TIMER_Encoder_Read_INST)){            //100ms定时，将编码器数据存入val
        case DL_TIMER_IIDX_ZERO:
            gEncoderVal_left = gEncoderCount_left;                              //读取左轮编码器数据
            gEncoderCount_left = 0;
            gEncoderVal_right = gEncoderCount_right;                            //读取右轮编码器数据
            gEncoderCount_right = 0;
            // printf("%d %d %d\r\n",gEncoderVal_left,gEncoderVal_right,xunji());
            if (timebegin==1)
            {
                if (timenum==2)
                {
                    whiteflag=1;
                    timebegin=0;
                    timenum=0;
                }
                timenum++;
            }

            // if (timebegin1==1)
            // {
            //     if (timenum1==1)
            //     {
            //         whiteflag1=1;
            //         timebegin1=0;
            //         timenum1=0;
            //     }
            //     timenum1++;
            // }

            if (ledbegin==1)
            {
                ledflag=1;
                if (lednum==10)
                {
                    ledflag=0;
                    ledbegin=0;
                    lednum=0;
                }
                lednum++;
            }
            break;
        default:
            break;
    }
}

void TIMER_0_INST_IRQHandler(void)
{
    switch (DL_TimerG_getPendingInterrupt(TIMER_0_INST))
    {
        case DL_TIMER_IIDX_ZERO:

            if (dirt_ignore_ticks>0) dirt_ignore_ticks--;
            if (timebegin1==1)
            {
                if (timenum1==3)
                {
                    whiteflag1=1;
                    timebegin1=0;
                    timenum1=0;
                }
                timenum1++;
            }

            if (timebegin2==1)
            {
                if (timenum2==19)
                {
                    whiteflag2=1;
                    timebegin2=0;
                    timenum2=0;
                }
                timenum2++;
            }

            if (timbegin==1)
            {
                tim = tim + 0.01;
            }
            
            break;
        default:
            break;
    }
}

float PWM_Limit(float IN,float max,float min)                   //pwm限幅
{
	float OUT = IN;
	if(OUT > max) OUT = max;
	if(OUT < min) OUT = min;
	return OUT;
}

int myabs(int a)                                                //自定义绝对值函数
{
	int temp;
	if(a < 0)  temp = -a;
	else temp = a;
	return temp;
}


