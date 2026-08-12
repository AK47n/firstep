#include "headfile.h"

#define DEST_STABLE_FRAMES  3

// 调试开关：强制锁定目的地编号（1~8），0=正常K230识别
#define DEBUG_FORCE_DEST    	0   // 调试：强制锁定目的地编号（1~8），0=正常识别

// K230识别调试：1=上电后直接观察K230检测到的所有数字及坐标，0=正常模式
#define K230_DEBUG          0

int main(void)
{
	char line[32];
	int len;

	char dest_label[8]     = "";
	char dest_candidate[8] = "";
	int  dest_stable_count = 0;
	int  dest_locked       = 0;

	gpio_init(GPIO_A, Pin_11, OUT_PP);
	gpio_init(GPIO_A, Pin_12, OUT_PP);
	gpio_set(GPIO_A, Pin_11, 0);  // 红灯初始熄灭
	gpio_set(GPIO_A, Pin_12, 0);  // 绿灯初始熄灭
	gpio_init(GPIO_B, Pin_5, IU);

	gray_init();
	motor_init();
	encoder_init();

	// ===== IMU初始化链（yaw_Kalman依赖，缺一不可）=====
	I2C_Init();                       // IMU软件I2C总线 (PB10=SCL, PB11=SDA)
	MPU6050_Init();                   // 唤醒陀螺仪 + 使能INT数据就绪中断(200Hz)
	HMC5883L_Init();                  // 磁力计（yaw观测源）
	exti_init(EXTI_PB7, RISING, 1);   // PB7=MPU6050 INT → EXTI7中断读数据+卡尔曼融合
	                                  // 注意：最后才开中断，防止传感器未配置完就触发

	pid_init(&motorA,   POSITION_PID, 600.0f, 0, 0);
	pid_init(&motorB,   POSITION_PID, 600.0f, 0, 0);
	pid_init(&angle,    POSITION_PID, 0, 0, 0);
	pid_init(&line_pid, POSITION_PID, 1.0f, 0, 2.5f);  // PD巡线：P=1.0降推力 D=2.5强阻尼 + 陀螺前馈防微摆

	// 定时器延迟启动：等"识别完成 + PB5按下"后才开，防止上电误动
	// tim_interrupt_ms_init(TIM_3, 10, 0);

	OLED_Init();
	OLED_Clear();
	digit_uart_init();

	OLED_ShowString(1, 1, "Smart Pharmacy");
	OLED_ShowString(2, 1, "Init done...");
	delay_ms(2000);
	OLED_Clear();

	// =====================================================================
	//  主循环 — 三阶段顺序执行：
	//    阶段1: K230 识别数字 → 锁定目的地
	//    阶段2: 按 PB5 确认出发
	//    阶段3: PID 巡线（由 pid_control 接管）
	// =====================================================================

	while (1)
	{
		// ==================== 接收 K230 数据 ====================
		digit_result.count   = 0;
		digit_result.updated = 0;
		digit_uart_parse();

		// ==================== K230 调试：模拟识别窗口，显示3/4的x坐标对比及左右判断 ====================
	#if K230_DEBUG
		if (!car_started)
		{
			static int dbg_cx3 = -1, dbg_cx4 = -1;
			static int dbg_vote_cnt = 0;
			static int dbg_vote_dir = -1;
			int i, j, n = 0;
			struct { char label[2]; int cx, cy; float conf; } d[MAX_DIGITS];

			// === 收集本帧所有有效数字 ===
			for (i = 0; i < digit_result.count && i < MAX_DIGITS; i++)
			{
				int cx = digit_result.digits[i].cx;
				if (cx < 150 || cx > 1050) continue;
				d[n].label[0] = digit_result.digits[i].label[0];
				d[n].label[1] = '\0';
				d[n].cx   = cx;
				d[n].conf = digit_result.digits[i].confidence;
				d[n].cy   = digit_result.digits[i].cy;
				n++;
			}

			// === 按cx升序排列 ===
			for (i = 0; i < n - 1; i++)
				for (j = i + 1; j < n; j++)
					if (d[i].cx > d[j].cx)
						{
								char tl0 = d[i].label[0], tl1 = d[i].label[1];
								int  tcx = d[i].cx;
							int  tcy = d[i].cy;
								float tconf = d[i].conf;
								d[i].label[0] = d[j].label[0]; d[i].label[1] = d[j].label[1];
								d[i].cx = d[j].cx;
							d[i].cy = d[j].cy;
							d[i].conf = d[j].conf;
								d[j].label[0] = tl0; d[j].label[1] = tl1;
								d[j].cx = tcx;
							d[j].cy = tcy;
							d[j].conf = tconf;
							}

			// === 记录3/4首次cx ===
			for (i = 0; i < n; i++)
			{
				if (d[i].label[0] == '3' && dbg_cx3 < 0)
					dbg_cx3 = d[i].cx;
				if (d[i].label[0] == '4' && dbg_cx4 < 0)
					dbg_cx4 = d[i].cx;
			}

			// === 投票确认 ===
			if (dbg_cx3 >= 0 && dbg_cx4 >= 0)
			{
				int f_cx3 = -1, f_cx4 = -1;
				for (i = 0; i < n; i++)
				{
					if (d[i].label[0] == '3') f_cx3 = d[i].cx;
					if (d[i].label[0] == '4') f_cx4 = d[i].cx;
				}
				if (f_cx3 >= 0 && f_cx4 >= 0)
				{
					int dir = (dbg_cx3 < dbg_cx4) ? 0 : 1;
					if (dir == dbg_vote_dir) dbg_vote_cnt++;
					else { dbg_vote_dir = dir; dbg_vote_cnt = 1; }
				}
			}

			// === OLED 调试显示：数字 + 置信度 ===
			// 第1行：所有检测到的数字及置信度（按cx升序）
			{
				int pos = 0;
				if (n > 0)
				{
					for (i = 0; i < n && pos < 14; i++)
						pos += sprintf(line + pos, "%s:%.0f%% ",
						               d[i].label, d[i].conf * 100.0f);
					line[pos] = '\0';
				}
				else
					sprintf(line, "No digit");
				OLED_ShowString(1, 1, line);
			}

			// 第2行：x坐标
			{
				int pos = sprintf(line, "cx:");
				for (i = 0; i < n && pos < 14; i++)
					pos += sprintf(line + pos, " %d", d[i].cx);
				OLED_ShowString(2, 1, line);
			}

			// 第3行：所有数字的cy坐标（★调试：确定最佳FAR_Y_CENTER）
			{
				int pos = sprintf(line, "cy:");
				for (i = 0; i < n && pos < 14; i++)
					pos += sprintf(line + pos, " %d", d[i].cy);
				if (n == 0)
					sprintf(line, "cy: ---");
				OLED_ShowString(3, 1, line);
			}

			// 第4行：首个检测数字的(cx,cy) + 置信度
			{
				if (n > 0)
					sprintf(line, "%s:(%d,%d)%.0f%%",
					        d[0].label, d[0].cx, d[0].cy, d[0].conf * 100.0f);
				else
					sprintf(line, "---");
				OLED_ShowString(4, 1, line);
			}
		}
	#endif  // K230_DEBUG

		// ==================== 阶段1：目的地识别 ====================
		if (!dest_locked)
		{
#if DEBUG_FORCE_DEST
			// ★调试模式：跳过K230识别，强制锁定目的地
			dest_index     = DEBUG_FORCE_DEST;
			dest_locked    = 1;
			sprintf(dest_label, "%d", DEBUG_FORCE_DEST);
			cross_count    = 0;
			route_complete = 0;
			return_mode    = 0;
			all_return_done = 0;
#else
			// ---- 识别逻辑：连续N帧同一个数字才锁定 ----
			if (digit_result.count == 1)
			{
				if (dest_candidate[0] == '\0'
					|| strcmp(dest_candidate, digit_result.digits[0].label) == 0)
				{
					strcpy(dest_candidate, digit_result.digits[0].label);
					dest_stable_count++;
				}
				else
				{
					strcpy(dest_candidate, digit_result.digits[0].label);
					dest_stable_count = 1;
				}
			}
			else
			{
				dest_candidate[0] = '\0';
				dest_stable_count = 0;
			}

			if (dest_stable_count >= DEST_STABLE_FRAMES)
			{
				strcpy(dest_label, dest_candidate);
				dest_locked = 1;
				// 根据识别到的数字设置目的地编号 + 重置所有状态
				if (strcmp(dest_label, "1") == 0)      dest_index = 1;
				else if (strcmp(dest_label, "2") == 0) dest_index = 2;
				else if (strcmp(dest_label, "3") == 0) dest_index = 3;
				else if (strcmp(dest_label, "4") == 0) dest_index = 4;
				else if (strcmp(dest_label, "5") == 0) dest_index = 5;
				else if (strcmp(dest_label, "6") == 0) dest_index = 6;
				else if (strcmp(dest_label, "7") == 0) dest_index = 7;
				else if (strcmp(dest_label, "8") == 0) dest_index = 8;
				cross_count    = 0;
				route_complete = 0;
				return_mode    = 0;
				all_return_done = 0;
			}
#endif  // DEBUG_FORCE_DEST

			// ---- 阶段1 OLED ----
	#if !K230_DEBUG
			// 第1行：识别进度
			if (dest_stable_count > 0)
				sprintf(line, "Lock:%s %d/%d",
				        dest_candidate, dest_stable_count, DEST_STABLE_FRAMES);
			else
				sprintf(line, "Detecting...");
			len = strlen(line);
			for (; len < 16; len++) line[len] = ' ';
			line[16] = '\0';
			OLED_ShowString(1, 1, line);

			// 第2行：K230 实时数据
			if (digit_result.updated && digit_result.count > 0)
				sprintf(line, "See:%s %.2f",
				        digit_result.digits[0].label,
				        digit_result.digits[0].confidence);
			else
				sprintf(line, "No digit seen");
			len = strlen(line);
			for (; len < 16; len++) line[len] = ' ';
			line[16] = '\0';
			OLED_ShowString(2, 1, line);
	#endif
		}

		// ==================== 阶段2：等待 PB5 启动 ====================
		if (dest_locked && !car_started)
		{
			// ---- 阶段2 OLED ----
	#if !K230_DEBUG
			sprintf(line, "Dest: %s", dest_label);
			len = strlen(line);
			for (; len < 16; len++) line[len] = ' ';
			line[16] = '\0';
			OLED_ShowString(1, 1, line);

			OLED_ShowString(2, 1, "Place med to start");
	#endif

			// ---- PB5 消抖（连续3次 HIGH = 300ms 确认（药物放上→高电平））----
			static int pb5_cnt = 0;

			if (gpio_get(GPIO_B, Pin_5) == 1)
			{
				pb5_cnt++;
				if (pb5_cnt >= 3)
				{
					OLED_Clear();  // ★先清屏（此时定时器未开，无I2C冲突）
					car_started = 1;
					gpio_set(GPIO_A, Pin_12, 0);
					tim_interrupt_ms_init(TIM_3, 10, 0);  // 最后开定时器
				}
			}
			else
			{
				pb5_cnt = 0;
			}
		}

		// ==================== 阶段3：巡线中，主循环刷OLED（大字模式）====================
		if (car_started && oled_dirty)
		{
			// ISR 已准备好数据到 oled_line1~2（各8字符），主循环用大字渲染
			OLED_ShowStringBig(1, 1, oled_line1);
			OLED_ShowStringBig(2, 1, oled_line2);
			oled_dirty = 0;
		}

		// ==================== LED 指示 ====================
		// 红绿灯全部由 pid_control 管理，主循环不干预

		delay_ms(100);
	}
}
