/*
 * 巡线小车决策框架 —— 题型：line_follow（car 1.1 巡线模板 mspm0 提炼）
 *
 * 本文件是「题型确定性框架段」（参考条目 framework/main.c）：骨架生成时
 * 原样注入 main.c 生成 prompt，作为**必须保留的结构**。类型 = 通用巡线
 * 小车主循环：灰度传感器读线 → PID 差速控制 → 主循环调度（10ms 节拍）。
 * 平台 / 接口中立：所有硬件调用一律写成注释占位
 *   // TODO: <角色> 由接口块替换
 * 由 AI 按当前所选模块接口实现（接口块里真实存在的函数）。
 *
 * 框架约定（AI 必须遵守）：
 * 1. 枚举 / 调度循环 / 框架函数名保持原样，改动只出现在 TODO 位；
 * 2. 控制分层：每周期「读线 → 计算偏差 → 设置电机」三步，不做题外逻辑；
 * 3. 所有持续运行逻辑挂在 10ms 调度周期上（isr 每 10ms 调一次
 *    xunji_dispatch），单次调度内不阻塞；
 * 4. 安全兜底：任何状态转换都要有超时转移，不许死等；
 * 5. 不在框架里写死参数（速度 / 偏差增益 / 死区全部经 TODO 参数区注入）。
 */

// ===== 巡线状态机 =====
typedef enum {
    XUNJI_STOP,        /* 等待启动（按键 / 上电复位） */
    XUNJI_FOLLOW,      /* 正常巡线中 */
    XUNJI_WAIT_LINE    /* 等待特定线型（如停车区） */
} xunji_state_t;

static xunji_state_t xunji_state = XUNJI_STOP;

// ===== TODO 参数区（AI 按题面 / 实际底盘标定值填写）=====
// TODO: 基础速度（PWM / 占空比） —— 由接口块替换
// TODO: 巡线偏差增益（PID 或 PD 的参数） —— 由接口块替换
// TODO: 停车区判定阈值（连续 N 帧检测到停车区特征） —— 由接口块替换
// TODO: 状态转换安全超时（ms） —— 由接口块替换

/*
 * 10ms 调度周期入口（isr 或定时器回调调用）。
 * 读线 → 算偏差 → 差速控制；状态机只做最小化转移。
 * TODO: 具体读哪个传感器 / 调哪个电机接口 —— 由接口块替换。
 */
static void xunji_dispatch(void) {
    // TODO: 读灰度线（如 gray_read()，返回线位置 / 路数） —— 由接口块替换
    // TODO: 读按键（如 key_read()，返回启动 / 停止） —— 由接口块替换

    switch (xunji_state) {
        case XUNJI_STOP:
            // TODO: 启动键按下 → xunji_state = XUNJI_FOLLOW —— 由接口块替换
            break;
        case XUNJI_FOLLOW:
            // TODO: 巡线控制：偏差 → 差速（如 motor_set(左, 右)） —— 由接口块替换
            // TODO: 检测到停车区特征（连续 N 帧）→ xunji_state = XUNJI_WAIT_LINE —— 由接口块替换
            break;
        case XUNJI_WAIT_LINE:
            // TODO: 停车：速度置零 / 等待确认 —— 由接口块替换
            // TODO: 确认完成（超时或按键）→ 回 XUNJI_FOLLOW / XUNJI_STOP —— 由接口块替换
            break;
    }
}

/*
 * main() 骨架：初始化 → 调度循环（while(1) 内只调 xunji_dispatch）。
 * TODO: 初始化调用 —— 由接口块替换（各模块初始化 + 定时器 10ms 起振）。
 */
int main(void) {
    // TODO: 模块初始化（如 led_init / motor_init / gray_init） —— 由接口块替换
    // TODO: 10ms 定时器启动（循环内轮询或中断调度） —— 由接口块替换

    for (;;) {
        xunji_dispatch();
        // TODO: 10ms 节拍等待（如 delay_ms(10)） —— 由接口块替换
    }
}
