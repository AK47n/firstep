# 03 — pid 剥离决策层（双平台巡线套装瘦身）

**What to build:** pid 模块瘦身为纯驱动（ADR 0009），双平台分别剥离决策层：stm32 侧 gray_track 十字路口检测 + pid_isr 10ms 调度 → 骨架；mspm0 侧 gray_track_mspm0 启停线检测 + LAP 状态机 → 骨架。保留驱动：PID 控制器（pid_cal / pid_control）+ 灰度读取（gray_track 双平台）。manifest 描述按判据四要素重写（能力方向 = PID 闭环控制 + 灰度循迹驱动）；deps 按剥离后实际依赖更新——若 ball_detect / digit_uart / ml_mpu6050 只被滚球决策层使用 → 移出 deps（决策层素材走参考文件库：21F / 26H 原工程在 sources/，归档路径实施时确认）。**先决依赖：工单 01 已闭环（结构测试 + EXCEPTION_REGISTRY 例外注册表已立）——本工单清理 pid 后必须删除注册表对应条目（不删 = 存量校验红）。注意与工单 04（ball_detect）交叉。**

**Status:** drafted

## 实施（细节实施会话定）

1. stm32 侧：pid.c / gray_track.c 保留 PID + 灰度读取，十字路口检测移出；pid_isr.c 评估——10ms 调度移出后若文件为空壳则删除（骨架自建定时器调度）。
2. mspm0 侧：gray_track_mspm0.c 保留灰度读取，启停线检测 + LAP 状态机移出；pid_mspm0.c 保留 PID。
3. manifest.json：description 四要素；deps 与剥离后一致。
4. 决策素材：21F / 26H 原工程若未归档进参考文件库 → 归档（register/write_archive_entries），工单记录归档结果。
5. 结构测试 EXCEPTION_REGISTRY（tests/test_module_universality.py）删除 pid 条目——不删 = 存量校验红。

## 文件边界

- library/modules/pid/code/*（pid.c / pid_isr.c / gray_track.c / gray_track_mspm0.c / pid_mspm0.c + 对应 .h）
- library/modules/pid/manifest.json
- 可能：references 库归档条目（决策源码素材）
- **不动**：motor / ball_detect / digit_uart / ml_mpu6050 模块内容（deps 变化只改 pid 的 manifest）

## 验收

- [ ] 双平台编译 0 错：stm32 UV4（21F 巡线线）+ mspm0 gmake（2026H 滚球线）。
- [ ] 结构测试绿（pid 不再命中黑名单）。
- [ ] manifest 四要素齐 + deps 与剥离后实际依赖一致。
- [ ] 决策层已剥离（无十字路口/启停线/LAP 状态机符号），决策素材归档有记录。
- [ ] EXCEPTION_REGISTRY 已删 pid 条目，删后全库测试仍绿。
- [ ] 工单补实施记录 + 验收勾选，Status resolved。
