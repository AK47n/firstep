#include "xunji.h"
#include "motor.h"

/* ===== 2024H 巡线题专用层（mspm0）—— car xunji 真机工程 control.c 移植 =====
 * 移植源：sources/car/car xunji/control.c（原生 mspm0 真机，Debug/PWM.out
 * 编译产物在；2026-08-11 领域建模判据：原生平台真机代码优先）。
 * 真机硬件 → 母版默认外设布局宏映射：
 *   灰度 8 路 GPIO_Gray_1..8 → HUIDU_L3/L2/L1/R1/R2/L4/R3/R4（huidu 模块
 *     索引序，编译级默认，实际接线不同改下方 P1..P8 宏）
 *   电机方向 GPIO_IN_PIN_AIN1/2、BIN1/2 → motor_set_direction（0停1正转2反转）
 *   PWM（真机 TIMG0 2500 计数百分比制）→ motor_set_duty 原始值 0~1300
 *   编码器（真机四倍频正交解码中断）→ key 模块 counter_1_A/counter_2_A
 *     （单沿计数无方向；xunji_tick_50ms 采样清零）
 *   陀螺仪 JY61P（UART2 0x55 帧）→ imu_uart current_attitude.yaw（IMU601，
 *     UART0 CRC16 帧）——不同件，掉头角常量与 Yaw 零偏/极性需上板校准
 *   LED（真机 GPIO_LED PA26）→ LED_BEEP_LED；真机无声光仅 LED（无蜂鸣器）
 *   STBY（真机 PA7）→ 母版硬件直连 3.3V（motor.h），关使能动作省略
 * 编译验证未上板。
 */

/* ---- 灰度 8 路（非零 = 白区，真机极性；26H gray_track_mspm0 同款直读）---- */
#define P1			DL_GPIO_readPins(HUIDU_L3_PORT,HUIDU_L3_PIN)
#define P2			DL_GPIO_readPins(HUIDU_L2_PORT,HUIDU_L2_PIN)
#define P3			DL_GPIO_readPins(HUIDU_L1_PORT,HUIDU_L1_PIN)
#define P4			DL_GPIO_readPins(HUIDU_R1_PORT,HUIDU_R1_PIN)
#define P5			DL_GPIO_readPins(HUIDU_R2_PORT,HUIDU_R2_PIN)
#define P6			DL_GPIO_readPins(HUIDU_L4_PORT,HUIDU_L4_PIN)
#define P7			DL_GPIO_readPins(HUIDU_R3_PORT,HUIDU_R3_PIN)
#define P8			DL_GPIO_readPins(HUIDU_R4_PORT,HUIDU_R4_PIN)

/* ---- 声光：真机 GPIO_LED → 母版 LED_BEEP 组 ---- */
#define LED_ON		DL_GPIO_setPins(LED_BEEP_PORT,LED_BEEP_LED_PIN)
#define LED_OFF		DL_GPIO_clearPins(LED_BEEP_PORT,LED_BEEP_LED_PIN)

volatile int32_t gEncoderVal_left = 0, gEncoderVal_right = 0;          //左右轮编码器记录值，50ms定时采样输出（真机 gEncoderCount 由 key 模块 counter 替代）
extern uint32_t counter_1_A, counter_2_A;                              //key 模块 GPIO 中断累加（符号级 extern，需手动同选 key）
extern Attitude_t current_attitude;                                    //imu_uart 姿态（Yaw 度；真机为 JY61P extern float Yaw，不同件）
#define Yaw current_attitude.yaw                                       //陀螺仪偏转角返回值

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
volatile int pwmstart=1;

static void Set_Pwm(int motor_left, int motor_right);                    //前置声明（定义在文件末尾）

void xunji_init(void)
{
	flag=1; n=1;
	whiteflag=0; whiteflag1=0; whiteflag2=0;
	timebegin=0; timenum=0;
	timebegin1=0; timenum1=0;
	timebegin2=0; timenum2=0;
	ledbegin=0; lednum=0; ledflag=0; ledflag1=0; ledflag2=0;
	m=0; a=0; pwmstart=1;
	gEncoderVal_left=0; gEncoderVal_right=0;
}

void Control_AB(void)                       //模式一
{
    float Speed_Middle=20;				//中值速度
    int Motor_Left, Motor_Right;            //电机赋值
    float bias;
    bias = Yaw;


    if ((P1==0 || P2==0 || P3==0 || P4==0 || P5==0 || P6==0 || P7==0 || P8==0)&&a==0)
    {
        pwmstart=0;
        ledbegin=1;
        a=1;
    }

    if (ledflag==1)
    {
        LED_ON;
    }
    else LED_OFF;

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
    float bias=0;                       //真机为未初始化声明（n%2 恒为 0/1），加 =0 消 -Wall 告警

    if (ledflag==1)//**亮灯指示器
    {
        LED_ON;
    }
    else LED_OFF;

    if (P1!=0 && P2!=0 && P3!=0 && P4!=0 && P5!=0 && P6!=0 && P7!=0 && P8!=0) timebegin=1;
    else whiteflag=0;

    if (whiteflag==1) //**白色区域标记 */
    {
        ledflag2=0;/*清楚巡线标记 */
        if(ledflag1==0)/*若是第一帧进入白色区域，则设立白色区域标志*/
        {
            ledflag1=1;/*第一帧则登记白色区域*/
            ledbegin=1;/*小灯开始*/
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
    }
	else Set_Pwm(Motor_Left, Motor_Right);
}

void Control_ACBDA(void)
{
    float Speed_Middle=20;				//中值速度
    int Motor_Left, Motor_Right;
    float bias=0;                       //真机为未初始化声明（n%2 恒为 0/1），加 =0 消 -Wall 告警

    if (ledflag==1) LED_ON;
    else LED_OFF;



    if (P1!=0 && P2!=0 && P3!=0 && P4!=0 && P5!=0 && P6!=0 && P7!=0 && P8!=0) timebegin1=1;/*初步认定白区*/
    else whiteflag1=0;/*不是白区*/

    if (whiteflag1==1) /*白区*/
    {
        ledflag2=0;/*黑区标志清0*/
        if(ledflag1==0)
        {
            ledflag1=1;
            ledbegin=1;
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
    }
	else Set_Pwm(Motor_Left, Motor_Right);
}

void Control_ACBDAx4(void)
{
    float Speed_Middle=20;				//中值速度
    int Motor_Left, Motor_Right;
    float bias=0;                       //真机为未初始化声明（n%2 恒为 0/1），加 =0 消 -Wall 告警

    /* 真机 m==18 时 DL_GPIO_clearPins(GPIO_STBY...) 关电机使能；母版 STBY
     * 硬件直连 3.3V（motor.h），省略。m==18 停车判据保留（下方 Set_Pwm(1,1)）。 */

    if (ledflag==1) LED_ON;
    else LED_OFF;

    if (P1!=0 && P2!=0 && P3!=0 && P4!=0 && P5!=0 && P6!=0 && P7!=0 && P8!=0) timebegin2=1;
    else whiteflag2=0;

    if (whiteflag2==1)
    {
        ledflag2=0;
        if(ledflag1==0)
        {
            ledflag1=1;
            ledbegin=1;
            m++;
        }

        if (n%2==0)
        {
            bias = Yaw + 103;
        }
        else if(n%2==1)
        {
            bias = Yaw;
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

// 真机 Set_Pwm：百分比制占空比（0~100，Limit=200 限幅后超 100 饱和）→ mspm0
// motor 模块原始占空比 0~1300（MAX_DUTY 对偶 pid_mspm0，13 = 1300/100）。
// 方向：正→motor_set_direction(id,1) 正转，负→2 反转（0停1正转2反转）。
#define XUNJI_MAX_DUTY  1300
static void Set_Pwm(int motor_left,int motor_right)
{
    if(motor_left > 0)		motor_set_direction(1, 1);		//前进
    else					motor_set_direction(1, 2);		//后退
    motor_set_duty(1, (uint32_t)(myabs(motor_left) * XUNJI_MAX_DUTY / 100));

    if(motor_right > 0)		motor_set_direction(2, 1);		//前进
    else					motor_set_direction(2, 2);		//后退
    motor_set_duty(2, (uint32_t)(myabs(motor_right) * XUNJI_MAX_DUTY / 100));
}

/* 50ms 周期任务（真机 TIMER_Encoder_Read_INST_IRQHandler）：编码器采样 +
 * 白区消抖（模式一 100ms）+ LED 时序（500ms）。 */
void xunji_tick_50ms(void)
{
    gEncoderVal_left = (int32_t)counter_1_A;                    //读取左轮编码器数据
    counter_1_A = 0;
    gEncoderVal_right = (int32_t)counter_2_A;                   //读取右轮编码器数据
    counter_2_A = 0;

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
}

/* 10ms 周期任务（真机 TIMER_0_INST_IRQHandler）：模式二/三白区消抖。 */
void xunji_tick_10ms(void)
{
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
