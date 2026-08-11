# 01 — 推荐层按平台过滤模块：库外建议语义对偶 ref-platform-filter（模块侧缺口）

**What to build:** 2026-08-11 MSPM0 线真机验收（2026H 题）发现：`/api/recommend` 的模块选择**不按平台过滤**——模型推荐了库里只有 stm32 实现的 pid / digit_uart / filter / ml_mpu6050（H 题摆杆控制确实需要 PID，但库里没有 mspm0 版），生成门禁平台检查兜底 400（"模块 X 没有平台 mspm0 的版本条目"），用户被迫手动 drop。参考库侧已有同款过滤（工单 ref-platform-filter：associated_references 按 platform 过滤），模块推荐侧是对偶缺口。收敛循环的模块清单应只含**本平台有实现的模块**；本平台没有的（如 mspm0 的 pid）走**库外建议**语义（suggestions，灰色展示不勾选）——与"题面证据驱动 + 库外建议"的设计一致。

**Blocked by:** 无

**Status:** resolved（2026-08-11 双回归验收，1009 绿 + mypy 干净）

## 需求

1. **模块清单按平台过滤**：推荐（收敛）流程拿到的模块库候选只含 `platforms` 含当前 platform 的条目（语义与 reference 的 `associated_references` 平台过滤同款：any 全进、空串不过滤——模块 manifest 无平台字段按现有语义处理）。platform 已透传到 recommend（请求体值，工单 02 架构已有）。
2. **过滤位置**：收敛循环的模块候选侧（模型不该看到"本平台没有的模块"当作可勾选实现），而非生成门禁（门禁保留兜底不动）。库外建议语义不变：本平台无实现的真实需求 → suggestions。
3. **回归**：stm32 线（2021F/2026C）结果逐字节等价或仅更好的（stm32 有全部模块，预期无变化）；mspm0 线（2026H）推荐 modules 全为 mspm0 可用。
4. **测试**：推荐层平台过滤单测（mspm0 请求不出现 stm32-only slug；stm32 请求全量）+ 2026H mspm0 端到端回归。

## 文件边界

- `src/contest_generator/selection.py`：收敛循环模块候选/提示词装配（filter 落点，实施者定位模块清单来源）
- `src/contest_generator/llm.py`：如协议/prompt 需要（只读）
- `tests/test_selection.py`（或推荐相关测试文件）+ generate_check 回归复用
- 不动：生成门禁 `_check_platform`（兜底保留）、reference 过滤（已做）

## 验收

- [x] 2026H mspm0 推荐：modules 全为 mspm0 可用（pid/digit_uart/filter/ml_mpu6050 不再出现；若模型仍提 pid 需求 → 在 suggestions 里）
- [x] 2021F stm32 回归：推荐结果与现行为一致（stm32 全量库不受影响）
- [x] 全量 pytest 绿 + mypy src 干净
- [x] 端到端：generate_check mspm0 2026H 可**去掉 --drop** 直接跑通（drop 保留为手动减模块语义）

## 验收记录（2026-08-11）

- 2026H mspm0（2026H_filt，无 --drop）：推荐 4 轮收敛 → huidu, motor, key, ntb_time, oled 全 mspm0 可用（pid/digit_uart/filter/ml_mpu6050 不再出现）；生成 26 文件，产物检查 0 问题。`--add imu_uart,led_beep` 为 include 门禁依赖补选（motor.h include imu.h/led_beep.h，两模块均 mspm0 可用——模型漏选依赖由门禁兜底，非平台过滤缺口）。
- 2021F stm32（2021F）：推荐 4 轮收敛 → digit_uart, pid, led_beep，related 含 pid（stm32-only 模块不受影响）；生成 51 文件，UV4 真机编译 0 错误。
- 全量 pytest 1009 绿 + mypy src 干净。
- 实现：`filter_manifests_by_platform`（selection.py，platform 空串不过滤、platforms 含该平台才留，与参考库 `_platform_matches` 同判据）；`resolve_topic_context` topic/no-topic 两路径装配点过滤（摘要行与关联模块同源同滤，参考锚定 kit 词表用全量候选不动）；`_no_topic_context` 加 platform 参数（缺省空串 = 现状）；`/api/recommend` 请求体补 platform（index.html + generate_check.py payload——之前真机流程从未触发过滤是 2026H "模型推荐 stm32-only 模块 → 门禁 400 → 手动 drop" 的传输层根因）。

## 实施提示词（复制到新会话）

```
实施推荐层平台过滤工单 .scratch/recommend-platform-filter/issues/01-platform-filter.md：
1. 读工单 + src/contest_generator/selection.py（推荐收敛循环模块候选来源）+
   src/contest_generator/reference_library.py（参考库平台过滤先例，语义对齐）
2. 模块候选侧按 platform 过滤（platforms 含当前平台；库外需求走 suggestions 不动）
3. 测试：平台过滤单测 + 2026H mspm0 / 2021F stm32 双回归
4. 全量 pytest + mypy
5. 提交（feat: 前缀）+ 推送
注意：生成门禁平台检查是兜底，不要动；模块 manifest 无 platforms 字段的条目按
现有语义处理（保持现状，不引入新行为）
```
