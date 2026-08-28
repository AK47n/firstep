# 工单 01：参数识别 + 应用后端（param-tune/01）

Status: resolved

## 目标

实现 spec 后端全链路：params.py（ParamItem/ParamList/读写/build_params/
apply_param_change）、llm.scan_params 新协议（Protocol/DeepSeek/RoutingLLM
passthrough）、run_param_scan / run_param_apply 编排、webapp 三路由、events
两事件、fakes/测试。

## 交付

- 新 `src/contest_generator/params.py`：PARAMS_FILENAME=".contest_params.json"、
  PARAMS_VERSION=1；ParamItem{name,label,old_value,anchor,unit="",range_hint=""}
  frozen + to_dict；ParamList{version,generated_at,params:tuple}；
  empty_params/load_params_file（无文件=None；坏 JSON→TaskError「参数表 …损坏」；
  非对象→「必须是 JSON 对象」）/read_params/write_params（原子 .tmp→replace）；
  build_params(raw, main_c) 域判决——dict {"params":[...]}；条目 name/label/
  old_value/anchor 非空 str、anchor 必须 in main_c、anchor 内 old_value 恰好
  出现 1 次（不满足 → TaskError）；unit/range_hint 宽松；空参数表合法；
  apply_param_change(main_c, param, new_value) 纯函数——anchor 不在 main_c →
  TaskError「参数锚已失效（main.c 可能被改动），请重新识别参数」；new_value
  空/超 64 字符 → TaskError；anchor 内 replace(old_value, new_value, 1)。
  from task_progress import TaskError（防环）。
- `llm.py`：TASK_PARAM_SYSTEM_PROMPT（识别 main.c 数值类可调参数——阈值/速度/
  PID 系数/延时/占空比#define 与初始化赋值；每参数给 name/label/old_value 原文/
  anchor（声明所在行原文，逐字节存在且 old_value 只出现一次）/unit/range_hint；
  不列结构开关/字符串/计算表达式；JSON {"params":[...]}）；Protocol.scan_params(
  main_c, module_interfaces) -> ParamList；DeepSeek impl（json_mode；parse =
  build_params，TaskError→LLMError 重试；operation="scan_params"，label=
  "参数识别"）；RoutingLLM passthrough remote；_param_scan_user_prompt(main_c,
  interfaces)（SKELETON_INTERFACES_HEADING + interfaces + 当前 main.c）。
- `task_progress.py` 不动（无 Task 变更）。新编排函数放 params.py 还是 webapp？
  —— 放 params.py 域层：run_param_scan(*, llm, main_c, module_interfaces,
  output_dir, emit) -> ParamList（emit EVENT_PARAM_SCANNING → llm.scan_params →
  build_params → write_params）与 run_param_apply(*, param, new_value, main_c,
  output_dir, work_root, platform, module_slugs, uv4_override, make_override,
  emit) -> dict（apply_param_change → backup_tree(revise_backup_root) → 写盘 →
  main_diff → verify_compile_tail(subject="参数修改") → {**result}；emit
  EVENT_PARAM_APPLYING 开头）。注意 params.py import deepen 的
  verify_compile_tail/main_diff + revision 的 backup_tree/revise_backup_root
  （检查环：deepen/revision 不 import params）。
- `events.py`：EVENT_PARAM_SCANNING="param_scanning" / EVENT_PARAM_APPLYING=
  "param_applying"（注释序列：scan = param_scanning→param_result→done；apply =
  param_applying→compile_start→fix_start→verify_result→done）。
- `webapp.py`：POST /api/tasks/params/scan（SSE；实参 = 读 .contest_context.json
  装配 main_c/module_interfaces，同 tasks 执行；done 带 {"params"}）；POST
  /api/tasks/params/apply（SSE；{output_dir, name, value}——name 从
  read_params 找、找不到 400；done 带 status/backup_id/compile/main_diff/
  message）；POST /api/tasks/params/read（同步；读当前 main_c 逐参校验
  anchor → {params: [{...原字段, valid}]}，无文件 = 空列表不 400）。
- `tests/fakes.py`：FakeLLM __init__ 加 param_list 参数（默认 ParamList 含
  THRESHOLD 一条：anchor="#define THRESHOLD 800"，old_value="800"）+
  scan_params_calls list[(main_c, interfaces tuple)] + scan_params 方法；
  RecordingLLM 同步（固定返回）。
- `tests/test_params.py`：build_params 域判决（缺失字段/anchor 不在/出现多次/
  宽松/空表）；读写 roundtrip + 坏 JSON + 非对象；apply_param_change（单处
  替换/锚失效/多出现校验/new_value 校验/替换后其余文本不变）；端点半流程
  （scan SSE 序列 + params 落盘 / apply 复用 verify 词表 + 备份回滚可用 /
  read valid 标志 / 404 400 分支）。
- `tests/test_llm.py`：scan_params 解析（成功/锚硬校验触发 _retry_parse 重试
  后成功/路由到 remote）；PROTOCOL_METHOD_NAMES / _call_all_protocol_methods /
  remote.calls 期望加 "scan_params"。
- 双轴评审通过 + 全量 pytest 绿后提交（中文提交信息，spec+issues 随提）。

## 验收

1. pytest 全量绿（新增 ±20 测试）；py_compile 通过。
2. 三路由行为符合 spec；apply 零 LLM 调用（FakeLLM 无 apply 方法）。
3. 双轴评审无硬违规。
