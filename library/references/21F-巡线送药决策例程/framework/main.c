/*
 * 巡线送药决策框架 —— 题型：line_follow（21F 巡线送药决策例程提炼）
 *
 * 本文件是「题型确定性框架段」（参考条目 framework/main.c）：骨架生成时
 * 原样注入 main.c 生成 prompt，作为**必须保留的结构**。类型 = 巡线送药类
 * 选题的决策骨架：巡线主循环 → 十字路口状态机 → 药房送达状态机 → 返程
 * 状态机。平台 / 接口中立：所有硬件调用一律写成注释占位
 *   // TODO: <角色> 由接口块替换
 * 由 AI 按当前所选模块接口实现（接口块里真实存在的函数）。
 *
 * 框架约定（AI 必须遵守）：
 * 1. 枚举 / 调度循环 / 框架函数名保持原样，改动只出现在 TODO 位；
 * 2. 状态机用 switch-case 分派：每个状态一个 case，块内只做“判定 → 动作 →
 *    状态转移”三步（不嵌长逻辑）；
 * 3. 所有持续运行逻辑挂在 10ms 调度周期上（isr 每 10ms 调一次
 *    decision_dispatch），单次调度内不阻塞；
 * 4. 安全兜底：任何“等结果”状态都要有超时转移（TURN_TIMEOUT_MS 等），
 *    不许死等；
 * 5. 不在框架里写死参数（速度标定 / 阈值全部经 TODO 参数区注入）。
 */

// ===== 十字路口状态机 =====
typedef enum {
    CROSS_NORMAL,      /* 正常巡线中 */
    CROSS_STRAIGHT,    /* 路口直行保序 */
    CROSS_TURN,        /* 路口转向执行 */
    CROSS_COOLDOWN     /* 转向完成冷却 */
} cross_state_t;

// ===== 药房送达状态机 =====
typedef enum {
    PHARMACY_WAIT_LIFT,  /* 等待抬升确认 */
    PHARMACY_TURN180,    /* 掉头执行 */
    PHARMACY_COOLDOWN,   /* 掉头完成冷却 */
    PHARMACY_DONE        /* 送达完成，返程接管 */
} pharmacy_state_t;

// ===== 返程导航状态机 =====
typedef enum {
    RETURN_NONE,         /* 未激活 */
    RETURN_TURN,         /* 返程转向 */
    RETURN_COOLDOWN      /* 返程冷却 */
} return_state_t;

static cross_state_t cross_state = CROSS_NORMAL;
static pharmacy_state_t pharmacy_state = PHARMACY_WAIT_LIFT;
static return_state_t return_state = RETURN_NONE;

// ===== TODO 参数区（AI 按题面 / 实际底盘标定值填写）=====
// TODO: 基础巡线速度（编码器计数 / 10ms） —— 由接口块替换
// TODO: 转向占空比 / 反转向占空比 —— 由接口块替换
// TODO: 路口判定消抖帧数（连续 N 帧检测到路口特征） —— 由接口块替换
// TODO: 转向安全超时（ms） —— 由接口块替换
// TODO: 路径路由表（每个十字路口：左 / 右 / 直） —— 由接口块替换

/*
 * 10ms 调度周期入口（isr 或定时器回调调用）。
 * 决策分派：当前状态 → 读传感器 → 判定 → 动作 → 状态转移。
 * TODO: 具体读哪个传感器 / 调哪个电机接口 —— 由接口块替换。
 */
static void decision_dispatch(void) {
    // TODO: 读灰度巡线值（如 gray_read()） —— 由接口块替换
    // TODO: 读限位 / 到位传感器（如 key_read()） —— 由接口块替换

    switch (cross_state) {
        case CROSS_NORMAL:
            // TODO: 巡线 PID 控制（如 pid_line_control()） —— 由接口块替换
            // TODO: 检测到路口特征 → cross_state = CROSS_STRAIGHT —— 由接口块替换
            break;
        case CROSS_STRAIGHT:
            // TODO: 直行保序计时 —— 由接口块替换
            // TODO: 计时到 → cross_state = CROSS_TURN —— 由接口块替换
            break;
        case CROSS_TURN:
            // TODO: 按路由表转向（如 motor_turn_left / motor_turn_right） —— 由接口块替换
            // TODO: 转角到位 → cross_state = CROSS_COOLDOWN —— 由接口块替换
            break;
        case CROSS_COOLDOWN:
            // TODO: 冷却计时 → 回 CROSS_NORMAL —— 由接口块替换
            break;
    }

    switch (pharmacy_state) {
        case PHARMACY_WAIT_LIFT:
            // TODO: 药房抬升检测（如 sensor_pharmacy_lift()） —— 由接口块替换
            // TODO: 检测到位 → pharmacy_state = PHARMACY_TURN180 —— 由接口块替换
            break;
        case PHARMACY_TURN180:
            // TODO: 掉头执行（如 motor_turn_180()） —— 由接口块替换
            // TODO: 掉头完成 → pharmacy_state = PHARMACY_COOLDOWN —— 由接口块替换
            break;
        case PHARMACY_COOLDOWN:
            // TODO: 冷却计时 → pharmacy_state = PHARMACY_DONE —— 由接口块替换
            break;
        case PHARMACY_DONE:
            // TODO: 返程接管：return_state = RETURN_TURN —— 由接口块替换
            break;
    }

    switch (return_state) {
        case RETURN_NONE:
            // TODO: 返程激活判定（如 key_return_pressed()） —— 由接口块替换
            break;
        case RETURN_TURN:
            // TODO: 返程转向（如 motor_turn_right_180()） —— 由接口块替换
            // TODO: 返程转角到位 → RETURN_COOLDOWN —— 由接口块替换
            break;
        case RETURN_COOLDOWN:
            // TODO: 冷却计时 → RETURN_NONE（继续巡线） —— 由接口块替换
            break;
    }
}

/*
 * main() 骨架：初始化 → 调度循环（while(1) 内只调 decision_dispatch）。
 * TODO: 初始化调用 —— 由接口块替换（各模块初始化 + 定时器 10ms 起振）。
 */
int main(void) {
    // TODO: 模块初始化（如 led_init / motor_init / gray_init） —— 由接口块替换
    // TODO: 10ms 定时器启动（循环内轮询或中断调度） —— 由接口块替换

    for (;;) {
        decision_dispatch();
        // TODO: 10ms 节拍等待（如 delay_ms(10)） —— 由接口块替换
    }
}
