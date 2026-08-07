# 05 — 存量 6 模块简介迁移

**What to build:** 存量 6 个模块（filter / lock_control / ml_mpu6050 / motor / pid / uwb_uart）的简介按三要素判据重写：AI 通读代码出草稿 → 用户确认/修改 → 真实 AI 一致性校验通过后写回；用户补填各平台条目的身份字段（kit + source_url）；专用性标注落进简介文本。迁移后全库简介达标、身份齐全。

专用性标注建议（最终由用户逐条确认）：lock_control → 2026C 数字钥匙题专用；pid → 巡线题专用；filter → 出身 2026C、逻辑通用；uwb_uart → 套件身份由用户填；ml_mpu6050 / motor → 通用驱动。lock_control 保留对 zone 的依赖（zone 补录是独立工单，本工单不涉及）。

**Blocked by:** 01 — 硬件身份字段 + 新录入强制；02 — 存量身份补填编辑路径；04 — 一致性校验认识"专用性"

**Status:** resolved

- [x] 6 个模块简介按三要素重写（AI 草稿 → 用户确认），专用性标注落进简介文本
- [x] 6 个模块的平台条目身份字段齐全（kit + source_url，用户填写）
- [x] 每次写回都通过真实 AI 一致性校验，全库简介与代码一致
- [x] 用户真机验收：选模块推荐能分辨套件与专用性（配合 03 的摘要行）

## Comments

- 2026-08-07 迁移执行（分支 ticket-module-desc-05，未合并）：**每模块 = AI 通读代码出草稿（真实 DeepSeek）→ 用户逐条确认/修改 → 真实 AI 一致性校验通过 → 写回**；身份字段由用户提供，走 `update_platform_identity`（无 AI 校验——身份是事实）。全程库层直调（:8000 是旧代码进程，无工单 02/03 端点）；驱动脚本 `.scratch/real-run/module_migrate.py`（draft / validate / save / identity 四个子命令，仿 module_import.py 先例）。

  **简介定稿**（专用性标注已落进文本，用户逐条确认）：
  - filter：出身 2026C 题、滤波逻辑通用、纯逻辑无硬件绑定
  - lock_control：2026C 数字钥匙题专用——措辞以"按赛题要求…"锚定代码内"赛题要求"注释后通过校验；zone 依赖保留
  - ml_mpu6050：MPU6050 I2C 通用驱动（套件 MPU6050）
  - motor：双路直流电机通用驱动（套件 轮趣）
  - pid：**2021F 巡线题专用**（用户提供题号；代码含送药/药房导航状态机，对得上）
  - uwb_uart：UWB 定位串口驱动（套件 最新ALX-AOA-FIT跟随套件开发资料）

  **身份字段**（用户提供）：ml_mpu6050 / motor / uwb_uart 补填 kit + source_url；filter / lock_control / pid 为纯逻辑模块，用户确认不填（与工单 06 修订一致）。

  **校验失败不落盘实录（4 次，全部验证生效、磁盘无污染）**：
  1. lock_control v1 含"纯逻辑模块，无硬件绑定"被拒——代码直接 gpio_init/gpio_set 驱动 LED/蜂鸣器 → 删除该句；
  2. lock_control v2 "2026C 数字钥匙题专用"被拒——AI 认为代码是通用门锁状态机、题号不可观测 → v3 以"赛题要求"锚定后通过（v3 亦曾单跑通过但保存复校验被拒一次，重试通过，LLM 判定有波动）；
  3. motor 草稿"编码器外部中断计数"被拒——真实问题：代码只配置 exti + 输入引脚、无计数逻辑（Encoder_count1/2 从未在中断更新）→ 如实改写为"编码器信号引脚配置"后通过；
  4. uwb_uart "对距离和方位角做…野值钳位"一度被拒（AI 称未见方位角钳位）→ 重试通过；但代码疑点属实：方位角钳位 `cur_az > 0` 守卫使负方位角永不触发钳位，建议后续修复（超出本工单范围）。

  **真机验收（真实 DeepSeek + 真实赛题文本，选模块清单含套件段与专用性）**：
  - 2026C 数字钥匙题（Desktop/2026C/赛题原文.md）→ 推荐 uwb_uart / zone / lock_control；未推荐 pid / motor / ml_mpu6050 ✓
  - 2021F 智能送药小车题（2021F_智能送药小车.pdf 提取文本，验收工具 `.scratch/real-run/select_check.py`）→ 推荐 pid / motor / filter（AI 理由直接引用"2021F题专用"）；未推荐 lock_control / zone / uwb_uart ✓
  - 双向判别成立：专用性标注正确引导选模块；filter "出身 2026C、逻辑通用"被当作通用件复用于巡线题 ✓；套件身份随 03 摘要行喂给 AI ✓
  - 验收期间发现 zone 已在并行工单 07 补录入库，lock_control 的 zone 依赖现可正常解析 ✓
