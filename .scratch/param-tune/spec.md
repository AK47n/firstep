# 参数速调（param-tune）spec

## 问题陈述

学生上板调试时最频繁的动作是「改一个数」（循迹阈值、PID 系数、速度、延时、占空比）。
现状下每改一个数都要重新点「做这一步」整任务重跑（一次 LLM 调用产全文 → 编译 →
烧录），十几分钟一次，且 AI 可能顺手改到别处。学生需要：**改数值 → 编译 → 烧录**
一条极短链路，且只改那一个常量、其余一字不动。

## 目标

- 一键识别 main.c 中的可调数值参数（阈值/速度/PID 系数/延时/占空比等），生成
  参数表（名称 / 中文含义 / 当前值 / 建议范围），落盘工程根，刷新不丢。
- 学生改值 → 确定性替换（**零 LLM 二次调用**）→ 整树备份 → 写盘 → 编译验证 →
  结果面板（diff + 编译徽章 + 回滚 + 烧录按钮）。
- 独立于任务清单：main.c 存在即可用（不要求已拆解）。

## 用户故事

1. 我在任务推进区看到「⚙️ 参数速调」卡片，点「识别 main.c 参数」→ AI 扫描后
   列出参数表（如 THRESHOLD｜循迹阈值｜当前 800｜建议 500-1000）。
2. 参数表里每个参数一行，当前值在输入框里可直接改；改完点「应用并验证」。
3. 应用过程只改声明处那一个常量，diff 里只有那一行变化；编译绿 = 状态「已验证」。
4. 应用结果显示 diff（可折叠）+ 编译徽章 + 「回滚到修改前」+ 「烧录到板子」。
5. 参数表落盘，刷新页面仍在；任务执行导致 main.c 变化后锚失效 → 面板标记
   「已失效，请重新识别」，应用时后端也会校验拒绝。
6. 无参数可识别（main.c 全是结构代码）→ 提示「未发现可调参数」，不落盘空表。
7. 改的值格式自由（数字 / 带后缀 1.2f / 宏 3000UL），只做非空 + 长度校验。

## 实现决策

- 识别（scan）走 LLM 一次（新协议 `llm.scan_params(main_c, module_interfaces)`，
  json_mode）→ 域判决 `params.build_params(raw, main_c)` 校验 → 落盘
  `.contest_params.json`（原子 .tmp→replace，与 idea_chat/drafts 同构）。
- **ParamItem**：`name`（参数标识）/ `label`（中文含义）/ `old_value`（当前值
  原文）/ `anchor`（声明行原文，**必须逐字节存在于 main.c 中且其中 old_value
  恰好出现 1 次**——解析层硬校验，不满足 → LLMError 整次重问）/ `unit`（可选）/
  `range_hint`（建议范围文本，可选）。
- 应用（apply）**零 LLM**：`apply_param_change(main_c, param, new_value)` 纯函数
  ——找 anchor 首次出现位置 → anchor 内 old_value 替换为新值 → 拼接。锚失效 /
  old_value 不在 anchor → TaskError「参数锚已失效…请重新识别」（400 中文）。
- apply 流程 = 备份（revise_backup_root 复用）→ 写盘 → `main_diff` →
  `verify_compile_tail(subject="参数修改")` → 返回 {status, backup_id, compile,
  main_diff, message}；**不造任务轮次、不调步骤报告**（diff 即简报）。
- 事件：`EVENT_PARAM_SCANNING`（scan SSE）、`EVENT_PARAM_APPLYING`（apply SSE
  开头，随后复用 compile_start/fix_start/verify_result 词表）。
- 路由：`POST /api/tasks/params/scan`（SSE：param_scanning → param_result →
  done，done 带 {params}）、`POST /api/tasks/params/apply`（SSE：param_applying →
  compile_start → fix_start → verify_result → done，done 带 {status, backup_id,
  compile, main_diff, message}）、`POST /api/tasks/params/read`（同步
  {params: [...valid 标志...]}——读现 main.c 校验每参数 anchor 是否仍在，给
  `valid` 布尔，前端失效行禁用）。
- 新文件 `src/contest_generator/params.py`（ParamItem/ParamList/读写/
  build_params/apply_param_change；from task_progress import TaskError 防环——
  task_progress 不 import params）。`llm.py` 新协议 scan_params（Protocol /
  DeepSeek impl / RoutingLLM passthrough remote；llm import params 的
  ParamList/build_params）。
- 前端：新 `fx/params.js` 纯函数模块（paramListHTML / paramResultHTML /
  paramEmptyHTML 等）+ `ui/params.js`（scan/apply SSE + 委托）；挂 tasks-box
  新 card-group「⚙️ 参数速调」（btn-params-scan / params-status / params-grid /
  params-msg / params-result）；结果面板烧录行 uid="params"（flashPanelHTML 复用）。
- 事件说明文案：scan 状态「AI 正在识别可调参数…」；apply 状态「正在改值并编译…」。

## 测试决策

- `tests/test_params.py`：build_params 域判决（缺字段拒 / anchor 不在 main_c 拒 /
  old_value 在 anchor 出现多次拒 / 宽松字段 / 空参数表合法）/ 读写 roundtrip 与
  损坏 / apply_param_change 确定性（单处替换、锚失效、多出现、new_value 校验）/
  端点三路由（scan SSE 事件序列含 param_scanning/param_result / apply 复用编译
  词表 / read 带 valid）。
- `tests/test_llm.py`：scan_params 解析（字段校验 / anchor 硬校验触发重试 /
  RoutingLLM 走 remote）；PROTOCOL_METHOD_NAMES + 协议方法清单 + remote.calls 期望。
- `tests/fakes.py`：FakeLLM.scan_params（固定返回 + scan_params_calls 记录）+
  RecordingLLM 同步。
- JS：`tests/js/params.test.mjs`（paramListHTML 渲染/失效行禁用/输入框默认值/
  paramResultHTML diff+烧录行）；fx-guard 登记 fx/params.js 新导出。
- 全量 pytest + JS + 语言检查；双轴评审（standards + spec）逐工单。

## 范围外

- 参数与任务联动（参数所属任务、改值后 needs_redo）——本期独立通道。
- 参数持久化到生成流程 / 反推（骨架生成时的参数表）。
- 多参数批量应用（本期单参数逐条应用；批量 = 前端循环，后端不提供批量）。
- 非数值参数（结构开关 / 字符串）——不识别。
- 自动烧录（改值后手动点烧录）。
