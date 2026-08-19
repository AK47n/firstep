# 02 — 扩本地组：澄清 / 简介校验 / 归档判定 转本地（3 → 6）

**What to build:** 配置了本地端点后，澄清（clarify）、简介一致性校验
（validate_module_description）、归档判定（reference_judge_archivable）三个调用
自动走本地模型——格式障碍（围栏）已被 01 移除，这三个 spike 已验证内容合理，
可安全转本地；其余调用仍走 DeepSeek。

**Blocked by:** 01（新方法依赖剥围栏才能稳定解析）

**Status:** resolved

## 实施备注（2026-08-17）

- llm.py：`LOCAL_LLM_METHODS` 3 → 6（+clarify / validate_module_description /
  reference_judge_archivable），常量注释 / `RoutingLLM` 类注释 / `_local_call`
  注释同步；三个新方法从 `_remote` 直通改走 `_local_call`（与三文本摘要同款
  `lambda delegate` 包装，失联大声失败共用原语）。`_delegate` 读常量派发零改动，
  扩集合即扩派发。
- test_llm.py：`test_routing_llm_routes_local_methods_to_local_and_rest_to_remote`
  显式列表更新（local 6 / remote 7）；每新方法一条 fake 记录派发用例（clarify /
  validate_module_description / reference_judge_archivable，remote 零调用断言）；
  新增 `test_unexpanded_methods_stay_remote`（select_modules / 骨架 / smoke / fix /
  distill / topic_split / topic_extract_number 仍落 remote + local 零调用断言）；
  「落 local 的方法集 = 常量」行为断言（`test_local_llm_methods_constant_matches_
  routing_dispatch`）扫全部协议方法对照常量，扩集合自动随动，零改动即绿。
- 真机复核（验收项，Ollama 在跑，qwen2.5-coder:7b-instruct）：probe 脚本
  `.scratch/local-llm-json-group/recheck-real-local.py`（本地端点配置 → build_llm
  返回 RoutingLLM）真实跑三次：澄清 → 0 疑问空元组、简介校验 → ValidationResult
  （consistent=False，7B 判定为内容质量问题非解析失败，严格解析本身可用）、
  归档判定 → 空元组——均经严格解析后输出可用，_unwrap_json_fence 剥围栏正常。
- 全量 pytest 1831 绿 + mypy src 47 文件干净。
- code-review 双轴：Standards 零违规（仅两条不具行动价值的重复性判例）；Spec
  验收 1-3 全实现、无越界（不碰剥围栏 / config / webapp / 前端）。

## 验收

- [x] `LOCAL_LLM_METHODS` 由 3 → 6：+clarify / validate_module_description /
      reference_judge_archivable。
- [x] 派发更新：「落 local 的方法集 = 常量」行为断言（02 已建）随集合更新；
      每个新方法一条 fake 记录派发用例（落 local）。
- [x] 未扩方法仍落 remote 断言：select_modules / generate_main_skeleton /
      generate_smoke_main / fix_compile_errors / distill_master /
      topic_split_topics / topic_extract_number。
- [x] 真机复核：配置本地端点，真实跑一次澄清 + 简介校验 + 归档判定，输出
      （经严格解析后）可用——用本地真实模型验证，不是假件。
- [x] 全量 pytest + mypy 绿。

## 文件边界

- llm.py：`LOCAL_LLM_METHODS` 常量扩充（一处）；`RoutingLLM` 类注释同步。
- 测试：test_llm.py 派发断言更新 + 新增用例。
- 不动剥围栏（01 的边界）、不动 config、不动 webapp、不动前端。
