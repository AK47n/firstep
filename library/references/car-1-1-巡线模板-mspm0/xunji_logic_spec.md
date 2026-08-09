# 小车巡线逻辑规格说明（AI可读）

> 适用于：智能小车基于灰度传感器的巡线/循迹控制逻辑
> 来源：control.c（MSPM0G3507 平台，TI Code Composer Studio）

---

## 一、硬件架构

### 1.1 传感器布局
```
    车头（前方）
  P1  P2  P3  P4  P5  P6  P7  P8
  左 ←──────────→ 右
  -7   -5   -3   -1   +1   +3   +5   +7   ← 质心权重
```

- **8个灰度传感器**（P1~P8），等间距排列在车头下方，面对地面
- 传感器为数字量（0=检测到黑线，1=检测到白色/地面）
- **黑线巡线模式**：黑色轨迹线在地面上，传感器压到黑线时输出0

### 1.2 执行机构
- **双轮差速驱动**：左轮（A轮）和右轮（B轮）
- **两路PWM**：控制左右电机转速和方向
- **编码器**：左右轮各一个，用于速度闭环反馈

### 1.3 姿态传感器
- **JY61P 陀螺仪**：通过UART获取偏航角（Yaw），范围 -180° ~ +180°
- 用于在白色区域（无黑线区域）保持方向或执行定向转弯

---

## 二、核心巡线算法：加权质心法（Weighted Centroid）

### 2.1 函数原型
```c
float xunji_centroid(float gain);
```

### 2.2 算法流程
```
1. 遍历8个传感器 P1~P8
2. 每个传感器有一个固定的位置权重：
   P1 = -7, P2 = -5, P3 = -3, P4 = -1
   P5 = +1, P6 = +3, P7 = +5, P8 = +7
3. 如果传感器检测到黑线（值为0 → 读回0，条件为真），
   累加其权重到 sum，cnt++
4. 计算加权平均值：centroid = sum / cnt
5. 最终输出：bias = -centroid * gain
```

### 2.3 伪代码
```python
def xunji_centroid(gain):
    sum = 0
    cnt = 0
    weights = [-7, -5, -3, -1, 1, 3, 5, 7]  # P1~P8
    
    for i, sensor in enumerate([P1, P2, P3, P4, P5, P6, P7, P8]):
        if sensor == 0:  # 检测到黑线
            sum += weights[i]
            cnt += 1
    
    if cnt == 0:
        return 0.0  # 没检测到线
    
    centroid = sum / cnt           # 线的加权中心位置
    bias = -centroid * gain        # 取反后乘以增益
    return bias
```

### 2.4 bias 的含义
```
bias > 0  → 线偏右 → 需要右转（左轮加速，右轮减速）
bias < 0  → 线偏左 → 需要左转（右轮加速，左轮减速）
bias = 0  → 线居中或未检测到线
```

### 2.5 增益（gain）调参
| 工况 | 增益值 | 说明 |
|------|--------|------|
| 普通速度 | 3.4 | 默认巡线增益 |
| 高速 | 7.0 | 弯道响应更快但可能抖动 |
| 低速 | 3.0 | 更平滑但弯道可能跟不上 |
| 调参规则 | ±0.5/次 | 直道抖动→减小gain；弯道出轨→增大gain |

---

## 三、差速驱动控制

### 3.1 速度分配公式
```c
targetA = Speed_Middle + bias;   // 左轮目标速度
targetB = Speed_Middle - bias;   // 右轮目标速度
```
- `Speed_Middle`：中值速度（基准速度），当前为 20
- `bias`：来自巡线算法（黑线区）或陀螺仪（白区）
- **效果**：bias为正时左轮快右轮慢→右转；bias为负时相反→左转

### 3.2 速度闭环（PID）
```c
Motor_Left  = PID_A(CurrentA, targetA);   // 左轮PID输出
Motor_Right = PID_B(CurrentB, targetB);   // 右轮PID输出
```
- **PID类型**：增量式PID
- **参数**：Kp=0.9, Ki=0, Kd=0（实际为纯P控制）
- **输入**：编码器测得的当前速度（每50ms更新一次）
- **输出**：PWM占空比（0~100%）
- **限幅**：±Limit（当前 Limit=200）

### 3.3 PWM限幅
```c
PWM_Limit(value, max, min)  // 将value钳制在[min, max]区间
```

---

## 四、电机驱动（Set_Pwm）

### 4.1 方向与PWM设置
```c
void Set_Pwm(int motor_left, int motor_right)
```
- motor > 0 → 前进（AIN1=1, AIN2=0）
- motor < 0 → 后退（AIN1=0, AIN2=1）
- PWM占空比 = |motor|（取绝对值）

### 4.2 占空比计算
```c
CompareValue = 2500 - 2500/100 * duty;  // 0~100 百分比转为定时器比较值
```

---

## 五、多模式赛道逻辑

小车支持4种赛道模式，通过按键切换：

### 5.1 公共状态变量
| 变量 | 含义 |
|------|------|
| `whiteflag` / `whiteflag1` / `whiteflag2` | 白色区域标志（不同模式用不同编号） |
| `flag` | 黑色区域标志（=1表示当前在黑线区域） |
| `n` | 区域计数器，n%2==0为掉头区，n%2==1为巡线区 |
| `m` | 模式段计数器，到达指定值后停车 |
| `ledflag` | 声光模块启动标志 |
| `timebegin/timebegin1/timebegin2` | 白区确认延时启动标志 |
| `timenum/timenum1/timenum2` | 白区确认延时计数器 |
| `Yaw` | 陀螺仪偏航角（-180°~+180°） |

### 5.2 白色区域防抖机制
```
条件：所有8个传感器都是1（都看不到黑线）
动作：启动延时计时器（timebegin=1）
延时：2~19个定时周期后确认进入白区（whiteflag=1）
目的：过滤噪声/缝隙，防止误判
```

### 5.3 模式0：Control_AB（仅巡线模式）
```
全程使用 Yaw 作为 bias，执行基础的陀螺仪辅助直线行驶。
检测到任意传感器见黑 → 亮灯、停车（a=1时）。
```

### 5.4 模式1：Control_ABCDA（单圈巡线）
```
赛道形状：A → B → C → D → A（环形）

状态机：
  IF 全部8个传感器 = 1（全白）:
    → 启动延时，延时到后 whiteflag=1
  
  IF whiteflag == 1（在白区）:
    → m++（第一帧进入白区时）
    → n 为偶数时：bias = error - |Yaw| 或 Yaw - error（掉头）
    → n 为奇数时：bias = Yaw（直行通过）
    → flag = 0
  
  ELSE（在黑区巡线）:
    → m++（第一帧进入黑区时）
    → n++（离开白区后开始新的巡线段）
    → bias = xunji_centroid(GAIN_NORMAL)    ← 核心巡线
    → whiteflag = 0

  若 m >= 6：停车
```

### 5.5 模式2：Control_ACBDA（含180°掉头）
```
赛道形状：A → C → B → D → A

与模式1类似，但偶数段（掉头段）的bias策略不同：
  → n为偶数时：bias = Yaw + 103（固定角度掉头）
  → n为奇数时：bias = xunji_centroid(GAIN_NORMAL)（巡线）
```

### 5.6 模式3：Control_ACBDAx4（多圈重复）
```
与模式2逻辑相同，但跑4圈（m>=18才停车）。
```

---

## 六、完整控制循环（时序）

```
main() 主循环（无延时，全速运行）:
  ├─ 读取按键（S2切换模式，S1启动）
  ├─ 根据mode调用对应的Control_xxx()函数
  │   ├─ 读取8路灰度传感器
  │   ├─ 判断黑区/白区状态
  │   ├─ 计算bias（巡线或陀螺仪）
  │   ├─ 读取编码器速度（gEncoderVal_left/right）
  │   ├─ PID速度控制
  │   └─ Set_Pwm()输出电机控制
  └─ 循环

中断服务:
  ├─ TIMER_Encoder_Read（50ms定时）:
  │   ├─ 读取编码器计数值并清零
  │   ├─ 白区延时计数处理
  │   └─ 声光模块延时处理
  ├─ TIMER_0（10ms定时）:
  │   └─ 白区确认延时（模式2/3用）
  ├─ GPIO_EncoderA/B 中断:
  │   └─ 编码器脉冲计数（正交解码）
  └─ UART_JY61P 中断:
      └─ 接收陀螺仪数据（Yaw/Pitch/Roll）
```

---

## 七、关键常量汇总

| 常量 | 值 | 说明 |
|------|-----|------|
| GAIN_NORMAL | 3.4 | 巡线加权质心增益 |
| Kp1 | 0.9 | 速度环P参数 |
| Ki1 | 0 | 速度环I参数 |
| Kd1 | 0 | 速度环D参数 |
| Limit | 200 | PWM输出限幅 |
| Speed_Middle | 20 | 基准速度 |
| 编码器倍率 | /3 | gEncoderVal→实际速度 |

---

## 八、移植到新平台时需要实现的接口

```c
// ===== 传感器读取 =====
bool read_grayscale_sensor(int index);  // index=0~7, 对应P1~P8, true=黑线

// ===== 电机驱动 =====
void set_motor_left(int pwm);   // pwm>0前进, pwm<0后退, |pwm|=占空比
void set_motor_right(int pwm);

// ===== 编码器 =====
int get_encoder_left();   // 返回当前速度（脉冲数/周期）
int get_encoder_right();

// ===== 陀螺仪（可选，白区使用） =====
float get_yaw();           // 返回偏航角 -180°~+180°

// ===== 定时器中断（50ms周期） =====
// 在中断中更新编码器速度值并处理延时计数器

// ===== 核心函数（平台无关，可直接复用） =====
float xunji_centroid(float gain);    // 加权质心巡线算法
float PID_control(float current, float target, float kp, float ki, float kd);
float limit_pwm(float value, float max, float min);
```
