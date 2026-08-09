#include "headfile.h"
#include "pid.h"
#include "motor.h"
#include "gray_track.h"
#include "ml_mpu6050.h"
#include "digit_uart.h"
#include <stdio.h>
#include <math.h>
// ===== 集中宏定义区（所有可调参数集中于此，方便修改）=====

// --- 路径记忆 ---
#define PATH_MAX_CROSSROADS  8           // 路径记忆最大容量
#define MAX_CROSSROADS        8           // 路由表最大路口数

// --- 十字路口动作 ---
#define CROSS_ACTION_LEFT      0
#define CROSS_ACTION_RIGHT     1
#define CROSS_ACTION_STRAIGHT  2
#define CROSS_ACTION_NONE     -1

// --- 药房/病房到达延迟 ---
#define PHARMACY_CHECK_DELAY  50          // 50周期 x 10ms = 500ms

// --- K230 第2路口识别 ---
#define K230_RECOG_WINDOW  100            // 第2路口识别窗口(100x10ms=1000ms)

// --- 电机左右轮速度校准 ---
#define MOTOR_A_SCALE     1.40f           // 左轮速度缩放（>1=补偿弱侧）
#define MOTOR_B_SCALE     0.70f           // 右轮速度缩放（>1=补偿弱侧）

// --- 开环参数（兼容保留）---
#define DUTY_SCALE   1000
#define TURN_GAIN    400

// --- 速度闭环 + 转弯参数 ---
#define BASE_SPEED        15.0f           // 基础速度（编码器计数/10ms）
#define FAST_BASE_SPEED   25.0f           // 快速接近模式基础速度
#define TURN_DUTY      6000               // 转弯时正转轮占空比（12%）
#define TURN_DUTY_REV  10000              // 转弯时反转轮占空比（20%）
#define GO_STRAIGHT_MS   200              // 检测到交叉口后直行时间(ms)
#define GO_STRAIGHT_MS_FAR_LEFT   200     // 远端左转直行时间(ms)
#define GO_STRAIGHT_MS_FAR_RIGHT  200     // 远端右转直行时间(ms)
#define GO_STRAIGHT_MS_K230_LEFT  200     // 第2路口K230左转直行时间(ms)
#define GO_STRAIGHT_MS_K230_RIGHT 200     // 第2路口K230右转直行时间(ms)
#define TURN_MAX_MS     3000              // 转弯安全超时(ms)
#define COOLDOWN_MS     800               // 转弯完成后冷却时间(ms)
#define TURN_TARGET_DEG 60.0f             // 目标转角（常规/小T/大T路口共用）
#define PHARMACY_TURN_DEG 160.0f          // 药房掉头目标转角

// --- 调试开关 ---
#define DEBUG_STOP_AFTER_TURN  0          // 1=转弯后永久停车观察角度
#define DEBUG_TURN_ON_ALL_WHITE  0        // 1=全白触发转弯（无场地时调试用）

// --- 药房/病房 PB5 药物检测消抖 ---
#define PB5_LIFT_STABLE  5                // 连续5次检测稳定=50ms确认

// --- 远端导航（大T + 小T路口）---
#define FAR_Y_CENTER             110      // Y-center阈值：第2路口/小T用
#define FAR_Y_CENTER_LARGE_T     110      // 大T路口专用Y-center阈值
#define FAR_Y_TOLERANCE          100      // Y坐标中心容差（像素）
#define FAR_Y_STABLE_CNT    5             // Y-center稳定帧数（5x10ms=50ms）
#define FAR_SCAN_DEG        10.0f         // 左转扫描Q3角度
#define FAR_RECOG_WINDOW    100           // 远端识别窗口周期数（100x10ms=1000ms）
#define FAR_RECOG_WARMUP    5             // 识别窗口预热帧数
#define FAR_TURN_TARGET_DEG 70.0f         // 大T字路口转弯目标角度（独立于常规路口）
#define YCENTER_SUPPRESS_CYCLES  25       // 转弯后Y-center抑制周期数（25x10ms=0.25s）

// --- 远端返程 ---
#define FAR_RET_TCROSS_STABLE_CNT  3      // 返程T字路口检测消抖次数

// --- 启动斜坡 ---
#define RAMP_CYCLES  50                   // 50周期x10ms=500ms完成加速

// --- PD 巡线参数 ---
#define GYRO_DAMP_GAIN   0                // 陀螺前馈增益（0=关闭）
#define LINE_DEADBAND    0.5f             // 死区阈值
#define LINE_PID_OUT_MAX 6.0f             // 轮速差上限
#define RETURN_ARRIVE_SPEED_RATIO  0.40f  // 返程到站前降速至40%

// --- OLED 大字格式化（8字符填充）---
#define FMT8(buf, str) do { \
    int _i; \
    for (_i = 0; _i < 8 && (str)[_i]; _i++) (buf)[_i] = (str)[_i]; \
    for (; _i < 8; _i++) (buf)[_i] = ' '; \
    (buf)[8] = '\0'; \
} while(0)


pid_t motorA;
pid_t motorB;
pid_t angle;
pid_t line_pid;

// ===== OLED 调试缓冲区（ISR 只写内存，主循环负责刷 I2C）=====
char oled_line1[32] = "";
char oled_line2[32] = "";
char oled_line3[32] = "";
char oled_line4[32] = "";
volatile int oled_dirty = 0;  // 主循环检查此标志，为1时刷新OLED

// ===== 小车全局状态 =====
int car_started         = 0;  // 药物放上(PB5=HIGH)后置1，启动巡线
int motor_test_mode     = 0;  // 电机测试模式：1=跳过pid_control，由main直接控制
int dest_index     = 0;  // 目的地编号（1/2/3...），0=未锁定
int cross_count    = 0;  // 已处理的十字路口计数（去程）
int route_complete = 0;  // 路由表执行完毕，后续十字路口忽略
static int cross_action = -1;  // 当前十字路口的动作（LEFT/RIGHT/STRAIGHT）
int in_pharmacy         = 0;  // 已到达病房，停止一切动作

// ===== 路径记忆系统（返程用）=====
static int path_memory[PATH_MAX_CROSSROADS];  // 记录去程每个十字路口的动作
static int path_len      = 0;  // 去程经过的十字路口总数
int return_mode          = 0;  // 1=返程模式
static int return_index  = 0;  // 返程已处理的十字路口计数
int all_return_done      = 0;  // 返程所有路口已处理完，准备进起始区
static int return_arrived = 0; // 到达出发点锁存：1=已到达停车，防止传感器噪声导致重启

// 全白检测延迟：左转完成后延迟N个周期再开始检测全白（防误触发）
static int pharmacy_delay_cnt = 0;
static int fast_approach = 0;           // 快速接近模式：1=使用高速，0=正常速度
static int fast_approach_init_done = 0; // 快速接近一次性初始化标记

// ===== K230动态路口决策 =====
// 识别窗口：路由表下一路口为K230_DECIDE时（dest≥3），上一路口冷却结束后开启，决策被消费时关闭
// 锁定逻辑：窗口内持续记录每个数字出现过的最高置信度及该帧cx，
//         取"置信度最高的两个数字"为锁定结果（随观测持续刷新，路口到达时以最终top2为准）；
//         若其中包含dest → 按dest的cx位置左/右转，否则直行（dest=1/2病房位置固定，不识别）
int recognition_active = 0;   // 1=识别窗口激活中
int k230_turn_ready   = 0;   // 1=K230决策已就绪（窗口内已见≥2个不同数字）
int k230_turn_result  = -1;  // 决策结果: CROSS_ACTION_LEFT / CROSS_ACTION_RIGHT / CROSS_ACTION_STRAIGHT
static float cand_conf[9] = {0};    // 数字1~8窗口内出现过的最高置信度（0=未见过）
static int   cand_cx[9]   = {0};    // 最高置信度那一帧的cx
static int   top_digit[2] = {0, 0}; // 当前置信度最高的两个数字（0=无），[0]为最高
static int recog_warmup = 0; // 识别窗口预热计数：跳过窗口开启后的前N帧旧数据

// ===== 第2路口K230 Y-center逼近停车+识别 =====
// 巡线逼近到Y-center位置 → 停车并立即开识别窗口（停车=识别，不再分两段），
// 识别1秒后锁存决策，继续巡线等物理路口
static int k230_approach_state = 0;  // 0=空闲 1=巡线逼近 2=停车+识别窗口（已合并，3=废弃）
static int k230_approach_cnt = 0;    // 通用计数器
static int k230_y_stable_cnt = 0;    // Y-center稳定帧计数
static int k230_decision_ready = 0;  // 1=Y-center识别已完成，等待物理路口触发转弯
static int k230_saved_action = -1;   // 识别窗口锁定的决策结果
static int k230_is_second_turn = 0;  // 1=当前转弯来自第2路口K230决策，用于区分直行延迟

// 关闭识别窗口并清空候选记录（未启动重置/守卫失败/决策消费/窗口重开前 共用）
static void k230_window_reset(void)
{
    int j;
    recognition_active = 0;
    k230_turn_ready   = 0;
    k230_turn_result  = -1;
    for (j = 0; j <= 8; j++) { cand_conf[j] = 0.0f; cand_cx[j] = -1; }
    top_digit[0] = top_digit[1] = 0;
    recog_warmup = 0;
}

void datavision_send()  // 虚拟示波器发送函数（调试编码器速度）
{
	// 数据包头
	uart_sendbyte(UART_1, 0x03);
	uart_sendbyte(UART_1, 0xfc);

	// 发送编码器实测速度（uint8_t，范围0~255），用于校准BASE_SPEED
	uart_sendbyte(UART_1, (uint8_t)motorA.now);   // 通道1：A轮实测速度
	uart_sendbyte(UART_1, (uint8_t)motorA.target);// 通道2：A轮目标速度
	uart_sendbyte(UART_1, (uint8_t)motorB.now);   // 通道3：B轮实测速度
	uart_sendbyte(UART_1, (uint8_t)motorB.target);// 通道4：B轮目标速度

	// 数据包尾
	uart_sendbyte(UART_1, 0xfc);
	uart_sendbyte(UART_1, 0x03);
}


void pid_init(pid_t *pid, uint32_t mode, float p, float i, float d)
{
	pid->pid_mode = mode;
	pid->p = p;
	pid->i = i;
	pid->d = d;
	// 清零PID状态，防止残留值导致飞车
	pid->target = 0;
	pid->now = 0;
	pid->error[0] = 0;
	pid->error[1] = 0;
	pid->error[2] = 0;
	pid->pout = 0;
	pid->iout = 0;
	pid->dout = 0;
	pid->out = 0;
}

// 左右轮速度校准：线偏右(56之间) → PID在右转纠偏 → 车天然左转 → 右轮偏强/左轮偏弱

void motor_target_set(float spe1, float spe2)
{
	if(spe1 >= 0)
	{
		motorA_dir = 0;        // 正转
		motorA.target = spe1 * MOTOR_A_SCALE;
	}
	else
	{
		motorA_dir = 1;        // 反转
		motorA.target = -spe1 * MOTOR_A_SCALE;
	}

	if(spe2 >= 0)
	{
		motorB_dir = 0;        // 正转
		motorB.target = spe2 * MOTOR_B_SCALE;
	}
	else
	{
		motorB_dir = 1;        // 反转
		motorB.target = -spe2 * MOTOR_B_SCALE;
	}
}


// 开环参数：调这两个改速度
// （速度闭环启用后，DUTY_SCALE/TURN_GAIN 不再用于巡线，仅保留以备兼容）

// ===== 速度闭环参数 =====

// 交叉口状态机
enum { CROSS_NORMAL, CROSS_STRAIGHT, CROSS_TURN, CROSS_COOLDOWN };
int cross_state = CROSS_NORMAL;
int cross_cnt = 0;
int turn_dir = 0;  // 0=左转  1=右转
int cross_turn_phase = 0;  // 转弯封装函数阶段: 0=直行, 1=旋转

// 调试开关：1=转弯完成后永久停车（方便读OLED角度），0=正常进入冷却继续巡线
int turn_debug_stop = 0;   // 置1后小车停止不再动作，OLED继续刷新

// 陀螺仪积分角转弯检测（yaw_gyro，不用磁融合的yaw_Kalman）
static float turn_start_yaw = 0.0f;  // 转弯起始积分角

// 设置转弯方向（在主循环或按键中调用）
void set_turn_dir(int dir) { turn_dir = dir; }

// ===== 转弯动作封装函数 =====
// 左转（两阶段：先直行GO_STRAIGHT_MS到路口中心，再原地旋转TURN_TARGET_DEG=60°）
// 返回: 0=直行中(PID控速), 1=旋转中(开环TURN_DUTY), 2=完成
static int turn_left_70(int *phase, int *cnt, float *start_yaw) {
    if (*phase == 0) {
        motor_target_set(BASE_SPEED, BASE_SPEED);
        if (--(*cnt) <= 0) { *phase = 1; *cnt = TURN_MAX_MS / 10; *start_yaw = yaw_gyro; }
        return 0;
    }
    motorA_dir = 1; motorB_dir = 0;
    motorA_duty(TURN_DUTY_REV); motorB_duty(TURN_DUTY);  // 反转轮补偿更高占空比
    float delta = fabs(yaw_gyro - *start_yaw);
    return (delta >= TURN_TARGET_DEG || --(*cnt) <= 0) ? 2 : 1;
}
// 右转（两阶段：先直行GO_STRAIGHT_MS到路口中心，再原地旋转TURN_TARGET_DEG=60°）
static int turn_right_70(int *phase, int *cnt, float *start_yaw) {
    if (*phase == 0) {
        motor_target_set(BASE_SPEED, BASE_SPEED);
        if (--(*cnt) <= 0) { *phase = 1; *cnt = TURN_MAX_MS / 10; *start_yaw = yaw_gyro; }
        return 0;
    }
    motorA_dir = 0; motorB_dir = 1;
    motorA_duty(TURN_DUTY); motorB_duty(TURN_DUTY_REV);  // 反转轮补偿更高占空比
    float delta = fabs(yaw_gyro - *start_yaw);
    return (delta >= TURN_TARGET_DEG || --(*cnt) <= 0) ? 2 : 1;
}
// 左掉头（单阶段：原地旋转PHARMACY_TURN_DEG=160°，病房已停车无需直行）
// 返回: 0=旋转中, 1=完成
static int turn_left_200(float start_yaw, int *cnt) {
    motorA_dir = 1; motorB_dir = 0;
    motorA_duty(TURN_DUTY_REV); motorB_duty(TURN_DUTY);  // 反转轮补偿更高占空比
    float delta = fabs(yaw_gyro - start_yaw);
    return (delta >= PHARMACY_TURN_DEG || --(*cnt) <= 0);
}
// 右掉头（单阶段：原地旋转PHARMACY_TURN_DEG=160°，病房已停车无需直行）
static int turn_right_200(float start_yaw, int *cnt) {
    motorA_dir = 0; motorB_dir = 1;
    motorA_duty(TURN_DUTY); motorB_duty(TURN_DUTY_REV);  // 反转轮补偿更高占空比
    float delta = fabs(yaw_gyro - start_yaw);
    return (delta >= PHARMACY_TURN_DEG || --(*cnt) <= 0);
}

// ===== K230动态路口决策函数 =====
// 算法（top2置信度制）：
//   1. 窗口内每帧扫描：刷新每个数字（cx在[150,1050]内）出现过的最高置信度及该帧cx
//   2. 每周期取置信度最高的两个数字作为锁定结果，持续刷新直到路口到达：
//      - dest在top2中：dest的cx较小→左转，较大→右转
//      - dest不在top2中：直行（继续前进）
static void k230_check_and_decide(void)
{
    int i;
    int d1, d2;

    if (!recognition_active)
        return;

    // 预热期：等待digit_uart_flush后的新帧到达，跳过旧数据
    if (recog_warmup > 0)
    {
        recog_warmup--;
        return;
    }

    if (dest_index < 3 || dest_index > 8)   // dest=1/2病房位置固定，无需识别
    {
        k230_window_reset();
        return;
    }

    // 遍历当前帧：刷新每个数字的最高置信度记录（cx<150或>1050忽略）
    for (i = 0; i < digit_result.count && i < MAX_DIGITS; i++)
    {
        char ch    = digit_result.digits[i].label[0];
        int  cx    = digit_result.digits[i].cx;
        float conf = digit_result.digits[i].confidence;

        if (digit_result.digits[i].label[1] != '\0') continue;   // 只接受单字符标签
        if (ch < '1' || ch > '8') continue;                      // 只接受数字1~8
        if (cx < 150 || cx > 1050) continue;                     // 边缘误检过滤

        if (conf > cand_conf[ch - '0'])
        {
            cand_conf[ch - '0'] = conf;
            cand_cx[ch - '0']   = cx;
        }
    }

    // 选出置信度最高的两个数字（d1最高，d2次高，0=无）
    d1 = 0; d2 = 0;
    for (i = 1; i <= 8; i++)
    {
        if (cand_conf[i] <= 0.0f) continue;
        if (d1 == 0 || cand_conf[i] > cand_conf[d1])      { d2 = d1; d1 = i; }
        else if (d2 == 0 || cand_conf[i] > cand_conf[d2]) { d2 = i; }
    }
    top_digit[0] = d1;   // 供OLED显示
    top_digit[1] = d2;

    // 窗口内出现过的数字不足两个 → 决策未就绪（路口到达时走兜底）
    if (d2 == 0)
    {
        k230_turn_ready = 0;
        return;
    }

    // top2就绪 → 计算决策（持续刷新，路口消费时取最终值）
    if (dest_index == d1)
        k230_turn_result = (cand_cx[d1] < cand_cx[d2]) ? CROSS_ACTION_LEFT : CROSS_ACTION_RIGHT;
    else if (dest_index == d2)
        k230_turn_result = (cand_cx[d2] < cand_cx[d1]) ? CROSS_ACTION_LEFT : CROSS_ACTION_RIGHT;
    else
        k230_turn_result = CROSS_ACTION_STRAIGHT;  // 不包含dest → 继续前进

    k230_turn_ready = 1;
}

// ===== 药房送达状态机 =====
// 简化版：检测PB5抬起后直接旋转PHARMACY_TURN_DEG=160°掉头返回
enum { PHARMACY_WAIT_LIFT, PHARMACY_TURN180, PHARMACY_COOLDOWN, PHARMACY_DONE };
int pharmacy_state = PHARMACY_WAIT_LIFT;

// PB5药物检测消抖计数
static int pb5_lift_cnt = 0;

// 药房转弯专用计数器（避免与cross_cnt冲突）
static int pharmacy_cnt = 0;

// ===== 远端导航（大T字路口 + 小T字路口）=====
// dest=3~8在第2路口K230决策直行后激活：第2路口锁定的2个中部病房 ≠ dest
// 剩余4个病房由"大T字路口→两个小T字路口"结构构成
// 大T：Q3/Q4各2张牌 → 左转10°扫Q3 → 排除法推Q4 → 左/右转进分支
// 小T：Q3/Q4各1张牌 → 识别后左/右转进病房 → 到达药房

// 保存第2路口K230锁定的中部2个病房号（用于排除法）
static int central_wards[2] = {0, 0};
static int far_nav_pending = 0;   // 第2路口直行后标记远端导航待激活

// 排除法：剩余4个远端病房号 = {3,4,5,6,7,8} - central_wards
static int far_remaining[4] = {0};

// 大T字路口：Q3识别到的2张卡牌号码
static int far_q3_cards[2] = {0};
// 大T字路口：Q4推导卡牌 = far_remaining - far_q3_cards
static int far_q4_cards[2] = {0};

// 小T字路口：Q3(左)和Q4(右)各1张卡牌
static int far_small_left  = 0;
static int far_small_right = 0;

// 远端导航状态机
enum {
    FAR_NONE = 0,
    FAR_LARGE_T_APPROACH,       // 前进中，监控K230 cy坐标 → Y-center停车
    FAR_LARGE_T_STOPPED,        // 短暂停车稳定
    FAR_LARGE_T_SCAN_LEFT,      // 左转10°使Q3卡牌进入视野
    FAR_LARGE_T_RECOGNIZE,      // ★先flush清旧数据，再开识别窗口锁定Q3的2张牌
    FAR_LARGE_T_TURN_BACK,      // 右转10°回正
    FAR_LARGE_T_TO_JUNCTION,    // ★巡线前进到物理路口，检测cross_detect
    FAR_LARGE_T_TURN,           // 70°转弯进分支（dest在Q3→左转，在Q4→右转）
    FAR_LARGE_T_COOLDOWN,       // 转弯后冷却 → 进小T干路
    FAR_SMALL_T_APPROACH,       // 驶向小T字路口（巡线+监控K230 cy）
    FAR_SMALL_T_STOPPED,        // 停车+识别（停车即flush开窗口，识别1秒，不再分两段）
    FAR_SMALL_T_RECOGNIZE,      // ★已废弃：识别已合并到FAR_SMALL_T_STOPPED中
    FAR_SMALL_T_TO_JUNCTION,    // ★巡线前进到物理路口（先巡线再转弯）
    FAR_SMALL_T_TURN,           // 小T路口转弯进病房
    FAR_SMALL_T_COOLDOWN,       // 转弯后冷却 → 进入药房检测
};
int far_state = FAR_NONE;
int far_nav_active = 0;

// 远端导航参数

static int far_cnt = 0;              // 通用计数器
static float far_turn_start_yaw = 0.0f;  // 转弯起始陀螺角
static int far_y_stable_cnt = 0;     // ★Y-center稳定帧计数（文件级，far_nav_init可重置）
static int far_y_miss_cnt = 0;       // ★连续未命中计数（连续N帧未命中才清零stable_cnt）
static int far_y_timeout_cnt = 0;    // ★Y-center超时计数（文件级，far_nav_init可重置）
static int ycenter_suppress_cnt = 0; // ★转弯后Y-center抑制计数：0=允许，>0=禁止（YCENTER_SUPPRESS_CYCLES×10ms）
static int far_turn_dir = 0;         // 0=左转 1=右转
static int far_large_turn_phase2 = 0; // ★大T转弯阶段标记：0=直行阶段，1=转弯阶段
static int far_small_turn_phase2 = 0; // ★小T转弯阶段标记：0=直行阶段，1=转弯阶段

// ===== 远端返程导航（小T + 大T路口返程）=====
// 去程经远端导航到达药房后，返程需按原路返回。
// 返程时从支路方向接近T字路口，灰度传感器仅能识别4~5个黑线，
// 无法触发常规t_cross_detect(≥6)，故使用ret_t_cross_detect(≥4)+消抖。
int far_return_active = 0;                  // 远端返程激活标志
int far_return_state  = 0;                  // 远端返程状态机当前状态
static int far_ret_cnt       = 0;           // 通用计数器
static int far_ret_turn_phase = 0;          // 转弯阶段标记: 0=直行过路口中心, 1=旋转
static float far_ret_turn_start_yaw = 0.0f; // 转弯起始陀螺角
static int far_ret_turn_dir  = 0;           // 返程转弯方向: 0=左转, 1=右转

// 保存去程大T/小T的转弯方向（返程时翻转使用：0↔1）
// -1=未使用远端导航（近端/中端病房，无需远端返程）
static int far_large_turn_saved = -1;       // 去程大T转弯: 0=左转进Q3, 1=右转进Q4
static int far_small_turn_saved = -1;       // 去程小T转弯: 0=左转进病房, 1=右转进病房

// 返程T字路口检测消抖（防止巡线中传感器噪声误触发达≥4）
static int far_ret_tcross_stable = 0;

// 远端返程状态机枚举
enum {
    FAR_RET_NONE = 0,
    FAR_RET_TO_SMALL_T,         // 从药房巡线到小T路口（监控ret_t_cross_detect）
    FAR_RET_SMALL_T_TURN,       // 小T路口转弯（反向，回到小T干路）
    FAR_RET_SMALL_T_COOLDOWN,   // 小T转弯后冷却
    FAR_RET_TO_LARGE_T,         // 沿小T干路巡线到大T路口
    FAR_RET_LARGE_T_TURN,       // 大T路口转弯（反向，回到主路）
    FAR_RET_LARGE_T_COOLDOWN,   // 大T转弯后冷却 → 交还标准返程(return_mode)
};

// 远端识别窗口：记录每个数字的最高置信度
static float far_cand_conf[9] = {0};
static int   far_cand_cx[9]   = {0};
static int   far_cand_cx_sum[9] = {0};  // cx 累加和（运行平均）
static int   far_cand_cx_cnt[9] = {0};  // 检测次数（运行平均）

// ===== 远端导航：计算剩余4个病房号 =====
// 排除法：从{3,4,5,6,7,8}中排除已锁定的中部2个病房
// ★安全保护：idx<4防止central_wards含0值时数组越界；
//   若排除后剩余>4个（因中部信息不全），只取前4个（3~6优先）
static void far_calc_remaining(void)
{
    int i, idx = 0;
    for (i = 3; i <= 8 && idx < 4; i++) {
        // ★只排除3~8范围内的有效中部病房号（0=无效，不过滤）
        int is_central = ((i == central_wards[0] && central_wards[0] >= 3 && central_wards[0] <= 8)
                       || (i == central_wards[1] && central_wards[1] >= 3 && central_wards[1] <= 8));
        if (!is_central)
            far_remaining[idx++] = i;
    }
}

// ===== 远端导航：初始化 =====
static void far_nav_init(void)
{
    far_calc_remaining();
    far_nav_active = 1;
    far_state = FAR_LARGE_T_APPROACH;
    far_cnt = 0;
    far_y_stable_cnt = 0;     // ★重置Y-center检测计数器
    far_y_miss_cnt = 0;       // ★重置连续未命中计数
    far_y_timeout_cnt = 0;    // ★重置超时计数器
    far_large_turn_phase2 = 0; // ★重置大T转弯阶段标记
    far_small_turn_phase2 = 0; // ★重置小T转弯阶段标记
    far_q3_cards[0] = far_q3_cards[1] = 0;
    far_q4_cards[0] = far_q4_cards[1] = 0;
    far_small_left  = 0;
    far_small_right = 0;
    digit_uart_flush();  // 清空K230缓冲区，准备接收新帧
}

// ===== 远端导航：重置识别窗口 =====
static void far_recog_reset(void)
{
    int j;
    for (j = 0; j <= 8; j++) { far_cand_conf[j] = 0.0f; far_cand_cx[j] = -1; far_cand_cx_sum[j] = 0; far_cand_cx_cnt[j] = 0; }
}

// ===== 远端导航：识别窗口核心（扫描K230帧，记录每个数字最高置信度）=====
static void far_recog_scan(void)
{
    int i;
    for (i = 0; i < digit_result.count && i < MAX_DIGITS; i++)
    {
        char ch    = digit_result.digits[i].label[0];
        int  cx    = digit_result.digits[i].cx;
        float conf = digit_result.digits[i].confidence;

        if (digit_result.digits[i].label[1] != '\0') continue;
        if (ch < '1' || ch > '8') continue;
        if (cx < 150 || cx > 1050) continue;

        if (conf > far_cand_conf[ch - '0'])
        {
            int idx = ch - '0';
            far_cand_conf[idx] = conf;
            // ★运行平均cx：每次更高置信度的检测都计入平均，抑制单帧噪声
            far_cand_cx_sum[idx] += cx;
            far_cand_cx_cnt[idx]++;
            far_cand_cx[idx] = far_cand_cx_sum[idx] / far_cand_cx_cnt[idx];
        }
    }
}

// ===== 远端导航：从识别结果中取置信度最高的N个数字（返回实际取到的数量）=====
static int far_recog_top_n(int n, int *out)
{
    int i, picked = 0;
    int used[9] = {0};
    while (picked < n) {
        int best = 0;
        float best_conf = -1.0f;
        for (i = 1; i <= 8; i++) {
            if (used[i]) continue;
            if (far_cand_conf[i] > best_conf) {
                best_conf = far_cand_conf[i];
                best = i;
            }
        }
        if (best == 0) break;  // 没有更多数字了
        used[best] = 1;
        out[picked++] = best;
    }
    return picked;
}

// ===== 远端导航：小T字路口实时计算左右分配 =====
// 在识别窗口内每周期调用，根据当前已累积的最高置信度数据实时计算
// 左/右数字和转弯方向，不修改任何全局状态。
// 返回值: 0=暂无有效数据, 1=可计算出结果
static int far_small_realtime_calc(int *out_left, int *out_right, int *out_turn_dir)
{
    int cards[2] = {0, 0};
    int picked = far_recog_top_n(2, cards);
    int left = 0, right = 0, tdir = -1;

    if (picked >= 2)
    {
        // 按cx排序：cx小的=左(Q3)，cx大的=右(Q4)
        if (far_cand_cx[cards[0]] < far_cand_cx[cards[1]])
        {
            left  = cards[0];
            right = cards[1];
        }
        else
        {
            left  = cards[1];
            right = cards[0];
        }
    }
    else if (picked == 1)
    {
        // 只识别到1张牌 → 假设识别到的是左侧，从剩余病房推算右侧
        int i;
        left  = cards[0];
        right = 0;
        for (i = 0; i < 4; i++) {
            if (far_remaining[i] != left) {
                right = far_remaining[i];
                break;
            }
        }
    }
    else
    {
        // 0张牌：无任何数据
        if (out_left)     *out_left     = 0;
        if (out_right)    *out_right    = 0;
        if (out_turn_dir) *out_turn_dir = -1;
        return 0;
    }

    // 决定转弯方向：目标在左侧→左转，在右侧→右转
    tdir = (dest_index == left) ? 0 : 1;  // 0=左转, 1=右转

    if (out_left)     *out_left     = left;
    if (out_right)    *out_right    = right;
    if (out_turn_dir) *out_turn_dir = tdir;
    return 1;
}

// ===== 远端导航：检测是否有数字的cy坐标位于指定Y阈值附近 =====
// y_center: Y-center阈值(像素)，不同路口可传入不同值以调整停车时机
static int far_check_y_center(int y_center)
{
    // ★转弯后0.75s内抑制Y-center检测，防止刚转弯完的误触发
    if (ycenter_suppress_cnt > 0) return 0;

    int i;
    for (i = 0; i < digit_result.count && i < MAX_DIGITS; i++)
    {
        int cy = digit_result.digits[i].cy;
        int cx = digit_result.digits[i].cx;
        // 忽略边缘检测
        if (cx < 150 || cx > 1050) continue;
        {
            int dy = cy - y_center;
            if (dy < 0) dy = -dy;
            if (dy < FAR_Y_TOLERANCE)
                return 1;
        }
    }
    return 0;
}

// ===== 远端导航主状态机（在pid_control中调用，替代常规十字路口逻辑）=====
// 返回值：1=电机已完全处理（调用者应return），0=继续执行速度PID输出

// 前向声明（line_pid_track定义在文件较后位置）
static void line_pid_track(void);

static int far_nav_control(void)
{
    int i;

    switch (far_state)
    {
    // ========== 大T字路口：前进 + cy监控 ==========
    case FAR_LARGE_T_APPROACH:
    {
        // 巡线前进
        line_pid_track();

        // 监控K230：检测数字Y坐标是否到达屏幕中央
        if (digit_result.updated && digit_result.count > 0)
        {
            if (far_check_y_center(FAR_Y_CENTER_LARGE_T))
                far_y_stable_cnt++;
            else if (far_y_stable_cnt > 0)
                far_y_stable_cnt--;
        }

        if (far_y_stable_cnt >= FAR_Y_STABLE_CNT)
        {
            // Y-center稳定 → 停车，进入下一状态
            far_state = FAR_LARGE_T_STOPPED;
            far_cnt = 20;  // 停车200ms稳定
            far_y_stable_cnt = 0;
            far_y_timeout_cnt = 0;
            return 1;  // 电机由下一状态处理
        }

        // ★兜底：Y-center长时间未触发（K230看不到牌/牌位太低）
        //   累计一定周期后，用灰度传感器检测物理T字路口作为触发条件
        //   防止小车一直巡线驶出地图
        far_y_timeout_cnt++;
        if (far_y_timeout_cnt > 200)  // 2秒后启动兜底检测
        {
            if (t_cross_detect())
            {
                // ★物理路口兜底触发 → 停车，跳过Y-center，直接进行扫描
                far_state = FAR_LARGE_T_STOPPED;
                far_cnt = 20;
                far_y_stable_cnt = 0;
                far_y_timeout_cnt = 0;
                return 1;
            }
        }

        return 0;  // 继续速度PID输出
    }

    // ========== 大T字路口：短暂停车 ==========
    case FAR_LARGE_T_STOPPED:
        motorA_duty(0);
        motorB_duty(0);
        if (--far_cnt <= 0)
        {
            // 开始左转10°扫描Q3
            far_state = FAR_LARGE_T_SCAN_LEFT;
            far_cnt = TURN_MAX_MS / 10;
            far_turn_start_yaw = yaw_gyro;
        }
        return 1;

    // ========== 大T字路口：左转10°扫描Q3 ==========
    case FAR_LARGE_T_SCAN_LEFT:
    {
        // 左转：左轮反转、右轮正转（反转轮补偿更高占空比）
        motorA_dir = 1;
        motorB_dir = 0;
        motorA_duty(TURN_DUTY_REV);
        motorB_duty(TURN_DUTY);

        float delta = fabs(yaw_gyro - far_turn_start_yaw);
        if (delta >= FAR_SCAN_DEG || --far_cnt <= 0)
        {
            // 转到位 → 停车 → ★先flush清空旧帧，再重置识别窗口
            motorA_duty(0);
            motorB_duty(0);
            digit_uart_flush();       // ★丢弃转弯前/转弯中的旧帧
            far_recog_reset();        // ★清零旧识别数据
            far_state = FAR_LARGE_T_RECOGNIZE;
            far_cnt = FAR_RECOG_WINDOW + FAR_RECOG_WARMUP;  // 预热+识别窗口
        }
        return 1;
    }

    // ========== 大T字路口：识别Q3的2张卡牌 ==========
    case FAR_LARGE_T_RECOGNIZE:
    {
        motorA_duty(0);
        motorB_duty(0);

        if (far_cnt > FAR_RECOG_WINDOW)
        {
            // 预热期：等待新帧
            far_cnt--;
            return 1;
        }

        // 扫描K230帧
        far_recog_scan();
        far_cnt--;

        if (far_cnt <= 0)
        {
            // 识别窗口结束 → 取置信度最高的2个数字作为Q3卡牌
            int picked = far_recog_top_n(2, far_q3_cards);

            if (picked < 2)
            {
                // 未识别到2张牌 → 兜底填充
                if (picked == 1)
                {
                    // 只识别到1张 → 从剩余病房中取一个补位
                    for (i = 0; i < 4; i++) {
                        if (far_remaining[i] != far_q3_cards[0]) {
                            far_q3_cards[1] = far_remaining[i];
                            break;
                        }
                    }
                }
                else  // picked == 0
                {
                    // 完全失败：默认前两个剩余病房=Q3
                    far_q3_cards[0] = far_remaining[0];
                    far_q3_cards[1] = far_remaining[1];
                }
            }

            // 排除法推Q4：Q4 = far_remaining - Q3
            {
                int q4_idx = 0;
                for (i = 0; i < 4; i++) {
                    int w = far_remaining[i];
                    if (w != far_q3_cards[0] && w != far_q3_cards[1])
                        far_q4_cards[q4_idx++] = w;
                }
            }

            // 转回正向
            far_state = FAR_LARGE_T_TURN_BACK;
            far_cnt = TURN_MAX_MS / 10;
            far_turn_start_yaw = yaw_gyro;
        }
        return 1;
    }

    // ========== 大T字路口：转回正向（右转10°）==========
    case FAR_LARGE_T_TURN_BACK:
    {
        // 右转回去：左轮正转、右轮反转（反转轮补偿更高占空比）
        motorA_dir = 0;
        motorB_dir = 1;
        motorA_duty(TURN_DUTY);
        motorB_duty(TURN_DUTY_REV);

        float delta = fabs(yaw_gyro - far_turn_start_yaw);
        if (delta >= FAR_SCAN_DEG || --far_cnt <= 0)
        {
            // ★转回正向 → 开始巡线前进，驶向物理大T路口
            far_state = FAR_LARGE_T_TO_JUNCTION;
            // 判断dest在Q3还是Q4（转弯方向在此确定）
            {
                int dest_in_q3 = 0;
                for (i = 0; i < 2; i++)
                    if (far_q3_cards[i] == dest_index)
                        dest_in_q3 = 1;
                far_turn_dir = dest_in_q3 ? 0 : 1;  // 0=左转进Q3, 1=右转进Q4
                far_large_turn_saved = far_turn_dir;  // ★保存大T转弯方向（远端返程用）
            }
        }
        return 1;
    }

    // ========== 大T字路口：巡线前进到物理路口 ==========
    case FAR_LARGE_T_TO_JUNCTION:
    {
        line_pid_track();  // 巡线前进

        // 检测物理交叉口（T字路口≥6路黑，十字路口8路全黑）
        if (t_cross_detect())
        {
            // 检测到路口 → 先直行让车轮到达路口中心（左右转可独立调节）
            far_cnt = (far_turn_dir == 0 ? GO_STRAIGHT_MS_FAR_LEFT : GO_STRAIGHT_MS_FAR_RIGHT) / 10;
            far_state = FAR_LARGE_T_TURN;
            return 0;
        }
        return 0;  // 巡线中，速度PID输出
    }

    // ========== 大T字路口：先直行过路口中心 → 再70°转弯进分支 ==========
    case FAR_LARGE_T_TURN:
    {
        int status = (far_turn_dir == 0)
            ? turn_left_70(&far_large_turn_phase2, &far_cnt, &far_turn_start_yaw)
            : turn_right_70(&far_large_turn_phase2, &far_cnt, &far_turn_start_yaw);
        if (status == 2)
        {
            far_state = FAR_LARGE_T_COOLDOWN;
            far_cnt = COOLDOWN_MS / 10;
            far_large_turn_phase2 = 0;
        }
        return (status == 0) ? 0 : 1;  // 直行→PID, 旋转→开环
    }

    // ========== 大T字路口转弯冷却 ==========
    case FAR_LARGE_T_COOLDOWN:
        line_pid_track();  // ★转弯后继续巡线不停车（与普通路口CROSS_COOLDOWN一致），冷却期内仅抑制路口检测
        if (--far_cnt <= 0)
        {
            // 进入小T字路口干路 → 开始前进+监控
            far_state = FAR_SMALL_T_APPROACH;
            far_y_stable_cnt = 0;   // ★重置Y-center检测计数器（小T路口复用）
            far_y_miss_cnt = 0;      // ★重置连续未命中计数
            far_y_timeout_cnt = 0;
            ycenter_suppress_cnt = YCENTER_SUPPRESS_CYCLES;  // ★进入巡线后抑制Y-center误触发（YCENTER_SUPPRESS_CYCLES×10ms）
            digit_uart_flush();
        }
        return 0;  // ★返回0让速度PID运行，与普通路口CROSS_COOLDOWN一致

    // ========== 小T字路口：前进 + cy监控 ==========
    case FAR_SMALL_T_APPROACH:
    {

        line_pid_track();

        if (digit_result.updated && digit_result.count > 0)
        {
            if (far_check_y_center(FAR_Y_CENTER))
            {
                far_y_stable_cnt++;
                far_y_miss_cnt = 0;     // 命中 → 清零连续未命中计数
            }
            else
            {
                far_y_miss_cnt++;
                if (far_y_miss_cnt >= 5)  // 连续5帧未命中 → 重置累积
                {
                    far_y_stable_cnt = 0;
                    far_y_miss_cnt = 0;
                }
            }
        }

        if (far_y_stable_cnt >= FAR_Y_STABLE_CNT)
        {
            far_state = FAR_SMALL_T_STOPPED;
            far_cnt = 100;  // 停车1000ms（1秒）
            far_y_stable_cnt = 0;
            return 1;
        }
        // 兜底超时（与大T路口相同逻辑）
        far_y_timeout_cnt++;
        if (far_y_timeout_cnt > 200)
        {
            if (t_cross_detect())
            {
                far_state = FAR_SMALL_T_STOPPED;
                far_cnt = 100;  // 停车1000ms（1秒）
                far_y_stable_cnt = 0;
                far_y_timeout_cnt = 0;
                return 1;
            }
        }

        return 0;
    }

    // ========== 小T字路口：停车+识别（停车即开始识别，不分两段）==========
    case FAR_SMALL_T_STOPPED:
    {
        motorA_duty(0);
        motorB_duty(0);

        // 第一帧：初始化flush+重置识别窗口
        if (far_cnt == 100)
        {
            far_recog_reset();
            digit_uart_flush();
            far_cnt--;
            return 1;
        }

        // 预热期：等flush后的新帧到达（FAR_RECOG_WARMUP=5帧）
        if (far_cnt > (100 - FAR_RECOG_WARMUP))
        {
            far_cnt--;
            return 1;
        }

        // 识别扫描
        far_recog_scan();
        far_cnt--;

        if (far_cnt <= 0)
        {
            // 取置信度最高的2个数字 → cx小的为左(Q3)，cx大的为右(Q4)
            int cards[2] = {0, 0};
            int picked = far_recog_top_n(2, cards);

            if (picked >= 2)
            {
                // 按cx排序：cx小的=左，cx大的=右
                if (far_cand_cx[cards[0]] < far_cand_cx[cards[1]])
                {
                    far_small_left  = cards[0];
                    far_small_right = cards[1];
                }
                else
                {
                    far_small_left  = cards[1];
                    far_small_right = cards[0];
                }
            }
            else if (picked == 1)
            {
                // 只识别到1张牌 → 假设识别到的是左侧
                far_small_left  = cards[0];
                far_small_right = 0;
                // 从剩余病房中排除
                for (i = 0; i < 4; i++) {
                    if (far_remaining[i] != far_small_left) {
                        far_small_right = far_remaining[i];
                        break;
                    }
                }
            }
            else
            {
                // 兜底：用remaining的前两个
                far_small_left  = far_remaining[0];
                far_small_right = far_remaining[1];
            }

            // 决定转弯方向
            if (dest_index == far_small_left)
                far_turn_dir = 0;  // 左转
        else if (dest_index == far_small_right)
            far_turn_dir = 1;  // 右转
        else
            far_turn_dir = 1;  // 兜底：默认右转
            far_small_turn_saved = far_turn_dir;  // ★保存小T转弯方向（远端返程用）

            // ★ 先巡线到物理路口，再在路口转弯（防止在识别位置就地转弯）
            far_state = FAR_SMALL_T_TO_JUNCTION;
        }
        return 1;
    }

    // ========== 小T字路口：巡线前进到物理路口 ==========
    case FAR_SMALL_T_TO_JUNCTION:
    {
        line_pid_track();  // 巡线前进

        // 检测物理交叉口（T字路口≥6路黑）
        if (t_cross_detect())
        {
            // 检测到路口 → 先直行让车轮到达路口中心（左右转可独立调节）
            far_cnt = (far_turn_dir == 0 ? GO_STRAIGHT_MS_FAR_LEFT : GO_STRAIGHT_MS_FAR_RIGHT) / 10;
            far_turn_start_yaw = yaw_gyro;
            far_state = FAR_SMALL_T_TURN;
            return 0;
        }
        return 0;  // 巡线中，速度PID输出
    }

    // ========== 小T字路口：先直行过路口中心 → 再转弯进病房 ==========
    case FAR_SMALL_T_TURN:
    {
        int status = (far_turn_dir == 0)
            ? turn_left_70(&far_small_turn_phase2, &far_cnt, &far_turn_start_yaw)
            : turn_right_70(&far_small_turn_phase2, &far_cnt, &far_turn_start_yaw);
        if (status == 2)
        {
            far_state = FAR_SMALL_T_COOLDOWN;
            far_cnt = COOLDOWN_MS / 10;
            far_small_turn_phase2 = 0;
        }
        return (status == 0) ? 0 : 1;  // 直行→PID, 旋转→开环
    }

    // ========== 小T转弯冷却 → 远端导航完成 → 转入药房检测 ==========
    case FAR_SMALL_T_COOLDOWN:
        line_pid_track();  // ★转弯后继续巡线不停车（与普通路口CROSS_COOLDOWN一致）
        if (--far_cnt <= 0)
        {
            // 远端导航完成，转入常规药房到达检测
            far_nav_active = 0;
            far_state = FAR_NONE;
            route_complete = 1;
            pharmacy_delay_cnt = PHARMACY_CHECK_DELAY;
        }
        return 0;  // ★返回0让速度PID运行

    default:
        return 0;
    }
}


// ===== 远端返程导航状态机（小T + 大T路口返程）=====
// 去程经远端导航(far_nav)到达药房后，返程需原路返回：
//   药房 → 小T路口(反向转弯) → 小T干路 → 大T路口(反向转弯) → 主路
// 返程时从支路方向接近T字路口，灰度传感器仅能识别4~5个黑线，
// 因此使用ret_t_cross_detect(≥4)+消抖替代t_cross_detect(≥6)。
//
// 返回值：1=电机已完全处理（调用者应return），0=继续执行速度PID输出
static int far_return_control(void)
{
    switch (far_return_state)
    {
    // ========== 药房 → 小T路口：巡线 + ret_t_cross_detect ==========
    case FAR_RET_TO_SMALL_T:
    {
        line_pid_track();

        // 返程T字路口检测（阈值≥4 + 消抖）
        if (ret_t_cross_detect())
            far_ret_tcross_stable++;
        else if (far_ret_tcross_stable > 0)
            far_ret_tcross_stable--;

        if (far_ret_tcross_stable >= FAR_RET_TCROSS_STABLE_CNT)
        {
            // 检测到小T路口 → 反向转弯（翻转去程小T转弯方向）
            // 去程左转(0)→返程右转(1)，去程右转(1)→返程左转(0)
            far_ret_turn_dir = (far_small_turn_saved == 0) ? 1 : 0;
            far_ret_cnt = (far_ret_turn_dir == 0
                ? GO_STRAIGHT_MS_FAR_LEFT : GO_STRAIGHT_MS_FAR_RIGHT) / 10;
            far_ret_turn_phase = 0;
            far_ret_tcross_stable = 0;
            far_return_state = FAR_RET_SMALL_T_TURN;
            return 0;  // 进入转弯状态，由下一状态处理电机
        }
        return 0;  // 巡线中，速度PID输出
    }

    // ========== 小T路口转弯（反向）==========
    case FAR_RET_SMALL_T_TURN:
    {
        int status = (far_ret_turn_dir == 0)
            ? turn_left_70(&far_ret_turn_phase, &far_ret_cnt, &far_ret_turn_start_yaw)
            : turn_right_70(&far_ret_turn_phase, &far_ret_cnt, &far_ret_turn_start_yaw);
        if (status == 2)
        {
            // 小T转弯完成 → 冷却
            far_return_state = FAR_RET_SMALL_T_COOLDOWN;
            far_ret_cnt = COOLDOWN_MS / 10;
            far_ret_turn_phase = 0;
        }
        return (status == 0) ? 0 : 1;  // 直行→PID, 旋转→开环
    }

    // ========== 小T转弯后冷却 ==========
    case FAR_RET_SMALL_T_COOLDOWN:
        line_pid_track();  // ★转弯后继续巡线不停车（与普通路口CROSS_COOLDOWN一致）
        if (--far_ret_cnt <= 0)
        {
            // 冷却结束 → 沿小T干路巡线去大T路口
            far_return_state = FAR_RET_TO_LARGE_T;
            far_ret_tcross_stable = 0;
        }
        return 0;  // ★返回0让速度PID运行

    // ========== 小T干路 → 大T路口：巡线 + ret_t_cross_detect ==========
    case FAR_RET_TO_LARGE_T:
    {
        line_pid_track();

        if (ret_t_cross_detect())
            far_ret_tcross_stable++;
        else if (far_ret_tcross_stable > 0)
            far_ret_tcross_stable--;

        if (far_ret_tcross_stable >= FAR_RET_TCROSS_STABLE_CNT)
        {
            // 检测到大T路口 → 反向转弯（翻转去程大T转弯方向）
            far_ret_turn_dir = (far_large_turn_saved == 0) ? 1 : 0;
            far_ret_cnt = (far_ret_turn_dir == 0
                ? GO_STRAIGHT_MS_FAR_LEFT : GO_STRAIGHT_MS_FAR_RIGHT) / 10;
            far_ret_turn_phase = 0;
            far_ret_tcross_stable = 0;
            far_return_state = FAR_RET_LARGE_T_TURN;
            return 0;
        }
        return 0;
    }

    // ========== 大T路口转弯（反向）==========
    case FAR_RET_LARGE_T_TURN:
    {
        int status = (far_ret_turn_dir == 0)
            ? turn_left_70(&far_ret_turn_phase, &far_ret_cnt, &far_ret_turn_start_yaw)
            : turn_right_70(&far_ret_turn_phase, &far_ret_cnt, &far_ret_turn_start_yaw);
        if (status == 2)
        {
            far_return_state = FAR_RET_LARGE_T_COOLDOWN;
            far_ret_cnt = COOLDOWN_MS / 10;
            far_ret_turn_phase = 0;
        }
        return (status == 0) ? 0 : 1;
    }

    // ========== 大T转弯后冷却 → 交还标准返程(return_mode) ==========
    case FAR_RET_LARGE_T_COOLDOWN:
        line_pid_track();  // ★转弯后继续巡线不停车（与普通路口CROSS_COOLDOWN一致）
        if (--far_ret_cnt <= 0)
        {
            // ★远端返程完成，交还给标准返程模式
            //   后续十字路口由path_memory逆转处理
            far_return_active = 0;
            far_return_state  = FAR_RET_NONE;
            far_large_turn_saved = -1;  // ★重置标记（防止再次激活）
            far_small_turn_saved = -1;
            // return_mode/return_index/path_len保持不变，继续标准返程
        }
        return 0;  // ★返回0让速度PID运行

    default:
        return 0;
    }
}
// ===== 十字路口路由表 =====
// 按目的地编号索引，每个目的地定义一串十字路口动作序列
// CROSS_ACTION_NONE 表示路由结束，后续路口全部忽略
// (CROSS_ACTION_* 宏已在文件顶部定义)

// 按目的地索引的兜底策略（第2路口到达时窗口内出现过的数字不足两个时使用）
// 号牌3~8随机分布在中部2个+远端4个位置，无信息时一律直行：
// dest在远端的先验概率2/3，且直行后还有机会在远端识别；转错弯则直接送错病房
static const int k230_fallback[9] = {
    -1,                        // 索引0：不使用
    -1, -1,                    // 目的地1,2：不使用K230决策
    CROSS_ACTION_STRAIGHT,     // 目的地3~8：兜底直行
    CROSS_ACTION_STRAIGHT,
    CROSS_ACTION_STRAIGHT,
    CROSS_ACTION_STRAIGHT,
    CROSS_ACTION_STRAIGHT,
    CROSS_ACTION_STRAIGHT
};

// 号牌3~8随机分布：中部路口2个 + 远端4个，只有1/2位置固定。
// 因此dest=3~8路由完全相同：第1路口直行，第2路口由K230窗口决策
// （锁定含dest→转弯进病房；不含→直行去远端，远端路口逻辑待定）
static const int route_table[9][MAX_CROSSROADS] = {
    {},  // 索引0：不使用
    {CROSS_ACTION_LEFT,  CROSS_ACTION_NONE},                           // 目的地1：第1个路口左转
    {CROSS_ACTION_RIGHT, CROSS_ACTION_NONE},                           // 目的地2：第1个路口右转
    {CROSS_ACTION_STRAIGHT, CROSS_ACTION_K230_DECIDE, CROSS_ACTION_NONE},  // 目的地3
    {CROSS_ACTION_STRAIGHT, CROSS_ACTION_K230_DECIDE, CROSS_ACTION_NONE},  // 目的地4
    {CROSS_ACTION_STRAIGHT, CROSS_ACTION_K230_DECIDE, CROSS_ACTION_NONE},  // 目的地5
    {CROSS_ACTION_STRAIGHT, CROSS_ACTION_K230_DECIDE, CROSS_ACTION_NONE},  // 目的地6
    {CROSS_ACTION_STRAIGHT, CROSS_ACTION_K230_DECIDE, CROSS_ACTION_NONE},  // 目的地7
    {CROSS_ACTION_STRAIGHT, CROSS_ACTION_K230_DECIDE, CROSS_ACTION_NONE},  // 目的地8
};

// ===== 启动斜坡：目标速度从0平滑过渡到BASE_SPEED，防止两电机起步不同步 =====
static int ramp_cnt = 0;

// ===== PD巡线：边缘中点偏差 + 陀螺角速度前馈 + 死区 + PD（无EMA滤波） =====
// ★ EMA 已移除。EMA低通滤波与PD的D项（微分）互相矛盾：
//   EMA把误差变化"抹平"→D项看不到真实变化率→阻尼失效→反而加剧振荡。
//   现在传感器偏差直接进PD，D项能即时反应→真正抑制微摆。
//   陀螺前馈提供超前阻尼：车身刚开始转就能检测到，比灰度快一个相位。

static float last_error = 0.0f;  // 丢线时保持的上次偏差值
static void line_pid_track(void)
{
    float error = line_error_calc();

    // 丢线保持：全白时沿用上次偏差（按原方向继续回线）
    if (!all_white_detect())
        last_error = error;

    // 死区：微小偏差视为居中，防止中心附近来回微调
    float error_out = last_error;
    if (error_out > -LINE_DEADBAND && error_out < LINE_DEADBAND)
        error_out = 0.0f;

    // ★ 陀螺仪角速度前馈阻尼 ★
    // gz/16.4 = 偏航角速度(°/s)，正值=车身右转
    // 车身右转时(gyro_rate>0) → now加正偏置 → PID输出左转力 → 抵消右转惯性
    float gyro_rate = (float)gz / 16.4f;
    float gyro_damp = gyro_rate * GYRO_DAMP_GAIN;

    line_pid.target = 0.0f;
    line_pid.now = -error_out + gyro_damp;  // 取反偏差 + 陀螺前馈
    pid_cal(&line_pid);  // POSITION_PID: out = P*偏差 + D*d(偏差)/dt

    // 输出限幅
    if (line_pid.out >  LINE_PID_OUT_MAX) line_pid.out =  LINE_PID_OUT_MAX;
    if (line_pid.out < -LINE_PID_OUT_MAX) line_pid.out = -LINE_PID_OUT_MAX;

    // 弯道减速：偏差越大基础速度越低
    // 快速接近模式：dest 3~8 送药过程第一个路口前使用高速（返程不变）
    // ★双重保险：同时检查 fast_approach 标志位 + dest_index 范围，防止任何意外
    float base_speed = (fast_approach && !return_mode
                        && dest_index >= 3 && dest_index <= 8)
                       ? FAST_BASE_SPEED : BASE_SPEED;
    float base = base_speed * (1.0f - 0.05f * fabs(last_error));

    // 启动斜坡
    if (ramp_cnt < RAMP_CYCLES)
    {
        ramp_cnt++;
        float ramp = (float)ramp_cnt / (float)RAMP_CYCLES;
        base *= ramp;
    }

    // 返程最后路口完成后：先全速1秒再降速（终点白线距路口有一定距离）
    // 降速确保传感器在白线上停留足够帧数，配合 arrive_cnt 可靠停车
    if (all_return_done)
    {
        static int full_speed_cnt = 0;
        static int prev_done = 0;
        if (!prev_done)
            full_speed_cnt = 0;   // all_return_done 上升沿复位计数器
        prev_done = 1;
        full_speed_cnt++;
        if (full_speed_cnt > 200) // 200×10ms = 2秒后再降速
            base *= RETURN_ARRIVE_SPEED_RATIO;
    }

    // out>0 → 左轮加速右轮减速 → 右转回中
    motor_target_set(base + line_pid.out,
                     base - line_pid.out);
}

void pid_control()
{
	int dutyA = 0, dutyB = 0;
	int skip_calc = 0;  // 转弯状态跳过正常计算
	int is_cross = 0;   // 十字路口检测结果（移到顶部避免goto跳过初始化警告）

	// ===== 电机测试模式：不做任何控制，由 main 直接操作电机 =====
	if (motor_test_mode)
		return;

		// ===== 未启动：停止所有电机 + 重置PID/ramp状态 =====
	if (!car_started)
	{
		motorA_duty(0);
		motorB_duty(0);
			// 重置速度PID积分（防止起步时I累积残留）
			motorA.iout = 0.0f;
			motorA.out  = 0.0f;
			motorA.error[0] = 0.0f;
			motorA.error[1] = 0.0f;
			motorB.iout = 0.0f;
			motorB.out  = 0.0f;
			motorB.error[0] = 0.0f;
			motorB.error[1] = 0.0f;
			// 重置巡线PID
			line_pid.out = 0.0f;
			line_pid.error[0] = 0.0f;
			line_pid.error[1] = 0.0f;
			line_pid.error[2] = 0.0f;
			// 重置启动斜坡
			ramp_cnt = 0;
			// 快速接近模式重置（实际激活在 car_started 上升沿一次性处理）
			fast_approach = 0;
			fast_approach_init_done = 0;
			// 重置K230识别窗口（防止状态残留）
			k230_window_reset();
		return;
	}
	// ★快速接近模式一次性初始化（定时器在 car_started=1 之后才启动，
	//   所以不能依赖 !car_started 块中的赋值，必须在此处首次运行时判断）
	if (!fast_approach_init_done)
	{
		fast_approach_init_done = 1;
		if (dest_index >= 3 && dest_index <= 8 && !return_mode)
			fast_approach = 1;
		else
			fast_approach = 0;  // dest 1~2 或返程：显式清零，确保不加速
	}
		// hard guard: dest 1~2 force clear fast_approach every cycle
		if (dest_index >= 1 && dest_index <= 2)
			fast_approach = 0;
	// ★转弯后Y-center抑制计数器递减（每周期10ms，75周期=0.75s）
	if (ycenter_suppress_cnt > 0) ycenter_suppress_cnt--;

// ===== OLED调试显示：每200ms刷新（放在pid_control，转弯期间也能更新）=====
	{
		static int dbg_cnt = 0;
		dbg_cnt++;
		if (dbg_cnt >= 20)
		{
			dbg_cnt = 0;

				// ===== OLED 显示（大字模式：2行×8字符，仅显示数字识别信息）=====
				{
					char tmp[16];
					int i;

					// 将字符串格式化为8字符（不足补空格，超出截断）

					if (recognition_active)
					{
						// === 第二路口 K230 识别中：按cx区分左右数字 ===
						int left_d = 0, right_d = 0;
						int min_cx = 9999, max_cx = -1;
						// 扫描所有已检测到且有cx的数字，找最左和最右
						for (i = 1; i <= 8; i++)
						{
							if (cand_conf[i] > 0.0f && cand_cx[i] >= 0)
							{
								if (cand_cx[i] < min_cx) { min_cx = cand_cx[i]; left_d = i; }
								if (cand_cx[i] > max_cx) { max_cx = cand_cx[i]; right_d = i; }
							}
						}
						if (left_d > 0 && right_d > 0 && left_d != right_d)
							sprintf(tmp, "L:%d R:%d", left_d, right_d);
						else if (left_d > 0)
							sprintf(tmp, "L:%d ?", left_d);
						else
							sprintf(tmp, "SCAN...");
						FMT8(oled_line1, tmp);

						// 第2行：识别状态
						if (k230_turn_ready)
						{
							if      (k230_turn_result == CROSS_ACTION_LEFT)  FMT8(oled_line2, "TURN L");
							else if (k230_turn_result == CROSS_ACTION_RIGHT) FMT8(oled_line2, "TURN R");
							else                                             FMT8(oled_line2, "GO STR");
						}
						else
							FMT8(oled_line2, "JUNC 2");
					}
					else if (far_nav_active && (far_state == FAR_LARGE_T_RECOGNIZE ||
					                           far_state == FAR_LARGE_T_TURN_BACK ||
					                           far_state == FAR_LARGE_T_TO_JUNCTION ||
					                           far_state == FAR_LARGE_T_TURN ||
					                           far_state == FAR_LARGE_T_COOLDOWN))
					{
						// === 大T路口：Q3（左）两张牌 / Q4（右）两张牌 ===
						// ★识别窗口内显示L:--/R:--，识别完成后（TURN_BACK→COOLDOWN）显示实际数字
						if (far_q3_cards[1] > 0)
							sprintf(tmp, "L:%d%d", far_q3_cards[0], far_q3_cards[1]);
						else if (far_q3_cards[0] > 0)
							sprintf(tmp, "L:%d", far_q3_cards[0]);
						else
							sprintf(tmp, "L:??");
						FMT8(oled_line1, tmp);

						if (far_q4_cards[1] > 0)
							sprintf(tmp, "R:%d%d", far_q4_cards[0], far_q4_cards[1]);
						else if (far_q4_cards[0] > 0)
							sprintf(tmp, "R:%d", far_q4_cards[0]);
						else
							sprintf(tmp, "R:??");
						FMT8(oled_line2, tmp);
					}
					else if (far_nav_active && far_state == FAR_SMALL_T_STOPPED)
					{
						// === 小T路口：左边数字 / 右边数字 ===
						int rt_left = 0, rt_right = 0, rt_dir = -1;
						far_small_realtime_calc(&rt_left, &rt_right, &rt_dir);
						if (rt_left > 0 && rt_right > 0)
							sprintf(tmp, "L:%d R:%d", rt_left, rt_right);
						else if (rt_left > 0)
							sprintf(tmp, "L:%d ?", rt_left);
						else
							sprintf(tmp, "RECG...");
						FMT8(oled_line1, tmp);

						if (rt_dir == 0)       FMT8(oled_line2, "TURN L");
						else if (rt_dir == 1)  FMT8(oled_line2, "TURN R");
						else                    FMT8(oled_line2, "SMALL T");
					}
					else
					{
						// === 默认：目的地 + 运行模式 ===
						sprintf(tmp, "DEST: %d", dest_index);
						FMT8(oled_line1, tmp);

						if (all_return_done)
							FMT8(oled_line2, "ARRIVED");
						else if (in_pharmacy)
							FMT8(oled_line2, "PHARM");
						else if (far_return_active)
							FMT8(oled_line2, "FAR RET");
						else if (far_nav_active)
							FMT8(oled_line2, "FAR NAV");
						else if (return_mode)
							FMT8(oled_line2, "<< RET");
						else
							FMT8(oled_line2, "GO >>");
					}

					// oled_line3/4 不再使用（清空以兼容旧代码）
					oled_line3[0] = '\0';
					oled_line4[0] = '\0';
				}
				oled_dirty = 1;
			}
	}

	// ===== 调试：转弯完成后永久停车（OLED已在上方刷新，可继续观察角度）=====
	if (turn_debug_stop)
	{
		motorA_duty(0);
		motorB_duty(0);
		return;
	}

	// ===== 返程到站检测：all_return_done + 全白确认 = 到达起始区 → 停车 =====
	if (all_return_done)
	{
		static int arrive_cnt = 0;
		static int arrive_black_cnt = 0;  // 连续非全白帧计数，抗噪递减用

		// ★到达锁存：一旦确认到达，永久停车+绿灯，防止传感器噪声重启电机
		if (return_arrived)
		{
			motorA_duty(0);
			motorB_duty(0);
			LED_RED_OFF();
			LED_GREEN_ON();
			return;
		}

		// 停车检测：优先检测黑白块图案，全白（后墙）为保底
		if (parking_block_detect() || all_white_detect())
		{
			arrive_black_cnt = 0;  // 复位黑帧计数
			arrive_cnt++;
			if (arrive_cnt >= 3)   // 累计3次停车图案（不要求连续，防传感器噪声）
			{
				return_arrived = 1;           // ★锁存到达状态
				motorA_duty(0);
				motorB_duty(0);
				LED_RED_OFF();
				LED_GREEN_ON();   // 绿灯亮 = 已回到起始区
				return;
			}
		}
		else if (arrive_cnt > 0)
		{
			arrive_black_cnt++;
			// 连续5帧(50ms)非全白才递减，防止终点白线前后偶发黑帧抵消计数
			if (arrive_black_cnt >= 5)
			{
				arrive_cnt--;
				arrive_black_cnt = 0;
			}
		}
		// 到站前继续巡线
		line_pid_track();
		pid_cal(&motorA);
		pid_cal(&motorB);
		{
			int _dA = (int)motorA.out;
			int _dB = (int)motorB.out;
			if (_dA > MAX_DUTY) { _dA = MAX_DUTY; motorA.out = MAX_DUTY; motorA.iout = MAX_DUTY - motorA.pout - motorA.dout; }
			if (_dA < 0)        { _dA = 0;        motorA.out = 0;        motorA.iout = -motorA.pout - motorA.dout; }
			if (_dB > MAX_DUTY) { _dB = MAX_DUTY; motorB.out = MAX_DUTY; motorB.iout = MAX_DUTY - motorB.pout - motorB.dout; }
			if (_dB < 0)        { _dB = 0;        motorB.out = 0;        motorB.iout = -motorB.pout - motorB.dout; }
			motorA_duty(_dA);
			motorB_duty(_dB);
		}
		return;
	}

	// ===== 病房到达流程：红灯常亮 → 等待药物被取走(PB5=LOW) → 160°掉头 → 返程 =====
	if (in_pharmacy)
	{
		switch(pharmacy_state)
		{
		case PHARMACY_WAIT_LIFT:
			motorA_duty(0);
			motorB_duty(0);
			LED_RED_ON();
			LED_GREEN_OFF();

			// PB5药物检测消抖：LOW=药物被取走，HIGH=药物在车上
			if (gpio_get(GPIO_B, Pin_5) == 0)
			{
				pb5_lift_cnt++;
				if (pb5_lift_cnt >= PB5_LIFT_STABLE)
				{
					LED_RED_OFF();                     // 熄灭红灯
					pharmacy_state = PHARMACY_TURN180;  // 160°掉头
					turn_start_yaw = yaw_gyro;
					pharmacy_cnt = TURN_MAX_MS / 10;
				}
			}
			else
			{
				pb5_lift_cnt = 0;
			}
			return;

		case PHARMACY_TURN180:
			// 原地160°掉头：根据最后一个路口的转弯方向决定掉头方向
			// 最后路口左转 → 左转掉头；最后路口右转 → 右转掉头
			{
				int last_action = (cross_count > 0 && cross_count <= PATH_MAX_CROSSROADS)
				                  ? path_memory[cross_count - 1]
				                  : CROSS_ACTION_LEFT;  // 安全兜底：默认左转
				int done = (last_action == CROSS_ACTION_RIGHT)
				? turn_right_200(turn_start_yaw, &pharmacy_cnt)
				: turn_left_200(turn_start_yaw, &pharmacy_cnt);
			if (done)
			{
				pharmacy_state = PHARMACY_COOLDOWN;
				pharmacy_cnt = COOLDOWN_MS / 10;
			}
		}
		return;

		case PHARMACY_COOLDOWN:
			// 转弯后短暂冷却，停车消抖
			motorA_duty(0);
			motorB_duty(0);
			if (--pharmacy_cnt <= 0)
			{
				// 启动返程模式
				in_pharmacy     = 0;
				route_complete  = 0;  // ★清除去程标志，防返程时误触发药房检测
				return_mode     = 1;
				return_index    = 0;
				path_len        = cross_count;
				all_return_done = 0;
				return_arrived  = 0;  // ★重置到达锁存
				cross_state     = CROSS_NORMAL;
				cross_action    = -1;
				ramp_cnt        = 0;

				// ★重置巡线偏差记忆（清除去程残留偏差）
				last_error = 0.0f;

				// ★重置速度PID状态（清除去程积分残留，防止返程起步异常）
				motorA.iout = 0.0f;
				motorA.out  = 0.0f;
				motorA.error[0] = 0.0f;
				motorA.error[1] = 0.0f;
				motorB.iout = 0.0f;
				motorB.out  = 0.0f;
				motorB.error[0] = 0.0f;
				motorB.error[1] = 0.0f;

				// ★重置巡线PID状态（清除去程误差历史）
				line_pid.iout = 0.0f;
				line_pid.out  = 0.0f;
				line_pid.error[0] = 0.0f;
				line_pid.error[1] = 0.0f;
				line_pid.error[2] = 0.0f;

				LED_GREEN_OFF(); // 绿灯灭，返程巡线中
				LED_RED_OFF();
				// ★远端返程激活：去程使用了远端导航(far_large_turn_saved≥0)
				//   返程须经过小T+大T路口，不能用标准path_memory逆转
				if (far_large_turn_saved >= 0)
				{
					far_return_active = 1;
					far_return_state  = FAR_RET_TO_SMALL_T;
					far_ret_cnt       = 0;
					far_ret_turn_phase = 0;
					far_ret_tcross_stable = 0;
				}
			}
			return;

		case PHARMACY_DONE:
			// 保留（不再使用，兼容性占位）
			motorA_duty(0);
			motorB_duty(0);
			LED_GREEN_ON();
			return;
		}
	}

	// ===== 药房到达检测（路由完成后，延迟后检测停车区黑白块图案或全白保底）=====
	if (route_complete && dest_index > 0)
	{
		if (pharmacy_delay_cnt > 0)
		{
			pharmacy_delay_cnt--;
		}
		else if (parking_block_detect() || all_white_detect())
		{
			in_pharmacy = 1;
			motorA_duty(0);
			motorB_duty(0);
			LED_RED_ON();
			LED_GREEN_OFF();
			return;
		}
	}

	// ===== 角度环（暂时不用）=====
	angle.target = -20;
	angle.now = yaw_Kalman;
	pid_cal(&angle);

	// ===== 远端返程导航接管（小T + 大T路口返程）=====
	// 去程使用远端导航的药房（far_large_turn_saved≥0），返程需优先处理T字路口
	// far_return_active与far_nav_active互斥，不会同时激活
	if (far_return_active)
	{
		int far_ret_handled = far_return_control();
		if (far_ret_handled)
			skip_calc = 1;
	}
	else if (far_nav_active)
	{
		// ===== 远端导航接管（大T字路口 + 小T字路口）=====
		// dest=3~8第2路口直行后激活，替代常规十字路口逻辑
		int far_handled = far_nav_control();
		// far_handled=1 → 电机已在状态机内直接控制(motorA_duty) → 跳过速度PID
		// far_handled=0 → line_pid_track已设置电机目标 → 由速度PID转换为占空比
		if (far_handled)
			skip_calc = 1;  // ★停车/转弯时跳过速度PID，保持far_nav_control内设定的占空比
	}
	else
	{
		// ===== 十字路口检测 =====
	// 调试开关：1=全白触发转弯（手头没有十字路口场地时用），0=全黑十字路口触发（正式逻辑）

	#if DEBUG_TURN_ON_ALL_WHITE
	is_cross = all_white_detect();  // 调试：8传感器全白 → 触发70°转弯
	#else
	is_cross = cross_detect();      // 正式：全部8传感器为黑 → 十字路口
	#endif

	// 路由已完成（且非返程模式）→ 忽略后续十字路口，专心巡线去药房
	if ((route_complete || far_nav_active) && !return_mode)
	{
		is_cross = 0;
	}

	// 返程已完成所有路口 → 忽略后续十字路口，直行回起始区
	if (all_return_done)
	{
		is_cross = 0;
	}

	switch(cross_state)
	{
		case CROSS_NORMAL:
			// ===== 第2路口K230 Y-center逼近 → 停车 → 识别窗口 =====
			// 替代原有的"冷却后立即开窗口"逻辑，先巡线到数字位于屏幕中央，
			// 停车1秒稳定图像后再开识别窗口，提高数字3/5的分辨率
			if (k230_approach_state == 1)  // 巡线 + 监控K230 cy
			{
				line_pid_track();
				if (digit_result.updated && digit_result.count > 0)
				{
					if (far_check_y_center(FAR_Y_CENTER))
						k230_y_stable_cnt++;
					else if (k230_y_stable_cnt > 0)
						k230_y_stable_cnt--;
				}
				if (k230_y_stable_cnt >= FAR_Y_STABLE_CNT)
				{
					k230_approach_state = 2;  // → 停车
					k230_approach_cnt = 100;  // 1秒(100×10ms)
					k230_y_stable_cnt = 0;
				}
				break;
			}

			if (k230_approach_state == 2)  // 停车+识别窗口（停车即开始识别，不再分两段）
			{
				// 停车立即flush+开窗口（用warmup跳过刹车时的模糊帧）
				if (k230_approach_cnt == 100)  // 第一帧：初始化
				{
					k230_window_reset();
					digit_uart_flush();
					recognition_active = 1;
					recog_warmup = FAR_RECOG_WARMUP;
					k230_approach_cnt--;  // 立即减1，剩余99周期=990ms识别窗口
					dutyA = 0; dutyB = 0;
					skip_calc = 1;
					break;
				}

				// 预热期：等flush后的新帧到达
				if (recog_warmup > 0)
				{
					recog_warmup--;
					k230_approach_cnt--;
					dutyA = 0; dutyB = 0;
					skip_calc = 1;
					break;
				}

				k230_check_and_decide();  // 扫描K230帧，累积置信度
				k230_approach_cnt--;

				if (k230_approach_cnt <= 0)
				{
					// 窗口结束 → 锁存决策，继续巡线等物理路口
					int k230_action;
					if (k230_turn_ready)
						k230_action = k230_turn_result;
					else
						k230_action = (dest_index >= 1 && dest_index <= 8)
						              ? k230_fallback[dest_index]
						              : CROSS_ACTION_LEFT;

					// ★远端导航标记：dest≥3且决策直行→保存中部病房号
					if (dest_index >= 3 && k230_action == CROSS_ACTION_STRAIGHT)
					{
						central_wards[0] = (top_digit[0] >= 3 && top_digit[0] <= 8) ? top_digit[0] : 0;
						central_wards[1] = (top_digit[1] >= 3 && top_digit[1] <= 8) ? top_digit[1] : 0;
						far_nav_pending = 1;
					}

					// ★保存决策，等待物理路口触发
					k230_saved_action = k230_action;
					k230_decision_ready = 1;
					k230_window_reset();
					k230_approach_state = 0;
					// 不直接转弯——继续巡线到物理路口(cross_detect)再执行
				}

				dutyA = 0; dutyB = 0;
				skip_calc = 1;
				break;
			}

			// 原有逻辑：K230识别窗口（保留兼容，dest=1/2等非K230_DECIDE场景）
			k230_check_and_decide();

			line_pid_track();  // PID巡线
		if(is_cross)
		{
			fast_approach = 0;  // 检测到第一个路口，退出快速模式
			// ===== 返程模式：从路径记忆中倒序读取并逆转动作 =====
			if (return_mode)
			{
				if (return_index < path_len)
				{
					// 倒序读取：path_memory[path_len-1], [path_len-2], ...
					int orig = path_memory[path_len - 1 - return_index];
					// 逆转：左↔右，直行不变
					if      (orig == CROSS_ACTION_LEFT)      cross_action = CROSS_ACTION_RIGHT;
					else if (orig == CROSS_ACTION_RIGHT)     cross_action = CROSS_ACTION_LEFT;
					else                                      cross_action = CROSS_ACTION_STRAIGHT;
					return_index++;
					if (cross_action == CROSS_ACTION_STRAIGHT)
					{
						cross_state = CROSS_COOLDOWN;
						cross_cnt = COOLDOWN_MS / 10;
					}
					else
					{
						cross_state = CROSS_TURN;
						cross_cnt = GO_STRAIGHT_MS / 10;
						cross_turn_phase = 0;
						turn_dir = (cross_action == CROSS_ACTION_RIGHT) ? 1 : 0;
					}
				}
				else
				{
					// 返程路口全部处理完 → 继续直行回起始区
					all_return_done = 1;
				}
				break;
			}

			// ===== 去程模式：查找路由表 =====
			int action = CROSS_ACTION_NONE;
			if (dest_index > 0 && dest_index <= 8 && cross_count < MAX_CROSSROADS)
			{
				action = route_table[dest_index][cross_count];
			}

			// K230动态决策：将CROSS_ACTION_K230_DECIDE解析为实际动作
			if (action == CROSS_ACTION_K230_DECIDE)
			{
				k230_is_second_turn = 1;  // ★标记第2路口转弯：左转直行延迟900ms，右转500ms
				// Y-center逼近模式已在识别窗口结束时锁存决策，
				// 且已处理far_nav_pending+central_wards+window_reset，此处只需消费
				if (k230_decision_ready)
				{
					action = k230_saved_action;
					k230_decision_ready = 0;  // 消费锁存的决策
				}
				else if (k230_turn_ready)
				{
					// 旧模式：巡线中开窗口，物理路口到达时使用动态决策结果
					action = k230_turn_result;

					// ★远端导航标记：dest≥3且K230决策直行 →
					//   保存中部2个病房号（排除法用），标记远端导航待激活
					if (dest_index >= 3 && action == CROSS_ACTION_STRAIGHT)
					{
						central_wards[0] = (top_digit[0] >= 3 && top_digit[0] <= 8) ? top_digit[0] : 0;
						central_wards[1] = (top_digit[1] >= 3 && top_digit[1] <= 8) ? top_digit[1] : 0;
						far_nav_pending = 1;
					}

					// 关闭识别窗口并重置，为下次使用做准备
					k230_window_reset();
				}
				else
				{
					// 窗口内出现过的数字不足两个 → 使用兜底策略
					action = (dest_index >= 1 && dest_index <= 8)
					         ? k230_fallback[dest_index]
					         : CROSS_ACTION_LEFT;
				}
			}

			// 路由表结束（CROSS_ACTION_NONE）→ 忽略后续路口，专心巡线
			if (action == CROSS_ACTION_NONE)
			{
				route_complete = 1;
				break;
			}

			// 记录到路径记忆中（返程用）
			if (cross_count < PATH_MAX_CROSSROADS)
			{
				path_memory[cross_count] = action;
			}

			cross_count++;  // 有效路口计数+1
			cross_action = action;
			if (action == CROSS_ACTION_STRAIGHT)
			{
				cross_state = CROSS_COOLDOWN;
				cross_cnt = COOLDOWN_MS / 10;
					k230_is_second_turn = 0;  // K230决策直行→远端导航，无转弯
			}
			else
			{
				cross_state = CROSS_TURN;
				cross_turn_phase = 0;
				turn_dir = (action == CROSS_ACTION_RIGHT) ? 1 : 0;
				// ★第2路口左右转直行延迟区分（K230决策）
				cross_cnt = (k230_is_second_turn
				             ? (turn_dir == 0 ? GO_STRAIGHT_MS_K230_LEFT : GO_STRAIGHT_MS_K230_RIGHT)
				             : GO_STRAIGHT_MS) / 10;
				k230_is_second_turn = 0;
			}
		}
		break;

	case CROSS_TURN:
			// 原地旋转转弯（封装函数：阶段0=直行GO_STRAIGHT_MS，阶段1=旋转TURN_TARGET_DEG）
			{
				int status = (turn_dir == 0)
					? turn_left_70(&cross_turn_phase, &cross_cnt, &turn_start_yaw)
					: turn_right_70(&cross_turn_phase, &cross_cnt, &turn_start_yaw);
				if (status == 1)  // 旋转中：跳过PID，反转轮补偿更高占空比
				{
					skip_calc = 1;
					dutyA = (turn_dir == 0) ? TURN_DUTY_REV : TURN_DUTY;
					dutyB = (turn_dir == 0) ? TURN_DUTY : TURN_DUTY_REV;
				}
				else if (status == 2)  // 完成
				{
				#if DEBUG_STOP_AFTER_TURN
					turn_debug_stop = 1;
				#else
					cross_state = CROSS_COOLDOWN;
					cross_cnt = COOLDOWN_MS / 10;
				#endif
				}
			}
			break;

		case CROSS_COOLDOWN:
		line_pid_track();  // PID巡线，冷却期内不检测十字路口
			// 返程最后路口转弯完成后立即标记到站，不等cooldown结束
			// 确保cooldown期间就以低速巡线，防止高速冲过终点白线
			if (return_mode && return_index >= path_len && !all_return_done)
				all_return_done = 1;
		if(--cross_cnt <= 0)
		{
			cross_state = CROSS_NORMAL;
			ycenter_suppress_cnt = YCENTER_SUPPRESS_CYCLES;  // ★进入巡线后抑制Y-center误触发（YCENTER_SUPPRESS_CYCLES×10ms）

			// 返程模式：检查是否所有返程路口已处理完
			if (return_mode && return_index >= path_len)
			{
				all_return_done = 1;
			}

			// 去程模式：检查路由表下一项
			// NONE → 路由完成（或远端导航）；K230_DECIDE → 开启识别窗口
			if (!return_mode && !route_complete && dest_index > 0 && dest_index <= 8)
			{
				int next_action = (cross_count < MAX_CROSSROADS)
					? route_table[dest_index][cross_count]
					: CROSS_ACTION_NONE;
				if (next_action == CROSS_ACTION_NONE)
				{
					if (far_nav_pending)
					{
						// ★远端导航激活：第2路口直行后进入大T/小T路口导航
						far_nav_pending = 0;
						far_nav_init();
					}
					else
					{
						route_complete = 1;
						pharmacy_delay_cnt = PHARMACY_CHECK_DELAY;
					}
				}
				else if (next_action == CROSS_ACTION_K230_DECIDE)
				{
					// ★Y-center逼近模式：先巡线到数字位于屏幕中央，停车后再开识别窗口
					k230_approach_state = 1;
					k230_approach_cnt = 0;
					k230_y_stable_cnt = 0;
				}
			}
		}
		break;
	}

	}  // else: 常规十字路口检测结束

	// ===== 速度闭环输出 =====
	if(!skip_calc)
	{
		// 速度PID：motorA/B.target=目标速度, motorA/B.now=实测速度(编码器计数/10ms)
		pid_cal(&motorA);
		pid_cal(&motorB);

		dutyA = (int)motorA.out;
		dutyB = (int)motorB.out;

		// 输出限幅 + 抗饱和（位置式PID需同步限幅iout，防止退饱和延迟）
		if(dutyA > MAX_DUTY) { dutyA = MAX_DUTY; motorA.out = MAX_DUTY; motorA.iout = MAX_DUTY - motorA.pout - motorA.dout; }
		if(dutyA < 0)        { dutyA = 0;        motorA.out = 0;        motorA.iout = -motorA.pout - motorA.dout; }
		if(dutyB > MAX_DUTY) { dutyB = MAX_DUTY; motorB.out = MAX_DUTY; motorB.iout = MAX_DUTY - motorB.pout - motorB.dout; }
		if(dutyB < 0)        { dutyB = 0;        motorB.out = 0;        motorB.iout = -motorB.pout - motorB.dout; }
	}

	// ★远端导航/返程处理电机时(skip_calc=1)跳过此输出，防止dutyA/B=0覆盖状态机内设定的占空比
	if (!((far_nav_active || far_return_active) && skip_calc))
	{
		motorA_duty(dutyA);
		motorB_duty(dutyB);
	}

	// 调试用：取消下面注释可输出编码器速度到串口示波器（VirtualScope）
	// 注意：会占用UART1 TX，与K230数字识别冲突，调试完请注释掉
	// datavision_send();
}
void pid_cal(pid_t *pid)
{
	// 计算当前偏差
	pid->error[0] = pid->target - pid->now;

	// PID计算
	if(pid->pid_mode == DELTA_PID)  // 增量式
	{
		pid->pout = pid->p * (pid->error[0] - pid->error[1]);
		pid->iout = pid->i * pid->error[0];
		pid->dout = pid->d * (pid->error[0] - 2 * pid->error[1] + pid->error[2]);
		pid->out += pid->pout + pid->iout + pid->dout;
	}
	else if(pid->pid_mode == POSITION_PID)  // 位置式
	{
		pid->pout = pid->p * pid->error[0];
		pid->iout += pid->i * pid->error[0];
		pid->dout = pid->d * (pid->error[0] - pid->error[1]);
		pid->out = pid->pout + pid->iout + pid->dout;
	}

	// 记录前两次偏差
	pid->error[2] = pid->error[1];
	pid->error[1] = pid->error[0];

	// 输出限幅
//	if(pid->out>=MAX_DUTY)
//		pid->out=MAX_DUTY;
//	if(pid->out<=0)
//		pid->out=0;

}

void pidout_limit(pid_t *pid)
{
	// 输出限幅
	if(pid->out>=MAX_DUTY)
		pid->out=MAX_DUTY;
	if(pid->out<=0)
		pid->out=0;
}
