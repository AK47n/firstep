# 04 — 深化：填 TODO + 编译验证闭环

**要做什么：** 在已修订（或未修订）的工程上，AI 按功能需求清单逐条填充 main.c 的 TODO 预留区（输入 = 现有 main.c + 功能需求清单 + 模块接口清单 + 题面与 Q&A；模块没变时读现有 main.c，不丢手工编辑；模块变过则在新骨架上填）。写回后强制走编译验证：工具链探测复用 → 编译 → 失败自动进修复闭环（修复中心机制复用）→ 重编译；编译绿标记"已验证"，无工具链时大声降级（结果保留、状态 = 未验证，明确提示）。不设自动循环，用户可重复触发。深化走 SSE 进度流（填 TODO 中 / 编译中 / 修复中 / 验证结果）。

**被谁阻塞：** 03（在修订后的工程与上下文上执行）

**状态：** resolved（2026-08-21 实施完成 + code-review 双轴评审整改闭环）

## Comments

**实施记录（2026-08-21）：**
- 新模块 `deepen.py`：run_deepen 编排——LLM 按功能需求清单逐条填充 main.c
  TODO（deepen_main_c：DEEPEN_SYSTEM_PROMPT 逐条对应、保留手工编辑、只调真实
  接口、纯 C 输出；文本模式走 remote）→ 整树备份（revise-backups，可回滚）→
  写盘 → 编译验证闭环。
- 编译验证：resolve_compile_toolchain 单源探测 → 无工具链 = 大声降级
  （status=unverified，结果保留、中文提示）；有 → collect_build_log 编译 →
  失败修一轮（run_fix_round 复用）→ 重编译 → 绿 = verified；修一轮仍红 =
  failed（结果保留可回滚）。不设自动循环，用户可重复触发。
- webapp POST /api/revise/deepen（SSE：deepening_start → compile_start →
  fix_start → verify_result → done 载荷 {status, backup_id, compile,
  message}）；main_c 服务端现读（手工编辑保留）。
- events.py 加 deepening_start / verify_result 词表；DeepenError 登记
  errors.py；测试 7 项（tests/test_deepen.py）+ 全量 2112 绿 + mypy 干净。

**评审整改（code-review 双轴）：**
- Standards：run_deepen 复用 resolve_compile_toolchain（与 /api/compile 同源
  探测，CompileRunnerError = 无工具链转降级）；_status_message 三分支单源
  （死分支消除）；.scratch/revise-deepen 目录入库。
- 决策留痕：webapp 层 main.c 为空同步 400（域层 SSE error 之外的双保险——
  同步快失败 UX 更好，测试断言此路径）；空 main.c 守卫双份为路由快失败 +
  域层兜底（语义不同，非冗余）。

- [x] 深化 API：读现有 main.c → 假 LLM 输出实现后的 main.c → 写盘（写盘前备份，可回滚）
- [x] 功能需求逐条可追踪：输出与需求清单对应（不做题外发挥）
- [x] 编译验证闭环：有工具链 → 编译 → 失败修复 → 重编译 → 绿 = 已验证；无工具链 → 状态 = 未验证 + 大声降级提示
- [x] 模块没变时深化在现有 main.c 上进行（手工编辑保留）；模块变过后在新骨架上进行
- [x] 结果载荷：验证状态 / 修改摘要 / 回滚入口


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
