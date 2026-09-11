# 02 — 真机验收：400 中文带数字

**要做什么：** 在真机路径上证明端到端可用——用一个「物理不可解」的 mspm0 选中集走
`/api/generate`，门禁 400 的中文回复里确实带着本单新增的数字段（落点 / 可用脚 / 占用 /
空闲 / 解开几组 / 剩余几组 / 至少去掉几个），而不是只在单测里成立。零额度、零真机编译。

**被谁阻塞：** 01（引脚容量诊断与门禁数字段）——诊断与文案未落地前无数字可验。

**状态：** resolved

- [x] 真机样本成形：`2026H / mspm0` 12 选中集（`recommend_2026H.json` 的 done 载荷，
      展开后 13 manifest）→ 造出「默认脚冲突」请求（不带 bindings），确认门禁确实 400。
- [x] HTTP 路径取证：`POST /api/generate` 的实际响应体 400 中文**逐字留档**，必须含
      落点数 42、可用 IO 31、占用 27、剩余空闲 0（解后）、无解组数 3 与三个角色对
      （`oled.OLED_SPI_SDA` / `motor.BIN2` / `motor.BIN1`）；证据件落
      `.scratch/pin-capacity/verify-02-*.txt`。
- [x] **输出目录未产生**（门禁在 `output_dir.mkdir` 之前拦下）——与 `pin-conflict-gate/01`
      同一条判据复核，不因本单回退。
- [x] 对照组（同一台机器、同一脚本）：`motor` + `servo` 可解形态 → 文案给「可用自动配置
      解开」且**无**「至少要去掉」；`--bindings` 解掉冲突的可解形态 → 生成放行（400 消失），
      证明本单只改文案、未加拦截。
- [x] 降级对照：板数据缺失 / 产物复核形态各一条，文案与改动前逐字一致。
- [x] 记录回归数值（`python -m pytest -q`、`node --test tests/js/*.test.mjs`）与工单 01
      实测的相对增量；本单本身不改产品代码（若探针需落在 `.scratch/pin-capacity/`，
      只允许新增只读探针）。
- [x] 明文记账：本单不覆盖「用户点一次 Keil5 / CCS 编译」（那是挂账单 A4/A5 的人工件），
      也不声称已证明真机编译通过——本单验收线只有「400 文案带数字」这一条。

## 验收记录（2026-09-18）

**探针**：`.scratch/pin-capacity/probe-05-http-acceptance.py`——走 FastAPI TestClient
（进程内真 HTTP 路径：真路由 → 真门禁），并用「一被调用就抛错」的假 LLM 工厂兜底。
**零额度、零 LLM 调用**：四跑全部在任何 LLM 调用之前结束（探针一触发 LLM 即失败，实测未触发）。
payload 与前端**手动目录模式**同形（`desktop: false` + 显式 `output_dir`，避开 AI 起名调用）。

| # | 形态 | HTTP | 输出目录产生 | 容量段 | 「至少要去掉」 |
|---|---|---|---|---|---|
| ① | 2026H / mspm0 12 选中（无 bindings） | **400** | **False** | 有 | 有（3 个模块） |
| ② | motor + servo（无 bindings） | **400** | **False** | 有 | **无**（说「不必去掉模块」） |
| ③ | motor + servo + `bindings {"servo.SERVO_PWM_C0": "PA0"}` | **200** | True | — | — |
| ④ | motor 单模块（无冲突） | **200** | True | — | — |

判据 = 四形态全部符合期望 → **True**。留档：`verify-02-http-acceptance.json`
（四跑状态 + 两跑 400 文案全文）。验收项里写的 `verify-02-*.txt` 实际落成 `.json`
（探针一次落盘全部形态，比逐份 txt 更便于逐条比对）——如实记账这处形态差异。

**① 的文案要点逐字命中**：`13 个模块 / 42 个引脚落点`、`板载可用 IO 31 脚，本次已占 27 脚、
剩余 4 脚`、`7 组同脚冲突`、`可解开 4 组，剩余 3 组无法靠改绑解开`、三个无解角色对、
`可用 IO 脚已全被占用（31 脚，一个空闲脚都不剩）`、`至少要去掉 3 个模块（冲突模块：
oled、imu_uart、motor、servo）`；且 **输出目录未产生**（门禁仍在 `mkdir` 之前拦下，
与 `pin-conflict-gate/01` 同一条判据，本单未回退）。

**③ 是「只改文案、未加拦截」的正证**：解掉撞脚后生成**放行**（HTTP 200、输出目录产生、
摘要键齐全），产物 `mspm0.syscfg` 里 `SERVO_PWM.peripheral.ccp0Pin.$assign = "PA0"`、
`DC_MOTOR.associatedPins[3].pin.$assign = "PA7"` —— 两脚分开、冲突消失。

**降级对照的真实覆盖面（如实记账）**：板数据缺失形态在 HTTP 路径上**不可造**——板定义不由
载荷决定，只有「绑定缺省 + 板加载失败」才会走到那条降级；故由工单 01 的两个缝用例
（`test_syscfg_pin_conflicts_no_capacity_numbers_without_board` /
`..._on_output_tree_corpus`）与落盘原文 `msg-motor_servo_noboard.txt` 覆盖。
本单不谎称 HTTP 路径已覆盖该形态。

**回归**：本单**零产品代码改动**（只加只读探针），故不改回归数值；沿用工单 01 实测
`python -m pytest -q` → **4000 passed**、`node --test tests/js/*.test.mjs` →
**1444 pass / 0 fail**。

**运行中的产品服务仍是旧进程（给用户的提醒）**：真机 8000 端口上的服务是本轮改动**之前**
启动的实例（进程启动时导入的模块已固定），故浏览器里现在看到的仍是旧文案。要让新文案在
页面生效需重启产品服务——本单不代做（避免打断用户正在用的会话）。
