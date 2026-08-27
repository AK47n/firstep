/*
 * 滚球巡线一圈决策框架 —— 题型：line_follow（26H 滚球巡线决策例程提炼）
 *
 * 本文件是「题型确定性框架段」（参考条目 framework/main.c）：骨架生成时
 * 原样注入 main.c 生成 prompt，作为**必须保留的结构**。类型 = 一圈巡线 +
 * 启停线停车类选题的决策骨架：按键启动 → 离开起点启停线 → 正常巡线 →
 * 检测启停线 → 减速停车 → 显示结果。平台 / 接口中立：所有硬件调用一律
 * 写成注释占位
 *   // TODO: <角色> 由接口块替换
 * 由 AI 按当前所选模块接口实现（接口块里真实存在的函数）。
 *
 * 框架约定（AI 必须遵守）：
 * 1. 枚举 / 调度循环 / 框架函数名保持原样，改动只出现在 TODO 位；
 * 2. 状态机用 if 分层（与 26H 原例程一致）：先判离开起点（消抖），再判
 *    正常运行，再判启停线（停车区），优先级从上到下；
 * 3. 所有持续运行逻辑挂在 10ms 调度周期上（isr 每 10ms 调一次
 *    lap_dispatch），单次调度内不阻塞；
 * 4. 安全兜底：启停线检测要消抖（连续 N 帧），防单帧误判；
 * 5. 不在框架里写死参数（消抖帧数 / 减速比例全部经 TODO 参数区注入）。
 */

// ===== LAP 一圈启停状态机 =====
typedef enum {
    LAP_IDLE,           /* 等待按键启动 */
    LAP_LEAVING_START,  /* 刚启动，正在离开起点启停线（忽略初始黑线） */
    LAP_RUNNING,        /* 正常运行中，等待检测启停线（完成一圈） */
    LAP_STOPPING,       /* 检测到启停线，减速停车中 */
    LAP_STOPPED         /* 已停车，显示结果 */
} lap_state_t;

static lap_state_t lap_state = LAP_IDLE;

// ===== TODO 参数区（AI 按题面 / 实际底盘标定值填写）=====
// TODO: 启停线检测消抖帧数（连续 N 帧 ≥4 路黑才算） —— 由接口块替换
// TODO: 离开起点冷却周期数（启动后若干周期内忽略黑线） —— 由接口块替换
// TODO: 减速停车比例（如 60% 速度停车） —— 由接口块替换
// TODO: 基础巡线速度 —— 由接口块替换

/*
 * 10ms 调度周期入口（isr 或定时器回调调用）。
 * 分层判定：离开起点 → 正常巡线 → 启停线 → 停车完成。
 * TODO: 具体读哪个传感器 / 调哪个电机接口 —— 由接口块替换。
 */
static void lap_dispatch(void) {
    // TODO: 读按键启动（如 key_start_pressed()） —— 由接口块替换
    // TODO: 读灰度线（如 gray_read_lines(), 返回 ≥4 路黑标志） —— 由接口块替换
    // TODO: 运行计时（如 tim_get_ms()） —— 由接口块替换

    if (lap_state == LAP_LEAVING_START) {
        // TODO: 离开起点：冷却周期计数到 → lap_state = LAP_RUNNING —— 由接口块替换
        // TODO: 冷却期内仍执行巡线控制 —— 由接口块替换
    }
    if (lap_state == LAP_IDLE) {
        // TODO: 按键按下 → lap_state = LAP_LEAVING_START + 计时清零 —— 由接口块替换
    }
    if (lap_state == LAP_STOPPED) {
        // TODO: 停车完成 → 显示总时间（如 oled_show_ms()） —— 由接口块替换
    }
    if (lap_state == LAP_STOPPING) {
        // TODO: 减速停车判定（速度降到阈值 → lap_state = LAP_STOPPED） —— 由接口块替换
    }
    if (lap_state == LAP_LEAVING_START || lap_state == LAP_RUNNING) {
        // TODO: 正常巡线 PID 控制（如 pid_line()） —— 由接口块替换
        if (lap_state == LAP_RUNNING) {
            // TODO: 检测到启停线（消抖通过）→ 计时结束 + lap_state = LAP_STOPPING —— 由接口块替换
        }
    }
}

/*
 * main() 骨架：初始化 → 调度循环（while(1) 内只调 lap_dispatch）。
 * TODO: 初始化调用 —— 由接口块替换（各模块初始化 + 定时器 10ms 起振）。
 */
int main(void) {
    // TODO: 模块初始化（如 led_init / motor_init / gray_init） —— 由接口块替换
    // TODO: 10ms 定时器启动（循环内轮询或中断调度） —— 由接口块替换

    for (;;) {
        lap_dispatch();
        // TODO: 10ms 节拍等待（如 delay_ms(10)） —— 由接口块替换
    }
}
